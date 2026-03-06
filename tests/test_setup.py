"""Tests for setup wizard — config detection, probe, and generation."""

import json
from pathlib import Path
from reeree.config import Config
from reeree.tui.setup_screen import _probe_provider


class TestFirstRunDetection:
    def test_first_run_no_key_no_models(self):
        config = Config.__new__(Config)
        config.backend = "together"
        config.api_key = ""
        config.models = {}
        assert config.is_first_run()

    def test_not_first_run_with_key(self):
        config = Config(api_key="test-key")
        assert not config.is_first_run()

    def test_not_first_run_with_models(self):
        config = Config.__new__(Config)
        config.backend = "together"
        config.api_key = ""
        config.models = {"fast": {"model": "x"}}
        assert not config.is_first_run()


class TestProbeProvider:
    def test_unreachable_returns_false(self):
        assert not _probe_provider("http://192.0.2.1:9999/v1")  # RFC 5737 test address

    def test_bad_url_returns_false(self):
        assert not _probe_provider("not-a-url")


class TestConfigSaveLoad:
    def test_save_and_load_roundtrip(self, tmp_path):
        config = Config(
            api_key="test-key",
            api_base="http://test",
            model="test-model",
            autonomy="high",
            max_context_tokens=16000,
            models={"fast": {"model": "small-model"}},
            routing={"fast": "fast"},
        )
        path = tmp_path / "config.json"
        config.save(path)

        loaded = Config.load(path)
        assert loaded.api_key == "test-key"
        assert loaded.model == "test-model"
        assert loaded.autonomy == "high"
        assert loaded.max_context_tokens == 16000
        assert loaded.models == {"fast": {"model": "small-model"}}
        assert loaded.routing == {"fast": "fast"}

    def test_save_creates_parent_dirs(self, tmp_path):
        config = Config(api_key="k")
        path = tmp_path / "deep" / "nested" / "config.json"
        config.save(path)
        assert path.exists()
