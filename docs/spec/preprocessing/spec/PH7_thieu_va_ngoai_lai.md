# PH7. Dữ liệu thiếu và ngoại lai (bước 6 của file thiết kế)

> **Nháp đặc tả, chờ bạn sửa** (10/11/2026). Chưa có code. Prompt: `docs/prompting/PH7_thieu_va_ngoai_lai.md` (chưa duyệt). Làm sau PH6 (cần cấp bậc 5 cấp, `job_family`, `work_mode`, `exp_min_years` đã đầy đủ hơn).
> **[ĐỀ XUẤT]** = mình đoán. **[CẦN CHỐT]** = cần bạn quyết (mã `X1`...).
> Số liệu đo ngày 10/11/2026, chỉ đọc, trong bộ nhớ, cùng cách đo với PH6 (chạy `integration.run.process_source` và `transformation.run.process_source` dry-run trên `data/preprocessing/01_clean/*.jsonl`: 5.076 tin; cấp bậc tính bằng `classify_seniority` của bước 04 hiện tại, **trước** khi PH6 đổi sang 5 cấp và bỏ tầng số năm). `data/preprocessing/03_transformation/` và `04_normalization/` đang trống nên chưa đo trên file thật.

## 1. Mục tiêu

Bước 6 của file thiết kế: xử lý thiếu và ngoại lai **có cờ**, không âm thầm.

1. Lương "Thỏa thuận": không điền, có cờ `salary_negotiable` (MNAR).
2. Cấp bậc trống: suy từ tiêu đề, gắn `level_inferred`.
3. Kinh nghiệm trống: suy từ cấp bậc hoặc `unknown`.
4. Lương ngoài 2-200 triệu/tháng: kiểm lỗi parse.
5. IQR theo từng cấp bậc: **chỉ gắn cờ**.
6. Có **bảng chiến lược xử lý thiếu kèm lý do** (mục 4) trong báo cáo.

Tiêu chí: Completeness, Accuracy. Không đặt số mẫu mục tiêu. Nguyên tắc: mọi giá trị suy ra phải phân biệt được với giá trị gốc (cột cờ + cột nguồn) để Mining có thể loại ra.

**Vị trí [ĐỀ XUẤT]:** không tạo thư mục bước mới; chạy **trong bước 04**, sau các luật PH6 (`N10`-`N19`) và trước log (`N7`), dùng thư viện đã có `preprocessing/missing_outlier/`. Mã luật `M1`-`M9`. Lý do: cần nhãn chuẩn của PH6; giữ nguyên số thư mục để Monitoring không đổi; khớp ranh giới P0 ("Normalization không scale trước khi xử lý outlier"). **[CẦN CHỐT] X1:** hay tách thành bước `04b_missing_outlier` riêng với báo cáo riêng?

## 2. Hiện trạng đo trên dữ liệu thật

### 2.1. Bảng hiện trạng so với thiết kế

| Mục thiết kế | Code hiện tại | Đo trên 5.076 tin | Lệch / việc cần làm |
|---|---|---|---|
| `salary_negotiable` (không điền, có cờ) | cột **`is_negotiable`** (bước 03, T2e); số để NaN | có số: 2.319; **không số**: 2.757; trong đó `is_negotiable` đủ (số lớn); **`is_negotiable` và có số cùng lúc: 29 tin**; **không số và không negotiable: 23 tin** | Tên cột khác thiết kế (X2). 29 tin mâu thuẫn, 23 tin "không ghi, không phải thỏa thuận" chưa có nhãn riêng. M1, M2 |
| Cấp bậc trống: suy từ tiêu đề + `level_inferred` | N2: raw -> title -> **số năm**; `seniority_source` ghi nguồn; **không có `level_inferred`** | null 899 tin sau cả 3 tầng; nguồn: kinh_nghiem **2.256**, title 1.130, raw 791 | Tầng số năm tạo gần nửa số nhãn mà không gắn cờ. Sau PH6 chỉ còn raw+title (1.921 tin có nhãn thật). M3 |
| Kinh nghiệm trống: suy từ cấp bậc hoặc `unknown` | không có | `exp_min_years` null: itviec 100%, topdev 74,4%, jobsgo 36,7%, glints 25,5%, vietnamworks 15,8%, careerviet 13,0%, topcv 9,6%, vieclam24h 1,1%. Cấp bậc thật (raw/title) mà thiếu kinh nghiệm: **831 tin** | M4 |
| Địa điểm thiếu: `unknown` | `tinh_chinh` null 843 (sau PH6 N13 còn khoảng 117) | | M7 |
| Lương ngoài 2-200 triệu: sửa lỗi parse | N6a: ngoài **1-500 triệu** -> NaN + `salary_suspect` (22 tin); `fix_common_salary_input_errors` có lỗi (PH6 2.2) | `< 2 triệu`: min 21, max 11; `> 200 triệu`: min 5, max 13; trong đó có lương USD hợp lệ (8.000-9.000 USD = 203-229 triệu) | Ngưỡng thiết kế (2-200) khác code (1-500). Cả hai đều sai với một số tin hợp lệ. M5, X3 |
| IQR theo cấp bậc, chỉ cờ | N6: **IQR gộp chung** toàn bảng (73 tin) + **winsorize 1-99%** ghi cột `*_capped` | pooled: Q1..Q3 -> cận trên 76,6 triệu; 73 tin; theo cấp bậc (6 nhãn cũ) tổng 100 tin | Chưa theo cấp bậc. Winsorize là "cap" chứ không phải "chỉ gắn cờ". M6, X4 |
| Bảng chiến lược xử lý thiếu | không có | | Mục 4, M9 |
| Null trá hình | `sneaky_null_detector.py` (T1) đã chạy ở bước 03 | `VietnamWorks raw_education_text="0"` đã xử lý | Không đổi |

### 2.2. Ma trận thiếu theo trường x nguồn (% tin **có** giá trị, đo 10/11/2026)

| Nguồn | Lương (số hoặc thỏa thuận) | Kinh nghiệm (`exp_min`) | Cấp bậc raw | Công ty | Tỉnh (sau N1 hiện tại) | Ngày đăng | Kỹ năng |
|---|---|---|---|---|---|---|---|
| careerviet | 99,8 | 87,0 | 98,0 | 100 | 98,7 | 98,0 | 79,6 |
| glints | 98,2 | 74,5 | **0** | 100 | 72,0 | 100 | 98,2 |
| itviec | 100 | **0** | **0** | 100 | **20,6** | 96,6 | 100 |
| jobsgo | 99,9 | 63,3 | 99,7 | 99,9 | 98,7 | 99,7 | 62,5 |
| topcv | 99,7 | 90,4 | 99,6 | 100 | 99,2 | **0** | 97,6 |
| topdev | 100 | **25,6** | 0,4 | 100 | 99,6 | 31,3 | 90,3 |
| vieclam24h | 98,9 | 98,9 | 100 | 100 | 100 | 100 | 100 |
| vietnamworks | 98,8 | 84,2 | 100 | 100 | 97,6 | 100 | 100 |

Cột "Lương" tính cả `is_negotiable`: số thật thấp hơn nhiều. Tỉ lệ **có số lương**: vieclam24h 92,3%, glints 59,8%, jobsgo 58,7%, topcv 56,6%, careerviet 30,4%, topdev 26,9%, vietnamworks 26,0%, itviec 25,5%; `is_negotiable`: itviec 74,8%, vietnamworks 71,6%, topdev 72,7%, careerviet 69,4%, topcv 42,2%, glints 39,9%, jobsgo 37,9%, vieclam24h 7,1%. Thiếu **phụ thuộc nguồn** (itviec, topdev không có cấp bậc/kinh nghiệm; topcv không có ngày đăng): MAR, không phải MCAR như bảng 3.4 của file thiết kế ghi cho địa điểm.

### 2.3. Phân bố lương theo cấp bậc (nhãn 6 cấp hiện tại, đơn vị triệu VND/tháng, mức max hoặc min nếu thiếu max)

| Cấp bậc | n có lương | trung vị | Q1 | Q3 | max |
|---|---|---|---|---|---|
| Thực tập | 142 | 4,0 | 3,0 | 8,0 | 38,1 |
| Mới tốt nghiệp | 149 | 15,0 | 12,0 | 20,0 | 60,0 |
| Junior | 829 | 20,0 | 15,0 | 28,0 | 500 |
| Middle | 341 | 30,0 | 25,0 | 40,0 | 450 |
| Senior | 189 | 45,7 | 38,1 | 60,0 | 114,3 |
| Trưởng nhóm/Quản lý | 336 | 40,0 | 29,0 | 50,0 | 500 |
| (null) | 333 | 20,0 | 14,0 | 45,7 | 450 |

Số tin ngoài IQR (1,5 x IQR) theo cấp: Junior 46/829, Trưởng nhóm 20/336, Middle 13/341, Thực tập 10/142, Senior 7/189, Mới tốt nghiệp 4/149. Các cực đại 450-500 triệu đều thuộc Junior/Middle/Trưởng nhóm, chính là các dòng nghi lương năm hoặc nhập sai của vietnamworks/topcv (PH6 K2). Quan sát: **Senior có trung vị 45,7 triệu nhưng Trưởng nhóm 40 triệu** (thấp hơn); do nhãn hiện tại lẫn tiêu đề "Manager" với tên việc (PH6 K6), nên IQR theo cấp phải đo lại sau khi PH6 sửa nhãn.

### 2.4. Số năm kinh nghiệm theo cấp bậc (cấp từ raw hoặc tiêu đề, `exp_min_years` đã có)

| Cấp | n | trung vị `exp_min` | Q1-Q3 | min-max |
|---|---|---|---|---|
| Thực tập | 37 | 0 | 0-0 | 0-1 |
| Mới tốt nghiệp | 22 | 0,5 | 0-1 | 0-2 |
| Junior | 51 | 1 | 1-1,5 | 0-3 |
| Middle | 44 | 2 | 2-3 | 1-6 |
| Senior | 278 | 3 | 3-5 | 0-7 |
| Trưởng nhóm/Quản lý | 658 | 3 | 3-5 | 0-20 |

Ý nghĩa cho "suy kinh nghiệm từ cấp bậc": chỉ **Intern/Fresher** có phân phối chặt (trung vị 0, Q1-Q3 0-1). Senior và Lead/Manager trải rộng (3-5, tối đa 7 và 20) nên **không có một số đúng** để điền. Cũng cho thấy luật số-năm-sang-cấp-bậc hiện tại (`1-2 năm -> Junior; 3-4 -> Middle; >= 5 -> Senior`) ngược với dữ liệu: Senior thật có trung vị 3 năm; còn spec P4 ghi `>= 2 -> Middle`, khớp trung vị Middle = 2. Số tin theo `exp_min`: 0: 212, 1: 834, 2: 794, 3: 864, 4: 157, 5: 397. Tức chọn ngưỡng đổi nhãn của hàng nghìn tin (X6).

### 2.5. Các giá trị khác

- `exp_min_years >= 15`: 4 tin (tối đa 20; `exp_max` tối đa 25). `exp_min > exp_max`: 0 tin.
- `salary_min_vnd > salary_max_vnd`: 1 tin.
- Cờ hiện có (`flags`): `deadline_before_crawl` 289, `salary_suspect` 22, `salary_under_1m` 15.
- `salary_period_raw = year`: 4 tin (kết quả: 25,0-66,7 triệu; 16,7 triệu; hai tin có `raw_salary_text` rỗng hoặc `Công ty không công khai thông tin này` nhưng vẫn ra số 50 triệu từ nguồn khác: **cần kiểm** vì chuỗi này nghĩa là không công khai; X7).

## 3. Luật PH7

Mã luật `M1`-`M9`. Mỗi luật `flag` hoặc `impute` ghi số tin và 3 ví dụ; luật `impute` luôn kèm cột nguồn.

### 3.1. Lương (M1, M2, M5, M6)

| Mã | Luật | Cột |
|---|---|---|
| M1 | `salary_negotiable` = `is_negotiable` (đã tính ở T2e). **Không điền** `salary_min/max` khi thỏa thuận (MNAR) | **[ĐỀ XUẤT]** giữ `is_negotiable`, thêm bản sao `salary_negotiable` hoặc đổi tên: X2 |
| M2 | `salary_status` in {`value`, `negotiable`, `not_stated`} (cùng bộ giá trị với gold `SALARY_KINDS`: negotiable / not_stated / value). `value` nếu có `salary_min` hoặc `salary_max`; `negotiable` nếu `is_negotiable` và không có số; `not_stated` còn lại | Đo: 23 tin `not_stated`; 29 tin vừa negotiable vừa có số -> `value` + cờ `salary_negotiable_with_value` để xem lại (nhiều khả năng "Up to X, thỏa thuận") |
| M5 | Khoảng hợp lệ lương tháng, **chỉ gắn cờ**, không sửa số: ngoài `[LOW, HIGH]` -> `salary_out_of_range`; thay luật chia 12 / x 25.400 của `fix_common_salary_input_errors`. Chỉ **được sửa** khi có bằng chứng trong chính tin: `salary_period_raw == "year"` (T2 đã chia 12) hoặc `salary_currency_raw == "USD"` (đã nhân 25.400); không sửa dựa trên chữ "năm" trong JD | `LOW/HIGH` theo X3. Giữ `salary_suspect` (đã có) |
| M6 | IQR **theo cấp bậc** (5 cấp của PH6) trên `salary_max_vnd` (hoặc `salary_min` nếu thiếu max): `salary_iqr_outlier` + `salary_iqr_bounds_level`; chỉ khi cấp có `>= 30` tin có lương (**[ĐỀ XUẤT]**, K nhỏ hơn thì không đủ để tính, ghi `not_enough_data`); tin cấp null: dùng IQR gộp, ghi `salary_iqr_scope="pooled"` | Không sửa số. Cờ cũ `is_outlier_salary` (IQR gộp, N6) giữ nguyên để Monitoring cũ không vỡ; thêm cột mới `salary_iqr_outlier_by_level` |

**Về khoảng hợp lệ (X3):** thiết kế ghi "ngoài 2-200 triệu: sửa lỗi parse"; code (03/11) dùng 1-500 triệu (`MONTHLY_MIN_VND`, `MONTHLY_MAX_VND`). Đo cho thấy: dưới 2 triệu có 21 giá trị min / 11 max, phần lớn là thực tập thật (trung vị thực tập 4 triệu, Q1 3 triệu), nên 2 triệu **cắt nhầm thực tập**; trên 200 triệu có USD hợp lệ 203-229 triệu (VietnamWorks, ITviec `6,000 - 9,000 USD`) cùng các dòng nghi lương năm (K2 của PH6). **[ĐỀ XUẤT]** `LOW = 1 triệu`, `HIGH = 500 triệu` để NaN hóa (đang chạy, N6a); **cờ riêng** `salary_out_of_range` cho ngoài 2-200 triệu **không** NaN hóa, để Mining xem. Bạn chốt số.

### 3.2. Cấp bậc (M3, thay tầng số-năm của N2)

| Mã | Luật | Cột |
|---|---|---|
| M3a | Cấp bậc đã có từ PH6 (`raw`, `title`): giữ, `level_inferred = False` | |
| M3b | Cấp bậc trống: **suy từ `job_title_core`/tiêu đề** (PH6 đã thử và không ra thì tới đây thử luật mở rộng nếu có, ví dụ `IT Manager` -> Lead/Manager nếu PH6 K6 chốt như vậy). Nếu PH6 đã dùng đủ luật tiêu đề thì M3b không thêm gì: ghi vào báo cáo "0 tin thêm" | `level_inferred=True`, `seniority_source="title_inferred"` |
| M3c | Còn trống: suy từ số năm tối thiểu (`exp_min_years`) theo bảng ngưỡng X6: `level_inferred=True`, `seniority_source="kinh_nghiem"` | Đây là luật đang chạy ở N2 tầng 3 (2.256 tin), chuyển sang PH7 và gắn cờ |
| M3d | Còn trống: `seniority = null`, `seniority_source = "none"`, `level_inferred = False` (không phải "đã suy", mà là "không suy được") | Đo: 899 tin null sau cả 3 tầng cũ |

**Luật chống vòng:** M4 (kinh nghiệm từ cấp bậc) **không dùng** cấp bậc có `seniority_source = "kinh_nghiem"` (nó vốn sinh ra từ kinh nghiệm), tránh vòng "kinh nghiệm -> cấp bậc -> kinh nghiệm".

### 3.3. Kinh nghiệm (M4)

| Mã | Luật | Ghi chú |
|---|---|---|
| M4a | `exp_min_years` đã có: giữ, `exp_inferred = False` | |
| M4b | `exp_min_years` null và cấp bậc `Intern/Fresher` **từ raw hoặc title**: `exp_min_years = 0`, `exp_inferred=True`, `exp_source="level_intern_fresher"` | Dữ liệu chống đỡ: Thực tập 37 tin trung vị 0 (0-0), Mới tốt nghiệp 22 tin 0,5 (0-1). Chưa kiểm 100%, nên chỉ điền **0** (cận dưới), không điền 0,5 |
| M4c | Các cấp khác (`Junior`, `Middle`, `Senior`, `Lead/Manager`): **không điền số**; `exp_min_years = null`, `exp_source = "unknown"` | Dữ liệu cho thấy khoảng rộng (Senior 3-5, tối đa 7; Lead 3-5, tối đa 20), điền một số sẽ sai; "unknown" đúng với file thiết kế ("suy từ cấp bậc **hoặc** unknown") |
| M4d | Cột bổ trợ **[ĐỀ XUẤT]** `exp_level_range` (chuỗi, ví dụ `"2-3"`, Q1-Q3 của cấp trong dữ liệu có `exp` thật) **không** thêm ở đợt này | Vì phân phối theo cấp chỉ mô tả, không phải luật; thêm khi Processing cần (feature construction 10c còn mở) |

Đo tác động: cấp bậc thật (raw/title) mà thiếu kinh nghiệm: 831 tin. Sau M4b chỉ điền được phần thuộc Intern/Fresher (con số thật ghi vào báo cáo; mình chưa đo riêng vì cần nhãn 5 cấp của PH6).

### 3.4. Địa điểm (M7)

`tinh_chinh` null (sau PH6 N13): `tinh_chinh = null` kèm `tinh_status="unknown"`, **không** điền "Hà Nội"/"TP. Hồ Chí Minh" theo mode (MAR phụ thuộc nguồn: itviec 719 trên 843 tin thiếu). Thiết kế gọi là MCAR "tỉ lệ nhỏ"; đo cho thấy **không phải MCAR** (itviec 20,6% có tỉnh). Tin `remote` và `ngoai_vn` không phải "thiếu": `tinh_status` = `remote` / `foreign` (không `unknown`). Giá trị `tinh_status` in {`ok`, `remote`, `foreign`, `unknown`}.

### 3.5. Ngoại lai khác (M8)

| Mã | Luật | Cột |
|---|---|---|
| M8a | `salary_min_vnd > salary_max_vnd`: **không** hoán đổi tự động; cờ `salary_min_gt_max` (1 tin). Hoán đổi chỉ khi X8 đồng ý | |
| M8b | `exp_min_years >= 15` hoặc `exp_max_years > 20`: cờ `exp_out_of_range` (4 tin); không sửa | |

### 3.6. Bảng chiến lược xử lý thiếu (M9)

Mỗi báo cáo bước 04 có `extra.missing_strategy`: một bảng (trường, cơ chế thiếu, cách xử lý, lý do, số tin thiếu trước, số tin điền sau, cờ). Nội dung mặc định, tiếng Việt:

| Trường | Cơ chế | Cách xử lý | Lý do | Cờ |
|---|---|---|---|---|
| Lương: thỏa thuận | MNAR | Không điền; `salary_negotiable`, `salary_status="negotiable"` | Vị trí lương cao hay giấu; điền trung bình kéo lệch phân phối. Hồi quy lương chỉ dùng tin `value` | `salary_negotiable` |
| Lương: không ghi | MNAR hoặc nguồn không có | Không điền; `salary_status="not_stated"` | Không phân biệt được "giấu" và "nguồn không cào" | `salary_status` |
| Cấp bậc | MAR (phụ thuộc nguồn: glints, itviec, topdev) | raw -> tiêu đề -> số năm; còn lại null | Phân biệt giá trị gốc và suy ra | `level_inferred`, `seniority_source` |
| Kinh nghiệm | MAR (itviec 100% thiếu, topdev 74%) | Intern/Fresher -> 0; còn lại `unknown` | Phân phối theo cấp rộng, điền một số sẽ sai (2.4) | `exp_inferred`, `exp_source` |
| Tỉnh | MAR (itviec 79,4% thiếu trước N13) | `unknown`, không điền mode | Mode (Hà Nội/TP.HCM) tạo tập trung giả | `tinh_status` |
| Ngày đăng | Cấu trúc (topcv không có) | Không điền | Nguồn không có trường | (không) |
| Kỹ năng | MAR (jobsgo 62,5%) | Không điền; PH8 trích từ JD | Kỹ năng đến từ văn bản JD | (không) |

Bảng này lấy số từ ma trận thật, không để tay.

## 4. Đo và báo cáo

- Mỗi luật `M1`-`M9`: số tin, 3 ví dụ (không có nội dung JD).
- `extra.missing_matrix`: trường x nguồn, `% có giá trị` **trước và sau** PH7 (cùng khuôn bảng 2.2); cùng dữ liệu cho heatmap bước 0 của PH1.
- `extra.outliers`: số tin theo cờ (`salary_out_of_range`, `salary_iqr_outlier_by_level`, `salary_suspect`, `salary_min_gt_max`, `exp_out_of_range`), theo cấp bậc và nguồn; cận IQR của từng cấp.
- `extra.inference`: số tin `level_inferred`, `exp_inferred`, theo nguồn nhãn (`title_inferred`, `kinh_nghiem`, `level_intern_fresher`).
- Kiểm tay: bạn xem **20 tin có `level_inferred=True` từ số năm** (seed 42), **20 tin cờ IQR theo cấp** và **29 tin vừa negotiable vừa có số**. Đích **[ĐỀ XUẤT]**: tin suy cấp từ tiêu đề đúng >= 90% trên 20 tin; không bắt buộc đạt cho suy từ số năm (chỉ báo cáo), vì 2.4 cho thấy luật đó yếu.
- Đo thêm: tỷ lệ nhãn cấp bậc **suy ra / thật** theo nguồn (hiện 2.256/1.921 trước khi PH6 tách); nếu suy ra > thật thì cảnh báo trong báo cáo.

## 5. Ranh giới

- Không xóa dòng (`rows_out = rows_in`); không xóa outlier; không sửa `raw_*`; không sửa giá trị gốc `salary_min_vnd`, `salary_max_vnd`, `exp_min_years` đã có (chỉ điền ô null, và mọi điền đều có cờ).
- Không bù bằng mean/median/mode; không dùng model (kể cả KNN/MICE); không điền lương.
- Giữ cột `*_capped` và `is_outlier_salary` hiện có để Monitoring và `test_normalization_step.py` không vỡ (X4 quyết có bỏ winsorize không).
- Không scale/log trước M5-M6 (`N7` sau `M*`).
- Không động tới R2, không cài gói.

## 6. [CẦN CHỐT]

| Mã | Câu hỏi | [ĐỀ XUẤT] |
|---|---|---|
| X1 | PH7 chạy trong bước 04 hay tách `04b`? | Trong 04 |
| X2 | Tên cột: `salary_negotiable` (thiết kế) hay giữ `is_negotiable` (code, Monitoring và test đang dùng)? | Giữ `is_negotiable`, thêm `salary_negotiable` là bản sao, bỏ sau khi Monitoring đổi |
| X3 | Khoảng hợp lệ lương: 2-200 (thiết kế) hay 1-500 (code), và hành vi: NaN hóa hay chỉ cờ? | NaN hóa 1-500 (giữ N6a); thêm cờ `salary_out_of_range` cho ngoài 2-200 |
| X4 | Winsorize 1-99% (N6, cột `*_capped`): giữ, hay bỏ vì thiết kế nói IQR "chỉ gắn cờ"? | Giữ làm cột riêng cho log/N7; nêu rõ nó không thay cột gốc. Bạn xem có muốn bỏ |
| X5 | Số tin tối thiểu mỗi cấp để tính IQR riêng | 30 |
| X6 | Ngưỡng đổi số năm sang cấp bậc (M3c): spec P4 (`0 -> Intern/Fresher, > 0 -> Junior, >= 2 -> Middle, >= 5 -> Senior`) hay code (`1-2 Junior, 3-4 Middle, >= 5 Senior`) hay theo dữ liệu (xem 2.4)? Quyết định đổi nhãn hơn 800 tin | Dùng spec P4 (0 -> Intern/Fresher; 1 -> Junior; 2-4 -> Middle; >= 5 -> Senior); mình thấy `Lead/Manager` không suy từ số năm. Bạn chốt vì mình không biết quy ước thực tế |
| X7 | Tin `raw_salary_text = "Công ty không công khai thông tin này"` mà có `salary_max = 50 triệu` (nguồn khác trong cùng tin?): giữ số hay bỏ? | Kiểm 5 tin trước; ghi nguyên nhân |
| X8 | `min > max`: hoán đổi hay chỉ cờ? | Chỉ cờ (1 tin) |
| X9 | `Intern/Fresher` thiếu kinh nghiệm điền 0: chấp nhận hay giữ `unknown`? | Điền 0 (có cờ) |
| X10 | Cấp suy từ tiêu đề (M3b): có nằm ở PH6 hay PH7? Hiện PH6 N12 đã dùng tiêu đề; nếu PH6 dùng hết luật tiêu đề thì M3b rỗng | Để trong PH6 `N12` (tầng `title`); PH7 chỉ tầng số năm. M3b chỉ còn khi bạn muốn luật tiêu đề lỏng hơn (ví dụ từ khóa thiếu chính xác) và gắn `level_inferred` |
| X11 | Kỹ năng thiếu (jobsgo 37,5%) và ngày thiếu: không xử lý ở PH7? | Không xử lý |

## 7. Tiêu chí xong

- `rows_in = rows_out + dropped` mọi nguồn, `dropped = 0`.
- `salary_negotiable` có ở mọi tin; 29 tin vừa negotiable vừa có số được cờ; 23 tin `not_stated`.
- Cấp bậc: cột `level_inferred` có; **0 tin `seniority_source="kinh_nghiem"` mà `level_inferred=False`**; số nhãn thật (raw+title) khớp báo cáo PH6.
- Kinh nghiệm: mọi tin điền có `exp_inferred=True` và `exp_source`; không tin nào điền số khác 0.
- Lương: 6 tin vietnamworks bị chia 12 sai (PH6 2.2) giữ nguyên số T2; `salary_out_of_range`, `salary_iqr_outlier_by_level` có đếm; không số nào bị sửa ngoài việc N6a NaN hóa ngoài 1-500.
- `extra.missing_strategy` và `extra.missing_matrix` có đủ, số khớp phép đo tay ở 2.2 (trước PH7).
- `pytest tests/unit` xanh; `test_normalization_step.py` cập nhật nhãn và cờ; ghi lý do mỗi test sửa.

## 8. Monitoring thấy gì

- Heatmap thiếu trường x nguồn trước/sau.
- Bảng chiến lược xử lý thiếu (mục 3.6) kèm số.
- Biểu đồ hộp lương theo cấp bậc, đánh dấu tin cờ IQR theo cấp; số `level_inferred` theo nguồn.
- **[CẦN CHỐT] X12:** hiển thị trong PH7 hay sau.

## 9. Không làm

Không điền lương, không điền kinh nghiệm cho Junior/Middle/Senior/Lead; không xóa ngoại lai; không dùng model; không sửa raw; không đổi tên cột đã có (trừ thêm bản sao X2); không ghi R2; không cài gói.

## 10. Quyết định đã chốt (10/11/2026, người dùng)

- **X3:** khoảng lương hợp lệ 2-100 triệu/tháng cho cờ `salary_out_of_range` (không sửa số); N6a NaN hóa ngoài 1-500 triệu giữ như cũ (agent hiểu theo đề xuất; cần xác nhận nếu muốn NaN hóa cả ngoài 2-100). Mọi chuyển đổi USD dùng 25.400, không coi số lớn là VND một cách mù quáng (xem PH6 mục 10).
- **X4:** giữ winsorize 1-99% (cột `*_capped`). **X6:** ngưỡng số năm theo spec P4: 0 Intern/Fresher, (0,2) Junior, [2,5) Middle, >= 5 Senior, có `level_inferred`; Lead/Manager không suy từ số năm. Các X còn lại theo [ĐỀ XUẤT].
- **Yêu cầu mới:** mọi cờ/bất thường/ngoại lai/suy luận kèm `job_id` và nguồn trong `reports/preprocessing/04_normalization/anomalies.json` (xem `docs/spec/monitoring/preprocessing_page_spec.md` mục 8).
