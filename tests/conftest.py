from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

GOOD_DESC = "Cleans messy CSV exports and fixes dates. Use when the user hands over a CSV that will not import."


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def make_skill(tmp_path):
    """Write <tmp>/skills/<folder>/SKILL.md and return its path."""

    def _make(folder: str, frontmatter: str = None, body: str = "# Title\n\nDo the thing.\n", raw: str = None) -> Path:
        d = tmp_path / "skills" / folder
        d.mkdir(parents=True, exist_ok=True)
        if raw is None:
            fm = frontmatter if frontmatter is not None else f"name: {folder}\ndescription: {GOOD_DESC}"
            raw = f"---\n{fm}\n---\n{body}"
        p = d / "SKILL.md"
        p.write_text(raw, encoding="utf-8")
        return p

    return _make


@pytest.fixture
def make_agent(tmp_path):
    def _make(filename: str, frontmatter: str, body: str = "You are a helper.\n") -> Path:
        d = tmp_path / "agents"
        d.mkdir(parents=True, exist_ok=True)
        p = d / filename
        p.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")
        return p

    return _make
