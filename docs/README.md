# reeree Documentation

## Values-Driven Systems Engineering

Every technical decision traces back to a stated value. Every value has concrete technical implementations. This creates accountability in both directions — values without implementations are aspirational; implementations without values are arbitrary.

```
VALUES → constrain → IMPLEMENTATION → inform → PLAN → bounded by → COST ← funded by ← REVENUE
   ↑                        ↑                      ↑                  ↑                    ↑
   └── "Should we?" ────────┴── "What exists?" ───┴── "What's next?" ┴── "Sustainable?" ──┴── "How?"
```

---

## The Core Documents

| Document | Purpose | Question |
|----------|---------|----------|
| [VALUES.md](../VALUES.md) | **Why we build** | Should we build this? |
| [IMPLEMENTATION.md](../IMPLEMENTATION.md) | **What we've decided** | What architecture exists? |
| [PROJECT_PLAN.md](../PROJECT_PLAN.md) | **What's next** | What are we building? |
| [COST.md](../COST.md) | **What it costs** | Is this sustainable? |
| [REVENUE.md](../REVENUE.md) | **How it sustains** | How does this keep running? |
| [PROFIT.md](../PROFIT.md) | **What success looks like** | What does "enough" mean? |

---

## Architecture Decisions (ADRs)

High-level decisions about *how* we build. Each ADR references the values it serves.

| ADR | Decision | Status | Values Served |
|-----|----------|--------|---------------|
| [ADR-001](strategic/decisions/ADR-001-unix-domain-socket.md) | Unix domain socket daemon/client | Accepted | Persistence Without Fragility |
| [ADR-002](strategic/decisions/ADR-002-textual-tui.md) | Textual for TUI framework | Accepted | Vim Is the Lingua Franca, Overlap Not Turn-Taking |
| [ADR-003](strategic/decisions/ADR-003-plan-as-markdown.md) | Plan as markdown work queue | Accepted | Plan Is the Interface, No Lock-in |
| [ADR-004](strategic/decisions/ADR-004-openai-compatible-api.md) | OpenAI-compatible API interface | Accepted | Sufficiency Over Maximalism, No Lock-in |
| [ADR-005](strategic/decisions/ADR-005-git-per-step-undo.md) | Git-per-step undo system | Accepted | Persistence Without Fragility |
| [ADR-006](strategic/decisions/ADR-006-focused-context.md) | Focused context per step | Accepted | Sufficiency Over Maximalism |
| [ADR-007](strategic/decisions/ADR-007-orchestrator-llm.md) | Orchestrator LLM (meta-layer) | Implemented | Sufficiency, Delegated Agency |
| [ADR-008](strategic/decisions/ADR-008-propagate-cohere.md) | Propagate and cohere commands | Implemented | Plan Is the Interface |
| [ADR-009](strategic/decisions/ADR-009-plugin-architecture.md) | Plugin architecture | Proposed | Sufficiency, Delegated Agency |
| [ADR-010](strategic/decisions/ADR-010-inter-daemon-communication.md) | Inter-daemon communication | Proposed | Overlap Not Turn-Taking, Plan Is the Interface |
| [ADR-011](strategic/decisions/ADR-011-subrepo-scope-as-lexical-binding.md) | Subrepo scope as lexical binding | Accepted | Focused Context, Plan Is the Interface |
| [ADR-012](strategic/decisions/ADR-012-daemon-personality-evolution.md) | Daemon personality evolution | Proposed | Delegated Agency, No Anthropomorphism |
| [ADR-013](strategic/decisions/ADR-013-pluggable-execution-backends.md) | Pluggable execution backends | Proposed | Sufficiency, No Lock-in |
| [ADR-014](strategic/decisions/ADR-014-simplified-technical-english.md) | Clear Technical English voice spec | Proposed | No Anthropomorphism, Sufficiency |

---

## Document Hierarchy

```
docs/
├── README.md                          # This file — navigation hub
│
├── strategic/decisions/               # Architecture decisions (ADRs)
│   ├── ADR-001-unix-domain-socket.md
│   ├── ADR-002-textual-tui.md
│   ├── ADR-003-plan-as-markdown.md
│   ├── ADR-004-openai-compatible-api.md
│   ├── ADR-005-git-per-step-undo.md
│   ├── ADR-006-focused-context.md
│   ├── ADR-007-orchestrator-llm.md
│   ├── ADR-008-propagate-cohere.md
│   ├── ADR-009-plugin-architecture.md
│   ├── ADR-010-inter-daemon-communication.md
│   ├── ADR-011-subrepo-scope-as-lexical-binding.md
│   ├── ADR-012-daemon-personality-evolution.md
│   ├── ADR-013-pluggable-execution-backends.md
│   └── ADR-014-simplified-technical-english.md
│
├── keyboard-shortcuts.md              # Complete keybinding reference
├── claude-code-gap-analysis.md        # Usage pattern analysis
└── GASTOWN_COMPARISON.md              # Comparative analysis
```

---

## When Proposing a Feature

```
1. DOES IT SERVE A VALUE?
   └── Check VALUES.md — if no value supports it, question whether to build it

2. DOES IT CONFLICT WITH RED LINES?
   └── Check VALUES.md §Red Lines — hard stops we never cross

3. HOW DOES IT FIT EXISTING DECISIONS?
   └── Check IMPLEMENTATION.md — does it align with architectural clusters?
   └── Check relevant ADRs in docs/strategic/decisions/

4. WHERE DOES IT GO IN THE PLAN?
   └── Check PROJECT_PLAN.md — what phase, what dependencies?

5. WHAT DOES IT COST?
   └── Check COST.md — is this sustainable at $0-15/month?
```

---

## Navigation

| If you're asking... | Start here |
|---------------------|------------|
| "Should we build this?" | [VALUES.md](../VALUES.md) — find which value it serves |
| "What have we decided?" | [IMPLEMENTATION.md](../IMPLEMENTATION.md) — current state |
| "Why did we choose X?" | [docs/strategic/decisions/](strategic/decisions/) — ADRs |
| "What's next?" | [PROJECT_PLAN.md](../PROJECT_PLAN.md) — roadmap |
| "Can we afford this?" | [COST.md](../COST.md) — sustainability check |
| "How does reeree compare?" | [GASTOWN_COMPARISON.md](GASTOWN_COMPARISON.md) — vs Gastown |
| "What are the keybindings?" | [keyboard-shortcuts.md](keyboard-shortcuts.md) — complete reference |

---

> **Core Planning Documents:** [Values](../VALUES.md) → [Implementation](../IMPLEMENTATION.md) → [Plan](../PROJECT_PLAN.md) → [Cost](../COST.md) → [Revenue](../REVENUE.md) → [Profit](../PROFIT.md)
