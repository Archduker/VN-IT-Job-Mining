# Bước 02: Integration

> Code: `preprocessing/integration/run.py` (`process_source`, `run`; hằng `KEYS`, `CLEAN_META`, `KEEP_18`), `json_flattener.py` (`flatten_raw_job_record`, `_flatten_<nguồn>`, `split_careerviet_benefits`), `schema.py` (pydantic `JobRecord`).
> Lệnh: `python scripts/run_preprocessing.py --step integration --source all [--dry-run]`. Phải chạy `--source all`, vì đầu ra là một file chung.
> Dữ liệu mẫu: [`samples/02_integration.json`](samples/02_integration.json) (chạy lại 18/11/2026 sau các quyết định L-50).
> Prompt: [`docs/prompting/preprocessing/02_integration.md`](../../prompting/preprocessing/02_integration.md).

## 1. Mục đích

- Đưa 8 schema raw về **một schema chung**, một dòng một tin, gộp 8 nguồn vào một `all.parquet`. Nhờ vậy mọi bước sau và mọi SD so được giữa các sàn.
- Tiêu chí: **consistency** (cùng tên, cùng kiểu), **completeness** (lấy đủ trường mà nguồn có, kể cả nguồn dự phòng như JSON-LD).
- Ranh giới: bước này **không parse số, không đổi tiền, không bù giá trị**. Giá trị giữ dạng chữ như raw, với tiền tố `raw_`. Bước chỉ bỏ dòng hỏng JSON hoặc sai schema.

## 2. Luật

Số tin là của lần chạy lại 18/11 (đầu vào đã qua C9 và luật bản giữ mới; TopCV đọc thêm `date_posted`, bỏ nhãn chuyên môn khỏi kỹ năng).

| Mã | Điều kiện | Hành động | Số tin |
|---|---|---|---|
| I1 | Làm phẳng envelope bằng `_flatten_<nguồn>` (`strict=True`) về 5 khóa, 6 trường từ 01 và 19 trường `raw_*` | modify | 4.495 |
| I2 | ITviec: ngày đăng lấy từ `job_posting_jsonld.datePosted`, thay cho dạng tương đối "Đăng 6 giờ trước" | modify | 788 |
| I3 | TopDev: ngày đăng lấy theo thứ tự `published.date` → `date_posted` → JSON-LD; kinh nghiệm lấy từ JSON-LD `experienceRequirements` | modify | 65 |
| I3b | TopCV: ngày đăng lấy từ `date_posted` (chỉ bản cào gần đây có; người dùng chốt 18/11, L-50). Không đếm riêng trong report | modify | 102 tin có giá trị |
| I4 | Bỏ tag SEO, ngành và nhãn chuyên môn khỏi `skills_list`: CareerViet `job-tags`, JobsGO `occupations`, TopCV `industry_knowledge` + `overview_tags["Chuyên môn"]` (thêm 18/11, L-50). Nhãn TopCV chuyển sang khóa `category_tags` chỉ có trong bộ nhớ: bộ lọc IT của bước 01 vẫn đọc nó (kết quả lọc không đổi), bước 02 không xuất | modify | 2.366 (careerviet 309, jobsgo 541, topcv 1.516) |
| I5 | Chuỗi rỗng và container rỗng chuyển thành null | modify | 1.750 (tăng vì `skills_list` TopCV rỗng ở 46% tin sau khi bỏ nhãn) |
| I0 | Dòng JSON hỏng | drop | 0 |
| I6 | Không qua `JobRecord` (khóa, kiểu, `job_title` rỗng) | drop | 1 (careerviet `35C8A80A`, thiếu `job_title`) |
| I7 | Lỗi trong `_flatten_<nguồn>` | drop | 0 |

**Luật chọn trường:**

- Một trường chỉ được giữ khi có ở ít nhất một nửa số nguồn. Theo luật này đã bỏ `company_scale`, `raw_age_text`, `raw_gender_text`, `raw_updated_at`, `raw_working_time`.
- Ngoại lệ được người dùng duyệt 18/11: **`raw_work_mode`**. Trường này chỉ có ở 3/8 nguồn nhưng là trường của bảng Silver, và giá trị nguồn ghi sẵn đúng hơn giá trị suy từ địa điểm.

**Tách phúc lợi theo nguồn** (`benefits_list`; số trong ngoặc là số item trung bình mỗi tin, đo 18/11). Mỗi phần tử của list phải là đúng một phúc lợi:

| Nguồn | Raw | Cách tách |
|---|---|---|
| vietnamworks | list `benefitValue` | 1 phần tử = 1 item (4,1) |
| itviec | list theo mục "Tại sao" / "Phúc lợi" | 1 phần tử = 1 item (14,7) |
| topcv | list `benefits_bullets` + tag "Quyền lợi" | 1 phần tử = 1 item (10,3) |
| jobsgo | list `benefits_bullets` | 1 phần tử = 1 item (7,2) |
| vieclam24h | list, dòng bị ngắt giữa câu | nối dòng gãy bằng `stitch_fragmented_bullets` (5,3) |
| glints | chuỗi hoặc list | chuỗi thì mỗi dòng 1 item (4,5) |
| topdev | `benefits_original` là một khối HTML `<ul><li>`; nếu rỗng thì dùng `benefits_v2` | bỏ HTML rồi mỗi dòng 1 item; `benefits_v2` lấy `description`, bỏ `name` vì đó là tên icon (9,4; trước khi sửa 0,98) |
| careerviet | chuỗi "Phúc lợi Laptop Chế độ bảo hiểm Du Lịch …": các ô icon có nhãn cố định, dính liền | `split_careerviet_benefits`: tách theo 15 nhãn cố định, khớp nhãn dài trước, bỏ phần "Địa điểm …" lọt vào cuối (8,7; trước khi sửa 1,0) |

## 3. Quy trình xử lý

`process_source` chạy cho từng nguồn, rồi `run` gộp kết quả:

1. Đọc từng dòng `data/preprocessing/01b_deduplication/<nguồn>.jsonl`. JSON hỏng → **I0**.
2. `flatten_raw_job_record(env, nguồn, strict=True)` gọi `_flatten_<nguồn>`. Lỗi → **I7**.
3. Đếm **I2** (itviec có `datePosted`), **I3** (topdev có ngày hoặc kinh nghiệm JSON-LD), **I4** (careerviet có `job-tags`, jobsgo có `occupations`, topcv có `category_tags`). Các giá trị này đã được flattener lấy ở bước 2; ở đây chỉ đếm và lấy ví dụ.
4. Dựng bản ghi theo thứ tự cột:
   1. 5 khóa: `job_id_global` = `<nguồn>_<job_id>`, `source_platform`, `source_job_id`, `source_url`, `crawled_at`.
   2. 6 trường từ `metadata.clean`: `it_rule`, `it_rule_level`, `it_status`, `dedup_key`, `also_on` (rỗng thì []). `first_crawled_at` = `first_scraped_at`; nếu thiếu thì lấy `crawled_at`.
   3. 19 trường `KEEP_18`, mỗi giá trị qua `_clean_empty`. Có trường bị đổi về null thì tính **I5**.
5. `JobRecord.model_validate(record)`. Lỗi → **I6**, ghi tên cột lỗi.
6. Ghi các dòng bị loại vào `data/preprocessing/rejected/02_integration/<nguồn>.jsonl`. File có cả `raw_line` để truy vết. File này không vào git.
7. Đo độ phủ 19 trường. Kiểm `job_id_global` không trùng (chỉ báo). `check_conserved()`.
8. `run` gộp 8 nguồn, sắp cột theo `ALL_OUTPUT_COLUMNS`, ghi `all.parquet` bằng pyarrow.

## 4. Input → Output

| | Đường dẫn | Định dạng | Số dòng 18/11 |
|---|---|---|---|
| Input | `data/preprocessing/01b_deduplication/<nguồn>.jsonl` | jsonl envelope | 4.496 |
| Output | `data/preprocessing/02_integration/all.parquet` | parquet, 30 cột | 4.495 |
| Bị loại | `data/preprocessing/rejected/02_integration/<nguồn>.jsonl` | jsonl: `step`, `source`, `rule`, `reason`, `job_id`, `line_no`, `raw_line` | 1 |
| Report | `reports/preprocessing/02_integration/` | `fields[]` là độ phủ 19 trường theo nguồn | — |

**Schema đầu ra** (30 cột; độ phủ trên toàn bảng):

| Nhóm | Cột (độ phủ) |
|---|---|
| Khóa | `job_id_global`, `source_platform`, `source_job_id`, `source_url`, `crawled_at` (đều 100%) |
| Từ 01 | `it_rule`, `it_rule_level` (int), `it_status`, `dedup_key` (99,9%), `also_on` (list, 2,6% khác rỗng), `first_crawled_at` (100%) |
| 19 trường `raw_*` | `job_title` 100%, `company_name` 100%, `company_address` 87,4%, `raw_category_text` 92,9%, `raw_location_text` 97,4%, `working_locations` (list) 98,7%, `raw_posted_date` 64,5%, `raw_deadline` 94,7%, `raw_salary_text` 99,6%, `raw_employment_type` 94,5%, `raw_work_mode` 54,6%, `raw_experience_text` 90,8%, `raw_seniority_text` 73,6%, `raw_education_text` 64,9%, `raw_headcount` 60%, `skills_list` (list) 62% (trước 78,3%: TopCV bỏ nhãn chuyên môn), `benefits_list` (list) 98,8%, `raw_description_text` 100%, `raw_requirements_text` 100% |

**Độ phủ theo nguồn của các trường mà bảng Silver cần** (%):

| Nguồn | `raw_posted_date` | `raw_salary_text` | `raw_employment_type` | `raw_work_mode` | `raw_experience_text` | `raw_seniority_text` | `skills_list` | `benefits_list` |
|---|---|---|---|---|---|---|---|---|
| careerviet | 97,8 | 97,8 | 97,8 | 0 | 89,5 | 97,8 | 0 | 91,2 |
| glints | 100 | 100 | 100 | 100 | 90,3 | 0 | 80,5 | 90,3 |
| itviec | 96,8 | 99,8 | 96,8 | 96,4 | 87,7 | 0 | 100 | 100 |
| jobsgo | 99,6 | 99,8 | 99,6 | 0 | 99,8 | 99,6 | 0 | 99,8 |
| topcv | **6,7** | 99,5 | 99,5 | 99,5 | 99,5 | 99,5 | 54,0 | 100 |
| topdev | 32,3 | 100 | **0** | 0 | **27,9** | 0,5 | 83,1 | 98,0 |
| vieclam24h | 100 | 100 | 100 | 0 | 100 | 100 | 100 | 100 |
| vietnamworks | 100 | 100 | 100 | 0 | 85,0 | 100 | 100 | 100 |

`skills_list` của TopCV còn 54% vì chỉ còn `required_skills`; kỹ năng còn lại do bước 03 T7 rút từ JD.

## 5. Dữ liệu mẫu

### 5a. Tin mẫu `topcv_2325743`

Envelope ở 01b trở thành một dòng (trích):

| Cột | Giá trị | Lấy từ raw |
|---|---|---|
| `job_id_global` | `topcv_2325743` | `metadata.job_id` |
| `crawled_at` | 2026-11-01T15:04:01Z | snapshot v2 |
| `first_crawled_at` | 2026-10-20T18:44:44Z | `metadata.clean.first_scraped_at` (v1) |
| `job_title` | Backend Developer | `title` |
| `company_name` | CÔNG TY TNHH EAERA VIỆT NAM | `company` |
| `raw_category_text` | Lập trình máy tính | `company_industry` |
| `raw_location_text` | Hà Nội | `location` |
| `working_locations` | ["Hà Nội: Số 3 Lê Văn Hưu, Phường Hai Bà Trưng (…)"] | `working_places` |
| `raw_posted_date` | 2026-10-08 | `date_posted` (đọc từ 18/11, L-50) |
| `raw_deadline` | 20/11/2026 | `deadline_raw` |
| `raw_salary_text` | 400 - 900 USD | `salary_raw` |
| `raw_employment_type` | Toàn thời gian | `general_info["Loại hình làm việc"]` |
| `raw_work_mode` | Làm việc tại văn phòng / Onsite | `general_info["Hình thức làm việc"]` |
| `raw_experience_text` | 1 năm | `experience` |
| `raw_seniority_text` | Nhân viên | `general_info["Cấp bậc"]` |
| `raw_education_text` | Đại Học trở lên | `general_info["Học vấn"]` |
| `raw_headcount` | 2 người | `general_info["Số lượng tuyển"]` |
| `skills_list` | null | `required_skills` (tin này rỗng). Trước 18/11 lẫn nhãn ngành "IT - Phần mềm", "Tài chính" từ `industry_knowledge`; nay các nhãn này chỉ còn ở `category_tags` cho bộ lọc IT (I4) |
| `benefits_list` | 7 item, ví dụ "A 13th-month salary as an end-of-year bonus." | `benefits_bullets` |
| `raw_description_text` | "At EAERA, we build and scale technology that powers modern fintech businesses…" | `description_bullets` |

### 5b. Ví dụ theo luật

| Luật | Tin | Trước | Sau |
|---|---|---|---|
| I2 | itviec `ai-engineer-remote-alpha-bravo-development-4157` | `posted_at_raw` tương đối | `raw_posted_date` 2026-09-29 |
| I3 | topdev `2133063` | không có ngày ở trường thường | 2026-10-26 (từ `published`) |
| I4 | jobsgo `27681538345` | ['Quản Lý Dự Án IT', 'Kiểm Thử Phần Mềm', 'Dữ Liệu - AI - Học Máy'] | `skills_list` [] → null |
| I4 | topcv `2013194` | nhãn ['Manual Tester', 'IT - Phần cứng và máy tính', 'IT - Phần mềm'] | `skills_list` ['Kỹ Năng Phân Tích Yêu Cầu', 'Kỹ Năng Viết Test Case'] |
| I5 | glints `00151110…` | '' hoặc [] | null |
| I6 | careerviet `35C8A80A` | `job_title` rỗng | bỏ, `SCHEMA: job_title` |
| Phúc lợi careerviet | (mọi tin) | "Phúc lợi Laptop Chế độ bảo hiểm Du Lịch …" | ["Laptop", "Chế độ bảo hiểm", "Du Lịch", …] |
| Phúc lợi topdev | (mọi tin) | `<ul><li>Thưởng dự án</li>…</ul>` | ["Thưởng dự án", …] |

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Cách | Kết quả 18/11 |
|---|---|---|
| Luật bảo toàn | `checks.rows_conserved` | Đạt (4.496 = 4.495 + 1) |
| Hợp đồng cột | `tests/unit/test_integration_step.py::test_integration_output_contract_and_conservation` (30 cột, không có cột cấm) | Xanh |
| Tách phúc lợi, work mode | `::test_careerviet_benefits_split_by_fixed_labels`, `::test_topdev_benefits_html_list_one_item_per_line`, `::test_itviec_work_model_kept_as_raw_work_mode`, `::test_topcv_date_posted_and_skills_without_industry_labels` | Xanh |
| `first_crawled_at` | Mọi dòng có giá trị; tin nhiều snapshot có `first_crawled_at` < `crawled_at` | Đạt |
| Heatmap độ phủ 19 trường × 8 nguồn | `docs/presentation/preprocessing_steps/02_integration.html` | Có |
| Đồng bộ Monitoring | Đổi tên trường thì sửa cả `monitoring/backend/app/core/feature_targets.py` (`RAW_PATHS`) | — |

## 7. Trạng thái, chỗ thiếu, việc mở

- **Trạng thái:** có code; sửa và chạy thật lại 18/11 (L-49), chạy lại lần nữa cùng ngày sau các quyết định L-50 (TopCV `date_posted`, nhãn chuyên môn).
- **Chỗ thiếu so với bảng Silver:**

| Chỗ thiếu | Số liệu 18/11 | Ảnh hưởng | Hướng xử lý (chờ duyệt) |
|---|---|---|---|
| TopCV chỉ 102/1.523 tin có `raw_posted_date` | 6,7%. Chỉ bản cào gần đây có `date_posted` | `posted_month` của 1.421 tin TopCV vẫn lấy từ `first_crawled_at` (PRE-37) | Không còn nguồn nào khác trong raw |
| TopDev thiếu loại hình và kinh nghiệm | `raw_employment_type` 0%, `raw_experience_text` 28,2% | `exp_min_years` thấp | Bước 03 lấy kinh nghiệm từ JD (từ điển `jd_extraction.json` đã duyệt 18/11) |
| Glints, ITviec, TopDev không có `raw_seniority_text` | 0%, 0%, 0,5% | Bước 04 phải suy cấp bậc từ tiêu đề và kinh nghiệm | Đã có luật suy ở 04 |
| `raw_work_mode` chỉ có ở 3 nguồn | 54,5% | `work_mode` của 5 nguồn còn lại phải lấy từ JD hoặc địa điểm | Bước 03 T-JD + 04 |

- **Việc mở:** GEN-7 (`integration/run.py` tự tạo `boto3.client` trong `ensure_p1_data_from_r2`, không đi qua `get_r2_client()`), PRE-37, PRE-40.
