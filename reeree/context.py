"""Context management — load only what's needed for the current step.

Cross-reference following: documents link to each other via markdown links
and ## Related sections. We parse those links, resolve paths, and load
referenced files into context within the char budget.
"""

import re
import subprocess
from pathlib import Path
from .plan import Step


# Markdown link pattern: [text](path) — relative paths only, not URLs
_LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')

# Related section pattern: ## Related People, ## Related Ideas, etc.
_RELATED_SECTION_RE = re.compile(r'^##\s+Related\s+', re.MULTILINE)


def _find_parent_contexts(project_dir: Path) -> list[tuple[str, str]]:
    """Walk up from project_dir to find parent repo CLAUDE.md files.

    Enables subrepo telescoping: working in private/kingfall still gets
    vorkosigan-level context. Stops at filesystem root or after 5 levels.
    """
    results = []
    current = project_dir.resolve().parent
    levels = 0

    while current != current.parent and levels < 5:
        # Check if this directory is a git repo root
        if (current / ".git").exists() or (current / ".git").is_file():
            claude_md = current / "CLAUDE.md"
            if claude_md.exists():
                label = f"parent:{current.name}/CLAUDE.md"
                results.append((label, claude_md.read_text()))
        current = current.parent
        levels += 1

    return results


def extract_cross_references(text: str, base_dir: Path) -> list[Path]:
    """Extract resolvable file paths from markdown cross-references.

    Finds:
    - [text](relative/path) markdown links (skips URLs, anchors)
    - Paths in ## Related * sections

    Returns resolved Paths that exist on disk.
    """
    refs = []
    seen = set()

    for match in _LINK_RE.finditer(text):
        link_target = match.group(2).strip()

        # Skip URLs, anchors, images
        if link_target.startswith(("http://", "https://", "#", "mailto:")):
            continue

        # Strip anchor from path (e.g., "file.md#section")
        path_part = link_target.split("#")[0]
        if not path_part:
            continue

        resolved = (base_dir / path_part).resolve()

        # If it's a directory, look for README.md inside it
        if resolved.is_dir():
            readme = resolved / "README.md"
            if readme.exists():
                resolved = readme

        if resolved.is_file() and str(resolved) not in seen:
            seen.add(str(resolved))
            refs.append(resolved)

    return refs


def gather_context(step: Step, project_dir: Path, max_chars: int = 80000,
                   follow_references: bool = True) -> str:
    """Build a focused context string for one step.

    Instead of loading the entire repo into context (the 200K crutch),
    we load only the files relevant to this specific step.

    When follow_references=True, also follows markdown links in loaded
    documents (one level deep) to pull in cross-referenced files.
    """
    parts = []
    total = 0
    loaded_paths: set[str] = set()  # track what's loaded to avoid duplicates

    def _add_content(label: str, content: str, path: str = "") -> bool:
        """Add content if within budget. Returns True if added."""
        nonlocal total
        if path and path in loaded_paths:
            return False
        if total + len(content) >= max_chars:
            return False
        parts.append(f"=== {label} ===\n{content}")
        total += len(content)
        if path:
            loaded_paths.add(path)
        return True

    # Walk up to find parent repo context (subrepo telescoping)
    parent_contexts = _find_parent_contexts(project_dir)
    for label, content in parent_contexts:
        _add_content(label, content)

    # Project-level context — collect for cross-reference scanning
    project_files_content: list[tuple[str, str, Path]] = []
    for ctx_file in ["CLAUDE.md", "README.md", ".reeree/config.json"]:
        p = project_dir / ctx_file
        if p.exists():
            content = p.read_text()
            if _add_content(ctx_file, content, str(p.resolve())):
                project_files_content.append((ctx_file, content, p))

    # Load files specified in the step
    step_files_content: list[tuple[str, str, Path]] = []
    for file_path in step.files:
        p = project_dir / file_path
        if p.exists() and p.is_file():
            content = p.read_text()
            if total + len(content) < max_chars:
                if _add_content(file_path, content, str(p.resolve())):
                    step_files_content.append((file_path, content, p))
            else:
                remaining = max_chars - total
                if remaining > 500:
                    parts.append(f"=== {file_path} (truncated) ===\n{content[:remaining]}")
                    total = max_chars
                    loaded_paths.add(str(p.resolve()))
                break

    # Cross-reference following — one level deep
    if follow_references and total < max_chars:
        # Budget for cross-references: up to 25% of remaining space
        xref_budget = (max_chars - total) // 4

        all_loaded = project_files_content + step_files_content
        xref_total = 0

        for label, content, file_path in all_loaded:
            if xref_total >= xref_budget:
                break

            refs = extract_cross_references(content, file_path.parent)
            for ref_path in refs:
                if xref_total >= xref_budget:
                    break
                if str(ref_path) in loaded_paths:
                    continue
                try:
                    ref_content = ref_path.read_text()
                except Exception:
                    continue

                # Cap individual cross-ref files at 5K chars
                if len(ref_content) > 5000:
                    ref_content = ref_content[:5000] + "\n... (truncated)"

                ref_label = f"xref:{ref_path.name}"
                if _add_content(ref_label, ref_content, str(ref_path)):
                    xref_total += len(ref_content)

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
