# POC Implementation Plan

**Goal:** Working demo where you edit a markdown plan in a Textual TUI, dispatch steps to an ollama-backed worker, and watch checkboxes tick. No daemon yet (Phase 2). Just the living document + one roomba.

**Timeline:** 2-3 weeks to POC, then iterate.

---

## Week 1: The Living Document

### Day 1-2: Textual markdown editor widget
- [ ] Study Frogmouth's markdown rendering (Textualize/frogmouth, MIT)
- [ ] Study Textual's built-in TextArea widget — it already has vim keybinding support
- [ ] Build `PlanEditor` widget: a TextArea that renders markdown plan format
  - Checkbox lines render with status colors (green=done, yellow=active, dim=pending)
  - Annotation lines (> ...) render indented and dimmer
  - Commit hashes render as clickable/highlightable
  - Cross-reference links ([text](path)) are visible
- [ ] Wire up plan.py parsing ↔ TextArea content (bidirectional)
- [ ] Test: can edit plan markdown, save, reload, round-trips cleanly

### Day 3-4: Textual app shell
- [ ] Build `ReereeApp(App)` — main Textual application
  - Full-screen PlanEditor as primary view
  - Status bar at bottom: mode indicator, worker count, progress (3/7)
  - Command bar (vim `:` mode) at bottom
- [ ] Implement basic vim modes:
  - Normal: hjkl in plan, dd to delete step, J/K to reorder
  - Insert (i): edit step descriptions, (o): new step below, (a): add annotation
  - Command (:): parse and execute commands
- [ ] Wire `:q` to quit, `:w` to save plan to disk
- [ ] Test: can launch app, see plan, navigate with vim keys, edit steps, save

### Day 5: Commands and splits
- [ ] Implement `:add "description"` — inserts new step
- [ ] Implement `:del N` — deletes step N
- [ ] Implement `:move N M` — reorders step
- [ ] Implement `:shell` — opens a split pane with terminal (Textual has Terminal widget?)
  - If no Terminal widget, use a read-only log pane that shows subprocess output
- [ ] Implement `:diff N` — split pane showing git diff for step N's commit
- [ ] `Ctrl-w q` or `:close` to close split panes
- [ ] Test: full edit loop — add steps, reorder, delete, open/close splits

---

## Week 2: The First Roomba

### Day 6-7: Worker execution loop
- [ ] Build `Worker` class:
  - Takes a Step + focused context
  - Calls LLM API (existing llm.py)
  - Parses response into actions (file edits, shell commands)
  - Executes actions (existing executor.py)
  - Creates git commit
  - Reports status back
- [ ] Build `Orchestrator`:
  - Watches plan for pending steps
  - When `:go` is called, picks next pending step
  - Spawns Worker in async task
  - Updates step status (pending → active → done/failed)
  - Updates plan file on disk
- [ ] Wire Worker status into TUI:
  - Step checkbox updates live as worker progresses
  - Worker status shows in status bar
- [ ] Test: `:go` dispatches step, worker executes, checkbox updates

### Day 8-9: Context and cross-references
- [ ] Upgrade context.py:
  - Parse `> files:` annotations for explicit file loading
  - Parse `> see [name](path)` links — follow and load referenced docs
  - Parse `> done:` criteria — include in worker's system prompt
  - Free-form annotations become part of worker prompt
- [ ] Smart context: if no files specified, use planner to identify relevant files
- [ ] Test: annotations actually affect worker behavior (done criteria, file hints, linked docs)

### Day 10: Integration and `:log` pane
- [ ] Implement `:log N` — split pane showing worker N's execution stream:
  - Files read
  - Actions taken (edits, shell commands, output)
  - LLM prompt/response (verbose mode)
  - Final status
- [ ] Implement `:undo N` — git revert for step N's commit
- [ ] Implement `:set model <name>` — change model on the fly
- [ ] Implement `:set autonomy low|medium|high` — change approval level
- [ ] Full integration test against sandbox project:
  - `reeree "add error handling to scraper.py"` (or launch app, type intent)
  - Plan appears in editor
  - Edit annotations on steps
  - `:go` dispatches
  - Watch checkboxes tick
  - `:log 1` to see what worker did
  - `:undo 1` to revert
- [ ] Test with ollama localhost — must work with free local model

---

## Week 3: Polish POC

### Day 11-12: Daemon (minimal)
- [ ] Unix domain socket server (`~/.reeree/sock`)
  - Start daemon: `reeree` when no daemon running
  - Attach: `reeree` when daemon exists → TUI connects to socket
  - Detach: `:q` detaches client, daemon keeps running
  - Kill: `:q!` or `reeree kill`
- [ ] Session state serialization — plan + worker status → JSON on disk
- [ ] `reeree ls` — list active sessions
- [ ] Crash recovery: daemon reads state from disk on restart
- [ ] Test: start, detach, reattach, verify state preserved

### Day 13-14: Parallel workers
- [ ] Worker pool (default: 2 concurrent)
- [ ] `:go` dispatches all pending steps to available workers
- [ ] Independent steps run in parallel
- [ ] Dependent steps (same files) queued
- [ ] Multiple worker status indicators in status bar
- [ ] `:pause N` / `:kill N` per worker
- [ ] Test: two independent steps execute simultaneously

### Day 15: Demo and dogfood prep
- [ ] Record demo: full workflow against sandbox project
- [ ] Document actual keybindings that work
- [ ] Fix top 5 UX papercuts found during testing
- [ ] Write QUICKSTART.md — install, configure ollama, first run
- [ ] Dogfood checkpoint: use reeree to develop reeree (Phase 6 starts)

---

## Key Technical Decisions

### TextArea vs custom widget for plan editor
Textual's built-in `TextArea` supports:
- Syntax highlighting (can customize for our plan format)
- Vim-style keybindings (built-in!)
- Undo/redo
- Selection, copy/paste

**Decision:** Start with TextArea, customize highlighting for plan syntax. Only build custom widget if TextArea doesn't support the live-updating checkboxes we need.

### Worker dispatch: async tasks
Workers run as `asyncio.Task` inside the Textual app's event loop. No threads, no subprocess workers. The LLM call is async (httpx supports async). File operations are fast enough to run in the event loop. Shell commands use `asyncio.create_subprocess_exec`.

### Plan file watching
Two approaches:
1. **App owns the plan**: only the TUI edits plan.md, workers report back via messages
2. **File watching**: plan.md is the source of truth, any editor can modify it, TUI watches for changes

**Decision for POC:** App owns the plan. File watching is Phase 6 (enables editing in external vim while TUI runs — the ultimate "it's just a markdown file" proof).

### LLM response format
Workers need structured output (file edits, shell commands). Options:
1. JSON mode (current approach in executor.py)
2. Tool/function calling (requires provider support)
3. Markdown with code blocks (parse naturally)

**Decision for POC:** JSON mode. It works with every provider. Upgrade to tool calling later if needed.

---

## Dependencies

```
textual>=0.80        # TUI framework (includes TextArea with vim support)
httpx>=0.27          # Async HTTP for LLM API
click>=8.1           # CLI entry point
gitpython>=3.1       # Git operations
```

No new dependencies beyond what's in pyproject.toml.

## Success Criteria for POC

The POC is successful when you can:
1. Launch reeree, see your plan as a markdown document
2. Edit the plan with vim keybindings
3. Add annotations to steps (specs, acceptance criteria, file hints)
4. `:go` dispatches a step to a worker (ollama local model)
5. Watch the checkbox update from [ ] to [>] to [x]
6. `:log 1` shows what the worker did
7. `:undo` reverts the step
8. Detach, reattach, state preserved
9. Two workers running in parallel on independent steps
10. Total time from `pip install -e .` to first dispatched step: < 2 minutes
