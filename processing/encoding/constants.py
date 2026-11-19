# -*- coding: utf-8 -*-
"""Hằng dùng chung cho bước 10 (F10.4, PRE-39): chuyển từ `preprocessing/encoding/run.py` sang `processing/`.

`preprocessing/encoding/run.py` import lại từ đây để code cũ của bước 05 vẫn chạy.
"""
from __future__ import annotations

import re

from preprocessing.common.province import fold
from preprocessing.normalization.text_cleaner import SENIORITY_LABELS as SENIORITY_ORDER

SENIORITY_MAP = {lab: idx for idx, lab in enumerate(SENIORITY_ORDER)}  # null -> -1 ở bên dùng
TOP_PROVINCES_K = 10


def to_col_slug(text: str) -> str:
    """Tạo slug chuẩn cho tên cột (chữ thường, ascii, gạch dưới)."""
    s = str(text or "").lower()
    s = s.replace("c#", "csharp").replace(".net", "dotnet").replace("c++", "cpp")
    s = fold(s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "unknown"
