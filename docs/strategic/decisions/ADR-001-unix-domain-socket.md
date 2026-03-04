# ADR-001: Unix Domain Socket Daemon/Client

**Status:** Accepted
**Date:** 2026-02-15

## Context

Sessions must survive terminal death. tmux does this with a daemon process — the terminal is just a view into a persistent session. reeree needs the same: kill your terminal, reconnect later, everything is where you left it.

## Decision

reeree runs as a background daemon communicating with TUI clients via Unix domain socket at `~/.reeree/sock`.

The daemon manages:
- Plan state (loaded plan, step statuses)
- Daemon pool (active executor/coherence/watcher daemons)
- Session state (serialized to disk for crash recovery)

TUI clients connect via the socket, send commands, receive updates. Multiple clients can attach to the same session.

## Values Served

- **[Persistence Without Fragility](../../VALUES.md#4-persistence-without-fragility)** — Sessions survive terminal death, like tmux
- **[Plan Is the Interface](../../VALUES.md#2-plan-is-the-interface)** — Plan state lives in the daemon, not the client

## Rationale

Same proven pattern as tmux. No network exposure. Fast IPC. The socket is a filesystem artifact — it can be listed, cleaned up, and managed with standard Unix tools.

## Alternatives Considered

| Option | Verdict | Why |
|--------|---------|-----|
| Run inside tmux | Rejected | Adds dependency, user must manage tmux sessions |
| Screen-style | Rejected | Less capable than tmux pattern |
| TCP socket | Rejected | Unnecessary network exposure |

## Consequences

- Need a daemon lifecycle (start/stop/attach/detach)
- Socket cleanup on crash (stale socket detection)
- Session state serialization to disk for recovery
- Client protocol design (JSON messages over socket)

## Trade-offs

More complex than a simple CLI. Worth it for persistence. The daemon lifecycle is the most complex piece — but tmux has proven the pattern works.

## Implementation

- Session state: `reeree/session.py` (serialization)
- Socket server: `reeree/server.py` (planned)
- Socket client: TUI connects via socket (planned)
- Current state: TUI runs daemons directly (no socket yet)

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
