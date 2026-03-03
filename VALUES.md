# Values

## Why This Exists

LLM coding tools are chatbots with shell access. They assume the AI is a conversational partner — an intern you talk to. That's wrong. The AI is a tool. It should amplify human agency, not simulate its own.

Power users already have the right workflow: tmux for persistence, vim for editing, bash for execution, git for undo. But they're the glue connecting these tools to LLM calls. reeree extracts that workflow into a single tool where the human directs and the machines execute.

**Audience:** Developers who already live in the terminal and want LLM capabilities without surrendering control to a chatbot.

**Stakes:** If we get this right, it's the first LLM coding tool designed around human agency instead of AI autonomy. If we get it wrong, it's another chatbot with a fancy TUI.

## Core Principles

### 1. Tool, Not Agent
**Principle:** The LLM amplifies user autonomy. It has none of its own.
**In practice:** The tool never initiates. It never suggests unless asked. It executes dispatched work and reports status. Like a roomba — it cleans where you point it.
**Rules out:** Proactive suggestions, "helpful" unsolicited actions, personality, opinions, conversation.

### 2. Plan Is the Interface
**Principle:** Steering happens through a visible, editable work queue — not through conversation.
**In practice:** The plan is a markdown file on disk. The user edits it directly. Workers read it. All state is visible. Nothing is hidden in a context window.
**Rules out:** Chat-first interfaces, hidden state, invisible "reasoning," context windows as the primary state store.

### 3. Overlap, Not Turn-Taking
**Principle:** User planning time and worker execution time happen simultaneously.
**In practice:** While workers execute steps 2-3, the user is editing step 5, adding step 7, annotating step 4 with acceptance criteria. Nobody waits for anybody.
**Rules out:** Sequential turn-based interaction, blocking prompts, "press enter to continue" gates.

### 4. Persistence Without Fragility
**Principle:** Sessions survive terminal death. Work survives session death.
**In practice:** tmux-style daemon with attach/detach. Plan on disk. Git commits per step. Any crash point is recoverable.
**Rules out:** In-memory-only state, sessions that die with the terminal, work that can be lost.

### 5. Vim Is the Lingua Franca
**Principle:** The tool uses the keybindings and modal paradigm the user already knows.
**In practice:** Normal/insert/command modes. hjkl navigation. : commands. The user's muscle memory works here.
**Rules out:** Emacs bindings (someone else can add those), custom key schemes that need learning, mouse-required interactions.

### 6. Sufficiency Over Maximalism
**Principle:** Works with small, cheap, local models. Doesn't require a $200/mo subscription.
**In practice:** 32K context models work fine because each step gets focused context. ollama on localhost is the default. Cloud APIs are optional.
**Rules out:** Requiring specific commercial APIs, depending on 200K context windows, features that only work with frontier models.

## Red Lines

What we will **never** build, regardless of convenience or demand:

1. **No autonomous agency.** The tool never takes actions the user didn't dispatch. No "I noticed X so I also did Y." Verification: did the user create or approve every step that executed?

2. **No hidden state.** All tool state must be representable as files on disk that the user can read and edit with any text editor. Verification: can you `cat` every piece of state the tool holds?

3. **No telemetry or phone-home.** Zero network calls except to the configured LLM API. Verification: run with network blocked except LLM endpoint — does everything work?

4. **No lock-in.** Plans are markdown. Config is JSON. The tool adds value through orchestration, not proprietary formats. Verification: can you stop using reeree and still use every artifact it created?

## Data and Consent Model

- reeree processes your code locally
- It sends code snippets to whatever LLM API you configure (your choice, your key)
- No data leaves your machine except to your configured LLM endpoint
- No accounts, no registration, no tracking
- The plan file, config, and all state are plain text files you own
