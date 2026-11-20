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
- **Thang cấp 0–4:** 0 = Intern/Fresher … 4 = Lead/Manager, -1 = chưa rõ (`SENIORITY_ORDER_LABELS`). S-04 từng ánh xạ lệch một bậc (sửa 20/11, M0.8).
- **`recommend` có trong `STEPS` nhưng chưa có code** (`NOT_BUILT`): `--only recommend` trả mã 2. Gỡ khỏi `NOT_BUILT` khi làm M6.
- **M1 (`bi.py`) lấy kỹ năng từ `job_skills` + `skill_view`** (slug, như tên cột ma trận vì `encoding_dictionary.json` không có `skills_map`). Không có `--job-skills` thì lùi về ma trận và ghi chú. File `sd1_*.json` không chứa thời điểm chạy để chạy lại ra cùng file.
- **`--synthetic` chỉ cho test** (`mining/synthetic.py`, schema giống Silver). Không lấy số báo cáo từ đó (L-19).
- Test ghi vào `tmp_path`; chạy xong xem `git status` (không được đổi `mining/artifacts/`, `data/`, `reports/`).
