# Project Plan

## Current State
Phases 1 and 3 complete. Two-mode vim (NORMAL/INSERT), Claude Code subprocess backend, queued task discovery, cross-reference following, machine tasks all working. 447 tests passing, 19 xfailed.

---

## Priority Order

1. **Parallel daemon safety** — file conflict detection, dependency analysis
2. **Dogfooding** — use reeree to develop reeree, collect real issues
3. **Plugin examples** — ship a real plugin (coherence, task-engine)
4. **Release** — pip install reeree
5. **Persistence** — socket daemon for tmux-like attach/detach (tmux works for now)

---

## Phase 5: Parallel Daemons — PRIORITY 1 (25%)
**Goal:** Multiple daemons running safely on independent steps.
**Values tested:** [Overlap Not Turn-Taking](VALUES.md#3-overlap-not-turn-taking)

### Done
1. Step IDs — stable identifiers for parallel-safe step references — **DONE**
2. StatusOverlay — daemon/step status display — **DONE**
3. DaemonRegistry — pause/resume/kill lifecycle — **DONE**
4. Per-daemon controls (`:pause N`, `:kill N`, `:log N`) — **DONE**

### Not done
5. File conflict detection — two daemons editing same file → block one
6. Dependency detection — same-file steps run sequentially
7. Daemon pool — configurable concurrent limit (default: 2)
8. Progress summary per daemon in exec log

### Estimated: 2-3 sessions

---

## Phase 6: Dogfooding — PRIORITY 2 (0%)
**Goal:** Use reeree to develop reeree. Fix everything that hurts.

Use the tool daily for real work. Collect issues from session logs.
The inter-daemon communication model (message bus) will emerge from this.

### Estimated: ongoing

---

## Phase 8: Plugin Ecosystem — PRIORITY 3 (Infrastructure COMPLETE)
**Goal:** Extensibility via Python entry points. Complexity is opt-in.
**ADRs:** [ADR-009](docs/strategic/decisions/ADR-009-plugin-architecture.md), [ADR-010](docs/strategic/decisions/ADR-010-inter-daemon-communication.md)

### Done
1. Plugin base class + entry point discovery — **DONE** (`plugin.py`)
2. Inter-daemon message bus — **DONE** (`message_bus.py`)
3. Plugin hook dispatch — **DONE** (on_plan_loaded, on_step_dispatched, on_step_completed, on_daemon_message)
4. Plugin command registration — **DONE**

### Not done
5. Example plugin (e.g. reeree-coherence)
6. Plugin documentation
7. Plugin config (enable/disable, settings)

### Estimated: 2 sessions

---

## Phase 7: Release — PRIORITY 4 (0%)
**Goal:** Open source. `pip install reeree`.

### Estimated: 1-2 sessions

---

## Phase 2: Persistence — PRIORITY 5 (25%)
**Goal:** Sessions survive terminal death. Attach/detach like tmux.
**Values tested:** [Persistence Without Fragility](VALUES.md#4-persistence-without-fragility)
**ADR:** [ADR-001](docs/strategic/decisions/ADR-001-unix-domain-socket.md)

**De-prioritized:** tmux works for now. Eventually port to a tmux wrapper with multiple reeree terminals.

### Done
1. Session state serialization — **DONE** (`session.py`, full round-trip)

### Not done
2. Unix domain socket server — background daemon process
3. Session management — create, list, attach, detach, kill
4. Client protocol — messages over socket
5. Crash recovery — restart, read state, resume

### Estimated: 2-3 sessions

---

## Phase 1: Core Loop — COMPLETE
**Goal:** One daemon executes. You can dispatch it, watch it, and undo its work.
**Values tested:** [Delegated Agency](VALUES.md#1-delegated-agency), [Plan Is the Interface](VALUES.md#2-plan-is-the-interface), Git-Per-Step

All 13 deliverables done. See `plan.py`, `llm.py`, `context.py`, `executor.py`, `planner.py`, `daemon_executor.py`, `daemon_registry.py`, `router.py`, `cli.py`, `tui/app.py`, `tui/daemon_tree.py`.

---

## Phase 3: TUI Polish — COMPLETE
**Goal:** Multi-pane terminal interface with plan view, daemon status, and command bar.
**Values tested:** [Plan Is the Interface](VALUES.md#2-plan-is-the-interface), [Overlap Not Turn-Taking](VALUES.md#3-overlap-not-turn-taking)

All 8 deliverables done. Three-zone layout, live-updating plan, daemon tree, command bar, exec log, chat panel, file viewer, tab cycling.

---

## Phase 4: Vim Keybindings — 90%
**Goal:** Full modal interface — NORMAL, INSERT, COMMAND modes.
**Values tested:** [Vim Is the Lingua Franca](VALUES.md#5-vim-is-the-lingua-franca)

Two-mode system (NORMAL/INSERT, no VIEW/:edit gate). hjkl, i/a/o, dd/yy/p/P, D/C/cc, J, x, w/b, g/G, u/Ctrl-r. 74 keyboard tests.

### Not done
- [ ] Visual mode
- [ ] Key mapping configuration

---

## All TUI Commands

| Command | Status | Description |
|---------|--------|-------------|
| `:w` | DONE | Save plan |
| `:go` / `:go N` / `:go all` / `:W` | DONE | Dispatch steps |
| `:add "desc"` | DONE | Add step |
| `:del N` | DONE | Delete step |
| `:move N M` | DONE | Reorder step |
| `:file path` | DONE | Vim file viewer |
| `:set key val` | DONE | Config (model, backend, claude-model, autonomy) |
| `:pause N` / `:resume N` / `:kill N` | DONE | Daemon control |
| `:chat [target]` / `:close` | DONE | Chat panel |
| `:cohere files` | DONE | Coherence check |
| `:propagate` | DONE | Crawl cross-refs |
| `:tasks` | DONE | List queued tasks |
| `:load-task N` | DONE | Load queued task as plan |
| `:setup` | DONE | Config wizard |
| `:diff [N]` / `:log [N]` | DONE | Show diffs/logs |
| `:undo` | DONE | Revert last step |
| `:q` / `:q!` / `:wq` | DONE | Quit |
| `:help` | DONE | Help |

---

> **Core Planning Documents:** [Values](VALUES.md) → [Implementation](IMPLEMENTATION.md) → **Plan** → [Cost](COST.md) → [Revenue](REVENUE.md) → [Profit](PROFIT.md)
