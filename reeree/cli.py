"""reeree CLI — open a document. machines work inside it."""

import click
import sys
from pathlib import Path

from .config import Config
from .plan import Plan
from .planner import create_plan


EXAMPLES = """
Examples:

  reeree                        Open default document (or plan)
  reeree essay.md               Open any markdown file
  reeree plan.yaml              Open a plan file
  reeree "fix the auth bug"     Create a plan from intent
  reeree init                   Initialize .reeree/ directory
"""

# Discovery order for default document when invoked with no arguments
DEFAULT_DOCS = ["PROJECT_PLAN.md", "PLAN.md", "README.md"]

REEREE_GITIGNORE = """\
session.json
session.log
local/
"""


class _ReereeCommand(click.Command):
    """Preserve epilog formatting."""

    def format_epilog(self, ctx, formatter):
        if self.epilog:
            formatter.write(self.epilog)


def init_reeree_dir(project_dir: Path) -> None:
    """Create .reeree/ directory with config.json and .gitignore."""
    reeree_dir = project_dir / ".reeree"
    reeree_dir.mkdir(exist_ok=True)

    # .gitignore — committed, ignores ephemeral files
    gitignore = reeree_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(REEREE_GITIGNORE)

    # config.json — committed, project-level settings
    config_file = reeree_dir / "config.json"
    if not config_file.exists():
        Config().save(config_file)

    # plan.yaml — committed, shared work queue (create empty if missing)
    plan_file = reeree_dir / "plan.yaml"
    if not plan_file.exists():
        Plan(intent="", steps=[]).save(plan_file)

    # local/ — gitignored, per-user scratch
    local_dir = reeree_dir / "local"
    local_dir.mkdir(exist_ok=True)


def _discover_default_doc(project_dir: Path, config: Config) -> Path | None:
    """Find the default document to open.

    Order: config.default_doc > PROJECT_PLAN.md > PLAN.md > README.md.
    """
    if config.default_doc:
        p = project_dir / config.default_doc
        if p.exists() and p.is_file():
            return p.resolve()

    for name in DEFAULT_DOCS:
        p = project_dir / name
        if p.exists() and p.is_file():
            return p.resolve()

    return None


@click.command(cls=_ReereeCommand, epilog=EXAMPLES)
@click.argument("target", nargs=-1, required=False)
@click.option("--model", help="Model to use (e.g. deepseek-coder-v2:latest)")
@click.option("--api-base", help="API base URL")
@click.option("--api-key", help="API key")
@click.option("--autonomy", type=click.Choice(["low", "medium", "high", "full"]), default="medium")
@click.option("--project", type=click.Path(exists=True), default=".", help="Project directory")
@click.option("--setup", is_flag=True, help="Launch setup wizard")
def main(target, model, api_base, api_key, autonomy, project, setup):
    """A text editor where machines work inside your document.

    Open a file. Drop in [machine: ...] annotations. Save.
    Daemons execute. Results appear.
    """
    project_dir = Path(project).resolve()

    # Handle "reeree init" — create .reeree/ directory and exit
    target_str = " ".join(target) if target else ""
    if target_str == "init":
        init_reeree_dir(project_dir)
        click.echo(f"Initialized .reeree/ in {project_dir}")
        return

    # Auto-init .reeree/ on first run if it doesn't exist
    reeree_dir = project_dir / ".reeree"
    if not reeree_dir.exists():
        init_reeree_dir(project_dir)

    # Load config
    config = Config.load(project_dir / ".reeree" / "config.json")
    if model:
        config.model = model
    if api_base:
        config.api_base = api_base
    if api_key:
        config.api_key = api_key
    config.autonomy = autonomy

    # Determine what to open
    plan = None
    open_file = None  # file to open in viewer on launch

    if target_str:
        # Is it a file path?
        target_path = Path(target_str)
        # Check relative to cwd first, then project dir
        if target_path.exists():
            resolved = target_path.resolve()
        elif (project_dir / target_path).exists():
            resolved = (project_dir / target_path).resolve()
        else:
            resolved = None

        if resolved and resolved.is_file():
            # Opening a specific document
            if resolved.suffix in (".yaml", ".yml"):
                # YAML file — try to load as plan
                try:
                    plan = Plan.load(resolved)
                    done, total = plan.progress
                    click.echo(f"Opening plan: {resolved.name} ({done}/{total} done)")
                except Exception:
                    # Not a plan YAML — open as file
                    open_file = resolved
                    click.echo(f"Opening: {resolved.name}")
            else:
                # Markdown or other file — open in file viewer
                open_file = resolved
                click.echo(f"Opening: {resolved.name}")
        else:
            # Not a file — treat as intent string for plan generation
            click.echo(f"Planning: {target_str}")
            try:
                plan = create_plan(target_str, project_dir, config)
                plan_path = project_dir / ".reeree" / "plan.yaml"
                plan.save(plan_path)
                click.echo(f"Plan: {plan_path} ({len(plan.steps)} steps)")
            except Exception as e:
                click.echo(f"Failed to create plan: {e}", err=True)
                sys.exit(1)
    else:
        # No target — discover default document, load plan in background
        plan_path = project_dir / ".reeree" / "plan.yaml"
        if plan_path.exists():
            try:
                plan = Plan.load(plan_path)
            except Exception:
                plan = None

        default_doc = _discover_default_doc(project_dir, config)
        if default_doc:
            open_file = default_doc
            if plan and plan.steps:
                done, total = plan.progress
                click.echo(f"Opening: {default_doc.name} (plan: {done}/{total} done)")
            else:
                click.echo(f"Opening: {default_doc.name}")
        elif plan and plan.steps:
            done, total = plan.progress
            click.echo(f"Resuming: {plan_path.name} ({done}/{total} done)")
        else:
            click.echo("No plan. :edit to start writing, :chat to talk to executor.")

    if plan is None:
        plan = Plan(intent="", steps=[])

    # Force first-run setup if --setup flag
    if setup:
        config.api_key = ""
        config.models = {}

    # Launch TUI
    from .tui.app import ReereeApp
    app = ReereeApp(project_dir=project_dir, config=config, plan=plan)

    # If opening a specific file, open it in the file viewer on mount
    if open_file:
        app._launch_file = open_file

    app.run()


if __name__ == "__main__":
    main()
