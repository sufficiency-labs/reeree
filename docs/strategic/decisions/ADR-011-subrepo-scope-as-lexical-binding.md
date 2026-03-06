# ADR-011: Scope Implicit in Document Path

**Status:** Superseded (replaces original `:cd`-based explicit scoping)
**Date:** 2026-03-06 (original: 2026-03-05)

## Context

The original version of this ADR defined a `:cd` command that explicitly pushed/popped scope to subdirectories (typically subrepos). This created a scope stack maintained by the TUI, with `:cd path` pushing a frame and `:cd ..` popping it. In practice, this mechanism was unnecessary -- opening a file already implies what directory you're working in. The explicit scope commands added complexity without adding capability.

## Decision

Scope is **implicit in the document path.** When you open a file with `reeree private/foo/PLAN.md`, the tool derives the working directory from the file's location (`private/foo/`). No explicit `:cd` command exists.

- **The file path IS the scope.** Opening `private/reeree/PLAN.md` means you're working in `private/reeree/`. Opening `private/relationships/people/alice/README.md` means you're working in that person's directory.
- **Parent context is discoverable.** CLAUDE.md files from parent directories are found by walking up the directory tree. A file at `private/reeree/docs/foo.md` can see CLAUDE.md from `private/reeree/` and from the repo root. This replaces the explicit "parent scope inheritance" from the original design.
- **Daemon write boundaries follow the file.** A daemon spawned for a file in `private/reeree/` writes within that directory tree. No separate scope tracking needed -- the file location determines the boundary.
- **No scope stack, no scope commands.** The `:cd`, `:cd ..`, and `:scope` commands are removed. The user opens a file; the tool knows where it is.

### What the tool derives from the path

- Working directory for daemon file operations
- Which CLAUDE.md files to load as context (walk up the tree)
- Git repository boundary (for commits)
- Config overrides (`.reeree/config.json` in the file's project directory)

### What stays the same from the original ADR

- `check_path_containment()` in `executor.py` still prevents path traversal
- Parent CLAUDE.md context still flows to child directories (read-only)
- Each daemon's write boundary is still fixed at spawn time

## Values Served

- **[Focused Context](../../VALUES.md#6-sufficiency-over-maximalism)** -- context is scoped to the file's location, no manual management
- **[Plan Is the Interface](../../VALUES.md#2-plan-is-the-interface)** -- the document you open determines the workspace
- **[Sufficiency Over Maximalism](../../VALUES.md#6-sufficiency-over-maximalism)** -- removed a command that duplicated what the filesystem already provides
- **[Git-Per-Step](../../VALUES.md)** -- commits target the repo containing the file

## Alternatives Considered

| Option | Verdict | Why |
|--------|---------|-----|
| Explicit `:cd` scope stack (original ADR-011) | Superseded | Unnecessary -- file path already implies scope |
| Flat scope (no nesting) | Still rejected | Parent context is valuable |
| Dynamic scoping (child sees all parent state) | Still rejected | Leaky, no containment |

## Consequences

- `:cd`, `:cd ..`, and `:scope` commands removed from the TUI
- Scope is determined at file-open time, not changed during a session
- Simpler mental model: the file you're editing IS your context
- Parent CLAUDE.md discovery is a directory-walk operation, not a stack operation

## Implementation

- Path-based scope derivation: `cli.py` resolves the file path to determine project directory
- Parent context discovery: `_find_parent_contexts()` in `context.py` walks up the directory tree
- Path enforcement: `check_path_containment()` in `executor.py`
- Daemon scope tracking: `Daemon.scope` field in `daemon_registry.py` (set from file path at spawn)

---

> **Core Planning Documents:** [Values](../../VALUES.md) -> [Implementation](../../IMPLEMENTATION.md) -> [Plan](../../PROJECT_PLAN.md) -> [Cost](../../COST.md) -> [Revenue](../../REVENUE.md) -> [Profit](../../PROFIT.md)
