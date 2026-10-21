import json
import subprocess
import sys

import pytest

from amagi_skill_lint import __version__
from amagi_skill_lint.cli import main


def run(capsys, *argv):
    rc = main(list(argv))
    out, err = capsys.readouterr()
    return rc, out, err


def test_demo_pack_text_and_exit_code(capsys, fixtures):
    rc, out, _ = run(capsys, str(fixtures / "demo_pack"), "--no-color")
    assert rc == 1
    assert "Checked 5 skills and 2 agents." in out
    assert "5 errors, 10 warnings, 1 info in 6 files." in out
    assert "Overlapping descriptions" in out
    assert "\033[" not in out


def test_clean_pack_exits_zero(capsys, fixtures):
    rc, out, _ = run(capsys, str(fixtures / "clean_pack"))
    assert rc == 0
    assert out.strip().endswith("No problems found.")


def test_fail_on_levels(capsys, fixtures):
    demo = str(fixtures / "demo_pack")
    assert run(capsys, demo, "--fail-on", "never")[0] == 0
    assert run(capsys, demo, "--select", "SL026", "--fail-on", "error")[0] == 0
    assert run(capsys, demo, "--select", "SL026", "--fail-on", "info")[0] == 1
    assert run(capsys, demo, "--select", "SL041", "--fail-on", "warning")[0] == 1


def test_ignore_removes_findings(capsys, fixtures):
    rc, out, _ = run(capsys, str(fixtures / "demo_pack"), "--ignore", "SL002,SL040,SL005,SL050", "--quiet")
    assert rc == 0
    assert "SL002" not in out and "0 errors" in out
    assert "Checked" not in out


def test_unknown_rule_id_is_usage_error(capsys, fixtures):
    with pytest.raises(SystemExit) as e:
        main([str(fixtures / "demo_pack"), "--ignore", "SL999"])
    assert e.value.code == 2
    assert "unknown rule id" in capsys.readouterr().err


def test_bad_overlap_value(capsys, fixtures):
    with pytest.raises(SystemExit) as e:
        main([str(fixtures / "demo_pack"), "--overlap", "1.5"])
    assert e.value.code == 2


def test_json_output(capsys, fixtures):
    rc, out, _ = run(capsys, str(fixtures / "demo_pack"), "--format", "json")
    data = json.loads(out)
    assert rc == 1
    assert data["tool"] == "amagi-skill-lint" and data["version"] == __version__
    assert data["summary"] == {"error": 5, "warning": 10, "info": 1}
    assert len(data["files"]) == 7 and len(data["overlaps"]) == 1
    rules = {f["rule"] for x in data["files"] for f in x["findings"]}
    assert {"SL002", "SL040", "SL050", "SL051"} <= rules


def test_github_output(capsys, fixtures):
    rc, out, _ = run(capsys, str(fixtures / "demo_pack"), "--format", "github")
    lines = out.strip().splitlines()
    assert any(l.startswith("::error file=") and "title=SL002 yaml-invalid::" in l for l in lines)
    assert any(l.startswith("::warning file=") for l in lines)
    assert any(l.startswith("::notice file=") for l in lines)
    assert lines[-1] == "amagi-skill-lint: 5 errors, 10 warnings, 1 info"


def test_list_rules(capsys):
    rc, out, _ = run(capsys, "--list-rules")
    assert rc == 0
    assert "SL001" in out and "SL051" in out and "overlapping-descriptions" in out


def test_missing_path(capsys, tmp_path):
    rc, _, err = run(capsys, str(tmp_path / "nope"))
    assert rc == 2 and "path not found" in err


def test_nothing_to_lint(capsys, tmp_path):
    rc, _, err = run(capsys, str(tmp_path))
    assert rc == 2 and "no SKILL.md" in err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert capsys.readouterr().out.strip() == f"amagi-skill-lint {__version__}"


def test_python_dash_m(fixtures):
    proc = subprocess.run(
        [sys.executable, "-m", "amagi_skill_lint", str(fixtures / "clean_pack")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    assert "No problems found." in proc.stdout
