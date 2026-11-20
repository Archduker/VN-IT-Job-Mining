# ĐẶC TẢ MINING (M0–M6): HỢP ĐỒNG CHUNG

> **Dự án:** VN-IT-Job-Mining. Đề tài: "Tích hợp và khai phá dữ liệu thị trường lao động phục vụ phân tích nghề nghiệp và kỹ năng trong IT".
> **Phiên bản:** 3.1.0, ngày 20/11/2026. **Trạng thái:** nháp, chờ duyệt cùng [`docs/spec/mining/`](mining/README.md). Bản 3.0.0 (17/11) đã duyệt; bản này rút phần chi tiết từng bước sang `spec/mining/` (như spec 06 với `spec/processing/`) và thay quyết định 3.
> **Quan hệ với tài liệu khác:** mã bước M1–M6 lấy theo [spec 03](03_data_mining_lifecycle.md) mục 3.3; M0 là phần nạp dữ liệu chung. Câu hỏi của từng SD ở [`docs/target/`](../target/00_de_tai.md); điều kiện dữ liệu ở [`06_yeu_cau_du_lieu.md`](../target/06_yeu_cau_du_lieu.md). **Luật chi tiết, quy trình, số hiện trạng của từng bước chỉ ghi ở file bước trong [`spec/mining/`](mining/README.md).** Nghiệm thu: [spec 08](08_evaluation_spec.md).

## 0. Cách đọc

- **Nguồn sự thật:** code `mining/` (`run_mining_pipeline.py` `STEPS`, `config.py`), rồi `mining/artifacts/mining_metrics.json` của lần chạy thật, rồi `docs/target/`.
- Số "hiện trạng" của từng bước là lần dry-run chỉ đọc 20/11/2026 trên dữ liệu Processing 19/11 (3.916 tin), ghi ở file bước.
- Ngưỡng chưa chốt ghi "đề xuất" và trỏ về PRE-36.

## 1. Ba tầng và các bước

| Tầng | Bước | Thuật toán | SD | Code | Đặc tả chi tiết |
|---|---|---|---|---|---|
| Chung | M0 | Nạp Silver, ba ma trận kỹ năng, e5 `job`, sanity | — | `mining/config.py`, `data_io.py`, `sanity.py` | [`M0_chuan_bi.md`](mining/M0_chuan_bi.md) |
| BI | M1 | Đếm, tỷ lệ, bảng chéo, trung vị, tứ phân vị | SD1 | **mới** `mining/bi.py` | [`M1_bi.md`](mining/M1_bi.md) |
| Không giám sát | M2 | FP-Growth, luật kết hợp | SD2 | `mining/association.py` | [`M2_fp_growth.md`](mining/M2_fp_growth.md) |
| Không giám sát | M3 | SVD, K-Means, HDBSCAN | SD3 (3.1, 3.2) | `mining/clustering.py` | [`M3_phan_cum.md`](mining/M3_phan_cum.md) |
| Không giám sát | M4 | Isolation Forest + GLOSH | SD3 (3.3) | `mining/anomaly.py` | [`M4_tin_khac_moi.md`](mining/M4_tin_khac_moi.md) |
| Train model | M5 | Chia theo công ty, Random Forest + SHAP; phương án B phân lớp khung lương | SD4 | `mining/salary_model.py` | [`M5_luong_shap.md`](mining/M5_luong_shap.md) |
| Tổng hợp | M6 | Điểm ưu tiên, thứ tự theo gói, coverage@N | SD5 | **mới** `mining/recommend.py` | [`M6_lo_trinh.md`](mining/M6_lo_trinh.md) |

- **Thứ tự chạy** (spec 03 mục 7): `bi, fp, cluster, anomaly, salary, recommend`. M4 sau M3 (dùng GLOSH); M5 sau M1 (baseline); M6 sau cùng (dùng M1, M2, M5). Hiện `STEPS` chỉ có `fp, cluster, anomaly, salary` (M0.5).
- **Lệnh:** `python -m mining.run_mining_pipeline [--only …] [--dry-run]`. Chỉ đọc file trên máy, ghi `mining/artifacts/`; không đụng R2, PostgreSQL, Airflow. Nạp Postgres cho Insights (`scripts/load_mart_from_parquet.py`) là việc riêng.
- **`--synthetic`** chỉ để test, ghi `mining/artifacts/_synthetic/`, metrics có `"synthetic": true`; không bao giờ lấy số báo cáo (L-19).
- `RANDOM_STATE = 42`.

## 2. Đầu vào chung

| Đầu vào | Đường dẫn | Dùng ở |
|---|---|---|
| Silver (bảng sạch, 26 trường) | `data/preprocessing/04_normalization/silver.parquet`. Code hiện vẫn trỏ `DEFAULT_GOLDEN` legacy và lùi về `all.parquet` (M0.1, PRE-39) | M1–M6 |
| Ma trận đặc trưng | `data/processing/10_features/features.parquet`, `encoding_dictionary.json` | M2–M5 |
| Kỹ năng theo tin | `data/processing/08_skills/job_skills.parquet` + `processing.extraction.skills.skill_view` | M1, M2 (bảng 2.1), M6 |
| Vector e5 | `data/processing/12_e5/job_emb.npz`, **khóa `job`** (mô tả + yêu cầu) | M3 |

- Nối các file theo `job_id` (Silver) = `job_id_global` (Processing); Silver và features **không cùng thứ tự dòng**.
- **Ba góc nhìn kỹ năng** (`06_yeu_cau_du_lieu.md` mục 2): K-tool = `skill__*`, K-concept = `concept__*`, K-soft = `soft__*`. Cột `<khối>__other_skill` không phải kỹ năng, không đưa vào luật, xếp hạng hay vector.
- Người mới = Intern/Fresher + Junior; Middle+ = Middle, Senior, Lead/Manager.
- Lương: `salary_target_m` của bước 10 (triệu VNĐ/tháng), chỉ trên tin `salary_outlier = false`; không bù lương thiếu.
- Mining không sửa giá trị của Silver hay Processing.

## 3. Đặc tả từng bước

Xem [`docs/spec/mining/`](mining/README.md). Mỗi file theo khuôn 7 mục (Mục đích; Luật 2.1 đang chạy, 2.2 đề xuất chờ duyệt; Quy trình; Input → Output; Dữ liệu mẫu; Kiểm tra; Trạng thái).

## 4. Quyết định đã chốt

Người dùng duyệt 17/11/2026 (1, 2) và 19/11/2026 (3, 4–9):

1. **Bỏ TF-IDF.** Biểu diễn nội dung JD chỉ dùng e5. Gỡ `build_tfidf`, `tfidf_weight` (M0.6) và bước 12_tfidf của Processing.
2. **Kỹ năng mềm và ngoại ngữ xếp riêng.** Bảng xếp hạng (2.1), kỹ năng hiếm và lộ trình tách danh sách công cụ và danh sách kỹ năng mềm, ngoại ngữ. Từ 19/11 việc tách dùng `skill_view` (K-soft = `kind` soft hoặc language), không dùng danh sách 8 slug cũ.
3. **M3 dùng K-tool + K-concept + e5 `job`** (19/11, thay quyết định "loại tin không có kỹ năng" ngày 17/11). Lý do: 643/3.916 tin không có công cụ nhưng là việc IT thật (BA, Tester, IT Manager, presales; trung vị 8 khái niệm/tin). Chỉ bỏ tin không có kỹ năng kỹ thuật nào; số tin bỏ chính xác (14 hay 1) chờ chọn ở M3.1b.
4. Kỹ năng của SD2, SD4, SD5 là **K-tool** (quyết định 1 của `06_yeu_cau_du_lieu.md`).
5. Giữ thẻ kỹ năng của sàn (quyết định 2).
6. Lead/Manager lương < Senior là **MNAR** (thỏa thuận nhiều), không phải lỗi (quyết định 3).
7. Mục tiêu lương = trung bình các cận có số (`salary_target_m`, quyết định 4).
8. `source` là biến kiểm soát của M5 (quyết định 5).
9. Không tự suy kỹ năng JD không ghi (quyết định 6): S-02 chỉ báo cáo, S-03 ngưỡng 0,60 (đề xuất M0.7, chờ duyệt).

## 5. Đầu ra và bên đọc

| File trong `mining/artifacts/` | Bước | Bên đọc |
|---|---|---|
| `sd1_<câu>.json`, `sd1_baseline_salary.json`, `sd1_demand.json` | M1 | Monitoring Insights, M5, M6 |
| `skill_association_rules.parquet`, `sd2_top_skills.json`, `sd2_rare_skills.json`, `sd2_hand_check.csv` | M2 | Monitoring, Mart, M6 |
| `job_clusters.parquet`, `cluster_family_crosstab.json` | M3 | Monitoring, Mart, M4 |
| `job_anomalies.parquet`, `sd3_anomaly_hand_check.csv` | M4 | Monitoring, Mart |
| `skill_salary_shap_values.parquet`, `salary_factor_importance.json`, `salary_estimates.parquet`, `trained_salary_rf_model.joblib` | M5 | Monitoring, M6 |
| `sd5_<nghề>.json`, `sd5_index.json` | M6 | Monitoring |
| `mining_metrics.json` | tất cả | Monitoring, spec 08: metrics từng bước, `sanity_checks`, `targets_summary`, thời gian, sha256 đầu vào |

`mining/artifacts/` không vào git. Dẫn số vào báo cáo thì ghi ngày chạy và sha256 đầu vào lấy từ `mining_metrics.json`.
