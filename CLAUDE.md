# CLAUDE.md — reeree Development Context

## What is reeree?

An LLM-assisted systems engineering tool. You edit a markdown document. Daemons respond to what you write. Terminal-native, vim keybindings, plan-as-file steering, parallel daemons, model-agnostic.

Not a chatbot. Not an IDE. A dispatch console.

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
├── config.py          # Configuration — single model + multi-model routing
├── context.py         # Focused context assembly per step
├── daemon_executor.py # Multi-turn LLM conversation (read→edit→verify loop)
├── daemon_registry.py # Daemon lifecycle — DaemonRegistry, DaemonKind, DaemonStatus
├── executor.py        # File edits, shell commands, git ops, safety classification
├── llm.py             # LLM API — OpenAI-compatible httpx calls
├── plan.py            # Plan/Step data model + markdown serialization
├── planner.py         # Intent → step list decomposition
├── plugin.py          # Plugin base class + entry point discovery
├── message_bus.py     # Inter-daemon communication (DaemonMessage, MessageBus)
├── router.py          # Model routing — reasoning/coding/fast tiers
├── session.py         # Session state serialization (Plan + Registry → JSON)
└── tui/
    ├── app.py         # Main Textual application (vim modal, all commands)
    ├── daemon_tree.py # Hierarchical daemon display widget
    └── setup_screen.py # First-run setup wizard
```

## Key Patterns

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
```

## Conventions

- **~3-5K lines total.** Not a framework. If it's getting bigger, something is wrong.
- **Markdown and YAML are the lingfranks.** Plan files are markdown. Daemon communication uses YAML. No JSON schemas, no custom DSLs.
- **Commit early, commit often.** One logical change per commit.
- **Tests document behavior.** 230+ passing, 19 xfailed (planned features).
- **Values trace to code.** Every ADR has a "Values served" field. See [docs/strategic/decisions/](docs/strategic/decisions/).

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
