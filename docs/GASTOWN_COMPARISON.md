# reeree vs Gastown: Comparison Analysis

Gastown (Steve Yegge, [github.com/steveyegge/gastown](https://github.com/steveyegge/gastown)) is a multi-agent orchestration system for Claude Code. reeree is a terminal-native LLM dispatch console. Both reject the chatbot paradigm. Both dispatch work to AI agents. The similarities end there.

## Scale

| Metric | Gastown | reeree |
|--------|---------|--------|
| Language | Go 1.25 | Python 3.11+ |
| Source (non-test) | ~194,670 lines | ~3,657 lines |
| Source files | 533 | 15 |
| Internal packages | 70+ | 2 |
| Test lines | 152,719 | 3,051 |
| Dependencies | Go, Dolt, Beads, tmux, Claude Code CLI | httpx, textual, click |
| Install | `gt install` + Dolt + tmux + town setup | `pip install -e .` |

Gastown is **53x larger** by code volume.

## Philosophy

### Gastown: The Industrial Town

The metaphor is civic infrastructure. A **Mayor** coordinates, a **Deacon** keeps the peace, **Polecats** are shift workers, **Crew** are long-term employees, **Dogs** are maintenance staff, and the **Refinery** handles quality control.

The core axiom is the **Propulsion Principle (GUPP)**: "If you find something on your hook, YOU RUN IT." The docs describe Gastown as "a steam engine. Agents are pistons."

This is an **enterprise-first** mental model. The primary questions are accountability questions: "Which agent introduced this bug? Which agents are reliable? Which agent should handle this Go refactor?" Attribution, audit trails, compliance. The docs reference SOX and GDPR.

### reeree: The Living Document

The metaphor is document editing. You edit a markdown file. Daemons respond to what you write.

The core axiom is **overlap, not turn-taking**: "You edit ahead. Daemons execute behind. Nobody waits."

This is a **power-user-first** mental model. The primary question is: "How do I direct multiple LLM processes from a document without waiting for each one?"

### Honest Assessment

Gastown's metaphor is richer but heavier. Seven named agent types (Mayor, Deacon, Witness, Refinery, Polecat, Crew, Dog) require significant learning investment. There are real semantic distinctions — "Dogs are NOT workers" is called out as a "common misconception." This complexity serves enterprise multi-user scenarios but is overkill for a single-user tool.

reeree's metaphor is simpler and more direct but less expressive. "You edit a document, daemons respond" is immediately graspable but has fewer abstractions for multi-agent coordination.

## Agent Model

### How Agents Get Work

**Gastown**: Pull + push hybrid. `gt sling` places a bead on an agent's "hook." Patrol agents poll continuously. A `DispatchCycle` manages capacity, batch limits, inter-spawn delays, and retry semantics.

**reeree**: Dispatch-only. `:go`, `:w`, `:W` trigger dispatch. No polling. No autonomous work pickup.

### Agent Lifecycle

**Gastown**: Three-layer persistent identity:
- **Identity** (permanent): work history, CV chain. Never dies.
- **Sandbox** (persistent): git worktree, branch. Reused across tasks.
- **Session** (ephemeral): Claude instance. Cycles per step/handoff.

The Witness monitors for stuck/zombie states and triggers recovery.

**reeree**: Simple task lifecycle. Daemons are asyncio tasks that run until done, failed, or killed. No identity persistence. No sandbox management. No crash recovery beyond restarting the TUI.

### Multi-Agent Coordination

**Gastown**: Full coordination stack — inter-agent mail (`gt mail`), cross-rig dispatch, convoys for batched work, merge queue (Refinery) for safe parallel merging, `gt seance` for querying previous sessions.

**reeree**: Multiple daemons run simultaneously (parent/child hierarchy) but share a single plan file and don't communicate.

## Work Tracking

**Gastown**: Structured data in Dolt (MySQL-compatible, git-versioned SQL database). Beads compose into Molecules (durable state machines defined in TOML Formulas). All agents write to the same database.

**reeree**: A markdown checklist in a file. The `Step` dataclass has: description, status, annotations, files, commit_hash, daemon_id. The plan file is simultaneously the spec, status display, steering wheel, history, and context system. Human-readable, human-editable, visible during execution.

## What Gastown Has That reeree Doesn't

1. **Agent identity and attribution** — every commit traced to a specific named agent
2. **Agent CVs and capability tracking** — success rates, skills, task history
3. **Multi-project orchestration** — multiple rigs under one town with cross-rig issue tracking
4. **Merge queue** — Bors-style batch-then-bisect safe parallel merging
5. **Agent supervision and recovery** — Witness → Deacon → Boot watchdog chain
6. **Inter-agent communication** — mail, nudge, escalate, seance
7. **Remote operations** — manage rigs on remote machines via SSH
8. **Durable workflow state** — Molecules survive agent restarts and crashes
9. **Multi-runtime support** — Claude Code, Codex, Gemini, Cursor, custom agents
10. **Telemetry** — OpenTelemetry integration for observability

## What reeree Has That Gastown Doesn't

1. **Document-as-interface** — the plan IS the UI, editable while daemons execute
2. **Inline steering** — annotations become daemon context and acceptance criteria
3. **Multi-turn daemon loop** — read → edit → verify loop with persistent conversation
4. **Execution safety guardrails** — command classification (blocked/dangerous/safe) + autonomy levels
5. **Multi-model routing** — classify tasks into tiers, route to different models per step
6. **Git-per-step undo** — every step is a commit, `:undo` reverts it
7. **Subrepo context telescoping** — automatic parent repo context in submodules
8. **Zero infrastructure** — no Dolt, no tmux management, no daemon processes

## What They Share

- Markdown as lingua franca
- Git as commit/undo substrate
- tmux-style session persistence (aspiration in reeree)
- Vim-like interaction model
- Dispatch over chat — both reject the chatbot paradigm
- Concern about agent reliability — watchdog chains vs safety guardrails
- Focused context loading — role-specific injection vs step-specific gathering

## Strategic Takeaways

### Learn from (but don't copy)

**Branch-per-daemon.** When `:W` dispatches multiple daemons, each should work on its own branch. A lightweight merge step prevents conflicts. This is a simplified version of Gastown's Refinery. reeree's most glaring architectural gap.

**Daemon heartbeat monitoring.** A timer checking whether each daemon has produced output recently. Mark stalled daemons in the tree view. No watchdog chain needed — just a check.

**Work attribution in commits.** Include daemon ID and model in commit messages (`reeree(d3/qwen3-coder): {step}`). Basic auditability without a database.

**Durable daemon state.** Serialize conversation state to disk. If the TUI dies mid-execution, recovery becomes possible.

### Don't adopt

**The role taxonomy.** Seven named agent types is enterprise complexity. reeree's four daemon types (executor, coherence, watcher, state) are sufficient for single-user use.

**Dolt.** A SQL database is right for multi-user, multi-project, federated work tracking. Wrong for a single user editing a markdown file. The plan-as-file model is a genuine strength — the user can see and edit everything. A database hides state.

**The 194,000-line complexity budget.** reeree's README says "Target ~3-5K lines total, not a framework." Gastown's complexity reflects different goals. Holding to discipline is more valuable than feature parity.

### The Core Insight

Gastown asks: "How do I manage 50 AI agents across 10 projects with accountability?"
reeree asks: "How do I direct LLM processes from a markdown document without waiting?"

Both are valid. The danger for reeree is looking at Gastown's feature list and feeling behind. Gastown's complexity is its moat AND its liability. reeree's simplicity is its moat — don't trade it away.

---

Sources:
- [steveyegge/gastown](https://github.com/steveyegge/gastown)
- [Welcome to Gas Town (Medium)](https://steve-yegge.medium.com/welcome-to-gas-town-4f25ee16dd04)
- [A Day in Gas Town (DoltHub Blog)](https://www.dolthub.com/blog/2026-01-15-a-day-in-gas-town/)
