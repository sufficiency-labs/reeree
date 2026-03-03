# CLAUDE.md — reeree

## What is reeree?
A dispatch console for LLM workers. Not a chatbot — a fleet management tool. Roombas, not interns.

Terminal-native, tmux-style persistent sessions, vim keybindings, plan-as-file steering, parallel workers, model-agnostic. Extracts the workflow power users already do by hand (tmux + vim + bash + LLM + git) into a single tool.

## Design Philosophy
- **Dispatch, not chat.** The user sends intents and commands. LLMs execute and report status. No conversation.
- **Plan is the interface.** A visible, editable markdown file. Steering is spatial (move/add/delete steps), not conversational.
- **Persistent sessions.** Daemon + Unix domain socket. Survives terminal death. Attach/detach like tmux.
- **Vim modal.** Normal, insert, command modes. No emacs.
- **Roombas.** Workers are disposable executors with focused context. They don't think — they clean.
- **Small context per step.** 32K models work fine. No 200K crutch.
- **Git-per-step.** Every step is a commit. Undo is trivial.
- **Tool, not agent.** Amplifies user autonomy. Has none of its own.

## Project Structure
```
reeree/
├── README.md              # Project overview and design
├── CLAUDE.md              # This file
├── pyproject.toml         # Package config
├── reeree/                # Python package
│   ├── __init__.py
│   ├── cli.py             # Entry point — start/attach/ls/kill sessions
│   ├── daemon.py          # Session daemon — Unix domain socket server
│   ├── client.py          # TUI client — Textual app, attaches to daemon
│   ├── tui/               # TUI components
│   │   ├── app.py         # Main Textual application
│   │   ├── plan_pane.py   # Plan view (left pane)
│   │   ├── worker_pane.py # Worker status view (right pane, stacked)
│   │   ├── command_bar.py # Vim command bar (bottom)
│   │   └── keybindings.py # Vim modal keybindings
│   ├── orchestrator.py    # Plan management + worker dispatch
│   ├── worker.py          # Individual worker — executes one step
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

## Key Commands
```
# Shell
reeree                          # start or reattach
reeree "make sync resilient"    # start with intent
reeree attach [name]            # attach to session
reeree ls                       # list sessions
reeree kill [name]              # kill session

# TUI command mode (:)
:go                             # dispatch pending steps
:pause [N]                      # pause worker(s)
:add "step description"         # add step
:del N                          # delete step
:diff [N]                       # show diff
:undo [N]                       # git revert step
:set autonomy low|medium|high   # approval level
:set model deepseek-v3          # change model
:log [N]                        # debug: show LLM interaction
:q                              # detach
:q!                             # kill + exit
```

## Development
- Python 3.11+
- Dependencies: textual (TUI), httpx (LLM API), click (CLI entry), gitpython (git ops)
- Test against sandbox/ project during development
- Run with local ollama for free iteration

## Conventions
- Keep it simple. Target ~3-5K lines total, not a framework.
- No over-engineering. Build what's needed for the dispatch console UX.
- Plan format is just markdown checkboxes — no custom DSL.
- Workers are dumb. They get a step, focused context, and execute. No memory between steps.
- The daemon is simple. Socket server, session state, worker pool. Not Kubernetes.
