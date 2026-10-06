# -*- coding: utf-8 -*-
"""Data quality check & validation helper.

Thực hiện kiểm tra tính toàn vẹn của dữ liệu cào sau mỗi batch:
- Đếm tổng số bản ghi (record count)
- Tỷ lệ hợp lệ schema Pydantic (validation rate)
- Độ duy nhất của dedup_key (uniqueness)
- Tỷ lệ các trường quan trọng không bị null (title, company, description)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from crawlers.common.logger import get_logger
from crawlers.common.schema import JobRecord, validate_record

logger = get_logger("data_quality")


class DataQualityChecker:
    """Kiểm tra chất lượng dữ liệu của file JSONL vừa thu thập."""

    def __init__(self, jsonl_path: str | Path) -> None:
        self.jsonl_path = Path(jsonl_path)

    def check(self) -> Dict[str, Any]:
        """Thực thi toàn bộ rules kiểm tra chất lượng dữ liệu."""
        if not self.jsonl_path.exists():
            return {
                "file": str(self.jsonl_path),
                "passed": False,
                "error": "File does not exist",
                "total_records": 0,
            }

        total_records = 0
        valid_schema_count = 0
        dedup_keys: set[str] = set()
        missing_titles = 0
        missing_companies = 0
        missing_descriptions = 0

        with open(self.jsonl_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                total_records += 1

                try:
                    data = json.loads(line)
                    # Validate schema
                    record = validate_record(data)
                    valid_schema_count += 1

                    # Check dedup key
                    dedup_keys.add(record.meta.dedup_key)

                    # Check required fields
                    if not record.raw.title:
                        missing_titles += 1
                    if not record.raw.company:
                        missing_companies += 1
                    if not record.raw.description_html:
                        missing_descriptions += 1

                except Exception as exc:
                    logger.warning(
                        "Quality check error at %s line %d: %s",
                        self.jsonl_path.name,
                        line_no,
                        exc,
                    )

        schema_valid_rate = (
            (valid_schema_count / total_records) if total_records > 0 else 0.0
        )
        unique_rate = (
            (len(dedup_keys) / total_records) if total_records > 0 else 0.0
        )

        passed = (
            total_records > 0
            and schema_valid_rate >= 0.95
            and unique_rate >= 0.99
            and missing_titles == 0
        )

        report = {
            "file": str(self.jsonl_path),
            "passed": passed,
            "total_records": total_records,
            "valid_schema_records": valid_schema_count,
            "schema_valid_rate": round(schema_valid_rate * 100, 2),
            "unique_keys": len(dedup_keys),
            "unique_rate": round(unique_rate * 100, 2),
            "missing_titles": missing_titles,
            "missing_companies": missing_companies,
            "missing_descriptions": missing_descriptions,
        }

        if passed:
            logger.info("✅ Data Quality Passed for %s: %s", self.jsonl_path.name, report)
        else:
            logger.warning("⚠️ Data Quality Issues for %s: %s", self.jsonl_path.name, report)

        return report
