# P2. Integration: làm phẳng về 18 trường chung

> Trạng thái: **đặc tả, chờ duyệt** (03/11/2026). Cần P1 xong trước.
> Prompt: `docs/prompting/P2_integration.md`.

## 1. Ngữ cảnh

- Flattener (`preprocessing/integration/json_flattener.py`, hàm `_flatten_<nguồn>`) ra 24 trường. Luật chốt 03/11/2026: một trường chỉ được giữ khi có ở ít nhất 3–4 trên 8 nguồn (≥ 50% tin có giá trị). Trường nào trích xuất được thì lấy, không thì để null.
- Đọc sai hoặc bỏ sót ở 4 chỗ:

| Vấn đề | Số liệu | Mã |
|---|---|---|
| ITviec ngày đăng dạng tương đối ("Đăng\n6 giờ trước") trong khi `job_posting_jsonld.datePosted` có ngày tuyệt đối | 855 tin | A2, C3 |
| TopDev ngày đăng, kinh nghiệm luôn rỗng: chỉ đọc `recalled_at`/`created_at`, bỏ qua `published.date`, `date_posted`, `job_posting_jsonld.experienceRequirements` | ngày đăng 0%, kinh nghiệm 0,1% | C1, PRE-7 |
| CareerViet lấy `job-tags` (tag SEO) làm kỹ năng; JobsGO lấy `occupations` (ngành nghề) | — | G1, PRE-6 |
| TopCV raw không có ngày đăng | 0% | C2: để null, không suy ra |

## 2. Input

`data/preprocessing/01_clean/<nguồn>.jsonl` (output P1). Không đọc `data/<nguồn>/raw/`.

## 3. Output

`data/preprocessing/02_integration/<nguồn>.parquet`, mỗi dòng một tin, cột:

| Nhóm | Cột |
|---|---|
| Khóa (luôn có) | `job_id_global`, `source_platform`, `source_job_id`, `source_url`, `crawled_at` |
| Từ Clean | `it_rule`, `it_prob`, `it_status`, `dedup_key`, `also_on` |
| 18 trường giữ (null được) | `job_title`, `company_name`, `company_address`, `raw_category_text`, `raw_location_text`, `working_locations`, `raw_posted_date`, `raw_deadline`, `raw_salary_text`, `raw_employment_type`, `raw_experience_text`, `raw_seniority_text`, `raw_education_text`, `raw_headcount`, `skills_list`, `benefits_list`, `raw_description_text`, `raw_requirements_text` |

Bỏ 6 trường: `company_scale`, `raw_age_text`, `raw_gender_text` (mỗi trường chỉ 1 nguồn có), `raw_updated_at`, `raw_working_time`, `raw_work_mode` (mỗi trường chỉ 2 nguồn có).

Mọi giá trị vẫn là **chữ như raw** (tiền tố `raw_`). Integration không parse.

## 4. Hướng xử lý

| Mã | Luật | Ví dụ trước → sau |
|---|---|---|
| I1 | Làm phẳng theo `_flatten_<nguồn>`, chỉ ghi 18 trường + khóa | envelope → 1 dòng |
| I2 | ITviec `raw_posted_date` lấy `job_posting_jsonld.datePosted`; không có mới dùng `posted_at_raw` | "Đăng\n6 giờ trước" → "2026-11-01T03:00:00+07:00" |
| I3 | TopDev `raw_posted_date` theo thứ tự `published.date` → `date_posted` → `job_posting_jsonld.datePosted`; `raw_experience_text` từ `job_posting_jsonld.experienceRequirements` | null → "2026-10-28" |
| I4 | Kỹ năng CareerViet và JobsGO: lấy trường kỹ năng thật nếu raw có; nếu raw không có thì để rỗng, **không** lấy tag SEO hay ngành nghề | `["IT Engineer","lập trình viên"]` → `[]` |
| I5 | Giá trị trống (`""`, `[]`, chỉ khoảng trắng) → null | `""` → null |

**Cảnh báo I4 (PRE-6):** commit `a87b2c1` từng bỏ hai trường này rồi phải hoàn tác. Khi `skills_list` rỗng, nhóm nghề chỉ còn dựa vào tiêu đề, và imputer cũ bị gọi cho mọi tin. Theo đặc tả mới, imputer đã bỏ, và P3 (T7b) rút kỹ năng từ JD bằng từ điển, nên `skills_clean` của hai nguồn này không còn rỗng. Kiểm lại ở P3: tỉ lệ tin CareerViet và JobsGO có `skills_clean` khác rỗng.

## 5. Ranh giới

- Không parse lương, ngày, số năm. Không đổi tiền. Không bỏ dòng (`rows_out = rows_in`). Không bù giá trị.
- Null trá hình ("0", "Đang cập nhật") để nguyên chữ; bước 03 mới đổi thành null.
- Đổi tên hoặc thêm trường thì sửa cả `monitoring/backend/app/core/feature_targets.py` (`RAW_PATHS`).

## 6. Monitoring thấy gì

- Heatmap độ phủ 18 trường × 8 nguồn của **output thật** (thay cho mục C của HTML 03/11).
- Ô có thay đổi so với flattener cũ được tô nổi, ví dụ TopDev ngày đăng từ 0% lên x%.
- Ví dụ trước → sau của I2, I3, I4.

## 7. Tiêu chí xong và cách review

- `rows_out = rows_in` ở cả 8 nguồn.
- Độ phủ sau sửa: ITviec `raw_posted_date` dạng tuyệt đối ≥ 95%; TopDev `raw_posted_date` > 0% và `raw_experience_text` > 0% (với raw cũ thiếu trường thì báo số thật, không ép).
- Review: mở 5 tin ITviec và 5 tin TopDev trên trang, so ngày đăng với cột mới.
- Test: mỗi luật I2–I5 một test với envelope mẫu; test cũ của flattener vẫn qua.
