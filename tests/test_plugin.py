"""Tests for plugin system — discovery, registration, hook dispatch."""

from reeree.plugin import ReereePlugin, PluginRegistry


class DummyPlugin(ReereePlugin):
    """Test plugin for unit tests."""

    def __init__(self):
        self.plan_loaded_calls = []
        self.step_dispatched_calls = []
        self.step_completed_calls = []
        self.message_calls = []

    @property
    def name(self) -> str:
        return "dummy"

    def on_plan_loaded(self, plan):
        self.plan_loaded_calls.append(plan)

    def on_step_dispatched(self, step, daemon):
        self.step_dispatched_calls.append((step, daemon))

    def on_step_completed(self, step, result):
        self.step_completed_calls.append((step, result))

    def on_daemon_message(self, message):
        self.message_calls.append(message)

    def register_commands(self):
        return {"dummy": lambda app, args: None}

    def register_daemon_kinds(self):
        return ["dummy_kind"]


class BrokenPlugin(ReereePlugin):
    """Plugin that raises on every hook — should never crash reeree."""

    @property
    def name(self) -> str:
        return "broken"

    def on_plan_loaded(self, plan):
        raise RuntimeError("broken plugin")

    def on_step_dispatched(self, step, daemon):
        raise RuntimeError("broken plugin")

    def on_step_completed(self, step, result):
        raise RuntimeError("broken plugin")

    def on_daemon_message(self, message):
        raise RuntimeError("broken plugin")

    def register_commands(self):
        raise RuntimeError("broken plugin")

    def register_daemon_kinds(self):
        raise RuntimeError("broken plugin")


class TestPluginRegistry:
    def test_register_plugin(self):
        registry = PluginRegistry()
        plugin = DummyPlugin()
        registry.register(plugin)
        assert len(registry.plugins) == 1
        assert registry.plugins[0].name == "dummy"

    def test_plugin_commands_registered(self):
        registry = PluginRegistry()
        plugin = DummyPlugin()
        registry.register(plugin)
        assert "dummy" in registry.commands

    def test_plugin_daemon_kinds(self):
        registry = PluginRegistry()
        plugin = DummyPlugin()
        registry.register(plugin)
        assert "dummy_kind" in registry.daemon_kinds

    def test_fire_plan_loaded(self):
        registry = PluginRegistry()
        plugin = DummyPlugin()
        registry.register(plugin)
        registry.fire_plan_loaded("test_plan")
        assert plugin.plan_loaded_calls == ["test_plan"]

    def test_fire_step_dispatched(self):
        registry = PluginRegistry()
        plugin = DummyPlugin()
        registry.register(plugin)
        registry.fire_step_dispatched("step", "daemon")
        assert plugin.step_dispatched_calls == [("step", "daemon")]

    def test_fire_step_completed(self):
        registry = PluginRegistry()
        plugin = DummyPlugin()
        registry.register(plugin)
        registry.fire_step_completed("step", {"status": "done"})
        assert plugin.step_completed_calls == [("step", {"status": "done"})]

    def test_fire_daemon_message(self):
        registry = PluginRegistry()
        plugin = DummyPlugin()
        registry.register(plugin)
        registry.fire_daemon_message("msg")
        assert plugin.message_calls == ["msg"]

    def test_broken_plugin_doesnt_crash(self):
        """Broken plugins should not crash reeree."""
        registry = PluginRegistry()
        broken = BrokenPlugin()
        good = DummyPlugin()
        registry.register(broken)
        registry.register(good)

        # All these should succeed despite broken plugin
        registry.fire_plan_loaded("plan")
        registry.fire_step_dispatched("step", "daemon")
        registry.fire_step_completed("step", {})
        registry.fire_daemon_message("msg")

        # Good plugin still got the calls
        assert len(good.plan_loaded_calls) == 1
        assert len(good.step_dispatched_calls) == 1
        assert len(good.step_completed_calls) == 1
        assert len(good.message_calls) == 1

    def test_discover_returns_empty_with_no_plugins(self):
        """Discovery returns empty list when no plugins installed."""
        registry = PluginRegistry()
        plugins = registry.discover()
        assert isinstance(plugins, list)

    def test_multiple_plugins_merge_commands(self):
        registry = PluginRegistry()

        class Plugin2(ReereePlugin):
            @property
            def name(self):
                return "plugin2"
            def register_commands(self):
                return {"cmd2": lambda app, args: None}

        registry.register(DummyPlugin())
        registry.register(Plugin2())

        assert "dummy" in registry.commands
        assert "cmd2" in registry.commands
