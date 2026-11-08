# -*- coding: utf-8 -*-
"""scripts/report_code_quality.py tìm hàm trùng logic, trùng tên, module không ai import và hàm không ai gọi."""

import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import report_code_quality as rcq  # noqa: E402

BODY = """
    total = 0
    for item in {arg}:
        if item:
            total += len(item)
    return total
"""


def write(path: Path, code: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(code), encoding="utf-8")
    return path


@pytest.fixture
def project(tmp_path):
    pkg = tmp_path / "pkg"
    write(pkg / "__init__.py", "")
    write(pkg / "a.py", "def count_a(rows):" + BODY.format(arg="rows") + "\n\ndef helper():\n    return 1\n\n\ndef used():\n    return 2\n")
    write(pkg / "b.py", "from pkg.a import used\n\n\ndef count_b(values):" + BODY.format(arg="values")
          + "\n\ndef helper():\n    return used() + 40\n\n\nprint(helper())\n")
    write(pkg / "orphan.py", "def lonely():\n    return 3\n")
    write(pkg / "cli.py", "def main():\n    return 0\n\n\nif __name__ == '__main__':\n    main()\n")
    write(tmp_path / "tests" / "test_x.py", "from pkg.orphan import lonely\n")
    return tmp_path


def py_files(root):
    return sorted((root / "pkg").glob("*.py"))


def test_logic_duplicates_ignore_variable_names(project):
    groups = rcq.find_logic_duplicates(py_files(project), project)
    names = [sorted(f["name"] for f in g) for g in groups]
    assert names == [["count_a", "count_b"]]


def test_name_duplicates_across_files(project):
    groups = rcq.find_name_duplicates(py_files(project), project)
    assert [(name, sorted(f["file"] for f in found)) for name, found in groups] == [("helper", ["pkg/a.py", "pkg/b.py"])]


def test_orphan_module_found_and_test_only_use_marked(project):
    orphans = rcq.find_orphan_modules(py_files(project), project, [project / "tests" / "test_x.py"])
    # a.py được b.py import, cli.py là entry point; b.py không ai import, orphan.py chỉ test import
    assert {o["file"]: o["only_tests"] for o in orphans} == {"pkg/b.py": False, "pkg/orphan.py": True}


def test_vulture_does_not_flag_called_function(project):
    names = {f["name"] for f in rcq.find_unused_code([project / "pkg"], project)}
    assert "used" not in names and "helper" not in names
    assert {"lonely", "count_a", "count_b"} <= names


def test_report_lists_every_section(project, tmp_path):
    out = tmp_path / "report.md"
    rcq.build_report([project / "pkg"], project, out, tests_dir=project / "tests")
    text = out.read_text(encoding="utf-8")
    for heading in ("## A.", "## B.", "## C.", "## D."):
        assert heading in text
    assert "count_a" in text and "pkg/orphan.py" in text
