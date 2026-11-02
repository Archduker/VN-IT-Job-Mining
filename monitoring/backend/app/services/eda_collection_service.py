# -*- coding: utf-8 -*-
"""Service tính toán Collection EDA (Giai đoạn 1: Thu Thập Thô).

Phân tích Field Inventory, Missing Rate và phân phối 2D trên dữ liệu cào thô As-Is.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd

from app.core.config import settings

logger = logging.getLogger("eda_collection_service")


class EDACollectionService:
    """Xử lý phân tích chất lượng dữ liệu cào thô (Giai đoạn 1)."""

    def __init__(self):
        self.data_dir = settings.DATA_DIR

    def _load_raw_samples(self, source: str, max_records: int = 200) -> List[Dict[str, Any]]:
        """Đọc mẫu các file JSON cào thô từ thư mục raw."""
        raw_dir = self.data_dir / source / "raw"
        records = []
        if not raw_dir.exists():
            return records

        for root, _, files in os.walk(raw_dir):
            for f in sorted(files):
                if f.endswith(".json") and not f.startswith("."):
                    fp = Path(root) / f
                    try:
                        with open(fp, "r", encoding="utf-8") as fl:
                            content = json.load(fl)
                        # File batch chứa danh sách envelope, file lẻ chứa một envelope
                        for item in content if isinstance(content, list) else [content]:
                            if not isinstance(item, dict):
                                continue
                            payload = item.get("raw_payload") or item.get("raw") or item
                            records.append(payload)
                            if len(records) >= max_records:
                                return records
                    except Exception:
                        continue
        return records

    def get_field_inventory(self, source: str) -> List[Dict[str, Any]]:
        """Sinh bảng kiểm kê trường và tỷ lệ khuyết thiếu (Field Inventory)."""
        samples = self._load_raw_samples(source, max_records=200)
        if not samples:
            return []

        df = pd.DataFrame(samples)
        total_rows = len(df)
        inventory = []

        for col in df.columns:
            try:
                empty_str_mask = (df[col] == "")
                null_count = int(df[col].isnull().sum() + (empty_str_mask.sum() if hasattr(empty_str_mask, "sum") else 0))
            except Exception:
                null_count = int(df[col].isnull().sum())
            
            null_rate = round((null_count / total_rows) * 100, 2)
            first_valid = df[col].dropna().iloc[0] if not df[col].dropna().empty else None

            try:
                unique_count = int(df[col].nunique())
            except (TypeError, Exception):
                try:
                    unique_count = int(df[col].astype(str).nunique())
                except Exception:
                    unique_count = 1

            inventory.append({
                "field_name": col,
                "data_type": str(df[col].dtype),
                "null_count": null_count,
                "null_rate_pct": null_rate,
                "unique_count": unique_count,
                "sample_value": str(first_valid)[:60] if first_valid is not None else "None",
            })

        return sorted(inventory, key=lambda x: x["null_rate_pct"])

    def get_summary(self, source: str) -> Dict[str, Any]:
        """Tóm tắt chất lượng của nguồn; số chưa đo được thì để None kèm lý do."""
        from app.services.pipeline_report_service import pipeline_report_service

        inventory = self.get_field_inventory(source)
        completeness = None
        if inventory:
            avg_null_rate = sum(item["null_rate_pct"] for item in inventory) / len(inventory)
            completeness = max(0.0, round(100.0 - avg_null_rate, 2))
        summary = pipeline_report_service.get_eda_summary(source, len(self._load_raw_samples(source)), completeness)
        summary["fields_count"] = len(inventory)
        return summary

    def get_charts_2d(self, source: str) -> Dict[str, Any]:
        """Biểu đồ tính từ parquet staging thật; chưa có file thì trả available=False."""
        from app.services.pipeline_report_service import pipeline_report_service

        return pipeline_report_service.get_eda_charts(source)

eda_collection_service = EDACollectionService()
