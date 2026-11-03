# -*- coding: utf-8 -*-
"""Tra tỉnh/thành theo 34 đơn vị sau sáp nhập (preprocessing/dictionaries/provinces_34.json).

Dùng ở 01 Clean (khóa trùng) và 04 Normalization (N1). Không viết bản thứ hai.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from preprocessing.common import REPO_ROOT

DICT_PATH = REPO_ROOT / "preprocessing" / "dictionaries" / "provinces_34.json"


def fold(text: Any) -> str:
    """Chữ thường, bỏ dấu, đ → d, mọi ký tự không phải chữ số thành khoảng trắng."""
    s = unicodedata.normalize("NFD", str(text or "")).lower()
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


@lru_cache(maxsize=1)
def _table() -> Tuple[Dict[str, Dict[str, Any]], List[Tuple[re.Pattern, str]], re.Pattern, re.Pattern]:
    doc = json.loads(DICT_PATH.read_text(encoding="utf-8"))
    by_key = {p["key"]: p for p in doc["provinces"]}
    names = []
    for p in doc["provinces"]:
        for n in {p["name"], *p["old"], *p["aliases"]}:
            names.append((fold(re.sub(r"^TP\.\s*", "", n)), p["key"]))
    names.sort(key=lambda x: -len(x[0]))  # tên dài trước: "ba ria vung tau" trước "vung tau"
    # "Nguyễn Huệ" là tên đường ở TP.HCM, không phải TP. Huế
    patterns = [(re.compile(("(?<!nguyen )" if n == "hue" else "") + rf"\b{re.escape(n)}\b"), k) for n, k in names if n]
    remote = re.compile(r"\b(" + "|".join(re.escape(fold(x)) for x in doc["remote"]) + r")\b")
    foreign = re.compile(r"\b(" + "|".join(re.escape(fold(x)) for x in doc["foreign"]) + r")\b")
    return by_key, patterns, remote, foreign


def find_all(text: Any) -> List[str]:
    """Mã các tỉnh xuất hiện trong chuỗi, theo vị trí xuất hiện, không lặp."""
    _, patterns, _, _ = _table()
    s = fold(text)
    hits: List[Tuple[int, str]] = []
    taken: List[Tuple[int, int]] = []
    for pat, key in patterns:
        for m in pat.finditer(s):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue  # đã nằm trong tên dài hơn
            taken.append((m.start(), m.end()))
            hits.append((m.start(), key))
    seen: List[str] = []
    for _, key in sorted(hits):
        if key not in seen:
            seen.append(key)
    return seen


def key(text: Any) -> Optional[str]:
    """Mã tỉnh của một địa điểm. Địa chỉ có nhiều tên tỉnh thì lấy tên ở cuối (tỉnh thường đứng cuối địa chỉ)."""
    found = find_all(text)
    return found[-1] if found else None


def name(province_key: Optional[str]) -> Optional[str]:
    return _table()[0][province_key]["name"] if province_key else None


def is_remote(text: Any) -> bool:
    return bool(_table()[2].search(fold(text)))


def is_foreign(text: Any) -> bool:
    return bool(_table()[3].search(fold(text)))
