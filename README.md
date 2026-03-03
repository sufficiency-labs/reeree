# reeree

A dispatch console for LLM workers. Not a chatbot. Roombas, not interns.

## What is this?

A terminal-native tool for directing LLM workers at coding tasks. You dispatch intents, watch progress on a heads-up display, and steer with vim commands. The LLMs don't talk to you — they execute, report status, and flag when stuck.

Think less "AI pair programmer" and more "fleet of roombas you watch on a map."

## The Problem

Every LLM coding tool is a chatbot. You type, it types back, you have a conversation. That's wrong. You don't want to *talk* to your tools. You want to *direct* them.

The workflow that actually works is what power users already do by hand: tmux panes, vim editing, shell execution, git discipline, LLM calls when needed. reeree extracts that workflow into a single persistent tool.

## Design

### Dispatch, not chat

- Primary input is **intents** and **commands**, not messages
- The **plan** is the interface — a visible, editable list of steps
- LLM "thinking" is invisible unless you toggle a debug pane
- Steering is **spatial** (move/add/delete steps) not conversational ("actually could you also...")
- LLMs only surface text when genuinely blocked: `BLOCKED: can't find config.yaml — specify path?`

### Persistent sessions (tmux-style)

- `reeree` starts or reattaches a session
- Sessions survive terminal death — daemon stays running via Unix domain socket
- `reeree attach`, `reeree ls`, `reeree kill`
- Detach with keybinding, reconnect later, plan + state intact

### Multi-pane TUI

```
┌─── Plan ──────────────┬─── Worker 1 ──────────────┐
│                       │ STATUS: executing          │
│ [x] Read sync scripts │ > read scripts/sync.sh     │
│ [>] Add retry logic   │ > edit: +retry decorator   │
│ [>] Add heartbeat     │ > write scripts/sync.sh    │
│ [ ] Test              │ DIFF: +14 -3 lines         │
│                       ├─── Worker 2 ──────────────┤
│                       │ STATUS: executing          │
│                       │ > read scripts/heartbeat   │
│                       │ > write scripts/hb.sh      │
│                       │ DIFF: +28 lines (new)      │
├───────────────────────┴────────────────────────────┤
│ NORMAL  :add "add logging"  :pause 1  :go  :diff 2│
└────────────────────────────────────────────────────┘
```

### Vim keybindings

- **Normal mode**: navigate plan, dispatch commands
- **Insert mode**: type intents, add steps
- **Command mode (`:`)**: `:go`, `:pause N`, `:kill N`, `:diff N`, `:undo N`, `:plan`, `:add "step"`, `:set autonomy high`
- No emacs. Someone else can add that if they want.

### Plan-as-file

- The plan is a markdown file on disk, not hidden state
- You can edit it with vim in another pane if you want
- Workers read the plan, execute their step, update status
- You see everything. Nothing is invisible.

### Workers (roombas)

- Each step dispatches to a worker with **focused context** (only the files that step needs)
- Workers run against small context windows — 32K models work fine
- Independent steps run in **parallel** (multiple roombas)
- Each worker's status shows in its own pane
- Workers don't chat. They: read → execute → diff → commit → report status.

### Git is the undo system

- Every completed step = one git commit
- `:undo 3` reverts step 3
- `:undo` reverts the last step
- Mistakes are always cheap

## Architecture

```
┌──────────────────────────────────────────────┐
│                  reeree daemon                │
│          (Unix domain socket server)          │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Worker 1 │  │ Worker 2 │  │ Worker N │   │
│  │ (step 2) │  │ (step 3) │  │  (idle)  │   │
│  └────┬─────┘  └────┬─────┘  └──────────┘   │
│       │              │                        │
│  ┌────┴──────────────┴──────┐                │
│  │       Orchestrator        │                │
│  │  plan.md ←→ workers ←→ git│               │
│  └────────────┬─────────────┘                │
│               │                               │
│  ┌────────────┴─────────────┐                │
│  │     LLM API (any)        │                │
│  │  ollama / deepseek / etc  │               │
│  └──────────────────────────┘                │
└──────────────┬───────────────────────────────┘
               │ Unix domain socket
┌──────────────┴───────────────────────────────┐
│              reeree client (TUI)              │
│  Textual app — plan pane, worker panes, cmd  │
│  Vim keybindings — attach/detach             │
└──────────────────────────────────────────────┘
```

## Tech Stack

- **Language:** Python 3.11+
- **TUI:** Textual (terminal UI framework)
- **IPC:** Unix domain socket (tmux-style daemon/client)
- **LLM:** Any OpenAI-compatible API (ollama, litellm, cloud providers)
- **VCS:** Git (undo system, one commit per step)
- **Plan format:** Markdown checkboxes
- **Editor paradigm:** Vim modal (normal/insert/command)

## Commands

```
reeree                          # start or reattach session
reeree "intent goes here"       # start session with initial intent
reeree attach [session-name]    # attach to running session
reeree ls                       # list sessions
reeree kill [session-name]      # kill a session

# Inside TUI (command mode):
:go                             # dispatch pending steps
:pause [N]                      # pause worker N (or all)
:kill [N]                       # kill worker N
:add "step description"         # add step to plan
:del N                          # delete step N
:move N M                       # move step N to position M
:diff [N]                       # show full diff from step/worker N
:undo [N]                       # revert step N (git revert)
:set autonomy low|medium|high   # change approval level
:set model deepseek-v3          # change model
:log [N]                        # show full LLM interaction for worker N (debug)
:q                              # detach (session keeps running)
:q!                             # kill session and exit
```

## Values Alignment

This project follows [Values-Driven Systems Engineering](https://github.com/robbymeals/values-driven-systems-engineering).

- **Human agency over AI autonomy** → You dispatch. They execute. The plan is always yours.
- **Sufficiency over maximalism** → Works with small, cheap, local models. No $200/mo subscription.
- **Transparency over magic** → Status, diffs, and execution logs are always visible. Nothing hidden.
- **Reversibility over correctness** → Git-per-step means every mistake is one `:undo` away.
- **Tool, not agent** → This amplifies your autonomy. It doesn't have its own.

## Status

Early design / scaffolding. Core modules exist. TUI and daemon architecture in progress.

## License

TBD
