"""reeree CLI — open a document. machines work inside it."""

import click
import sys
from pathlib import Path

from .config import Config
from .plan import Plan
from .planner import create_plan


@click.group(invoke_without_command=True)
@click.argument("target", nargs=-1, required=False)
@click.option("--model", help="Model to use (e.g. deepseek-coder-v2:latest)")
@click.option("--api-base", help="API base URL")
@click.option("--api-key", help="API key")
@click.option("--autonomy", type=click.Choice(["low", "medium", "high", "full"]), default="medium")
@click.option("--project", type=click.Path(exists=True), default=".", help="Project directory")
@click.option("--setup", is_flag=True, help="Launch setup wizard")
@click.pass_context
def main(ctx, target, model, api_base, api_key, autonomy, project, setup):
    """reeree — a text editor where machines work inside your document.

    Open a document. Edit it. Drop in [machine: ...] annotations. Save.
    Daemons execute. Results appear. The document evolves.

    Examples:
        reeree                          # open default plan (or create)
        reeree essay.md                 # open any markdown file
        reeree plan.yaml                # open a plan file
        reeree IMPLEMENTATION_PLAN.md   # open a project doc
        reeree "fix the auth bug"       # create a plan from intent
        reeree ls                       # list sessions
    """
    if ctx.invoked_subcommand is not None:
        return

    project_dir = Path(project).resolve()

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
    target_str = " ".join(target) if target else ""
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
        # No target — open default plan
        plan_path = project_dir / ".reeree" / "plan.yaml"
        if plan_path.exists():
            plan = Plan.load(plan_path)
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


@main.command()
def ls():
    """List active sessions."""
    # TODO: read from daemon socket
    click.echo("Sessions: (daemon not yet implemented)")


@main.command()
def kill():
    """Kill the daemon."""
    # TODO: send kill to daemon
    click.echo("Kill: (daemon not yet implemented)")


if __name__ == "__main__":
    main()
