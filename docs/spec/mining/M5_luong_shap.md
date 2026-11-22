# M5: Giá trị kỹ năng và lương ước tính cho SD4 (Random Forest + SHAP)

> Code: `mining/salary_model.py` (`select_training_subset`, `build_salary_features`, `assert_no_leakage`, `_groups`, `_cv_scores`, `train_salary_model`, `skill_values_from_shap`). Hàm mới đề xuất: `baseline_level_family`, `mae_by_group`, `estimate_negotiable`, `compare_distributions`, `train_band_classifier` (phương án B), `factor_importance`.
> Lệnh: `python -m mining.run_mining_pipeline --only bi,salary [--dry-run]` (baseline lấy từ M1).
> Câu hỏi: [`docs/target/04_sd4_gia_tri_ky_nang.md`](../../target/04_sd4_gia_tri_ky_nang.md). Trạng thái: **đã duyệt 20/11 (người dùng: "approved").** Train model là bước chính thức từ 16/11.

## 1. Mục đích

- 4.1 yếu tố nào ảnh hưởng lương công bố nhiều nhất;
- 4.2 mỗi kỹ năng cộng hoặc trừ khoảng bao nhiêu triệu/tháng (khi giữ các yếu tố khác);
- 4.3 model đúng tới đâu, với nhóm nào thì không nên tin;
- 4.4 ước tính khoảng lương cho tin "thỏa thuận", có nhãn "ước tính".

`premium(k)` của 4.2 là đầu vào điểm ưu tiên của M6. SHAP mô tả cách model dùng đặc trưng, **không phải nhân quả** (MINE-6).

## 2. Luật

### 2.1. Đang chạy (code hiện tại, dry-run 20/11, không SHAP)

| Mã | Luật | Số 20/11 |
|---|---|---|
| M5.1 | Tập train: lương > 0, không thỏa thuận, không `salary_suspect`, trong khoảng hợp lệ; bỏ tin lệch > 3 lần trung vị cùng cấp (`level_ratio_limit`) | 1.731 có lương; bỏ 20 vừa thỏa thuận vừa có số, 91 lệch so với cấp → 1.620 tin (41,4%) |
| M5.2 | Mục tiêu log1p(trung bình hai cận đã cap), tự tính trong `build_meta` | — |
| M5.3 | Đặc trưng: 290 `skill__`, `seniority_ord`, `exp_min_years` (+ cờ thiếu), nhóm tỉnh, one-hot `job_family` | 310 cột |
| M5.4 | Chia: `_groups` dùng `dup_group_id`; không có cột này nên **chia ngẫu nhiên** 80/20; CV 5 phần | train 1.296, test 324 |
| M5.5 | RF chọn 1 trong 4 bộ tham số bằng CV | Bộ 2 (depth 20, leaf 3): CV R² 0,571 ± 0,030 |
| M5.6 | Baseline: model "cấp + kinh nghiệm" | Holdout: model R²(log) 0,629, MAE 6,05 triệu; baseline MAE 6,31 → hơn baseline 4,1% |
| M5.7 | Ngưỡng trong code: R² ≥ 0,60, MAE ≤ 4,5, std CV ≤ 0,05 | R² đạt, MAE không đạt, std đạt |

Độ quan trọng (impurity) cao nhất 20/11: `exp_min_years` 0,40, `seniority_ord` 0,27, rồi aws 0,022, kubernetes 0,014, `jf::Bridge` 0,013. Số này **lạc quan** vì chia ngẫu nhiên: cùng công ty có thể ở cả hai phía.

### 2.2. Đề xuất, đã duyệt 20/11 (code xong 20/11; quyết định sau review ở cuối bảng)

| Mã | Đề xuất | Lý do |
|---|---|---|
| M5.1 | Tập có lương = `salary_target_m` khác null, `salary_negotiable = false`, `salary_outlier = false`. Giữ luật lệch > 3 lần trung vị cùng cấp và ghi số tin bị bỏ theo lý do. 20/11 trước luật lệch: 1.644 − 20 vừa thỏa thuận vừa có số | Dùng cờ Silver, không tự tính lại (M0.9) |
| M5.2 | Mục tiêu = log1p(`salary_target_m`) của bước 10 | Quyết định 4 (19/11) |
| M5.3a | Đặc trưng chính: `skill__*` (K-tool, bỏ `other_skill`), `seniority_ord`, `exp_min_years` + cờ thiếu, nhóm tỉnh, `fam__*`, **`src__*`** | Quyết định 5: `source` là biến kiểm soát (itviec, topdev công bố lương ít, mức khác) |
| M5.3b | **`concept__*` là đặc trưng phụ**: chạy hai cấu hình (có / không có `concept__`), báo cả hai bộ chỉ số. **Không** tự chọn cấu hình tốt hơn; người dùng chọn khi xem số | Tránh chọn ngầm; concept nhiều cột (561) dễ nhiễu |
| M5.3c | `assert_no_leakage` chặn mọi cột chứa "salary" (gồm `salary_target_m`, `salary_bin_*`, `salary_mid`, `salary_range_ratio`) | Spec 06 mục 2.2 |
| M5.4 | **Chia theo `company_id`**: GroupShuffleSplit 80/20 (seed 42); CV GroupKFold 5 phần theo công ty trên phần train. Kiểm: không `company_id` nào ở cả hai phía. `company_id` null (1 tin) thành nhóm riêng theo `job_id` | SD4 mục 4; 978 công ty trong tập có lương, công ty lớn nhất 21 tin |
| M5.6 | **Baseline = trung vị `salary_target_m` cấp × nghề** lấy từ `sd1_baseline_salary.json` (M1.B), tính lại **chỉ trên phần train** để không rò test | SD4 |
| M5.7 | **Phương án A đạt** khi MAE test thấp hơn baseline ≥ 10% (chốt 22/11, L-60) **và** std R² qua CV ≤ 0,05. R² ≥ 0,60 và MAE ≤ 4,5 chỉ báo cáo (chốt 22/11, L-60). Không đạt → **phương án B**: RF phân lớp 4 khung theo tứ phân vị của phần train, macro-F1 và accuracy so với baseline "luôn đoán khung đông nhất" | SD4 mục 4 |
| M5.8 | 4.3: `mae_by_group` theo `job_family`, `seniority`, `source` trên tập test; nhóm n < 30 ghi "ít dữ liệu" | SD4 câu 4.3 |
| M5.9 | 4.1: `factor_importance` = trung bình |SHAP| gộp theo nhóm đặc trưng (cấp, kinh nghiệm, tỉnh, nghề, nguồn, kỹ năng gộp, từng kỹ năng top 20) | Impurity importance thiên về biến liên tục |
| M5.10 | 4.2: `skill_values_from_shap` giữ cách tính hiện có (trung bình φ trên tin có kỹ năng, quy ra triệu bằng lương nền × (e^φ − 1)); **chỉ định giá kỹ năng có ≥ 30 tin trong tập có lương** (`min_skill_sample`); thêm khoảng tin cậy bootstrap 200 lần (seed 42) trên các tin có kỹ năng. Ghi chú F10.6: cấp và kinh nghiệm tương quan nên chia điểm SHAP với nhau | SD4 câu 4.2 |
| M5.11 | 4.4: `estimate_negotiable` cho tin thỏa thuận (2.192 tin, trừ tin có số): `salary_estimated_m` = expm1(trung bình các cây), `p10`, `p90` từ dự đoán từng cây, `salary_is_estimated = true`. Lưu ở `salary_estimates.parquet`, **không ghi đè** cột lương nào | SD4 câu 4.4 |
| M5.12 | `compare_distributions`: tỷ lệ cấp, nghề, nguồn ở tập thỏa thuận so với tập có lương. Nhóm nào tỷ lệ ở tập thỏa thuận ≥ 2 lần tập có lương thì ước tính của nhóm đó mang `warning`. 20/11: Senior 20,7% ở tập thỏa thuận so với 8,8% ở tập có lương (2,4 lần) → Senior bị cảnh báo | SD4 "Kiểm tra trước khi ước tính"; MNAR |
| M5.13 | Model cuối fit lại trên toàn tập có lương (chỉ số lấy từ holdout); SHAP tối đa 3.000 dòng | Như code hiện tại |
| M5.3b' | **Quyết định 1.B (20/11, sau dry-run):** dùng cấu hình `tool_concept` (`SalaryParams.feature_config`); `tool_only` vẫn được đo và ghi trong `configs` | `tool_only` hơn baseline 3,7% (không đạt A); `tool_concept` hơn 10,6% (đạt A), R²(log) 0,600 |
| M5.7' | **Quyết định 2.A (20/11):** phương án B chỉ chạy khi A không đạt | Lần chạy thật đạt A nên không có `band_classifier`. Dry-run `tool_only` (B): macro-F1 0,53, accuracy 0,57 so với 0,30 khi đoán khung đông nhất |
| M5.11' | P10, P90 được kẹp để luôn bao quanh ước tính (`min(p10, ước tính)`, `max(p90, ước tính)`) | Trung bình các cây (thang log) gần như luôn nằm trong P10–P90; kẹp chỉ để hợp đồng `p10 ≤ ước tính ≤ p90` không bao giờ sai |

## 3. Quy trình xử lý

1. Tập có lương (M5.1); ghi số bỏ theo lý do.
2. Dựng đặc trưng (M5.3a), cấu hình phụ thêm `concept__` (M5.3b); `assert_no_leakage`.
3. GroupShuffleSplit theo `company_id`; kiểm không trùng công ty.
4. Baseline cấp × nghề trên phần train (M5.6).
5. Chọn tham số bằng GroupKFold; fit; holdout R², MAE, RMSE; so baseline (M5.7).
6. Nếu A không đạt: phương án B.
7. `mae_by_group` (M5.8).
8. Fit lại trên toàn tập; SHAP; `factor_importance` (M5.9); `skill_values_from_shap` + bootstrap (M5.10).
9. `compare_distributions` (M5.12), `estimate_negotiable` (M5.11).
10. Sanity S-04 (đã sửa ở M0), S-05, S-06; mức đóng góp SHAP của cấp tăng dần; chiều giá trị kỹ năng so với chênh lệch trung vị thô (tin có / không có kỹ năng) ở tập có lương.
11. Ghi artifact (bỏ qua nếu dry-run).

## 4. Input → Output

| Input | Dùng |
|---|---|
| `meta`: `salary_target_m`, `salary_negotiable`, `salary_outlier`, `seniority_ord`, `exp_min_years`, `province`, `job_family`, `source`, `company_id` | mục tiêu, đặc trưng, chia nhóm |
| `MiningData.skills`, `.concepts` | đặc trưng |
| `sd1_baseline_salary.json` (M1) | đối chiếu baseline |

| Output | Nội dung |
|---|---|
| `skill_salary_shap_values.parquet` | kỹ năng, `n_jobs`, `phi_mean`, `delta_m` (triệu), `ci_low`, `ci_high`, `job_family` (ALL hoặc nghề nếu đủ tin) |
| `salary_factor_importance.json` | 4.1 |
| `salary_estimates.parquet` | `job_id`, `salary_estimated_m`, `p10_m`, `p90_m`, `salary_is_estimated`, `warning` |
| `trained_salary_rf_model.joblib` | model cuối |
| `mining_metrics.json` khối `salary` | phương án, số tin, tham số, CV, holdout, baseline, % hơn baseline, MAE theo nhóm, hai cấu hình concept |

## 5. Dữ liệu mẫu

Chạy thật 20/11 (`--only bi,fp,cluster,salary`, cấu hình `tool_concept`, sha256 đầu vào như M0):

| Mục | Số |
|---|---|
| Tập có lương (M5.1) | 1.561 tin; bỏ 20 vừa thỏa thuận vừa có số, 86 `salary_outlier`, 64 lệch > 3 lần trung vị cấp |
| Chia theo công ty (M5.4) | train 1.247 tin / 746 công ty, test 314 tin / 187 công ty, **0 công ty chung** |
| Baseline cấp × nghề (M5.6) | MAE 6,142 triệu (220 tin dùng ô, 94 lùi về cấp) |
| `tool_only` | 318 đặc trưng; CV R² 0,567 ± 0,030; holdout R²(log) 0,558, MAE 5,918; hơn baseline 3,7% → không đạt A |
| `tool_concept` (dùng) | 879 đặc trưng; CV R² 0,569 ± 0,028; holdout R²(log) 0,600, MAE 5,489, RMSE 7,392; **hơn baseline 10,6% → phương án A** |
| 4.1 nhóm yếu tố (mean \|tổng SHAP\|) | kinh nghiệm 42%, cấp bậc 26%, khái niệm 13%, nguồn tin 8%, công cụ 6%, nghề 2%, tỉnh 2% |
| Đóng góp SHAP của cấp | Intern/Fresher −0,230 < Junior −0,067 < Middle +0,047 < Senior +0,201 (tăng dần, đạt); Lead/Manager +0,176 |
| 4.2 công cụ cộng nhiều nhất (triệu/tháng, CI 95%) | kubernetes +0,62 (0,53–0,71), cisco +0,53, docker +0,43, oracle_db +0,37, cpp +0,32, spring_boot +0,25, claude +0,24, tensorflow +0,23 |
| 4.2 công cụ trừ nhiều nhất | illustrator −1,11, photoshop −0,53, mysql −0,21, excel −0,19, powerpoint −0,13 |
| Chiều so với chênh trung vị thô | 66,7% trong 78 công cụ được định giá (lương nền SHAP 20,93 triệu) |
| 4.3 MAE theo nhóm (test) | model kém baseline ở Other, Tester (sát), Intern/Fresher; nhóm < 30 tin ghi "ít dữ liệu" (DevOps, Security, Senior, itviec, …) |
| 4.4 ước tính (M5.11) | 2.172 tin thỏa thuận; trung vị 26,5 triệu (tin có lương: 21,0); độ rộng P10–P90 trung vị 19,6 triệu |
| Cảnh báo phân bố (M5.12) | 1.274 tin: Senior (2,1 lần), cấp Không rõ (2,6), DevOps/Cloud (2,1), IoT (2,5), itviec (2,9), vietnamworks (2,5) |
| Sanity | S-04, S-05 pass (aws φ 0,008, kubernetes 0,029); S-06 fail (đã chốt) |

Có `concept__` thì giá trị các công cụ nhỏ hơn bản `tool_only` (kubernetes 0,97 → 0,62), vì khái niệm đi kèm chia điểm SHAP với công cụ.

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Ngưỡng |
|---|---|
| Không rò rỉ: không `company_id` nào ở cả train và test; `assert_no_leakage` pass | bắt buộc |
| A thắng baseline cấp × nghề | MAE thấp hơn ≥ 10% (chốt 22/11; đạt 16,7%) |
| std R² qua GroupKFold | ≤ 0,05 |
| S-04 (sửa ở M0), S-05 (φ > 0 cho AWS, Kubernetes hoặc System Design), S-06 | pass hoặc có giải thích |
| Đóng góp SHAP của cấp tăng dần Intern/Fresher → Senior | pass hoặc có giải thích (Lead MNAR) |
| Chỉ định giá kỹ năng ≥ 30 tin | bắt buộc |
| Tin thỏa thuận không dùng để chấm model | bắt buộc |
| `pytest tests/unit/test_mining_salary_model.py` (thêm: chia theo công ty, baseline cấp × nghề, khoảng p10–p90, cảnh báo phân bố) | xanh |

## 7. Trạng thái, chỗ thiếu, việc mở

- **Chạy thật 20/11** (mục 5): phương án A với `tool_concept` (quyết định 1.B, 2.A).
- Artifact: `skill_salary_shap_values.parquet` (thêm `delta_m`, `ci_low`, `ci_high`; chỉ kỹ năng ≥ 30 tin), `salary_estimates.parquet`, `salary_factor_importance.json` (4.1 và bảng so phân bố), `trained_salary_rf_model.joblib`.
- Sửa kèm: S-05 luôn "skipped" vì so tên `AWS` với slug `aws` (L-56).
- Giá trị kỹ năng đều dưới ±1,2 triệu: kinh nghiệm và cấp giải thích phần lớn; không đọc thành "học X thì lương tăng X" (MINE-6).
- MINE-5 (Mart chưa có bảng SHAP), PRE-35 (lương phủ 44%). SHAP là liên hệ, không phải nhân quả.
