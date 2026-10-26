# -*- coding: utf-8 -*-
"""Custom Airflow Operators for VN-IT-Job-Mining.

Bao gồm:
- JobCrawlerOperator: Điều khiển crawler theo từng nguồn.
- DataQualityOperator: Kiểm tra tính toàn vẹn và chất lượng sau mỗi lần cào.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from airflow.exceptions import AirflowSkipException
from airflow.models import BaseOperator
from airflow.utils.context import Context

from collection.common.adaptive_router import AdaptiveWorkloadRouter, MAX_ITEMS_PER_BATCH
from collection.common.data_quality import DataQualityChecker
from collection.common.r2_storage import upload_file_to_r2
from collection.common.utils import (
    clean_text,
    text_to_clean_lines,
    parse_salary_detail,
    classify_job_tags,
)
from run import run_crawler

logger = logging.getLogger("airflow.operators.vn_it_job")

SOURCE_PROFILES = {
    "topdev": {"max_items": 30, "max_pages": 2, "timeout_minutes": 3},
    "vietnamworks": {"max_items": 30, "max_pages": 2, "timeout_minutes": 3},
    "careerviet": {"max_items": 30, "max_pages": 2, "timeout_minutes": 4},
    "vieclam24h": {"max_items": 30, "max_pages": 2, "timeout_minutes": 4},
    "itviec": {"max_items": 30, "max_pages": 2, "timeout_minutes": 5},
    "topcv": {"max_items": 30, "max_pages": 2, "timeout_minutes": 5},
    "jobsgo": {"max_items": 30, "max_pages": 2, "timeout_minutes": 5},
    "glints": {"max_items": 30, "max_pages": 2, "timeout_minutes": 5},
}


class AdaptiveRouteCheckOperator(BaseOperator):
    """Operator kiểm tra hàng đợi backlog và điều phối nhịp cào co giãn đàn hồi."""

    template_fields = ("source",)

    def __init__(self, source: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.source = source.lower().strip()

    def execute(self, context: Context) -> dict[str, Any]:
        router = AdaptiveWorkloadRouter(self.source)
        decision = router.evaluate()

        logger.info(
            "[AdaptiveRouter] Nguồn %s: Quyết định = %s | Phân cấp = %s | Quota = %d | Backlog = %d | Lý do = %s",
            self.source.upper(),
            decision["should_run"],
            decision["tier"],
            decision["quota"],
            decision["backlog"],
            decision["reason"],
        )

        if not decision["should_run"]:
            raise AirflowSkipException(
                f"[AdaptiveRouter Skip] Nguồn {self.source.upper()} ({decision['tier']}): {decision['reason']}"
            )

        router.record_start()
        context["ti"].xcom_push(key="dynamic_max_items", value=decision["quota"])
        return decision


class JobCrawlerOperator(BaseOperator):
    """Operator để chạy crawler của một nguồn cụ thể theo từng Pha (Phase)."""

    template_fields = ("source", "phase", "max_items", "max_pages")

    def __init__(
        self,
        source: str,
        phase: str = "detail",
        max_items: Optional[int] = None,
        max_pages: Optional[int] = None,
        output_dir: Optional[str] = "data",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.source = source.lower().strip()
        self.phase = phase.lower().strip()
        profile = SOURCE_PROFILES.get(self.source, {"max_items": 30, "max_pages": 2})
        self.max_items = max_items if max_items is not None else profile["max_items"]
        self.max_pages = max_pages if max_pages is not None else profile["max_pages"]
        self.output_dir = output_dir

    def execute(self, context: Context) -> dict[str, Any]:
        effective_max_items = self.max_items

        # Nếu là Pha Detail, kiểm tra xem Router có cấp Quota động qua XCom không
        if self.phase == "detail" and context and "ti" in context:
            dynamic_quota = context["ti"].xcom_pull(
                task_ids=f"check_route_{self.source}",
                key="dynamic_max_items",
            )
            if dynamic_quota is not None:
                effective_max_items = dynamic_quota

        logger.info(
            "Executing JobCrawlerOperator for source='%s', phase='%s', max_items=%s (effective=%s), max_pages=%s",
            self.source,
            self.phase,
            self.max_items,
            effective_max_items,
            self.max_pages,
        )

        out_dir = self.output_dir or "data"
        if not Path(out_dir).is_absolute():
            out_dir = str(PROJECT_ROOT / out_dir)

        stats = run_crawler(
            source=self.source,
            max_items=effective_max_items,
            output_dir=out_dir,
            phase=self.phase,
            max_pages=self.max_pages,
        )

        # Ghi nhận hoàn tất ca cào vào AdaptiveRouter để bắt đầu tính giờ nghỉ Cooldown
        if self.phase == "detail":
            try:
                router = AdaptiveWorkloadRouter(self.source)
                items_crawled = stats.get("success", 0) or stats.get("items_crawled", 0) or 0
                router.record_finish(items_crawled=items_crawled, success=True)
            except Exception as re:
                logger.warning("[JobCrawlerOperator] Lỗi ghi nhận router finish cho %s: %s", self.source, re)

        if stats.get("output_file"):
            output_path = Path(stats["output_file"])
            object_key = f"raw/{self.source}/{output_path.parent.name}/{output_path.name}"
            try:
                stats["r2_uri"] = upload_file_to_r2(
                    output_path,
                    object_key=object_key,
                )
                logger.info("Uploaded %s crawl output to Cloudflare R2: %s", self.source, stats["r2_uri"])
            except Exception as up_err:
                logger.warning("Auto-upload to Cloudflare R2 skipped or failed for %s: %s", self.source, up_err)

        if stats.get("output_file"):
            context["ti"].xcom_push(key="output_file", value=stats["output_file"])

        return stats


class DataQualityOperator(BaseOperator):
    """Operator kiểm tra chất lượng dữ liệu của file JSONL sinh ra từ crawler task."""

    template_fields = ("file_path",)

    def __init__(
        self,
        file_path: Optional[str] = None,
        source_task_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.file_path = file_path
        self.source_task_id = source_task_id

    def execute(self, context: Context) -> dict[str, Any]:
        target_file = self.file_path

        if not target_file and self.source_task_id:
            target_file = context["ti"].xcom_pull(
                task_ids=self.source_task_id,
                key="output_file",
            )

        if not target_file:
            logger.warning("No output file specified for quality check, skipping.")
            return {"passed": True, "skipped": True}

        logger.info("Running DataQualityCheck on file: %s", target_file)
        checker = DataQualityChecker(target_file)
        report = checker.check()

        if not report["passed"]:
            logger.error("Data Quality check FAILED: %s", report)
            raise ValueError(f"Data quality check failed for {target_file}: {report}")

        return report


class DataPreprocessOperator(BaseOperator):
    """Operator tiền xử lý và chuẩn hóa dữ liệu từ tầng Raw sang tầng Staging.
    
    Nhiệm vụ:
    - Đọc các raw snapshot JSON trong data/{source}/raw/{date}/
    - Làm sạch văn bản (loại bỏ bullet rác, chuẩn hóa khoảng trắng)
    - Chuẩn hóa mức lương số học (salary_min, salary_max, currency, is_salary_negotiable)
    - Phân loại thẻ kỹ năng và yêu cầu (technical_skills, job_roles, attributes)
    - Xuất file sạch sang data/{source}/staging/{date}/{job_id}_clean.json
    """

    template_fields = ("source", "date_str")

    def __init__(
        self,
        source: str,
        date_str: Optional[str] = None,
        base_dir: str = "data",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.source = source.lower().strip()
        self.date_str = date_str
        b_path = Path(base_dir)
        self.base_dir = b_path if b_path.is_absolute() else (PROJECT_ROOT / b_path)

    def execute(self, context: Context) -> dict[str, Any]:
        import json
        from datetime import datetime, timezone

        d_str = self.date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        raw_dir = self.base_dir / self.source / "raw" / d_str
        staging_dir = self.base_dir / self.source / "staging" / d_str
        staging_dir.mkdir(parents=True, exist_ok=True)

        logger.info("[Preprocess] Bắt đầu tiền xử lý nguồn %s (Ngày: %s)...", self.source.upper(), d_str)

        if not raw_dir.exists() or not raw_dir.is_dir():
            logger.warning("[Preprocess] Thư mục raw không tồn tại: %s. Bỏ qua.", raw_dir)
            return {"source": self.source, "total_raw": 0, "total_cleaned": 0, "staging_dir": str(staging_dir)}

        raw_files = sorted(list(raw_dir.glob("*.json")))
        cleaned_files = []

        for f_path in raw_files:
            try:
                with open(f_path, "r", encoding="utf-8") as rf:
                    envelope = json.load(rf)

                meta = envelope.get("metadata", {})
                raw = envelope.get("raw_payload") or envelope.get("raw") or envelope
                job_id = meta.get("job_id") or raw.get("id") or f_path.stem.split("_")[0]

                # 1. Làm sạch Title & Company
                title_clean = clean_text(raw.get("title") or raw.get("job-title") or "")
                company_raw = raw.get("company") or raw.get("company-name") or ""
                if isinstance(company_raw, dict):
                    company_clean = clean_text(company_raw.get("display_name") or company_raw.get("name") or "")
                else:
                    company_clean = clean_text(str(company_raw))

                # 2. Làm sạch Sections: Mô tả, Yêu cầu, Phúc lợi
                desc_raw = (
                    raw.get("responsibilities_original")
                    or raw.get("content")
                    or raw.get("description_list")
                    or raw.get("description")
                    or ""
                )
                if isinstance(desc_raw, dict):
                    desc_raw = list(desc_raw.values())
                elif not isinstance(desc_raw, list):
                    desc_raw = [desc_raw]
                desc_clean = text_to_clean_lines("\n".join(str(d) for d in desc_raw if d))

                req_raw = (
                    raw.get("requirements_original")
                    or raw.get("requirements_arr")
                    or raw.get("requirements_list")
                    or raw.get("requirements")
                    or ""
                )
                if isinstance(req_raw, dict):
                    req_raw = list(req_raw.values())
                elif not isinstance(req_raw, list):
                    req_raw = [req_raw]
                req_clean = text_to_clean_lines("\n".join(str(r) for r in req_raw if r))

                ben_raw = (
                    raw.get("benefits_original")
                    or raw.get("benefits_v2")
                    or raw.get("benefits_list")
                    or raw.get("benefits")
                    or ""
                )
                ben_items = []
                if isinstance(ben_raw, list):
                    for b in ben_raw:
                        if isinstance(b, dict):
                            ben_items.append(b.get("value") or b.get("content") or b.get("benefit") or "")
                        else:
                            ben_items.append(str(b))
                elif isinstance(ben_raw, dict):
                    ben_items = [str(v) for v in ben_raw.values()]
                else:
                    ben_items = [str(ben_raw)]
                ben_clean = text_to_clean_lines("\n".join(b for b in ben_items if b))

                # 3. Chuẩn hóa dải lương số học
                salary_str = raw.get("salary_raw") or raw.get("salary") or ""
                if isinstance(salary_str, dict):
                    salary_str = salary_str.get("salary_range") or salary_str.get("salary_text") or str(salary_str)
                salary_parsed = parse_salary_detail(str(salary_str), title=title_clean)

                # 4. Phân loại thẻ tags & kỹ năng
                tags_raw = (
                    raw.get("skills_arr")
                    or raw.get("skills_str")
                    or raw.get("tags")
                    or raw.get("skills")
                    or []
                )
                if isinstance(tags_raw, str):
                    tags_raw = [t.strip() for t in tags_raw.split(",") if t.strip()]
                elif isinstance(tags_raw, list):
                    flattened_tags = []
                    for t in tags_raw:
                        if isinstance(t, dict):
                            flattened_tags.append(t.get("name") or t.get("skill_name") or t.get("tag") or "")
                        else:
                            flattened_tags.append(str(t))
                    tags_raw = [t.strip() for t in flattened_tags if t.strip()]

                tags_classified = classify_job_tags(tags_raw)

                # 5. Địa điểm & Hạn nộp
                loc_raw = raw.get("addresses") or raw.get("location_text") or raw.get("location") or ""
                if isinstance(loc_raw, list):
                    loc_items = []
                    for loc in loc_raw:
                        if isinstance(loc, dict):
                            loc_items.append(loc.get("address") or loc.get("location") or "")
                        else:
                            loc_items.append(str(loc))
                    loc_clean = clean_text("; ".join(l for l in loc_items if l))
                elif isinstance(loc_raw, dict):
                    loc_clean = clean_text(loc_raw.get("address") or loc_raw.get("location") or "")
                else:
                    loc_clean = clean_text(str(loc_raw))

                dl_raw = raw.get("recalled_at") or raw.get("deadline_text") or raw.get("deadline_raw") or raw.get("deadline") or ""
                dl_clean = clean_text(str(dl_raw))

                # 6. Đóng gói Staging Clean Record
                cleaned_record = {
                    "staging_metadata": {
                        "source": self.source,
                        "job_id": str(job_id),
                        "cleaned_at": datetime.now(timezone.utc).isoformat(),
                        "raw_file": str(f_path.name),
                        "content_hash": meta.get("content_hash"),
                        "version": meta.get("version", 1),
                    },
                    "cleaned_job": {
                        "title": title_clean,
                        "company": company_clean,
                        "salary": salary_parsed,
                        "skills": tags_classified.get("technical_skills") or [],
                        "job_roles": tags_classified.get("job_roles") or [],
                        "attributes": tags_classified.get("attributes") or {},
                        "description_clean": desc_clean,
                        "requirements_clean": req_clean,
                        "benefits_clean": ben_clean,
                        "location": loc_clean,
                        "deadline": dl_clean,
                    },
                }

                clean_file = staging_dir / f"{job_id}_clean.json"
                with open(clean_file, "w", encoding="utf-8") as wf:
                    json.dump(cleaned_record, wf, ensure_ascii=False, indent=2)

                cleaned_files.append(str(clean_file))

            except Exception as exc:
                logger.warning("[Preprocess] Bỏ qua lỗi khi làm sạch file %s: %s", f_path.name, exc)
                continue

        logger.info(
            "[Preprocess] Hoàn thành %s: Đã tiền xử lý %d/%d file raw sang staging: %s",
            self.source.upper(),
            len(cleaned_files),
            len(raw_files),
            staging_dir,
        )

        if context and "ti" in context:
            context["ti"].xcom_push(key="staging_dir", value=str(staging_dir))
            context["ti"].xcom_push(key="cleaned_count", value=len(cleaned_files))

        return {
            "source": self.source,
            "total_raw": len(raw_files),
            "total_cleaned": len(cleaned_files),
            "staging_dir": str(staging_dir),
        }

