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
- Workers are dumb. They get a step, focused context, and execute. No memory between steps.
- The daemon is simple. Socket server, session state, worker pool. Not Kubernetes.

## Daemon Types (Architecture Note)

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

The TUI, socket architecture, and vim interface are generic daemon management. reeree is the first daemon type, not the only one.
