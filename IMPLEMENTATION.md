# Implementation

## Value-to-Implementation Traceability

| Value | Implementation Decision | Rationale |
|-------|------------------------|-----------|
| Tool, Not Agent | Workers only execute dispatched steps, never self-initiate | Roombas don't decide to clean — you press the button |
| Tool, Not Agent | No chat interface — intents, commands, status only | Chat implies conversational partner; dispatch implies tool |
| Plan Is the Interface | Plan stored as markdown file, parsed/written by both user and workers | Visible, editable with any text editor, diffable in git |
| Plan Is the Interface | Step annotations (`> ` lines) carry specs inline | User writes acceptance criteria directly in the plan |
| Overlap, Not Turn-Taking | Async worker pool with parallel dispatch | Multiple roombas clean simultaneously |
| Overlap, Not Turn-Taking | Plan is editable while workers execute | User is always ahead, editing future steps |
| Persistence Without Fragility | Unix domain socket daemon/client architecture | Session survives terminal death, like tmux |
| Persistence Without Fragility | Git commit per completed step | Work survives everything — crash, reboot, mistake |
| Vim Is the Lingua Franca | Modal TUI with normal/insert/command modes | User's muscle memory works |
| Vim Is the Lingua Franca | `:` command mode for all operations | Vim users already know this paradigm |
| Sufficiency Over Maximalism | Each step gets focused context (~24K tokens) | 32K models work fine, no 200K crutch |
| Sufficiency Over Maximalism | Default API: localhost ollama | Free local inference is the default, not the fallback |

## Architecture Decisions

### ADR-001: Unix Domain Socket Daemon/Client
**Status:** Accepted
**Context:** Sessions must survive terminal death. tmux does this with a daemon.
**Decision:** reeree runs as a background daemon communicating with TUI clients via Unix domain socket at `~/.reeree/sock`.
**Values served:** Persistence Without Fragility
**Rationale:** Same proven pattern as tmux. No network exposure. Fast IPC.
**Alternatives considered:** (a) Run inside tmux — adds dependency, user must manage tmux sessions. (b) Screen-style — less capable. (c) TCP socket — unnecessary network exposure.
**Consequences:** Need a daemon lifecycle (start/stop/attach/detach). Socket cleanup on crash.
**Trade-offs acknowledged:** More complex than a simple CLI. Worth it for persistence.

### ADR-002: Textual for TUI Framework
**Status:** Accepted
**Context:** Need a multi-pane terminal UI with vim-style keybindings.
**Decision:** Use Textual (Python) for the TUI client.
**Values served:** Vim Is the Lingua Franca, Overlap Not Turn-Taking (parallel pane updates)
**Rationale:** Textual supports reactive widgets, CSS-like styling, async updates. Active development, good docs. Python matches the rest of the stack.
**Alternatives considered:** (a) curses — too low-level for multi-pane reactive UI. (b) blessed/urwid — less active, fewer features. (c) Go with bubbletea — would split the codebase language.
**Consequences:** Python TUI performance is adequate for this use case.

### ADR-003: Plan as Markdown Work Queue
**Status:** Accepted
**Context:** Need a shared data structure between user and workers that's human-readable and editable.
**Decision:** Plan is a markdown file with checkboxes and `> ` annotation lines.
**Values served:** Plan Is the Interface, No Hidden State, No Lock-in
**Rationale:** Markdown is universally readable. Checkboxes are universally understood. Annotations are just indented lines. No custom DSL to learn.
**Alternatives considered:** (a) JSON — not human-editable. (b) YAML — fragile indentation. (c) Custom format — violates No Lock-in.
**Consequences:** Parser must be tolerant of hand-edited markdown. Round-trip fidelity matters.

### ADR-004: OpenAI-Compatible API Interface
**Status:** Accepted
**Context:** Must work with any LLM provider, local or cloud.
**Decision:** All LLM calls go through OpenAI-compatible `/v1/chat/completions` endpoint.
**Values served:** Sufficiency Over Maximalism, No Lock-in
**Rationale:** ollama, litellm, vllm, and every cloud provider support this format. One interface covers everything.
**Alternatives considered:** (a) Native provider SDKs — each is different, creates lock-in. (b) LangChain — massive dependency, over-abstracted.
**Consequences:** Features that require provider-specific APIs (tool use, structured output) need adapter patterns or degraded gracefully.

### ADR-005: Git-Per-Step Undo System
**Status:** Accepted
**Context:** Mistakes must be cheap and reversible.
**Decision:** Each completed step creates a git commit. Undo = git revert.
**Values served:** Persistence Without Fragility, No Hidden State
**Rationale:** Git is already the user's VCS. No new system to learn. Full history preserved. Can revert any step independently.
**Alternatives considered:** (a) Custom undo stack — reinventing git poorly. (b) File snapshots — doesn't compose with user's existing git workflow.
**Consequences:** Requires the project to be a git repo. Creates potentially many small commits (can squash later).

### ADR-007: Orchestrator LLM (Meta-Layer)
**Status:** Proposed
**Context:** Different steps need different models. A complex refactor wants Claude Sonnet. A file rename wants a free local model. A vision task needs Gemini. The user shouldn't have to manually pick models per step.
**Decision:** An orchestrator (can be a cheap local model) classifies each step by task type and routes it to the best-fit executor model, with cost estimate. It also surfaces available external tools/services with signup links when a step would benefit from capabilities not in the current stack. The user approves or overrides the routing.
**Values served:** Sufficiency Over Maximalism (use the cheapest adequate model per step), Tool Not Agent (recommendations, not decisions)
**Rationale:** Cost-aware routing. The orchestrator classifies the task and routes to the cheapest adequate executor. $0.003 on a hard step, $0 on an easy one.
**Alternatives considered:** (a) Single model for everything — wasteful. (b) User picks model per step manually — tedious. (c) Hardcoded rules — too rigid.
**Consequences:** Needs a model registry with capabilities and pricing. Orchestrator prompt must be reliable about cost estimation.
**Timeline:** Post-POC. For now, single model for all steps.

### ADR-008: Propagate and Cohere Commands
**Status:** Proposed
**Context:** Documents reference each other. When one changes, linked docs may become incoherent.
**Decision:** Two commands: `:propagate` crawls links from the current doc and checks all referenced docs for coherence. `:cohere doc1 doc2 doc3` checks coherence across an explicit set. Both dispatch "coherence roombas" that read the docs, identify conflicts or stale references, and either flag or propose fixes.
**Values served:** Plan Is the Interface (the doc tree IS the system), Transparency (conflicts are surfaced, not hidden)
**Rationale:** This is the constraint cascade from VDSE applied to any doc tree. Edit VALUES.md, propagate checks IMPLEMENTATION.md. Edit a spec, cohere checks if the code matches.
**Implementation (POC):** Simple LLM calls — "here are two docs, find contradictions." Later: smart crawling, caching, incremental checks.
**Timeline:** Packaged reasoning calls for POC. Proper engineering in Phase 4-5.

### ADR-006: Focused Context Per Step
**Status:** Accepted
**Context:** Small models (32K context) should work well. Large context is a crutch.
**Decision:** Each worker gets only the files relevant to its specific step, not the whole repo.
**Values served:** Sufficiency Over Maximalism
**Rationale:** A step that edits `sync.sh` doesn't need `README.md`, `package.json`, and 40 other files. Focused context = better results from smaller models.
**Alternatives considered:** (a) Full repo context — requires 200K+ window, expensive, noisy. (b) RAG-based retrieval — adds complexity, not needed for focused steps.
**Consequences:** Planner must identify relevant files per step. Context builder must be smart about what to include.

## Technology Stack

| Component | Choice | Value Trace |
|-----------|--------|-------------|
| Language | Python 3.11+ | Fast iteration, good subprocess/async support |
| TUI | Textual | Multi-pane reactive UI, vim keybindings possible |
| LLM API | httpx → OpenAI-compatible endpoint | No Lock-in, Sufficiency |
| CLI entry | Click | Simple, well-documented |
| Git ops | GitPython + subprocess | Git-Per-Step undo |
| IPC | Unix domain socket (asyncio) | Persistence, tmux-style |
| Plan format | Markdown | No Lock-in, human-editable |
| Config | JSON | Simple, no dependencies |

## Data Architecture

All state lives on disk as plain text:

```
~/.reeree/                    # Global config + session management
├── config.json               # Default model, API, preferences
├── sock                      # Unix domain socket (runtime only)
└── sessions/
    └── <session-id>/
        ├── state.json        # Session state (workers, status)
        └── plan.md           # The plan file

<project>/.reeree/            # Per-project state
├── config.json               # Project-specific overrides
└── plan.md                   # Current plan (symlink or copy)
```
