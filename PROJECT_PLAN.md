# Project Plan

## Current State
Phase 1 complete. Phase 3 complete. Phase 8 infrastructure complete. Session serialization (Phase 2) done. Socket daemon (Phase 2) not started. File viewer, chat-based setup, log tightening, voice spec, YAML plan format all working. Inline machine tasks working — any document is machine-addressable. Three-mode model (VIEW/NORMAL/INSERT) with step IDs for parallel dispatch infrastructure. 396 tests passing.

---

## Phase 1: Core Loop — COMPLETE
**Goal:** One daemon executes. You can dispatch it, watch it, and undo its work.
**Values tested:** [Delegated Agency](VALUES.md#1-delegated-agency), [Plan Is the Interface](VALUES.md#2-plan-is-the-interface), Git-Per-Step

### Deliverables
1. Plan parser/writer — **DONE** (`plan.py`)
2. LLM API interface — **DONE** (`llm.py`)
3. Context builder — **DONE** (`context.py`)
4. Executor (file edit, shell, git commit) — **DONE** (`executor.py`)
5. Planner (intent → steps) — **DONE** (`planner.py`)
6. Multi-turn daemon executor (YAML protocol) — **DONE** (`daemon_executor.py`)
7. Daemon registry (lifecycle, hierarchy) — **DONE** (`daemon_registry.py`)
8. Model router (reasoning/coding/fast tiers) — **DONE** (`router.py`)
9. TUI with vim modal editing — **DONE** (`tui/app.py`)
10. Daemon tree view — **DONE** (`tui/daemon_tree.py`)
11. Setup wizard (chat-based) — **DONE** (`tui/app.py`)
12. CLI entry point — **DONE** (`cli.py`, ls/kill are stubs)
13. Sandbox project — **DONE** (`sandbox/`)

### Remaining
- Ollama localhost testing
- `reeree ls` and `reeree kill` CLI subcommands (stubs exist)

---

## Phase 2: Persistence — 25% Complete
**Goal:** Sessions survive terminal death. Attach/detach like tmux.
**Values tested:** [Persistence Without Fragility](VALUES.md#4-persistence-without-fragility)
**ADR:** [ADR-001](docs/strategic/decisions/ADR-001-unix-domain-socket.md)

### Deliverables
1. Session state serialization — **DONE** (`session.py`, full round-trip)
2. Daemon process — background server with Unix domain socket — NOT STARTED
3. Session management — create, list, attach, detach, kill — NOT STARTED
4. Client protocol — messages over socket (JSON) — NOT STARTED
5. Crash recovery — restart, read state, resume — NOT STARTED

### Success Criteria
- [ ] `reeree` starts daemon if not running, attaches if running
- [ ] Kill terminal → daemon keeps running → `reeree attach` reconnects
- [ ] `reeree ls` shows active sessions
- [ ] Crash → restart → state recovered from disk
- [ ] Socket cleaned up properly on shutdown

---

## Phase 3: TUI Polish — COMPLETE
**Goal:** Multi-pane terminal interface with plan view, daemon status, and command bar.
**Values tested:** [Plan Is the Interface](VALUES.md#2-plan-is-the-interface), [Overlap Not Turn-Taking](VALUES.md#3-overlap-not-turn-taking)

### Deliverables — all done
1. Three-zone layout (plan/daemon/log) — **DONE**
2. Plan pane (live-updating checklist) — **DONE**
3. Daemon pane (tree view with status) — **DONE**
4. Command bar (vim command mode) — **DONE**
5. Exec log pane — **DONE**
6. Chat panel — **DONE**
7. File viewer (`:file`, vim modal, `:w`/`:q`/`:wq`) — **DONE**
8. Tab cycling between panes — **DONE**

### Remaining
- (Step IDs now provide stable references for reordering during execution)

---

## Phase 4: Vim Keybindings — 85% Complete
**Goal:** Full modal interface — normal, insert, command modes.
**Values tested:** [Vim Is the Lingua Franca](VALUES.md#5-vim-is-the-lingua-franca)

### What works
- [x] Normal mode: hjkl navigation, g/G for start/end of line
- [x] Insert mode: i/a/o enter, Escape exits (parses YAML back into plan)
- [x] Command mode: `:` enters, Enter/Escape/Up/Down all work
- [x] Mode indicator in status bar (green/yellow/cyan)
- [x] File viewer: full vim modal (NORMAL/INSERT with hjkl)
- [x] Tab / Ctrl+W pane cycling (plan → exec log → chat → plan)
- [x] Command history (up to 100 entries)
- [x] All keyboard shortcuts documented ([docs/keyboard-shortcuts.md](docs/keyboard-shortcuts.md))
- [x] 74 dedicated workflow + keyboard tests
- [x] Three-mode model (VIEW/NORMAL/INSERT)
- [x] `:edit` command for entering edit mode
- [x] 396 tests passing

### What doesn't
- [ ] Vim motions: d, y, p, visual mode
- [ ] J/K step reordering in normal mode
- [ ] Key mapping configuration

---

## Phase 5: Parallel Daemons — 25%
**Goal:** Multiple daemons running simultaneously on independent steps.
**Values tested:** [Overlap Not Turn-Taking](VALUES.md#3-overlap-not-turn-taking)

### Deliverables
1. Step IDs — stable identifiers for parallel-safe step references — **DONE**
2. StatusOverlay — overlay widget for daemon/step status display — **DONE**
3. Daemon pool — configurable concurrent limit (default: 2)
4. Dependency detection — same-file steps run sequentially
5. File conflict detection
6. Per-daemon controls (`:pause 2`, `:kill 1`, `:log 3`) — **DONE** (registry supports it)
7. Progress summary

---

## Phase 6: Polish and Dogfood — 0%
**Goal:** Use reeree to develop reeree. Fix everything that hurts.

---

## Phase 7: Release — 0%
**Goal:** Open source. `pip install reeree`.

---

## Phase 8: Plugin Ecosystem — Infrastructure COMPLETE
**Goal:** Extensibility via Python entry points. Complexity is opt-in.
**ADRs:** [ADR-009](docs/strategic/decisions/ADR-009-plugin-architecture.md), [ADR-010](docs/strategic/decisions/ADR-010-inter-daemon-communication.md)

### Deliverables
1. Plugin base class + entry point discovery — **DONE** (`plugin.py`)
2. Inter-daemon message bus — **DONE** (`message_bus.py`)
3. Plugin hook dispatch — **DONE** (on_plan_loaded, on_step_dispatched, on_step_completed, on_daemon_message)
4. Plugin command registration — **DONE** (extends `:` commands)
5. Example plugin — NOT STARTED

### Success Criteria
- [x] `from reeree.plugin import ReereePlugin` works
- [x] Plugins discovered via `importlib.metadata.entry_points`
- [x] Message bus delivers messages between daemons
- [x] Core works with zero plugins installed
- [ ] Plugin commands appear in `:help`
- [ ] Example plugin shipped

---

## All TUI Commands

| Command | Status | Description |
|---------|--------|-------------|
| `:w` | DONE | Save plan (exit edit mode if editing) |
| `:go N` | DONE | Dispatch step N |
| `:W` | DONE | Dispatch ALL pending steps |
| `:edit` | DONE | Enter edit mode |
| `:add "desc"` | DONE | Add step |
| `:del N` | DONE | Delete step |
| `:move N M` | DONE | Reorder step |
| `:file path` | DONE | Vim file viewer overlay |
| `:set key val` | DONE | Config (model, autonomy) |
| `:pause N` | DONE | Pause daemon |
| `:resume N` | DONE | Resume daemon |
| `:kill N` | DONE | Kill daemon |
| `:chat [target]` | DONE | Toggle chat panel |
| `:close` | DONE | Close chat |
| `:cohere files` | DONE | Coherence check |
| `:propagate` | DONE | Crawl cross-refs |
| `:setup` | DONE | Chat-based config |
| `:diff [N]` | DONE | Show step diff |
| `:log [N]` | DONE | Show daemon log |
| `:undo` | DONE | Revert last step |
| `:q` / `:q!` / `:wq` | DONE | Quit |
| `:help` | DONE | Help |

---

## MVP Definition

The MVP is **Phase 1 + Phase 2 + Phase 3**: a single daemon executing plan steps through a persistent TUI.

**Status:** Phase 1 and 3 are done. Phase 2 session serialization is done. The missing piece is the Unix socket daemon server for attach/detach persistence.

---

> **Core Planning Documents:** [Values](VALUES.md) → [Implementation](IMPLEMENTATION.md) → **Plan** → [Cost](COST.md) → [Revenue](REVENUE.md) → [Profit](PROFIT.md)
