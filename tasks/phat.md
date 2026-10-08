# 📋 Bản Giao Việc Chi Tiết — Phát (Nguồn ITviec)

> **Dự án**: VN-IT-Job-Mining — Hệ thống Thu thập & Khai phá Dữ liệu Tuyển dụng IT Việt Nam  
> **Người thực hiện**: Phát  
> **Vai trò**: Crawler Developer — Nguồn ITviec ([`https://itviec.com`](https://itviec.com))  
> **Ngày giao việc**: 2026-10-08  
> **Tài liệu gốc tham chiếu**: [`docs/crawler_api_analysis.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawler_api_analysis.md#L351-L440) | [`TASKS.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/TASKS.md)

---

## 🎯 1. Mục Tiêu & Công Việc Cần Làm

Crawler **ITviec** hiện tại đang chạy tốt việc bóc tách JSON-LD và HTML section, tuy nhiên đang có 5 vấn đề kỹ thuật lớn cần bạn can thiệp và hoàn thiện:

1. **Đổi định dạng đầu ra sang `.json` (thay vì `.jsonl`)**:
   - Hiện tại file [`crawlers/sources/itviec/crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/itviec/crawler.py) đang tự định nghĩa hàm `open_jsonl()` và `write_record()`.
   - Bạn cần refactor để ghi ra file **`.json` chuẩn dạng mảng đối tượng** (`data/itviec/dt=YYYY-MM-DD/batch_001.json`), sử dụng bộ `JsonWriter` chung từ `crawlers.common.json_writer` hoặc ghi danh sách `[ {...}, {...} ]`.
2. **Dọn dẹp triệt để thẻ HTML trong các trường văn bản**:
   - Trong `raw.requirements_text`, `raw.benefits_text`, `raw.description_text` vẫn còn lẫn các thẻ `<p>`, `<strong>`, `<ul>`, `<li>`.
   - Cần bóc tách sạch sẽ các khối thẻ HTML, chuẩn hóa ngắt dòng: Các đoạn văn liệt kê dạng `AA,\nBB` phải được xuống dòng rõ ràng:
     ```text
     AA,
     BB
     ```
3. **Bóc tách trường Lương số học (`salary_min`, `salary_max`, `salary_currency`)**:
   - ITviec có một số bài ghi lương cụ thể dạng USD (ví dụ: *"1,500 - 2,500 USD"* hoặc trong thẻ JSON-LD `baseSalary`).
   - Hãy viết hàm regex bóc tách:
     * `salary_min`: số thực float (vd: `1500.0`)
     * `salary_max`: số thực float (vd: `2500.0`)
     * `salary_currency`: `"USD"` hoặc `"VND"`
   - Với các tin có `salary_text` là *"Đăng nhập để xem mức lương"* hoặc *"You'll love it"*, gán `salary_min = None`, `salary_max = None`.
4. **Xử lý ngày đăng tin (`posted_date_text`)**:
   - Nếu `datePosted` trong JSON-LD bị thiếu hoặc rỗng, hãy suy luận từ `validThrough` (hạn nộp). Nếu hiển thị dạng "còn 14 ngày" (`14 days left`), hãy tính: `ngày đăng = ngày cào - (30 - số ngày còn lại)`.
5. **Thêm Metadata Ngôn ngữ (`language`)**:
   - ITviec có khoảng 80% tin bằng tiếng Anh và 20% bằng tiếng Việt.
   - Sử dụng helper `detect_language()` để gán `_meta.language = "en"` hoặc `"vi"`.

---

## 📂 2. Danh Sách File Cần Làm Việc

* **Crawler điều phối**: [`crawlers/sources/itviec/crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/itviec/crawler.py)
* **Bộ bóc tách HTML/JSON-LD**: [`crawlers/sources/itviec/parser.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/itviec/parser.py)
* **Cấu hình**: [`crawlers/sources/itviec/config.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/itviec/config.py)
* **Bộ test**: [`crawlers/sources/itviec/tests/test_parser.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/itviec/tests/test_parser.py)

---

## ⚙️ 3. Quy Trình Kỹ Thuật Bắt Buộc

Chu trình làm việc chuẩn bắt buộc:

```text
[BƯỚC 1] KÉO FILE HTML & LẤY DỮ LIỆU THỰC TẾ
   │     Chạy crawler với 1 job để dump HTML hoặc lấy file test sample trong tests/fixtures.
   ▼
[BƯỚC 2] ĐỌC RA CÁC THÀNH PHẦN ĐƯỢC TRÍCH XUẤT
   │     Kiểm tra kỹ JSON-LD baseSalary, section requirements_html, benefits_html.
   ▼
[BƯỚC 3] SỬA CODE TRONG parser.py & crawler.py
   │     Làm sạch triệt để thẻ HTML, định dạng tách dòng AA,\nBB, bóc tách min/max lương.
   ▼
[BƯỚC 4] CHUẨN HÓA DỮ LIỆU
   │     Gán language: "vi"|"en", lưu vào JobRecord và đổi sang JsonWriter (.json).
   ▼
[BƯỚC 5] NẾU CÓ LỖI (Vẫn còn tag <p>, text bị dính, file jsonl chưa thành json)
   │     Đọc lại cấu trúc HTML gốc, debug regex và parser.
   ▼
[BƯỚC 6] FIX & TỐI ƯU
   │     Khắc phục lỗi và chạy lại test suite.
   ▼
[BƯỚC 7] RA ĐƯỢC BỘ JSON CHUẨN
         Tạo file batch_001.json là một mảng JSON hoàn chỉnh.
```

---

## 📤 4. Output Kỳ Vọng & Tiêu Chuẩn Nghiệm Thu

1. **Lệnh chạy kiểm tra**:
   ```bash
   .venv/bin/python run.py --source itviec --max-items 3 -v
   ```
2. **File đầu ra sinh ra**:
   `data/itviec/dt=YYYY-MM-DD/batch_001.json` (phải là JSON array có dấu `[` ở đầu và `]` ở cuối).
3. **Mẫu bản ghi hợp lệ trong JSON**:
   ```json
   {
     "_meta": {
       "source": "itviec",
       "source_job_id": "business-analyst-officer-motorist-4823",
       "url": "https://itviec.com/viec-lam-it/business-analyst-officer-motorist-4823",
       "dedup_key": "itviec:business-analyst-officer-motorist-4823",
       "crawled_at": "2026-10-08T21:39:03+07:00",
       "batch_id": "2026-10-08_itviec_001",
       "crawler_version": "0.3.0",
       "language": "en"
     },
     "raw": {
       "title": "Business Analyst Officer",
       "company": "Motorist Pte Ltd",
       "description_html": "<p>The Business Analyst based in Vietnam...</p>",
       "description_text": "The Business Analyst based in Vietnam is responsible for gathering and documenting product requirements, analyzing and improving processes.\nWe are Singapore's leading car portal.",
       "requirements_text": "Years of Experience:\n2 - 5 years as a Business Analyst (BA) / Product Manager (PM)\nSkills / Technical Knowledge:\nUI/UX and User Flow Design,\nAgile development methodology",
       "salary_text": "Đăng nhập để xem mức lương",
       "salary_min": null,
       "salary_max": null,
       "salary_currency": "USD",
       "location_text": "Hồ Chí Minh, Thành phố Thủ Đức",
       "skills_text": "Business Intelligence, Product Owner, Business Analysis, UI-UX, Agile",
       "benefits_text": "Competitive salary and benefits package\nTravel opportunities to Singapore\nModern co-working space",
       "posted_date_text": "2026-10-08"
     }
   }
   ```
4. **Bộ test**: `pytest crawlers/sources/itviec/tests/` phải **PASSED 100%**.

---

## 🌿 5. Hướng Dẫn Git Workflow (Kéo Code, Tạo Nhánh & Push)

> [!CAUTION]
> **QUY TẮC BẮT BUỘC TRƯỚC KHI BẮT ĐẦU**:
> 1. Luôn chuyển về `main` và kéo code mới nhất từ remote: `git checkout main && git pull origin main`.
> 2. **BẮT BUỘC TẠO NHÁNH RIÊNG** cho nhiệm vụ của mình: `git checkout -b feature/itviec-json-clean-parser`.  
>    🚫 **TUYỆT ĐỐI KHÔNG** commit hoặc viết code trực tiếp trên nhánh `main`!
> 3. Sau khi hoàn thành và test pass 100%, push nhánh lên GitHub và tạo Pull Request để Team Leader (@billtran) review và merge.

```bash
# 1. Kéo code mới nhất từ nhánh main
git checkout main
git pull origin main

# 2. Bắt buộc tạo nhánh riêng cho mình từ main
git checkout -b feature/itviec-json-clean-parser

# 3. Chỉnh sửa code và chạy test
pytest crawlers/sources/itviec/tests/
.venv/bin/python run.py --source itviec --max-items 3

# 4. Kiểm tra diff và add file
git status
git add crawlers/sources/itviec/
git commit -m "refactor(itviec): output standard json array, clean html formatting, and parse numeric salary"

# 5. Đẩy nhánh lên GitHub và mở Pull Request
git push -u origin feature/itviec-json-clean-parser
```
