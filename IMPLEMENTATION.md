# Implementation

## Value-to-Implementation Traceability

| Value | Implementation Decision | Rationale |
|-------|------------------------|-----------|
| [Delegated Agency](VALUES.md#1-delegated-agency) | Daemons execute within dispatched scope, never self-initiate goals | Agency is delegated by the user, bounded by dispatch scope |
| [Delegated Agency](VALUES.md#1-delegated-agency) | Autonomy levels (low/medium/high) control delegation breadth | User sets how much authority the process has per session |
| [Plan Is the Interface](VALUES.md#2-plan-is-the-interface) | Plan stored as markdown file, parsed/written by both user and daemons | Visible, editable with any text editor, diffable in git |
| [Plan Is the Interface](VALUES.md#2-plan-is-the-interface) | Step annotations (`> ` lines) carry specs inline | User writes acceptance criteria directly in the plan |
| [Overlap, Not Turn-Taking](VALUES.md#3-overlap-not-turn-taking) | Async daemon pool with parallel dispatch | Multiple daemons execute simultaneously |
| [Overlap, Not Turn-Taking](VALUES.md#3-overlap-not-turn-taking) | Plan is editable while daemons execute | User is always ahead, editing future steps |
| [Persistence Without Fragility](VALUES.md#4-persistence-without-fragility) | Unix domain socket daemon/client architecture (planned) | Session survives terminal death, like tmux |
| [Persistence Without Fragility](VALUES.md#4-persistence-without-fragility) | Git commit per completed step | Work survives everything — crash, reboot, mistake |
| [Vim Is the Lingua Franca](VALUES.md#5-vim-is-the-lingua-franca) | Modal TUI with normal/insert/command modes | User's muscle memory works |
| [Vim Is the Lingua Franca](VALUES.md#5-vim-is-the-lingua-franca) | `:` command mode for all operations | Vim users already know this paradigm |
| [Sufficiency Over Maximalism](VALUES.md#6-sufficiency-over-maximalism) | Each step gets focused context (~24K tokens) | 32K models work fine, no 200K crutch |
| [Sufficiency Over Maximalism](VALUES.md#6-sufficiency-over-maximalism) | Default API: localhost ollama | Free local inference is the default, not the fallback |
| [Sufficiency Over Maximalism](VALUES.md#6-sufficiency-over-maximalism) | Model routing: cheapest adequate model per task tier | $0.003 on a hard step, $0 on an easy one |

## Architecture Decisions

All ADRs are standalone files in [`docs/strategic/decisions/`](docs/strategic/decisions/).

### Core Architecture

| ADR | Decision | Status | Values |
|-----|----------|--------|--------|
| [ADR-001](docs/strategic/decisions/ADR-001-unix-domain-socket.md) | Unix domain socket daemon/client | Accepted | Persistence |
| [ADR-002](docs/strategic/decisions/ADR-002-textual-tui.md) | Textual for TUI framework | Accepted | Vim, Overlap |
| [ADR-003](docs/strategic/decisions/ADR-003-plan-as-markdown.md) | Plan as markdown work queue | Accepted | Plan Is Interface |
| [ADR-005](docs/strategic/decisions/ADR-005-git-per-step-undo.md) | Git-per-step undo system | Accepted | Persistence |

### Model & Context

| ADR | Decision | Status | Values |
|-----|----------|--------|--------|
| [ADR-004](docs/strategic/decisions/ADR-004-openai-compatible-api.md) | OpenAI-compatible API interface | Accepted | Sufficiency, No Lock-in |
| [ADR-006](docs/strategic/decisions/ADR-006-focused-context.md) | Focused context per step | Accepted | Sufficiency |
| [ADR-007](docs/strategic/decisions/ADR-007-orchestrator-llm.md) | Orchestrator LLM / model routing | Implemented | Sufficiency, Agency |

### Coordination & Extensibility

| ADR | Decision | Status | Values |
|-----|----------|--------|--------|
| [ADR-008](docs/strategic/decisions/ADR-008-propagate-cohere.md) | Propagate and cohere commands | Implemented | Plan Is Interface |
| [ADR-009](docs/strategic/decisions/ADR-009-plugin-architecture.md) | Plugin architecture | Proposed | Sufficiency, Agency |
| [ADR-010](docs/strategic/decisions/ADR-010-inter-daemon-communication.md) | Inter-daemon communication | Proposed | Overlap, Plan Is Interface |
| [ADR-011](docs/strategic/decisions/ADR-011-subrepo-scope-as-lexical-binding.md) | Subrepo scope as lexical binding | Accepted | Focused Context, Plan Is Interface |
| [ADR-012](docs/strategic/decisions/ADR-012-daemon-personality-evolution.md) | Daemon personality evolution | Proposed | Delegated Agency, No Anthropomorphism |
| [ADR-013](docs/strategic/decisions/ADR-013-pluggable-execution-backends.md) | Pluggable execution backends | Proposed | Sufficiency, No Lock-in |
| [ADR-014](docs/strategic/decisions/ADR-014-simplified-technical-english.md) | Clear Technical English voice spec | Proposed | No Anthropomorphism, Sufficiency |

## Current State (as of 2026-03-06)

### What's Built

| Component | Module | Status |
|-----------|--------|--------|
| Plan parser/writer | `plan.py` | Complete — YAML canonical format + markdown display round-trip |
| LLM API interface | `llm.py` | Complete — OpenAI-compatible, model overrides |
| Context builder | `context.py` | Complete — focused per-step, scope inheritance |
| Executor (file/shell/git) | `executor.py` | Complete — safety classification, autonomy levels |
| Planner (intent → steps) | `planner.py` | Complete — LLM-powered decomposition |
| Multi-turn daemon executor | `daemon_executor.py` | Complete — read→edit→verify loop, YAML protocol |
| Daemon registry | `daemon_registry.py` | Complete — lifecycle, hierarchy, pause/resume/kill |
| Model router | `router.py` | Complete — reasoning/coding/fast tier classification |
| TUI main app | `tui/app.py` | Complete — vim modal, all commands, split panes |
| Daemon tree view | `tui/daemon_tree.py` | Complete — hierarchical display with status |
| Setup wizard | `tui/setup_screen.py` | Complete — first-run "character creation" |
| CLI entry point | `cli.py` | Complete — start, resume, ls, kill, setup |
| Configuration | `config.py` | Complete — single + multi-model, load/save |
| Plugin system | `plugin.py` | New — base class, discovery, hook dispatch |
| Message bus | `message_bus.py` | New — inter-daemon communication |
| Session serialization | `session.py` | New — Plan + Registry → JSON → disk |

### What's Not Built Yet

| Component | ADR | Phase |
|-----------|-----|-------|
| Daemon persistence (socket server) | ADR-001 | Phase 2 |
| Attach/detach (tmux-style) | ADR-001 | Phase 2 |
| Crash recovery | ADR-001 | Phase 2 |
| Parallel daemon dispatch | — | Phase 5 |
| File conflict detection | — | Phase 5 |
| Vim motions (d, y, p, visual mode) | — | Phase 4 |
| Plugin ecosystem | ADR-009 | Phase 8 |

### Recent Changes

- **Daemon registry refactor** (3b26d3e) — replaced ad-hoc `_daemons` dict with `DaemonRegistry` class. `app.py` now uses `self._daemon_registry`.
- **Model routing** (977d246) — tier-based classification routes steps to reasoning/coding/fast models
- **Daemon tree view** (417c6ce) — hierarchical display replaces flat progress indicators
- **Setup wizard** (0ab83bc) — first-run "character creation" for configuration
- **Pause/resume/kill** (b38bbc6) — gap closure on daemon lifecycle commands
- **Commit bug fix** (62a6fe7) — failed git commit incorrectly returned `status: done`
- **Gastown comparison** (1546068) — philosophy, architecture, strategic takeaways
- **YAML plan format** — canonical plan storage switched from markdown to YAML
- **Voice specification** — STE-derived clear prose rules in `voice.py`, wired into all daemon system prompts
- **Workflow tests** — 74 comprehensive workflow/keyboard tests in `test_workflows.py`
- **Keyboard shortcut docs** — complete reference at `docs/keyboard-shortcuts.md`

## Technology Stack

| Component | Choice | Value Trace |
|-----------|--------|-------------|
| Language | Python 3.11+ | Fast iteration, good subprocess/async support |
| TUI | Textual | [ADR-002](docs/strategic/decisions/ADR-002-textual-tui.md) |
| LLM API | httpx → OpenAI-compatible endpoint | [ADR-004](docs/strategic/decisions/ADR-004-openai-compatible-api.md) |
| CLI entry | Click | Simple, well-documented |
| Git ops | GitPython + subprocess | [ADR-005](docs/strategic/decisions/ADR-005-git-per-step-undo.md) |
| IPC | Unix domain socket (asyncio) | [ADR-001](docs/strategic/decisions/ADR-001-unix-domain-socket.md) |
| Plan format | Markdown | [ADR-003](docs/strategic/decisions/ADR-003-plan-as-markdown.md) |
| Config | JSON | Simple, no dependencies |
| Daemon protocol | YAML | Lingua franca — human-readable, machine-parseable |

## Data Architecture

All state lives on disk as plain text:

```
~/.reeree/                    # Global config + session management
├── config.json               # Default model, API, preferences
├── sock                      # Unix domain socket (runtime only)
└── sessions/
    └── <session-id>/
        ├── state.json        # Session state (daemons, status)
        └── plan.yaml         # The plan file (YAML format)

<project>/.reeree/            # Per-project state
├── config.json               # Project-specific overrides
├── plugins.json              # Plugin enable/disable + settings
├── session.json              # Session state for persistence/recovery
└── plan.yaml                 # Current plan (YAML canonical format)
```

---

> **Core Planning Documents:** [Values](VALUES.md) → **Implementation** → [Plan](PROJECT_PLAN.md) → [Cost](COST.md) → [Revenue](REVENUE.md) → [Profit](PROFIT.md)
