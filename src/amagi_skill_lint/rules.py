"""Lint rules for Claude Code skills (SKILL.md) and subagents (agents/*.md).

Limits come from Anthropic's docs:
- Agent Skills overview (API / claude.ai uploads): name at most 64 characters of
  lowercase letters, numbers and hyphens, no "anthropic" or "claude", no XML
  tags; description non-empty, at most 1,024 characters, no XML tags.
- Claude Code skills: description + when_to_use is cut at 1,536 characters in
  the skill listing; keep SKILL.md under 500 lines.
- Claude Code subagents: name and description required, name at most 256
  characters and no ":"; model is sonnet, opus, haiku, fable, inherit or a full
  model ID.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from . import refs as refmod
from .discover import Target
from .frontmatter import Parsed, parse
from .overlap import similar_pairs

ERROR, WARNING, INFO = "error", "warning", "info"
SEVERITY_RANK = {INFO: 1, WARNING: 2, ERROR: 3}

RULES: Dict[str, tuple] = {
    "SL001": (ERROR, "no-frontmatter", "File has no YAML frontmatter block, or it is never closed with ---."),
    "SL002": (ERROR, "yaml-invalid", "Frontmatter is not valid YAML, so Claude Code cannot read name or description."),
    "SL003": (ERROR, "frontmatter-not-mapping", "Frontmatter parses, but not as key: value pairs."),
    "SL004": (ERROR, "missing-name", "Required field name is missing or empty."),
    "SL005": (ERROR, "missing-description", "Required field description is missing or empty."),
    "SL006": (WARNING, "name-not-portable", "Skill name breaks the Agent Skills spec (64 chars max, lowercase letters, numbers, hyphens)."),
    "SL007": (WARNING, "name-reserved-word", "Skill name contains a reserved word (anthropic, claude) that the Skills API rejects."),
    "SL008": (ERROR, "name-invalid", "Name holds characters Claude Code refuses (<, >, control characters; ':' in agent names) or is too long."),
    "SL009": (WARNING, "name-folder-mismatch", "Skill name differs from its folder name."),
    "SL010": (WARNING, "key-typo", "Frontmatter key looks like a misspelled known key, so it is ignored."),
    "SL011": (WARNING, "bad-field-value", "A known frontmatter field has a value Claude Code does not accept."),
    "SL012": (WARNING, "duplicate-key", "Frontmatter repeats a key; only the last value is kept."),
    "SL020": (ERROR, "description-truncated", "Skill description (+ when_to_use) is over 1,536 characters and gets cut off in the skill listing."),
    "SL021": (WARNING, "description-over-api-limit", "Description is over 1,024 characters, the limit for API and claude.ai skill uploads."),
    "SL022": (WARNING, "description-too-short", "Description is too short to tell Claude when to pick this over anything else."),
    "SL023": (WARNING, "no-trigger-cue", "Description says what it does but not when to use it."),
    "SL024": (WARNING, "first-person", "Description is written in first or second person; Anthropic recommends third person."),
    "SL025": (WARNING, "xml-in-description", "Skill description contains XML tags, which the Agent Skills spec forbids."),
    "SL026": (INFO, "vague-wording", "Description leans on vague words that do not help Claude choose."),
    "SL030": (WARNING, "body-too-many-lines", "SKILL.md is over the line budget (Anthropic suggests under 500)."),
    "SL031": (WARNING, "body-too-many-tokens", "Body is over the token budget for one file loaded on trigger."),
    "SL040": (ERROR, "broken-link", "Markdown link points to a file that does not exist."),
    "SL041": (WARNING, "missing-file-mention", "Body mentions a bundled file path (scripts/, references/, ...) that does not exist."),
    "SL042": (WARNING, "machine-specific-path", "Absolute or user-specific path that breaks on anyone else's machine."),
    "SL043": (WARNING, "backslash-path", "Link uses Windows backslashes; use forward slashes so it works everywhere."),
    "SL050": (ERROR, "duplicate-name", "Two files declare the same name; which one Claude Code loads is undefined."),
    "SL051": (WARNING, "overlapping-descriptions", "Two descriptions share most of their distinctive words, so the wrong one can fire."),
}

SKILL_KEYS = [
    "name", "description", "when_to_use", "disable-model-invocation", "user-invocable", "allowed-tools",
    "disallowed-tools", "argument-hint", "arguments", "model", "effort", "context", "agent", "background",
    "shell", "paths", "hooks", "metadata", "license", "compatibility", "version",
]
AGENT_KEYS = [
    "name", "description", "tools", "disallowedTools", "model", "permissionMode", "maxTurns",
    "autoCompactWindow", "skills", "mcpServers", "hooks", "memory", "background", "omitClaudeMd", "effort",
    "isolation", "color", "initialPrompt", "experimental",
]
MODEL_ALIASES = {"sonnet", "opus", "haiku", "fable", "inherit"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
COLORS = {"red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"}
PERMISSION_MODES = {"default", "acceptEdits", "auto", "dontAsk", "bypassPermissions", "plan", "manual"}
MEMORY_SCOPES = {"user", "project", "local"}
SKILL_BOOL_KEYS = ("disable-model-invocation", "user-invocable", "background")
AGENT_BOOL_KEYS = ("background", "omitClaudeMd")

TRIGGER_RE = re.compile(
    r"\b(use (it |this |me )?(when|whenever|for|if|to|on|after|before|in)|use proactively|when (the |a |you|someone|working|asked|ask)"
    r"|whenever|trigger|invoke|if the user|if you|asks? (for|to|about)|for (requests|tasks|questions|any)|before (any|you|writing|starting)"
    r"|must be used|use only|do not use|don't use|applies (when|to)|for when|activate (for|when|on|whenever)|(best|ideal|good) for)\b",
    re.I,
)
FIRST_PERSON_RE = re.compile(r"^\s*(i|i'm|i am|i can|i will|i'll|we|we can|you can|you should|let me)\b|\b(i can help|i will help|i'll help|helps you)\b", re.I)
XML_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9_-]*(\s[^<>]*)?/?>")
VAGUE_RE = re.compile(r"\b(helps? with|various|miscellaneous|misc\b|stuff|and more|and so on|general utilit(y|ies)|all kinds of)", re.I)
PORTABLE_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
BAD_NAME_CHARS_RE = re.compile("[<>\x00-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069\u00a0]")
DISABLE_RE = re.compile(r"skill-lint-disable[:=\s]+((?:SL\d{3}[\s,]*)+)")


@dataclass
class Config:
    max_lines: int = 500
    max_tokens: int = 5000
    min_description: int = 40
    overlap_threshold: float = 0.4
    ignore: Sequence[str] = ()
    select: Sequence[str] = ()


@dataclass
class Finding:
    rule: str
    path: Path
    line: int
    message: str
    severity: str = ""

    def __post_init__(self):
        if not self.severity:
            self.severity = RULES[self.rule][0]

    @property
    def slug(self) -> str:
        return RULES[self.rule][1]


@dataclass
class FileResult:
    target: Target
    parsed: Parsed
    name: Optional[str] = None
    trigger_text: str = ""
    model_invocable: bool = True
    body_tokens: int = 0
    body_lines: int = 0
    listing_tokens: int = 0
    disabled: set = field(default_factory=set)
    findings: List[Finding] = field(default_factory=list)

    @property
    def path(self) -> Path:
        return self.target.path

    @property
    def kind(self) -> str:
        return self.target.kind


def est_tokens(text: str) -> int:
    """Rough token estimate: characters / 4."""
    return (len(text) + 3) // 4


def _str(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, (list, dict)):
        return None
    return str(v).strip()


def lint_file(target: Target, cfg: Config) -> FileResult:
    try:
        raw = target.path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        p = parse("")
        r = FileResult(target, p)
        r.findings.append(Finding("SL001", target.path, 1, f"cannot read file: {exc}"))
        return r
    p = parse(raw)
    r = FileResult(target, p)
    r.disabled = {c for m in DISABLE_RE.finditer(p.text) for c in re.findall(r"SL\d{3}", m.group(1))}
    add = r.findings.append
    path = target.path
    is_skill = target.kind == "skill"

    r.body_lines = len(p.text.split("\n")) if is_skill else len(p.body.split("\n"))
    r.body_tokens = est_tokens(p.body)

    if not p.has_frontmatter:
        add(Finding("SL001", path, 1, "no frontmatter: the file must start with a --- line, then name: and description:"))
    elif not p.closed:
        add(Finding("SL001", path, 1, "frontmatter opened with --- but never closed with a second --- line"))
    elif p.yaml_error:
        hint = ""
        if "mapping values are not allowed" in p.yaml_error:
            hint = ' -- a value contains ": "; wrap the whole value in quotes, e.g. description: "..."'
        add(Finding("SL002", path, p.yaml_error_line or 1, f"frontmatter is not valid YAML: {p.yaml_error}{hint}"))
    elif p.data is not None and not isinstance(p.data, dict):
        add(Finding("SL003", path, p.fm_start + 1, f"frontmatter parsed as {type(p.data).__name__}, expected key: value pairs"))

    fm = p.mapping
    for key, line in p.duplicates:
        add(Finding("SL012", path, line, f"key '{key}' appears more than once; the last value wins"))

    usable = p.closed and not p.yaml_error and (p.data is None or isinstance(p.data, dict))
    if usable:
        _check_fields(r, fm, cfg)

    if is_skill and r.body_lines > cfg.max_lines:
        add(Finding("SL030", path, 1, f"SKILL.md is {r.body_lines} lines (budget {cfg.max_lines}); move detail into reference files"))
    if r.body_tokens > cfg.max_tokens:
        add(Finding("SL031", path, p.body_start, f"body is ~{r.body_tokens:,} tokens (budget {cfg.max_tokens:,}); it all loads when this fires"))

    _check_refs(r)
    r.findings = [f for f in r.findings if _enabled(f.rule, cfg, r.disabled)]
    return r


def _enabled(rule: str, cfg: Config, disabled: set) -> bool:
    if rule in disabled or rule in cfg.ignore:
        return False
    return not cfg.select or rule in cfg.select


def _check_fields(r: FileResult, fm: Dict[str, Any], cfg: Config) -> None:
    add = r.findings.append
    path, p = r.path, r.parsed
    is_skill = r.kind == "skill"
    known = SKILL_KEYS if is_skill else AGENT_KEYS
    line_of = lambda k: p.key_lines.get(k, p.fm_start + 1)  # noqa: E731

    for key in fm:
        k = str(key)
        if k in known:
            continue
        close = difflib.get_close_matches(k, known, n=1, cutoff=0.8)
        if not close:
            close = [c for c in known if c.lower().replace("_", "-") == k.lower().replace("_", "-")]
        if close:
            add(Finding("SL010", path, line_of(k), f"unknown key '{k}' -- did you mean '{close[0]}'? Claude Code ignores it as written"))

    name = _str(fm.get("name"))
    if not name:
        add(Finding("SL004", path, line_of("name"), "missing 'name'" if "name" not in fm else "'name' is empty"))
    else:
        r.name = name
        bad = BAD_NAME_CHARS_RE.search(name)
        if bad or name != name.strip():
            add(Finding("SL008", path, line_of("name"), f"name {name!r} contains a character Claude Code rejects ({bad.group(0)!r})" if bad else f"name {name!r} has leading/trailing spaces"))
        if is_skill:
            if not PORTABLE_NAME_RE.match(name) or len(name) > 64:
                why = f"{len(name)} characters (max 64)" if len(name) > 64 else "use only lowercase letters, numbers and single hyphens"
                add(Finding("SL006", path, line_of("name"), f"name '{name}' is not portable to the Skills API / claude.ai: {why}"))
            low = name.lower()
            for word in ("anthropic", "claude"):
                if word in low:
                    add(Finding("SL007", path, line_of("name"), f"name '{name}' contains the reserved word '{word}'; the Skills API rejects it (Claude Code accepts it)"))
            folder = r.path.parent.name
            if folder and folder.lower() != name.lower() and r.path.name.lower() == "skill.md":
                add(Finding("SL009", path, line_of("name"), f"name '{name}' differs from folder '{folder}'; people will look for one and find the other"))
        else:
            if ":" in name:
                add(Finding("SL008", path, line_of("name"), f"agent name '{name}' contains ':', which Claude Code reserves for plugin-scoped names"))
            if len(name) > 256:
                add(Finding("SL008", path, line_of("name"), f"agent name is {len(name)} characters (max 256)"))

    desc_raw = fm.get("description")
    desc = _str(desc_raw) or ""
    if not desc:
        add(Finding("SL005", path, line_of("description"), "missing 'description'" if "description" not in fm else "'description' is empty"))
    when = _str(fm.get("when_to_use")) or "" if is_skill else ""
    trigger = (desc + " " + when).strip()
    r.trigger_text = trigger
    if is_skill and fm.get("disable-model-invocation") is True:
        r.model_invocable = False
    if trigger and r.model_invocable:
        r.listing_tokens = est_tokens((name or "") + ": " + trigger)

    if desc:
        dl = line_of("description")
        combined = len(desc) + (len(when) + 1 if when else 0)
        if is_skill and combined > 1536:
            add(Finding("SL020", path, dl, f"description{' + when_to_use' if when else ''} is {combined:,} characters; Claude Code cuts the listing at 1,536"))
        elif len(desc) > 1024:
            sev = WARNING if is_skill else INFO
            extra = "" if is_skill else " (agents have no hard limit, but every character sits in the Agent tool listing)"
            add(Finding("SL021", path, dl, f"description is {len(desc):,} characters, over the 1,024 limit for API/claude.ai skills{extra}", sev))
        if len(trigger) < cfg.min_description:
            add(Finding("SL022", path, dl, f"description is {len(trigger)} characters; say what it does and when to use it (aim for {cfg.min_description}+)"))
        elif r.model_invocable and not TRIGGER_RE.search(trigger):
            add(Finding("SL023", path, dl, "description has no 'use when ...' style cue; add when Claude should pick it (e.g. 'Use when the user asks to ...')",
                        WARNING if is_skill else INFO))
        if FIRST_PERSON_RE.search(desc):
            add(Finding("SL024", path, dl, "description reads as first/second person ('I can...', 'You can...'); write 'Extracts...', 'Use when...'"))
        if is_skill and XML_RE.search(desc):
            add(Finding("SL025", path, dl, f"description contains an XML tag {XML_RE.search(desc).group(0)!r}; the Agent Skills spec forbids them"))
        m = VAGUE_RE.search(desc)
        if m:
            add(Finding("SL026", path, dl, f"vague wording '{m.group(0)}'; name the concrete inputs, outputs or file types instead"))
    elif desc_raw is not None and isinstance(desc_raw, (list, dict)):
        add(Finding("SL011", path, line_of("description"), "description must be a string, not a list or mapping"))

    _check_values(r, fm, line_of)


def _check_values(r: FileResult, fm: Dict[str, Any], line_of) -> None:
    add = r.findings.append
    path = r.path
    is_skill = r.kind == "skill"

    model = fm.get("model")
    if model is not None:
        ms = str(model).strip()
        if ms not in MODEL_ALIASES and not ms.startswith("claude-"):
            add(Finding("SL011", path, line_of("model"), f"model '{ms}' is not sonnet, opus, haiku, fable, inherit or a full claude-* model ID"))
    effort = fm.get("effort")
    if effort is not None and str(effort) not in EFFORTS:
        add(Finding("SL011", path, line_of("effort"), f"effort '{effort}' should be one of {', '.join(sorted(EFFORTS))}"))
    for key in (SKILL_BOOL_KEYS if is_skill else AGENT_BOOL_KEYS):
        if key in fm and not isinstance(fm[key], bool):
            add(Finding("SL011", path, line_of(key), f"'{key}' should be true or false, got {fm[key]!r}"))
    if is_skill:
        ctx = fm.get("context")
        if ctx is not None and str(ctx) != "fork":
            add(Finding("SL011", path, line_of("context"), f"context '{ctx}' is not recognised (Claude Code supports 'fork')"))
        return
    color = fm.get("color")
    if color is not None and str(color) not in COLORS:
        add(Finding("SL011", path, line_of("color"), f"color '{color}' should be one of {', '.join(sorted(COLORS))}"))
    pm = fm.get("permissionMode")
    if pm is not None and str(pm) not in PERMISSION_MODES:
        add(Finding("SL011", path, line_of("permissionMode"), f"permissionMode '{pm}' should be one of {', '.join(sorted(PERMISSION_MODES))}"))
    mem = fm.get("memory")
    if mem is not None and str(mem) not in MEMORY_SCOPES:
        add(Finding("SL011", path, line_of("memory"), f"memory '{mem}' should be user, project or local"))
    tools = fm.get("tools")
    if tools is not None:
        if isinstance(tools, str):
            items = [t.strip() for t in tools.split(",")]
        elif isinstance(tools, list):
            items = [str(t).strip() for t in tools]
        else:
            items = None
            add(Finding("SL011", path, line_of("tools"), "tools should be a comma-separated string or a YAML list"))
        if items is not None and not any(items):
            add(Finding("SL011", path, line_of("tools"), "tools is empty; the subagent would launch with zero tools (omit the field to inherit all)"))
    mt = fm.get("maxTurns")
    if mt is not None and (isinstance(mt, bool) or not isinstance(mt, int) or mt < 1):
        add(Finding("SL011", path, line_of("maxTurns"), f"maxTurns should be a positive whole number, got {mt!r}"))


def _check_refs(r: FileResult) -> None:
    p = r.parsed
    if not p.closed and p.has_frontmatter:
        return
    base = r.path.parent
    add = r.findings.append
    seen = set()
    for ref in refmod.extract(p.body, p.body_start):
        key = (ref.target, ref.line)
        if key in seen:
            continue
        seen.add(key)
        if ref.kind == "link":
            kind = refmod.classify_link(ref.target)
            if kind is None:
                continue
            if kind == "abs":
                add(Finding("SL042", r.path, ref.line, f"link to absolute path '{ref.target}' only works on this machine; ship the file and link it relatively"))
                continue
            if kind == "backslash":
                add(Finding("SL043", r.path, ref.line, f"link '{ref.target}' uses backslashes; use '{ref.target.replace(chr(92), '/')}'"))
            if not refmod.resolve(base, ref.target).exists():
                add(Finding("SL040", r.path, ref.line, f"link target '{ref.target}' does not exist (relative to {base.name}/)"))
        else:
            if not refmod.mention_should_check(base, ref.target, ref.in_code):
                continue
            if not refmod.resolve(base, ref.target).exists():
                where = " (in a code block)" if ref.in_code else ""
                add(Finding("SL041", r.path, ref.line, f"'{ref.target}'{where} is not in the {r.kind} folder"))
    flagged = {f.line for f in r.findings if f.rule == "SL042"}
    for line, path in refmod.machine_paths(p.body, p.body_start):
        if line in flagged:
            continue
        add(Finding("SL042", r.path, line, f"machine-specific path '{path}...' will not exist for anyone else"))


@dataclass
class OverlapResult:
    a: FileResult
    b: FileResult
    score: float
    shared: List[str]


def lint_set(targets: Sequence[Target], cfg: Config):
    results = [lint_file(t, cfg) for t in targets]
    overlaps: List[OverlapResult] = []
    for kind in ("skill", "agent"):
        group = [r for r in results if r.kind == kind]
        by_name: Dict[str, List[FileResult]] = {}
        for r in group:
            if r.name:
                by_name.setdefault(r.name.lower(), []).append(r)
        for name, rs in by_name.items():
            if len(rs) < 2:
                continue
            for r in rs:
                others = ", ".join(o.path.as_posix() for o in rs if o is not r)
                f = Finding("SL050", r.path, r.parsed.key_lines.get("name", 2), f"{kind} name '{r.name}' is also declared in {others}")
                if _enabled("SL050", cfg, r.disabled):
                    r.findings.append(f)
        cands = [r for r in group if r.trigger_text and r.model_invocable]
        if len(cands) < 2 or not _enabled("SL051", cfg, set()):
            continue
        for pair in similar_pairs([c.trigger_text for c in cands], cfg.overlap_threshold):
            a, b = cands[pair.a], cands[pair.b]
            if "SL051" in a.disabled or "SL051" in b.disabled:
                continue
            if a.name and b.name and a.name.lower() == b.name.lower():
                continue
            overlaps.append(OverlapResult(a, b, pair.score, pair.shared))
            for x, y in ((a, b), (b, a)):
                x.findings.append(Finding(
                    "SL051", x.path, x.parsed.key_lines.get("description", 2),
                    f"description overlaps {y.kind} '{y.name or y.path}' ({pair.score:.2f}); shared words: {', '.join(pair.shared)}",
                ))
    for r in results:
        r.findings.sort(key=lambda f: (f.line, -SEVERITY_RANK[f.severity], f.rule))
    return results, overlaps
