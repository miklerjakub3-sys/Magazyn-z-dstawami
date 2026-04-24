from __future__ import annotations

import ast
from pathlib import Path


def test_tabs_issues_python_syntax_is_valid() -> None:
    path = Path(__file__).resolve().parents[1] / "magazyn" / "ui" / "tabs_issues.py"
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=str(path))
