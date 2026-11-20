# Prompt M5: Giá trị kỹ năng và lương ước tính cho SD4

> Đặc tả: [`docs/spec/mining/M5_luong_shap.md`](../../spec/mining/M5_luong_shap.md) (M5.1–M5.13; đã duyệt 20/11). Câu hỏi: `docs/target/04_sd4_gia_tri_ky_nang.md`.
> **Trạng thái:** chạy thật 20/11 (phương án A, `tool_concept`).

## 1. Ngữ cảnh

**Đọc trước:** đặc tả M5; `mining/salary_model.py`; `tests/unit/test_mining_salary_model.py`; target SD4 mục 4, 6.

**Vì sao làm** (dry-run 20/11, code cũ):

- Model đạt R²(log) 0,629, MAE 6,05 triệu, chỉ hơn baseline "cấp + kinh nghiệm" 4,1%.
- Chia ngẫu nhiên (không có `dup_group_id`), nên cùng công ty có thể ở cả train lẫn test: số lạc quan.
- Thiếu `src__`, baseline cấp × nghề, phương án B, MAE theo nhóm, 4.1 theo SHAP, ước tính 4.4, so phân bố.

**Số đã đo:**

- 978 công ty trong tập có lương (lớn nhất 21 tin).
- Senior chiếm 20,7% tin thỏa thuận so với 8,8% tin có lương.

## 2. Việc cần sửa

**Input:**

- `meta`: `salary_target_m`, `is_negotiable`, `salary_outlier`, `seniority_ord`, `exp_min_years`, `province`, `job_family`, `source_platform`, `company_id`;
- `MiningData.skills`, `.concepts`;
- baseline từ M1 (hàm, không chỉ file).

**Output:**

- `skill_salary_shap_values.parquet`, `salary_factor_importance.json`, `salary_estimates.parquet`, `trained_salary_rf_model.joblib`;
- khối `salary` trong metrics (hai cấu hình `tool_only` và `tool_concept`).

**File:**

- `mining/salary_model.py`: `select_training_subset` dùng cờ Silver; `_groups` theo `company_id`; `build_salary_features` thêm `src__`, tùy chọn `concepts`. Hàm mới: `baseline_level_family`, `mae_by_group`, `factor_importance`, `bootstrap_ci`, `estimate_negotiable`, `compare_distributions`, `train_band_classifier`.
- `mining/config.py`: `SalaryParams.baseline_margin` 0,10, `bootstrap_n` 200, `dist_warn_ratio` 2,0, `n_bands` 4, `min_group_eval` 30.
- `run_mining_pipeline.py`.

## 3. Pseudo code

```
S = salary_target_m notna & !is_negotiable & !salary_outlier; bỏ lệch > 3× median cấp; ghi lý do
y = log1p(salary_target_m[S])
for cfg in ("tool_only", "tool_concept"):
    X = [skill__ (bỏ other), seniority_ord, exp_min_years(+missing), loc groups, fam__, src__] (+ concept__ nếu cfg)
    assert_no_leakage(X.columns)
    groups = company_id (null → "job:"+job_id)
    tr, te = GroupShuffleSplit(0.2, seed 42); assert không công ty chung
    base = baseline_level_family(train) → dự đoán test (lùi về cấp, toàn bộ như M1.B)
    params = argmin GroupKFold(5) trên tr; rf.fit(tr); holdout R², MAE, RMSE (triệu)
    pass_A = MAE_rf ≤ (1-0,10) × MAE_base and std_cv ≤ 0,05
    mae_by_group(te) theo family, seniority, source (n < 30 → "ít dữ liệu")
cfg_report = cả hai; cfg_used cho SHAP/ước tính = "tool_only" (không tự chọn; người dùng chọn sau review)
nếu !pass_A[cfg_used]: train_band_classifier (4 khung theo tứ phân vị train; macro-F1, acc vs khung đông nhất)
rf_final.fit(S toàn bộ); shap trên ≤ 3000 dòng
factor_importance = mean|φ| gộp nhóm (cấp, kinh nghiệm, tỉnh, nghề, nguồn, kỹ năng gộp) + top 20 kỹ năng
skill_values = skill_values_from_shap (≥ 30 tin) + bootstrap_ci(200, seed 42)
dist = compare_distributions(negotiable, S) theo seniority, family, source; ratio ≥ 2 → warning
est = estimate_negotiable(rf_final, negotiable & salary_target_m null):
      mean cây → expm1; p10, p90 từ dự đoán từng cây; salary_is_estimated true; warning theo dist
```

## 4. Ràng buộc

- Không ghi đè cột lương nào; ước tính chỉ ở `salary_estimates.parquet`.
- Tin thỏa thuận không dùng để train hay chấm.
- `salary_target_m` và mọi cột chứa "salary" không làm đặc trưng.
- **Không tự chọn cấu hình concept**: báo cả hai, mặc định `tool_only` cho SHAP tới khi người dùng chọn.
- SHAP không phải nhân quả: ghi `note` MINE-6 và F10.6 trong metrics.

## 5. Ví dụ (thành test)

| Đầu vào (dựng tay) | Kết quả mong đợi |
|---|---|
| 3 công ty, mỗi công ty 20 tin | tập train và test không chung `company_id` |
| `company_id` null 1 tin | nhóm riêng, không lỗi |
| Lương = 10 + 5·cấp + 8·[python] (+ nhiễu nhỏ) | `delta_m` của python > 0, gần 8 |
| Ô baseline cấp × nghề n < 30 | lùi về median cấp |
| Model không thắng baseline 10% | chạy phương án B, metrics `plan = "B"` |
| Cột `salary_mid` trong X | `assert_no_leakage` báo lỗi |
| Tin thỏa thuận | có `salary_estimated_m`, `p10_m ≤ salary_estimated_m ≤ p90_m` |
| Senior 40% ở tập thỏa thuận, 10% ở tập có lương | ước tính tin Senior có `warning` |
| Kỹ năng có 10 tin trong tập có lương | không có trong `skill_salary_shap_values` |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit/test_mining_salary_model.py -q` | Xanh |
| Dry-run | `python -m mining.run_mining_pipeline --only bi,salary --dry-run` (SHAP bật) | Gửi: n train/test, số công ty, MAE so baseline cấp × nghề cho hai cấu hình, std CV, MAE theo nhóm, top 15 kỹ năng theo `delta_m`, 4.1, cảnh báo phân bố |
| Không rò rỉ | metrics `n_companies_overlap` = 0 | Đạt |
| Sanity | S-04, S-05, S-06; đóng góp cấp tăng dần | Pass hoặc có giải thích |
| Người dùng | chọn cấu hình concept, xác nhận A hay B | Ghi vào Log |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| 1 | Duyệt đặc tả | 20/11 | "approved" | 1036a11 |
| 2 | Duyệt prompt | 20/11 | "continue" sau khi nhận bộ prompt | e230f28 |
| 3 | Test rồi code | 20/11 | 9 test mới (chia theo công ty, `company_id` null, `src::`, baseline lùi về cấp, khôi phục +8 triệu cài sẵn, P10 ≤ ước tính ≤ P90, phương án B, cảnh báo Senior, kỹ năng < 30 tin bị bỏ) + test S-05 slug. Code: `company_split`, `baseline_level_family` (dùng `bi.baseline_salary`), `mae_by_group`, `train_band_classifier`, `bootstrap_ci`, `factor_importance`, `compare_distributions`, `estimate_negotiable`; `train_salary_model` trả 4 phần tử. **Đi khác prompt:** P10/P90 kẹp quanh ước tính; tên cột Mart cũ của bảng SHAP giữ, thêm `delta_m`, `ci_low`, `ci_high` | (commit này) |
| 4 | Dry-run | 20/11 | Trước khi sửa: 1.620 tin train, chia ngẫu nhiên, R² 0,629, MAE 6,05, baseline cấp + kinh nghiệm 6,31. Sau: 1.561 tin, 0 công ty chung, baseline cấp × nghề 6,142; `tool_only` hơn 3,7% (B: macro-F1 0,53), `tool_concept` hơn 10,6% (A); S-05 từng skipped (L-56) | |
| 5 | Review, chạy thật | 20/11 | Người dùng "1.B 2.A": dùng `tool_concept`; phương án B chỉ khi A không đạt. Chạy thật `--only bi,fp,cluster,salary`: A, R²(log) 0,600, MAE 5,489; 2.172 ước tính, 1.274 có cảnh báo; sanity 4 pass / 1 info / 1 fail (S-06) | (commit này) |
