# Prompt P3: Transformation (lương, ngày, kinh nghiệm, chữ, địa điểm 3 cấp, dịch JD, kỹ năng và phúc lợi)

## 1. Ngữ cảnh

Đọc trước:
- `docs/preprocessing/spec/P3_transformation.md`: luật T1–T9, cột mới.
- `preprocessing/transformation/salary_parser.py`: `UniversalSalaryParser.parse_text`, `parse_salary_cascade`.
- `preprocessing/missing_outlier/sneaky_null_detector.py`. Không dùng `genai_text_imputer.py` nữa (bỏ Gemini, xem P0 mục 6).
- `docs/preprocessing/spec/P0_pipeline_contract.md` mục 6: gọi Gemini (API Google, khóa `GEMINI_API_KEY`) để dịch, cache, `--use-api`.
- `docs/preprocessing/spec/P4_normalization.md` mục N1: bảng 34 tỉnh (T8 dùng để nhận tên tỉnh).
- `preprocessing/transformation/html_cleaner.py`, `bullet_stitcher.py`, `text_metrics.py`.

Lỗi lương:
- "Up to 2,000 USD" ra 50.800 VND (D2, 59 tin dưới 1 triệu).
- "Từ X" bị gán max = min (D3, 192 tin).

## 2. Việc cần sửa

- **Input:** `data/preprocessing/02_integration/all.parquet` (đã gộp 8 nguồn).
- **Output:**
  - `data/preprocessing/03_transformation/all.parquet`: giữ cột cũ, thêm cột theo đặc tả mục 3. Báo cáo theo nguồn có được nhờ `groupby("source_platform")`.
  - Báo cáo bước.
  - Code: `preprocessing/transformation/run.py` (mới), sửa `salary_parser.py`, thêm `experience_parser.py` (mới) nếu chưa có hàm tương tự.

## 3. Pseudo code

```text
run(sources, dry_run, use_api):
    df = đọc all.parquet; với mỗi nhóm source_platform gọi process_source(rows) rồi nối lại
    T1: với mỗi cột raw_*: is_val_null(v) → null (cột mới, giữ cột raw_*)
    T2: for row: s = parse_salary_cascade(raw_salary_text, title, description)   # header → title → jd
        # title/JD chỉ nhận cụm có đơn vị tiền (triệu/tr/M/k/$/USD/VND), không lấy số trong mã tin, năm, "Microsoft 365"
        # mọi tầng: lương tháng ngoài 1–500 triệu → min=max=None, flag salary_suspect (T2f); số 0 là cận trống
    T3: posted_date, deadline_date = parse_date(...)  # ISO | dd/mm/yyyy; deadline < crawled_at → flag
    T4: exp_min, exp_max = parse_experience(raw_experience_text)
    T5: headcount = int(số đầu tiên) or null
    T6: job_title_clean, description_clean, requirements_clean
    T6: language = detect_jd_language(description_clean + requirements_clean, title, company)
        # chỉ xét JD; bỏ "Chi tiết công việc <title> tại <công ty>" của TopCV; chữ có dấu < 1% → "en", ngược lại "vi". Không có "bilingual"
    T6b: nếu language == "en" và đã có preprocessing/transformation/translate_model.json (người dùng chọn):
            description_vi = translate(description_clean, keep=DO_NOT_TRANSLATE); translated_by = model
         nếu language == "vi": description_vi = description_clean; translated_by = None
    sau vòng lặp: export_review_30_jd(JD en)   # 30 JD rải đều theo nguồn, dịch bằng 2 model
    T7a: skills_field = [t for t in skills_list if ≤ 4 từ and not là_danh_mục(t)]
    T7b: skills_jd = dict_match(SKILLS, description_clean + requirements_clean)   # bản gốc, khớp từ nguyên vẹn
         skills_clean = bỏ_trùng_không_phân_biệt_hoa(skills_field + skills_jd)
    T7c: benefits_std = dict_match(BENEFITS, benefits_list + description_clean)
    T8: locations = [split_location(x) for x in working_locations or [raw_location_text] or [company_address]]
    T9: không bù. Ô null giữ null.

split_location(text):
    parts = tách theo dấu phẩy, " - "
    tinh_thanh = phần cuối khớp tên hoặc bí danh trong provinces_34.json (cả tên cũ), không khớp → None
    trước khi tách: chỉ lấy dòng đầu; bỏ "(...)" (thông tin cũ); bỏ nhãn "Địa chỉ trụ sở:", "Hà Nội :"
    tinh_thanh = province.key(phần) từ cuối lên (khớp nguyên từ, chặn "Điện Biên Phủ", "Nguyễn Huệ")
    phuong_xa  = phần có tiền tố "Phường"/"P."/"Xã"/"Đặc khu" VÀ tên có trong wards_34.json của đúng tỉnh,
                 tên phường cũ đã sáp nhập (vd. "Phường Đội Cấn") → None
    dia_chi_cu_the = các phần trước tỉnh, bỏ hẳn "Quận/Huyện/Thị xã", bỏ "Việt Nam"; rỗng → None
    return {dia_chi_cu_the, phuong_xa, tinh_thanh, raw: text}

DO_NOT_TRANSLATE = tên chuẩn + cách viết trong skills.json  ∪  {Backend, Frontend, Fullstack, DevOps, QA, QC, BA,
                   Intern, Fresher, Junior, Middle, Senior, Lead, Manager, Scrum, Agile, ...}
translate(text, keep):
    chia text theo dòng thành đoạn ≤ 3.000 ký tự (không cắt bỏ phần nào); dịch từng đoạn rồi nối
    với mỗi đoạn: h = sha256(model + prompt_version + đoạn); có cache thì trả cache
    if dry_run: đếm token (≈ 4 ký tự/token) và ước tính tiền theo giá model (ra ≈ 1,5× vào), return None
    nếu tiền lần này ≥ trần hoặc sổ spend_google.json ≥ 0,95 USD: dừng gọi
    POST generativelanguage.googleapis.com/v1beta/models/<model>:generateContent, header x-goog-api-key,
      systemInstruction:
      "Dịch sang tiếng Việt tự nhiên, chính xác cho ngành IT tuyển dụng. BẮT BUỘC giữ nguyên từng thuật ngữ kỹ thuật,
       tên công nghệ, chức danh trong danh sách sau: [KEEP có trong đoạn, tối đa 40]. Giữ nguyên định dạng gạch đầu dòng
       và số liệu. Chỉ trả về duy nhất bản dịch tiếng Việt."
      bỏ phần "thought" trong câu trả lời; tiền = promptTokenCount × giá vào + (candidates + thoughts) × giá ra
      429 (gói miễn phí hết lượt/phút): chờ rồi thử lại; lần chạy sau đọc cache, chỉ dịch phần còn thiếu
    kiểm sau dịch: mọi từ trong KEEP có trong gốc thì phải có trong bản dịch, thiếu thì gắn flag translate_lost_term

UniversalSalaryParser (sửa):
    số "2,000" | "2.000" (dấu + đúng 3 chữ số) → 2000;  "8.5" → 8.5          # T2a
    "từ X" (không có "-"/"đến") → min=X, max=None                           # T2b
    "up to X" | "tới X" | "đến X" (không có cận dưới) → min=None, max=X        # T2c
    USD × 25_400; "/năm" | "per year" → /12                                   # T2d
    < 1_000_000 sau quy đổi → flag salary_under_1m                            # T2f
```

## 4. Ràng buộc

- Không bỏ dòng, không cap, không log, không ánh xạ về từ điển chuẩn.
- Không ghi đè cột `raw_*`.
- Lương thỏa thuận: NaN + `is_negotiable=true`, không bù.
- Không bù giá trị. Không có khóa hoặc không có `--use-api` thì không dịch: `description_vi = null`, `translated_by = null`, báo cáo ghi lý do.
- Rút kỹ năng/phúc lợi từ **bản gốc**, không từ bản dịch.
- Hai model thi 30 JD: `gemini-3.8-flash` (A, mặc định, có gói miễn phí) và `gemini-4-argon` (B, chỉ trả phí). Chưa có `translate_model.json` thì không dịch toàn bộ. Trần 0,95 USD đọc từ `data/preprocessing/_cache/spend_google.json`.
- Từ điển `skills.json`, `benefits.json`, `provinces_34.json` là dữ liệu JSON, không viết cứng trong code.
- Test của `salary_parser` đang khẳng định hành vi sai (vd. "Từ X" → max = min) thì sửa test, ghi lý do trong commit sau này.

## 5. Ví dụ (thành test)

| `raw_salary_text` | min | max | khác |
|---|---|---|---|
| "Up to 2,000 USD" | None | 50.800.000 | |
| "Từ 15 triệu" | 15.000.000 | None | |
| "10 - 15 triệu" | 10.000.000 | 15.000.000 | |
| "8.5 - 12 triệu" | 8.500.000 | 12.000.000 | |
| "Thỏa thuận", title "Java Dev (15-20tr)" | 15.000.000 | 20.000.000 | `salary_source="title"` |
| "0.5 - 1 triệu" | None | None | flag `salary_suspect` (dưới 1 triệu/tháng) |
| "Up to 40.000.000 VND" | None | 40.000.000 | |
| "From 9.000.000 VND" | 9.000.000 | None | "m" trong "from" không phải đơn vị triệu |
| "Thỏa thuận", title "Chuyên viên dữ liệu (2026TD450981)" | None | None | `salary_source="none"` |
| "Thỏa thuận", title "BA (2+ Năm Kinh Nghiệm) - Upto 35 Triệu" | None | 35.000.000 | không chia 12 vì chữ "Năm" |

| `raw_experience_text` | exp_min | exp_max |
|---|---|---|
| "Không yêu cầu kinh nghiệm" | 0 | 0 |
| "1 - 2 năm" | 1 | 2 |
| "Trên 3 năm" | 3 | None |
| "Dưới 1 năm" | 0 | 1 |

`skills_list=["Java","Việc làm TP.HCM","java","Có kinh nghiệm làm việc nhóm tốt"]` → `["Java"]`.

| Đầu vào | Kết quả |
|---|---|
| JD "Thành thạo ReactJS, có kiến thức về SQL" | `skills_clean` có `React`, `SQL` |
| benefits "Đăng Ký Hưởng Bảo hiểm (insurance)", "13th month salary" | `benefits_std=["Bảo hiểm","Lương tháng 13"]` |
| "Tòa nhà MB, 18 Lê Văn Lương, P. Thanh Xuân, Hà Nội" | `{"dia_chi_cu_the":"Tòa nhà MB, 18 Lê Văn Lương","phuong_xa":"Phường Thanh Xuân","tinh_thanh":"TP. Hà Nội"}` |
| "Quận 1, Hồ Chí Minh" | `{"dia_chi_cu_the":null,"phuong_xa":null,"tinh_thanh":"TP. Hồ Chí Minh"}` |
| "Hà Nội : Số 181 Nghi Tàm, Phường Tây Hồ (Quận Tây Hồ, Hà Nội cũ)" | `{"dia_chi_cu_the":"Số 181 Nghi Tàm","phuong_xa":"Phường Tây Hồ","tinh_thanh":"TP. Hà Nội"}` |
| "72 Điện Biên Phủ, Ba Đình, Hà Nội" | `tinh_thanh="TP. Hà Nội"` |
| JD "Nhân viên kinh doanh tại tòa nhà C" | không có kỹ năng `C`; "C/C++" mới có |
| "Remote" | `{"dia_chi_cu_the":null,"phuong_xa":null,"tinh_thanh":null,"raw":"Remote"}` (P4 gắn cờ) |
| JD tiếng Anh "Experience with Python and Docker is a plus" (LLM mock) | bản dịch vẫn có "Python", "Docker"; mock bỏ mất "Docker" → flag `translate_lost_term` |
| JD tiếng Việt | `translated_by=None`, không gọi API |

## 6. Cách review

- Trước → sau: xuất 20 dòng ngẫu nhiên (seed 42) gồm `raw_salary_text`, `salary_min/max_vnd`, `salary_source`. Bạn đánh dấu sai.
- Số tin < 1 triệu: xem từng tin còn lại, phải đều là thực tập hoặc lương giờ thật.
- 192 tin "Từ X": đều có `salary_max_vnd = None`.
- Kinh nghiệm: tỉ lệ parse được ≥ 90%. Xem 20 giá trị chữ không parse được.
- **Chấm bản dịch:** `--use-api` dịch 30 JD tiếng Anh (rải đều theo nguồn, seed 42) bằng 2 model, xuất `data/preprocessing/review/translate_30.csv` (`ban_goc`, `ban_dich_a`, `ban_dich_b`, `diem_a`, `diem_b` 1–5). Bạn chấm, rồi ghi `{"model": "..."}` vào `preprocessing/transformation/translate_model.json`; lần chạy sau mới dịch hết. File đã có điểm thì không bị ghi đè.
- Địa điểm: 30 dòng ngẫu nhiên, so `raw` với 3 cấp đã tách.
- H3: kiểm 10 tin TopCV có hạn nộp trước ngày cào trên trang web, ghi kết luận vào báo cáo (`checks.notes`).
