# -*- coding: utf-8 -*-
"""preprocessing.transformation.headcount_parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bóc tách chỉ tiêu tuyển dụng headcount theo luật T5.
"""

from __future__ import annotations

import re
from typing import Optional


def parse_headcount(raw_headcount: Optional[str]) -> Optional[int]:
    """Trích xuất số lượng tuyển dụng nguyên dương đầu tiên."""
    if not raw_headcount or not str(raw_headcount).strip():
        return None

    s = str(raw_headcount).strip()
    match = re.search(r"\b(\d+)\b", s)
    if match:
        val = int(match.group(1))
        return val if val > 0 else None
    return None
