"""Tests for reeree.context — focused context loading."""

import subprocess
from pathlib import Path

from reeree.context import gather_context, find_relevant_files, _find_parent_contexts
from reeree.plan import Step


class TestGatherContext:
    def test_includes_readme(self, tmp_project):
        step = Step(description="do something")
        ctx = gather_context(step, tmp_project)
        assert "Test Project" in ctx

    def test_includes_specified_files(self, tmp_project):
        step = Step(description="fix main", files=["main.py"])
        ctx = gather_context(step, tmp_project)
        assert "hello world" in ctx

    def test_includes_claude_md_if_exists(self, tmp_project):
        (tmp_project / "CLAUDE.md").write_text("# Project Rules\nDo not break things.\n")
        step = Step(description="do something")
        ctx = gather_context(step, tmp_project)
        assert "Do not break things" in ctx

    def test_respects_max_chars(self, tmp_project):
        # Write a large file
        (tmp_project / "big.py").write_text("x = 1\n" * 10000)
        step = Step(description="fix big file", files=["big.py"])
        ctx = gather_context(step, tmp_project, max_chars=1000)
        assert len(ctx) <= 1500  # some overhead for labels

    def test_missing_file_graceful(self, tmp_project):
        step = Step(description="fix nonexistent", files=["does_not_exist.py"])
        ctx = gather_context(step, tmp_project)
        # Should not crash, just skip missing file
        assert "does_not_exist" not in ctx or "NOT FOUND" not in ctx


class TestFindRelevantFiles:
    def test_finds_by_keyword(self, tmp_project):
        files = find_relevant_files("fix the main function", tmp_project)
        assert "main.py" in files

    def test_finds_utils(self, tmp_project):
        files = find_relevant_files("update utils helper", tmp_project)
        assert "utils.py" in files

    def test_respects_max_files(self, tmp_project):
        # Create many files
        for i in range(20):
            (tmp_project / f"module_{i}.py").write_text(f"# module {i}\n")
        files = find_relevant_files("module", tmp_project, max_files=5)
        assert len(files) <= 5

    def test_skips_hidden_dirs(self, tmp_project):
        hidden = tmp_project / ".hidden" / "secret.py"
        hidden.parent.mkdir()
        hidden.write_text("secret = True\n")
        files = find_relevant_files("secret", tmp_project)
        assert not any(".hidden" in f for f in files)


class TestParentContexts:
    def test_finds_parent_claude_md(self, tmp_path):
        """If project is inside a parent git repo, finds parent CLAUDE.md."""
        # Create parent repo
        parent = tmp_path / "parent"
        parent.mkdir()
        subprocess.run(["git", "init"], cwd=parent, capture_output=True)
        (parent / "CLAUDE.md").write_text("# Parent context\nImportant rules here.\n")

        # Create child project inside parent
        child = parent / "private" / "child"
        child.mkdir(parents=True)
        subprocess.run(["git", "init"], cwd=child, capture_output=True)

        contexts = _find_parent_contexts(child)
        assert len(contexts) >= 1
        labels = [label for label, _ in contexts]
        assert any("parent" in label for label in labels)
        contents = [content for _, content in contexts]
        assert any("Important rules here" in c for c in contents)

    def test_no_parent(self, tmp_path):
        """No parent context if project is top-level."""
        project = tmp_path / "standalone"
        project.mkdir()
        subprocess.run(["git", "init"], cwd=project, capture_output=True)

        contexts = _find_parent_contexts(project)
        # May find system-level repos or none — should not crash
        assert isinstance(contexts, list)

    def test_context_telescoping_in_gather(self, tmp_path):
        """gather_context includes parent CLAUDE.md when available."""
        parent = tmp_path / "parent"
        parent.mkdir()
        subprocess.run(["git", "init"], cwd=parent, capture_output=True)
        (parent / "CLAUDE.md").write_text("# Parent Rules\nAlways test first.\n")

        child = parent / "sub" / "project"
        child.mkdir(parents=True)
        subprocess.run(["git", "init"], cwd=child, capture_output=True)
        (child / "main.py").write_text("print('hello')\n")

        step = Step(description="fix main", files=["main.py"])
        ctx = gather_context(step, child)
        assert "Always test first" in ctx
