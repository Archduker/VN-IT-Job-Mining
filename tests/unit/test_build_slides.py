# -*- coding: utf-8 -*-
"""Slide thuyết trình: bảng vấn đề ↔ luật phải khớp hai chiều với luật trong báo cáo."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from build_slides import ISSUE_TO_RULES, check_links, n, pct  # noqa: E402


def test_check_links_catches_both_directions():
    rules = {r for rs in ISSUE_TO_RULES.values() for r in rs}
    assert check_links(ISSUE_TO_RULES, rules) == []
    assert "luật Z9 không giải vấn đề nào" in check_links(ISSUE_TO_RULES, rules | {"Z9"})
    assert "luật C1 không có trong báo cáo" in check_links(ISSUE_TO_RULES, rules - {"C1"})
    assert "vấn đề X không có luật" in check_links({**ISSUE_TO_RULES, "X": []}, rules)


def test_vietnamese_number_format():
    assert n(14292) == "14.292" and pct(54.1) == "54,1%"
