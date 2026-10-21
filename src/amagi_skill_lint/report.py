"""Render lint results as text, JSON, or GitHub Actions annotations."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Sequence

from . import __version__
from .rules import ERROR, INFO, RULES, WARNING, FileResult, OverlapResult

COLORS = {ERROR: "\033[31m", WARNING: "\033[33m", INFO: "\033[36m", "dim": "\033[2m", "bold": "\033[1m", "reset": "\033[0m"}


def display_path(p: Path) -> str:
    try:
        rel = os.path.relpath(p)
        if not rel.startswith(".."):
            return rel.replace("\\", "/")
    except ValueError:
        pass
    return str(p).replace("\\", "/")


def counts(results: Sequence[FileResult]) -> dict:
    c = {ERROR: 0, WARNING: 0, INFO: 0}
    for r in results:
        for f in r.findings:
            c[f.severity] += 1
    return c


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def render_text(results: Sequence[FileResult], overlaps: Sequence[OverlapResult], color: bool = False, quiet: bool = False) -> str:
    def c(key: str, s: str) -> str:
        return f"{COLORS[key]}{s}{COLORS['reset']}" if color else s

    out: List[str] = []
    for r in results:
        if not r.findings:
            continue
        out.append(c("bold", display_path(r.path)) + c("dim", f"  ({r.kind})"))
        for f in r.findings:
            out.append(f"  {f.line:>4}  {c(f.severity, f'{f.severity:<7}')}  {f.rule}  {f.message}")
        out.append("")
    if overlaps:
        out.append(c("bold", "Overlapping descriptions") + c("dim", "  (pairs most likely to fire for each other's prompts)"))
        for o in overlaps:
            out.append(f"  {o.score:.2f}  {o.a.name or display_path(o.a.path)}  <->  {o.b.name or display_path(o.b.path)}   shared: {', '.join(o.shared)}")
        out.append("")
    if not quiet:
        skills = [r for r in results if r.kind == "skill"]
        agents = [r for r in results if r.kind == "agent"]
        parts = [_plural(len(g), label) for label, g in (("skill", skills), ("agent", agents)) if g]
        tok = sum(r.listing_tokens for r in results)
        out.append(f"Checked {' and '.join(parts)}. Their names + descriptions cost ~{tok:,} tokens in every session.")
        heavy = sorted((r for r in results if r.body_tokens), key=lambda r: -r.body_tokens)[:3]
        if heavy:
            out.append("Largest bodies: " + ", ".join(f"{r.name or display_path(r.path)} ~{r.body_tokens:,}" for r in heavy) + " tokens.")
    n = counts(results)
    files_with = sum(1 for r in results if r.findings)
    if sum(n.values()) == 0:
        out.append(c("bold", "No problems found."))
    else:
        out.append(
            c("bold", f"{_plural(n[ERROR], 'error')}, {_plural(n[WARNING], 'warning')}, {n[INFO]} info")
            + f" in {_plural(files_with, 'file')}."
        )
    return "\n".join(out)


def render_json(results: Sequence[FileResult], overlaps: Sequence[OverlapResult]) -> str:
    data = {
        "tool": "amagi-skill-lint",
        "version": __version__,
        "files": [
            {
                "path": display_path(r.path),
                "kind": r.kind,
                "name": r.name,
                "listing_tokens": r.listing_tokens,
                "body_tokens": r.body_tokens,
                "body_lines": r.body_lines,
                "findings": [
                    {"rule": f.rule, "slug": f.slug, "severity": f.severity, "line": f.line, "message": f.message}
                    for f in r.findings
                ],
            }
            for r in results
        ],
        "overlaps": [
            {"a": display_path(o.a.path), "b": display_path(o.b.path), "score": o.score, "shared": o.shared}
            for o in overlaps
        ],
        "summary": counts(results),
    }
    return json.dumps(data, indent=2)


def _gh_escape(s: str) -> str:
    return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def render_github(results: Sequence[FileResult]) -> str:
    level = {ERROR: "error", WARNING: "warning", INFO: "notice"}
    lines = []
    for r in results:
        for f in r.findings:
            path = display_path(r.path).replace(",", "%2C").replace(":", "%3A")
            lines.append(f"::{level[f.severity]} file={path},line={f.line},title={f.rule} {f.slug}::{_gh_escape(f.message)}")
    n = counts(results)
    lines.append(f"amagi-skill-lint: {n[ERROR]} errors, {n[WARNING]} warnings, {n[INFO]} info")
    return "\n".join(lines)


def render_rules() -> str:
    lines = [f"{'ID':<6} {'severity':<8} {'slug':<28} what it catches"]
    for rid, (sev, slug, desc) in RULES.items():
        lines.append(f"{rid:<6} {sev:<8} {slug:<28} {desc}")
    return "\n".join(lines)
