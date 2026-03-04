"""Daemon tree view — hierarchical display of all running daemons.

Replaces flat DaemonProgress widgets with a single tree that shows
parent/child relationships, status, elapsed time, and model tier.
"""

import time
from textual.widgets import Static

from ..daemon_registry import DaemonRegistry, DaemonStatus


# Status icons by daemon status
_STATUS_ICONS = {
    DaemonStatus.ACTIVE: "[cyan]●[/cyan]",
    DaemonStatus.PAUSED: "[yellow]◌[/yellow]",
    DaemonStatus.DONE: "[green]✓[/green]",
    DaemonStatus.FAILED: "[red]✗[/red]",
}

# Box-drawing chars for tree structure
_TEE = "├── "
_LAST = "└── "
_PIPE = "│   "
_SPACE = "    "


class DaemonTreeView(Static):
    """Renders the daemon hierarchy from DaemonRegistry.

    Refreshes every second via timer. Shows:
    - Tree structure with box-drawing characters
    - Status icon, daemon id, description
    - Elapsed time, model tier tag
    """

    def __init__(self, registry: DaemonRegistry, **kwargs):
        super().__init__(**kwargs)
        self._registry = registry

    def on_mount(self) -> None:
        self._timer = self.set_interval(1.0, self._refresh_tree)
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        tree = self._registry.tree()
        if not tree:
            self.update("")
            return

        lines = []
        for i, (daemon, depth) in enumerate(tree):
            # Build prefix for tree structure
            if depth == 0:
                prefix = ""
            else:
                # Check if this is the last sibling at this depth
                is_last = True
                for j in range(i + 1, len(tree)):
                    if tree[j][1] < depth:
                        break
                    if tree[j][1] == depth:
                        is_last = False
                        break
                connector = _LAST if is_last else _TEE
                # Build ancestor pipes
                ancestor_prefix = ""
                for d in range(1, depth):
                    # Check if there are more siblings at depth d after this point
                    has_more = False
                    for j in range(i + 1, len(tree)):
                        if tree[j][1] < d:
                            break
                        if tree[j][1] == d:
                            has_more = True
                            break
                    ancestor_prefix += _PIPE if has_more else _SPACE
                prefix = ancestor_prefix + connector

            icon = _STATUS_ICONS.get(daemon.status, "?")
            elapsed = daemon.elapsed_str
            desc = daemon.description[:40]
            model_tag = f"  [dim]{daemon.model}[/dim]" if daemon.model else ""
            tier_tag = ""

            line = f"{prefix}{icon} [bold]d{daemon.id}[/bold] {desc}  [dim]{elapsed}{model_tag}[/dim]"
            lines.append(line)

        self.update("\n".join(lines))
