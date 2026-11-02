# Báo Cáo Kiểm Toán Kỹ Thuật Crawler TopDev (topdev.vn)

> **Hiện trạng 03/11/2026**
>
> - Crawler: `collection/sources/topdev/crawler.py`, gọi API TopDev; detail lấy từ API chi tiết với `DETAIL_FIELDS`.
> - Đã sửa: `DETAIL_FIELDS` thiếu kinh nghiệm, cấp bậc, ngày đăng (L-05); bỏ `published.since` khỏi raw để hash ổn định; ghi version mới cho nội dung không đổi khi cào lại (L-03).
> - Còn mở: raw cào trước 02/11 vẫn thiếu F5, F6, F8 (SCRAPE-5).
> - Test: `tests/contract/test_topdev_contract.py`, mẫu `tests/fixtures/topdev/` (tin thường, lương thỏa thuận, ẩn lương; TopDev không có cờ VIP).
>
> Đường dẫn `crawlers/` cũ đã đổi thành `collection/`. Thư mục `samples/`, file `test_5_jobs.json`, `batch_001.json` và test riêng trong thư mục nguồn nhắc bên dưới là lịch sử, không còn trong repo; mẫu và test hiện ở `tests/fixtures/<nguồn>/` và `tests/contract/`. Tiêu chuẩn chung: `collection/CLAUDE.md`; lỗi đã sửa: `docs/issue_log.md`.

> **Nhánh kiểm toán**: `origin/feature/topdev-son`  
> **Commit**: `6dc0b528c2cc9e15b3a9c3c769789cb4ed60bcdc` (*"feat(topdev): clean html tags, parse numeric salary and detect language to json"*)  
> **Tác giả phụ trách**: Sơn (`sonbnUTH`)  
> **Người kiểm toán**: Ban Kiểm Toán & Quản Trị Hệ Thống VN-IT-Job-Mining  
> **Ngày kiểm toán**: 11/10/2026  
> **Trạng thái phê duyệt**:  **CẦN DỌN DẸP FILE DATA TRƯỚC KHI MERGE (ACTION REQUIRED)**

---

## 1. Tổng Quan Cải Tiến Trong Nhánh Của Sơn

Nền tảng **TopDev** (`https://topdev.vn`) cung cấp hệ thống REST API v2 (`https://api.topdev.vn/td/v2/jobs`) hỗ trợ phân trang và dữ liệu việc làm IT rất dồi dào.

Trong commit `6dc0b52`, bạn Sơn đã thực hiện nâng cấp quy mô lớn đối với [`collection/sources/topdev/crawler.py`](../../collection/sources/topdev/crawler.py) (+1,579 lines):
1. **Làm sạch thẻ HTML**: Tích hợp BeautifulSoup và `text_to_clean_lines` để bóc tách mô tả, yêu cầu, trách nhiệm thành danh sách dòng sạch.
2. **Chuẩn hóa mức lương**: Sử dụng `parse_salary_detail` kết hợp các trường số từ API (`salary_min`, `salary_max`, `currency`).
3. **Phát hiện ngôn ngữ**: Nhận diện bài đăng tiếng Anh/tiếng Việt và lưu vào `JobMetadata.language`.
4. **Hỗ trợ đa danh mục IT**: Mở rộng danh mục cào qua các `JOB_CATEGORY_IDS` (IT, Business/Finance, Management, Engineering).

---

## 2. Vấn Đề Nghiêm Trọng Cần Xử Lý Trước Khi Merge (Critical Issue)

> [!CAUTION]
> **Commit nhầm file dữ liệu lớn vào Git Tracking**:
> Trong commit `6dc0b52`, bạn Sơn đã commit trực tiếp file:
> `collection/sources/topdev/batch_001.json` (kích thước **3.13 MB**, gồm **64,948 dòng JSON**).
> 
> **Hậu quả nếu merge trực tiếp vào `main`**:
> - Làm phình to dung lượng git repository `.git` vĩnh viễn.
> - Vi phạm nguyên tắc lưu trữ dữ liệu của dự án: Dữ liệu crawl thực tế phải nằm trong `data/raw/` (được `.gitignore` bảo vệ) hoặc đẩy lên AWS S3, tuyệt đối không commit file JSON crawl hàng chục ngàn dòng vào source tree.

---

## 3. Phương Án Xử Lý & Lộ Trình Merge An Toàn (Resolution Strategy)

Để giữ lại 100% công sức cải tiến code của Sơn mà không làm bẩn git repository:

1. **Bước 1**: Đọc và trích xuất 5 bản ghi mẫu đầu tiên từ `batch_001.json` để tạo file benchmark đạt chuẩn chất lượng:
   `collection/sources/topdev/test_5_jobs.json` (~500 dòng).
2. **Bước 2**: Chạy kiểm tra `DataQualityChecker` trên `test_5_jobs.json` để đảm bảo 100% schema validity.
3. **Bước 3**: Khi merge nhánh `origin/feature/topdev-son` vào nhánh quản lý `crawl-main`:
   - Chỉ cherry-pick / merge file mã nguồn `collection/sources/topdev/crawler.py`.
   - Di chuyển `batch_001.json` vào thư mục `data/raw/topdev/batch_001.json` (được gitignore bảo vệ) hoặc loại bỏ khỏi Git index:
     ```bash
     git rm --cached collection/sources/topdev/batch_001.json
     ```
4. **Bước 4**: Thêm unit test kiểm chứng TopDev vào `tests/unit/test_topdev_crawler.py`.

---

## 4. Kết Luận & Khuyến Nghị
- Cải tiến logic bóc tách của Sơn rất chất lượng và hoàn toàn phù hợp với Data Contract v1.
- **Quyết định**: **DUYỆT MERGE CÓ ĐIỀU KIỆN** — Bắt buộc phải áp dụng quy trình loại bỏ file `batch_001.json` 64k dòng theo Bước 3 trước khi merge vào `main`.
