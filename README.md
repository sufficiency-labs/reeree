# reeree

You edit a markdown document. Roombas respond to what you write.

## What is this?

The interface is a **living markdown document** — your plan. You write steps, annotate them with specs, link to other docs for context. Workers (roombas) pick up steps, read your annotations, execute, and update the checkboxes. You're always editing ahead of them.

Everything else — worker logs, shell access, file views, diffs — opens as a split pane when you want it and closes when you don't. The document is always there.

Not a chatbot. Not an IDE. A markdown document that things happen to.

## The Problem

Every LLM coding tool is a chatbot. You type, it types back, you have a conversation. That's the wrong paradigm. You don't want to *talk* to your tools. You want to *direct* them.

Power users already have the right workflow: tmux for persistence, vim for editing, bash for execution, git for undo. But they're the glue. reeree makes the document the glue instead.

## How it works

You're in a persistent terminal session, editing a markdown document:

```markdown
# Plan: make sync resilient

- [x] Read current sync scripts [a3f2c01]
- [>] Add retry logic to sync.sh (worker 1)
  > max 3 retries, exponential backoff
  > see [retry patterns](./docs/retry-patterns.md)
  > done: scripts/test-retry.sh passes
- [ ] Add heartbeat check
  > see [heartbeat spec](./docs/heartbeat.md)
  > done: heartbeat.sh writes timestamp, watchdog reads it
- [ ] Wire heartbeat into cron
  > files: scripts/crontab, scripts/watchdog.sh
```

That's the interface. You're editing this document. The roombas are reading it too.

- Write a new step → next idle roomba picks it up
- Add an annotation (`> done: tests pass`) → the roomba reads it as acceptance criteria
- Link to another doc (`[spec](./docs/spec.md)`) → the roomba follows the link and reads it as context
- Delete a step → the roomba that was about to start it doesn't
- Reorder steps → execution order changes

The document is simultaneously the spec, the status display, the steering wheel, the history, and the context system.

## Peeking behind the curtain

The document is home base. When you want to look at what a roomba is doing:

```
:log 1          → split pane with worker 1's execution stream
:shell          → split pane with a bash shell
:diff 3         → split pane showing the diff from step 3
:file sync.sh   → split pane showing the file
Ctrl-w q        → close the pane, back to your document
```

Every pane is ephemeral. The document is permanent. This is vim's split/buffer model — open a view, use it, close it.

```
┌──────────────────────────┬──────────────────────┐
│                          │ worker 1 log         │
│   Your document          │ > read sync.sh       │
│   (still here,           │ > edit: +@retry      │
│    still editable)       │ > shell: pytest       │
│                          │   PASS (3 tests)     │
│   - [x] Read sync...    │ > git commit a3f2c01 │
│   - [>] Add retry...    │ STATUS: done          │
│   - [ ] Add heartbeat   │                      │
│                          │                      │
├──────────────────────────┴──────────────────────┤
│ NORMAL  :log 1                      2 roombas   │
└─────────────────────────────────────────────────┘
```

Close the split. Back to full-screen document. Open a shell. Same pattern.

## Key properties

**The document is alive.** Checkboxes update as workers complete steps. Worker assignment shows in real time. Commit hashes appear when steps finish.

**Cross-references are context.** Link to another markdown doc and the worker reads it. Your existing docs, specs, READMEs — they're all feedable context. Just link.

**Annotations are inline specs.** Indent with `> ` under a step to give the worker instructions, acceptance criteria, file hints. The worker reads them before executing.

**Sessions persist.** tmux-style daemon. Kill your terminal, reconnect later, document and workers are right where you left them.

**Git is undo.** Every completed step is a git commit. `:undo 3` reverts step 3. Mistakes cost nothing.

**Any model.** ollama local models by default. Any OpenAI-compatible API. Switch models with `:set model deepseek-v3`. No subscriptions required.

**Vim keybindings.** Normal/insert/command modes. hjkl navigation. `:` commands. Your muscle memory works.

## Commands

```
# Terminal
reeree                          # start or reattach session
reeree "intent goes here"       # start with initial plan generation
reeree attach [name]            # attach to running session
reeree ls                       # list sessions
reeree kill [name]              # kill a session

# Inside the document (command mode)
:go                             # dispatch pending steps to roombas
:pause [N]                      # pause worker(s)
:kill [N]                       # kill worker N
:add "step description"         # add step to plan
:del N                          # delete step N
:move N M                       # move step N to position M
:diff [N]                       # split: show diff from step N
:log [N]                        # split: show worker N's execution log
:file <path>                    # split: show a file
:shell                          # split: open bash
:undo [N]                       # git revert step N
:set autonomy low|medium|high   # approval level for writes
:set model <name>               # change LLM model
:q                              # detach (session keeps running)
:q!                             # kill session and exit
```

## Architecture

```
┌──────────────────────────────────────────────┐
│                 reeree daemon                 │
│           (Unix domain socket)               │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │           Orchestrator                  │  │
│  │  plan.md ←→ worker pool ←→ git         │  │
│  └────────────┬───────────────────────────┘  │
│               │                              │
│  ┌────────┐ ┌────────┐ ┌────────┐           │
│  │Roomba 1│ │Roomba 2│ │Roomba N│           │
│  │(step 2)│ │(step 3)│ │ (idle) │           │
│  └───┬────┘ └───┬────┘ └────────┘           │
│      │          │                            │
│  ┌───┴──────────┴──────────────┐             │
│  │     LLM API (any model)     │             │
│  └─────────────────────────────┘             │
└──────────────┬───────────────────────────────┘
               │ Unix domain socket
┌──────────────┴───────────────────────────────┐
│           reeree client (TUI)                │
│  Textual app — document view + split panes   │
│  Vim keybindings — attach/detach             │
└──────────────────────────────────────────────┘
```

## Values

Built with [Values-Driven Systems Engineering](https://github.com/robbymeals/values-driven-systems-engineering). See [VALUES.md](VALUES.md) for the full statement.

- **Tool, not agent** → Roombas execute. They don't initiate, suggest, or opine.
- **Document is the interface** → All state is visible, editable prose. Nothing hidden.
- **Overlap, not turn-taking** → You edit ahead. Roombas work behind. Nobody waits.
- **Persistence** → Sessions survive terminal death. Work survives everything (git).
- **Sufficiency** → $0 with local models. 32K context works fine.

## Status

Early development. Core modules exist. See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the roadmap.

## License

TBD
