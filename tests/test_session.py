"""Tests for session state serialization — round-trip fidelity."""

import json
from pathlib import Path

from reeree.plan import Plan, Step
from reeree.daemon_registry import DaemonRegistry, DaemonKind, DaemonStatus
from reeree.message_bus import MessageBus, DaemonMessage, MessageKind
from reeree.session import (
    serialize_session,
    deserialize_session,
    save_session,
    load_session,
)


class TestSessionSerialization:
    def test_round_trip_empty_session(self):
        plan = Plan(intent="test", steps=[])
        registry = DaemonRegistry()
        bus = MessageBus()

        data = serialize_session(plan, registry, bus)
        restored = deserialize_session(data)

        assert restored["plan"].intent == "test"
        assert restored["plan"].steps == []
        assert restored["registry"].total_count == 0
        assert len(restored["message_bus"].history) == 0

    def test_round_trip_plan_with_steps(self):
        plan = Plan(intent="add error handling", steps=[
            Step(description="Read current code", status="done",
                 annotations=["files: scraper.py"], files=["scraper.py"],
                 commit_hash="abc1234"),
            Step(description="Add try/except", status="active",
                 annotations=["max 3 retries", "done: tests pass"],
                 daemon_id=1),
            Step(description="Update README", status="pending"),
        ])
        registry = DaemonRegistry()
        bus = MessageBus()

        data = serialize_session(plan, registry, bus)
        restored = deserialize_session(data)
        rplan = restored["plan"]

        assert rplan.intent == "add error handling"
        assert len(rplan.steps) == 3
        assert rplan.steps[0].status == "done"
        assert rplan.steps[0].commit_hash == "abc1234"
        assert rplan.steps[0].files == ["scraper.py"]
        assert rplan.steps[1].status == "active"
        assert rplan.steps[1].daemon_id == 1
        assert rplan.steps[1].annotations == ["max 3 retries", "done: tests pass"]
        assert rplan.steps[2].status == "pending"

    def test_round_trip_registry_with_daemons(self):
        registry = DaemonRegistry()
        d1 = registry.spawn(DaemonKind.EXECUTOR, "main executor")
        d2 = registry.spawn(DaemonKind.STEP, "step 1", parent_id=d1.id,
                           step_id="step-0", model="qwen3")
        d2.status = DaemonStatus.DONE
        d2.log = "Executed step 1\nDone\n"

        plan = Plan(intent="test", steps=[])
        data = serialize_session(plan, registry)
        restored = deserialize_session(data)
        rreg = restored["registry"]

        assert rreg.total_count == 2
        d1r = rreg.get(1)
        d2r = rreg.get(2)
        assert d1r.kind == DaemonKind.EXECUTOR
        assert d1r.description == "main executor"
        assert d2r.kind == DaemonKind.STEP
        assert d2r.parent_id == d1r.id
        assert d2r.step_id == "step-0"
        assert d2r.model == "qwen3"
        assert d2r.status == DaemonStatus.DONE
        assert "Executed step 1" in d2r.log

    def test_round_trip_message_bus(self):
        bus = MessageBus()
        bus.send(DaemonMessage(sender_id=1, recipient_id=2,
                               kind=MessageKind.NOTE, payload="hello"))
        bus.send(DaemonMessage(sender_id=2, recipient_id=None,
                               kind=MessageKind.CONFLICT, payload="clash"))

        plan = Plan(intent="test", steps=[])
        registry = DaemonRegistry()
        data = serialize_session(plan, registry, bus)
        restored = deserialize_session(data)
        rbus = restored["message_bus"]

        assert len(rbus.history) == 2
        assert rbus.history[0].payload == "hello"
        assert rbus.history[0].kind == MessageKind.NOTE
        assert rbus.history[1].kind == MessageKind.CONFLICT

    def test_round_trip_metadata(self):
        plan = Plan(intent="test", steps=[])
        registry = DaemonRegistry()

        data = serialize_session(plan, registry, project_dir="/home/user/project")

        restored = deserialize_session(data)
        assert restored["project_dir"] == "/home/user/project"

    def test_save_and_load(self, tmp_path):
        plan = Plan(intent="persistence test", steps=[
            Step(description="Step 1", status="done", commit_hash="abc1234"),
            Step(description="Step 2", status="pending"),
        ])
        registry = DaemonRegistry()
        registry.spawn(DaemonKind.EXECUTOR, "exec")
        bus = MessageBus()
        bus.send(DaemonMessage(sender_id=1, recipient_id=None,
                               kind=MessageKind.DONE, payload="finished"))

        path = tmp_path / ".reeree" / "session.json"
        save_session(path, plan, registry, bus, project_dir="/test")

        # File exists and is valid JSON
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["version"] == 1

        # Load it back
        restored = load_session(path)
        assert restored["plan"].intent == "persistence test"
        assert len(restored["plan"].steps) == 2
        assert restored["registry"].total_count == 1
        assert len(restored["message_bus"].history) == 1

    def test_version_check(self):
        """Unknown versions should raise."""
        import pytest
        with pytest.raises(ValueError, match="Unknown session version"):
            deserialize_session({"version": 99})

    def test_json_serializable(self):
        """The serialized output must be valid JSON."""
        plan = Plan(intent="json test", steps=[
            Step(description="has unicode: é à ñ 中文", status="pending"),
        ])
        registry = DaemonRegistry()
        registry.spawn(DaemonKind.COHERENCE, "coherence check")
        bus = MessageBus()

        data = serialize_session(plan, registry, bus)
        # Must not raise
        json_str = json.dumps(data)
        # Must round-trip through JSON
        parsed = json.loads(json_str)
        assert parsed["plan"]["intent"] == "json test"

    def test_next_id_preserved(self):
        """Registry's next_id should survive serialization."""
        registry = DaemonRegistry()
        registry.spawn(DaemonKind.EXECUTOR, "d1")
        registry.spawn(DaemonKind.STEP, "d2")
        registry.spawn(DaemonKind.STEP, "d3")
        # next_id should be 4

        plan = Plan(intent="test", steps=[])
        data = serialize_session(plan, registry)
        restored = deserialize_session(data)

        # The restored registry should continue from id 4
        rreg = restored["registry"]
        assert rreg._next_id == 4
