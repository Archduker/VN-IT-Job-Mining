"""Tầng 2 - Khử trùng lặp đa sàn (Inter-Source Entity Resolution), docs/spec/05 mục 3.2.

Ba giai đoạn đúng đặc tả:
  A. Blocking Key Partitioning (`blocking.blocking_key`) - chỉ so các bài cùng block.
  B. TF-IDF Cosine Similarity trên D = Clean_Title + Clean_Requirements + Clean_Description,
     char n-gram 3..5 (mục 3.2.B.2 cho phép char 3-5 HOẶC word 1-2; chọn char vì tiếng Việt
     không tách từ). Ngưỡng quyết định: cosine >= 0.85 (mục 3.2.B.5).
  C. Golden Record Master Fusion (bảng mục 3.2.C): hợp nhất thành một bản ghi vàng,
     không xóa dữ liệu - bản thua vẫn được ghi trong `merged_from` của bản thắng.

Không dùng model/embedding nào (P0 mục 6): toàn bộ là TF-IDF của scikit-learn, tất định.
"""

from __future__ import annotations

import math
import re
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from preprocessing.deduplication.blocking import blocking_key
from preprocessing.deduplication.text_norm import clean_text, fold

COSINE_THRESHOLD = 0.85  # SPEC-05 mục 3.2.B.5
MIN_JD_CHARS = 40        # JD quá ngắn không đủ ngữ cảnh để so văn bản
BLOCK_SUFFIX = (3, 5)    # char n-gram 3..5
SALARY_NUMBER = re.compile(r"\d")
MIN_COMPANY_SLUG = 3     # slug ngắn hơn mức này (kể cả rỗng) không đủ căn cứ nói hai tin cùng công ty
AMBIGUOUS_SLUG = 4       # slug dưới mức này dễ trùng tên viết tắt của nhiều công ty khác nhau

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


def block_slug(key: str) -> str:
    """Lấy lại phần Slug(Company) từ blocking key `slug_city_group`."""
    return key.rsplit("_", 2)[0]


def same_company(a: Item, b: Item) -> bool:
    """Tên công ty (đã bỏ dấu) trùng nhau hoặc bao hàm nhau.

    Dùng cho block có slug ngắn: `fpt` là slug của cả FPT Software lẫn FPT Telecom, nên nếu
    chỉ trông chờ cosine thì hai vị trí của hai công ty con khác nhau dễ bị gộp nhầm.
    """
    na = fold(clean_text(a["flat"].get("company_name")))
    nb = fold(clean_text(b["flat"].get("company_name")))
    if not na or not nb:
        return False
    ta, tb = set(na.split()), set(nb.split())
    return ta <= tb or tb <= ta


def candidate_blocks(blocks: dict[str, list[Item]]) -> dict[str, list[Item]]:
    """Chỉ giữ block có từ 2 sàn trở lên và slug công ty không rỗng/không quá ngắn.

    Block slug ngắn vẫn được đưa vào so, nhưng từng cặp phải qua `same_company` (xem dưới).
    """
    return {key: g for key, g in blocks.items()
            if len(g) > 1 and len({x["src"] for x in g}) > 1 and len(block_slug(key)) >= MIN_COMPANY_SLUG}


# ---------------------------------------------------------------- B. cosine
def exact_cross_pairs(items: Sequence[Item]) -> list[tuple[Item, Item, float]]:
    """Cặp khác nguồn trùng hash nhận dạng 100% - bằng chứng chắc nhất, tính trước khi so cosine (D4)."""
    by_hash: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        if it["xhash"]:
            by_hash[it["xhash"]].append(it)
    hits: list[tuple[Item, Item, float]] = []
    for g in by_hash.values():
        if len({x["src"] for x in g}) < 2:
            continue
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                if g[i]["src"] != g[j]["src"]:
                    hits.append((g[i], g[j], 1.0))
    return hits


def cross_source_pairs(items: Sequence[Item], threshold: float = COSINE_THRESHOLD) -> list[tuple[Item, Item, float]]:
    """Mọi cặp khác nguồn trong cùng block có cosine >= threshold; trả kèm điểm để đưa vào audit."""
    hits: list[tuple[Item, Item, float]] = []
    for key, group in candidate_blocks(build_blocks(items)).items():
        texts = [g["jd"] for g in group]
        if all(len(t) < MIN_JD_CHARS for t in texts):
            continue
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=BLOCK_SUFFIX, min_df=1)
        try:
            mat = vec.fit_transform(texts)
        except ValueError:  # block chỉ có chuỗi rỗng
            continue
        sim = cosine_similarity(mat)
        strict = len(block_slug(key)) < AMBIGUOUS_SLUG  # slug ngắn: đòi bằng chứng cùng công ty
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                if group[i]["src"] == group[j]["src"]:
                    continue
                if strict and not same_company(group[i], group[j]):
                    continue
                if sim[i, j] >= threshold:
                    hits.append((group[i], group[j], float(sim[i, j])))
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


def max_cosine(cluster: Sequence[Item], scores: dict[tuple[int, int], float]) -> float:
    """Điểm cosine cao nhất trong cụm, dùng cho báo cáo khi duyệt mẫu."""
    best = math.nan
    for a, b in zip(cluster, cluster[1:], strict=False):
        key = (min(id(a), id(b)), max(id(a), id(b)))
        if key in scores and (math.isnan(best) or scores[key] > best):
            best = scores[key]
    return best


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


def _dates(group: Sequence[Item]) -> tuple[str, str]:
    posted = sorted({str(g["flat"].get("raw_posted_date")) for g in group if g["flat"].get("raw_posted_date")})
    seen = sorted({str(g["seen_at"]) for g in group if g["seen_at"]})
    return (posted[0] if posted else "", seen[-1] if seen else "")


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
        "first_posted_at": first_posted,
        "last_seen_at": last_seen,
        "duplicate_count": len(ordered),
        "is_cross_platform": len({g["src"] for g in ordered}) > 1,
    }
