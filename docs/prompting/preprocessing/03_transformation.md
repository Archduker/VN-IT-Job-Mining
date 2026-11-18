# Prompt 03: Transformation (dịch EN→VI, `posted_month`, trích JD theo từ điển đã duyệt)

> Đặc tả: [`docs/spec/preprocessing/03_transformation.md`](../../spec/preprocessing/03_transformation.md), mục 2.2–2.3 là luật mới. Từ điển: `preprocessing/dictionaries/jd_extraction.json` (`approved: true`, 18/11).
> **Trạng thái:** viết ngày 18/11/2026, **chờ người dùng duyệt** cùng đặc tả (bước 1–2 của quy trình). Chưa viết code luật mới.

## 1. Ngữ cảnh

**Đọc trước:**

- Đặc tả bước 03 (mục 2.2 bảng luật mới, mục 2.3 cách áp T9, mục 7 chỗ thiếu).
- `jd_extraction.json` (mẫu, cụm nhiễu, `decisions`).
- Trang đo `docs/presentation/preprocessing_steps/jd_dictionary.html`.
- `preprocessing/CLAUDE.md`: chỉ 2 model; khớp theo từ nguyên vẹn; ranh giới 03.
- Code: `preprocessing/transformation/run.py`, `skill_extractor.py`, `date_parser.py`; `preprocessing/common/text_clean.py`; `scripts/review_jd_dictionary.py` (bản đo, có sẵn logic áp mẫu để tái dùng); `tests/unit/test_transformation_step.py`.

**Vì sao làm:**

- Người dùng: "bước 03 phải có công việc dịch nữa", "xác định các thành phần có thể trích xuất từ JD", "làm cách A … kết hợp từ việc bạn sẽ đọc hết các jd rồi lấy ra hết toàn bộ từ điển".
- Bảng Silver cần `posted_month`, `work_mode`, `exp_min_years`; bước 02 không đủ dữ liệu cho các trường này (đặc tả 02 mục 7).

**Số liệu hiện tại** (bảng 03 ngày 18/11, chưa dịch):

| Trường | Hiện trạng |
|---|---|
| `posted_month` | Chưa có |
| `work_mode` | Ô của sàn chỉ có ở 2.559 tin |
| `exp_min_years` | topdev 28,2%; itviec là mức gom 10/37/61 tháng |
| Bản dịch | 1.274 tin tiếng Anh `not_run`; lần dịch có `--translate` đang chạy nền (cache `data/preprocessing/translation/translations_cache.jsonl`) |

## 2. Việc cần sửa

**Input:** `data/preprocessing/02_integration/all.parquet` (30 cột).

**Output:**

- `data/preprocessing/03_transformation/all.parquet` (67 + 15 cột);
- `reports/preprocessing/03_transformation/`;
- trang `03_transformation.html`;
- `docs/spec/preprocessing/samples/03_transformation.json`.

**Các việc:**

1. **T3b** trong `run.py`, sau T3:
   - `posted_month` = `posted_date[:7]` nếu có;
   - nếu không: tháng của `first_crawled_at` đổi sang UTC+7 (`zoneinfo` "Asia/Ho_Chi_Minh").
2. **T6.5**:
   - `benefits_clean` = [NFC, bỏ ký tự ẩn, gộp khoảng trắng cho mỗi item của `benefits_list`, bỏ item rỗng];
   - `extract_benefits` đọc `benefits_clean`;
   - dùng lại `text_clean` (không viết hàm NFC mới).
3. **T7 (sửa)**:
   - `extract_skills` nhận văn bản **gốc** (`description_clean` + `requirements_clean`), không nối `*_vi`;
   - bỏ dòng `combined_text = f"{combined_text} {tr['description_vi']…}"` khỏi phần rút kỹ năng.
4. **T9**: module mới `preprocessing/transformation/jd_extractor.py`.
   - Đọc `jd_extraction.json` **một lần**; từ chối chạy nếu `_meta.approved` khác true.
   - Có 3 hàm thuần, không I/O:
     - `work_mode(rec) -> dict`;
     - `employment_type(rec) -> dict`;
     - `experience(rec) -> dict`.
   - Trả đúng các cột ở đặc tả mục 2.2.
   - Logic áp mẫu lấy từ `scripts/review_jd_dictionary.py`. Sau đó script này **import** `jd_extractor`, để chỉ còn một chỗ chứa logic.
   - Report:
     - luật `T9a`, `T9b`, `T9c` (`action` = flag, `rows_affected` = số tin có giá trị JD, kèm 3 ví dụ);
     - `extra.jd_extraction` = số theo mẫu × nguồn, số tin lệch, phân bố `work_mode_raw` / `work_mode_jd`.
5. Khi lần dịch chạy xong:
   - chép cache dịch sang chỗ được lưu trong git (hỏi người dùng chỗ để: đề xuất `data/preprocessing/gold/translation/translations_cache.jsonl`, force-add như `it_review`);
   - chạy `scripts/mine_jd_phrases.py` trên cột `*_vi`, báo những cách viết tiếng Việt mà từ điển chưa có.
6. Chạy lại 03 có `--translate`. Cache đã đủ nên không dịch lại; chạy nhanh.

## 3. Pseudo code

```text
D = load(jd_extraction.json); assert D._meta.approved

for rec in 02:
    T1 ; T6 (clean title/desc/req) ; lang = fastText(desc)
    T6b translate (nếu --translate; cache)
    T2 lương ; T3 ngày
    T3b posted_month = month(posted_date) or month(to_vn_tz(first_crawled_at))
    T4 kinh nghiệm (ô của sàn) ; T5 headcount
    T6.5 benefits_clean = [nfc_clean(b) for b in benefits_list if b]
    T7 skills = extract_skills(skills_list, desc_clean + req_clean, company)   # chỉ bản gốc
       benefits_std = extract_benefits(benefits_clean, desc_clean)
    T8 locations
    T9:
      title = job_title_clean ; body = sentences(desc_clean) + sentences(req_clean)
      wm_raw = map(raw_work_mode) or hint(raw_employment_type, nguồn)
      hits   = [mẫu khớp (sau khi xóa cụm nhiễu) trên title, rồi body]
      wm_jd  = resolve(hits)  ; strong = any(hit ở title or id ∈ {WH4, WH5})
      conflict = wm_raw and wm_jd and wm_raw != wm_jd
      et_raw, et_list = map(raw_employment_type) ; et_jd = first(internship>part_time>contract>full_time)
      exp_jd = first_match(req) or first_match(desc) or zero_phrase → (min, max, kind, text)
check_conserved ; ghi parquet ; report T9a/T9b/T9c + extra.jd_extraction
```

## 4. Ràng buộc

- **Không bỏ dòng, không chọn giá trị cuối** cho `work_mode`, `employment_type`, `exp_min_years`. Việc chọn là của bước 04.
- Không ghi đè `raw_*` hay `exp_min_years` (T4).
- Không dùng model nào ngoài fastText `lid.176` và envit5 (revision `840bc881`). T9 là regex và từ điển.
- Không sửa `jd_extraction.json` mà không hỏi người dùng. Thấy mẫu sai trên dữ liệu thật thì báo, kèm ví dụ.
- Khớp theo từ nguyên vẹn; đọc bản gốc, không đọc bản dịch (T7, T9).
- Không đẩy R2. Không bật scheduler. Không xóa cache dịch. Không push.
- Test dùng câu thật lấy từ dữ liệu, ghi `job_id` trong chú thích.

## 5. Ví dụ (thành test trong `tests/unit/test_transformation_step.py`)

| Đầu vào (câu thật) | Kết quả mong đợi |
|---|---|
| `posted_date` null, `first_crawled_at` 2026-10-20T18:44:44Z (`topcv_2325743`) | `posted_month` "2026-10" |
| `posted_date` null, `first_crawled_at` 2026-10-31T18:30:00Z | "2026-11" (01/11 01:30 giờ Việt Nam) |
| `posted_date` 2026-09-29 (itviec) | "2026-09" |
| `benefits_list` có item dạng NFD "Bảo hiểm" | `benefits_clean` NFC |
| `--translate`, JD tiếng Anh có "Kafka", bản dịch thêm từ nào đó trùng tên kỹ năng | `skills_clean` chỉ chứa kỹ năng có trong bản gốc |
| itviec, tiêu đề "Remote - QA Engineer (Games)", `raw_work_mode` "Tại văn phòng" | `work_mode_raw` onsite, `work_mode_jd` remote, `strong` true, `conflict` true |
| glints, thân "Work from home 2 days/ week.", raw "Làm tại công ty / Onsite" | `work_mode_jd` hybrid (WH4), `strong` true |
| topcv, "Có kinh nghiệm triển khai SOC trên On-Premise, Cloud hoặc Hybrid." | `work_mode_jd` null (cụm nhiễu, WH7 không khớp) |
| vietnamworks, "Ứng viên có thể chọn địa điểm làm việc tại nhà máy Hà Nội" | `work_mode_jd` null ("tại nhà máy" không phải "tại nhà") |
| itviec "Linh hoạt" | `work_mode_raw` hybrid |
| jobsgo `raw_employment_type` "Toàn thời gian, Remote" | `employment_type_raw` full_time, `employment_types_raw` ["full_time"], `work_mode_raw` remote |
| itviec "Oracle Consultant Intern", FULL_TIME | `employment_type_jd` internship, `conflict` true |
| jobsgo "Tư Vấn Triển Khai Phần Mềm Website Fulltime (Không Hỗ Trợ Mộc Thực Tập)" | `employment_type_jd` không phải internship (cụm nhiễu "mộc thực tập") |
| "Có tối thiểu 5 năm kinh nghiệm trong lĩnh vực an ninh mạng…" | `exp_min_years_jd` 5,0, `kind` jd |
| "5+ years of professional experience as a Product Owner…" | 5,0 |
| "Có từ 0-1 năm kinh nghiệm trong lĩnh vực An toàn thông tin…" | min 0,0, max 1,0 |
| "Review lương định kì vào tháng 3 hàng năm…" (có "năm", không có ngữ cảnh kinh nghiệm) | null |
| "Sinh viên năm 4, hoặc mới tốt nghiệp trong lĩnh vực lập trình." | 0,0, `kind` jd_zero |
| `jd_extraction.json` có `approved` false | `jd_extractor` báo lỗi rõ ràng |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit/test_transformation_step.py -q`, rồi `make test-fast` | Xanh |
| Dry-run | `python scripts/run_preprocessing.py --step transformation --source glints --dry-run`, rồi `--source all --dry-run` | Bảo toàn; T9 có số |
| Số T9 so với bản đo | `python scripts/review_jd_dictionary.py` (đã import `jd_extractor`) | Trùng số đã duyệt: lệch work_mode 12, Intern lệch 180, JD bù kinh nghiệm 257 (lệch thì giải thích) |
| Đọc tay | Mọi ca `work_mode_conflict`, 30 ca T9c ngẫu nhiên (seed 42) | Người dùng đồng ý |
| `posted_month` | Độ phủ 100%; phân bố theo tháng × nguồn | Tháng 9 chỉ có ở nguồn ghi ngày đăng (spec 05 mục 4.2) |
| Bản dịch | `translation_status` theo nguồn; số `failed`; 50 JD (`scripts/build_translation_review_sample.py`) | Ghi số; so với 222 `failed` lần 10/11 (PRE-34) |
| Chạy thật | `python scripts/run_preprocessing.py --step transformation --source all --translate` | 4.671 → 4.671 |
| Trang và mẫu | `visualize_preprocessing_steps.py --step 03_transformation`; `build_step_samples.py --step 03_transformation` | Có; tin mẫu có `posted_month` 2026-10 |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| — | Chạy 03 không dịch (trước khi có luật mới) | 18/11 | Chạy thật trên bảng 02 đã sửa: 4.671 → 4.671. Trang `03_transformation.html`. Thấy thiếu `posted_month`, `work_mode`, kinh nghiệm topdev | `ee7d7ac` |
| — | Lập từ điển (phương án A + Claude đọc JD) | 18/11 | `scripts/mine_jd_phrases.py` gom câu ứng viên; Claude đọc và lập mẫu; đo bằng `scripts/review_jd_dictionary.py`. Người dùng duyệt 7 quyết định: "1. đúng rồi 2. oke 3. oke luôn 4. có 5. giữ ô sàn 6. nếu trích xuất ra được 100% thì sẽ thêm vào" | `d5039db`, `adaa693` |
| — | Dịch | 18/11 | Cài torch 2.14.1+cu130 (Quadro T1000 4 GB). Chạy `--translate` nền từ 07:42; khoảng 64 dòng/phút trên 24.670 dòng | — |
| 1 | Duyệt đặc tả | chưa | Đặc tả 03 mục 2.2–2.3 | — |
| 2 | Duyệt prompt | chưa | Prompt này | — |
| 3 | Test rồi code | chưa | | |
| 4 | Dry-run | chưa | | |
| 5 | Review, chạy thật | chưa | | |
