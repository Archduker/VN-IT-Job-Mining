# PH8. Processing bước 7–9: tách section/bullet, trích kỹ năng Aho–Corasick, tách từ và stopword

> **Nháp đặc tả, chờ bạn sửa** (10/11/2026). Chưa có code. Prompt: `docs/prompting/PH8_tach_section_ky_nang_tach_tu.md` (chưa duyệt).
> **[ĐỀ XUẤT]** = mình đoán. **[CẦN CHỐT]** = mình không biết, cần bạn quyết.
> Số liệu đo ngày 10/11/2026, chỉ đọc, trên `data/preprocessing/01_clean/*.jsonl` (5.077 tin: topcv 1.561, topdev 227, vietnamworks 800, careerviet 448, vieclam24h 182, itviec 905, glints 271, jobsgo 683) qua `flatten_raw_job_record` + `clean_text` (PH2). **`data/preprocessing/02_integration/` đang trống và `04_normalization/all.parquet` không có trên máy**, nên chưa đo được trên đúng bảng đầu vào của `processing/`; số dưới đây là xấp xỉ trên văn bản `description + requirements` đã `clean_text`. Báo cáo 03/04 trong `reports/preprocessing/` là bản cũ (03/11, 5.177 dòng), không dùng làm số đo.

## 1. Mục tiêu

Ba bước của file thiết kế, đặt trong `processing/` (đã chốt ở plan):

| Bước thiết kế | Thư mục | Đầu ra theo thiết kế |
|---|---|---|
| 7 Tách section, bullet | `processing/extraction/` | `staging/bullets` |
| 8 Trích xuất kỹ năng | `processing/extraction/` | `staging/job_skills` |
| 9 Tách từ, stopword | `processing/transformation/` | `gold/` |

Tiêu chí chính: Consistency, Completeness. Đích nghiệm thu theo file thiết kế: **tách section đúng ≥ 90% và F1 kỹ năng ≥ 0.85 trên bộ gold 100 JD**. Bước 9 file thiết kế không ghi tiêu chí "Xong khi"; PH8 đề xuất ở mục 7. Không dùng model (luật if-else, từ điển, `pyahocorasick`, `underthesea`).

Tên "đầu ra" của thiết kế (`staging/`, `gold/`) ánh xạ sang R2 theo quyết định PH0: bảng gộp 8 nguồn nằm dưới `pipeline/<bước>/`. Tên thư mục con mới cho 3 bước này: **[CẦN CHỐT] P1.** **[ĐỀ XUẤT]** `07_sections`, `08_skills`, `09_tokens` (local `data/processing/<bước>/`, báo cáo `reports/processing/<bước>/`, R2 `pipeline/<bước>/`); lý do: cùng kiểu đánh số với 01–05, không đụng `data/preprocessing/`.

## 2. Hiện trạng so với thiết kế

### 2.1. Môi trường và dữ liệu

| Mục | Hiện trạng đo | Ghi chú |
|---|---|---|
| `pyahocorasick` | 2.3.1, import được trong `.venv` | **không có trong `requirements*.txt`** (grep 10/11); phải ghim version ở PH9 hoặc khi code PH8 |
| `underthesea` | 9.5.0, import được | không có trong `requirements*.txt`. `word_tokenize` trả `list` (không phải chuỗi) |
| Bộ gold | `data/preprocessing/gold/gold_sample.json`: 100 JD, `seed` ghi trong file, 8 nguồn 12–13 tin (vieclam24h, itviec, glints, jobsgo 12; còn lại 13) | **chưa có file nhãn** (chỉ có `gold_sample.json`, không có file xuất từ `gold_labeler.html`) nên **chưa đo được F1 và độ đúng tách section** |
| Hàm đọc nhãn | `preprocessing/common/gold.py` `load_gold`, `validate_label`, `coverage` | `sections`: danh sách `{section, start, end}` với `start/end` là **offset ký tự trên trường `text` của `gold_sample.json`** (chuỗi `raw_description_text` + `\n\n` + `raw_requirements_text` đã bỏ thẻ, theo `scripts/build_gold_sample.py::_text`). `skills`: `{name, level: required|preferred}`, `name` là chuỗi tự do |
| Văn bản vào bước 7 | `description_clean`, `requirements_clean` (+ `*_norm`, `*_fold`) từ PH2 | `clean_text` đã chuẩn hóa bullet về `- ` đầu dòng; **không còn thẻ HTML**, nên "lấy theo thẻ HTML nếu nguồn có" của thiết kế không làm được ở `processing/` (không đọc lại raw, `processing/CLAUDE.md`) |

### 2.2. Bước 7: tách section

Đo khả năng nhận tiêu đề section bằng một regex tạm của người soạn (tiêu đề đứng riêng một dòng ≤ 40 ký tự, có các cụm "mô tả", "yêu cầu", "quyền lợi", "phúc lợi", "thông tin khác", "job description", "requirement(s)", "benefit(s)", "responsibilit", "nice to have", "ưu tiên", "lợi ích", "why you"). **Đây không phải luật và không phải danh sách duyệt**, chỉ để biết quy mô:

| Nguồn | Tin | Có ≥ 1 dòng giống tiêu đề | Trung bình số từ `description+requirements` (sau `clean_text`) |
|---|---|---|---|
| topcv | 1.561 | 106 | 332 |
| topdev | 227 | 25 | 396 |
| vietnamworks | 800 | 132 | 332 |
| careerviet | 448 | 0 | 539 |
| vieclam24h | 182 | 14 | 281 |
| itviec | 905 | 131 | 421 |
| glints | 271 | 109 | 428 |
| jobsgo | 683 | 36 | 268 |

Kết luận: tiêu đề độc lập nhận được rất ít bằng regex đơn giản, nên **không thể chỉ dựa vào "regex tiêu đề"** như thiết kế. Có hai nguồn tín hiệu khác đo được:
- **Trường nguồn**: cả 8 nguồn đều có `description` và `requirements` riêng (số tin có cả hai: bằng số tin, trừ jobsgo thiếu 1 mô tả). Ở raw, 5 nguồn (topcv, topdev, vietnamworks, itviec/glints qua `jobBenefits`, jobsgo) còn có trường phúc lợi riêng (`benefits_bullets`, `benefits`, `benefits_list`, `welfare_tags`). Nhưng `raw_benefits_text` **không có** trong đầu ra làm phẳng; code 03 dùng `rec["benefits_list"]`. **[CẦN CHỐT] S1:** bảng đầu vào của bước 7 có cột `benefits_list` hay không; mình chưa kiểm vì không có `02/04` trên máy.
- Thẻ HTML trong raw (có ở `description`/`requirements` của topdev 227/227, vietnamworks 772/800, `job_posting_jsonld.description` 874/905 itviec, 271/271 glints...) bị `clean_text` bỏ; ranh giới `<li>`, `<h*>` chỉ còn lại dưới dạng xuống dòng và `- `.

| Thiết kế | Hiện có | Lệch / thiếu |
|---|---|---|
| Lấy section theo thẻ HTML nếu nguồn có | không có ở `processing/` | Không làm được từ `text_clean`. Xem **[CẦN CHỐT] S2** |
| Không có thẻ thì regex tiêu đề | không có | Cần từ điển tiêu đề `dictionaries/section_headings.json` (mới) |
| 5 section `mo_ta / yeu_cau / uu_tien / phuc_loi / khac` | `preprocessing/common/gold.py` `SECTIONS` đã có đúng 5 mã này | Dùng lại hằng này, không khai báo bản thứ hai |
| Mỗi bullet một dòng | PH2 đã chuẩn hóa `- ` đầu dòng + `stitch_fragmented_bullets` | Bước 7 tách theo dòng; không viết lại stitcher |
| Đúng ≥ 90% trên gold | chưa có nhãn | **Chưa đo được**; định nghĩa "đúng" ở **[CẦN CHỐT] S3** |

### 2.3. Bước 8: kỹ năng

Hiện có **ba** nguồn kỹ năng khác nhau trong repo (đã đếm):

| Tệp | Số kỹ năng | Số alias | Ai dùng |
|---|---|---|---|
| `preprocessing/dictionaries/skills.json` | 40 | 162 | `transformation/skill_extractor.py` (T7b, đang chạy ở bước 03, tạo `skills_clean`) |
| `preprocessing/dictionaries/skills_taxonomy.json` (`version` 1.0.0, mô tả "baseline") | 92 | 274 | tài liệu/phân tích encoding; không thấy code chạy gọi trực tiếp |
| `preprocessing/encoding/skills_taxonomy_230.py` (`TAXONOMY_230`) | 230 (6 nhóm) | 519 khóa tra cứu không mơ hồ, `ALIAS_CONFLICTS` = 1 (`critical thinking` → `logical_thinking`, `problem_solving`) | encoding P5 (230 cột kỹ năng) |

File thiết kế nói "khoảng 300 kỹ năng". **Không có tệp nào có 300.** **[CẦN CHỐT] K1:** taxonomy của bước 8 là tệp nào? **[ĐỀ XUẤT]** `TAXONOMY_230` vì encoding P5 đã dùng và đã có alias; xuất ra một JSON trong `dictionaries/` (ví dụ `skills_taxonomy_230.json`) để `processing/` không import từ `preprocessing/encoding/` (code Encoding sẽ được chuyển sau). Nếu bạn muốn ~300, danh sách thêm 70 kỹ năng do bạn duyệt, mình không tự thêm.

Đo thử một bộ quét Aho–Corasick dựng từ `TAXONOMY_230` (khóa = `fold(canonical|slug|alias)`, bỏ khóa mơ hồ, chặn ranh giới bằng `[a-z0-9_#+]`) trên `fold(clean_text(description+requirements))` của 5.077 tin, so với `extract_skills_from_text` hiện tại (`skills.json`) trên cùng văn bản:

| Nguồn | Hiện tại (skills.json): tin 0 kỹ năng | Hiện tại: TB kỹ năng/tin | Thử AC-230 + fold: tin 0 kỹ năng | AC-230: TB/tin |
|---|---|---|---|---|
| topcv | 34,4% | 3,13 | 6,5% | 7,51 |
| topdev | 32,2% | 3,32 | 2,6% | 8,13 |
| vietnamworks | 33,4% | 2,25 | 5,2% | 6,06 |
| careerviet | 20,3% | 3,75 | 0,4% | 9,29 |
| vieclam24h | 50,5% | 1,85 | 1,1% | 5,17 |
| itviec | 8,1% | 5,88 | 0,4% | 12,3 |
| glints | 28,0% | 3,92 | 1,1% | 9,24 |
| jobsgo | 37,5% | 2,40 | 5,7% | 6,17 |

**Cảnh báo, số này không phải độ chính xác.** Số kỹ năng tăng gấp đôi trở lên một phần vì có nhiều kỹ năng hơn (230 so với 40), nhưng một phần là **nhiễu do `fold`**: trong 5.077 tin, alias `bi` khớp 1.314 tin, `ba` 675, `soc` 285, `c` 267, `r` 175 (số tin có khớp, sau ràng buộc ranh giới). Chữ `bi` ra từ `bị`, `bí`, `bì`; `ba` từ `bà`, `bạ`; `soc` từ `sốc`... bị bỏ dấu thành cùng một chuỗi. Trong `TAXONOMY_230`, 52 trên 519 khóa dài ≤ 3 ký tự (`ba, bi, c, r, ts, tf, gin, sh, soc, vue, js, ios, ...`). Vậy **quét trên `text_fold` đúng như thiết kế sẽ sinh nhiễu hàng loạt với alias ngắn**; đây là điểm lệch quan trọng nhất của bước 8 (xem K3).

| Thiết kế | Hiện có | Lệch / thiếu |
|---|---|---|
| Taxonomy ~300 kỹ năng + alias, trong file từ điển | 40 / 92 / 230 kỹ năng, 3 nơi | **[CẦN CHỐT] K1** |
| Aho–Corasick trên `text_fold`, có ranh giới từ | `pyahocorasick` đã cài; hiện dùng 1 regex cho mỗi alias (`extract_skills_from_text`) | Cần module mới; ranh giới phải xử lý `C# C++ .NET Node.js` (ký tự `# + .` thuộc tên) |
| Trọng số: bắt buộc = 1, ưu tiên = 0.5 | không có | Cần liên hệ với section (mục 4.2) |
| Đầu ra `staging/job_skills` | `skills_clean` (danh sách, trộn nhãn nguồn + từ điển) trong bảng 03 | Bảng mới dạng dọc; **không đổi `skills_clean`** (encoding P5 và các bước sau đọc nó) |
| F1 ≥ 0.85 trên gold | chưa có nhãn | **Chưa đo được** |
| Zero-shot bằng model chỉ khi F1 < 0.8 (thiết kế 4.2) | — | Dự án mặc định không dùng model; nếu F1 < 0.85 thì dừng và báo, không thêm model (xem 8) |

### 2.4. Bước 9: tách từ, stopword

| Thiết kế | Hiện có / đo | Lệch / thiếu |
|---|---|---|
| Thay kỹ năng bằng token chuẩn trước, rồi `underthesea` | `underthesea` 9.5.0 đã cài | Chưa có code |
| Lý do phải thay trước | đo: `word_tokenize("C++, Node.js và C#/.NET; CI/CD")` trả `['C','+','+', ',', 'Node', '.', 'js', 'và', 'C', '#', '/', '.', 'NET', ';', ..., 'CI', '/', 'CD']` | Đúng như thiết kế, tokenizer cắt vụn |
| Token giữ chỗ có sống sót qua tokenizer không | đo: `skill_python`, `skill_csharp`, `SKILLPYTHON` đi qua nguyên vẹn (không bị tách) | Dạng token cụ thể: **[CẦN CHỐT] W1** |
| Tách từ ghép tiếng Việt | đo: `kinh nghiệm`, `lập trình viên`, `công ty`, `phần mềm` ra thành 1 token (dấu cách trong token); `format="text"` nối bằng `_` | Dùng đầu ra `list`, không dùng `format="text"` (trùng `_` với token giữ chỗ) |
| Tốc độ | đo: 100 JD gold (31.103 token) mất 1,3 giây | Ngoại suy 5.077 tin ≈ 70 giây (ngoại suy, không đo); chưa đo trên bảng thật |
| Stopword chung | `preprocessing/encoding/assets/jd_stopwords_v1.json`: 91 từ, trích từ `COMMON_JD_STOPWORDS` (`tfidf_extractor.py`), song ngữ Anh–Việt, dành cho unigram | Tái dùng được **[CẦN CHỐT] W2**; chưa có stopword theo token ghép của `underthesea` |
| Stopword theo miền (DF > 60%) | không có | Tính từ corpus; số token vượt ngưỡng **chưa biết**, sẽ đo khi làm |
| Đầu ra `gold/` | — | **[CẦN CHỐT] W3** (cột, đơn vị: theo bullet hay theo JD) |

## 3. Đầu vào và đầu ra

- **Đầu vào:** bảng sau pre-processing gộp 8 nguồn, **[CẦN CHỐT] P2:** `data/preprocessing/04_normalization/all.parquet` (như `processing/CLAUDE.md`) hay đầu ra mới nhất của các phase PH3–PH7 khi PH9 chạy. Cột cần: `job_id_global`, `source_platform`, `description_clean`, `requirements_clean`, `description_fold`, `requirements_fold` (PH2), và, nếu có, `benefits_list`. Khi PH5 (dịch) chưa làm: cột tiếng Việt = cột gốc, `<trường>_source` ghi rõ (theo plan). Bước 7–9 chạy trên cột "tiếng Việt" nếu có.
- **Đầu ra** (tên đề xuất, **[CẦN CHỐT] P1**):
  - `07_sections`: bảng `bullets` (dọc): `job_id_global`, `source_platform`, `bullet_idx`, `section`, `text`, `section_rule` (mã luật đã quyết).
  - `08_skills`: bảng `job_skills` (dọc): `job_id_global`, `skill` (canonical), `slug`, `level` (`required|preferred`), `weight` (1 / 0.5), `section`, `via` (`text|meta`), `n_mentions`.
  - `09_tokens`: bảng `tokens` theo JD (**[CẦN CHỐT] W3**): `job_id_global`, `tokens` (list), `tokens_nostop` (list), `n_tokens`.
- Mỗi bước ghi `StepReport` (`preprocessing/common/step_report.py`) với luật bảo toàn `rows_in = rows_out + dropped`; ba bước này **không bỏ JD** (số JD vào = số JD ra, JD không có bullet/kỹ năng vẫn giữ và được đếm riêng).

## 4. Luật (mã dạng `S7.x`, `K8.x`, `W9.x`)

### 4.1. Tách section, bullet (bước 7)

| Mã | Luật | Hành động |
|---|---|---|
| S7.1 | Tách theo dòng; dòng bắt đầu bằng `- ` là một bullet; dòng không có bullet là một bullet (câu văn) hoặc tiêu đề (S7.3). Bỏ dòng rỗng | bullet |
| S7.2 | Section mặc định theo trường nguồn: dòng thuộc `description_clean` → `mo_ta`, thuộc `requirements_clean` → `yeu_cau`; dòng từ `benefits_list` (nếu có, **[CẦN CHỐT] S1**) → `phuc_loi` | gán |
| S7.3 | Dòng là **tiêu đề** (ngắn, thường kết thúc `:`, khớp `section_headings.json`) đổi section hiện tại cho các dòng sau cho tới tiêu đề kế tiếp; chính dòng tiêu đề không thành bullet | gán |
| S7.4 | Cụm tín hiệu "ưu tiên" ở **đầu bullet hoặc tiêu đề** (từ điển trong cùng file, ví dụ theo thiết kế: "ưu tiên", "nice to have", "là một lợi thế", "plus"; **danh sách chính thức do EDA, bạn duyệt**) → `uu_tien` | gán |
| S7.5 | Không khớp luật nào ngoài S7.2 → giữ section mặc định; dòng trước mọi tiêu đề của trường không rõ → `khac` chỉ khi **[CẦN CHỐT] S4** | gán |

Từ điển tiêu đề **không tự bịa**: bước đầu chỉ chạy script đếm các dòng ngắn đứng riêng (≤ 6 từ, kết thúc `:` hoặc in hoa toàn bộ) trên 5.077 tin, xếp theo tần suất, bạn duyệt rồi mới đưa vào `section_headings.json`. Chưa có file duyệt thì file là `{}` và chỉ trường nguồn (S7.2) hoạt động; số đo gold khi đó là cận dưới.

### 4.2. Trích kỹ năng (bước 8)

| Mã | Luật | Hành động |
|---|---|---|
| K8.1 | Dựng automaton một lần từ taxonomy: khóa = `fold(alias)` cho alias dài ≥ 4 ký tự hoặc có ký tự `# + .` (`c#`, `c++`, `.net`) | quét |
| K8.2 | Ranh giới: ký tự liền trước và liền sau khớp **không** thuộc `[a-z0-9_#+]` (lấy từ `extract_skills_from_text`); riêng `.net`, `node.js` kiểm tra thêm dấu `.` | lọc |
| K8.3 | **Alias ngắn hoặc dễ trùng từ thường** (≤ 3 ký tự, hoặc trùng từ tiếng Việt thường sau `fold`: `bi`, `ba`, `soc`, `c`, `r`, `go`, `ts`, `tf`...) **không** quét trên `text_fold`; quét trên `text_clean` **phân biệt hoa thường** (ví dụ chỉ chấp nhận `BI`, `BA`, `SOC`, `C`, `R` viết hoa đúng) và với `c`, `r`, `go` thêm điều kiện ngữ cảnh (đã có tiền lệ trong `skills.json`: `ngôn ngữ c`, `lập trình c`). **Danh sách alias thuộc nhóm này do script đo + bạn duyệt**, không đoán | lọc |
| K8.4 | Mỗi bullet quét riêng (không quét cả JD một lần) để biết `section` của từng lần khớp | quét |
| K8.5 | `level`/`weight`: khớp trong bullet `yeu_cau` → `required`, 1; trong `uu_tien` → `preferred`, 0,5; trong `mo_ta` và `khac` **[CẦN CHỐT] K2**; trong `phuc_loi` không ghi kỹ năng (**[ĐỀ XUẤT]**). Cùng kỹ năng nhiều lần: giữ `level` cao nhất, cộng `n_mentions` | gán |
| K8.6 | Kỹ năng từ metadata nguồn (`skills_list`, đã lọc ở T7a): ghi thêm với `via=meta`, `level=required`, **[CẦN CHỐT] K4**; F1 gate chỉ tính `via=text` | gán |

### 4.3. Tách từ, stopword (bước 9)

| Mã | Luật | Hành động |
|---|---|---|
| W9.1 | Trên mỗi bullet: thay mọi kỹ năng đã khớp ở bước 8 bằng token giữ chỗ **trước** khi gọi `word_tokenize`; sau tokenize, giữ token giữ chỗ nguyên | thay |
| W9.2 | `underthesea.word_tokenize(text)` (đầu ra `list`); chuyển viết thường trừ token giữ chỗ | tách |
| W9.3 | Bỏ dấu câu và token chỉ gồm ký hiệu; số: **[CẦN CHỐT] W4** | lọc |
| W9.4 | Stopword lớp chung (**[CẦN CHỐT] W2**) | lọc (cột `tokens_nostop`) |
| W9.5 | Stopword lớp miền: token xuất hiện trong > 60% số JD của corpus (DF tính theo JD, không theo lần xuất hiện), bỏ khỏi `tokens_nostop`; token giữ chỗ kỹ năng **không bao giờ** bị coi là stopword; ngưỡng 0,6 là tham số trong báo cáo | lọc |

## 5. Đo và báo cáo

- `StepReport` mỗi bước + `extra`:
  - 07: số bullet, số bullet theo `section` × nguồn, tỉ lệ bullet theo `section_rule` (S7.2/7.3/7.4/7.5), số JD không có bullet; **độ đúng trên gold** (nếu đã có nhãn): xem 5.1.
  - 08: số dòng `job_skills`, số kỹ năng khác nhau, tỉ lệ JD 0 kỹ năng theo nguồn (so với số đo 2.3), top 30 kỹ năng theo số JD; số khớp bị K8.3 chặn; P/R/F1 trên gold (5.2).
  - 09: số token trung bình/JD, số token bị stopword loại theo lớp, danh sách stopword lớp miền (token + DF) để bạn duyệt, thời gian chạy; phiên bản `underthesea` và `pyahocorasick` (không có model, ghi "không dùng model").
- Ghi vào `meta.json`/`extra` phiên bản các file luật (`section_headings.json`, taxonomy, stopword) bằng hash ngắn (tái lập, thiết kế 4.4).
- `dry-run` tính và ghi báo cáo, không ghi parquet.

### 5.1. Độ đúng tách section trên gold

Offset nhãn gold nằm trên `text` của `gold_sample.json` (raw bỏ thẻ), **không** khớp offset của `text_clean`. **[CẦN CHỐT] S3.** **[ĐỀ XUẤT]** so theo **nội dung dòng**: lấy mỗi đoạn nhãn `text[start:end]`, chạy `clean_text` + `fold` từng dòng; bullet dự đoán đúng nếu `fold(bullet)` nằm trong tập dòng của đoạn nhãn cùng section. Chỉ số: **độ đúng theo bullet** = (số bullet có section khớp nhãn) / (số bullet nằm trong vùng đã gán nhãn), gộp trên các JD có `sections` ≠ `null`. Báo thêm tỉ lệ JD đúng 100% bullet (thông tin, không phải cổng). Theo nguồn và tổng. Bullet nằm ngoài mọi đoạn nhãn: không tính. Đã gán `sections = "none"`: không tính.

### 5.2. F1 kỹ năng trên gold

- Nhãn `name` tự do: ánh xạ về `canonical` bằng cùng bảng tra cứu của taxonomy (so `fold` + viết thường). Nhãn không ánh xạ được: **[CẦN CHỐT] K5** (**[ĐỀ XUẤT]** tính vào FN và báo riêng "kỹ năng ngoài taxonomy" để thấy phạm vi taxonomy thiếu gì, không đẩy F1 lên bằng cách bỏ chúng).
- F1 micro trên tập cặp (JD, kỹ năng) của các JD có `skills` ≠ `null` (`"none"` = JD không có kỹ năng, mọi dự đoán là FP). Báo cáo từng nguồn và tổng; thêm F1 theo `level` (required/preferred) làm thông tin. Cổng 0,85 là F1 micro tổng, `via=text`.
- Báo cáo ghi số JD đã gán nhãn lúc đo: gold chưa gán hết thì số đo là tạm. **[CẦN CHỐT] K6:** cần tối thiểu bao nhiêu JD đã gán mới được tuyên bố đạt/không đạt?

## 6. Ranh giới

- Không đọc lại raw, không sửa cột đã chuẩn hóa ở giai đoạn trước; không đổi `skills_clean`, `description_clean`, `requirements_clean`.
- Raw bất biến; `text_clean` không bị ghi đè.
- Không dùng model (chỉ `pyahocorasick` + `underthesea`, hai thư viện xác định). `underthesea` có thể tải tài nguyên lần đầu: nếu cần mạng, báo và dừng, không tự tải (đã đo trên máy chạy được không cần ghi thêm; **chưa biết** nó có tải gì lần đầu trên máy sạch).
- Không ghi R2 (PH9). Không cài gói. Bảo toàn: không bỏ JD.
- Fit (DF stopword miền) chỉ trên dữ liệu thật; không cần chia train/test vì mining unsupervised (bước 11 tùy chọn). **[CẦN CHỐT] W5:** nếu sau này có bước giám sát, DF phải tính lại trên train.
- `random_state`: không có bước ngẫu nhiên; nếu cần lấy mẫu để đo thì seed cố định.

## 7. Tiêu chí xong

- **Tách section:** độ đúng theo bullet ≥ 90% trên gold (định nghĩa 5.1, sau khi bạn chốt S3 và gán nhãn `sections` đủ số JD K6).
- **Kỹ năng:** F1 micro `via=text` ≥ 0,85 trên gold (5.2). Báo từng nguồn; nguồn thấp rõ rệt được ghi lỗi còn lại, không che.
- **Tách từ:** (**[ĐỀ XUẤT]**, file thiết kế để trống) (a) không còn `C++`, `C#`, `Node.js`, `.NET` bị cắt vụn trong `tokens` (kiểm trên chuỗi thật); (b) mọi kỹ năng ở `job_skills` có token giữ chỗ tương ứng trong `tokens` của đúng JD; (c) token giữ chỗ không nằm trong `tokens_nostop` bị bỏ; (d) bạn đọc 20 JD cạnh nhau (seed 42).
- `rows_in = rows_out + dropped` mọi bước, mọi nguồn (dropped = 0).
- Chạy lại hai lần cùng đầu vào cho cùng hash đầu ra (tái lập, idempotent).
- `pytest tests/unit` xanh; test mới ở mục 8 prompt.
- Nếu chưa đạt cổng: báo số, lỗi còn lại, **không** hạ ngưỡng, **không** thêm model khi chưa được bạn đồng ý.

## 8. Monitoring thấy gì

- Mỗi bước 07/08/09 một khối: số vào/ra, luật bị kích hoạt, ví dụ trước → sau (không chứa toàn văn JD), `extra` ở mục 5. Thiếu báo cáo thì hiện "chưa chạy", không điền 0. Việc thêm vào trang `/preprocessing`, API và dải bước thuộc PH9.

## 9. Không làm

Không tự gán nhãn gold thay bạn; không tự thêm kỹ năng ngoài danh sách bạn duyệt; không đưa danh sách tiêu đề/alias ngắn vào code trước khi bạn duyệt; không chuyển code Encoding sang `processing/`; không gộp 3 taxonomy (chỉ chọn một nguồn, ghi việc dọn vào danh sách); không ghi R2; không cài gói; không đổi hành vi `skill_extractor.py` (giữ làm đối chứng).

## 10. Tổng hợp [CẦN CHỐT]

| Mã | Câu hỏi | [ĐỀ XUẤT] |
|---|---|---|
| P1 | Tên thư mục con và đường dẫn đầu ra 3 bước | `07_sections`, `08_skills`, `09_tokens` |
| P2 | Bảng đầu vào của `processing/` | `04_normalization/all.parquet` hoặc đầu ra mới nhất lúc chạy PH9 |
| S1 | Bảng đầu vào có `benefits_list` không, có tạo bullet `phuc_loi` từ đó không | có nếu cột tồn tại |
| S2 | Thiết kế muốn tách theo thẻ HTML; `text_clean` đã mất thẻ | dùng trường nguồn + dòng tiêu đề + cụm "ưu tiên"; không đọc lại raw |
| S3 | Định nghĩa "tách đúng ≥ 90%" và cách so khi offset gold khác `text_clean` | theo bullet, so nội dung dòng đã `fold` (5.1) |
| S4 | Dòng không thuộc luật nào vào `khac` hay giữ section mặc định | giữ mặc định, `khac` chỉ cho tiêu đề "thông tin khác" |
| K1 | Taxonomy nào (40 / 92 / 230 / ~300 như thiết kế) | `TAXONOMY_230` xuất ra JSON; thêm kỹ năng do bạn duyệt |
| K2 | Kỹ năng trong `mo_ta`/`khac` có `level` gì | `required` (weight 1) nếu không nằm dưới `uu_tien` |
| K3 | Quét trên `text_fold` như thiết kế hay tách alias ngắn khỏi fold | tách (K8.3), vì đo thấy `bi` khớp 1.314/5.077 tin |
| K4 | Có ghi kỹ năng metadata (`via=meta`) vào `job_skills` | có, tách khỏi F1 |
| K5 | Nhãn gold ngoài taxonomy tính thế nào | tính FN, báo riêng |
| K6 | Số JD gold tối thiểu để tuyên bố đạt | bạn quyết (mình không biết bạn gán được bao nhiêu) |
| W1 | Dạng token giữ chỗ kỹ năng | `sk_<slug>` (đã đo `skill_python` đi qua nguyên vẹn; dạng chính xác chưa kiểm hết slug) |
| W2 | Stopword chung: dùng `jd_stopwords_v1.json` (91 từ) hay danh sách mới | dùng lại, ghi version vào báo cáo |
| W3 | Đầu ra bước 9: theo bullet hay theo JD; có giữ cả `tokens` lẫn `tokens_nostop` | theo JD, giữ cả hai |
| W4 | Số có giữ làm token không | giữ (năm kinh nghiệm, `2` `3`...) |
| W5 | Tính DF stopword miền trên toàn corpus hay chỉ train khi có bước giám sát | toàn corpus, ghi rõ |

## 11. Quyết định của người dùng (10/11/2026) và phần đã code

**Đã chốt:** K1 = taxonomy 230 kỹ năng (xuất sang `processing/dictionaries/skills_taxonomy_230.json`, nguồn `TAXONOMY_230`; chưa thêm kỹ năng nào). K3 = tách alias ngắn khỏi đường fold: alias fold ≤ 3 ký tự không chứa `# + .` không bao giờ quét trên văn bản fold, chỉ khớp phân biệt hoa thường trên văn bản gốc, và chỉ các dạng đã duyệt. Danh sách tiêu đề section, cụm "ưu tiên", alias ngắn: chỉ tạo ứng viên `approved:false` (`*_candidates.json`); code chỉ đọc file đã duyệt `section_headings.json`, `priority_cues.json`, `short_aliases.json` (chưa tồn tại = chưa duyệt gì). Các mã còn lại giữ [ĐỀ XUẤT]: P1 `07_sections/08_skills/09_tokens` dưới `data/processing/`, `reports/processing/`, S4, K2, K4, W1 (`sk_<slug>`), W2, W3, W4, W5.

**Mới: giảm thưa ma trận kỹ năng** (`processing/selection/sparsity.py`, tham số cấu hình, mặc định tắt). Ba bước, mọi ngưỡng là **[ĐỀ XUẤT], bạn duyệt sau**:
1. Gộp alias về canonical: đã có sẵn ở lúc khớp (mọi alias trong taxonomy → một `slug`). Gộp thêm giữa hai kỹ năng (`merge_map`) chỉ dùng mục đã duyệt trong `skill_merge_candidates.json`.
2. Ngưỡng DF tối thiểu `min_df` (theo JD, toàn corpus): kỹ năng có DF < `min_df` bị gom vào **họ kỹ năng** `family_<group>` (6 nhóm của taxonomy; `mode=family`) hoặc `other_skill` (`mode=other`); kỹ năng `protected` được giữ. Trùng (JD, kỹ năng) sau gom: level cao nhất, weight lớn nhất, cộng `n_mentions`. [ĐỀ XUẤT] mặc định chưa đặt; số đo dưới đây để chọn.
3. Báo cáo độ thưa trước/sau trong `extra.sparsity` của báo cáo 08 `_all`: mật độ (trên cột đang dùng và trên 230), kỹ năng/JD (TB, trung vị), JD 0 kỹ năng, số cột có DF dưới 3/5/10/20/50.

Số đo (`scripts/ph8_measure.py`, 5.077 tin của `01_clean`, `via=text`, chưa có tiêu đề/cụm duyệt, chưa có alias ngắn duyệt): 32.879 cặp (JD, kỹ năng), 220 cột dùng, mật độ 0,0294, TB 6,48 kỹ năng/JD, 414 JD 0 kỹ năng; số cột DF < 3/5/10/20/50 = 15/26/42/61/99. Gom họ với `min_df`=10: 183 cột, mật độ 0,0354; `min_df`=20: 164 cột, 0,0394; `min_df`=50: 127 cột, 0,0505 (mất TB kỹ năng/JD 6,48 → 6,42). Giả định duyệt hết 49 alias ngắn ứng viên không mơ hồ: 38.615 cặp, 225 cột, TB 7,61, 347 JD 0 kỹ năng. Alias ngắn gây nhiễu trên fold (số tin khớp fold so với khớp hoa thường): `bi` 1314/363, `ba` 675/554, `soc` 285/81, `js` 271/34, `c` 267/241, `lua` 231/4.

**Đánh giá gold:** `processing/evaluate.py` + `scripts/eval_gold_processing.py --gold <file>` đọc đúng định dạng `gold.py`. Chưa có file nhãn nên **chưa đo F1 và độ đúng section**; test chỉ chạy đường code trên fixture tay tối thiểu. Gold chỉ có chuỗi `text` (không tách mô tả/yêu cầu), nên script tra lại `description/requirements` từ `01_clean` theo `job_id_global`.
