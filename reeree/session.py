"""Session state serialization — Plan + DaemonRegistry → JSON → disk.

Enables crash recovery and daemon persistence (Phase 2). The session
state captures everything needed to resume after a TUI disconnect or crash.

See ADR-001: docs/strategic/decisions/ADR-001-unix-domain-socket.md
"""

import json
import time
from dataclasses import asdict
from pathlib import Path

from .plan import Plan, Step
from .daemon_registry import DaemonRegistry, Daemon, DaemonKind, DaemonStatus
from .message_bus import MessageBus


def serialize_session(
    plan: Plan,
    registry: DaemonRegistry,
    message_bus: MessageBus | None = None,
    project_dir: str = ".",
    scope_stack: list[str] | None = None,
) -> dict:
    """Serialize full session state to a dict (JSON-safe).

    Captures:
    - Plan (intent + all steps with status/annotations/files/commit hashes)
    - Daemon registry (all daemons with status, kind, hierarchy)
    - Message bus history
    - Project directory and scope stack
    - Timestamp
    """
    return {
        "version": 1,
        "timestamp": time.time(),
        "project_dir": str(project_dir),
        "scope_stack": scope_stack or [],
        "plan": _serialize_plan(plan),
        "daemons": _serialize_registry(registry),
        "messages": message_bus.to_dict() if message_bus else {"messages": []},
    }


def deserialize_session(data: dict) -> dict:
    """Deserialize session state from a dict.

    Returns a dict with keys: plan, registry, message_bus, project_dir, scope_stack.
    """
    version = data.get("version", 1)
    if version != 1:
        raise ValueError(f"Unknown session version: {version}")

    plan = _deserialize_plan(data["plan"])
    registry = _deserialize_registry(data["daemons"])
    message_bus = MessageBus.from_dict(data.get("messages", {"messages": []}))

    return {
        "plan": plan,
        "registry": registry,
        "message_bus": message_bus,
        "project_dir": data.get("project_dir", "."),
        "scope_stack": data.get("scope_stack", []),
        "timestamp": data.get("timestamp", 0),
    }


def save_session(
    path: Path,
    plan: Plan,
    registry: DaemonRegistry,
    message_bus: MessageBus | None = None,
    project_dir: str = ".",
    scope_stack: list[str] | None = None,
) -> None:
    """Serialize session state and write to a JSON file."""
    data = serialize_session(plan, registry, message_bus, project_dir, scope_stack)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def load_session(path: Path) -> dict:
    """Load session state from a JSON file.

    Returns dict with keys: plan, registry, message_bus, project_dir, scope_stack.
    Raises FileNotFoundError if the file doesn't exist.
    """
    data = json.loads(path.read_text())
    return deserialize_session(data)


# --- Plan serialization ---

def _serialize_plan(plan: Plan) -> dict:
    """Serialize a Plan to a dict."""
    return {
        "intent": plan.intent,
        "steps": [
            {
                "description": step.description,
                "status": step.status,
                "annotations": step.annotations,
                "files": step.files,
                "commit_hash": step.commit_hash,
                "daemon_id": step.daemon_id,
                "error": step.error,
            }
            for step in plan.steps
        ],
    }


def _deserialize_plan(data: dict) -> Plan:
    """Deserialize a Plan from a dict."""
    steps = [
        Step(
            description=s["description"],
            status=s.get("status", "pending"),
            annotations=s.get("annotations", []),
            files=s.get("files", []),
            commit_hash=s.get("commit_hash"),
            daemon_id=s.get("daemon_id"),
            error=s.get("error"),
        )
        for s in data.get("steps", [])
    ]
    return Plan(intent=data.get("intent", ""), steps=steps)


# --- Registry serialization ---

def _serialize_registry(registry: DaemonRegistry) -> dict:
    """Serialize a DaemonRegistry to a dict."""
    return {
        "next_id": registry._next_id,
        "daemons": [
            {
                "id": d.id,
                "kind": d.kind.value,
                "description": d.description,
                "status": d.status.value,
                "parent_id": d.parent_id,
                "step_index": d.step_index,
                "scope": d.scope,
                "model": d.model,
                "log": d.log,
                "error": d.error,
            }
            for d in registry.all()
        ],
    }


def _deserialize_registry(data: dict) -> DaemonRegistry:
    """Deserialize a DaemonRegistry from a dict."""
    registry = DaemonRegistry()
    registry._next_id = data.get("next_id", 1)

    for d in data.get("daemons", []):
        daemon = Daemon(
            id=d["id"],
            kind=DaemonKind(d["kind"]),
            description=d["description"],
            status=DaemonStatus(d.get("status", "done")),
            parent_id=d.get("parent_id"),
            step_index=d.get("step_index", -1),
            scope=d.get("scope", ""),
            model=d.get("model", ""),
            log=d.get("log", ""),
            error=d.get("error", ""),
        )
        registry._daemons[daemon.id] = daemon

    return registry
