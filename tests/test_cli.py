"""Tests for reeree.cli — init and default document discovery."""

import json
from pathlib import Path

from reeree.cli import DEFAULT_DOCS, REEREE_GITIGNORE, init_reeree_dir, _discover_default_doc
from reeree.config import Config
from reeree.plan import Plan


class TestInitReereeDir:
    def test_creates_directory_structure(self, tmp_path):
        """init creates .reeree/ with config.json, plan.yaml, .gitignore, local/."""
        init_reeree_dir(tmp_path)

        reeree_dir = tmp_path / ".reeree"
        assert reeree_dir.is_dir()
        assert (reeree_dir / "config.json").is_file()
        assert (reeree_dir / "plan.yaml").is_file()
        assert (reeree_dir / ".gitignore").is_file()
        assert (reeree_dir / "local").is_dir()

    def test_gitignore_contents(self, tmp_path):
        """Gitignore excludes session files and local/."""
        init_reeree_dir(tmp_path)

        gitignore = (tmp_path / ".reeree" / ".gitignore").read_text()
        assert "session.json" in gitignore
        assert "session.log" in gitignore
        assert "local/" in gitignore

    def test_config_is_valid_json(self, tmp_path):
        """config.json is valid and loadable."""
        init_reeree_dir(tmp_path)

        config = Config.load(tmp_path / ".reeree" / "config.json")
        assert config.api_base  # has a default

    def test_plan_is_valid_yaml(self, tmp_path):
        """plan.yaml is valid and loadable."""
        init_reeree_dir(tmp_path)

        plan = Plan.load(tmp_path / ".reeree" / "plan.yaml")
        assert plan.steps == []

    def test_idempotent(self, tmp_path):
        """Running init twice doesn't overwrite existing files."""
        init_reeree_dir(tmp_path)

        # Modify config
        config_file = tmp_path / ".reeree" / "config.json"
        config = Config(model="custom-model")
        config.save(config_file)

        # Run init again
        init_reeree_dir(tmp_path)

        # Config should still have custom model
        loaded = Config.load(config_file)
        assert loaded.model == "custom-model"


class TestDiscoverDefaultDoc:
    def test_project_plan_first(self, tmp_path):
        """PROJECT_PLAN.md is preferred over other docs."""
        (tmp_path / "PROJECT_PLAN.md").write_text("# Plan")
        (tmp_path / "README.md").write_text("# Readme")
        config = Config()

        result = _discover_default_doc(tmp_path, config)
        assert result == (tmp_path / "PROJECT_PLAN.md").resolve()

    def test_plan_md_second(self, tmp_path):
        """PLAN.md is used if no PROJECT_PLAN.md."""
        (tmp_path / "PLAN.md").write_text("# Plan")
        (tmp_path / "README.md").write_text("# Readme")
        config = Config()

        result = _discover_default_doc(tmp_path, config)
        assert result == (tmp_path / "PLAN.md").resolve()

    def test_readme_fallback(self, tmp_path):
        """README.md is used if no plan docs exist."""
        (tmp_path / "README.md").write_text("# Readme")
        config = Config()

        result = _discover_default_doc(tmp_path, config)
        assert result == (tmp_path / "README.md").resolve()

    def test_none_if_no_docs(self, tmp_path):
        """Returns None if no default docs exist."""
        config = Config()

        result = _discover_default_doc(tmp_path, config)
        assert result is None

    def test_config_default_doc_overrides(self, tmp_path):
        """config.default_doc overrides discovery order."""
        (tmp_path / "PROJECT_PLAN.md").write_text("# Plan")
        (tmp_path / "CUSTOM.md").write_text("# Custom")
        config = Config(default_doc="CUSTOM.md")

        result = _discover_default_doc(tmp_path, config)
        assert result == (tmp_path / "CUSTOM.md").resolve()

    def test_config_default_doc_missing_falls_through(self, tmp_path):
        """If config.default_doc doesn't exist, fall through to discovery."""
        (tmp_path / "README.md").write_text("# Readme")
        config = Config(default_doc="NONEXISTENT.md")

        result = _discover_default_doc(tmp_path, config)
        assert result == (tmp_path / "README.md").resolve()

    def test_explicit_target_overrides_discovery(self, tmp_path):
        """Explicit file target should not trigger discovery (tested via CLI flow)."""
        # This tests the constant, not the full CLI flow
        assert "PROJECT_PLAN.md" in DEFAULT_DOCS
        assert "PLAN.md" in DEFAULT_DOCS
        assert "README.md" in DEFAULT_DOCS


class TestDefaultDocs:
    def test_discovery_order(self):
        """DEFAULT_DOCS has the correct priority order."""
        assert DEFAULT_DOCS == ["PROJECT_PLAN.md", "PLAN.md", "README.md"]

    def test_gitignore_template(self):
        """REEREE_GITIGNORE has the right entries."""
        assert "session.json" in REEREE_GITIGNORE
        assert "session.log" in REEREE_GITIGNORE
        assert "local/" in REEREE_GITIGNORE
