# -*- coding: utf-8 -*-
"""Giảm thưa ma trận kỹ năng (PH8 mục 10b, yêu cầu mới): gộp alias, ngưỡng DF tối thiểu, gom kỹ năng hiếm.

Mọi ngưỡng là tham số cấu hình [ĐỀ XUẤT]; mặc định không làm gì (min_df=None). Đầu vào: rows dict
{job_id_global, slug, level, weight, n_mentions, ...}, một dòng mỗi (JD, kỹ năng).
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

OTHER = "other_skill"
LEVEL_RANK = {"preferred": 0, "required": 1}
THRESHOLDS = (3, 5, 10, 20, 50)


def family_slug(group: str) -> str:
    return f"family_{group}"


def remap(rows: Iterable[dict], mapping: Mapping[str, str]) -> List[dict]:
    """Đổi slug theo mapping rồi gộp trùng (JD, slug): level cao nhất, weight lớn nhất, cộng n_mentions."""
    acc: Dict[tuple, dict] = {}
    for r in rows:
        slug = mapping.get(r["slug"], r["slug"])
        key = (r["job_id_global"], slug)
        cur = acc.get(key)
        if cur is None:
            acc[key] = {**r, "slug": slug}
        else:
            cur["n_mentions"] += r["n_mentions"]
            cur["weight"] = max(cur["weight"], r["weight"])
            if LEVEL_RANK[r["level"]] > LEVEL_RANK[cur["level"]]:
                cur["level"] = r["level"]
    return [acc[k] for k in sorted(acc)]


def document_frequency(rows: Iterable[dict]) -> Counter:
    return Counter(slug for _, slug in {(r["job_id_global"], r["slug"]) for r in rows})


def rare_mapping(rows: Sequence[dict], groups: Mapping[str, str], min_df: int, mode: str = "family",
                 protected: Iterable[str] = ()) -> Dict[str, str]:
    if mode not in ("family", "other"):
        raise ValueError("mode phải là family hoặc other")
    protected = set(protected)
    return {s: (family_slug(groups[s]) if mode == "family" else OTHER)
            for s, c in document_frequency(rows).items() if c < min_df and s not in protected}


def sparsity_stats(rows: Sequence[dict], n_jobs: int, n_universe: Optional[int] = None) -> dict:
    df = document_frequency(rows)
    per_job = Counter(r["job_id_global"] for r in rows)
    counts = list(per_job.values()) + [0] * (n_jobs - len(per_job))
    used = len(df)
    nnz = len(rows)
    return {
        "n_jobs": n_jobs, "nnz": nnz, "n_cols_used": used,
        "density_used_cols": round(nnz / (n_jobs * used), 6) if n_jobs and used else None,
        "density_universe": round(nnz / (n_jobs * n_universe), 6) if n_jobs and n_universe else None,
        "mean_skills_per_job": round(nnz / n_jobs, 3) if n_jobs else None,
        "median_skills_per_job": statistics.median(counts) if counts else None,
        "jobs_with_zero_skills": n_jobs - len(per_job),
        "cols_below_df": {str(t): sum(1 for c in df.values() if c < t) for t in THRESHOLDS},
    }


def reduce_sparsity(rows: Sequence[dict], n_jobs: int, groups: Mapping[str, str], n_universe: Optional[int] = None,
                    merge_map: Optional[Mapping[str, str]] = None, min_df: Optional[int] = None,
                    mode: str = "family", protected: Iterable[str] = ()):
    """Trả (rows_sau, báo cáo before/after). merge_map = gộp alias đã duyệt; min_df=None = không gom hiếm."""
    cur = remap(rows, merge_map) if merge_map else list(rows)
    mapping = rare_mapping(cur, groups, min_df, mode, protected) if min_df else {}
    after = remap(cur, mapping) if mapping else cur
    folded = defaultdict(list)
    for s, t in mapping.items():
        folded[t].append(s)
    rep = {"config": {"merge_map_size": len(merge_map or {}), "min_df": min_df, "mode": mode},
           "before": sparsity_stats(rows, n_jobs, n_universe),
           "after": sparsity_stats(after, n_jobs, None),
           "n_skills_folded": len(mapping),
           "folded_into": {k: sorted(v) for k, v in sorted(folded.items())}}
    return after, rep
