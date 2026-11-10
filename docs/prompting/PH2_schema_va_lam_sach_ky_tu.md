# Prompt PH2: đồng nhất schema (bước 02) và làm sạch ký tự (bước 03, T6)

> **Đã chốt và đã thực hiện (10/11/2026).** Quyết định ở mục 0 của spec PH2 ghi đè mọi "[ĐỀ XUẤT]" bên dưới: C0 (làm sạch ở 03), C7 (giữ tên cột cũ, thêm `*_norm`/`*_fold`), C3/C4/C13 (regex sửa, bullet chuẩn `- ` gồm `+`, lặp bước khi còn HTML/NFD tối đa 3 lần rồi cảnh báo, không dừng), C2 (`job_title` rỗng bị loại ở 02, I6), C10 (từ điển viết tắt chỉ có mục `approved=false` cho tới khi duyệt). Code: `preprocessing/common/text_clean.py`, `integration/schema.py`, các sửa trong `html_cleaner.py`, `json_flattener.py`, `integration/run.py`, `transformation/run.py`; test `tests/unit/test_text_clean.py`, `test_integration_step.py`.

## 1. Ngữ cảnh

Đọc trước:
- `docs/spec/preprocessing/spec/PH2_schema_va_lam_sach_ky_tu.md` (nháp, mục 2 là hiện trạng đã đo; mục 4-5 là luật).
- `Tiền xử lý dữ liệu JD ngành IT cho Data Mining.md` bước 1, 2, bảng 3.3, mục 3.2, 4.3.
- `docs/spec/preprocessing/spec/P0_pipeline_contract.md` (mục 4 schema báo cáo, mục 7 ranh giới), `P2_integration.md`, `P3_transformation.md` (T6).
- Code: `preprocessing/integration/run.py`, `preprocessing/integration/json_flattener.py` (`flatten_raw_job_record`), `preprocessing/transformation/run.py` (`_clean_text_field`, `_clean_job_title`), `html_cleaner.py`, `bullet_stitcher.py`, `preprocessing/deduplication/text_norm.py` (`fold`), `preprocessing/common/step_report.py`.

Hiện tại (đã đo 10/11/2026 trên `data/preprocessing/01_clean/*.jsonl`, 5.077 tin):
- Bước 02: dòng JSON hỏng bị **giữ** thành dòng giả (spec nói phải drop); không có pydantic; không có `rejected/`; lỗi trong `_flatten_<nguồn>` bị nuốt; id dự phòng dùng `hash()` không tái lập.
- Bước 03: `description_clean/requirements_clean` 0 tin còn HTML, nhưng 42 tin còn NFD (topdev 5, careerviet 16, glints 21), 5 tin còn ký tự ẩn, chưa chuẩn hóa gạch ngang/bullet, chưa có `*_norm`, `*_fold`, chưa có từ điển viết tắt.
- `strip_html_tags` có 3 lỗi: nuốt đoạn giữa `<` và `>` thường (`"AC <-> test case"` mất `<->`), để lại `&nbsp;` khi mã hóa hai lần, cắt đôi từ khi gặp thẻ inline (`<b>Java</b>Script`).

## 2. Việc cần sửa

**A. Bước 02 Integration**
1. `preprocessing/integration/schema.py` (mới): model pydantic `JobRecord` theo spec mục 4.2 (khóa bắt buộc: `job_id_global` có tiền tố `<source_platform>_`, `source_platform` thuộc `SOURCES`, `source_job_id`, `source_url`, `crawled_at` parse được ISO; còn lại tùy chọn, đúng kiểu).
2. `json_flattener.py`: thêm tham số `strict: bool = False` cho `flatten_raw_job_record` (True thì không nuốt lỗi `_flatten_<nguồn>`); thay `abs(hash(source_url))` bằng `hashlib.sha1(...).hexdigest()[:16]`. Các nơi gọi khác (`clean/run.py`, `deduplication/run.py`, `run_integration.py`, `scripts/build_gold_sample.py`) không đổi.
3. `integration/run.py`: dòng JSON hỏng (I0), lỗi làm phẳng (I7), lỗi schema (I6) đều đi vào `rejected` và là luật **drop**; bỏ đoạn dựng dòng giả. Ghi `data/preprocessing/rejected/02_integration/<nguồn>.jsonl` (chạy thật, ghi đè theo nguồn, xóa file cũ nếu không còn dòng; dry-run không ghi). Cập nhật `checks.notes` với số `job_id_global` trùng trong `all.parquet` (chỉ báo).
4. Giữ tên `_flatten_<nguồn>` (spec C1 [ĐỀ XUẤT]).

**B. Bước 03 Transformation (T6)**
1. `preprocessing/common/text_clean.py` (mới): `clean_text(raw) -> str | None`, `make_text_columns(raw) -> (clean, norm, fold)`, `html_residual(s) -> bool`, `is_nfc(s) -> bool`. Import `fold` từ `preprocessing.deduplication.text_norm`, không viết bản thứ bảy.
2. `html_cleaner.strip_html_tags`: sửa 3 lỗi ở mục 1 (regex thẻ chỉ coi `<` là thẻ khi theo sau là chữ cái, `/`, `!`; thẻ khối thành xuống dòng, thẻ inline bỏ không chèn khoảng trắng; `unescape` lặp tối đa 2 lần). Giữ chữ ký hàm vì flattener và tests đang gọi.
3. `transformation/run.py`: `_clean_text_field` gọi `clean_text` (thứ tự: bóc HTML → unescape → NFC → ký tự ẩn → gạch ngang → bullet → khoảng trắng → `stitch_fragmented_bullets`); thêm cột `description_norm`, `description_fold`, `requirements_norm`, `requirements_fold`, `job_title_fold` [ĐỀ XUẤT: không đổi tên cột cũ]; `_clean_job_title` dùng chung bước NFC/ký tự ẩn/khoảng trắng.
4. `preprocessing/dictionaries/abbreviations.json` (mới) **chỉ chứa các mục bạn đã duyệt** (spec C10). Áp dụng cho `*_norm` theo từ nguyên vẹn; viết tắt dễ nhầm khớp phân biệt hoa thường. Nếu chưa có danh sách được duyệt, tạo file `{}` và chỉ viết hàm + test bằng từ điển nhỏ dựng trong test.
5. Báo cáo: các luật `T6.1` (HTML), `T6.2` (NFC), `T6.3` (ký tự ẩn), `T6.4` (gạch ngang/bullet) kiểu `modify` kèm số tin; `extra.text_quality` = `residual_html_pct`, `residual_nfd_pct`, `residual_hidden_char_pct` tính trên cột đầu ra, theo nguồn và `_all`. HTML hoặc NFD > 0 thì dừng bước (spec C13 [ĐỀ XUẤT]); ký tự ẩn > 0 chỉ ghi `checks.notes`.

## 3. Pseudo code

```text
# 02 integration
process_source(source, dry_run):
    rows, rejected = [], []
    for line_no, line in enumerate(đọc jsonl, 1):
        if dòng rỗng: continue
        n_in += 1
        try: env = json.loads(line)
        except JSONDecodeError as e: rejected.append(rej("I0","JSON_INVALID",line_no,line)); continue
        try: flat = flatten_raw_job_record(env, source, strict=True)
        except Exception as e: rejected.append(rej("I7", f"FLATTEN_ERROR: {type(e).__name__}", ...)); continue
        rec = dựng 28 cột như hiện tại (I2-I5 giữ nguyên)
        try: JobRecord.model_validate(rec)
        except ValidationError as e: rejected.append(rej("I6", "SCHEMA: " + ",".join(loc đầu của từng lỗi), ...)); continue
        rows.append(rec)
    report.set_io(in_file, n_in, OUT_FILE, len(rows))
    cho mỗi rule I0/I6/I7: report.rule(id, tên, "drop", số, ví dụ[:3] KHÔNG chứa raw_line)
    if not dry_run: ghi rejected jsonl (hoặc xóa file cũ nếu rỗng)
    report.check_conserved()          # n_in == len(rows) + len(rejected)

# 03 transformation, trong vòng lặp từng bản ghi (thay _clean_text_field)
clean_text(raw):
    if raw rỗng: return None
    s = strip_html_tags(raw)                      # đã sửa: thẻ khối -> \n, inline -> "", "<" chỉ là thẻ khi theo sau là chữ cái, "/", "!"
    s = unicodedata.normalize("NFC", s)
    s = s.translate(xóa \u200b \u200c \u200d \u2060 \ufeff)
    s = thay \xa0 \u2000-\u200a \u202f \u205f \u3000 bằng " "
    s = thay – — − ‐ ‑ ‒ bằng "-"
    s = với mỗi dòng: nếu bắt đầu bằng • ✔ ✓ ➢ ➤ ● ▪ ▫ ○ ◦ ★ ✅ hoặc "* " hoặc "+ " thì đổi thành "- "
    s = gộp [ \t]+ thành " ", bỏ khoảng trắng đầu/cuối dòng, tối đa 1 dòng trống liên tiếp
    dòng = stitch_fragmented_bullets(s)
    return "\n".join(dòng) hoặc None

make_text_columns(raw):
    clean = clean_text(raw)
    norm  = mở_rộng_viết_tắt(clean).lower() if clean else None     # từ điển abbreviations.json
    fold  = text_norm.fold(norm) if norm else None
    return clean, norm, fold

html_residual(s): re.search(r"<\s*/?\s*[A-Za-z!][^>]*>", s) or html.unescape(s) != s
is_nfc(s): unicodedata.is_normalized("NFC", s)
```

## 4. Ràng buộc

- Không sửa raw, không sửa cột `raw_*`, không đổi tên cột đã có, không động tới R2, không cài gói, không dùng model, không commit.
- `text_clean` không xóa boilerplate (khác `text_norm.clean_text`). Không dùng lại `text_norm.clean_text` cho `text_clean` vì nó gộp xuống dòng và xóa nội dung.
- Bước 03 vẫn `rows_out = rows_in`. Bước 02: chỉ I0, I6, I7 mới bỏ dòng, mỗi dòng bỏ đều có file `rejected` và số trong báo cáo.
- Thứ tự gạch ngang → bullet → stitcher giữ như pseudo code; chuẩn hóa gạch ngang phải xảy ra trước `parse_salary_cascade` (đã đúng vì T6 chạy trước T2 trong cùng vòng lặp; không đảo).
- Không đưa `raw_line` hay nội dung JD vào `reports/` (được đưa vào git). `data/preprocessing/rejected/` không vào git.
- Test không dùng dữ liệu giả: chuỗi thật lấy từ `tests/fixtures/topdev/standard.json`, `tests/fixtures/topcv/*.html`, hoặc ghi lại từ dữ liệu trong spec mục 2.3 (ghi `job_id` nguồn trong chú thích test). Các chuỗi NFD tự dựng bằng `unicodedata.normalize("NFD", câu_thật)` là hợp lệ vì là biến đổi của chuỗi thật.
- Sửa test cũ nào khẳng định hành vi sai (dòng JSON hỏng được giữ; `strip_html_tags` thay thẻ bằng khoảng trắng) thì ghi lý do trong commit/summary.
- Sau khi xong ghi lỗi vào `docs/issue_log.md` (mã `L-` kế tiếp), nhất là 3 lỗi `strip_html_tags` và lỗi dòng JSON hỏng bị giữ.

## 5. Ví dụ (thành test)

| Đầu vào (thật) | Kết quả mong đợi |
|---|---|
| `tests/fixtures/topdev/standard.json` trường `requirements_original` (có `Y&ecirc;u cầu:`, `<li style=...>`, `\r\n`) | `text_clean` bắt đầu `"Yêu cầu:\n- Nắm vững Java Core, OOP và…"`; không còn `<`, `&` thực thể |
| `"Tư vấn – Thiết kế — Sản xuất"` (thật, `careerviet_35C32FB4`) | `"Tư vấn - Thiết kế - Sản xuất"` |
| `"phản biện cá\ufeffc thiết kế"` (thật, `topcv_2324178`) | `"phản biện các thiết kế"` |
| `"Môi trường làm việc:\u200d\n- Môi trường product"` (thật, `glints_369649a4-b509-48ad-a767-e464745bdbb0`) | `"Môi trường làm việc:\n- Môi trường product"` |
| `unicodedata.normalize("NFD", "Khám sức khỏe định kỳ")` | `is_nfc(text_clean)` True; `text_clean == "Khám sức khỏe định kỳ"` (NFC); `text_fold == "kham suc khoe dinh ky"` |
| `"giữ traceability AC <-> test case"` (thật, `topcv_2238387`) | giữ nguyên `<->`; `html_residual` False |
| `"phân tích dữ liệu & P&L; giao tiếp"` (thật, `topdev_2138377`) | không đổi; `html_residual` False |
| `"&amp;nbsp;Java"` | `"Java"` (hoặc `" Java"` sau strip → `"Java"`) |
| `"<b>Java</b>Script"` | `"JavaScript"` |
| `"Kinh nghiệm < 3 năm, lương > 10tr"` | giữ nguyên cả cụm |
| `"• Tham gia\n✔ Có 2–4 năm kinh nghiệm"` | `"- Tham gia\n- Có 2-4 năm kinh nghiệm"` |
| `text_fold("Lập trình viên C#/C++ .NET")` | `"lap trinh vien c#/c++ .net"` |
| từ điển test `{"kinh nghiệm": ["kn"], "đại học": ["đh"]}` và `"Tốt nghiệp ĐH, 2 năm kn"` | `text_clean` giữ nguyên; `text_norm == "tốt nghiệp đại học, 2 năm kinh nghiệm"` |
| `"Yêu cầu: be curious"` và `"BE Java"` (từ điển `{"backend": ["BE"]}` phân biệt hoa thường) | `"be curious"` không đổi; `"BE Java"` thành `"backend java"` |
| 02: file `jsonl` 3 dòng tốt + 1 dòng `{"hỏng":` | `n_in=4`, `output=3`, `dropped=[I0:1]`, `rejected/…jsonl` có 1 dòng, bảo toàn đúng, parquet không có dòng rác |
| 02: envelope thật với `metadata.scraped_at` xóa | I6 `SCHEMA: crawled_at`, vào rejected |
| 02: `job_id` rỗng và `source_url` giống nhau, chạy hai tiến trình khác `PYTHONHASHSEED` | cùng `job_id_global` |
| 03: 8 nguồn chạy thật | `extra.text_quality` ba chỉ số ghi được; HTML = 0 và NFD = 0 trên đầu ra, hoặc bước dừng với thông báo |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit -q` (và `tests/unit/test_text_clean.py` mới) | xanh |
| Bảo toàn 02 | `python scripts/run_preprocessing.py --step integration --source all --dry-run`, rồi chạy thật | `input = output + dropped` mọi nguồn; số `rejected` khớp số dòng file |
| Dòng giả | so `all.parquet` trước/sau sửa với 8 nguồn | không còn dòng `job_id` là số thứ tự dòng |
| Số 5.077 tin | báo cáo `_all.json` 02 | so với số đo 10/11 trong spec; nếu khác, ghi lý do (dữ liệu đổi hay luật mới loại) |
| Văn bản sau T6 | `python scripts/run_preprocessing.py --step transformation --source all` | `extra.text_quality`: HTML 0%, NFD 0%; 42 tin NFD và 5 tin ký tự ẩn về 0, ghi "trước → sau" |
| Đọc tay | 20 tin ngẫu nhiên (seed 42) cạnh nhau `raw_description_text` và `description_clean`, gồm cả careerviet, glints, topdev | không mất chữ, không dính từ, bullet đúng |
| Gạch ngang | 10 chuỗi lương thật có `–` (ví dụ glints `8.500.000 – 9.000.000 VNĐ`) qua T2 | kết quả lương không đổi so với trước hoặc tốt hơn |
| Git | `git status` | không có file dữ liệu/rejected trong git; `reports/preprocessing/` có thể đổi |
| Ranh giới | `git diff --stat` | không đụng `collection/`, R2, raw; không đổi tên cột |
