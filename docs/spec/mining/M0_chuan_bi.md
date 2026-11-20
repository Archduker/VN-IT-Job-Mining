# M0: Chuẩn bị đầu vào Mining

> Code: `mining/config.py` (đường dẫn, `COLUMN_ALIASES`, `SKILL_PREFIXES`, `*Params`), `mining/data_io.py` (`build_meta`, `skills_from_features`, `prepare_mining_data`, `load_e5`, `load_mining_data`, `MiningData`), `mining/run_mining_pipeline.py` (`STEPS`, `run_pipeline`, `_targets_summary`), `mining/sanity.py` (`run_sanity_checks`).
> Lệnh: `python -m mining.run_mining_pipeline --only <bước> --dry-run`. M0 không có artifact riêng: nó là phần nạp dữ liệu mà mọi bước dùng.
> Trạng thái: **bản nháp 20/11, chờ duyệt.**

## 1. Mục đích

Mọi bước M1–M6 đọc **cùng một bộ dữ liệu**, đúng định nghĩa đã chốt ở Processing 19/11:

- meta từ **Silver** (người dùng chốt: "đồng nhất phần silver cho processing và mining");
- ba ma trận kỹ năng tách theo `skill_view` (K-tool, K-concept, K-soft);
- vector e5 khóa `job` (mô tả + yêu cầu, không phúc lợi).

Tiêu chí: **consistency** (một định nghĩa kỹ năng, một bảng đầu vào), **accuracy** (nối theo id, không theo thứ tự dòng), tái lập được (sha256 đầu vào trong metrics).

## 2. Luật

### 2.1. Đang chạy (code hiện tại, đo 20/11)

| Mã | Luật hiện tại | Hệ quả trên dữ liệu 19/11 |
|---|---|---|
| M0.1 | `DEFAULT_GOLDEN` = `data/curated/curated_flat_golden_jobs.parquet`; thiếu thì dùng `FALLBACK_GOLDEN` = bảng 04 `all.parquet` | Thư mục `data/curated/` không còn; code đang đọc `all.parquet` (93 cột), không đọc Silver |
| M0.2 | `COLUMN_ALIASES` chỉ có tên cột của bảng 04 / golden cũ (`job_title_clean`, `salary_min_vnd_capped`, `is_negotiable`, `salary_suspect`, `tinh_chinh`, `dup_group_id`…) | Silver đặt tên khác (`title`, `salary_min`, `salary_negotiable`, `salary_outlier`, `province`, `company_id`, `source`); đọc Silver bây giờ sẽ thiếu cột |
| M0.3 | `SKILL_PREFIXES = ("skill__", "skill_")`; bỏ `skill__other_skill` | Lấy đúng 290 cột K-tool. `concept__`, `soft__` không bị nuốt (không khớp `skill_`), nhưng cũng **không được nạp** |
| M0.4 | `load_e5` đọc khóa `all` | Vector có cả phúc lợi; SD3 cần khóa `job` (12_e5 đã có từ 19/11) |
| M0.5 | `STEPS = ("fp", "cluster", "anomaly", "salary")` | Không có `bi`, `recommend` |
| M0.6 | `ClusteringParams.tfidf_weight` = 0, `tfidf_max_features`; `build_tfidf` còn trong `clustering.py` | Code chết (spec 07 quyết định 1) |
| M0.7 | Sanity S-02: Flutter ⇒ Dart conf ≥ 0,90; S-03: React ⇒ JS/TS conf ≥ 0,80 | 20/11: S-02 0,394 fail (n = 66), S-03 0,671 fail (n = 313), S-01 0,961 pass |
| M0.8 | **S-04 ánh xạ cấp lệch một bậc**: `levels = {1: "Fresher", 2: "Junior", 3: "Middle", 4: "Senior"}` trong khi thang là 0 = Intern/Fresher … 4 = Lead/Manager | Báo "Fresher=15,5 < Junior=22,86 < Middle=38,1 < Senior=30,0 → fail", thật ra là Junior, Middle, Senior, Lead. Tính đúng trên Silver (lương có, không ngoại lai): Intern/Fresher 10,0 (n 291) < Junior 15,5 (339) < Middle 22,5 (552) < Senior 37,5 (140) → **pass**; Lead/Manager 30,0 (260) < Senior |

### 2.2. Đề xuất, chờ duyệt

| Mã | Đề xuất | Lý do |
|---|---|---|
| M0.1 | `DEFAULT_TABLE` = `data/preprocessing/04_normalization/silver.parquet`. Bỏ `DEFAULT_GOLDEN`, `FALLBACK_GOLDEN`; thiếu Silver thì báo lỗi, không lùi về bảng khác. Cờ CLI `--golden` đổi tên `--table` (giữ `--golden` làm bí danh) | PRE-39; một đầu vào duy nhất |
| M0.2 | `COLUMN_ALIASES` thêm tên Silver lên đầu danh sách: `job_title`←`title`; `salary_min`/`salary_max` (đã có); `is_negotiable`←`salary_negotiable`; `salary_suspect`←`salary_outlier`; `province`←`province`; `company_id` (mới) ←`company_id`; `source_platform`←`source`; `seniority_inferred` (mới); `posted_month` (mới); `work_mode`, `employment_type`, `language`, `benefits` (mới, cho M1); `jd_text`←`description`, `jd_requirements`←`requirements`. Bỏ `dup_group_id` khỏi hợp đồng (Silver đã khử trùng; M5 chia theo công ty) | Silver là bảng sạch duy nhất |
| M0.3 | `MiningData` có ba ma trận: `skills` (`skill__*`, K-tool), `concepts` (`concept__*`), `soft` (`soft__*`), cùng thứ tự dòng với `meta`. `SKILL_PREFIXES = ("skill__",)`. Bỏ cả ba cột `<khối>__other_skill`. `meta` thêm `n_tools`, `n_concepts`, `n_soft`, `salary_target_m` lấy thẳng từ `features.parquet` (không tính lại) | Một định nghĩa kỹ năng (`skill_view`); `n_skills` cũ chỉ đếm 290 cột nên lệch với `n_tools` của bước 10 (672 so với 643 tin "0 công cụ") |
| M0.4 | `load_e5` đọc khóa `job`; thiếu khóa `job` hoặc thiếu tin thì `MiningContractError` | SD3 không lẫn phúc lợi |
| M0.5 | `STEPS = ("bi", "fp", "cluster", "anomaly", "salary", "recommend")`. `--only recommend` khi chưa có artifact của M1, M2, M5 thì tự chạy các bước đó trong bộ nhớ (không ghi) | Chuỗi đã duyệt ở spec 03 mục 7 |
| M0.6 | Gỡ `build_tfidf`, `tfidf_weight`, `tfidf_max_features`, `n_tfidf_features` | Spec 07 quyết định 1 |
| M0.7a | **S-02 thành mục báo cáo, không phải cổng**: vẫn tính confidence Flutter ⇒ Dart, `status = "info"`, không tính vào `all_passed` | Quyết định 6 (19/11): không tự suy kỹ năng JD không ghi; nhiều JD Flutter không viết "Dart". Con số đo độ đầy đủ của JD, không đo lỗi trích |
| M0.7b | **S-03 ngưỡng 0,60** (thay 0,80) | T2 (19/11) = 0,67 là mức K-tool đo được trên dữ liệu thật; 0,80 trái quyết định 6 |
| M0.8 | Sửa S-04: dùng `SENIORITY_ORDER_LABELS` đúng thang 0–4, so Intern/Fresher < Junior < Middle < Senior. Lead/Manager **không nằm trong chuỗi**, ghi riêng kèm tỷ lệ thỏa thuận theo cấp (MNAR, quyết định 3) | Lỗi code; Lead < Senior là do lương Lead công bố ít (58% thỏa thuận), không phải lỗi dữ liệu |
| M0.9 | S-04 và S-06 tính trên `salary_target_m` của bước 10 và cờ `salary_outlier` của Silver, không tự tính lại trung bình hai cận | Một định nghĩa mục tiêu lương (quyết định 4) |

S-01, S-05, S-06 giữ nguyên ngưỡng.

## 3. Quy trình xử lý (sau khi sửa)

1. Đọc Silver; kiểm có đủ cột hợp đồng (bảng ở mục 4); `job_id` không trùng.
2. `build_meta`: đổi tên cột về tên logic qua `COLUMN_ALIASES`; cấp bậc lấy `seniority` (nhãn chữ) → `seniority_ord` 0–4, null → -1; nhóm tỉnh `location_group`.
3. Đọc `features.parquet`; nối theo `job_id_global` = `job_id`; thiếu tin nào thì báo lỗi.
4. Tách ba ma trận theo tiền tố, bỏ `__other_skill`; kiểm chỉ 0/1, không NaN. Gắn `n_tools`, `n_concepts`, `n_soft`, `salary_target_m` vào `meta`.
5. Đọc `job_emb.npz` khóa `job`, xếp theo `job_id`.
6. Ghi `row_log`, `notes`, sha256 của 4 file đầu vào vào metrics.
7. `run_pipeline` chạy các bước theo `STEPS`; cuối cùng `run_sanity_checks` và `_targets_summary`.

## 4. Input → Output

| Đầu vào | Cột / khóa dùng |
|---|---|
| `silver.parquet` (3.916 × 26) | `job_id`, `source`, `title`, `job_family`, `seniority`, `seniority_inferred`, `exp_min_years`, `exp_inferred`, `salary_min`, `salary_max`, `salary_negotiable`, `salary_outlier`, `province`, `work_mode`, `employment_type`, `company_id`, `benefits`, `description`, `requirements`, `language`, `posted_month` |
| `features.parquet` (3.916 × 994) | `job_id_global`, `skill__*` (290 + other), `concept__*` (561 + other), `soft__*` (62 + other), `n_tools`, `n_concepts`, `n_soft`, `salary_target_m`, `fam__*`, `src__*`, `tinh__*`, `seniority_ord`, `exp_*` |
| `encoding_dictionary.json` | tên hiển thị kỹ năng |
| `job_emb.npz` | `ids`, `job` (3.916 × 768) |

Đầu ra: đối tượng `MiningData` (`meta`, `skills`, `concepts`, `soft`, `e5`, `row_log`, `notes`); khối `data` trong `mining_metrics.json` (số tin, số cột từng khối, độ thưa, cột đã ánh xạ, sha256).

## 5. Dữ liệu mẫu

Điền sau lần chạy thật của M0.

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Cách đo | Ngưỡng |
|---|---|---|
| Đọc đúng bảng | `metrics.data.table_path` kết thúc bằng `silver.parquet` | bắt buộc |
| Đủ tin | `n_jobs` = 3.916 = số dòng Silver = số dòng features | bắt buộc |
| Ba khối | Số cột `skills` / `concepts` / `soft` = 290 / 561 / 62 (không có `other_skill`) | bắt buộc |
| Khối không lẫn nhau | Mọi cột `skills` là K-tool theo `skill_view`; không cột `concept__` nào trong `skills` | test |
| `n_tools` khớp | `meta.n_tools` = cột `n_tools` của bước 10 cho mọi tin | bắt buộc |
| e5 | shape (3.916, 768), khóa `job`; thiếu khóa thì lỗi | test |
| Sanity | S-01 pass; S-02 `info`; S-03 ≥ 0,60; S-04 đơn điệu 4 cấp (Lead ghi riêng); S-06 pass | chờ duyệt M0.7, M0.8 |
| Test | `pytest tests/unit/test_mining_data_io.py tests/unit/test_mining_sanity.py tests/unit/test_mining_pipeline.py` | xanh; `git status` không đổi `data/`, `reports/` |

**Kết quả dry-run 20/11 (code cũ):** đọc `all.parquet`; 3.916 tin; 290 cột kỹ năng, độ thưa 0,9798; e5 (3.916, 768) từ khóa `all`; sanity 2 pass (S-01, S-06) / 3 fail (S-02, S-03, S-04) / 1 bỏ qua (S-05).

## 7. Trạng thái, chỗ thiếu, việc mở

- Chờ duyệt M0.1–M0.9.
- PRE-39 (bảng legacy), MINE-1 (sanity fail), MINE-7 (code chưa theo SD).
- `scripts/load_mart_from_parquet.py` vẫn mặc định `--curated-path` legacy: không thuộc M0, ghi ở PRE-39.
- Viết `mining/CLAUDE.md` (bẫy: ba khối kỹ năng, khóa e5 `job`, Silver là đầu vào, nối theo id, synthetic không báo cáo).
