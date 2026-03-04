# ADR-009: Plugin Architecture

**Status:** Proposed
**Date:** 2026-03-04

## Context

reeree's daemon types (EXECUTOR, STEP, COHERENCE, WATCHER, STATE) are proto-plugin types — each has a specific trigger, reads specific context, and writes specific outputs. The model router is plugin-shaped (classifies tasks, routes to handlers). The TUI command registry is extensible via dict.

Users will want to add capabilities without modifying core code: multi-agent orchestration patterns (from Gastown analysis), domain-specific coherence checkers, branch-per-daemon isolation, heartbeat monitoring. These should be opt-in — users who want simplicity get simplicity, users who want complexity can install plugins.

## Decision

Plugin system using Python entry points (`importlib.metadata`) and an abstract base class.

### Plugin Base Class

```python
from abc import ABC, abstractmethod

class ReereePlugin(ABC):
    """Base class for reeree plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier."""

    def on_plan_loaded(self, plan) -> None:
        """Called after a plan is loaded or created. Modify/annotate plan."""

    def on_step_dispatched(self, step, daemon) -> None:
        """Called before a daemon starts executing a step."""

    def on_step_completed(self, step, result) -> None:
        """Called after a daemon finishes a step."""

    def on_daemon_message(self, message) -> None:
        """Called when a daemon sends a message via the message bus."""

    def register_commands(self) -> dict[str, callable]:
        """Return dict of :command_name → handler for TUI commands."""
        return {}

    def register_daemon_kinds(self) -> list:
        """Return list of new DaemonKind values this plugin provides."""
        return []
```

### Plugin Discovery

Plugins register via `pyproject.toml` entry points:

```toml
[project.entry-points."reeree.plugins"]
gastown = "reeree_gastown:GastownPlugin"
coherence = "reeree_coherence:CoherencePlugin"
```

Discovery at startup:

```python
from importlib.metadata import entry_points

def discover_plugins() -> list[ReereePlugin]:
    eps = entry_points(group="reeree.plugins")
    return [ep.load()() for ep in eps]
```

### Plugin Configuration

- Global: `~/.config/reeree/plugins.json` — enable/disable, per-plugin settings
- Per-project: `.reeree/plugins.json` — project-level overrides

### Lifecycle Hooks

| Hook | When | Example Use |
|------|------|-------------|
| `on_plan_loaded` | After plan parse | Add quality gates, inject coherence steps |
| `on_step_dispatched` | Before daemon starts | Create branch, set up sandbox |
| `on_step_completed` | After daemon finishes | Run linter, merge branch, update metrics |
| `on_daemon_message` | On message bus event | React to conflicts, coordinate daemons |
| `register_commands` | At startup | Add `:gastown`, `:branch`, `:heartbeat` commands |
| `register_daemon_kinds` | At startup | Add MAYOR, POLECAT, REFINERY daemon types |

## Values Served

- **[Sufficiency Over Maximalism](../../VALUES.md#6-sufficiency-over-maximalism)** — Core stays simple (~3-5K lines). Complexity is opt-in via plugins.
- **[Delegated Agency](../../VALUES.md#1-delegated-agency)** — User chooses which capabilities to enable. Plugins extend delegation scope, not override it.
- **No Lock-in** (Red Line) — Plugins use standard Python packaging. No proprietary plugin format.

## Example Plugins (Future)

| Plugin | What it does | Gastown Equivalent |
|--------|-------------|-------------------|
| `reeree-gastown` | Multi-agent orchestration patterns | Mayor/Polecat coordination |
| `reeree-coherence` | Domain-specific coherence rules | — |
| `reeree-branch` | Branch-per-daemon isolation + merge | Refinery |
| `reeree-heartbeat` | Stall detection and recovery | Witness |

## Alternatives Considered

| Option | Verdict | Why |
|--------|---------|-----|
| Built-in everything | Rejected | Violates sufficiency — most users don't need multi-agent orchestration |
| Separate processes (Unix pipes) | Rejected | Too complex for daemon lifecycle hooks |
| Config-driven (YAML rules) | Rejected | Not expressive enough for real extensibility |

## Consequences

- Plugin API is a public contract — changes require semver discipline
- Plugins can break core if hooks are poorly designed — need clear boundaries
- Discovery adds startup time (minimal with importlib.metadata)
- Core must remain functional with zero plugins installed

## Implementation

- Plugin base: `reeree/plugin.py` — ABC + discovery + registry
- Hook dispatch: integrated into daemon_executor.py and tui/app.py
- Tests: `tests/test_plugin.py` — discovery, hook invocation, command registration

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
