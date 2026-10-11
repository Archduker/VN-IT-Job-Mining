# Báo Cáo Kiểm Toán Kỹ Thuật Crawler Việc Làm 24h (vieclam24h.vn)

> **Nhánh kiểm toán**: `origin/feature/crawler-vieclam24h`  
> **Commit**: `7681c66a9622a79d41a052187591dc2635b7d7ba` (*"Hoan thien crawler vieclam24h"*)  
> **Tác giả phụ trách**: Nguyễn Minh Phúc  
> **Người kiểm toán**: Ban Kiểm Toán & Quản Trị Hệ Thống VN-IT-Job-Mining  
> **Ngày kiểm toán**: 11/10/2026  
> **Trạng thái phê duyệt**: ⚠️ **CẦN SỬA LỖI TRƯỚC KHI MERGE (ACTION REQUIRED)**

---

## 1. Tổng Quan Kiến Trúc Thu Thập (Crawler Architecture)

Nguồn tuyển dụng **Việc Làm 24h** (`https://vieclam24h.vn`) là một nền tảng tuyển dụng truyền thông lớn tại Việt Nam, hiện nay được xây dựng trên nền tảng Frontend **Next.js (SSR & React Hydration)** kết hợp hệ thống chống bot Cloudflare.

Trong nhánh `origin/feature/crawler-vieclam24h`, bạn Phúc đã tái cấu trúc crawler dựa trên mô hình:
- **Trình duyệt tự động**: Sử dụng **Selenium WebDriver (Chrome)** để vượt qua cơ chế tải động client-side, tương tác với dropdown chọn chuyên ngành React-Select ("IT Phần cứng - Mạng", "IT Phần mềm").
- **Kỹ thuật trích xuất dữ liệu chi tiết**: Sử dụng BeautifulSoup để đọc khối thẻ script chứa state khởi tạo của server:
  ```html
  <script id="__NEXT_DATA__" type="application/json">
  ```
  Nhờ đó, crawler không phải parse HTML selector phân mảnh mà trích xuất trực tiếp payload JSON dạng `props.initialState.api.jobDetailHiddenContact.data`.

### Sơ Đồ Luồng Hoạt Động (Data Flow)

```
[Khởi tạo Selenium Chrome]
       │
       ▼
[Mở https://vieclam24h.vn] ──► [Kích hoạt React Select: Tìm ngành IT]
       │
       ▼
[Duyệt Listing Jobs] ──► [Lấy link thẻ <a data-job-id ...>]
       │
       ▼
[Mở tab chi tiết (window.open)] ──► [Đọc <script id="__NEXT_DATA__">]
       │                                     │
       │                                     ▼
       │                            [Trích xuất JSON State]
       ▼                                     │
[Chuyển đổi JobRecord (Pydantic)] ◄──────────┘
```

---

## 2. Đánh Giá Chi Tiết Theo Tiêu Chuẩn Kỹ Thuật

### 2.1. Tuân thủ BaseCrawler (`crawlers.base.base_crawler.BaseCrawler`)

| Tiêu chí | Đánh giá | Chi tiết phân tích |
| :--- | :---: | :--- |
| **Kế thừa Class** | ✅ Đạt | Kế thừa `BaseCrawler`, thiết lập `source_name = "vieclam24h"`, `crawler_version = "0.1.0"`. |
| **Hàm `fetch_items`** | ⚠️ Cảnh báo | Implement đúng generator yield `{"job_detail": ..., "url": ...}`, nhưng phụ thuộc hoàn toàn vào Chrome GUI. |
| **Hàm `parse_item`** | ⚠️ Lỗi tiềm ẩn | Có implement chuyển đổi thành `JobRecord`, nhưng xử lý rỗng gây crash Pydantic (xem chi tiết mục 2.2). |
| **Tích hợp vòng lặp `run()`** | ❌ **Lỗi nghiêm trọng** | **Lỗi Fatal trong `main()`** làm gãy luồng chạy chuẩn của hệ thống (xem phân tích mục 3.1). |

---

### 2.2. Tuân thủ Data Contract & Schema v1 (`JobRecord`, `JobRaw`, `JobSalary`, `JobTags`)

| Trường Schema | Trạng thái | Nhận xét chi tiết & Rủi ro |
| :--- | :---: | :--- |
| `_meta.source` | ✅ Chuẩn | `"vieclam24h"` |
| `_meta.source_job_id` | ✅ Chuẩn | Lấy từ `job_detail["id"]` |
| `_meta.language` | ✅ Chuẩn | Tích hợp hàm `detect_language` từ common utils |
| `raw.title` | ✅ Chuẩn | Làm sạch khoảng trắng qua `_clean_text` |
| `raw.company` | ✅ Chuẩn | Trích xuất từ `job_detail["employer_info"]["name"]` |
| `raw.description_list` | ❌ **Lỗi Schema** | Gán `description_list = description_list or None`. Khi tin đăng không có mô tả (hoặc parse rỗng `[]`), giá trị trả về là `None`. Schema v1 quy định `description_list: list[str]` bắt buộc không rỗng, dẫn đến `ValidationError` làm drop tin. |
| `raw.salary` | ⚠️ Cần tinh chỉnh | Quy đổi chia cho `1,000,000` thành triệu VND. Tuy nhiên nếu tin thỏa thuận thì `salary_currency` là `None`, `is_negotiable=True` (hợp lệ). |
| `raw.tags` | ❌ **Sai ngữ nghĩa** | Nhầm lẫn giữa **Thẻ tag phân loại (pill badges)** và **Danh sách bullet nội dung**. Gán toàn bộ `requirements_list` vào `tags.requirements` và `benefits_list` vào `tags.benefits` thay vì trích xuất tags chuyên môn/kỹ năng (`skills`). |
| `raw.extra` | ❌ **Hardcode giả lập** | Đang hardcode nhiều trường mà không kiểm tra dữ liệu thật: `employment_type_text="Toàn thời gian"`, `seniority_text="Nhân viên"`, `work_schedule="Thứ 2 - Thứ 6"`, `education="Đại Học trở lên"`. Điều này gây sai lệch nghiêm trọng khi phân tích thống kê thị trường lao động. |

---

## 3. Các Lỗi Kỹ Thuật Trọng Yếu Cần Khắc Phục (Critical Issues)

### 3.1. [FATAL BUG] Vòng Lặp Lỗi Tại Hàm `main()` Gây Crash Khi Chạy Độc Lập
Tại dòng 541 của [`crawlers/sources/vieclam24h/crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/vieclam24h/crawler.py#L541):
```python
# CODE HIỆN TẠI (LỖI):
for record in crawler.run():
    record_dict = record.to_jsonl_dict()
    ...
```
- **Nguyên nhân**: Trong kiến trúc chuẩn `BaseCrawler`, phương thức `crawler.run()` tự động điều phối toàn bộ chu trình (lấy item -> parse -> checkpoint -> JsonWriter -> flush file) và trả về **một `dict` thống kê** (ví dụ: `{"source": "vieclam24h", "crawled": 10, "skipped": 2, ...}`).
- **Hậu quả**: Khi duyệt `for record in crawler.run():`, Python sẽ lặp qua các khóa dạng chuỗi (`"source"`, `"crawled"`, ...). Khi gọi `record.to_jsonl_dict()`, chương trình lập tức văng ngoại lệ:
  ```text
  AttributeError: 'str' object has no attribute 'to_jsonl_dict'
  ```
- **Xung đột ghi đĩa kép**: `BaseCrawler` đã tự động ghi dữ liệu chuẩn vào thư mục `data/vieclam24h/dt=.../batch_*.json`. Việc tác giả tự viết thêm cơ chế `_atomic_write` ra file `vieclam24h_jobs.json` là dư thừa và làm sai lệch cơ chế partition của hệ thống.

---

### 3.2. Khởi Tạo WebDriver Thiếu Headless Gây Crash Môi Trường Server/CI
Tại dòng 364 của [`crawlers/sources/vieclam24h/crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/vieclam24h/crawler.py#L364):
```python
self.driver = webdriver.Chrome()
```
- **Rủi ro**: Không cấu hình Chrome Options (`--headless=new`, `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`).
- Khi chạy trên server Linux không có Display X11 hoặc chạy trong Docker container, crawler sẽ crash ngay lập tức tại thời điểm khởi tạo đối tượng class.

---

### 3.3. Dữ Liệu Bị Hardcode Trong `extra`
Tại dòng 263-270:
```python
raw_values = dict(
    ...
    employment_type_text="Toàn thời gian",
    seniority_text="Nhân viên",
    extra={
        "work_schedule": "Thứ 2 - Thứ 6",
        "education": "Đại Học trở lên",
        "hiring_quantity": f"{job_detail.get('vacancy_quantity', 1)} người",
        ...
    }
)
```
- **Nhận xét**: Nhiều công ty tuyển Thực tập sinh (Intern), Bán thời gian (Part-time), làm Thứ 7, hoặc yêu cầu Cao đẳng... nhưng đều bị crawler gán cứng thành "Toàn thời gian", "Nhân viên", "Thứ 2 - Thứ 6", "Đại học trở lên". Phải đọc từ payload API hoặc để `None`.

---

## 4. Kế Hoạch Khắc Phục (Action Plan)

1. **Sửa đổi hàm `main()`**:
   Bỏ vòng lặp thừa và gọi trực tiếp `crawler.run()`. Để `BaseCrawler` quản lý `JsonWriter` và `CheckpointManager`.
2. **Bổ sung Chrome Headless Options**:
   Thêm cờ cấu hình trình duyệt không giao diện an toàn cho server Linux.
3. **Sửa Schema Mapping**:
   - Nếu `description_list` rỗng, fallback về tiêu đề tóm tắt dạng `[title]` thay vì gán `None`.
   - Bỏ gán cứng text vào `tags.requirements` và `tags.benefits`; sử dụng hàm `classify_job_tags` từ common utils.
   - Trích xuất linh hoạt `work_schedule`, `education`, `employment_type` từ `job_detail` nếu có; nếu không có thì gán `None`.
4. **Bổ sung Test Suite**:
   Tạo file test tại `tests/unit/test_vieclam24h_crawler.py` để mock dữ liệu HTML `__NEXT_DATA__` và xác minh tính toàn vẹn schema mà không cần mở Chrome thật.

---

## 5. Kết Luận Kiểm Toán

Crawler Việc Làm 24h có hướng đi kỹ thuật rất thông minh khi khai thác state `__NEXT_DATA__`. Tuy nhiên, do còn tồn tại lỗi cú pháp gọi `BaseCrawler.run()`, thiếu headless options và một số trường hợp schema bị hardcode/null sai quy tắc, **chưa đủ điều kiện merge trực tiếp vào `crawl-main`**. 

Khuyến nghị: Áp dụng bản vá kỹ thuật (patch) trước khi tiến hành merge.
