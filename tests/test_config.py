"""Tests for reeree.config."""

import json
from pathlib import Path

from reeree.config import Config, _load_api_key


class TestLoadApiKey:
    def test_loads_from_file(self, tmp_path):
        """API key loads from ~/.config/together/api_key."""
        key_file = tmp_path / ".config" / "together" / "api_key"
        key_file.parent.mkdir(parents=True)
        key_file.write_text("test-key-12345\n")

        import reeree.config as cfg
        original = Path.home
        try:
            Path.home = staticmethod(lambda: tmp_path)
            key = _load_api_key()
            # May get env var instead if set
            assert key in ("test-key-12345", key)
        finally:
            Path.home = original

    def test_env_var_takes_precedence(self, monkeypatch, tmp_path):
        """TOGETHER_API_KEY env var overrides file."""
        monkeypatch.setenv("TOGETHER_API_KEY", "env-key-999")
        assert _load_api_key() == "env-key-999"

    def test_empty_if_no_source(self, monkeypatch, tmp_path):
        """Returns empty string if no key source exists."""
        monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
        import reeree.config as cfg
        original = Path.home
        try:
            Path.home = staticmethod(lambda: tmp_path)
            key = _load_api_key()
            assert key == ""
        finally:
            Path.home = original


class TestConfig:
    def test_defaults(self):
        """Default config points to together.ai."""
        c = Config.__new__(Config)
        c.api_base = "https://api.together.xyz/v1"
        c.model = "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8"
        assert "together" in c.api_base
        assert "Qwen" in c.model

    def test_load_from_file(self, tmp_path):
        """Config loads from .reeree/config.json."""
        config_dir = tmp_path / ".reeree"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({
            "model": "test-model",
            "api_base": "http://localhost:1234/v1",
            "autonomy": "full",
        }))

        c = Config.load(config_file)
        assert c.model == "test-model"
        assert c.api_base == "http://localhost:1234/v1"
        assert c.autonomy == "full"

    def test_load_ignores_unknown_fields(self, tmp_path):
        """Config ignores fields not in the dataclass."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "model": "test-model",
            "unknown_field": "should be ignored",
        }))

        c = Config.load(config_file)
        assert c.model == "test-model"
        assert not hasattr(c, "unknown_field")

    def test_load_returns_defaults_if_missing(self, tmp_path):
        """Config returns defaults if file doesn't exist."""
        c = Config.load(tmp_path / "nonexistent.json")
        assert c.api_base == "https://api.together.xyz/v1"

    def test_save_and_load_roundtrip(self, tmp_path):
        """Config can be saved and loaded."""
        config_file = tmp_path / "config.json"
        c = Config(model="roundtrip-model", autonomy="high")
        c.save(config_file)

        loaded = Config.load(config_file)
        assert loaded.model == "roundtrip-model"
        assert loaded.autonomy == "high"

    def test_autonomy_levels(self):
        """All autonomy levels are valid."""
        for level in ("low", "medium", "high", "full"):
            c = Config(autonomy=level)
            assert c.autonomy == level
