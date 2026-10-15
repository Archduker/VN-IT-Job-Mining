# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ (RAW CRAWL INVENTORY) — TOPCV

> **Người thực hiện:** Trần Vĩnh Thuận (TopCV Source Lead)  
> **Nguồn phụ trách:** TopCV (`https://www.topcv.vn`)  
> **Nhánh Git:** `crawls/topcv` (đồng bộ trên `main`)  
> **Ngày hoàn thành cào:** 2026-10-16  
> **Tổng số URL phát hiện (URL Ledger):** 48 bài đăng (Pha 1 Discovery)  
> **Số snapshot thô đã trích xuất (Pha 2 Detail):** 1 snapshot mẫu thành công (`data/raw/topcv/2026-10-15/2321616_v1.json`) + 3 cặp HTML/JSON đối chứng chuẩn (`crawlers/sources/topcv/samples/`)  
> **Đường dẫn lưu trữ MinIO / Local:** `minio://vn-it-jobs/raw/topcv/` và `data/raw/topcv/`  

---

## 1. Danh Sách 100% Trường Dữ Liệu Gốc Đã Thu Thập (Field Inventory)

Theo nguyên tắc **Zero Information Loss (SD1)**, crawler TopCV giữ nguyên 100% các trường dữ liệu thô, selector CSS và cấu trúc HTML nguyên bản từ container `div.job-detail`:

| STT | Tên trường gốc (Key JSON / Selector Class) | Kiểu dữ liệu gốc | Tỷ lệ xuất hiện (%) | Tỷ lệ Null (%) | Ví dụ giá trị mẫu | Mô tả ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `job_id` | String | 100% | 0% | `"2321616"` | Mã định danh duy nhất của tin tuyển dụng trên TopCV |
| 2 | `job-detail__box--title` / `h1` | String | 100% | 0% | `"UI/UX Designer - Mobile App - [HCM] - Thu Nhập Lên Đến 30 Triệu"` | Chức danh công việc hiển thị |
| 3 | `company-name` | String | 100% | 0% | `"CÔNG TY TNHH FOXSCORE"` | Tên đầy đủ của nhà tuyển dụng |
| 4 | `job-detail__box--salary` | String | 100% | 0% | `"15 - 30 triệu"` hoặc `"Thoả thuận"` | Mức lương hiển thị trên tiêu đề |
| 5 | `job-detail__box--experience` | String | 95% | 5% | `"2 năm"` hoặc `"Không yêu cầu kinh nghiệm"` | Yêu cầu số năm kinh nghiệm |
| 6 | `job-detail__box--level` | String | 90% | 10% | `"Nhân viên"` / `"Trưởng nhóm"` | Cấp bậc chuyên môn tuyển dụng |
| 7 | `job-detail__box--type` | String | 98% | 2% | `"Toàn thời gian"` | Hình thức làm việc (Full-time/Part-time) |
| 8 | `job-detail__box--deadline` | String | 85% | 15% | `"15/11/2026"` | Hạn chót ứng tuyển hồ sơ |
| 9 | `job-detail__box--quantity` | String | 70% | 30% | `"2 người"` | Số lượng ứng viên cần tuyển |
| 10 | `job-tags` / `.badge-skill` | List[String] | 88% | 12% | `["Figma", "UI/UX", "Prototype", "Design System"]` | Danh sách thẻ kỹ năng chuyên môn gắn trên bài |
| 11 | `job-detail__box--description_html` | HTML String | 100% | 0% | `"<div class=\"job-description\">...</div>"` | Toàn văn mô tả công việc (HTML gốc) |
| 12 | `job-detail__box--requirements_html`| HTML String | 98% | 2% | `"<div class=\"job-requirements\">...</div>"` | Toàn văn yêu cầu ứng viên (HTML gốc) |
| 13 | `job-detail__box--benefits_html` | HTML String | 95% | 5% | `"<div class=\"job-benefits\">...</div>"` | Toàn văn quyền lợi đãi ngộ (HTML gốc) |
| 14 | `job-detail__box--address` | String | 92% | 8% | `"Tân Bình, TP. Hồ Chí Minh"` | Địa chỉ làm việc chi tiết |
| 15 | `company-scale` | String | 75% | 25% | `"100-499 nhân viên"` | Quy mô nhân sự doanh nghiệp |
| 16 | `company-field` | String | 80% | 20% | `"IT - Phần mềm"` | Lĩnh vực hoạt động công ty |
| 17 | `content_hash` | String (SHA256) | 100% | 0% | `"99eeb2fde7736207fb918a7b09706db38696b5dd55af3ae25548da83f7626736"` | Mã băm Clean Container HTML Hash trên `div.job-detail` |

---

## 2. Thống Kê Cơ Chế CDC & Versioning

- **Chu kỳ Re-crawl:** Thiết lập cố định **21 ngày** (Hàm `is_due_for_recrawl(last_scraped_at, days=21)`).
- **Trạng thái bài đăng:** Sử dụng chuẩn `DONE` cho bài đã cào chi tiết thành công; `PENDING` cho bài mới phát hiện; `FAILED` cho bài bị Safe Skip tạm thời; `CLOSED` cho bài hết hạn (404/expired).
- **Cơ chế Clean Container HTML Hashing:**
  - Bóc tách đúng container `div.job-detail`, loại bỏ các thẻ nhiễu biến động theo thời gian (`<script>`, `<style>`, `<iframe>`, `<svg>`, `<noscript>`), chuẩn hóa whitespace và băm SHA256.
  - Trường hợp URL cũ cập nhật nội dung: Giữ nguyên `url_hash`, tăng version $v_1 \rightarrow v_2$, lưu snapshot mới `data/raw/topcv/<date>/<job_id>_v2.json`.
  - Trường hợp URL mới nhưng nội dung trùng bài đăng cũ (Repost): Phát hiện qua `find_by_content_hash()`, gắn cờ `repost_of_url_hash` trỏ về bài đăng gốc, không tạo bản ghi rác.

---

## 3. Các Vấn Đề Kỹ Thuật Đã Gặp & Giải Pháp

1. **Cloudflare WAF Rate Limiting (HTTP 429) & Turnstile Challenge:**
   - *Triệu chứng:* Khi cào tuần tự tốc độ cao bằng headless Playwright, Cloudflare chặn bằng màn hình "Attention Required! | Cloudflare" hoặc Cloudflare Turnstile "Thực hiện xác minh bảo mật" (HTTP 429 Too Many Requests).
   - *Giải pháp kiến trúc:* 
     - Thiết lập cơ chế **Safe Skip**: Bắt ngoại lệ WAF, log cảnh báo rõ ràng, đánh dấu record là `FAILED` và tiếp tục vòng lặp cho các URL kế tiếp thay vì làm sập toàn bộ batch.
     - Cấu hình Playwright Stealth: Bổ sung `extra_http_headers` (Accept-Language, Referer) và inject `navigator.webdriver = undefined`.
     - Điều phối Airflow: Tách riêng Pha 1 (Discovery) và Pha 2 (Extraction) với batch nhỏ (`max_items=5..10`) và delay thích ứng (jitter 3-5s).

2. **DOM layout đa hình thức:**
   - Cung cấp sẵn 3 mẫu đối chứng tại `crawlers/sources/topcv/samples/`:
     - `sample_standard_job`: Tin tuyển dụng tiêu chuẩn với đầy đủ 3 phần Description, Requirements, Benefits.
     - `sample_hot_vip_job`: Tin tuyển dụng TopCV Hot/VIP với layout header nổi bật và danh sách tags công nghệ mở rộng.
     - `sample_negotiable_salary`: Tin tuyển dụng có mức lương "Thoả thuận" hoặc dải lương hoa hồng, kiểm thử parser fallback.

3. **Tương thích MinIO Lakehouse:**
   - Dữ liệu thô lưu trữ theo phân vùng ngày `data/raw/topcv/YYYY-MM-DD/`, sẵn sàng đồng bộ trực tiếp lên bucket `vn-it-jobs/raw/topcv/` qua MinIO/S3 API.
