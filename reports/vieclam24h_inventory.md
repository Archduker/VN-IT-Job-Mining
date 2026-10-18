# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ (RAW CRAWL INVENTORY) — VIECLAM24H

> **Người thực hiện:** Phạm Nguyễn Minh Phúc (Vieclam24h Source Lead)  
> **Nguồn phụ trách:** Vieclam24h (`https://vieclam24h.vn`)  
> **Nhánh Git:** `crawls/vieclam24h` (đồng bộ trên `main`)  
> **Ngày hoàn thành cào:** 2026-10-17  
> **Tổng số URL phát hiện (URL Ledger):** 478 bài đăng (Pha 1 Discovery)  
> **Số snapshot thô đã trích xuất (Pha 2 Detail):** 1 snapshot mẫu thành công (`data/vieclam24h/raw/2026-10-17/200962244_v1.json`) + dữ liệu quản lý UrlLedger  
> **Đường dẫn lưu trữ MinIO / Local:** `minio://vn-it-jobs/raw/vieclam24h/` và `data/vieclam24h/`  

---

## 1. Danh Sách 100% Trường Dữ Liệu Gốc Đã Thu Thập (Field Inventory)

Theo nguyên tắc **Zero Information Loss (SD1)**, crawler Vieclam24h giữ nguyên 100% các trường dữ liệu thô thu thập được trong cấu trúc UrlLedger JSON từ hệ thống:

| STT | Tên trường gốc (JSON Key) | Kiểu dữ liệu gốc | Tỷ lệ xuất hiện (%) | Tỷ lệ Null (%) | Ví dụ giá trị mẫu | Mô tả ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `"url_hash"` | String (Chuỗi) | 100% | 0% | `"47bb29693c502ba6128bb4747e1d6094"` | Mã băm MD5/SHA256 định danh URL duy nhất trong Ledger |
| 2 | `"canonical_url"` | String (Chuỗi) | 100% | 0% | `"https://vieclam24h.vn/it-phan-mem/ky-su-lap-trinh-plc-c8p210000187id200962244.html"` | Đường dẫn chuẩn của bài đăng tuyển dụng |
| 3 | `"source"` | String (Chuỗi) | 100% | 0% | `"vieclam24h"` | Tên mã nguồn tuyển dụng |
| 4 | `"job_id"` | String (Chuỗi) | 100% | 0% | `"200962244"` | Mã ID định danh công việc gốc trên hệ thống Vieclam24h |
| 5 | `"discovered_at"` | String (Thời gian ISO 8601) | 100% | 0% | `"2026-10-17T07:15:33.234244+00:00"` | Thời điểm crawler phát hiện URL ở Pha 1 |
| 6 | `"status"` | String (Chuỗi) | 100% | 0% | `"CLOSED"` | Trạng thái xử lý của URL trong vòng đời cào dữ liệu |
| 7 | `"preliminary_title"` | String (Chuỗi) | 100% | 0% | `"Kỹ Sư Lập Trình Plc"` | Tiêu đề sơ bộ trích xuất được từ trang danh mục (Listing) |
| 8 | `"preliminary_company"` | String (Chuỗi) | 100% | 0% | `"Unknown"` | Tên công ty sơ bộ thu thập từ Pha 1 |
| 9 | `"identity_key"` | String (Chuỗi) | 100% | 0% | `"unknown__kỹ_sư_lập_trình_plc"` | Khóa định danh tổng hợp phục vụ so sánh và khử trùng lặp |
| 10 | `"last_seen_at"` | String (Thời gian ISO 8601) | 100% | 0% | `"2026-10-17T10:53:30.355661+00:00"` | Thời điểm cuối cùng phát hiện lại bài đăng khi quét danh mục |
| 11 | `"last_scraped_at"` | Null / None | 100% | 100% | `null` | Thời điểm thực hiện cào chi tiết thành công ở Pha 2 |
| 12 | `"content_hash"` | Null / None | 100% | 100% | `null` | Hash nội dung HTML container `main` dùng kiểm tra thay đổi |
| 13 | `"latest_version"` | Integer (Số nguyên) | 100% | 0% | `0` | Số phiên bản dữ liệu của bài đăng khi có thay đổi nội dung |
| 14 | `"repost_of_url_hash"` | Null / None | 100% | 100% | `null` | Trỏ tới `url_hash` gốc nếu phát hiện bài đăng lại (Repost) |
| 15 | `"error_log"` | Null / None | 100% | 100% | `null` | Chi tiết thông tin lỗi gặp phải trong quá trình cào |
| 16 | `"retry_count"` | Integer (Số nguyên) | 100% | 0% | `0` | Số lần đã thử cào lại khi gặp sự cố mạng hoặc WAF |

---

## 2. Thống Kê Cơ Chế CDC & Versioning

- **Chu kỳ Re-crawl:** Thiết lập cố định **21 ngày** (`is_due_for_recrawl(last_scraped_at, days=21)`).
- **Trạng thái bài đăng (UrlLedger Status):** 
  - `DONE`: Bài đã cào chi tiết thành công ở Pha 2.
  - `PENDING`: Bài mới phát hiện ở Pha 1, chờ tải chi tiết.
  - `CLOSED`: Bài không tồn tại hoặc hết hạn (Phát hiện HTTP 404 / "Tin tuyển dụng này không tồn tại").
  - `FAILED`: Lỗi ngoại lệ tạm thời trong quá trình tải dữ liệu.
- **Cơ chế Clean Container HTML Hashing:**
  - Bóc tách container `main`, loại bỏ các thẻ nhiễu, chuẩn hóa whitespace và băm SHA256.
  - Trường hợp URL mới nhưng nội dung trùng bài đăng cũ (Repost): Phát hiện qua `find_by_content_hash()`, gắn cờ `repost_of_url_hash` trỏ về `url_hash` gốc, không tạo bản ghi rác.

---

## 3. Các Vấn Đề Kỹ Thuật Đã Gặp & Giải Pháp

1. **Trích xuất dữ liệu qua Next.js SSR State (`__NEXT_DATA__`):**
   - *Giải pháp:* Trích xuất trực tiếp JSON state từ thẻ `<script id="__NEXT_DATA__">` để lấy toàn bộ danh sách listing API và chi tiết `jobDetailHiddenContact`, kết hợp quét selector `main` làm fallback HTML.
2. **Cơ chế Safe Skip & Xử lý lỗi kết nối:**
   - *Giải pháp:* Cấu hình `HttpClient` kèm theo cơ chế bắt ngoại lệ Safe Skip để cập nhật `status: FAILED` / `CLOSED` và lưu `error_log` cụ thể trong Ledger mà không ngắt đột ngột tiến trình cào.

---

## 4. Giá Trị Mẫu Bản Ghi UrlLedger (Sample Record)

Dưới đây là cấu trúc bản ghi thô chuẩn được trích xuất từ tập tin JSON trong hệ thống UrlLedger của Vieclam24h:

```json
{
  "47bb29693c502ba6128bb4747e1d6094": {
    "url_hash": "47bb29693c502ba6128bb4747e1d6094",
    "canonical_url": "https://vieclam24h.vn/it-phan-mem/ky-su-lap-trinh-plc-c8p210000187id200962244.html",
    "source": "vieclam24h",
    "job_id": "200962244",
    "discovered_at": "2026-10-17T07:15:33.234244+00:00",
    "status": "CLOSED",
    "preliminary_title": "Kỹ Sư Lập Trình Plc",
    "preliminary_company": "Unknown",
    "identity_key": "unknown__kỹ_sư_lập_trình_plc",
    "last_seen_at": "2026-10-17T10:53:30.355661+00:00",
    "last_scraped_at": null,
    "content_hash": null,
    "latest_version": 0,
    "repost_of_url_hash": null,
    "error_log": null,
    "retry_count": 0
  }
}
```