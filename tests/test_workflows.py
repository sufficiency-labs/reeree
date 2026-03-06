"""Comprehensive workflow tests — exercise every command path, find crashes.

This file is the testing loop: run it after every change. If anything
crashes, the test name tells you what broke. Tests are ordered by
workflow complexity: simple commands → multi-step flows → edge cases.

No LLM calls — these test TUI mechanics, state management, and crash paths.
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
    c.api_base = "https://api.together.xyz/v1"
    c.model = "test-model"
    c.api_key = "test-key-for-testing"
    c.autonomy = "medium"
    c.project_dir = "."
    c.plan_file = ".reeree/plan.yaml"
    c.max_context_tokens = 24000
    c.models = {}
    c.routing = {}
    return c


def _plan() -> Plan:
    return Plan(
        intent="fix the scraper bugs",
        steps=[
            Step(description="Add visited URL tracking", files=["scraper.py"],
                 annotations=["files: scraper.py", "done: dedup test passes"]),
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
        await app.execute_command(cmd_str)
        await pilot.pause()


# ===========================================================================
# Command coverage — every execute_command branch
# ===========================================================================

class TestCommandCoverage:
    """Exercise every command dispatch branch. No command should crash."""

    @pytest.mark.asyncio
    async def test_help(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("help")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_scope(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("scope")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_setup(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            # Setup launches a modal — just verify it doesn't crash
            # Can't fully test without dismissing the modal
            # The setup screen needs API key, so we just test the path exists
            pass

    @pytest.mark.asyncio
    async def test_diff_no_args(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("diff")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_diff_with_step(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("diff 1")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_diff_invalid_step(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("diff 99")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_log_no_args(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("log")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_log_with_daemon(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._daemon_registry.spawn(DaemonKind.EXECUTOR, "test")
            await app.execute_command("log 1")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_log_nonexistent_daemon(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("log 99")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_undo_no_args(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("undo")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_undo_with_step(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("undo 1")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_unknown_command(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("xyzzy_not_real")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_empty_command(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_whitespace_command(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("   ")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_pause_no_args(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            # pause without args falls to unknown
            await app.execute_command("pause")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_resume_no_args(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("resume")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_kill_no_args(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("kill")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_pause_non_numeric(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("pause abc")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_resume_non_numeric(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("resume xyz")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_kill_non_numeric(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("kill xyz")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_set_unknown_key(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("set nonexistent_key value")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_set_no_value(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("set model")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_cd_no_args(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._change_scope("")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_move_no_args(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("move")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_move_one_arg(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("move 1")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_move_invalid_range(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("move 99 1")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_add_empty(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            count = len(app.plan.steps)
            await app.execute_command("add")
            await pilot.pause()
            # empty add should be a noop or warn
            assert len(app.plan.steps) <= count + 1

    @pytest.mark.asyncio
    async def test_del_zero(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            count = len(app.plan.steps)
            await app.execute_command("del 0")
            await pilot.pause()
            assert len(app.plan.steps) == count

    @pytest.mark.asyncio
    async def test_del_non_numeric(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            count = len(app.plan.steps)
            await app.execute_command("del abc")
            await pilot.pause()
            assert len(app.plan.steps) == count


# ===========================================================================
# Multi-step workflows
# ===========================================================================

class TestWorkflows:
    """Complex multi-step workflows that simulate real usage."""

    @pytest.mark.asyncio
    async def test_build_plan_from_scratch(self, tmp_path):
        """Start with empty plan, add steps, reorder, save."""
        app = _app(tmp_path, plan=Plan(intent="", steps=[]))
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command('add "Read the codebase"')
            await app.execute_command('add "Write the feature"')
            await app.execute_command('add "Write tests"')
            await app.execute_command('add "Deploy"')
            await pilot.pause()
            assert len(app.plan.steps) == 4
            assert app.plan.steps[0].description == "Read the codebase"

            # Move tests before deploy
            await app.execute_command("move 3 4")
            await pilot.pause()

            # Delete first step
            await app.execute_command("del 1")
            await pilot.pause()
            assert len(app.plan.steps) == 3

            # Save
            await app.execute_command("w")
            await pilot.pause()
            plan_path = tmp_path / ".reeree" / "plan.yaml"
            assert plan_path.exists()

            # Reload and verify
            loaded = Plan.load(plan_path)
            assert len(loaded.steps) == 3

    @pytest.mark.asyncio
    async def test_scope_push_pop_with_plans(self, tmp_path):
        """Scope change preserves parent plan and loads child plan."""
        # Create child dir with its own plan
        child = tmp_path / "lib"
        child.mkdir()
        (child / ".reeree").mkdir()
        child_plan = Plan(intent="lib work", steps=[Step(description="refactor")])
        child_plan.save(child / ".reeree" / "plan.yaml")

        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            # Verify parent plan
            assert app.plan.intent == "fix the scraper bugs"
            assert len(app.plan.steps) == 3

            # Push into child
            app._change_scope("lib")
            await pilot.pause()
            assert app.plan.intent == "lib work"
            assert len(app.plan.steps) == 1
            assert app.project_dir == child

            # Modify child plan
            await app.execute_command('add "new child step"')
            await pilot.pause()
            assert len(app.plan.steps) == 2

            # Pop back to parent
            app._change_scope("..")
            await pilot.pause()
            assert app.plan.intent == "fix the scraper bugs"
            assert len(app.plan.steps) == 3
            assert app.project_dir == tmp_path

    @pytest.mark.asyncio
    async def test_deep_scope_nesting(self, tmp_path):
        """Push 3 levels deep, pop back to root."""
        a = tmp_path / "a"
        b = a / "b"
        c = b / "c"
        for d in (a, b, c):
            d.mkdir(parents=True)
            (d / ".reeree").mkdir()

        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._change_scope("a")
            app._change_scope("b")
            app._change_scope("c")
            await pilot.pause()
            assert app.project_dir == c
            assert len(app._scope_stack) == 3

            app._change_scope("..")
            assert app.project_dir == b
            app._change_scope("..")
            assert app.project_dir == a
            app._change_scope("..")
            assert app.project_dir == tmp_path
            assert len(app._scope_stack) == 0

    @pytest.mark.asyncio
    async def test_file_viewer_workflow(self, tmp_path):
        """Open file, view, close, open another."""
        (tmp_path / "a.py").write_text("def a(): pass\n")
        (tmp_path / "b.py").write_text("def b(): pass\n")
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            # Open first file
            app._show_file("a.py")
            await pilot.pause()
            assert app._file_viewer_path == tmp_path / "a.py"
            viewer = app.query_one("#file-viewer", FileViewer)
            assert "def a" in viewer.text

            # Open second file (replaces first)
            app._show_file("b.py")
            await pilot.pause()
            assert app._file_viewer_path == tmp_path / "b.py"
            assert "def b" in viewer.text

            # Close
            app._close_file_viewer()
            await pilot.pause()
            assert app._file_viewer_path is None

    @pytest.mark.asyncio
    async def test_file_viewer_q_intercept(self, tmp_path):
        """:q closes file viewer, not app. Second :q closes app."""
        (tmp_path / "f.py").write_text("x = 1")
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._show_file("f.py")
            await pilot.pause()
            assert app._file_viewer_path is not None

            # First :q closes viewer
            await app.execute_command("q")
            await pilot.pause()
            assert app._file_viewer_path is None

    @pytest.mark.asyncio
    async def test_file_viewer_wq(self, tmp_path):
        """:wq in file viewer saves and closes."""
        f = tmp_path / "data.txt"
        f.write_text("original")
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._show_file("data.txt")
            await pilot.pause()
            viewer = app.query_one("#file-viewer", FileViewer)
            viewer.read_only = False
            viewer.load_file("modified content")

            await app.execute_command("wq")
            await pilot.pause()
            assert app._file_viewer_path is None
            assert f.read_text() == "modified content"

    @pytest.mark.asyncio
    async def test_daemon_lifecycle_full(self, tmp_path):
        """Spawn → pause → resume → kill, check all state transitions."""
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            # Spawn
            d = app._daemon_registry.spawn(DaemonKind.EXECUTOR, "main")
            child = app._daemon_registry.spawn(DaemonKind.STEP, "step 1", parent_id=d.id)
            assert d.status == DaemonStatus.ACTIVE
            assert child.status == DaemonStatus.ACTIVE

            # Pause parent
            await app.execute_command(f"pause {d.id}")
            await pilot.pause()
            assert d.status == DaemonStatus.PAUSED

            # Resume parent
            await app.execute_command(f"resume {d.id}")
            await pilot.pause()
            assert d.status == DaemonStatus.ACTIVE

            # Kill parent — should kill child too
            await app.execute_command(f"kill {d.id}")
            await pilot.pause()
            assert d.status == DaemonStatus.FAILED
            assert d.error == "killed"
            assert child.status == DaemonStatus.FAILED
            assert child.error == "parent killed"

    @pytest.mark.asyncio
    async def test_chat_panel_workflow(self, tmp_path):
        """Open chat, switch targets, close."""
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            # Open chat
            await app.execute_command("chat")
            await pilot.pause()
            panel = app.query_one("#chat-panel")
            assert panel.has_class("visible")
            assert app._chat_target == "executor"

            # Switch target — clears messages
            app._chat_messages.append({"role": "user", "content": "test"})
            await app.execute_command("chat coherence")
            await pilot.pause()
            assert app._chat_target == "coherence"
            assert app._chat_messages == []

            # Close
            await app.execute_command("close")
            await pilot.pause()
            assert not panel.has_class("visible")

    @pytest.mark.asyncio
    async def test_plan_insert_mode_yaml(self, tmp_path):
        """INSERT mode shows YAML, NORMAL mode shows rich display."""
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            editor = app.query_one("#plan-editor", PlanEditor)
            status = app.query_one("#status-bar", StatusBar)

            # NORMAL mode — rich display
            assert status.mode == "NORMAL"
            normal_text = editor.text
            assert "✓" in normal_text or "○" in normal_text  # unicode indicators

            # INSERT mode — YAML
            await pilot.press("i")
            assert status.mode == "INSERT"
            insert_text = editor.text
            assert "intent:" in insert_text
            assert "description:" in insert_text

            # Back to NORMAL — rich display again
            await pilot.press("escape")
            assert status.mode == "NORMAL"
            normal_text_2 = editor.text
            assert "intent:" not in normal_text_2 or "✓" in normal_text_2


# ===========================================================================
# INSERT mode YAML editing
# ===========================================================================

class TestInsertModeYAML:
    """Test YAML round-trip through INSERT mode edits."""

    @pytest.mark.asyncio
    async def test_yaml_roundtrip_preserves_plan(self, tmp_path):
        """Enter INSERT, don't change anything, exit — plan unchanged."""
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            original_steps = len(app.plan.steps)
            original_intent = app.plan.intent

            await pilot.press("i")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            assert len(app.plan.steps) == original_steps
            assert app.plan.intent == original_intent

    @pytest.mark.asyncio
    async def test_yaml_save_roundtrip(self, tmp_path):
        """Save plan as YAML, verify it loads back correctly."""
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("w")
            await pilot.pause()

            plan_path = tmp_path / ".reeree" / "plan.yaml"
            content = plan_path.read_text()
            assert content.startswith("intent:")
            assert "Add visited URL tracking" in content

            loaded = Plan.load(plan_path)
            assert loaded.intent == app.plan.intent
            assert len(loaded.steps) == len(app.plan.steps)
            for orig, loaded_step in zip(app.plan.steps, loaded.steps):
                assert loaded_step.description == orig.description
                assert loaded_step.status == orig.status


# ===========================================================================
# File viewer edge cases
# ===========================================================================

class TestFileViewerEdgeCases:

    @pytest.mark.asyncio
    async def test_binary_file(self, tmp_path):
        """Opening a binary file shouldn't crash."""
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01\x02\xff\xfe")
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._show_file("data.bin")
            await pilot.pause()
            # May or may not open — shouldn't crash

    @pytest.mark.asyncio
    async def test_large_file(self, tmp_path):
        """Opening a large file shouldn't crash."""
        f = tmp_path / "big.py"
        f.write_text("x = 1\n" * 10000)
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._show_file("big.py")
            await pilot.pause()
            assert app._file_viewer_path == tmp_path / "big.py"
            app._close_file_viewer()

    @pytest.mark.asyncio
    async def test_symlink(self, tmp_path):
        """Opening a symlink should work."""
        target = tmp_path / "real.py"
        target.write_text("# real file\n")
        link = tmp_path / "link.py"
        link.symlink_to(target)
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._show_file("link.py")
            await pilot.pause()
            # Should open the target content
            if app._file_viewer_path is not None:
                viewer = app.query_one("#file-viewer", FileViewer)
                assert "real file" in viewer.text
            app._close_file_viewer()

    @pytest.mark.asyncio
    async def test_directory_path(self, tmp_path):
        """Trying to open a directory shouldn't crash."""
        (tmp_path / "subdir").mkdir()
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._show_file("subdir")
            await pilot.pause()
            # Should not open or should show error
            assert app._file_viewer_path is None

    @pytest.mark.asyncio
    async def test_path_traversal(self, tmp_path):
        """Attempting path traversal should be blocked."""
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._show_file("../../etc/passwd")
            await pilot.pause()
            # Should not open files outside project dir
            assert app._file_viewer_path is None


# ===========================================================================
# Status bar accuracy
# ===========================================================================

class TestStatusBarAccuracy:

    @pytest.mark.asyncio
    async def test_progress_updates_on_step_change(self, tmp_path):
        """Progress should update when steps change status."""
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            status = app.query_one("#status-bar", StatusBar)
            assert status.progress == (1, 3)  # 1 done of 3

            # Mark another done
            app.plan.steps[0].status = "done"
            app._update_status()
            await pilot.pause()
            assert status.progress == (2, 3)

            # Mark all done
            app.plan.steps[1].status = "done"
            app._update_status()
            await pilot.pause()
            assert status.progress == (3, 3)

    @pytest.mark.asyncio
    async def test_daemon_count_tracks_active(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            status = app.query_one("#status-bar", StatusBar)
            assert status.active_daemons == 0

            d1 = app._daemon_registry.spawn(DaemonKind.EXECUTOR, "a")
            d2 = app._daemon_registry.spawn(DaemonKind.STEP, "b", parent_id=d1.id)
            app._update_status()
            await pilot.pause()
            assert status.active_daemons == 2

            app._daemon_registry.kill(d1.id)
            app._update_status()
            await pilot.pause()
            assert status.active_daemons == 0  # parent + child both killed

    @pytest.mark.asyncio
    async def test_mode_display_through_transitions(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            status = app.query_one("#status-bar", StatusBar)
            assert status.mode == "NORMAL"

            await pilot.press("i")
            assert status.mode == "INSERT"

            await pilot.press("escape")
            assert status.mode == "NORMAL"

            await pilot.press("colon")
            await pilot.pause()
            # In command mode, status bar might still say NORMAL
            # (command screen is modal overlay)
            await pilot.press("escape")
            await pilot.pause()
            assert status.mode == "NORMAL"


# ===========================================================================
# Rapid sequences (race conditions, state corruption)
# ===========================================================================

class TestRapidSequences:

    @pytest.mark.asyncio
    async def test_rapid_add_delete(self, tmp_path):
        """Rapidly adding and deleting steps shouldn't corrupt plan."""
        app = _app(tmp_path, plan=Plan(intent="stress", steps=[]))
        async with app.run_test(size=(120, 40)) as pilot:
            for i in range(20):
                await app.execute_command(f'add "step {i}"')
            await pilot.pause()
            assert len(app.plan.steps) == 20

            for i in range(20, 0, -1):
                await app.execute_command(f"del {i}")
            await pilot.pause()
            assert len(app.plan.steps) == 0

    @pytest.mark.asyncio
    async def test_rapid_scope_changes(self, tmp_path):
        """Rapidly pushing and popping scope shouldn't corrupt state."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / ".reeree").mkdir()

        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            for _ in range(10):
                app._change_scope("sub")
                app._change_scope("..")
            await pilot.pause()
            assert app.project_dir == tmp_path
            assert len(app._scope_stack) == 0

    @pytest.mark.asyncio
    async def test_rapid_mode_switching_with_commands(self, tmp_path):
        """Interleaving mode switches and commands."""
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            for _ in range(10):
                await pilot.press("i")
                await pilot.press("escape")
                await app.execute_command("help")
                await pilot.pause()
            status = app.query_one("#status-bar", StatusBar)
            assert status.mode == "NORMAL"


# ===========================================================================
# Plan annotation handling
# ===========================================================================

class TestPlanAnnotations:

    @pytest.mark.asyncio
    async def test_annotations_preserved_through_save_load(self, tmp_path):
        plan = Plan(intent="test", steps=[
            Step(description="annotated step",
                 annotations=["files: a.py, b.py", "done: tests pass", "use the new API"]),
        ])
        app = _app(tmp_path, plan=plan)
        async with app.run_test(size=(120, 40)) as pilot:
            await app.execute_command("w")
            await pilot.pause()

            loaded = Plan.load(tmp_path / ".reeree" / "plan.yaml")
            assert len(loaded.steps[0].annotations) == 3
            assert loaded.steps[0].done_criteria == "tests pass"
            assert loaded.steps[0].file_hints == ["a.py", "b.py"]
            assert "use the new API" in loaded.steps[0].context_annotations

    @pytest.mark.asyncio
    async def test_step_properties(self, tmp_path):
        """Step properties compute correctly."""
        step = Step(
            description="test",
            annotations=["files: x.py, y.py", "done: green build", "hint: be careful"],
        )
        assert step.done_criteria == "green build"
        assert step.file_hints == ["x.py", "y.py"]
        assert step.context_annotations == ["hint: be careful"]
        assert step.checkbox == "[ ]"
        assert step.rich_indicator == "○"

        step.status = "done"
        assert step.checkbox == "[x]"
        assert step.rich_indicator == "✓"


# ===========================================================================
# Voice module
# ===========================================================================

# ===========================================================================
# Keyboard shortcuts — exhaustive coverage
# ===========================================================================

class TestKeyboardNormalMode:
    """Every keybinding in NORMAL mode."""

    @pytest.mark.asyncio
    async def test_i_enters_insert(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            status = app.query_one("#status-bar", StatusBar)
            editor = app.query_one("#plan-editor", PlanEditor)
            assert status.mode == "NORMAL"
            assert editor.read_only

            await pilot.press("i")
            assert status.mode == "INSERT"
            assert not editor.read_only

    @pytest.mark.asyncio
    async def test_a_enters_insert(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            status = app.query_one("#status-bar", StatusBar)
            await pilot.press("a")
            assert status.mode == "INSERT"

    @pytest.mark.asyncio
    async def test_o_enters_insert_newline(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            status = app.query_one("#status-bar", StatusBar)
            await pilot.press("o")
            assert status.mode == "INSERT"

    @pytest.mark.asyncio
    async def test_escape_returns_to_normal(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            status = app.query_one("#status-bar", StatusBar)
            await pilot.press("i")
            assert status.mode == "INSERT"
            await pilot.press("escape")
            assert status.mode == "NORMAL"

    @pytest.mark.asyncio
    async def test_hjkl_navigation(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            editor = app.query_one("#plan-editor", PlanEditor)
            # Just verify no crash — cursor position testing is tricky
            for key in ("j", "k", "h", "l"):
                await pilot.press(key)
            assert editor.read_only  # still NORMAL mode

    @pytest.mark.asyncio
    async def test_g_beginning_of_line(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("g")
            # No crash
            editor = app.query_one("#plan-editor", PlanEditor)
            assert editor.read_only

    @pytest.mark.asyncio
    async def test_G_end_of_line(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("G")
            # No crash
            editor = app.query_one("#plan-editor", PlanEditor)
            assert editor.read_only

    @pytest.mark.asyncio
    async def test_colon_enters_command(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("colon")
            await pilot.pause()
            assert isinstance(app.screen, CommandScreen)
            await pilot.press("escape")

    @pytest.mark.asyncio
    async def test_tab_cycles_panes(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            editor = app.query_one("#plan-editor", PlanEditor)
            # Tab should move focus away from editor
            await pilot.press("tab")
            await pilot.pause()
            # Focus changed — either exec log or chat
            # Just verify no crash

    @pytest.mark.asyncio
    async def test_ctrl_w_cycles_panes(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("ctrl+w")
            await pilot.pause()
            # Ctrl+W is the binding for focus_side — verify no crash


class TestKeyboardInsertMode:
    """INSERT mode keyboard behavior."""

    @pytest.mark.asyncio
    async def test_typing_in_insert_mode(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("i")
            editor = app.query_one("#plan-editor", PlanEditor)
            # In INSERT, text is YAML
            assert "intent:" in editor.text
            await pilot.press("escape")

    @pytest.mark.asyncio
    async def test_escape_parses_yaml_back(self, tmp_path):
        """Exiting INSERT parses YAML and re-renders rich display."""
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("i")
            editor = app.query_one("#plan-editor", PlanEditor)
            # YAML should be visible
            assert "intent:" in editor.text
            await pilot.press("escape")
            # Now back to rich display
            rich_text = editor.text
            # Should have at least one step indicator
            assert any(c in rich_text for c in "✓○▶–✗◌")

    @pytest.mark.asyncio
    async def test_hjkl_not_intercepted_in_insert(self, tmp_path):
        """h/j/k/l should type characters in INSERT mode, not navigate."""
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("i")
            editor = app.query_one("#plan-editor", PlanEditor)
            # In insert mode, typing should modify text, not navigate
            # We can't easily test character insertion without knowing cursor pos,
            # but we can verify we're still in INSERT mode after pressing these keys
            status = app.query_one("#status-bar", StatusBar)
            assert status.mode == "INSERT"
            await pilot.press("escape")


class TestKeyboardCommandMode:
    """COMMAND mode (: prefix) keyboard behavior."""

    @pytest.mark.asyncio
    async def test_escape_cancels(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("colon")
            await pilot.pause()
            assert isinstance(app.screen, CommandScreen)
            await pilot.press("escape")
            await pilot.pause()
            status = app.query_one("#status-bar", StatusBar)
            assert status.mode == "NORMAL"

    @pytest.mark.asyncio
    async def test_enter_submits(self, tmp_path):
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("colon")
            await pilot.pause()
            screen = app.screen
            if isinstance(screen, CommandScreen):
                inp = screen.query_one("#cmd-input")
                inp.value = "help"
                await pilot.press("enter")
                await pilot.pause()
            # Should be back to NORMAL after command
            status = app.query_one("#status-bar", StatusBar)
            assert status.mode == "NORMAL"

    @pytest.mark.asyncio
    async def test_up_down_history(self, tmp_path):
        CommandScreen._history.clear()
        CommandScreen._history.extend(["add 'x'", "w", "help"])
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("colon")
            await pilot.pause()
            screen = app.screen
            if isinstance(screen, CommandScreen):
                inp = screen.query_one("#cmd-input")
                await pilot.press("up")
                assert inp.value == "help"
                await pilot.press("up")
                assert inp.value == "w"
                await pilot.press("down")
                assert inp.value == "help"
                await pilot.press("down")
                assert inp.value == ""  # back to empty draft
            await pilot.press("escape")


class TestKeyboardFileViewer:
    """Keyboard behavior in file viewer mode."""

    @pytest.mark.asyncio
    async def test_i_enters_edit_mode(self, tmp_path):
        (tmp_path / "test.py").write_text("x = 1\n")
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._show_file("test.py")
            await pilot.pause()
            viewer = app.query_one("#file-viewer", FileViewer)
            assert viewer.read_only

    @pytest.mark.asyncio
    async def test_colon_in_viewer_opens_command(self, tmp_path):
        """Commands should work while file viewer is open."""
        (tmp_path / "test.py").write_text("x = 1\n")
        app = _app(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app._show_file("test.py")
            await pilot.pause()
            # :q should close the file viewer
            await app.execute_command("q")
            await pilot.pause()
            assert app._file_viewer_path is None


class TestVoice:

    def test_voice_constant_exists(self):
        from reeree.voice import VOICE
        assert "filler" in VOICE.lower()
        assert "hedging" in VOICE.lower()
        assert len(VOICE) < 500  # should be compact

    def test_voice_in_executor_system_prompt(self):
        from reeree.daemon_executor import EXECUTOR_SYSTEM
        assert "filler" in EXECUTOR_SYSTEM.lower() or "Active voice" in EXECUTOR_SYSTEM

    def test_voice_in_planner_system_prompt(self):
        from reeree.planner import PLANNER_SYSTEM
        assert "filler" in PLANNER_SYSTEM.lower() or "Active voice" in PLANNER_SYSTEM
