"""The code examples embedded in the wiki pages must run.

The ``python`` block of ``docs/wiki/Library-API.md`` is executed verbatim (offline, on the demo
data) and every name it imports from ``firefly_reports`` must exist in ``firefly_reports.__all__``.
"""

import ast
from pathlib import Path

import firefly_reports

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGE = REPO_ROOT / "docs" / "wiki" / "Library-API.md"


def extract_python_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    lines = text.splitlines()
    in_block = False
    current: list[str] = []
    language = ""
    for line in lines:
        if line.startswith("```"):
            if not in_block:
                in_block = True
                language = line[3:].strip()
                current = []
            else:
                in_block = False
                if language == "python":
                    blocks.append("\n".join(current))
            continue
        if in_block:
            current.append(line)
    assert not in_block, "unclosed fenced code block in Library-API.md"
    return blocks


def test_library_api_example_runs_offline() -> None:
    blocks = extract_python_blocks(PAGE.read_text(encoding="utf-8"))
    assert blocks, "Library-API.md has no python example"
    namespace: dict[str, object] = {}
    exec(compile(blocks[0], str(PAGE), "exec"), namespace)  # noqa: S102 - the wiki example itself
    result = namespace["result"]
    assert result.ok  # the demo run wrote every file
    assert namespace["infos"] == firefly_reports.available_reports()


def test_library_api_names_are_exported() -> None:
    tree = ast.parse(extract_python_blocks(PAGE.read_text(encoding="utf-8"))[0])
    checked = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "firefly_reports":
            for alias in node.names:
                assert alias.name in firefly_reports.__all__, (
                    f"{alias.name} is used in the wiki example but is not in __all__"
                )
                checked += 1
    assert checked > 0
