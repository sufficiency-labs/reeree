"""Plugin system — opt-in extensibility via Python entry points.

Plugins extend reeree's capabilities without modifying core code.
Discovery uses importlib.metadata entry points (standard Python packaging).
Each plugin is an ABC subclass with lifecycle hooks.

See ADR-009: docs/strategic/decisions/ADR-009-plugin-architecture.md
"""

from abc import ABC, abstractmethod
from typing import Any, Callable


class ReereePlugin(ABC):
    """Base class for reeree plugins.

    Subclass this and register via pyproject.toml entry points:

        [project.entry-points."reeree.plugins"]
        my_plugin = "my_package:MyPlugin"

    All hook methods are optional (default implementations are no-ops).
    Only `name` is required.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier (e.g., 'gastown', 'branch', 'heartbeat')."""

    def on_plan_loaded(self, plan: Any) -> None:
        """Called after a plan is loaded or created.

        Modify or annotate the plan. Called before any daemons are dispatched.
        The plan object is a reeree.plan.Plan instance.
        """

    def on_step_dispatched(self, step: Any, daemon: Any) -> None:
        """Called before a daemon starts executing a step.

        step is a reeree.plan.Step, daemon is a reeree.daemon_registry.Daemon.
        Use for: creating branches, setting up sandboxes, logging.
        """

    def on_step_completed(self, step: Any, result: dict) -> None:
        """Called after a daemon finishes a step.

        result is the dict returned by dispatch_step() with keys:
        status, commit_hash, summary, next_step_notes.
        Use for: merging branches, running linters, updating metrics.
        """

    def on_daemon_message(self, message: Any) -> None:
        """Called when a message is sent on the message bus.

        message is a reeree.message_bus.DaemonMessage.
        Use for: reacting to conflicts, coordinating daemons.
        """

    def register_commands(self) -> dict[str, Callable]:
        """Return dict of command_name → handler for TUI : commands.

        Keys are command names without the colon (e.g., 'branch', 'heartbeat').
        Values are callables that receive (app, args_str) and return None.

        Example:
            def register_commands(self):
                return {"branch": self._handle_branch}
        """
        return {}

    def register_daemon_kinds(self) -> list[str]:
        """Return list of new daemon kind values this plugin provides.

        These extend the DaemonKind enum conceptually (stored as strings).
        Example: ["mayor", "polecat", "refinery"]
        """
        return []


class PluginRegistry:
    """Discovers and manages plugins."""

    def __init__(self):
        self._plugins: list[ReereePlugin] = []
        self._commands: dict[str, Callable] = {}

    def discover(self) -> list[ReereePlugin]:
        """Discover plugins via importlib.metadata entry points.

        Returns list of instantiated plugin objects.
        """
        try:
            from importlib.metadata import entry_points
            eps = entry_points(group="reeree.plugins")
        except Exception:
            return []

        plugins = []
        for ep in eps:
            try:
                plugin_cls = ep.load()
                plugin = plugin_cls()
                if isinstance(plugin, ReereePlugin):
                    plugins.append(plugin)
            except Exception:
                # Don't let a broken plugin crash reeree
                pass

        self._plugins = plugins
        self._rebuild_commands()
        return plugins

    def register(self, plugin: ReereePlugin) -> None:
        """Manually register a plugin (for testing or built-in plugins)."""
        self._plugins.append(plugin)
        self._rebuild_commands()

    def _rebuild_commands(self) -> None:
        """Rebuild the merged command registry from all plugins."""
        self._commands = {}
        for plugin in self._plugins:
            try:
                cmds = plugin.register_commands()
                self._commands.update(cmds)
            except Exception:
                pass

    @property
    def plugins(self) -> list[ReereePlugin]:
        return list(self._plugins)

    @property
    def commands(self) -> dict[str, Callable]:
        """All registered plugin commands."""
        return dict(self._commands)

    @property
    def daemon_kinds(self) -> list[str]:
        """All registered plugin daemon kinds."""
        kinds = []
        for plugin in self._plugins:
            try:
                kinds.extend(plugin.register_daemon_kinds())
            except Exception:
                pass
        return kinds

    # --- Hook dispatch ---

    def fire_plan_loaded(self, plan: Any) -> None:
        """Call on_plan_loaded on all plugins."""
        for plugin in self._plugins:
            try:
                plugin.on_plan_loaded(plan)
            except Exception:
                pass

    def fire_step_dispatched(self, step: Any, daemon: Any) -> None:
        """Call on_step_dispatched on all plugins."""
        for plugin in self._plugins:
            try:
                plugin.on_step_dispatched(step, daemon)
            except Exception:
                pass

    def fire_step_completed(self, step: Any, result: dict) -> None:
        """Call on_step_completed on all plugins."""
        for plugin in self._plugins:
            try:
                plugin.on_step_completed(step, result)
            except Exception:
                pass

    def fire_daemon_message(self, message: Any) -> None:
        """Call on_daemon_message on all plugins."""
        for plugin in self._plugins:
            try:
                plugin.on_daemon_message(message)
            except Exception:
                pass
