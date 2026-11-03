# P3. Transformation: ép kiểu, parse số, làm sạch chữ, dịch JD, rút kỹ năng và phúc lợi

> **Cập nhật 04/11/2026: dự án bỏ hẳn model/LLM (JEV qua OpenCode, Gemini).** Mọi đoạn trong file này nói về JEV, LLM, GenAI, dịch JD, `--use-api`, cache hay sổ tiền API đã hết hiệu lực. Thay bằng luật if-else: xem `docs/preprocessing/spec/P0_pipeline_contract.md` mục 6 và `docs/issue_log.md` L-28.

> Trạng thái: **đã làm, chạy thật 03/11/2026** (8.378 → 8.378, chưa dịch). Sửa sau review 03/11 ở mục 8.
> Prompt: `docs/prompting/P3_transformation.md`.

## 1. Ngữ cảnh

| Vấn đề | Số liệu | Mã |
|---|---|---|
| Bộ parse lương đọc dấu phẩy hàng nghìn thành dấu thập phân | "Up to 2,000 USD" → 50.800 VND; 59 tin ra lương < 1 triệu (TopDev 29, TopCV 11, ITviec 5, Glints 5…); một phần là thực tập thật ("0.5 - 1 triệu") | D2 |
| "Từ X" gán max = min | 192 tin (TopDev 86, JobsGO 57, TopCV 49) | D3 |
| Chỉ có một đầu ("Up to", "Tới") | TopCV 243, JobsGO 138 | D4 |
| Lương USD | ITviec 24,7%, VietnamWorks 13,0% | D5 |
| Lương nằm trong tiêu đề | JobsGO 212, TopCV 140, Vieclam24h 80, TopDev 76 | D7 |
| Null trá hình | VietnamWorks `raw_education_text = "0"` ở 309 tin | C4 |
| Kinh nghiệm nhiều dạng chữ | "Không yêu cầu", "1 - 2 năm", "Dưới một năm kinh nghiệm" | F1 |
| Kỹ năng là câu hoặc danh mục | tag > 4 từ: TopCV 3.771, JobsGO 3.617, Vieclam24h 3.398; "Việc làm TP.HCM", "IT - Phần mềm" | G1, G2 |
| Địa chỉ đường phố, nhiều thành phố trong một chuỗi | ITviec 418 giá trị địa chỉ; nhiều thành phố: ITviec 888, VietnamWorks 603 | E1, E2 |
| HTML/entity còn sót | VietnamWorks 8 tin | I2 |
| JD tiếng Anh hoặc song ngữ | chưa đếm trên bộ mới (bộ golden cũ có cột `language`); đếm ở `--dry-run` của T6b | — |
| Hạn nộp trước ngày cào | TopCV 486 tin (chưa rõ do tin hết hạn hay đọc sai `dd/mm/yyyy`) | H3 |

## 2. Input

`data/preprocessing/02_integration/<nguồn>.parquet`.

## 3. Output

`data/preprocessing/03_transformation/<nguồn>.parquet`: giữ mọi cột `raw_*` của P2 để đối chiếu, thêm:

| Cột mới | Kiểu | Từ |
|---|---|---|
| `salary_min_vnd`, `salary_max_vnd` | float, null được | `raw_salary_text`, rồi tiêu đề, rồi JD |
| `salary_currency_raw`, `salary_period_raw` | str | VND/USD; tháng/năm |
| `is_negotiable` | bool | thỏa thuận, cạnh tranh… |
| `salary_source` | str | `header`, `title`, `jd`, `none` |
| `posted_date`, `deadline_date` | date, null được | `raw_posted_date`, `raw_deadline` |
| `exp_min_years`, `exp_max_years` | float, null được | `raw_experience_text` |
| `headcount` | int, null được | `raw_headcount` |
| `job_title_clean` | str | `job_title` bỏ mã, ngoặc, số tin, viết hoa toàn bộ (I3) |
| `description_clean`, `requirements_clean` | str | bỏ HTML, nối bullet |
| `skills_clean` | list[str] | `skills_list` đã làm sạch, gộp với kỹ năng rút từ JD (T7) |
| `benefits_std` | list[str] | phúc lợi rút bằng từ điển (T7) |
| `description_vi`, `requirements_vi` | str | bản tiếng Việt (T6b); JD vốn tiếng Việt thì bằng bản sạch |
| `translated_by` | str, null được | tên model đã dịch; `null` nếu không phải dịch |
| `locations` | list[dict] JSON | địa điểm 3 cấp `dia_chi_cu_the`, `phuong_xa`, `tinh_thanh` + `raw`, tách chữ, **chưa chuẩn hóa** (T8) |
| `language` | str | `vi`, `en`, `bilingual` |
| `flags` | list[str] | ví dụ `deadline_before_crawl`, `salary_under_1m` |

## 4. Hướng xử lý (đúng thứ tự)

| Mã | Luật | Ví dụ trước → sau |
|---|---|---|
| T1 | Null trá hình → null, dùng `preprocessing/missing_outlier/sneaky_null_detector.py` | `raw_education_text="0"` → null |
| T2 | Lương: sửa `UniversalSalaryParser` (`preprocessing/transformation/salary_parser.py`) | |
| T2a | Dấu phân cách hàng nghìn: `2,000` và `2.000` là 2000 khi theo sau đủ 3 chữ số; `8.5` vẫn là 8,5 | "Up to 2,000 USD" → max 50.800.000 |
| T2b | "Từ X" chỉ đặt min, max = null | "Từ 15 triệu" → min 15tr, max null |
| T2c | "Up to X", "Tới X" chỉ đặt max | "Up to 30tr" → min null, max 30tr |
| T2d | USD × 25.400; theo năm chia 12 | "1,500 USD" → 38.100.000 |
| T2e | Thỏa thuận → `is_negotiable=true`, số để NaN (MNAR, không bù). Có số trong tiêu đề thì lấy, `salary_source="title"`, rồi mới đến JD | title "Dev (15-20tr)" → 15tr–20tr |
| T2f | Kết quả < 1 triệu: giữ số, gắn cờ `salary_under_1m` để P4 xem lại | "0.5 - 1 triệu" → giữ, cờ |
| T3 | Ngày: ISO và `dd/mm/yyyy` → date; hạn nộp trước ngày cào thì gắn cờ, không sửa | "15/10/2026" → 2026-10-15 |
| T4 | Kinh nghiệm → khoảng năm | "Không yêu cầu" → 0–0; "1 - 2 năm" → 1–2; "Trên 3 năm" → 3–null; "Dưới 1 năm" → 0–1 |
| T5 | Headcount → int | "2 người" → 2 |
| T6 | Chữ: bỏ HTML/entity (`html_cleaner.py`), nối bullet (`bullet_stitcher.py`), làm sạch tiêu đề, đo `language` (`text_metrics.detect_language`) | "&amp;nbsp;Java" → "Java" |
| T6b | **Dịch JD sang tiếng Việt** bằng LLM (P0 mục 6), chỉ cho `language` ∈ {`en`, `bilingual`}. Prompt dịch có **bảng không dịch**: mọi kỹ năng trong từ điển kỹ năng, tên công cụ và công nghệ, chức danh kỹ thuật (Backend, Frontend, DevOps…), khóa cấp bậc (Intern, Fresher, Junior, Middle, Senior, Lead, Manager). Có cache, có `--use-api` | "Experience with Python and Docker is a plus" → "Có kinh nghiệm với Python và Docker là một lợi thế" |
| T7a | Kỹ năng từ trường: bỏ tag > 4 từ, tag khớp danh mục ngành hoặc "Việc làm …", tag là tên công ty; bỏ trùng không phân biệt hoa thường | `["Java","Việc làm TP.HCM","java"]` → `["Java"]` |
| T7b | **Rút kỹ năng từ JD bằng từ điển song ngữ** `preprocessing/dictionaries/skills.json` (file mới: tên chuẩn → các cách viết tiếng Anh, tiếng Việt), khớp theo từ nguyên vẹn trên `description_clean` + `requirements_clean` (bản gốc, không dùng bản dịch); gộp với T7a | JD "Thành thạo ReactJS, có kiến thức về cơ sở dữ liệu SQL" → thêm `React`, `SQL` |
| T7c | **Rút phúc lợi** từ `benefits_list` + JD bằng `preprocessing/dictionaries/benefits.json` (file mới), song ngữ | "Đăng Ký Hưởng Bảo hiểm (insurance)", "13th month salary" → `["Bảo hiểm", "Lương tháng 13"]` |
| T8 | **Địa điểm 3 cấp**: tách mỗi địa điểm (theo `working_locations`, rồi `raw_location_text`, rồi `company_address`) thành `{dia_chi_cu_the, phuong_xa, tinh_thanh, raw}`. Tỉnh nhận theo tên trong `provinces_34.json` (cả tên cũ); phường/xã nhận theo tiền tố "Phường", "Xã", "P.", "Đặc khu"; phần còn lại là địa chỉ cụ thể. "Quận/Huyện" (cấp đã bỏ sau 01/07/2025) giữ trong `dia_chi_cu_the`. Không chắc thì để null, không đoán | "Tòa nhà MB, 18 Lê Văn Lương, P. Thanh Xuân, Hà Nội" → `{"dia_chi_cu_the": "Tòa nhà MB, 18 Lê Văn Lương", "phuong_xa": "Phường Thanh Xuân", "tinh_thanh": "Hà Nội"}` |
| T9 | ~~Bù giá trị bằng imputer Gemini~~: **bỏ**. Ô còn null giữ null; cấp bậc và nhóm nghề còn thiếu do P4 xử lý bằng luật + JEV có xác suất | — |

## 5. Ranh giới

- Không bỏ dòng (`rows_out = rows_in`).
- Không cap outlier, không log, không ánh xạ về từ điển chuẩn (để P4).
- Không ghi đè cột `raw_*`.
- Bản dịch không thay bản gốc; mọi bước sau rút thông tin từ bản gốc, bản dịch chỉ để đọc và phân tích văn bản tiếng Việt.
- Từ điển không thêm kỹ năng không xuất hiện trong chữ.

## 6. Monitoring thấy gì

- Lương: phân bố `salary_source`, số tin sửa nhờ T2a, T2b (so với parser cũ trên cùng input); 3 ví dụ mỗi luật.
- Bảng "chữ → số" cho kinh nghiệm: giá trị chữ phổ biến nhất và kết quả parse; số chưa parse được.
- Kỹ năng: số tag bị bỏ theo lý do.
- Địa điểm: tỉ lệ có đủ 3 cấp, chỉ có tỉnh, không nhận được; ví dụ mỗi loại.
- Dịch: số JD đã dịch theo nguồn, model, chi phí; 3 cặp gốc → dịch.
- Kỹ năng, phúc lợi: số kỹ năng thêm từ JD theo nguồn, top phúc lợi.

## 7. Tiêu chí xong và cách review

- Số tin < 1 triệu giảm từ 59 xuống chỉ còn tin thực tập thật (xem từng tin còn lại).
- 192 tin "Từ X" đều có max = null.
- Kinh nghiệm: ≥ 90% giá trị chữ có trong raw được parse.
- Review: so 20 dòng ngẫu nhiên (seed cố định) giữa cột `raw_salary_text` và `salary_min/max_vnd`; 20 dòng kinh nghiệm.
- Test: mỗi luật T2a–T2f, T3, T4, T7 một test; test cũ của `salary_parser` vẫn qua (sửa test nào đang khẳng định hành vi sai thì ghi rõ).
- Dịch: chấm 30 JD (2 model, P0 mục 6). Đạt khi không có bản nào dịch mất thuật ngữ trong bảng không dịch hoặc sai nghĩa yêu cầu.
- Từ điển kỹ năng: 20 JD ngẫu nhiên, so kỹ năng rút được với đọc tay.
- H3: kiểm 10 tin TopCV có hạn nộp trước ngày cào trên trang, ghi kết luận vào báo cáo.

## 8. Sửa sau review 03/11/2026

| Mục | Trước | Sau |
|---|---|---|
| Input/Output | file theo nguồn | `02_integration/all.parquet` → `03_transformation/all.parquet` |
| T2 lương | tiêu đề/JD nhận mọi số: 676 tin lấy lương từ tiêu đề, phần lớn sai ("(2026TD450981)" → 2 tỷ, "Microsoft 365" → 365 triệu, "2+ Năm … Upto 35 Triệu" → 2,9 triệu) | tiêu đề/JD chỉ nhận cụm có đơn vị tiền; đơn vị "triệu/m" phải đứng sát số; số có dấu hàng nghìn đọc đủ; ngoài 1–500 triệu/tháng → NaN + `salary_suspect` (T2f). Còn 27 tin lấy từ tiêu đề, 33 tin nghi sai |
| T6 ngôn ngữ | đếm từ khóa, 1.583 tin "bilingual" | chỉ xét JD, bỏ dòng đầu TopCV, chữ có dấu < 1% → `en`. Kết quả: 6.593 `vi`, 1.785 `en` |
| T6b dịch | dịch cả `bilingual`, cắt ở 4.000 ký tự, file chấm tạo lúc dry-run nên trống | chỉ dịch `en`; chia đoạn ≤ 3.000 ký tự; file `translate_30.csv` chỉ ghi khi có bản dịch thật của 2 model (Mistral Small 3.2, DeepSeek V3.2); dịch toàn bộ chỉ khi có `preprocessing/transformation/translate_model.json`; trần chung 0,95 USD |
| T7 kỹ năng | "c", "go", "py", "ts" khớp chữ đứng riêng: "C" ở 6.912/8.373 tin | "C" chỉ khi "C/C++", "ngôn ngữ C"…; bỏ "go", "py", "ts". Còn 243 tin |
| T8 địa điểm | giữ "Quận 1", "Địa chỉ trụ sở:", phường cụt ngoặc; "Điện Biên Phủ" → tỉnh Điện Biên | bỏ quận/huyện; `phuong_xa` phải có trong `dictionaries/wards_34.json` (3.321 phường/xã mới, nguồn thanglequoc/vietnamese-provinces-database, MIT); tên phường cũ → null. 3.456 tin có phường |
