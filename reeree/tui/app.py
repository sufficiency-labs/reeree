"""Main Textual application — the living document."""

import logging
from datetime import datetime
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


def _setup_file_logger(project_dir: Path) -> logging.Logger:
    """Set up a file logger at .reeree/session.log."""
    log_dir = project_dir / ".reeree"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "session.log"

    logger = logging.getLogger("reeree")
    logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    logger.handlers.clear()

    fh = logging.FileHandler(log_file, mode="a")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(fh)

    logger.info("=== Session started ===")
    return logger


class PlanEditor(TextArea):
    """The plan document — a TextArea with vim-style modal editing.

    NORMAL mode: read-only, hjkl nav, : for commands, i to edit
    INSERT mode: full editing, Escape returns to NORMAL
    """

    vim_mode = reactive("NORMAL")

    def __init__(self, plan: Plan | None = None, **kwargs):
        try:
            super().__init__(
                language="markdown",
                theme="monokai",
                show_line_numbers=True,
                read_only=True,  # Start in NORMAL mode
                **kwargs,
            )
        except Exception:
            super().__init__(
                theme="monokai",
                show_line_numbers=True,
                read_only=True,
                **kwargs,
            )
        if plan:
            self.load_plan(plan)

    def load_plan(self, plan: Plan) -> None:
        """Load a plan into the editor."""
        was_readonly = self.read_only
        self.read_only = False
        self.text = plan.to_markdown()
        self.read_only = was_readonly

    def get_plan(self) -> Plan:
        """Parse the current editor content as a Plan."""
        return Plan.from_markdown(self.text)

    def update_step_status(self, step_index: int, status: str, commit_hash: str | None = None) -> None:
        """Update a step's status without disrupting the user's cursor."""
        plan = self.get_plan()
        if 0 <= step_index < len(plan.steps):
            plan.steps[step_index].status = status
            if commit_hash:
                plan.steps[step_index].commit_hash = commit_hash
            cursor = self.cursor_location
            was_readonly = self.read_only
            self.read_only = False
            self.text = plan.to_markdown()
            self.read_only = was_readonly
            try:
                self.cursor_location = cursor
            except Exception:
                pass

    def _enter_insert_mode(self) -> None:
        """Switch to INSERT mode — editable."""
        self.read_only = False
        self.vim_mode = "INSERT"
        app = self.app
        if isinstance(app, ReereeApp):
            app.query_one("#status-bar", StatusBar).mode = "INSERT"
            app._log.debug("Mode: INSERT")

    def _enter_normal_mode(self) -> None:
        """Switch to NORMAL mode — read-only, commands work."""
        self.read_only = True
        self.vim_mode = "NORMAL"
        app = self.app
        if isinstance(app, ReereeApp):
            app.query_one("#status-bar", StatusBar).mode = "NORMAL"
            app._log.debug("Mode: NORMAL")

    def on_key(self, event: events.Key) -> None:
        if self.vim_mode == "NORMAL":
            # NORMAL mode keybindings
            if event.key == "i":
                self._enter_insert_mode()
                event.prevent_default()
                event.stop()
            elif event.key == "a":
                self._enter_insert_mode()
                # Move cursor right one (append)
                event.prevent_default()
                event.stop()
            elif event.key == "o":
                # Open line below
                self._enter_insert_mode()
                self.action_cursor_line_end()
                self.read_only = False
                self.insert("\n")
                event.prevent_default()
                event.stop()
            elif event.key == "colon":
                # Enter command mode
                app = self.app
                if isinstance(app, ReereeApp):
                    app.action_command_mode()
                event.prevent_default()
                event.stop()
            elif event.key == "j":
                self.action_cursor_down()
                event.prevent_default()
                event.stop()
            elif event.key == "k":
                self.action_cursor_up()
                event.prevent_default()
                event.stop()
            elif event.key == "h":
                self.action_cursor_left()
                event.prevent_default()
                event.stop()
            elif event.key == "l":
                self.action_cursor_right()
                event.prevent_default()
                event.stop()
            elif event.key == "g":
                # gg = go to top (simplified: single g goes to top)
                self.action_cursor_line_start()
                event.prevent_default()
                event.stop()
            elif event.key == "G":
                self.action_cursor_line_end()
                event.prevent_default()
                event.stop()
            elif event.key == "tab":
                # Cycle focus to side panel
                app = self.app
                if isinstance(app, ReereeApp):
                    app._focus_next_pane()
                event.prevent_default()
                event.stop()

        elif self.vim_mode == "INSERT":
            if event.key == "escape":
                self._enter_normal_mode()
                event.prevent_default()
                event.stop()


class DaemonLog(RichLog):
    """Log pane for a daemon's execution stream."""

    def __init__(self, daemon_id: int, **kwargs):
        super().__init__(
            highlight=True,
            markup=True,
            wrap=True,
            id=f"daemon-{daemon_id}",
            **kwargs,
        )
        self.daemon_id = daemon_id
        self.write(f"[bold]Daemon {daemon_id}[/bold] — idle")


class FileViewer(TextArea):
    """Read-only file viewer pane."""

    def __init__(self, file_path: Path, **kwargs):
        content = ""
        if file_path.exists():
            content = file_path.read_text()
        lang_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".md": "markdown", ".json": "json", ".yaml": "yaml",
            ".yml": "yaml", ".sh": "bash", ".rs": "rust", ".go": "go",
            ".toml": "toml", ".html": "html", ".css": "css",
        }
        lang = lang_map.get(file_path.suffix, None)
        try:
            super().__init__(
                content,
                language=lang,
                theme="monokai",
                read_only=True,
                show_line_numbers=True,
                id=f"file-{file_path.name}",
                **kwargs,
            )
        except Exception:
            super().__init__(
                content,
                theme="monokai",
                read_only=True,
                show_line_numbers=True,
                id=f"file-{file_path.name}",
                **kwargs,
            )


class StatusBar(Static):
    """Bottom status bar — mode, daemon count, progress."""

    mode = reactive("NORMAL")
    daemon_count = reactive(0)
    active_daemons = reactive(0)
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
        daemon_str = f"{self.active_daemons} active" if self.active_daemons else "idle"
        return f" [{color}]{self.mode}[/{color}]  |  daemons: {daemon_str}  |  progress: {progress_str}  |  [dim]i=edit  :=cmd  Tab/^W=pane  :help[/dim]"


class CommandInput(TextArea):
    """Vim-style command bar. Activated with : in normal mode."""

    def __init__(self, **kwargs):
        super().__init__(
            "",
            id="command-input",
            **kwargs,
        )
        self.styles.height = 1
        self.display = False


class ReereeApp(App):
    """The reeree application — a living markdown document with daemons."""

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
    DaemonLog {
        height: 1fr;
        border: solid $primary;
    }
    FileViewer {
        height: 1fr;
        border: solid $secondary;
    }
    """

    BINDINGS = [
        Binding("ctrl+w", "focus_side", "Focus side panel", show=False),
    ]

    def __init__(self, project_dir: Path, config: Config, plan: Plan | None = None):
        super().__init__()
        self.project_dir = project_dir
        self.config = config
        self.plan = plan or Plan(intent="", steps=[])
        self._daemons: dict[int, dict] = {}
        self._next_daemon_id = 1
        self._command_buffer = ""
        self._log = _setup_file_logger(project_dir)
        self._log.info(f"Project: {project_dir}")
        self._log.info(f"Model: {config.model}")
        self._log.info(f"Plan: {len(self.plan.steps)} steps — {self.plan.intent!r}")

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
        active = sum(1 for w in self._daemons.values() if w.get("status") == "active")
        status.active_daemons = active
        status.daemon_count = len(self._daemons)

    def action_command_mode(self) -> None:
        """Enter command mode (vim : )."""
        self._log.debug("Mode: COMMAND")
        status = self.query_one("#status-bar", StatusBar)
        status.mode = "COMMAND"

        async def handle_command(cmd: str) -> None:
            status.mode = "NORMAL"
            if cmd:
                self._log.info(f"Command: :{cmd}")
                await self.execute_command(cmd)

        self.push_screen(CommandScreen(), callback=lambda cmd: self.call_later(handle_command, cmd))

    def action_focus_side(self) -> None:
        """Toggle focus between plan editor and side panel."""
        self._focus_next_pane()

    def _focus_next_pane(self) -> None:
        """Cycle focus: plan editor → side panel → plan editor."""
        panel = self.query_one("#side-panel")
        editor = self.query_one("#plan-editor", PlanEditor)
        side_content = self.query_one("#side-content", RichLog)

        if panel.has_class("visible"):
            if editor.has_focus:
                side_content.focus()
            else:
                editor.focus()
        # If side panel not visible, stay on editor

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
            await self._dispatch_daemons()
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
            self._show_daemon_log(args)
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
            self._pause_daemon(args)
        elif command == "kill" and args:
            self._kill_daemon(args)
        elif command == "close":
            self.query_one("#side-panel").remove_class("visible")
        elif command == "help":
            self._show_help()
        else:
            self.notify(f"Unknown command: {command}", severity="error")

    def _show_help(self) -> None:
        """Show command reference."""
        self.show_side_panel(
            "NORMAL MODE:\n"
            "  i        Enter INSERT mode\n"
            "  :        Enter COMMAND mode\n"
            "  hjkl     Navigate\n"
            "  Esc      Return to NORMAL from INSERT\n"
            "\n"
            "COMMANDS:\n"
            "  :go              Dispatch pending steps\n"
            "  :add \"desc\"      Add a step\n"
            "  :del N           Delete step N\n"
            "  :move N M        Move step N to position M\n"
            "  :diff [N]        Show diff for step N\n"
            "  :log [N]         Show daemon N log\n"
            "  :file path       View a file\n"
            "  :undo [N]        Revert last step\n"
            "  :set key value   Set config (model, autonomy)\n"
            "  :propagate       Check coherence on linked docs\n"
            "  :cohere d1 d2    Check coherence across docs\n"
            "  :w               Save plan\n"
            "  :q               Quit\n"
            "  :wq              Save and quit\n"
            "  :help            This help\n"
            "  Tab / Ctrl+W     Cycle focus between panes\n"
            "  :close           Close side panel\n",
            title="Help",
        )

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
                from ..executor import run_shell
                result = run_shell("git diff HEAD~1 HEAD", self.project_dir)
                self.show_side_panel(result.output or "No diff", title="Last diff")
        except (ValueError, IndexError):
            self.notify("Usage: :diff [N]", severity="warning")

    def _show_daemon_log(self, daemon_str: str) -> None:
        """Show a daemon's execution log."""
        try:
            wid = int(daemon_str) if daemon_str else 1
            if wid in self._daemons:
                log = self._daemons[wid].get("log", "No log yet")
                self.show_side_panel(log, title=f"Daemon {wid}")
            else:
                self.notify(f"No daemon {wid}", severity="warning")
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

    async def _dispatch_daemons(self) -> None:
        """Dispatch daemons for pending steps."""
        editor = self.query_one("#plan-editor", PlanEditor)
        self.plan = editor.get_plan()

        pending = self.plan.dispatchable_steps
        if not pending:
            self._log.info("Dispatch: no pending steps")
            self.notify("No pending steps to dispatch")
            return

        self._log.info(f"Dispatch: {len(pending)} pending, dispatching up to 2")
        for idx, step in pending[:2]:  # Max 2 parallel for POC
            daemon_id = self._next_daemon_id
            self._next_daemon_id += 1
            step.status = "active"
            step.daemon_id = daemon_id
            self._daemons[daemon_id] = {"status": "active", "step_index": idx, "log": ""}
            editor.update_step_status(idx, "active")
            self._update_status()
            self._log.info(f"Daemon {daemon_id} dispatched: step {idx+1} — {step.description}")
            self.notify(f"Daemon {daemon_id}: {step.description[:50]}")

            self._run_daemon(daemon_id, step, idx)

    async def _run_daemon_task(self, daemon_id: int, step, step_index: int) -> None:
        """Execute a daemon and update status when done."""
        from ..daemon_executor import dispatch_step
        try:
            result = await dispatch_step(
                step=step,
                step_index=step_index,
                project_dir=self.project_dir,
                config=self.config,
                on_log=lambda msg, did=daemon_id: self._daemon_log(did, msg),
            )
            editor = self.query_one("#plan-editor", PlanEditor)
            status = result.get("status", "failed")
            commit_hash = result.get("commit_hash")

            if status == "done":
                editor.update_step_status(step_index, "done", commit_hash)
                self.plan.steps[step_index].status = "done"
                self.plan.steps[step_index].commit_hash = commit_hash
                self._save_plan()
                self._log.info(f"Daemon {daemon_id} DONE: {result.get('summary', '')} [commit: {commit_hash}]")
                self.notify(f"Daemon {daemon_id} done: {result.get('summary', '')[:50]}")
            else:
                editor.update_step_status(step_index, "failed")
                self.plan.steps[step_index].status = "failed"
                self.plan.steps[step_index].error = result.get("error", "unknown")
                self._save_plan()
                self._log.error(f"Daemon {daemon_id} FAILED: {result.get('error', '')}")
                self.notify(f"Daemon {daemon_id} failed: {result.get('error', '')[:50]}", severity="error")

            self._daemons[daemon_id]["status"] = status
            self._update_status()

        except Exception as e:
            self._daemon_log(daemon_id, f"EXCEPTION: {e}")
            self._daemons[daemon_id]["status"] = "failed"
            self._log.exception(f"Daemon {daemon_id} EXCEPTION: {e}")
            self.notify(f"Daemon {daemon_id} error: {e}", severity="error")
            self._update_status()

    def _run_daemon(self, daemon_id: int, step, step_index: int) -> None:
        """Launch a daemon task."""
        import asyncio
        asyncio.ensure_future(self._run_daemon_task(daemon_id, step, step_index))

    def _daemon_log(self, daemon_id: int, message: str) -> None:
        """Append to a daemon's log."""
        if daemon_id in self._daemons:
            self._daemons[daemon_id]["log"] += message + "\n"
        self._log.debug(f"[daemon-{daemon_id}] {message}")

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
        self.notify("Propagate: dispatching coherence daemons on linked docs...")
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
        self.show_side_panel(
            f"Cohere checks coherence across:\n" +
            "\n".join(f"  - {d}" for d in docs) +
            "\n\nNot yet implemented — coming soon.",
            title="Cohere",
        )

    def _pause_daemon(self, daemon_str: str) -> None:
        self.notify("Pause: not yet implemented")

    def _kill_daemon(self, daemon_str: str) -> None:
        self.notify("Kill daemon: not yet implemented")


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
