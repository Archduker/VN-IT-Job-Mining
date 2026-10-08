# 📋 Bản Giao Việc Chi Tiết — Phúc (Nguồn Việc Làm 24h)

> **Dự án**: VN-IT-Job-Mining — Hệ thống Thu thập & Khai phá Dữ liệu Tuyển dụng IT Việt Nam  
> **Người thực hiện**: Phúc  
> **Vai trò**: Crawler Developer — Nguồn Việc Làm 24h ([`https://vieclam24h.vn`](https://vieclam24h.vn))  
> **Ngày giao việc**: 2026-10-08  
> **Tài liệu gốc tham chiếu**: [`docs/crawler_api_analysis.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawler_api_analysis.md#L501-L550) | [`TASKS.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/TASKS.md)

---

## 🎯 1. Mục Tiêu & Công Việc Cần Làm

Bạn chịu trách nhiệm kiểm tra, hoàn thiện và fix các vấn đề bóc tách trong crawler **Việc Làm 24h** ([`crawlers/sources/vieclam24h/crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/vieclam24h/crawler.py)):

1. **Xử lý dọn sạch thẻ HTML & Chuẩn hóa định dạng ngắt dòng `AA,\nBB`**:
   - Trong dữ liệu bóc tách từ Next.js SSR (`job_requirement_html`, `job_description_html`), trường `description_text` và `requirements_text` hiện tại vẫn còn sót các thẻ `<p>`, `<span>`, `<div>`.
   - Cần xử lý triệt để: dọn sạch 100% thẻ HTML.
   - Các đoạn văn bản có dạng `AA,\nBB` hoặc nối câu bằng dấu phẩy và xuống dòng phải được format tách dòng ngay ngắn:
     ```text
     AA,
     BB
     ```
2. **Tính toán Ngày đăng tin bài từ thời hạn còn lại (Deadline / "14 days left")**:
   - Trên Việc Làm 24h, trường `created_at` trong một số trường hợp bị rỗng hoặc không có sẵn, nhưng có trường `expire_date` hoặc chuỗi text *"Còn 14 ngày để ứng tuyển"*.
   - **Quy tắc tính toán**: Một tin tuyển dụng thông thường trên Việc Làm 24h có hạn tồn tại trong **30 ngày**.
     * Nếu có `expire_date`: `posted_date = expire_date - timedelta(days=30)`.
     * Nếu có số ngày còn lại (ví dụ *"14 days left"*): `posted_date = ngày_cào - timedelta(days=(30 - 14))`.
     * Lưu kết quả theo định dạng ngày ISO `YYYY-MM-DD` vào `raw.posted_date_text`.
3. **Bóc tách trường Lương số học (`salary_min`, `salary_max`, `salary_currency`)**:
   - Việc Làm 24h có sẵn trường `salary_min` và `salary_max` (dưới dạng triệu VNĐ hoặc VNĐ nguyên bản).
   - Hãy chuẩn hóa:
     * `salary_min`: số thực float (ví dụ: `15.0` nếu là 15 triệu VNĐ).
     * `salary_max`: số thực float (ví dụ: `25.0` nếu là 25 triệu VNĐ).
     * `salary_currency`: Luôn là `"VND"`.
     * `salary_text`: Format chuỗi hiển thị: `"15 - 25 triệu VND"` (hoặc `"Thương lượng"` nếu min/max rỗng).
4. **Nhận diện Ngôn ngữ (`language`)**:
   - Hầu hết tin trên Việc Làm 24h là tiếng Việt. Hãy kiểm tra qua `detect_language()` để gán `_meta.language = "vi"` (hoặc `"en"` nếu bài đăng viết bằng tiếng Anh).
5. **Đổi định dạng đầu ra sang `.json`**:
   - Đảm bảo crawler ghi ra file mảng JSON: `data/vieclam24h/dt=YYYY-MM-DD/batch_001.json`.

---

## 📂 2. File Sẽ Làm Việc

* **File crawler chính**: [`crawlers/sources/vieclam24h/crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/vieclam24h/crawler.py)
* **File test liên quan**: [`tests/unit/test_crawlers.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/tests/unit/test_crawlers.py) (Hàm `test_vieclam24h_crawler_parse_item`)
* **Tài liệu phân tích API tham khảo**: [`docs/crawler_api_analysis.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawler_api_analysis.md#L501-L550) (Mục 3.5: Việc Làm 24h Next.js SSR).

---

## ⚙️ 3. Quy Trình Kỹ Thuật Bắt Buộc

Quy trình phát triển chuẩn bắt buộc bạn phải tuân thủ:

```text
[BƯỚC 1] KÉO FILE HTML / NEXT.JS STATE TỪ VIỆC LÀM 24H
   │     Chạy test 1 tin để lấy raw payload __NEXT_DATA__.
   ▼
[BƯỚC 2] ĐỌC RA CÁC THÀNH PHẦN ĐƯỢC TRÍCH XUẤT
   │     Kiểm tra các trường: salary_min, salary_max, expire_date, job_requirement_html.
   ▼
[BƯỚC 3] SỬA CODE PARSER TRONG parse_item()
   │     - Viết hàm làm sạch thẻ HTML, tách dòng chuẩn AA,\nBB.
   │     - Viết logic tính ngày đăng từ (30 - days_left).
   │     - Gán salary_min, salary_max, salary_currency và language.
   ▼
[BƯỚC 4] CHUẨN HÓA DỮ LIỆU
   │     Đóng gói vào JobRecord đúng quy định schema.
   ▼
[BƯỚC 5] NẾU CÓ LỖI (Còn sót tag <p>, ngày tính sai, lương null sai)
   │     So sánh với HTML trang gốc, điều chỉnh regex/logic.
   ▼
[BƯỚC 6] FIX & TỐI ƯU
   │     Khắc phục dứt điểm mọi lỗi phát sinh.
   ▼
[BƯỚC 7] RA ĐƯỢC BỘ JSON CHUẨN MẢNG
         File batch_001.json mở được bằng json.load() mượt mà.
```

---

## 📤 4. Output Kỳ Vọng & Tiêu Chuẩn Nghiệm Thu

1. **Lệnh chạy kiểm tra**:
   ```bash
   .venv/bin/python run.py --source vieclam24h --max-items 3 -v
   ```
2. **File đầu ra sinh ra**:
   `data/vieclam24h/dt=YYYY-MM-DD/batch_001.json`
3. **Mẫu bản ghi nghiệm thu chuẩn**:
   ```json
   {
     "_meta": {
       "source": "vieclam24h",
       "source_job_id": "2009876",
       "url": "https://vieclam24h.vn/cntt/lap-trinh-vien-php-id2009876.html",
       "dedup_key": "vieclam24h:2009876",
       "crawled_at": "2026-10-08T22:10:00Z",
       "batch_id": "2026-10-08_vieclam24h_001",
       "crawler_version": "0.3.0",
       "language": "vi"
     },
     "raw": {
       "title": "Lập Trình Viên PHP / Laravel (Junior/Middle)",
       "company": "Công Ty Cổ Phần Công Nghệ ABC",
       "description_html": "<p>Tham gia phát triển hệ thống ERP...</p>",
       "description_text": "Tham gia phát triển và bảo trì hệ thống ERP doanh nghiệp.\nTối ưu hóa cơ sở dữ liệu MySQL và xây dựng RESTful API.",
       "requirements_text": "Có từ 1 - 2 năm kinh nghiệm làm việc với PHP và Laravel,\nThành thạo MySQL,\nHiểu biết về Git và Docker là một lợi thế.",
       "salary_text": "12 - 20 triệu VND",
       "salary_min": 12.0,
       "salary_max": 20.0,
       "salary_currency": "VND",
       "location_text": "Hồ Chí Minh",
       "posted_date_text": "2026-09-24",
       "deadline_text": "2026-10-24"
     }
   }
   ```
4. **Kiểm tra chất lượng**: Tuyệt đối không còn thẻ `<p>`, `<br>` nào trong `description_text` và `requirements_text`.

---

## 🌿 5. Hướng Dẫn Git Workflow (Kéo Code, Tạo Nhánh & Push)

> [!CAUTION]
> **QUY TẮC BẮT BUỘC TRƯỚC KHI BẮT ĐẦU**:
> 1. Luôn chuyển về `main` và kéo code mới nhất từ remote: `git checkout main && git pull origin main`.
> 2. **BẮT BUỘC TẠO NHÁNH RIÊNG** cho nhiệm vụ của mình: `git checkout -b feature/vieclam24h-clean-html-date-salary`.  
>    🚫 **TUYỆT ĐỐI KHÔNG** commit hoặc viết code trực tiếp trên nhánh `main`!
> 3. Sau khi hoàn thành và test pass, push nhánh lên GitHub và tạo Pull Request để Team Leader (@billtran) review và merge.

```bash
# 1. Kéo code mới nhất từ nhánh main
git checkout main
git pull origin main

# 2. Bắt buộc tạo nhánh riêng cho mình từ main
git checkout -b feature/vieclam24h-clean-html-date-salary

# 3. Chỉnh sửa code trong crawlers/sources/vieclam24h/crawler.py
pytest tests/unit/test_crawlers.py -k vieclam24h
.venv/bin/python run.py --source vieclam24h --max-items 3

# 4. Kiểm tra diff và add code
git status
git add crawlers/sources/vieclam24h/crawler.py
git commit -m "feat(vieclam24h): clean html tags, calculate posted_date from deadline and parse numeric salary"

# 5. Đẩy nhánh lên GitHub
git push -u origin feature/vieclam24h-clean-html-date-salary

# 6. Tạo Pull Request trên GitHub vào main
```
