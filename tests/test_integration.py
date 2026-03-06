"""End-to-end integration tests for reeree TUI.

Tests the full user workflow: launch, vim modes, commands, file viewer,
command history, plan manipulation, daemon lifecycle.
Runs in headless mode via Textual's run_test().
"""

from pathlib import Path

import pytest

from reeree.config import Config
from reeree.plan import Plan, Step
from reeree.tui.app import (
    ReereeApp,
    PlanEditor,
    StatusBar,
    CommandScreen,
    FileViewer,
)
from reeree.daemon_registry import DaemonKind, DaemonStatus


def _cfg() -> Config:
    c = Config.__new__(Config)
    c.backend = "together"
    c.api_base = "https://api.together.xyz/v1"
    c.model = "test-model"
    c.api_key = "test-key-for-testing"
    c.claude_model = "sonnet"
    c.autonomy = "medium"
    c.project_dir = "."
    c.plan_file = ".reeree/plan.yaml"
    c.max_context_tokens = 24000
    c.default_doc = ""
    c.models = {}
    c.routing = {}
    return c


def _plan() -> Plan:
    return Plan(
        intent="fix the scraper bugs",
        steps=[
            Step(description="Add visited URL tracking", files=["scraper.py"]),
            Step(description="Add request timeouts", files=["scraper.py", "utils.py"]),
            Step(description="Write tests for error cases", status="done", commit_hash="abc1234"),
        ],
    )


def _app(tmp_path: Path, plan: Plan | None = None) -> ReereeApp:
    (tmp_path / ".reeree").mkdir(exist_ok=True)
    return ReereeApp(project_dir=tmp_path, config=_cfg(), plan=plan or _plan())


async def _cmd(app, pilot, cmd_str: str) -> None:
    """Submit a : command via the CommandScreen modal."""
    await pilot.press("colon")
    await pilot.pause()
    screen = app.screen
    if isinstance(screen, CommandScreen):
        inp = screen.query_one("#cmd-input")
        inp.value = cmd_str
        await pilot.press("enter")
        await pilot.pause()
    else:
        # Fallback: call execute_command directly
        await app.execute_command(cmd_str)
        await pilot.pause()


# ---------------------------------------------------------------------------
# Full session lifecycle
# ---------------------------------------------------------------------------

class TestFullWorkflow:

    @pytest.mark.asyncio
    async def test_launch_edit_command_quit(self, tmp_path):
        (tmp_path / "scraper.py").write_text("def scrape(): pass\n")
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            status = app.query_one("#status-bar", StatusBar)
            editor = app.query_one("#plan-editor", PlanEditor)

            # 1. starts NORMAL (vim-native)
            assert status.mode == "NORMAL"
            assert "Add visited URL tracking" in editor.text

            # 2. NORMAL → INSERT → NORMAL
            await pilot.press("i")
            assert status.mode == "INSERT"
            await pilot.press("escape")  # INSERT → NORMAL
            assert status.mode == "NORMAL"

            # 3. add a step via command
            await _cmd(app, pilot, 'add "Deploy to prod"')
            assert len(app.plan.steps) == 4
            assert app.plan.steps[3].description == "Deploy to prod"

            # 4. delete it
            await _cmd(app, pilot, "del 4")
            assert len(app.plan.steps) == 3

            # 5. save plan
            await _cmd(app, pilot, "w")
            plan_file = tmp_path / ".reeree" / "plan.yaml"
            assert plan_file.exists()
            assert "fix the scraper bugs" in plan_file.read_text()


# ---------------------------------------------------------------------------
# Vim modes
# ---------------------------------------------------------------------------

class TestVimModes:

    @pytest.mark.asyncio
    async def test_full_modal_cycle(self, tmp_path):
        """NORMAL → INSERT(i) → NORMAL → INSERT(a) → NORMAL → INSERT(o) → NORMAL → COMMAND → NORMAL"""
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            status = app.query_one("#status-bar", StatusBar)
            editor = app.query_one("#plan-editor", PlanEditor)

            assert status.mode == "NORMAL"
            assert editor.read_only

            for key in ("i", "a", "o"):
                await pilot.press(key)
                assert status.mode == "INSERT"
                assert not editor.read_only
                await pilot.press("escape")  # INSERT → NORMAL
                assert status.mode == "NORMAL"
                assert editor.read_only

            # COMMAND mode from NORMAL
            await pilot.press("colon")
            await pilot.pause()
            assert isinstance(app.screen, CommandScreen)
            await pilot.press("escape")
            await pilot.pause()
            assert status.mode == "NORMAL"

    @pytest.mark.asyncio
    async def test_rapid_mode_switching(self, tmp_path):
        """Rapidly toggling modes doesn't corrupt state."""
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            for _ in range(20):
                await pilot.press("i")
                await pilot.press("escape")
            status = app.query_one("#status-bar", StatusBar)
            assert status.mode == "NORMAL"
            assert app.query_one("#plan-editor", PlanEditor).read_only


# ---------------------------------------------------------------------------
# File viewer
# ---------------------------------------------------------------------------

class TestFileViewer:

    @pytest.mark.asyncio
    async def test_open_and_close(self, tmp_path):
        (tmp_path / "hello.py").write_text("print('hello')\n")
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._show_file("hello.py")
            await pilot.pause()
            assert app._file_viewer_path == tmp_path / "hello.py"

            app._close_file_viewer()
            await pilot.pause()
            assert app._file_viewer_path is None

    @pytest.mark.asyncio
    async def test_nonexistent_file(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._show_file("nope.py")
            await pilot.pause()
            assert app._file_viewer_path is None

    @pytest.mark.asyncio
    async def test_save(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("original")
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._show_file("test.txt")
            await pilot.pause()

            viewer = app.query_one("#file-viewer", FileViewer)
            viewer.read_only = False
            viewer.load_file("modified")
            viewer.read_only = True

            assert app._save_file_viewer() is True
            assert f.read_text() == "modified"
            app._close_file_viewer()

    @pytest.mark.asyncio
    async def test_q_closes_viewer_not_app(self, tmp_path):
        (tmp_path / "data.json").write_text('{"x":1}')
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._show_file("data.json")
            await pilot.pause()
            assert app._file_viewer_path is not None

            await app.execute_command("q")
            await pilot.pause()
            assert app._file_viewer_path is None

    @pytest.mark.asyncio
    async def test_empty_path_no_crash(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._show_file("")
            await pilot.pause()
            assert app._file_viewer_path is None

    @pytest.mark.asyncio
    async def test_language_map(self):
        assert FileViewer.LANG_MAP[".py"] == "python"
        assert FileViewer.LANG_MAP[".rs"] == "rust"
        assert FileViewer.LANG_MAP[".go"] == "go"
        assert FileViewer.LANG_MAP.get(".xyz") is None


# ---------------------------------------------------------------------------
# Command history
# ---------------------------------------------------------------------------

class TestCommandHistory:

    @pytest.mark.asyncio
    async def test_stored_in_history(self, tmp_path):
        CommandScreen._history.clear()
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await _cmd(app, pilot, "help")
            assert "help" in CommandScreen._history

    @pytest.mark.asyncio
    async def test_no_consecutive_duplicates(self, tmp_path):
        CommandScreen._history.clear()
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            for _ in range(3):
                await _cmd(app, pilot, "help")
            assert CommandScreen._history.count("help") == 1

    @pytest.mark.asyncio
    async def test_up_arrow_recalls(self, tmp_path):
        CommandScreen._history.clear()
        CommandScreen._history.extend(["add 'step 1'", "w", "help"])
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("colon")
            await pilot.pause()
            screen = app.screen
            inp = screen.query_one("#cmd-input")

            await pilot.press("up")
            assert inp.value == "help"
            await pilot.press("up")
            assert inp.value == "w"
            await pilot.press("up")
            assert inp.value == "add 'step 1'"
            # At beginning, stays
            await pilot.press("up")
            assert inp.value == "add 'step 1'"
            # Down goes forward
            await pilot.press("down")
            assert inp.value == "w"

            await pilot.press("escape")

    @pytest.mark.asyncio
    async def test_preserves_draft(self, tmp_path):
        CommandScreen._history.clear()
        CommandScreen._history.append("help")
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("colon")
            await pilot.pause()
            screen = app.screen
            inp = screen.query_one("#cmd-input")
            inp.value = "my draft"

            await pilot.press("up")
            assert inp.value == "help"
            await pilot.press("down")
            assert inp.value == "my draft"

            await pilot.press("escape")


# ---------------------------------------------------------------------------
# Daemon lifecycle
# ---------------------------------------------------------------------------

class TestDaemonLifecycle:

    @pytest.mark.asyncio
    async def test_spawn_and_kill(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            d = app._daemon_registry.spawn(DaemonKind.EXECUTOR, "test")
            assert d.id == 1

            await app.execute_command("kill 1")
            await pilot.pause()
            assert app._daemon_registry.get(1).status == DaemonStatus.FAILED
            assert app._daemon_registry.get(1).error == "killed"

    @pytest.mark.asyncio
    async def test_pause_resume(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._daemon_registry.spawn(DaemonKind.STEP, "step 1")

            app._daemon_registry.pause(1)
            assert app._daemon_registry.get(1).status == DaemonStatus.PAUSED

            app._daemon_registry.resume(1)
            assert app._daemon_registry.get(1).status == DaemonStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_kill_nonexistent(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("kill 999")
            await pilot.pause()
            # No crash


# ---------------------------------------------------------------------------
# Plan manipulation
# ---------------------------------------------------------------------------

class TestPlanManipulation:

    @pytest.mark.asyncio
    async def test_add_del_move(self, tmp_path):
        app = _app(tmp_path, plan=Plan(intent="test", steps=[
            Step(description="Step A"),
            Step(description="Step B"),
        ]))
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command('add "Step C"')
            await pilot.pause()
            assert len(app.plan.steps) == 3
            assert app.plan.steps[2].description == "Step C"

            await app.execute_command("move 3 1")
            await pilot.pause()
            assert app.plan.steps[0].description == "Step C"

            await app.execute_command("del 1")
            await pilot.pause()
            assert len(app.plan.steps) == 2
            assert app.plan.steps[0].description == "Step A"

    @pytest.mark.asyncio
    async def test_save_and_load(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("w")
            await pilot.pause()
            plan_path = tmp_path / ".reeree" / "plan.yaml"
            assert plan_path.exists()
            content = plan_path.read_text()
            assert "fix the scraper bugs" in content
            assert "abc1234" in content

    @pytest.mark.asyncio
    async def test_del_out_of_range(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("del 99")
            await pilot.pause()
            assert len(app.plan.steps) == 3


# ---------------------------------------------------------------------------
# Chat panel
# ---------------------------------------------------------------------------

class TestChatPanel:

    @pytest.mark.asyncio
    async def test_open_close(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("chat")
            await pilot.pause()
            panel = app.query_one("#chat-panel")
            assert panel.has_class("visible")
            assert app._chat_target == "executor"

            await app.execute_command("close")
            await pilot.pause()
            assert not panel.has_class("visible")

    @pytest.mark.asyncio
    async def test_target_switch(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("chat coherence")
            await pilot.pause()
            assert app._chat_target == "coherence"
            assert app._chat_messages == []


# ---------------------------------------------------------------------------
# Config commands
# ---------------------------------------------------------------------------

class TestConfigCommands:

    @pytest.mark.asyncio
    async def test_set_model(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("set model qwen3:8b")
            await pilot.pause()
            assert app.config.model == "qwen3:8b"

    @pytest.mark.asyncio
    async def test_set_autonomy_levels(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            for level in ("low", "medium", "high", "full"):
                await app.execute_command(f"set autonomy {level}")
                await pilot.pause()
                assert app.config.autonomy == level


# ---------------------------------------------------------------------------
# Status bar
# ---------------------------------------------------------------------------

class TestStatusBar:

    @pytest.mark.asyncio
    async def test_progress_tracking(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            status = app.query_one("#status-bar", StatusBar)
            # 1 done out of 3
            assert status.progress == (1, 3)

            app.plan.steps[0].status = "done"
            app._update_status()
            await pilot.pause()
            assert status.progress == (2, 3)

    @pytest.mark.asyncio
    async def test_daemon_count(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            status = app.query_one("#status-bar", StatusBar)
            assert status.active_daemons == 0

            app._daemon_registry.spawn(DaemonKind.EXECUTOR, "test")
            app._update_status()
            await pilot.pause()
            assert status.active_daemons == 1

    @pytest.mark.asyncio
    async def test_empty_plan(self, tmp_path):
        app = _app(tmp_path, plan=Plan(intent="empty", steps=[]))
        async with app.run_test(size=(120, 40)) as pilot:
            status = app.query_one("#status-bar", StatusBar)
            assert status.progress == (0, 0)


# ---------------------------------------------------------------------------
# Help and edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    @pytest.mark.asyncio
    async def test_help_no_crash(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("help")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_unknown_command(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("xyzzy")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_scope_shows(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("scope")
            await pilot.pause()
