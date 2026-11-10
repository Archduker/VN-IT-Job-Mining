# Tiền xử lý dữ liệu JD ngành IT cho Data Mining

Nov 10, 2026 · @BIll

## 1. Đề tài

**Tích hợp Data Mining vào phân tích nghề nghiệp và kỹ năng ngành IT.** Tài liệu này chỉ chốt phần xử lý và tiền xử lý: biến JSON tin tuyển dụng (JD) thô thành bộ dữ liệu sạch, unique, có cấu trúc, sẵn sàng cho các bước khai phá.

| Hạng mục | Chốt |
| --- | --- |
| Dữ liệu | Tin tuyển dụng IT tại Việt Nam, chỉ cào, không dùng bộ dữ liệu có sẵn |
| Nguồn | 8 nguồn |
| Quy mô | Không đặt số mẫu mục tiêu. Báo cáo số tin đưa vào pipeline (hiện 10.758 tin mới nhất trước lọc IT, theo `docs/spec/preprocessing/data_issues_2026-11-03.md`) và số còn lại sau mỗi bước (bảng phễu, mục 4.3). Cào đều theo tuần |
| Định dạng thô | JSON, lưu trên R2 (data lake), xử lý theo ELT, đưa dữ liệu `curated` vào PostgreSQL Mart |
| Thời gian | 8 tuần |
| Đầu ra của tiền xử lý | Bảng JD sạch, bảng bullet theo section, bảng kỹ năng của từng JD, đặc trưng và vector cho phân tích |

Tiền xử lý là phần quyết định chất lượng của cả đề tài. Mọi phân tích phía sau (nhóm nghề, kỹ năng đi cùng nhau, kỹ năng theo cấp bậc, kỹ năng ảnh hưởng tới lương) đều dùng output của nó, đặc biệt là bảng kỹ năng.

Tiền xử lý được trình bày theo 4 nhóm tác vụ của giáo trình Han, Kamber & Pei (*Data Mining: Concepts and Techniques*): **Data Cleaning, Data Integration, Data Reduction, Data Transformation & Discretization**. Chất lượng đầu ra đo theo **5 tiêu chí của dự án**: completeness, accuracy, consistency, timeliness, uniqueness. Cột "Chiều chất lượng" trong các bảng bên dưới dùng 6 chiều của giáo trình (accuracy, completeness, consistency, timeliness, believability, interpretability); ánh xạ sang 5 tiêu chí (**đề xuất, cần bạn xác nhận**): believability → accuracy, interpretability → consistency, còn uniqueness là tiêu chí thêm, do bước khử trùng đảm nhiệm.

## 2. Phân tích các lỗi

JSON cào từ 8 nguồn có 26 loại lỗi, chia vào 4 nhóm tiền xử lý. Lỗi nguy hiểm nhất là lỗi âm thầm: không báo gì nhưng làm sai kết quả, ví dụ Unicode NFC/NFD, trùng lặp khác nguồn, tokenizer cắt hỏng tên kỹ năng.

### 2.1. Lỗi cần làm sạch (Data Cleaning)

| Lỗi | Ví dụ | Hậu quả nếu bỏ qua | Chiều chất lượng |
| --- | --- | --- | --- |
| HTML còn sót | `<li>`, `&nbsp;`, `&amp;` | Nhiễu từ vựng, regex bắt sai | Accuracy |
| Unicode không thống nhất | "ệ" mã hoá kiểu NFC và NFD | Cùng một từ thành hai từ khác nhau, hash khử trùng lặp sai | Consistency |
| Ký tự ẩn | `​`, `﻿`, `\xa0` | Regex và hash hỏng mà mắt thường không thấy | Accuracy |
| Gạch ngang, bullet lẫn lộn | `– — −`, `• ✔ ➢` | Parse sai khoảng lương "15–25", tách bullet sai | Consistency |
| Tiếng Việt không dấu | "kinh nghiem", "tieng nhat" | Từ điển không khớp, mất kỹ năng và yêu cầu | Consistency |
| Viết tắt, teencode | kn, tr, ĐH, BE/FE, CTV | Không hiểu đúng nghĩa khi trích xuất | Interpretability |
| Tin không phải IT | "Sales phần mềm", "Kế toán" gắn nhãn IT. Tiêu đề không khớp từ khóa IT (ước lượng thô): TopDev 81,8%, Vieclam24h 55,0%, JobsGO 32,7% (A1) | Sai phạm vi, lệch kết quả phân tích | Believability |
| Tin rác, quá ngắn | Mô tả dưới 50 từ, tin tuyển CTV, đa cấp | Nhiễu phân cụm và luật kết hợp | Believability |
| Lương "Thỏa thuận" | "Thỏa thuận", "Cạnh tranh" | Thiếu dữ liệu kiểu MNAR: vị trí cao hay giấu lương, điền trung bình sẽ làm sai phân phối | Completeness |
| Thiếu cấp bậc, kinh nghiệm, địa điểm | Một số nguồn không có trường này | Thiếu đặc trưng khi phân tích | Completeness |
| Lương parse sai | "2000" bị hiểu là 2000 triệu thay vì 2000 USD; lương năm bị hiểu là lương tháng | Ngoại lai giả | Accuracy |
| Lương: dấu phân cách hàng nghìn | "Up to 2,000 USD" bị đọc thành 50.800 VND; 59 tin ra lương dưới 1 triệu (D2) | Ngoại lai giả | Accuracy |
| Lương: "Từ X" hoặc chỉ có một đầu | "Từ 15 triệu" chỉ có mức sàn nhưng bị gán max = min (192 tin, D3); "Up to", "Tới" chỉ có mức trần (D4) | Khoảng lương sai | Accuracy |
| Lương nằm trong tiêu đề | JobsGO 212, TopCV 140, Vieclam24h 80, TopDev 76 tin (D7) | Mất lương khi trường lương trống | Completeness |
| Null trá hình | Giá trị kiểu "N/A", "Không yêu cầu" thay cho thiếu thật (đã có `sneaky_null_detector.py`, chưa có số đo trong `data_issues`) | Đếm sai tỉ lệ thiếu | Completeness |
| Ngoại lai thật | Lương rất cao so với cấp bậc | Kéo lệch mô hình hồi quy | Accuracy |

### 2.2. Lỗi khi hợp nhất 8 nguồn (Data Integration)

| Lỗi | Ví dụ | Hậu quả nếu bỏ qua |
| --- | --- | --- |
| Mỗi nguồn một schema | `salary` / `luong` / `salary_text`; có nguồn tách sẵn 3 phần JD, có nguồn không | Không ghép được dữ liệu |
| Trùng trong cùng nguồn | Cùng tin bị cào lại ở tuần sau | Đếm sai tần suất kỹ năng |
| Nhiều snapshot `_v<N>` của cùng tin | 1.975 snapshot v>1 (TopDev 1.105, VietnamWorks 725) (B1) | Đếm trùng nếu không chọn bản mới nhất |
| File batch cũ trùng file từng tin | VietnamWorks 931 tin, Vieclam24h 616 tin (B2) | Trùng cả loạt |
| Trùng khác nguồn (gần trùng) | Một công ty đăng cùng tin trên TopCV và VietnamWorks, chỉ khác vài dòng | Trùng mẫu, rò rỉ giữa train và test |
| Tên công ty nhiều biến thể | "Công ty TNHH FPT Software", "FPT Software JSC" | Không nhóm được theo công ty, không chia train/test theo công ty được |
| Ngày tương đối | "2 ngày trước", "3 weeks ago" | Sai mốc thời gian (Timeliness) |
| Ngày tương đối nằm trong hash | ITviec lưu "Đăng 6 giờ trước" (855 tin), làm hash đổi mỗi lần cào (A2) | Tin không đổi vẫn bị coi là đổi |
| Trường thiếu theo nguồn | TopDev: kinh nghiệm, cấp bậc 0,1%, ngày đăng 0%; ITviec và Glints: cấp bậc 0% (mục C của `data_issues`) | Không so sánh được giữa nguồn |
| Đơn vị và định dạng khác nhau | Lương triệu/USD; "HCM", "TP.HCM", "Sài Gòn"; "2+ năm", "Không yêu cầu" | Không so sánh được giữa các nguồn |
| Ngôn ngữ lẫn | ITviec, TopDev có nhiều JD tiếng Anh (khoảng 24,2% toàn bộ tin, theo `KNOWN_ISSUED.md`) | Bỏ đi thì lệch nguồn, giữ nguyên thì từ điển tiếng Việt không khớp. Chốt: dịch hết sang tiếng Việt (bước 4b) |

### 2.3. Lỗi trong phần văn bản dài (Reduction & Transformation)

| Lỗi | Ví dụ | Hậu quả nếu bỏ qua |
| --- | --- | --- |
| 3 phần JD trộn vào nhau | Mô tả, Yêu cầu, Phúc lợi, giới thiệu công ty nằm chung một đoạn | Không phân biệt kỹ năng bắt buộc với ưu tiên; phúc lợi (MacBook, du lịch) làm nhiễu phân cụm |
| Kỹ năng nhiều cách viết | ReactJS / React.js / react; riêng "React Native" là kỹ năng khác | Đếm tần suất sai, luật kết hợp sai |
| Tên kỹ năng ngắn, mơ hồ | Go, R, C | Bắt nhầm từ thường |
| Tokenizer cắt hỏng tên kỹ năng | `C++` thành `C` `++`, `Node.js` thành `Node` `js` | Mất kỹ năng sau khi tách từ |
| Stopword theo miền | ứng\_viên, công\_ty, môi\_trường, năng\_động | Chiếm trọng số, làm mờ đặc trưng TF-IDF |
| Đoạn mở đầu JD giống nhau | 300 ký tự đầu giống hệt: TopDev 739, JobsGO 479, Vieclam24h 213 tin (B5), thường là giới thiệu công ty chung | Làm nhiễu TF-IDF và khử trùng gần trùng |
| Kỹ năng hiếm, số chiều lớn | Hàng nghìn từ vựng, kỹ năng xuất hiện 1–2 lần | Vector thưa, không đủ thống kê |
| Phân phối lương lệch phải | Ít tin lương rất cao | Mô hình tuyến tính bị kéo lệch |

## 3. Quy trình xử lý

Dữ liệu đi qua 3 tầng Bronze → Silver → Gold với 13 bước theo thứ tự cố định. **Bronze giữ nguyên JSON thô**; mọi biến đổi bắt đầu từ lúc chuyển sang Silver.

### 3.1. Kiến trúc 3 tầng

| Tầng | Nội dung | Vị trí | Các bước |
| --- | --- | --- | --- |
| **Bronze** | File JSON nguyên văn từ crawler. Chỉ ghi thêm (append-only), không parse, không sửa, không xoá. Crawler ghi sẵn `source`, `crawled_at` (cần đối chiếu envelope thật xem có `crawl_week` không) | `raw/<source>/<YYYY-MM-DD>/<job_id>_v<N>.json`, sổ cái ở `url_ledger/<source>/catalog_master.json` (R2) | Bước 0 chỉ đọc |
| **Silver** | Dữ liệu đã đồng nhất schema, sạch, unique, chuẩn hoá; bảng bullet; bảng kỹ năng | `staging/` (Parquet): jobs, bullets, job_skills. Nơi đặt bảng `rejected` chờ chốt | Bước 1 → 8 |
| **Gold** | Dữ liệu sẵn sàng cho phân tích và model: ma trận kỹ năng, đặc trưng, vector | `curated/` (Parquet, `.npy`); golden file hiện là `curated_flat_golden_jobs.parquet` | Bước 9 → 12 |
| **Pipeline** | Đầu ra và báo cáo của từng bước (mỗi bước một thư mục con), để xem lại từng bước và chạy lại riêng một bước | `pipeline/<bước>/` (R2), cạnh `raw/`, `staging/`, `curated/` | Mọi bước |

Khi đổi bất kỳ quy tắc nào (ngưỡng, từ điển), chỉ cần xoá Silver/Gold rồi chạy lại từ Bronze, không phải cào lại.

### 3.1b. Ánh xạ các bước sang quy trình 4 giai đoạn của dự án

Dự án chốt 4 giai đoạn: Collection → Pre-processing → Processing → Mining. Ánh xạ dưới đây là **đề xuất, cần bạn duyệt**:

| Giai đoạn | Bước trong file này | Việc dự án yêu cầu |
| --- | --- | --- |
| Collection | Bước 0 chỉ đọc Bronze | Cào, lọc, khử trùng, JSON đầy đủ trường |
| Pre-processing | 0, 1, 2, 3, 4, 4b, 5, 6 | Imputation, deduplicate, noise, typecasting, string standardization |
| Processing | 7, 8, 9, 10, 10b, 10c, 10d, 12 | Feature extraction (7, 8, 12), transformation (9, 10), selection (10b), construction (10c), encoding (10d) |
| Mining | ngoài phạm vi file này | Unsupervised: clustering, association rules, anomaly detection, dimensionality reduction |

Các bước 10b, 10c, 10d là bước mới thêm cho đủ 4 bước feature engineering và encoding; nội dung chi tiết của 10b, 10c còn để trống chờ bạn chốt.

### 3.2. Thứ tự và những chỗ không được đảo

- **NFC trước hash**: nếu không, hai văn bản giống hệt nhau nhưng khác mã hoá dấu sẽ lọt qua khử trùng lặp.
- **Lọc phạm vi trước khử trùng lặp gần trùng**: không tốn MinHash cho những tin sắp bị loại.
- **Khử trùng lặp trước khi chia train/test**: nếu không, cùng một JD nằm ở cả hai tập, điểm mô hình cao ảo.
- **Trích xuất kỹ năng trước khi tách từ**: tokenizer cắt hỏng `C++`, `Node.js`.
- **Dịch sau khi lọc phạm vi và khử trùng, trước khi tách section và trích kỹ năng**: không tốn thời gian dịch cho tin sắp bị loại (vị trí này là đề xuất, cần bạn duyệt).
- **Chỉ fit trên tập train**: TF-IDF, scaler, ngưỡng lọc tần suất đều fit trên train rồi mới áp cho test.

### 3.3. Bảng chốt từng bước

| # | Bước | Nhóm | Chốt | Đầu ra | Xong khi |
| --- | --- | --- | --- | --- | --- |
| 0 | Profiling | – | `ydata-profiling` trên 500 tin mỗi nguồn + script đo tỉ lệ thiếu theo trường × nguồn (vẽ heatmap màu), tỉ lệ còn HTML, tỉ lệ NFD, tỉ lệ không dấu | Báo cáo HTML, bảng "trước xử lý" | Có số đo hiện trạng cho cả 8 nguồn |
| 1 | Đồng nhất schema | Integration | Mỗi nguồn một hàm `map_<nguồn>()`. Kiểm tra bằng `pydantic`. `job_id = <nguồn>_<id gốc>`. Bắt buộc có `crawled_at`. Bản ghi lỗi vào `rejected/` kèm lý do | `staging/jobs` | Không bản ghi nào mất mà không có lý do |
| 2 | Làm sạch ký tự | Cleaning | `get_text("\n")` → `html.unescape` → NFC → bỏ `​ ﻿ \xa0` → chuẩn hoá gạch ngang, bullet → gộp khoảng trắng. Lưu 3 cột: `text_clean`, `text_norm` (viết thường), `text_fold` (viết thường + bỏ dấu, chỉ để so khớp). Từ điển viết tắt trong file từ điển |  | 0% còn HTML, 0% còn NFD |
| 3 | Lọc phạm vi | Cleaning | Luật từ khoá title để lọc tin không phải IT. Bỏ tin có mô tả dưới 50 từ, tin CTV/đa cấp. Giữ cả JD tiếng Anh, gắn cột `lang` (fastText `lid.176`); dịch ở bước 4b |  | Kiểm tay 100 tin bị loại, loại nhầm dưới 5% |
| 4 | Khử trùng lặp | Reduction | 3 tầng: `nguồn + id` → `sha1(text_fold)` → MinHash (shingle 5 từ, 128 perm, ngưỡng 0.85) kết hợp khoá `company_key + title_key`. Giữ bản đầy đủ nhất; lưu `duplicate_of`, `sources[]` |  | Precision ≥ 95% trên 50 cặp gần ngưỡng |
| 4b | Dịch JD tiếng Anh → tiếng Việt | Transformation | Dịch **toàn bộ** JD có `lang` = en bằng `VietAI/envit5-translation`, chạy local (Hugging Face). Giữ nguyên cột JD gốc; thêm cột JD tiếng Việt dùng cho các bước sau; tính lại `text_norm`, `text_fold` trên bản dịch. Model có giới hạn độ dài đầu vào, JD dài cần cắt theo bullet hoặc câu rồi ghép lại (cần kiểm giới hạn thực tế khi làm). Ghi `<trường>_source` = `model`, tên và phiên bản model vào `meta.json`. Tên kỹ năng viết bằng tiếng Anh (React, Docker...) phải giữ nguyên sau khi dịch | `staging/jobs` | Kiểm tay 50 JD đã dịch: kỹ năng và số liệu (lương, năm kinh nghiệm) không bị đổi |
| 5 | Chuẩn hoá trường | Integration + Transformation | Lương → VND/tháng, **1 USD = 25.400đ**, mặc định gross; dấu `.` `,` trong số là phân cách hàng nghìn; "Từ X" chỉ có mức sàn, "Up to/Tới X" chỉ có mức trần, không gán min = max. Kinh nghiệm → số năm tối thiểu. Cấp bậc → 5 cấp (Intern/Fresher, Junior, Middle, Senior, Lead/Manager, theo `docs/spec/03_data_mining_lifecycle.md`). Địa điểm → 34 tỉnh thành sau sáp nhập (`preprocessing/dictionaries/provinces_34.json`); Remote/Hybrid là cột hình thức làm việc riêng (theo `docs/spec/01_product_spec.md`). Nhóm nghề → 12 nhóm của `docs/spec/01_product_spec.md` + nhóm **Other** cho tin chưa xác định được (bằng luật từ khoá title và kỹ năng). Công ty → `company_key` + `rapidfuzz` ≥ 90. Ngày → tuyệt đối theo `crawled_at` |  | Mỗi parser đúng ≥ 95% trên 50 chuỗi thật |
| 6 | Thiếu & ngoại lai | Cleaning | Lương "Thỏa thuận": không điền, tạo cờ `salary_negotiable`. Cấp bậc trống: suy từ title, gắn `level_inferred`. Kinh nghiệm trống: suy từ cấp bậc hoặc `unknown`. Lương ngoài 2–200 triệu: sửa lỗi parse. IQR theo từng cấp bậc: chỉ gắn cờ |  | Có bảng chiến lược xử lý thiếu kèm lý do |
| 7 | Tách section, bullet | Transformation | Lấy theo thẻ HTML nếu nguồn có; không có thì regex tiêu đề. 5 section: `mo_ta / yeu_cau / uu_tien / phuc_loi / khac`. Mỗi bullet một dòng | `staging/bullets` | Tách đúng ≥ 90% trên bộ gold |
| 8 | Trích xuất kỹ năng | Transformation | Taxonomy (file từ điển) khoảng 300 kỹ năng kèm alias. Quét Aho–Corasick trên `text_fold`, có ranh giới từ. Trọng số: bắt buộc = 1, ưu tiên = 0.5 | `staging/job_skills` | F1 ≥ 0.85 trên bộ gold |
| 9 | Tách từ, stopword | Transformation | Thay kỹ năng bằng token chuẩn trước, rồi tách từ bằng `underthesea`. Stopword 2 lớp: chung + theo miền (DF > 60%) | `gold/` |  |
| 10 | Biến đổi, rời rạc hoá | Transformation | `log1p` lương. Khoảng lương: equal-frequency 5 nhóm và theo miền. Kinh nghiệm 0 / 1–2 / 3–5 / >5. Thành phố top 5 + `other`. Bỏ kỹ năng xuất hiện dưới 5 lần | `gold/` |  |
| 10b | Chọn đặc trưng (feature selection) | Transformation | Bỏ kỹ năng xuất hiện dưới 5 lần (chuyển từ bước 10). Các tiêu chí chọn khác: chưa chốt | `curated/` |  |
| 10c | Xây đặc trưng (feature construction) | Transformation | Danh sách đặc trưng mới tạo: chưa chốt | `curated/` |  |
| 10d | Encoding | Transformation | Multi-hot kỹ năng, ordinal cấp bậc, one-hot/cờ nhị phân theo `docs/spec/preprocessing/spec/P5_encoding.md` | `curated/` |  |
| 11 | Chia train/test | – | **Tùy chọn** (mining chỉ unsupervised, chỉ cần khi chạy mô hình có giám sát). `GroupShuffleSplit` theo công ty, 80/20, `random_state=42`. Mọi bước fit nằm trong `sklearn.Pipeline` | `features/` | Không công ty nào ở cả hai tập |
| 12 | Vector hoá | Transformation | TF-IDF (ngram 1–2, `min_df=5`, `max_features=20k`) và `multilingual-e5-base` (tùy chọn). Embedding tính một lần, lưu cache | `features/` |  |

### 3.4. Chiến lược xử lý dữ liệu thiếu

| Trường | Cơ chế thiếu | Cách xử lý | Lý do |
| --- | --- | --- | --- |
| Lương "Thỏa thuận" | MNAR | Không điền; cờ `salary_negotiable`; hồi quy lương chỉ dùng tin có lương | Điền trung bình kéo lương vị trí cao xuống |
| Cấp bậc | MAR (phụ thuộc nguồn, title) | Suy từ title, cờ `level_inferred` | Luôn phân biệt được giá trị gốc và giá trị suy ra |
| Kinh nghiệm | MAR | Suy từ cấp bậc, không được thì `unknown` |  |
| Địa điểm | MCAR | `unknown` | Tỉ lệ nhỏ |

## 4. Cách áp dụng

Nhóm chỉ gán tay một bộ gold 100 JD để đánh giá, dùng luật và model có sẵn để xử lý, và chỉ train model riêng khi một bước đo ra kết quả kém.

### 4.1. Bộ gold 100 JD (phần gán nhãn duy nhất bắt buộc)

Mỗi nguồn lấy khoảng 12–13 JD (100 JD chia 8 nguồn). Chỉ một người gán nhãn, bằng một file `.html` mở trực tiếp trên trình duyệt (công cụ gán nhãn, giao diện gọn gàng, xuất ra file nhãn). Không cần cố định nơi lưu file nhãn. Bộ này dùng để đánh giá, không dùng để train, và dùng lại cho mọi bước:

| Gán gì trên mỗi JD | Đo bước nào | Chỉ số |
| --- | --- | --- |
| IT hay không IT | Bước 3 – lọc phạm vi | Accuracy |
| Lương, kinh nghiệm, cấp bậc, địa điểm đúng | Bước 5 – các parser | Tỉ lệ đúng |
| Ranh giới các section | Bước 7 – tách section | Tỉ lệ tách đúng |
| Danh sách kỹ năng, bắt buộc hay ưu tiên | Bước 8 – trích xuất kỹ năng | Precision / Recall / F1, báo cáo theo từng nguồn |

Ngoài bộ gold, có 3 lần kiểm tay nhỏ: 100 tin bị loại ở bước 3, 50 cặp gần ngưỡng ở bước 4, 50 chuỗi thật cho mỗi parser ở bước 5.

### 4.2. Chính sách dùng model: luật trước, model sau

| Bước | Cách làm chính | Model |
| --- | --- | --- |
| Làm sạch ký tự, khử trùng lặp | Thuật toán xác định (NFC, hash, MinHash) | Không dùng |
| Parse lương, kinh nghiệm, ngày | Regex + bộ test | Không dùng |
| Lọc IT | Luật từ khoá title | Chỉ khi đo ra kém |
| Trích xuất kỹ năng | Từ điển + Aho–Corasick | Chỉ khi F1 dưới 0.8 |
| Phân loại bullet (kỹ năng, kinh nghiệm, học vấn, ngoại ngữ, kỹ năng mềm) | Zero-shot: embedding `multilingual-e5-base` so với câu mẫu, không cần dữ liệu train | Model có sẵn |
| Gán nhãn phúc lợi (làm nhẹ) | Zero-shot bằng embedding + vài luật rõ ràng ("lương tháng 13") | Model có sẵn |
| Dịch JD tiếng Anh → tiếng Việt | Không có luật thay thế | `VietAI/envit5-translation`, chạy local; dịch toàn bộ JD tiếng Anh (bước 4b) |

Mọi trường do model sinh ra có thêm 2 cột: `<trường>_source` (`rule` / `model` / `llm`) và `<trường>_conf` (độ tin cậy).

### 4.3. Đo và báo cáo

- **Bảng phễu dữ liệu**: sau mỗi bước gọi `log_step()`, ghi số bản ghi còn lại, số bị loại và lý do. Bảng này đưa thẳng vào báo cáo.
- **Bảng chất lượng trước và sau**: 6 chiều chất lượng × các trường chính, số "trước" lấy từ bước 0.
- **Kết quả đánh giá trên bộ gold**: mỗi bước một con số, kèm các lỗi còn lại.

```python
funnel = []
def log_step(df, step, reason=""):
    prev = funnel[-1]["rows"] if funnel else len(df)
    funnel.append({"step": step, "rows": len(df),       # số bản ghi còn lại sau bước này
                   "removed": prev - len(df), "reason": reason})
    return df
```

### 4.4. Tái lập và chạy lại

- Bronze không bao giờ bị sửa.
- Mọi quy tắc (từ điển viết tắt, taxonomy kỹ năng, alias địa điểm, ngưỡng) nằm trong file từ điển ở `preprocessing/dictionaries/` (hiện là JSON; file này gọi tắt là YAML ở bản cũ), commit lên git.
- Pipeline idempotent: chạy lại bao nhiêu lần cũng ra cùng kết quả; chạy lại được riêng một tuần.
- Mỗi lần xử lý ghi `meta.json` lưu version của các file quy tắc.

### 4.5. Cấu trúc repo (theo repo hiện tại)

```
collection/<nguồn>/              # crawler của từng nguồn
preprocessing/
  clean/ deduplication/ integration/ missing_outlier/
  transformation/ normalization/ encoding/ common/
  dictionaries/                  # provinces_34.json, skills.json, it_policy.json ...
scripts/run_staging_integration_pipeline.py   # driver hiện tại
data/preprocessing/review/       # nhãn tay hiện có (chờ chốt chỗ đặt bộ gold 100 JD)
tests/
```

### 4.6. Công cụ

| Công cụ | Dùng ở bước | Trong `requirements*.txt` |
| --- | --- | --- |
| pydantic | 1 | Có |
| scikit-learn, mlxtend, hdbscan | 11, 12, mining | Có |
| ydata-profiling | 0 | Chưa |
| fastText (`lid.176`) | 3 | Chưa |
| datasketch (MinHash + LSH) | 4 | Chưa |
| rapidfuzz | 5 | Chưa |
| pyahocorasick | 8 | Chưa |
| underthesea | 9 | Chưa |
| sentence-transformers (`multilingual-e5-base`) | 4.2, 12 | Chưa |
| transformers + `VietAI/envit5-translation` | 4b | Chưa kiểm (`transformers`, `torch`) |

Cột cuối kiểm bằng `grep` trên `requirements*.txt` và `pyproject.toml` ngày 10/11/2026. Hiện dự án chưa cài gì thêm; khử trùng hiện tại là TF-IDF/Jaccard, chưa dùng MinHash.

## 5. Đã chốt (10/11/2026) và còn mở

**Đã chốt**
1. Không đặt số mẫu mục tiêu; chỉ báo cáo số tin đưa vào và số còn lại sau mỗi bước.
2. Feature selection, construction, encoding nằm trong Processing (bước 10b, 10c, 10d).
3. Cấp bậc: 5 cấp. Địa điểm: 34 tỉnh thành.
4. Bước dịch (4b): dịch sau khử trùng, giữ cả cột JD gốc và cột JD tiếng Việt.
5. Ánh xạ 6 chiều chất lượng sang 5 tiêu chí, ánh xạ 13 bước sang 4 giai đoạn: đồng ý.
6. Bỏ đoạn "Phần mở rộng" (LLM gán nhãn) ở mục 4.2. Bỏ JEV, OpenJev, Qwen.
7. Bộ gold 100 JD: một người gán, qua file `.html`; nơi lưu nhãn không cần cố định.
8. R2 chỉ còn `url_ledger/`, `raw/`, `staging/`, `curated/`, `pipeline/`. Đã sửa code `collection/common/r2_storage.py` (prefix `silver/`, `gold/` cũ vẫn đọc được và đổi sang `staging/`, `curated/`). Chưa chạy gì trên R2: đổi tên các object `silver/`, `gold/` đang có và dọn các prefix `quality/`, `integration/`, `transformation/` phải chạy thử trước và chờ bạn đồng ý.

**Còn mở**
- Nội dung chi tiết của bước 10b (tiêu chí chọn đặc trưng ngoài ngưỡng 5 lần) và 10c (danh sách đặc trưng mới).
- Tên thư mục con trong `pipeline/` theo bước.
- `crawl_week` có trong envelope Bronze không (chưa đối chiếu).
- Giới hạn độ dài đầu vào của `envit5-translation` (chưa kiểm).
