# M4: Tin "khác hoặc mới" cho SD3 (câu 3.3)

> Code: `mining/anomaly.py` (`build_anomaly_space`, `_reason_codes`, `detect_anomalies`, `salary_level_ratio`). Hàm mới đề xuất: `classify_kind` (mới / khác), `hand_check_sample`.
> Lệnh: `python -m mining.run_mining_pipeline --only cluster,anomaly [--dry-run]` (M4 cần điểm GLOSH của M3).
> Câu hỏi: [`docs/target/03_sd3_nhom_viec_va_tin_khac_hoac_moi.md`](../../target/03_sd3_nhom_viec_va_tin_khac_hoac_moi.md) câu 3.3. Trạng thái: **bản nháp 20/11, chờ duyệt.**

## 1. Mục đích

Tìm tin **khác** mặt bằng (đòi hỏi lệch so với cấp, lương lệch) hoặc **mới** (tổ hợp nội dung chưa thuộc nhóm nào), mỗi tin có **loại** và **lý do đọc được**. "Khác" không có nghĩa là tin lừa đảo; "mới" không có nghĩa là đang tăng (chỉ có hai tháng dữ liệu).

## 2. Luật

### 2.1. Đang chạy (code hiện tại, dry-run 20/11)

| Mã | Luật | Số 20/11 |
|---|---|---|
| M4.1 | Isolation Forest (300 cây, `contamination` 0,03) trên 8 đặc trưng: `exp_min_years`, `exp__missing`, `log_salary`, `log_salary_vs_level`, `salary__missing`, `n_skills`, `skills_per_level`, `seniority_ord`. Lương thiếu điền hằng + cờ, không bù | 118 tin |
| M4.2 | Thêm tin có cờ GLOSH của M3 (P97) | 118 tin; trùng IF 6 |
| M4.3 | `anomaly_score` = max(IF, GLOSH × cờ) | 230 tin bị gắn cờ (5,87%) |
| M4.4 | Mã lý do, luật sau ghi đè luật trước: `ISOLATION_GENERIC` (mặc định) → `TOO_MANY_SKILLS` (`n_skills` > P99) → `SALARY_TOO_LOW/HIGH_FOR_LEVEL` (< 1/3 hoặc > 3 × trung vị cùng cấp) → `EXP_SENIORITY_MISMATCH` (người mới, `exp_min_years` ≥ 5) → `FRESHER_TOO_MANY_SKILLS` (người mới, `n_skills` > 15) | `SKILL_PROFILE_OUTLIER` 109, `ISOLATION_GENERIC` 94, `FRESHER_TOO_MANY_SKILLS` 10, `SALARY_TOO_HIGH` 6, `TOO_MANY_SKILLS` 6, `SALARY_TOO_LOW` 5, `EXP_SENIORITY_MISMATCH` 0 |

`n_skills` của code cũ đếm 290 cột K-tool của M0 (khác `n_skills` của bước 10, đếm mọi loại). Ngưỡng 15 là số cố định, đặt khi kỹ năng còn lẫn soft.

### 2.2. Đề xuất, chờ duyệt

| Mã | Đề xuất | Lý do / số 20/11 |
|---|---|---|
| M4.1 | Isolation Forest dùng `n_tools` (bước 10) thay `n_skills`; `skills_per_level` = `n_tools / (seniority_ord + 1)`; lương là `salary_target_m` (M0.9). Giữ `contamination` 0,03, 300 cây | Một định nghĩa (M0.3) |
| M4.4a | **Ngưỡng theo phân vị của dữ liệu**, tính lại mỗi lần chạy và ghi vào metrics: `TOO_MANY_SKILLS` khi `n_tools` > P99 của mọi tin (20/11: 26,85 → > 26); `FRESHER_TOO_MANY_SKILLS` khi tin người mới có `n_tools` > P95 của tin người mới (20/11: 16) | Thay số cố định 15 |
| M4.4b | `EXP_SENIORITY_MISMATCH`: giữ ≥ 5 năm. 20/11 không tin nào thỏa (người mới ≥ 3 năm: 3 tin) | Giữ luật để bắt dữ liệu sau này; ghi 0 |
| M4.4c | Lương: chỉ xét tin có `salary_target_m` và `salary_outlier = false`; tin `salary_outlier = true` có mã riêng `SALARY_OUTLIER_FLAGGED` (Silver đã gắn cờ 87 tin) | Không gắn lý do lương trên số đã biết là ngoại lai |
| M4.5 | `classify_kind`: **khác** = có mã lý do cụ thể (khác `ISOLATION_GENERIC` và `SKILL_PROFILE_OUTLIER`); **mới** = cờ GLOSH, mã chỉ là `SKILL_PROFILE_OUTLIER`/`ISOLATION_GENERIC`, và các trường kinh nghiệm, lương, số công cụ nằm trong P5–P95 của cấp; còn lại = **chưa rõ** (IF gắn cờ nhưng không có lý do đọc được) | SD3 mục 4; hiện code chưa chia loại |
| M4.6 | `hand_check_sample`: 20 tin (seed 42), phân tầng theo loại (khác / mới / chưa rõ tỷ lệ theo số tin), xuất `sd3_anomaly_hand_check.csv` có cột `dung`, `loi_parse`, `ghi_chu`. Đã điền thì không ghi đè | Spec 08: tỷ lệ tin đúng là khác/mới thật so với tin do parse lỗi |

## 3. Quy trình xử lý

1. Nhận meta (M0) và `glosh_score`, `glosh_outlier`, `in_clustering` (M3). Tin không vào phân cụm (M3.1b) không có GLOSH.
2. `build_anomaly_space` (M4.1), Isolation Forest.
3. Tính ngưỡng phân vị (M4.4a), gán mã lý do.
4. Hợp IF và GLOSH; `classify_kind`.
5. `hand_check_sample`.
6. Ghi artifact (bỏ qua nếu dry-run).

## 4. Input → Output

| Input | Dùng |
|---|---|
| `meta`: `exp_min_years`, `seniority_ord`, `n_tools`, `salary_target_m`, `salary_outlier` | đặc trưng, lý do |
| `job_clusters` (M3) | GLOSH |

| Output | Nội dung |
|---|---|
| `job_anomalies.parquet` | `job_id`, `anomaly_score`, `isolation_score`, `glosh_score`, `source_flag` (if / glosh / both), `reason_code`, `kind` (khac / moi / chua_ro), các trường giải thích (`n_tools`, `exp_min_years`, `salary_ratio_to_level`) |
| `sd3_anomaly_hand_check.csv` | 20 tin để kiểm tay |
| `mining_metrics.json` khối `anomaly` | số tin theo nguồn cờ, theo mã, theo loại; ngưỡng phân vị đã dùng |

## 5. Dữ liệu mẫu

Điền sau lần chạy thật.

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Ngưỡng |
|---|---|
| Mỗi tin bị gắn cờ có đúng một `kind` và một `reason_code` | bắt buộc |
| Ngưỡng phân vị ghi trong metrics, chạy lại ra cùng số | bắt buộc |
| Kiểm tay 20 tin: tỷ lệ đúng là khác/mới thật | báo cáo; ngưỡng chờ PRE-36 |
| Tỷ lệ "chưa rõ" | báo cáo; cao thì xem lại M4.5 |
| `pytest tests/unit/test_mining_anomaly.py` (thêm test ngưỡng phân vị, `kind`) | xanh |

## 7. Trạng thái, chỗ thiếu, việc mở

- Có code; thiếu chia loại, ngưỡng theo dữ liệu, mẫu kiểm tay (MINE-7).
- Chờ duyệt M4.4a–c, M4.5 (định nghĩa "mới" dùng P5–P95), M4.6.
- PRE-36.
