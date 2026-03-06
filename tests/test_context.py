"""Tests for reeree.context — focused context loading + cross-reference following."""

import subprocess
from pathlib import Path

from reeree.context import (
    gather_context,
    find_relevant_files,
    _find_parent_contexts,
    extract_cross_references,
)
from reeree.plan import Step


class TestExtractCrossReferences:
    def test_finds_markdown_links(self, tmp_path):
        """Extracts relative paths from [text](path) links."""
        (tmp_path / "other.md").write_text("# Other doc")
        text = "See [the other doc](other.md) for details."
        refs = extract_cross_references(text, tmp_path)
        assert len(refs) == 1
        assert refs[0].name == "other.md"

    def test_skips_urls(self, tmp_path):
        """Ignores http/https links."""
        text = "See [docs](https://example.com) and [more](http://foo.bar)."
        refs = extract_cross_references(text, tmp_path)
        assert refs == []

    def test_skips_anchors(self, tmp_path):
        """Ignores #anchor-only links."""
        text = "See [section](#overview) below."
        refs = extract_cross_references(text, tmp_path)
        assert refs == []

    def test_strips_anchor_from_path(self, tmp_path):
        """Resolves file.md#section to file.md."""
        (tmp_path / "doc.md").write_text("# Doc")
        text = "See [section](doc.md#details)."
        refs = extract_cross_references(text, tmp_path)
        assert len(refs) == 1
        assert refs[0].name == "doc.md"

    def test_resolves_directory_to_readme(self, tmp_path):
        """Directory links resolve to README.md inside."""
        sub = tmp_path / "people" / "alice"
        sub.mkdir(parents=True)
        (sub / "README.md").write_text("# Alice")
        text = "See [Alice](people/alice/)."
        refs = extract_cross_references(text, tmp_path)
        assert len(refs) == 1
        assert refs[0].name == "README.md"

    def test_skips_nonexistent(self, tmp_path):
        """Skips links to files that don't exist."""
        text = "See [missing](does-not-exist.md)."
        refs = extract_cross_references(text, tmp_path)
        assert refs == []

    def test_deduplicates(self, tmp_path):
        """Same file referenced twice → only one entry."""
        (tmp_path / "doc.md").write_text("# Doc")
        text = "See [doc](doc.md) and [also doc](doc.md)."
        refs = extract_cross_references(text, tmp_path)
        assert len(refs) == 1

    def test_multiple_refs(self, tmp_path):
        """Extracts multiple distinct references."""
        (tmp_path / "a.md").write_text("# A")
        (tmp_path / "b.md").write_text("# B")
        text = "See [a](a.md) and [b](b.md)."
        refs = extract_cross_references(text, tmp_path)
        assert len(refs) == 2

    def test_relative_parent_paths(self, tmp_path):
        """Handles ../ relative paths."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "parent.md").write_text("# Parent")
        text = "See [parent](../parent.md)."
        refs = extract_cross_references(text, sub)
        assert len(refs) == 1
        assert refs[0].name == "parent.md"

    def test_skips_mailto(self, tmp_path):
        """Ignores mailto: links."""
        text = "Email [me](mailto:test@test.com)."
        refs = extract_cross_references(text, tmp_path)
        assert refs == []


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

    def test_follows_cross_references(self, tmp_path):
        """Loads files linked from project docs."""
        (tmp_path / "CLAUDE.md").write_text("See [other](other.md) for details.")
        (tmp_path / "other.md").write_text("# Cross-referenced content here")
        step = Step(description="test")
        ctx = gather_context(step, tmp_path, follow_references=True)
        assert "Cross-referenced content" in ctx

    def test_no_cross_refs_when_disabled(self, tmp_path):
        """Skips cross-references when follow_references=False."""
        (tmp_path / "CLAUDE.md").write_text("See [other](other.md) for details.")
        (tmp_path / "other.md").write_text("# Should not appear")
        step = Step(description="test")
        ctx = gather_context(step, tmp_path, follow_references=False)
        assert "Should not appear" not in ctx

    def test_cross_refs_truncated(self, tmp_path):
        """Individual cross-ref files capped at 5K chars."""
        (tmp_path / "CLAUDE.md").write_text("See [big](big.md).")
        (tmp_path / "big.md").write_text("x" * 20000)
        step = Step(description="test")
        ctx = gather_context(step, tmp_path, follow_references=True)
        assert "truncated" in ctx

    def test_no_duplicate_loads(self, tmp_path):
        """Same file not loaded twice (project file + cross-ref)."""
        (tmp_path / "CLAUDE.md").write_text("See [readme](README.md).")
        (tmp_path / "README.md").write_text("# The readme")
        step = Step(description="test")
        ctx = gather_context(step, tmp_path)
        assert ctx.count("The readme") == 1


class TestFindRelevantFiles:
    def test_finds_by_keyword(self, tmp_project):
        files = find_relevant_files("fix the main function", tmp_project)
        assert "main.py" in files

    def test_finds_utils(self, tmp_project):
        files = find_relevant_files("update utils helper", tmp_project)
        assert "utils.py" in files

    def test_respects_max_files(self, tmp_project):
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
        parent = tmp_path / "parent"
        parent.mkdir()
        subprocess.run(["git", "init"], cwd=parent, capture_output=True)
        (parent / "CLAUDE.md").write_text("# Parent context\nImportant rules here.\n")

        child = parent / "private" / "child"
        child.mkdir(parents=True)
        subprocess.run(["git", "init"], cwd=child, capture_output=True)

        contexts = _find_parent_contexts(child)
        assert len(contexts) >= 1
        assert any("Important rules here" in c for _, c in contexts)

    def test_no_parent(self, tmp_path):
        project = tmp_path / "standalone"
        project.mkdir()
        subprocess.run(["git", "init"], cwd=project, capture_output=True)
        contexts = _find_parent_contexts(project)
        assert isinstance(contexts, list)

    def test_context_telescoping_in_gather(self, tmp_path):
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
