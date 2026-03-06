# reeree

A text editor where machines work inside your document.

You write markdown. You drop in machine task annotations. You save. Daemons execute the tasks. Results appear in your document. The log shows what's happening. You can chat with a daemon if you need to.

Terminal-native. Vim keybindings. Persistent sessions. Model-agnostic.

## What is this?

You're editing a document. Some parts of it are machine-addressable — task annotations, plan steps, inline instructions. When you save, the tool processes the document: finds machine work, dispatches daemons, splices results back in. The log on the right shows what's happening.

The document can be anything. A plan. An essay. A spec. A research brief. Slides. Any human-readable format that can be represented in markdown or YAML.

When you run `reeree` with no arguments, it discovers your project's default document: `PROJECT_PLAN.md` first, then `PLAN.md`, then `README.md`. The `.reeree/plan.yaml` execution queue loads in the background regardless. Override with `"default_doc"` in `.reeree/config.json`.

Not a chatbot. Not an IDE. A text editor with daemons.

## Two kinds of documents

### Plans (YAML) — structured work queues

The default document. You write steps, annotate them with specs, daemons pick them up and execute.

```yaml
intent: make sync resilient
steps:
  - id: rea-a1b2
    description: Read current sync scripts
    status: done
    commit: a3f2c01
  - id: add-c3d4
    description: Add retry logic to sync.sh
    status: active
    annotations:
      - "max 3 retries, exponential backoff"
      - "done: scripts/test-retry.sh passes"
  - id: add-e5f6
    description: Add heartbeat check
    status: pending
    files: [scripts/heartbeat.sh, scripts/watchdog.sh]
```

Commands: `i` to edit, `:w` to save, `:go` to dispatch steps to daemons.

### Markdown — everything else

Any markdown file. Write prose, drop in machine tasks, save, results appear.

```markdown
# Climate Adaptation in Coastal Cities

Rising sea levels threaten infrastructure worldwide.
The most vulnerable cities include [machine: research and list
the 5 most at-risk coastal cities with population and elevation].

The common thread across these cases is
[machine: analyze the pattern across the above list and write
a one-paragraph synthesis of shared vulnerabilities].
```

Type `:w`. The `[machine: ...]` annotations dispatch daemons. While running, they show `[⏳ ...]`. When done, the results replace the annotations in-place. The document evolves.

## The interface

Three panes. Document on the left. Log on the right. Chat at the bottom when you want it.

```
┌──────────────────────────┬──────────────────────┐
│                          │ daemon 1 log         │
│   Your document          │ > read sync.sh       │
│   (always here,          │ > edit: +@retry      │
│    always editable)      │ > shell: pytest      │
│                          │   PASS (3 tests)     │
│                          │ > git commit a3f2c01 │
│                          │ STATUS: done         │
│                          │                      │
├──────────────────────────┴──────────────────────┤
│ NORMAL  i=insert  :go=dispatch      2 daemons   │
└─────────────────────────────────────────────────┘
```

## Vim modes

Two modes, like vim:

| Mode | What it is | Status bar |
|------|-----------|-----------|
| **NORMAL** | YAML source, read-only. hjkl nav. `i`/`a`/`o` to insert. Default. | green |
| **INSERT** | YAML source, editable. Escape returns to NORMAL. | yellow |
| **COMMAND** | `:` commands (from NORMAL via `:`). | cyan |

Opens in NORMAL mode. `i` enters INSERT immediately — no `:edit` gate. `:w` saves the plan. `:q` quits.

## Commands

```
# Editing
:w                          save document
:q                          quit

# Dispatch
:go                         dispatch next 2 pending steps
:go all / :W                dispatch ALL pending steps
:go N                       dispatch step N

# Steps
:add "description"          add a step to the plan
:del N                      delete step N
:move N M                   move step N to position M

# Views
:file path                  open a project file (vim editing, machine tasks)
:diff [N]                   show diff for step N
:log [N]                    show daemon N's log

# Communication
:chat                       toggle chat panel (talk to executor daemon)
:chat coherence             chat with coherence daemon

# Daemon control
:pause N / :resume N        pause/resume daemon
:kill N                     kill daemon and children

# Configuration
:set model <name>           change LLM model (together backend)
:set backend <name>         together|claude-code
:set claude-model <name>    sonnet|opus|haiku (claude-code backend)
:set autonomy <level>       low|medium|high|full
:setup                      re-run setup wizard

# Analysis
:cohere [path|glob]         run coherence check
:propagate                  crawl cross-references

# Session
:undo                       git revert last step
:q / :q! / :wq              quit / force quit / save+quit
:help                       command reference
```

## Machine tasks

Any document can contain inline machine task annotations:

```
[machine: description of what to do]
```

On `:w`, the tool finds these annotations, dispatches daemons, and splices results back into the document. The annotation disappears. The result takes its place.

This works in any markdown file opened with `:file`. The plan is one kind of machine-addressable document. An essay is another. Same tool, same capabilities.

## Key properties

**The document is alive.** Plan checkboxes update as daemons complete steps. Machine task results appear inline. The document evolves.

**Any document works.** Plans, essays, specs, research briefs — anything in markdown or YAML. Machine tasks work everywhere.

**Chat when you need it.** `:chat` opens a conversation with the executor daemon. It's there for when you need to talk through something. But dispatch is the primary interface — you write, the tool executes.

**Cross-references are context.** Link to another markdown doc and the daemon reads it. Your existing docs, specs, READMEs — they're all feedable context.

**Sessions persist.** tmux-style daemon. Kill your terminal, reconnect later, document and daemons are right where you left them.

**Git is undo.** Every completed step is a git commit. `:undo` reverts. Mistakes cost nothing.

**Two backends.** Together.ai/OpenAI-compatible API for open models (DeepSeek, Qwen, Llama). Or Claude Code as persistent subprocesses — each daemon is a full Claude session with `--resume` for context persistence. `:set backend claude-code` to switch.

**Vim keybindings.** Your muscle memory works.

## Design Philosophy

- **Document is the interface.** Any document can be machine-addressable. The plan is a prominent example, not the only one.
- **Dispatch, not just chat.** You write intents and annotations. Daemons execute. Chat exists for when you need it, but writing is the primary interface.
- **Delegated agency.** The tool acts with your authority, not its own. You dispatch, it executes within scope.
- **Overlap, not turn-taking.** You edit ahead. Daemons execute behind. Nobody waits.
- **Persistence.** Sessions survive terminal death. Work survives everything (git).
- **Sufficiency.** $0 with local models. 32K context works fine.
- **Personality, not anthropomorphism.** The tool has a voice. It doesn't pretend to think or feel.

See [VALUES.md](VALUES.md) for the full values statement and [IMPLEMENTATION.md](IMPLEMENTATION.md) for how values trace to code decisions.

## Architecture

```
reeree/
├── cli.py              # Entry point
├── config.py           # Configuration
├── context.py          # Focused context per step
├── claude_backend.py   # Claude Code subprocess backend (--resume persistence)
├── daemon_executor.py  # Together.ai/OpenAI multi-turn step execution
├── daemon_registry.py  # Daemon lifecycle (hierarchy, pause/kill)
├── executor.py         # File edits, shell, git, safety
├── llm.py              # LLM API (OpenAI-compatible)
├── machine_tasks.py    # Inline [machine: ...] annotation parser
├── message_bus.py      # Inter-daemon communication
├── plan.py             # Plan/Step data model + YAML serialization
├── planner.py          # Intent → step list decomposition
├── voice.py            # Voice specification
├── plugin.py           # Plugin base class
├── router.py           # Model routing (reasoning/coding/fast)
├── session.py          # Session state serialization
└── tui/
    ├── app.py          # Main application (vim modal, commands)
    ├── daemon_tree.py  # Daemon display widget
    └── setup_screen.py # Setup wizard
```

## .reeree/ directory

Each project gets a `.reeree/` directory (auto-created on first run, or `reeree init`):

```
.reeree/
├── config.json     # Committed — project settings (model, API, routing)
├── plan.yaml       # Committed — shared work queue (current steps)
├── .gitignore      # Committed — ignores ephemeral files below
├── session.json    # Gitignored — per-session daemon state
├── session.log     # Gitignored — per-session event log
└── local/          # Gitignored — per-user scratch
    └── plan.yaml   # Per-user local plan (not shared)
```

`PROJECT_PLAN.md` is the strategic abstraction (phases, deliverables, values). `.reeree/plan.yaml` is the tactical execution queue (steps, annotations, daemon dispatch). Two views of the same work — one for humans reading the project, one for machines executing it.

## Development

```bash
source /mnt/vorkosigan_data_v2/vorkosigan/.venv/bin/activate
cd /mnt/vorkosigan_data_v2/vorkosigan/private/reeree
pip install -e .

# Run tests (423 passing, 19 xfailed)
python -m pytest tests/ -v

# Launch TUI
reeree --project sandbox "add error handling to the scraper"

# Inside TUI: NORMAL mode by default
#   i         → insert mode (edit YAML)
#   :go       → dispatch daemons
#   :chat     → talk to executor
#   :help     → command reference
```

## Status

Active development. 408 tests passing. Core dispatch loop, multi-turn daemons, daemon hierarchy, model routing, inline machine tasks, Claude Code subprocess backend, setup wizard, and TUI all working. See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the roadmap.

---

> **Core Planning Documents:**
> - [VALUES.md](VALUES.md) — Why we build this way
> - [IMPLEMENTATION.md](IMPLEMENTATION.md) — How values trace to code decisions
> - [PROJECT_PLAN.md](PROJECT_PLAN.md) — What's next (8-phase roadmap)
> - [COST.md](COST.md) — What it costs ($0 local, $5-15 cloud)
> - [REVENUE.md](REVENUE.md) — How it might sustain itself
> - [PROFIT.md](PROFIT.md) — What success looks like

## License

[Anti-Fascist MIT License](LICENSE)
