# ADR-011: Subrepo Scope as Lexical Binding

**Status:** Accepted
**Date:** 2026-03-05

## Context

Reeree's `:cd` command changes the working scope to a subdirectory (typically a subrepo). The question is: what's the relationship between parent and child scope? Currently it's ad-hoc — parent CLAUDE.md is inherited, daemons are global, chat is scoped. This needs a clear model.

## Decision

Subrepo scoping follows **lexical binding** semantics from programming languages:

- **Parent scope is read-only ambient context.** The child can *see* parent bindings (CLAUDE.md, conventions, project structure) but cannot mutate them. Parent context flows down automatically.
- **Child scope is the focused workspace.** All daemon writes (file edits, shell commands, git commits) are confined to the child scope's directory tree. The child cannot write to parent paths.
- **Daemons are global.** They continue running regardless of scope changes, but each daemon's *write boundary* is fixed to the scope it was spawned in. A daemon spawned in `private/reeree/` cannot write to `vorkosigan/`.
- **Scope stack = call stack.** `:cd lib` is like a function call — you push a new frame. `:cd ..` returns. The parent's state (plan, chat) is preserved on the stack exactly as left.

### What the child inherits (read-only)

- Parent CLAUDE.md (and grandparent, up to 5 levels)
- Parent project structure awareness (via context telescoping)
- Parent daemon output in exec log (visible, not editable)
- Parent config as defaults (overridable by child `.reeree/config.json`)

### What the child does NOT inherit

- Parent plan (child has its own plan, possibly empty)
- Parent chat history (fresh chat per scope)
- Write access to parent files

### Enforcement

- `check_path_containment()` in `executor.py` already prevents path traversal
- Daemon spawn records `scope` — the project_dir name at spawn time
- Daemons from a different scope than current have their output quieted in the TUI log (file log gets everything)

### Roles analogy

Like IAM roles:
- **Root scope** = admin. Full access to the top-level repo.
- **Child scope** = scoped role. Read parent context, write only to child directory.
- **`:cd ..`** = assume parent role again.
- **Daemon scope** = fixed at spawn. A daemon's permissions don't change when the user changes scope.

## Values Served

- **[Focused Context](../../VALUES.md#6-sufficiency-over-maximalism)** — child scope gets only relevant parent context, not everything
- **[Plan Is the Interface](../../VALUES.md#2-plan-is-the-interface)** — each scope has its own plan, its own work queue
- **[Git-Per-Step](../../VALUES.md)** — child scope commits go to the child repo, parent commits go to the parent repo

## Alternatives Considered

| Option | Verdict | Why |
|--------|---------|-----|
| Flat scope (no nesting) | Rejected | Can't work on a subrepo in context of parent |
| Dynamic scoping (child sees all parent state) | Rejected | Leaky, confusing, no containment |
| Full isolation (child sees nothing from parent) | Rejected | Loses valuable context |

## Consequences

- Each daemon has a fixed write boundary at its spawn scope
- `check_path_containment()` must use the daemon's scope, not the user's current scope
- Parent context is always available but clearly marked as ambient (not editable)
- Scope changes don't affect running daemons — they keep their original scope

## Implementation

- Scope stack: `app._scope_stack` in `tui/app.py`
- Scope push/pop: `_change_scope()` in `tui/app.py`
- Parent context discovery: `_find_parent_contexts()` in `context.py`
- Path enforcement: `check_path_containment()` in `executor.py`
- Daemon scope tracking: `Daemon.scope` field in `daemon_registry.py`

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
