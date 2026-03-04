# ADR-003: Plan as Markdown Work Queue

**Status:** Accepted
**Date:** 2026-02-15

## Context

Need a shared data structure between user and daemons that's human-readable and editable. The plan is simultaneously the spec, the status display, the steering wheel, the history, and the context system.

## Decision

Plan is a markdown file with checkboxes and `> ` annotation lines.

```markdown
- [ ] Add retry logic to sync.sh
  > max 3 retries, exponential backoff
  > files: scripts/sync.sh, scripts/retry.sh
  > done: retry_test.sh passes
```

- `- [ ]` / `- [x]` / `- [>]` / `- [!]` — step status (pending/done/active/failed)
- `> ` indented lines — annotations (specs, acceptance criteria, file hints)
- `> done:` — acceptance criteria the daemon reads before marking complete
- `> files:` — file hints the daemon uses for focused context

## Values Served

- **[Plan Is the Interface](../../VALUES.md#2-plan-is-the-interface)** — Visible, editable with any text editor, diffable in git
- **No Hidden State** (Red Line) — All state representable as files on disk
- **No Lock-in** (Red Line) — Markdown is universally readable, no proprietary format

## Rationale

Markdown is universally readable. Checkboxes are universally understood. Annotations are just indented lines. No custom DSL to learn. The plan file is simultaneously human-readable documentation and machine-parseable state.

## Alternatives Considered

| Option | Verdict | Why |
|--------|---------|-----|
| JSON | Rejected | Not human-editable |
| YAML | Rejected | Fragile indentation |
| Custom format | Rejected | Violates No Lock-in |

## Consequences

- Parser must be tolerant of hand-edited markdown
- Round-trip fidelity matters (parse → serialize → parse should be lossless)
- Rich display mode (Unicode indicators) needs separate parser path

## Implementation

- Plan model: `reeree/plan.py` — `Plan` and `Step` dataclasses
- Markdown parser: `Plan.from_markdown()` — tolerant regex parsing
- Rich display: `Plan.to_rich_display()` / `Plan.from_rich_display()` — Unicode status indicators
- File operations: `Plan.save()` / `Plan.load()` — disk I/O

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
