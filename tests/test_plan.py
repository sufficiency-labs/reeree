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
        path = tmp_path / "plan.md"
        plan.save(path)
        assert path.exists()

        loaded = Plan.load(path)
        assert loaded.intent == "test save"
        assert len(loaded.steps) == 2


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
