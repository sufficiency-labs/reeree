"""Tests for reeree.task_discovery — queued task file parsing and discovery."""

import textwrap
from pathlib import Path

import pytest

from reeree.task_discovery import (
    parse_task_file,
    discover_tasks,
    task_to_steps,
    task_to_plan,
    format_task_list,
    TaskFile,
)


class TestParseTaskFile:
    def test_parses_title(self, tmp_path):
        """Extracts title from # heading."""
        f = tmp_path / "task.md"
        f.write_text("# Fix the auth bug\n\n**STATUS:** PENDING\n")
        tf = parse_task_file(f)
        assert tf.title == "Fix the auth bug"

    def test_parses_status_bold(self, tmp_path):
        """Parses **STATUS:** format."""
        f = tmp_path / "task.md"
        f.write_text("# Task\n\n**STATUS:** PENDING\n**PRIORITY:** HIGH\n")
        tf = parse_task_file(f)
        assert tf.status == "PENDING"
        assert tf.priority == "HIGH"

    def test_parses_status_list(self, tmp_path):
        """Parses - **Status**: format (task-engine style)."""
        f = tmp_path / "task.md"
        f.write_text("# Task\n\n- **Status**: OPEN\n- **Priority**: MEDIUM\n")
        tf = parse_task_file(f)
        assert tf.status == "OPEN"
        assert tf.priority == "MEDIUM"

    def test_parses_sections(self, tmp_path):
        """Extracts ## sections."""
        f = tmp_path / "task.md"
        f.write_text(textwrap.dedent("""\
            # Task

            **STATUS:** PENDING

            ## Implementation Order

            1. Do thing A
            2. Do thing B

            ## Success Criteria

            - A works
            - B works
        """))
        tf = parse_task_file(f)
        assert "Implementation Order" in tf.sections
        assert "Do thing A" in tf.sections["Implementation Order"]
        assert "Success Criteria" in tf.sections

    def test_parses_description(self, tmp_path):
        """Extracts first paragraph after metadata."""
        f = tmp_path / "task.md"
        f.write_text(textwrap.dedent("""\
            # Fix Auth

            **STATUS:** PENDING
            **PRIORITY:** HIGH

            The auth system is broken and needs fixing.

            ## Steps
        """))
        tf = parse_task_file(f)
        assert "auth system is broken" in tf.description

    def test_is_actionable(self, tmp_path):
        """Actionable = PENDING, OPEN, or READY."""
        f = tmp_path / "task.md"
        f.write_text("# Task\n\n**STATUS:** PENDING\n")
        assert parse_task_file(f).is_actionable

        f.write_text("# Task\n\n**STATUS:** OPEN\n")
        assert parse_task_file(f).is_actionable

        f.write_text("# Task\n\n**STATUS:** COMPLETE\n")
        assert not parse_task_file(f).is_actionable

    def test_filename(self, tmp_path):
        """Filename property returns stem.md."""
        f = tmp_path / "my-task.md"
        f.write_text("# Task\n")
        assert parse_task_file(f).filename == "my-task.md"


class TestDiscoverTasks:
    def test_finds_tasks_in_coordination_queued(self, tmp_path):
        """Discovers tasks in coordination/queued/."""
        queued = tmp_path / "coordination" / "queued"
        queued.mkdir(parents=True)
        (queued / "task-a.md").write_text("# Task A\n\n**STATUS:** PENDING\n")
        (queued / "task-b.md").write_text("# Task B\n\n**STATUS:** PENDING\n")
        (queued / "README.md").write_text("# README\n")  # should be skipped

        tasks = discover_tasks(tmp_path)
        assert len(tasks) == 2
        titles = {t.title for t in tasks}
        assert "Task A" in titles
        assert "Task B" in titles

    def test_skips_completed_tasks(self, tmp_path):
        """Filters out non-actionable tasks by default."""
        queued = tmp_path / "coordination" / "queued"
        queued.mkdir(parents=True)
        (queued / "task-a.md").write_text("# Task A\n\n**STATUS:** PENDING\n")
        (queued / "task-b.md").write_text("# Task B\n\n**STATUS:** COMPLETE\n")

        tasks = discover_tasks(tmp_path)
        assert len(tasks) == 1
        assert tasks[0].title == "Task A"

    def test_include_done(self, tmp_path):
        """include_done=True returns all tasks."""
        queued = tmp_path / "coordination" / "queued"
        queued.mkdir(parents=True)
        (queued / "task-a.md").write_text("# Task A\n\n**STATUS:** PENDING\n")
        (queued / "task-b.md").write_text("# Task B\n\n**STATUS:** COMPLETE\n")

        tasks = discover_tasks(tmp_path, include_done=True)
        assert len(tasks) == 2

    def test_finds_tasks_in_reeree_tasks(self, tmp_path):
        """Discovers tasks in .reeree/tasks/."""
        tasks_dir = tmp_path / ".reeree" / "tasks"
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "local-task.md").write_text("# Local Task\n\n**STATUS:** PENDING\n")

        tasks = discover_tasks(tmp_path)
        assert len(tasks) == 1
        assert tasks[0].title == "Local Task"

    def test_empty_when_no_dirs(self, tmp_path):
        """Returns empty list when no task directories exist."""
        tasks = discover_tasks(tmp_path)
        assert tasks == []

    def test_walks_up_for_coordination(self, tmp_path):
        """Finds coordination/queued/ in parent directories."""
        queued = tmp_path / "coordination" / "queued"
        queued.mkdir(parents=True)
        (queued / "task.md").write_text("# Parent Task\n\n**STATUS:** PENDING\n")

        sub = tmp_path / "private" / "myproject"
        sub.mkdir(parents=True)

        tasks = discover_tasks(sub)
        assert len(tasks) == 1
        assert tasks[0].title == "Parent Task"

    def test_skips_summary_and_index(self, tmp_path):
        """Skips README.md, SUMMARY.md, INDEX.md."""
        queued = tmp_path / "coordination" / "queued"
        queued.mkdir(parents=True)
        (queued / "README.md").write_text("# README\n")
        (queued / "SUMMARY.md").write_text("# Summary\n")
        (queued / "INDEX.md").write_text("# Index\n")
        (queued / "real-task.md").write_text("# Real\n\n**STATUS:** PENDING\n")

        tasks = discover_tasks(tmp_path)
        assert len(tasks) == 1


class TestTaskToSteps:
    def test_extracts_implementation_steps(self, tmp_path):
        """Parses numbered items from Implementation Order section."""
        f = tmp_path / "task.md"
        f.write_text(textwrap.dedent("""\
            # Build the widget

            **STATUS:** PENDING

            ## Implementation Order

            1. Create widget.py with base class
            2. Add rendering logic
            3. Write tests
        """))
        tf = parse_task_file(f)
        steps = task_to_steps(tf)
        assert len(steps) == 3
        assert "Create widget.py" in steps[0].description
        assert "rendering logic" in steps[1].description
        assert "Write tests" in steps[2].description

    def test_extracts_bulleted_items(self, tmp_path):
        """Parses - items from Steps section."""
        f = tmp_path / "task.md"
        f.write_text(textwrap.dedent("""\
            # Fix things

            **STATUS:** PENDING

            ## Steps

            - Fix the database connection
            - Update the config file
        """))
        tf = parse_task_file(f)
        steps = task_to_steps(tf)
        assert len(steps) == 2

    def test_fallback_single_step(self, tmp_path):
        """Creates one step from title when no implementation section."""
        f = tmp_path / "task.md"
        f.write_text("# Migrate the database\n\n**STATUS:** PENDING\n")
        tf = parse_task_file(f)
        steps = task_to_steps(tf)
        assert len(steps) == 1
        assert "Migrate the database" in steps[0].description

    def test_adds_source_annotation(self, tmp_path):
        """Each step has source: filename annotation."""
        f = tmp_path / "my-task.md"
        f.write_text("# Task\n\n**STATUS:** PENDING\n")
        tf = parse_task_file(f)
        steps = task_to_steps(tf)
        assert any("source: my-task.md" in a for a in steps[0].annotations)

    def test_adds_success_criteria(self, tmp_path):
        """Appends done: annotation from Success Criteria section."""
        f = tmp_path / "task.md"
        f.write_text(textwrap.dedent("""\
            # Task

            **STATUS:** PENDING

            ## Implementation Order

            1. Do the thing

            ## Success Criteria

            All tests pass and docs updated
        """))
        tf = parse_task_file(f)
        steps = task_to_steps(tf)
        assert any("done:" in a for a in steps[-1].annotations)

    def test_adds_context_annotation(self, tmp_path):
        """Adds context from Problem/Context section to first step."""
        f = tmp_path / "task.md"
        f.write_text(textwrap.dedent("""\
            # Task

            **STATUS:** PENDING

            ## Problem

            The system crashes on startup.

            ## Implementation Order

            1. Fix the crash
        """))
        tf = parse_task_file(f)
        steps = task_to_steps(tf)
        assert any("crashes on startup" in a for a in steps[0].annotations)

    def test_strips_markdown_formatting(self, tmp_path):
        """Strips bold and code formatting from step descriptions."""
        f = tmp_path / "task.md"
        f.write_text(textwrap.dedent("""\
            # Task

            **STATUS:** PENDING

            ## Implementation Order

            1. Create **widget.py** with `BaseWidget` class
        """))
        tf = parse_task_file(f)
        steps = task_to_steps(tf)
        assert "**" not in steps[0].description
        assert "`" not in steps[0].description


class TestTaskToPlan:
    def test_creates_plan(self, tmp_path):
        """Converts task to Plan with intent and steps."""
        f = tmp_path / "task.md"
        f.write_text(textwrap.dedent("""\
            # Build the widget

            **STATUS:** PENDING

            ## Implementation Order

            1. Create the file
            2. Write the code
        """))
        tf = parse_task_file(f)
        plan = task_to_plan(tf)
        assert plan.intent == "Build the widget"
        assert len(plan.steps) == 2


class TestFormatTaskList:
    def test_formats_empty(self):
        """Empty list → message."""
        assert "No queued tasks" in format_task_list([])

    def test_formats_tasks(self, tmp_path):
        """Formats task list with numbers and priority markers."""
        tasks = [
            TaskFile(path=tmp_path / "a.md", title="High Task", priority="HIGH"),
            TaskFile(path=tmp_path / "b.md", title="Low Task", priority="LOW"),
        ]
        output = format_task_list(tasks)
        assert "1." in output
        assert "2." in output
        assert "High Task" in output
        assert "Low Task" in output
        assert ":load-task" in output
