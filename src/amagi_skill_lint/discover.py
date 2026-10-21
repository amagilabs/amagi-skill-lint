"""Find the skill and subagent files under a set of paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".tox", "dist", "build", "site-packages", ".pytest_cache", ".mypy_cache",
}
SKIP_AGENT_FILES = {"readme.md", "changelog.md", "license.md", "contributing.md"}


@dataclass(frozen=True)
class Target:
    path: Path
    kind: str  # "skill" or "agent"


def _is_skill_file(p: Path) -> bool:
    return p.name.lower() == "skill.md"


def _inside_skill(agents_dir: Path, root: Path) -> bool:
    """True if a folder above agents_dir, still inside root, holds a SKILL.md.

    Skills sometimes keep helper prompts in their own agents/ subfolder; those
    are not Claude Code subagents.
    """
    root = root.resolve()
    cur = agents_dir.resolve().parent
    while cur == root or root in cur.parents:
        if any(_is_skill_file(c) for c in _safe_iterdir(cur)):
            return True
        if cur == root:
            break
        cur = cur.parent
    return False


def _safe_iterdir(d: Path):
    try:
        return list(d.iterdir())
    except OSError:
        return []


def _agent_candidate(p: Path) -> bool:
    name = p.name.lower()
    return (
        p.suffix.lower() == ".md"
        and p.parent.name.lower() == "agents"
        and not name.startswith(("_", "."))
        and name not in SKIP_AGENT_FILES
    )


def discover(paths: Iterable[str]) -> List[Target]:
    found = {}
    for raw in paths:
        root = Path(raw)
        if root.is_file():
            kind = "skill" if _is_skill_file(root) else "agent"
            found[root.resolve()] = Target(root, kind)
            continue
        if not root.is_dir():
            raise FileNotFoundError(raw)
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info"))
            here = Path(dirpath)
            for fn in sorted(filenames):
                p = here / fn
                if _is_skill_file(p):
                    found.setdefault(p.resolve(), Target(p, "skill"))
                elif _agent_candidate(p) and not _inside_skill(p.parent, root):
                    found.setdefault(p.resolve(), Target(p, "agent"))
    return sorted(found.values(), key=lambda t: (t.kind != "skill", str(t.path).lower()))
