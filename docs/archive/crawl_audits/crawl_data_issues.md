# Báo Cáo Sự Cố Dữ Liệu & Bất Thường Kỹ Thuật (Crawl Data & Code Issues Log)

> **Mục tiêu tài liệu**: Ghi nhận tập trung toàn bộ các bất thường dữ liệu (Data Anomalies), vi phạm Data Contract Schema v1, và các lỗi kỹ thuật phát hiện trong quá trình kiểm toán các nhánh thành viên để Nhóm trưởng theo dõi và quyết định trước khi merge code.  
> **Cập nhật ngày**: 11/10/2026

---

## 1. Danh Sách Các Bất Thường Được Phát Hiện

### 🔴 Sự Cố 1: Commit File Dữ Liệu 64k Dòng (3.13 MB) Vào Git Tree (TopDev - Bạn Sơn)
- **Vị trí**: `crawlers/sources/topdev/batch_001.json` trong commit `6dc0b52` (nhánh `origin/feature/topdev-son`).
- **Hiện tượng**: File chứa **64,948 dòng JSON**, dung lượng 3,132,227 bytes được thêm trực tiếp vào git source tree.
- **Rủi ro**: Làm phình to dung lượng git repository vĩnh viễn, vi phạm kiến trúc lưu trữ (dữ liệu thô phải nằm trong `data/raw/` được `.gitignore` bảo vệ).
- **Giải pháp xử lý**:
  1. Trích xuất 5 bản ghi mẫu đạt chuẩn vào `crawlers/sources/topdev/test_5_jobs.json`.
  2. Loại bỏ file `batch_001.json` khỏi git index khi merge (`git rm --cached crawlers/sources/topdev/batch_001.json`).

---

### 🔴 Sự Cố 2: Lỗi Crash `crawler.run()` & Vi Phạm Data Contract Schema v1 (Việc Làm 24h - Bạn Phúc)
- **Vị trí**: `crawlers/sources/vieclam24h/crawler.py` trong commit `7681c66` (nhánh `origin/feature/crawler-vieclam24h`).
- **Hiện tượng**:
  1. **Lỗi Fatal Bug**: Tại hàm `main()`: `for record in crawler.run(): record.to_jsonl_dict()`. Do `crawler.run()` trả về một `dict` thống kê (`{"source": "...", "crawled": 5}`), duyệt `for` trên dict sẽ nhận về chuỗi string, dẫn đến crash:
     ```text
     AttributeError: 'str' object has no attribute 'to_jsonl_dict'
     ```
  2. **Vi phạm Schema v1**: Khi tin không có mô tả, gán `description_list = None` thay vì fallback, làm rớt tin và vi phạm Pydantic contract (bắt buộc `list[str]`).
  3. **Hardcode dữ liệu**: Hardcode các trường `work_schedule`, `education`, `employment_type_text`, `seniority_text` gây sai lệch dữ liệu thị trường.
  4. **Khởi tạo Selenium thiếu headless**: Khởi tạo `webdriver.Chrome()` không có `--headless=new` gây crash trên môi trường CI/Server.
- **Giải pháp xử lý**: Sửa lỗi `crawler.run()`, thêm headless options, fallback `description_list`, và gỡ bỏ hardcode trước khi merge vào `crawl-main`.

---

### 🟡 Sự Cố 3: Sai Lệch Thư Mục Unit Test (Glints - Bạn Duy)
- **Vị trí**: `test/unit/test_glints_crawler.py` trong commit `539aaee` (nhánh `origin/crawler-glints`).
- **Hiện tượng**: Đặt trong thư mục `test/` (số ít), trong khi toàn bộ dự án đang dùng `tests/` (số nhiều). Khi chạy `pytest tests/`, test suite của Glints bị bỏ qua.
- **Giải pháp xử lý**: Di chuyển file sang `tests/unit/test_glints_crawler.py` khi merge.

---

## 2. Nhật Ký Giám Sát Dữ Liệu Các Crawler
Toàn bộ các crawler sau khi refactor bắt buộc phải được chạy qua `DataQualityChecker` để xác nhận:
- `schema_valid_rate == 100.0%`
- `unique_rate == 100.0%`
- `passed == True`
