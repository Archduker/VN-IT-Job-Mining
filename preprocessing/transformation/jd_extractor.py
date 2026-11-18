# -*- coding: utf-8 -*-
"""Bước 03 T9: rút hình thức làm việc, loại hợp đồng, kinh nghiệm từ ô của sàn và từ JD.

Đặc tả: docs/spec/preprocessing/03_transformation.md mục 2.2–2.3. Luật nằm trong
preprocessing/dictionaries/jd_extraction.json (người dùng duyệt 18/11/2026); file này chỉ áp luật.

- Regex + từ điển, không dùng model. Khớp theo từ nguyên vẹn, trên văn bản gốc (không đọc bản dịch).
- Bước 03 chỉ ghi giá trị raw, giá trị JD và cờ lệch; bước 04 chọn giá trị cuối.
- Các hàm thuần, không I/O ngoài lần đọc từ điển đầu tiên.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator, Optional

DICT_PATH = Path(__file__).resolve().parent.parent / "dictionaries" / "jd_extraction.json"
_F = re.IGNORECASE
_WINDOW = 6  # số từ hai bên cụm số năm khi tìm ngữ cảnh "kinh nghiệm"
_ET_ORDER = ("internship", "part_time", "contract", "full_time")
_STRONG_IDS = {"WH4", "WH5"}  # mẫu có số ngày cụ thể: thắng ô của sàn khi lệch (người dùng chốt 18/11)


class DictionaryNotApproved(RuntimeError):
    """Từ điển chưa được người dùng duyệt (`_meta.approved` khác true)."""


@dataclass(frozen=True)
class _Pattern:
    id: str
    value: str
    where: str  # title | body | title+body
    rx: re.Pattern


@dataclass(frozen=True)
class _Topic:
    patterns: tuple[_Pattern, ...]
    noise: dict[str, Optional[re.Pattern]]


@dataclass(frozen=True)
class Rules:
    work_mode: _Topic
    employment_type: _Topic
    wm_raw_map: dict[str, str]
    et_raw_map: dict[str, Optional[str]]
    exp_rx: re.Pattern
    exp_ctx: re.Pattern
    exp_noise: re.Pattern
    exp_zero: re.Pattern


def _alt(items: list[str]) -> Optional[re.Pattern]:
    return re.compile("|".join(f"(?:{x})" for x in items), _F) if items else None


def _topic(spec: dict[str, Any]) -> _Topic:
    pats = tuple(_Pattern(p["id"], val, p["where"], re.compile(p["re"], _F))
                 for val, ps in spec["jd_patterns"].items() for p in ps)
    noise = {k: _alt(v) for k, v in spec["jd_noise"].items() if not k.startswith("_")}
    return _Topic(pats, noise)


@lru_cache(maxsize=4)
def load_rules(path: str = str(DICT_PATH)) -> Rules:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("_meta", {}).get("approved") is not True:
        raise DictionaryNotApproved(f"{path}: _meta.approved khác true, chưa được duyệt nên không chạy T9")
    g = d["experience"]["grammar"]
    return Rules(
        work_mode=_topic(d["work_mode"]),
        employment_type=_topic(d["employment_type"]),
        wm_raw_map={k: v for k, v in d["work_mode"]["raw_map"].items() if not k.startswith("_")},
        et_raw_map={k: v for k, v in d["employment_type"]["raw_map"].items() if not k.startswith("_")},
        exp_rx=re.compile(r"(?:(dưới|under|less than)\s*)?" + g["prefix"] + r"\s*" + g["number"] + r"\s*" + g["unit"], _F),
        exp_ctx=re.compile(g["context"], _F),
        exp_noise=_alt(d["experience"]["noise"]),
        exp_zero=_alt(d["experience"]["zero_phrases"]),
    )


# ---------------------------------------------------------------- văn bản
def norm(s: Any) -> str:
    """NFC + gộp khoảng trắng; giá trị không phải chuỗi thành rỗng."""
    return " ".join(unicodedata.normalize("NFC", s).split()) if isinstance(s, str) else ""


def sentences(text: Any) -> Iterator[str]:
    """Tách theo dòng, và theo dấu kết câu đứng trước chữ hoa."""
    if not isinstance(text, str):
        return
    for ln in re.split(r"[\n\r]+|(?<=[.;!?])\s+(?=[A-ZĐÀ-Ỵ])", unicodedata.normalize("NFC", text)):
        ln = " ".join(ln.split())
        if ln:
            yield ln


def hits(topic: _Topic, title: str, body: list[str]) -> list[tuple[str, str, str, str]]:
    """[(giá trị, mã mẫu, 'title'|'body', dòng khớp)]; mỗi mẫu tính tối đa một lần, tiêu đề xét trước."""
    out = []
    for p in topic.patterns:
        nz = topic.noise.get(p.value)
        cands = {"title": [("title", title)], "body": [("body", b) for b in body],
                 "title+body": [("title", title)] + [("body", b) for b in body]}[p.where]
        for where, ln in cands:
            if ln and p.rx.search(nz.sub(" ", ln) if nz else ln):
                out.append((p.value, p.id, where, ln))
                break
    return out


def _resolve_mode(vals: list[str]) -> Optional[str]:
    s = set(vals)
    if not s:
        return None
    if "hybrid" in s or {"remote", "onsite"} <= s:
        return "hybrid"
    return next(iter(s))


# ---------------------------------------------------------------- T9a
def work_mode_raw(source: str, raw_work_mode: Any, raw_employment_type: Any, rules: Rules | None = None) -> Optional[str]:
    r = rules or load_rules()
    if isinstance(raw_work_mode, str) and raw_work_mode.strip():
        # topcv cho chọn nhiều giá trị, ngăn bởi ", " trước chữ hoa đầu mục
        parts = [r.wm_raw_map.get(p.strip().lower()) for p in re.split(r",\s*(?=[A-ZKL])", norm(raw_work_mode))]
        return _resolve_mode([p for p in parts if p])
    et = norm(raw_employment_type).lower()
    if source == "jobsgo" and "remote" in [x.strip() for x in et.split(",")]:
        return "remote"
    if source == "topcv" and et == "làm tại nhà":
        return "remote"
    if source == "vietnamworks" and et == "7":
        return "remote"
    return None


def work_mode(rec: dict[str, Any], rules: Rules | None = None) -> dict[str, Any]:
    r = rules or load_rules()
    title = norm(rec.get("job_title_clean") or rec.get("job_title"))
    body = list(sentences(rec.get("description_clean"))) + list(sentences(rec.get("requirements_clean")))
    hh = hits(r.work_mode, title, body)
    in_title = [v for v, _, w, _ in hh if w == "title"]
    jd = _resolve_mode(in_title) or _resolve_mode([v for v, *_ in hh])
    raw = work_mode_raw(str(rec.get("source_platform") or ""), rec.get("raw_work_mode"), rec.get("raw_employment_type"), r)
    strong = [v for v, pid, w, _ in hh if w == "title" or pid in _STRONG_IDS]
    return {
        "work_mode_raw": raw,
        "work_mode_jd": jd,
        "work_mode_jd_rules": sorted({pid for _, pid, *_ in hh}),
        # Tín hiệu mạnh thì 04 cho JD thắng raw; giá trị mạnh là _resolve_mode(strong), trùng jd khi có tiêu đề
        "work_mode_jd_strong": bool(strong) and _resolve_mode(strong) == jd,
        "work_mode_conflict": bool(raw and jd and raw != jd),
    }


# ---------------------------------------------------------------- T9b
def employment_types_raw(raw_employment_type: Any, rules: Rules | None = None) -> list[str]:
    r = rules or load_rules()
    out: list[str] = []
    for p in (x.strip().lower() for x in norm(raw_employment_type).split(",")):
        v = r.et_raw_map.get(p)
        if isinstance(v, str) and not v.startswith("->") and v not in out:
            out.append(v)
    return out


def employment_type(rec: dict[str, Any], rules: Rules | None = None) -> dict[str, Any]:
    r = rules or load_rules()
    title = norm(rec.get("job_title_clean") or rec.get("job_title"))
    body = list(sentences(rec.get("description_clean"))) + list(sentences(rec.get("requirements_clean")))
    found = {v for v, *_ in hits(r.employment_type, title, body)}
    jd = next((o for o in _ET_ORDER if o in found), None)
    lst = employment_types_raw(rec.get("raw_employment_type"), r)
    raw = lst[0] if lst else None
    return {
        "employment_type_raw": raw,
        "employment_types_raw": lst,
        "employment_type_jd": jd,
        "employment_type_conflict": bool(raw and jd and raw != jd and jd != "full_time"),
    }


# ---------------------------------------------------------------- T9c
def _num(s: str) -> float:
    return float(s.replace(",", "."))


def experience_from_lines(lines: list[str], rules: Rules | None = None) -> Optional[dict[str, Any]]:
    """Cụm hợp lệ đầu tiên theo thứ tự dòng; trong một dòng, cụm số trước cụm '0 năm'."""
    r = rules or load_rules()
    for ln in lines:
        for m in r.exp_rx.finditer(ln):
            before = " ".join(ln[:m.start()].split()[-_WINDOW:])
            after = " ".join(ln[m.end():].split()[:_WINDOW])
            win = f"{before} {m.group(0)} {after}"
            if not r.exp_ctx.search(win) or r.exp_noise.search(win):
                continue
            lo = _num(m.group(2))
            hi = _num(m.group(3)) if m.group(3) else None
            k = 1 / 12 if m.group(4).lower().startswith(("tháng", "month")) else 1.0
            if m.group(1):  # "dưới N năm"
                lo, hi = 0.0, lo
            lo, hi = round(lo * k, 2), (round(hi * k, 2) if hi is not None else None)
            if lo > 20:
                continue
            if hi is not None and hi < lo:
                hi = None
            return {"exp_min_years_jd": lo, "exp_max_years_jd": hi, "exp_jd_kind": "jd", "exp_jd_text": m.group(0).strip()}
        z = r.exp_zero.search(ln)
        if z and not r.exp_noise.search(ln):
            return {"exp_min_years_jd": 0.0, "exp_max_years_jd": None, "exp_jd_kind": "jd_zero", "exp_jd_text": z.group(0)}
    return None


def experience(rec: dict[str, Any], rules: Rules | None = None) -> dict[str, Any]:
    lines = list(sentences(rec.get("requirements_clean"))) + list(sentences(rec.get("description_clean")))
    got = experience_from_lines(lines, rules)
    return got or {"exp_min_years_jd": None, "exp_max_years_jd": None, "exp_jd_kind": None, "exp_jd_text": None}


def extract(rec: dict[str, Any], rules: Rules | None = None) -> dict[str, Any]:
    """Mọi cột T9 cho một dòng của bảng 03 (cần `*_clean`, `raw_work_mode`, `raw_employment_type`, `source_platform`)."""
    r = rules or load_rules()
    return {**work_mode(rec, r), **employment_type(rec, r), **experience(rec, r)}


T9_COLUMNS = ("work_mode_raw", "work_mode_jd", "work_mode_jd_rules", "work_mode_jd_strong", "work_mode_conflict",
              "employment_type_raw", "employment_types_raw", "employment_type_jd", "employment_type_conflict",
              "exp_min_years_jd", "exp_max_years_jd", "exp_jd_kind", "exp_jd_text")
