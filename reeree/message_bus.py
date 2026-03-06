"""Inter-daemon communication — typed message passing.

Daemons send messages via the MessageBus. Recipients check their mailbox
between LLM turns. All messages are visible in the TUI log unless silenced.

See ADR-010: docs/strategic/decisions/ADR-010-inter-daemon-communication.md
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class MessageKind(str, Enum):
    """Types of inter-daemon messages."""
    NOTE = "note"            # Informational, no response expected
    REQUEST = "request"      # Asks recipient for information
    RESPONSE = "response"    # Reply to a REQUEST
    CONFLICT = "conflict"    # Flags a conflict between daemons
    DONE = "done"            # Signals completion with notes


@dataclass
class DaemonMessage:
    """A message between daemons."""
    sender_id: int
    recipient_id: int | None  # None = broadcast to all
    kind: MessageKind
    payload: str
    timestamp: float = field(default_factory=time.time)

    def format_log(self) -> str:
        """Format for TUI log display."""
        target = f"d{self.recipient_id}" if self.recipient_id else "*"
        return f"[d{self.sender_id}→{target}] {self.kind.value}: {self.payload}"

    def format_context(self) -> str:
        """Format for injecting into LLM context between turns."""
        return f"Message from daemon {self.sender_id} ({self.kind.value}): {self.payload}"


class MessageBus:
    """Central message bus for inter-daemon communication.

    Messages are stored per-recipient. Broadcast messages go to all
    recipients. Subscribers get notified of every message (for TUI log).
    """

    def __init__(self):
        self._mailboxes: dict[int, list[DaemonMessage]] = {}
        self._all_messages: list[DaemonMessage] = []
        self._subscribers: list[Callable[[DaemonMessage], None]] = []

    def send(self, message: DaemonMessage) -> None:
        """Send a message. Routes to recipient mailbox or broadcasts."""
        self._all_messages.append(message)

        if message.recipient_id is not None:
            # Direct message
            if message.recipient_id not in self._mailboxes:
                self._mailboxes[message.recipient_id] = []
            self._mailboxes[message.recipient_id].append(message)
        else:
            # Broadcast — add to all existing mailboxes
            for mailbox in self._mailboxes.values():
                mailbox.append(message)

        # Notify subscribers (TUI log, plugins)
        for callback in self._subscribers:
            try:
                callback(message)
            except Exception:
                pass  # Don't let a bad subscriber break the bus

    def receive(self, daemon_id: int) -> list[DaemonMessage]:
        """Receive and clear all pending messages for a daemon.

        Returns the messages and removes them from the mailbox.
        Called by daemon executor between LLM turns.
        """
        messages = self._mailboxes.get(daemon_id, [])
        self._mailboxes[daemon_id] = []
        return messages

    def peek(self, daemon_id: int) -> list[DaemonMessage]:
        """Peek at pending messages without clearing them."""
        return list(self._mailboxes.get(daemon_id, []))

    def broadcast(self, sender_id: int, kind: MessageKind, payload: str) -> None:
        """Convenience: send a broadcast message."""
        self.send(DaemonMessage(
            sender_id=sender_id,
            recipient_id=None,
            kind=kind,
            payload=payload,
        ))

    def subscribe(self, callback: Callable[[DaemonMessage], None]) -> None:
        """Subscribe to all messages. Used by TUI log and plugins.

        Callback receives every message as it's sent.
        """
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[DaemonMessage], None]) -> None:
        """Remove a subscriber."""
        try:
            self._subscribers.remove(callback)
        except ValueError:
            pass

    def register_daemon(self, daemon_id: int) -> None:
        """Register a daemon's mailbox. Called when daemon is spawned."""
        if daemon_id not in self._mailboxes:
            self._mailboxes[daemon_id] = []

    def unregister_daemon(self, daemon_id: int) -> None:
        """Remove a daemon's mailbox. Called when daemon finishes."""
        self._mailboxes.pop(daemon_id, None)

    @property
    def history(self) -> list[DaemonMessage]:
        """All messages ever sent, in order."""
        return list(self._all_messages)

    @property
    def pending_count(self) -> int:
        """Total pending messages across all mailboxes."""
        return sum(len(msgs) for msgs in self._mailboxes.values())

    def to_dict(self) -> dict:
        """Serialize for session persistence."""
        return {
            "messages": [
                {
                    "sender_id": m.sender_id,
                    "recipient_id": m.recipient_id,
                    "kind": m.kind.value,
                    "payload": m.payload,
                    "timestamp": m.timestamp,
                }
                for m in self._all_messages
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MessageBus":
        """Deserialize from session persistence."""
        bus = cls()
        for m in data.get("messages", []):
            msg = DaemonMessage(
                sender_id=m["sender_id"],
                recipient_id=m.get("recipient_id"),
                kind=MessageKind(m["kind"]),
                payload=m["payload"],
                timestamp=m.get("timestamp", 0.0),
            )
            bus._all_messages.append(msg)
        return bus
