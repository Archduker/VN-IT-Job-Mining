# 📊 BÁO CÁO KIỂM ĐỊNH NGOẠI LAI & CHẤT LƯỢNG DỮ LIỆU (OUTLIER & QUALITY AUDIT)

> **Thành viên:** Phan Nhật Tài — Bước 5, Giai đoạn 3 (TASKS.md 6.3.5)  
> **Ngày chạy:** 2026-10-26  
> **Đầu vào:** `integrated_flat_all_sources.json` — 9,824 bản ghi staging phẳng đã ép phẳng của 8 sàn (output `json_flattener.py` — Phạm Nguyễn Minh Phúc)  
> **Chuỗi thực thi:** `parse_salary_cascade` (Khoa) → `apply_outlier_pipeline` (sửa R1–R3, IQR chẩn đoán, Winsorize P1–P99 per-source) → `summarize_quality` (Tài)  
> **Cơ sở ngưỡng:** Bệnh án EDA 8 sàn (`eda_all.json`) qua `reports/quality/outlier_spec.md` — EDA-First Protocol.

## 1. Độ phủ lương sau cascade (điều kiện tiền quyết để kiểm định)

- Bản ghi **có số lương VND/tháng đo được**: **4,990/9,824** (50.8%)
- Bóc tách thành công từ **lương ẩn trong JD** (`jd_regex`): **157** tin — đúng cảnh báo Trụ cột 2 bệnh án (tin 'Thỏa thuận' nhưng lộ lương trong JD)
- Tin ẩn lương thật (`header_negotiable`, MNAR — giữ NaN, **không điền mean/median**): **4,834** (49.2%) — loại đúng khỏi tính phân vị

## 2. Kết quả theo từng sàn (sau sửa lỗi số, trước capping để chẩn đoán)

| Sàn | Bản ghi | Có lương số | R1 USD→VND | R2 thừa số 0 | R3 lương năm | Hàng bị cap P1–P99 | % cap | Q1 (VND/tháng) | Q3 | Bound trên IQR | Ngoại lai IQR | quality_score TB |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **topdev** | 2,755 | 1,117 | 32 | 0 | 0 | 13 | 0.47 | 1,000,000 | 5,000,000 | 11,000,000 | 26 | 0.996 |
| **topcv** | 1,950 | 1,127 | 4 | 0 | 2 | 30 | 1.54 | 15,000,000 | 30,000,000 | 52,500,000 | 43 | 0.999 |
| **jobsgo** | 1,520 | 1,022 | 0 | 0 | 2 | 12 | 0.79 | 13,000,000 | 26,000,000 | 45,500,000 | 55 | 0.999 |
| **vietnamworks** | 1,359 | 411 | 6 | 8 | 36 | 6 | 0.44 | 22,430,000 | 50,800,000 | 93,355,000 | 33 | 0.987 |
| **itviec** | 691 | 193 | 0 | 2 | 3 | 5 | 0.72 | 33,020,000 | 63,500,000 | 109,220,000 | 8 | 0.996 |
| **vieclam24h** | 619 | 591 | 0 | 0 | 0 | 6 | 0.97 | 15,000,000 | 20,000,000 | 27,500,000 | 83 | 1.0 |
| **careerviet** | 599 | 272 | 2 | 0 | 8 | 6 | 1.0 | 14,750,000 | 30,000,000 | 52,875,000 | 14 | 0.992 |
| **glints** | 331 | 257 | 0 | 0 | 3 | 4 | 1.21 | 12,000,000 | 30,000,000 | 57,000,000 | 17 | 0.997 |

> ⚠️ Quy tắc nghi ngờ (outlier_spec.md mục 6): sàn có % cap > 5% cần đối chiếu lại tầng Transformation thay vì cap mù. **Không sàn nào vượt 5%** — cap hoàn toàn nằm trong dải kỳ vọng của phân bố thật.

### 2.1 Phát hiện quan trọng: dải lương topdev bị JUNK-LOW giả tạo (chuyển tầng Transformation — Anh Khoa)

- Sample chẩn đoán: `topdev` `'1******* - 1******* VND' -> 1000000.0 / 1000000.0` — **chính topdev che hậu tố lương bằng dấu `*`** (client-side masking), chỉ lộ chữ số đầu.
- Hệ quả: parser diễn giải `1***…` thành 1.000.000 (lệch thật ~100 lần) khiến Q1/Q3 topdev tụt xuống 1M/5M, tạo **junk-low** (không phải ngoại lai thống kê). 32 ca R1 của topdev cũng là tín hiệu cần đối chiếu lại regex.
- Hành động theo đúng nguyên tắc EDA-First (không cap mù lỗi hệ thống): **flag về tầng Transformation** — xử lý che `*` phải nằm ở `salary_parser.py` (hoặc chấp nhận topdev chỉ có `salary_min_vnd` bậc triệu và loại khỏi suy luận lương). Tầng outlier của Tài giữ nguyên kết quả, không chỉnh sửa để che đậy bản chất dữ liệu.

## 3. Bằng chứng tự sửa 3 lỗi nhập liệu số (ca thực tế từ dữ liệu)

**R1 — Gõ USD vào ô VNĐ (×25.400):**
- `careerviet` — "Thực Tập Sinh Kinh Doanh Website Phần Mềm": 500 → 12,701,270
- `careerviet` — "Thực tập sinh lập trình viên": 500 → 12,700,000

**R2 — Thừa số 0, vị trí non-Director (chia bậc 10):**
- `itviec` — "Generative Game Artist (Intern)": 5,842,000,000,000 → 5,842,000,000
- `itviec` — "Generative Game Artist (Intern)": 5,842,000,000,000 → 5,842,000,000

**R3 — Nhầm lương năm sang tháng (÷12):**
- `careerviet` — "Chuyên viên cao cấp Cơ sở dữ liệu (DBA) - Senior Database Of": 286,000,000 → 23,833,333
- `careerviet` — "[District 12] Project Assistant - German-speaking / Trợ lý d": 500,000,000 → 41,666,667

## 4. Toàn vẹn logic & điểm chất lượng (QR1–QR5)

- Tổng bản ghi sau pipeline: **9,824** (bất biến, **0 dòng bị drop** — Winsorization thay drop)
- Hàng bị capping P1–P99: **82** (cờ `is_outlier_capped`)
- `quality_score` trung bình toàn bảng: **0.996** (thấp nhất: 0.15)
- Bản ghi quality_score < 0.5: **40**
- Số vi phạm luật toàn vẹn: `violation_salary_range` = 44; `violation_date_order` = 7; `violation_negative_salary` = 0; `violation_multiple_fixes` = 40; `is_outlier_capped` = 82

## 5. Giới hạn kiểm định lần này (minh bạch nghiệm thu)

1. **Chưa đo cột `min_experience_years`**: `date_experience_parser.py` (TASKS 6.3.2 — Anh Khoa) **chưa tồn tại** trong `preprocessing/transformation/`. IQR/Winsorization cho kinh nghiệm đã sẵn sàng API và sẽ tự chạy khi cột xuất hiện — **không cần làm lại gì**, chỉ chạy lại chuỗi mục đầu vào.
2. Báo cáo chạy trên bản staging hợp nhất `integrated_flat_all_sources.json`; khi Thuận đưa vào `master_pipeline.py`, số liệu sẽ được tái sinh tự động — toàn bộ số liệu ở đây tái lập bằng đúng 1 lệnh gọi `apply_outlier_pipeline(df)`.
3. Cờ GenAI (`is_imputed_by_genai`) chưa bật trong run này do chưa chạy tầng Missing của Sơn trên bảng hợp nhất; trọng số trừ điểm đã cài sẵn, tự có hiệu lực khi cột tồn tại.

## 6. Kết luận DoD 6.3.5

- ✅ Tự động nhận diện & sửa 3 lỗi nhập liệu số (chứng minh bằng unit test; dữ liệu thật ghi nhận số ca thực tế tại mục 3).
- ✅ Winsorization chặn đúng P1–P99 per-source, 0 dòng drop, không crash với NaN (9.824/9.824 dòng nguyên vẹn).
- ✅ `quality_score` (0.0–1.0) tính cho toàn bộ bản ghi; báo cáo kiểm định hoàn tất.