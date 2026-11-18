# Prompt 02: Integration (sửa L-49: hình thức làm việc, lần cào đầu, tách phúc lợi)

> Đặc tả: [`docs/spec/preprocessing/02_integration.md`](../../spec/preprocessing/02_integration.md). Dữ liệu mẫu: `docs/spec/preprocessing/samples/02_integration.json`.
> Prompt này viết lại ngày 18/11/2026 sao cho làm lại ra **đúng kết quả lần chạy lại 18/11** (L-49, rồi L-50): 4.496 → 4.495, 30 cột. Lần chạy đầu 18/11 ra 4.672 → 4.671.

## 1. Ngữ cảnh

**Đọc trước:**

- Đặc tả bước 02 (mục 2 luật chọn trường và cách tách phúc lợi, mục 7 chỗ thiếu).
- `preprocessing/CLAUDE.md`: `_flatten_<nguồn>` phải khớp `monitoring/backend/app/core/feature_targets.py`.
- Code: `preprocessing/integration/run.py`, `json_flattener.py`, `schema.py`; test `tests/unit/test_integration_step.py`.

**Vì sao làm:** trang `docs/presentation/preprocessing_steps/02_integration.html` lần chạy đầu ngày 18/11 cho thấy 4 lỗi:

| Lỗi | Hệ quả |
|---|---|
| Bảng 02 không có `raw_work_mode` | Bước 04 chỉ suy `work_mode` từ địa điểm; tin có tỉnh thì mặc định onsite |
| itviec có `work_model` ở 789/818 tin nhưng flattener không đọc | Mất hình thức làm việc của itviec |
| Không có lần cào đầu | Không tạo được `posted_month` (PRE-37) |
| Phúc lợi tách sai | careerviet trung bình 1,0 item mỗi tin (các nhãn dính liền); topdev 0,98 (cả khối HTML thành 1 item) |

Người dùng: "oke sửa bước 02 trước rồi chạy tiếp bước 03 nha".

## 2. Việc cần sửa

**Input:** `data/preprocessing/01b_deduplication/<nguồn>.jsonl`. **Output:** `data/preprocessing/02_integration/all.parquet` (30 cột), `rejected/02_integration/`, `reports/preprocessing/02_integration/`, trang `02_integration.html`.

1. `run.py`:
   - `CLEAN_META` thêm `first_crawled_at`. Giá trị = `metadata.clean.first_scraped_at`; thiếu thì lấy `crawled_at`.
   - `KEEP_18` thêm `raw_work_mode`, ngay sau `raw_employment_type`. Đây là ngoại lệ của luật "có ở ít nhất nửa số nguồn"; người dùng duyệt 18/11.
   - Tên luật I1: "… về 19 trường chuẩn (18 + raw_work_mode) + khóa + first_crawled_at".
2. `json_flattener.py`:
   - itviec: `flat["raw_work_mode"] = _clean_str(raw.get("work_model"))`.
   - careerviet: `split_careerviet_benefits(text)`:
     - bỏ chữ "Phúc lợi" ở đầu;
     - cắt ở "Địa điểm";
     - tách theo 15 nhãn cố định (`CAREERVIET_BENEFIT_LABELS`), khớp nhãn dài trước.
   - topdev:
     - `benefits_original`: bỏ HTML, mỗi dòng 1 item, bỏ ký tự " -•*\t" ở đầu và cuối;
     - `benefits_v2`: lấy `value` → `description` → `name`; `name` là tên icon nên chỉ dùng khi không còn gì khác.
3. Test. Chạy lại 01 → 01b → 02 (vì 01 thêm `first_scraped_at`). Sinh trang. Ghi `docs/issue_log.md` L-49, sửa `docs/KNOWN_ISSUED.md` (PRE-37 việc 1 xong; PRE-41 chỉ còn từ điển).

### Bổ sung 18/11 (L-50, người dùng chốt)

1. `_flatten_topcv`: `raw_posted_date` = `date_posted`.
2. `_flatten_topcv`: `industry_knowledge` và `overview_tags["Chuyên môn"]` không vào `skills_list`, chuyển sang `flat["category_tags"]`. Bước 02 không xuất khóa này (không thuộc `KEEP_18`), bước 01 đưa nó vào bộ lọc IT.
3. `run.py` I4 đếm thêm topcv có `category_tags`; tên luật "Bỏ tag SEO, ngành nghề và nhãn chuyên môn khỏi skills_list".
4. `monitoring/backend/app/core/feature_targets.py` `RAW_PATHS["topcv"]`: F7 chỉ còn `required_skills`, F8 thêm `date_posted`.

## 3. Pseudo code

```text
for dòng in 01b/<nguồn>.jsonl:
    env = json.loads(dòng)                  # lỗi → I0
    flat = _flatten_<nguồn>(env, strict)    # lỗi → I7
        itviec:     raw_work_mode = work_model
        careerviet: benefits_list = split_careerviet_benefits(chuỗi "Phúc lợi …")
        topdev:     benefits_list = lines(strip_html(benefits_original)) or [v2.value|description|name]
    record = KEYS + CLEAN_META(+ first_crawled_at = first_scraped_at or crawled_at)
             + KEEP_18(+ raw_work_mode), mỗi giá trị qua _clean_empty   # → I5
    JobRecord.validate(record)              # lỗi → I6
gộp 8 nguồn → all.parquet theo ALL_OUTPUT_COLUMNS
```

## 4. Ràng buộc

- Không parse số, không đổi tiền, không bù giá trị. Giữ dạng chữ như raw.
- Không sửa raw. Sửa cách đọc ở flattener.
- Đổi hoặc thêm trường thì kiểm `RAW_PATHS` ở `monitoring/backend/app/core/feature_targets.py`.
- Test dùng chuỗi thật lấy từ raw, ghi `job_id` nguồn trong chú thích.
- Test cũ khẳng định "không có `raw_work_mode`" thì sửa và ghi lý do (ngoại lệ đã duyệt).
- Chạy thật phải `--source all`. Không đẩy R2. Không push.

## 5. Ví dụ (thành test)

| Đầu vào (raw thật) | Kết quả mong đợi | Test |
|---|---|---|
| careerviet "Phúc lợi Laptop Chế độ bảo hiểm Du Lịch … Địa điểm …" | ["Laptop", "Chế độ bảo hiểm", "Du Lịch", …], không còn "Địa điểm" | `tests/unit/test_integration_step.py::test_careerviet_benefits_split_by_fixed_labels` |
| topdev `benefits_original` là khối `<ul><li>`; `benefits_v2` có `name` "Library" và `description` "Thưởng dự án" | Mỗi `<li>` một item; từ v2 lấy ["Thưởng dự án"] | `::test_topdev_benefits_html_list_one_item_per_line` |
| itviec `work_model` "Tại văn phòng" | `raw_work_mode` "Tại văn phòng" | `::test_itviec_work_model_kept_as_raw_work_mode` |
| Envelope có `metadata.clean.first_scraped_at` | `first_crawled_at` = giá trị đó; thiếu thì bằng `crawled_at` | `::test_integration_output_contract_and_conservation` |
| Tin mẫu `topcv_2325743` | 30 cột; `raw_work_mode` "Làm việc tại văn phòng / Onsite"; `first_crawled_at` 2026-10-20T18:44:44Z; `raw_salary_text` "400 - 900 USD" | kiểm trên dữ liệu thật (`samples/02_integration.json`) |
| careerviet `35C8A80A` thiếu `job_title` | I6 bỏ, `SCHEMA: job_title` | `::test_i6_missing_crawled_at_and_empty_title_rejected` |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit/test_integration_step.py tests/unit/test_clean_step.py -q` | Xanh |
| Dry-run | `python scripts/run_preprocessing.py --step integration --source all --dry-run` | Bảo toàn |
| Chạy thật | 01 → 01b → 02, `--source all` | 4.496 → 4.495, 30 cột; I4 2.366 (topcv 1.516); TopCV `raw_posted_date` 102 tin; top kỹ năng TopCV không còn nhãn ngành |
| `raw_work_mode` | Độ phủ theo nguồn | topcv 99,5%, glints 100%, itviec 96,5% |
| Phúc lợi | Số item trung bình mỗi tin | careerviet ≈ 8,7; topdev ≈ 9,5 |
| `first_crawled_at` | Độ phủ | 100% |
| Trang | `02_integration.html` (heatmap 19 trường × 8 nguồn) | Có, không tràn ngang ở 390px |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| 1 | Duyệt đặc tả | 18/11 | Từ trang 02, người dùng duyệt: giữ `raw_work_mode` dù chỉ có ở 3/8 nguồn; tách lại phúc lợi; mang lần cào đầu. "oke sửa bước 02 trước rồi chạy tiếp bước 03 nha" | `77cac00` (spec 05 mục 3.3 bản 3.0.0) |
| 2 | Duyệt prompt | 18/11 | Đi tắt: làm ngay theo câu duyệt ở bước 1. Prompt này viết lại để lưu log | — |
| 3 | Test rồi code | 18/11 | 3 test mới + sửa `test_integration_output_contract_and_conservation` (30 cột) và `test_clean_step` (`first_scraped_at`) | `77cac00` |
| 4 | Dry-run | 18/11 | 8 nguồn: 4.672 → 4.671 | — |
| 5 | Review, chạy thật | 18/11 | Chạy thật 01 → 01b → 02. L-49 ghi vào `docs/issue_log.md`; PRE-37 việc 1 xong; PRE-41 thu về phần từ điển. Trang `02_integration.html` | `77cac00` |
| — | Chỗ thiếu mới (đã xử lý ở L-50 bên dưới) | 18/11 | Khi viết đặc tả chi tiết thấy thêm: TopCV không đọc `date_posted` (102 tin có); `skills_list` TopCV gộp `industry_knowledge` (nhãn ngành). Chờ người dùng quyết | — |
| 1 | Duyệt đặc tả (bổ sung L-50) | 18/11 | Người dùng trả lời các chỗ thiếu PRE-43: "thêm 3 cờ vào silver đi rồi cập nhật lại tài liệu. có thể láy vô tháng. um bỏ nhãn it phần mềm. hmm bạn thấy cáo nào nó có hiệu quả hơn thì lấy cía đó. lấy các loại hợp đồng đó vào sliver đi. bỏ luôn 76 tin glint đó đi"; chọn "Mọi sàn, trước 09/2026" | — |
| 2 | Duyệt prompt | 18/11 | Đi tắt: làm ngay theo câu duyệt ở bước 1; prompt này cập nhật để lưu log | — |
| 3 | Test rồi code | 18/11 | Test trước: `test_topcv_date_posted_and_skills_without_industry_labels`. Lần đầu bỏ hẳn nhãn khỏi bộ lọc thì 55 tin TopCV IT (IT PM, System Admin, UI/UX…) bị xếp ngoài IT; chuyển sang `category_tags` để bộ lọc giữ nguyên | `591391b` |
| 4 | Dry-run | 18/11 | Không dry-run riêng: dry-run 01b và 02 đọc đầu ra cũ của bước trước nên không đo được tác động. Chạy thật trên máy (không đụng R2), so report với git HEAD | — |
| 5 | Review, chạy thật | 18/11 | Chạy thật 01 → 01b → 02. 02: 4.496 → 4.495, 30 cột; `skills_list` TopCV 54% (chỉ `required_skills`). L-50; PRE-43 đóng. Chờ người dùng xem | `591391b` + commit tài liệu |
