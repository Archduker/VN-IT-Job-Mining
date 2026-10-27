# -*- coding: utf-8 -*-
"""preprocessing.missing_outlier.market_anchor_calculator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tính toán bảng mỏ neo thống kê mức lương thị trường (Market Anchors) từ các bài đăng
đã có mức lương số học thực tế (Observed Ground Truth).

Ma trận mỏ neo được phân tầng theo:
  (source_platform, standardized_seniority) -> {median_min, median_max, mean_min, mean_max, count}
với cơ chế fallback phân cấp:
  1. Tổ hợp Cụ thể: (platform, seniority)
  2. Fallback Cấp bậc toàn thị trường: (*, seniority)
  3. Fallback Toàn sàn: (platform, *)
  4. Fallback Toàn thị trường chung: (*, *)
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("MarketAnchorCalculator")

# Dải lương mặc định toàn thị trường IT Việt Nam (Fallback cuối cùng nếu dữ liệu rỗng)
GLOBAL_DEFAULT_ANCHOR = {
    "median_min": 15000000.0,
    "median_max": 25000000.0,
    "mean_min": 16500000.0,
    "mean_max": 27000000.0,
    "sample_count": 0,
}

# Khung tham chiếu cấp bậc tối thiểu để đảm bảo tính hợp lý kinh tế
SENIORITY_FLOOR_MAP: Dict[str, Tuple[float, float]] = {
    "Intern": (3000000.0, 7000000.0),
    "Fresher": (8000000.0, 15000000.0),
    "Junior": (12000000.0, 22000000.0),
    "Middle": (20000000.0, 35000000.0),
    "Senior": (35000000.0, 60000000.0),
    "Lead": (50000000.0, 85000000.0),
    "Director": (70000000.0, 130000000.0),
}


class MarketAnchorCalculator:
    """Bộ tính toán và tra cứu mỏ neo tiền lương thị trường."""

    def __init__(self, min_samples_per_cell: int = 5):
        self.min_samples_per_cell = min_samples_per_cell
        self.cell_anchors: Dict[Tuple[str, str], Dict[str, float]] = {}
        self.seniority_anchors: Dict[str, Dict[str, float]] = {}
        self.platform_anchors: Dict[str, Dict[str, float]] = {}
        self.global_anchor: Dict[str, float] = dict(GLOBAL_DEFAULT_ANCHOR)
        self.total_samples_analyzed: int = 0

    def fit(self, records: List[Dict[str, Any]]) -> MarketAnchorCalculator:
        """Alias cho fit_from_records."""
        return self.fit_from_records(records)

    def fit_from_records(self, records: List[Dict[str, Any]]) -> MarketAnchorCalculator:
        """Huấn luyện bảng neo từ danh sách các bản ghi (hỗ trợ cả nested grouped và flat)."""
        cell_mins = defaultdict(list)
        cell_maxs = defaultdict(list)

        sen_mins = defaultdict(list)
        sen_maxs = defaultdict(list)

        plat_mins = defaultdict(list)
        plat_maxs = defaultdict(list)

        all_mins: List[float] = []
        all_maxs: List[float] = []

        for rec in records:
            if not isinstance(rec, dict):
                continue

            # 1. Trích xuất mức lương số VND
            s_min, s_max = self._extract_salary(rec)
            if s_min is None or s_max is None or s_min <= 0 or s_max <= 0:
                continue

            # 2. Trích xuất platform và seniority
            platform = self._extract_platform(rec)
            seniority = self._extract_seniority(rec)

            cell_mins[(platform, seniority)].append(s_min)
            cell_maxs[(platform, seniority)].append(s_max)

            sen_mins[seniority].append(s_min)
            sen_maxs[seniority].append(s_max)

            plat_mins[platform].append(s_min)
            plat_maxs[platform].append(s_max)

            all_mins.append(s_min)
            all_maxs.append(s_max)

        self.total_samples_analyzed = len(all_mins)
        logger.info("MarketAnchorCalculator: Đã phân tích %d bài đăng có lương thực tế.", self.total_samples_analyzed)

        # 3. Tính toán cho từng cell (platform, seniority)
        for (plat, sen), mins in cell_mins.items():
            maxs = cell_maxs[(plat, sen)]
            self.cell_anchors[(plat, sen)] = {
                "median_min": round(float(median(mins)), 1),
                "median_max": round(float(median(maxs)), 1),
                "mean_min": round(float(mean(mins)), 1),
                "mean_max": round(float(mean(maxs)), 1),
                "sample_count": len(mins),
            }

        # 4. Tính toán cho seniority level
        for sen, mins in sen_mins.items():
            maxs = sen_maxs[sen]
            self.seniority_anchors[sen] = {
                "median_min": round(float(median(mins)), 1),
                "median_max": round(float(median(maxs)), 1),
                "mean_min": round(float(mean(mins)), 1),
                "mean_max": round(float(mean(maxs)), 1),
                "sample_count": len(mins),
            }

        # 5. Tính toán cho platform level
        for plat, mins in plat_mins.items():
            maxs = plat_maxs[plat]
            self.platform_anchors[plat] = {
                "median_min": round(float(median(mins)), 1),
                "median_max": round(float(median(maxs)), 1),
                "mean_min": round(float(mean(mins)), 1),
                "mean_max": round(float(mean(maxs)), 1),
                "sample_count": len(mins),
            }

        # 6. Tính toán toàn thị trường
        if all_mins:
            self.global_anchor = {
                "median_min": round(float(median(all_mins)), 1),
                "median_max": round(float(median(all_maxs)), 1),
                "mean_min": round(float(mean(all_mins)), 1),
                "mean_max": round(float(mean(all_maxs)), 1),
                "sample_count": len(all_mins),
            }

        return self

    def fit_from_file(self, file_path: Path | str) -> MarketAnchorCalculator:
        """Nạp dữ liệu từ file JSON và huấn luyện bảng neo."""
        path = Path(file_path)
        if not path.is_file():
            logger.warning("Tệp %s không tồn tại, sử dụng neo mặc định.", path)
            return self

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return self.fit_from_records(data)
        logger.warning("Dữ liệu trong %s không phải list, bỏ qua fit.", path)
        return self

    def get_anchor(self, platform: Optional[str], seniority: Optional[str]) -> Dict[str, float]:
        """Tra cứu mỏ neo với cơ chế fallback phân cấp."""
        plat_clean = (platform or "").strip().lower()
        sen_clean = (seniority or "").strip().lower()

        # Cấp 1: Khớp chính xác cả sàn và cấp bậc (nếu đủ mẫu)
        if (plat_clean, sen_clean) in self.cell_anchors:
            anchor = self.cell_anchors[(plat_clean, sen_clean)]
            if anchor.get("sample_count", 0) >= self.min_samples_per_cell:
                return dict(anchor)

        # Cấp 2: Fallback về cấp bậc toàn thị trường
        if sen_clean in self.seniority_anchors:
            return dict(self.seniority_anchors[sen_clean])

        # Cấp 3: Fallback về sàn
        if plat_clean in self.platform_anchors:
            return dict(self.platform_anchors[plat_clean])

        # Cấp 4: Tham chiếu khung lương sàn theo seniority nếu có
        for sen_key, (f_min, f_max) in SENIORITY_FLOOR_MAP.items():
            if sen_clean == sen_key.lower():
                return {
                    "median_min": f_min,
                    "median_max": f_max,
                    "mean_min": f_min * 1.05,
                    "mean_max": f_max * 1.05,
                    "sample_count": 0,
                }

        # Cấp 5: Toàn thị trường chung
        return dict(self.global_anchor)

    def format_anchor_context(self, platform: Optional[str], seniority: Optional[str]) -> str:
        """Định dạng chuỗi giải thích ngắn gọn để nhúng vào Prompt của LLM."""
        anchor = self.get_anchor(platform, seniority)
        plat_name = platform or "thị trường IT"
        sen_name = seniority or "tiêu chuẩn"
        return (
            f"Thống kê lương thực tế tại sàn [{plat_name}] cho cấp bậc [{sen_name}]: "
            f"Median: {anchor['median_min']:,.0f} - {anchor['median_max']:,.0f} VND "
            f"(Mean: {anchor['mean_min']:,.0f} - {anchor['mean_max']:,.0f} VND)."
        )

    def _extract_salary(self, rec: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        # Tìm trong nhóm salary (nested)
        sal = rec.get("salary")
        if isinstance(sal, dict):
            s_min = sal.get("salary_min_vnd") or sal.get("salary_min")
            s_max = sal.get("salary_max_vnd") or sal.get("salary_max")
            if s_min is not None and s_max is not None:
                try:
                    return float(s_min), float(s_max)
                except (ValueError, TypeError):
                    pass

        # Tìm ở root (flat)
        s_min = rec.get("salary_min_vnd") or rec.get("salary_min")
        s_max = rec.get("salary_max_vnd") or rec.get("salary_max")
        if s_min is not None and s_max is not None:
            try:
                return float(s_min), float(s_max)
            except (ValueError, TypeError):
                pass

        return None, None

    def _extract_platform(self, rec: Dict[str, Any]) -> str:
        plat = rec.get("source_platform") or ""
        return str(plat).strip().lower()

    def _extract_seniority(self, rec: Dict[str, Any]) -> str:
        # Nhóm requirements hoặc job_info
        req = rec.get("requirements")
        if isinstance(req, dict) and req.get("standardized_seniority"):
            return str(req["standardized_seniority"]).strip().lower()

        jinfo = rec.get("job_info")
        if isinstance(jinfo, dict) and jinfo.get("standardized_seniority"):
            return str(jinfo["standardized_seniority"]).strip().lower()

        sen = rec.get("standardized_seniority")
        return str(sen).strip().lower() if sen else "middle"
