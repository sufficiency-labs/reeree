"""Main Textual application — the living document."""

from pathlib import Path
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, Static, TextArea, Input, RichLog
from textual.reactive import reactive
from textual import events, on

from ..config import Config
from ..plan import Plan


class PlanEditor(TextArea):
    """The plan document — a TextArea with plan-aware rendering.

    This is the primary interface. The user edits markdown.
    Roombas read and update the same content.
    """

    BINDINGS = [
        Binding("escape", "normal_mode", "Normal mode", show=False),
    ]

    def __init__(self, plan: Plan | None = None, **kwargs):
        super().__init__(
            language="markdown",
            theme="monokai",
            show_line_numbers=True,
            **kwargs,
        )
        if plan:
            self.load_plan(plan)

    def load_plan(self, plan: Plan) -> None:
        """Load a plan into the editor."""
        self.text = plan.to_markdown()

    def get_plan(self) -> Plan:
        """Parse the current editor content as a Plan."""
        return Plan.from_markdown(self.text)

    def update_step_status(self, step_index: int, status: str, commit_hash: str | None = None) -> None:
        """Update a step's status in the document without disrupting the user's cursor."""
        plan = self.get_plan()
        if 0 <= step_index < len(plan.steps):
            plan.steps[step_index].status = status
            if commit_hash:
                plan.steps[step_index].commit_hash = commit_hash
            # Preserve cursor position
            cursor = self.cursor_location
            self.text = plan.to_markdown()
            try:
                self.cursor_location = cursor
            except Exception:
                pass


class WorkerLog(RichLog):
    """Log pane for a worker's execution stream."""

    def __init__(self, worker_id: int, **kwargs):
        super().__init__(
            highlight=True,
            markup=True,
            wrap=True,
            id=f"worker-{worker_id}",
            **kwargs,
        )
        self.worker_id = worker_id
        self.write(f"[bold]Worker {worker_id}[/bold] — idle")


class FileViewer(TextArea):
    """Read-only file viewer pane."""

    def __init__(self, file_path: Path, **kwargs):
        content = ""
        if file_path.exists():
            content = file_path.read_text()
        # Guess language from extension
        lang_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".md": "markdown", ".json": "json", ".yaml": "yaml",
            ".yml": "yaml", ".sh": "bash", ".rs": "rust", ".go": "go",
            ".toml": "toml", ".html": "html", ".css": "css",
        }
        lang = lang_map.get(file_path.suffix, None)
        super().__init__(
            content,
            language=lang,
            theme="monokai",
            read_only=True,
            show_line_numbers=True,
            id=f"file-{file_path.name}",
            **kwargs,
        )


class StatusBar(Static):
    """Bottom status bar — mode, worker count, progress."""

    mode = reactive("NORMAL")
    worker_count = reactive(0)
    active_workers = reactive(0)
    progress = reactive((0, 0))

    def render(self) -> str:
        done, total = self.progress
        mode_colors = {
            "NORMAL": "bold green",
            "INSERT": "bold yellow",
            "COMMAND": "bold cyan",
        }
        color = mode_colors.get(self.mode, "bold white")
        progress_str = f"{done}/{total}" if total > 0 else "no plan"
        worker_str = f"{self.active_workers} active" if self.active_workers else "idle"
        return f" [{color}]{self.mode}[/{color}]  |  workers: {worker_str}  |  progress: {progress_str}"


class CommandInput(TextArea):
    """Vim-style command bar. Activated with : in normal mode."""

    def __init__(self, **kwargs):
        super().__init__(
            "",
            id="command-input",
            **kwargs,
        )
        self.styles.height = 1
        self.display = False  # Hidden until : pressed


class ReereeApp(App):
    """The reeree application — a living markdown document with roombas."""

    TITLE = "reeree"
    CSS = """
    #plan-editor {
        width: 1fr;
    }
    #side-panel {
        width: 45%;
        display: none;
    }
    #side-panel.visible {
        display: block;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
    }
    #command-bar {
        dock: bottom;
        height: 1;
        background: $primary-background;
    }
    #command-bar.visible {
        display: block;
    }
    WorkerLog {
        height: 1fr;
        border: solid $primary;
    }
    FileViewer {
        height: 1fr;
        border: solid $secondary;
    }
    """

    BINDINGS = [
        Binding("colon", "command_mode", "Command mode", show=False),
        Binding("ctrl+w", "close_split", "Close split", show=False),
    ]

    def __init__(self, project_dir: Path, config: Config, plan: Plan | None = None):
        super().__init__()
        self.project_dir = project_dir
        self.config = config
        self.plan = plan or Plan(intent="", steps=[])
        self._workers: dict[int, dict] = {}
        self._next_worker_id = 1
        self._command_buffer = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield PlanEditor(self.plan, id="plan-editor")
            with Vertical(id="side-panel"):
                yield RichLog(id="side-content", highlight=True, markup=True, wrap=True)
        yield StatusBar(id="status-bar")
        yield Static(":", id="command-bar", classes="")

    def on_mount(self) -> None:
        """Focus the plan editor on start."""
        self.query_one("#plan-editor", PlanEditor).focus()
        self._update_status()

    def _update_status(self) -> None:
        """Update the status bar."""
        status = self.query_one("#status-bar", StatusBar)
        if self.plan.steps:
            status.progress = self.plan.progress
        active = sum(1 for w in self._workers.values() if w.get("status") == "active")
        status.active_workers = active
        status.worker_count = len(self._workers)

    def action_command_mode(self) -> None:
        """Enter command mode (vim : )."""
        status = self.query_one("#status-bar", StatusBar)
        status.mode = "COMMAND"

        async def handle_command(cmd: str) -> None:
            status.mode = "NORMAL"
            if cmd:
                await self.execute_command(cmd)

        self.push_screen(CommandScreen(), callback=lambda cmd: self.call_later(handle_command, cmd))

    def action_close_split(self) -> None:
        """Close the side panel."""
        panel = self.query_one("#side-panel")
        panel.remove_class("visible")

    def show_side_panel(self, content: str, title: str = "") -> None:
        """Show content in the side split pane."""
        panel = self.query_one("#side-panel")
        panel.add_class("visible")
        log = self.query_one("#side-content", RichLog)
        log.clear()
        if title:
            log.write(f"[bold]{title}[/bold]\n")
        log.write(content)

    def show_file(self, path: str) -> None:
        """Open a file in the side panel."""
        full_path = self.project_dir / path
        if full_path.exists():
            content = full_path.read_text()
            self.show_side_panel(content, title=path)
        else:
            self.notify(f"File not found: {path}", severity="error")

    async def execute_command(self, cmd: str) -> None:
        """Execute a vim-style command."""
        parts = cmd.strip().split(None, 1)
        if not parts:
            return

        command = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        if command in ("q", "quit"):
            self.exit()
        elif command in ("q!", "quit!"):
            self.exit()
        elif command == "w":
            self._save_plan()
            self.notify("Plan saved")
        elif command == "wq":
            self._save_plan()
            self.exit()
        elif command == "go":
            await self._dispatch_workers()
        elif command == "add":
            self._add_step(args.strip('"').strip("'"))
        elif command == "del":
            self._delete_step(args)
        elif command == "move":
            move_parts = args.split()
            if len(move_parts) == 2:
                self._move_step(move_parts[0], move_parts[1])
        elif command == "diff":
            self._show_diff(args)
        elif command == "log":
            self._show_worker_log(args)
        elif command == "file":
            self.show_file(args)
        elif command == "shell":
            self.show_side_panel("Shell not yet implemented in POC.\nUse :file or :diff for now.", title="Shell")
        elif command == "undo":
            await self._undo_step(args)
        elif command == "set":
            self._set_option(args)
        elif command == "propagate":
            await self._propagate()
        elif command == "cohere":
            await self._cohere(args)
        elif command == "pause":
            self._pause_worker(args)
        elif command == "kill" and args:
            self._kill_worker(args)
        elif command == "close":
            self.action_close_split()
        else:
            self.notify(f"Unknown command: {command}", severity="error")

    def _save_plan(self) -> None:
        """Save plan from editor to disk."""
        editor = self.query_one("#plan-editor", PlanEditor)
        self.plan = editor.get_plan()
        plan_path = self.project_dir / ".reeree" / "plan.md"
        self.plan.save(plan_path)

    def _add_step(self, description: str) -> None:
        """Add a step to the plan."""
        if not description:
            self.notify("Usage: :add \"step description\"", severity="warning")
            return
        from ..plan import Step
        self.plan.steps.append(Step(description=description))
        editor = self.query_one("#plan-editor", PlanEditor)
        editor.load_plan(self.plan)
        self._save_plan()
        self._update_status()

    def _delete_step(self, index_str: str) -> None:
        """Delete a step by number (1-indexed)."""
        try:
            idx = int(index_str) - 1
            if 0 <= idx < len(self.plan.steps):
                self.plan.steps.pop(idx)
                editor = self.query_one("#plan-editor", PlanEditor)
                editor.load_plan(self.plan)
                self._save_plan()
                self._update_status()
            else:
                self.notify(f"Step {index_str} out of range", severity="error")
        except ValueError:
            self.notify("Usage: :del N", severity="warning")

    def _move_step(self, from_str: str, to_str: str) -> None:
        """Move a step from one position to another (1-indexed)."""
        try:
            from_idx = int(from_str) - 1
            to_idx = int(to_str) - 1
            if 0 <= from_idx < len(self.plan.steps) and 0 <= to_idx < len(self.plan.steps):
                step = self.plan.steps.pop(from_idx)
                self.plan.steps.insert(to_idx, step)
                editor = self.query_one("#plan-editor", PlanEditor)
                editor.load_plan(self.plan)
                self._save_plan()
        except ValueError:
            self.notify("Usage: :move N M", severity="warning")

    def _show_diff(self, step_str: str) -> None:
        """Show git diff for a step."""
        try:
            idx = int(step_str) - 1 if step_str else -1
            if 0 <= idx < len(self.plan.steps):
                step = self.plan.steps[idx]
                if step.commit_hash:
                    from ..executor import run_shell
                    result = run_shell(f"git diff {step.commit_hash}~1 {step.commit_hash}", self.project_dir)
                    self.show_side_panel(result.output or "No diff", title=f"Diff: Step {idx + 1}")
                else:
                    self.notify("Step has no commit yet", severity="warning")
            else:
                # Show last diff
                from ..executor import run_shell
                result = run_shell("git diff HEAD~1 HEAD", self.project_dir)
                self.show_side_panel(result.output or "No diff", title="Last diff")
        except (ValueError, IndexError):
            self.notify("Usage: :diff [N]", severity="warning")

    def _show_worker_log(self, worker_str: str) -> None:
        """Show a worker's execution log."""
        try:
            wid = int(worker_str) if worker_str else 1
            if wid in self._workers:
                log = self._workers[wid].get("log", "No log yet")
                self.show_side_panel(log, title=f"Worker {wid}")
            else:
                self.notify(f"No worker {wid}", severity="warning")
        except ValueError:
            self.notify("Usage: :log [N]", severity="warning")

    def _set_option(self, args: str) -> None:
        """Set a configuration option."""
        parts = args.split(None, 1)
        if len(parts) != 2:
            self.notify("Usage: :set option value", severity="warning")
            return
        key, value = parts
        if key == "model":
            self.config.model = value
            self.notify(f"Model: {value}")
        elif key == "autonomy":
            if value in ("low", "medium", "high", "full"):
                self.config.autonomy = value
                self.notify(f"Autonomy: {value}")
            else:
                self.notify("Autonomy must be: low, medium, high, full", severity="error")
        else:
            self.notify(f"Unknown option: {key}", severity="error")

    async def _dispatch_workers(self) -> None:
        """Dispatch roombas for pending steps."""
        from ..worker import dispatch_step
        editor = self.query_one("#plan-editor", PlanEditor)
        self.plan = editor.get_plan()

        pending = self.plan.dispatchable_steps
        if not pending:
            self.notify("No pending steps to dispatch")
            return

        for idx, step in pending[:2]:  # Max 2 parallel workers for POC
            worker_id = self._next_worker_id
            self._next_worker_id += 1
            step.status = "active"
            step.worker_id = worker_id
            self._workers[worker_id] = {"status": "active", "step_index": idx, "log": ""}
            editor.update_step_status(idx, "active")
            self._update_status()
            self.notify(f"Worker {worker_id} dispatched: {step.description[:50]}")

            # Run worker as async task
            self.run_worker(
                dispatch_step(
                    step=step,
                    step_index=idx,
                    project_dir=self.project_dir,
                    config=self.config,
                    on_log=lambda msg, wid=worker_id: self._worker_log(wid, msg),
                ),
                name=f"worker-{worker_id}",
                exit_on_error=False,
            )

    def _worker_log(self, worker_id: int, message: str) -> None:
        """Append to a worker's log."""
        if worker_id in self._workers:
            self._workers[worker_id]["log"] += message + "\n"

    async def _undo_step(self, step_str: str) -> None:
        """Undo a step by reverting its git commit."""
        from ..executor import git_revert_last
        result = git_revert_last(self.project_dir)
        if result.success:
            self.notify("Reverted last step")
        else:
            self.notify(f"Revert failed: {result.output}", severity="error")

    async def _propagate(self) -> None:
        """Propagate: crawl links from current doc, check coherence."""
        self.notify("Propagate: dispatching coherence roombas on linked docs...")
        # TODO: implement propagation crawler
        self.show_side_panel(
            "Propagate crawls links from the current document and checks\n"
            "all referenced docs for coherence with your edits.\n\n"
            "Not yet implemented — coming soon.",
            title="Propagate",
        )

    async def _cohere(self, args: str) -> None:
        """Cohere: check coherence across explicit doc set."""
        docs = args.split()
        if not docs:
            self.notify("Usage: :cohere doc1.md doc2.md doc3.md", severity="warning")
            return
        self.notify(f"Cohere: checking {len(docs)} docs for consistency...")
        # TODO: implement coherence checker
        self.show_side_panel(
            f"Cohere checks coherence across:\n" +
            "\n".join(f"  - {d}" for d in docs) +
            "\n\nNot yet implemented — coming soon.",
            title="Cohere",
        )

    def _pause_worker(self, worker_str: str) -> None:
        """Pause a worker."""
        self.notify("Pause: not yet implemented")

    def _kill_worker(self, worker_str: str) -> None:
        """Kill a worker."""
        self.notify("Kill worker: not yet implemented")


class CommandScreen(ModalScreen[str]):
    """Vim-style : command input overlay."""

    DEFAULT_CSS = """
    CommandScreen {
        align: center bottom;
    }
    #cmd-container {
        dock: bottom;
        height: 1;
        width: 100%;
        background: $surface;
    }
    #cmd-input {
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="cmd-container"):
            yield Static(":", id="cmd-prefix")
            yield Input(placeholder="command", id="cmd-input")

    def on_mount(self) -> None:
        self.query_one("#cmd-input", Input).focus()

    @on(Input.Submitted, "#cmd-input")
    def on_submit(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss("")
