# Bước 03: Transformation

> Code: `preprocessing/transformation/run.py` (`process_source`, `run`); `salary_parser.py` (`parse_salary_cascade`), `date_parser.py` (`process_dates`), `experience_parser.py`, `headcount_parser.py`, `location_parser.py`, `skill_extractor.py` (`extract_skills`, `extract_benefits`); `preprocessing/common/text_clean.py`, `lang_id.py`; `preprocessing/translation/` (`make_context`, `translator.py`, `core.py`); `preprocessing/missing_outlier/sneaky_null_detector.py`. Luật mới T9: `preprocessing/transformation/jd_extractor.py` đọc `preprocessing/dictionaries/jd_extraction.json`.
> Lệnh: `python scripts/run_preprocessing.py --step transformation --source all [--dry-run] [--translate]`.
> Dữ liệu mẫu: [`samples/03_transformation.json`](samples/03_transformation.json) (chạy lại 19/11/2026 **có dịch**, dùng cache bản dịch 18/11, đầu vào là bảng 02 sau bộ lọc IT ba tầng, 3.997 tin).
> Prompt: [`docs/prompting/preprocessing/03_transformation.md`](../../prompting/preprocessing/03_transformation.md).
>
> **Trạng thái của file này:** mục 2.1 và 2.2 là luật đang chạy. Mục 2.2 được người dùng duyệt 18/11, đã code và **chạy thật 18/11 (có dịch)**. Số trong file là của lần chạy đó, trừ chỗ ghi khác.

## 1. Mục đích

Biến chữ thành giá trị dùng được:

| Giá trị | SD dùng |
|---|---|
| Lương VND/tháng | SD1, SD4 |
| Số năm kinh nghiệm | SD1, SD4, SD5 |
| Tháng đăng | SD1 |
| Hình thức làm việc | SD1 |
| Văn bản sạch, kèm bản dịch tiếng Việt | SD3 (qua Processing 07, 09, 12) |
| Danh sách kỹ năng, phúc lợi | SD1, SD2, SD4, SD5 |
| Địa điểm 3 cấp | SD1 |

- Tiêu chí: **accuracy** (parse đúng), **consistency** (cùng đơn vị, cùng ngôn ngữ để so khớp).
- Ranh giới:
  - **không bỏ dòng, không cap ngoại lai, không log, không ghi đè cột `raw_*`**;
  - giá trị suy ra luôn có cột nguồn (`*_source`) hoặc cờ;
  - khi có hai nguồn cho cùng một khái niệm (ô của sàn và JD), bước 03 ghi **cả hai và cờ lệch**; bước 04 chọn giá trị cuối.

## 2. Luật

### 2.1. Luật đang chạy

Số tin là của lần chạy lại 19/11 có dịch (3.997 tin, sau bộ lọc IT ba tầng ở 01; lần 18/11 là 4.495 tin).

| Mã | Điều kiện / cách làm | Hành động | Số tin 18/11 |
|---|---|---|---|
| T1 | Null trá hình ("0", "Đang cập nhật", "N/A", …) ở mọi cột `raw_*` chuyển thành null (`is_val_null`) | modify | 11.500 ô |
| T6 | Làm sạch chữ cho `raw_description_text`, `raw_requirements_text`, `job_title` → `*_clean`, `*_norm` (viết thường), `*_fold` (viết thường, bỏ dấu, chỉ để so khớp). Gồm: T6.1 bóc thẻ HTML và entity; T6.2 NFC; T6.3 bỏ ký tự ẩn (`​`, `﻿`, `\xa0`); T6.4 gạch ngang và bullet về `- `. Còn HTML hoặc NFD thì lặp lại, tối đa 3 lần | modify | 4.495 (T6.1: 8, T6.2: 25, T6.3: 27, T6.4: 1.460) |
| T6 (ngôn ngữ) | fastText `lid.176` trên `description_clean`. Độ tin cậy dưới 0,6 thì ra `other`. Luật đếm dấu cũ giữ ở `language_rule` để đối chiếu | modify | `vi` 2.876, `en` 1.114, `other` 7 |
| T6b | Chỉ khi có `--translate`: dịch `description_clean` và `requirements_clean` của tin `en` bằng envit5 (revision `840bc881`). Thuật ngữ trong `no_translate.json` được thay bằng token `XTERMnX` trước khi dịch. Văn bản cắt thành đoạn ≤ 200 token, giải mã greedy. Bản dịch được kiểm (số liệu, token, tỷ lệ độ dài 0,3–3,0); hỏng thì giữ bản gốc và ghi `failed`. Cache ở `data/preprocessing/translation/translations_cache.jsonl` | modify | 1.114 tin `en`: 914 `translated`, 200 `failed` (giữ bản gốc ở đoạn hỏng). Lần 18/11: 1.193 tin, 209 `failed`, 257/25.121 đoạn hỏng sau 1 lần thử lại |
| T2 | Lương, đọc lần lượt trường lương → tiêu đề → JD. Tiêu đề và JD chỉ nhận cụm số có đơn vị tiền đứng sát số. `.` và `,` theo sau đủ 3 chữ số là dấu hàng nghìn. "Từ X" chỉ đặt min; "Up to X", "Tới X" chỉ đặt max. **1 USD = 25.400 đ**; lương năm chia 12. Thỏa thuận thì `is_negotiable` = true và số để NaN (thiếu kiểu MNAR, không bù) | modify | 2.052 từ ô lương, 20 từ tiêu đề, 5 từ JD; 2.443 thỏa thuận |
| T2f | Lương tháng ngoài 1–500 triệu: bỏ số, gắn `salary_suspect` | flag | 13 |
| T3 | `raw_posted_date`, `raw_deadline` dạng ISO hoặc `dd/mm/yyyy` → date. Hạn nộp trước ngày cào thì chỉ gắn cờ `deadline_before_crawl` | modify | 4.323 |
| T4 | `raw_experience_text` → khoảng năm: "Không yêu cầu" → 0–0; "1 - 2 năm" → 1–2; "Trên 3 năm" → 3–null; "Dưới 1 năm" → 0–1 | modify | 4.080 |
| T5 | `raw_headcount` → số nguyên | modify | 2.695 |
| T7 | Kỹ năng (`extract_skills`): bỏ tag dài hơn 4 từ, tag danh mục, tên công ty; rút thêm từ JD bằng `skills.json`, khớp theo từ nguyên vẹn, **chỉ trên bản gốc** (T7 sửa). Phúc lợi (`extract_benefits`): khớp `benefits.json` trên `benefits_clean` + mô tả | modify | 4.474 |
| T8 | Địa điểm 3 cấp, lấy lần lượt từ `working_locations` → `raw_location_text` → `company_address`. Tỉnh theo `provinces_34.json` (kể cả tên cũ). Phường/xã phải có trong `wards_34.json`. Không chắc thì để null | modify | 4.480 |

### 2.2. Luật thêm ngày 18/11 (người dùng duyệt, đã chạy thật)

Số tin lần chạy lại 19/11: T3b 3.997 (2.676 từ ngày đăng, 1.321 từ lần cào đầu); T6.5 960; T9a 101; T9b 248; T9c 3.069.

| Mã | Điều kiện / cách làm | Hành động | Cột mới | Vì sao |
|---|---|---|---|---|
| **T3b** | `posted_month` = `YYYY-MM` của `posted_date` nếu có. Nếu không, lấy tháng của `first_crawled_at` đổi sang giờ Việt Nam (UTC+7) | modify | `posted_month` | PRE-37 việc 2; spec 05 mục 4.2. Đổi giờ để tin cào lúc 18:00 UTC ngày 31 không bị tính sang tháng sau |
| **T6.5** | NFC + bỏ ký tự ẩn cho từng item của `benefits_list` (ghi ra `benefits_clean`), trước T7 | modify | `benefits_clean` | T6.2 hiện chỉ làm sạch mô tả, yêu cầu, tiêu đề; phúc lợi chưa được NFC |
| **T7 (sửa)** | Rút kỹ năng **chỉ từ bản gốc**, không nối bản dịch vào văn bản để rút | modify | — | Code hiện nối `description_vi`, `requirements_vi` vào văn bản rút kỹ năng khi có `--translate`. Điều này trái với spec 05 và `preprocessing/CLAUDE.md` ("kỹ năng rút từ bản gốc") |
| **T9a** | Hình thức làm việc theo `jd_extraction.json` → `work_mode` (mục 2.3) | flag | `work_mode_raw`, `work_mode_jd`, `work_mode_jd_rules`, `work_mode_jd_strong`, `work_mode_conflict` | `raw_work_mode` chỉ có ở 3/8 nguồn |
| **T9b** | Loại hợp đồng theo `jd_extraction.json` → `employment_type` | flag | `employment_type_raw`, `employment_types_raw` (list), `employment_type_jd`, `employment_type_conflict` | Tách thực tập toàn thời gian khỏi toàn thời gian; cấp tín hiệu Intern cho `seniority` ở 04 |
| **T9c** | Kinh nghiệm từ JD theo `jd_extraction.json` → `experience` | flag | `exp_min_years_jd`, `exp_max_years_jd`, `exp_jd_kind` (`jd` hoặc `jd_zero`), `exp_jd_text` (cụm khớp) | TopDev chỉ có 28,2% kinh nghiệm; ô của ITviec là mức gom SEO |

### 2.3. Luật T9 (từ điển đã duyệt 18/11)

Toàn bộ mẫu, cụm nhiễu và quyết định nằm trong `preprocessing/dictionaries/jd_extraction.json` (`approved: true`, 7 quyết định của người dùng ở khóa `decisions`). Trang đo: `docs/presentation/preprocessing_steps/jd_dictionary.html` (sinh bằng `scripts/review_jd_dictionary.py`). Phần dưới tóm tắt cách áp:

1. **Văn bản đọc:**
   - `job_title_clean` (tiêu đề), và từng câu của `description_clean`, `requirements_clean` (thân bài);
   - chỉ bản gốc, không đọc bản dịch, giống quy tắc rút kỹ năng;
   - NFC, gộp khoảng trắng, không phân biệt hoa thường, khớp theo từ nguyên vẹn (`\b`).
2. **Cụm nhiễu:** xóa khỏi câu (thay bằng khoảng trắng) trước khi so mẫu. Ví dụ: "hybrid cloud", "remote support", "tin học văn phòng", "smart contract", "mộc thực tập".
3. **`work_mode_raw`:**
   - Map `raw_work_mode` theo `raw_map`. "Linh hoạt" của itviec → hybrid.
   - TopCV cho chọn nhiều giá trị: có onsite cùng remote hoặc hybrid → hybrid.
   - Nếu `raw_work_mode` trống thì xét ô loại hình: jobsgo có "Remote" → remote; topcv "Làm tại nhà" → remote; vietnamworks mã 7 → remote.
4. **`work_mode_jd`:**
   - Áp các mẫu WR*, WH*, WO*. Có hybrid → hybrid; có cả remote và onsite → hybrid; còn lại lấy mode duy nhất.
   - Tín hiệu ở tiêu đề được xét trước thân bài.
   - `work_mode_jd_strong` = true khi tín hiệu nằm ở tiêu đề hoặc đến từ mẫu có số ngày cụ thể (WH4, WH5).
5. **`work_mode_conflict`** = true khi raw và JD đều có và khác nhau.
6. **`employment_type_raw`:**
   - Map `raw_employment_type`. Giá trị nhiều phần (jobsgo, careerviet) giữ hết ở `employment_types_raw`; giá trị chính là phần đầu sau khi bỏ "Remote".
   - vietnamworks mã 5, 6 và "Khác" → null.
7. **`employment_type_jd`:** EI1 (tiêu đề có intern / thực tập sinh / trainee), EP*, EC*, EF1. Thứ tự ưu tiên: internship > part_time > contract > full_time.
8. **`employment_type_conflict`** = true khi raw và JD đều có, khác nhau, và JD không phải full_time.
9. **Kinh nghiệm từ JD:**
   - Cụm `tiền tố? + số/khoảng + đơn vị`, có từ ngữ cảnh (kinh nghiệm, experience, …) trong cửa sổ 6 từ, và không có cụm nhiễu (lương, thưởng, hợp đồng, thành lập, thử việc, …).
   - Tháng đổi ra năm (chia 12); "dưới N" → 0–N; bỏ giá trị > 20 năm.
   - Lấy cụm đầu tiên trong `requirements_clean`; không có thì cụm đầu tiên trong `description_clean`.
   - Không có cụm số thì xét cụm "0 năm" ("không yêu cầu kinh nghiệm", "mới tốt nghiệp", "fresh graduate", "sinh viên năm cuối", …) → 0, `exp_jd_kind` = `jd_zero`.
10. **Bước 03 không chọn giá trị cuối.** Bước 04 chọn theo các quyết định đã duyệt:

| Khái niệm | Luật chọn ở bước 04 |
|---|---|
| `work_mode` | `work_mode_raw`. Nếu lệch và `work_mode_jd_strong` thì lấy `work_mode_jd`. Nếu raw trống thì lấy `work_mode_jd`. Nếu cả hai trống thì suy theo địa điểm (N14). Không suy được thì `unknown` |
| `employment_type` | raw, trừ khi tiêu đề có Intern (EI1) thì lấy internship. Raw trống thì lấy JD |
| `exp_min_years` | itviec: JD trước, ô JSON-LD làm dự phòng. 7 nguồn còn lại: ô của sàn trước, JD bù chỗ trống. Gắn `exp_source` = `raw` / `jd` / `jd_zero` / `itviec_jsonld` và `exp_conflict` khi ô và JD lệch ≥ 1 năm |

**Số đo lần chạy lại 19/11** (bảng 03, 3.997 tin):

| Khái niệm | Số đo |
|---|---|
| `work_mode` | Ô của sàn có ở 2.188 tin. JD có ở 101 tin (70 tín hiệu mạnh), thêm 54 tin ô trống. 10 tin lệch ô ↔ JD (7 tín hiệu mạnh). Còn 1.755 tin cần bước 04 suy |
| `employment_type` | JD có ở 248 tin (thực tập 190). 154 tin lệch ô ↔ JD, phần lớn là tin thực tập mà ô ghi toàn thời gian |
| `exp_min_years` | JD có ở 3.069 tin (182 là "không yêu cầu kinh nghiệm"). JD bù 219 tin ô trống (topdev 90, itviec 57, vietnamworks 40, careerviet 17, glints 9, topcv 4, jobsgo 2). itviec có JD ở 591 tin, bước 04 lấy JD trước |
| `employment_type` vào Silver? | Cả ô và JD đều trống ở 259 tin (topdev 164, vietnamworks 54, itviec 22, …). Người dùng chốt 18/11: vẫn đưa vào Silver, null khi không biết (spec 05 mục 4.4) |

## 3. Quy trình xử lý

Thứ tự trong `process_source`, cho từng dòng. Các mục **[mới]** thêm ngày 18/11.

1. **T1**: null trá hình ở mọi cột `raw_*`.
2. **T6**: làm sạch tiêu đề, mô tả, yêu cầu → `*_clean`, `*_norm`, `*_fold`.
3. Nhận ngôn ngữ: `detect_lang(description_clean)` → `language`, `language_conf`; `language_rule` để đối chiếu.
4. **T6b**: `translate_fields(desc, req, lang)`. Tin `vi` → `not_needed`; không có `--translate` → `not_run`. Ghi `*_vi`, `*_vi_norm`, `*_vi_fold`, `translated_by`, `translation_status`, `translation_chunks`.
5. **T2**: `parse_salary_cascade(raw_salary_text, title, desc)` → các cột lương, `salary_source`, cờ.
6. **T3**: `process_dates(raw_posted_date, raw_deadline, crawled_at)` → `posted_date`, `deadline_date`, cờ. **[mới] T3b**: `posted_month`.
7. **T4**: `parse_experience(raw_experience_text)` → `exp_min_years`, `exp_max_years`.
8. **T5**: `parse_headcount`.
9. **[mới] T6.5**: `benefits_clean` = NFC của từng item trong `benefits_list`.
10. **T7**: `extract_skills(skills_list, văn bản gốc, company_name)`, `extract_benefits(benefits_clean, desc)`.
11. **T8**: `parse_locations(working_locations, raw_location_text, company_address)`.
12. **[mới] T9a, T9b, T9c**: `jd_extractor.extract(rec)` → các cột ở mục 2.2.
13. Gom `flags`. Sau khi xong mọi dòng: đăng ký luật, đo độ phủ, `extra.language_distribution`, `extra.text_quality`; với T9 thêm `extra.jd_extraction` (số theo luật và nguồn, số tin lệch).
14. `run`:
    - đọc `02_integration/all.parquet`, chia theo nguồn;
    - chỉ tạo `make_context(4, cache)` khi có `--translate` và không phải dry-run;
    - `check_conserved` cho từng nguồn và tổng;
    - ghi `03_transformation/all.parquet`.

## 4. Input → Output

| | Đường dẫn | Số dòng 18/11 |
|---|---|---|
| Input | `data/preprocessing/02_integration/all.parquet` (30 cột) | 3.997 |
| Output | `data/preprocessing/03_transformation/all.parquet`: giữ 30 cột của 02, thêm 52 cột (82 cột), gồm 15 cột của T3b, T6.5, T9 | 3.997 |
| Cache dịch | `data/preprocessing/translation/translations_cache.jsonl` (khóa `k` = hash văn bản, `v` = bản dịch) | — |
| Report | `reports/preprocessing/03_transformation/`; `extra.language_distribution`, `extra.text_quality`, `extra.language` (sha256 model `7e69ec54…`) | — |

**Cột thêm** và độ phủ lần chạy thật 18/11 (toàn bảng):

| Cột | Luật | Độ phủ |
|---|---|---|
| `description_clean`, `requirements_clean`, `job_title_clean` (+ `_norm`, `_fold`) | T6 | 100% |
| `language`, `language_conf`, `language_rule` | T6 | 100% |
| `description_vi`, `requirements_vi` (+ `_vi_norm`, `_vi_fold`), `translated_by`, `translation_status`, `translation_chunks` | T6b | `not_needed` 2.883, `translated` 914, `failed` 200 |
| `salary_min_vnd` / `salary_max_vnd` | T2 | 40,2% / 44,6% |
| `is_negotiable` | T2 | 2.443 tin thỏa thuận |
| `salary_currency_raw`, `salary_period_raw`, `salary_source` | T2 | `header` 2.052, `title` 20, `jd` 5, `none` 2.418 |
| `salary_suspect` | T2f | 13 tin |
| `posted_date` / `deadline_date` | T3 | 64,5% / 94,6% |
| `posted_month` | T3b | 100%: 2026-09 886, 2026-10 3.091, 2026-11 20 |
| `exp_min_years` / `exp_max_years` | T4 | 90,8% / — |
| `headcount` | T5 | 60,0% |
| `benefits_clean` | T6.5 | 4.439 tin có phúc lợi |
| `skills_clean` / `benefits_std` | T7 | 92,7% / 92,7% |
| `locations` | T8 | 99,7% |
| `work_mode_raw`, `work_mode_jd`, `work_mode_jd_rules`, `work_mode_jd_strong`, `work_mode_conflict` | T9a | ô 54,9%, JD 2,4% |
| `employment_type_raw`, `employment_types_raw`, `employment_type_jd`, `employment_type_conflict` | T9b | ô 93,0%, JD 6,5% |
| `exp_min_years_jd`, `exp_max_years_jd`, `exp_jd_kind`, `exp_jd_text` | T9c | 75,2% |
| `flags` | nhiều luật | — |

**Độ phủ theo nguồn** (%):

| Nguồn | salary_min | posted_date | exp_min | skills_clean | benefits_std | locations |
|---|---|---|---|---|---|---|
| careerviet | 27,5 | 97,8 | 89,5 | 80,2 | 91,2 | 98,5 |
| glints | 61,7 | 100 | 90,3 | 96,8 | 79,2 | 100 |
| itviec | 24,2 | 96,8 | 87,7* | 100 | 92,9 | 100 |
| jobsgo | 54,3 | 99,6 | 99,8 | 63,5 | 94,1 | 99,8 |
| topcv | 48,9 | 6,7** | 99,5 | 86,7*** | 97,2 | 99,5 |
| topdev | 25,4 | 32,3 | **27,9** | 89,6 | 92,5 | 100 |
| vieclam24h | 92,0 | 100 | 100 | 100 | 95,7 | 100 |
| vietnamworks | 23,9 | 100 | 85,0 | 100 | 88,5 | 99,9 |

\* Ô kinh nghiệm của itviec là mức gom 10/37/61 tháng, không phải yêu cầu thật (T9c).

\*\* TopCV có `date_posted` từ 18/11 (L-50), nhưng chỉ ở một phần tin; `posted_month` vẫn đủ 100% nhờ lần cào đầu.

\*\*\* Giảm từ 97,6% vì nhãn ngành TopCV không còn lọt vào kỹ năng (L-50). Kỹ năng sẽ lấy từ bước 08 với từ điển mới (K8.9).

## 5. Dữ liệu mẫu

### 5a. Tin mẫu `topcv_2325743` (bảng 03 lần chạy thật 18/11, có dịch)

| Cột | Trước (02) | Sau (03) | Luật |
|---|---|---|---|
| lương | `raw_salary_text` "400 - 900 USD" | `salary_min_vnd` 10.160.000, `salary_max_vnd` 22.860.000, `salary_currency_raw` USD, `salary_source` header | T2 (400 × 25.400; 900 × 25.400) |
| kinh nghiệm | `raw_experience_text` "1 năm" | `exp_min_years` 1,0 | T4 |
| ngày | `raw_posted_date` null, `raw_deadline` "20/11/2026" | `posted_date` null, `deadline_date` 2026-11-20 | T3 |
| tháng đăng | — | **[T3b]** `posted_month` "2026-10" (từ `first_crawled_at` 2026-10-20T18:44Z, tức 21/10 01:44 giờ Việt Nam) | T3b |
| ngôn ngữ | — | `language` en, `translation_status` translated (có `description_vi`, `requirements_vi`) | T6, T6b |
| kỹ năng | `skills_list` rỗng (nhãn "IT - Phần mềm", "Tài chính" đã chuyển sang `category_tags` ở 02, L-50) | `skills_clean` 16 mục: Agile/Scrum, Azure, CI/CD, Docker, Git, JavaScript, Kafka, Kubernetes, Linux, NoSQL, Python, REST API, Ruby, SQL, TypeScript, Vue | T7, chỉ bản gốc |
| phúc lợi | 7 item tiếng Anh | `benefits_std` ["Lương tháng 13", "Đào tạo"] | T7: 5/7 item tiếng Anh không khớp từ điển (PRE-41) |
| địa điểm | `working_locations` ["Hà Nội: Số 3 Lê Văn Hưu, Phường Hai Bà Trưng (…)"] | `locations` [{`tinh_thanh` "TP. Hà Nội", `phuong_xa` "Phường Hai Bà Trưng", …}] | T8 |
| kinh nghiệm từ JD | — | **[T9c]** `exp_min_years_jd` 1,0, `exp_jd_kind` jd (khớp ô) | T9c |
| work mode | `raw_work_mode` "Làm việc tại văn phòng / Onsite" | **[T9a]** `work_mode_raw` onsite; `work_mode_jd` null; `work_mode_conflict` false | T9a |
| loại hình | `raw_employment_type` "Toàn thời gian" | **[T9b]** `employment_type_raw` full_time; `employment_type_jd` null | T9b |

### 5b. Ví dụ theo luật

Lấy từ report và từ trang `jd_dictionary.html`.

| Luật | Tin | Trước | Sau |
|---|---|---|---|
| T2 | glints `00b4d332…` | "₫8.500.000-9.000.000/Tháng" | 8.500.000 – 9.000.000 VND (header) |
| T4 | glints `00151110…` | "1 - 3 năm kinh nghiệm" | 1,0 – 3,0 |
| T7 | glints `00151110…` | `skills_list` null | `skills_clean` ['AWS', 'Azure'] (rút từ JD) |
| T8 | glints `00151110…` | "Quận Một" | {`dia_chi_cu_the` "Tầng 17, tòa nhà Saigon …", …} |
| T9a | itviec "Remote - QA Engineer (Games)" | `raw_work_mode` "Tại văn phòng" | `work_mode_raw` onsite, `work_mode_jd` remote (WR1, tiêu đề), `strong` true, `conflict` true → 04 chọn remote |
| T9a | glints "System/ Network Administration … French Speaking" | `raw_work_mode` "Làm tại công ty / Onsite" | JD "Work from home 2 days/ week." (WH4) → `work_mode_jd` hybrid, `strong` true → 04 chọn hybrid |
| T9b | itviec "Oracle Consultant Intern" | `raw_employment_type` FULL_TIME | `employment_type_jd` internship (EI1), `conflict` true → 04 chọn internship |
| T9c | topdev "Chuyên viên cao cấp an ninh mạng" | `raw_experience_text` null | `exp_min_years_jd` 5,0 từ "Có tối thiểu 5 năm kinh nghiệm trong lĩnh vực an ninh mạng…" |
| T9c | itviec "Product Owner" | ô JSON-LD "3.1 năm (37 tháng)" → 3,0 | `exp_min_years_jd` 5,0 từ "5+ years of professional experience as a Product Owner…" → 04 chọn 5,0 (itviec lấy JD trước) |
| T9c | itviec "Thực tập sinh DEV" | ô trống | `exp_jd_kind` jd_zero, 0,0, từ "Sinh viên năm 4, hoặc mới tốt nghiệp…" |

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Cách | Ngưỡng | Kết quả 18/11 |
|---|---|---|---|
| Luật bảo toàn | `checks.rows_conserved` | vào = ra | Đạt (3.997) |
| Chất lượng chữ | `extra.text_quality.residual_*_pct` | HTML 0%, NFD 0%, ký tự ẩn 0% | Đạt |
| Parser lương, kinh nghiệm, ngày, địa điểm | 50 chuỗi thật mỗi parser, gán tay | ≥ 95% | Chưa đo |
| Bản dịch | 50 JD (`scripts/build_translation_review_sample.py`): kỹ năng và số liệu không đổi | 0 lỗi đổi số | Chưa kiểm (PRE-33) |
| T9 | `scripts/review_jd_dictionary.py` sau khi chạy; đọc tay mọi ca lệch | Đọc 100% ca lệch | Bản nháp: 9/11 ca lệch work_mode thì JD đúng. Lần chạy lại 19/11: 10 ca lệch work_mode, 154 ca lệch loại hợp đồng, chưa đọc tay |
| Test | `pytest tests/unit/test_transformation_step.py` (có test T3b, T6.5, T7, T9) | Xanh | Xanh |
| Trang | `docs/presentation/preprocessing_steps/03_transformation.html` | Có | Có |

## 7. Trạng thái, chỗ thiếu, việc mở

- **Trạng thái:**
  - Có code cho T1–T9. Chạy thật 18/11 có dịch (`--translate`, GPU Quadro T1000), từ 09:43 đến 18:57.
  - Bản dịch lưu ở cache (`translations_cache.jsonl`, 23.281 dòng): chạy lại 03 sau khi làm lại bộ lọc IT chỉ phải dịch tin mới.
- **Chỗ thiếu so với bảng Silver:**

| Chỗ thiếu | Số liệu | Luật xử lý |
|---|---|---|
| ~~Không có `posted_month`~~ | Xong: 100% | T3b |
| `work_mode` chỉ dựa vào ô của 3 sàn | Ô 54,9%, JD thêm 55 tin; 1.974 tin còn trống | T9a + 04 suy |
| Kinh nghiệm thiếu hoặc sai ở topdev, itviec | topdev 27,9% ô; JD bù 111 tin topdev; itviec có JD 612 tin | T9c + 04 |
| ~~Kỹ năng lẫn nhãn ngành TopCV~~ | Xong ở 02 (L-50) | — |
| Phúc lợi tiếng Anh không khớp từ điển; glints 74,4% | — | PRE-41 (người dùng đã duyệt mở rộng từ điển) |
| ~~Kỹ năng bị rút cả từ bản dịch~~ | Xong | T7 (sửa) |
| ~~Phúc lợi chưa NFC~~ | Xong: 960 tin được sửa (19/11) | T6.5 |
| Tin dịch `failed` | 200/1.114 (18,0%, giữ bản gốc tiếng Anh, 19/11). Lần 18/11: 209/1.193; lần 10/11: 222/1.274. Model làm rơi "+" trong "5+ years" (chưa đo lại) | PRE-34 |

- **Việc mở:** PRE-33, PRE-34, PRE-35, PRE-37, PRE-40, PRE-41.
