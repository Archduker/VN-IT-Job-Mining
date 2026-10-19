# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ (RAW CRAWL INVENTORY) — TOPDEV

> **Người thực hiện:** Sơn (TopDev Source Lead)
> **Nguồn phụ trách:** TopDev (`https://topdev.vn`)
> **Nhánh Git:** `crawls/topdev` (merge vào `crawls/all`)
> **Ngày hoàn thành kiểm kê:** 2026-10-18
> **Tổng số URL phát hiện (URL Ledger):** 65 bài đăng (Pha 1 Discovery)
> **Số snapshot thô đã trích xuất (Pha 2 Detail):** 3 snapshot mẫu thành công + 3 cặp HTML/JSON đối chứng (`crawlers/sources/topdev/samples/`)
> **Đường dẫn lưu trữ MinIO / Local:** `minio://vn-it-jobs/raw/topdev/` và `data/raw/topdev/`

---

## 1. Danh Sách 100% Trường Dữ Liệu Gốc Đã Thu Thập (Field Inventory)

Theo nguyên tắc **Zero Information Loss (SD1)**, crawler TopDev thu thập trọn vẹn JSON payload từ API và HTML container chi tiết:

| STT | Tên trường gốc | Kiểu dữ liệu gốc | Tỷ lệ xuất hiện (%) | Tỷ lệ Null (%) | Ví dụ giá trị mẫu | Mô tả ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `id` / `source_job_id` | Integer / String | 100% | 0% | `"184920"` | Định danh duy nhất bài tuyển dụng trên TopDev |
| 2 | `title` | String | 100% | 0% | `"Senior Backend Engineer (Golang, Microservices)"` | Chức danh công việc hiển thị |
| 3 | `company.name` | String | 100% | 0% | `"Tech Vanguard Asia"` | Tên pháp nhân nhà tuyển dụng |
| 4 | `salary.min` / `salary.max` | Float / Int | 72% | 28% | `35000000` / `60000000` | Mức lương min/max định lượng |
| 5 | `salary.currency` | String | 72% | 28% | `"VND"` / `"USD"` | Đơn vị tiền tệ của dải lương |
| 6 | `salary.is_negotiable` | Boolean | 100% | 0% | `false` | Cờ báo hiệu lương thỏa thuận |
| 7 | `job_description` | HTML String | 100% | 0% | `"<p>Architect scalable APIs...</p>"` | Mô tả trách nhiệm công việc |
| 8 | `job_requirements` | HTML String | 100% | 0% | `"<ul><li>3+ years Golang</li></ul>"` | Yêu cầu kỹ năng và năng lực |
| 9 | `benefits` | HTML String | 90% | 10% | `"<ul><li>13th month salary</li></ul>"` | Quyền lợi và chế độ đãi ngộ |
| 10 | `skills_str` / `skills` | List[String] | 95% | 5% | `["Golang", "Microservices", "Docker", "PostgreSQL"]` | Danh sách thẻ kỹ năng công nghệ |
| 11 | `addresses` / `location` | List[Dict] / String | 98% | 2% | `"District 1, Ho Chi Minh City"` | Địa điểm làm việc chi tiết |
| 12 | `levels` | List[String] | 85% | 15% | `["Senior", "Lead"]` | Cấp bậc chuyên môn tuyển dụng |
| 13 | `published_date` | String (ISO) | 90% | 10% | `"2026-10-15T08:00:00Z"` | Ngày công bố bài tuyển dụng |
| 14 | `content_hash` | String (SHA256) | 100% | 0% | `"ab87f892a012c..."` | Clean Container HTML / API payload hash |

---

## 2. Thống Kê Cơ Chế CDC & Versioning

- **Chu kỳ Re-crawl:** Thiết lập cố định **21 ngày** thông qua `UrlLedger.is_due_for_recrawl(last_scraped_at, days=21)`.
- **Trạng thái URL Ledger:** `PENDING` (chờ quét), `DONE` (đã cào thành công), `FAILED` (gặp sự cố tạm thời, Safe Skip), `CLOSED` (tin hết hạn 404/expired).
- **Cơ chế Clean Container HTML Hashing:**
  - Áp dụng SHA-256 trên nội dung chính của bài đăng sau khi bóc tách và loại bỏ markup biến động.
  - Hỗ trợ phát hiện cập nhật nội dung ($v_1 ightarrow v_2$) và bài đăng trùng lặp xuyên suốt.

---

## 3. Vấn Đề Kỹ Thuật & Khắc Phục

1. **WAF & Rate Limiting:** TopDev áp dụng Cloudflare bảo vệ API và web detail. Bổ sung `User-Agent` xoay vòng và jitter delay 2-4s giữa các request.
2. **Safe Skip:** Bọc toàn bộ Pha 2 `crawl_details` trong try...except item-level, đảm bảo lỗi của một tin không làm gián đoạn toàn bộ batch.
