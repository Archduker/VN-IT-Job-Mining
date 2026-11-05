#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Báo cáo chất lượng code: thừa, trùng, chết (Phase 2.2). Chỉ đọc code, không sửa gì.

    python scripts/report_code_quality.py                 # ghi docs/code_quality.md
    python scripts/report_code_quality.py --out /tmp/x.md

Bốn bảng:
    A. Import thừa, biến không dùng, hàm khai báo lại (ruff F401, F841, F811).
    B. Hàm, class, method không ai gọi (vulture) và module không ai import (AST).
    C. Hàm trùng logic giữa các file, kể cả khác tên (so cây cú pháp sau khi đổi tên biến).
    D. Hàm trùng tên ở nhiều file.

Đây là danh sách để người duyệt quyết xóa, gộp hay giữ. Script luôn trả exit 0.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
SCOPE = ("collection", "scripts", "run.py", "airflow/plugins", "airflow/dags", "monitoring/backend/app")
SKIP_PARTS = {".venv", "node_modules", "__pycache__", "archive"}
MIN_LINES = 5  # hàm ngắn hơn thì trùng là bình thường (getter, wrapper)
# Tên trùng là chủ ý (giao diện chung, entry point), không báo ở bảng D
COMMON_NAMES = {"main", "run", "parse_args", "setup", "execute", "build_parser", "get_parser", "cli"}
# vulture không thấy được các chỗ gọi này: override của lớp cha, framework tự gọi
VULTURE_IGNORE_DECORATORS = "@router.*,@app.*,@*.get,@*.post,@*.put,@*.delete,@field_validator,@validator,@model_validator,@pytest.*"
VULTURE_IGNORE_NAMES = "handle_*,visit_*,model_config,Config"
VULTURE_KINDS = ("function", "method", "class", "property")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def collect_files(paths: Iterable[Path]) -> List[Path]:
    files: List[Path] = []
    for p in paths:
        if p.is_file() and p.suffix == ".py":
            files.append(p)
        elif p.is_dir():
            files.extend(f for f in sorted(p.rglob("*.py")) if not SKIP_PARTS & set(f.parts))
    return files


def _parse(path: Path) -> Optional[ast.Module]:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None


def _functions(tree: ast.Module) -> Iterable[Tuple[ast.AST, Optional[str]]]:
    """(hàm, tên class chứa nó hoặc None) cho hàm cấp module và method."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node, None
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield item, node.name


# ---------------------------------------------------------------- C. trùng logic
class _Normalize(ast.NodeTransformer):
    """Đổi tên biến và tham số thành v0, v1… theo thứ tự xuất hiện; giữ nguyên tên thuộc tính và hằng."""

    def __init__(self) -> None:
        self.names: Dict[str, str] = {}

    def _name(self, name: str) -> str:
        return self.names.setdefault(name, f"v{len(self.names)}")

    def visit_Name(self, node: ast.Name) -> ast.AST:
        return ast.copy_location(ast.Name(id=self._name(node.id), ctx=node.ctx), node)

    def visit_arg(self, node: ast.arg) -> ast.AST:
        return ast.copy_location(ast.arg(arg=self._name(node.arg), annotation=None), node)


def _fingerprint(func: ast.AST) -> str:
    body = list(func.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]  # bỏ docstring
    norm = _Normalize()
    norm.visit(func.args)
    dumped = "".join(ast.dump(norm.visit(stmt), annotate_fields=False, include_attributes=False) for stmt in body)
    return hashlib.sha1(dumped.encode()).hexdigest()


def find_logic_duplicates(files: Sequence[Path], root: Path) -> List[List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for path in files:
        tree = _parse(path)
        if tree is None:
            continue
        for func, cls in _functions(tree):
            if (func.end_lineno or func.lineno) - func.lineno + 1 < MIN_LINES:
                continue
            name = f"{cls}.{func.name}" if cls else func.name
            groups[_fingerprint(func)].append({"name": name, "file": _rel(path, root), "line": func.lineno,
                                               "lines": (func.end_lineno or func.lineno) - func.lineno + 1})
    result = [g for g in groups.values() if len(g) >= 2 and len({f["file"] for f in g}) >= 2]
    return sorted(result, key=lambda g: (-g[0]["lines"] * len(g), g[0]["file"]))


# ---------------------------------------------------------------- D. trùng tên
def find_name_duplicates(files: Sequence[Path], root: Path) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """Hàm cấp module và method private (một dấu _) cùng tên ở >= 2 file. Method public là giao diện chung nên bỏ."""
    by_name: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for path in files:
        tree = _parse(path)
        if tree is None:
            continue
        for func, cls in _functions(tree):
            name = func.name
            if name.startswith("__") or name in COMMON_NAMES or name.startswith("test_"):
                continue
            if cls and not name.startswith("_"):
                continue
            by_name[name].append({"file": _rel(path, root), "line": func.lineno, "class": cls,
                                  "lines": (func.end_lineno or func.lineno) - func.lineno + 1})
    result = [(n, f) for n, f in by_name.items() if len({x["file"] for x in f}) >= 2]
    return sorted(result, key=lambda item: (-len({x["file"] for x in item[1]}), item[0]))


# ---------------------------------------------------------------- B. module không ai import
def _module_name(path: Path, root: Path) -> str:
    parts = list(path.resolve().relative_to(root.resolve()).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imported_names(path: Path, root: Path) -> set:
    tree = _parse(path)
    names: set = set()
    if tree is None:
        return names
    here = _module_name(path, root).split(".") if path.resolve().is_relative_to(root.resolve()) else []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                pkg = here[:-node.level] if path.name != "__init__.py" else here[: len(here) - node.level + 1]
                base = ".".join([*pkg, base] if base else pkg)
            names.add(base)
            names.update(f"{base}.{a.name}" for a in node.names)
    return names


def _is_entry_point(path: Path) -> bool:
    if path.name in ("__init__.py", "main.py", "conftest.py") or "dags" in path.parts:
        return True
    text = path.read_text(encoding="utf-8", errors="ignore")
    return bool(re.search(r"__name__\s*==\s*['\"]__main__['\"]", text))


def _matches(module: str, imported: set) -> bool:
    short = module.split(".", 1)[1] if "." in module else module  # import qua sys.path (vd. app.core, tên script)
    candidates = {module, short, module.rsplit(".", 1)[-1]}
    return any(name == c or name.startswith(c + ".") or name.endswith("." + c) for name in imported for c in candidates)


def find_orphan_modules(files: Sequence[Path], root: Path, test_files: Sequence[Path] = ()) -> List[Dict[str, Any]]:
    imports = {p: _imported_names(p, root) for p in files}
    test_imports: set = set()
    for p in test_files:
        test_imports |= _imported_names(p, root)
    result = []
    for path in files:
        if _is_entry_point(path):
            continue
        module = _module_name(path, root)
        used = set().union(*(names for other, names in imports.items() if other != path)) if len(files) > 1 else set()
        if _matches(module, used):
            continue
        result.append({"file": _rel(path, root), "only_tests": _matches(module, test_imports)})
    return result


# ---------------------------------------------------------------- B. hàm không ai gọi (vulture)
def find_unused_code(paths: Sequence[Path], root: Path, min_confidence: int = 60) -> List[Dict[str, Any]]:
    cmd = [sys.executable, "-m", "vulture", *map(str, paths), "--min-confidence", str(min_confidence),
           "--ignore-decorators", VULTURE_IGNORE_DECORATORS, "--ignore-names", VULTURE_IGNORE_NAMES]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=root).stdout
    found = []
    for line in out.splitlines():
        m = re.match(r"(.+?):(\d+): unused (\w+) '([^']+)' \((\d+)% confidence", line)
        if m and m.group(3) in VULTURE_KINDS:
            found.append({"file": _rel(Path(m.group(1)) if Path(m.group(1)).is_absolute() else root / m.group(1), root),
                          "line": int(m.group(2)), "kind": m.group(3), "name": m.group(4), "confidence": int(m.group(5))})
    return found


def _used_in_tests(name: str, tests_dir: Optional[Path]) -> bool:
    if not tests_dir or not tests_dir.exists():
        return False
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    return any(pattern.search(p.read_text(encoding="utf-8", errors="ignore")) for p in tests_dir.rglob("*.py"))


# ---------------------------------------------------------------- A. ruff
def ruff_findings(paths: Sequence[Path], root: Path) -> List[Dict[str, Any]]:
    ruff = shutil.which("ruff", path=str(Path(sys.executable).parent)) or shutil.which("ruff")
    if not ruff:
        return []
    cmd = [ruff, "check", *map(str, paths), "--select", "F401,F811,F841", "--output-format", "json",
           "--no-fix", "--exit-zero", "--isolated", "--extend-exclude", "*.ipynb"]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=root).stdout
    try:
        items = json.loads(out or "[]")
    except ValueError:
        return []
    return [{"file": _rel(Path(i["filename"]), root), "line": i["location"]["row"], "code": i["code"],
             "message": i["message"]} for i in items]


# ---------------------------------------------------------------- báo cáo
RUFF_LABEL = {"F401": "import thừa", "F841": "biến không dùng", "F811": "khai báo lại"}


def build_report(paths: Sequence[Path], root: Path, out: Path, tests_dir: Optional[Path] = None) -> Dict[str, int]:
    files = collect_files(paths)
    test_files = collect_files([tests_dir]) if tests_dir and tests_dir.exists() else []
    ruff = ruff_findings(paths, root)
    unused = find_unused_code(paths, root)
    orphans = find_orphan_modules(files, root, test_files)
    logic = find_logic_duplicates(files, root)
    names = find_name_duplicates(files, root)

    counts = {"ruff": len(ruff), "unused": len(unused), "orphans": len(orphans), "logic": len(logic), "names": len(names)}
    lines = [
        "# Báo cáo chất lượng code",
        "",
        f"Sinh bởi `python scripts/report_code_quality.py` ngày {date.today():%d/%m/%Y}. Chỉ là danh sách để duyệt: "
        "chưa xóa hay gộp gì. Chạy lại bằng `make quality`.",
        "",
        f"Phạm vi: {', '.join(f'`{_rel(p, root)}`' for p in paths)}. Không quét `preprocessing/` và `tests/`.",
        "",
        "| Bảng | Kiểm tra | Số mục |",
        "|---|---|---|",
        f"| A | Import thừa, biến không dùng, khai báo lại (ruff) | {len(ruff)} |",
        f"| B1 | Hàm, method, class không ai gọi (vulture) | {len(unused)} |",
        f"| B2 | Module không ai import | {len(orphans)} |",
        f"| C | Nhóm hàm trùng logic giữa các file | {len(logic)} |",
        f"| D | Tên hàm trùng ở nhiều file | {len(names)} |",
        "",
        "## A. Import thừa, biến không dùng, khai báo lại",
        "",
        "Ruff tự sửa được phần lớn (`ruff check --select F401,F841 --fix`), nhưng import trong `__init__.py` có thể là "
        "API công khai, cần xem trước khi xóa.",
        "",
    ]
    by_file: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in ruff:
        by_file[item["file"]].append(item)
    if by_file:
        lines += ["| File | Số mục | Chi tiết (dòng: nội dung) |", "|---|---|---|"]
        for f, items in sorted(by_file.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            detail = "; ".join(f"{i['line']}: {RUFF_LABEL.get(i['code'], i['code'])} {i['message'].split('`')[1] if '`' in i['message'] else ''}"
                               for i in items[:8])
            more = f"; … và {len(items) - 8} mục nữa" if len(items) > 8 else ""
            lines.append(f"| `{f}` | {len(items)} | {detail}{more} |")
    else:
        lines.append("Không có.")

    lines += ["", "## B. Code chết", "", "### B1. Hàm, method, class không ai gọi", "",
              "vulture tìm theo tên trong phạm vi quét, độ tin cậy 60% (hàm luôn ở mức này). Cột \"Test dùng\" là tên "
              "có xuất hiện trong `tests/`: có thì code chỉ còn test gọi. Hàm được gọi qua `getattr`, chuỗi, hay từ "
              "notebook thì vulture không thấy, nên phải tìm lại trước khi xóa.", ""]
    if unused:
        lines += ["| Vị trí | Loại | Tên | Test dùng |", "|---|---|---|---|"]
        for u in unused:
            lines.append(f"| `{u['file']}:{u['line']}` | {u['kind']} | `{u['name']}` | "
                         f"{'có' if _used_in_tests(u['name'].split('.')[-1], tests_dir) else 'không'} |")
    else:
        lines.append("Không có.")
    lines += ["", "### B2. Module không ai import", "",
              "Không tính entry point (`__init__.py`, `main.py`, file có `if __name__ == \"__main__\"`, DAG Airflow).", ""]
    if orphans:
        lines += ["| Module | Chỉ test import |", "|---|---|"]
        lines += [f"| `{o['file']}` | {'có' if o['only_tests'] else 'không'} |" for o in orphans]
    else:
        lines.append("Không có.")

    lines += ["", "## C. Hàm trùng logic giữa các file", "",
              f"Hai hàm cùng nhóm có thân giống hệt nhau sau khi đổi tên biến và tham số (hàm từ {MIN_LINES} dòng). "
              "Ứng viên để gộp vào `collection/common/`.", ""]
    if logic:
        lines += ["| Nhóm | Số dòng | Các bản |", "|---|---|---|"]
        for idx, group in enumerate(logic, 1):
            copies = "<br>".join(f"`{f['file']}:{f['line']}` `{f['name']}`" for f in group)
            lines.append(f"| C{idx} | {group[0]['lines']} | {copies} |")
    else:
        lines.append("Không có.")

    lines += ["", "## D. Tên hàm trùng ở nhiều file", "",
              "Hàm cấp module và method private (`_tên`) cùng tên ở từ 2 file. Cùng tên chưa chắc cùng việc: xem bảng C "
              "để biết bản nào giống hệt. Method public như `discover_urls` là giao diện chung nên không liệt kê.", ""]
    if names:
        lines += ["| Tên | Số file | Vị trí |", "|---|---|---|"]
        for name, found in names:
            where = "<br>".join(f"`{f['file']}:{f['line']}`" + (f" ({f['class']})" if f["class"] else "") for f in found)
            lines.append(f"| `{name}` | {len({f['file'] for f in found})} | {where} |")
    else:
        lines.append("Không có.")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "code_quality.md")
    args = parser.parse_args()
    paths = [ROOT / p for p in SCOPE if (ROOT / p).exists()]
    counts = build_report(paths, ROOT, args.out, tests_dir=ROOT / "tests")
    print(f"Đã ghi {args.out}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
