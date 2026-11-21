# Prompt M4: Tin "khác hoặc mới" cho SD3

> Đặc tả: [`docs/spec/mining/M4_tin_khac_moi.md`](../../spec/mining/M4_tin_khac_moi.md) (M4.1, M4.4a–c, M4.5, M4.6; đã duyệt 20/11). Câu hỏi: `docs/target/03_sd3_nhom_viec_va_tin_khac_hoac_moi.md` câu 3.3.
> **Trạng thái:** viết 20/11, chờ duyệt prompt. Cần M0, M3 xong.

## 1. Ngữ cảnh

**Đọc trước:** đặc tả M4; `mining/anomaly.py`; `tests/unit/test_mining_anomaly.py`.

**Vì sao làm** (dry-run 20/11):

- 230 tin bị gắn cờ, nhưng chưa chia loại "mới" / "khác".
- 203/230 tin chỉ mang mã chung (`SKILL_PROFILE_OUTLIER` 109, `ISOLATION_GENERIC` 94).
- Ngưỡng 15 kỹ năng là số cố định, đặt khi kỹ năng còn lẫn soft.

**Ngưỡng theo dữ liệu 19/11:** `n_tools` P99 toàn bộ 26,85; P95 tin người mới 16.

## 2. Việc cần sửa

**Input:**

- `meta`: `exp_min_years`, `seniority_ord`, `n_tools`, `salary_target_m`, `salary_outlier`;
- kết quả M3: `glosh_score`, `glosh_outlier`, `in_clustering`.

**Output:**

- `job_anomalies.parquet`: `job_id`, `anomaly_score`, `isolation_score`, `glosh_score`, `source_flag`, `reason_code`, `kind`, `n_tools`, `exp_min_years`, `salary_ratio_to_level`.
- `sd3_anomaly_hand_check.csv`.
- Khối `anomaly` trong metrics, gồm `thresholds_used`.

**File:**

- `mining/anomaly.py`: `build_anomaly_space` dùng `n_tools` và `salary_target_m`; `_reason_codes` dùng ngưỡng phân vị; thêm `classify_kind`, `hand_check_sample`.
- `mining/config.py`: `AnomalyParams.too_many_q` 0,99, `fresher_q` 0,95, `normal_band` (0,05, 0,95), `hand_check_n` 20; bỏ `fresher_skill_limit`.
- `run_mining_pipeline.py`.

## 3. Pseudo code

```
X = [exp_min_years, exp__missing, log_salary, log_salary_vs_level, salary__missing,
     n_tools, n_tools / (seniority_ord+1), seniority_ord]     # lương = salary_target_m khi !salary_outlier
iso = IsolationForest(300, contamination 0.03, seed 42)
t_all = quantile(n_tools, 0.99); t_new = quantile(n_tools[newcomer], 0.95)
reason (luật sau ghi đè):
    ISOLATION_GENERIC → SKILL_PROFILE_OUTLIER (cờ GLOSH) → TOO_MANY_SKILLS (n_tools > t_all)
    → SALARY_OUTLIER_FLAGGED (salary_outlier) → SALARY_TOO_LOW/HIGH (ratio < 1/3 | > 3, chỉ lương hợp lệ)
    → EXP_SENIORITY_MISMATCH (newcomer & exp ≥ 5) → FRESHER_TOO_MANY_SKILLS (newcomer & n_tools > t_new)
flagged = iso ∪ glosh_outlier
kind:
    reason ∉ {ISOLATION_GENERIC, SKILL_PROFILE_OUTLIER} → "khac"
    glosh_outlier & reason ∈ {…GENERIC, SKILL_PROFILE…} & exp, lương, n_tools trong P5–P95 của cấp → "moi"
    còn lại → "chua_ro"
hand_check: 20 tin seed 42, phân tầng theo kind (tỷ lệ theo số tin, mỗi loại ≥ 1 nếu có) → csv;
    file đã điền → không ghi đè
```

## 4. Ràng buộc

- Không bù lương; lương thiếu → hằng + cờ như cũ.
- Tin không vào phân cụm (M3.1b) không có GLOSH; vẫn chạy Isolation Forest.
- Ngưỡng phân vị tính lại mỗi lần chạy và ghi vào metrics, không hardcode số.
- "khác" không phải "lừa đảo". Không đặt tên mã gợi ý điều đó.

## 5. Ví dụ (thành test)

| Đầu vào (dựng tay) | Kết quả mong đợi |
|---|---|
| 100 tin `n_tools` 1..100 | `t_all` = P99 = 99,01; tin 100 có `TOO_MANY_SKILLS` |
| Junior `n_tools` > P95 người mới | `FRESHER_TOO_MANY_SKILLS`, `kind` "khac" |
| Tin `salary_outlier` true | `SALARY_OUTLIER_FLAGGED`, không có mã lương theo cấp |
| Tin GLOSH, các trường trong P5–P95 | `kind` "moi" |
| Tin chỉ IF gắn cờ, không mã cụ thể, trường lệch | `kind` "chua_ro" |
| Tin `in_clustering` false | có `isolation_score`, `glosh_score` null |
| Mỗi tin bị gắn cờ | đúng một `kind`, một `reason_code` |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit/test_mining_anomaly.py -q` | Xanh |
| Dry-run | `python -m mining.run_mining_pipeline --only cluster,anomaly --dry-run` | Gửi: số tin theo nguồn cờ, mã, loại; ngưỡng đã dùng |
| Kiểm tay | người dùng điền csv 20 tin | Ghi tỷ lệ đúng / do parse lỗi |
| Tỷ lệ "chua_ro" | báo cáo | Cao (> 50%) thì xem lại M4.5 cùng người dùng |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| 1 | Duyệt đặc tả | 20/11 | "approved" | 1036a11 |
| 2 | Duyệt prompt | 20/11 | "continue" sau khi nhận bộ prompt | e230f28 |
| 3 | Test rồi code | 20/11 | `tests/unit/test_mining_anomaly.py` 11 test (ngưỡng P99, P95 người mới, `SALARY_OUTLIER_FLAGGED`, mới/chưa rõ, GLOSH null, một `kind` mỗi tin, mẫu kiểm tay phân tầng, tin chưa rõ cấp không qua IF). `AnomalyParams` bỏ `fresher_skill_limit`, thêm `too_many_q`, `fresher_q`, `normal_band`, `hand_check_n`; driver truyền GLOSH null, ghi `sd3_anomaly_hand_check.csv` | (commit này) |
| 4 | Dry-run | 20/11 | Trước khi sửa: 230 tin (5,87%), IF 118, GLOSH 118, cả hai 6. Sau khi sửa: 230 tin, chưa rõ 40%; 97/117 cờ IF là tin chưa rõ cấp (nhóm 7,3% dữ liệu) | |
| 5 | Review, chạy thật | 20/11 | Người dùng "1.b 2.a": IF chỉ fit tin biết cấp, tin chưa rõ cấp có mã cụ thể gắn cờ nguồn `rule`; trường thiếu tính là không lệch. Chạy thật cả chuỗi: 246 tin (6,28%), IF 106 + GLOSH 115 + cả hai 3 + rule 22; khác 109, mới 105, chưa rõ 32 (13%). Ngưỡng P99 26,85, P95 người mới 16. **Kiểm tay 20 tin còn mở** | (commit này) |
