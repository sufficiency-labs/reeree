# ADR-007: Orchestrator LLM (Meta-Layer)

**Status:** Implemented
**Date:** 2026-02-15
**Implemented:** 2026-03-02

## Context

Different steps need different models. A complex refactor wants Claude Sonnet. A file rename wants a free local model. A vision task needs Gemini. The user shouldn't have to manually pick models per step.

## Decision

A model router classifies each step by task type (reasoning/coding/fast) and routes it to the best-fit executor model, with the appropriate API configuration. The user can override routing at any time.

### Tier Classification

| Tier | Use Case | Keywords |
|------|----------|----------|
| Reasoning | Architecture, design, review, coherence | architect, design, refactor, plan, analyze, review |
| Coding | Implementation, editing, building | Default for executor daemons |
| Fast | Read-only, search, status checks | read, check, list, grep, find, search |

### Daemon Kind Overrides

| Daemon Kind | Forced Tier | Why |
|-------------|-------------|-----|
| COHERENCE | Reasoning | Cross-document analysis requires strong reasoning |
| STATE | Reasoning | State assessment requires nuanced analysis |
| WATCHER | Fast | File watching is read-only |

## Values Served

- **[Sufficiency Over Maximalism](../../VALUES.md#6-sufficiency-over-maximalism)** — Cheapest adequate model per step. $0.003 on a hard step, $0 on an easy one.
- **[Delegated Agency](../../VALUES.md#1-delegated-agency)** — Routing within delegated scope, user approves or overrides

## Implementation

- Router: `reeree/router.py` — `classify_task()` + `route_model()`
- Config: `reeree/config.py` — `models` dict (per-key model/api_base/api_key) + `routing` dict (tier → model_key)
- Daemon executor: `reeree/daemon_executor.py` — calls `route_model()` before each dispatch

## Consequences

- Needs a model registry with capabilities and pricing (future)
- Keyword-based classification is good enough for now; LLM-based classification later
- Fallback: single configured model for all steps if no routing configured

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
