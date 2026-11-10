# -*- coding: utf-8 -*-
"""PH6 N18: company_key bằng rapidfuzz trên toàn bảng. Tự gộp chỉ khi token_sort >= 90 VÀ (tên này là tập từ của tên kia
hoặc bằng nhau sau khi bỏ khoảng trắng). Cặp >= 90 còn lại ghi ra để người duyệt, không gộp tự động."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

_TONE = {
    "o": "óòỏõọ", "a": "áàảãạ", "e": "éèẻẽẹ", "u": "úùủũụ", "y": "ýỳỷỹỵ",
}


def fix_tone(s: str) -> str:
    """N18a: dấu thanh kiểu cũ -> kiểu mới (hoá -> hóa, qủy -> quỷ, khoẻ -> khỏe)."""
    # oa/oe: dấu về nguyên âm đầu (hoá -> hóa); uy: dấu về y (qủy -> quỷ), theo quy ước PH6 N18a
    for i in range(5):
        for second in ("a", "e"):
            s = s.replace("o" + _TONE[second][i], _TONE["o"][i] + second)
        s = s.replace(_TONE["u"][i] + "y", "u" + _TONE["y"][i])
    return re.sub(r"\s+", " ", s).strip()


def compute_company_keys(norms: Sequence[Optional[str]], threshold: int = 90
                         ) -> Tuple[Dict[str, Optional[str]], List[Tuple[str, str, float]]]:
    """Trả (map company_norm -> company_key, các cặp chờ duyệt). company_norm rỗng -> None."""
    from rapidfuzz import fuzz, process

    fixed = {n: fix_tone(n) for n in {x for x in norms if x}}
    uniq = sorted(set(fixed.values()))
    parent = list(range(len(uniq)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    pending: List[Tuple[str, str, float]] = []
    if uniq:
        mat = process.cdist(uniq, uniq, scorer=fuzz.token_sort_ratio, score_cutoff=threshold, workers=1)
        for i, j in zip(*mat.nonzero()):
            if i >= j:
                continue
            a, b = uniq[i], uniq[j]
            same = a.replace(" ", "") == b.replace(" ", "")
            if same or fuzz.token_set_ratio(a, b) == 100:
                parent[find(j)] = find(i)
            else:
                pending.append((a, b, float(mat[i, j])))
    groups: Dict[int, List[str]] = {}
    for i, n in enumerate(uniq):
        groups.setdefault(find(i), []).append(n)
    rep = {n: min(g, key=lambda x: (len(x), x)) for g in groups.values() for n in g}
    return {orig: rep[f] for orig, f in fixed.items()}, pending
