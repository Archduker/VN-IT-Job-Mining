# Báo Cáo Kiểm Toán Kỹ Thuật Crawler Glints (glints.com/vn)

> **Nhánh kiểm toán**: `origin/crawler-glints`  
> **Commits**: `a634cdd58c6d5ffc9624ce23aa8b58a470b057fe`, `539aaee0174828990f675c2694150e71b56815ef` (*"Add Glints Vietnam crawler"*)  
> **Tác giả phụ trách**: Khắc Duy (`duynkh9326-hub`)  
> **Người kiểm toán**: Ban Kiểm Toán & Quản Trị Hệ Thống VN-IT-Job-Mining  
> **Ngày kiểm toán**: 11/10/2026  
> **Trạng thái phê duyệt**:  **ĐẠT CHUẨN KỸ THUẬT - SẴN SÀNG MERGE (KÈM ĐIỀU CHỈNH THƯ MỤC TEST)**

---

## 1. Tổng Quan Kiến Trúc Thu Thập (Crawler Architecture)

**Glints Vietnam** (`https://glints.com/vn`) là một trong những nền tảng tuyển dụng công nghệ và tài năng trẻ phát triển nhanh nhất tại Đông Nam Á. Trang web kết hợp giữa GraphQL API backend và Next.js SSR frontend có gắn dữ liệu cấu trúc Schema.org (`JobPosting`).

Bạn Duy đã thiết kế crawler theo mô hình **Hybrid API Listing + JSON-LD Detail**:
1. **Giai đoạn 1 (Listing)**: Gọi GraphQL endpoint chính thức `https://glints.com/api/v3` với query `searchJobsV3` để lấy danh sách việc làm IT đang mở, lọc theo `countryCode: "VN"`.
2. **Giai đoạn 2 (Detail Parsing)**: Từ URL bài đăng, tải HTML chi tiết và trích xuất khối dữ liệu cấu trúc chuẩn Google `<script type="application/ld+json">` để lấy toàn bộ dữ liệu sạch (Title, Organization, Salary, Description HTML, ValidThrough).

```
        [Glints GraphQL API] ──► fetch_items() (Listing)
                                      │
                                      ▼
     [Glints Web Detail Page] ──► fetch_jobposting_details()
                                      │ (JSON-LD JobPosting)
                                      ▼
                                [parse_item()]
                                      ├── html_to_text_list() -> description_list
                                      ├── extract salary -> JobSalary
                                      ├── map skills/requirements -> JobTags
                                      └── detect_language() -> _meta.language
```

---

## 2. Đánh Giá Chi Tiết Theo Tiêu Chuẩn Data Contract Schema v1

### 2.1. Đánh Giá Tiêu Chuẩn

| Tiêu chuẩn | Kết quả | Chi tiết phân tích kỹ thuật |
| :--- | :---: | :--- |
| **Kế thừa `BaseCrawler`** |  **Đạt** | Class `GlintsCrawler(BaseCrawler)` thiết lập đầy đủ `source_name = "glints"`, `crawler_version = "0.2.0"`, quản lý checkpoint thông qua `seen_ids`. |
| **Mức Lương (`JobSalary`)** |  **Đạt** | Bóc tách từ `baseSalary` trong JSON-LD thành `salary_min`, `salary_max`, `salary_currency`, `pay_period = "month"`, tự động format `salary_text` chống lỗi hiển thị số mũ khoa học (`scientific notation`). |
| **Phân Loại Thẻ Tags (`JobTags`)** |  **Đạt** | Phân tách rõ ràng 3 nhóm: `skills`, `requirements`, `benefits`. |
| **Làm Sạch Dòng Văn Bản** |  **Đạt** | Sử dụng `html_to_text_list` để phân tách `description_list`, `requirements_list`, `benefits_list` loại bỏ thẻ HTML. Có cơ chế fallback: nếu bài đăng không có mô tả sẽ gắn thông báo dự phòng, không để rỗng. |
| **Nhận Diện Ngôn Ngữ** |  **Đạt** | Tích hợp hàm `detect_language(title, company, description)` tự động phân loại `"vi"` hoặc `"en"` ghi vào `_meta.language`. |
| **Hạn Nộp & Extra** |  **Đạt** | Trích xuất `validThrough` làm `deadline_text`, tính toán ngày đăng fallback qua số ngày còn lại (`14 days left`), lưu trạng thái `description_available` vào `extra`. |

---

## 3. Điểm Cần Nhóm Trưởng Lưu Ý Khi Merge

> [!WARNING]
> **Vị trí thư mục Unit Test**:
> Bạn Duy đặt file test tại: `test/unit/test_glints_crawler.py` (thư mục `test/` số ít).
> Trong khi toàn bộ hệ thống dự án đang cấu hình `pytest` quét trong `tests/` (số nhiều: `tests/unit/`).
> - **Khuyến nghị xử lý**: Khi merge vào nhánh `crawl-main`, nhóm trưởng sẽ di chuyển file test sang `tests/unit/test_glints_crawler.py` để tích hợp mượt mà vào lệnh `pytest tests/` chung của CI/CD.

---

## 4. Kết Luận & Khuyến Nghị
- Mã nguồn viết rất chỉn chu, có fake HTTP client phục vụ test offline, code có type hints và docstrings rõ ràng.
- **Quyết định**: **DUYỆT MERGE** vào nhánh `crawl-main` (kèm di chuyển thư mục test).
