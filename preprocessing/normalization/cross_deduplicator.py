# -*- coding: utf-8 -*-
"""preprocessing.normalization.cross_deduplicator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module khử trùng lặp thực thể ngữ nghĩa xuyên sàn (Cross-Platform Entity Resolution).

Quy trình 3 bước chuẩn mực:
  1. Lọc thô (Blocking): Chuẩn hóa tên công ty và địa phương (company_normalized + primary_city).
  2. So khớp ngữ nghĩa (Semantic Matching): Kết hợp độ tương đồng tiêu đề (Jaccard token set)
     và độ tương đồng văn bản JD (TF-IDF Cosine Similarity) với ngưỡng >= 0.82 - 0.88.
  3. Hợp nhất bản ghi Vàng (Golden Record Selection & Fusion):
     - Ưu tiên giữ bản ghi có lương đầy đủ, mô tả dài nhất và kỹ năng phong phú nhất.
     - Hợp nhất kỹ năng (skills_list) và quyền lợi (benefits_list) từ tất cả bản ghi trùng.
     - Lưu trữ vết truy xuất nguồn gốc (provenance): danh sách duplicate_job_ids, duplicate_platforms.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _safe_str(val: Any) -> str:
    """Chuyển đổi an toàn sang str, xử lý triệt để float('nan') và None."""
    if val is None:
        return ""
    if isinstance(val, float) and np.isnan(val):
        return ""
    return str(val)


def normalize_company_name(name: Optional[str]) -> str:
    """Chuẩn hóa tên công ty để phục vụ Blocking:
    - Chuyển chữ thường, chuẩn hóa Unicode NFKC.
    - Loại bỏ tiền tố/hậu tố pháp nhân phổ biến (Công ty, TNHH, CP, Cổ phần, MTV, JSC, Inc, Ltd, Corp).
    - Loại bỏ dấu câu và khoảng trắng thừa.
    """
    if not name or not isinstance(name, str):
        return ""

    s = unicodedata.normalize("NFKC", name).lower().strip()

    # Bỏ các tiền tố pháp nhân tiếng Việt & tiếng Anh
    legal_patterns = [
        r"\bcông ty\b",
        r"\btnhh\b",
        r"\bcổ phần\b",
        r"\bcp\b",
        r"\bmtv\b",
        r"\btập đoàn\b",
        r"\bchi nhánh\b",
        r"\bcorporation\b",
        r"\bcorp\b",
        r"\bco\.,?\s*ltd\b",
        r"\bltd\b",
        r"\bjsc\b",
        r"\binc\b",
        r"\bgroup\b",
        r"\bviệt nam\b",
        r"\bvietnam\b",
        r"\bvn\b",
    ]
    for pat in legal_patterns:
        s = re.sub(pat, " ", s, flags=re.IGNORECASE)

    # Xóa ký tự đặc biệt, giữ lại chữ và số
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compute_title_token_similarity(t1: str, t2: str) -> float:
    """Tính toán độ tương đồng giữa 2 tiêu đề công việc dựa trên Jaccard Token Overlap."""
    if not t1 or not t2:
        return 0.0

    toks1 = set(re.findall(r"\w+", t1.lower()))
    toks2 = set(re.findall(r"\w+", t2.lower()))

    # Bỏ các stopword tiêu đề tuyển dụng phổ biến
    stopwords = {"tuyển", "dụng", "gấp", "cần", "việc", "làm", "nhân", "viên", "job", "hiring", "urgent"}
    toks1 -= stopwords
    toks2 -= stopwords

    if not toks1 or not toks2:
        return 0.0

    intersection = len(toks1 & toks2)
    union = len(toks1 | toks2)
    return intersection / union if union > 0 else 0.0


def deduplicate_cross_platform_jobs(
    df: pd.DataFrame,
    title_sim_threshold: float = 0.65,
    jd_sim_threshold: float = 0.82,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Thực hiện khử trùng lặp bản ghi xuyên sàn trên bảng phẳng thống nhất.

    Args:
        df: DataFrame bảng phẳng chứa các cột chuẩn.
        title_sim_threshold: Ngưỡng tương đồng tiêu đề (Jaccard).
        jd_sim_threshold: Ngưỡng tương đồng văn bản JD (TF-IDF Cosine Similarity).

    Returns:
        Tuple gồm (curated_golden_df, audit_metrics_dict).
    """
    total_raw_records = len(df)
    if total_raw_records == 0:
        return df.copy(), {
            "total_input_records": 0,
            "total_golden_records": 0,
            "duplicates_removed": 0,
            "deduplication_rate_pct": 0.0,
            "cross_platform_cluster_count": 0,
        }

    records = df.to_dict(orient="records")

    # Chuẩn hóa khóa blocking: company_norm + city_norm
    for rec in records:
        rec["_norm_company"] = normalize_company_name(_safe_str(rec.get("company_name")))
        rec["_norm_city"] = (_safe_str(rec.get("primary_city")) or "toan_quoc").lower().strip()
        rec["_block_key"] = f"{rec['_norm_company']}||{rec['_norm_city']}"

    # Nhóm theo Block Key
    blocks: Dict[str, List[int]] = defaultdict(list)
    for idx, rec in enumerate(records):
        blocks[rec["_block_key"]].append(idx)

    # Đánh dấu các bản ghi đã được gom vào Golden Record
    visited: Set[int] = set()
    golden_records: List[Dict[str, Any]] = []
    cluster_count = 0

    for block_key, indices in blocks.items():
        # Nếu block chỉ có 1 bản ghi hoặc tên công ty quá ngắn (không đáng tin), giữ nguyên
        norm_comp = block_key.split("||")[0]
        if len(indices) == 1 or len(norm_comp) < 3:
            for idx in indices:
                if idx not in visited:
                    visited.add(idx)
                    rec = records[idx].copy()
                    rec["is_golden_merged"] = False
                    rec["duplicate_count"] = 1
                    rec["duplicate_platforms"] = [rec.get("source_platform")]
                    rec["duplicate_job_ids"] = [rec.get("job_id_global")]
                    golden_records.append(rec)
            continue

        # Với block có nhiều bản ghi, so khớp pairwise
        n = len(indices)
        matched_groups: List[List[int]] = []
        assigned = set()

        # Chuẩn bị văn bản JD cho khối này
        block_texts = []
        for i in indices:
            t = f"{_safe_str(records[i].get('job_title'))} {_safe_str(records[i].get('raw_description_text'))[:500]}".strip()
            block_texts.append(t if t else "job")

        tfidf_matrix = None
        sim_matrix = None
        if n > 1:
            try:
                vec = TfidfVectorizer(ngram_range=(1, 2), max_features=1000, min_df=1)
                tfidf_matrix = vec.fit_transform(block_texts)
                sim_matrix = cosine_similarity(tfidf_matrix)
            except Exception:
                tfidf_matrix = None
                sim_matrix = None

        for i in range(n):
            if i in assigned:
                continue
            group = [indices[i]]
            assigned.add(i)

            for j in range(i + 1, n):
                if j in assigned:
                    continue

                # 1. Kiểm tra tiêu đề tương đồng
                title_sim = compute_title_token_similarity(
                    _safe_str(records[indices[i]].get("job_title")),
                    _safe_str(records[indices[j]].get("job_title")),
                )

                # 2. Kiểm tra văn bản JD tương đồng từ ma trận sim_matrix đã tính trước
                jd_sim = float(sim_matrix[i, j]) if sim_matrix is not None else 0.0

                # Điều kiện hợp nhất: Tiêu đề rất giống (>= 0.75) HOẶC (Tiêu đề giống vừa >= 0.60 VÀ JD giống >= 0.70)
                is_duplicate = False
                if title_sim >= 0.85:
                    is_duplicate = True
                elif title_sim >= title_sim_threshold and jd_sim >= 0.60:
                    is_duplicate = True
                elif jd_sim >= jd_sim_threshold and title_sim >= 0.40:
                    is_duplicate = True

                if is_duplicate:
                    group.append(indices[j])
                    assigned.add(j)

            matched_groups.append(group)

        # Hợp nhất từng group trong block
        for group in matched_groups:
            for idx in group:
                visited.add(idx)

            if len(group) == 1:
                rec = records[group[0]].copy()
                rec["is_golden_merged"] = False
                rec["duplicate_count"] = 1
                rec["duplicate_platforms"] = [rec.get("source_platform")]
                rec["duplicate_job_ids"] = [rec.get("job_id_global")]
                golden_records.append(rec)
            else:
                cluster_count += 1
                # Hợp nhất: Chọn bản ghi có lương đầy đủ nhất, JD dài nhất làm gốc
                group_recs = [records[idx] for idx in group]

                def _rank_score(r: Dict[str, Any]) -> int:
                    score = 0
                    sal_max = r.get("salary_max_vnd")
                    sal_min = r.get("salary_min_vnd")
                    if sal_max is not None and not (isinstance(sal_max, float) and np.isnan(sal_max)) and sal_max > 0:
                        score += 50
                    if sal_min is not None and not (isinstance(sal_min, float) and np.isnan(sal_min)) and sal_min > 0:
                        score += 30
                    desc = r.get("raw_description_text")
                    if desc and isinstance(desc, str):
                        score += min(len(desc) // 50, 40)
                    skills = r.get("skills_list")
                    if skills is not None and isinstance(skills, (list, np.ndarray)) and len(skills) > 0:
                        score += min(len(skills) * 5, 30)
                    return score

                group_recs.sort(key=_rank_score, reverse=True)
                golden = group_recs[0].copy()

                all_platforms = list(dict.fromkeys(r.get("source_platform") for r in group_recs if r.get("source_platform")))
                all_job_ids = list(dict.fromkeys(r.get("job_id_global") for r in group_recs if r.get("job_id_global")))

                # Hợp nhất Kỹ năng và Quyền lợi
                merged_skills: List[str] = []
                merged_benefits: List[str] = []
                seen_skills: Set[str] = set()
                seen_benefits: Set[str] = set()

                for r in group_recs:
                    sk_list = r.get("skills_list")
                    if sk_list is not None and isinstance(sk_list, (list, np.ndarray)):
                        for sk in sk_list:
                            sk_clean = str(sk).strip()
                            if sk_clean and sk_clean.lower() not in seen_skills:
                                seen_skills.add(sk_clean.lower())
                                merged_skills.append(sk_clean)

                    bf_list = r.get("benefits_list")
                    if bf_list is not None and isinstance(bf_list, (list, np.ndarray)):
                        for bf in bf_list:
                            bf_clean = str(bf).strip()
                            if bf_clean and bf_clean.lower() not in seen_benefits:
                                seen_benefits.add(bf_clean.lower())
                                merged_benefits.append(bf_clean)

                # Bổ sung lương nếu bản ghi gốc bị thiếu nhưng bản ghi trùng có
                sal_max_val = golden.get("salary_max_vnd")
                is_sal_empty = (
                    sal_max_val is None
                    or (isinstance(sal_max_val, float) and np.isnan(sal_max_val))
                    or sal_max_val <= 0
                )
                if is_sal_empty:
                    for r in group_recs[1:]:
                        r_sal = r.get("salary_max_vnd")
                        if r_sal is not None and not (isinstance(r_sal, float) and np.isnan(r_sal)) and r_sal > 0:
                            golden["salary_min_vnd"] = r.get("salary_min_vnd")
                            golden["salary_max_vnd"] = r.get("salary_max_vnd")
                            golden["salary_source"] = f"{r.get('salary_source')}_fused"
                            golden["salary_currency"] = r.get("salary_currency", "VND")
                            break

                golden["skills_list"] = merged_skills
                golden["benefits_list"] = merged_benefits
                golden["is_golden_merged"] = True
                golden["duplicate_count"] = len(group)
                golden["duplicate_platforms"] = all_platforms
                golden["duplicate_job_ids"] = all_job_ids
                golden_records.append(golden)

    # Đảm bảo dọn dẹp các trường tạm
    for r in golden_records:
        r.pop("_norm_company", None)
        r.pop("_norm_city", None)
        r.pop("_block_key", None)

    curated_df = pd.DataFrame(golden_records)
    total_golden = len(curated_df)
    duplicates_removed = total_raw_records - total_golden
    dedup_rate = (duplicates_removed / total_raw_records * 100.0) if total_raw_records > 0 else 0.0

    metrics = {
        "total_input_records": total_raw_records,
        "total_golden_records": total_golden,
        "duplicates_removed": duplicates_removed,
        "deduplication_rate_pct": round(dedup_rate, 2),
        "cross_platform_cluster_count": cluster_count,
    }

    return curated_df, metrics
