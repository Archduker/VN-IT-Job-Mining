# Thống kê vấn đề dữ liệu trước khi refactor pre-processing (03/11/2026)

Đầu vào: raw trên máy (đã khớp R2), mỗi tin lấy snapshot mới nhất, làm phẳng bằng `flatten_raw_job_record` hiện tại. Chỉ đọc, không sửa dữ liệu.

**Bản trực quan có biểu đồ và số liệu đầy đủ: [`data_issues_2026-11-03.html`](data_issues_2026-11-03.html)**, sinh bằng `python scripts/report_data_issues.py`. File này giữ các kết luận và luật đã chốt; số chi tiết xem ở HTML.

| Nguồn | Tin (bản mới nhất) | Snapshot | Snapshot v>1 | File batch cũ |
|---|---|---|---|---|
| topcv | 2.674 | 2.749 | 66 | — |
| topdev | 2.782 | 3.890 | 1.105 | — |
| vietnamworks | 1.219 | 1.947 | 725 | 1 (931 tin) |
| careerviet | 642 | 660 | 18 | — |
| vieclam24h | 660 | 660 | 3 | 1 (616 tin) |
| itviec | 910 | 911 | 1 | — |
| glints | 331 | 331 | 0 | — |
| jobsgo | 1.540 | 1.597 | 57 | — |
| **Tổng** | **10.758** | | | |

Mức: **Cao** = làm sai số liệu phân tích; **TB** = mất thông tin hoặc khó so giữa nguồn; **Thấp** = làm sạch thêm.

## A. Phạm vi dữ liệu (một phần thuộc collection)

| # | Vấn đề | Số liệu | Mức | Thuộc |
|---|---|---|---|---|
| A1 | Tin ngoài IT lẫn vào | Tiêu đề không khớp từ khóa IT (ước lượng thô): TopDev 81,8%, Vieclam24h 55,0%, JobsGO 32,7%, CareerViet 23,8%, VietnamWorks 23,0%, TopCV 21,6%, Glints 18,1%, ITviec 5,6%. **TopDev đã chứng minh:** API `/td/v2/jobs` trả cùng 14.572 tin dù có hay không có `category_ids=1` (đo 03/11/2026, trang 1 giống 50/50), tức tham số lọc IT của crawler bị bỏ qua; tỉ lệ ngoài IT ~80% ở cả đợt 20/10 và 01/11 | Cao | **Chưa quyết bỏ** (chốt 03/11/2026): kiểm ở cả 8 nguồn (`spec/P1_clean.md` C4a–C4c). Phân loại bằng luật + JEV, gán nhãn tay mẫu từng nguồn, tìm nguyên nhân (crawler kéo sai / nguồn đăng lẫn / phân loại sai) rồi mới duyệt chính sách bỏ. TopDev: sửa phạm vi cào ở collection |
| A2 | ITviec lưu ngày đăng dạng tương đối trong raw và đưa vào hash | `posted_at_raw` = "Đăng\n6 giờ trước"; 855 tin. **Khắc phục được:** raw đã có `job_posting_jsonld.datePosted` dạng tuyệt đối → sửa flattener, không cần cào lại; crawler bỏ `posted_at_raw` khỏi hash cho các lần cào sau | Cao | Pre-processing (P1) + collection |
| A3 | Raw TopDev cũ thiếu kinh nghiệm, cấp bậc, ngày đăng | SCRAPE-5. **Khắc phục được:** cào lại là có đủ (`DETAIL_FIELDS` đã sửa 02/11) | TB | Collection (cào lại) |

## B. Trùng lặp

| # | Vấn đề | Số liệu | Mức |
|---|---|---|---|
| B1 | Nhiều version của cùng tin | 1.975 snapshot v>1 (TopDev 1.105, VietnamWorks 725) | Cao nếu không chọn bản mới nhất |
| B2 | File batch cũ trùng file từng tin (PRE-8) | VietnamWorks 931 tin, Vieclam24h 616 tin | Cao |
| B3 | Trùng theo luật đã chốt | **Luật: cùng công ty + cùng tiêu đề + cùng nơi làm việc (thành phố) + cùng khung thời gian đăng (tuần).** Tiêu đề + công ty: 636 tin thừa; + thành phố: 407; + tuần đăng: 188. Nhóm trùng khác nguồn tụt 169 → 9 khi thêm thành phố vì mỗi nguồn ghi thành phố một kiểu: **phải chuẩn hóa thành phố trước khi so**. Trụ sở không dùng được (TopDev 0% có địa chỉ); TopCV, TopDev không có ngày đăng nên dùng tuần cào | TB |
| B3a | Cùng tiêu đề + công ty trong một nguồn (đếm cũ) | 462 tin thừa (JobsGO 195, TopCV 80, TopDev 75, ITviec 36, VietnamWorks 35, CareerViet 24, Glints 10, Vieclam24h 7) | TB |
| B4 | Cùng tiêu đề + công ty ở nhiều nguồn | 150 cặp; nhiều nhất JobsGO–TopCV 54, TopCV–VietnamWorks 18 | TB (đúng mục tiêu dedup chéo) |
| B5 | 300 ký tự đầu JD giống hệt nhau | TopDev 739, JobsGO 479, Vieclam24h 213, TopCV 163, ITviec 139, VietnamWorks 137 | Thấp (thường là đoạn giới thiệu công ty chung) |

## C. Thiếu trường sau làm phẳng (% tin có giá trị)

| Trường | topcv | topdev | vnw | careerviet | vl24h | itviec | glints | jobsgo |
|---|---|---|---|---|---|---|---|---|
| raw_posted_date | **0** | **0** | 100 | 97,8 | 100 | 96,2 (tương đối) | 100 | 99,5 |
| raw_deadline | 98,5 | **0** | 100 | 97,8 | 100 | 96,2 | 97,6 | 99,6 |
| raw_experience_text | 96,8 | **0,1** | 82,9 | 88,5 | 100 | 86,6 | 88,8 | 99,6 |
| raw_seniority_text | 96,8 | **0,1** | 100 | 97,8 | 100 | **0** | **0** | 99,5 |
| skills_list | 97,7 | **45,0** | 100 | 79,1 | 100 | 99,6 | 88,5 | 99,5 |
| raw_description_text | **88,9** | 100 | 100 | 100 | 100 | 99,6 | 100 | 98,5 |
| raw_category_text | 92,0 | **0** | 100 | 97,8 | 100 | 96,2 | 100 | 99,5 |
| company_scale | 95,0 | 0 | 43,8 | 0 | 0 | 0 | 0 | 0 |

- C1. TopDev: flattener chỉ đọc `recalled_at`/`created_at` (rỗng) và bỏ qua `published.date`, `date_posted`, `job_posting_jsonld.experienceRequirements` (PRE-7).
- C2. TopCV: raw không có ngày đăng (chỉ có `deadline_raw`); cần xem trang có hiển thị không.
- C3. ITviec: flattener lấy `posted_at_raw` (tương đối) trong khi `job_posting_jsonld.datePosted` có ngày tuyệt đối.
- C4. Null trá hình: VietnamWorks `raw_education_text = "0"` ở 309 tin.
- **Luật chọn trường cho integration (chốt 03/11/2026):** trích xuất được thì lấy, không thì để null; chỉ giữ trường mà ít nhất 3–4/8 nguồn có (≥ 50% tin có giá trị). Kết quả: giữ 18 trường; bỏ 6 trường `company_scale`, `raw_age_text`, `raw_gender_text` (1 nguồn), `raw_updated_at`, `raw_working_time`, `raw_work_mode` (2 nguồn). Không có trường nào đúng 3 nguồn nên ngưỡng 3 hay 4 cho cùng kết quả. Ma trận đầy đủ trong HTML, mục C.

## D. Lương

| # | Vấn đề | Số liệu | Mức |
|---|---|---|---|
| D1 | Lương thỏa thuận (giữ NaN + cờ, MNAR) | ITviec 72,6%, VietnamWorks 71,0%, CareerViet 64,2%, TopDev 60,1%, TopCV 39,1%, JobsGO 32,8%, Vieclam24h 4,7%, Glints 0% | — (đặc điểm nguồn) |
| D2 | **Bộ parse đọc sai dấu phân cách hàng nghìn** | "Up to 2,000 USD" → 50.800 VND; "Up to 4.000 USD" → sai tương tự. 59 tin ra lương < 1 triệu (TopDev 29, TopCV 11, ITviec 5, Glints 5…); một phần là thực tập thật ("0.5 - 1 triệu") | Cao |
| D3 | **"Từ X" bị gán max = min** | 192 tin (TopDev 86, JobsGO 57, TopCV 49). "Từ 15 triệu" chỉ có mức sàn | Cao |
| D4 | Chỉ có một đầu ("Up to", "Tới") | TopCV 243, JobsGO 138, TopDev 17, CareerViet 15, ITviec 9 | TB |
| D5 | Lương USD (đổi theo tỉ giá cố định 25.400) | ITviec 24,7%, VietnamWorks 13,0% | TB |
| D6 | Lương theo năm, gross/net | Rất ít (Glints 2 theo năm, ITviec 2 gross) | Thấp |
| D7 | Lương nằm trong tiêu đề | JobsGO 212, TopCV 140, Vieclam24h 80, TopDev 76 | Thấp (nguồn bù khi trường lương thỏa thuận) |

## E. Địa điểm

- E1. ITviec `raw_location_text` là địa chỉ đường phố (418 giá trị khác nhau, ví dụ "Tòa nhà MB, số 18 Lê Văn Lương…"), cần tách thành phố.
- E2. Nhiều thành phố trong một chuỗi: ITviec 888, VietnamWorks 603, TopDev 185, TopCV 142.
- E3. `working_locations` rỗng: TopCV 11,7%, JobsGO 6,4%, ITviec 3,8%.
- E4. Tên không dấu chưa gộp ở bộ golden (PRE-3: "Ha Noi" 509, "Ho Chi Minh" 351).
- **Luật địa điểm (chốt 03/11/2026):** phạm vi Việt Nam, **34 tỉnh/thành sau sáp nhập**; tên tỉnh cũ đổi sang tên mới. Mỗi địa điểm lưu JSON 3 cấp `dia_chi_cu_the`, `phuong_xa`, `tinh_thanh` (`spec/P3_transformation.md` T8, `spec/P4_normalization.md` N1).

## F. Kinh nghiệm và cấp bậc

- F1. Kinh nghiệm nhiều dạng: "Không yêu cầu"/"Chưa có kinh nghiệm" (JobsGO 632, TopCV 348, Vieclam24h 226), khoảng "1 - 2 năm" (JobsGO 495, CareerViet 351, Glints 243), chữ "Dưới một năm kinh nghiệm".
- F2. Cấp bậc mỗi nguồn một bộ từ: VietnamWorks 4 giá trị ("Nhân viên", "Trưởng phòng", "Mới Tốt Nghiệp", "Giám Đốc và Cấp Cao Hơn"), TopCV 7 giá trị. ITviec, Glints, TopDev không có trường này.
- F3. Phân loại theo chuỗi con sai (PRE-1: "intern" trong "international").

## G. Kỹ năng

- G1. Trường kỹ năng chứa danh mục ngành, không phải kỹ năng: TopCV "IT - Phần mềm", "Marketing / Quảng cáo"; JobsGO "Lập Trình - Phát Triển Phần Mềm" (PRE-6); Vieclam24h "Việc làm TP.HCM" và tên công ty bị cắt ("Công Ty Cổ Phần Viễn ..."); CareerViet tag SEO là tên vị trí ("IT Engineer", "lập trình viên").
- G2. Tag dài hơn 4 từ (dấu hiệu là câu, không phải kỹ năng): TopCV 3.771, JobsGO 3.617, Vieclam24h 3.398.
- G3. Kỹ năng rỗng: TopDev 55,0%, CareerViet 20,9%, Glints 11,5%.

## H. Ngày tháng

- H1. ITviec ngày đăng dạng tương đối ở 855 tin (xem C3).
- H2. Glints 95 tin đăng hơn 90 ngày.
- H3. TopCV 486 tin có hạn nộp trước ngày cào (cần kiểm: tin hết hạn vẫn được cào, hay đọc sai định dạng `dd/mm/yyyy`).

## I. Văn bản, tiêu đề, công ty

- I1. JD rỗng: TopCV 11,1%; JD ngắn dưới 200 ký tự: JobsGO 90, TopDev 60, TopCV 49.
- I2. HTML hoặc entity còn sót: VietnamWorks 8 tin.
- I3. Tiêu đề có mã, ngoặc, số tin: khoảng 4.000 tin (TopCV 850, TopDev 839, ITviec 630); viết hoa toàn bộ: TopDev 235.
- I4. Cùng công ty khác cách viết: VietnamWorks 15 nhóm, TopCV 12 (ví dụ "CÔNG TY CỔ PHẦN CÔNG NGHỆ KIOTVIET" / "Công ty Cổ phần Công nghệ KiotViet").

## Liên hệ với việc đang mở

| Vấn đề ở đây | Mục trong `KNOWN_ISSUED.md` |
|---|---|
| C1 | PRE-7 |
| G1 (JobsGO, CareerViet) | PRE-6 |
| F3 | PRE-1 |
| E4 | PRE-3 |
| B2 | PRE-8 |
| A3 | SCRAPE-5 |
| A1, A2, C2, C3, D2, D3, E1, G1 (TopCV, Vieclam24h), H1–H3, I4 | Mới, chưa có mục |
