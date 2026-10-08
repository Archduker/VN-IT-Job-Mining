# 📋 Bản Giao Việc Chi Tiết — Sơn (Nguồn TopDev)

> **Dự án**: VN-IT-Job-Mining — Hệ thống Thu thập & Khai phá Dữ liệu Tuyển dụng IT Việt Nam  
> **Người thực hiện**: Sơn  
> **Vai trò**: Crawler Developer — Nguồn TopDev ([`https://topdev.vn`](https://topdev.vn))  
> **Ngày giao việc**: 2026-10-08  
> **Tài liệu gốc tham chiếu**: [`docs/crawler_api_analysis.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawler_api_analysis.md#L203-L270) | [`TASKS.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/TASKS.md)

---

## 🎯 1. Mục Tiêu & Công Việc Cần Làm

Bạn chịu trách nhiệm kiểm tra, sửa đổi và nâng cấp crawler nguồn **TopDev** ([`crawlers/sources/topdev/crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topdev/crawler.py)) nhằm giải quyết triệt để 5 vấn đề tồn đọng:

1. **Làm sạch thẻ HTML triệt để**:
   - Trong `raw.description_text`, `raw.requirements_text`, `raw.benefits_text` hiện nay vẫn còn sót một số thẻ HTML như `<p>`, `<span>`, `<strong>`, `<ul>`, `<li>`. Cần dùng hàm `strip_html_tags()` dọn sạch 100%.
2. **Chuẩn hóa ngắt dòng `AA,\nBB`**:
   - Khi API trả về các danh sách dạng `AA,\nBB` hoặc các câu nối nhau bằng dấu phẩy và xuống dòng, cần tách định dạng rõ ràng thành:
     ```text
     AA,
     BB
     ```
     Đảm bảo text hiển thị có cấu trúc, không bị dính cục hoặc ngắt dòng lộn xộn.
3. **Bóc tách chuẩn xác Mức Lương (`salary_min`, `salary_max`, `salary_currency`)**:
   - API của TopDev có sẵn object `salary: {"min": 1500, "max": 2500, "currency": "USD", "is_negotiable": "0"}`.
   - Trích xuất:
     * `salary_min`: Ép kiểu float (hoặc int), ví dụ `1500.0`. Nếu `min` là `"*"` hoặc thiếu thì gán `None`.
     * `salary_max`: Ép kiểu float (hoặc int), ví dụ `2500.0`. Nếu `max` là `"*"` hoặc thiếu thì gán `None`.
     * `salary_currency`: Lấy trực tiếp từ API (`"USD"` hoặc `"VND"`).
     * `salary_text`: Format chuỗi hiển thị đẹp mắt (ví dụ: `"1500 - 2500 USD"` hoặc `"Thương lượng"`).
4. **Nhận diện Ngôn ngữ bài đăng (`language`)**:
   - Kiểm tra nội dung tiêu đề và mô tả công việc bằng hàm `detect_language()` từ `crawlers.common.utils`.
   - Gán giá trị `"vi"` (nếu là bài đăng tiếng Việt) hoặc `"en"` (nếu là bài đăng tiếng Anh) vào trường `_meta.language`.
5. **Xuất file đầu ra là `.json`**:
   - Đảm bảo crawler ghi dữ liệu qua `BaseCrawler` ra file mảng JSON: `data/topdev/dt=YYYY-MM-DD/batch_001.json` (chứa `[ {...}, {...} ]`).

---

## 📂 2. File Sẽ Làm Việc

* **File chính**: [`crawlers/sources/topdev/crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topdev/crawler.py) (File duy nhất chứa toàn bộ logic cào và parse của TopDev).
* **Tài liệu phân tích API tham khảo**: [`docs/crawler_api_analysis.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawler_api_analysis.md#L203-L270) (Mục 3.1: TopDev REST API v2).
* **File test liên quan**: [`tests/unit/test_crawlers.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/tests/unit/test_crawlers.py) (Hàm `test_topdev_crawler_parse_item`).

---

## ⚙️ 3. Quy Trình Kỹ Thuật Bắt Buộc

Bạn bắt buộc phải tuân thủ nghiêm ngặt 7 bước sau trong quá trình thực hiện:

```text
[BƯỚC 1] LẤY MẪU RAW JSON TỪ API TOPDEV
   │     Chạy crawler với 1 item để quan sát cấu trúc gốc của trường content, salary, requirements.
   ▼
[BƯỚC 2] ĐỌC RA CÁC THÀNH PHẦN CẦN TRÍCH XUẤT
   │     Xác định vị trí các trường: salary.min, salary.max, requirements_arr, benefits_v2.
   ▼
[BƯỚC 3] SỬA CODE PARSER TRONG parse_item()
   │     Áp dụng làm sạch HTML, tách dòng AA,\nBB, bóc tách lương số học và detect language.
   ▼
[BƯỚC 4] CHUẨN HÓA DỮ LIỆU
   │     Ép dữ liệu vào JobRecord đúng quy định schema chung của nhóm.
   ▼
[BƯỚC 5] NẾU CÓ LỖI (Còn sót thẻ HTML, min/max ra sai kiểu dữ liệu)
   │     So sánh lại với RAW JSON ban đầu, viết thêm regex hoặc helper làm sạch.
   ▼
[BƯỚC 6] FIX & TỐI ƯU
   │     Khắc phục dứt điểm cho đến khi kết quả đầu ra sạch 100%.
   ▼
[BƯỚC 7] RA ĐƯỢC BỘ FILE JSON CHUẨN MẢNG
         File batch_001.json mở được bằng json.load() và thỏa mãn mọi tiêu chí.
```

---

## 📤 4. Output Kỳ Vọng & Tiêu Chuẩn Nghiệm Thu

1. **Lệnh chạy thử nghiệm kiểm tra**:
   ```bash
   .venv/bin/python run.py --source topdev --max-items 5 -v
   ```
2. **File kết quả sinh ra**:
   `data/topdev/dt=YYYY-MM-DD/batch_001.json`
3. **Mẫu bản ghi nghiệm thu chuẩn**:
   ```json
   {
     "_meta": {
       "source": "topdev",
       "source_job_id": "2134039",
       "url": "https://topdev.vn/detail-jobs/hanoi-senior-automation-ai-system-engineer-zeder-viet-nam-2134039",
       "dedup_key": "topdev:2134039",
       "crawled_at": "2026-10-08T14:38:36.830581Z",
       "batch_id": "2026-10-08_topdev_001",
       "crawler_version": "0.3.0",
       "language": "en"
     },
     "raw": {
       "title": "[Hanoi] Senior Automation & AI System Engineer",
       "company": "ZEDER VIỆT NAM",
       "description_html": "<p>Zeder Corporation is hiring...</p>",
       "description_text": "Zeder Corporation is hiring two Senior Automation & AI System Engineer into our Automation and AI team in Hanoi.\nThe work covers three areas:\nconventional automation and system integration,\nagentic automation,\nLLM assisted automation.",
       "salary_text": "Thương lượng",
       "salary_min": null,
       "salary_max": null,
       "salary_currency": "USD",
       "location_text": "Thành phố Hà Nội",
       "skills_text": "JavaScript, Python, REST API, Jira, DevOps, AI, CI/CD",
       "requirements_text": "5+ years experience in automation\nStrong hands-on Python/JS",
       "benefits_text": "13 Months of Salary\nFull Paid for Social Insurance, plus Bao Viet Healthcare\n14 Days of Annual Leave"
     }
   }
   ```
4. **Kiểm tra chất lượng**: Không còn bất kỳ thẻ `<p>`, `<span>` nào trong `description_text`, `requirements_text`, `benefits_text`.

---

## 🌿 5. Hướng Dẫn Git Workflow (Kéo Code, Tạo Nhánh & Push)

> [!CAUTION]
> **QUY TẮC BẮT BUỘC TRƯỚC KHI BẮT ĐẦU**:
> 1. Luôn chuyển về `main` và kéo code mới nhất từ remote: `git checkout main && git pull origin main`.
> 2. **BẮT BUỘC TẠO NHÁNH RIÊNG** cho nhiệm vụ của mình: `git checkout -b feature/topdev-crawler-json-clean`.  
>    🚫 **TUYỆT ĐỐI KHÔNG** commit hoặc viết code trực tiếp trên nhánh `main`!
> 3. Sau khi hoàn thành và test pass, push nhánh lên GitHub và tạo Pull Request để Team Leader (@billtran) review và merge.

```bash
# 1. Cập nhật nhánh main từ remote
git checkout main
git pull origin main

# 2. Bắt buộc tạo nhánh riêng cho mình từ main
git checkout -b feature/topdev-crawler-json-clean

# 3. Tiến hành chỉnh sửa file crawlers/sources/topdev/crawler.py
# Chạy kiểm thử:
pytest tests/unit/test_crawlers.py -k topdev
.venv/bin/python run.py --source topdev --max-items 3

# 4. Xem diff và add code
git status
git diff crawlers/sources/topdev/crawler.py
git add crawlers/sources/topdev/crawler.py

# 5. Commit với thông điệp rõ ràng
git commit -m "feat(topdev): clean html tags, parse numeric salary and detect language to json"

# 6. Đẩy nhánh lên GitHub
git push -u origin feature/topdev-crawler-json-clean

# 7. Truy cập GitHub tạo Pull Request vào nhánh 'main' và tag @billtran review
```
