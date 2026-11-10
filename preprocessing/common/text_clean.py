# -*- coding: utf-8 -*-
"""PH2 bước 2 (T6): làm sạch ký tự. Spec: docs/spec/preprocessing/spec/PH2_schema_va_lam_sach_ky_tu.md.

`clean_text` giữ hoa thường, dấu, xuống dòng (không xóa boilerplate). `*_norm` = mở rộng viết tắt
đã duyệt + lower; `*_fold` = bỏ dấu (dùng lại `text_norm.fold`, không viết bản thứ bảy).
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from preprocessing.deduplication.text_norm import fold
from preprocessing.transformation.bullet_stitcher import stitch_fragmented_bullets
from preprocessing.transformation.html_cleaner import _ANY_TAG, strip_html_tags

MAX_RETRIES = 3  # số lần lặp tối đa khi còn HTML/NFD; hết lượt chỉ cảnh báo, không dừng pipeline
ABBREV_FILE = Path(__file__).resolve().parents[1] / "dictionaries" / "abbreviations.json"

_HIDDEN = re.compile("[​‌‍⁠﻿]")
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
_SPACES = re.compile("[\xa0 -   　]")
_DASH = re.compile("[–—−‐‑‒]")
# Ký hiệu bullet chắc chắn (đứng riêng ở đầu dòng) và "*"/"+" chỉ khi theo sau là dấu cách
_BULLET = re.compile(r"^[ \t]*(?:(?:[•✔✓➢➤●▪▫○◦★✅]+|[*+](?=[ \t])|-(?=[ \t]))[ \t]*)+", re.M)
_LI = re.compile(r"<li\b[^<>]*>", re.I)


def html_residual(s: Optional[str]) -> bool:
    # Không dùng regex &\w+; đơn thuần: "F&B; trường", "P&L; giao tiếp" không phải entity
    return bool(s) and (bool(_ANY_TAG.search(s)) or html.unescape(s) != s)


def is_nfc(s: Optional[str]) -> bool:
    return not s or unicodedata.is_normalized("NFC", s)


def _once(s: str) -> Optional[str]:
    s = strip_html_tags(_LI.sub("\n- ", s))  # <li> thành bullet chuẩn
    if not s:
        return None
    s = unicodedata.normalize("NFC", s)
    s = _HIDDEN.sub("", s)
    s = _CTRL.sub("", _SPACES.sub(" ", s.replace("\r", "\n")))
    s = _DASH.sub("-", s)
    s = _BULLET.sub("- ", s)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in s.split("\n")]
    return "\n".join(ln for ln in lines if ln) or None


def clean_text_checked(raw: Any) -> Tuple[Optional[str], Dict[str, bool]]:
    """Trả (văn bản sạch, info). info: cờ 'trước' (html/nfc/hidden/dash_bullet) và 'sau' (residual_*)."""
    if raw is None or not str(raw).strip():
        return None, {}
    raw = str(raw)
    info = {
        "html": html_residual(raw), "nfc": not is_nfc(raw), "hidden": bool(_HIDDEN.search(raw)),
        "dash_bullet": bool(_DASH.search(raw) or re.search(r"^[ \t]*[•✔✓➢➤●▪▫○◦★✅*+]", raw, re.M)),
    }
    s: Optional[str] = raw
    for _ in range(MAX_RETRIES):  # lặp lại bước HTML/chuẩn hóa tới khi sạch
        s = _once(s)
        if not s or not (html_residual(s) or not is_nfc(s)):
            break
    if s:
        s = "\n".join(stitch_fragmented_bullets(s)) or None
    info.update(residual_html=html_residual(s), residual_nfd=not is_nfc(s),
                residual_hidden=bool(s and _HIDDEN.search(s)))
    return s, info


def clean_text(raw: Any) -> Optional[str]:
    return clean_text_checked(raw)[0]


def compile_abbreviations(entries: List[Dict[str, Any]]) -> List[Tuple[re.Pattern, str]]:
    """Chỉ nhận mục approved=True; khớp theo từ nguyên vẹn."""
    out = []
    for e in entries:
        if e.get("approved") is not True:
            continue
        flags = 0 if e.get("case_sensitive") else re.IGNORECASE
        for v in e.get("variants", []):
            out.append((re.compile(rf"(?<!\w){re.escape(v)}(?!\w)", flags), e["canonical"]))
    return out


def load_abbreviations(path: Path = ABBREV_FILE) -> List[Tuple[re.Pattern, str]]:
    if not path.exists():
        return []
    return compile_abbreviations(json.loads(path.read_text(encoding="utf-8")).get("entries", []))


def make_text_columns(raw: Any, abbrev: Optional[List[Tuple[re.Pattern, str]]] = None
                      ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    clean = clean_text(raw)
    return _columns(clean, abbrev)


def _columns(clean: Optional[str], abbrev) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not clean:
        return None, None, None
    s = clean
    for pat, canon in abbrev or []:  # mở rộng trước khi lower để luật phân biệt hoa thường còn hiệu lực
        s = pat.sub(canon, s)
    norm = s.lower()
    return clean, norm, fold(norm)
