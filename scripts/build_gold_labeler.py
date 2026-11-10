#!/usr/bin/env python3
"""Nhúng 34 tỉnh và tên kỹ năng vào scripts/gold_labeler_template.html -> scripts/gold_labeler.html (mở thẳng bằng trình duyệt)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "preprocessing" / "dictionaries"


def _js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def main() -> None:
    provinces = [{"key": p["key"], "name": p["name"]} for p in json.loads((D / "provinces_34.json").read_text(encoding="utf-8"))["provinces"]]
    skills = sorted(json.loads((D / "skills.json").read_text(encoding="utf-8")))
    html = (ROOT / "scripts" / "gold_labeler_template.html").read_text(encoding="utf-8")
    html = html.replace("__PROVINCES__", _js(provinces)).replace("__SKILLS__", _js(skills))
    (ROOT / "scripts" / "gold_labeler.html").write_text(html, encoding="utf-8")
    print(f"gold_labeler.html: {len(provinces)} tỉnh, {len(skills)} kỹ năng")


if __name__ == "__main__":
    main()
