# -*- coding: utf-8 -*-
"""preprocessing.transformation.location_parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bóc tách địa điểm 3 cấp (dia_chi_cu_the, phuong_xa, tinh_thanh, raw) theo luật T8.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from preprocessing.common import REPO_ROOT
from preprocessing.common import province
from preprocessing.common.province import fold

WARDS_PATH = REPO_ROOT / "preprocessing" / "dictionaries" / "wards_34.json"

_LABEL = re.compile(r"^\s*(?:địa chỉ(?: trụ sở| làm việc| văn phòng)?|trụ sở(?: chính)?|văn phòng|address|office)\s*:\s*", re.IGNORECASE)
_PROVINCE_LABEL = re.compile(r"^\s*[^,:\d]{2,30}?\s+:\s*")  # "Hà Nội : Số 181 ..." -> "Số 181 ..."
_DISTRICT = re.compile(r"^(?:quận|huyện|thị xã|q\.|h\.|tx\.)\s*\S", re.IGNORECASE)
_WARD = re.compile(r"^(phường|p\.|xã|đặc khu)\s*(.+)$", re.IGNORECASE)
_COUNTRY = {"viet nam", "vietnam", "vn"}


@lru_cache(maxsize=1)
def _wards() -> Dict[str, Dict[str, str]]:
    """{tinh_key: {tên phường đã fold: tên chính thức}} theo danh mục 3.321 phường/xã mới."""
    doc = json.loads(WARDS_PATH.read_text(encoding="utf-8"))
    return {k: {fold(w): w for w in v["phuong_xa"]} for k, v in doc["tinh"].items()}


def match_ward(part: str, tinh_key: Optional[str]) -> Optional[str]:
    """Chỉ nhận phường/xã có tiền tố và có trong danh mục mới của đúng tỉnh; tên phường cũ thì None."""
    m = _WARD.match(part.strip())
    if not m or not tinh_key:
        return None
    kind = {"p.": "phường"}.get(m.group(1).lower(), m.group(1).lower())
    return _wards().get(tinh_key, {}).get(fold(f"{kind} {m.group(2).strip()}"))


def split_location(text: Optional[str]) -> Dict[str, Any]:
    """Tách địa chỉ thành {dia_chi_cu_the, phuong_xa, tinh_thanh, raw}; bỏ hẳn quận/huyện."""
    raw = str(text or "").strip()
    empty = {"dia_chi_cu_the": None, "phuong_xa": None, "tinh_thanh": None, "raw": raw}
    if not raw or fold(raw) in {"remote", "tu xa", "lam viec tu xa", "online"}:
        return empty

    line = next((ln for ln in raw.splitlines() if ln.strip()), "")
    line = re.sub(r"\([^)]*\)?", " ", line)  # "(Quận Tây Hồ, Hà Nội cũ)" là thông tin cũ
    line = _PROVINCE_LABEL.sub("", _LABEL.sub("", line))
    parts = [p.strip(" .") for p in re.split(r"[,|;]|\s+-\s+", line) if p.strip(" .")]

    tinh_key, tinh_idx = None, -1
    for idx in range(len(parts) - 1, -1, -1):
        k = province.key(parts[idx])
        if k:
            tinh_key, tinh_idx = k, idx
            break
    if tinh_key is None:  # tỉnh nằm ngoài dòng đầu hoặc chỉ có trong phần ngoặc
        tinh_key = province.key(raw)

    phuong_xa, specific = None, []
    for i, p in enumerate(parts):
        if i == tinh_idx or fold(p) in _COUNTRY or _DISTRICT.match(p):
            continue
        if _WARD.match(p):
            phuong_xa = phuong_xa or match_ward(p, tinh_key)
            continue
        if i < (tinh_idx if tinh_idx >= 0 else len(parts)):
            specific.append(p)

    return {
        "dia_chi_cu_the": ", ".join(specific) or None,
        "phuong_xa": phuong_xa,
        "tinh_thanh": province.name(tinh_key),
        "raw": raw,
    }


def parse_locations(
    working_locations: Any,
    raw_location_text: Optional[str],
    company_address: Optional[str]
) -> List[Dict[str, Any]]:
    """Lấy địa điểm theo thứ tự ưu tiên: working_locations -> raw_location_text -> company_address."""
    sources: List[str] = []
    if working_locations is not None:
        if isinstance(working_locations, (list, tuple)):
            sources = [str(x).strip() for x in working_locations if str(x).strip()]
        elif hasattr(working_locations, "tolist"):
            sources = [str(x).strip() for x in working_locations.tolist() if str(x).strip()]

    if not sources and raw_location_text and str(raw_location_text).strip():
        sources = [str(raw_location_text).strip()]
    elif not sources and company_address and str(company_address).strip():
        sources = [str(company_address).strip()]

    if not sources:
        return []

    return [split_location(src) for src in sources]
