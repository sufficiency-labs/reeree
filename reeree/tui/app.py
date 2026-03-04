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
    logger.handlers.clear()

    fh = logging.FileHandler(log_file, mode="a")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(fh)

    logger.info("=== Session started ===")
    return logger


class PlanEditor(TextArea):
    """The plan document — vim-style modal editing.

    NORMAL: read-only, hjkl nav, : for commands, i to edit
    INSERT: full editing, Escape returns to NORMAL
    """

    vim_mode = reactive("NORMAL")

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
        self.text = plan.to_markdown()
        self.read_only = was_readonly

    def get_plan(self) -> Plan:
        return Plan.from_markdown(self.text)

    def update_step_status(self, step_index: int, status: str, commit_hash: str | None = None) -> None:
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
        self.read_only = False
        self.vim_mode = "INSERT"
        app = self.app
        if isinstance(app, ReereeApp):
            app.query_one("#status-bar", StatusBar).mode = "INSERT"
            app._flog.debug("Mode: INSERT")

    def _enter_normal_mode(self) -> None:
        self.read_only = True
        self.vim_mode = "NORMAL"
        app = self.app
        if isinstance(app, ReereeApp):
            app.query_one("#status-bar", StatusBar).mode = "NORMAL"
            app._flog.debug("Mode: NORMAL")

    def on_key(self, event: events.Key) -> None:
        if self.vim_mode == "NORMAL":
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
        return f" [{color}]{self.mode}[/{color}]  |  daemons: {daemon_str}  |  progress: {progress_str}  |  [dim]i=edit  :=cmd  Tab=pane  :help[/dim]"


class ReereeApp(App):
    """reeree — plan on the left, execution log on the right."""

    TITLE = "reeree"
    CSS = """
    #main-layout {
        width: 100%;
        height: 1fr;
    }
    #plan-editor {
        width: 55%;
    }
    #right-panel {
        width: 45%;
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
        self._daemons: dict[int, dict] = {}
        self._next_daemon_id = 1
        self._flog = _setup_file_logger(project_dir)
        self._flog.info(f"Project: {project_dir}")
        self._flog.info(f"Model: {config.model}")
        self._flog.info(f"Plan: {len(self.plan.steps)} steps — {self.plan.intent!r}")
        # Chat state — persistent message history with the executor daemon
        self._chat_messages: list[dict] = []
        self._chat_target = "executor"  # which daemon type we're chatting with
        self._chat_busy = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-layout"):
            yield PlanEditor(self.plan, id="plan-editor")
            with Vertical(id="right-panel"):
                yield RichLog(id="exec-log", highlight=True, markup=True, wrap=True)
                with Vertical(id="chat-panel"):
                    yield Input(placeholder="chat with daemon (type 'exit' to close)", id="chat-input")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self.query_one("#plan-editor", PlanEditor).focus()
        self._update_status()
        # Show initial state in exec log
        exec_log = self.query_one("#exec-log", RichLog)
        exec_log.write(f"[bold]reeree[/bold] — {self.plan.intent or 'no plan'}")
        exec_log.write(f"[dim]{self.config.model} via {self.config.api_base}[/dim]")
        exec_log.write(f"[dim]{len(self.plan.steps)} steps  |  :go to dispatch  |  :help for commands[/dim]")
        exec_log.write("")

    def _update_status(self) -> None:
        status = self.query_one("#status-bar", StatusBar)
        if self.plan.steps:
            status.progress = self.plan.progress
        active = sum(1 for w in self._daemons.values() if w.get("status") == "active")
        status.active_daemons = active
        status.daemon_count = len(self._daemons)

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
            status.mode = "NORMAL"
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

        if command in ("q", "quit"):
            self._save_plan()
            self._flog.info("Quit. Plan saved.")
            self.exit()
        elif command in ("q!", "quit!"):
            self._flog.info("Force quit.")
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
        elif command == "pause":
            self.notify("Pause: not yet implemented")
        elif command == "kill" and args:
            self.notify("Kill daemon: not yet implemented")
        elif command == "help":
            self._show_help()
        else:
            self.notify(f"Unknown command: {command}", severity="error")

    def _show_help(self) -> None:
        self._exec_write(
            "[bold]NORMAL MODE[/bold]\n"
            "  i        Enter INSERT mode\n"
            "  :        Enter COMMAND mode\n"
            "  hjkl     Navigate\n"
            "  Esc      Return to NORMAL\n"
            "  Tab/^W   Cycle pane focus\n"
            "\n"
            "[bold]COMMANDS[/bold]\n"
            "  :go              Dispatch pending steps\n"
            "  :add \"desc\"      Add a step\n"
            "  :del N           Delete step N\n"
            "  :move N M        Move step N to M\n"
            "  :diff [N]        Show diff for step N\n"
            "  :log [N]         Show daemon N log\n"
            "  :file path       View a file in log\n"
            "  :undo            Revert last step\n"
            "  :set key value   Set config (model, autonomy)\n"
            "  :chat            Toggle chat (executor daemon)\n"
            "  :chat coherence  Chat with coherence daemon\n"
            "  :chat state      Chat with state daemon\n"
            "  :w / :q / :wq    Save / quit / both\n"
            "  :help            This help\n"
        )

    def _toggle_chat(self, target: str = "") -> None:
        panel = self.query_one("#chat-panel")
        if target:
            self._chat_target = target
            self._chat_messages = []  # Fresh context for new target
            self._exec_write(f"[bold]Chat target: {target} daemon[/bold]")
            panel.add_class("visible")
            self.query_one("#chat-input", Input).focus()
        elif panel.has_class("visible"):
            panel.remove_class("visible")
            self.query_one("#plan-editor", PlanEditor).focus()
        else:
            panel.add_class("visible")
            if not self._chat_messages:
                self._exec_write(f"[dim]Chat open — talking to {self._chat_target} daemon. Type 'exit' to close.[/dim]")
            self.query_one("#chat-input", Input).focus()

    def _toggle_chat_off(self) -> None:
        self.query_one("#chat-panel").remove_class("visible")

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

        self._exec_write(f"[bold cyan]you:[/bold cyan] {msg}")
        self._flog.info(f"Chat [{self._chat_target}]: {msg}")

        if self._chat_busy:
            self._exec_write("[dim]Waiting for previous response...[/dim]")
            return

        # Add user message to history
        self._chat_messages.append({"role": "user", "content": msg})

        # Launch async response
        import asyncio
        asyncio.ensure_future(self._chat_respond(msg))

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
            for did, dinfo in self._daemons.items():
                if dinfo.get("log"):
                    daemon_history += f"\n--- Daemon {did} ---\n{dinfo['log'][-500:]}\n"

            system = (
                f"You are an executor daemon for a coding project.\n"
                f"You can READ and WRITE the plan. The plan is a living markdown document.\n"
                f"You can modify the plan by including an updated version in a ```plan code block.\n"
                f"When you include a ```plan block, the plan will be updated live in the editor and saved.\n\n"
                f"Plan format — each step is a markdown checkbox:\n"
                f"  - [ ] Step N: description          (pending)\n"
                f"  - [x] Step N: description          (done)\n"
                f"  - [>] Step N: description          (active)\n"
                f"  - [!] Step N: description          (failed)\n"
                f"  - [~] Step N: description          (blocked)\n"
                f"  Indented > lines are annotations the executor reads as context.\n\n"
                f"Example — to add two steps to a plan:\n"
                f"```plan\n"
                f"# Plan: fix the bugs\n\n"
                f"- [x] Step 1: Fix the crash\n"
                f"- [ ] Step 2: Add input validation\n"
                f"  > check for empty strings and None\n"
                f"- [ ] Step 3: Write tests\n"
                f"```\n\n"
                f"Be concise and direct. If the user asks you to change the plan, DO IT — "
                f"include the updated ```plan block. Don't just describe what you would do.\n\n"
                f"Project context:\n{context[:8000]}\n\n"
                f"Current plan:\n{plan_md}\n\n"
            )
            if daemon_history:
                system += f"Recent execution:\n{daemon_history[:2000]}\n"

            response = await chat_async(self._chat_messages, self.config, system=system)

            # Add response to history
            self._chat_messages.append({"role": "assistant", "content": response})

            # Check for plan update block in response
            plan_updated = self._apply_plan_from_response(response)

            # Display in exec log (same stream as everything else)
            # Strip the plan block from display since we applied it
            display_response = response
            if plan_updated:
                import re
                display_response = re.sub(r'```plan\n.*?```', '[plan updated]', response, flags=re.DOTALL)
                self._exec_write(f"[bold green]{self._chat_target}:[/bold green] {display_response}")
                self._exec_write(f"[bold yellow]Plan updated and saved.[/bold yellow]")
            else:
                self._exec_write(f"[bold green]{self._chat_target}:[/bold green] {response}")

            # Keep message history manageable
            if len(self._chat_messages) > 40:
                self._chat_messages = self._chat_messages[-40:]

        except Exception as e:
            self._exec_write(f"[red]Chat error: {e}[/red]")
            self._flog.error(f"Chat error: {e}")
        finally:
            self._chat_busy = False

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

    def _save_plan(self) -> None:
        editor = self.query_one("#plan-editor", PlanEditor)
        self.plan = editor.get_plan()
        plan_path = self.project_dir / ".reeree" / "plan.md"
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
        self._exec_write(f"[green]+[/green] Added: {description}")

    def _delete_step(self, index_str: str) -> None:
        try:
            idx = int(index_str) - 1
            if 0 <= idx < len(self.plan.steps):
                removed = self.plan.steps.pop(idx)
                editor = self.query_one("#plan-editor", PlanEditor)
                editor.load_plan(self.plan)
                self._save_plan()
                self._update_status()
                self._exec_write(f"[red]-[/red] Deleted step {index_str}: {removed.description}")
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
            if wid in self._daemons:
                log_text = self._daemons[wid].get("log", "No log yet")
                self._exec_write(f"[bold]Daemon {wid} log:[/bold]\n{log_text}")
            else:
                self.notify(f"No daemon {wid}", severity="warning")
        except ValueError:
            self.notify("Usage: :log [N]", severity="warning")

    def _show_file(self, path: str) -> None:
        full_path = self.project_dir / path
        if full_path.exists():
            content = full_path.read_text()
            self._exec_write(f"[bold]{path}[/bold]\n{content}")
        else:
            self.notify(f"File not found: {path}", severity="error")

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

    async def _dispatch_daemons(self) -> None:
        editor = self.query_one("#plan-editor", PlanEditor)
        self.plan = editor.get_plan()

        pending = self.plan.dispatchable_steps
        if not pending:
            self._exec_write("[dim]No pending steps to dispatch[/dim]")
            return

        self._exec_write(f"[bold]Dispatching {min(len(pending), 2)} daemon(s)...[/bold]")
        for idx, step in pending[:2]:
            daemon_id = self._next_daemon_id
            self._next_daemon_id += 1
            step.status = "active"
            step.daemon_id = daemon_id
            self._daemons[daemon_id] = {"status": "active", "step_index": idx, "log": ""}
            editor.update_step_status(idx, "active")
            self._update_status()
            self._exec_write(f"[cyan]▶ Daemon {daemon_id}:[/cyan] Step {idx+1} — {step.description}")

            self._run_daemon(daemon_id, step, idx)

    async def _run_daemon_task(self, daemon_id: int, step, step_index: int) -> None:
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
                summary = result.get('summary', '')
                self._exec_write(f"[green]✓ Daemon {daemon_id} done:[/green] {summary}")
                if commit_hash:
                    self._exec_write(f"  [dim]commit: {commit_hash}[/dim]")
            else:
                editor.update_step_status(step_index, "failed")
                self.plan.steps[step_index].status = "failed"
                self.plan.steps[step_index].error = result.get("error", "unknown")
                self._save_plan()
                self._exec_write(f"[red]✗ Daemon {daemon_id} failed:[/red] {result.get('error', '')}")

            self._daemons[daemon_id]["status"] = status
            self._update_status()

        except Exception as e:
            self._daemon_log(daemon_id, f"EXCEPTION: {e}")
            self._daemons[daemon_id]["status"] = "failed"
            self._exec_write(f"[red]✗ Daemon {daemon_id} exception:[/red] {e}")
            self._update_status()

    def _run_daemon(self, daemon_id: int, step, step_index: int) -> None:
        import asyncio
        asyncio.ensure_future(self._run_daemon_task(daemon_id, step, step_index))

    def _daemon_log(self, daemon_id: int, message: str) -> None:
        if daemon_id in self._daemons:
            self._daemons[daemon_id]["log"] += message + "\n"
        # Stream daemon output to exec log
        self._exec_write(f"  [dim][d{daemon_id}][/dim] {message}")

    async def _undo_step(self, step_str: str) -> None:
        from ..executor import git_revert_last
        result = git_revert_last(self.project_dir)
        if result.success:
            self._exec_write("[yellow]Reverted last step[/yellow]")
        else:
            self._exec_write(f"[red]Revert failed:[/red] {result.output}")

    async def _propagate(self) -> None:
        self._exec_write("[dim]Propagate: not yet implemented[/dim]")

    async def _cohere(self, args: str) -> None:
        docs = args.split()
        if not docs:
            self.notify("Usage: :cohere doc1.md doc2.md", severity="warning")
            return
        self._exec_write(f"[dim]Cohere ({len(docs)} docs): not yet implemented[/dim]")


class CommandScreen(ModalScreen[str]):
    """Vim-style : command input — appears at the very bottom of the screen."""

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
