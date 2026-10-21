"""Command-line entry point: amagi-skill-lint [PATH ...]."""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import List, Optional

from . import __version__
from .discover import discover
from .report import render_github, render_json, render_rules, render_text
from .rules import RULES, SEVERITY_RANK, Config, lint_set

EXIT_OK, EXIT_FINDINGS, EXIT_USAGE = 0, 1, 2


def _rule_list(value: str) -> List[str]:
    ids = [v.strip().upper() for v in re.split(r"[,\s]+", value) if v.strip()]
    unknown = [i for i in ids if i not in RULES]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown rule id(s): {', '.join(unknown)} (see --list-rules)")
    return ids


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="amagi-skill-lint",
        description=(
            "Lint Claude Code skills (SKILL.md) and subagents (agents/*.md): frontmatter, description "
            "triggers, token size, broken file references, and descriptions that overlap enough to make "
            "the wrong one fire."
        ),
        epilog="Exit codes: 0 clean, 1 findings at or above --fail-on, 2 usage error or nothing to lint.",
    )
    p.add_argument("paths", nargs="*", default=["."], help="skill folders, agents folders, single .md files, or a repo root (default: .)")
    p.add_argument("--format", choices=["text", "json", "github"], default="text", help="output format (github = Actions annotations)")
    p.add_argument("--fail-on", choices=["error", "warning", "info", "never"], default="error", help="lowest severity that makes the exit code 1 (default: error)")
    p.add_argument("--ignore", type=_rule_list, default=[], metavar="IDS", help="comma-separated rule IDs to skip, e.g. SL042,SL026")
    p.add_argument("--select", type=_rule_list, default=[], metavar="IDS", help="run only these rule IDs")
    p.add_argument("--overlap", type=float, default=0.4, metavar="SCORE", help="similarity (0-1) at which two descriptions count as overlapping (default: 0.4)")
    p.add_argument("--max-lines", type=int, default=500, metavar="N", help="SKILL.md line budget (default: 500)")
    p.add_argument("--max-tokens", type=int, default=5000, metavar="N", help="body token budget, chars/4 estimate (default: 5000)")
    p.add_argument("--min-description", type=int, default=40, metavar="N", help="shortest acceptable description in characters (default: 40)")
    p.add_argument("--quiet", action="store_true", help="text format: skip the token summary lines")
    p.add_argument("--no-color", action="store_true", help="disable ANSI colour (also honours NO_COLOR)")
    p.add_argument("--list-rules", action="store_true", help="print every rule ID and exit")
    p.add_argument("--version", action="version", version=f"amagi-skill-lint {__version__}")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_rules:
        print(render_rules())
        return EXIT_OK
    if not 0 < args.overlap <= 1:
        parser.error("--overlap must be between 0 and 1")
    if args.max_lines < 1 or args.max_tokens < 1 or args.min_description < 0:
        parser.error("--max-lines and --max-tokens must be positive, --min-description zero or more")

    try:
        targets = discover(args.paths)
    except FileNotFoundError as exc:
        print(f"amagi-skill-lint: path not found: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if not targets:
        print(
            "amagi-skill-lint: no SKILL.md or agents/*.md files found under " + ", ".join(args.paths),
            file=sys.stderr,
        )
        return EXIT_USAGE

    cfg = Config(
        max_lines=args.max_lines,
        max_tokens=args.max_tokens,
        min_description=args.min_description,
        overlap_threshold=args.overlap,
        ignore=args.ignore,
        select=args.select,
    )
    results, overlaps = lint_set(targets, cfg)

    if args.format == "json":
        print(render_json(results, overlaps))
    elif args.format == "github":
        print(render_github(results))
    else:
        color = not args.no_color and "NO_COLOR" not in os.environ and sys.stdout.isatty()
        print(render_text(results, overlaps, color=color, quiet=args.quiet))

    if args.fail_on == "never":
        return EXIT_OK
    floor = SEVERITY_RANK[args.fail_on]
    worst = max((SEVERITY_RANK[f.severity] for r in results for f in r.findings), default=0)
    return EXIT_FINDINGS if worst >= floor else EXIT_OK
