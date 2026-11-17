# ĐẶC TẢ MINING (M1–M6)

> **Dự án:** VN-IT-Job-Mining. Đề tài: "Tích hợp và khai phá dữ liệu thị trường lao động phục vụ phân tích nghề nghiệp và kỹ năng trong IT".
> **Phiên bản:** 3.0.0, ngày 17/11/2026. **Trạng thái:** đã duyệt 17/11/2026 (chặng 4), kèm 3 quyết định ở mục 4.
> **Thay cho:** bản 2.0 ("Mining chỉ unsupervised", Random Forest là "phần phụ").
> **Quan hệ với tài liệu khác:** mã bước M1–M6 lấy theo [spec 03](03_data_mining_lifecycle.md) mục 3.3. Câu hỏi, phương pháp và tiêu chí của từng SD nằm ở [`docs/target/`](../target/00_de_tai.md); spec này chỉ đặc tả **code làm việc đó thế nào** và **còn thiếu gì**. Tiêu chí nghiệm thu: [spec 08](08_evaluation_spec.md). Đầu vào: bảng sạch ([spec 05](05_preprocessing_spec.md) mục 4) và đầu ra Processing ([spec 06](06_processing_spec.md)).

## 0. Cách đọc

- **Nguồn sự thật:** code `mining/` (`run_mining_pipeline.py` `STEPS`, `config.py`), rồi `mining/artifacts/mining_metrics.json` của lần chạy thật, rồi `docs/target/`.
- **Số liệu chạy thật** lấy từ `docs/issue_log.md` L-46, L-47 (11/11/2026, 4.671 tin), vì `mining/artifacts/` không có trong git và không có trên máy dùng để viết spec này.
- **Mỗi bước** viết theo khuôn: Mục đích, Code, Đầu vào, Đầu ra, Luật và tham số, Kiểm tra, Trạng thái, **Thiếu so với SD**, Việc mở.
- **Ngưỡng:** tham số đang có trong `mining/config.py` ghi đúng giá trị code. Ngưỡng nghiệm thu chưa chốt thì trỏ về PRE-36, không ghi như đã chốt.

## 1. Ba tầng và sáu bước

| Tầng | Bước | Thuật toán | SD | Code |
|---|---|---|---|---|
| BI | M1 | Đếm, tỷ lệ, bảng chéo, trung vị, tứ phân vị | SD1 | **Chưa có** (đề xuất `mining/bi.py`) |
| Không giám sát | M2 | FP-Growth, luật kết hợp | SD2 | `mining/association.py` |
| Không giám sát | M3 | K-Means, HDBSCAN, giảm chiều SVD/PCA | SD3 (3.1, 3.2) | `mining/clustering.py` |
| Không giám sát | M4 | Isolation Forest + điểm GLOSH của HDBSCAN | SD3 (3.3) | `mining/anomaly.py` |
| Train model | M5 | Chia train/test theo công ty (bước 11 cũ), Random Forest + SHAP; phương án B phân lớp khung lương | SD4 | `mining/salary_model.py` |
| Tổng hợp | M6 | Điểm ưu tiên, thứ tự học, coverage@N | SD5 | **Chưa có** (đề xuất `mining/recommend.py`) |

- **Thứ tự chạy** (đã duyệt ở spec 03 mục 7): `bi, fp, cluster, anomaly, salary, recommend`. Hiện `STEPS` chỉ có `fp, cluster, anomaly, salary`.
  - M4 chạy sau M3 vì dùng điểm GLOSH của HDBSCAN.
  - M6 chạy sau cùng vì cần kết quả của M1, M2, M5.
- **Lệnh:** `python mining/run_mining_pipeline.py [--only fp,cluster] [--dry-run] [--e5 <job_emb.npz>]`. Chỉ đọc file trên máy, ghi vào `mining/artifacts/`; không đụng R2 hay PostgreSQL. Nạp vào Postgres cho trang Insights thì dùng `scripts/load_mart_from_parquet.py`, là việc riêng.
- **`--synthetic`** chạy trên bộ dữ liệu giả `mining/synthetic.py`, ghi vào `mining/artifacts/_synthetic/`, metrics có `"synthetic": true`. **Không bao giờ dùng số từ chế độ này để báo cáo** (L-19).
- `RANDOM_STATE = 42` cho mọi thuật toán.

## 2. Đầu vào chung

| Đầu vào | Đường dẫn | Dùng ở |
|---|---|---|
| Bảng sạch | `data/preprocessing/04_normalization/all.parquet` (`mining/config.py` đang trỏ `DEFAULT_GOLDEN` về `data/curated/curated_flat_golden_jobs.parquet`, lấy bảng 04 làm dự phòng; đổi theo PRE-39) | M1–M6 |
| Ma trận đặc trưng | `data/processing/10_features/features.parquet`, `encoding_dictionary.json` | M2 (cột `skill__*`), M3, M4, M5 |
| Vector e5 | `data/processing/12_e5/job_emb.npz` (thiếu thì M3 chạy không có e5) | M3 |
| Kỹ năng theo tin | `data/processing/08_skills/job_skills.parquet` | dự kiến M1, M6 (cần mức bắt buộc hay ưu tiên) |

- `mining/data_io.py` (`load_mining_data`, `prepare_mining_data`) đổi tên cột về tên logic qua `COLUMN_ALIASES`, rồi kiểm hợp đồng cột (`MiningContractError`). Đổi tên cột ở bước trước thì chỉ sửa `COLUMN_ALIASES`.
- **Nguồn kỹ năng của Mining là cột `skill__*` của bước 10** (bộ 230 kỹ năng, đã qua `min_df`). Không trộn với `skills_std` của bảng 04 (PRE-40). Bỏ `SKILL_EXCLUDE_COLUMNS` (`skill__other_skill`…).
- Cấp bậc lấy theo thứ tự ưu tiên `seniority_ord` (bước 10) → nhãn chữ → `seniority_level` (bảng 04), cùng thang 0–4.
- Lương tính bằng triệu VNĐ/tháng.

## 3. Các bước

### 3.1. M1: BI (SD1)

| Mục | Nội dung |
|---|---|
| Mục đích | Trả lời câu 1.1–1.7 của SD1 bằng số đếm. Đây cũng là baseline cho M5 (trung vị lương cấp × nghề) và nguồn `demand(k)` cho M6 |
| Code | **Chưa có.** Đề xuất `mining/bi.py`, mỗi câu một hàm |
| Đầu vào | Bảng 04; `10_features`; `08_skills` cho câu 1.5 (số kỹ năng của tin người mới) |
| Đầu ra | `mining/artifacts/sd1_<câu>.json`, mỗi bảng có kèm `n` và độ phủ. Monitoring chỉ đọc các file này, không tự tính |
| Luật | Theo `docs/target/01_sd1_buc_tranh_thi_truong.md` mục 4: lương dùng trung vị và tứ phân vị trên tin có lương và không bị gắn cờ ngoại lai; ô có n < 30 ghi "ít dữ liệu" (PRE-36); câu 1.7 theo `posted_month`, tách theo `posted_month_source`, chỉ so cơ cấu; lương ước tính từ M5 chỉ hiện ở cột riêng có nhãn "ước tính" |
| Kiểm tra | Tổng mỗi bảng khớp số tin của bảng 04; tỷ lệ cộng lại đủ 100%; chạy lại ra cùng số |
| Trạng thái | Chưa có code. Trang Insights hiện đọc Postgres (`curated_jobs`) do `scripts/load_mart_from_parquet.py` nạp |
| Việc mở | MINE-7, PRE-37 (`posted_month` chưa có, nên câu 1.7 chưa làm được), PRE-38 (tỉnh) |

### 3.2. M2: Luật kết hợp kỹ năng (SD2)

| Mục | Nội dung |
|---|---|
| Mục đích | SD2: top kỹ năng theo nghề (2.1), gói kỹ năng (2.2), khác biệt giữa nghề và cấp (2.3), kỹ năng hiếm (2.4). Luật của từng nghề còn là đầu vào cho M6 |
| Code | `mining/association.py`: `mine_rules`, `mine_stratified_rules`, `format_rules`, `find_skill`, `pair_stats` (mlxtend FP-Growth) |
| Đầu vào | Ma trận `skill__*` (một tin là một giỏ), `job_family` |
| Đầu ra | `mining/artifacts/skill_association_rules.parquet` (cột `job_family_scope`, vế trái, vế phải, support, confidence, lift, conviction, cosine); `mining_metrics.json` khối `association` |

**Luật và tham số** (`AssociationParams`):

| Tham số | Giá trị | Ý nghĩa |
|---|---|---|
| `macro_min_support` | 0,05 | Phạm vi toàn bộ tin (`ALL`) |
| `micro_min_support` | 0,02 | Phạm vi từng nghề |
| `min_confidence` | 0,60 | |
| `min_lift` | 1,20 | |
| `max_len` | 3 | Luật tối đa 3 kỹ năng (A, B ⇒ C) |
| `min_group_size` | 100 | Nghề có ít hơn 100 tin thì không chạy vi mô, ghi `skipped` |

- Tin không có kỹ năng nào không được tính là giỏ, vì sẽ làm loãng support. Số tin bị bỏ ghi trong metrics.
- Mỗi luật có 4 chỉ số: support, confidence, lift, conviction, kèm cosine.

| Mục | Nội dung |
|---|---|
| Kiểm tra | Sanity S-01, S-02, S-03 (`mining/sanity.py`, spec 08). Mọi luật báo cáo có lift ≥ 1,20 và đủ support của phạm vi. Kiểm tay 20 luật mạnh nhất. Chạy lại với support thấp hơn và cao hơn một bậc: luật mạnh nhất không đổi lớn |
| Trạng thái | Có code, đã chạy thật 11/11: 13.514 luật. S-02 (Flutter ⇒ Dart, conf 0,375) và S-03 (React ⇒ JS/TS, conf 0,654) **fail** |
| Thiếu so với SD | **2.1:** chưa có bảng top 15 kỹ năng theo nghề (đề xuất: tính ở M1, dùng lại ở M2). **2.3:** chỉ chia theo nghề, chưa chia theo cấp bậc hay nghề × cấp. **2.4:** chưa có code tìm kỹ năng hiếm. Chưa có lần chạy đổi ngưỡng support để kiểm độ ổn định. Kỹ năng mềm và ngoại ngữ (communication, english, teamwork) đang đứng đầu; chưa tách nhóm riêng khi xếp hạng như quyết định 2 (mục 4) |
| Việc mở | MINE-1 (sanity fail), MINE-7, PRE-33 (F1 kỹ năng 0,27), PRE-36 (ngưỡng kỹ năng hiếm), PRE-40 (chưa phân biệt bắt buộc và ưu tiên) |

### 3.3. M3: Phân cụm việc làm (SD3, câu 3.1 và 3.2)

| Mục | Nội dung |
|---|---|
| Mục đích | Tìm nhóm việc từ nội dung JD và kỹ năng, không dùng `job_family`; sau đó so với `job_family` để tìm nghề lai, nghề ngách, tin có vẻ bị gán sai |
| Code | `mining/clustering.py`: `build_vector_space`, `reduce_svd`, `scan_k`, `choose_k`, `fit_labels`, `run_hdbscan`, `profile_clusters`, `cluster_jobs` |
| Đầu vào | Ma trận `skill__*`, `job_emb.npz` (e5), `job_family` (chỉ để so sánh), các cột mô tả (cấp, lương, tiêu đề) |
| Đầu ra | `mining/artifacts/job_clusters.parquet` (`job_id`, `cluster_id`, điểm GLOSH, `pca_x`, `pca_y`, `pca_z`); `mining_metrics.json` khối `clustering` (bảng quét k, Silhouette, Davies–Bouldin, ARI, NMI, hồ sơ cụm, kết quả không dùng e5) |

**Luật và tham số** (`ClusteringParams`):

- **Tập tin đưa vào phân cụm:** chỉ tin có ít nhất một kỹ năng trích được từ JD (bước 08, cột `skill__*`). Tin không có kỹ năng nào bị loại khỏi M3, nên không có điểm GLOSH; M4 vẫn chạy Isolation Forest trên mọi tin. Số tin bị loại ghi trong metrics `clustering.n_dropped_no_skill` (quyết định 3, mục 4). Lần chạy 11/11 có 292 tin như vậy.
- **Không gian vector:** khối kỹ năng (trọng số 0,5) ghép khối e5 (`e5_weight` 0,5), chuẩn hóa L2. **Không dùng TF-IDF** (quyết định 1, mục 4): code còn `build_tfidf` và `tfidf_weight` = 0 (tắt từ L-47), phải gỡ.
- **Giảm chiều:** TruncatedSVD giữ khoảng 80% phương sai (`svd_variance_target`), tối đa 60 thành phần, rồi chuẩn hóa L2 lại. Silhouette và Davies–Bouldin đo trên chính không gian này.
- **K-Means:** `k_fixed` = 10 (người dùng chốt 11/11). Vẫn quét k = 2–20 để báo Elbow và Silhouette. Có thể đổi thuật toán sang `agglomerative` hoặc `gmm`.
- **HDBSCAN:** `min_cluster_size` = 25. Tin có điểm GLOSH trên phân vị 97% (`glosh_outlier_quantile`) bị gắn cờ ngoại lai. Nếu không có thư viện `hdbscan` thì dùng `sklearn.cluster.HDBSCAN` với `1 - probabilities_`, và ghi rõ điều này trong metrics.
- **PCA 3 thành phần** trên không gian gốc (trước SVD), để vẽ 2D và 3D.
- **Hồ sơ cụm:** kỹ năng đặc trưng (theo lift so với toàn bộ), nghề chiếm đa số, lương trung vị. Mỗi cụm lấy 8 kỹ năng.
- ARI và NMI so với `job_family` chỉ tính trên tin khác `Other`.

| Mục | Nội dung |
|---|---|
| Kiểm tra | Silhouette, Davies–Bouldin, độ ổn định qua 5 seed, kích thước cụm nhỏ nhất, trung vị số kỹ năng theo cụm (spec 08) |
| Trạng thái | Có code, đã chạy thật 11/11 (L-47): k = 10, Silhouette 0,1015, Davies–Bouldin 2,49; ARI 0,071 và NMI 0,144 trên 3.964 tin khác Other. Không dùng e5: Silhouette 0,1055, ARI 0,096. **Cụm 1 chứa 292/293 tin không có kỹ năng; cụm 9 là cụm nhiều kỹ năng (trung vị 15)**, nghĩa là phân cụm một phần đang tách theo số kỹ năng |
| Thiếu so với SD | Chưa chạy 5 seed để đo ARI ổn định. Chưa kiểm trung vị số kỹ năng theo cụm như một tiêu chí. Chưa xuất bảng chéo cụm × `job_family` thành artifact riêng. Chưa có luật đánh dấu nghề lai, nghề ngách, tin có vẻ bị gán sai (3.2). Chưa lọc tin không có kỹ năng trước khi phân cụm. Chưa gỡ `build_tfidf` |
| Việc mở | MINE-1, MINE-7 |

### 3.4. M4: Tin "khác hoặc mới" (SD3, câu 3.3)

| Mục | Nội dung |
|---|---|
| Mục đích | Tìm tin khác mặt bằng (đòi hỏi bất thường so với cấp bậc, lương lệch) hoặc mới (tổ hợp nội dung chưa có nhóm), kèm lý do đọc được |
| Code | `mining/anomaly.py`: `build_anomaly_space`, `_reason_codes`, `detect_anomalies` |
| Đầu vào | Cột mô tả của tin (kinh nghiệm, lương, cấp, số kỹ năng); điểm và cờ GLOSH từ M3 |
| Đầu ra | `mining/artifacts/job_anomalies.parquet` (cột theo `ANOMALY_COLUMNS`: `job_id`, `anomaly_score`, `reason_code`, `isolation_score`, `glosh_outlier_score`…); metrics khối `anomaly` |

**Luật và tham số** (`AnomalyParams`):

- **Isolation Forest** (300 cây, `contamination` = 0,03) trên: kinh nghiệm, log lương, log lương lệch so với trung vị cùng cấp, số kỹ năng, số kỹ năng / (cấp + 1), cấp bậc. Khoảng 55% tin không có lương; các tin này **không được bù giá trị**, mà điền hằng số kèm cờ `salary__missing` để cây vẫn tách được.
- `anomaly_score` = max(điểm Isolation Forest, điểm GLOSH × cờ GLOSH).
- **Mã lý do**, xét theo thứ tự; luật sau ghi đè luật trước, nên luật cụ thể nhất đứng cuối:

  | Mã | Điều kiện |
  |---|---|
  | `ISOLATION_GENERIC` | Mặc định |
  | `TOO_MANY_SKILLS` | Số kỹ năng trên phân vị 99% |
  | `SALARY_TOO_LOW_FOR_LEVEL`, `SALARY_TOO_HIGH_FOR_LEVEL` | Lương < 1/3 hoặc > 3 lần trung vị cùng cấp (`salary_ratio_limit`) |
  | `EXP_SENIORITY_MISMATCH` | Intern/Fresher hoặc Junior mà đòi ≥ 5 năm kinh nghiệm |
  | `FRESHER_TOO_MANY_SKILLS` | Intern/Fresher hoặc Junior mà đòi > 15 kỹ năng |

| Mục | Nội dung |
|---|---|
| Kiểm tra | Kiểm tay 20 tin ngẫu nhiên: tỷ lệ tin đúng là khác hoặc mới thật, so với tin chỉ do parse lỗi (spec 08) |
| Trạng thái | Có code, đã chạy thật 11/11: 282 tin bị gắn cờ (6,04%), gồm Isolation Forest 3% và GLOSH |
| Thiếu so với SD | **Chưa chia hai loại "mới" và "khác"** như SD3 mục 4: tin HDBSCAN để riêng nhưng các trường bình thường là "mới"; tin có mã lý do về kỹ năng, kinh nghiệm hoặc lương là "khác". Hiện chỉ có `reason_code`; tin GLOSH không có lý do cụ thể đang mang `ISOLATION_GENERIC`. Chưa có quy trình kiểm tay 20 tin |
| Việc mở | MINE-7, PRE-36 |

### 3.5. M5: Giá trị kỹ năng và lương ước tính (SD4)

| Mục | Nội dung |
|---|---|
| Mục đích | SD4: yếu tố nào ảnh hưởng lương (4.1), mỗi kỹ năng cộng bao nhiêu triệu (4.2), model đúng tới đâu (4.3), ước tính lương cho tin thỏa thuận (4.4). Giá trị kỹ năng còn là `premium(k)` cho M6 |
| Code | `mining/salary_model.py`: `select_training_subset`, `build_salary_features`, `assert_no_leakage`, `_groups`, `_cv_scores`, `train_salary_model`, `skill_values_from_shap` |
| Đầu vào | Cột mô tả của tin; ma trận `skill__*` |
| Đầu ra | `mining/artifacts/skill_salary_shap_values.parquet`, `trained_salary_rf_model.joblib`; metrics khối `salary` |

**Luật và tham số** (`SalaryParams`):

- **Tập có lương:** lương > 0, không thỏa thuận, không `salary_suspect`, nằm trong khoảng lương hợp lệ; loại thêm tin lệch quá 3 lần so với trung vị cùng cấp (`level_ratio_limit` = 3,0). Số tin bị loại theo từng lý do ghi trong metrics.
- **Mục tiêu:** `y = log(1 + lương trung bình)`, đơn vị triệu VNĐ/tháng.
- **Đặc trưng:** `skill__*`, `seniority_ord`, `exp_min_years` (thiếu thì -1, kèm cờ `__missing`), nhóm địa điểm (`LOCATION_FEATURE_GROUPS`), one-hot `job_family`. `assert_no_leakage` chặn mọi cột mang thông tin lương. Theo spec 06 mục 2.2, `salary_bin_*`, `salary_mid`, `salary_range_ratio` không được đưa vào.
- **Chia dữ liệu** (bước 11 cũ): giữ 20% làm tập test (`test_size`), CV 5 phần trên phần train. **SD4 yêu cầu chia theo công ty** (`company_key`), phân tầng theo cấp bậc.
- **Random Forest:** chọn tham số trong 4 bộ (`param_grid`, 300 cây) bằng CV.
- **SHAP:** TreeExplainer trên model fit lại bằng toàn bộ tập có lương, tối đa 3.000 dòng. Giá trị của kỹ năng i là trung bình φᵢ **trên các tin có kỹ năng i**; nếu lấy trung bình trên mọi tin thì giá trị bị kéo về gần 0, vì ma trận thưa khoảng 97%. Quy đổi ra tiền: Δ = lương nền × (e^φ − 1), với lương nền = expm1(E[f(x)]). Chỉ định giá kỹ năng có ≥ 30 tin trong tập có lương (`min_skill_sample`).
- **Ngưỡng hiện có trong code:** R² ≥ 0,60, MAE ≤ 4,5 triệu, độ lệch chuẩn R² qua CV ≤ 0,05. Ngưỡng nghiệm thu của SD4 thì theo PRE-36.

| Mục | Nội dung |
|---|---|
| Kiểm tra | So với baseline, CV theo công ty, sanity S-04, S-05, S-06, mức đóng góp của cấp bậc tăng dần, chiều của giá trị kỹ năng khớp chênh lệch trung vị thô ở M1 (spec 08) |
| Trạng thái | Có code, **chưa chạy trên dữ liệu thật** (MINE-1). Sanity về lương chạy 11/11: S-04 (lương Senior < Middle) và S-06 (tỷ lệ lương HN/HCM) **fail** |
| Thiếu so với SD | **Nhóm khi chia dữ liệu:** `_groups` dùng `dup_group_id` (nhóm tin trùng), không phải `company_key`; chưa phân tầng theo cấp bậc. **Baseline:** code so với model "cấp bậc + kinh nghiệm", SD4 yêu cầu trung vị lương theo cấp × nghề. **Phương án B** (phân lớp 4 khung lương, macro-F1) chưa có. **Câu 4.4** (`salary_estimated_vnd`, `salary_is_estimated`, khoảng P10–P90 từ các cây) chưa có. Chưa có MAE theo nghề, cấp, nguồn. Chưa so phân bố giữa tập có lương và tập thỏa thuận. Chưa xếp hạng yếu tố (4.1) |
| Việc mở | MINE-1, MINE-5 (Mart chưa có bảng SHAP), MINE-6 (SHAP không phải nhân quả), MINE-7, PRE-35 (lương phủ 40–45%), PRE-36 |

### 3.6. M6: Lộ trình học cho người mới (SD5)

| Mục | Nội dung |
|---|---|
| Mục đích | SD5: với mỗi nghề có ≥ 30 tin cho người mới, xếp hạng kỹ năng nên học (5.1), thứ tự học (5.2), kỹ năng chưa nên đầu tư sớm (5.3), độ phủ coverage@N (5.4) |
| Code | **Chưa có.** Đề xuất `mining/recommend.py`, dùng lại `mine_stratified_rules` (M2) và `skill_values_from_shap` (M5) |
| Đầu vào | `demand(k)` từ M1 (tin Intern/Fresher và Junior của nghề), luật của nghề từ M2, `premium(k)` từ M5, tỷ lệ kỹ năng ở tin Senior/Lead |
| Đầu ra | `mining/artifacts/sd5_<nghề>.json`: danh sách ưu tiên, lộ trình theo bậc kèm luật dẫn chứng, danh sách để sau, coverage@5/10/15 |
| Luật | Kỹ năng kỹ thuật và kỹ năng mềm, ngoại ngữ xếp thành hai danh sách riêng (quyết định 2, mục 4). Theo `docs/target/05_sd5_lo_trinh_hoc.md` mục 4: `điểm(k) = demand(k) × (1 + premium_chuẩn_hóa(k))`; kỹ năng M5 không định giá được thì `premium` = 0; bậc 1 là kỹ năng nền không nằm ở vế sau của luật mạnh nào (confidence ≥ 0,60 và lift ≥ 1,20); B đứng sau A nếu có luật mạnh A ⇒ B. Ngưỡng 30 tin, 5%, gấp 3 lần, 70%, 10 điểm phần trăm theo PRE-36 |
| Kiểm tra | coverage@10 cao hơn baseline "top 10 kỹ năng toàn thị trường"; tách tập 80/20; mọi kỹ năng truy được về `demand`, luật, giá trị SHAP; người làm nghề đọc lộ trình của 2 nghề (spec 08) |
| Trạng thái | Chưa có code |
| Thiếu so với SD | Toàn bộ. Phụ thuộc M1, M2 (luật theo nghề trên tin người mới), M5 |
| Việc mở | MINE-7, PRE-35 (số tin người mới ít; khoảng 317 tin itviec "0,8 năm"), PRE-40 (chưa phân biệt bắt buộc và ưu tiên) |

## 4. Quyết định đã chốt (người dùng duyệt 17/11/2026)

1. **Bỏ TF-IDF.** Biểu diễn nội dung JD chỉ dùng e5. Gỡ `build_tfidf` và `tfidf_weight` khỏi `mining/clustering.py` và `ClusteringParams`; bỏ luôn bước 12_tfidf của Processing (spec 06 mục 3.5). Không làm phép so TF-IDF với e5.
2. **Kỹ năng mềm và ngoại ngữ ở M1, M2 và M6.** Vẫn giữ trong ma trận `skill__*` (M2 vẫn tìm luật có các kỹ năng này, M5 vẫn định giá). Nhưng bảng xếp hạng (top 15 theo nghề, kỹ năng hiếm) và lộ trình học tách thành **hai danh sách**: kỹ năng kỹ thuật và kỹ năng mềm, ngoại ngữ. Nhóm sau gồm 8 slug: `communication`, `teamwork`, `problem_solving`, `logical_thinking`, `time_management`, `presentation`, `english`, `japanese`. Không lấy nguyên nhóm `methodologies_softskills_data` của `skills_taxonomy_230.json`, vì nhóm này lẫn cả Agile, BI, machine learning. Việc code: thêm trường đánh dấu (ví dụ `"soft": true`) cho 8 slug trong taxonomy (MINE-7). Nhờ vậy communication, english, teamwork không chiếm chỗ của kỹ năng kỹ thuật.
3. **Tin không có kỹ năng ở M3.** Tin nào trích từ JD (bước 08) mà không ra kỹ năng nào thì **loại khỏi phân cụm** và ghi số tin bị loại. Chỉ loại sau khi đã trích từ JD; không loại chỉ vì nguồn không có thẻ kỹ năng. Lần chạy 11/11 có 292 tin như vậy (gom gần hết vào cụm 1). Con số sẽ đổi khi bước 08 tốt hơn (PRE-33: F1 kỹ năng 0,27; chưa có alias ngắn).

## 5. Đầu ra và bên đọc

| File trong `mining/artifacts/` | Bước | Bên đọc |
|---|---|---|
| `sd1_*.json` (đề xuất) | M1 | Monitoring Insights, M5 (baseline), M6 |
| `skill_association_rules.parquet` | M2 | Monitoring, Mart (`load_mart_from_parquet.py`), M6 |
| `job_clusters.parquet` | M3 | Monitoring, Mart, M4 |
| `job_anomalies.parquet` | M4 | Monitoring, Mart |
| `skill_salary_shap_values.parquet`, `trained_salary_rf_model.joblib` | M5 | Monitoring, M6 |
| `sd5_*.json` (đề xuất) | M6 | Monitoring |
| `mining_metrics.json` | tất cả | Monitoring, spec 08. Gồm metrics từng bước, `sanity_checks`, `targets_summary`, thời gian chạy, sha256 của file đầu vào |

`mining/artifacts/` không đưa vào git. Muốn dẫn số vào báo cáo thì ghi kèm ngày chạy và sha256 đầu vào lấy từ `mining_metrics.json`.
