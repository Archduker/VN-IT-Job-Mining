# -*- coding: utf-8 -*-
"""preprocessing.missing_outlier.outlier_handler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module kiểm định ngoại lai định lượng bằng phương pháp IQR và Winsorization.

Quy tắc:
  - Áp dụng cho 2 biến liên tục: mức lương (VND/tháng) và số năm kinh nghiệm.
  - Tự động nhận diện và sửa các lỗi bóc tách regex / lỗi nhập liệu số phổ biến:
    + Bẫy số điện thoại sau tên người ("Khánh Lương SĐT...")
    + Mức lương bị che giấu trên website (TopDev "1*** USD")
    + Mẫu câu phúc lợi gây nhiễu ("13th month", "18 days off", "24/24")
    + Nhầm lẫn dấu chấm phần nghìn với dấu thập phân ("500.000 VND" -> 500k)
  - Áp dụng Winsorization (capping tại phân vị 1% và 99%) thay vì xóa bỏ hàng,
    nhằm bảo toàn nguyên vẹn hồ sơ kỹ năng quý giá (Zero Record Loss Policy).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


def clean_and_repair_salary_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Làm sạch và khử bẫy lương ảo (False-Positive Scrubber) hậu Transformer.

    Trả về bản ghi đã được làm sạch, giữ nguyên tính bất biến của các trường gốc raw_*.
    """
    rec = dict(record)
    s_max = rec.get("salary_max_vnd")
    s_min = rec.get("salary_min_vnd")
    s_source = rec.get("salary_source")
    raw_s = str(rec.get("raw_salary_text") or "")
    ext_s = str(rec.get("salary_text_raw") or "")

    if s_max is None:
        return rec

    # 1. Bẫy số bị che giấu (Masked Salary e.g. "1*** USD", "***")
    if "***" in ext_s or "***" in raw_s:
        rec["salary_min_vnd"] = None
        rec["salary_max_vnd"] = None
        rec["salary_source"] = "masked_negotiable"
        rec["is_negotiable"] = 1
        rec["is_salary_negotiable_declared"] = 1
        return rec

    # 2. Sửa lỗi dấu chấm phân tách phần nghìn (e.g. "500.000 VND" bị ép thành 500.0 VND)
    if 100.0 <= s_max < 1000.0 and (re.search(r"\b\d{3}\.\d{3}\b", ext_s) or re.search(r"\b\d{3}\.\d{3}\b", raw_s)):
        rec["salary_max_vnd"] = s_max * 1000.0
        if s_min is not None and 100.0 <= s_min < 1000.0:
            rec["salary_min_vnd"] = s_min * 1000.0
        return rec

    # 3. Khử bẫy Regex bắt nhầm trong JD / Benefits
    if s_source in ("jd_regex", "benefits_regex"):
        # 3.1. Bẫy số điện thoại sau tên người liên hệ có chữ "Lương" hoặc prefix SĐT
        if re.search(r"(?:sđt|sdt|hotline|máy lẻ|liên hệ|tel|\b0\d{2,3}[.\s]?\d{3,4})", ext_s, re.I):
            rec["salary_min_vnd"] = None
            rec["salary_max_vnd"] = None
            rec["salary_source"] = "scrubbed_false_positive_phone"
            rec["is_negotiable"] = 1
            return rec

        # 3.2. Bẫy số ngày phép / nghỉ lễ ("18 days off", "19 days of leaves")
        if re.search(r"\b\d+\s*(?:days?\s+off|days?\s+of\s+leaves?|ngày\s+phép)\b", ext_s, re.I):
            rec["salary_min_vnd"] = None
            rec["salary_max_vnd"] = None
            rec["salary_source"] = "scrubbed_false_positive_leave"
            rec["is_negotiable"] = 1
            return rec

        # 3.3. Bẫy lương tháng 13 / thưởng tết ("13th month salary", "thưởng tháng lương 13")
        if re.search(r"(?:13th\s+month|tháng\s+(?:lương\s+)?13)", ext_s, re.I):
            rec["salary_min_vnd"] = None
            rec["salary_max_vnd"] = None
            rec["salary_source"] = "scrubbed_false_positive_13th"
            rec["is_negotiable"] = 1
            return rec

        # 3.4. Bẫy ca kíp / bảo hiểm 24/7 ("247 working option", "24/24")
        if re.search(r"\b247\b|\b24/7\b|\b24/24\b", ext_s, re.I):
            rec["salary_min_vnd"] = None
            rec["salary_max_vnd"] = None
            rec["salary_source"] = "scrubbed_false_positive_hours"
            rec["is_negotiable"] = 1
            return rec

    # 4. Sửa 3 lỗi nhập liệu số học phổ biến nếu có
    fixed_max = fix_common_salary_input_errors(rec["salary_max_vnd"], ext_s)
    if fixed_max != rec["salary_max_vnd"]:
        rec["salary_max_vnd"] = fixed_max
        if rec.get("salary_min_vnd"):
            rec["salary_min_vnd"] = fix_common_salary_input_errors(rec["salary_min_vnd"], ext_s)

    # 5. Tự động sửa lỗi đảo ngược biên lương (Inverted Salary Range min > max)
    cur_min = rec.get("salary_min_vnd")
    cur_max = rec.get("salary_max_vnd")
    if cur_min is not None and cur_max is not None and cur_min > cur_max:
        rec["salary_min_vnd"] = cur_max
        rec["salary_max_vnd"] = cur_min
        rec["salary_fix_note"] = "swapped_inverted_bounds"

    return rec


def detect_iqr_outliers(series: pd.Series, multiplier: float = 1.5) -> Dict[str, Any]:
    """Phát hiện ngoại lai số học bằng phương pháp Khoảng Phân Vị (IQR Method)."""
    valid = series.dropna()
    if len(valid) == 0:
        return {
            "total_records": 0,
            "q1": None,
            "q3": None,
            "iqr": None,
            "lower_bound": None,
            "upper_bound": None,
            "outlier_count": 0,
            "outlier_rate_pct": 0.0,
        }

    q1 = float(valid.quantile(0.25))
    q3 = float(valid.quantile(0.75))
    iqr = q3 - q1

    lower_bound = max(0.0, q1 - multiplier * iqr)
    upper_bound = q3 + multiplier * iqr

    outliers = valid[(valid < lower_bound) | (valid > upper_bound)]
    outlier_count = len(outliers)
    outlier_rate = round((outlier_count / len(valid)) * 100, 2)

    return {
        "total_records": len(valid),
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "outlier_count": outlier_count,
        "outlier_rate_pct": outlier_rate,
        "skewness": round(float(valid.skew()), 2) if len(valid) > 2 else 0.0,
        "kurtosis": round(float(valid.kurtosis()), 2) if len(valid) > 3 else 0.0,
    }


# Tỷ giá quy đổi chuẩn USD -> VND theo khế ước dự án.
USD_TO_VND_RATE = 25_400.0

# Từ khóa cấp bậc quản lý cấp cao — được miễn trừ rule Over-zeroing.
DIRECTOR_TOKENS = ("director", "giám đốc", "chief", "executive",
                   "tổng giám đốc", "phó tổng", "vp", "head of")

# Chuỗi đặc trưng "lương THEO NĂM" tường minh cho rule R3. Cố Ý KHÔNG dùng từ
# trần "năm"/"year": mọi JD đều chứa "X năm kinh nghiệm" -> sẽ chia 12 oan
# lương tháng thật của ghế cấp cao (vi phạm nguyên tắc TRUE-outlier bệnh án EDA).
ANNUAL_SALARY_TOKENS = ("annual", "yearly", "per year", "each year",
                        "/năm", "/ năm", "lương năm", "thu nhập năm",
                        "theo năm", "tính năm", "quy đổi năm")


def fix_salary_input_errors_detailed(
    salary_vnd: Optional[float],
    jd_text: str = "",
    seniority_text: str = "",
) -> Tuple[Optional[float], Optional[str]]:
    """Nhận diện và sửa 3 lỗi nhập liệu số phổ biến, trả kèm nhãn vết sửa.

    Quy tắc (TASKS.md 6.3.5 / outlier_spec.md mục 3):
      R1. Gõ USD vào ô VNĐ : 100 < salary < 50,000 -> nhân 25,400 ("usd_to_vnd").
      R3. Nhầm lương năm   : salary > 200 triệu và JD chứa dấu hiệu lương THEO
                            NĂM tường minh ("annual", "/năm", "lương năm"...)
                            -> chia 12 ("annual_to_monthly").
      R2. Thừa số 0        : salary > 300 triệu, vị trí non-Director, không có từ
                            khóa năm -> chia bậc 10 về dải hợp lý ("over_zeroing").

    Thứ tự ưu tiên R1 -> R3 -> R2 (lương năm bản chất cũng > 300 triệu nên R3
    phải chạy trước, nếu không sẽ bị quy oan thành lỗi gõ thừa số 0).
    An toàn NaN/kiểu lạ: đầu vào khuyết hoặc không parse được -> (None, None).
    """
    if salary_vnd is None:
        return None, None
    try:
        val = float(salary_vnd)
    except (TypeError, ValueError):
        return None, None
    if np.isnan(val):
        return None, None

    # R1: Gõ nhầm USD vào ô VNĐ (lương tháng VND không thể rẻ đến mức này)
    if 100.0 < val < 50_000.0:
        return val * USD_TO_VND_RATE, "usd_to_vnd"

    jd_lower = (jd_text or "").lower()
    sen_lower = (seniority_text or "").lower()

    # R3: Nhầm lương năm vào ô lương tháng (chỉ khi JD nêu ngữ cảnh lương năm
    # tường minh — xem ANNUAL_SALARY_TOKENS để tránh chia oan "X năm kinh nghiệm")
    if val > 200_000_000.0 and any(k in jd_lower for k in ANNUAL_SALARY_TOKENS):
        return val / 12.0, "annual_to_monthly"

    # R2: Gõ thừa số 0 cho vị trí non-Director
    is_director = any(tok in sen_lower for tok in DIRECTOR_TOKENS)
    if val > 300_000_000.0 and not is_director:
        fixed = val
        for _ in range(3):  # Giới hạn 3 bậc 10, tránh vòng lặp mở
            if fixed > 300_000_000.0:
                fixed /= 10.0
            else:
                break
        return fixed, "over_zeroing"

    return val, None


def fix_common_salary_input_errors(
    salary_vnd: Optional[float],
    jd_text: str = "",
    seniority_text: str = "",
) -> Optional[float]:
    """Tương thích ngược: chỉ trả giá trị sau sửa (wrapper của hàm chi tiết)."""
    fixed, _ = fix_salary_input_errors_detailed(salary_vnd, jd_text, seniority_text)
    return fixed


def winsorize_series(
    series: pd.Series, lower_pct: float = 0.01, upper_pct: float = 0.99
) -> pd.Series:
    """Áp dụng Winsorization: Kéo các giá trị ngoài ngưỡng về phân vị 1% và 99%.

    Bảo toàn toàn bộ bản ghi mà không drop hàng.
    """
    valid = series.dropna()
    if len(valid) == 0:
        return series

    p_low = valid.quantile(lower_pct)
    p_high = valid.quantile(upper_pct)

    return series.clip(lower=p_low, upper=p_high)


def winsorize_with_capping(
    series: pd.Series,
    lower_pct: float = 0.01,
    upper_pct: float = 0.99,
) -> Tuple[pd.Series, pd.Series]:
    """Winsorization bảo toàn phân phối + sinh cờ đánh dấu hàng bị can thiệp.

    Trả về tuple (series_đã_cap, mask_boolean_bị_cap) phục vụ kiểm toán minh bạch.
    """
    values = pd.to_numeric(series, errors="coerce")
    valid = values.dropna()
    if len(valid) == 0:
        return values, pd.Series(False, index=values.index)

    p_low = float(valid.quantile(lower_pct))
    p_high = float(valid.quantile(upper_pct))
    capped = ((values < p_low) | (values > p_high)).fillna(False)
    return values.clip(lower=p_low, upper=p_high), capped


def winsorize_by_source(
    df: pd.DataFrame,
    col: str,
    source_col: str = "source",
    lower_pct: float = 0.01,
    upper_pct: float = 0.99,
) -> Tuple[pd.Series, pd.Series]:
    """Winsorization tính phân vị THEO TỪNG SÀN (per-source).

    Cơ sở bệnh án (outlier_spec.md mục 2): ITviec là sàn top lương cao nhất thị
    trường — dùng bound chung toàn bảng sẽ cap nhầm lương thật của Tech Lead.
    Trả về (series_đã_cap, mask_bị_cap).
    """
    values = pd.to_numeric(df[col], errors="coerce")
    if source_col not in df.columns:
        return winsorize_with_capping(values, lower_pct, upper_pct)

    clipped = values.copy()
    capped = pd.Series(False, index=df.index)
    groups = df[source_col].fillna("unknown")
    for _, idx in values.groupby(groups).groups.items():
        cl, cp = winsorize_with_capping(values.loc[idx], lower_pct, upper_pct)
        clipped.loc[cl.index] = cl
        capped.loc[cp.index] = cp
    return clipped, capped


def _pick_first_col(df: pd.DataFrame, candidates: Tuple[str, ...]) -> Optional[str]:
    """Chọn cột đầu tiên tồn tại trong danh sách ứng viên (linh hoạt theo staging thật)."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def apply_outlier_pipeline(
    df: pd.DataFrame,
    salary_cols: Tuple[str, ...] = ("salary_min_vnd", "salary_max_vnd"),
    experience_col: str = "min_experience_years",
    jd_cols: Tuple[str, ...] = ("raw_description_text", "raw_requirements_text"),
    seniority_col: Optional[str] = None,
    source_col: Optional[str] = None,
    lower_pct: float = 0.01,
    upper_pct: float = 0.99,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Toàn trình Bước 5 trên một DataFrame staging phẳng (không drop dòng).

    Thứ tự: (1) sửa 3 lỗi nhập liệu số R1-R3 -> (2) chẩn đoán IQR phục vụ audit
    -> (3) Winsorize P1-P99 per-source.
    Sinh cột vết: `<col>_fix` (nhãn lỗi đã sửa), `is_outlier_capped`.
    Tên cột nguồn tự nhận diện theo quy ước staging thật của nhóm
    (`source_platform`/`job_seniority`, tương thích cả `source`/`standardized_seniority`).
    Trả về (df_kết_quả, stats_for_audit_report).
    """
    out = df.copy()

    if source_col is None:
        source_col = _pick_first_col(out, ("source", "source_platform")) or "source"
    if seniority_col is None:
        seniority_col = _pick_first_col(
            out, ("standardized_seniority", "job_seniority", "raw_seniority_text")
        )

    stats: Dict[str, Any] = {
        "rows_in": len(out),
        "rows_out": len(out),
        "salary_fix_counts": {},
        "capped_count": 0,
        "iqr_diagnostics": {},
    }

    # Ghép văn bản JD từ các cột hiện diện (dùng cho rule R3 phát hiện "năm/annual")
    jd_cols_present = [c for c in jd_cols if c in out.columns]
    if jd_cols_present:
        jd_series = (
            out[jd_cols_present].astype("string").fillna("").agg(" ".join, axis=1).tolist()
        )
    else:
        jd_series = [""] * len(out)
    sen_series = (out[seniority_col].astype("string").fillna("").tolist()
                  if seniority_col else [""] * len(out))

    # 1) Sửa lỗi nhập liệu số theo từng cột lương
    for col in salary_cols:
        if col not in out.columns:
            continue
        fixed_vals, labels = [], []
        for raw_v, jd_t, sen_t in zip(out[col], jd_series, sen_series):
            fv, label = fix_salary_input_errors_detailed(raw_v, str(jd_t), str(sen_t))
            fixed_vals.append(fv)
            labels.append(label)
        out[col] = fixed_vals
        out[f"{col}_fix"] = labels
        counts: Dict[str, int] = {}
        for lb in labels:
            if lb:
                counts[lb] = counts.get(lb, 0) + 1
        stats["salary_fix_counts"][col] = counts

    # Tự động hoán vị dải lương ngược (min > max) nếu có
    if "salary_min_vnd" in out.columns and "salary_max_vnd" in out.columns:
        inv_mask = (
            out["salary_min_vnd"].notna()
            & out["salary_max_vnd"].notna()
            & (out["salary_min_vnd"] > out["salary_max_vnd"])
        )
        if inv_mask.any():
            temp_min = out.loc[inv_mask, "salary_min_vnd"].copy()
            out.loc[inv_mask, "salary_min_vnd"] = out.loc[inv_mask, "salary_max_vnd"]
            out.loc[inv_mask, "salary_max_vnd"] = temp_min
            stats["inverted_salary_bounds_swapped"] = int(inv_mask.sum())

    # 2) Chẩn đoán IQR sau sửa (số liệu cho báo cáo kiểm định ngoại lai)
    numeric_cols = [c for c in list(salary_cols) + [experience_col] if c in out.columns]
    for col in numeric_cols:
        stats["iqr_diagnostics"][col] = detect_iqr_outliers(
            pd.to_numeric(out[col], errors="coerce")
        )

    # 3) Winsorization per-source, tuyệt đối không drop dòng
    any_cap = pd.Series(False, index=out.index)
    for col in numeric_cols:
        clipped, capped = winsorize_by_source(
            out, col, source_col=source_col, lower_pct=lower_pct, upper_pct=upper_pct
        )
        out[col] = clipped
        any_cap |= capped
    out["is_outlier_capped"] = any_cap
    stats["capped_count"] = int(any_cap.sum())
    stats["rows_out"] = len(out)
    return out, stats
