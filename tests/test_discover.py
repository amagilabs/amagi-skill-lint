import pytest

from amagi_skill_lint.discover import discover


def test_finds_skills_and_agents(fixtures):
    targets = discover([str(fixtures / "demo_pack")])
    kinds = [(t.kind, t.path.parent.name if t.kind == "skill" else t.path.name) for t in targets]
    assert ("skill", "pdf-forms") in kinds
    assert ("agent", "code-reviewer.md") in kinds
    assert sum(1 for k, _ in kinds if k == "skill") == 5
    assert sum(1 for k, _ in kinds if k == "agent") == 2
    # reference/fields.md is not a skill or an agent
    assert all(t.path.name != "fields.md" for t in targets)


def test_skills_come_before_agents(fixtures):
    targets = discover([str(fixtures / "demo_pack")])
    kinds = [t.kind for t in targets]
    assert kinds == sorted(kinds, key=lambda k: k != "skill")


def test_agents_folder_inside_a_skill_is_ignored(tmp_path):
    skill = tmp_path / "skills" / "grader"
    (skill / "agents").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: grader\ndescription: d\n---\n", encoding="utf-8")
    (skill / "agents" / "helper.md").write_text("prompt text", encoding="utf-8")
    targets = discover([str(tmp_path)])
    assert [t.kind for t in targets] == ["skill"]


def test_agents_dir_as_root_and_skips_readme_and_underscore(tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "a.md").write_text("---\nname: a\ndescription: d\n---\n", encoding="utf-8")
    (agents / "README.md").write_text("# agents", encoding="utf-8")
    (agents / "_ROSTER.md").write_text("# roster", encoding="utf-8")
    targets = discover([str(agents)])
    assert [t.path.name for t in targets] == ["a.md"]


def test_single_files_and_dedup(fixtures):
    f = fixtures / "demo_pack" / "agents" / "code-reviewer.md"
    targets = discover([str(f), str(fixtures / "demo_pack" / "agents")])
    assert len(targets) == 2
    assert all(t.kind == "agent" for t in targets)


def test_skips_vendor_dirs(tmp_path):
    hidden = tmp_path / "node_modules" / "pkg"
    hidden.mkdir(parents=True)
    (hidden / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    assert discover([str(tmp_path)]) == []


def test_missing_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        discover([str(tmp_path / "nope")])
