# reeree

High-bandwidth, tight-steering LLM coding tool. The Iron Man suit for shell.

## What is this?

A CLI tool that gives you agentic coding capabilities (decompose big tasks, execute shell commands, edit files, run tests) with **responsive steering** — you can see the plan, interrupt at any point, edit the direction, and control exactly how much autonomy the tool gets.

## The Problem

Existing tools force a tradeoff:
- **High bandwidth, loose steering** (Claude Code, Goose, OpenCode): Express big intents, tool figures it out. But when it goes off the rails, you're cleaning up the mess.
- **Low bandwidth, tight steering** (Aider, AIChat): You drive every step. Tight control, but you're doing all the thinking.

Neither is right. You want **both**: express a big intent, have it decompose and execute faithfully, and the moment you twitch the stick it responds instantly.

## Core Design

The plan is a **live, shared document** — not hidden state inside a context window.

```
1. User says intent ("make the sync resilient")
2. Tool decomposes into plan.md:
   - [ ] Read current sync scripts
   - [ ] Add retry logic to phone-media-sync.sh
   - [ ] Add heartbeat verification
   - [ ] Test each script
3. Plan is displayed. User can:
   - approve as-is
   - reorder / delete / add / edit steps
4. Tool executes step 1:
   - loads ONLY relevant files into context
   - does the work
   - shows diff before applying
   - user: approve / reject / edit
5. Each step = one git commit. Undo = revert.
6. User can interrupt and re-edit the plan at ANY point.
```

## Key Principles

- **The plan is a file, not hidden state.** Both human and tool read/write it. This is the steering wheel.
- **Each step gets its own small context.** A 32K model works fine — no 200K context crutch needed.
- **Approval granularity is adjustable.** Trust the tool? Auto-approve reads, pause on writes. Nervous? Approve every step. The *user* sets the autonomy level.
- **Interruption is first-class.** Ctrl-C pauses between steps, doesn't kill.
- **Git is the undo system.** Every step is a commit. Revert any step cleanly.
- **Model-agnostic.** Any OpenAI-compatible API: ollama local models, DeepSeek, Claude, GPT, whatever.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   User CLI  │────▶│  Orchestrator │────▶│  LLM API    │
│  (steering) │◀────│  (plan.md)    │◀────│  (any model) │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────┴───────┐
                    │  Executors    │
                    │  - file edit  │
                    │  - shell run  │
                    │  - git commit │
                    │  - test run   │
                    └──────────────┘
```

The orchestrator is the core — it manages the plan, dispatches steps to the LLM with focused context, applies results through executors, and keeps the human in the steering seat.

## Tech Stack

- **Language:** Python (fast to iterate, good subprocess/API support)
- **LLM interface:** OpenAI-compatible API (works with ollama, litellm, any provider)
- **VCS:** Git (for undo/history, one commit per step)
- **Plan format:** Markdown with checkboxes
- **Config:** YAML or TOML

## Values Alignment

This project follows [Values-Driven Systems Engineering](https://github.com/robbymeals/values-driven-systems-engineering). Every design decision traces to an explicit value:

- **Human agency over AI autonomy** → The plan is always visible and editable. The human steers.
- **Sufficiency over maximalism** → Works with small, cheap models. No 200K context required.
- **Transparency over magic** → Every step is shown before execution. No invisible actions.
- **Reversibility over correctness** → Git commits per step mean mistakes are cheap to undo.

## Status

Early design phase. See CLAUDE.md for development context.

## License

TBD
