# Đặc tả chi tiết từng bước pre-processing

> **Quan hệ với spec 05:** [`05_preprocessing_spec.md`](../05_preprocessing_spec.md) giữ hợp đồng chung (chuỗi bước, layout file, report, ranh giới bước, dùng model, bảng sạch cuối và bảng Silver). Các file ở đây là **đặc tả chi tiết** của từng bước: luật, quy trình xử lý theo thứ tự trong code, input → output, dữ liệu mẫu của lần chạy thật, kiểm tra. Mỗi luật chỉ được ghi chi tiết ở một chỗ, là file của bước đó.
>
> **Prompt để làm hoặc làm lại từng bước:** [`docs/prompting/preprocessing/`](../../prompting/preprocessing/README.md).

## Mục lục

| Bước | File | Code | Lần chạy thật gần nhất |
|---|---|---|---|
| 00 Profiling | [`00_profiling.md`](00_profiling.md) | `scripts/profile_sources.py` | 10/11 (chạy lại sau khi có 03 mới) |
| 01 Clean | [`01_clean.md`](01_clean.md) | `preprocessing/clean/run.py` | 18/11, 13.361 → 4.799 |
| 01b Deduplication | [`01b_deduplication.md`](01b_deduplication.md) | `preprocessing/deduplication/run.py` | 18/11, 4.799 → 4.672 |
| 02 Integration | [`02_integration.md`](02_integration.md) | `preprocessing/integration/run.py` | 18/11, 4.672 → 4.671 |
| 03 Transformation | [`03_transformation.md`](03_transformation.md) | `preprocessing/transformation/run.py` | 18/11 (không dịch); đang chạy lại có dịch |
| 04 Normalization | [`04_normalization.md`](04_normalization.md) | `preprocessing/normalization/run.py` | 10–11/11 (chưa chạy lại) |
| Bảng Silver | [`silver.md`](silver.md) | (chưa có, PRE-39) | — |

## Khuôn của mỗi file

Mọi file bước dùng đúng 7 mục, theo thứ tự này:

1. **Mục đích**: SD được phục vụ và tiêu chí chất lượng (completeness, accuracy, consistency, timeliness, uniqueness).
2. **Luật**: bảng gồm mã, điều kiện, hành động (`drop`, `modify`, `flag`), số tin của lần chạy thật.
3. **Quy trình xử lý**: các bước đánh số đúng thứ tự thực thi trong code.
4. **Input → Output**: đường dẫn, định dạng, số dòng theo nguồn, schema, report và file phụ.
5. **Dữ liệu mẫu**: (a) tin mẫu xuyên suốt ở bước này; (b) ví dụ thật trước → sau của từng luật.
6. **Kiểm tra và nghiệm thu**: lệnh, ngưỡng, kết quả lần chạy thật.
7. **Trạng thái, chỗ thiếu, việc mở**: chỗ thiếu so với bảng Silver, mã PRE.

## Dữ liệu mẫu

- Mọi số và mẫu trong các file bước lấy từ `samples/<bước>.json`. Các file này do `python scripts/build_step_samples.py` sinh ra từ dữ liệu trên máy (`data/preprocessing/<bước>/`) và report (`reports/preprocessing/<bước>/_all.json`).
- Script chỉ đọc. Chạy lại trên cùng dữ liệu thì ra file giống hệt.
- Lần chạy dùng trong các file này: **18/11/2026**, trên tập raw đang có trên R2. 71 file TopCV chỉ có trên máy được tạm chuyển sang `data/_local_only/`.
  - Số tin vào và ra trùng với lần chạy 10/11.
  - Khác biệt là bước 01 có thêm `first_scraped_at`, bước 02 có thêm `raw_work_mode` và `first_crawled_at`, và phúc lợi CareerViet, TopDev được tách lại (L-49).

### Tin mẫu xuyên suốt: `topcv_2325743`

**Backend Developer, CÔNG TY TNHH EAERA VIỆT NAM** (<https://www.topcv.vn/viec-lam/backend-developer/2325743.html>).

**Cách chọn:** `build_step_samples.py` có hàm `candidates()` lọc tin thỏa đủ các điều kiện sau:

- còn tới bước 03;
- có lương, kinh nghiệm, `raw_work_mode` và ít nhất 3 phúc lợi;
- JD tiếng Anh;
- lương ngoại tệ;
- có ít nhất 2 snapshot raw.

Trên dữ liệu 18/11 chỉ có đúng 1 tin thỏa (tin này). Tin này đi qua được nhiều luật nhất.

| Bước | Tin này ở bước đó |
|---|---|
| Raw | 2 snapshot: `data/topcv/raw/2026-10-20/2325743_v1.json` (cào 20/10 18:44 UTC) và `2026-11-01/2325743_v2.json` (01/11 15:04 UTC) |
| 01 | C1 giữ v2. `first_scraped_at` = lần cào của v1. C4a: `it`, tầng 1. `dedup_key` = `eaera\|backend developer` |
| 01b | Không trùng tin nào: `cluster_size` 1, `blocking_key` `eaera_HN_backend` |
| 02 | Một dòng 30 cột. `raw_salary_text` "400 - 900 USD", `raw_work_mode` "Làm việc tại văn phòng / Onsite", `raw_experience_text` "1 năm", `first_crawled_at` 2026-10-20 |
| 03 | `salary_min_vnd` 10.160.000, `salary_max_vnd` 22.860.000 (USD → VND), `exp_min_years` 1, `language` `en` |
| 04, Silver | Điền khi chạy lại |

Tin này cũng cho thấy 3 chỗ thiếu:

| Chỗ thiếu | Bước gây ra | Chi tiết |
|---|---|---|
| Thiếu ngày đăng | 02 | Raw có `date_posted` = 2026-10-08 nhưng `raw_posted_date` rỗng. `_flatten_topcv` không đọc trường này; 102/1.520 tin TopCV có trường này |
| `skills_list` lẫn nhãn ngành | 02 | `skills_list` = ["IT - Phần mềm", "Tài chính"], là nhãn ngành chứ không phải kỹ năng. 03 vẫn rút ra "Tài chính" |
| Phúc lợi tiếng Anh chưa nhận | 03 | `benefits_std` chỉ nhận 2/7 phúc lợi tiếng Anh |

Chi tiết các chỗ thiếu này nằm ở mục 7 của từng file bước.
