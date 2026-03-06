# Values

## Why This Exists

LLM coding tools are chatbots with shell access. They assume the AI is a conversational partner — an intern you talk to. That's wrong. The AI is a tool. It should amplify human agency, not simulate its own.

Power users already have the right workflow: tmux for persistence, vim for editing, bash for execution, git for undo. But they're the glue connecting these tools to LLM calls. reeree extracts that workflow into a single tool where the human directs and the machines execute. Dispatch-first, but chat is there when you need it — freeform conversation is a valid mode, not a forbidden one.

**Audience:** Developers who already live in the terminal and want LLM capabilities without surrendering control to a chatbot.

**Stakes:** If we get this right, it's a text editor where machines work inside your document — plans are the prominent example, but any document works. If we get it wrong, it's another chatbot with a fancy TUI.

## Core Principles

### 1. Delegated Agency
**Principle:** The tool acts with the user's delegated authority. The user is always the principal — any autonomous action the tool takes is the user's agency being exercised, not the tool's own.
**Test question:** Can every action be traced to a user dispatch, approval, or standing delegation?
**In practice:** The user dispatches work, sets autonomy levels, and approves plans. Within that delegation, the tool can act autonomously — executing steps, making tactical decisions, routing to models. But the delegation is always explicit, the scope is always bounded, and the user can override anything at any time.
**Rules out:** Self-initiated goals, actions outside delegated scope, opaque decision-making, any framing where the tool "wants" or "decides" independently.
**Implementation:** [ADR-001](docs/strategic/decisions/ADR-001-unix-domain-socket.md) (daemon architecture), [ADR-007](docs/strategic/decisions/ADR-007-orchestrator-llm.md) (orchestrator routing within delegated scope), [ADR-009](docs/strategic/decisions/ADR-009-plugin-architecture.md) (plugins extend delegation scope, not override it).

### 2. Plan Is the Interface
**Principle:** Steering happens through visible, editable documents on disk — not through conversation. The plan is the prominent example, but any document is machine-addressable. Write `[machine: ...]` in an essay, a spec, a research brief, and daemons respond the same way they respond to plan steps.
**Test question:** Is all state visible to the user as editable text on disk?
**In practice:** The plan is a markdown file on disk. So is any other document you're working on. The user edits directly; daemons read the file, execute inline `[machine: ...]` annotations, and splice results back in. The document evolves. All state is visible. Nothing is hidden in a context window.
**Rules out:** Chat-first interfaces, hidden state, invisible "reasoning," context windows as the primary state store.
**Implementation:** [ADR-003](docs/strategic/decisions/ADR-003-plan-as-markdown.md) (markdown work queue), [ADR-008](docs/strategic/decisions/ADR-008-propagate-cohere.md) (coherence across the doc tree), [plan.py](reeree/plan.py) (plan parser), [machine_tasks.py](reeree/machine_tasks.py) (inline `[machine: ...]` annotation dispatch).

### 3. Overlap, Not Turn-Taking
**Principle:** User planning time and daemon execution time happen simultaneously.
**Test question:** Can the user edit step 5 while daemons execute step 2?
**In practice:** While daemons execute steps 2-3, the user is editing step 5, adding step 7, annotating step 4 with acceptance criteria. Nobody waits for anybody.
**Rules out:** Sequential turn-based interaction, blocking prompts, "press enter to continue" gates.
**Implementation:** Async daemon pool in [app.py](reeree/tui/app.py), parallel dispatch via `:go`/`:w`/`:W` commands, [ADR-010](docs/strategic/decisions/ADR-010-inter-daemon-communication.md) (daemons coordinate without blocking).

### 4. Persistence Without Fragility
**Principle:** Sessions survive terminal death. Work survives session death.
**Test question:** If the terminal dies right now, how much work is lost? (Answer should be: none.)
**In practice:** tmux-style daemon with attach/detach. Plan on disk. Git commits per step. Any crash point is recoverable.
**Rules out:** In-memory-only state, sessions that die with the terminal, work that can be lost.
**Implementation:** [ADR-001](docs/strategic/decisions/ADR-001-unix-domain-socket.md) (daemon), [ADR-005](docs/strategic/decisions/ADR-005-git-per-step-undo.md) (git-per-step).

### 5. Vim Is the Lingua Franca
**Principle:** The tool uses the keybindings and modal paradigm the user already knows.
**Test question:** Does the user's vim muscle memory work here without retraining?
**In practice:** Normal/insert/command modes. hjkl navigation. : commands. The user's muscle memory works here.
**Rules out:** Emacs bindings (someone else can add those), custom key schemes that need learning, mouse-required interactions.
**Implementation:** [ADR-002](docs/strategic/decisions/ADR-002-textual-tui.md) (Textual with vim modes), modal keybindings in [app.py](reeree/tui/app.py).

### 6. Sufficiency Over Maximalism
**Principle:** Works with small, cheap, local models. Doesn't require a $200/mo subscription.
**Test question:** Does this feature work with a 32K context, $0/month local model?
**In practice:** 32K context models work fine because each step gets focused context. ollama on localhost is the default. Cloud APIs are optional.
**Rules out:** Requiring specific commercial APIs, depending on 200K context windows, features that only work with frontier models.
**Implementation:** [ADR-004](docs/strategic/decisions/ADR-004-openai-compatible-api.md) (any LLM API), [ADR-006](docs/strategic/decisions/ADR-006-focused-context.md) (focused context for small models), [ADR-009](docs/strategic/decisions/ADR-009-plugin-architecture.md) (complexity is opt-in), [config.py](reeree/config.py).

### 7. No Anthropomorphism (Personality Is Fine)
**Principle:** The tool can have voice, style, and personality. It must not pretend to think, feel, have preferences, or be sentient. Personality ≠ anthropomorphism.
**Test question:** Does any text in the UI imply the tool thinks, feels, or wants?
**In practice:** The tool can have a distinctive style in how it reports status and surfaces information. "Routed to Qwen3-Coder for this step" is fine (reporting action). "I think Qwen3-Coder would be better for this" is not (implying cognition). The line is: describing what happened vs. implying internal experience.
**Rules out:** Implying cognition ("I think..."), simulating emotions ("I'm excited to..."), claiming preferences ("I'd suggest..."), pretending to have experiences. First person for action reporting is acceptable; first person for simulated inner life is not.
**Implementation:** Voice specification in [voice.py](reeree/voice.py) — STE-derived clear prose rules prepended to all daemon system prompts. See [ADR-014](docs/strategic/decisions/ADR-014-simplified-technical-english.md).

### 8. Look Before You Ask
**Principle:** Exhaust existing context before requesting new input from the user.
**Test question:** Could the daemon have found the answer by searching the project first?
**In practice:** Daemons search project files, config, history, linked documents, and prior outputs before surfacing a question. If the answer exists anywhere in the user's system, the daemon finds it — not bothers the user for it. Every question that reaches the user should be genuinely novel, not something a grep could have answered.
**Rules out:** Lazy escalation, defaulting to "ask the user," prompting for information already in the codebase, re-asking for things documented elsewhere.
**Implementation:** Context telescoping in [context.py](reeree/context.py), scope inheritance via `:cd`.

## Red Lines

What we will **never** build, regardless of convenience or demand:

1. **Agency is always delegated.** The tool acts within explicitly delegated scope — dispatched steps, approved plans, configured autonomy levels. It does not self-initiate goals or expand its own scope. The user is the principal; the tool is the agent in the legal sense, not the AI sense. Verification: can every action be traced to a user dispatch, approval, or standing delegation?

2. **No hidden state.** All tool state must be representable as files on disk that the user can read and edit with any text editor. Verification: can you `cat` every piece of state the tool holds?

3. **No telemetry or phone-home.** Zero network calls except to the configured LLM API. Verification: run with network blocked except LLM endpoint — does everything work?

4. **No lock-in.** Plans are markdown. Config is JSON. The tool adds value through orchestration, not proprietary formats. Verification: can you stop using reeree and still use every artifact it created?

5. **No anthropomorphism (personality is fine).** The tool can have voice and style. It must not imply cognition, simulate emotions, or pretend to have preferences or experiences. Action reporting in first person is acceptable ("routed step 3 to Qwen3-Coder"). Simulated inner life is not ("I think this approach is better"). Verification: no language in UI or output implies the tool thinks, feels, or wants.

## Data and Consent Model

- reeree processes your code locally
- It sends code snippets to whatever LLM API you configure (your choice, your key)
- No data leaves your machine except to your configured LLM endpoint
- No accounts, no registration, no tracking
- The plan file, config, and all state are plain text files you own

---

> **Core Planning Documents:** **Values** → [Implementation](IMPLEMENTATION.md) → [Plan](PROJECT_PLAN.md) → [Cost](COST.md) → [Revenue](REVENUE.md) → [Profit](PROFIT.md)
