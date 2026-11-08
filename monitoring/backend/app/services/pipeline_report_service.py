# -*- coding: utf-8 -*-
"""Số liệu thật cho các trang Pre-processing, Processing, Master Dashboard và EDA.

Chỉ đọc file do pipeline ghi ra:
- reports/<source>/<source>_quality_health_card.json      (scripts/run_staging_integration_pipeline.py)
- reports/curated_golden_dataset_health_card.json          (cùng script, sau khử trùng lặp)
- reports/integration/<source|master>_integration_report.json (preprocessing/integration/run_integration.py)
- data/staging/<source>/<source>_flat_clean.parquet

Thiếu file thì trả None kèm lý do, không ước lượng hay điền số mặc định.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from app.core.config import settings
from app.core.data_paths import load_json_report

PIPELINE_CMD = "python scripts/run_staging_integration_pipeline.py"
INTEGRATION_CMD = "python preprocessing/integration/run_integration.py"

# Pipeline chưa ghi các số này ra file nào, nên trang chỉ nêu là chưa có.
NOT_RECORDED = [
    "Phân phối điểm tương đồng giữa các cặp tin: cross_deduplicator chỉ ghi số cụm trùng, không ghi điểm từng cặp.",
    "Cặp sàn trùng nhau nhiều nhất: health card không tách số trùng theo cặp nguồn.",
]


def _reports_dir():
    return settings.ROOT_DIR / "reports"


def health_card(source: str) -> Optional[Dict[str, Any]]:
    return load_json_report(_reports_dir() / source / f"{source}_quality_health_card.json")


def curated_card() -> Optional[Dict[str, Any]]:
    return load_json_report(_reports_dir() / "curated_golden_dataset_health_card.json")


def integration_report(name: str) -> Optional[Dict[str, Any]]:
    return load_json_report(_reports_dir() / "integration" / f"{name}_integration_report.json")


def staging_frame(source: str) -> Optional[pd.DataFrame]:
    path = settings.DATA_DIR / "staging" / source / f"{source}_flat_clean.parquet"
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def _ranked(counts: Optional[Dict[str, Any]], limit: Optional[int] = None) -> List[Dict[str, Any]]:
    items = sorted(((str(k), int(v)) for k, v in (counts or {}).items()), key=lambda kv: kv[1], reverse=True)
    return [{"label": k, "count": v} for k, v in items[:limit]]


def _million(value: Any) -> Optional[float]:
    return None if value is None else round(float(value) / 1_000_000, 2)


def _completeness(audit: Dict[str, Any], field: str) -> Optional[float]:
    item = audit.get(field)
    return item.get("completeness_pct") if isinstance(item, dict) else None


class PipelineReportService:
    def get_preprocessing(self) -> Dict[str, Any]:
        rows = []
        for src in settings.SUPPORTED_SOURCES:
            card = health_card(src)
            if not card:
                rows.append({"source": src, "available": False})
                continue
            salary = card.get("salary_metrics") or {}
            imputation = card.get("imputation_metrics") or {}
            rows.append({
                "source": src,
                "available": True,
                "audit_timestamp": card.get("audit_timestamp"),
                "raw_envelopes": card.get("total_raw_envelopes"),
                "stub_removed": card.get("stub_jds_removed_policy_1b"),
                "clean_records": card.get("total_clean_records"),
                "salary_coverage_pct": salary.get("salary_coverage_pct"),
                "salary_jd_hits": salary.get("salary_jd_regex_implicit_hits"),
                "imputed_records": imputation.get("records_imputed_by_genai"),
                "imputation_rate_pct": imputation.get("imputation_rate_pct"),
                "language_distribution": card.get("language_distribution") or {},
            })
        present = [r for r in rows if r["available"]]

        def total(key: str) -> Optional[int]:
            return sum(r.get(key) or 0 for r in present) if present else None

        return {
            "available": bool(present),
            "unavailable_reason": None if present else f"Chưa có health card trong reports/. Chạy {PIPELINE_CMD}.",
            "generated_at": max((r["audit_timestamp"] or "" for r in present), default=None) or None,
            "sources": rows,
            "totals": {
                "raw_envelopes": total("raw_envelopes"),
                "stub_removed": total("stub_removed"),
                "clean_records": total("clean_records"),
                "imputed_records": total("imputed_records"),
            },
        }

    def get_processing(self) -> Dict[str, Any]:
        card = curated_card()
        master = integration_report("master")
        dedup = (card or {}).get("deduplication_metrics") or None
        audit = (master or {}).get("field_completeness_audit") or {}
        fields = sorted(
            (
                {"field": name, "filled": v.get("filled_count"), "missing": v.get("missing_count"),
                 "completeness_pct": v.get("completeness_pct")}
                for name, v in audit.items() if isinstance(v, dict)
            ),
            key=lambda f: -(f["completeness_pct"] or 0),
        )
        reasons = []
        if not card:
            reasons.append(f"Chưa có reports/curated_golden_dataset_health_card.json. Chạy {PIPELINE_CMD}.")
        if not master:
            reasons.append(f"Chưa có reports/integration/master_integration_report.json. Chạy {INTEGRATION_CMD}.")
        return {
            "available": bool(card or master),
            "unavailable_reason": " ".join(reasons) or None,
            "generated_at": (card or {}).get("generated_at") or (master or {}).get("timestamp"),
            "integrated_records": (master or {}).get("total_integrated_records"),
            "dedup": None if not dedup else {
                "input_records": dedup.get("total_input_records"),
                "golden_records": dedup.get("total_golden_records"),
                "duplicates_removed": dedup.get("duplicates_removed"),
                "deduplication_rate_pct": dedup.get("deduplication_rate_pct"),
                "cross_platform_clusters": dedup.get("cross_platform_cluster_count"),
            },
            "field_completeness": fields,
            "not_recorded": NOT_RECORDED,
        }

    def get_dashboard(self) -> Dict[str, Any]:
        card = curated_card()
        master = integration_report("master")
        if not card:
            return {
                "available": False,
                "unavailable_reason": f"Chưa có bộ golden. Chạy {PIPELINE_CMD} để tạo reports/curated_golden_dataset_health_card.json.",
                "generated_at": None, "totals": None, "platform_breakdown": [], "salary_vnd_million": None,
                "job_family": [], "seniority": [], "top_cities": [], "lineage": [],
            }
        golden = card.get("total_golden_records") or 0
        salary = card.get("salary_metrics") or {}
        dedup = card.get("deduplication_metrics") or {}
        integrated = (master or {}).get("total_integrated_records")
        lineage = [
            {"step": "Sau Integration", "records": integrated},
            {"step": "Sau loại JD rỗng", "records": card.get("total_staging_records")},
            {"step": "Golden sau khử trùng lặp", "records": golden},
        ]
        return {
            "available": True,
            "unavailable_reason": None,
            "generated_at": card.get("generated_at"),
            "totals": {
                "integrated_records": integrated,
                "staging_records": card.get("total_staging_records"),
                "golden_records": golden,
                "deduplication_rate_pct": dedup.get("deduplication_rate_pct"),
                "salary_coverage_pct": salary.get("salary_coverage_pct"),
            },
            "platform_breakdown": [
                {"source": item["label"], "golden_records": item["count"],
                 "share_pct": round(100 * item["count"] / golden, 2) if golden else None}
                for item in _ranked(card.get("platform_breakdown"))
            ],
            "salary_vnd_million": None if not salary else {
                "p1": _million(salary.get("salary_p1_vnd")), "q1": _million(salary.get("salary_q1_vnd")),
                "median": _million(salary.get("salary_median_vnd")), "q3": _million(salary.get("salary_q3_vnd")),
                "p99": _million(salary.get("salary_p99_vnd")),
            },
            "job_family": _ranked(card.get("job_family_breakdown")),
            "seniority": _ranked(card.get("seniority_breakdown")),
            "top_cities": _ranked(card.get("top_cities"), 10),
            "lineage": [row for row in lineage if row["records"] is not None],
        }

    def get_eda_summary(self, source: str, completeness: Optional[float]) -> Dict[str, Any]:
        card = health_card(source) or {}
        report = integration_report(source) or {}
        frame = staging_frame(source)
        negotiable = None
        if frame is not None and "is_salary_negotiable_declared" in frame and len(frame):
            negotiable = round(100 * float(frame["is_salary_negotiable_declared"].fillna(0).mean()), 2)
        return {
            "source": source,
            "total_records": report.get("total_integrated_records"),
            "completeness_score_pct": completeness,
            "salary_parse_rate_pct": (card.get("salary_metrics") or {}).get("salary_coverage_pct"),
            "negotiable_salary_pct": negotiable,
            "reason": None if card and report else (
                f"Chưa có báo cáo Integration hoặc health card của {source}. Chạy {PIPELINE_CMD}."
            ),
        }

    def get_eda_charts(self, source: str) -> Dict[str, Any]:
        frame = staging_frame(source)
        if frame is None or frame.empty:
            return {
                "available": False,
                "unavailable_reason": f"Chưa có data/staging/{source}/{source}_flat_clean.parquet. Tải về từ R2 hoặc chạy {PIPELINE_CMD}.",
                "salary_histogram": [], "skills_pareto": [], "locations": [], "records": 0,
            }
        salary_cols = frame[[c for c in ("salary_min_vnd", "salary_max_vnd") if c in frame]]
        salary_mid = salary_cols.where(salary_cols > 0).mean(axis=1).dropna() / 1e6  # 0 VND là lương ẩn
        edges = [0, 10, 20, 30, 40, 50, 60, 80, 100, 150, float("inf")]
        hist = pd.cut(salary_mid, bins=edges, right=False).value_counts(sort=False)
        histogram = [
            {"bin": f"{int(iv.left)}–{int(iv.right)}M" if iv.right != float("inf") else f"≥{int(iv.left)}M", "count": int(n)}
            for iv, n in hist.items()
        ]
        skills = pd.Series(
            [str(s) for row in frame.get("skills_list", pd.Series(dtype=object)).dropna() for s in list(row) if str(s).strip()],
            dtype=object,
        )
        top = skills.value_counts().head(10)
        total_skills = int(top.sum()) or 1
        running = 0
        pareto = []
        for label, count in top.items():
            running += int(count)
            pareto.append({"label": label, "count": int(count), "cumulative_pct": round(100 * running / total_skills, 1)})
        cities = frame["primary_city"].value_counts().head(8) if "primary_city" in frame else pd.Series(dtype=int)
        return {
            "available": True,
            "unavailable_reason": None,
            "records": int(len(frame)),
            "salary_records": int(len(salary_mid)),
            "salary_histogram": histogram,
            "skills_pareto": pareto,
            "locations": [{"label": str(k), "count": int(v)} for k, v in cities.items()],
        }

    def get_eda_compare(self) -> Dict[str, Any]:
        rows = []
        for src in settings.SUPPORTED_SOURCES:
            report = integration_report(src)
            card = health_card(src) or {}
            audit = (report or {}).get("field_completeness_audit") or {}
            values = [v.get("completeness_pct") for v in audit.values() if isinstance(v, dict)]
            rows.append({
                "source": src,
                "available": bool(report),
                "records": (report or {}).get("total_integrated_records"),
                "completeness_pct": round(sum(values) / len(values), 2) if values else None,
                "salary_text_pct": _completeness(audit, "raw_salary_text"),
                "salary_numeric_pct": (card.get("salary_metrics") or {}).get("salary_coverage_pct"),
                "experience_pct": _completeness(audit, "raw_experience_text"),
                "seniority_pct": _completeness(audit, "raw_seniority_text"),
            })
        present = any(r["available"] for r in rows)
        return {
            "available": present,
            "unavailable_reason": None if present else f"Chưa có reports/integration/. Chạy {INTEGRATION_CMD}.",
            "sources": rows,
        }


pipeline_report_service = PipelineReportService()
