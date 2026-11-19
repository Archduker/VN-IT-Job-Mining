# preprocessing/CLAUDE.md

Ngữ cảnh khi làm việc với giai đoạn **Pre-processing** (bước 00–04). Đặc tả chính thức: `docs/spec/05_preprocessing_spec.md` (hợp đồng chung, bảng Silver) và `docs/spec/preprocessing/<bước>.md` (luật, quy trình, input → output, dữ liệu mẫu của từng bước). Prompt làm từng bước: `docs/prompting/preprocessing/`. Mã bước và vị trí của bước trong quy trình: `docs/spec/03_data_mining_lifecycle.md` mục 3.1. Đọc mục tiêu SD1–SD5 ở `docs/target/` trước khi đổi luật, vì mọi SD đều đọc bảng sạch của bước 04.

## Chuỗi bước

Driver: `python scripts/run_preprocessing.py --step <bước>|all --source <nguồn>|all [--dry-run] [--translate]`. Mỗi bước là `preprocessing/<thư mục>/run.py` có `run(sources, dry_run)`.

| Bước | Thư mục | Việc |
|---|---|---|
| 00 profiling | `scripts/profile_sources.py` | Đo trước và sau làm sạch (chỉ đọc) |
| 01 clean | `clean/`, `common/it_filter.py`, `common/raw_reader.py` | Snapshot mới nhất, lọc IT 3 tầng theo `dictionaries/it_filter_v2.json` (L-51), bỏ JD dưới 50 từ, bỏ CTV/đa cấp, khử trùng theo công ty + tiêu đề |
| 01b deduplication | `deduplication/` | 3 tầng: (nguồn, id) → `sha1(text_fold)` → MinHash + Jaccard ≥ 0,85 cùng `company_slug` |
| 02 integration | `integration/` | Làm phẳng về 19 trường `raw_*` (gồm `raw_work_mode`) + khóa + `first_crawled_at`, gộp 8 nguồn vào `all.parquet` |
| 03 transformation | `transformation/`, `translation/`, `common/text_clean.py`, `common/lang_id.py` | Làm sạch ký tự, parse lương/ngày/kinh nghiệm, fastText ngôn ngữ, dịch EN→VI (envit5), rút kỹ năng và phúc lợi, tách địa điểm |
| 04 normalization | `normalization/`, `missing_outlier/` | 34 tỉnh, 5 cấp bậc, 10 nhóm nghề + Other, `company_key`, kỹ năng chuẩn; thiếu và ngoại lai chỉ gắn cờ |

- `05_encoding` (`encoding/`) đã được bước 10 của `processing/` thay thế, nhưng vẫn còn trong `STEPS` (PRE-39). Không thêm logic mới vào `encoding/`.
- Bảng sạch cuối là `data/preprocessing/04_normalization/all.parquet` (spec 05 mục 4.1, duyệt 17/11). Tin dịch hỏng bị cách ly sang `quarantine.parquet` (luật Q1, 19/11), nên Silver, Processing và Mining cùng một tập tin; đừng tự lọc thêm ở bên đọc. Silver (`silver.parquet`, 26 trường) ghi bằng `python -m preprocessing.normalization.silver` **sau bước 08**, vì `skills` lấy từ `job_skills.parquet`. Chuỗi mới không ghi `data/curated/`; các script còn đọc `curated_flat_golden_jobs.parquet` sẽ đổi theo PRE-39.
- Từ bước 02 dữ liệu 8 nguồn nằm chung một `all.parquet` (cột `source_platform`). Chạy thật 02–04 phải dùng `--source all`, nếu không sẽ ghi đè bằng một phần dữ liệu.
- Report: `reports/preprocessing/<bước>/<nguồn>.json` và `_all.json` (`common/step_report.py`). Luật bảo toàn `input = output + dropped`; sai thì cả bước dừng.
- `transformation/pipeline.py`, `run_transformation.py`, `normalization/run_normalization.py` và `scripts/run_staging_integration_pipeline.py` là pipeline cũ, không nằm trong chuỗi. Không sửa chúng khi sửa luật của chuỗi mới.

## Quy tắc

- **Ranh giới bước là hợp đồng** (spec 05 mục 2.4). 02 không parse, không đổi tiền, không bù. 03 không bỏ dòng, không cap ngoại lai, không log. 04 không bỏ dòng, không ghi đè cột gốc, không bù lương bằng trung bình hay trung vị. Cap ngoại lai (N6) trước log (N7).
- **Không dùng model để phân loại hay chuẩn hóa.** Chỉ có hai model: fastText `lid.176` (nhận diện ngôn ngữ, 03) và `VietAI/envit5-translation` (dịch, 03 T6b, chỉ khi có `--translate`). Giữ cột JD gốc; kỹ năng rút từ bản gốc. Thêm model khác phải được người dùng đồng ý.
- **Lương thỏa thuận** giữ NaN kèm `is_negotiable` (MNAR). Giá trị suy ra luôn có cờ (`level_inferred`, `exp_inferred`, `*_source`).
- **Ngày đăng:** bảng sạch dùng `posted_month`, không dùng `posted_date` và không có `posted_month_source` (PRE-37, bỏ 17/11). Bảng target gọn tên tiếng Anh là `04_normalization/silver.parquet` (spec 05 mục 4.4, PRE-39). Tháng phải lấy từ lần cào **đầu tiên**, không phải snapshot mới nhất mà 01 chọn.
- **Raw là bất biến:** sửa cách đọc một trường thì sửa ở đây, không sửa file raw. Raw TopDev cũ thiếu một số trường, nên flattener phải chịu được trường vắng.
- `_flatten_<nguồn>` phải khớp `monitoring/backend/app/core/feature_targets.py` (`RAW_PATHS`). Đổi tên trường ở một bên thì sửa cả bên kia.
- Khớp từ khóa và kỹ năng **theo từ nguyên vẹn**, không theo chuỗi con ("intern" từng khớp "international", "ba" khớp "backend"). Tên kỹ năng ngắn (C, R, Go) chỉ thêm kèm ngữ cảnh.
- Khóa trùng ở 01 (C6, C7) chỉ gồm công ty + tiêu đề (L-40). C7 (`c7_winner`) và D5 (`pick_cross_winner`) chọn bản giữ cùng một luật: nhiều trường nhất → sàn uy tín → mới nhất → `job_id`. Sửa một bên thì sửa cả bên kia (L-50).
- Kỳ nghiên cứu: C9 bỏ tin có ngày đăng trước `STUDY_START` (2026-09-01) ở bước 01; tin không có ngày đăng thì giữ (L-50).
- Nhãn chuyên môn của sàn (TopCV `industry_knowledge`, `overview_tags["Chuyên môn"]`) không phải kỹ năng: flattener để ở `category_tags`, chỉ bộ lọc IT của 01 đọc. Đưa lại vào `skills_list` sẽ làm "IT - Phần mềm" thành kỹ năng; bỏ hẳn khỏi bộ lọc thì 55 tin IT bị xếp ngoài IT (L-50).
- Nhóm nghề: muốn đổi nhóm thì chỉ sửa `FAMILY_MAP` trong `normalization/job_title.py`, rồi chạy lại 04, `10_features` và Mining (L-47).
- Cấp bậc ↔ kinh nghiệm: [0,1) Intern/Fresher, [1,2) Junior, [2,4) Middle, [4,5) Senior, từ 5 năm để trống (L-39).
- File mẫu gán nhãn `data/preprocessing/review/it_<nguồn>.csv` đã có nhãn tay thì không bao giờ bị ghi đè. Bộ gold `data/preprocessing/gold/gold_labels.json` gắn với mẫu `e58bceb3a5`; không dựng lại mẫu.
- Thêm nguồn mới: thêm `_flatten_<nguồn>` và tên nguồn vào `SOURCES` ở `common/__init__.py`, `VALID_SOURCES` ở `scripts/read_eda_diagnosis.py`, và monitoring `config.py`.
- Bẫy riêng của từng bước: `clean/CLAUDE.md`, `deduplication/CLAUDE.md`, `encoding/CLAUDE.md`.

## Dữ liệu đầu vào

- Đọc `data/<nguồn>/raw/`, nên chạy `python scripts/sync_cloud_lakehouse.py --download` trước.
- File batch cũ `data/vieclam24h/raw/2026-10-20/batch_001.json` và `data/vietnamworks/raw/2026-10-16/raw_batch.json` gom nhiều tin, trùng với file từng tin. Bước 01 bỏ theo luật C2, ưu tiên file từng tin (L-25).
- Repost không có file raw; ledger ghi `repost_of_url_hash`.
- EDA theo nguồn: `python scripts/read_eda_diagnosis.py --source <nguồn>`, không mở notebook (chứa ảnh base64 rất lớn).

## Việc còn mở

`docs/KNOWN_ISSUED.md` mục 3: PRE-33 (việc chờ người dùng), PRE-34 (222 tin dịch hỏng), PRE-35 (dữ liệu chưa sạch cho SD1–SD5), PRE-37 (`posted_month`), PRE-38 (tỉnh lấy từ trụ sở), PRE-39 (dọn code theo spec 05).

Chạy lại pipeline thì so số trước và sau, rồi mới đẩy lên R2 bằng `scripts/push_preprocessing_to_r2.py` (chạy thử trước, người dùng duyệt rồi mới `--push`).
