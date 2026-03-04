# Project Plan

## Current Phase
Phase 1 is substantially complete. Core loop, daemon registry, model routing, tree view, and setup wizard all working. Phase 2 (persistence) is next.

---

## Phase 1: Core Loop (First Daemon) — 90% Complete
**Goal:** One daemon executes. You can dispatch it, watch it, and undo its work.
**Values tested:** [Delegated Agency](VALUES.md#1-delegated-agency), [Plan Is the Interface](VALUES.md#2-plan-is-the-interface), Git-Per-Step

### Deliverables
1. Plan parser/writer with annotation support — **DONE** (`plan.py`)
2. LLM API interface — **DONE** (`llm.py`)
3. Context builder — focused file loading per step — **DONE** (`context.py`)
4. Executor — file edit, shell run, git commit — **DONE** (`executor.py`)
5. Planner — intent → step list via LLM — **DONE** (`planner.py`)
6. Multi-turn daemon executor — read→edit→verify loop — **DONE** (`daemon_executor.py`)
7. Daemon registry — lifecycle, hierarchy, pause/resume/kill — **DONE** (`daemon_registry.py`)
8. Model router — tier-based multi-model dispatch — **DONE** (`router.py`)
9. TUI with vim modal editing, all commands — **DONE** (`tui/app.py`)
10. Daemon tree view — hierarchical display — **DONE** (`tui/daemon_tree.py`)
11. Setup wizard — first-run configuration — **DONE** (`tui/setup_screen.py`)
12. CLI entry point — start, resume, ls, kill — **DONE** (`cli.py`)
13. Sandbox project for testing — **DONE** (`sandbox/`)

### Success Criteria
- [x] `reeree "add error handling to scraper.py"` against sandbox project produces a plan
- [x] Each step executes and creates a git commit
- [x] `:undo` reverts the last step cleanly
- [x] Works with any OpenAI-compatible API (tested with together.ai)
- [ ] Works with ollama localhost (untested — needs setup wizard path)

### Remaining
- Ollama localhost testing
- Edge case hardening from dogfooding

---

## Phase 2: Persistence (The Daemon) — 10% Complete
**Goal:** Sessions survive terminal death. Attach/detach like tmux.
**Values tested:** [Persistence Without Fragility](VALUES.md#4-persistence-without-fragility)
**ADR:** [ADR-001](docs/strategic/decisions/ADR-001-unix-domain-socket.md)

### Deliverables
1. Session state serialization — Plan + DaemonRegistry → JSON → disk — **IN PROGRESS** (`session.py`)
2. Daemon process — background server with Unix domain socket
3. Session management — create, list, attach, detach, kill
4. Client protocol — messages over socket (JSON)
5. Graceful crash recovery — daemon restarts, reads state from disk, resumes

### Success Criteria
- [ ] `reeree` starts daemon if not running, attaches if running
- [ ] Kill terminal → daemon keeps running → `reeree attach` reconnects
- [ ] `reeree ls` shows active sessions
- [ ] Crash → restart → state recovered from disk
- [ ] Socket cleaned up properly on shutdown

---

## Phase 3: TUI Polish — 70% Complete
**Goal:** Multi-pane terminal interface with plan view, daemon status, and command bar.
**Values tested:** [Plan Is the Interface](VALUES.md#2-plan-is-the-interface), [Overlap Not Turn-Taking](VALUES.md#3-overlap-not-turn-taking)

### Deliverables
1. Textual app with three-zone layout — **DONE**
2. Plan pane — live-updating checklist — **DONE**
3. Daemon pane — daemon tree view with status — **DONE**
4. Command bar — vim command mode — **DONE**
5. Live plan editing — add/delete/reorder steps while daemons execute — **PARTIAL** (edit works, reorder pending)
6. Exec log pane — **DONE**
7. Chat panel — **DONE**

### Success Criteria
- [x] Can see plan and daemon status simultaneously
- [x] Can add a step while a daemon is executing another step
- [x] Daemon pane updates in real time as actions complete
- [x] Command bar accepts and executes all planned commands
- [ ] Step reordering while daemons execute

---

## Phase 4: Vim Keybindings (Muscle Memory) — 30% Complete
**Goal:** Full modal interface — normal, insert, command modes.
**Values tested:** [Vim Is the Lingua Franca](VALUES.md#5-vim-is-the-lingua-franca)

### Deliverables
1. Normal mode — hjkl navigation, J/K to reorder steps
2. Insert mode (i) — type new step descriptions, annotations — **DONE**
3. Command mode (:) — all dispatch and control commands — **DONE**
4. Visual feedback — mode indicator in status bar — **DONE**
5. Key mapping configuration (optional)

### Success Criteria
- [ ] Navigate plan with hjkl
- [x] `i` enters insert mode to add step, `Esc` returns to normal
- [x] `:go` dispatches, `:pause` pauses, `:undo` reverts
- [x] Mode indicator shows current mode
- [ ] Full hjkl muscle memory transfer

---

## Phase 5: Parallel Daemons (The Fleet)
**Goal:** Multiple daemons running simultaneously on independent steps.
**Values tested:** [Overlap Not Turn-Taking](VALUES.md#3-overlap-not-turn-taking), [Sufficiency Over Maximalism](VALUES.md#6-sufficiency-over-maximalism)

### Deliverables
1. Daemon pool — configurable number of concurrent daemons (default: 2)
2. Dependency detection — steps that touch the same files run sequentially
3. Daemon pane stacking — multiple daemon status views in right pane
4. Per-daemon controls — `:pause 2`, `:kill 1`, `:log 3`
5. Progress summary — `(3/7 done, 2 active, 2 pending)`

### Success Criteria
- [ ] Two independent steps execute in parallel
- [ ] Dependent steps (same files) wait correctly
- [ ] Can pause one daemon while others continue
- [ ] Daemon panes show independent status streams
- [ ] Wall-clock time for independent steps ≈ time for longest single step

---

## Phase 6: Polish and Dogfood
**Goal:** Use reeree to develop reeree. Fix everything that hurts.
**Values tested:** [All values](VALUES.md), in practice.

### Deliverables
1. Dogfood for 2 weeks on real projects
2. Fix UX friction discovered during dogfooding
3. Error recovery improvements (bad LLM output, network failures, git conflicts)
4. Performance tuning (startup time, daemon dispatch latency)
5. Documentation — usage guide, config reference

### Success Criteria
- [ ] Can use reeree for a full development session without falling back to manual workflow
- [ ] Startup to first dispatched step < 5 seconds
- [ ] No data loss scenarios in normal operation
- [ ] A new user can install and run their first intent in < 2 minutes

---

## Phase 7: Release
**Goal:** Open source release.
**Values tested:** No Lock-in, [Sufficiency Over Maximalism](VALUES.md#6-sufficiency-over-maximalism)

### Deliverables
1. License decision (likely MIT or Apache 2.0)
2. PyPI package — `pip install reeree`
3. README with clear positioning: dispatch console, not chatbot
4. Demo video/gif showing the workflow
5. Contributing guide

### Success Criteria
- [ ] `pip install reeree && reeree "hello world"` works on a fresh machine
- [ ] README communicates the dispatch paradigm clearly
- [ ] At least one non-Rob user can install and use it successfully

---

## Phase 8: Plugin Ecosystem
**Goal:** Extensibility via Python entry points. Complexity is opt-in.
**Values tested:** [Sufficiency Over Maximalism](VALUES.md#6-sufficiency-over-maximalism), [Delegated Agency](VALUES.md#1-delegated-agency)
**ADRs:** [ADR-009](docs/strategic/decisions/ADR-009-plugin-architecture.md), [ADR-010](docs/strategic/decisions/ADR-010-inter-daemon-communication.md)

### Deliverables
1. Plugin base class + entry point discovery — **IN PROGRESS** (`plugin.py`)
2. Inter-daemon message bus — **IN PROGRESS** (`message_bus.py`)
3. Plugin hook dispatch (on_plan_loaded, on_step_dispatched, on_step_completed)
4. Plugin command registration (extends `:` commands)
5. Example plugin: `reeree-branch` (branch-per-daemon isolation)

### Success Criteria
- [ ] `from reeree.plugin import ReereePlugin` works
- [ ] Plugins discovered via `importlib.metadata.entry_points`
- [ ] Plugin commands appear in `:help`
- [ ] Message bus delivers messages between daemons
- [ ] Core works with zero plugins installed

---

## MVP Definition

The MVP is **Phase 1 + Phase 2 + Phase 3**: a single daemon executing plan steps through a persistent TUI. This is the smallest thing that validates the core thesis: **dispatch console with visible plan beats chatbot with hidden state.**

Phase 4-5 (vim bindings, parallel daemons) are important but not required to test the thesis. Phase 6-7 (polish, release) come after validation. Phase 8 (plugins) comes after release.

---

> **Core Planning Documents:** [Values](VALUES.md) → [Implementation](IMPLEMENTATION.md) → **Plan** → [Cost](COST.md) → [Revenue](REVENUE.md) → [Profit](PROFIT.md)
