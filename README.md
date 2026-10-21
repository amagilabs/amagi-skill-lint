# amagi-skill-lint

Find the skills and subagents Claude Code never loads, cuts off, or picks
by mistake, before you ship them.

![demo](assets/demo.gif)

amagi-skill-lint reads your `SKILL.md` files and `agents/*.md` files and
checks the things that fail silently: frontmatter that does not parse,
descriptions that are missing, truncated or never say when to use them,
bodies too big to load cheaply, links to files the skill does not ship,
two files claiming the same name, and descriptions so alike that the wrong
one fires.

We pointed it at a working `~/.claude` folder with 87 SKILL.md files and 87
agent files. It found:

- one skill whose frontmatter is invalid YAML, so its name and description can't be read
- one description at 1,677 characters, past the 1,536 where Claude Code cuts it off
- 14 mentions of bundled files that do not exist
- 7 pairs of descriptions close enough to fire for each other's prompts

The names and descriptions alone cost about 16,843 tokens in every session.

It reads files and nothing else: no network, no LLM calls, no API keys.

## Install

```
pipx install amagi-skill-lint
```

Python 3.9 or newer. The only dependency is PyYAML.

## Usage

```
amagi-skill-lint [PATH ...] [--format text|json|github] [--fail-on error|warning|info|never]
                 [--ignore IDS] [--select IDS] [--overlap 0.4]
                 [--max-lines 500] [--max-tokens 5000] [--min-description 40]
```

A PATH can be a skills folder, an agents folder, one `.md` file, or a repo
root. Any `SKILL.md` counts as a skill. Any `.md` directly inside a folder
named `agents` counts as a subagent. With no PATH it scans the current folder.

```
amagi-skill-lint ~/.claude/skills ~/.claude/agents
amagi-skill-lint . --fail-on warning
```

This is the real output on the demo fixture in this repo
(`tests/fixtures/demo_pack`):

```
$ amagi-skill-lint skills agents
skills/invoice-chaser/SKILL.md  (skill)
     3  error    SL002  invalid YAML: mapping values are not allowed here -- a value contains ": ", so wrap the whole value in quotes

skills/meeting-notes/SKILL.md  (skill)
     2  warning  SL006  name 'Meeting_Notes' fails the Skills API / claude.ai rule: lowercase letters, numbers, hyphens only
     2  warning  SL009  name 'Meeting_Notes' differs from its folder 'meeting-notes'
     3  warning  SL023  no 'use when ...' cue; say when Claude should pick it, e.g. 'Use when the user asks to ...'
     3  warning  SL024  first/second person ('I can...', 'You can...'); write 'Extracts...', 'Use when...'
     3  info     SL026  vague wording 'various'; name the concrete inputs, outputs or file types instead

skills/pdf-forms/SKILL.md  (skill)
     3  warning  SL051  description overlaps skill 'pdf-tables' (0.45); shared words: pdf, forms, fields, fill

skills/pdf-tables/SKILL.md  (skill)
     3  warning  SL051  description overlaps skill 'pdf-forms' (0.45); shared words: pdf, forms, fields, fill
     8  warning  SL041  'scripts/tables.py' is not in the skill folder
    10  error    SL040  link target 'reference/tables.md' does not exist (relative to pdf-tables/)

agents/code-reviewer.md  (agent)
     2  error    SL050  agent name 'code-reviewer' is also declared in agents/security-reviewer.md

agents/security-reviewer.md  (agent)
     2  error    SL005  missing 'description'
     2  error    SL050  agent name 'code-reviewer' is also declared in agents/code-reviewer.md
     3  warning  SL010  unknown key 'descripton' -- did you mean 'description'? As written it is ignored
     4  warning  SL011  model 'gpt-4' is not sonnet, opus, haiku, fable, inherit or a claude-* model ID
     5  warning  SL011  color 'teal' should be one of blue, cyan, green, orange, pink, purple, red, yellow

Overlapping descriptions  (pairs most likely to fire for each other's prompts)
  0.45  pdf-forms  <->  pdf-tables   shared: pdf, forms, fields, fill

Checked 5 skills and 2 agents. Their names + descriptions cost ~150 tokens in every session.
Largest bodies: pdf-forms ~86, pdf-tables ~43, release-notes ~34 tokens.
5 errors, 10 warnings, 1 info in 6 files.
```

Each finding gives the line, the severity, the rule ID and what to change.
The summary shows what your skill listing costs in context on every turn and
which bodies are heaviest when they load.

### Options

| Option | What it does |
|---|---|
| `--format` | `text` (default), `json`, or `github` for Actions annotations |
| `--fail-on` | Lowest severity that sets exit code 1: `error` (default), `warning`, `info`, `never` |
| `--ignore IDS` | Skip rules, e.g. `--ignore SL026,SL042` |
| `--select IDS` | Run only these rules |
| `--overlap SCORE` | Similarity from 0 to 1 at which two descriptions count as overlapping (default 0.4) |
| `--max-lines N` | SKILL.md line budget (default 500) |
| `--max-tokens N` | Body token budget, estimated as characters / 4 (default 5000) |
| `--min-description N` | Shortest acceptable description in characters (default 40) |
| `--quiet` | Leave out the token summary lines |
| `--list-rules` | Print every rule and exit |

Exit codes: 0 clean, 1 findings at or above `--fail-on`, 2 usage error or
no files found.

To switch a rule off for one file, put this comment anywhere in it:

```
<!-- skill-lint-disable SL041 SL042 -->
```

## What it checks

| ID | Severity | Catches |
|---|---|---|
| SL001 | error | No frontmatter block, or one that never closes |
| SL002 | error | Frontmatter is not valid YAML (most often an unquoted `: ` in the description) |
| SL003 | error | Frontmatter is not `key: value` pairs |
| SL004 | error | `name` missing or empty |
| SL005 | error | `description` missing or empty |
| SL006 | warning | Skill name breaks the Agent Skills rule: 64 characters max, lowercase letters, numbers, hyphens |
| SL007 | warning | Skill name contains `anthropic` or `claude`, which the Skills API rejects |
| SL008 | error | Name has characters Claude Code refuses (`<`, `>`, control characters, `:` in agent names) or is too long |
| SL009 | warning | Skill name differs from its folder name |
| SL010 | warning | Misspelled frontmatter key (`descripton`, `allowed_tools`) that gets ignored |
| SL011 | warning | Bad value for a known field: `model`, `effort`, `color`, `permissionMode`, `memory`, `tools`, booleans |
| SL012 | warning | Key repeated in the frontmatter; only the last one counts |
| SL020 | error | Skill description plus `when_to_use` over 1,536 characters, so the listing cuts it off |
| SL021 | warning | Description over 1,024 characters, the limit for API and claude.ai skill uploads |
| SL022 | warning | Description too short to choose by |
| SL023 | warning | Description says what it does but never when to use it |
| SL024 | warning | Description in first or second person ("I can help...") |
| SL025 | warning | XML tags in a skill description |
| SL026 | info | Vague wording ("various", "helps with", "and more") |
| SL030 | warning | SKILL.md over the line budget |
| SL031 | warning | Body over the token budget |
| SL040 | error | Markdown link to a file that does not exist |
| SL041 | warning | Body names a bundled file (`scripts/`, `references/`, ...) that does not exist |
| SL042 | warning | Absolute or user-specific path that only works on your machine |
| SL043 | warning | Link written with Windows backslashes |
| SL050 | error | Two skills, or two agents, declare the same name |
| SL051 | warning | Two descriptions share most of their distinctive words |

For agents, SL021 and SL023 drop to info. Agent descriptions have no hard
length limit, and many good ones describe a role without a "use when" line.

The limits come from Anthropic's Agent Skills and Claude Code docs. Overlap
is TF-IDF cosine similarity over description words, with common and
boilerplate words removed. The 0.4 default came from running it on the 87
real skills above. The pairs that scored over it were ones a person would
mix up too.

## Use it in CI

GitHub Actions runners ship with pipx. `--format github` turns each finding
into an annotation on the pull request diff:

```yaml
- uses: actions/checkout@v4
- run: pipx install amagi-skill-lint
- run: amagi-skill-lint . --format github
```

Lines look like this:

```
::error file=skills/invoice-chaser/SKILL.md,line=3,title=SL002 yaml-invalid::invalid YAML: mapping values are not allowed here -- a value contains ": ", so wrap the whole value in quotes
```

Add `--fail-on warning` to block merges on warnings too. Use
`--format json` for anything else that reads results.

## Use it as a Claude Code skill

The repo includes a `SKILL.md`. Copy it into your skills folder:

```
mkdir -p ~/.claude/skills/amagi-skill-lint
cp SKILL.md ~/.claude/skills/amagi-skill-lint/SKILL.md
```

Ask Claude why a skill is not triggering, or to clean up your skills
folder, and it runs `amagi-skill-lint` and works through the findings.

## Limitations

- Token counts are estimates (characters / 4), not a real tokenizer.
- Overlap compares words, not meaning. Two descriptions that say the same
  thing in different words score low.
- SL023 looks for phrases like "use when", "invoke", "whenever" and
  "best for". A clear trigger worded another way gets flagged; disable the
  rule for that file.
- Path mentions inside code blocks are checked only under conventional
  skill folders that exist (`scripts/`, `references/`, `assets/`, ...),
  since commands there often name the user's own files.

## Related AmagiLabs projects

- [amagi-watch](https://github.com/amagilabs/amagi-watch): give Claude a
  video URL and get back a transcript and key frames.
- [amagi-listen](https://github.com/amagilabs/amagi-listen): chaptered,
  timestamped transcripts from audio and video files.
- [amagi-screen](https://github.com/amagilabs/amagi-screen): give Claude a
  screen recording and get back a frame timeline.
- [amagi-legal-review-skills](https://github.com/amagilabs/amagi-legal-review-skills):
  Claude Code skills and subagents for a first-pass review of contracts and
  leases.
- More at [github.com/amagilabs](https://github.com/amagilabs).

If amagi-skill-lint caught a skill that was quietly broken, star the repo so
other people building skills can find it.

## License

MIT. Copyright (c) 2026 Amagisolutionsgroup, Inc. (AmagiLabs). See [LICENSE](LICENSE).
