# -*- coding: utf-8 -*-
"""tests.test_outliers_quality
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ kiểm thử đơn vị cho Bước 5 — Outlier & Quality Rules (Phan Nhật Tài).

Chứng minh 2 điều kiện DoD (TASKS.md 6.3.5):
  1. Tự động sửa đúng 3 lỗi nhập liệu số (R1 USD->VND, R2 thừa số 0, R3 lương năm).
  2. Winsorization capping chặn đúng ngưỡng P1-P99 và không gây crash khi gặp NaN.

Quy ước: chạy offline hoàn toàn, không mạng, không file ngoài thư mục test.
"""

import numpy as np
import pandas as pd
import pytest

from preprocessing.missing_outlier.outlier_handler import (
    USD_TO_VND_RATE,
    apply_outlier_pipeline,
    detect_iqr_outliers,
    fix_common_salary_input_errors,
    fix_salary_input_errors_detailed,
    winsorize_by_source,
    winsorize_series,
    winsorize_with_capping,
)
from preprocessing.missing_outlier.quality_rules import (
    add_quality_flags,
    compute_quality_score,
    summarize_quality,
)


# ---------------------------------------------------------------------------
# DoD 1 — Ba lỗi nhập liệu số (R1, R2, R3)
# ---------------------------------------------------------------------------

class TestSalaryInputErrorFixes:
    """Test 3 luật tự sửa lỗi nhập liệu số theo outlier_spec.md mục 3."""

    def test_r1_usd_typed_into_vnd_field(self):
        # Lương 1,500 (gõ nhầm USD vào ô VND) -> nhân 25,400
        fixed, label = fix_salary_input_errors_detailed(1_500.0)
        assert label == "usd_to_vnd"
        assert fixed == pytest.approx(1_500.0 * USD_TO_VND_RATE)

    def test_r1_upper_boundary_50k(self):
        # 30,000 nằm trong dải (100, 50,000) -> vẫn sửa theo R1
        fixed, label = fix_salary_input_errors_detailed(30_000.0)
        assert label == "usd_to_vnd"
        # 60,000 ngoài dải -> giữ nguyên, không gắn nhãn
        untouched, no_label = fix_salary_input_errors_detailed(60_000.0)
        assert untouched == 60_000.0 and no_label is None

    def test_r2_over_zeroing_non_director(self):
        # 400 triệu cho vị trí Nhân viên (80.5% mẫu careerviet) -> chia bậc 10
        fixed, label = fix_salary_input_errors_detailed(
            400_000_000.0, jd_text="Lương hấp dẫn", seniority_text="Nhân viên"
        )
        assert label == "over_zeroing"
        assert fixed == pytest.approx(40_000_000.0)

    def test_r2_director_exempt(self):
        # 800 triệu của Director -> hàng thật, KHÔNG sửa
        untouched, label = fix_salary_input_errors_detailed(
            800_000_000.0, jd_text="", seniority_text="IT Director"
        )
        assert untouched == 800_000_000.0 and label is None

    def test_r3_annual_salary_mistyped_as_monthly(self):
        # 360 triệu + JD có từ "năm" -> chia 12 (ví dụ bệnh án careerviet)
        fixed, label = fix_salary_input_errors_detailed(
            360_000_000.0, jd_text="Thu nhập 360 triệu/năm, thưởng tháng 13"
        )
        assert label == "annual_to_monthly"
        assert fixed == pytest.approx(30_000_000.0)

    def test_r3_takes_priority_over_r2(self):
        # 450 triệu vừa >300M vừa có "annual" -> phải là R3 (chia 12), không phải R2
        fixed, label = fix_salary_input_errors_detailed(
            450_000_000.0, jd_text="annual package 450 million", seniority_text="Middle"
        )
        assert label == "annual_to_monthly"
        assert fixed == pytest.approx(37_500_000.0)

    def test_valid_salary_untouched(self):
        untouched, label = fix_salary_input_errors_detailed(25_000_000.0)
        assert untouched == 25_000_000.0 and label is None

    def test_nan_and_garbage_safe(self):
        assert fix_salary_input_errors_detailed(None) == (None, None)
        assert fix_salary_input_errors_detailed(np.nan) == (None, None)
        assert fix_salary_input_errors_detailed("không rõ mức lương") == (None, None)
        # Wrapper tương thích ngược
        assert fix_common_salary_input_errors(None) is None
        assert fix_common_salary_input_errors(1_000.0) == pytest.approx(25_400_000.0)


# ---------------------------------------------------------------------------
# DoD 2 — Winsorization P1-P99, không drop dòng, không crash khi NaN
# ---------------------------------------------------------------------------

class TestWinsorization:

    def _series_with_extremes(self) -> pd.Series:
        rng = np.random.default_rng(42)
        normal = rng.uniform(10_000_000, 40_000_000, size=200)
        extremes = np.array([1e10, 2e10, 3e10, 1_000.0, 2_000.0])
        return pd.Series(np.concatenate([normal, extremes]))

    def test_cap_bounds_are_p1_p99(self):
        s = self._series_with_extremes()
        clipped, capped = winsorize_with_capping(s)
        valid = s.dropna()
        p_low, p_high = valid.quantile(0.01), valid.quantile(0.99)
        assert clipped.max() == pytest.approx(p_high)
        assert clipped.min() == pytest.approx(p_low)
        # 5 hàng cực đoan cuối phải nằm trong mặt nạ cap; hàng sát biên P1/P99
        # có thể bị cap thêm theo đúng ngữ nghĩa phân vị nội suy (>= 5)
        assert capped.loc[[200, 201, 202, 203, 204]].all()
        assert int(capped.sum()) >= 5
        # Không drop dòng
        assert len(clipped) == len(s)

    def test_all_nan_no_crash(self):
        s = pd.Series([np.nan] * 50)
        clipped, capped = winsorize_with_capping(s)
        assert len(clipped) == 50 and clipped.isna().all() and not capped.any()

    def test_winsorize_series_backward_compatible(self):
        s = self._series_with_extremes()
        out = winsorize_series(s)
        assert isinstance(out, pd.Series) and len(out) == len(s)

    def test_per_source_bounds(self):
        # itviec lương cao hơn topcv: bound chung sẽ cap nhầm lương thật itviec
        topcv = pd.Series(np.linspace(5e6, 20e6, 100))
        itviec = pd.Series(np.linspace(60e6, 90e6, 100))
        df = pd.DataFrame({
            "salary_max_vnd": pd.concat([topcv, itviec], ignore_index=True),
            "source": ["topcv"] * 100 + ["itviec"] * 100,
        })
        clipped, capped = winsorize_by_source(df, "salary_max_vnd")
        # Lương itviec không bị kéo về đỉnh topcv
        assert clipped.iloc[100:].min() == pytest.approx(60e6, rel=0.05)
        # Bound P99 per-source cao hơn bound toàn bảng
        global_clipped, _ = winsorize_with_capping(df["salary_max_vnd"])
        assert clipped.iloc[100:].max() > global_clipped.iloc[100:].max()

    def test_iqr_detect_handles_nan(self):
        s = pd.Series([np.nan] * 10)
        diag = detect_iqr_outliers(s)
        assert diag["total_records"] == 0 and diag["upper_bound"] is None


class TestApplyOutlierPipeline:

    def _mock_df(self) -> pd.DataFrame:
        rng = np.random.default_rng(7)
        n = 100
        return pd.DataFrame({
            "source": ["careerviet"] * (n + 2),
            "salary_min_vnd": list(rng.uniform(10e6, 20e6, n)) + [1_500.0, np.nan],
            "salary_max_vnd": list(rng.uniform(20e6, 40e6, n)) + [3_000.0, 25e6],
            "min_experience_years": list(rng.uniform(0, 5, n)) + [1.0, np.nan],
            "raw_description_text": [""] * (n + 2),
            "standardized_seniority": ["Nhân viên"] * (n + 2),
        })

    def test_no_drop_and_flags(self):
        df = self._mock_df()
        out, stats = apply_outlier_pipeline(df)
        assert len(out) == len(df) == stats["rows_out"]        # không drop dòng
        assert "is_outlier_capped" in out.columns
        assert "salary_max_vnd_fix" in out.columns
        # Row 100: min 1,500 & max 3,000 đều dính R1
        assert out.loc[100, "salary_min_vnd_fix"] == "usd_to_vnd"
        assert out.loc[100, "salary_max_vnd_fix"] == "usd_to_vnd"
        # Row 101: NaN lương -> giữ NaN, không gắn nhãn sửa (MNAR của Sơn không bị đụng)
        assert pd.isna(out.loc[101, "salary_min_vnd"])
        assert pd.isna(out.loc[101, "salary_min_vnd_fix"])
        # Stats phục vụ audit
        assert stats["salary_fix_counts"]["salary_min_vnd"]["usd_to_vnd"] == 1
        assert "iqr_diagnostics" in stats

    def test_deterministic_fixed_value(self):
        df = self._mock_df()
        out, _ = apply_outlier_pipeline(df)
        # 1,500 USD nhầm VND -> 38,100,000 (có thể bị cap P99 nếu vượt)
        raw_fixed = 1_500.0 * USD_TO_VND_RATE
        assert out.loc[100, "salary_min_vnd"] == pytest.approx(min(raw_fixed, out["salary_min_vnd"].max()))


# ---------------------------------------------------------------------------
# Quality rules & quality_score
# ---------------------------------------------------------------------------

class TestQualityRules:

    def _df_with_violations(self) -> pd.DataFrame:
        return pd.DataFrame({
            "salary_min_vnd": [30e6, 30e6, -5e6, 10e6, 1_500.0],
            "salary_max_vnd": [10e6, 40e6, 20e6, 20e6, 3_000.0],
            "min_experience_years": [2.0, -1.0, 3.0, 45.0, 1.0],
            "raw_posted_date": ["2026-10-01"] * 5,
            "raw_deadline": ["2026-11-01", "2026-11-01", "2026-11-01",
                             "2026-11-01", "2026-09-01"],
            "salary_min_vnd_fix": [None, None, None, None, "usd_to_vnd"],
            "salary_max_vnd_fix": [None, None, None, None, "usd_to_vnd"],
        })

    def test_flags(self):
        flagged = add_quality_flags(self._df_with_violations())
        assert flagged.loc[0, "violation_salary_range"]      # QR1: min > max
        assert flagged.loc[2, "violation_negative_salary"]   # QR4: lương âm
        assert flagged.loc[1, "violation_experience_range"]  # QR2: exp < 0
        assert flagged.loc[3, "violation_experience_range"]  # QR2: exp > 30
        assert not flagged.loc[0, "violation_date_order"]
        assert flagged.loc[4, "violation_multiple_fixes"]    # QR5: sửa cả 2 cột

    def test_score_bounds_and_ordering(self):
        scored = compute_quality_score(self._df_with_violations())
        q = scored["quality_score"]
        assert q.between(0.0, 1.0).all()
        assert q.iloc[0] < 1.0            # có vi phạm -> trừ điểm
        assert q.loc[q.idxmax()] >= 0.5   # vẫn còn bản ghi chất lượng tốt
        # Bản ghi sạch (không cột fix) điểm = 1.0
        clean = pd.DataFrame({"salary_min_vnd": [10e6], "salary_max_vnd": [20e6],
                              "min_experience_years": [2.0]})
        assert compute_quality_score(clean)["quality_score"].iloc[0] == 1.0

    def test_missing_columns_graceful(self):
        # Chỉ có đúng 1 cột số cũng không được crash
        df = pd.DataFrame({"min_experience_years": [1.0, np.nan]})
        scored = compute_quality_score(df)
        assert scored["quality_score"].iloc[0] == 1.0

    def test_summary_for_audit(self):
        summary = summarize_quality(self._df_with_violations())
        assert summary["total_records"] == 5
        assert 0.0 <= summary["quality_score_mean"] <= 1.0
        assert summary["violation_counts"]["violation_salary_range"] == 1
