# PH6. Chuẩn hóa trường và gom chức danh (bước 5 của file thiết kế)

> **Nháp đặc tả, chờ bạn sửa** (10/11/2026). Chưa có code. Prompt: `docs/prompting/PH6_chuan_hoa_truong.md` (chưa duyệt).
> **[ĐỀ XUẤT]** = mình đoán. **[CẦN CHỐT]** = mình không biết, cần bạn quyết (mã `K1`...).
> Số liệu đo ngày 10/11/2026, chỉ đọc, trong bộ nhớ: chạy `integration.run.process_source` rồi `transformation.run.process_source` (dry-run, không ghi file) trên `data/preprocessing/01_clean/*.jsonl` (5.077 tin vào, 5.076 ra khỏi bước 02 vì 1 tin bị `rejected`: topcv 1.561, itviec 905, vietnamworks 800, jobsgo 683, careerviet 447, glints 271, topdev 227, vieclam24h 182), sau đó gọi các hàm của bước 04 hiện tại (`classify_seniority`, `classify_job_family_rule`, `_normalize_locations`, `normalize_company_name`). `data/preprocessing/02_integration/` và `03_transformation/` đang trống nên chưa đo được trên file thật. Mọi con số "đo" dưới đây có thể tái lập bằng cách chạy lại hai bước đó trong bộ nhớ.

## 1. Mục tiêu

Bước 5 của file thiết kế: đưa mọi trường về một dạng chuẩn dùng chung cho 8 sàn.

| Trường | Chuẩn đích (đã chốt) |
|---|---|
| Lương | VND/tháng, **1 USD = 25.400 đ**, mặc định gross; `.` `,` là phân cách hàng nghìn; "Từ X" chỉ có sàn, "Up to X" chỉ có trần, không gán min = max |
| Kinh nghiệm | số năm tối thiểu |
| Cấp bậc | **5 cấp**: Intern/Fresher, Junior, Middle, Senior, Lead/Manager |
| Địa điểm | **34 tỉnh/thành** sau sáp nhập (`provinces_34.json`); Remote/Hybrid là cột hình thức làm việc riêng |
| Nhóm nghề | **12 nhóm + Other** (luật từ khóa tiêu đề và kỹ năng) |
| Công ty | `company_key` + `rapidfuzz` >= 90 |
| Ngày | tuyệt đối theo `crawled_at` |
| **Chức danh (yêu cầu mới 10/11)** | `job_title_clean` -> chức danh chuẩn `title_canonical` -> nhóm nghề; luật if-else + `rapidfuzz`, không dùng model |

Mỗi parser phải đúng >= 95% trên 50 chuỗi thật. Tiêu chí chất lượng chính: Consistency, Accuracy. Không đặt số mẫu mục tiêu.

**Ranh giới với PH7:** PH6 chỉ *đọc ra* giá trị từ chính trường của tin (raw hoặc tiêu đề). Mọi việc *suy ra / điền / gắn cờ ngoại lai* (cấp bậc từ số năm, kinh nghiệm từ cấp bậc, khoảng lương hợp lệ, IQR) thuộc PH7. Hệ quả: tầng 3 của `classify_seniority` hiện nay (suy cấp bậc từ `exp_min_years`) **chuyển sang PH7** (xem mục 3.3).

## 2. Hiện trạng đo trên dữ liệu thật

### 2.1. Bảng hiện trạng so với thiết kế

| Trường | Thiết kế yêu cầu | Code hiện tại | Đo trên 5.076 tin | Lệch / việc cần làm |
|---|---|---|---|---|
| Lương: số, USD, `.` `,` | đọc đúng dấu hàng nghìn, USD x 25.400 | `salary_parser.py` (T2a-T2f, đã làm 03/11); hằng 25.400 còn lặp ở `outlier_handler.py` (`25_400.0`) | 2.319 tin có số (45,7%); `salary_currency_raw`: VND 4.727, USD 349; `salary_period_raw`: month 5.072, year 4 | Hằng số nằm 2 nơi. Mục 3.1 |
| Lương: "Từ X"/"Up to" | một đầu | T2b, T2c | chỉ min: 68 tin; chỉ max: 276 tin; `min > max`: 1 tin | Đúng thiết kế; 1 tin min > max cần kiểm (PH7 M6) |
| Lương: sửa ở bước 04 | không nằm trong bước 5 | `fix_common_salary_input_errors` (N6) chia 12 khi JD có chữ "năm", nhân 25.400 khi 100 <= số <= 10.000 | Nhánh "x 25.400": 0 tin. Nhánh "chia 12": **6 giá trị, cả 6 ở vietnamworks, đều sai** (xem 2.2) | **Lỗi.** Chữ "năm" có trong gần như mọi JD ("2 năm kinh nghiệm") nên không phân biệt được lương năm. Sửa ở PH7 (M5) |
| Lương gross/net | mặc định gross | không có cột | "net" trong `raw_salary_text`: 1 tin ("Up to 1700 usd net"), "gross": 1 tin | Quá ít để thêm cột. K3 |
| Kinh nghiệm | số năm tối thiểu | `experience_parser.parse_experience_range` | `raw_experience_text` có chữ nhưng **`exp_min_years` null: 1.237 tin** (xem 2.3) | Thêm 5 dạng chuỗi. Mục 3.2 |
| Cấp bậc | 5 cấp | `normalization/text_cleaner.classify_seniority`: **6 nhãn** (Thực tập, Mới tốt nghiệp, Junior, Middle, Senior, Trưởng nhóm/Quản lý); `experience_parser` có bộ 5 nhãn riêng (`SENIORITY_LEVELS`) nhưng P4 không dùng | null: 899 tin; nguồn nhãn: kinh_nghiem 2.256, title 1.130, raw 791 | Lệch số cấp (6 so với 5), 2 bộ mã trùng lặp. Mục 3.3 |
| Địa điểm 34 tỉnh | 34 tỉnh; Remote/Hybrid cột riêng | `normalization/run.py` `_normalize_locations` (N1), `common/province.py` | `tinh_chinh` null **843 tin** (16,6%): itviec 719, glints 76, vietnamworks 19, topcv 13, jobsgo 9, careerviet 6, topdev 1; `remote` 7 tin, `ngoai_vn` 25; **không có cột hình thức làm việc, không có Hybrid** | Mục 3.4 |
| Nhóm nghề | 12 nhóm + Other | **3 danh sách 12 nhóm khác nhau** (mục 2.4) | P4: "Khác" 560 tin (11,0%), jobsgo 18,7%, vieclam24h 23,1% | Mục 3.5, 3.6 |
| Chức danh | (yêu cầu mới) | `job_title_clean` chỉ làm sạch ký tự (PH2). `text_cleaner.clean_job_title` (bỏ `[HN]`, lương cuối tiêu đề) **không được gọi ở đâu trong luồng chạy** | Mục 2.5 | Mục 3.5 |
| Công ty | `company_key` + rapidfuzz >= 90 | `company_norm` = `normalize_company_name` (bỏ "công ty", "tnhh", "cp"...), chưa có rapidfuzz | 2.466 tên gốc -> 2.218 `company_norm` -> **2.193** nhóm khi gộp bằng `token_sort_ratio >= 90` (chỉ gộp thêm 24 tên); 3 tên rỗng sau chuẩn hóa | Gộp ngưỡng 90 có **gộp nhầm** (2.6). Mục 3.7 |
| Ngày | tuyệt đối theo `crawled_at` | `date_parser.py` (T3) | `raw_posted_date` non-null 3.317 tin, **0 tin dạng tương đối** ("trước", "ago", "hôm qua"); `posted_date` có: topcv 0% (không có raw), topdev 31,3%, còn lại 96,6-100% | Luật tương đối chưa có chuỗi thật nào để thử. Mục 3.8 |
| `rapidfuzz` | dùng cho công ty và chức danh | **đã cài** (`rapidfuzz 3.14.6` trong `.venv`); chưa có dòng nào trong `preprocessing/` import nó | | Không cần cài thêm; cần ghi version vào `requirements.txt` nếu chưa có |

### 2.2. Lương: ví dụ thật của lỗi chia 12 (N6)

| Nguồn | `raw_salary_text` | Giá trị đúng sau T2 | Sau `fix_common_salary_input_errors` |
|---|---|---|---|
| vietnamworks (2 tin trùng nội dung) | `8000 - 9000 USD` | 203,2 - 228,6 triệu/tháng | 16,9 - 19,1 triệu (chia 12) |
| vietnamworks | `0 - 450000000 VND` | max 450 triệu | 37,5 triệu |
| vietnamworks | `400000000 - 450000000 VND` | 400-450 triệu | (kiểm tay: chưa rõ là tháng hay năm) |

Ghi chú: "8000-9000 USD" cho vị trí cấp cao là mức hợp lý theo tháng (VietnamWorks), không phải lương năm. Còn `topcv 300 - 500 triệu` và các dòng `200000000 - 500000000 VND` có thể là lương năm hoặc nhập sai; **mình không biết**, cần bạn xem trang gốc (K2).

### 2.3. Kinh nghiệm: 1.237 tin có chữ nhưng không parse được

| Chuỗi thật (`raw_experience_text`) | Số tin | Nguồn | Kết quả hiện tại |
|---|---|---|---|
| `3.1 năm (37 tháng)` | 425 | itviec | null |
| `0.8 năm (10 tháng)` | 317 | itviec | null |
| `5.1 năm (61 tháng)` | 45 | itviec | null |
| `Không yêu cầu` | 393 (jobsgo 250, topcv 143) | | null. `experience_parser._NO_EXPERIENCE` cần cả cụm "không yêu cầu kinh nghiệm"; spec P3 T4 ghi "Không yêu cầu -> 0-0" |
| `Dưới một năm kinh nghiệm` | 45 | glints | null (viết "một" bằng chữ) |
| `Lên đến N Năm` | 9 (N = 1, 2, 5, 7) | careerviet | null (chỉ nhận "up to", "tối đa", "không quá", "dưới") |
| `Hơn 5 năm` | 2 | careerviet | null (chỉ nhận "trên", "tối thiểu", "ít nhất", "từ") |

itviec: `exp_min_years` điền 0% dù `raw_experience_text` có ở 87,0% tin. Chỉ có 3 giá trị khác nhau trên cả 787 tin (3,1 / 0,8 / 5,1 năm), nên nhiều khả năng là nhóm đã quy đổi, không phải số của tin. **Mình không biết nghĩa gốc** (K4).

Giá trị `exp_min_years` đang có (3.012 tin) toàn số nguyên: 0: 212, 1: 834, 2: 794, 3: 864, 4: 157, 5: 397, 6 trở lên: 85.

### 2.4. Ba danh sách "12 nhóm nghề" đang tồn tại

| Nguồn danh sách | 12 nhóm |
|---|---|
| **SPEC-01 mục 4.4** (`docs/spec/01_product_spec.md`; file thiết kế trỏ tới đây) | Backend, Frontend, Fullstack, Mobile, DevOps/Cloud, **Data Engineer, Data Science/AI**, QA/QC, Security, **Product/Project**, **System/Network**, **Embedded/IoT** |
| P4 (`normalization/text_cleaner.JOB_FAMILIES`, đang chạy) | Backend, Frontend, Fullstack, Mobile, **Data/AI**, DevOps/Cloud, Kiểm thử (QA/QC), Bảo mật, Hệ thống/Mạng, **Phân tích nghiệp vụ (BA)**, Quản lý sản phẩm/dự án, **Thiết kế UI/UX** |
| `transformation/job_family_classifier.JOB_FAMILIES` (tên "Duy's handbook") | Backend, Frontend, Fullstack, Mobile, DevOps/Cloud, Data/AI, QA/QC, Security, **BA**, Product, System, **Embedded** |

Khác biệt cốt lõi: SPEC-01 **không có BA và UI/UX** nhưng **có Embedded/IoT và tách Data Engineer khỏi Data Science/AI**; P4 **không có Embedded**; `job_family_classifier.py` không có UI/UX. Hai module phân loại cho kết quả khác nhau trên cùng dữ liệu:

| Nhóm | P4 `classify_job_family_rule` (đang chạy) | `job_family_classifier.classify_job_family` (title + skills + category) |
|---|---|---|
| Backend | 856 | 277 |
| Data/AI | 672 | 439 |
| DevOps/Cloud | 671 | 299 |
| QA/QC | 543 | 483 |
| BA | 355 | 359 |
| Product (quản lý sản phẩm/dự án) | 294 | 225 |
| UI/UX | 263 | (không có) |
| Hệ thống/Mạng | 210 | 240 |
| Mobile | 199 | 141 |
| Fullstack | 197 | 189 |
| Bảo mật | 179 | 184 |
| Frontend | 77 | 45 |
| Embedded | (không có) | 56 |
| Không xếp được ("Khác"/None) | 560 | 2.139 |

Khác biệt số lớn nhất ở Backend (856 và 277) và ở số không xếp được (560 và 2.139: `job_family_classifier` chỉ dùng kỹ năng khi có `category` IT).

**Hiện trạng chất lượng của P4 (đọc tay mẫu, seed 7):**
- Backend 856 = 585 theo tiêu đề + 271 theo kỹ năng. Trong 585 theo tiêu đề, **398 không có chữ "back" trong tiêu đề**: khớp nhờ từ chung `developer`, `software engineer`, `lập trình viên`, `java`, `python`, `node`. Hệ quả thật: `Middle/Senior Embedded Software Engineer (C++,C)` -> Backend; `.Net Core Developer` -> Backend (đúng); `IT PROGRAMER`, `Oracle Consultant Intern`, `CRM Data Analytics Manager`, `Finance & Data Specialist` -> Backend theo kỹ năng (sai).
- UI/UX 263, **100% theo tiêu đề, phần lớn là thiết kế đồ họa ngoài IT**: `Nhân Viên Thiết Kế`, `Chuyên Viên Thiết Kế Bao Bì & Thương Hiệu`, `Chuyên Viên Thiết Kế Hệ Thống Lạnh`, `Senior Creative Designer`, vì từ khóa `thiết kế`, `designer`. Phần này lẽ ra bị bước lọc IT loại.
- Frontend chỉ 77 tin vì `ReactJS Developer` bị Backend hút ("developer"); Embedded Engineer thì không có nhóm.

### 2.5. `job_title_clean` trên dữ liệu thật

| Chỉ số | Giá trị |
|---|---|
| Số tin | 5.076 |
| Chức danh khác nhau (`job_title_clean`) | **4.223**; sau `casefold` 4.106 (=`job_title_fold` 4.106) |
| Chức danh chỉ xuất hiện 1 lần (sau casefold) | 3.631 (88,4% số chức danh khác nhau) |
| Top 50 chức danh phủ | 9,1% tin; top 200 phủ 17,6% tin |
| Có ngoặc `[...]` hoặc `(...)` | 2.251 (44,3%) |
| Có dấu phân cách ` - `, ` – `, ` | `, ` / ` | 1.214 |
| Có dãy 4 chữ số trở lên (mã tin, `2026TD450981`...) | 184 |
| Có tên địa điểm (HN/HCM/Hà Nội/...) | 172 |
| Có lương (`15-20tr`, `Upto 2000$`) | 153 |
| Viết hoa toàn bộ | 115 |
| Dài hơn 80 ký tự | 221 (tối đa 46 từ, p99 = 21 từ) |
| Rỗng | 0 |
| Số từ | trung vị 6, p90 12 |
| Khác nhau theo nguồn | topcv 1.368, itviec 835, vietnamworks 751, jobsgo 589, careerviet 411, glints 250, topdev 221, vieclam24h 174 |

Top chức danh (casefold, nguyên văn): `nhân viên it` 31, `devops engineer` 29, `nhân viên thiết kế` 23, `business analyst` 20, `data engineer` 20, `product owner` 20, `ai engineer` 17, `chuyên viên phân tích dữ liệu` 14, `data analyst` 14, `chuyên viên thiết kế` 13, `project manager` 12, `network engineer` 12, `it helpdesk` 11.

Thử một hàm bỏ nhiễu (bỏ `[...]`, `(...)`, phần sau ` - `/` | `, từ cấp bậc `senior/junior/lead/intern/fresher`, tiền tố `nhân viên/chuyên viên/kỹ sư/tuyển gấp`; **đây là hàm thử trong bộ nhớ, chưa có trong repo**):

| | Trước | Sau bỏ nhiễu |
|---|---|---|
| Chức danh khác nhau | 4.106 | **2.470** (21 tin rỗng sau khi bỏ nhiễu: chỉ còn từ cấp bậc/tiền tố) |
| Top 100 chức danh phủ | 17,6% (top 200) | **37,9%** (top 100) |
| Gộp thêm bằng `rapidfuzz.token_sort_ratio >= 90` | | chỉ xuống **2.215** |

Kết luận đo: (1) bỏ nhiễu giảm gần 40% số chức danh nhưng vẫn còn hàng nghìn; (2) **`rapidfuzz` chỉ gộp thêm khoảng 10%**, vì phần lớn chức danh khác nhau về *từ* (`Phân tích nghiệp vụ` / `Business Analyst` / `BA`), không phải về chính tả. Vì vậy phần chính phải là **từ điển chức danh chuẩn** (luật), `rapidfuzz` chỉ là lớp đỡ cho lỗi gõ và biến thể gần, không phải cơ chế chính.

Các từ xuất hiện nhiều nhất trong chức danh đã bỏ nhiễu (số tin chứa từ đó): `engineer` 929, `it` 510, `developer` 505, `analyst` 320, `business` 276, `ai` 275, `data` 264, `manager` 189, `qa` 174, `backend` 169, `software` 167, `tester` 153, `fullstack` 143, `product` 141, `designer` 111, `devops` 111, `qc` 97, `java` 96, `system` 94, `project` 88, `security` 81, `support` 80, `network` 67.

**Dữ liệu cho thấy một lớp chức danh chung chung không xác định được nhóm nghề từ tiêu đề:** `nhân viên it` (31+21), `it` (93 sau bỏ nhiễu), `chuyên viên it`, `it manager`, `thực tập sinh fulltime cntt`, `it engineer`, `it generalist`. Lớp này phải ra "Other" trừ khi kỹ năng JD quyết định (xem 3.6).

### 2.6. Gộp công ty bằng rapidfuzz >= 90: 23 nhóm, đọc tay

Trên 2.218 `company_norm`, gộp tham lam bằng `token_sort_ratio >= 90` ra 23 nhóm. Đọc tay:

| Loại | Ví dụ thật | Số nhóm (mình đọc) |
|---|---|---|
| Đúng (cùng công ty) | `car doctor` / `cardoctor`; `công nghệ quảng ích` / `công nghệ quảng ích qig`; `headhunter hrchannels` / `headhunter hrchannels com`; `infinity technologies global` / `infinity technology global`; `ngân hàng lộc phát lpbank` / `ngân hàng tmcp lộc phát lpbank`; `truyền thông văn hoá việt` / `truyền thông văn hóa việt` (khác dấu thanh `hoá`/`hóa`) | khoảng 17 |
| **Nhầm** (khác công ty) | `công nghệ dtg` / `công nghệ g` / `công nghệ itg`; `htc viễn thông quốc tế` / `viễn thông quốc tế fpt`; `công nghệ một giải pháp` / `giải pháp công nghệ ite`; `sotatek` / `statek`; `công nghệ sota` / `công nghệ sotatek`; `orenda` / `renda` | khoảng 6 |

**[CẦN CHỐT] K7** (mục 6) cần bạn xác nhận cách đọc này. Hệ quả: dùng thẳng ngưỡng 90 sẽ gộp nhầm khoảng một phần tư số nhóm; gộp nhầm công ty làm sai việc chia train/test theo công ty (PH sau).

## 3. Luật PH6

Mã luật mới nối tiếp N1-N9 của P4: `N10`-`N19`. Mỗi luật là một dòng trong `StepReport` của bước 04, kèm số tin bị tác động và 3 ví dụ.

### 3.1. Lương (N10)

| Mã | Luật | Ghi chú |
|---|---|---|
| N10a | Một hằng `USD_VND = 25_400` trong một module (đề xuất `preprocessing/common/constants.py` hoặc ngay trong `salary_parser.py`); `outlier_handler.py` import, không tự ghi 25_400.0 | Quyết định đã chốt (file thiết kế, 10/11). Test: mọi chỗ trong `preprocessing/` dùng hằng này |
| N10b | **Bỏ nhánh "chia 12 khi JD có chữ năm" và nhánh "x 25.400 khi 100..10.000" khỏi `fix_common_salary_input_errors`** khỏi luồng chuẩn hóa. T2 (bước 03) đã đọc `year`/`USD` bằng cột `salary_period_raw`, `salary_currency_raw` | Chia 12 sai cả 6 giá trị đo được (2.2). Nhánh x 25.400 có 0 ca. PH7 M5 quyết định có giữ một dạng đã sửa hay không |
| N10c | Không sửa gì khác ở `salary_parser.py` (T2a-T2f đã đúng theo spec P3; 5 dạng D2-D7) | Kiểm lại bằng 50 chuỗi thật (mục 4) |

### 3.2. Kinh nghiệm (N11)

Mở rộng `experience_parser.parse_experience_range`, không đổi chữ ký, thêm các `status` mới (không đoán số khi chuỗi không rõ):

| Mã | Chuỗi | Kết quả [ĐỀ XUẤT] | status |
|---|---|---|---|
| N11a | `Không yêu cầu` (đứng một mình, sau khi bỏ dấu) | `exp_min=0, exp_max=null` | `explicit_zero` |
| N11b | `Dưới một năm`, `Dưới 1 năm` ("một" = 1) | `0, 1` | `upper_bound` |
| N11c | `Lên đến N năm` | `0, N` | `upper_bound` |
| N11d | `Hơn N năm`, `Trên N năm` | `N, null` | `lower_bound` |
| N11e | `X năm (Y tháng)` (dạng itviec) | **phụ thuộc K4** | `compound_years_months` |

Lưu ý hiện tại `parse_experience` (wrapper) đặt `exp_max = exp_min` cho `explicit_zero`, nên "Không yêu cầu" ra `(0, 0)` đúng T4 trong spec P3; N11a giữ hành vi đó.

### 3.3. Cấp bậc 5 cấp (N12)

Nhãn chuẩn (giá trị cột `seniority`, tiếng Anh theo spec P4 mục 3, đã chốt 5 cấp): `Intern/Fresher`, `Junior`, `Middle`, `Senior`, `Lead/Manager`. `seniority_level` 0-4; không xác định: null (không dùng -1 `"Chưa rõ"`, để cột nhất quán với `seniority`). **[CẦN CHỐT] K5**: P4 spec ghi -1; code hiện tại ghi null.

Thứ tự tra (PH6 chỉ hai tầng đầu):

1. `raw_seniority_text` -> `seniority_source="raw"`.
2. `job_title_clean` (chỉ phần lõi, sau khi bỏ nhiễu ở N15) -> `seniority_source="title"`.
3. ~~Số năm kinh nghiệm~~ -> **chuyển sang PH7 (M3)**, vì là suy luận và phải gắn `level_inferred`.

Đổi so với code: `classify_seniority` trả `Thực tập` và `Mới tốt nghiệp` thành hai nhãn; PH6 gộp thành `Intern/Fresher`. `"Trưởng nhóm/Quản lý"` đổi tên `Lead/Manager` (cùng tập từ khóa). Giữ luật "Nhân viên"/"Chuyên viên" không nói cấp bậc.

Đo hiện trạng `raw_seniority_text`: `Nhân viên` 2.313 tin, `Nhân Viên/Chuyên Viên` 536, `Trưởng nhóm` 241, `Trưởng phòng` 114, `Thực tập sinh` 94+76, `Trưởng Nhóm/Trưởng Phòng` 51, `Quản lý / Giám sát` 49, `Trưởng/Phó phòng` 49, `Trưởng nhóm / Giám sát` 30, `Quản lý` 29, `Mới Tốt Nghiệp` 20+1, `Giám đốc` 14, `Sinh viên/ Thực tập sinh` 11, `Giám Đốc và Cấp Cao Hơn` 11, `Cộng tác viên` 9, `Chuyên gia` 7. **Không có giá trị nào của raw tự nói `Junior`, `Middle` hay `Senior`** (các nhãn này chỉ ra từ tiêu đề hoặc số năm). Glints và itviec: 0% có `raw_seniority_text`; topdev 0,4%.

Nhãn hiện tại (6 nhãn, trước khi gộp): Junior 1.429, Trưởng nhóm/Quản lý 822, Senior 729, Middle 683, Thực tập 288, Mới tốt nghiệp 226, null 899. Nguồn nhãn: **kinh_nghiem 2.256 (44,4%)**, title 1.130, raw 791, null 899. Tức gần một nửa nhãn hiện nay do luật số năm tạo ra: khi chuyển sang PH7, báo cáo PH6 sẽ nhận chỉ 1.921 nhãn thật (raw + title) và 3.155 null trước khi PH7 suy luận.

Luật theo tiêu đề, chỉ để làm rõ chỗ mơ hồ (các từ khớp theo từ nguyên vẹn qua `has_term`): `quản lý` đứng một mình trong tiêu đề thường là tên việc ("Quản lý dự án", "Quản lý vận hành"), không phải cấp bậc, hiện đã bỏ khỏi luật tiêu đề, giữ nguyên. `Lead` trong `Tech Lead/Team Lead/Lead Developer` là Lead; `Product Owner`, `Project Manager` có `manager` trong tiêu đề nhưng là tên nhóm nghề, **không phải cấp bậc Lead/Manager nếu không có từ chỉ cấp**. **[CẦN CHỐT] K6.**

### 3.4. Địa điểm và hình thức làm việc (N13, N14)

| Mã | Luật | Ghi chú |
|---|---|---|
| N13 | Khi mọi phần tử `locations` không ra tỉnh, thử `prov_key(raw_location_text)` toàn chuỗi (rồi `company_address`); ra thì dùng, ghi `tinh_source="raw_location_full"` | Đo: trong 843 tin `tinh_chinh` null, **712 tin** (84,5%) có `prov_key(raw_location_text)` ra tỉnh. 14 tin nữa ra từ `company_address`. Ví dụ thật chưa ra: `Tòa nhà MB, số 18 Lê Văn Lương, Phường Yên Hòa, Hà Nội`, `32 Pham Ngoc Thach, Xuân Hòa, TP Hồ Chí Minh`, `Ha Noi`, `Tân Phú`, `Quận Cầu Giấy` (quận/huyện đơn lẻ: không suy ra tỉnh, vì dictionary phường chỉ có phường mới; ghi nhận, không đoán) |
| N14 | Cột `work_mode` in {`onsite`, `remote`, `hybrid`, `unknown`} (cùng bộ giá trị với gold `WORK_MODES`) theo thứ tự: địa điểm `Remote`/"từ xa" -> `remote`; từ `hybrid` trong tiêu đề hoặc `raw_location_text` -> `hybrid`; còn lại: `onsite` nếu có tỉnh, ngược lại `unknown` | Đo: `remote` hoặc "từ xa" trong tiêu đề/địa điểm 35 tin, `hybrid` 18 tin; trong JD: remote 63 tin, hybrid 109 tin. **Không** dùng JD để đặt `remote` (JD hay viết "hybrid" như một phúc lợi hoặc phạm vi ứng viên); K8 |

`ngoai_vn` hiện 25 tin, `remote` 7 tin theo `_normalize_locations`. Giữ `locations` dạng cũ, thêm cột `work_mode` ở mức tin.

### 3.5. Chức danh -> chức danh chuẩn -> nhóm nghề (N15, N16, N17): phần mới

Ba cột mới nối tiếp nhau, mỗi cột có `*_source` cho biết luật nào quyết:

| Cột | Từ | Ý nghĩa |
|---|---|---|
| `job_title_core` | `job_title_clean` | tiêu đề đã bỏ nhiễu, **chưa** gộp (vẫn là chữ của tin, viết thường không bắt buộc) |
| `title_canonical` | `job_title_core` (+ `job_title_fold`) | chức danh chuẩn trong từ điển `preprocessing/dictionaries/job_titles.json`, hoặc null |
| `job_family` (đã có, đổi nguồn) | `title_canonical`, rồi từ khóa tiêu đề, rồi kỹ năng | 1 trong 12 nhóm hoặc `Other` |
| `title_canonical_source`, `title_match_score` | | `exact`, `alias`, `fuzzy`, `none`; điểm rapidfuzz (null nếu không dùng) |
| `job_family_source` (đã có) | | `canonical`, `title`, `skills`, `none` |

**N15. Bỏ nhiễu (`job_title_core`)**, mỗi bước là một luật con, theo thứ tự, viết bằng regex, **không đổi `job_title_clean`**:

| Mã | Việc | Ví dụ thật trước -> sau |
|---|---|---|
| N15a | Bỏ khối `[...]` đầu hoặc cuối tiêu đề | `[All level] BackEnd Engineer (Java, Spring Boot) - Khối Công nghệ thông tin (2025TD1785)` -> `BackEnd Engineer (Java, Spring Boot)` |
| N15b | Bỏ mã tin: dãy >= 4 chữ số kèm chữ (`2026TD450981`, `DNA699`) | `Data Quality Management Specialist ... (2026TD450981)` -> không còn mã |
| N15c | Bỏ cụm lương và địa điểm cuối tiêu đề (`- (15-20tr) Tại Hà Nội`, `- Thu Nhập 15-35 Triệu`, `Upto 2000$`) | `Nhân Viên IT- Thu Nhập 15-35 Triệu- Tại Hải Phòng` -> `Nhân Viên IT` |
| N15d | Bỏ cụm quảng cáo đầu tiêu đề (`Tuyển Gấp`, `Hot`) | `Tuyển Gấp- Junior QA Automation Engineer (M/f/d)` -> `Junior QA Automation Engineer` |
| N15e | Tách **cấp bậc** khỏi tiêu đề (để N12 dùng; **không xóa khỏi `job_title_clean`**): `Senior/Junior/Middle/Lead/Intern/Fresher/Thực tập sinh/Trưởng nhóm` | `Senior DevOps Engineer` -> `core = DevOps Engineer`, cấp = Senior |
| N15f | Giữ nội dung trong ngoặc nếu nó là **kỹ năng/công nghệ** (`(Java, Spring Boot)`, `(C/C++, Firmware, RTOS)`) vào cột riêng `title_tech_hint` (list) để N17 dùng, thay vì bỏ mất | `Embedded Engineer (C/C++, Firmware, Git, RTOS)` -> core `Embedded Engineer`, hint `[C/C++, Firmware, Git, RTOS]` |

N15 chỉ sửa chữ; không bao giờ xóa dòng và không bao giờ đổi `job_title`, `job_title_clean` (raw/clean bất biến).

**N16. Chức danh chuẩn (`title_canonical`)**, ba lớp theo thứ tự, lớp sau chỉ chạy khi lớp trước không ra:

1. **`exact`**: `job_title_fold` đã bỏ nhiễu và cấp bậc khớp *nguyên văn* một `alias` trong `job_titles.json`.
2. **`alias`**: khớp theo từ nguyên vẹn (`has_term` đã có) một cụm từ khóa của một chức danh chuẩn (ví dụ cụm `phan tich nghiep vu` -> `Business Analyst`).
3. **`fuzzy`** (rapidfuzz): `rapidfuzz.process.extractOne(core_fold, tất cả alias_fold, scorer=fuzz.token_set_ratio, score_cutoff=T)`; chỉ nhận nếu điểm >= **T** và độ dài chuỗi >= 8 ký tự (tránh `ba`, `qa`, `it` khớp lung tung); điểm lưu vào `title_match_score`. **[ĐỀ XUẤT] T = 90**, giống ngưỡng công ty trong file thiết kế, nhưng **ngưỡng phải đo lại trên dữ liệu thật trước khi chốt** (K10), vì ở công ty ngưỡng 90 gộp nhầm khoảng một phần tư nhóm (2.6). Không dùng `fuzzy` để tạo chức danh chuẩn mới; chỉ để gán vào chức danh đã có trong từ điển.

Ngoài ra `title_canonical = null` khi không lớp nào ra, **không đặt "Other" ở cột này**: null nghĩa là "từ điển chưa biết chức danh này". Phần lớn trong 2.470 chức danh còn lại là đuôi dài (88% chỉ xuất hiện một lần), dự kiến vẫn null.

**N17. Nhóm nghề (`job_family`)**, thứ tự ưu tiên, **luật if-else, không dùng model**:

1. Nếu `title_canonical` không null: dùng nhóm gắn sẵn cho chức danh chuẩn đó trong `job_titles.json` (`job_family_source="canonical"`).
2. Ngược lại: luật từ khóa tiêu đề, **thu hẹp** so với P4: bỏ các từ chung (`developer`, `software engineer`, `lập trình viên`, `java`, `python`, `node`) khỏi danh sách từ khóa Backend (đo: 398 trong 585 tin Backend-theo-tiêu đề chỉ khớp từ chung). Từ chung chỉ cho nhóm nghề khi có kỹ năng xác nhận (bước 3). Giữ nguyên **thứ tự ưu tiên đặc thù trước, chung sau** của `_FAMILY_RULES` trong `job_family_classifier.py` (Embedded, Security, QA, BA... trước Backend).
3. Ngược lại: kỹ năng (`skills_std`) chỉ khi **một nhóm duy nhất** có >= 2 kỹ năng đặc trưng (đã có cơ chế `_SKILL_GATES` trong `job_family_classifier.py`). Nếu hai nhóm hòa (Backend và Frontend cùng có) -> xem K11 (Fullstack hay Other).
4. Ngược lại: `Other` (`job_family_source="none"`).

`job_family_can_kiem` (đã có): giữ. Thêm cờ `job_family_generic_title` = True khi tiêu đề chung chung (`nhân viên it`, `it`, `chuyên viên it`...) để PH7 và Mining biết nhóm nghề đến từ kỹ năng, không từ tiêu đề.

**Từ điển `job_titles.json` [ĐỀ XUẤT]** (file mới, cùng khuôn `abbreviations.json`: mỗi mục `approved: false` cho tới khi bạn duyệt; **bản đầu chỉ chứa mục có trong dữ liệu**, không tự nghĩ thêm):

```json
{"version": "0.1-candidates", "note": "...", "families": ["Backend", "..."],
 "entries": [{"canonical": "Business Analyst", "family": "<theo K9>", "aliases": ["business analyst", "ba", "phân tích nghiệp vụ", "it business analyst"],
              "docs_with_title": 145, "approved": false}]}
```

Ứng viên chức danh chuẩn rút từ dữ liệu (số tin = số tin có chức danh lõi đó sau bỏ nhiễu, đo bằng hàm thử; **đây là ứng viên để bạn duyệt, chưa phải từ điển**): `Business Analyst` 145 (+ `it business analyst` 16, `phân tích nghiệp vụ` 33), `AI Engineer` 86, `DevOps Engineer` 68, `Product Owner` 63, `Backend Developer/Engineer` 60+42, `Data Engineer` 59, `Fullstack Developer/Engineer` 57+16, `Data Analyst` 47 (+ `phân tích dữ liệu` 24), `Software Engineer/Developer` 42+14, `Project Manager` 37, `IT Helpdesk` 34 (+ `it support` 24), `QA/QA Engineer` 31+20, `Network Engineer` 28, `Tester/Manual Tester` 27+27 (+ `kiểm thử phần mềm` 22), `Java Developer` 24, `Game Designer` 22, `Solution Architect` 21, `Unity Developer` 19, `System Engineer` 18, `Mobile Developer` 15, `IT Manager` 15, `Product Manager` 14, `Frontend Developer` 13. Cách làm đúng theo EDA: một script đếm chức danh lõi, in ra ứng viên có tần suất >= một ngưỡng bạn chọn (K9), bạn duyệt, rồi mới vào file.

**Taxonomy 12 nhóm + Other [ĐỀ XUẤT]** (K9 là điểm bạn phải quyết trước khi viết `job_titles.json`):

| Phương án | Nội dung | Ưu / nhược (theo số đo mục 2.4) |
|---|---|---|
| **A (mình đề xuất)** | **Dùng đúng 12 nhóm của SPEC-01** (Backend, Frontend, Fullstack, Mobile, DevOps/Cloud, Data Engineer, Data Science/AI, QA/QC, Security, Product/Project, System/Network, Embedded/IoT) + `Other`. BA (355 tin theo P4) xếp vào **Product/Project**; UI/UX và thiết kế đồ họa (263) xếp `Other`; Data Analyst xem K9b | Khớp văn bản SPEC-01 mà file thiết kế trỏ tới. Có Embedded/IoT (56 tin P4 đang xếp sai vào Backend). Đổi tên nhãn P4 hiện tại (Mining/Monitoring phải đọc nhãn mới) |
| B | Giữ danh sách P4 (có BA, UI/UX; không Embedded) | Không đổi code đang chạy; nhưng lệch SPEC-01, và Embedded vẫn bị Backend hút |
| C | Giữ 12 của P4 nhưng thay UI/UX bằng Embedded/IoT | Chỉ đúng nếu bạn bỏ UI/UX khỏi 12 |

Nhãn lưu trong parquet: **[ĐỀ XUẤT]** tiếng Anh như SPEC-01 (`Backend`, `Data Engineer`, `QA/QC`...), `Other` (không phải "Khác"), tên ngắn, không dấu, ổn định. Spec P4 mục 3 ghi nhãn tiếng Việt ("Khác", "Bảo mật", "Kiểm thử (QA/QC)"); thuật ngữ ngành P4 nói giữ tiếng Anh. K9c.

Với Data Analyst (47 + 24 tin): SPEC-01 chỉ có Data Engineer và Data Science/AI. **[CẦN CHỐT] K9b**: Data Analyst, Business Intelligence, "phân tích dữ liệu" thuộc nhóm nào (mình không tự gán).

### 3.6. Tiêu đề chung chung và "Other"

Dựa trên đo (560 tin "Khác" ở P4; top: `nhân viên it` 21, `it engineer` 4, `chuyên viên it` 3, `it manager` 3, `nhân viên tư vấn triển khai phần mềm website` 4, `nhân viên lập trình cnc` 4 (không phải IT), `3d game artist`, `data quality management specialist` 3+2, `erp pmo consultant` 2): mọi tin không xếp được vào 12 nhóm ra `Other`, **không bỏ dòng** (ranh giới PH6; bỏ tin ngoài IT là việc của bước Clean). `nhân viên lập trình cnc`, `Kỹ sư lập trình khuôn`, `Nhân Viên Nhập Liệu - Phần Mềm SAP` là tin ngoài IT lọt qua bước lọc: ghi nhận vào báo cáo `extra.other_samples` (5 ví dụ) để PH3 xem lại, PH6 không loại.

### 3.7. Công ty (N18)

| Mã | Luật | Ghi chú |
|---|---|---|
| N18a | `company_norm` giữ nguyên (đã có). Thêm bước chuẩn hóa dấu thanh tiếng Việt (`hoá`->`hóa`, `qủy`->`quỷ`) và gộp khoảng trắng trước khi so khớp | Ví dụ thật `truyền thông văn hoá việt` / `văn hóa việt` |
| N18b | `company_key`: gộp nhóm bằng `rapidfuzz` trên các `company_norm` khác nhau của **toàn bảng gộp**, **chỉ tự động gộp** khi `token_sort_ratio >= 90` **và** (`token_set_ratio == 100` tức một tên là tập con của tên kia, hoặc hai tên bằng nhau sau khi bỏ khoảng trắng) | **[ĐỀ XUẤT]**. Phép thử trên 23 nhóm: các cặp nhầm (`dtg/g/itg`, `htc viễn thông quốc tế / viễn thông quốc tế fpt`, `sotatek/statek`, `orenda/renda`) đều **không** thỏa "một tên là tập con của tên kia"; các cặp đúng (`quảng ích / quảng ích qig`, `lộc phát lpbank / tmcp lộc phát lpbank`, `hrchannels / hrchannels com`) thỏa. Chưa kiểm hết, đo lại trong code |
| N18c | Các cặp đạt `>= 90` nhưng không thỏa điều kiện tập con: **không gộp tự động**, ghi vào `data/preprocessing/review/company_pairs.csv` (git-ignored, như `it_<nguồn>.csv`, đã có nhãn tay thì không ghi đè) để bạn duyệt `merge/keep` | Dự kiến khoảng 6 cặp trên dữ liệu hiện tại |
| N18d | Công ty rỗng sau chuẩn hóa (3 tin): `company_key = null`, **không** dùng "unknown" làm khóa (sẽ gộp mọi công ty không tên thành một) | Quan trọng cho chia train/test theo công ty |

`company_key` là chuỗi ổn định (đại diện nhóm = tên ngắn nhất, hòa thì theo thứ tự chữ), chạy lại cho cùng kết quả. Cột `company_norm` giữ.

### 3.8. Ngày (N19)

| Mã | Luật | Ghi chú |
|---|---|---|
| N19a | `posted_date`, `deadline_date`: kiểm lại parser bước 03 (ISO, `dd/mm/yyyy`) và thêm xử lý ngày tương đối `N giờ/ngày/tuần/tháng trước`, `hôm qua`, `N days/weeks ago` **chỉ khi gặp**: tính từ `crawled_at`, ghi `posted_date_source="relative_from_crawled_at"` | Đo: `raw_posted_date` 3.317 tin non-null, **0 tin tương đối** (kiểm bằng `trước|ago|hôm qua`); nên luật này hiện **không có chuỗi thật nào để test**. Test chỉ dùng chuỗi thật nếu tìm được trong `data/*/raw/` (đã nói trong spec P3 mục 4); nếu không tìm được, ghi rõ test dùng chuỗi tự viết theo mẫu itviec "Đăng 6 giờ trước" nêu trong file thiết kế |
| N19b | `deadline_before_crawl` (H3, đã có): **không sửa**, chỉ kiểm đếm | Đo: 289 tin (topcv 271, careerviet 18). Nguyên nhân (tin hết hạn thật hay đọc sai `dd/mm`) vẫn mở (spec P3 mục 7 H3) |

## 4. Đo và báo cáo

- Mỗi luật `N10`-`N19`: `StepReport.rule(..., modify|flag)` kèm số tin và 3 ví dụ (không đưa nội dung JD).
- `extra.field_parse` cho từng nguồn và `_all`: số chuỗi vào, số parse được, số `unparsed`, giá trị chữ `unparsed` phổ biến nhất (10 giá trị) cho lương, kinh nghiệm, cấp bậc, tỉnh, ngày. Mục đích: "Mỗi parser đúng >= 95%" có số đo, không chỉ dựa vào đọc tay.
- `extra.title_taxonomy`: số `job_title_clean` khác nhau, số `job_title_core` khác nhau, số `title_canonical` khác nhau, số tin theo `title_canonical_source` (exact/alias/fuzzy/none), phân bố `job_family` theo nguồn và theo `job_family_source`, top 20 `job_title_core` null chưa gom được, số tin `Other`.
- Kiểm tay (bạn): **50 chuỗi thật mỗi parser** (lương, kinh nghiệm, cấp bậc, tỉnh) và **50 tin cho nhóm nghề**, seed 42. Bộ gold 100 JD của PH1 đã có trường `salary`, `experience_years`, `seniority`, `location` trong `gold.py` (`FIELDS`), nhưng **không có trường nhóm nghề**. **[CẦN CHỐT] K12:** thêm trường `job_family` (và `work_mode`) vào công cụ gán nhãn gold, hay làm file riêng `data/preprocessing/review/family_50.csv` (khuôn như `it_<nguồn>.csv`)? **[ĐỀ XUẤT]** file riêng 50 tin (không động vào PH1 đã duyệt).
- Đích: mỗi parser >= 95% đúng trên 50 chuỗi; `job_family` >= 90% đúng trên 50 tin (P4 mục 7 đã đặt 90%; file thiết kế đặt 95% cho *parser*, nhóm nghề không phải parser). K13: ngưỡng cho `title_canonical` (**[ĐỀ XUẤT]** precision >= 95% trên các tin có `title_canonical != null`, độ phủ chỉ báo cáo, không ép).

## 5. Ranh giới

- Không bỏ dòng (`rows_out = rows_in`), không sửa `raw_*`, không sửa `job_title`, `job_title_clean`, `salary_min_vnd`, `salary_max_vnd` của bước 03 (cột đã có chỉ được *thêm* cột mới cạnh nó).
- Không dùng model: chỉ `rapidfuzz` (thư viện khớp chuỗi) + từ điển + regex. Model duy nhất của dự án (`envit5-translation`) thuộc PH5.
- Không điền giá trị thiếu, không suy cấp bậc từ số năm, không suy kinh nghiệm từ cấp bậc, không gắn cờ ngoại lai: đó là PH7.
- Không cap, không log, không đụng R2, không cài gói (`rapidfuzz` đã có trong `.venv`).
- Không tự nghĩ thêm chức danh chuẩn: từ điển chỉ chứa mục có trong dữ liệu và đã được bạn duyệt.

## 6. [CẦN CHỐT]

| Mã | Câu hỏi | [ĐỀ XUẤT] |
|---|---|---|
| K1 | Tên cột mới: `job_title_core`, `title_canonical`, `title_group` hay tên khác? Bạn dùng "title_group" trong yêu cầu; mình dùng `title_canonical` (chức danh chuẩn) và `job_family` (nhóm) cho hai cấp khác nhau | `title_canonical` + `job_family`; không tạo thêm `title_group` để khỏi trùng nghĩa với `job_family` |
| K2 | Lương lớn bất thường (`300 - 500 triệu` topcv, `200000000 - 500000000 VND`, `0 - 450000000 VND` vietnamworks): tháng hay năm? Cần mở 5 trang gốc | Chưa sửa gì, chỉ gắn cờ ở PH7 (M5) cho tới khi có bằng chứng |
| K3 | Thêm cột `salary_is_net`? Chỉ 1 tin ghi "net" trong trường lương, 4 tin ghi "lương net" trong JD | Không thêm cột; báo cáo ghi "mặc định gross; 1 tin nhắc net" |
| K4 | itviec `3.1 năm (37 tháng)`, `0.8 năm (10 tháng)`, `5.1 năm (61 tháng)` (787 tin, chỉ 3 giá trị): nghĩa là gì? Là mức tối thiểu, trung bình hay nhóm? Cần xem 5 trang itviec | Tạm `exp_min = số năm` và `exp_source="compound_years_months"` kèm cờ; đổi khi bạn xác nhận |
| K5 | Cấp bậc không xác định: null hay -1 `Chưa rõ`? P4 spec ghi -1, code ghi null | null (nhất quán với `seniority`) |
| K6 | Tiêu đề có `Manager`/`Quản lý` nhưng là tên việc (`Project Manager`, `Product Manager`, `IT Manager`): cấp Lead/Manager hay không? | `Project/Product Manager` không tự thành Lead/Manager (là tên việc); `IT Manager`, `Head of`, `Director`, `Giám đốc` là Lead/Manager. Bạn xem lại 20 tin |
| K7 | Đọc 23 nhóm gộp công ty ở mục 2.6: 17 đúng, 6 nhầm, đúng không? | Xem N18b/N18c |
| K8 | `work_mode`: có dùng `hybrid`/`remote` trong JD (63 và 109 tin) để đặt, hay chỉ tiêu đề và địa điểm (35 và 18 tin)? | Chỉ tiêu đề và địa điểm; JD không dùng |
| **K9** | **Taxonomy 12 nhóm: A, B hay C (mục 3.5)?** Cụ thể BA, UI/UX, Embedded, Data Engineer/Data Science | Phương án A (SPEC-01); K9b Data Analyst vào nhóm nào; K9c nhãn lưu tiếng Anh hay Việt |
| K10 | Ngưỡng `rapidfuzz` cho chức danh (T) | 90 làm điểm khởi đầu, đo lại trên dữ liệu rồi bạn chốt |
| K11 | Tin chung chung (`Nhân viên IT`, `IT Engineer`): `Other`; tin có cả kỹ năng Backend lẫn Frontend nhưng tiêu đề chung (`Software Engineer`): Fullstack hay Other? | `Other` (không đoán). Fullstack chỉ khi tiêu đề nói fullstack/toàn diện (luật đã có) |
| K12 | Gold nhóm nghề: thêm vào công cụ gold PH1 hay file `family_50.csv` riêng? | File riêng |
| K13 | Ngưỡng nghiệm thu `title_canonical` | precision >= 95% trên tin có giá trị, không ép độ phủ |
| K14 | Số `Backend` P4 đang 856: đổi sang luật thu hẹp sẽ làm số nhóm nghề đổi lớn so với bản chạy 04/11 (đã đẩy Monitoring). Chấp nhận, ghi "trước -> sau"? | Chấp nhận |

## 7. Tiêu chí xong

- `USD_VND` ở một nơi; `fix_common_salary_input_errors` không còn chia 12: các tin vietnamworks `8000 - 9000 USD` giữ 203,2-228,6 triệu.
- Kinh nghiệm: số tin có chữ nhưng `exp_min_years` null giảm từ **1.237** (`Không yêu cầu` 393 -> 0; `Dưới một năm` 45; `Lên đến N năm` 9; `Hơn N năm` 2; itviec 787 theo K4); chuỗi nào còn `unparsed` phải liệt kê.
- Cấp bậc: đúng 5 nhãn (không còn `Thực tập`, `Mới tốt nghiệp`, `Trưởng nhóm/Quản lý`); `seniority_source in {raw, title}`; không còn nhãn do số năm tạo ra (đã chuyển PH7).
- Địa điểm: `tinh_chinh` null giảm từ **843** xuống khoảng 117 (843 - 712 - 14); có cột `work_mode`.
- Nhóm nghề: phân bố 12 + `Other` theo K9; `Embedded` có tin (nếu chọn A); không còn `Embedded Software Engineer` trong `Backend`; không còn `Nhân Viên Thiết Kế` (đồ họa) trong nhóm IT.
- Chức danh: báo cáo `extra.title_taxonomy` có đủ số; `job_title_core` 4.106 -> ước lượng ~2.470 khác nhau (số thật ghi vào báo cáo); `title_canonical` precision đo trên 50 tin.
- Công ty: `company_key` khác nhau <= 2.218 và các cặp nhầm trong 2.6 **không** bị gộp tự động; file `company_pairs.csv` có các cặp còn lại.
- 50 chuỗi thật mỗi parser >= 95% đúng (bạn chấm); nhóm nghề >= 90% (50 tin).
- `pytest tests/unit` xanh; test cũ nào khẳng định hành vi sai (`classify_seniority` trả 6 nhãn; `fix_common_salary_input_errors` chia 12) thì sửa và ghi lý do. `tests/unit/test_normalization_step.py` hiện có và sẽ phải đổi nhãn.

## 8. Monitoring thấy gì

- Bảng "parse được / không parse được" theo trường và nguồn, kèm top giá trị `unparsed`.
- Biểu đồ phân bố 12 nhóm + `Other` theo nguồn, tách theo `job_family_source`; bảng top `job_title_core` chưa có `title_canonical`.
- Khối công ty: số cặp chờ duyệt.
- `work_mode` theo nguồn.
- Không thêm trang mới. **[CẦN CHỐT] K15:** trang `/preprocessing` có hiển thị khối `extra.title_taxonomy` ngay trong PH6 hay để sau?

## 9. Không làm

Không sửa raw; không sửa `job_title_clean`; không điền hay suy giá trị; không bỏ dòng; không dùng model; không ghi R2; không cài gói; không bịa chức danh chuẩn ngoài dữ liệu; không dọn các bản `fold` rời nhau (đã ghi ở PH2); không chuyển `Encoding` sang `processing/`.

## 10. Quyết định đã chốt (10/11/2026, người dùng)

- **K9 = A:** đúng 12 nhóm SPEC-01 (Backend, Frontend, Fullstack, Mobile, DevOps/Cloud, Data Engineer, Data Science/AI, QA/QC, Security, Product/Project, System/Network, Embedded/IoT) + `Other`; BA vào Product/Project; UI/UX và thiết kế đồ họa vào `Other`. K9c: nhãn tiếng Anh. **K9b (agent chọn, người dùng xem lại):** Data Analyst, BI, "phân tích dữ liệu" vào Data Science/AI.
- **K4:** itviec `3.1 năm (37 tháng)` đọc phần nguyên: 3 năm (`0.8 -> 0`, `5.1 -> 5`), status `compound_years_months`. Hệ quả cần xem: `0.8 năm` cho `exp_min = 0` nên PH7 M3c suy `Intern/Fresher` (có cờ `level_inferred`) cho 317 tin itviec.
- **K5:** cấp bậc không xác định là null (không dùng -1). **K6:** Project/Product Manager tính là Lead/Manager (đổi so với đề xuất cũ).
- **Lương:** `USD_VND = 25.400` một nơi; nhãn tiền tệ lấy từ chữ trong chuỗi (USD, $, VND, triệu...); nhãn USD với số >= 100.000 (>= 1.000.000 nếu lương năm) đọc lại là VND; lương năm chỉ chia 12 khi JD ghi đúng các số đó là lương năm; tiền tệ khác (EUR, SGD, JPY...) được nhận diện và bỏ số, chưa có tỷ giá được duyệt. `fix_common_salary_input_errors` giữ chữ ký nhưng không sửa số.
- **K10-K15 và còn lại** theo [ĐỀ XUẤT]: T = 90, tin chung chung là `Other`, `family_50.csv` file riêng (chưa tạo), `precision >= 95%` cho `title_canonical`, chấp nhận số nhóm nghề đổi lớn so với bản 04/11, K15 để sau.
- `job_titles.json` chỉ gồm ứng viên `approved=false` đếm từ dữ liệu thật (`scripts/count_title_candidates.py`); chỉ mục `approved=true` được nạp. `classify_job_family_rule`/`JOB_FAMILIES` cũ của `text_cleaner.py` giữ nguyên vì `common/it_filter.py` (tầng 2 của PH3) và `encoding/` còn dùng; bước 04 dùng `normalization/job_title.py`.
