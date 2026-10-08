# 📋 Bản Giao Việc Chi Tiết — Thuận (Team Leader & Data Platform)

> **Dự án**: VN-IT-Job-Mining — Hệ thống Thu thập & Khai phá Dữ liệu Tuyển dụng IT Việt Nam  
> **Người thực hiện**: Thuận (Bill Tran — Leader)  
> **Vai trò**: Quản phối Kiến trúc Pipeline, Chuẩn hóa Core/Base Modules & Crawler TopCV  
> **Ngày giao việc**: 2026-10-08  
> **Tài liệu gốc tham chiếu**: [`docs/crawler_api_analysis.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawler_api_analysis.md) | [`TASKS.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/TASKS.md)

---

## 🎯 1. Mục Tiêu & Tổng Quan Công Việc

Là Trưởng nhóm và Kỹ sư Nền tảng Dữ liệu (Lead / Data Platform Engineer), bạn chịu trách nhiệm 3 trọng trách then chốt:
1. **Nâng cấp Hệ thống Core (`crawlers/common` & `crawlers/base`)**:
   - Chuyển đổi toàn bộ cơ chế ghi file từ `.jsonl` sang định dạng **`.json` chuẩn (mảng JSON uncompressed UTF-8: `[ {...}, {...} ]`)**.
   - Bổ sung trường `language: "vi" | "en"` trong metadata (`JobMetadata`) để phân biệt bài đăng tiếng Việt hay tiếng Anh.
   - Chuẩn hóa các trường số học của mức lương (`salary_min`, `salary_max`, `salary_currency`) và hàm xử lý văn bản sạch (`strip_html_tags`, xử lý tách dòng `AA,\nBB` sạch đẹp).
2. **Refactor Crawler TopCV ([`crawlers/sources/topcv/crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/crawler.py))**:
   - Khắc phục triệt để các thẻ HTML còn sót trong card/description.
   - Bóc tách mức lương từ chuỗi text (ví dụ: *"15 - 35 triệu"* -> `min: 15.0, max: 35.0, currency: 'VND'`).
   - Tự động nhận diện ngôn ngữ `language: "vi"` hoặc `"en"`.
   - Xuất file kết quả dạng `batch_001.json`.
3. **Bộ Tích Hợp Dữ Liệu (Data Integration Tool)**:
   - Viết script `scripts/merge_datasets.py` để gộp các file `batch_*.json` từ tất cả 7 nguồn lại thành 1 file duy nhất `data/processed/combined_jobs.json` sẵn sàng bàn giao cho 2 bạn làm EDA (Tài và Khoa).

---

## 📂 2. Danh Sách File Cần Làm Việc

| Tên file / Module | Đường dẫn tuyệt đối | Nhiệm vụ cụ thể |
| :--- | :--- | :--- |
| **Schema Module** | [`crawlers/common/schema.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/common/schema.py) | Thêm `language` vào `JobMetadata`, thêm `salary_min`, `salary_max`, `salary_currency` vào `JobRaw`. |
| **Utils Module** | [`crawlers/common/utils.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/common/utils.py) | Nâng cấp `strip_html_tags` dọn sạch `<p>`, format ngắt dòng `AA,\nBB`, thêm helper `detect_language`. |
| **JSON Writer** | [`crawlers/common/json_writer.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/common/json_writer.py) | Tạo Writer ghi mảng `[ ... ]` chuẩn JSON với atomic write qua file `.tmp`. |
| **Base Crawler** | [`crawlers/base/base_crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/base/base_crawler.py) | Sử dụng `JsonWriter`, ghi file đuôi `.json`. |
| **Data Quality** | [`crawlers/common/data_quality.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/common/data_quality.py) | Hỗ trợ kiểm thử file `.json` (load mảng JSON). |
| **Runner Dispatcher** | [`run.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/run.py) | Tìm file kết quả `batch_*.json`, thêm hỗ trợ nguồn mới `glints`. |
| **TopCV Crawler** | [`crawlers/sources/topcv/crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/crawler.py) | Bóc tách Playwright, làm sạch text, trích xuất lương min/max, gán language tag. |
| **Merge Script** | [`scripts/merge_datasets.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/scripts/merge_datasets.py) | Script CLI gộp và validate toàn bộ các nguồn. |

---

## ⚙️ 3. Quy Trình Kỹ Thuật Bắt Buộc

Mọi crawler và thành viên trong nhóm phải tuân thủ nghiêm ngặt chu trình:
```text
KÉO FILE HTML / PHẢN HỒI API
  └─> ĐỌC RA CÁC THÀNH PHẦN ĐƯỢC TRÍCH XUẤT
       └─> SỬA CODE
            └─> CHUẨN HÓA DỮ LIỆU
                 └─> NẾU CÓ LỖI (Tag html còn sót, parse sai)
                      └─> ĐỌC LẠI HTML / JSON RAW
                           └─> FIX CODE
                                └─> RA ĐƯỢC BỘ JSON CHUẨN
```

### Chi tiết xử lý kỹ thuật:
1. **Xử lý Tag HTML & Dấu ngắt dòng `AA,\nBB`**:
   - Khi text gốc là:
     ```html
     <p>Yêu cầu:</p>AA,<br>BB
     ```
   - Phải xử lý triệt để loại bỏ toàn bộ thẻ `<p>`, `<span>`, `<br>`, và đưa các mục phân cách bằng dấu phẩy xuống dòng rõ ràng:
     ```text
     Yêu cầu:
     AA,
     BB
     ```
2. **Chuẩn hóa Mức lương**:
   - Trích xuất ra các trường:
     * `salary_min`: số thực (float, ví dụ `15.0`)
     * `salary_max`: số thực (float, ví dụ `35.0`)
     * `salary_currency`: `"VND"` hoặc `"USD"`
   - Nếu thỏa thuận: `salary_min = None`, `salary_max = None`, `salary_text = "Thỏa thuận"`.
3. **Nhận diện Ngôn ngữ (`language`)**:
   - Viết hàm `detect_language(text: str) -> str` trong `crawlers/common/utils.py`.
   - Sử dụng tần suất từ khóa đặc trưng (hoặc regex kiểm tra ký tự tiếng Việt có dấu `à, á, ả, ã, ạ, ...`). Nếu tỷ lệ từ tiếng Việt cao -> `"vi"`, ngược lại -> `"en"`. Lưu vào `_meta.language`.

---

## 📤 4. Output Kỳ Vọng & Tiêu Chuẩn Nghiệm Thu

1. **File dữ liệu mẫu TopCV**: `data/topcv/dt=YYYY-MM-DD/batch_001.json` là một **JSON Array** hợp lệ (`[ { ... }, { ... } ]`), mở được bằng `json.load()` không lỗi.
2. **Cấu trúc mỗi Record**:
   ```json
   {
     "_meta": {
       "source": "topcv",
       "source_job_id": "123456",
       "url": "https://www.topcv.vn/viec-lam/...",
       "dedup_key": "topcv:123456",
       "crawled_at": "2026-10-08T22:00:00Z",
       "batch_id": "2026-10-08_topcv_001",
       "crawler_version": "0.3.0",
       "language": "vi"
     },
     "raw": {
       "title": "Senior Java Developer",
       "company": "FPT Software",
       "description_html": "<p>Chi tiết...</p>",
       "description_text": "Mô tả công việc sạch hoàn toàn không còn tag HTML...",
       "salary_text": "20 - 40 triệu VND",
       "location_text": "Hà Nội",
       "skills_text": "Java, Spring Boot, Microservices",
       "salary_min": 20.0,
       "salary_max": 40.0,
       "salary_currency": "VND"
     }
   }
   ```
3. **Bộ test**: Toàn bộ unit tests `pytest` vượt qua 100% (Coverage ≥ 75%).

---

## 🌿 5. Hướng Dẫn Git Workflow (Kéo Code, Tạo Nhánh & Push)

> [!CAUTION]
> **QUY TẮC BẮT BUỘC TRƯỚC KHI BẮT ĐẦU**:
> 1. Luôn chuyển về `main` và kéo code mới nhất từ remote: `git checkout main && git pull origin main`.
> 2. **BẮT BUỘC TẠO NHÁNH RIÊNG** cho nhiệm vụ của mình: `git checkout -b feature/core-json-schema-topcv`.  
>    🚫 **TUYỆT ĐỐI KHÔNG** commit hoặc viết code trực tiếp trên nhánh `main`!
> 3. Sau khi hoàn thành và test pass 100%, push nhánh lên GitHub và tạo Pull Request để kiểm duyệt.

```bash
# 1. Chuyển về nhánh main và kéo code mới nhất
git checkout main
git pull origin main

# 2. Bắt buộc tạo nhánh riêng cho mình từ main
git checkout -b feature/core-json-schema-topcv

# 3. Tiến hành sửa code, kiểm tra test
pytest tests/
.venv/bin/python run.py --source topcv --max-items 3

# 4. Kiểm tra trạng thái và commit code đúng chuẩn
git status
git add crawlers/common/ crawlers/base/ crawlers/sources/topcv/ run.py scripts/
git commit -m "feat(core): switch output to json array, add language meta and refactor topcv"

# 5. Đẩy nhánh lên GitHub và tạo Pull Request
git push -u origin feature/core-json-schema-topcv
```
> Sau khi push nhánh, hãy tạo PR lên `main` và thông báo cho cả nhóm để mọi người `git pull origin main` cập nhật `BaseCrawler` và `schema` mới nhất!
