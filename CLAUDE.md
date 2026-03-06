# CLAUDE.md — reeree Development Context

## What is reeree?

A text editor where machines work inside your document. Any document — markdown, YAML, a plan, a checklist, a spec, a research brief — can be machine-addressable. You write `[machine: ...]` annotations inline, save, and daemons do the work, splicing results back into the document. The plan/checklist is the prominent example, but the architecture is document-general. Terminal-native, vim keybindings, parallel daemons, model-agnostic.

Not a chatbot. Not an IDE. Not just a dispatch console.

## Default Voice: Ship's Computer

All daemon output defaults to ship's-computer tone — direct, informational, competent. Personality is fine but it's not performative personhood.

- Report what was done, not what you're "going to" do
- No "I think", "I'll try", "Let me", "Great choice!"
- Conversational language is good (natural language > machine codes). Anthropomorphized language is bad.
- Log output: informational and summarized. One line per action, not paragraphs.
- Chat responses: natural language expressing constraints and results. Not a chatbot performing helpfulness.

## Architecture

```
reeree/
├── cli.py             # Entry point — Click CLI
├── claude_backend.py  # Claude Code subprocess backend (--resume persistence)
├── config.py          # Configuration — backend, models, routing
├── context.py         # Focused context assembly per step
├── daemon_executor.py # Together.ai/OpenAI multi-turn LLM conversation
├── daemon_registry.py # Daemon lifecycle — DaemonRegistry, DaemonKind, DaemonStatus
├── executor.py        # File edits, shell commands, git ops, safety classification
├── llm.py             # LLM API — OpenAI-compatible httpx calls
├── machine_tasks.py   # [machine: ...] annotation parser + dispatcher
├── plan.py            # Plan/Step data model + YAML serialization
├── planner.py         # Intent → step list decomposition
├── voice.py           # Voice specification (STE-derived clear prose rules)
├── plugin.py          # Plugin base class + entry point discovery
├── message_bus.py     # Inter-daemon communication (DaemonMessage, MessageBus)
├── router.py          # Model routing — reasoning/coding/fast tiers
├── session.py         # Session state serialization (Plan + Registry → JSON)
└── tui/
    ├── app.py         # Main Textual application (vim modal, all commands)
    ├── daemon_tree.py # Hierarchical daemon display widget
    └── setup_screen.py # First-run setup wizard
```

## .reeree/ Directory

Each project has a `.reeree/` directory (auto-created on first run or `reeree init`):

- **`config.json`** — committed. Project settings (model, API base, routing, `default_doc`).
- **`plan.yaml`** — committed. Shared execution queue (steps, annotations).
- **`.gitignore`** — committed. Ignores `session.json`, `session.log`, `local/`.
- **`session.json`** — gitignored. Per-session daemon state.
- **`session.log`** — gitignored. Per-session event log.
- **`local/`** — gitignored. Per-user scratch space (e.g. `local/plan.yaml`).

### Default Document Discovery

When invoked with no arguments, `cli.py` discovers the default document:

1. `config.default_doc` (if set in `.reeree/config.json`)
2. `PROJECT_PLAN.md`
3. `PLAN.md`
4. `README.md`

The discovered doc opens in the file viewer. `.reeree/plan.yaml` always loads as the execution queue regardless of which document is active. Explicit targets (`reeree essay.md`) override discovery.

## Backends

Two execution backends, switchable via `config.backend` or `:set backend`:

### Together.ai / OpenAI-compatible (`backend: "together"`)
Default. Uses `llm.py` + `daemon_executor.py`. The daemon calls an OpenAI-compatible API, gets YAML action responses, and executes them locally via `executor.py`. Multi-turn loop: LLM → parse YAML → execute actions → feed results back.

### Claude Code subprocess (`backend: "claude-code"`)
Each daemon is a persistent Claude Code session. Spawns `claude -p` with `--output-format json`. Claude Code handles file operations, shell commands, and search natively — no YAML action parsing needed. Sessions persist via `--resume <session_id>`, stored on `Daemon.session_id`.

Config fields: `backend` ("together" | "claude-code"), `claude_model` ("sonnet" | "opus" | "haiku").

Runtime: `:set backend claude-code`, `:set claude-model opus`.

## Key Patterns

### Machine Tasks
`[machine: ...]` annotations in any document. On `:w`, `machine_tasks.py` finds them, dispatches daemons, and splices results back into the document. The annotation disappears, replaced by the daemon's output. Works in any markdown or YAML file — plans, specs, essays, research briefs.

### StatusOverlay
The daemon updates the buffer with status while work is in progress. Changes merge cleanly on edit mode exit so the user never loses keystrokes.

### Step IDs
Stable identifiers (e.g. `add-a1b2`) that survive reordering. Steps can be moved, inserted, or deleted without breaking references.

### Three Modes
- **VIEW** (default): rich display, read-only, status overlays visible
- **EDIT**: YAML source, full vim keybindings, `:edit` to enter
- **INSERT**: typing within edit mode, `i`/`a`/`o` to enter from EDIT

### DaemonRegistry (not _daemons dict)
`app.py` uses `self._daemon_registry` (a `DaemonRegistry` instance). The old `self._daemons` dict pattern is gone. All daemon lifecycle goes through the registry.

### YAML Protocol
Daemon-LLM communication uses YAML. The daemon executor sends structured prompts, the LLM responds with `actions:` + `status:` + `summary:` YAML. No JSON schemas, no chat-style prompting.

### Model Routing
`router.py` classifies tasks into tiers (reasoning/coding/fast) and routes to the best available model. Daemon kind overrides exist (COHERENCE → reasoning, WATCHER → fast).

### Plugin Hooks
`plugin.py` defines lifecycle hooks: `on_plan_loaded`, `on_step_dispatched`, `on_step_completed`, `on_daemon_message`. Plugins register via `pyproject.toml` entry points.

### Message Bus
`message_bus.py` provides typed inter-daemon communication. Messages print to the TUI log unless silenced. CONFLICT messages are never silenced.

## Development

```bash
# Activate venv
source /mnt/vorkosigan_data_v2/vorkosigan/.venv/bin/activate
cd /mnt/vorkosigan_data_v2/vorkosigan/private/reeree

# Run tests
python -m pytest tests/ -v

# Run unit tests only (no API calls)
python -m pytest tests/ -v -k "not (test_basic_response or test_json_response or test_system_prompt or test_edit_step or test_write_step or test_logging_callback)"

# Launch TUI
reeree --project sandbox "add error handling to the scraper"
# Inside the TUI: :edit to edit the plan, :go to dispatch, :w to save + run machine tasks
```

## Conventions

- **~3-5K lines total.** Not a framework. If it's getting bigger, something is wrong.
- **YAML is the canonical plan format.** Plan files save as YAML on disk. Daemon communication uses YAML. Display is markdown-like but storage is YAML. No JSON schemas, no custom DSLs.
- **Commit early, commit often.** One logical change per commit.
- **Tests document behavior.** 396 passing, 19 xfailed (planned features).
- **Values trace to code.** Every ADR has a "Values served" field. See [docs/strategic/decisions/](docs/strategic/decisions/).
- **Voice spec in voice.py.** All daemon system prompts import `VOICE` from `voice.py` (STE-derived clear prose rules). See [ADR-014](docs/strategic/decisions/ADR-014-simplified-technical-english.md).

## Test Droplet

```bash
ssh rob@138.197.23.221
# Ubuntu 24.04, 2vCPU/2GB, NYC3
```

## VDSE Docs

| Doc | What it is |
|-----|-----------|
| [VALUES.md](VALUES.md) | Why we build — 8 principles + red lines |
| [IMPLEMENTATION.md](IMPLEMENTATION.md) | What's been decided — ADR index + current state |
| [PROJECT_PLAN.md](PROJECT_PLAN.md) | What's next — 8-phase roadmap |
| [docs/](docs/README.md) | Navigation hub + standalone ADRs |
| [COST.md](COST.md) | What it costs |
| [REVENUE.md](REVENUE.md) | How it sustains |
| [PROFIT.md](PROFIT.md) | What success looks like |
