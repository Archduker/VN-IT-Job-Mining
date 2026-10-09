# -*- coding: utf-8 -*-
"""Data quality check & validation helper.

Thực hiện kiểm tra tính toàn vẹn của dữ liệu cào sau mỗi batch:
- Đếm tổng số bản ghi (record count)
- Tỷ lệ hợp lệ schema Pydantic (validation rate)
- Độ duy nhất của dedup_key (uniqueness)
- Tỷ lệ các trường quan trọng không bị null (title, company, description)
- Hỗ trợ cả file JSON chuẩn dạng mảng [ ... ] lẫn file JSONL dòng (stream).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from crawlers.common.logger import get_logger
from crawlers.common.schema import JobRecord, validate_record

logger = get_logger("data_quality")


class DataQualityChecker:
    """Kiểm tra chất lượng dữ liệu của file JSON / JSONL vừa thu thập."""

    def __init__(
        self,
        file_path: Optional[Union[str, Path]] = None,
        jsonl_path: Optional[Union[str, Path]] = None,
    ) -> None:
        target = file_path if file_path is not None else jsonl_path
        if target is None:
            raise ValueError("Phải cung cấp file_path hoặc jsonl_path")
        self.file_path = Path(target)
        self.jsonl_path = self.file_path  # tương thích ngược

    def check(self) -> Dict[str, Any]:
        """Thực thi toàn bộ rules kiểm tra chất lượng dữ liệu."""
        if not self.file_path.exists():
            return {
                "file": str(self.file_path),
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

        # Đọc dữ liệu: Hỗ trợ JSON array [ ... ] hoặc fallback JSONL
        records_to_check: List[tuple[int, Any]] = []

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except Exception as exc:
            logger.error("Không thể mở file %s: %s", self.file_path, exc)
            return {
                "file": str(self.file_path),
                "passed": False,
                "error": str(exc),
                "total_records": 0,
            }

        if not content:
            # File rỗng
            pass
        elif self.file_path.suffix == ".json" or content.startswith("["):
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    for idx, item in enumerate(data, 1):
                        records_to_check.append((idx, item))
                else:
                    records_to_check.append((1, data))
            except json.JSONDecodeError as exc:
                logger.warning(
                    "Không thể parse JSON array %s (%s), fallback sang đọc từng dòng",
                    self.file_path.name,
                    exc,
                )
                for line_no, line in enumerate(content.splitlines(), 1):
                    line = line.strip()
                    if line:
                        try:
                            records_to_check.append((line_no, json.loads(line)))
                        except Exception as parse_err:
                            logger.warning(
                                "Quality check error at %s line %d: %s",
                                self.file_path.name,
                                line_no,
                                parse_err,
                            )
                            total_records += 1
        else:
            # File .jsonl
            for line_no, line in enumerate(content.splitlines(), 1):
                line = line.strip()
                if line:
                    try:
                        records_to_check.append((line_no, json.loads(line)))
                    except Exception as parse_err:
                        logger.warning(
                            "Quality check error at %s line %d: %s",
                            self.file_path.name,
                            line_no,
                            parse_err,
                        )
                        total_records += 1

        for idx, item in records_to_check:
            total_records += 1
            try:
                record = validate_record(item)
                valid_schema_count += 1
                dedup_keys.add(record.meta.dedup_key)

                if not record.raw.title:
                    missing_titles += 1
                if not record.raw.company:
                    missing_companies += 1
                has_desc = bool(getattr(record.raw, "description_list", None) or getattr(record.raw, "description_html", None) or getattr(record.raw, "description_text", None))
                if not has_desc:
                    missing_descriptions += 1
            except Exception as exc:
                logger.warning(
                    "Quality check error at %s record %d: %s",
                    self.file_path.name,
                    idx,
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
            "file": str(self.file_path),
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
            logger.info("✅ Data Quality Passed for %s: %s", self.file_path.name, report)
        else:
            logger.warning("⚠️ Data Quality Issues for %s: %s", self.file_path.name, report)

        return report
