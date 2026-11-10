"""Tầng 2 - Khử trùng lặp đa sàn (Inter-Source Entity Resolution), docs/spec/05 mục 3.2.

Giai đoạn:
  A. Blocking Key (`blocking.blocking_key`) - chỉ còn dùng làm khóa mô tả/audit.
  B. Cặp trùng: sha1(text_fold) ở đây, MinHash/Jaccard ở `minhash.py` (PH4, thay TF-IDF cosine).
  C. Golden Record Master Fusion (bảng mục 3.2.C): hợp nhất thành một bản ghi vàng,
     không xóa dữ liệu - bản thua vẫn được ghi trong `merged_from` của bản thắng.

Không dùng model/embedding nào (P0 mục 6): tất định.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from preprocessing.deduplication.blocking import blocking_key
from preprocessing.deduplication.text_norm import clean_text, fold

SALARY_NUMBER = re.compile(r"\d")

# Thứ tự uy tín tiêu đề khi hợp nhất: ITviec > TopDev > VietnamWorks > sàn khác (SPEC-05 mục 3.2.C)
PLATFORM_AUTHORITY = ("itviec", "topdev", "vietnamworks", "topcv", "careerviet", "glints", "jobsgo", "vieclam24h")

Item = dict[str, Any]


# ---------------------------------------------------------------- A. blocking
def build_blocks(items: Sequence[Item]) -> dict[str, list[Item]]:
    """Gán và chia block theo Blocking Key (Giai đoạn A)."""
    blocks: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        it["bkey"] = it.get("bkey") or blocking_key(it["flat"])
        blocks[it["bkey"]].append(it)
    return blocks


# ---------------------------------------------------------------- B. tầng 2 liên sàn
def exact_cross_pairs(items: Sequence[Item]) -> list[tuple[Item, Item, float]]:
    """Cặp khác nguồn trùng sha1(text_fold) và cùng company_slug (khóa `fkey`), tính trước MinHash (D4)."""
    by_hash: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        if it["fkey"]:
            by_hash[it["fkey"]].append(it)
    hits: list[tuple[Item, Item, float]] = []
    for g in by_hash.values():
        if len({x["src"] for x in g}) < 2:
            continue
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                if g[i]["src"] != g[j]["src"]:
                    hits.append((g[i], g[j], 1.0))
    return hits


def clusters(items: Sequence[Item], pairs: Sequence[tuple[Item, Item, float]]) -> list[list[Item]]:
    """Nối các cặp trùng thành cụm bằng union-find (tính bắc cầu của quan hệ cùng vị trí thật)."""
    parent = {id(it): id(it) for it in items}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, _ in pairs:
        ra, rb = find(id(a)), find(id(b))
        if ra != rb:
            parent[ra] = rb

    groups: dict[int, list[Item]] = defaultdict(list)
    for it in items:
        groups[find(id(it))].append(it)
    return [g for g in groups.values() if len(g) > 1]


# ---------------------------------------------------------------- C. golden fusion
def authority(src: str) -> int:
    """Số thứ tự uy tín sàn (nhỏ hơn = uy tín hơn) theo SPEC-05 mục 3.2.C."""
    return PLATFORM_AUTHORITY.index(src) if src in PLATFORM_AUTHORITY else len(PLATFORM_AUTHORITY)


def _longest(group: Iterable[Item], field: str) -> Any:
    return max((g["flat"].get(field) for g in group), key=lambda v: len(clean_text(v)), default=None)


def _pick_title(group: Sequence[Item]) -> Any:
    win = min(group, key=lambda g: (authority(g["src"]), -len(clean_text(g["flat"].get("job_title")))))
    return win["flat"].get("job_title")


def _pick_salary(group: Sequence[Item]) -> tuple[Any, str]:
    """Ưu tiên bản ghi có khoảng lương số thay vì 'Thỏa thuận' (SPEC-05 mục 3.2.C)."""
    numeric = [g for g in group if SALARY_NUMBER.search(clean_text(g["flat"].get("raw_salary_text")))]
    win = numeric[0] if numeric else max(group, key=lambda g: len(clean_text(g["flat"].get("raw_salary_text"))))
    return win["flat"].get("raw_salary_text"), win["src"]


def parse_date(value: Any) -> datetime | None:
    """ISO hoặc ngày VN; thời gian không offset được hiểu theo Asia/Ho_Chi_Minh (+07).

    Giá trị không hiểu được không tham gia min/max; raw vẫn được giữ nguyên.
    """
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
        for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(
        tzinfo=timezone(timedelta(hours=7)))).astimezone(UTC)


def _dates(group: Sequence[Item]) -> tuple[str, str]:
    def select(values, latest=False):
        valid = [(parsed, str(v)) for v in values if (parsed := parse_date(v)) is not None]
        return (max(valid) if latest else min(valid))[1] if valid else ""

    return (select(g["flat"].get("raw_posted_date") for g in group),
            select((g["seen_at"] for g in group), latest=True))


def fuse(cluster: Sequence[Item]) -> dict[str, Any]:
    """Hợp nhất một cụm thành Golden Record theo bảng SPEC-05 mục 3.2.C."""
    ordered = sorted(cluster, key=lambda g: (authority(g["src"]), g["jid"]))
    salary, salary_src = _pick_salary(ordered)
    skills: list[str] = []
    seen_skill: set[str] = set()
    for g in ordered:  # Set Union S1 u S2 u ... Sk
        for s in g["flat"].get("skills_list") or []:
            t = clean_text(s)
            if t and t.lower() not in seen_skill:
                seen_skill.add(t.lower())
                skills.append(t)
    first_posted, last_seen = _dates(ordered)
    anchor = ordered[0].get("bkey") or f"{ordered[0]['src']}:{ordered[0]['jid']}"
    return {
        # UUID v5 theo Blocking_Key; thêm neo job_id đầu cụm để hai cụm cùng key không trùng master_id
        "master_id": str(uuid.uuid5(uuid.NAMESPACE_OID, f"{anchor}|{ordered[0]['src']}:{ordered[0]['jid']}")),
        "job_title": _pick_title(ordered),
        "company_name": _longest(ordered, "company_name"),
        "job_description": _longest(ordered, "raw_description_text"),
        "requirements": _longest(ordered, "raw_requirements_text"),
        "skills_extracted": skills,
        "salary_text": salary,
        "salary_source_platform": salary_src if SALARY_NUMBER.search(clean_text(salary)) else None,
        "location": _longest(ordered, "raw_location_text"),
        "source_platforms": sorted({g["src"] for g in ordered}, key=authority),
        "source_job_ids": [f"{g['src']}:{g['jid']}" for g in ordered],
        "source_urls": [g["url"] for g in ordered],
        "blocking_key": ordered[0].get("bkey"),
        "content_hashes": [g["chash"] for g in ordered],
        # Reposts đã loại ở D2 phải đi theo cả thành viên thua ở tầng liên sàn.
        "repost_records": sorted(
            (r for g in ordered for r in g.get("reposts", [])),
            key=lambda r: (r["source"], r["job_id"])),
        "unparsed_dates": [
            {"source": g["src"], "job_id": g["jid"], "field": field, "value": str(value)}
            for g in ordered
            for field, value in (("raw_posted_date", g["flat"].get("raw_posted_date")),
                                 ("scraped_at", g["seen_at"]))
            if value and parse_date(value) is None],
        "first_posted_at": first_posted,
        "last_seen_at": last_seen,
        "duplicate_count": len(ordered),
        "is_cross_platform": len({g["src"] for g in ordered}) > 1,
    }
