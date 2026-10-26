# Báo Cáo Kiểm Toán Kỹ Thuật Crawler ITviec (itviec.com)

> **Nhánh kiểm toán**: `origin/feature/itviec-crawler`  
> **Commit**: `a85c815534c9394bff27cf99d7a61a3a1e295dc0` (*"refactor: source ITviec crawler"*)  
> **Tác giả phụ trách**: Hồng Phát  
> **Người kiểm toán**: Ban Kiểm Toán & Quản Trị Hệ Thống VN-IT-Job-Mining  
> **Ngày kiểm toán**: 11/10/2026  
> **Trạng thái phê duyệt**:  **ĐẠT CHUẨN XUẤT SẮC - SẴN SÀNG MERGE (READY TO MERGE)**

---

## 1. Tổng Quan Kiến Trúc Thu Thập (Crawler Architecture)

Nguồn tuyển dụng **ITviec** (`https://itviec.com`) là nền tảng chuyên biệt hàng đầu cho việc làm IT tại Việt Nam. Trang web áp dụng mô hình Server-Side Rendering (SSR) kết hợp nhúng dữ liệu cấu trúc chuẩn Google Schema.org (`<script type="application/ld+json">`).

Trong nhánh `origin/feature/itviec-crawler`, bạn Phát đã hoàn thành một đợt refactor toàn diện:
- **Tách bạch trách nhiệm (Separation of Concerns)**:
  - [`config.py`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/crawlers/sources/itviec/config.py): Lưu hằng số, cấu hình URL, delay, retry, phiên bản crawler.
  - [`parser.py`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/crawlers/sources/itviec/parser.py): Chuyên trách bóc tách HTML thuần (Listing & Detail), trả về dict cấu trúc chuẩn.
  - [`crawler.py`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/crawlers/sources/itviec/crawler.py): Kế thừa `BaseCrawler`, quản lý kết nối HTTP, checkpoint, vòng lặp thu thập.
  - [`tests/`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/crawlers/sources/itviec/tests): Bộ unit test ngoại tuyến độc lập.

### Sơ Đồ Khối Module ITviec

```
                 [run.py]
                    │
                    ▼
          [ItviecCrawler] (crawler.py)
          ├── Kế thừa: BaseCrawler
          ├── Sử dụng: HttpClient + CheckpointManager + JsonWriter
          │
          ├──► fetch_items() ──► parser.parse_listing()
          │                            │
          │                            ▼
          └──► parse_item()  ──► parser.parse_detail()
                                       │
                                       ├── Đọc JSON-LD JobPosting
                                       ├── Làm sạch bullet (text_to_clean_lines)
                                       ├── Bóc tách lương (parse_salary_detail)
                                       └── Phân loại tags (classify_job_tags)
```

---

## 2. Đánh Giá Chi Tiết Theo Tiêu Chuẩn Kỹ Thuật

### 2.1. Tuân thủ BaseCrawler (`crawlers.base.base_crawler.BaseCrawler`)

| Tiêu chí | Đánh giá | Chi tiết phân tích |
| :--- | :---: | :--- |
| **Kế thừa Class** |  **Xuất sắc** | Khởi tạo đầy đủ `super().__init__(...)`, gán `source_name = "itviec"`, `crawler_version = "0.5.0"`. |
| **Tích hợp HttpClient** |  **Xuất sắc** | Sử dụng `HttpClient` với `DelayConfig` (nghỉ ngẫu nhiên), `RetryConfig` (tự động thử lại khi lỗi mạng). |
| **Xử lý Brotli Encoding** |  **Rất tinh tế** | Khắc phục triệt để lỗi requests không giải nén được định dạng Brotli (`br`) bằng cách ép header: `"Accept-Encoding": "gzip, deflate"`. |
| **Hàm `fetch_items`** |  **Chuẩn xác** | Lặp qua các địa bàn trọng điểm (TP.HCM, Hà Nội, Đà Nẵng, Remote), kiểm tra checkpoint `is_seen()` ngay từ khâu listing để tiết kiệm băng thông. |
| **Hàm `parse_item`** |  **Chuẩn xác** | Trả về đối tượng `JobRecord` hợp lệ qua factory method `JobRecord.create(...)`. |

---

### 2.2. Đánh Giá Refactor CLI Hệ Thống (`run.py`)

Trong code gốc của dự án, nhánh `itviec` trước đây sử dụng đoạn code chắp vá can thiệp trực tiếp vào biến module:
```python
# CODE CŨ TRƯỚC REFACTOR:
import crawlers.sources.itviec.config as itviec_config
import crawlers.sources.itviec.crawler as itviec_crawler
itviec_config.DATA_DIR = itviec_data_dir  # Monkey-patch nguy hiểm!
stats = itviec_crawler.crawl(max_items=max_items, batch_id=batch_id)
```

Bạn Phát đã refactor thành cấu trúc hướng đối tượng chuẩn:
```python
# CODE MỚI TRONG NHÁNH ITVIEC:
from crawlers.sources.itviec.crawler import ItviecCrawler

crawler = ItviecCrawler(
    checkpoint_dir=checkpoint_dir,
    output_dir=output_dir,
    max_items=max_items,
)
if batch_id:
    crawler.batch_id = batch_id
return crawler.run()
```
- **Lợi ích**: Code ngắn gọn hơn 26 dòng, loại bỏ hoàn toàn việc gán đè biến toàn cục, đồng bộ 100% với cách gọi của các crawler khác (`TopcvCrawler`, `CareervietCrawler`).

---

### 2.3. Tuân thủ Data Contract Schema v1

| Trường Schema | Trạng thái | Đánh giá kỹ thuật |
| :--- | :---: | :--- |
| `_meta.source` |  Đạt | `"itviec"` chuẩn xác. |
| `_meta.source_job_id` |  Đạt | Trích xuất slug định danh hoặc hash URL an toàn. |
| `_meta.language` |  Đạt | Nhận diện tự động qua `detect_language(desc_text)`. Tách `language` ra khỏi `raw` đưa vào `_meta`. |
| `raw.title` |  Đạt | Tiêu đề nguyên bản sạch sẽ. |
| `raw.company` |  Đạt | Tên doanh nghiệp từ JSON-LD hoặc header. |
| `raw.description_list` |  Đạt | Danh sách bullet points trích xuất qua `text_to_clean_lines`. |
| `raw.salary` |  Đạt | Sử dụng `parse_salary_detail`: trích xuất số thực `salary_min`, `salary_max`, tiền tệ (`VND`/`USD`), cờ `is_negotiable`. |
| `raw.tags` |  Đạt | Phân loại trực tiếp thành 3 nhóm `requirements`, `benefits`, `skills` với quy tắc `null` nếu không có trên trang. |
| `raw.requirements_list` |  Đạt | Danh sách các yêu cầu công việc dạng list string. |
| `raw.benefits_list` |  Đạt | Danh sách các đãi ngộ, phúc lợi dạng list string. |

---

## 3. Đánh Giá Bộ Test Suite (`crawlers/sources/itviec/tests/`)

Nhánh ITviec có chất lượng kiểm thử tốt nhất trong 4 nhánh:
1. [`test_crawler_helpers.py`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/crawlers/sources/itviec/tests/test_crawler_helpers.py):
   - Kiểm thử khởi tạo `ItviecCrawler`, thuộc tính `source_name`, `crawler_version`, định dạng `batch_id`.
   - Kiểm thử việc xây dựng và chuẩn hóa URL phân trang (`_listing_url`).
   - Kiểm thử logic bỏ qua bài đăng trùng lặp (`checkpoint.is_seen`).
2. [`test_parser.py`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/crawlers/sources/itviec/tests/test_parser.py):
   - Kiểm thử trích xuất thẻ JSON-LD `JobPosting`.
   - Kiểm thử bóc tách đa ngôn ngữ (bài đăng thuần tiếng Anh và tiếng Việt).
   - Kiểm thử xử lý dải lương nhiều biến thể: Lương USD, Lương triệu VND, Lương Thỏa thuận ("You'll love it").
   - Tất cả test case đều chạy offline bằng HTML fixtures giả lập, tốc độ thực thi < 0.2s.

---

## 4. Khuyến Nghị Khi Merge

Nhánh `origin/feature/itviec-crawler` đã đạt độ chín muồi rất cao:
- Không gây conflict với các nguồn khác do phân tách thư mục độc lập.
- File `run.py` sửa đổi chuẩn xác, giúp hệ thống hoàn thiện việc thống nhất CLI chung.
- **Khuyến nghị**: **ƯU TIÊN MERGE ĐẦU TIÊN (Priority 1)** vào nhánh `crawl-main`.
