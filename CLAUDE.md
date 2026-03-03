# CLAUDE.md — reeree

## What is reeree?
A terminal-native LLM coding tool with shell execution capabilities and responsive steering. Think Claude Code's agentic capabilities but model-agnostic, cheap, and with the plan as a visible, editable artifact the user controls.

## Design Philosophy
- It's a **terminal tool** — runs in your shell, IS your shell companion
- The user is always in control — this is an Iron Man suit, not an autonomous agent
- Small context per step — works with 32K models via task decomposition
- Plan-as-file — the steering mechanism is a markdown plan both human and tool read/write
- Git-per-step — every atomic change is a commit, undo is trivial

## Project Structure
```
reeree/
├── README.md          # Project overview and design
├── CLAUDE.md          # This file
├── reeree/            # Python package
│   ├── __init__.py
│   ├── cli.py         # Entry point, terminal UI, user interaction loop
│   ├── planner.py     # Task decomposition — big intent → step list
│   ├── executor.py    # Step execution — file edits, shell commands, git
│   ├── context.py     # Context management — load only what's needed per step
│   ├── llm.py         # LLM API interface (OpenAI-compatible)
│   ├── plan.py        # Plan file read/write/display
│   └── config.py      # Configuration (model, API endpoint, autonomy level)
├── tests/             # Test suite
├── sandbox/           # Test project for development/testing
└── pyproject.toml     # Package config
```

## Key Commands (planned)
```
reeree "make the sync resilient"     # Start with an intent
reeree --plan plan.md                # Resume from existing plan
reeree --model ollama/deepseek-v3    # Specify model
reeree --autonomy high               # Auto-approve reads, pause on writes
reeree --autonomy low                # Approve every step
```

## Development
- Python 3.11+
- Dependencies: httpx (LLM API), rich (terminal UI), click (CLI), gitpython (git ops)
- Test against sandbox/ project during development
- Run with local ollama for free iteration

## Conventions
- Keep it simple. This is ~2-3K lines, not a framework.
- No over-engineering. Build what's needed, nothing more.
- The plan.md format is just markdown checkboxes — no custom DSL.
