"""Daemon registry — lifecycle management for all daemon processes.

Replaces the ad-hoc dict[int, dict] tracking with proper dataclass + registry.
Supports parent/child hierarchy, pause/resume, and tree rendering.
"""

import time
from dataclasses import dataclass, field
from enum import Enum


class DaemonKind(str, Enum):
    """What kind of daemon this is."""
    EXECUTOR = "executor"      # Parent — persistent orchestrator
    STEP = "step"              # Child — executes one plan step
    COHERENCE = "coherence"    # Child — coherence checker
    WATCHER = "watcher"        # Child — watches for file changes
    STATE = "state"            # Child — state assessment daemon


class DaemonStatus(str, Enum):
    """Daemon lifecycle status."""
    ACTIVE = "active"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Daemon:
    """A tracked daemon process."""
    id: int
    kind: DaemonKind
    description: str
    status: DaemonStatus = DaemonStatus.ACTIVE
    parent_id: int | None = None
    step_index: int = -1
    scope: str = ""
    model: str = ""
    start_time: float = field(default_factory=time.monotonic)
    last_log_time: float = 0.0
    log: str = ""
    error: str = ""
    task: object = None  # asyncio.Task reference

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.start_time

    @property
    def elapsed_str(self) -> str:
        mins, secs = divmod(int(self.elapsed), 60)
        return f"{mins}:{secs:02d}" if mins else f"{secs}s"

    @property
    def is_active(self) -> bool:
        return self.status == DaemonStatus.ACTIVE

    def append_log(self, message: str) -> None:
        self.log += message + "\n"
        self.last_log_time = time.monotonic()


class DaemonRegistry:
    """Central registry for all daemons. Replaces _daemons dict + _next_daemon_id."""

    def __init__(self):
        self._daemons: dict[int, Daemon] = {}
        self._next_id = 1

    def spawn(
        self,
        kind: DaemonKind,
        description: str,
        parent_id: int | None = None,
        step_index: int = -1,
        scope: str = "",
        model: str = "",
    ) -> Daemon:
        """Create and register a new daemon. Returns the Daemon."""
        daemon = Daemon(
            id=self._next_id,
            kind=kind,
            description=description,
            parent_id=parent_id,
            step_index=step_index,
            scope=scope,
            model=model,
        )
        self._daemons[daemon.id] = daemon
        self._next_id += 1
        return daemon

    def get(self, daemon_id: int) -> Daemon | None:
        """Get a daemon by ID."""
        return self._daemons.get(daemon_id)

    def kill(self, daemon_id: int) -> bool:
        """Mark a daemon (and all descendants) as failed."""
        daemon = self._daemons.get(daemon_id)
        if daemon is None:
            return False
        daemon.status = DaemonStatus.FAILED
        daemon.error = "killed"
        # Recursively kill all descendants
        for child in self.children(daemon_id):
            if child.status in (DaemonStatus.ACTIVE, DaemonStatus.PAUSED):
                self.kill(child.id)
                child.error = "parent killed"
        return True

    def pause(self, daemon_id: int) -> bool:
        """Pause an active daemon."""
        daemon = self._daemons.get(daemon_id)
        if daemon is None or daemon.status != DaemonStatus.ACTIVE:
            return False
        daemon.status = DaemonStatus.PAUSED
        return True

    def resume(self, daemon_id: int) -> bool:
        """Resume a paused daemon."""
        daemon = self._daemons.get(daemon_id)
        if daemon is None or daemon.status != DaemonStatus.PAUSED:
            return False
        daemon.status = DaemonStatus.ACTIVE
        return True

    def children(self, parent_id: int) -> list[Daemon]:
        """Get all direct children of a daemon."""
        return [d for d in self._daemons.values() if d.parent_id == parent_id]

    def active(self) -> list[Daemon]:
        """Get all active daemons."""
        return [d for d in self._daemons.values() if d.is_active]

    def all(self) -> list[Daemon]:
        """Get all daemons."""
        return list(self._daemons.values())

    @property
    def active_count(self) -> int:
        return sum(1 for d in self._daemons.values() if d.is_active)

    @property
    def total_count(self) -> int:
        return len(self._daemons)

    def tree(self) -> list[tuple[Daemon, int]]:
        """Return daemons as a flat list with depth for tree rendering.

        Returns list of (daemon, depth) tuples in display order:
        roots first (depth=0), then children (depth=1), etc.
        """
        result: list[tuple[Daemon, int]] = []

        # Find roots (no parent)
        roots = [d for d in self._daemons.values() if d.parent_id is None]
        roots.sort(key=lambda d: d.id)

        def _walk(daemon: Daemon, depth: int) -> None:
            result.append((daemon, depth))
            kids = self.children(daemon.id)
            kids.sort(key=lambda d: d.id)
            for child in kids:
                _walk(child, depth + 1)

        for root in roots:
            _walk(root, 0)

        return result
