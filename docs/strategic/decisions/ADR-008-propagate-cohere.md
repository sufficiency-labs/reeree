# ADR-008: Propagate and Cohere Commands

**Status:** Implemented
**Date:** 2026-02-15
**Implemented:** 2026-02-28

## Context

Documents reference each other. When one changes, linked docs may become incoherent. This is the constraint cascade from VDSE applied to any document tree — edit VALUES.md, propagate checks IMPLEMENTATION.md. Edit a spec, cohere checks if the code matches.

## Decision

Two commands:

- **`:propagate`** — Crawls links from the current doc and checks all referenced docs for coherence
- **`:cohere doc1 doc2 doc3`** — Checks coherence across an explicit set of docs

Both dispatch coherence daemons that read the docs, identify conflicts or stale references, and either flag or propose fixes.

## Values Served

- **[Plan Is the Interface](../../VALUES.md#2-plan-is-the-interface)** — The doc tree IS the system. Coherence ensures the tree stays consistent.
- **Transparency** — Conflicts are surfaced, not hidden

## Rationale

This is the VDSE pattern: values constrain implementation, implementation informs plan. When any node changes, connected nodes may need updating. Rather than requiring the user to manually check, daemons crawl the link graph and surface issues.

## Implementation

- TUI commands: `:cohere` and `:propagate` in `reeree/tui/app.py`
- Daemon kind: `DaemonKind.COHERENCE` in `reeree/daemon_registry.py`
- Current state: Simple LLM calls ("here are two docs, find contradictions")
- Future: Smart crawling, caching, incremental checks

## Consequences

- Coherence checking is LLM-powered, so it costs tokens per run
- Results appear in the exec log panel
- Future: plugin-based coherence checkers could add domain-specific rules

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
