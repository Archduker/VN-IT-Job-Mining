# PH2. Đồng nhất schema và làm sạch ký tự (bước 1 và 2 của file thiết kế)

> **Đã chốt và đã code (10/11/2026)** theo mục 0 bên dưới; các mục [CẦN CHỐT] trong thân bài đã được mục 0 ghi đè. Prompt: `docs/prompting/PH2_schema_va_lam_sach_ky_tu.md`.
> **[ĐỀ XUẤT]** = mình đoán. **[CẦN CHỐT]** = mình không biết, cần bạn quyết. Số liệu dưới đây đo ngày 10/11/2026 trên `data/preprocessing/01_clean/*.jsonl` có trên máy (5.077 tin: topcv 1.561, topdev 227, vietnamworks 800, careerviet 448, vieclam24h 182, itviec 905, glints 271, jobsgo 683), chỉ đọc, bằng `flatten_raw_job_record` + `_clean_text_field` hiện tại. `data/preprocessing/02_integration/` đang trống nên chưa đo được trên đầu ra thật của bước 02.

## 0. Quyết định của bạn (10/11/2026, ghi đè phần [CẦN CHỐT] bên dưới) và kết quả code

| Mã | Quyết định | Trạng thái |
|---|---|---|
| C0 | Làm sạch ký tự ở `03_transformation` (luật T6.x); kiểm schema ở `02_integration` | Đã làm |
| C7 | Giữ `description_clean`, `requirements_clean`, `job_title_clean`; thêm `*_norm`, `*_fold` (description, requirements, job_title) | Đã làm |
| C3/C4/C13 | Bóc HTML bằng regex đã sửa (không BeautifulSoup); bullet `-`, `•`, `+`, `*` và ký hiệu tương tự đều về một bullet chuẩn `- ` (`<li>` cũng thành `- `); gạch ngang `– — − ‐ ‑ ‒` về `-`. Còn HTML hoặc NFD sau khi làm sạch thì **lặp lại** bước (tối đa `MAX_RETRIES = 3`), hết lượt chỉ ghi cảnh báo vào `checks.notes`, không dừng pipeline | Đã làm |
| C2 | `job_title` rỗng là lỗi schema: bỏ dòng, vào `rejected/02_integration` với lý do `SCHEMA: job_title` | Đã làm (dữ liệu thật: 1 tin careerviet `35C8A80A`) |
| C10 | Từ điển viết tắt: đã đếm token thật (mục 5.3.1); `abbreviations.json` chỉ chứa ứng viên với `approved=false`, code bỏ qua mọi mục chưa duyệt | Chờ bạn duyệt |

Sửa 3 lỗi đã tìm: (1) `integration/run.py` không còn giữ dòng JSON hỏng (I0 là drop, vào rejected); (2) id dự phòng dùng `sha1(source_url)[:16]` thay `hash()` (tái lập được); (3) `strip_html_tags` không còn nuốt `<->`, `&amp;nbsp;` được giải mã hai lần, thẻ inline không cắt đôi từ. `flatten_raw_job_record(..., strict=True)` ném lỗi làm phẳng (I7); mặc định giữ hành vi cũ cho các nơi gọi khác.

Kết quả đo thật (5.077 tin, dry-run, không ghi file): trước: 42 tin NFD (topdev 5, careerviet 17, glints 21), 26+ tin có ký tự ẩn, 10 tin có HTML/entity (vietnamworks 9, glints 1); sau: **0 HTML, 0 NFD, 0 ký tự ẩn** ở cả 8 nguồn. Bước 02: 5.076 ra, 1 bị loại (I6). Số trước khác bảng 2.3 vì đo mới gồm cả `job_title` và entity chưa bóc.

## 1. Mục tiêu

1. **Bước 1 (đồng nhất schema):** mỗi bản ghi ra khỏi Integration đều có khóa đúng kiểu (`job_id_global = <nguồn>_<id gốc>`, `crawled_at` hợp lệ); bản ghi hỏng không biến mất mà vào `rejected/` kèm lý do; luật bảo toàn `input = output + dropped` vẫn đúng.
2. **Bước 2 (làm sạch ký tự):** văn bản JD sạch HTML, NFC, không ký tự ẩn, gạch ngang và bullet thống nhất, kèm 3 cột `text_clean`, `text_norm`, `text_fold`. Đích theo file thiết kế: 0% còn HTML, 0% còn NFD.

Tiêu chí chất lượng chính: Consistency, Accuracy, Uniqueness (nền cho khử trùng lặp ở PH4). Không đặt số mẫu mục tiêu.

## 2. Hiện trạng đã đọc trong code (chỉ ghi phần cần thêm/sửa)

### 2.1. Bước 1

| Đã có | Ở đâu | Thiếu / lệch |
|---|---|---|
| `job_id_global = f"{source}_{id}"`, `crawled_at` lấy từ `metadata.scraped_at` | `json_flattener.py` `flatten_raw_job_record` | Không kiểm bắt buộc: `crawled_at` mặc định `""`. Đo: 0 trên 5.077 tin thiếu `crawled_at`, nhưng không có gì chặn khi thiếu |
| Mỗi nguồn một hàm `_flatten_<nguồn>` | `json_flattener.py` | Tên khác file thiết kế (`map_<nguồn>`). Xem **[CẦN CHỐT]** C1 |
| Báo cáo bước + luật bảo toàn | `preprocessing/common/step_report.py` | Đủ dùng, không sửa |
| `pydantic==2.11.3` | `requirements.txt` | Chưa có model nào trong `preprocessing/` |
| `rejected/` | không có | Chưa ghi ở đâu |
| Dòng JSON hỏng | `integration/run.py` | **Lệch với spec P2 mục 8.** Spec nói I0 là luật *drop*; code đang dựng một dòng giả (`raw_payload.description = nội dung dòng hỏng`, `job_id = số thứ tự dòng`) và **giữ vào output**, rule I0 ghi `modify`. Dòng rác này đi tiếp xuống các bước sau |
| Lỗi trong `_flatten_<nguồn>` | `flatten_raw_job_record` | `except Exception: _flatten_generic(...)` nuốt lỗi, không đếm, không cờ |
| ID dự phòng khi nguồn thiếu id | `flatten_raw_job_record` | `abs(hash(source_url))` đổi giá trị mỗi lần chạy (Python đặt hạt giống băm ngẫu nhiên cho `str` theo từng tiến trình) nên trái nguyên tắc chạy lại ra cùng kết quả. Khó xảy ra với đầu vào từ Clean (C3 đã bỏ tin thiếu `job_id`), nhưng các nơi khác gọi hàm này (`clean/run.py`, `deduplication/run.py`, `run_integration.py`, `scripts/build_gold_sample.py`) vẫn có thể chạm |

### 2.2. Bước 2

| Đã có | Ở đâu | Thiếu / lệch |
|---|---|---|
| Bỏ thẻ HTML bằng regex, `html.unescape`, thay `\xa0` và `​` | `transformation/html_cleaner.py` `strip_html_tags` | Xem 2.3 (3 lỗi đo được) |
| Nối bullet bị chẻ vụn | `transformation/bullet_stitcher.py` (tiền tố bullet nhận `- – • * + ▪ ▫ ➢` hoặc `1.`/`1)`) | Không nhận `✔ ✓ ➤ ● ✅`; sẽ cần đồng bộ với bullet chuẩn mới |
| Tạo `description_clean`, `requirements_clean`, `job_title_clean` | `transformation/run.py` `_clean_text_field`, `_clean_job_title` (T6) | `_clean_job_title` chỉ `strip()` |
| NFC, bỏ ký tự điều khiển, `fold()` (bỏ dấu, giữ `C# C++ .NET F#`) | `deduplication/text_norm.py` (`clean_text`, `fold`) | Chỉ dùng để tính khóa băm ở Clean, không ghi ra cột; `clean_text` còn **xóa boilerplate** và **gộp mọi xuống dòng thành khoảng trắng**, nên không dùng làm `text_clean` |
| NFC cho so khớp tiêu đề IT | `common/it_filter.py` | Chỉ trong hàm so khớp |
| Bản `fold` riêng (NFD, bỏ dấu) | `experience_parser.py`, `job_family_classifier.py`, `salary_parser.py`, `skill_normalizer.py`, `location_normalizer.py` | 5 bản sao rời nhau + 1 ở `text_norm.fold`. PH2 không gộp (ngoài phạm vi), chỉ không thêm bản thứ 7 |
| 3 cột `text_clean/text_norm/text_fold`, từ điển viết tắt | không có | Cần thêm |

### 2.3. Đo hiện trạng văn bản (10 tháng 11 2026)

Đo trên `description_clean + requirements_clean` hiện tại (đã qua `_clean_text_field`), số **tin** có lỗi:

| Nguồn | Tin | Còn thẻ HTML | Còn entity | Còn NFD | Còn ký tự ẩn (`​ ‌ ‍ ﻿ ⁠ \xa0`) |
|---|---|---|---|---|---|
| topcv | 1.561 | 0 | 0 | 0 | 2 |
| topdev | 227 | 0 | 0 | 5 | 0 |
| vietnamworks | 800 | 0 | 0 | 0 | 0 |
| careerviet | 448 | 0 | 0 | 16 | 1 |
| vieclam24h | 182 | 0 | 0 | 0 | 1 |
| itviec | 905 | 0 | 0 | 0 | 0 |
| glints | 271 | 0 | 0 | 21 | 1 |
| jobsgo | 683 | 0 | 0 | 0 | 0 |
| **Tổng** | **5.077** | **0** | **0** | **42** | **5** |

Kết luận: HTML đã sạch với dữ liệu hiện có (nhưng xem lỗi bên dưới); việc còn lại thật sự là **NFD (42 tin, 3 nguồn)**, ký tự ẩn còn sót (5 tin), và chưa có gạch ngang/bullet chuẩn. Số tin có gạch ngang `– — −` trong văn bản gốc sau làm phẳng: topcv 327, topdev 76, vietnamworks 217, careerviet 151, vieclam24h 48, itviec 261, glints 118, jobsgo 152. Số tin có ký hiệu bullet `• ✔ ✓ ➢ ➤ ● ▪ ○ ◦ ★ ✅`: topcv 119, vietnamworks 32, careerviet 86, vieclam24h 13, itviec 17, glints 40, jobsgo 16, topdev 0.

Ví dụ thật: Careerviet `careerviet_35C32FB4` có `"…PLC, HMI: ​Tiếp nhận…"`; TopCV `topcv_2324178` có `"phản biện cá﻿c thiết kế"` (ký tự ẩn nằm **giữa từ**, làm "các" thành hai mảnh khi tách từ); Glints `glints_0ff5749d-d031-48e8-b2ee-c92648699e18` và TopDev `topdev_2136004` có chuỗi NFD; VietnamWorks `vietnamworks_2113803` có `"Requirement Gathering &amp; Analysis"` ở dạng trước khi bóc.

**Ba lỗi của `strip_html_tags` đo trực tiếp** (chạy hàm hiện tại trên chuỗi thử):

| Đầu vào | Kết quả hiện tại | Lỗi |
|---|---|---|
| `Kinh nghiệm < 3 năm, lương > 10tr` | `Kinh nghiệm 10tr` | Regex `<[^>]+>` nuốt cả đoạn giữa hai ký tự `<` và `>` thường (mất dữ liệu). Trên dữ liệu thật: TopCV `topcv_2238387` và Glints `glints_5806f3c5-f2aa-43bd-bbb3-608c4221929f` có `"AC <-> test case"`, mũi tên bị xóa |
| `&amp;nbsp;Java` | `&nbsp;Java` | Entity mã hóa hai lần còn sót (P3 mục 4 T6 lấy đúng ví dụ này làm đích) |
| `<b>Java</b>Script` | `Java Script` | Thẻ inline bị thay bằng khoảng trắng nên cắt đôi từ |

Hai chuỗi đầu là chuỗi thử mình tự dựng (dữ liệu hiện tại không còn dạng này sau bóc); chuỗi `AC <-> test case` là dữ liệu thật.

## 3. Quyết định đặt bước 2 ở đâu

**[ĐỀ XUẤT] Bước 1 ở `02_integration`; bước 2 ở `03_transformation` (luật T6), không đặt ở 02.** Lý do từ code và hợp đồng:

1. `P0_pipeline_contract.md` mục 6.1 đã ánh xạ "2 Làm sạch ký tự" sang 03 Transformation, "1 Đồng nhất schema" sang 02 Integration; bảng ranh giới mục 7 cho Integration "ánh xạ trường, làm phẳng", cấm "parse số, đổi tiền, bỏ dòng, bù giá trị" và P2 mục 3 viết rõ giá trị Integration "vẫn là chữ như raw".
2. `description_clean`, `requirements_clean`, `job_title_clean` đã được tạo ở `transformation/run.py` T6 và các luật sau (T2 lương, T6 ngôn ngữ, T7 kỹ năng, T8 địa điểm) đọc chúng, nên chỉ cần sửa một chỗ để mọi luật sau hưởng; đặt ở 02 thì T6 phải bỏ bước bóc HTML riêng.
3. Chuẩn hóa gạch ngang (`15–25` thành `15-25`) phải chạy **trước** parse lương T2; trong `process_source` của 03, T6 đã chạy trước T2 (cùng vòng lặp), nên thứ tự hiện tại đã đúng.
4. NFC phải đứng trước băm: khử trùng lặp (Clean, 01) tự gọi `text_norm.clean_text` có NFC, nên điều kiện "NFC trước hash" trong mục 3.2 của file thiết kế đã được thỏa mà không cần đổi thứ tự pipeline.

Phản biện đã cân nhắc: Integration cũng đang gọi `strip_html_tags` cho TopDev (dòng 652-653, 659) và ITviec (dòng 444) trong flattener, tức là Integration đã *không* giữ nguyên chữ raw ở ba chỗ đó. Mình không đụng, vì bỏ ra sẽ đổi `raw_description_text` của TopDev và làm lệch Clean, Transformation, tests; ghi lại thành [CẦN CHỐT] C6.

**[CẦN CHỐT] C0:** bạn đồng ý đặt bước 2 ở 03 (T6) như trên không? Nếu muốn ở 02 thì cột `raw_*` phải đổi nghĩa từ "chữ như raw" sang "chữ đã làm sạch" và phải sửa P2 mục 3, P0 mục 7.

## 4. Bước 1: đồng nhất schema (ở `02_integration`)

### 4.1. Luật

| Mã | Luật | Hành động | Ví dụ trước → sau |
|---|---|---|---|
| I0 | Dòng JSON hỏng không parse được: ghi vào `rejected`, **không** dựng dòng giả | drop | dòng `{"hỏng":` → vào rejected, lý do `JSON_INVALID` |
| I6 | Bản ghi sau làm phẳng không qua `JobRecord` (pydantic): thiếu/sai khóa | drop | `crawled_at=""` → rejected, lý do `SCHEMA: crawled_at` |
| I7 | `_flatten_<nguồn>` ném lỗi: ghi rejected thay vì rơi lặng lẽ sang `_flatten_generic` | drop | lỗi `KeyError` → rejected, lý do `FLATTEN_ERROR: KeyError` |

I1–I5 giữ nguyên. Mã `I0` đổi từ `modify` thành `drop` để khớp spec P2 mục 8 và luật bảo toàn.

### 4.2. Model pydantic `JobRecord` (file mới `preprocessing/integration/schema.py`)

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `job_id_global` | str | bắt đầu bằng `<source_platform>_` và còn phần id không rỗng |
| `source_platform` | str | thuộc `SOURCES` |
| `source_job_id` | str | không rỗng |
| `source_url` | str | không rỗng |
| `crawled_at` | str | bắt buộc, parse được ISO-8601 (ví dụ `2026-11-01T15:03:19.902189+00:00`); giữ nguyên chuỗi, không đổi múi giờ |
| 5 cột Clean (`it_rule`, `it_rule_level`, `it_status`, `dedup_key`, `also_on`) | theo giá trị hiện có | null được; `also_on` là list |
| 18 trường giữ | str hoặc null; `working_locations`, `skills_list`, `benefits_list` là list[str] | null được |

Chỉ khóa mới *bắt buộc*; 18 trường thiếu vẫn hợp lệ (null) vì luật chọn trường chốt 03/11: "thiếu thì null". **[CẦN CHỐT] C2:** có cần coi `job_title` rỗng là lỗi schema (rejected) không? Hiện Clean đã bỏ JD rỗng và tin thiếu `job_id/source_url`; mình chưa thấy luật nào chặn `job_title` rỗng. **[ĐỀ XUẤT]** không bắt buộc ở PH2.

**[CẦN CHỐT] C1:** tên hàm. File thiết kế ghi `map_<nguồn>()`, code là `_flatten_<nguồn>`. **[ĐỀ XUẤT]** giữ `_flatten_<nguồn>` (đổi tên đụng ít nhất 8 chỗ và các test, không đổi hành vi), ghi trong spec rằng chúng *là* các hàm map của bước 1.

### 4.3. `rejected/`

- Trên máy: `data/preprocessing/rejected/02_integration/<nguồn>.jsonl` **[ĐỀ XUẤT]** (spec ghi `data/preprocessing/rejected/`; thư mục con theo bước để PH sau dùng chung). Mỗi dòng: `{"step","source","rule","reason","job_id","line_no","raw_line"}`. `raw_line` là dòng gốc trong `01_clean` để tái lập. `data/preprocessing/` đã git-ignore.
- Chạy thật ghi đè file của nguồn (idempotent); không có dòng nào thì xóa file cũ của nguồn đó. `--dry-run` không ghi, chỉ đếm vào báo cáo.
- Báo cáo (`reports/preprocessing/02_integration/<nguồn>.json`) chỉ giữ tối đa 3 ví dụ mỗi luật qua `StepReport.rule(...)`; **không** đưa `raw_line` vào `reports/` (được đưa vào git).
- Tên trên R2 sau này: `pipeline/rejected/` (PH0 đã nhận `rejected` làm tên thư mục hợp lệ). PH2 không ghi gì lên R2.

### 4.4. Bảo toàn và kiểm tra thêm

- `input.rows` = số dòng không rỗng của `01_clean/<nguồn>.jsonl`; `output.rows` = số dòng vào parquet; `dropped` = I0 + I6 + I7. `check_conserved()` đã có.
- **[ĐỀ XUẤT]** thêm vào `checks.notes` số `job_id_global` trùng trong `all.parquet` (chỉ báo, không bỏ dòng; khử trùng lặp là việc của Clean).
- Sửa `abs(hash(source_url))` thành `hashlib.sha1(url.encode()).hexdigest()[:16]` để id dự phòng tái lập được.
- `flatten_raw_job_record(..., strict=False)`: thêm tham số `strict`; `integration/run.py` gọi `strict=True` (lỗi ném ra → I7), các nơi khác giữ hành vi cũ.

## 5. Bước 2: làm sạch ký tự (ở `03_transformation`, luật T6)

### 5.1. Thứ tự biến đổi

| # | Việc | Có sẵn? |
|---|---|---|
| 1 | Bỏ thẻ HTML: thẻ khối (`p div li tr br h1-h6 ul ol`) thành xuống dòng; thẻ inline (`b i strong span a em u ins`) bỏ hẳn không chèn khoảng trắng; chỉ coi `<` là mở thẻ khi theo sau là chữ cái, `/` hoặc `!` | Một phần (đang thay mọi thẻ bằng khoảng trắng, regex nuốt `<->`) |
| 2 | `html.unescape`, **lặp tối đa 2 lần** nếu còn `&...;` hợp lệ (xử lý `&amp;nbsp;`) | Một lần |
| 3 | `unicodedata.normalize("NFC", s)` | Chưa |
| 4 | Bỏ ký tự ẩn `​ ‌ ‍ ⁠ ﻿` (xóa hẳn); `\xa0` và các khoảng trắng Unicode (` -      　`) thành dấu cách; ký tự điều khiển (trừ `\n \t`) xóa | Chỉ `​`, `\xa0` |
| 5 | Gạch ngang `– — − ‐ ‑ ‒` thành `-` (gạch nối ASCII) | Chưa |
| 6 | Bullet `• ✔ ✓ ➢ ➤ ● ▪ ▫ ○ ◦ ★ ✅ * +` ở đầu dòng thành `- `; `&bull;` đã thành `•` ở bước 2 | Chưa |
| 7 | Gộp `[ \t]+` thành một dấu cách, bỏ khoảng trắng đầu/cuối dòng, tối đa một dòng trống liên tiếp | Một phần |
| 8 | `stitch_fragmented_bullets` (đã có), chạy **sau** bước 5-7 | Có |

Ý nghĩa của bước 3 trước 4: một số chuỗi NFD có dấu tổ hợp đi kèm ký tự ẩn; NFC trước để chuỗi vào các bước sau ở dạng chuẩn.

**[CẦN CHỐT] C3 (cách bóc HTML):** file thiết kế ghi `get_text("\n")` (BeautifulSoup); code hiện có dùng regex và cho ra 0 thẻ sót trên dữ liệu thật. `get_text("\n")` chèn xuống dòng giữa mọi nút chữ, nên `<b>Java</b>Script` sẽ thành `Java\nScript` và `<strong>&bull; Số lượng tuyển:</strong> 05` (TopDev fixture `tests/fixtures/topdev/standard.json`) thành hai dòng. **[ĐỀ XUẤT]** giữ regex đã sửa theo mục 5.1 bước 1, không đổi sang BeautifulSoup; chỉ đổi nếu bạn muốn đúng chữ trong file thiết kế.

**[CẦN CHỐT] C4 (bullet chuẩn):** `- ` hay `• `? **[ĐỀ XUẤT]** `- ` vì `BULLET_PREFIX_REGEX` của bullet_stitcher và regex phân tách khoảng lương (`-|–|—`) đều đã nhận `-`; bước 7 của file thiết kế (tách bullet) cũng dễ hơn với một ký hiệu ASCII.

**[CẦN CHỐT] C5:** dấu `*` và `+` đầu dòng có thể là bullet hoặc phần ký hiệu thật (`+ 3 năm kinh nghiệm`). **[ĐỀ XUẤT]** chỉ đổi `* ` và `+ ` (kèm dấu cách theo sau) ở đầu dòng; không đổi nếu liền chữ (`+84`, `*Lưu ý`).

### 5.2. Ba cột văn bản

Mỗi trường văn bản dài (hiện: mô tả, yêu cầu) có ba dạng:

| Cột | Cách tạo | Dùng để |
|---|---|---|
| `text_clean` | kết quả mục 5.1 (giữ hoa thường, dấu, xuống dòng) | đọc, hiển thị, dịch (PH5), tách section (PH7) |
| `text_norm` | `text_clean` viết thường (`str.lower()` sau NFC) + mở rộng từ điển viết tắt (mục 5.3) | so khớp có dấu, từ điển, phân loại |
| `text_fold` | `text_norm` bỏ dấu (NFD, bỏ `Mn`, `đ`→`d`), **giữ `C# C++ .NET F#`**, rồi NFC | chỉ để so khớp (kỹ năng, hash); không bao giờ hiển thị |

**[CẦN CHỐT] C7 (tên cột):** hiện đã có `description_clean` và `requirements_clean`, và các bước sau (04 `normalization/run.py`, 05 encoding, `mining/config.py`, `monitoring/.../eda_exploration_service.py`, tests) đọc các tên đó. **[ĐỀ XUẤT]** *không đổi tên*; coi `description_clean` = `text_clean` của mô tả, và thêm `description_norm`, `description_fold`, `requirements_norm`, `requirements_fold` (4 cột mới). `text_clean/text_norm/text_fold` trong file thiết kế là tên khái quát. Hỏi: bạn muốn tên cột đúng như file thiết kế (`text_*`, gộp mô tả + yêu cầu) thì phải sửa các bước sau; chọn cách nào?

**[CẦN CHỐT] C8:** `job_title` có cần `norm/fold` không? Dedup tầng 2 và so khớp nhóm nghề dùng tiêu đề. **[ĐỀ XUẤT]** `job_title_clean` qua cùng bước 1-7 (NFC, ký tự ẩn, khoảng trắng), thêm `job_title_fold` thôi, không thêm `job_title_norm`. Và benefits/skills không đụng.

Dùng lại `deduplication/text_norm.fold` làm lõi `text_fold` (đã đúng yêu cầu giữ `C# C++ .NET F#`), không viết bản fold thứ bảy. **[CẦN CHỐT] C9:** `text_norm.fold` hiện gọi `.lower()` *sau* NFC; kết quả `đ`→`d` đã xử lý. OK để dùng nguyên, hay muốn tách module `preprocessing/common/text_clean.py` rồi để `text_norm` gọi ngược lại (đụng Clean)? **[ĐỀ XUẤT]** module mới import `fold` từ `deduplication.text_norm`, không đụng Clean.

### 5.3. Từ điển viết tắt

- Tên file **[ĐỀ XUẤT]** `preprocessing/dictionaries/abbreviations.json`, dạng `{"kinh nghiệm": ["kn"], "đại học": ["đh"], ...}` giống `skills.json` (chuẩn → các cách viết); commit lên git; version ghi vào báo cáo.
- Áp dụng **chỉ cho `*_norm`**, không đổi `*_clean` (giữ chữ gốc để hiển thị và dịch), khớp theo từ nguyên vẹn (`(?<!\w)…(?!\w)`), không phân biệt hoa thường, trừ các viết tắt dễ nhầm với từ thường thì khớp phân biệt hoa thường (ví dụ `BE`, `FE` khác từ `be` trong câu tiếng Anh).
- File thiết kế nêu các ví dụ: `kn, tr, ĐH, BE/FE, CTV`. **[CẦN CHỐT] C10:** danh sách đầy đủ. Mình không biết danh sách này dài bao nhiêu và không bịa. **[ĐỀ XUẤT]** làm theo EDA: bước đầu chỉ chạy script đếm tần suất token ngắn (≤ 4 ký tự, viết hoa toàn bộ hoặc có dấu chấm) trên `description_clean` 8 nguồn, bạn duyệt danh sách ứng viên rồi mới đưa vào file. Bản đầu của file chỉ chứa các mục bạn đã duyệt.
- Cảnh báo cụ thể: `tr` (triệu) trùng với bộ parse lương `salary_parser.py`, và `BE`/`FE` có thể là backend/frontend hoặc không. **[ĐỀ XUẤT]** không đưa `tr` vào từ điển vì parse lương (T2) đã xử lý; nếu cần, chỉ khớp khi liền sau số (`15tr`).
- Thứ tự: mở rộng viết tắt **sau** NFC và **trước** viết thường để rule phân biệt hoa thường còn hiệu lực. **[CẦN CHỐT] C11:** có mở rộng ở `*_norm` thì `*_fold` kế thừa (đã mở rộng); chấp nhận?

### 5.3.1. Ứng viên viết tắt đếm trên dữ liệu thật (10/11/2026, số tin trong 5.077 có token, khớp nguyên từ, phân biệt hoa thường như ghi)

CNTT 1.182, BHXH 193, BHYT 164, BHTN 136, CSDL 134, ĐH 124, TP 84, HCM 74, CĐ 66, TNHH 49, BE 39, FE 17, KN 11 (`KN` 10, `kn` 1), NV 10, HN 8, VP 7, Cty 5 (`Cty` 5, `cty` 1), CTV 4, SV 3, YC 3, TC 3, QLDA 2, `tr` 2. Không đưa vào ứng viên: `BA`, `QA`, `FS` (tên vị trí, không phải viết tắt cần mở rộng), `HCM`/`HN`/`TP` (đã thuộc luật địa điểm T8), `tr` (do parse lương), `NV/VP/SV/YC/TC/QLDA/ĐT` (tần suất thấp hoặc nghĩa mơ hồ; bạn quyết có thêm không).
File `preprocessing/dictionaries/abbreviations.json` hiện có 13 mục ứng viên, **tất cả `approved=false`**: kinh nghiệm (KN), đại học (ĐH), cao đẳng (CĐ), công nghệ thông tin (CNTT), cơ sở dữ liệu (CSDL), bảo hiểm xã hội (BHXH), bảo hiểm y tế (BHYT), bảo hiểm thất nghiệp (BHTN), trách nhiệm hữu hạn (TNHH), cộng tác viên (CTV), công ty (Cty), backend (BE, phân biệt hoa thường), frontend (FE, phân biệt hoa thường). Duyệt bằng cách đổi `approved` thành `true` từng mục; chỉ mục `true` được mở rộng vào `*_norm`.

### 5.4. Đo và báo cáo

- `StepReport` của 03: rule `T6` (đã có) tách thành `T6a` (HTML), `T6b` (NFC), `T6c` (ký tự ẩn), `T6d` (gạch ngang, bullet), mỗi rule `modify` với số tin bị tác động. **Lưu ý:** mã `T6b` hiện được spec P3 dùng cho bước *dịch*. **[CẦN CHỐT] C12:** đặt mã khác cho các luật này (ví dụ `T6.1`–`T6.4`) để không đụng mã dịch?  **[ĐỀ XUẤT]** `T6.1`–`T6.4`.
- `extra.text_quality` ở mỗi báo cáo nguồn và `_all`: `residual_html_pct`, `residual_nfd_pct`, `residual_hidden_char_pct` tính trên **cột đầu ra** (không phải đầu vào), kèm số tử và mẫu. Định nghĩa đo (dùng chung với PH1):
  - còn HTML: có `re.search(r"<\s*/?\s*[A-Za-z!][^>]*>")` hoặc `html.unescape(s) != s`. Không dùng regex `&\w+;` đơn thuần vì `F&B; trường` và `P&L; giao tiếp` (dữ liệu thật TopCV, TopDev) khớp mà không phải entity.
  - còn NFD: `not unicodedata.is_normalized("NFC", s)`.
- Đích: cả ba chỉ số = 0% trên đầu ra. **[CẦN CHỐT] C13:** nếu > 0 thì dừng bước (như luật bảo toàn) hay chỉ ghi `checks.notes`? **[ĐỀ XUẤT]** dừng chỉ với HTML và NFD (hai mục tiêu bạn đặt), ký tự ẩn chỉ cảnh báo.
- `dry-run` vẫn tính và ghi báo cáo, không ghi parquet.

## 6. Ranh giới

- Raw bất biến: không sửa `data/<nguồn>/raw/` và không sửa các cột `raw_*`. Mọi làm sạch ghi vào cột mới.
- Bước 02 không bỏ dòng **ngoài** I0, I6, I7 (dòng không thể coi là bản ghi). Bước 03 vẫn `rows_out = rows_in`.
- Không dùng model ở PH2 (model duy nhất của dự án, `VietAI/envit5-translation`, thuộc PH5).
- `text_clean` không xóa boilerplate (khác `text_norm.clean_text`): xóa nội dung là việc của Clean/PH tách section, không phải bước làm sạch ký tự.
- Không động tới R2.

## 7. Tiêu chí xong

- Bước 1: `rows_in = rows_out + dropped` ở cả 8 nguồn; chạy với tệp có một dòng JSON hỏng thì dòng đó vào `rejected`, không vào parquet; `job_id_global` bắt đầu bằng `<nguồn>_`; không dòng nào có `crawled_at` rỗng.
- Bước 2: `residual_html_pct = 0` và `residual_nfd_pct = 0` trên đầu ra thật của 03 (5.077 tin hiện có trên máy hoặc số tin thực tế lúc chạy); ví dụ `cá﻿c` ra `các`.
- Hiện có 42 tin NFD và 5 tin ký tự ẩn: số này phải về 0, và báo cáo ghi "trước → sau".
- `pytest tests/unit` xanh (test cũ của `html_cleaner`, `transformation`, `integration` vẫn qua; test nào khẳng định hành vi sai thì sửa và ghi lý do).

## 8. Monitoring thấy gì

- Bước 02: số bản ghi vào `rejected` theo luật và nguồn, 3 ví dụ (không có nội dung JD).
- Bước 03: bảng `residual_*` trước/sau theo nguồn; 3 ví dụ trước → sau cho mỗi luật `T6.x`.
- Không thêm trang mới; nếu `monitoring` đọc báo cáo bước thì chỉ cần khối `extra` mới. **[CẦN CHỐT] C14:** trang `/preprocessing` có cần hiển thị khối `extra.text_quality` ngay trong PH2 hay để sau?

## 9. Không làm

Không sửa raw; không ghi R2; không cài gói (`pydantic`, `bs4`, `lxml` đã có); không đổi tên cột đã có; không gộp 6 bản `fold` rời nhau (ghi vào danh sách việc dọn, không phải PH2); không đưa `abbreviations.json` vào code trước khi bạn duyệt danh sách.
