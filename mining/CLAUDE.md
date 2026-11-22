# mining/CLAUDE.md

Giai đoạn 4 (M0–M6). Đặc tả từng bước: `docs/spec/mining/`; prompt và Log: `docs/prompting/mining/`; hợp đồng chung: `docs/spec/07_mining_spec.md`; nghiệm thu: `docs/spec/08_evaluation_spec.md`. Câu hỏi của SD1–SD5 ở `docs/target/`.

Lệnh: `python -m mining.run_mining_pipeline [--only fp,cluster,…] [--dry-run] [--no-shap]`. Ghi `mining/artifacts/` (không vào git); không đụng R2, Postgres, Airflow.

## Bẫy dễ lặp lại

- **Đầu vào là Silver** (`data/preprocessing/04_normalization/silver.parquet`, `DEFAULT_TABLE`). Thiếu thì báo lỗi; không lùi về `all.parquet` hay `data/curated/` (legacy, PRE-39). `--golden` chỉ còn là bí danh của `--table`.
- **Silver và `features.parquet` không cùng thứ tự dòng.** Luôn nối theo `job_id` = `job_id_global` (`_aligned_features`), không ghép theo vị trí.
- **Ba khối kỹ năng, không trộn:** `data.skills` = K-tool (`skill__`), `data.concepts` = `concept__`, `data.soft` = `soft__`. Tiền tố `skill_` một gạch không còn hợp lệ. Cột `<khối>__other_skill` là kỹ năng hiếm đã gom, không phải kỹ năng: không đưa vào luật, xếp hạng, vector.
- **Đếm và lương lấy từ bước 10, không tính lại:** `meta.n_tools`, `n_concepts`, `n_soft`, `salary_target_m`; `meta.salary_avg_mil` = `salary_target_m`. `meta.n_skills` chỉ là số cột K-tool của ma trận (ít hơn `n_tools` ở tin có công cụ hiếm đã gom: 672 so với 643 tin "0 công cụ").
- **Cờ lương:** `meta.salary_outlier` (cờ của Silver). Tên cũ `salary_suspect` là cột của bước 03/04, không dùng trong Mining.
- **e5 khóa `job`** (mô tả + yêu cầu, không phúc lợi). Thiếu khóa thì `MiningContractError`, không lùi về `all`.
- **M3: K-Means cần `n_init` 150** (`ClusteringParams.kmeans_n_init`). Với `n_init` 10, ARI giữa 5 seed chỉ 0,73; `n_init` 50 cho 0,826 trên 3.916 tin nhưng tụt 0,79 trên 3.718 tin (22/11, L-59), 150 cho 0,826; mỗi lần dữ liệu đổi phải đo lại; đổi trọng số khối hay k thì đo lại `stability`. Trọng số tool lớn (0,35) làm tin không công cụ gom thành một cụm (L-47).
- **M5 dùng cấu hình `tool_concept`** (`SalaryParams.feature_config`, người dùng chốt 20/11). `train_salary_model` trả 4 phần tử (model, giá trị kỹ năng, metrics, `extra` có `estimates`). Chia train/test theo `company_id`; không dùng `dup_group_id`.
- **Tên kỹ năng là slug** (`aws`), không phải "AWS": so tên trong sanity hay báo cáo phải chuẩn hóa (L-56).
- **Thang cấp 0–4:** 0 = Intern/Fresher … 4 = Lead/Manager, -1 = chưa rõ (`SENIORITY_ORDER_LABELS`). S-04 từng ánh xạ lệch một bậc (sửa 20/11, M0.8).
- **M6 (`recommend.py`): luật X ⇒ Y cho cạnh Y → X** (Y là nền, học trước; người dùng chốt 20/11), chỉ dùng luật 1 ⇒ 1. Đảo lại thì javascript rơi xuống sau react. Bậc = đường **ngắn nhất** từ nền (3.B); đường dài nhất đẩy angular xuống bậc 4.
- **M4 (`anomaly.py`): Isolation Forest chỉ fit tin biết cấp** (`seniority_ord >= 0`, quyết định 1.B). Cấp −1 nằm tách riêng nên IF sẽ bắt "tin thiếu cấp" thay vì tin lạ; tin chưa rõ cấp chỉ gắn cờ qua GLOSH hoặc mã lý do cụ thể (nguồn `rule`). Ngưỡng `TOO_MANY_SKILLS`, `FRESHER_TOO_MANY_SKILLS` là phân vị tính lại mỗi lần chạy, xem `metrics.anomaly.thresholds_used`. `--only recommend` chạy riêng sẽ đọc luật và SHAP từ `mining/artifacts/` nếu có, không thì tính lại M2, M5 (chậm vài phút).
- **M1 (`bi.py`) lấy kỹ năng từ `job_skills` + `skill_view`** (slug, như tên cột ma trận vì `encoding_dictionary.json` không có `skills_map`). Không có `--job-skills` thì lùi về ma trận và ghi chú. File `sd1_*.json` không chứa thời điểm chạy để chạy lại ra cùng file.
- **`--synthetic` chỉ cho test** (`mining/synthetic.py`, schema giống Silver). Không lấy số báo cáo từ đó (L-19).
- Test ghi vào `tmp_path`; chạy xong xem `git status` (không được đổi `mining/artifacts/`, `data/`, `reports/`).
- **Nghiệm thu (22/11, L-60):** `targets_summary` chỉ chứa cổng; Silhouette/DB và R²/MAE tuyệt đối nằm ở `targets_summary.report_only`, đừng đưa lại thành cổng. Tên cụm có tiền tố "Hỗn hợp"/"Ít công cụ" (M3.8b): code đọc nghề của cụm phải dùng `dominant_job_family`, không tách từ `cluster_name`. Chạy lại mining thì chạy `python scripts/build_mining_charts.py --inject` để slide khớp số.
