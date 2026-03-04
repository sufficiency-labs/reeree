# ADR-010: Inter-Daemon Communication

**Status:** Proposed
**Date:** 2026-03-04

## Context

Daemons currently have no way to communicate. Each daemon is an isolated multi-turn LLM conversation that reads the plan file and executes in its own context. When daemons work on related steps, they can't share observations, flag conflicts, or coordinate.

Gastown solves this with inter-agent mail (`gt mail`), cross-rig dispatch, and convoys. reeree needs something simpler — lightweight message passing that stays visible in the TUI.

## Decision

A message bus attached to the DaemonRegistry. Daemons send typed messages. Recipients check their mailbox between turns. All messages are visible in the TUI log (unless silenced).

### Message Format

```python
@dataclass
class DaemonMessage:
    sender_id: int
    recipient_id: int | None  # None = broadcast
    kind: MessageKind         # NOTE, REQUEST, RESPONSE, CONFLICT, DONE
    payload: str
    timestamp: float
```

### Message Kinds

| Kind | Semantics | Example |
|------|-----------|---------|
| `NOTE` | Informational, no response expected | "Step 3 modified auth.py — heads up" |
| `REQUEST` | Asks recipient for information | "What's the return type of parse()?" |
| `RESPONSE` | Reply to a REQUEST | "parse() returns dict | None" |
| `CONFLICT` | Flags a conflict between daemons | "Step 3 and Step 5 both modify auth.py" |
| `DONE` | Signals completion with notes | "Step 3 complete — added retry logic" |

### Message Bus API

```python
class MessageBus:
    def send(self, message: DaemonMessage) -> None
    def receive(self, daemon_id: int) -> list[DaemonMessage]
    def broadcast(self, sender_id: int, kind: MessageKind, payload: str) -> None
    def subscribe(self, callback: Callable[[DaemonMessage], None]) -> None
```

### TUI Integration

- Messages print to the exec log widget by default
- Format: `[d{sender}→d{recipient}] {kind}: {payload}`
- Broadcast messages: `[d{sender}→*] {kind}: {payload}`
- Silenceable via `:set message_verbosity quiet` (only CONFLICT and REQUEST shown)
- CONFLICT messages always shown (never silenced)

### Daemon Integration

The daemon executor checks the mailbox between LLM turns:

```python
# In the multi-turn loop, between turns:
messages = message_bus.receive(daemon_id)
if messages:
    # Inject messages into LLM context as a system note
    feedback.append(format_messages(messages))
```

### Plugin Subscription

Plugins can subscribe to the message bus via their `on_daemon_message` hook:

```python
class MyPlugin(ReereePlugin):
    def on_daemon_message(self, message):
        if message.kind == MessageKind.CONFLICT:
            # Handle conflict
            pass
```

## Values Served

- **[Overlap Not Turn-Taking](../../VALUES.md#3-overlap-not-turn-taking)** — Daemons coordinate without blocking. Messages are async, checked between turns.
- **[Plan Is the Interface](../../VALUES.md#2-plan-is-the-interface)** — Messages bubble up as visible log entries. Nothing hidden.
- **No Hidden State** (Red Line) — All messages visible in the TUI log

## Alternatives Considered

| Option | Verdict | Why |
|--------|---------|-----|
| Shared files on disk | Rejected | Race conditions, no ordering guarantees |
| Direct function calls | Rejected | Couples daemons, breaks isolation |
| Full message queue (Redis/ZMQ) | Rejected | Over-engineered for in-process communication |

## Consequences

- Message bus adds state to track (serializable for persistence)
- Daemons that check mailbox frequently are slower (negligible — just a list check)
- CONFLICT detection is the highest-value immediate use case
- Future: message history as part of session state serialization

## Implementation

- Message bus: `reeree/message_bus.py` — `DaemonMessage`, `MessageKind`, `MessageBus`
- Registry integration: `DaemonRegistry` gets a `message_bus` attribute
- Daemon executor: check mailbox between turns in `dispatch_step()`
- TUI: log widget prints messages via `MessageBus.subscribe()`
- Tests: `tests/test_message_bus.py`

---

> **Core Planning Documents:** [Values](../../VALUES.md) → [Implementation](../../IMPLEMENTATION.md) → [Plan](../../PROJECT_PLAN.md) → [Cost](../../COST.md) → [Revenue](../../REVENUE.md) → [Profit](../../PROFIT.md)
