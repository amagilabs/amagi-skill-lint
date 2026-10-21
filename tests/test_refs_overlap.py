from amagi_skill_lint import overlap, refs

# Built at runtime so this file holds no literal Windows home-folder path.
WIN_USERS = "C:" + chr(92) + "Users"


def test_extract_links_and_mentions_with_lines():
    body = "intro\n[a](reference/a.md) and scripts/b.py\n![img](assets/c.png)\n[d]: docs/d.md\n"
    got = [(r.target, r.line, r.kind) for r in refs.extract(body, 10)]
    assert ("reference/a.md", 11, "link") in got
    assert ("scripts/b.py", 11, "mention") in got
    assert ("assets/c.png", 12, "link") in got
    assert ("docs/d.md", 13, "link") in got
    # the link target itself is not also counted as a mention
    assert ("reference/a.md", 11, "mention") not in got


def test_links_inside_code_are_not_links():
    body = "```\n[a](missing.md)\n```\n`[b](also.md)`\n"
    assert [r for r in refs.extract(body, 1) if r.kind == "link"] == []


def test_mentions_in_code_are_flagged_as_in_code():
    body = "```\npython scripts/run.py\n```\n"
    (r,) = refs.extract(body, 1)
    assert r.target == "scripts/run.py" and r.in_code


def test_classify_link():
    assert refs.classify_link("https://x.dev/a.md") is None
    assert refs.classify_link("#anchor") is None
    assert refs.classify_link("${CLAUDE_SKILL_DIR}/a.md") is None
    assert refs.classify_link("/etc/a.md") == "abs"
    assert refs.classify_link(WIN_USERS + "\\x\\a.md") == "abs"
    assert refs.classify_link("~/a.md") == "abs"
    assert refs.classify_link("ref\\a.md") == "backslash"
    assert refs.classify_link("ref/a.md") == "rel"


def test_resolve_strips_anchor_query_and_decodes(tmp_path):
    assert refs.resolve(tmp_path, "my%20file.md#top") == tmp_path / "my file.md"
    assert refs.resolve(tmp_path, "a\\b.md?x=1") == tmp_path / "a" / "b.md"


def test_mention_should_check(tmp_path):
    (tmp_path / "data").mkdir()
    assert refs.mention_should_check(tmp_path, "scripts/a.py", in_code=False)
    assert refs.mention_should_check(tmp_path, "data/a.csv", in_code=False)
    assert not refs.mention_should_check(tmp_path, "src/a.py", in_code=False)
    assert not refs.mention_should_check(tmp_path, ".github/workflows/ci.yml", in_code=False)
    assert not refs.mention_should_check(tmp_path, "scripts/a.py", in_code=True)
    (tmp_path / "scripts").mkdir()
    assert refs.mention_should_check(tmp_path, "scripts/a.py", in_code=True)


def test_machine_paths():
    body = "a " + WIN_USERS + "\\bob\\x.txt b /Users/alice/y c /home/carol/z d /usr/bin/env\n"
    got = [p for _, p in refs.machine_paths(body, 1)]
    assert got == [WIN_USERS + "\\bob", "/Users/alice", "/home/carol"]


def test_overlap_scores_related_pairs_only():
    texts = [
        "Fill PDF forms and extract PDF form fields. Use when working with PDF forms.",
        "Extract tables from PDF pages. Use when working with PDF tables.",
        "Write release notes from merged pull requests after a tag.",
    ]
    pairs = overlap.similar_pairs(texts, 0.2)
    assert [(p.a, p.b) for p in pairs] == [(0, 1)]
    assert 0 < pairs[0].score <= 1
    assert "pdf" in pairs[0].shared


def test_overlap_ignores_stopwords_and_boilerplate():
    a = "Use this skill when the user asks for help with the task."
    b = "Use this skill when the user asks for help with a task."
    assert overlap.similar_pairs([a, b], 0.1) == []


def test_identical_descriptions_score_one():
    t = "Converts scanned invoices into ledger entries for bookkeeping."
    (p,) = overlap.similar_pairs([t, t], 0.5)
    assert abs(p.score - 1.0) < 1e-9
