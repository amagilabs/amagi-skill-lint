---
name: amagi-skill-lint
description: The amagi-skill-lint CLI checks Claude Code SKILL.md files and subagent .md files for broken frontmatter, missing or truncated descriptions, descriptions with no "use when" cue, oversized bodies, links to files that do not exist, duplicate names, and descriptions that overlap enough to make the wrong skill fire. Use when the user wants to lint, audit or clean up a skills or agents folder, find out why a skill does not load or triggers wrongly, or add a skill check to CI.
---

# amagi-skill-lint

## When to use

- A skill or subagent does not show up, never triggers, or fires when another
  one should have.
- The user wants a whole `~/.claude/skills`, `.claude/agents` or plugin repo
  checked before sharing or committing it.
- The user wants a CI step that fails on broken skills.

It reads files only. No network, no LLM calls, no API keys.

## How to invoke

```
amagi-skill-lint [PATH ...] [--format text|json|github] [--fail-on error|warning|info|never]
                 [--ignore IDS] [--select IDS] [--overlap 0.4] [--max-lines 500]
                 [--max-tokens 5000] [--min-description 40] [--quiet] [--list-rules]
```

PATH can be a skills folder, an agents folder, one `.md` file or a repo root.
Any `SKILL.md` counts as a skill; any `.md` directly inside a folder named
`agents` counts as a subagent. With no PATH it scans the current folder.

Examples:

```
amagi-skill-lint ~/.claude/skills ~/.claude/agents
amagi-skill-lint . --format github
amagi-skill-lint skills --ignore SL026 --fail-on warning
amagi-skill-lint --list-rules
```

## What to read afterward

- One block per file with problems: line number, severity, rule ID, message.
- "Overlapping descriptions": pairs of skills (or of agents) whose descriptions
  share most of their distinctive words, with the score and the shared words.
  Make each description name what sets it apart.
- The summary line: how many tokens all names and descriptions cost in every
  session, the three largest bodies, then the error/warning/info counts.
- Exit codes: 0 clean, 1 findings at or above `--fail-on` (default error),
  2 usage error or no files found.

## Fixing common findings

- SL002 yaml-invalid: a value contains `: `. Wrap the whole description in quotes.
- SL020 description-truncated: description plus when_to_use is over 1,536
  characters, so Claude Code cuts it. Move detail into the body.
- SL023 no-trigger-cue: add a sentence like "Use when the user asks to ...".
- SL040 / SL041: the body points at a file the skill does not ship.
- SL050 duplicate-name: two files declare the same name. Rename or delete one.
- To silence a rule in one file, put `<!-- skill-lint-disable SL041 -->` in it.

## Notes

- Token counts are estimates (characters / 4), not a real tokenizer.
- The overlap score is TF-IDF cosine over description words. 0.4 is the
  default; raise `--overlap` to see fewer pairs.
