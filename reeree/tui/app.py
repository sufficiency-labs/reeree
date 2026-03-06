"""Main Textual application — the living document."""

import logging
import time
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
from ..daemon_registry import DaemonRegistry, DaemonKind, DaemonStatus
from ..machine_tasks import find_tasks, mark_in_progress, splice_result, MachineTask
from ..plan import Plan, StatusOverlay, StepStatusUpdate
from ..voice import VOICE
from .daemon_tree import DaemonTreeView


def _setup_file_logger(project_dir: Path) -> logging.Logger:
    """Set up a file logger at .reeree/session.log."""
    log_dir = project_dir / ".reeree"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "session.log"

    logger = logging.getLogger("reeree")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fh = logging.FileHandler(log_file, mode="a")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(fh)

    logger.info("=== Session started ===")
    return logger


class PlanEditor(TextArea):
    """The plan document — three-mode editing.

    VIEW:   Rich display, read-only. Navigate with hjkl. : for commands.
    NORMAL: YAML source, read-only. hjkl nav. i/a/o to insert. : for commands.
    INSERT: YAML source, editable. Escape returns to NORMAL.

    VIEW is the default. :edit enters NORMAL (YAML). :w in NORMAL exits back to VIEW.
    This gives full vim keybindings within the YAML editing context.
    """

    vim_mode = reactive("VIEW")

    def __init__(self, plan: Plan | None = None, **kwargs):
        try:
            super().__init__(
                language="markdown",
                theme="monokai",
                show_line_numbers=True,
                read_only=True,
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
        was_readonly = self.read_only
        self.read_only = False
        if self.vim_mode in ("NORMAL", "INSERT"):
            self.text = plan.to_yaml()
        else:
            self.text = plan.to_rich_display()
        self.read_only = was_readonly

    def get_plan(self) -> Plan:
        if self.vim_mode in ("NORMAL", "INSERT"):
            return Plan.from_yaml(self.text)
        else:
            return Plan.from_rich_display(self.text)

    def refresh_view(self, plan: Plan) -> None:
        """Re-render the plan in VIEW mode without disturbing cursor."""
        if self.vim_mode != "VIEW":
            return
        cursor = self.cursor_location
        self.read_only = False
        self.text = plan.to_rich_display()
        self.read_only = True
        try:
            self.cursor_location = cursor
        except Exception:
            pass

    def cursor_step_index(self) -> int | None:
        """Get the plan step index at the current cursor line, or None."""
        plan = self.get_plan()
        if not plan.steps:
            return None
        row, _col = self.cursor_location
        text = self.text
        lines = text.split("\n")
        if row >= len(lines):
            return None
        import re
        step_idx = -1
        for i, line in enumerate(lines):
            if i > row:
                break
            if re.match(r'\s*[✓▶–✗◌?○]\s+\d+\.', line):
                step_idx += 1
            elif re.match(r'- \[.\] Step \d+:', line):
                step_idx += 1
        return step_idx if step_idx >= 0 else None

    def enter_edit_mode(self) -> None:
        """VIEW → NORMAL: convert rich display to YAML for vim-style editing."""
        try:
            plan = self.get_plan()  # parse from rich display
            self.vim_mode = "NORMAL"
            self.read_only = True  # NORMAL = read-only (hjkl navigation)
            self.text = plan.to_yaml()  # show editable YAML
        except Exception:
            self.vim_mode = "NORMAL"
            self.read_only = True
        app = self.app
        if isinstance(app, ReereeApp):
            app.query_one("#status-bar", StatusBar).mode = "EDIT"
            app._flog.debug("Mode: EDIT (NORMAL)")

    def exit_edit_mode(self) -> None:
        """NORMAL/INSERT → VIEW: parse YAML edits, merge overlay, render rich display."""
        try:
            plan = Plan.from_yaml(self.text)  # parse YAML edits
            # Drain any daemon status updates that arrived during editing
            app = self.app
            if isinstance(app, ReereeApp) and app._status_overlay.has_pending:
                for update in app._status_overlay.drain():
                    target = plan.step_by_id(update.step_id)
                    if target:
                        update.apply(target)
                app.plan = plan  # sync back
            self.read_only = True
            self.vim_mode = "VIEW"
            self.text = plan.to_rich_display()  # back to rich display
        except Exception:
            self.read_only = True
            self.vim_mode = "VIEW"
        app = self.app
        if isinstance(app, ReereeApp):
            app.query_one("#status-bar", StatusBar).mode = "VIEW"
            app._flog.debug("Mode: VIEW")

    def _enter_insert_mode(self) -> None:
        """NORMAL → INSERT: unlock YAML for typing."""
        self.read_only = False
        self.vim_mode = "INSERT"
        app = self.app
        if isinstance(app, ReereeApp):
            app.query_one("#status-bar", StatusBar).mode = "INSERT"
            app._flog.debug("Mode: INSERT")

    def _enter_normal_mode(self) -> None:
        """INSERT → NORMAL: lock YAML, keep in YAML view for navigation."""
        self.read_only = True
        self.vim_mode = "NORMAL"
        app = self.app
        if isinstance(app, ReereeApp):
            app.query_one("#status-bar", StatusBar).mode = "EDIT"
            app._flog.debug("Mode: EDIT (NORMAL)")

    def on_key(self, event: events.Key) -> None:
        if self.vim_mode == "VIEW":
            # VIEW mode: read-only rich display, navigate + commands only
            if event.key == "colon":
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
                self.action_cursor_line_start()
                event.prevent_default()
                event.stop()
            elif event.key == "G":
                self.action_cursor_line_end()
                event.prevent_default()
                event.stop()
            elif event.key == "tab":
                app = self.app
                if isinstance(app, ReereeApp):
                    app._focus_next_pane()
                event.prevent_default()
                event.stop()
            # Block all other keys in VIEW — no accidental typing
            elif event.key not in ("escape", "ctrl+w", "ctrl+c"):
                event.prevent_default()
                event.stop()

        elif self.vim_mode == "NORMAL":
            # NORMAL mode: YAML displayed, read-only, full vim navigation
            if event.key == "i":
                self._enter_insert_mode()
                event.prevent_default()
                event.stop()
            elif event.key == "a":
                self._enter_insert_mode()
                event.prevent_default()
                event.stop()
            elif event.key == "o":
                self._enter_insert_mode()
                self.action_cursor_line_end()
                self.read_only = False
                self.insert("\n")
                event.prevent_default()
                event.stop()
            elif event.key == "colon":
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
                self.action_cursor_line_start()
                event.prevent_default()
                event.stop()
            elif event.key == "G":
                self.action_cursor_line_end()
                event.prevent_default()
                event.stop()
            elif event.key == "escape":
                # Escape in NORMAL exits back to VIEW
                self.exit_edit_mode()
                event.prevent_default()
                event.stop()
            elif event.key == "tab":
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


class StatusBar(Static):
    """Bottom status bar."""

    mode = reactive("VIEW")
    daemon_count = reactive(0)
    active_daemons = reactive(0)
    progress = reactive((0, 0))

    def render(self) -> str:
        done, total = self.progress
        mode_colors = {
            "VIEW": "bold green",
            "EDIT": "bold blue",
            "INSERT": "bold yellow",
            "COMMAND": "bold cyan",
        }
        color = mode_colors.get(self.mode, "bold white")
        progress_str = f"{done}/{total}" if total > 0 else "no plan"
        daemon_str = f"{self.active_daemons} active" if self.active_daemons else "idle"
        hints = {
            "VIEW": ":edit=edit plan  :go=dispatch  :chat=talk  :help",
            "EDIT": "i=insert  Esc=view  :w=save  :help",
            "INSERT": "Esc=normal  type to edit YAML",
            "COMMAND": "Enter=run  Esc=cancel",
        }
        hint = hints.get(self.mode, ":help")
        return f" [{color}]{self.mode}[/{color}]  |  daemons: {daemon_str}  |  progress: {progress_str}  |  [dim]{hint}[/dim]"


class FileViewer(TextArea):
    """File editor — overlays the plan editor for viewing/editing project files.

    Vim-style: opens in NORMAL mode (read-only), i to edit, :w to save,
    :q to close back to plan. :wq to save and close.
    """

    vim_mode = reactive("NORMAL")

    LANG_MAP = {
        ".py": "python", ".js": "javascript", ".ts": "javascript",
        ".md": "markdown", ".yml": "yaml", ".yaml": "yaml",
        ".json": "json", ".toml": "toml", ".sh": "bash",
        ".css": "css", ".html": "html", ".rs": "rust", ".go": "go",
    }

    def __init__(self, file_path: Path, **kwargs):
        self._file_path = file_path
        self._pending_content: str | None = None
        lang = self.LANG_MAP.get(file_path.suffix, None)
        try:
            super().__init__(
                language=lang,
                theme="monokai",
                show_line_numbers=True,
                read_only=True,
                **kwargs,
            )
        except Exception:
            super().__init__(
                theme="monokai",
                show_line_numbers=True,
                read_only=True,
                **kwargs,
            )
        # Read file content but defer loading until mounted
        if file_path.exists() and file_path != Path("/dev/null"):
            self._pending_content = file_path.read_text()

    def on_mount(self) -> None:
        """Load file content after widget is mounted in the DOM."""
        if self._pending_content is not None:
            self.load_file(self._pending_content)
            self._pending_content = None

    @property
    def file_path(self) -> Path:
        return self._file_path

    def load_file(self, content: str) -> None:
        """Load content without recursion — bypasses our text property."""
        was_readonly = self.read_only
        self.read_only = False
        super().load_text(content)
        self.read_only = was_readonly

    def on_key(self, event: events.Key) -> None:
        if self.vim_mode == "NORMAL":
            if event.key == "i":
                self.read_only = False
                self.vim_mode = "INSERT"
                app = self.app
                if isinstance(app, ReereeApp):
                    app.query_one("#status-bar", StatusBar).mode = "INSERT"
                event.prevent_default()
                event.stop()
            elif event.key == "colon":
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
                self.action_cursor_line_start()
                event.prevent_default()
                event.stop()
            elif event.key == "G":
                self.action_cursor_line_end()
                event.prevent_default()
                event.stop()
            elif event.key == "tab":
                app = self.app
                if isinstance(app, ReereeApp):
                    app._focus_next_pane()
                event.prevent_default()
                event.stop()
        elif self.vim_mode == "INSERT":
            if event.key == "escape":
                self.read_only = True
                self.vim_mode = "NORMAL"
                app = self.app
                if isinstance(app, ReereeApp):
                    app.query_one("#status-bar", StatusBar).mode = "NORMAL"
                event.prevent_default()
                event.stop()

    def save(self) -> bool:
        """Write buffer to disk. Returns True on success."""
        try:
            self._file_path.write_text(self.text)
            return True
        except Exception:
            return False


class ReereeApp(App):
    """reeree — plan on the left, execution log on the right."""

    TITLE = "reeree"
    CSS = """
    #main-layout {
        width: 100%;
        height: 1fr;
    }
    #plan-editor {
        width: 1fr;
        min-width: 30;
    }
    #file-viewer {
        width: 1fr;
        min-width: 30;
        display: none;
    }
    #file-viewer.visible {
        display: block;
    }
    #right-panel {
        width: 1fr;
        min-width: 30;
    }
    #daemon-tree {
        height: auto;
        max-height: 8;
        border-left: solid $primary;
        border-bottom: solid $primary-darken-2;
    }
    #exec-log {
        height: 1fr;
        border-left: solid $primary;
    }
    #chat-panel {
        height: auto;
        border-left: solid $secondary;
        border-top: solid $secondary;
        display: none;
    }
    #chat-panel.visible {
        display: block;
    }
    #chat-input {
        height: 3;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
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
        self._daemon_registry = DaemonRegistry()
        self._flog = _setup_file_logger(project_dir)
        self._flog.info(f"Project: {project_dir}")
        self._flog.info(f"Model: {config.model}")
        self._flog.info(f"Plan: {len(self.plan.steps)} steps — {self.plan.intent!r}")
        # Chat state — persistent message history with the executor daemon
        self._chat_messages: list[dict] = []
        self._chat_target = "executor"  # which daemon type we're chatting with
        self._chat_busy = False
        # Scope stack — context telescoping within a session
        # Each entry: (project_dir, plan, chat_messages, chat_target)
        # Daemons are NOT scoped — they're global to the session.
        # All daemon output goes to the shared exec log regardless of active scope.
        self._scope_stack: list[tuple] = []
        self._file_viewer_path: Path | None = None  # Track open file
        self._status_overlay = StatusOverlay()  # Daemon status updates buffer

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-layout"):
            yield PlanEditor(self.plan, id="plan-editor")
            yield FileViewer(Path("/dev/null"), id="file-viewer")
            with Vertical(id="right-panel"):
                yield DaemonTreeView(self._daemon_registry, id="daemon-tree")
                yield RichLog(id="exec-log", highlight=True, markup=True, wrap=True)
                with Vertical(id="chat-panel"):
                    yield Input(placeholder="chat with daemon (type 'exit' to close)", id="chat-input")
        yield StatusBar(id="status-bar")

    # Default daemon types — always available
    DAEMON_TYPES = {
        "executor": {
            "desc": "Executes plan steps — edits code, runs commands, commits",
            "always_on": False,
            "trigger": "dispatched (:w, :W, :go)",
        },
        "coherence": {
            "desc": "Checks consistency across linked documents, flags conflicts",
            "always_on": False,
            "trigger": "triggered (:cohere, :propagate, on-save)",
        },
        "watcher": {
            "desc": "Monitors project for changes, runs tests, reports breakage",
            "always_on": True,
            "trigger": "file changes in project",
        },
    }

    def on_mount(self) -> None:
        self.query_one("#plan-editor", PlanEditor).focus()
        self._update_status()

        # Startup info
        exec_log = self.query_one("#exec-log", RichLog)
        exec_log.write(f"[bold]reeree[/bold] — {self.plan.intent or 'no plan'}")
        exec_log.write(f"[dim]project: {self.project_dir}[/dim]")
        exec_log.write("")

        # Model info
        model_short = self.config.model.split("/")[-1] if "/" in self.config.model else self.config.model
        exec_log.write(f"  [bold]model:[/bold]    {model_short}")
        exec_log.write(f"  [bold]api:[/bold]      {self.config.api_base}")
        exec_log.write(f"  [bold]autonomy:[/bold] {self.config.autonomy}")
        exec_log.write(f"  [bold]context:[/bold]  {self.config.max_context_tokens:,} tokens")
        exec_log.write("")

        # Daemon types
        exec_log.write(f"  [bold]daemons:[/bold]")
        for name, info in self.DAEMON_TYPES.items():
            on_tag = "[green]always-on[/green]" if info["always_on"] else f"[dim]{info['trigger']}[/dim]"
            exec_log.write(f"    {name:12s} {info['desc']}")
            exec_log.write(f"    {'':12s} {on_tag}")
        exec_log.write("")

        # Plan summary
        if self.plan.steps:
            done, total = self.plan.progress
            exec_log.write(f"  [bold]plan:[/bold] {done}/{total} steps  |  :go to dispatch  |  :edit to edit plan  |  :help for commands")
        else:
            exec_log.write(f"  [dim]no plan — :edit to start writing, :chat to talk to executor[/dim]")
        exec_log.write("")

        # Start heartbeat timer for always-on daemons
        self._heartbeat_timer = self.set_interval(120, self._daemon_heartbeat)

        # First-run setup wizard
        if self.config.is_first_run():
            self._launch_setup()

    def _update_status(self) -> None:
        status = self.query_one("#status-bar", StatusBar)
        if self.plan.steps:
            status.progress = self.plan.progress
        status.active_daemons = self._daemon_registry.active_count
        status.daemon_count = self._daemon_registry.total_count

    def _launch_setup(self) -> None:
        """Launch setup as a chat daemon — natural language configuration.

        Opens the chat panel with a "setup" daemon target. The daemon probes
        available APIs and guides the user through configuration via conversation.
        Chat is the right interface for expressing nuanced constraints like
        "use ollama but fall back to together.ai for hard steps."
        """
        self._chat_target = "setup"
        self._chat_messages = []

        # Probe available APIs before starting the conversation
        import os
        probe_results = []
        providers = [
            ("ollama (local)", "http://localhost:11434/v1", None),
            ("together.ai", "https://api.together.xyz/v1", "TOGETHER_API_KEY"),
            ("openai", "https://api.openai.com/v1", "OPENAI_API_KEY"),
        ]
        for name, base, env_var in providers:
            key = os.environ.get(env_var, "") if env_var else ""
            if not key and env_var:
                # Check common key file locations
                key_file = {
                    "TOGETHER_API_KEY": "~/.config/together/api_key",
                    "OPENAI_API_KEY": "~/.config/openai/api_key",
                }.get(env_var, "")
                if key_file:
                    from pathlib import Path
                    kf = Path(key_file).expanduser()
                    if kf.exists():
                        key = kf.read_text().strip()
            try:
                import httpx
                headers = {"Authorization": f"Bearer {key}"} if key else {}
                resp = httpx.get(f"{base}/models", headers=headers, timeout=5.0)
                available = resp.status_code == 200
            except Exception:
                available = False
            status = "available" if available else "not detected"
            has_key = "key found" if key else "no key"
            probe_results.append(f"  {name}: {status}" + (f" ({has_key})" if env_var else ""))

        probe_summary = "\n".join(probe_results)

        # Current config state
        current = (
            f"Current config:\n"
            f"  model: {self.config.model}\n"
            f"  api_base: {self.config.api_base}\n"
            f"  api_key: {'set' if self.config.api_key else 'not set'}\n"
            f"  autonomy: {self.config.autonomy}\n"
            f"  max_context_tokens: {self.config.max_context_tokens}\n"
        )

        # Seed the conversation with probe results as context
        setup_context = (
            f"Detected providers:\n{probe_summary}\n\n{current}\n"
            f"The user wants to configure reeree. Help them set up their LLM provider, "
            f"model, autonomy level, and context budget. Ask what they need."
        )
        self._chat_messages.append({"role": "user", "content": setup_context})

        # Open chat panel
        panel = self.query_one("#chat-panel")
        panel.add_class("visible")
        chat_input = self.query_one("#chat-input", Input)
        chat_input.placeholder = "configure reeree (type 'done' when finished)"
        chat_input.focus()

        # Show probe results in exec log
        providers = " | ".join(probe_results) if probe_results else "none detected"
        self._exec_write(f"[bold]setup[/bold] detected: {providers}")
        self._exec_write("[dim]describe your preferences, type 'done' when finished[/dim]")

        # Get the LLM to respond with its opening question
        import asyncio
        asyncio.ensure_future(self._setup_respond())

    def _exec_write(self, message: str) -> None:
        """Write to the execution log (right pane) and file log."""
        try:
            exec_log = self.query_one("#exec-log", RichLog)
            exec_log.write(message)
        except Exception:
            pass
        # Strip markup for file log
        import re
        plain = re.sub(r'\[/?[^\]]*\]', '', message)
        self._flog.info(plain)

    def action_command_mode(self) -> None:
        self._flog.debug("Mode: COMMAND")
        status = self.query_one("#status-bar", StatusBar)
        status.mode = "COMMAND"

        async def handle_command(cmd: str) -> None:
            editor = self.query_one("#plan-editor", PlanEditor)
            mode_map = {"VIEW": "VIEW", "NORMAL": "EDIT", "INSERT": "INSERT"}
            status.mode = mode_map.get(editor.vim_mode, "VIEW")
            if cmd:
                self._flog.info(f"Command: :{cmd}")
                await self.execute_command(cmd)

        self.push_screen(CommandScreen(), callback=lambda cmd: self.call_later(handle_command, cmd))

    def action_focus_side(self) -> None:
        self._focus_next_pane()

    def _focus_next_pane(self) -> None:
        """Cycle focus: plan editor → exec log → chat input → plan editor."""
        editor = self.query_one("#plan-editor", PlanEditor)
        exec_log = self.query_one("#exec-log", RichLog)
        chat_panel = self.query_one("#chat-panel")

        if editor.has_focus:
            exec_log.focus()
        elif exec_log.has_focus:
            if chat_panel.has_class("visible"):
                self.query_one("#chat-input", Input).focus()
            else:
                editor.focus()
        else:
            editor.focus()

    async def execute_command(self, cmd: str) -> None:
        parts = cmd.strip().split(None, 1)
        if not parts:
            return

        command = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        # File viewer intercepts: :q closes file, :w saves file, :wq both
        if self._file_viewer_path is not None:
            if command in ("q", "quit"):
                self._close_file_viewer()
                return
            elif command in ("q!", "quit!"):
                self._close_file_viewer()
                return
            elif command == "w" and not args:
                self._save_file_viewer()
                self._process_machine_tasks_in_viewer()
                return
            elif command == "wq":
                self._save_file_viewer()
                self._close_file_viewer()
                return
            # Other commands fall through — you can :file another file,
            # :chat, :help, etc. while a file is open

        if command in ("q", "quit"):
            # In edit mode, :q exits back to view without saving
            editor = self.query_one("#plan-editor", PlanEditor)
            if editor.vim_mode in ("NORMAL", "INSERT"):
                editor.exit_edit_mode()
                self._exec_write("[dim]edit discarded[/dim]")
                return
            self._save_plan()
            self._flog.info("Quit. Plan saved.")
            self.exit()
        elif command in ("q!", "quit!"):
            editor = self.query_one("#plan-editor", PlanEditor)
            if editor.vim_mode in ("NORMAL", "INSERT"):
                editor.exit_edit_mode()
                return
            self._flog.info("Force quit.")
            self.exit()
        elif command == "w":
            # :w — save (and exit edit mode if editing)
            # In edit mode: parse YAML, save, return to VIEW
            # In view mode: just save current plan to disk
            editor = self.query_one("#plan-editor", PlanEditor)
            if editor.vim_mode in ("NORMAL", "INSERT"):
                # Parse the YAML, update self.plan, exit to VIEW, save
                try:
                    self.plan = Plan.from_yaml(editor.text)
                except Exception as e:
                    self._exec_write(f"[red]YAML parse error: {e}[/red]")
                    return
                editor.exit_edit_mode()
                self._save_plan()
                self._update_status()
                self._exec_write("plan saved")
            else:
                self._save_plan()
                self._exec_write("plan saved")
        elif command == "W":
            # :W — dispatch all pending steps
            self._save_plan()
            await self._dispatch_all()
        elif command == "wq":
            editor = self.query_one("#plan-editor", PlanEditor)
            if editor.vim_mode in ("NORMAL", "INSERT"):
                try:
                    self.plan = Plan.from_yaml(editor.text)
                except Exception:
                    pass
                editor.exit_edit_mode()
            self._save_plan()
            self.exit()
        elif command == "edit":
            # :edit — enter YAML editing mode with full vim keybindings
            editor = self.query_one("#plan-editor", PlanEditor)
            if editor.vim_mode == "VIEW":
                editor.enter_edit_mode()
                self._exec_write("[dim]editing plan (YAML) — :w to save, :q to discard, i to insert[/dim]")
            else:
                self._exec_write("[dim]already editing[/dim]")
        elif command == "go":
            # :go — the dispatch verb
            # :go          dispatch next 2 pending
            # :go all      dispatch ALL pending
            # :go N        dispatch step N
            # :go N M      dispatch steps N and M
            await self._dispatch_go(args)
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
            self._show_file(args)
        elif command == "undo":
            await self._undo_step(args)
        elif command == "set":
            self._set_option(args)
        elif command == "propagate":
            await self._propagate()
        elif command == "cohere":
            await self._cohere(args)
        elif command == "chat":
            self._toggle_chat(args)
        elif command == "close":
            self._toggle_chat_off()
        elif command == "cd":
            self._change_scope(args.strip())
        elif command == "scope":
            self._show_scope()
        elif command == "pause" and args:
            try:
                did = int(args.strip())
                if self._daemon_registry.pause(did):
                    self._exec_write(f"d{did} paused")
                else:
                    self._exec_write(f"d{did} not active")
            except ValueError:
                self.notify("Usage: :pause N", severity="warning")
        elif command == "resume" and args:
            try:
                did = int(args.strip())
                if self._daemon_registry.resume(did):
                    self._exec_write(f"d{did} resumed")
                else:
                    self._exec_write(f"d{did} not paused")
            except ValueError:
                self.notify("Usage: :resume N", severity="warning")
        elif command == "kill" and args:
            try:
                did = int(args.strip())
                if self._daemon_registry.kill(did):
                    self._exec_write(f"d{did} killed")
                else:
                    self._exec_write(f"d{did} not found")
            except ValueError:
                self.notify("Usage: :kill N", severity="warning")
        elif command == "setup":
            self._launch_setup()
        elif command == "help":
            self._show_help()
        else:
            self.notify(f"Unknown command: {command}", severity="error")

    def _show_help(self) -> None:
        self._exec_write(
            "[bold]VIEW MODE[/bold] (default — rich plan display)\n"
            "  :        Enter COMMAND mode\n"
            "  hjkl     Navigate the plan\n"
            "  Tab/^W   Cycle pane focus\n"
            "\n"
            "[bold]EDIT MODE[/bold] (via :edit — YAML with full vim)\n"
            "  i/a/o    Enter INSERT (type text)\n"
            "  Esc      INSERT→NORMAL (stop typing) or NORMAL→VIEW (exit edit)\n"
            "  hjkl     Navigate (in NORMAL)\n"
            "  :w       Save edits, return to VIEW\n"
            "  :q       Discard edits, return to VIEW\n"
            "\n"
            "[bold]COMMANDS[/bold]\n"
            "  :edit            Edit the plan (YAML, full vim keybindings)\n"
            "  :w               Save plan (or save+exit if editing)\n"
            "  :go              Dispatch next 2 pending steps\n"
            "  :go all / :W     Dispatch ALL pending steps\n"
            "  :go N            Dispatch step N\n"
            "  :add \"desc\"      Add a step\n"
            "  :del N           Delete step N\n"
            "  :move N M        Move step N to M\n"
            "  :diff [N]        Show diff for step N\n"
            "  :log [N]         Show daemon N log\n"
            "  :file path       View/edit a project file\n"
            "  :undo            Revert last step\n"
            "  :set key value   Set config (model, autonomy)\n"
            "  :chat            Chat with executor daemon\n"
            "  :chat coherence  Chat with coherence daemon\n"
            "  :cd path         Push scope to subrepo\n"
            "  :cd ..           Pop scope to parent\n"
            "  :cohere path     Run coherence check\n"
            "  :propagate       Crawl cross-references\n"
            "  :pause N         Pause daemon N\n"
            "  :resume N        Resume paused daemon N\n"
            "  :kill N          Kill daemon N (and children)\n"
            "  :setup           Re-run setup wizard\n"
            "  :q / :q! / :wq   Quit / force quit / save+quit\n"
            "  :help            This help\n"
        )

    def _change_scope(self, path: str) -> None:
        """Change execution scope — context telescoping within a session.

        :cd sandbox      Push into sandbox/, new executor context
        :cd ..            Pop back to parent scope
        :cd               Show current scope (same as :scope)

        The parent context doesn't disappear — it's on the stack.
        Daemons from the parent scope keep running.
        The new scope inherits parent CLAUDE.md context automatically
        (via context.py's _find_parent_contexts).
        """
        if not path:
            self._show_scope()
            return

        if path == "..":
            # Pop scope — return to parent
            if not self._scope_stack:
                self._exec_write("[yellow]Already at root scope[/yellow]")
                return

            # Save current scope state
            self._save_plan()

            # Restore parent scope
            parent = self._scope_stack.pop()
            (self.project_dir, self.plan,
             parent_chat, parent_target) = parent

            # Daemons are global — they keep running, keep printing to exec log.
            # Only chat and plan are scoped.
            self._chat_messages = parent_chat
            self._chat_target = parent_target

            # Reload plan in editor
            editor = self.query_one("#plan-editor", PlanEditor)
            editor.load_plan(self.plan)
            self._update_status()
            self.sub_title = str(self.project_dir.name)
            self._exec_write(f"scope: {self.project_dir}")
            self._flog.info(f"Scope popped to: {self.project_dir}")
            return

        # Push scope — descend into child directory
        new_dir = (self.project_dir / path).resolve()
        if not new_dir.exists():
            self._exec_write(f"[red]Directory not found: {path}[/red]")
            return
        if not new_dir.is_dir():
            self._exec_write(f"[red]Not a directory: {path}[/red]")
            return

        # Save current scope to stack (daemons are global, not scoped)
        self._save_plan()
        self._scope_stack.append((
            self.project_dir,
            self.plan,
            list(self._chat_messages),
            self._chat_target,
        ))

        # Switch to new scope
        self.project_dir = new_dir
        self._chat_messages = []  # Fresh chat for new scope
        self._chat_target = "executor"

        # Load plan from new scope if it exists
        new_plan_path = new_dir / ".reeree" / "plan.yaml"
        if new_plan_path.exists():
            self.plan = Plan.load(new_plan_path)
        else:
            self.plan = Plan(intent="", steps=[])

        editor = self.query_one("#plan-editor", PlanEditor)
        editor.load_plan(self.plan)
        self._update_status()
        self.sub_title = str(new_dir.name)

        # Show scope info
        scope_depth = len(self._scope_stack)
        parent_names = " > ".join(s[0].name for s in self._scope_stack)
        self._exec_write(
            f"[bold]Scope: {parent_names} > {new_dir.name}[/bold]\n"
            f"[dim]Depth: {scope_depth}  |  Parent context inherited  |  :cd .. to return[/dim]"
        )
        self._flog.info(f"Scope pushed to: {new_dir}")

    def _show_scope(self) -> None:
        """Show the current scope stack."""
        lines = [f"[bold]Scope stack:[/bold]  [dim]({self._daemon_registry.active_count} daemons running globally)[/dim]"]
        for i, (pdir, plan, _chat, _target) in enumerate(self._scope_stack):
            done, total = plan.progress if plan.steps else (0, 0)
            lines.append(
                f"  {'  ' * i}{pdir.name}/  "
                f"[dim]{done}/{total} steps[/dim]"
            )
        # Current scope
        depth = len(self._scope_stack)
        done, total = self.plan.progress if self.plan.steps else (0, 0)
        lines.append(
            f"  {'  ' * depth}[bold]{self.project_dir.name}/[/bold]  "
            f"[dim]{done}/{total} steps[/dim]  ← current"
        )
        self._exec_write("\n".join(lines))

    def _toggle_chat(self, target: str = "") -> None:
        panel = self.query_one("#chat-panel")
        if target:
            self._chat_target = target
            self._chat_messages = []  # Fresh context for new target
            self._exec_write(f"chat: {target}")
            panel.add_class("visible")
            self.query_one("#chat-input", Input).focus()
        elif panel.has_class("visible"):
            panel.remove_class("visible")
            self.query_one("#plan-editor", PlanEditor).focus()
        else:
            panel.add_class("visible")
            if not self._chat_messages:
                self._exec_write(f"[dim]chat: {self._chat_target} ('exit' to close)[/dim]")
            self.query_one("#chat-input", Input).focus()

    def _toggle_chat_off(self) -> None:
        self.query_one("#chat-panel").remove_class("visible")

    async def _daemon_heartbeat(self) -> None:
        """Periodic heartbeat — always-on daemons check for work.

        Runs every 2 minutes. Checks:
        - Are there pending coherence tasks?
        - Did any watched files change?
        - Are any active daemons stalled?
        """
        active = self._daemon_registry.active()
        if active:
            self._flog.debug(f"Heartbeat: {len(active)} active daemons")

        # Check for stalled daemons (no log output in 5+ min)
        now = time.monotonic()
        for daemon in active:
            if daemon.last_log_time > 0 and now - daemon.last_log_time > 300:
                self._exec_write(f"[yellow]d{daemon.id} stalled ({int(now - daemon.last_log_time)}s)[/yellow]")
                self._flog.warning(f"d{daemon.id} stalled {int(now - daemon.last_log_time)}s")

    @on(events.Key)
    def on_chat_escape(self, event: events.Key) -> None:
        """Escape from chat input returns focus to plan editor."""
        if event.key == "escape":
            chat_input = self.query_one("#chat-input", Input)
            if chat_input.has_focus:
                self.query_one("#plan-editor", PlanEditor).focus()
                event.prevent_default()
                event.stop()

    @on(Input.Submitted, "#chat-input")
    def on_chat_submit(self, event: Input.Submitted) -> None:
        """Handle chat input — send to daemon, responses appear in exec log."""
        msg = event.value.strip()
        if not msg:
            return
        event.input.value = ""

        # "exit" or "close" closes the chat interface
        if msg.lower() in ("exit", "close", "quit", "q"):
            self._toggle_chat_off()
            self.query_one("#plan-editor", PlanEditor).focus()
            return

        # "done" in setup mode saves config and closes
        if msg.lower() == "done" and self._chat_target == "setup":
            self._exec_write("[green]Setup complete.[/green]")
            self._toggle_chat_off()
            self.query_one("#plan-editor", PlanEditor).focus()
            self.query_one("#chat-input", Input).placeholder = "chat with daemon (type 'exit' to close)"
            return

        self._exec_write(f"> {msg}")
        self._flog.info(f"Chat [{self._chat_target}]: {msg}")

        if self._chat_busy:
            self._exec_write("[dim]Waiting for previous response...[/dim]")
            return

        # Add user message to history
        self._chat_messages.append({"role": "user", "content": msg})

        # Route to setup daemon or general chat
        import asyncio
        if self._chat_target == "setup":
            asyncio.ensure_future(self._setup_respond(msg))
        else:
            asyncio.ensure_future(self._chat_respond(msg))

    async def _setup_respond(self, user_msg: str) -> None:
        """Handle setup conversation — configure reeree via natural language.

        The setup daemon interprets the user's preferences, builds a Config,
        and saves it. Responses include ```config blocks that get applied.
        """
        from ..llm import chat_async

        self._chat_busy = True
        setup_daemon = None

        try:
            import json as _json

            system = (
                f"{VOICE}\n\n"
                "Setup daemon. Configure LLM provider, model, autonomy, context budget.\n\n"
                "When the user expresses a preference, respond with:\n"
                "1. Brief confirmation of what was understood\n"
                "2. A ```config block with the JSON configuration\n\n"
                "Config format:\n"
                "```config\n"
                '{"api_base": "https://api.together.xyz/v1", "model": "model-name", '
                '"api_key": "key-or-empty", "autonomy": "medium", "max_context_tokens": 24000}\n'
                "```\n\n"
                "Valid autonomy levels:\n"
                "  low — approve everything (safest)\n"
                "  medium — auto-approve reads, ask about writes (default)\n"
                "  high — auto-approve reads+writes, ask about shell commands\n"
                "  full — auto-approve all (fastest)\n\n"
                "Valid context budgets: 8000, 16000, 24000 (default), 32000\n\n"
                "For multi-model routing (optional), include a models and routing section:\n"
                "```config\n"
                '{"api_base": "http://localhost:11434/v1", "model": "qwen3:8b", '
                '"autonomy": "medium", "max_context_tokens": 24000,\n'
                ' "models": {"local": {"model": "qwen3:8b", "api_base": "http://localhost:11434/v1"},\n'
                '            "cloud": {"model": "Qwen/Qwen3-Coder", "api_base": "https://api.together.xyz/v1", '
                '"api_key": "..."}},\n'
                ' "routing": {"fast": "local", "coding": "local", "reasoning": "cloud"}}\n'
                "```\n\n"
                "Common setups:\n"
                "- 'use ollama' → api_base: http://localhost:11434/v1, model: whatever they have\n"
                "- 'use together.ai' → api_base: https://api.together.xyz/v1\n"
                "- 'ollama for fast, together for reasoning' → multi-model routing\n\n"
                "Rules:\n"
                "- Concise. Configuration, not a tutorial.\n"
                "- Always emit a ```config block when the user expresses a preference.\n"
                "- Ask clarifying questions only if ambiguous.\n"
                "- 'done' closes setup.\n"
            )

            setup_daemon = self._daemon_registry.spawn(
                DaemonKind.EXECUTOR, f"setup: {user_msg[:40]}",
                scope="config",
            )

            response = await chat_async(
                self._chat_messages, self.config, system=system,
            )

            self._chat_messages.append({"role": "assistant", "content": response})

            # Extract and apply ```config blocks
            import re
            config_blocks = re.findall(r'```config\s*\n(.*?)```', response, re.DOTALL)
            display_response = re.sub(r'```config\s*\n.*?```', '[config applied]', response, flags=re.DOTALL).strip()

            if config_blocks:
                for block in config_blocks:
                    try:
                        cfg_data = _json.loads(block.strip())
                        # Apply to current config
                        for key in ("api_base", "model", "api_key", "autonomy", "max_context_tokens"):
                            if key in cfg_data:
                                setattr(self.config, key, cfg_data[key])
                        # Multi-model routing
                        if "models" in cfg_data:
                            self.config.models = cfg_data["models"]
                        if "routing" in cfg_data:
                            self.config.routing = cfg_data["routing"]
                        # Save config
                        self.config.save(self.project_dir / ".reeree" / "config.json")
                        routing = f", routing: {self.config.routing}" if self.config.models else ""
                        self._exec_write(f"config saved: {self.config.model} @ {self.config.api_base}, autonomy={self.config.autonomy}{routing}")
                        self._update_status()
                    except (_json.JSONDecodeError, Exception) as e:
                        self._exec_write(f"[red]Config parse error: {e}[/red]")

            if display_response:
                self._exec_write(f"setup: {display_response}")

        except Exception as e:
            self._exec_write(f"[red]Setup error: {e}[/red]")
            self._flog.error(f"Setup error: {e}")
            if setup_daemon:
                setup_daemon.status = DaemonStatus.FAILED
                setup_daemon.error = str(e)
        finally:
            self._chat_busy = False
            if setup_daemon and setup_daemon.is_active:
                setup_daemon.status = DaemonStatus.DONE

    async def _chat_respond(self, user_msg: str) -> None:
        """Get LLM response with persistent context. Output goes to exec log.

        The executor can modify the plan by including a ```plan block in its
        response. The block contents replace the current plan markdown, the
        editor updates live, and the plan is saved to disk.
        """
        from ..llm import chat_async
        from ..context import gather_context
        from ..plan import Step, Plan

        self._chat_busy = True

        try:
            # Build system prompt with project context
            dummy_step = Step(description=user_msg)
            context = gather_context(dummy_step, self.project_dir, self.config.max_context_tokens * 4)
            plan_md = self.plan.to_markdown()

            # Daemon execution history
            daemon_history = ""
            for daemon in self._daemon_registry.all():
                if daemon.log:
                    daemon_history += f"\n--- Daemon {daemon.id} ---\n{daemon.log[-500:]}\n"

            system = (
                f"{VOICE}\n\n"
                f"Executor daemon. You execute actions AND respond conversationally.\n"
                f"ALWAYS include natural language alongside action blocks. The user reads your\n"
                f"text responses — empty responses with only action blocks are bad UX.\n"
                f"Describe what you're doing, what you found, what happened. Be concise but present.\n\n"
                f"## CRITICAL: Plan-First Workflow\n\n"
                f"Your FIRST action on any new task MUST be to update the plan. The plan is the shared "
                f"work queue between you and the user. Before executing anything:\n"
                f"1. Read the current plan (shown below)\n"
                f"2. Decompose the user's request into concrete steps\n"
                f"3. Emit a ```yaml block with the updated plan\n"
                f"4. THEN start executing steps\n\n"
                f"PRESERVE existing completed steps — never remove done items.\n\n"
                f"## Actions you can take\n\n"
                f"Update the plan (DO THIS FIRST on every new task):\n"
                f"```yaml\n"
                f"plan:\n"
                f"  intent: \"short description of what we're doing\"\n"
                f"  steps:\n"
                f"    - status: done\n"
                f"      description: \"Already completed thing\"\n"
                f"      commit: abc1234\n"
                f"    - status: active\n"
                f"      description: \"Currently executing\"\n"
                f"    - status: pending\n"
                f"      description: \"Next thing to do\"\n"
                f"      annotations:\n"
                f"        - \"files: scraper.py\"\n"
                f"        - \"done: tests pass\"\n"
                f"    - status: failed\n"
                f"      description: \"This step failed\"\n"
                f"```\n\n"
                f"Valid statuses: done, active, pending, failed\n"
                f"Annotations are optional strings for context, file hints, acceptance criteria.\n\n"
                f"Run shell commands:\n"
                f"```shell\n"
                f"python -m pytest tests/ -v\n"
                f"```\n\n"
                f"Write a file:\n"
                f"```write:path/to/file.py\n"
                f"file contents here\n"
                f"```\n\n"
                f"Edit a file (find and replace):\n"
                f"```edit:path/to/file.py\n"
                f"<<<old text>>>\n"
                f"<<<new text>>>\n"
                f"```\n\n"
                f"Read a file:\n"
                f"```read:path/to/file.py\n"
                f"```\n\n"
                f"Search for files or content:\n"
                f"```search\n"
                f"pattern: TODO|FIXME\n"
                f"glob: *.py\n"
                f"```\n\n"
                f"List directory:\n"
                f"```ls:path/to/dir\n"
                f"```\n\n"
                f"You can include MULTIPLE action blocks in one response. They execute in order.\n"
                f"After actions execute, you'll see results and can take follow-up actions.\n"
                f"This is a MULTI-TURN loop — up to 5 rounds of action→result→action.\n"
                f"ALWAYS read files before editing them. ALWAYS check git status before committing.\n\n"
                f"## Rules\n"
                f"- RESPOND CONVERSATIONALLY. Every response MUST include text the user reads.\n"
                f"  Action blocks are stripped from display — only your conversational text shows.\n"
                f"  Describe what you found, what you changed, what's next.\n"
                f"- Update the plan via ```yaml blocks (these are processed silently, not shown).\n"
                f"- If asked to run something, include ```shell block. Describe the result in text.\n"
                f"- If asked to edit code, read first, then ```edit or ```write. Summarize changes in text.\n"
                f"- Update step statuses as you work (active → done/failed).\n"
                f"- Git commit after meaningful changes.\n"
                f"- When done, update plan statuses and say DONE.\n\n"
                f"Project context:\n{context[:8000]}\n\n"
                f"Current plan:\n{plan_md}\n\n"
            )
            # Include parent scope context if we're in a child scope
            if self._scope_stack:
                parent_ctx = []
                for pdir, pplan, _chat, _target in self._scope_stack:
                    parent_ctx.append(f"Parent scope: {pdir.name}")
                    if pplan.intent:
                        parent_ctx.append(f"  Plan: {pplan.intent}")
                    claude_md = pdir / "CLAUDE.md"
                    if claude_md.exists():
                        parent_ctx.append(f"  {claude_md.read_text()[:2000]}")
                system += f"Parent context (ambient):\n{''.join(parent_ctx)[:4000]}\n\n"
            if daemon_history:
                system += f"Recent execution:\n{daemon_history[:2000]}\n"

            # Multi-turn action loop — up to 5 rounds of LLM → actions → results → LLM
            max_turns = 5
            chat_daemon = self._daemon_registry.spawn(
                DaemonKind.EXECUTOR, user_msg[:50],
                scope=str(self.project_dir.name),
            )
            for turn in range(max_turns):
                try:
                    response = await chat_async(
                        self._chat_messages, self.config, system=system,
                    )
                finally:
                    self._flog.info(f"chat turn {turn + 1}: {chat_daemon.elapsed_str}")

                # Add response to history
                self._chat_messages.append({"role": "assistant", "content": response})

                # Execute action blocks
                display_response, action_results = await self._execute_actions_from_response(response)

                # Display in exec log
                if display_response.strip():
                    self._exec_write(f"{self._chat_target}: {display_response}")

                # If no actions were taken, we're done
                if not action_results:
                    break

                # Feed results back to LLM for follow-up
                results_msg = "\n".join(action_results)
                self._chat_messages.append({"role": "user", "content": f"[Action results]\n{results_msg}"})

                # If LLM said DONE or no more action blocks expected, stop
                if "DONE" in response.upper().split("```")[-1]:
                    break

                self._flog.info(f"Chat turn {turn + 1}/{max_turns} — {len(action_results)} actions executed")

            # Keep message history manageable
            if len(self._chat_messages) > 40:
                self._chat_messages = self._chat_messages[-40:]

        except Exception as e:
            self._exec_write(f"[red]Chat error: {e}[/red]")
            self._flog.error(f"Chat error: {e}")
            if chat_daemon:
                chat_daemon.status = DaemonStatus.FAILED
                chat_daemon.error = str(e)
        finally:
            self._chat_busy = False
            if chat_daemon and chat_daemon.is_active:
                chat_daemon.status = DaemonStatus.DONE

    async def _execute_actions_from_response(self, response: str) -> tuple[str, list[str]]:
        """Parse and execute action blocks from LLM response.

        Handles: ```shell, ```write:path, ```edit:path, ```read:path, ```search, ```ls:path, ```yaml (plan), ```plan (legacy)
        Returns (display_text, action_results).
        """
        import re
        import glob as globmod
        from ..executor import run_shell, write_file, edit_file, check_autonomy, check_path_containment

        results = []

        # Find all fenced code blocks with language tags
        blocks = list(re.finditer(
            r'```(shell|write:([^\n]+)|edit:([^\n]+)|read:([^\n]+)|search|ls:([^\n]*)|yaml|plan)\n(.*?)```',
            response, re.DOTALL
        ))

        if not blocks:
            return response.strip(), results

        # Strip all action blocks from display — user sees only conversational text
        display = response
        for block in reversed(blocks):  # reverse to preserve indices
            display = display[:block.start()] + display[block.end():]
        display = display.strip()

        for block in blocks:
            tag = block.group(1)  # full tag like "shell", "write:foo.py", "read:bar.py"
            content = block.group(6).strip()  # body of the block

            if tag == "shell":
                ok, reason = check_autonomy(content, self.config.autonomy)
                if not ok:
                    self._exec_write(f"[red]Blocked: {reason}[/red]")
                    results.append(f"BLOCKED: {reason}")
                    continue
                result = run_shell(content, self.project_dir, autonomy=self.config.autonomy)
                status = "ok" if result.success else "fail"
                out_len = len(result.output) if result.output else 0
                self._exec_write(f"[dim]$ {content} → {status}" + (f" ({out_len} chars)" if out_len > 200 else "") + "[/dim]")
                self._flog.info(f"Shell: {content} → {'ok' if result.success else 'fail'}")
                results.append(f"$ {content}\n{result.output[:4000]}")

            elif tag.startswith("write:"):
                filepath = tag[6:].strip()
                full_path = self.project_dir / filepath
                result = write_file(full_path, content + "\n", project_dir=self.project_dir)
                self._exec_write(f"[dim]write {filepath} → {'ok' if result.success else 'fail: ' + result.output}[/dim]")
                self._flog.info(f"write {filepath} → {'ok' if result.success else 'fail'}")
                results.append(f"write {filepath}: {'ok' if result.success else result.output}")

            elif tag.startswith("edit:"):
                filepath = tag[5:].strip()
                full_path = self.project_dir / filepath
                edit_match = re.match(r'<<<(.+?)>>>\s*<<<(.+?)>>>', content, re.DOTALL)
                if edit_match:
                    old_text, new_text = edit_match.group(1), edit_match.group(2)
                    result = edit_file(full_path, old_text, new_text, project_dir=self.project_dir)
                    self._exec_write(f"[dim]edit {filepath} → {'ok' if result.success else 'fail: ' + result.output}[/dim]")
                    self._flog.info(f"edit {filepath} → {'ok' if result.success else 'fail'}")
                    results.append(f"edit {filepath}: {'ok' if result.success else result.output}")
                else:
                    self._exec_write(f"[yellow]Edit parse error for {filepath}[/yellow]")
                    results.append(f"edit {filepath}: parse error — expected <<<old>>> <<<new>>>")

            elif tag.startswith("read:"):
                filepath = tag[5:].strip()
                full_path = self.project_dir / filepath
                ok, reason = check_path_containment(full_path, self.project_dir)
                if not ok:
                    results.append(f"read {filepath}: {reason}")
                    continue
                if full_path.exists() and full_path.is_file():
                    file_content = full_path.read_text()
                    self._exec_write(f"[dim]read {filepath} ({len(file_content)} chars)[/dim]")
                    self._flog.info(f"read {filepath} ({len(file_content)} chars)")
                    results.append(f"=== {filepath} ===\n{file_content[:8000]}")
                else:
                    self._exec_write(f"[yellow]File not found: {filepath}[/yellow]")
                    results.append(f"read {filepath}: file not found")

            elif tag == "search":
                # Parse search params from content
                search_pattern = ""
                search_glob = "*.py"
                for line in content.split("\n"):
                    if line.startswith("pattern:"):
                        search_pattern = line[8:].strip()
                    elif line.startswith("glob:"):
                        search_glob = line[5:].strip()
                if search_pattern:
                    import subprocess
                    try:
                        cmd = f"grep -rn '{search_pattern}' --include='{search_glob}' ."
                        proc = subprocess.run(
                            cmd, shell=True, capture_output=True, text=True,
                            cwd=self.project_dir, timeout=10
                        )
                        output = proc.stdout[:4000] or "No matches"
                        self._exec_write(f"[dim]search {search_pattern} in {search_glob} ({len(proc.stdout)} chars)[/dim]")
                        self._flog.info(f"search {search_pattern} → {len(proc.stdout)} chars")
                        results.append(f"search '{search_pattern}' in {search_glob}:\n{output}")
                    except Exception as e:
                        results.append(f"search error: {e}")
                else:
                    # Just list files matching glob
                    import subprocess
                    proc = subprocess.run(
                        f"find . -name '{search_glob}' -not -path './.git/*' | head -50",
                        shell=True, capture_output=True, text=True,
                        cwd=self.project_dir, timeout=10
                    )
                    results.append(f"files matching {search_glob}:\n{proc.stdout[:4000]}")

            elif tag.startswith("ls:"):
                dirpath = tag[3:].strip() or "."
                full_dir = self.project_dir / dirpath
                if full_dir.exists() and full_dir.is_dir():
                    import subprocess
                    proc = subprocess.run(
                        ["ls", "-la"], capture_output=True, text=True, cwd=full_dir
                    )
                    self._exec_write(f"[dim]ls {dirpath} ({len(proc.stdout.splitlines())} entries)[/dim]")
                    results.append(f"ls {dirpath}:\n{proc.stdout[:4000]}")
                else:
                    results.append(f"ls {dirpath}: not found")

            elif tag == "plan":
                # Legacy markdown plan block
                self._apply_plan_from_response(response)
                results.append("plan updated")

            elif tag == "yaml":
                # YAML plan block — preferred format
                if self._apply_yaml_plan(content):
                    results.append("plan updated (yaml)")
                else:
                    # Not a plan yaml — just report it
                    results.append(f"yaml block (not a plan): {content[:200]}")

        # Strip action blocks from display text
        display = re.sub(
            r'```(shell|write:[^\n]+|edit:[^\n]+|read:[^\n]+|search|ls:[^\n]*|yaml|plan)\n.*?```',
            lambda m: f'[dim][{m.group(1).split(":")[0]}][/dim]',
            display, flags=re.DOTALL
        )

        return display, results

    def _apply_plan_from_response(self, response: str) -> bool:
        """Extract ```plan block from LLM response and apply to editor.

        Returns True if plan was updated.
        """
        import re
        from ..plan import Plan

        match = re.search(r'```plan\n(.*?)```', response, re.DOTALL)
        if not match:
            return False

        plan_md = match.group(1).strip()
        try:
            new_plan = Plan.from_markdown(plan_md)
            if not new_plan.steps and not new_plan.intent:
                return False  # Empty parse — don't clobber the plan

            self.plan = new_plan
            editor = self.query_one("#plan-editor", PlanEditor)
            editor.load_plan(self.plan)
            self._save_plan()
            self._update_status()
            self._flog.info(f"Plan updated via chat: {len(new_plan.steps)} steps")
            return True
        except Exception as e:
            self._flog.error(f"Failed to parse plan from chat: {e}")
            self._exec_write(f"[red]Plan parse error: {e}[/red]")
            return False

    def _apply_yaml_plan(self, yaml_content: str) -> bool:
        """Parse a YAML plan block and apply to editor.

        Expected format:
            plan:
              intent: "description"
              steps:
                - status: done|active|pending|failed
                  description: "step text"
                  commit: optional-hash
                  annotations:
                    - "annotation text"

        Returns True if plan was updated.
        """
        import yaml
        from ..plan import Plan, Step

        try:
            data = yaml.safe_load(yaml_content)
        except Exception as e:
            self._flog.error(f"YAML parse error: {e}")
            return False

        if not isinstance(data, dict) or "plan" not in data:
            return False

        plan_data = data["plan"]
        intent = plan_data.get("intent", self.plan.intent or "")
        steps_data = plan_data.get("steps", [])

        if not steps_data:
            return False

        STATUS_MAP = {
            "done": "done",
            "active": "active",
            "pending": "pending",
            "failed": "failed",
            # Accept markdown-style too
            "x": "done",
            ">": "active",
            " ": "pending",
            "!": "failed",
        }

        steps = []
        for s in steps_data:
            if not isinstance(s, dict):
                continue
            status = STATUS_MAP.get(str(s.get("status", "pending")).lower(), "pending")
            desc = s.get("description", "")
            if not desc:
                continue
            step = Step(
                description=desc,
                status=status,
                commit_hash=s.get("commit", None),
            )
            # Parse annotations
            for ann in s.get("annotations", []):
                ann_str = str(ann).strip()
                if ann_str.startswith("files:"):
                    step.files = [f.strip() for f in ann_str[6:].split(",")]
                elif ann_str.startswith("done:"):
                    step.annotations.append(ann_str)
                else:
                    step.annotations.append(ann_str)
            # Also accept top-level files key
            if "files" in s:
                if isinstance(s["files"], list):
                    step.files = s["files"]
                elif isinstance(s["files"], str):
                    step.files = [f.strip() for f in s["files"].split(",")]
            steps.append(step)

        if not steps:
            return False

        try:
            new_plan = Plan(intent=intent, steps=steps)
            self.plan = new_plan
            editor = self.query_one("#plan-editor", PlanEditor)
            editor.load_plan(self.plan)
            self._save_plan()
            self._update_status()
            self._flog.info(f"Plan updated via YAML: {len(steps)} steps")
            self._exec_write(f"[cyan]Plan updated: {len(steps)} steps[/cyan]")
            return True
        except Exception as e:
            self._flog.error(f"Failed to apply YAML plan: {e}")
            self._exec_write(f"[red]YAML plan error: {e}[/red]")
            return False

    def _save_plan(self) -> None:
        editor = self.query_one("#plan-editor", PlanEditor)
        self.plan = editor.get_plan()
        plan_path = self.project_dir / ".reeree" / "plan.yaml"
        self.plan.save(plan_path)

    def _add_step(self, description: str) -> None:
        if not description:
            self.notify("Usage: :add \"step description\"", severity="warning")
            return
        from ..plan import Step
        self.plan.steps.append(Step(description=description))
        editor = self.query_one("#plan-editor", PlanEditor)
        editor.load_plan(self.plan)
        self._save_plan()
        self._update_status()
        self._exec_write(f"+ {description}")

    def _delete_step(self, index_str: str) -> None:
        try:
            idx = int(index_str) - 1
            if 0 <= idx < len(self.plan.steps):
                removed = self.plan.steps.pop(idx)
                editor = self.query_one("#plan-editor", PlanEditor)
                editor.load_plan(self.plan)
                self._save_plan()
                self._update_status()
                self._exec_write(f"- step {index_str}: {removed.description}")
            else:
                self.notify(f"Step {index_str} out of range", severity="error")
        except ValueError:
            self.notify("Usage: :del N", severity="warning")

    def _move_step(self, from_str: str, to_str: str) -> None:
        try:
            from_idx = int(from_str) - 1
            to_idx = int(to_str) - 1
            if 0 <= from_idx < len(self.plan.steps) and 0 <= to_idx < len(self.plan.steps):
                step = self.plan.steps.pop(from_idx)
                self.plan.steps.insert(to_idx, step)
                editor = self.query_one("#plan-editor", PlanEditor)
                editor.load_plan(self.plan)
                self._save_plan()
                self._exec_write(f"Moved step {from_str} → {to_str}")
        except ValueError:
            self.notify("Usage: :move N M", severity="warning")

    def _show_diff(self, step_str: str) -> None:
        try:
            idx = int(step_str) - 1 if step_str else -1
            if 0 <= idx < len(self.plan.steps):
                step = self.plan.steps[idx]
                if step.commit_hash:
                    from ..executor import run_shell
                    result = run_shell(f"git diff {step.commit_hash}~1 {step.commit_hash}", self.project_dir)
                    self._exec_write(f"[bold]Diff: Step {idx + 1}[/bold]\n{result.output or 'No diff'}")
                else:
                    self.notify("Step has no commit yet", severity="warning")
            else:
                from ..executor import run_shell
                result = run_shell("git diff HEAD~1 HEAD", self.project_dir)
                self._exec_write(f"[bold]Last diff[/bold]\n{result.output or 'No diff'}")
        except (ValueError, IndexError):
            self.notify("Usage: :diff [N]", severity="warning")

    def _show_daemon_log(self, daemon_str: str) -> None:
        try:
            wid = int(daemon_str) if daemon_str else 1
            daemon = self._daemon_registry.get(wid)
            if daemon:
                self._exec_write(f"[bold]Daemon {wid} log:[/bold]\n{daemon.log or 'No log yet'}")
            else:
                self.notify(f"No daemon {wid}", severity="warning")
        except ValueError:
            self.notify("Usage: :log [N]", severity="warning")

    def _show_file(self, path: str) -> None:
        """Open a file in the file viewer, overlaying the plan editor.

        :q in the file viewer closes it back to the plan.
        :w saves changes, :wq saves and closes.
        """
        if not path.strip():
            self.notify("Usage: :file <path>", severity="warning")
            return

        full_path = self.project_dir / path.strip()
        if not full_path.exists():
            self.notify(f"File not found: {path}", severity="error")
            return
        if full_path.is_dir():
            self.notify(f"Not a file: {path}", severity="error")
            return

        self._file_viewer_path = full_path

        # Load content into existing file viewer
        viewer = self.query_one("#file-viewer", FileViewer)
        viewer._file_path = full_path
        try:
            content = full_path.read_text()
        except (UnicodeDecodeError, ValueError):
            self.notify(f"Cannot read binary file: {path}", severity="error")
            self._file_viewer_path = None
            return
        viewer.load_file(content)
        viewer.vim_mode = "NORMAL"
        viewer.read_only = True
        viewer.add_class("visible")

        # Hide plan editor, show file viewer
        self.query_one("#plan-editor").styles.display = "none"
        viewer.styles.display = "block"
        viewer.focus()

        self._exec_write(f"opened {path} (:q close, i edit, :w save)")
        self._flog.info(f"File viewer: {full_path}")

    def _close_file_viewer(self) -> None:
        """Close the file viewer and return to the plan editor."""
        viewer = self.query_one("#file-viewer", FileViewer)
        # If in INSERT mode, switch back to NORMAL first
        if viewer.vim_mode == "INSERT":
            viewer.read_only = True
            viewer.vim_mode = "NORMAL"

        viewer.remove_class("visible")
        viewer.styles.display = "none"
        self.query_one("#plan-editor").styles.display = "block"
        self.query_one("#plan-editor", PlanEditor).focus()
        self.query_one("#status-bar", StatusBar).mode = "NORMAL"
        self._file_viewer_path = None
        self._exec_write("[dim]closed[/dim]")

    def _save_file_viewer(self) -> bool:
        """Save the file viewer's contents to disk."""
        viewer = self.query_one("#file-viewer", FileViewer)
        if viewer.save():
            self._exec_write(f"saved {viewer.file_path.name}")
            return True
        else:
            self._exec_write(f"[red]save failed: {viewer.file_path.name}[/red]")
            return False

    def _process_machine_tasks_in_viewer(self) -> None:
        """Find [machine: ...] annotations in the file viewer and dispatch daemons."""
        viewer = self.query_one("#file-viewer", FileViewer)
        tasks = find_tasks(viewer.text)
        if not tasks:
            return

        self._exec_write(f"[cyan]{len(tasks)} machine task(s) found[/cyan]")

        # Mark all tasks as in-progress in the document
        updated_text = mark_in_progress(viewer.text, tasks)
        viewer.load_file(updated_text)
        viewer.save()

        # Dispatch each task
        for task in tasks:
            self._dispatch_machine_task(task, viewer.file_path)

    def _process_machine_tasks_in_plan(self) -> None:
        """Find [machine: ...] annotations in plan step annotations and dispatch."""
        for step in self.plan.steps:
            for i, ann in enumerate(step.annotations):
                tasks = find_tasks(ann)
                if tasks:
                    for task in tasks:
                        step.annotations[i] = mark_in_progress(ann, [task])
                        self._dispatch_machine_task(task, None, step_context=step.description)
                    self._refresh_plan_display()
                    self._save_plan()

    def _dispatch_machine_task(self, task: MachineTask, file_path: "Path | None", step_context: str = "") -> None:
        """Dispatch a daemon to execute an inline machine task."""
        daemon = self._daemon_registry.spawn(
            DaemonKind.STEP, f"machine: {task.description[:50]}",
            scope=str(self.project_dir.name),
        )
        task.daemon_id = daemon.id
        self._exec_write(f"d{daemon.id} → [machine: {task.description[:60]}]")

        import asyncio
        asyncio.ensure_future(
            self._run_machine_task(daemon.id, task, file_path, step_context)
        )

    async def _run_machine_task(self, daemon_id: int, task: MachineTask, file_path: "Path | None", step_context: str = "") -> None:
        """Execute an inline machine task via LLM and splice the result back."""
        from ..llm import chat_async
        from ..context import gather_context
        from ..plan import Step

        daemon = self._daemon_registry.get(daemon_id)

        try:
            # Gather context from the project
            dummy_step = Step(description=task.description)
            context = gather_context(dummy_step, self.project_dir, self.config.max_context_tokens * 4)

            # Build the document context
            doc_context = ""
            if file_path and file_path.exists():
                doc_text = file_path.read_text()
                # Show surrounding text for context (up to 2000 chars around the task)
                doc_context = f"\nDocument ({file_path.name}):\n{doc_text[:4000]}\n"

            system = (
                f"{VOICE}\n\n"
                f"Inline machine task. The user is writing a document and has placed an inline\n"
                f"annotation requesting machine work. Produce ONLY the content that should\n"
                f"replace the annotation — no preamble, no 'here is...', no wrapping.\n\n"
                f"If the task asks for a list, produce a markdown list.\n"
                f"If it asks for prose, produce prose.\n"
                f"If it asks for research, produce concise findings.\n"
                f"Match the voice and style of the surrounding document.\n\n"
                f"Project context:\n{context[:4000]}\n"
                f"{doc_context}"
            )

            prompt = task.description
            if step_context:
                prompt = f"Context: {step_context}\n\nTask: {task.description}"

            messages = [{"role": "user", "content": prompt}]
            result = await chat_async(messages, self.config, system=system)
            result = result.strip()

            time_str = daemon.elapsed_str if daemon else "?"

            # Splice result back into the document
            if file_path and file_path.exists():
                doc_text = file_path.read_text()
                updated = splice_result(doc_text, task.description, result)
                file_path.write_text(updated)

                # Update the file viewer if it's still showing this file
                if self._file_viewer_path == file_path:
                    viewer = self.query_one("#file-viewer", FileViewer)
                    viewer.load_file(updated)

                self._exec_write(
                    f"[green]done[/green] d{daemon_id} ({time_str}) — spliced into {file_path.name}"
                )
            else:
                # Result goes to exec log if no file to splice into
                self._exec_write(
                    f"[green]done[/green] d{daemon_id} ({time_str}):\n{result[:500]}"
                )

            if daemon:
                daemon.status = DaemonStatus.DONE
                daemon.log = result[:1000]

        except Exception as e:
            self._exec_write(f"[red]fail[/red] d{daemon_id}: {e}")
            if daemon:
                daemon.status = DaemonStatus.FAILED
                daemon.error = str(e)

            # Remove progress indicator on failure
            if file_path and file_path.exists():
                doc_text = file_path.read_text()
                # Restore original annotation
                updated = splice_result(doc_text, task.description, f"[machine: {task.description}] ← FAILED: {e}")
                file_path.write_text(updated)
                if self._file_viewer_path == file_path:
                    viewer = self.query_one("#file-viewer", FileViewer)
                    viewer.load_file(updated)

        self._update_status()

    def _set_option(self, args: str) -> None:
        parts = args.split(None, 1)
        if len(parts) != 2:
            self.notify("Usage: :set option value", severity="warning")
            return
        key, value = parts
        if key == "model":
            self.config.model = value
            self._exec_write(f"Model → {value}")
        elif key == "autonomy":
            if value in ("low", "medium", "high", "full"):
                self.config.autonomy = value
                self._exec_write(f"Autonomy → {value}")
            else:
                self.notify("Autonomy must be: low, medium, high, full", severity="error")
        else:
            self.notify(f"Unknown option: {key}", severity="error")

    async def _dispatch_go(self, args: str) -> None:
        """Parse :go args and dispatch accordingly.

        :go          dispatch next 2 pending steps
        :go all      dispatch ALL pending steps
        :go N        dispatch step N
        :go N M      dispatch steps N and M
        :go "desc"   create new step + dispatch it
        """
        args = args.strip()

        if not args:
            # :go with no args — dispatch next 2 pending
            await self._dispatch_next(2)
            return

        if args.lower() == "all":
            await self._dispatch_all()
            return

        import re
        # Extract quoted string
        quoted_match = re.search(r'"([^"]+)"', args)
        instruction = quoted_match.group(1) if quoted_match else None
        nums_part = re.sub(r'"[^"]*"', '', args).strip()
        step_nums = [int(x) - 1 for x in nums_part.split() if x.isdigit()]

        if instruction and not step_nums:
            # :go "description" — create + dispatch
            from ..plan import Step
            new_step = Step(description=instruction)
            self.plan.steps.append(new_step)
            editor = self.query_one("#plan-editor", PlanEditor)
            editor.load_plan(self.plan)
            self._save_plan()
            self._exec_write(f"+ {instruction}")
            await self._dispatch_steps_by_id([new_step.id])
        elif step_nums:
            # :go N or :go N M — dispatch specific steps by number
            step_ids = []
            for idx in step_nums:
                if 0 <= idx < len(self.plan.steps):
                    step_ids.append(self.plan.steps[idx].id)
                else:
                    self._exec_write(f"[yellow]Step {idx + 1} out of range[/yellow]")
            if step_ids:
                await self._dispatch_steps_by_id(step_ids)
        else:
            self._exec_write("[dim]nothing to dispatch[/dim]")

    async def _dispatch_steps_by_id(self, step_ids: list[str]) -> None:
        """Dispatch specific steps by their stable ID."""
        editor = self.query_one("#plan-editor", PlanEditor)

        dispatched = 0
        for step_id in step_ids:
            step = self.plan.step_by_id(step_id)
            if step is None:
                self._exec_write(f"[yellow]Step {step_id} not found[/yellow]")
                continue
            step_idx = self.plan.step_index_by_id(step_id)
            if step.status != "pending":
                self._exec_write(f"[dim]Step {(step_idx or 0) + 1} already {step.status}[/dim]")
                continue

            daemon = self._daemon_registry.spawn(
                DaemonKind.STEP, step.description,
                step_id=step_id, scope=self.project_dir.name,
            )
            step.status = "active"
            step.daemon_id = daemon.id
            self._refresh_plan_display()
            self._exec_write(f"d{daemon.id} → step {(step_idx or 0)+1}: {step.description}")
            self._run_daemon(daemon.id, step, step_id)
            dispatched += 1

        self._update_status()

    async def _dispatch_next(self, count: int) -> None:
        """Dispatch next N pending steps."""
        pending = self.plan.dispatchable_steps
        if not pending:
            self._exec_write("[dim]no pending steps[/dim]")
            return

        step_ids = [step.id for _idx, step in pending[:count]]
        await self._dispatch_steps_by_id(step_ids)

    async def _dispatch_all(self) -> None:
        """Dispatch ALL pending steps."""
        pending = [(i, s) for i, s in enumerate(self.plan.steps)
                   if s.status == "pending"]
        if not pending:
            self._exec_write("[dim]no pending steps[/dim]")
            return

        step_ids = [step.id for _idx, step in pending]
        await self._dispatch_steps_by_id(step_ids)

    def _refresh_plan_display(self) -> None:
        """Re-render plan in the editor. In VIEW mode, updates immediately.
        In NORMAL/INSERT mode, no-op (user is editing YAML)."""
        editor = self.query_one("#plan-editor", PlanEditor)
        if editor.vim_mode == "VIEW":
            editor.refresh_view(self.plan)
        # In edit modes, don't touch the TextArea — StatusOverlay handles merge

    async def _run_daemon_task(self, daemon_id: int, step, step_id: str) -> None:
        from ..daemon_executor import dispatch_step

        daemon = self._daemon_registry.get(daemon_id)
        step_idx = self.plan.step_index_by_id(step_id)

        def on_log(msg, did=daemon_id):
            self._daemon_log(did, msg)

        try:
            result = await dispatch_step(
                step=step,
                step_index=step_idx if step_idx is not None else 0,
                project_dir=self.project_dir,
                config=self.config,
                on_log=on_log,
                should_continue=lambda: daemon.is_active if daemon else True,
            )

            time_str = daemon.elapsed_str if daemon else "?"
            status = result.get("status", "failed")
            commit_hash = result.get("commit_hash")

            # Post status update via overlay
            update = StepStatusUpdate(
                step_id=step_id,
                status="done" if status == "done" else "failed",
                commit_hash=commit_hash,
                error=result.get("error") if status != "done" else None,
            )

            # Apply to in-memory plan immediately
            target_step = self.plan.step_by_id(step_id)
            if target_step:
                update.apply(target_step)
                self._save_plan()

            # Update display based on current mode
            editor = self.query_one("#plan-editor", PlanEditor)
            if editor.vim_mode == "VIEW":
                # Refresh immediately
                self._refresh_plan_display()
            else:
                # Queue for merge when user exits edit mode
                self._status_overlay.post(update)

            if status == "done":
                summary = result.get('summary', '')
                hash_str = f" {commit_hash[:7]}" if commit_hash else ""
                summary_str = f" — {summary}" if summary else ""
                self._exec_write(
                    f"[green]done[/green] d{daemon_id}{hash_str} ({time_str}){summary_str}"
                )
                # Apply notes to next pending step
                next_notes = result.get("next_step_notes", [])
                if next_notes:
                    current_idx = self.plan.step_index_by_id(step_id)
                    if current_idx is not None:
                        self._annotate_next_step(current_idx, next_notes, editor)
            else:
                err = result.get('error', '')
                self._exec_write(
                    f"[red]fail[/red] d{daemon_id} ({time_str}) {err}"
                )

            if daemon:
                daemon.status = DaemonStatus.DONE if status == "done" else DaemonStatus.FAILED
            self._update_status()

        except Exception as e:
            self._daemon_log(daemon_id, f"EXCEPTION: {e}")
            if daemon:
                daemon.status = DaemonStatus.FAILED
                daemon.error = str(e)
            self._exec_write(f"[red]fail[/red] d{daemon_id}: {e}")
            self._update_status()

    def _run_daemon(self, daemon_id: int, step, step_id: str) -> None:
        import asyncio
        asyncio.ensure_future(self._run_daemon_task(daemon_id, step, step_id))

    def _annotate_next_step(self, completed_index: int, notes: list[str], editor: "PlanEditor") -> None:
        """Apply daemon notes to the next pending step after a completed one."""
        next_idx = None
        for i in range(completed_index + 1, len(self.plan.steps)):
            if self.plan.steps[i].status == "pending":
                next_idx = i
                break

        if next_idx is None:
            return

        next_step = self.plan.steps[next_idx]
        for note in notes:
            if isinstance(note, str) and note.strip():
                annotation = f"[from step {completed_index + 1}] {note.strip()}"
                next_step.annotations.append(annotation)

        if notes:
            self._refresh_plan_display()
            self._save_plan()
            self._exec_write(
                f"  [dim]→ {len(notes)} note(s) added to step {next_idx + 1}[/dim]"
            )

    def _daemon_log(self, daemon_id: int, message: str) -> None:
        daemon = self._daemon_registry.get(daemon_id)
        if daemon:
            daemon.append_log(message)
        # Always log to file
        self._flog.info(f"d{daemon_id}: {message}")
        # Only show actions and status changes in TUI, not LLM chatter
        if any(message.startswith(p) for p in ("$ ", "Wrote ", "Edited ", "Read ", "Search:", "EXCEPTION")):
            self._exec_write(f"[dim]d{daemon_id}[/dim] {message}")

    async def _undo_step(self, step_str: str) -> None:
        from ..executor import git_revert_last
        result = git_revert_last(self.project_dir)
        if result.success:
            self._exec_write("[yellow]Reverted last step[/yellow]")
        else:
            self._exec_write(f"[red]Revert failed:[/red] {result.output}")

    async def _propagate(self) -> None:
        """Crawl cross-references from the current plan/doc and check coherence."""
        # Find all markdown links in the current plan
        import re
        plan_text = self.plan_editor.text
        link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        links = link_pattern.findall(plan_text)

        if not links:
            self._exec_write("[dim]No cross-references found to propagate.[/dim]")
            return

        # Resolve paths relative to project dir
        doc_paths = []
        for _label, href in links:
            if href.startswith("http"):
                continue
            p = (self.project_dir / href).resolve()
            if p.exists() and p.suffix in (".md", ".txt", ".py", ".json"):
                doc_paths.append(p)

        if not doc_paths:
            self._exec_write("[dim]No local doc cross-references found.[/dim]")
            return

        self._exec_write(f"propagating coherence across {len(doc_paths)} linked docs")
        await self._run_coherence_check(doc_paths)

    async def _cohere(self, args: str) -> None:
        """Check coherence across specified docs. Accepts paths, globs, wildcards."""
        import glob as globmod

        if not args.strip():
            self.notify("Usage: :cohere doc1.md doc2.md  or  :cohere *.md  or  :cohere docs/", severity="warning")
            return

        doc_paths = []
        for arg in args.split():
            # Try as glob first
            matches = globmod.glob(str(self.project_dir / arg), recursive=True)
            if matches:
                for m in matches:
                    p = Path(m)
                    if p.is_file() and p.suffix in (".md", ".txt", ".py", ".json", ".toml", ".yaml", ".yml"):
                        doc_paths.append(p)
            else:
                # Try as direct path
                p = (self.project_dir / arg).resolve()
                if p.is_file():
                    doc_paths.append(p)
                elif p.is_dir():
                    # If it's a directory, grab all markdown files in it
                    for md in sorted(p.glob("**/*.md")):
                        doc_paths.append(md)
                else:
                    self._exec_write(f"[yellow]Warning: {arg} not found[/yellow]")

        if not doc_paths:
            self._exec_write("[red]No documents found matching the given paths.[/red]")
            return

        # Deduplicate
        doc_paths = list(dict.fromkeys(doc_paths))
        self._exec_write(f"coherence check: {len(doc_paths)} docs")
        await self._run_coherence_check(doc_paths)

    async def _run_coherence_check(self, doc_paths: list) -> None:
        """Dispatch a coherence daemon to check a set of documents."""
        # Read all docs
        doc_contents = []
        total_chars = 0
        max_chars = self.config.max_context_tokens * 4  # rough char estimate
        for dp in doc_paths:
            try:
                content = dp.read_text()
                rel = dp.relative_to(self.project_dir) if dp.is_relative_to(self.project_dir) else dp.name
                if total_chars + len(content) > max_chars:
                    content = content[:max_chars - total_chars] + "\n... (truncated)"
                doc_contents.append(f"### {rel}\n```\n{content}\n```")
                total_chars += len(content)
                if total_chars >= max_chars:
                    break
            except Exception as e:
                self._exec_write(f"[yellow]Could not read {dp}: {e}[/yellow]")

        if not doc_contents:
            self._exec_write("[red]No documents could be read.[/red]")
            return

        system = (
            f"{VOICE}\n\n"
            "Coherence daemon. Read documents, identify contradictions, stale references,\n"
            "inconsistencies, and gaps.\n\n"
            "For each issue: location (doc + section), issue (what's wrong), fix (how to resolve).\n"
            "Focus on factual contradictions and structural issues, not style.\n"
            "If everything is coherent, say so in one line.\n"
        )

        user_msg = f"Check these documents for coherence:\n\n{''.join(doc_contents)}"

        # Dispatch as a daemon task
        daemon = self._daemon_registry.spawn(
            DaemonKind.COHERENCE, "coherence check",
            scope=str(self.project_dir.name),
        )
        did = daemon.id
        self._exec_write(f"d{did} → coherence ({len(doc_contents)} docs, {total_chars} chars)")

        import asyncio

        async def run_coherence():
            try:
                messages = [{"role": "user", "content": user_msg}]
                response = await chat_async(messages, self.config, system=system)
                self._daemon_log(did, response)
                self._exec_write(f"[green]done[/green] d{did} coherence")
                daemon.status = DaemonStatus.DONE
            except Exception as e:
                self._daemon_log(did, f"ERROR: {e}")
                self._exec_write(f"[red]fail[/red] d{did} coherence: {e}")
                daemon.status = DaemonStatus.FAILED
                daemon.error = str(e)

        task = asyncio.create_task(run_coherence())
        daemon.task = task


class CommandScreen(ModalScreen[str]):
    """Vim-style : command input with history (up/down arrows)."""

    # Class-level history shared across all instances (persists for session)
    _history: list[str] = []
    _max_history: int = 100

    DEFAULT_CSS = """
    CommandScreen {
        align: left bottom;
        background: transparent;
    }
    #cmd-container {
        dock: bottom;
        height: 3;
        width: 100%;
        background: $surface;
    }
    #cmd-prefix {
        width: 2;
        height: 3;
        content-align: left middle;
        padding: 1 0 0 1;
    }
    #cmd-input {
        width: 1fr;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._history_index = len(self._history)  # past the end = new command
        self._draft = ""  # what the user was typing before browsing history

    def compose(self) -> ComposeResult:
        with Horizontal(id="cmd-container"):
            yield Static(":", id="cmd-prefix")
            yield Input(placeholder="command", id="cmd-input")

    def on_mount(self) -> None:
        self.query_one("#cmd-input", Input).focus()

    @on(Input.Submitted, "#cmd-input")
    def on_submit(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        if cmd and (not self._history or self._history[-1] != cmd):
            self._history.append(cmd)
            if len(self._history) > self._max_history:
                self._history.pop(0)
        self.dismiss(cmd)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss("")
        elif event.key == "up":
            if self._history:
                inp = self.query_one("#cmd-input", Input)
                if self._history_index == len(self._history):
                    self._draft = inp.value
                if self._history_index > 0:
                    self._history_index -= 1
                    inp.value = self._history[self._history_index]
                    inp.cursor_position = len(inp.value)
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            if self._history:
                inp = self.query_one("#cmd-input", Input)
                if self._history_index < len(self._history):
                    self._history_index += 1
                    if self._history_index == len(self._history):
                        inp.value = self._draft
                    else:
                        inp.value = self._history[self._history_index]
                    inp.cursor_position = len(inp.value)
            event.prevent_default()
            event.stop()
