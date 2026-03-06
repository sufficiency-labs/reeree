"""Tests for inline machine task parsing and splicing."""

from reeree.machine_tasks import find_tasks, mark_in_progress, splice_result, find_in_progress


class TestFindTasks:
    """Find [machine: ...] annotations in text."""

    def test_single_task(self):
        text = "Here is some text [machine: research topic X] and more text."
        tasks = find_tasks(text)
        assert len(tasks) == 1
        assert tasks[0].description == "research topic X"

    def test_multiple_tasks(self):
        text = (
            "First [machine: do thing A] then "
            "second [machine: do thing B] done."
        )
        tasks = find_tasks(text)
        assert len(tasks) == 2
        assert tasks[0].description == "do thing A"
        assert tasks[1].description == "do thing B"

    def test_no_tasks(self):
        text = "Just regular markdown with [links](url) and stuff."
        tasks = find_tasks(text)
        assert len(tasks) == 0

    def test_does_not_match_markdown_links(self):
        text = "See [machine: looks like a task](but-its-a-link)"
        tasks = find_tasks(text)
        assert len(tasks) == 0

    def test_preserves_offsets(self):
        text = "abc [machine: task] xyz"
        tasks = find_tasks(text)
        assert tasks[0].start == 4
        assert tasks[0].end == 19
        assert text[tasks[0].start:tasks[0].end] == "[machine: task]"

    def test_multiword_description(self):
        text = "[machine: put a bulleted list of his sins here, one I can draft from]"
        tasks = find_tasks(text)
        assert len(tasks) == 1
        assert "bulleted list" in tasks[0].description

    def test_task_id_generated(self):
        tasks = find_tasks("[machine: test]")
        assert tasks[0].task_id.startswith("mt-")

    def test_whitespace_in_description_trimmed(self):
        text = "[machine:   lots of spaces   ]"
        tasks = find_tasks(text)
        assert tasks[0].description == "lots of spaces"


class TestMarkInProgress:
    """Replace [machine: ...] with [⏳ ...]."""

    def test_single_task(self):
        text = "Text [machine: do thing] more."
        tasks = find_tasks(text)
        result = mark_in_progress(text, tasks)
        assert "[⏳ do thing]" in result
        assert "[machine:" not in result

    def test_multiple_tasks(self):
        text = "[machine: A] and [machine: B]"
        tasks = find_tasks(text)
        result = mark_in_progress(text, tasks)
        assert "[⏳ A]" in result
        assert "[⏳ B]" in result
        assert "[machine:" not in result

    def test_preserves_surrounding_text(self):
        text = "before [machine: task] after"
        tasks = find_tasks(text)
        result = mark_in_progress(text, tasks)
        assert result == "before [⏳ task] after"


class TestSpliceResult:
    """Replace [⏳ description] with result text."""

    def test_inline_result(self):
        text = "His failures include [⏳ list failures] and more."
        result = splice_result(text, "list failures", "losing money, bad tweets")
        assert result == "His failures include losing money, bad tweets and more."
        assert "⏳" not in result

    def test_multiline_result_on_own_line(self):
        text = "[⏳ list items]\nMore text"
        result = splice_result(text, "list items", "- item 1\n- item 2")
        assert "- item 1" in result
        assert "- item 2" in result
        assert "⏳" not in result

    def test_multiline_result_after_inline_text(self):
        text = "Things: [⏳ list them] next paragraph"
        result = splice_result(text, "list them", "- a\n- b\n- c")
        assert "- a" in result
        assert "⏳" not in result

    def test_no_match_returns_unchanged(self):
        text = "no progress markers here"
        result = splice_result(text, "nonexistent", "whatever")
        assert result == text

    def test_description_with_special_chars(self):
        text = "[⏳ list (important) items [now]]"
        result = splice_result(text, "list (important) items [now]", "done")
        assert result == "done"


class TestFindInProgress:
    """Find tasks currently in progress."""

    def test_finds_progress_markers(self):
        text = "Text [⏳ doing thing] more [⏳ other thing] end."
        in_progress = find_in_progress(text)
        assert len(in_progress) == 2
        assert "doing thing" in in_progress
        assert "other thing" in in_progress

    def test_no_markers(self):
        text = "Clean document with no tasks."
        assert find_in_progress(text) == []
