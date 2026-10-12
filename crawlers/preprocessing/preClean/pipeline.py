# -*- coding: utf-8 -*-
"""crawlers.preprocessing.preClean.pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pipeline điều phối quy trình Sơ chế sơ bộ (Pre-clean):
- Đọc an toàn các batch files thô từ data/<source>/dt=*/batch_*.json.
- Phân luồng:
  + Mẫu hợp lệ -> Bảo toàn 100% cấu trúc List (description_list, requirements_list, benefits_list),
    làm sạch trực tiếp từng phần tử, bảo toàn tags (3 nhóm), extra, timeline, enrich salary và unified_id
    -> data/processed/preClean/merged_jobs_clean.json.
  + Mẫu dị biệt / nhiều null -> Ghi nhận vào data/queue/recrawl_corrupted_queue.json và cập nhật JobStateCatalog sang FAILED_RETRY_NEXT_RUN.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from crawlers.common.logger import get_logger
from crawlers.common.job_catalog import JobStateCatalog
from crawlers.preprocessing.preClean.schema import CleanedJobRecord
from crawlers.preprocessing.preClean.text_cleaner import (
    clean_single_line_text,
    clean_text,
    generate_unified_id,
)
from crawlers.preprocessing.preClean.salary_parser import parse_salary_to_numbers
from crawlers.preprocessing.preClean.anomaly_detector import detect_anomalous_sample

logger = get_logger("preclean_pipeline")


class PreCleanPipeline:
    """Điều phối toàn bộ quy trình làm sạch sơ bộ và hợp nhất đa nguồn đầy đủ ý."""

    def __init__(
        self,
        data_dir: str | Path = "data",
        output_clean_dir: str | Path = "data/processed/preClean",
        queue_dir: str | Path = "data/queue",
        catalog_db_path: Optional[str | Path] = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.output_clean_dir = Path(output_clean_dir)
        self.queue_dir = Path(queue_dir)
        self.catalog = JobStateCatalog(db_path=catalog_db_path)

        self.output_clean_dir.mkdir(parents=True, exist_ok=True)
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def run(self, source: Optional[str] = None) -> Dict[str, Any]:
        """Thực thi pipeline trên các file batch thô."""
        pattern = f"{source}/**/batch_*.json" if source else "**/batch_*.json"
        batch_files = sorted(self.data_dir.glob(pattern))

        # Loại bỏ các thư mục xử lý nội bộ
        batch_files = [
            f for f in batch_files 
            if "processed" not in str(f) and "state" not in str(f) and "queue" not in str(f)
        ]

        logger.info("Bắt đầu PreCleanPipeline (Full-Fidelity) trên %d batch files...", len(batch_files))

        cleaned_records: List[Dict[str, Any]] = []
        corrupted_queue: List[Dict[str, Any]] = []
        stats_by_source: Dict[str, Dict[str, int]] = {}

        for bf in batch_files:
            try:
                with open(bf, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception as exc:
                logger.warning("Không thể đọc file batch %s: %s", bf, exc)
                continue

            if not isinstance(records, list):
                continue

            for rec in records:
                meta = rec.get("_meta", {})
                raw = rec.get("raw", {})

                src = str(meta.get("source") or "").lower().strip()
                jid = str(meta.get("source_job_id") or meta.get("id") or "").strip()
                url = str(meta.get("url") or "").strip()

                if not src:
                    continue

                if src not in stats_by_source:
                    stats_by_source[src] = {"total": 0, "cleaned": 0, "corrupted": 0}
                stats_by_source[src]["total"] += 1

                # 1. Kiểm tra mẫu dị biệt / nhiều null
                is_anomalous, reason = detect_anomalous_sample(rec)
                if is_anomalous:
                    stats_by_source[src]["corrupted"] += 1
                    corrupted_queue.append({
                        "source": src,
                        "job_id": jid,
                        "job_url": url,
                        "reason": reason,
                        "file_origin": str(bf),
                    })
                    # Đưa vào catalog để lần tới cào bù
                    if jid:
                        self.catalog.mark_job_failed_for_next_run(
                            source=src,
                            job_id=jid,
                            error_msg=f"CORRUPTED_NULL: {reason}",
                        )
                    continue

                # 2. Xử lý mẫu hợp lệ: Làm sạch trực tiếp, bảo toàn cấu trúc List
                unified_id = generate_unified_id(src, jid)
                title = clean_single_line_text(raw.get("title"))
                company = clean_single_line_text(raw.get("company"))

                # Phân tích và bổ sung lương định lượng
                salary_raw_obj = raw.get("salary")
                salary_info = parse_salary_to_numbers(salary_raw_obj)
                if isinstance(salary_raw_obj, dict):
                    salary_info["is_negotiable"] = salary_raw_obj.get("is_negotiable", False)
                    salary_info["has_commission"] = salary_raw_obj.get("has_commission", False)
                else:
                    salary_info["is_negotiable"] = salary_info["salary_type"] == "NEGOTIABLE"
                    salary_info["has_commission"] = False

                # Làm sạch danh sách mô tả, yêu cầu, quyền lợi (Bảo toàn List[str])
                raw_desc = raw.get("description_list") or []
                raw_req = raw.get("requirements_list") or []
                raw_ben = raw.get("benefits_list") or []

                clean_desc_list = [clean_text(x) for x in raw_desc if clean_text(x)]
                clean_req_list = [clean_text(x) for x in raw_req if clean_text(x)]
                clean_ben_list = [clean_text(x) for x in raw_ben if clean_text(x)]

                # Làm sạch và bảo toàn 3 nhóm thẻ tags
                raw_tags = raw.get("tags") or {}
                tags_clean: Dict[str, List[str]] = {
                    "skills": [],
                    "requirements": [],
                    "benefits": [],
                }
                if isinstance(raw_tags, dict):
                    # Kỹ năng
                    skills_raw = raw_tags.get("skills") or raw_tags.get("skills_required") or raw_tags.get("professional_skills") or []
                    tags_clean["skills"] = [clean_single_line_text(s) for s in skills_raw if clean_single_line_text(s)]
                    # Yêu cầu
                    req_tags = raw_tags.get("requirements") or []
                    tags_clean["requirements"] = [clean_single_line_text(s) for s in req_tags if clean_single_line_text(s)]
                    # Quyền lợi
                    ben_tags = raw_tags.get("benefits") or []
                    tags_clean["benefits"] = [clean_single_line_text(s) for s in ben_tags if clean_single_line_text(s)]

                # Địa điểm
                location_text = clean_single_line_text(raw.get("location_text"))
                locations = [location_text] if location_text else []

                # Timeline & Thông tin công việc
                employment_type_text = clean_single_line_text(raw.get("employment_type_text"))
                seniority_text = clean_single_line_text(raw.get("seniority_text"))
                posted_date_text = clean_single_line_text(raw.get("posted_date_text"))
                deadline_text = clean_single_line_text(raw.get("deadline_text"))

                # Bảo toàn nguyên vẹn toàn bộ khối extra
                extra_data = raw.get("extra") if isinstance(raw.get("extra"), dict) else {}

                # Tạo CleanedJobRecord đầy đủ ý
                cleaned_obj = CleanedJobRecord(
                    _meta={
                        "unified_id": unified_id,
                        "source": src,
                        "source_job_id": jid,
                        "url": url,
                        "crawled_at": meta.get("crawled_at") or meta.get("scraped_at"),
                        "language": meta.get("language") or "vi",
                    },
                    title=title,
                    company=company,
                    salary=salary_info,
                    description_list=clean_desc_list,
                    requirements_list=clean_req_list,
                    benefits_list=clean_ben_list,
                    tags=tags_clean,
                    locations=locations,
                    location_text=location_text,
                    employment_type_text=employment_type_text,
                    seniority_text=seniority_text,
                    posted_date_text=posted_date_text,
                    deadline_text=deadline_text,
                    extra=extra_data,
                )

                cleaned_records.append(cleaned_obj.model_dump(by_alias=True))
                stats_by_source[src]["cleaned"] += 1

        # 3. Ghi file đầu ra
        out_clean_file = self.output_clean_dir / "merged_jobs_clean.json"
        with open(out_clean_file, "w", encoding="utf-8") as f:
            json.dump(cleaned_records, f, ensure_ascii=False, indent=2)

        out_queue_file = self.queue_dir / "recrawl_corrupted_queue.json"
        with open(out_queue_file, "w", encoding="utf-8") as f:
            json.dump({
                "total_corrupted": len(corrupted_queue),
                "items": corrupted_queue,
            }, f, ensure_ascii=False, indent=2)

        logger.info(
            "Hoàn tất PreClean: %d jobs sạch -> %s | %d jobs dị biệt -> %s",
            len(cleaned_records),
            out_clean_file,
            len(corrupted_queue),
            out_queue_file,
        )

        return {
            "total_processed": len(cleaned_records) + len(corrupted_queue),
            "cleaned_count": len(cleaned_records),
            "corrupted_count": len(corrupted_queue),
            "clean_file": str(out_clean_file),
            "corrupted_queue_file": str(out_queue_file),
            "stats_by_source": stats_by_source,
        }
