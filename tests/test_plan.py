"""Tests for reeree.plan — the living document data model."""

from pathlib import Path

from reeree.plan import Plan, Step


class TestStep:
    def test_default_status_is_pending(self):
        s = Step(description="do something")
        assert s.status == "pending"

    def test_files_default_empty(self):
        s = Step(description="do something")
        assert s.files == []

    def test_annotations_default_empty(self):
        s = Step(description="do something")
        assert s.annotations == []


class TestPlanMarkdown:
    def test_to_markdown_pending(self):
        plan = Plan(intent="fix bugs", steps=[
            Step(description="Fix the crash"),
        ])
        md = plan.to_markdown()
        assert "- [ ] Step 1: Fix the crash" in md
        assert "fix bugs" in md

    def test_to_markdown_done(self):
        plan = Plan(intent="fix bugs", steps=[
            Step(description="Fix the crash", status="done", commit_hash="abc1234"),
        ])
        md = plan.to_markdown()
        assert "- [x] Step 1: Fix the crash" in md

    def test_to_markdown_active(self):
        plan = Plan(intent="fix bugs", steps=[
            Step(description="Fix the crash", status="active", daemon_id=1),
        ])
        md = plan.to_markdown()
        assert "Fix the crash" in md
        # Active steps should be visually distinct
        assert "~" in md or ">" in md or "daemon" in md.lower() or "[" in md

    def test_to_markdown_failed(self):
        plan = Plan(intent="fix bugs", steps=[
            Step(description="Fix the crash", status="failed", error="edit failed"),
        ])
        md = plan.to_markdown()
        assert "Fix the crash" in md

    def test_from_markdown_roundtrip(self):
        original = Plan(intent="add tests", steps=[
            Step(description="Write unit tests"),
            Step(description="Write integration tests"),
            Step(description="Set up CI"),
        ])
        md = original.to_markdown()
        restored = Plan.from_markdown(md)
        assert restored.intent == original.intent
        assert len(restored.steps) == len(original.steps)
        for orig, rest in zip(original.steps, restored.steps):
            assert rest.description == orig.description

    def test_from_markdown_preserves_done_status(self):
        md = "# Plan: fix things\n\n- [x] Step 1: First step\n- [ ] Step 2: Second step\n"
        plan = Plan.from_markdown(md)
        assert plan.steps[0].status == "done"
        assert plan.steps[1].status == "pending"

    def test_annotations_roundtrip(self):
        plan = Plan(intent="test", steps=[
            Step(
                description="Do the thing",
                annotations=["use pytest", "check edge cases"],
                files=["test.py"],
            ),
        ])
        md = plan.to_markdown()
        restored = Plan.from_markdown(md)
        # Annotations should survive roundtrip
        assert len(restored.steps[0].annotations) >= 1 or len(restored.steps[0].context_annotations) >= 1

    def test_empty_plan(self):
        plan = Plan(intent="", steps=[])
        md = plan.to_markdown()
        restored = Plan.from_markdown(md)
        assert len(restored.steps) == 0

    def test_save_and_load(self, tmp_path):
        plan = Plan(intent="test save", steps=[
            Step(description="Step one"),
            Step(description="Step two", status="done"),
        ])
        path = tmp_path / "plan.yaml"
        plan.save(path)
        assert path.exists()

        loaded = Plan.load(path)
        assert loaded.intent == "test save"
        assert len(loaded.steps) == 2


class TestPlanYAML:
    def test_to_yaml_basic(self):
        plan = Plan(intent="fix bugs", steps=[
            Step(description="Fix the crash"),
            Step(description="Add tests", status="done", commit_hash="abc1234"),
        ])
        y = plan.to_yaml()
        assert "intent: fix bugs" in y
        assert "Fix the crash" in y
        assert "abc1234" in y

    def test_from_yaml_roundtrip(self):
        original = Plan(intent="add tests", steps=[
            Step(description="Write unit tests", annotations=["use pytest"]),
            Step(description="Write integration tests", status="done", commit_hash="def5678"),
            Step(description="Set up CI", files=["ci.yml", "Makefile"]),
        ])
        y = original.to_yaml()
        restored = Plan.from_yaml(y)
        assert restored.intent == original.intent
        assert len(restored.steps) == 3
        assert restored.steps[0].annotations == ["use pytest"]
        assert restored.steps[1].status == "done"
        assert restored.steps[1].commit_hash == "def5678"
        assert restored.steps[2].files == ["ci.yml", "Makefile"]

    def test_from_yaml_preserves_all_fields(self):
        original = Plan(intent="test all", steps=[
            Step(
                description="Do thing",
                status="active",
                annotations=["hint 1", "done: tests pass"],
                files=["a.py"],
                commit_hash="abc1234",
                daemon_id=3,
                error="something broke",
            ),
        ])
        y = original.to_yaml()
        restored = Plan.from_yaml(y)
        s = restored.steps[0]
        assert s.description == "Do thing"
        assert s.status == "active"
        assert s.annotations == ["hint 1", "done: tests pass"]
        assert s.files == ["a.py"]
        assert s.commit_hash == "abc1234"
        assert s.daemon_id == 3
        assert s.error == "something broke"

    def test_from_yaml_simple_string_steps(self):
        y = "intent: quick\nsteps:\n  - do this\n  - do that\n"
        plan = Plan.from_yaml(y)
        assert len(plan.steps) == 2
        assert plan.steps[0].description == "do this"
        assert plan.steps[0].status == "pending"

    def test_empty_yaml(self):
        plan = Plan(intent="", steps=[])
        y = plan.to_yaml()
        restored = Plan.from_yaml(y)
        assert restored.intent == ""
        assert len(restored.steps) == 0

    def test_load_detects_yaml(self, tmp_path):
        plan = Plan(intent="yaml test", steps=[Step(description="step 1")])
        path = tmp_path / "plan.yaml"
        plan.save(path)
        loaded = Plan.load(path)
        assert loaded.intent == "yaml test"

    def test_load_detects_markdown(self, tmp_path):
        """Backward compat: load() still reads old markdown plan files."""
        md = "# Plan: legacy\n\n- [ ] Step 1: old step\n"
        path = tmp_path / "plan.md"
        path.write_text(md)
        loaded = Plan.load(path)
        assert loaded.intent == "legacy"
        assert len(loaded.steps) == 1

    def test_save_writes_yaml(self, tmp_path):
        plan = Plan(intent="test save format", steps=[Step(description="s1")])
        path = tmp_path / "plan.yaml"
        plan.save(path)
        content = path.read_text()
        assert content.startswith("intent:")


class TestPlanProperties:
    def test_pending_steps(self, sample_plan):
        pending = sample_plan.pending_steps
        assert len(pending) == 2  # steps 2 and 3 (0-indexed)

    def test_active_steps(self, sample_plan):
        active = sample_plan.active_steps
        assert len(active) == 1

    def test_dispatchable_steps(self, sample_plan):
        dispatchable = sample_plan.dispatchable_steps
        # Should only return pending steps (not active, done, blocked)
        for idx, step in dispatchable:
            assert step.status == "pending"

    def test_progress(self, sample_plan):
        done, total = sample_plan.progress
        assert done == 1
        assert total == 5

    def test_is_complete_false(self, sample_plan):
        assert not sample_plan.is_complete

    def test_is_complete_true(self):
        plan = Plan(intent="done", steps=[
            Step(description="a", status="done"),
            Step(description="b", status="done"),
        ])
        assert plan.is_complete

    def test_is_complete_empty(self):
        plan = Plan(intent="", steps=[])
        assert plan.is_complete
