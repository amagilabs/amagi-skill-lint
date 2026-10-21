from amagi_skill_lint.frontmatter import parse


def test_parses_mapping_and_body_line():
    p = parse("---\nname: x\ndescription: y\n---\n# Body\n")
    assert p.has_frontmatter and p.closed
    assert p.mapping == {"name": "x", "description": "y"}
    assert p.body.startswith("# Body")
    assert p.body_start == 5
    assert p.key_lines == {"name": 2, "description": 3}


def test_no_frontmatter():
    p = parse("# Just markdown\n")
    assert not p.has_frontmatter
    assert p.body == "# Just markdown\n"


def test_unclosed_frontmatter():
    p = parse("---\nname: x\n# body\n")
    assert p.has_frontmatter and not p.closed


def test_unquoted_colon_is_a_yaml_error_with_file_line():
    p = parse("---\nname: x\ndescription: Use when: the user asks\n---\n")
    assert p.yaml_error and "mapping values" in p.yaml_error
    assert p.yaml_error_line == 3


def test_bom_and_crlf_are_handled():
    crlf = chr(13) + chr(10)
    p = parse(chr(0xFEFF) + crlf.join(["---", "name: x", "description: y", "---", "body", ""]))
    assert p.mapping["name"] == "x"
    assert p.body == "body\n"


def test_folded_block_scalar():
    p = parse("---\nname: x\ndescription: >\n  first line\n  second line\n---\n")
    assert p.mapping["description"].strip() == "first line second line"


def test_duplicate_keys_are_recorded():
    p = parse("---\nname: a\nname: b\ndescription: d\n---\n")
    assert p.mapping["name"] == "b"
    assert p.duplicates == [("name", 3)]


def test_empty_frontmatter_is_none():
    p = parse("---\n---\nbody\n")
    assert p.closed and p.data is None and p.mapping == {}
