"""Tests for model routing — task classification and model selection."""

from reeree.config import Config
from reeree.daemon_registry import DaemonKind
from reeree.router import classify_task, route_model, ModelChoice


class TestClassifyTask:
    def test_coherence_daemon_is_reasoning(self):
        assert classify_task("check docs", DaemonKind.COHERENCE) == "reasoning"

    def test_state_daemon_is_reasoning(self):
        assert classify_task("assess state", DaemonKind.STATE) == "reasoning"

    def test_watcher_daemon_is_fast(self):
        assert classify_task("watch files", DaemonKind.WATCHER) == "fast"

    def test_reasoning_keywords(self):
        assert classify_task("architect the auth system", DaemonKind.STEP) == "reasoning"
        assert classify_task("refactor the database layer", DaemonKind.STEP) == "reasoning"
        assert classify_task("design the API schema", DaemonKind.STEP) == "reasoning"

    def test_fast_keywords(self):
        assert classify_task("read the config file", DaemonKind.STEP) == "fast"
        assert classify_task("check if tests pass", DaemonKind.STEP) == "fast"
        assert classify_task("list all endpoints", DaemonKind.STEP) == "fast"

    def test_default_is_coding(self):
        assert classify_task("implement user login", DaemonKind.STEP) == "coding"
        assert classify_task("add error handling", DaemonKind.STEP) == "coding"

    def test_executor_daemon_uses_keywords(self):
        assert classify_task("review the architecture", DaemonKind.EXECUTOR) == "reasoning"
        assert classify_task("implement the feature", DaemonKind.EXECUTOR) == "coding"


class TestRouteModel:
    def test_fallback_to_single_model(self):
        config = Config(model="test-model", api_base="http://test", api_key="key123")
        choice = route_model("do something", DaemonKind.STEP, config)
        assert choice.model == "test-model"
        assert choice.api_base == "http://test"
        assert choice.api_key == "key123"
        assert choice.tier == "coding"

    def test_multi_model_routing(self):
        config = Config(
            model="default-model",
            api_base="http://default",
            api_key="default-key",
            models={
                "big": {"model": "big-model", "api_base": "http://big", "api_key": "big-key"},
                "small": {"model": "small-model", "api_base": "http://small", "api_key": "small-key"},
            },
            routing={
                "reasoning": "big",
                "coding": "big",
                "fast": "small",
            },
        )
        # Fast task → small model
        choice = route_model("read the file", DaemonKind.STEP, config)
        assert choice.model == "small-model"
        assert choice.tier == "fast"

        # Reasoning task → big model
        choice = route_model("design the architecture", DaemonKind.STEP, config)
        assert choice.model == "big-model"
        assert choice.tier == "reasoning"

    def test_missing_routing_key_falls_back(self):
        config = Config(
            model="default-model",
            api_base="http://default",
            api_key="key",
            models={"big": {"model": "big-model"}},
            routing={"reasoning": "big"},  # no coding or fast mapping
        )
        choice = route_model("implement feature", DaemonKind.STEP, config)
        # coding tier not in routing → fallback to default
        assert choice.model == "default-model"

    def test_missing_model_key_falls_back(self):
        config = Config(
            model="default-model",
            api_base="http://default",
            api_key="key",
            models={},
            routing={"coding": "nonexistent"},
        )
        choice = route_model("implement feature", DaemonKind.STEP, config)
        assert choice.model == "default-model"

    def test_partial_model_config_inherits_defaults(self):
        """Model config can omit api_base/api_key to inherit from config."""
        config = Config(
            model="default-model",
            api_base="http://default",
            api_key="default-key",
            models={"fast": {"model": "fast-model"}},  # no api_base or api_key
            routing={"fast": "fast"},
        )
        choice = route_model("check status", DaemonKind.STEP, config)
        assert choice.model == "fast-model"
        assert choice.api_base == "http://default"  # inherited
        assert choice.api_key == "default-key"  # inherited


class TestConfigExtensions:
    def test_is_first_run_no_key(self):
        config = Config.__new__(Config)  # skip __post_init__ auto-loading
        config.backend = "together"
        config.api_key = ""
        config.models = {}
        assert config.is_first_run()

    def test_is_first_run_with_key(self):
        config = Config(api_key="some-key")
        assert not config.is_first_run()

    def test_is_first_run_with_models(self):
        config = Config(api_key="", models={"fast": {"model": "x"}})
        assert not config.is_first_run()

    def test_models_and_routing_default_empty(self):
        config = Config()
        assert config.models == {}
        assert config.routing == {}
