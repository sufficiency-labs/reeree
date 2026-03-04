# reeree

An LLM-assisted systems engineering tool. You edit a markdown document. Daemons respond to what you write.

Terminal-native, tmux-style persistent sessions, vim keybindings, plan-as-file steering, parallel daemons, model-agnostic. Extracts the workflow power users already do by hand (tmux + vim + bash + LLM + git) into a single tool.

## What is this?

The interface is a **living markdown document** — your plan. You write steps, annotate them with specs, link to other docs for context. Daemons pick up steps, read your annotations, execute, and update the checkboxes. You're always editing ahead of them.

Everything else — daemon logs, shell access, file views, diffs — opens as a split pane when you want it and closes when you don't. The document is always there.

Not a chatbot. Not an IDE. A markdown document that things happen to.

## The Problem

Every LLM coding tool is a chatbot. You type, it types back, you have a conversation. That's the wrong paradigm. You don't want to *talk* to your tools. You want to *direct* them.

Power users already have the right workflow: tmux for persistence, vim for editing, bash for execution, git for undo. But they're the glue. reeree makes the document the glue instead.

## How it works

You're in a persistent terminal session, editing a markdown document:

```markdown
# Plan: make sync resilient

- [x] Read current sync scripts [a3f2c01]
- [>] Add retry logic to sync.sh (daemon 1)
  > max 3 retries, exponential backoff
  > see [retry patterns](./docs/retry-patterns.md)
  > done: scripts/test-retry.sh passes
- [ ] Add heartbeat check
  > see [heartbeat spec](./docs/heartbeat.md)
  > done: heartbeat.sh writes timestamp, watchdog reads it
- [ ] Wire heartbeat into cron
  > files: scripts/crontab, scripts/watchdog.sh
```

That's the interface. You're editing this document. The daemons are reading it too.

- Write a new step → next idle daemon picks it up
- Add an annotation (`> done: tests pass`) → the daemon reads it as acceptance criteria
- Link to another doc (`[spec](./docs/spec.md)`) → the daemon follows the link and reads it as context
- Delete a step → the daemon that was about to start it doesn't
- Reorder steps → execution order changes

The document is simultaneously the spec, the status display, the steering wheel, the history, and the context system.

## Peeking behind the curtain

The document is home base. When you want to look at what a daemon is doing:

```
:log 1          → split pane with daemon 1's execution stream
:shell          → split pane with a bash shell
:diff 3         → split pane showing the diff from step 3
:file sync.sh   → split pane showing the file
Ctrl-w q        → close the pane, back to your document
```

Every pane is ephemeral. The document is permanent. This is vim's split/buffer model — open a view, use it, close it.

```
┌──────────────────────────┬──────────────────────┐
│                          │ daemon 1 log         │
│   Your document          │ > read sync.sh       │
│   (still here,           │ > edit: +@retry      │
│    still editable)       │ > shell: pytest       │
│                          │   PASS (3 tests)     │
│   - [x] Read sync...    │ > git commit a3f2c01 │
│   - [>] Add retry...    │ STATUS: done          │
│   - [ ] Add heartbeat   │                      │
│                          │                      │
├──────────────────────────┴──────────────────────┤
│ NORMAL  :log 1                     2 daemons   │
└─────────────────────────────────────────────────┘
```

Close the split. Back to full-screen document. Open a shell. Same pattern.

## Key properties

**The document is alive.** Checkboxes update as daemons complete steps. Daemon assignment shows in real time. Commit hashes appear when steps finish.

**Cross-references are context.** Link to another markdown doc and the daemon reads it. Your existing docs, specs, READMEs — they're all feedable context. Just link.

**Annotations are inline specs.** Indent with `> ` under a step to give the daemon instructions, acceptance criteria, file hints. The daemon reads them before executing.

**Sessions persist.** tmux-style daemon. Kill your terminal, reconnect later, document and daemons are right where you left them.

**Git is undo.** Every completed step is a git commit. `:undo 3` reverts step 3. Mistakes cost nothing.

**Any model.** ollama local models by default. Any OpenAI-compatible API. Switch models with `:set model deepseek-v3`. No subscriptions required.

**Vim keybindings.** Normal/insert/command modes. hjkl navigation. `:` commands. Your muscle memory works.

## Design Philosophy

- **Dispatch, not chat.** The user sends intents and commands. LLMs execute and report status. No conversation.
- **Plan is the interface.** A visible, editable markdown file. Steering is spatial (move/add/delete steps), not conversational.
- **Delegated agency.** The tool acts with the user's delegated authority. It can be autonomous within dispatch scope, but the user is always the principal. Like any process — it has agency, but it's the user's agency.
- **Persistent sessions.** Daemon + Unix domain socket. Survives terminal death. Attach/detach like tmux.
- **Vim modal.** Normal, insert, command modes. No emacs.
- **Small context per step.** 32K models work fine. No 200K crutch.
- **Git-per-step.** Every step is a commit. Undo is trivial.
- **Personality, not anthropomorphism.** The tool has a voice. It doesn't pretend to think or feel. Same distinction as any good CLI — pandoc has personality, it doesn't have sentience.

See [VALUES.md](VALUES.md) for the full values statement and [IMPLEMENTATION.md](IMPLEMENTATION.md) for how values trace to code decisions.

## Commands

```
# Terminal
reeree                          # start or reattach session
reeree "intent goes here"       # start with initial plan generation
reeree attach [name]            # attach to running session
reeree ls                       # list sessions
reeree kill [name]              # kill a session

# Inside the document (command mode)
:go                             # dispatch pending steps to daemons
:w                              # dispatch up to cursor / save
:W                              # dispatch ALL pending steps
:pause [N]                      # pause daemon(s)
:kill [N]                       # kill daemon N
:add "step description"         # add step to plan
:del N                          # delete step N
:move N M                       # move step N to position M
:diff [N]                       # split: show diff from step N
:log [N]                        # split: show daemon N's execution log
:file <path>                    # split: show a file
:shell                          # split: open bash
:undo [N]                       # git revert step N
:set autonomy low|medium|high   # approval level for writes
:set model <name>               # change LLM model
:cd <path>                      # change scope to subrepo
:cd ..                          # return to parent scope
:scope                          # show scope stack
:cohere [path|glob]             # check document coherence
:propagate                      # propagate changes through linked docs
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
│  │  plan.md ←→ daemon pool ←→ git         │  │
│  └────────────┬───────────────────────────┘  │
│               │                              │
│  ┌────────┐ ┌────────┐ ┌────────┐           │
│  │Daemon 1│ │Daemon 2│ │Daemon N│           │
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

## Daemon Types

Executor daemons are one type. The framework manages any persistent LLM process:

| Type | Trigger | Reads | Writes | Always-on? |
|------|---------|-------|--------|------------|
| Executor | dispatched (:go) | plan step + focused context | code, shell, git | no |
| Coherence | triggered (:propagate, :cohere, on-save) | linked doc tree | conflict flags, update proposals | no |
| State | always-on | user activity, inputs, patterns | state.md assessment | yes |
| Forecast | scheduled/triggered | calendar, state, history | forecast.md | no |
| Orchestrator | on dispatch | step description, model registry | routing decision, cost estimate | no |

All daemons share the same shape:
- Persistent LLM process with focused context
- Specific domain and instruction set
- Read/write interface to files on disk
- Visible output (split pane in TUI)
- User can read, edit, override any daemon's output

Daemons are processes. Some are short-lived (execute a step and exit), some are persistent (coherence, state monitoring). Same UX model as Unix processes — some run in the foreground, some in the background, some are long-lived services.

## Project Structure

```
reeree/
├── README.md              # This file (project overview + dev guide)
├── pyproject.toml         # Package config
├── reeree/                # Python package
│   ├── __init__.py
│   ├── cli.py             # Entry point — start/attach/ls/kill sessions
│   ├── daemon.py          # Session daemon — Unix domain socket server
│   ├── client.py          # TUI client — Textual app, attaches to daemon
│   ├── tui/               # TUI components
│   │   ├── app.py         # Main Textual application
│   │   ├── plan_pane.py   # Plan view (left pane)
│   │   ├── worker_pane.py # Daemon status view (right pane, stacked)
│   │   ├── command_bar.py # Vim command bar (bottom)
│   │   └── keybindings.py # Vim modal keybindings
│   ├── orchestrator.py    # Plan management + daemon dispatch
│   ├── worker.py          # Individual daemon — executes one step
│   ├── planner.py         # Intent → step list decomposition
│   ├── executor.py        # File edits, shell commands, git ops
│   ├── context.py         # Load focused context per step
│   ├── llm.py             # LLM API interface (OpenAI-compatible)
│   ├── plan.py            # Plan file read/write
│   └── config.py          # Configuration
├── tests/                 # Test suite
├── sandbox/               # Test project for development
└── .gitignore
```

## Development

### Setup
```bash
source /mnt/vorkosigan_data_v2/vorkosigan/.venv/bin/activate
cd /mnt/vorkosigan_data_v2/vorkosigan/private/reeree
pip install -e .
```

### Running
```bash
# Launch TUI with a new plan
reeree --project sandbox "add error handling to the scraper"

# Launch TUI, resume existing plan
reeree --project sandbox

# Inside TUI: NORMAL mode by default
#   i         → INSERT mode (edit the plan)
#   Escape    → back to NORMAL
#   :         → COMMAND mode
#   :go       → dispatch daemons for pending steps
#   :help     → full command reference
```

### Testing
```bash
# Run all tests
python -m pytest tests/ -v

# Run just unit tests (no API calls)
python -m pytest tests/ -v -k "not (test_basic_response or test_json_response or test_system_prompt or test_edit_step or test_write_step or test_logging_callback)"

# Run integration tests (requires together.ai key at ~/.config/together/api_key)
python -m pytest tests/test_daemon_executor.py tests/test_llm.py -v

# See xfail tests (unimplemented features)
python -m pytest tests/test_unimplemented.py -v
```

### Self-testing from Claude Code
The TUI requires a real terminal, but the daemon executor can be tested headlessly:
```python
import asyncio
from pathlib import Path
from reeree.config import Config
from reeree.plan import Step
from reeree.daemon_executor import dispatch_step

async def test():
    config = Config()
    step = Step(description="Add a docstring to main()", files=["scraper.py"])
    result = await dispatch_step(step=step, step_index=0, project_dir=Path("sandbox"), config=config, on_log=print)
    print(result)

asyncio.run(test())
```

### Dependencies
- Python 3.11+
- textual (TUI), httpx (LLM API), click (CLI), gitpython (git), tree-sitter-markdown (syntax)
- LLM: together.ai with Qwen3-Coder-480B-A35B-Instruct-FP8 (default), any OpenAI-compatible API
- API key: `~/.config/together/api_key` or `TOGETHER_API_KEY` env var

## Conventions
- Keep it simple. Target ~3-5K lines total, not a framework.
- No over-engineering. Build what's needed for the dispatch console UX.
- Plan format is just markdown checkboxes — no custom DSL.
- The session daemon is simple. Socket server, session state, daemon pool. Not Kubernetes.

## Values

Built with [Values-Driven Systems Engineering](https://github.com/robbymeals/values-driven-systems-engineering). See [VALUES.md](VALUES.md) for the full statement.

- **Delegated agency** → The tool acts with your authority, not its own. You dispatch, it executes within scope.
- **Document is the interface** → All state is visible, editable prose. Nothing hidden.
- **Overlap, not turn-taking** → You edit ahead. Daemons execute behind. Nobody waits.
- **Persistence** → Sessions survive terminal death. Work survives everything (git).
- **Sufficiency** → $0 with local models. 32K context works fine.
- **Personality, not anthropomorphism** → The tool has a voice. It doesn't pretend to think or feel.

## Status

Early development. Core modules exist. See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the roadmap.

---

> **Core Planning Documents:**
> - [VALUES.md](VALUES.md) — Why we build this way
> - [IMPLEMENTATION.md](IMPLEMENTATION.md) — How values trace to code decisions
> - [PROJECT_PLAN.md](PROJECT_PLAN.md) — What's next (7-phase roadmap)
> - [POC_PLAN.md](POC_PLAN.md) — The 3-week proof of concept
> - [COST.md](COST.md) — What it costs ($0 local, $5-15 cloud)
> - [REVENUE.md](REVENUE.md) — How it might sustain itself
> - [PROFIT.md](PROFIT.md) — What success looks like

## License

TBD
