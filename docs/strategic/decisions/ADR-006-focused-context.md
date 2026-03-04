# ADR-006: Focused Context Per Step

**Status:** Accepted
**Date:** 2026-02-15

## Context

Small models (32K context) should work well. Large context windows are a crutch that encourages dumping everything into the prompt instead of thinking about what's relevant.

## Decision

Each daemon gets only the files relevant to its specific step, not the whole repo. Context is assembled per-step based on file hints, annotations, and project structure.

## Values Served

- **[Sufficiency Over Maximalism](../../VALUES.md#6-sufficiency-over-maximalism)** — 32K models work fine with focused context. No 200K crutch needed.

## Rationale

A step that edits `sync.sh` doesn't need `README.md`, `package.json`, and 40 other files. Focused context = better results from smaller models. Less noise means more signal.

## Alternatives Considered

| Option | Verdict | Why |
|--------|---------|-----|
| Full repo context | Rejected | Requires 200K+ window, expensive, noisy |
| RAG-based retrieval | Rejected | Adds complexity, not needed for focused steps |

## Consequences

- Planner must identify relevant files per step
- Context builder must be smart about what to include
- Subrepo context telescoping: when working in a submodule, automatically include relevant parent context

## Implementation

- Context builder: `reeree/context.py` — `gather_context()` assembles per-step context
- Max tokens: `Config.max_context_tokens` (default 24K, leaves room in 32K window)
- Scope system: `:cd` changes project scope, context adjusts automatically
- File hints: `> files: a.py, b.py` annotations guide context assembly

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
