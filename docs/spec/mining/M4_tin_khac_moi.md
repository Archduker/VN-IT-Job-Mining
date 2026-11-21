# M4: Tin "khác hoặc mới" cho SD3 (câu 3.3)

> Code: `mining/anomaly.py` (`build_anomaly_space`, `_reason_codes`, `detect_anomalies`, `salary_level_ratio`). `classify_kind` (mới / khác / chưa rõ), `hand_check_sample`.
> Lệnh: `python -m mining.run_mining_pipeline --only cluster,anomaly [--dry-run]` (M4 cần điểm GLOSH của M3).
> Câu hỏi: [`docs/target/03_sd3_nhom_viec_va_tin_khac_hoac_moi.md`](../../target/03_sd3_nhom_viec_va_tin_khac_hoac_moi.md) câu 3.3. Trạng thái: **chạy thật 20/11 (quyết định 1.B, 2.A).**

## 1. Mục đích

Tìm tin **khác** mặt bằng (đòi hỏi lệch so với cấp, lương lệch) hoặc **mới** (tổ hợp nội dung chưa thuộc nhóm nào), mỗi tin có **loại** và **lý do đọc được**. "Khác" không có nghĩa là tin lừa đảo; "mới" không có nghĩa là đang tăng (chỉ có hai tháng dữ liệu).

## 2. Luật

### 2.1. Đang chạy (code 20/11, chạy thật 20/11)

| Mã | Luật | Số 20/11 |
|---|---|---|
| M4.1 | Isolation Forest (300 cây, `contamination` 0,03) trên 8 đặc trưng: `exp_min_years`, `exp__missing`, `log_salary`, `log_salary_vs_level`, `salary__missing`, `n_tools`, `tools_per_level` = `n_tools / (seniority_ord + 1)`, `seniority_ord`. Lương = `salary_target_m`, chỉ dùng khi hợp lệ và `salary_outlier = false`; thiếu thì điền 0 + cờ, không bù | 109 tin |
| M4.1b | **Quyết định 1.B (20/11):** IF chỉ fit trên tin **biết cấp** (`seniority_ord ≥ 0`). Cấp −1 nằm tách riêng trong không gian nên trước đó IF bắt chủ yếu "tin thiếu cấp" (97/117 cờ, trong khi nhóm này chỉ 7,3% dữ liệu). Tin chưa rõ cấp không có `isolation_score`; vẫn xét bằng GLOSH và luật: có mã lý do cụ thể thì gắn cờ, nguồn `rule` | 285 tin không qua IF; 22 tin gắn cờ nguồn `rule` |
| M4.2 | Thêm tin có cờ GLOSH của M3 (P97). Tin không vào phân cụm có GLOSH null, coi là không cờ | 118 tin; trùng IF 3 |
| M4.3 | `anomaly_score` = max(IF, GLOSH × cờ) | **246 tin (6,28%)**: `glosh` 115, `if` 106, `rule` 22, `both` 3 |
| M4.4 | Mã lý do, luật sau ghi đè luật trước: `ISOLATION_GENERIC` → `SKILL_PROFILE_OUTLIER` (có cờ GLOSH) → `TOO_MANY_SKILLS` (`n_tools` > P99 mọi tin) → `SALARY_OUTLIER_FLAGGED` → `SALARY_TOO_LOW/HIGH_FOR_LEVEL` (< 1/3 hoặc > 3 × trung vị cùng cấp) → `EXP_SENIORITY_MISMATCH` (người mới, `exp_min_years` ≥ 5) → `FRESHER_TOO_MANY_SKILLS` (người mới, `n_tools` > P95 của tin người mới) | Ngưỡng: P99 = 26,85; P95 người mới = 16. `SKILL_PROFILE_OUTLIER` 113, `SALARY_TOO_LOW` 34, `FRESHER_TOO_MANY` 31, `ISOLATION_GENERIC` 24, `TOO_MANY_SKILLS` 18, `SALARY_OUTLIER_FLAGGED` 16, `SALARY_TOO_HIGH` 10, `EXP_SENIORITY_MISMATCH` 0 |
| M4.5 | `classify_kind`: **khác** = có mã cụ thể; **mới** = cờ GLOSH, mã chung (`SKILL_PROFILE_OUTLIER`/`ISOLATION_GENERIC`), và kinh nghiệm, lương, số công cụ trong P5–P95 của cấp. **Quyết định 2.A (20/11):** trường bị thiếu tính là không lệch. Còn lại = **chưa rõ** | khác 109, mới 105, chưa rõ 32 (13,0%; trước 1.B là 40%) |
| M4.6 | `hand_check_sample`: 20 tin (seed 42), phân tầng theo loại, xuất `sd3_anomaly_hand_check.csv` có cột `dung`, `loi_parse`, `ghi_chu`. Đã điền thì không ghi đè | 20 tin |

Bảng chéo mã × loại (20/11): mọi tin "mới" có mã `SKILL_PROFILE_OUTLIER`; "chưa rõ" gồm 24 `ISOLATION_GENERIC` và 8 `SKILL_PROFILE_OUTLIER` có trường lệch khỏi P5–P95 của cấp.

### 2.2. Đề xuất chờ duyệt

Không còn. M4.4a–c, M4.5, M4.6 (duyệt 20/11) đã vào code ở mục 2.1, kèm quyết định 1.B, 2.A.

## 3. Quy trình xử lý

1. Nhận meta (M0) và `glosh_outlier_score`, `is_outlier` (M3). Tin không vào phân cụm (M3.1b) có GLOSH null.
2. `build_anomaly_space` (M4.1), Isolation Forest trên tin biết cấp (M4.1b).
3. Tính ngưỡng phân vị, gán mã lý do (M4.4).
4. Hợp IF, GLOSH và cờ luật cho tin chưa rõ cấp; `classify_kind` (M4.5).
5. `hand_check_sample` (M4.6).
6. Ghi artifact (bỏ qua nếu dry-run).

## 4. Input → Output

| Input | Dùng |
|---|---|
| `meta`: `exp_min_years`, `seniority_ord`, `n_tools`, `salary_avg_mil` (= `salary_target_m`), `salary_outlier` | đặc trưng, lý do |
| `job_clusters` (M3) | GLOSH |

| Output | Nội dung |
|---|---|
| `job_anomalies.parquet` | 6 cột Mart (`job_id`, `job_title`, `company_name`, `anomaly_score`, `reason_code`, `detected_by`: `IsolationForest` / `HDBSCAN_GLOSH` / cả hai / `Rule`) + `isolation_score`, `glosh_outlier_score`, `source_flag` (if / glosh / both / rule), `kind` (khac / moi / chua_ro), `n_tools`, `exp_min_years`, `salary_ratio_to_level` |
| `sd3_anomaly_hand_check.csv` | 20 tin để kiểm tay |
| `mining_metrics.json` khối `anomaly` | số tin theo nguồn cờ, theo mã, theo loại, `kind_by_reason`, `share_chua_ro`, `n_rule_unknown_level`, `n_unknown_level_excluded_from_if`; ngưỡng đã dùng (`thresholds_used`) |

## 5. Dữ liệu mẫu

Chạy thật 20/11 (`python -m mining.run_mining_pipeline`; Silver sha256_16 `ab97efa75bb7f48d`, features `a6d41b4f7159fa4e`).

| Loại | Tin | Mã | n_tools | KN (năm) | Lương / trung vị cấp |
|---|---|---|---|---|---|
| khác | DevOps/Platform Engineer (người mới) | `FRESHER_TOO_MANY_SKILLS` | 30 | 0 | 2,16 |
| khác | IT Intern | `FRESHER_TOO_MANY_SKILLS` | 22 | 0 | 0,40 |
| khác | Backend .NET Developer (Microservices/API), người mới | `FRESHER_TOO_MANY_SKILLS` | 29 | 0 | — |
| mới | Chuyên viên lập trình báo cáo các phân hệ SAP | `SKILL_PROFILE_OUTLIER` | 15 | 0 | 2,00 |
| mới | Thực tập sinh triển khai phần mềm | `SKILL_PROFILE_OUTLIER` | 6 | 0 | 0,35 |
| chưa rõ | AI Agent - Tech Lead (Golang, ReactJS, Python, NodeJS) | `ISOLATION_GENERIC` | 26 | 5 | 1,61 |
| chưa rõ | Quality Assurance Manager | `ISOLATION_GENERIC` | 24 | 5 | 1,75 |

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Ngưỡng | Kết quả 20/11 |
|---|---|---|
| Mỗi tin bị gắn cờ có đúng một `kind` và một `reason_code` | bắt buộc | đạt (test) |
| Ngưỡng phân vị ghi trong metrics, chạy lại ra cùng số | bắt buộc | đạt (dry-run và chạy thật cùng 246 tin, cùng ngưỡng) |
| Kiểm tay 20 tin: tỷ lệ đúng là khác/mới thật | báo cáo; ngưỡng chờ PRE-36 | chờ người dùng |
| Tỷ lệ "chưa rõ" | báo cáo; cao thì xem lại M4.5 | 13,0% |
| `pytest tests/unit/test_mining_anomaly.py` | xanh | 11 passed |

## 7. Trạng thái, chỗ thiếu, việc mở

- Code xong và chạy thật 20/11 (quyết định 1.B, 2.A).
- Mở: kiểm tay `sd3_anomaly_hand_check.csv`; ngưỡng nghiệm thu chờ PRE-36.
- `EXP_SENIORITY_MISMATCH` chưa bắt tin nào (người mới ≥ 5 năm: 0 tin); giữ luật cho dữ liệu sau.
- Nhóm "mới" gồm nhiều tin thực tập lương thấp (tỷ lệ 0,35–0,5 vẫn trong P5–P95 của cấp): GLOSH xem hồ sơ kỹ năng lạ, chưa chắc là nghề mới. Kiểm tay sẽ cho biết có cần siết M4.5 không.
