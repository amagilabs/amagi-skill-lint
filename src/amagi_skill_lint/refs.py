"""Find file references in a skill or agent body and check that they exist."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote

# Folders a skill conventionally ships next to SKILL.md.
CONVENTIONAL_DIRS = ("scripts", "references", "reference", "assets", "templates", "examples", "resources", "docs")

FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^)\s]+)(?:\s+[\"'(][^\n]*?[\"')])?\s*\)")
REF_DEF_RE = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|\S+)", re.M)
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]+:")
WIN_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")
PATH_MENTION_RE = re.compile(
    r"(?<![\w./$\\-])(?:\$\{?CLAUDE_SKILL_DIR\}?/|\./)?((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,8})(?![\w/])"
)
MACHINE_PATH_RE = re.compile(
    r"(?<![\w])(?:[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s`'\"]+|/Users/[^/\s`'\"]+|/home/[^/\s`'\"]+)(?=[\\/])"
)


@dataclass
class Ref:
    target: str
    line: int  # 1-based file line
    kind: str  # "link" or "mention"
    in_code: bool = False


def _code_mask(body: str) -> List[bool]:
    mask = []
    in_code = False
    for line in body.split("\n"):
        if FENCE_RE.match(line):
            mask.append(True)
            in_code = not in_code
            continue
        mask.append(in_code)
    return mask


def _strip_inline_code_spans(line: str) -> str:
    return re.sub(r"`[^`]*`", lambda m: " " * len(m.group(0)), line)


def extract(body: str, body_start: int) -> List[Ref]:
    refs: List[Ref] = []
    mask = _code_mask(body)
    for i, line in enumerate(body.split("\n")):
        lineno = body_start + i
        in_code = mask[i]
        if not in_code:
            prose = _strip_inline_code_spans(line)
            for m in INLINE_LINK_RE.finditer(prose):
                refs.append(Ref(m.group(1).strip("<>"), lineno, "link"))
            for m in REF_DEF_RE.finditer(prose):
                refs.append(Ref(m.group(1).strip("<>"), lineno, "link"))
        link_spans = [] if in_code else [m.span() for m in INLINE_LINK_RE.finditer(_strip_inline_code_spans(line))]
        for m in PATH_MENTION_RE.finditer(line):
            if any(a <= m.start() < b for a, b in link_spans):
                continue
            refs.append(Ref(m.group(1), lineno, "mention", in_code))
    return refs


def machine_paths(body: str, body_start: int) -> List[tuple]:
    out = []
    for i, line in enumerate(body.split("\n")):
        for m in MACHINE_PATH_RE.finditer(line):
            out.append((body_start + i, m.group(0)))
    return out


def classify_link(target: str) -> Optional[str]:
    """Return None for links we do not check (URLs, anchors), else 'abs', 'backslash' or 'rel'."""
    if not target or target.startswith("#"):
        return None
    if WIN_ABS_RE.match(target) or target.startswith(("/", "~", "\\")):
        return "abs"
    if SCHEME_RE.match(target):
        return None
    if "{" in target or "$" in target:
        return None
    if "\\" in target:
        return "backslash"
    return "rel"


def resolve(base: Path, target: str) -> Path:
    clean = unquote(target.split("#", 1)[0].split("?", 1)[0]).replace("\\", "/")
    return base / clean


def mention_should_check(base: Path, rel: str, in_code: bool) -> bool:
    """Decide whether a bare path mention is a claim about the skill's own files.

    Outside code blocks: paths under a conventional skill folder (scripts/,
    references/, ...) or under any folder that exists next to SKILL.md.
    Inside code blocks only paths under a conventional folder that exists,
    since commands there often name the user's own project files.
    """
    first = rel.split("/", 1)[0]
    if first.startswith("."):
        return False
    conventional = first.lower() in CONVENTIONAL_DIRS
    exists = (base / first).is_dir()
    if in_code:
        return conventional and exists
    return conventional or exists
