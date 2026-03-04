# Project Plan

## Current Phase
Phase 1 — Core Loop. Get a single daemon executing a single step from a plan, with the user watching.

---

## Phase 1: Core Loop (First Daemon)
**Goal:** One daemon executes. You can dispatch it, watch it, and undo its work.
**Values tested:** [Delegated Agency](VALUES.md#1-delegated-agency), [Plan Is the Interface](VALUES.md#2-plan-is-the-interface), Git-Per-Step

### Deliverables
1. Plan parser/writer with annotation support (DONE — `plan.py`)
2. LLM API interface (DONE — `llm.py`)
3. Context builder — focused file loading per step (DONE — `context.py`)
4. Executor — file edit, shell run, git commit (DONE — `executor.py`)
5. Planner — intent → step list via LLM (DONE — `planner.py`)
6. Single-daemon orchestrator — pick step, gather context, call LLM, execute actions, commit
7. Basic CLI — `reeree "intent"` → plan → approve → execute step by step
8. Sandbox project for testing

### Success Criteria
- [ ] `reeree "add error handling to scraper.py"` against sandbox project produces a plan
- [ ] Each step executes and creates a git commit
- [ ] `:undo` reverts the last step cleanly
- [ ] Works with ollama localhost (no cloud API required)

### Status: IN PROGRESS
Core modules exist. Need orchestrator + CLI integration.

---

## Phase 2: Persistence (The Daemon)
**Goal:** Sessions survive terminal death. Attach/detach like tmux.
**Values tested:** [Persistence Without Fragility](VALUES.md#4-persistence-without-fragility)

### Deliverables
1. Daemon process — background server with Unix domain socket
2. Session management — create, list, attach, detach, kill
3. Session state serialization — plan + daemon status on disk
4. Client protocol — messages over socket (JSON or msgpack)
5. Graceful crash recovery — daemon restarts, reads state from disk, resumes

### Success Criteria
- [ ] `reeree` starts daemon if not running, attaches if running
- [ ] Kill terminal → daemon keeps running → `reeree attach` reconnects
- [ ] `reeree ls` shows active sessions
- [ ] Crash → restart → state recovered from disk
- [ ] Socket cleaned up properly on shutdown

---

## Phase 3: TUI (The Heads-Up Display)
**Goal:** Multi-pane terminal interface with plan view, daemon status, and command bar.
**Values tested:** [Plan Is the Interface](VALUES.md#2-plan-is-the-interface), [Overlap Not Turn-Taking](VALUES.md#3-overlap-not-turn-taking)

### Deliverables
1. Textual app with three-zone layout: plan (left), daemons (right), command bar (bottom)
2. Plan pane — live-updating checklist, highlights active step
3. Daemon pane — shows current action, file being edited, diff preview
4. Command bar — vim command mode for `:go`, `:pause`, `:add`, etc.
5. Live plan editing — add/delete/reorder steps while daemons execute
6. Pane resizing and focus management

### Success Criteria
- [ ] Can see plan and daemon status simultaneously
- [ ] Can add a step while a daemon is executing another step
- [ ] Daemon pane updates in real time as actions complete
- [ ] Command bar accepts and executes all planned commands

---

## Phase 4: Vim Keybindings (Muscle Memory)
**Goal:** Full modal interface — normal, insert, command modes.
**Values tested:** [Vim Is the Lingua Franca](VALUES.md#5-vim-is-the-lingua-franca)

### Deliverables
1. Normal mode — hjkl navigation in plan, J/K to reorder steps
2. Insert mode (i) — type new step descriptions, annotations
3. Command mode (:) — all dispatch and control commands
4. Visual feedback — mode indicator in status bar
5. Key mapping configuration (optional)

### Success Criteria
- [ ] Navigate plan with hjkl
- [ ] `i` enters insert mode to add step, `Esc` returns to normal
- [ ] `:go` dispatches, `:pause` pauses, `:undo` reverts
- [ ] Mode indicator shows current mode
- [ ] Muscle memory from vim transfers directly

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

## MVP Definition

The MVP is **Phase 1 + Phase 2 + Phase 3**: a single daemon executing plan steps through a persistent TUI. This is the smallest thing that validates the core thesis: **dispatch console with visible plan beats chatbot with hidden state.**

Phase 4-5 (vim bindings, parallel daemons) are important but not required to test the thesis. Phase 6-7 (polish, release) come after validation.

---

> **Core Planning Documents:** [Values](VALUES.md) → [Implementation](IMPLEMENTATION.md) → **Plan** → [POC](POC_PLAN.md) → [Cost](COST.md) → [Revenue](REVENUE.md) → [Profit](PROFIT.md)
