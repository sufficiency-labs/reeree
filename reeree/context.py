"""Context management — load only what's needed for the current step."""

from pathlib import Path
from .plan import Step


def gather_context(step: Step, project_dir: Path, max_chars: int = 80000) -> str:
    """Build a focused context string for one step.

    Instead of loading the entire repo into context (the 200K crutch),
    we load only the files relevant to this specific step.
    """
    parts = []
    total = 0

    # Always include project-level context if it exists
    for ctx_file in ["CLAUDE.md", "README.md", ".reeree/config.json"]:
        p = project_dir / ctx_file
        if p.exists():
            content = p.read_text()
            if total + len(content) < max_chars:
                parts.append(f"=== {ctx_file} ===\n{content}")
                total += len(content)

    # Load files specified in the step
    for file_path in step.files:
        p = project_dir / file_path
        if p.exists() and p.is_file():
            content = p.read_text()
            if total + len(content) < max_chars:
                parts.append(f"=== {file_path} ===\n{content}")
                total += len(content)
            else:
                # Truncate if too large
                remaining = max_chars - total
                if remaining > 500:
                    parts.append(f"=== {file_path} (truncated) ===\n{content[:remaining]}")
                    total = max_chars
                break

    return "\n\n".join(parts)


def find_relevant_files(description: str, project_dir: Path, max_files: int = 10) -> list[str]:
    """Heuristically find files that might be relevant to a step description.

    This is a simple keyword-based search. The LLM can refine the list.
    """
    results = []
    keywords = [w.lower() for w in description.split() if len(w) > 3]

    for p in sorted(project_dir.rglob("*")):
        if not p.is_file():
            continue
        if any(part.startswith(".") for part in p.parts):
            continue
        if p.suffix in (".pyc", ".pyo", ".so", ".o", ".class"):
            continue

        name_lower = p.name.lower()
        rel = str(p.relative_to(project_dir))

        # Check if any keyword appears in the filename or path
        if any(kw in name_lower or kw in rel.lower() for kw in keywords):
            results.append(rel)
            if len(results) >= max_files:
                break

    return results
