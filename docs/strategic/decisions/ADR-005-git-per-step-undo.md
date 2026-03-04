# ADR-005: Git-Per-Step Undo System

**Status:** Accepted
**Date:** 2026-02-15

## Context

Mistakes must be cheap and reversible. When a daemon makes a bad edit, the user needs to undo it instantly without manual git archaeology.

## Decision

Each completed step creates a git commit. Undo = `git revert`.

Commit message format: `reeree: {step description}`

## Values Served

- **[Persistence Without Fragility](../../VALUES.md#4-persistence-without-fragility)** — Work survives everything: crash, reboot, mistake
- **No Hidden State** (Red Line) — Git history is the undo stack, visible via `git log`

## Rationale

Git is already the user's VCS. No new system to learn. Full history preserved. Can revert any step independently. The git log becomes a readable history of what the daemons did.

## Alternatives Considered

| Option | Verdict | Why |
|--------|---------|-----|
| Custom undo stack | Rejected | Reinventing git poorly |
| File snapshots | Rejected | Doesn't compose with user's existing git workflow |

## Consequences

- Requires the project to be a git repo
- Creates potentially many small commits (can squash later)
- Commit message attribution includes daemon info for auditability

## Implementation

- Git operations: `reeree/executor.py` — `git_commit()`, `git_revert()`
- Daemon executor: `reeree/daemon_executor.py` — commits on step completion
- TUI command: `:undo` triggers `git revert` for the last completed step

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
