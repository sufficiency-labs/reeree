# ADR-002: Textual for TUI Framework

**Status:** Accepted
**Date:** 2026-02-15

## Context

Need a multi-pane terminal UI with vim-style keybindings. The TUI is the primary interface — plan editor on the left, daemon status on the right, command bar at the bottom, exec log and chat panels that open/close.

## Decision

Use [Textual](https://textual.textualize.io/) (Python) for the TUI client.

## Values Served

- **[Vim Is the Lingua Franca](../../VALUES.md#5-vim-is-the-lingua-franca)** — Textual supports custom key bindings, enabling normal/insert/command modal editing
- **[Overlap Not Turn-Taking](../../VALUES.md#3-overlap-not-turn-taking)** — Reactive widgets update independently; daemon pane refreshes while user edits the plan

## Rationale

Textual supports reactive widgets, CSS-like styling, async updates. Active development, good docs. Python matches the rest of the stack. The reactive model (widgets re-render on state change) is a natural fit for displaying live daemon status alongside an editable plan.

## Alternatives Considered

| Option | Verdict | Why |
|--------|---------|-----|
| curses | Rejected | Too low-level for multi-pane reactive UI |
| blessed/urwid | Rejected | Less active, fewer features |
| Go + bubbletea | Rejected | Would split the codebase language |

## Consequences

- Python TUI performance is adequate for this use case
- Textual's CSS-like styling system requires some learning
- Widget composition model works well for split-pane layouts

## Implementation

- Main app: `reeree/tui/app.py` — PlanEditor, DaemonTreeView, ExecLog, ChatPanel, CommandInput
- Daemon tree: `reeree/tui/daemon_tree.py` — hierarchical daemon display
- Setup wizard: `reeree/tui/setup_screen.py` — first-run "character creation"

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
