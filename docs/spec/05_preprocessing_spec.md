# ĐẶC TẢ PRE-PROCESSING (bước 00–04)

> **Dự án:** VN-IT-Job-Mining. Đề tài: "Tích hợp và khai phá dữ liệu thị trường lao động phục vụ phân tích nghề nghiệp và kỹ năng trong IT".
> **Phiên bản:** 3.0.0, ngày 17/11/2026. **Trạng thái:** đã duyệt 17/11/2026 (chặng 2).
> **Thay cho:** bản 2.0 (đặc tả theo thiết kế 13 bước), các file P0–P4 và PH0–PH7 trong `docs/spec/preprocessing/spec/`, và các file thiết kế cũ trong `docs/spec/preprocessing/`.
> **Quan hệ với tài liệu khác:** mã bước, thư mục và đường dẫn lấy theo [spec 03](03_data_mining_lifecycle.md) mục 3.1. Mục tiêu lấy theo [`docs/target/`](../target/00_de_tai.md). Processing (bước 07–12) đặc tả ở [spec 06](06_processing_spec.md).

## 0. Cách đọc

- **Nguồn sự thật**, xếp theo thứ tự ưu tiên:
  1. Code: `scripts/run_preprocessing.py` (`CHAIN`, `MODULES`), `preprocessing/common/__init__.py` (`STEPS`), `preprocessing/<bước>/run.py`.
  2. Report của lần chạy thật gần nhất: `reports/preprocessing/<bước>/_all.json`.
  3. Đặc tả cũ, chỉ lấy phần còn khớp với code.
- **Số liệu trong file này** lấy từ report chạy thật ngày 10–11/11/2026 (`code_version` 37bb865), trừ khi ghi ngày khác. Dữ liệu đang được làm sạch tiếp (PRE-35), nên các số này sẽ đổi.
- **Mỗi bước** được mô tả theo cùng một khuôn: Mục đích, Code, Đầu vào, Đầu ra, Report, Luật, Kiểm tra, Trạng thái, Việc mở.
- Mã luật có tiền tố theo bước: `C` (01), `D` (01b), `I` (02), `T` (03), `N` và `M` (04). `M` là các luật xử lý thiếu và ngoại lai, gộp vào 04.

## 1. Pre-processing phục vụ SD nào

Pre-processing biến raw của 8 sàn thành **một bảng sạch**, mỗi dòng là một tin IT duy nhất. Mọi SD đều đọc bảng này, trực tiếp hoặc qua Processing.

| Cột trong bảng sạch | Bước tạo | SD dùng |
|---|---|---|
| `job_family` (10 nhóm + Other) | 04 N3 | SD1, SD2 (luật theo nghề), SD3 (đối chiếu cụm), SD4, SD5 |
| `seniority`, `seniority_level` (5 cấp) | 04 N2, M3c | SD1, SD2, SD4, SD5 (lọc tin người mới) |
| `tinh_chinh` (34 tỉnh) | 04 N1, N13 | SD1, SD4 |
| `work_mode` | 04 | SD1 |
| `posted_month` | 03 (chưa có, PRE-37) | SD1 |
| `salary_min_vnd`, `salary_max_vnd`, `is_negotiable`, `salary_status`, các cờ ngoại lai | 03 T2, 04 N6–M8 | SD1, SD4 |
| `exp_min_years`, `exp_source` | 03 T4, 04 M4 | SD1, SD4, SD5 |
| `skills_std` | 03 T7, 04 N4 | SD2, SD4, SD5 (Processing 08 rút lại kỹ năng từ JD) |
| `description_clean`, `requirements_clean`, bản dịch `*_vi` | 03 T6, T6b | SD3 (qua 07, 09, 12) |
| `company_key` | 04 N18 | SD4 (chia train/test theo công ty, bước M5) |
| `source_platform`, `also_on` | 01, 02 | Mọi SD (đếm theo nguồn, truy vết) |

Pre-processing **không** trả lời câu hỏi nào của SD. Nhiệm vụ của nó là làm cho dữ liệu đạt 5 tiêu chí: completeness, accuracy, consistency, timeliness, uniqueness.

## 2. Hợp đồng chung

### 2.1. Chuỗi bước

```text
data/<nguồn>/raw/                      (raw, bất biến)
  │  00 profiling     chỉ đọc, đo trước và sau làm sạch
  ▼  01 clean          lọc tin IT, bỏ tin rác, chọn snapshot; vẫn giữ dạng envelope, file theo nguồn
  ▼  01b deduplication khử trùng 3 tầng; vẫn file theo nguồn
  ▼  02 integration    làm phẳng về 18 trường chung, gộp 8 nguồn vào một all.parquet
  ▼  03 transformation làm sạch ký tự, parse số và ngày, nhận ngôn ngữ, dịch EN→VI, rút kỹ năng, tách địa điểm
  ▼  04 normalization  đưa về danh mục chuẩn; xử lý thiếu và ngoại lai bằng cờ
data/preprocessing/04_normalization/all.parquet   (bảng sạch, mục 4)
```

- Lệnh chạy: `python scripts/run_preprocessing.py --step <bước>|all --source <nguồn>|all [--dry-run] [--translate]`. Lệnh này chạy cả Processing (07–12) nếu chọn `all`.
- **Output của bước N là input duy nhất của bước N+1.** Chỉ bước 01 đọc raw.
- **Thứ tự không được đảo.** Lý do ở spec 03 mục 4.
- Từ bước 02 trở đi, dữ liệu 8 nguồn nằm chung một file `all.parquet`, có cột `source_platform`. Chạy thật mà thiếu nguồn thì driver dừng, vì sẽ ghi đè `all.parquet` bằng một phần dữ liệu (`run_chain`).
- Dry-run chỉ đọc và ghi report, không ghi dữ liệu. Nếu thiếu đầu ra của bước trước, bước đó báo `INPUT_MISSING`, không điền 0.
- Chạy lẻ một nguồn thì report ghi vào `reports/preprocessing/_partial/<bước>/`, không đè report chính.
- Pre-processing chỉ ghi trên máy. Muốn đẩy lên R2 thì dùng `scripts/push_preprocessing_to_r2.py` (chạy thử trước, người dùng duyệt rồi mới `--push`).

### 2.2. Layout file

| Bước | Dữ liệu | Bản ghi bị loại | Report |
|---|---|---|---|
| 00 | — | — | `reports/preprocessing/00_profiling/{before_clean,after_clean}/` |
| 01 | `data/preprocessing/01_clean/<nguồn>.jsonl` | `data/preprocessing/rejected/01_clean/<nguồn>.jsonl` | `reports/preprocessing/01_clean/<nguồn>.json`, `_all.json` |
| 01b | `data/preprocessing/01b_deduplication/<nguồn>.jsonl`, `golden_master_jobs.parquet`, `duplicates_audit.csv` | (trong `duplicates_audit.csv`) | `reports/preprocessing/01b_deduplication/…` |
| 02 | `data/preprocessing/02_integration/all.parquet` | `data/preprocessing/rejected/02_integration/<nguồn>.jsonl` | `reports/preprocessing/02_integration/…` |
| 03 | `data/preprocessing/03_transformation/all.parquet` | — (không bỏ dòng) | `reports/preprocessing/03_transformation/…` |
| 04 | `data/preprocessing/04_normalization/all.parquet` | — (không bỏ dòng) | `reports/preprocessing/04_normalization/…`, `anomalies.json` |

- `data/preprocessing/` không đưa vào git. `reports/preprocessing/` có trong git, vì Monitoring đọc thư mục này.
- Mẫu gán nhãn tay nằm ở `data/preprocessing/review/it_<nguồn>.csv`. File nào đã có nhãn thì không bao giờ bị ghi đè.
- Bộ gold 100 JD nằm ở `data/preprocessing/gold/gold_labels.json`, gắn với mẫu `e58bceb3a5`. Không dựng lại mẫu, vì làm vậy nhãn sẽ không còn khớp (PRE-33).

### 2.3. Report của bước

Mọi bước ghi report theo một schema chung, dựng bằng `preprocessing/common/step_report.py`. Các khóa: `step`, `source`, `mode` (`dry_run` hoặc `applied`), `generated_at`, `code_version`, `input`, `output`, `dropped[]`, `rules[]`, `fields[]`, `checks`, `api`, `extra`, `samples`.

- **Luật bảo toàn:** `input.rows = output.rows + Σ dropped[].rows`. Nếu sai thì cả bước dừng và không nguồn nào được ghi.
- `rules[]`: mỗi luật có `id`, `name`, `action` (`drop`, `flag`, `modify`), `rows_affected`, `by_source`, và tối đa 3 ví dụ trước → sau có link tin. Ví dụ được chọn ổn định, nên chạy lại vẫn ra cùng ví dụ.
- `fields[]`: độ phủ của từng trường, trước và sau bước.
- `samples`: mẫu trước → sau (seed 42) do driver gắn thêm vào.
- `api`: bước nào có dùng model thì ghi tên và phiên bản model. Bước không dùng model ghi `used: false`.

### 2.4. Ranh giới bước

| Bước | Được làm | Không được làm |
|---|---|---|
| 01 | Bỏ dòng (snapshot cũ, test, ngoài IT theo chính sách đã duyệt, JD ngắn, CTV/đa cấp, trùng khóa); gắn cờ vào `metadata.clean` | Sửa `raw_payload`, làm phẳng, parse |
| 01b | Bỏ dòng trùng; gắn `metadata.dedup`, `merged_from`, `duplicate_of` | Sửa nội dung trường |
| 02 | Ánh xạ trường, làm phẳng, đọc dự phòng (JSON-LD), kiểm schema; bỏ dòng hỏng JSON hoặc sai schema | Parse số, đổi tiền, bù giá trị |
| 03 | Ép kiểu, parse, làm sạch chữ, nhận ngôn ngữ, dịch, rút kỹ năng và phúc lợi, tách địa điểm | Bỏ dòng, cap ngoại lai, log, ghi đè cột `raw_*` |
| 04 | Ánh xạ về danh mục chuẩn, suy giá trị thiếu **có cờ**, gắn cờ ngoại lai, winsorize ra cột riêng, log | Bỏ dòng, ghi đè cột gốc, bù lương bằng trung bình hoặc trung vị |

### 2.5. Dùng model

- Phân loại IT, chuẩn hóa và xử lý thiếu đều dùng **luật if-else và từ điển**. Lý do: chạy lại ra cùng kết quả, không tốn chi phí, không cần khóa API.
- Có đúng hai model có sẵn, cả hai chạy local:

  | Model | Bước | Việc | Ghim phiên bản |
  |---|---|---|---|
  | fastText `lid.176` | 03 T6 | Nhận diện ngôn ngữ JD (`vi`, `en`, `other`) | sha256 của file model ghi trong report |
  | `VietAI/envit5-translation` | 03 T6b | Dịch description và requirements tiếng Anh sang tiếng Việt | commit `840bc88104d5…` (`preprocessing/translation/core.py`) |

- JEV, OpenJev, Qwen, Gemini đã bỏ (L-28). Muốn thêm model khác phải được người dùng đồng ý.

## 3. Các bước

### 3.0. Bước 00: Profiling

| Mục | Nội dung |
|---|---|
| Mục đích | Đo hiện trạng trước và sau làm sạch cho cả 8 nguồn, để báo cáo có bảng "trước và sau". Không SD nào đọc trực tiếp |
| Code | `scripts/profile_sources.py --when before\|after\|both [--sample 500] [--seed 42]` (chỉ đọc) |
| Đầu vào | `before_clean`: raw mới nhất của mỗi `job_id`, làm phẳng trong bộ nhớ. `after_clean`: `data/preprocessing/03_transformation/all.parquet` |
| Đầu ra | Không có dữ liệu |
| Report | `reports/preprocessing/00_profiling/<when>/`: `missing_matrix.json`, `missing_heatmap.html`, `text_quality.json` (tỷ lệ còn HTML, NFD, ký tự ẩn, không dấu), `profile_<nguồn>.html` (ydata-profiling) |
| Luật | Lấy mẫu 500 tin mỗi nguồn với seed 42 (nguồn nhỏ hơn thì lấy hết). Nếu ydata-profiling không chạy được thì chỉ làm heatmap và các tỷ lệ bằng pandas |
| Kiểm tra | Đủ 8 nguồn. Cùng seed thì ra cùng kết quả |
| Trạng thái | Có code, đã chạy 10/11. **Bản `after_clean` chạy lúc 11:54 UTC, trước lần chạy 03 lúc 19:54 UTC**, nên đang đo trên bản 03 cũ (ví dụ topcv 1.533 tin so với 1.520 hiện tại). Phải chạy lại sau mỗi lần chạy lại 03 |
| Việc mở | PRE-35 |

### 3.1. Bước 01: Clean

| Mục | Nội dung |
|---|---|
| Mục đích | Chỉ giữ tin IT thật và còn nội dung, mỗi tin một snapshot. Tiêu chí: accuracy (phạm vi đúng), uniqueness. Phục vụ cả 5 SD, vì tin ngoài IT làm sai mọi tỷ lệ |
| Code | `preprocessing/clean/run.py`; `preprocessing/common/it_filter.py` (`classify`, `classify_unknown`), `raw_reader.py`; `preprocessing/clean/it_policy.json`, `scope_keywords.json`, `label_review.py` |
| Đầu vào | `data/<nguồn>/raw/**/*.json` (snapshot `<id>_v<N>.json` và file batch cũ), bỏ qua `_index`, `_quality`, `_listing`, `_listing_failures`. `input.rows` = số snapshot + số tin trong file batch |
| Đầu ra | `data/preprocessing/01_clean/<nguồn>.jsonl`: mỗi dòng một envelope, **giữ nguyên `raw_payload`**, thêm khối `metadata.clean` (`it_rule`, `it_status`, `it_rule_level`, `dedup_key`, `also_on`, `snapshot_file`). Tin bị loại ghi vào `rejected/01_clean/` kèm lý do |
| Report | `reports/preprocessing/01_clean/`; `extra.review` ghi độ đúng của luật IT trên nhãn tay theo nguồn; `extra.cross_source_pairs` |

**Luật** (thứ tự chạy thật: C3 chạy trước C1, vì bản ghi thiếu `job_id` không gom được; report vẫn ghi theo thứ tự mã):

| Mã | Luật | Hành động | Số dòng 10/11 |
|---|---|---|---|
| C1 | Mỗi `job_id` giữ snapshot mới nhất theo (`scraped_at`, `version`) | drop | 1.987 |
| C2 | Tin trong file batch cũ đã có file riêng thì bỏ; chưa có thì giữ bản batch (L-25) | drop | 616 |
| C3 | Bản ghi test, thiếu `job_id` hoặc `source_url`, sai nguồn | drop | 0 |
| C4a | Phân loại IT bằng luật 2 tầng. Tầng 1: từ khóa tiêu đề, khớp theo từ nguyên vẹn (không theo chuỗi con, vì "intern" từng khớp "international"). Tầng 2, chỉ cho tin tầng 1 ra `unknown`: xếp IT khi tiêu đề thuộc một nhóm nghề và JD có ≥ 2 kỹ năng. Từ yếu đứng một mình ("kỹ thuật", "engineer", "security") không đủ để tính là IT | flag | 5.424 |
| C4c | Bỏ tin `non_it` **chỉ ở nguồn có chính sách** trong `it_policy.json` do người dùng duyệt. `can_kiem` không bao giờ bị bỏ tự động | drop | 5.424 |
| C5 | JD dưới 50 từ | drop | 187 |
| C8 | Tin CTV, đa cấp theo `scope_keywords.json` (mã lý do `S3_*`) | drop | 13 |
| C6 | Trùng trong cùng nguồn theo `dedup_key = company_norm \| title_norm` (không có tỉnh và tuần, L-40). Giữ bản cào mới nhất; nếu bằng nhau thì giữ bản có nhiều trường có giá trị hơn | drop | 200 |
| C7 | Trùng khác nguồn theo cùng khóa: giữ bản có nhiều trường có giá trị nhất, các bản khác ghi vào `also_on` | drop | 135 |

Kết quả 10/11: 13.361 bản ghi vào, 4.799 ra.

| Mục | Nội dung |
|---|---|
| Kiểm tra | Luật bảo toàn ở 8 nguồn và ở `_all`. Độ đúng của luật IT đo trên nhãn tay `data/preprocessing/review/it_<nguồn>.csv`, báo riêng precision IT, precision non-IT, recall IT và TP/FP/TN/FN. Nếu không có nhãn thì trả `null` kèm `reason=NO_LABELS`. Đích theo thiết kế: kiểm tay 100 tin bị loại, loại nhầm dưới 5% |
| Trạng thái | Có code, đã chạy thật 10/11. Có 643 nhãn tay; độ đúng 92,4%, chưa đạt ≥ 95% |
| Việc mở | PRE-12 (nghiệm thu bộ lọc IT; tầng 2 chưa đọc `raw_category_text`), PRE-35 |

### 3.2. Bước 01b: Deduplication

| Mục | Nội dung |
|---|---|
| Mục đích | Mỗi vị trí tuyển dụng thật chỉ còn một dòng (tiêu chí uniqueness). Nếu còn trùng thì tần suất kỹ năng (SD1, SD2) bị đếm hai lần, và cùng một JD có thể nằm ở cả tập train lẫn test (SD4) |
| Code | `preprocessing/deduplication/run.py`, `intra_source.py`, `inter_source.py`, `minhash.py`, `blocking.py`, `text_norm.py`; tham số trong `preprocessing/dictionaries/dedup_policy.json` |
| Đầu vào | `data/preprocessing/01_clean/<nguồn>.jsonl` |
| Đầu ra | `data/preprocessing/01b_deduplication/<nguồn>.jsonl`: bản ghi giữ lại, thêm `metadata.dedup` (`text_fold_sha1`, `jaccard`, `merged_from`). Thêm `golden_master_jobs.parquet` (bản hợp nhất) và `duplicates_audit.csv`, gồm mọi cặp trùng, cặp sát ngưỡng và một dòng truy vết cho mỗi bản bị loại qua liên kết gián tiếp |
| Report | `reports/preprocessing/01b_deduplication/`; `extra` có `tier_counts`, `clusters`, `cross_platform_clusters`, `pairs_by_band`, `cdc`, `unparsed_dates` |

**Luật:**

| Mã | Luật | Hành động | Số dòng 10/11 |
|---|---|---|---|
| D0 | Tầng 1: trùng (`nguồn`, `job_id`). Đây là lưới an toàn, vì 01 đã khử | drop | 0 |
| D1 | Kiểm chuỗi version CDC: lần cào lại có thật sự đổi nội dung không | flag | 1.987 |
| D2 | Tầng 2, cùng sàn: `sha1(text_fold)` trùng và cùng `company_slug` | drop | 0 |
| D3 | Gán blocking key | flag | — |
| D4 | Tầng 2, khác sàn: như D2 | drop | 0 |
| D5 | Tầng 3: MinHash/LSH (shingle 5 từ, 128 permutation, seed 42) chỉ để sinh cặp ứng viên. Mọi cặp phải qua Jaccard chính xác. Cặp có J ≥ 0,85 **và** cùng `company_slug` không rỗng thì bị loại, áp dụng cả cùng sàn lẫn khác sàn. Gộp bắc cầu bằng Union-Find | drop | 127 |
| D6 | Hợp nhất golden record: bản giữ lại có `merged_from` | flag | 108 cụm (27 cụm khác sàn) |
| D7 | Cặp có J từ 0,70 trở lên nhưng không bị loại (khác công ty hoặc dưới 0,85): chỉ ghi vào audit | flag | 168 |

Kết quả 10/11: 4.799 vào, 4.672 ra.

- **Chọn bản giữ:** giữ bản đầy đủ nhất. Khi so ngày thì parse ISO và `dd/mm/yyyy`, quy ngày không có múi giờ về +07 rồi so theo UTC; không sort chuỗi ngày. Giá trị không parse được ghi vào `unparsed_dates`.
- **Bước 01b vẫn dùng `raw_posted_date`** để chọn bản giữ. Quyết định bỏ `posted_date` (mục 4.2) chỉ áp cho bảng sạch cuối.

| Mục | Nội dung |
|---|---|
| Kiểm tra | Mọi input của 01 có đúng một tham chiếu trong `source_job_ids` hoặc `repost_records`. Đích theo thiết kế: precision ≥ 95% trên 50 cặp gần ngưỡng (mẫu sinh bằng `scripts/build_dedup_pairs_sample.py`; `manual_check` trong `dedup_policy.json`) |
| Trạng thái | Có code, đã chạy thật 10/11. Người dùng duyệt 50 cặp ngày 11/11 ("ổn rồi"), nhưng chưa chấm từng cặp nên chưa có con số precision |
| Việc mở | PRE-33 (chuẩn hóa tên công ty để bắt cặp khác nguồn, ví dụ MBBANK và Ngân hàng TMCP Quân đội). Mục 6: bước 01 cũng khử trùng (C6, C7) |

### 3.3. Bước 02: Integration

| Mục | Nội dung |
|---|---|
| Mục đích | Đưa 8 schema về một schema, để mọi bước sau và mọi SD so sánh được giữa các nguồn (tiêu chí consistency, completeness) |
| Code | `preprocessing/integration/run.py`, `json_flattener.py` (`_flatten_<nguồn>`), `schema.py` (pydantic `JobRecord`) |
| Đầu vào | `data/preprocessing/01b_deduplication/<nguồn>.jsonl`. Không đọc raw |
| Đầu ra | `data/preprocessing/02_integration/all.parquet`: một dòng một tin, gộp 8 nguồn. Bản ghi bị loại ghi vào `rejected/02_integration/` kèm lý do |
| Report | `reports/preprocessing/02_integration/`; `fields[]` là độ phủ 18 trường |

**Cột đầu ra:**

| Nhóm | Cột |
|---|---|
| Khóa (luôn có) | `job_id_global`, `source_platform`, `source_job_id`, `source_url`, `crawled_at` |
| Từ 01 (`CLEAN_META`) | `it_rule`, `it_rule_level`, `it_status`, `dedup_key`, `also_on` |
| 18 trường, giữ dạng chữ như raw (tiền tố `raw_`) | `job_title`, `company_name`, `company_address`, `raw_category_text`, `raw_location_text`, `working_locations`, `raw_posted_date`, `raw_deadline`, `raw_salary_text`, `raw_employment_type`, `raw_experience_text`, `raw_seniority_text`, `raw_education_text`, `raw_headcount`, `skills_list`, `benefits_list`, `raw_description_text`, `raw_requirements_text` |
| Chưa có, cần thêm (PRE-37) | `first_crawled_at`: thời điểm cào lần đầu của tin (bản `_v1`) |

- Một trường chỉ được giữ khi có ở ít nhất một nửa số nguồn. Theo luật này đã bỏ 6 trường: `company_scale`, `raw_age_text`, `raw_gender_text`, `raw_updated_at`, `raw_working_time`, `raw_work_mode`.
- Đổi tên hoặc thêm trường thì phải sửa cả `monitoring/backend/app/core/feature_targets.py` (`RAW_PATHS`).

**Luật:**

| Mã | Luật | Hành động | Số dòng 10/11 |
|---|---|---|---|
| I1 | Làm phẳng envelope theo `_flatten_<nguồn>` về 18 trường và khóa | modify | 4.671 |
| I2 | ITviec: lấy ngày đăng từ `job_posting_jsonld.datePosted`, thay cho dạng tương đối "Đăng 6 giờ trước" | modify | 792 |
| I3 | TopDev: lấy ngày đăng theo thứ tự `published.date` → `date_posted` → JSON-LD; lấy kinh nghiệm từ JSON-LD `experienceRequirements` | modify | 66 |
| I4 | Bỏ tag SEO và ngành nghề khỏi `skills_list` (CareerViet `job-tags`, JobsGO `occupations`) | modify | 855 |
| I5 | Chuỗi rỗng và container rỗng chuyển thành null | modify | 1.098 |
| I0 | Dòng JSON hỏng | drop | 0 |
| I6 | Không qua `JobRecord` (khóa, kiểu, `job_title` rỗng) | drop | 1 |
| I7 | Lỗi trong `_flatten_<nguồn>` | drop | 0 |

Kết quả 10/11: 4.672 vào, 4.671 ra.

- Độ phủ 10/11: `raw_posted_date` 63,8% (topcv 0%), `raw_salary_text` 99,6%, `raw_experience_text` 90,7%, `raw_seniority_text` 72,5%, `skills_list` 78,3%.

| Mục | Nội dung |
|---|---|
| Kiểm tra | Luật bảo toàn. Ghép 18 trường × 8 nguồn ra một heatmap độ phủ để Monitoring hiển thị |
| Trạng thái | Có code, đã chạy thật 10/11. Chưa mang `first_crawled_at` |
| Việc mở | PRE-37 (việc 1), GEN-7 (`integration/run.py` tự tạo `boto3.client`) |


**Phúc lợi theo nguồn** (`benefits_list`, kiểm 17/11/2026 trên `integration/json_flattener.py` và trang `docs/presentation/raw_bronze/`). Mỗi phần tử của list phải là **một** phúc lợi:

| Nguồn | Raw | Cách tách hiện tại | Đúng chưa |
|---|---|---|---|
| topdev, vietnamworks | list | 1 phần tử = 1 item | đúng |
| itviec, topcv (`benefits_bullets`, tag "Quyền lợi") | list | 1 phần tử = 1 item | đúng |
| glints | chuỗi hoặc list | chuỗi thì mỗi dòng 1 item | đúng |
| careerviet | chuỗi "Phúc lợi" | tách theo `\n ; • - *` | **sai**: dấu `-` làm vỡ cụm ("Work-life balance"), và các item dính nhau thành "Phúc lợi Laptop Chế độ bảo hiểm…" (PRE-41) |
| topcv (khi không có bullets), jobsgo, vieclam24h | chuỗi | cả chuỗi thành 1 item | **sai**: không tách dòng (PRE-41) |

`benefits_std` (bước 03 T7) khớp từ khóa trên toàn bộ chuỗi nên ít bị ảnh hưởng bởi lỗi tách; cột `benefits` của bảng target lấy từ đây (mục 4.4).

### 3.4. Bước 03: Transformation

| Mục | Nội dung |
|---|---|
| Mục đích | Biến chữ thành giá trị dùng được: số lương VND/tháng, số năm kinh nghiệm, ngày, văn bản sạch một ngôn ngữ, danh sách kỹ năng. Tiêu chí: accuracy, consistency. Lương phục vụ SD1, SD4; kỹ năng phục vụ SD2, SD4, SD5; văn bản phục vụ SD3 |
| Code | `preprocessing/transformation/run.py`; `salary_parser.py` (`parse_salary_cascade`), `date_parser.py`, `experience_parser.py`, `headcount_parser.py`, `location_parser.py`, `skill_extractor.py`; `preprocessing/common/text_clean.py`, `lang_id.py`; `preprocessing/missing_outlier/sneaky_null_detector.py`; `preprocessing/translation/` |
| Đầu vào | `data/preprocessing/02_integration/all.parquet` |
| Đầu ra | `data/preprocessing/03_transformation/all.parquet`: giữ mọi cột của 02, thêm các cột ở bảng dưới |
| Report | `reports/preprocessing/03_transformation/`; `extra.language_distribution`, `extra.text_quality` (tỷ lệ HTML, NFD, ký tự ẩn còn lại) |

**Cột thêm:**

| Cột | Từ |
|---|---|
| `salary_min_vnd`, `salary_max_vnd`, `salary_currency_raw`, `salary_period_raw`, `is_negotiable`, `salary_source` (`header`, `title`, `jd`, `none`), `salary_suspect` | T2 |
| `posted_date`, `deadline_date` | T3 (chỉ dùng ở tầng trung gian, xem mục 4.2) |
| `posted_month` | **Chưa có** (PRE-37, việc 2) |
| `exp_min_years`, `exp_max_years` | T4 |
| `headcount` | T5 |
| `job_title_clean`, `description_clean`, `requirements_clean` và các bản `*_norm` (viết thường), `*_fold` (viết thường, bỏ dấu, chỉ để so khớp) | T6 |
| `language` (`vi`, `en`, `other`), `language_conf`, `language_rule` (luật cũ, để đối chiếu) | T6 |
| `description_vi`, `requirements_vi` và `*_vi_norm`, `*_vi_fold`; `translation_status` (`translated`, `failed`); tên model dịch | T6b |
| `skills_clean`, `benefits_std` | T7 |
| `locations`: danh sách `{dia_chi_cu_the, phuong_xa, tinh_thanh, raw}`, chưa chuẩn hóa | T8 |
| `flags` (ví dụ `deadline_before_crawl`) | nhiều luật |

**Luật:**

| Mã | Luật | Số dòng 10/11 |
|---|---|---|
| T1 | Null trá hình chuyển thành null ("0", "Đang cập nhật", "N/A") | 9.854 ô |
| T2 | Lương, đọc lần lượt trường lương → tiêu đề → JD; tiêu đề và JD chỉ nhận cụm số có đơn vị tiền đứng sát số. `.` và `,` theo sau đủ 3 chữ số là dấu hàng nghìn ("2,000 USD" là 2000). "Từ X" chỉ đặt min; "Up to X", "Tới X" chỉ đặt max, không gán min = max. 1 USD = 25.400 đ; lương năm chia 12. Thỏa thuận thì `is_negotiable = true` và để số NaN (thiếu kiểu MNAR, không bù) | 2.140 |
| T2f | Lương tháng ngoài khoảng 1–500 triệu: bỏ số, gắn `salary_suspect` | 15 |
| T3 | Ngày dạng ISO và `dd/mm/yyyy` chuyển thành date. Hạn nộp trước ngày cào thì chỉ gắn cờ, không sửa | 4.493 |
| T4 | Kinh nghiệm chuyển thành khoảng năm: "Không yêu cầu" → 0–0; "1 - 2 năm" → 1–2; "Trên 3 năm" → 3–null; "Dưới 1 năm" → 0–1 | 4.236 |
| T5 | Số lượng tuyển chuyển thành số nguyên | 2.773 |
| T6 | Làm sạch chữ: T6.1 bóc thẻ HTML và entity bằng regex (10 tin); T6.2 NFC (34); T6.3 bỏ ký tự ẩn `​`, `﻿`, `\xa0` (28); T6.4 đưa gạch ngang và bullet về một dạng (`- `) (1.526). Nếu còn HTML hoặc NFD thì lặp lại, tối đa 3 lần; hết lượt thì ghi vào `checks.notes`. Sau đó nhận ngôn ngữ bằng fastText `lid.176` trên 1.000 ký tự đầu; độ tin cậy dưới 0,6 thì ra `other` | 4.671 |
| T6b | Dịch description và requirements của tin `language = en` bằng envit5. Thuật ngữ trong `dictionaries/no_translate.json` (kỹ năng, công cụ, chức danh kỹ thuật) được thay bằng token giữ chỗ trước khi dịch, dịch xong thì trả lại. Văn bản cắt thành đoạn tối đa 200 token. Bản dịch được kiểm (số liệu, token giữ chỗ, tỷ lệ độ dài 0,3–3,0); hỏng thì giữ bản gốc và ghi `failed`. Có cache theo hash văn bản. Cột gốc luôn được giữ. Chỉ chạy khi có cờ `--translate` | 1.274 |
| T7 | Kỹ năng: bỏ tag dài hơn 4 từ, tag là danh mục ("Việc làm TP.HCM", "IT - Phần mềm") hoặc tên công ty; rút thêm từ JD bằng từ điển song ngữ `dictionaries/skills.json`, khớp theo từ nguyên vẹn trên **bản gốc**. Tên ngắn (C, R, Go) chỉ khớp khi có ngữ cảnh ("C/C++", "ngôn ngữ C"). Phúc lợi rút bằng `dictionaries/benefits.json` | 4.657 |
| T8 | Địa điểm 3 cấp, lấy lần lượt từ `working_locations` → `raw_location_text` → `company_address`. Tỉnh nhận theo `provinces_34.json` (kể cả tên cũ). Phường/xã phải có trong `wards_34.json` (3.321 phường/xã mới); tên phường cũ để null. Bỏ cấp quận/huyện. Không chắc thì để null, không đoán | 4.656 |

Kết quả 10/11: 4.671 vào, 4.671 ra. Ngôn ngữ: `vi` 3.390, `en` 1.274, `other` 7.

- Bản dịch không thay bản gốc. Kỹ năng rút từ bản gốc. Bản dịch dùng cho phân tích văn bản tiếng Việt ở Processing (07, 09, 12).
- Độ phủ sau 03, ngày 10/11: `salary_min_vnd` 40,2%, `salary_max_vnd` 44,5%, `posted_date` 63,8%, `exp_min_years` 90,7%, `skills_clean` 92,9%, `locations` 99,7%.

| Mục | Nội dung |
|---|---|
| Kiểm tra | 0% còn HTML, 0% NFD, 0% ký tự ẩn sau làm sạch (đo 10/11: đạt). Đích theo thiết kế: mỗi parser (lương, kinh nghiệm, ngày, địa điểm) đúng ≥ 95% trên 50 chuỗi thật; kiểm tay 50 JD đã dịch, không được đổi kỹ năng hoặc số liệu (mẫu sinh bằng `scripts/build_translation_review_sample.py`) |
| Trạng thái | Có code, đã chạy thật 10/11, có dịch. Chưa đo parser trên bộ gold. Chưa kiểm tay bản dịch. Chưa có `posted_month` |
| Việc mở | PRE-34 (222/1.274 tin tiếng Anh dịch `failed`; model làm rơi dấu "+" trong "5+ years"), PRE-33 (kiểm tay 50 JD dịch), PRE-37 (việc 2), PRE-35 |

### 3.5. Bước 04: Normalization

| Mục | Nội dung |
|---|---|
| Mục đích | Đưa giá trị về danh mục chuẩn chung cho 8 sàn, để BI và mô hình đếm và so sánh được. Xử lý thiếu và ngoại lai bằng **cờ**, không bằng cách xóa dòng hay điền trung bình. Tiêu chí: consistency, completeness, accuracy. Phục vụ cả 5 SD |
| Code | `preprocessing/normalization/run.py`; `location_normalizer.py`, `job_title.py` (`FAMILY_MAP`, `family_from_title`), `skill_normalizer.py`, `company_key.py`, `log_transformer.py`; `preprocessing/missing_outlier/missing_rules.py`, `outlier_handler.py`; từ điển `provinces_34.json`, `wards_34.json`, `job_titles.json`, `skills.json`, `skills_taxonomy.json` |
| Đầu vào | `data/preprocessing/03_transformation/all.parquet` |
| Đầu ra | `data/preprocessing/04_normalization/all.parquet` (bảng sạch, mục 4): giữ mọi cột trước đó, thêm cột ở bảng dưới. `anomalies.json` liệt kê mọi tin bị gắn cờ, kèm `job_id`, nguồn và loại cờ |
| Report | `reports/preprocessing/04_normalization/`; `extra.global_salary_stats`, `extra.anomalies_by_kind`, `extra.company_pairs_pending` |

**Cột thêm:**

| Cột | Giá trị |
|---|---|
| `locations` (thêm khóa), `tinh_chinh`, `tinh_cu`, `tinh_key`, `tinh_source`, `tinh_status`, `remote`, `ngoai_vn` | 34 tỉnh/thành sau sáp nhập (hiệu lực 01/07/2025) |
| `work_mode` | hình thức làm việc, suy từ địa điểm, tiêu đề và `raw_location_text` (luật N14; `tinh_status` là luật M7) |
| `seniority`, `seniority_level`, `seniority_source`, `level_inferred`, `seniority_can_kiem` | 5 cấp: Intern/Fresher (0), Junior (1), Middle (2), Senior (3), Lead/Manager (4); không rõ thì null |
| `job_family`, `job_family_source`, `job_family_can_kiem`, `job_family_generic_title`, `job_title_core`, `title_canonical`, `title_match_score`, `title_tech_hint` | 10 nhóm nghề + Other: Web, Mobile, Game, Bridge, DevOps/Cloud, Tester, Security, IoT, Design, Data/AI (L-47) |
| `skills_std` | tên kỹ năng chuẩn theo `skills.json` |
| `company_norm`, `company_key` | tên công ty chuẩn và khóa nhóm công ty |
| `exp_min_years` (được điền thêm), `exp_inferred`, `exp_source` | |
| `salary_min_vnd_capped`, `salary_max_vnd_capped`, `log_salary_min`, `log_salary_max`, `is_outlier_salary`, `salary_status`, `salary_out_of_range`, `salary_iqr_outlier_by_level`, `salary_iqr_scope`, `salary_iqr_upper` | lương sau xử lý ngoại lai |

**Luật:**

| Mã | Luật | Hành động | Số dòng 10/11 |
|---|---|---|---|
| N1 | Tỉnh: bỏ dấu, chữ thường, bỏ "tp", "tỉnh", "thành phố" rồi tra bí danh trong `provinces_34.json`. Tên cũ đổi sang tên mới, giữ tên cũ ở `tinh_cu` (Bình Dương → TP. Hồ Chí Minh). "Remote" → `remote = true`. Tên nước ngoài → `ngoai_vn = true`. `tinh_chinh` là tỉnh đầu tiên khác null | modify | 4.574 |
| N13 | Khi `locations` không ra tỉnh thì lấy tỉnh từ `raw_location_text`, rồi từ `company_address` | modify | 656 |
| N2 | Cấp bậc: từ `raw_seniority_text` → tiêu đề, theo từ nguyên vẹn. "Nhân viên", "Chuyên viên" không tính là cấp | modify | 4.283 |
| M3c | Cấp bậc còn trống thì suy từ số năm kinh nghiệm: [0, 1) Intern/Fresher, [1, 2) Junior, [2, 4) Middle, [4, 5) Senior; từ 5 năm trở lên để trống. Gắn `level_inferred = true` | flag | 2.516 |
| M4 | Intern/Fresher mà thiếu kinh nghiệm thì điền 0, gắn `exp_inferred` (L-39) | flag | 192 |
| N2b | Nhãn mâu thuẫn: Senior/Trưởng nhóm mà kinh nghiệm < 2 năm, hoặc Thực tập/Mới tốt nghiệp mà ≥ 3 năm → `seniority_can_kiem`. Có nhóm nghề mà JD không có kỹ năng → `job_family_can_kiem` | flag | 371 (115 cấp bậc, 258 nhóm nghề) |
| N16 | Chức danh chuẩn từ `job_titles.json` (khớp exact, alias, fuzzy) | modify | 2.091 |
| N3 | Nhóm nghề: chức danh lõi → chức danh chuẩn → nhóm, rồi gộp về 10 nhóm qua `FAMILY_MAP`. Luật không ra thì Other, không ép tin vào nhóm | modify | 3.964 khác Other |
| N4 | Kỹ năng về tên chuẩn ("ReactJS", "React.js" → "React"), bỏ trùng | modify | 4.337 |
| N5 | `company_norm` (bỏ "Công ty Cổ phần", "TNHH"…) | modify | 4.668 |
| N18 | `company_key`: gom tên công ty bằng rapidfuzz `token_sort_ratio` ≥ 90 và quan hệ tập con | modify | 4.668 |
| N6a | Lương tháng ngoài 1–500 triệu: bỏ số, gắn `salary_suspect` (chạy trước IQR) | flag | 15 |
| N6 | IQR trên toàn bộ tin để gắn `is_outlier_salary`; winsorize 1–99% ra cột `*_capped` riêng, cột gốc giữ nguyên | modify | 104 |
| M5 | Lương ngoài 2–100 triệu/tháng: chỉ gắn cờ `salary_out_of_range` | flag | 74 |
| M6 | IQR theo từng cấp bậc: chỉ gắn cờ `salary_iqr_outlier_by_level` | flag | 150 |
| M8 | min > max, kinh nghiệm ngoài khoảng: chỉ gắn cờ | flag | 5 |
| N7 | `log1p` lương, chạy **sau** N6 | modify | 2.081 |

Kết quả 10/11: 4.671 vào, 4.671 ra. Nhóm nghề sau L-47 (11/11): Web 1.853, Other 707, Bridge 533, Data/AI 430, Tester 429, DevOps/Cloud 258, Security 254, Design 78, Game 61, IoT 38, Mobile 30.

| Mục | Nội dung |
|---|---|
| Kiểm tra | Không bỏ dòng. N6 chạy trước N7. Mọi tỉnh cũ đều tra ra đúng tỉnh mới; không còn hai cách viết có dấu và không dấu của cùng một tỉnh. Đích theo thiết kế: nhóm nghề đúng ≥ 90% trên 50 tin gán tay (seed 42); bảng chéo `raw_seniority_text` × `seniority` cho VietnamWorks và TopCV |
| Trạng thái | Có code, đã chạy thật 10–11/11. Chưa đo nhóm nghề trên nhãn tay. Độ phủ: `seniority` 91,7%, `tinh_chinh` 97,8%, `skills_std` 92,9% |
| Việc mở | PRE-35 (8,3% thiếu cấp bậc, 94 tin `tinh_unknown`, 258 tin `job_family_can_kiem`), PRE-33 (87/140 mục `job_titles.json` chưa duyệt; ~317 tin itviec "0,8 năm"), PRE-38 (tỉnh lấy từ trụ sở công ty, mục 6), PRE-37 (việc 3) |

## 4. Bảng sạch cuối (Golden Master)

### 4.1. Tên và vị trí (người dùng duyệt 17/11/2026)

Hiện có ba file cùng mang nghĩa "golden", dễ nhầm:

| File | Do ai ghi | Hiện trạng |
|---|---|---|
| `data/curated/curated_flat_golden_jobs.parquet` | Pipeline cũ `scripts/run_staging_integration_pipeline.py` | Chuỗi mới không ghi file này. Vẫn được đọc bởi `mining/config.py` (`DEFAULT_GOLDEN`), `scripts/load_mart_from_parquet.py` (nạp Postgres cho trang Insights), `scripts/create_golden_master_eda_notebook.py` |
| `data/preprocessing/01b_deduplication/golden_master_jobs.parquet` | Bước 01b | Bản hợp nhất sau khử trùng, **chưa làm phẳng, chưa làm sạch**. Không bước nào sau đọc |
| `data/preprocessing/04_normalization/all.parquet` | Bước 04 | Đầu ra cuối của chuỗi mới. `mining/config.py` dùng làm dự phòng; Processing 10 đọc file này |

**Quyết định** (code chưa sửa, việc ghi ở PRE-39):

1. **Bảng sạch cuối = `data/preprocessing/04_normalization/all.parquet`.** Trong tài liệu gọi là "bảng 04" hoặc Golden Master. Không chép sang tên khác.
2. Bỏ tên `data/curated/curated_flat_golden_jobs.parquet`:
   - `mining/config.py`: `DEFAULT_GOLDEN` trỏ về bảng 04, bỏ `FALLBACK_GOLDEN`;
   - `scripts/load_mart_from_parquet.py` và `scripts/create_golden_master_eda_notebook.py` đọc bảng 04.
3. Đổi tên file của 01b thành `golden_records.parquet`, để không trùng nghĩa với bảng sạch cuối.
4. `scripts/run_staging_integration_pipeline.py` là pipeline cũ: đánh dấu là cũ trong `scripts/CLAUDE.md`. Xóa hay giữ thì hỏi riêng ở chặng 5, vì Monitoring vẫn đọc health card do nó sinh ra (`reports/curated_golden_dataset_health_card.json`).
5. Trên R2, bảng 04 vẫn được đẩy vào `curated/preprocessing/` bằng `scripts/push_preprocessing_to_r2.py` (đã có, không đổi).

Spec 03 mục 6 đã ghi theo quyết định này.

### 4.2. Ngày đăng: `posted_month` thay `posted_date` (người dùng chốt 17/11, PRE-37)

- **Bảng sạch không có cột ngày đăng đầy đủ.** Bảng 04 bỏ `posted_date` và `raw_posted_date`. Hai cột này vẫn có ở bảng 02 và 03 để truy vết; bước 01b dùng ngày đăng trong envelope để chọn bản giữ.
- **Cột thay thế** (tạo ở bước 03):
  - `posted_month` (`YYYY-MM`): tháng của `posted_date` nếu nguồn có; nếu không có thì lấy tháng của `first_crawled_at`.
  - Không có cột nguồn tháng: người dùng bỏ `posted_month_source` ngày 17/11 (mục 4.4).
- **Phải là lần cào đầu tiên.** Bước 01 đang chọn snapshot mới nhất (`raw_reader.latest_envelopes`), nên một tin cào lại sau 21 ngày sẽ bị dời sang tháng sau. Vì vậy phải mang `first_crawled_at` qua bước 02.
- **Phạm vi:** tin đăng từ tháng 9, cào trong tháng 10–11/2026. Tháng 9 chỉ có tin từ những nguồn ghi ngày đăng (topcv không có tin nào ở tháng 9), nên khi BI so tháng 9 với tháng 10–11 thì chỉ dùng các nguồn ghi ngày đăng cho gần hết tin (vietnamworks, careerviet, vieclam24h, itviec, glints, jobsgo: 96–100%); bỏ topcv (0%) và topdev (40,4%), vì tin thiếu ngày đăng của hai nguồn này mang tháng cào. Đo trên Bronze 17/11: 1.629 tin đăng tháng 9 (vietnamworks 445, jobsgo 567, itviec 304, vieclam24h 144, careerviet 102, glints 67). Số tin mỗi tháng phụ thuộc lịch cào, nên chỉ so cơ cấu, không so tổng.
- `crawled_at` (lần cào gần nhất) vẫn giữ. `days_to_deadline` ở Processing 10 tính từ cột này.
- `deadline_date` vẫn giữ ở bảng 04, không vào bảng target (mục 4.4).

### 4.3. Thiếu dữ liệu: chiến lược

| Trường | Cơ chế thiếu | Cách xử lý | Lý do |
|---|---|---|---|
| Lương "thỏa thuận" | MNAR (vị trí cao, hoặc tuyển số lượng lớn lương thấp, hay giấu lương) | Không điền. `is_negotiable = true`, số để NaN. SD4 phương án A chỉ train trên tin có lương; tin thỏa thuận được ước tính ở bước M5, không điền vào bảng sạch | Điền trung bình hoặc trung vị tạo một đỉnh giả và kéo lệch phân phối |
| Cấp bậc | MAR (phụ thuộc nguồn, tiêu đề) | Suy từ số năm kinh nghiệm, gắn `level_inferred` | Luôn phân biệt được giá trị gốc với giá trị suy ra |
| Kinh nghiệm | MAR | Intern/Fresher thiếu thì điền 0, gắn `exp_inferred`. Các trường hợp khác để null | |
| Tỉnh | Phần lớn MCAR, tỷ lệ nhỏ | Lấy từ ô địa chỉ khác (N13); không ra thì `tinh_status = unknown` | |
| Kỹ năng | Nguồn không có trường kỹ năng | Rút từ JD bằng từ điển (T7). Processing 08 rút lại trên từng section | |

Mọi giá trị suy ra đều có cờ hoặc cột `*_source`. SD nào cần dữ liệu gốc thì tự lọc theo cờ.

### 4.4. Bảng target (Silver) (người dùng chốt 17/11/2026)

Bảng 04 là bảng làm việc: giữ mọi cột trung gian, cờ và bản sao để truy vết, nên có hàng trăm cột với tên lẫn Việt và Anh. Người dùng bảng sạch (BI, Monitoring, báo cáo) cần một bảng gọn hơn. Quyết định:

- Thêm một bước cuối ghi `data/preprocessing/04_normalization/silver.parquet`: **chọn cột và đổi tên sang tiếng Anh**, không tính lại giá trị. Bảng 04 `all.parquet` giữ nguyên, vì Processing 07–10 và Mining đang đọc theo tên cột cũ; chuyển dần sang bảng target sau (PRE-39).
- Tên trường tiếng Anh, ở dạng gốc và gọn nhất. Mỗi khái niệm một cột; cờ và bản phụ không vào bảng target.

| Trường | Kiểu | Ý nghĩa | Lấy từ cột bảng 04 | SD |
|---|---|---|---|---|
| `job_id` | string | Mã tin, duy nhất, dạng `<nguồn>_<mã trên sàn>` | `job_id_global` | tất cả |
| `source` | string | Sàn của tin | `source_platform` | SD1 |
| `url` | string | Link gốc | `source_url` | truy vết |
| `title` | string | Tiêu đề đã làm sạch | `job_title_clean` | SD1, SD3 |
| `title_canonical` | string, null | Chức danh chuẩn theo `job_titles.json`; null nếu không khớp (55% tin, 10/11) | `title_canonical` | SD1 |
| `job_family` | string | 10 nhóm + Other | `job_family` | tất cả |
| `seniority` | string, null | Intern/Fresher, Junior, Middle, Senior, Lead/Manager; null nếu không rõ | `seniority` | SD1, SD4, SD5 |
| `exp_min_years` | float, null | Năm kinh nghiệm tối thiểu; "Không yêu cầu" = 0 | `exp_min_years` | SD1, SD4, SD5 |
| `exp_max_years` | float, null | Năm kinh nghiệm tối đa; "Trên 3 năm" = null | `exp_max_years` | SD1 |
| `salary_min` | float, null | Lương thấp nhất, VND/tháng, đã đổi tiền tệ và chặn ngoại lai | `salary_min_vnd_capped` | SD1, SD4 |
| `salary_max` | float, null | Lương cao nhất, VND/tháng | `salary_max_vnd_capped` | SD1, SD4 |
| `salary_negotiable` | bool | Tin ghi "thỏa thuận"; khi đó min/max là null. Giữ để phân biệt với tin parse lương lỗi | `is_negotiable` | SD4 |
| `province` | string, null | Tỉnh/thành chính, 34 tỉnh sau sáp nhập | `tinh_chinh` | SD1 |
| `work_mode` | string | `onsite`, `hybrid`, `remote`, `unknown` | `work_mode` | SD1 |
| `company` | string | Tên công ty đã chuẩn hóa | `company_norm` | SD1 |
| `company_id` | string | Khóa gộp các cách viết của một công ty (rapidfuzz `token_sort` ≥ 90); dùng đếm công ty và chia train/test theo công ty ở SD4 | `company_key` | SD1, SD4 |
| `skills` | list[string] | Kỹ năng chuẩn | `skills_std` (đổi sang nguồn bước 08 khi chốt PRE-40) | SD1–SD5 |
| `benefits` | list[string] | Phúc lợi chuẩn theo `dictionaries/benefits.json` (mục 3.3, PRE-41) | `benefits_std` | SD1 |
| `description` | string | Mô tả công việc, đã bỏ HTML | `description_clean` | SD3 |
| `requirements` | string | Yêu cầu ứng viên, đã bỏ HTML | `requirements_clean` | SD3, SD5 |
| `language` | string | Ngôn ngữ JD: `vi`, `en`, `other` | `language` | truy vết |
| `posted_month` | string | Tháng đăng `YYYY-MM` (mục 4.2) | `posted_month` (PRE-37) | SD1 |

**Trường ngoài target** (vẫn ở bảng 04 để truy vết, không vào `silver.parquet`):

| Trường | Lý do |
|---|---|
| `headcount` | Chưa SD nào dùng; 2.773 tin có số (10/11) |
| `deadline_date` | Là ngày tin đóng, không thay được ngày đăng (gộp vào `posted_month` sẽ dời tin sang tháng sau). Processing 10 vẫn đọc từ bảng 04 để tính `days_to_deadline` |
| `posted_month_source` | Người dùng bỏ khỏi target 17/11. So tháng 9 với tháng 10–11 theo luật nguồn ở mục 4.2 |
| `crawled_at` | Đã có `posted_month` |
| `salary_min_vnd`, `salary_max_vnd` (chưa chặn), `log_salary_*`, `salary_currency_raw`, `salary_period_raw`, `salary_source`, `salary_suspect`, `salary_status`, `is_outlier_salary`, `salary_out_of_range`, `salary_iqr_*` | Bản trung gian và cờ chất lượng. Bản log do Processing 10 tự tính; cờ ngoại lai ghi ở `anomalies.json` |
| `locations`, `tinh_cu`, `tinh_key`, `tinh_source`, `tinh_status`, `remote`, `ngoai_vn` | Chi tiết địa điểm; target chỉ cần `province` và `work_mode` |
| `seniority_level`, `seniority_source`, `level_inferred`, `seniority_can_kiem`, `exp_inferred`, `exp_source` | Mã số và cờ suy ra |
| `job_family_source`, `job_family_can_kiem`, `job_family_generic_title`, `job_title_core`, `title_match_score`, `title_tech_hint` | Cờ và bước trung gian của luật N3 |
| `raw_*`, `*_norm`, `*_fold`, `*_vi*`, `translation_status`, `language_conf`, `language_rule`, `skills_list`, `skills_clean`, `benefits_list`, `flags` | Chữ gốc và bản phụ để so khớp, dịch, truy vết |

## 5. Kiểm tra chung

- **Luật bảo toàn** ở mọi bước và mọi nguồn (report `checks.rows_conserved`).
- **Phễu dữ liệu** (dùng cho báo cáo và Monitoring), lần chạy 10/11:

  | Sau bước | Số tin |
  |---|---|
  | Raw (snapshot + tin trong batch) | 13.361 |
  | 01 clean | 4.799 |
  | 01b deduplication | 4.672 |
  | 02 integration | 4.671 |
  | 03 transformation | 4.671 |
  | 04 normalization | 4.671 |

- **Bộ gold 100 JD** dùng để đo bước 01 (IT hay không IT) và các parser ở bước 03, 04 (lương, kinh nghiệm, cấp bậc, địa điểm). Hiện mới đo phần Processing (`scripts/eval_gold_processing.py`). Phần Pre-processing chưa có script đo.
- Test: `tests/unit/test_clean_step.py` và các test theo bước trong `tests/unit/`. Mỗi luật nên có ít nhất một test.

## 6. Chỗ lệch cần biết

| Chỗ lệch | Ảnh hưởng | Xử lý |
|---|---|---|
| Bước 01 vẫn khử trùng theo khóa công ty + tiêu đề (C6, C7: 335 tin), sau đó 01b mới khử trùng theo nội dung (D5: 127 tin) | Khử trùng nằm ở hai bước. C6 gộp mọi tin cùng công ty và cùng tiêu đề, kể cả khác tỉnh | Giữ như code. Ghi nhận rủi ro: cùng tên vị trí ở hai tỉnh bị coi là một tin |
| N13 lấy tỉnh từ trụ sở công ty khi địa điểm làm việc không ra tỉnh. Report có ví dụ "Nhật Bản" → TP. Hà Nội, "Long Thành" → TP. Hồ Chí Minh (Long Thành thuộc Đồng Nai) | Tin làm việc ở nước ngoài bị đếm vào tỉnh trụ sở; có thể sai tỉnh (SD1, SD4) | PRE-38: kiểm 656 tin N13; tin `ngoai_vn` không lấy tỉnh từ trụ sở |
| Report 04 ghi tên luật N3 là "16 nhóm + Other"; docstring `normalization/run.py` cũng vậy | Chỉ sai nhãn. Đầu ra đã là 10 nhóm (L-47) | Sửa chuỗi tên luật khi chạy lại 04 |
| Docstring `transformation/run.py` ghi "không dịch, không gọi model nào" | Sai: 03 có dịch (T6b) và dùng fastText | Sửa docstring |
| `STEPS` còn `05_encoding`; `reports/preprocessing/05_encoding/` có 70 file (PRE-26) | Chuỗi chạy thêm một bước đã bị bước 10 thay thế | Bỏ khỏi `STEPS` (đề xuất spec 03 mục 7, đã duyệt). Ghi ở PRE-39 |
| Docstring và comment trong code trỏ tới `docs/spec/preprocessing/spec/P*.md` | Sau khi xóa các file đó (mục 7), các trỏ này sẽ chết | Đổi sang `docs/spec/05_preprocessing_spec.md` mục tương ứng (PRE-39) |
| Bản 00 `after_clean` đo trên bản 03 cũ | Bảng "trước và sau" lệch vài chục tin | Chạy lại 00 sau mỗi lần chạy lại 03 |

## 7. Tài liệu đã gộp vào spec này

Nội dung còn đúng của các file dưới đây đã nằm trong spec này. Người dùng duyệt và các file đã bị xóa ngày 17/11/2026; muốn xem bản cũ thì dùng `git show <commit>:<đường dẫn>`. Cùng đợt đã xóa các bản sao P0–P4 trong `docs/prompting/draft/` và `docs/prompting/preprocessing/`.

- `docs/spec/preprocessing/spec/P0_pipeline_contract.md`, `P1_clean.md`, `P2_integration.md`, `P3_transformation.md`, `P4_normalization.md`.
- `docs/spec/preprocessing/spec/PH0`–`PH7`.
- `docs/spec/preprocessing/00_architecture_overview.md`, `05_post_integration_master_pipeline.md`, `integration/`, `transformation/`, `missing_outlier/`, `normalization/`.
- Thiết kế 13 bước cũ, bước 0–6 (`git show HEAD:"Tiền xử lý dữ liệu JD ngành IT cho Data Mining.md"`).

P5, PH8, PH9 và `docs/spec/preprocessing/encoding/` thuộc Processing, sẽ gộp vào spec 06 ở chặng 3.
