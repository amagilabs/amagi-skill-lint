"""Split a markdown file into YAML frontmatter and body, and parse the YAML.

Line numbers in the result are 1-based and refer to the original file, so
findings can point straight at the offending line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml


class DuplicateKeyError(Exception):
    def __init__(self, key: str, line: int):
        super().__init__(key)
        self.key = key
        self.line = line  # 0-based within the YAML text


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that records duplicate mapping keys instead of silently keeping the last one."""


def _construct_mapping(loader: _StrictLoader, node: yaml.MappingNode, deep: bool = False) -> Dict[Any, Any]:
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            hashable = key in seen
        except TypeError:
            continue
        if hashable:
            loader.duplicates.append((str(key), key_node.start_mark.line))
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


@dataclass
class Parsed:
    text: str
    has_frontmatter: bool = False
    closed: bool = False
    data: Any = None
    yaml_error: Optional[str] = None
    yaml_error_line: Optional[int] = None  # 1-based file line
    key_lines: Dict[str, int] = field(default_factory=dict)  # top-level key -> 1-based file line
    duplicates: List[tuple] = field(default_factory=list)  # (key, 1-based file line)
    fm_start: int = 1  # line of the opening ---
    body: str = ""
    body_start: int = 1  # 1-based file line where the body begins

    @property
    def mapping(self) -> Dict[str, Any]:
        return self.data if isinstance(self.data, dict) else {}


def parse(text: str) -> Parsed:
    if text.startswith(chr(0xFEFF)):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    result = Parsed(text=text, body=text)
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return result
    result.has_frontmatter = True
    end = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() in ("---", "..."):
            end = i
            break
    if end is None:
        return result
    result.closed = True
    yaml_text = "\n".join(lines[1:end])
    result.body = "\n".join(lines[end + 1:])
    result.body_start = end + 2

    for idx, line in enumerate(lines[1:end]):
        if line and not line[0].isspace() and not line.startswith("#") and ":" in line:
            key = line.split(":", 1)[0].strip().strip("'\"")
            result.key_lines.setdefault(key, idx + 2)

    loader = _StrictLoader(yaml_text)
    loader.duplicates = []
    try:
        result.data = loader.get_single_data()
        result.duplicates = [(k, ln + 2) for k, ln in loader.duplicates]
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
        problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
        result.yaml_error = problem
        result.yaml_error_line = (mark.line + 2) if mark is not None else 2
    finally:
        loader.dispose()
    return result
