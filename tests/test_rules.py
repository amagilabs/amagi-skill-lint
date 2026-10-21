from amagi_skill_lint.discover import Target, discover
from amagi_skill_lint.rules import ERROR, INFO, WARNING, Config, lint_file, lint_set

from conftest import GOOD_DESC


def rules_for(path, kind="skill", cfg=None):
    return [f.rule for f in lint_file(Target(path, kind), cfg or Config()).findings]


def findings_for(path, kind="skill", cfg=None):
    return lint_file(Target(path, kind), cfg or Config()).findings


# --- frontmatter -----------------------------------------------------------

def test_clean_skill_has_no_findings(make_skill):
    assert rules_for(make_skill("csv-cleaner")) == []


def test_no_frontmatter(make_skill):
    assert rules_for(make_skill("x", raw="# Hello\n")) == ["SL001"]


def test_unclosed_frontmatter(make_skill):
    assert rules_for(make_skill("x", raw="---\nname: x\n")) == ["SL001"]


def test_yaml_error_points_at_line_with_quote_hint(make_skill):
    p = make_skill("x", "name: x\ndescription: Sends reminders. Use when: invoices are late")
    f = findings_for(p)
    assert [x.rule for x in f] == ["SL002"]
    assert f[0].line == 3
    assert "wrap the whole value in quotes" in f[0].message


def test_frontmatter_not_mapping(make_skill):
    assert rules_for(make_skill("x", "- a\n- b")) == ["SL003"]


def test_missing_name_and_description(make_skill):
    assert set(rules_for(make_skill("x", "license: MIT"))) == {"SL004", "SL005"}


def test_empty_description(make_skill):
    f = findings_for(make_skill("x", 'name: x\ndescription: ""'))
    assert [x.rule for x in f] == ["SL005"]
    assert "empty" in f[0].message


def test_duplicate_key(make_skill):
    p = make_skill("x", f"name: x\ndescription: {GOOD_DESC}\ndescription: {GOOD_DESC}")
    assert rules_for(p) == ["SL012"]


# --- names -----------------------------------------------------------------

def test_name_not_portable_and_folder_mismatch(make_skill):
    p = make_skill("meeting-notes", f"name: Meeting_Notes\ndescription: {GOOD_DESC}")
    assert set(rules_for(p)) == {"SL006", "SL009"}


def test_name_too_long_for_api(make_skill):
    name = "a" * 65
    p = make_skill(name, f"name: {name}\ndescription: {GOOD_DESC}")
    f = findings_for(p)
    assert [x.rule for x in f] == ["SL006"]
    assert "65 characters" in f[0].message


def test_reserved_word(make_skill):
    p = make_skill("claude-helper", f"name: claude-helper\ndescription: {GOOD_DESC}")
    assert rules_for(p) == ["SL007"]


def test_name_with_angle_bracket_is_invalid(make_skill):
    p = make_skill("x", f'name: "x<y"\ndescription: {GOOD_DESC}')
    assert "SL008" in rules_for(p)


def test_agent_name_with_colon(make_agent):
    p = make_agent("a.md", f'name: "team:a"\ndescription: {GOOD_DESC}')
    assert rules_for(p, "agent") == ["SL008"]


def test_agent_names_do_not_need_folder_or_portable_name(make_agent):
    p = make_agent("whatever.md", f"name: Code Reviewer\ndescription: {GOOD_DESC}")
    assert rules_for(p, "agent") == []


# --- keys and values ---------------------------------------------------------

def test_key_typo(make_skill):
    p = make_skill("x", f"name: x\ndescription: {GOOD_DESC}\nallowed_tools: Read")
    f = findings_for(p)
    assert [x.rule for x in f] == ["SL010"]
    assert "allowed-tools" in f[0].message


def test_unknown_but_unrelated_key_is_fine(make_skill):
    p = make_skill("x", f"name: x\ndescription: {GOOD_DESC}\nowner: platform-team")
    assert rules_for(p) == []


def test_bad_values_skill(make_skill):
    p = make_skill("x", f"name: x\ndescription: {GOOD_DESC}\nmodel: gpt-4\neffort: extreme\nuser-invocable: yes please\ncontext: thread")
    msgs = [x.message for x in findings_for(p)]
    assert len(msgs) == 4 and all(x.startswith(("model", "effort", "'user-invocable'", "context")) for x in msgs)


def test_good_values_skill(make_skill):
    p = make_skill("x", f"name: x\ndescription: {GOOD_DESC}\nmodel: claude-opus-5-5\neffort: high\ncontext: fork\nuser-invocable: false")
    assert rules_for(p) == []


def test_bad_values_agent(make_agent):
    fm = (f"name: a\ndescription: {GOOD_DESC}\nmodel: gpt-4\ncolor: teal\npermissionMode: yolo\n"
          "memory: global\ntools: \"\"\nmaxTurns: 0")
    assert rules_for(make_agent("a.md", fm), "agent") == ["SL011"] * 6


def test_good_values_agent(make_agent):
    fm = (f"name: a\ndescription: {GOOD_DESC}\nmodel: inherit\ncolor: cyan\npermissionMode: plan\n"
          "memory: project\ntools: Read, Grep\nmaxTurns: 10\nbackground: false")
    assert rules_for(make_agent("a.md", fm), "agent") == []


def test_tools_as_yaml_list(make_agent):
    fm = f"name: a\ndescription: {GOOD_DESC}\ntools:\n  - Read\n  - Bash"
    assert rules_for(make_agent("a.md", fm), "agent") == []


# --- descriptions ------------------------------------------------------------

def test_description_truncated_includes_when_to_use(make_skill):
    long = "Use when the user asks about invoices. " + "x" * 1000
    p = make_skill("x", f"name: x\ndescription: {long}\nwhen_to_use: {'y' * 600}")
    f = findings_for(p)
    assert [x.rule for x in f] == ["SL020"]
    assert "when_to_use" in f[0].message


def test_description_over_api_limit(make_skill, make_agent):
    long = "Use when the user asks about invoices. " + "x" * 1000
    assert rules_for(make_skill("x", f"name: x\ndescription: {long}")) == ["SL021"]
    f = findings_for(make_agent("a.md", f"name: a\ndescription: {long}"), "agent")
    assert [(x.rule, x.severity) for x in f] == [("SL021", INFO)]


def test_description_too_short(make_skill):
    assert rules_for(make_skill("x", "name: x\ndescription: Formats CSV.")) == ["SL022"]


def test_min_description_is_configurable(make_skill):
    p = make_skill("x", "name: x\ndescription: Formats CSV. Use when asked.")
    assert rules_for(p, cfg=Config(min_description=10)) == []


def test_no_trigger_cue_is_warning_for_skills_info_for_agents(make_skill, make_agent):
    d = "Converts scanned PDF invoices into structured JSON with totals and line items."
    f = findings_for(make_skill("x", f"name: x\ndescription: {d}"))
    assert [(x.rule, x.severity) for x in f] == [("SL023", WARNING)]
    f = findings_for(make_agent("a.md", f"name: a\ndescription: {d}"), "agent")
    assert [(x.rule, x.severity) for x in f] == [("SL023", INFO)]


def test_trigger_cues_recognised(make_skill):
    for d in (
        "Converts scanned PDF invoices into JSON. Use when the user uploads an invoice.",
        "Converts scanned PDF invoices into JSON. Invoke after an invoice upload.",
        "Converts scanned PDF invoices into JSON whenever an invoice shows up.",
        "Converts scanned PDF invoices into JSON. Best for batch accounting imports.",
    ):
        assert rules_for(make_skill("x", f"name: x\ndescription: {d}")) == [], d


def test_trigger_cue_can_come_from_when_to_use(make_skill):
    d = "Converts scanned PDF invoices into structured JSON with totals."
    p = make_skill("x", f"name: x\ndescription: {d}\nwhen_to_use: Use when an invoice is uploaded.")
    assert rules_for(p) == []


def test_disabled_model_invocation_skips_trigger_check(make_skill):
    d = "Converts scanned PDF invoices into structured JSON with totals."
    p = make_skill("x", f"name: x\ndescription: {d}\ndisable-model-invocation: true")
    r = lint_file(Target(p, "skill"), Config())
    assert r.findings == [] and r.model_invocable is False and r.listing_tokens == 0


def test_first_person_and_vague(make_skill):
    p = make_skill("x", "name: x\ndescription: I can help you with meeting notes and various other stuff. Use when asked.")
    assert set(rules_for(p)) == {"SL024", "SL026"}


def test_xml_in_skill_description(make_skill):
    p = make_skill("x", 'name: x\ndescription: "Wraps output in <result> tags. Use when the user wants tagged output."')
    assert rules_for(p) == ["SL025"]


def test_description_as_list(make_skill):
    assert set(rules_for(make_skill("x", "name: x\ndescription:\n  - a\n  - b"))) == {"SL005", "SL011"}


# --- size --------------------------------------------------------------------

def test_line_and_token_budgets(make_skill):
    body = "\n".join(f"line {i} " + "word " * 20 for i in range(600))
    p = make_skill("x", body=body)
    assert set(rules_for(p)) == {"SL030", "SL031"}
    assert rules_for(p, cfg=Config(max_lines=1000, max_tokens=100000)) == []


def test_agent_has_no_line_budget(make_agent):
    body = "\n".join("short" for _ in range(600))
    assert rules_for(make_agent("a.md", f"name: a\ndescription: {GOOD_DESC}", body), "agent") == []


# --- references --------------------------------------------------------------

def test_broken_link_and_missing_mention(make_skill):
    p = make_skill("x", body="See [the guide](reference/guide.md) and run scripts/go.py.\n")
    f = findings_for(p)
    assert [(x.rule, x.line) for x in f] == [("SL040", 5), ("SL041", 5)]


def test_existing_files_pass(make_skill):
    p = make_skill("x", body="See [the guide](reference/guide.md#setup) and run `scripts/go.py`.\n")
    (p.parent / "reference").mkdir()
    (p.parent / "reference" / "guide.md").write_text("ok", encoding="utf-8")
    (p.parent / "scripts").mkdir()
    (p.parent / "scripts" / "go.py").write_text("", encoding="utf-8")
    assert rules_for(p) == []


def test_urls_and_anchors_are_not_checked(make_skill):
    p = make_skill("x", body="[docs](https://example.com/a.md) [top](#top) [mail](mailto:help)\n")
    assert rules_for(p) == []


def test_absolute_and_backslash_links(make_skill):
    p = make_skill("x", body="[a](C:/Users/bob/notes.md)\n[b](reference\\guide.md)\n")
    assert sorted((f.line, f.rule) for f in findings_for(p)) == [(5, "SL042"), (6, "SL040"), (6, "SL043")]


def test_machine_path_in_prose(make_skill):
    p = make_skill("x", body="Config lives in /home/alice/.config/tool.toml\n")
    assert rules_for(p) == ["SL042"]


def test_code_block_paths_need_existing_conventional_dir(make_skill):
    body = "```bash\npython src/app.py\npython scripts/run.py\n```\n"
    p = make_skill("x", body=body)
    assert rules_for(p) == []  # no scripts/ folder: commands likely refer to the user's project
    (p.parent / "scripts").mkdir()
    f = findings_for(p)
    assert [(x.rule, x.line) for x in f] == [("SL041", 7)]


def test_inline_disable_comment(make_skill):
    p = make_skill("x", body="<!-- skill-lint-disable SL041 -->\nRun scripts/go.py.\n")
    assert rules_for(p) == []


def test_disable_comment_shown_in_code_does_not_disable(make_skill):
    p = make_skill("x", body="Write `<!-- skill-lint-disable SL041 -->` to silence it.\nRun scripts/go.py.\n")
    assert rules_for(p) == ["SL041"]


def test_ignore_and_select(make_skill):
    p = make_skill("Bad_Name", "name: Bad_Name\ndescription: Formats CSV.")
    assert set(rules_for(p)) == {"SL006", "SL022"}
    assert rules_for(p, cfg=Config(ignore=["SL006"])) == ["SL022"]
    assert rules_for(p, cfg=Config(select=["SL006"])) == ["SL006"]


# --- set-level rules ----------------------------------------------------------

def test_duplicate_names_across_files(tmp_path, make_agent):
    make_agent("a.md", f"name: reviewer\ndescription: {GOOD_DESC}")
    make_agent("b.md", f"name: Reviewer\ndescription: Writes release notes from merged pull requests. Use after tagging.")
    results, _ = lint_set(discover([str(tmp_path)]), Config())
    assert [[f.rule for f in r.findings] for r in results] == [["SL050"], ["SL050"]]


def test_overlap_detected_and_threshold(tmp_path, make_skill):
    make_skill("pdf-forms", "name: pdf-forms\ndescription: Fill PDF forms, extract PDF form fields and flatten PDF pages. Use when working with PDF forms.")
    make_skill("pdf-tables", "name: pdf-tables\ndescription: Extract tables from PDF pages and merge PDF files. Use when working with PDF tables.")
    make_skill("csv-cleaner")
    targets = discover([str(tmp_path)])
    results, overlaps = lint_set(targets, Config())
    assert len(overlaps) == 1
    o = overlaps[0]
    assert {o.a.name, o.b.name} == {"pdf-forms", "pdf-tables"}
    assert "pdf" in o.shared
    assert sum(1 for r in results for f in r.findings if f.rule == "SL051") == 2
    _, none = lint_set(targets, Config(overlap_threshold=0.95))
    assert none == []


def test_overlap_skips_disabled_model_invocation(tmp_path, make_skill):
    make_skill("pdf-forms", "name: pdf-forms\ndescription: Fill PDF forms, extract PDF form fields and flatten PDF pages. Use when working with PDF forms.")
    make_skill("pdf-tables", "name: pdf-tables\ndescription: Extract tables from PDF pages and merge PDF files. Use when working with PDF tables.\ndisable-model-invocation: true")
    _, overlaps = lint_set(discover([str(tmp_path)]), Config())
    assert overlaps == []


def test_skills_and_agents_do_not_overlap_each_other(tmp_path, make_skill, make_agent):
    d = "Fill PDF forms, extract PDF form fields and flatten PDF pages. Use when working with PDF forms."
    make_skill("pdf-forms", f"name: pdf-forms\ndescription: {d}")
    make_agent("pdf-agent.md", f"name: pdf-agent\ndescription: {d}")
    _, overlaps = lint_set(discover([str(tmp_path)]), Config())
    assert overlaps == []


# --- fixtures end to end -------------------------------------------------------

def test_demo_pack_findings(fixtures):
    results, overlaps = lint_set(discover([str(fixtures / "demo_pack")]), Config())
    by = {(r.name or r.path.parent.name): sorted(f.rule for f in r.findings) for r in results}
    assert by["pdf-forms"] == ["SL051"]
    assert by["pdf-tables"] == ["SL040", "SL041", "SL051"]
    assert by["invoice-chaser"] == ["SL002"]
    assert by["Meeting_Notes"] == ["SL006", "SL009", "SL023", "SL024", "SL026"]
    assert by["release-notes"] == []
    sev = [f.severity for r in results for f in r.findings]
    assert (sev.count(ERROR), sev.count(WARNING), sev.count(INFO)) == (5, 10, 1)
    assert len(overlaps) == 1


def test_clean_pack_is_clean(fixtures):
    results, overlaps = lint_set(discover([str(fixtures / "clean_pack")]), Config())
    assert [f for r in results for f in r.findings] == [] and overlaps == []
