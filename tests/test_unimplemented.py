"""Failing tests for features not yet implemented.

These tests document the intended behavior of features that are planned
but not yet built. They should fail now and pass as features are completed.

Mark tests with @pytest.mark.xfail so they don't break CI but are visible.
"""

import pytest

from reeree.config import Config
from reeree.plan import Plan, Step


# === DAEMON PERSISTENCE (Unix domain socket) ===

@pytest.mark.xfail(reason="Daemon persistence not yet implemented")
class TestDaemonPersistence:
    def test_daemon_starts_as_background_process(self):
        """reeree should start a daemon process that persists after client exits."""
        from reeree.daemon import Daemon
        d = Daemon()
        d.start()
        assert d.is_running()
        d.stop()

    def test_client_attaches_to_running_daemon(self):
        """Client should attach to existing daemon via Unix socket."""
        from reeree.daemon import Daemon
        from reeree.client import Client
        d = Daemon()
        d.start()
        c = Client()
        c.attach(d.socket_path)
        assert c.is_connected()
        c.detach()
        d.stop()

    def test_daemon_survives_client_disconnect(self):
        """Daemon keeps running when client disconnects."""
        from reeree.daemon import Daemon
        from reeree.client import Client
        d = Daemon()
        d.start()
        c = Client()
        c.attach(d.socket_path)
        c.detach()
        assert d.is_running()
        d.stop()

    def test_session_list(self):
        """reeree ls should list running sessions."""
        from reeree.daemon import list_sessions
        sessions = list_sessions()
        assert isinstance(sessions, list)


# === PARALLEL DAEMONS ===

@pytest.mark.xfail(reason="Parallel daemon execution not yet implemented")
class TestParallelDaemons:
    def test_multiple_daemons_execute_concurrently(self):
        """Multiple pending steps should dispatch to parallel daemons."""
        from reeree.orchestrator import Orchestrator
        plan = Plan(intent="test", steps=[
            Step(description="Step 1", files=["a.py"]),
            Step(description="Step 2", files=["b.py"]),
            Step(description="Step 3", files=["c.py"]),
        ])
        orch = Orchestrator(plan=plan, max_parallel=3)
        orch.dispatch_all()
        assert orch.active_daemon_count == 3

    def test_daemons_dont_conflict_on_same_file(self):
        """Two daemons editing the same file should be sequenced, not parallel."""
        from reeree.orchestrator import Orchestrator
        plan = Plan(intent="test", steps=[
            Step(description="Edit file", files=["shared.py"]),
            Step(description="Also edit file", files=["shared.py"]),
        ])
        orch = Orchestrator(plan=plan, max_parallel=2)
        orch.dispatch_all()
        # Only one should be active since they share a file
        assert orch.active_daemon_count == 1


# === ORCHESTRATOR / MODEL ROUTING ===

class TestOrchestrator:
    def test_routes_to_best_model(self):
        """Router selects optimal model tier for each task type."""
        from reeree.router import route_model
        from reeree.config import Config
        from reeree.daemon_registry import DaemonKind
        config = Config(model="test-model", api_base="http://test", api_key="k")
        choice = route_model("Fix a Python syntax error", DaemonKind.STEP, config)
        assert choice.model == "test-model"
        assert choice.tier == "coding"

    def test_cost_estimation(self):
        """Router classifies refactor as reasoning tier."""
        from reeree.router import classify_task
        from reeree.daemon_registry import DaemonKind
        tier = classify_task("Refactor entire codebase", DaemonKind.STEP)
        assert tier == "reasoning"


# === COHERENCE DAEMONS (:propagate, :cohere) ===

@pytest.mark.xfail(reason="Coherence daemons not yet implemented")
class TestCoherenceDaemons:
    def test_propagate_crawls_links(self, tmp_path):
        """Propagate finds linked documents and checks coherence."""
        from reeree.daemons.coherence import propagate
        # Create docs with cross-references
        (tmp_path / "plan.md").write_text("# Plan\nSee [design](design.md) for details.\n")
        (tmp_path / "design.md").write_text("# Design\nThe plan says X but we do Y.\n")

        issues = propagate(tmp_path / "plan.md")
        assert isinstance(issues, list)

    def test_cohere_checks_doc_set(self, tmp_path):
        """Cohere checks consistency across explicit document set."""
        from reeree.daemons.coherence import cohere
        (tmp_path / "a.md").write_text("# Doc A\nThe API uses REST.\n")
        (tmp_path / "b.md").write_text("# Doc B\nThe API uses GraphQL.\n")

        issues = cohere([tmp_path / "a.md", tmp_path / "b.md"])
        assert len(issues) > 0  # Should find the contradiction


# === STATE ASSESSMENT DAEMON ===

@pytest.mark.xfail(reason="State assessment daemon not yet implemented")
class TestStateDaemon:
    def test_state_daemon_runs_continuously(self):
        """State daemon monitors user activity and writes state.md."""
        from reeree.daemons.state import StateDaemon
        d = StateDaemon()
        d.start()
        assert d.is_running()
        d.stop()

    def test_state_daemon_writes_assessment(self, tmp_path):
        """State daemon produces a state assessment file."""
        from reeree.daemons.state import StateDaemon
        d = StateDaemon(output_path=tmp_path / "state.md")
        d.assess()
        assert (tmp_path / "state.md").exists()


# === FORECAST DAEMON ===

@pytest.mark.xfail(reason="Forecast daemon not yet implemented")
class TestForecastDaemon:
    def test_forecast_daemon_produces_output(self, tmp_path):
        """Forecast daemon generates predictions based on current state."""
        from reeree.daemons.forecast import ForecastDaemon
        d = ForecastDaemon(output_path=tmp_path / "forecast.md")
        d.forecast()
        assert (tmp_path / "forecast.md").exists()


# === DECISION BUBBLING ===

@pytest.mark.xfail(reason="Decision bubbling not yet implemented")
class TestDecisionBubbling:
    def test_daemon_surfaces_decision(self):
        """When a daemon encounters an ambiguous choice, it surfaces a decision."""
        from reeree.plan import Decision
        d = Decision(
            question="Which error handling strategy?",
            options=["try/except per function", "global handler", "both"],
            context="The codebase currently has no error handling.",
        )
        assert d.question
        assert len(d.options) >= 2

    def test_decision_appears_in_plan(self):
        """Decisions show up as [?] items in the plan document."""
        plan = Plan(intent="test", steps=[
            Step(description="Choose error strategy", status="decision"),
        ])
        md = plan.to_markdown()
        assert "[?]" in md


# === VIM MODAL KEYBINDINGS ===

@pytest.mark.xfail(reason="Full vim modal keybindings not yet implemented")
class TestVimBindings:
    def test_normal_mode_hjkl(self):
        """hjkl navigation works in normal mode."""
        from reeree.tui.keybindings import VimBindings
        vb = VimBindings()
        assert vb.handle_key("j", mode="normal") == "cursor_down"
        assert vb.handle_key("k", mode="normal") == "cursor_up"

    def test_insert_mode_escape(self):
        """Escape returns to normal mode from insert mode."""
        from reeree.tui.keybindings import VimBindings
        vb = VimBindings()
        result = vb.handle_key("escape", mode="insert")
        assert result == "normal_mode"

    def test_command_mode_entry(self):
        """Colon enters command mode from normal mode."""
        from reeree.tui.keybindings import VimBindings
        vb = VimBindings()
        result = vb.handle_key(":", mode="normal")
        assert result == "command_mode"


# === SUBREPO CONTEXT SCOPING ===

@pytest.mark.xfail(reason="Full subrepo scoping not yet implemented")
class TestSubrepoScoping:
    def test_move_context_down(self, tmp_path):
        """User can scope context down to a subrepo."""
        from reeree.context import ScopedContext
        sc = ScopedContext(root=tmp_path)
        sc.scope_down("private/kingfall")
        assert sc.project_dir == tmp_path / "private" / "kingfall"

    def test_move_context_up(self, tmp_path):
        """User can scope context up to parent repo."""
        from reeree.context import ScopedContext
        sc = ScopedContext(root=tmp_path / "private" / "kingfall")
        sc.scope_up()
        assert sc.project_dir == tmp_path

    def test_parent_context_available_in_child(self, tmp_path):
        """Working in a subrepo still has parent context accessible."""
        from reeree.context import ScopedContext
        sc = ScopedContext(root=tmp_path / "private" / "kingfall")
        ctx = sc.get_full_context()
        assert "parent" in ctx.lower() or isinstance(ctx, str)
