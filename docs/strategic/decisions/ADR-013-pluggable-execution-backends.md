# ADR-013: Pluggable Execution Backends

**Status:** Proposed
**Date:** 2026-03-05

## Context

Reeree's current executor daemon reimplements coding tool capabilities: file reading, editing, shell commands, git operations, LLM conversation loops. But Claude Code, aider, Codex CLI, and other tools already do this well. Reimplementing them is wasted effort and always inferior to the original.

Key insight: reeree is an **orchestration layer**, not an execution engine. Its value is the plan-as-interface, daemon parallelism, scope management, and personality evolution — not the mechanics of reading a file and editing it. Those mechanics can be delegated to existing tools.

Claude Code is a CLI tool. Aider is a CLI tool. Codex is a CLI tool. Any of them can run as a subprocess inside a reeree daemon.

## Decision

Reeree's daemon executor supports **pluggable execution backends**. Each backend is a CLI tool that the daemon shells out to for the actual coding work. Reeree handles orchestration; the backend handles execution.

### Architecture

```
User ← Plan (YAML) → Reeree Orchestrator
                          │
                          ├── Daemon 1 (backend: claude-code)
                          │     └── claude --dangerously-skip-permissions ...
                          │
                          ├── Daemon 2 (backend: aider)
                          │     └── aider --message "..." --yes
                          │
                          ├── Daemon 3 (backend: native)
                          │     └── built-in executor (current implementation)
                          │
                          └── Daemon 4 (backend: codex)
                                └── codex --quiet "..."
```

### Backend Interface

Each backend implements a simple contract:

```python
class ExecutionBackend(ABC):
    name: str                    # "claude-code", "aider", "native"
    binary: str                  # path to CLI tool

    def execute_step(self, step: Step, context: str, project_dir: Path) -> StepResult:
        """Run a plan step using this backend."""
        # Shells out to the CLI tool with appropriate flags
        # Parses output for results (files changed, errors, summary)

    def chat(self, message: str, context: str) -> str:
        """Send a chat message through this backend."""

    def is_available(self) -> bool:
        """Check if the CLI tool is installed and configured."""
```

### Backend: Claude Code

```yaml
# .reeree/backends/claude-code.yaml
name: claude-code
binary: claude
flags:
  - --dangerously-skip-permissions  # reeree manages permissions
  - --output-format json            # structured output for parsing
model: claude-sonnet-4-5  # or whatever the user's plan allows
cost_tier: premium  # $20/mo subscription or API costs
```

Advantages:
- Best coding quality available
- Full tool use (Read, Edit, Write, Bash, WebSearch, WebFetch)
- Agent mode for complex multi-step work
- Already installed in this environment

Disadvantages:
- Expensive (subscription or API)
- Anthropic-only (vendor lock-in for this backend)

### Backend: Aider

```yaml
name: aider
binary: aider
flags:
  - --yes           # auto-confirm
  - --no-suggest-shell-commands
model: configurable  # works with any OpenAI-compatible API
cost_tier: variable  # depends on model chosen
```

Advantages:
- Model-agnostic (works with Together, Ollama, OpenAI, Anthropic)
- Good git integration (auto-commits)
- Already in the venv

### Backend: Native (Current)

```yaml
name: native
binary: null  # built-in
model: configurable
cost_tier: variable
```

The current daemon_executor.py implementation. Direct LLM calls via OpenAI-compatible API, YAML action protocol.

Advantages:
- Full control over prompts, protocol, personality
- No external dependencies
- Cheapest (direct API calls, no overhead)

Disadvantages:
- Less capable than Claude Code for complex tasks
- Must reimplement every capability

### Backend Selection

Configurable per daemon kind, per step, or globally:

```yaml
# .reeree/config.json
backends:
  default: native
  executor: native
  coherence: native
  complex_step: claude-code  # for steps annotated > backend: claude-code
```

Or per-step in the plan:

```yaml
steps:
  - description: Refactor auth module
    backend: claude-code  # this step is complex, use the big guns
  - description: Update version number
    backend: native  # trivial, use direct API
```

### The Meta Possibility

Reeree could run Claude Code as a daemon, with Claude Code's own agent spawning sub-agents. This is turtles all the way down — reeree orchestrates Claude Code which orchestrates its own sub-agents. The plan file is the coordination layer that keeps it coherent.

## Values Served

- **[Delegated Agency](../../VALUES.md#1-delegated-agency)** — the user chooses which backend executes each step. Full control over delegation scope.
- **[Sufficiency Over Maximalism](../../VALUES.md#6-sufficiency-over-maximalism)** — native backend works with free/cheap models. Claude Code backend available when quality matters. User chooses the cost/quality tradeoff.
- **[No Lock-in](../../VALUES.md#red-lines)** — multiple backends prevent vendor lock-in. If Claude Code disappears tomorrow, aider or native still work.

## Alternatives Considered

| Option | Verdict | Why |
|--------|---------|-----|
| Reimplement everything natively | Rejected | Wasted effort. Claude Code already has 100+ person-years of engineering. |
| Use only Claude Code | Rejected | Vendor lock-in. Expensive. Violates sufficiency principle. |
| Use only native executor | Current state | Works but limited. Can't match Claude Code's capabilities. |
| Hybrid (proposed) | Accepted | Best of all worlds. User controls the tradeoff. |

## Consequences

- Need a `BackendRegistry` similar to `DaemonRegistry`
- Each backend needs output parsing (different tools report results differently)
- Claude Code backend requires the user's Claude subscription or API key
- Backend selection adds a config dimension but defaults keep it simple
- Testing must cover each backend independently

## Implementation Path

1. Define `ExecutionBackend` ABC in `reeree/backend.py`
2. Implement `NativeBackend` wrapping current `daemon_executor.py`
3. Implement `ClaudeCodeBackend` wrapping `claude` CLI
4. Implement `AiderBackend` wrapping `aider` CLI
5. Add backend selection to config and plan step annotations
6. Setup wizard detects available backends and configures defaults

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
