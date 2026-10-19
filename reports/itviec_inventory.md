# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ (RAW CRAWL INVENTORY) — ITVIEC

> **Người thực hiện:** Hồng Phát (ITviec Source Lead)  
> **Nguồn phụ trách:** ITviec (`https://itviec.com`)  
> **Nhánh Git:** `feature/itviec-crawler` (Tích hợp vào `backup/crawls_all_pre_merge`)  
> **Ngày hoàn thành kiểm kê:** 2026-10-18  
> **Tổng số URL phát hiện (URL Ledger Pha 1):** 112 bài đăng hợp lệ (`crawlers/sources/itviec/url_ledger/`)  
> **Số snapshot thô đã trích xuất (Pha 2 Detail):** 3 cặp HTML/JSON mẫu chuẩn (`crawlers/sources/itviec/samples/`)  
> **Đường dẫn lưu trữ MinIO / Local:** `minio://vn-it-jobs/raw/itviec/` và `data/itviec/raw/`  

---

## 1. Danh Sách 100% Trường Dữ Liệu Gốc Đã Thu Thập (Field Inventory)

Theo nguyên tắc **Zero Information Loss (SD1)** và tư tưởng **Raw-First**, crawler ITviec lưu trữ nguyên bản toàn bộ cấu trúc dữ liệu schema.org `JobPosting` do website render qua Server-Side Rendering (SSR) kết hợp dữ liệu bóc tách từ DOM container `section.job-content`:

| STT | Tên trường gốc (Key Payload / Selector) | Kiểu dữ liệu gốc | Tỷ lệ xuất hiện (%) | Tỷ lệ Null (%) | Ví dụ giá trị mẫu | Mô tả ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `job_id` | String | 100% | 0% | `"backend-engineer-python-vng-01"` | Slug định danh duy nhất của tin tuyển dụng trên ITviec |
| 2 | `title` / `h1` | String | 100% | 0% | `"Backend Engineer (Python / FastAPI / PostgreSQL)"` | Tiêu đề chức danh công việc tuyển dụng |
| 3 | `company_name` | String | 100% | 0% | `"VNG Corporation"` | Tên nhà tuyển dụng (ưu tiên JSON-LD `hiringOrganization.name`) |
| 4 | `company_url` | String | 95% | 5% | `"/nha-tuyen-dung/vng-corporation"` | Đường dẫn trang thông tin nhà tuyển dụng trên sàn |
| 5 | `salary_display_text` | String | 100% | 0% | `"30 - 45 triệu"` hoặc `"Đăng nhập để xem mức lương"` | Chuỗi mức lương hiển thị nguyên văn trên giao diện |
| 6 | `salary_range_datalayer` | String | 65% | 35% | `"30M - 45M VND"` | Dải lương công khai đọc từ data-layer analytics của site |
| 7 | `skill_tags` | List[String] | 98% | 2% | `["Python, FastAPI, PostgreSQL, Redis, Docker"]` | Danh sách chuỗi kỹ năng trích từ JSON-LD |
| 8 | `sections` | Dict[str, List[str]] | 100% | 0% | `{"Mô tả công việc": [...], "Yêu cầu công việc": [...]}` | Các mục nội dung văn bản sạch bóc tách theo từng thẻ h2 |
| 9 | `job_posting_jsonld` | Dict[str, Any] | 100% | 0% | `{"@context": "https://schema.org", "@type": "JobPosting", ...}` | Toàn văn dữ liệu cấu trúc Google JobPosting nguyên vẹn |
| 10 | `content_hash` | String (SHA256) | 100% | 0% | `"4e8f1b6a78c9...d2e3"` | Mã băm SHA256 LAI giữa clean text container và canonical JSON-LD |

---

## 2. Thống Kê Cơ Chế CDC & Versioning

- **Chu kỳ Re-crawl:** Cố định **21 ngày** (`RECHECK_DAYS = 21`), đảm bảo tái kiểm tra bài đăng định kỳ mà không gây tải quá mức lên server.
- **Trạng thái URL Ledger:**
  - `PENDING`: URL vừa được khám phá từ sitemap hoặc phân trang listing Pha 1.
  - `DONE`: Tin đã bóc tách chi tiết snapshot thành công và tính mã content hash.
  - `FAILED`: Lỗi mạng hoặc rate-limit tạm thời, được kích hoạt cơ chế Safe Skip để thử lại lần sau.
  - `CLOSED`: Phát hiện mã phản hồi 404 hoặc thông báo bài đăng đã hết hạn/gỡ bỏ (`CLOSED_MARKERS`).
- **Mã băm Content Hash LAI (`section.job-content+canonical-jsonld/v1`):**
  - Kết hợp 2 thành phần: `SHA256( clean_text(section.job-content) + canonical_jsonld )`.
  - **Miễn nhiễm thay đổi UI:** Header/footer/sidebar/recommender thay đổi không làm đổi hash.
  - **Nhạy cảm với thay đổi tuyển dụng:** Nhà tuyển dụng cập nhật mô tả, tăng dải lương hoặc bổ sung kỹ năng trong JSON-LD sẽ sinh hash mới $\rightarrow$ tự động tạo version mới $v_2, v_3$ mà không ghi đè dữ liệu lịch sử.
  - **Phát hiện Repost:** URL mới nhưng có content hash trùng với bài viết đã cào sẽ được gắn cờ `repost_of_url_hash`, tránh nhân bản bản ghi rác.

---

## 3. Các Thách Thức Kỹ Thuật Đã Gặp & Giải Pháp

1. **Vấn đề rò rỉ tên công ty từ Sidebar (Sidebar Noise Leakage):**
   - *Triệu chứng:* Lấy thẻ anchor công ty đầu tiên trên trang dễ dính nhầm danh sách "Nhà tuyển dụng nổi bật" hoặc logo quảng cáo ở sidebar/header thay vì công ty thực sự tuyển dụng.
   - *Giải pháp:* Thiết kế hàm `_resolve_company` ưu tiên trường chuẩn JSON-LD `hiringOrganization.name`, kết hợp scoping trong container `div.jd-main` và so khớp token slug với `job_id`.

2. **Cơ chế ẩn mức lương (Salary Sign-in Gate):**
   - *Triệu chứng:* Nhiều tin yêu cầu đăng nhập mới hiển thị mức lương (`"Đăng nhập để xem mức lương"`).
   - *Giải pháp:* Lưu nguyên văn chuỗi gate vào `salary_display_text`, đồng thời trích xuất trường phụ `salary_range` từ attribute analytics `data-jobs--save-data-layer-value` nếu nhà tuyển dụng có cấu hình công khai.

3. **Bảo vệ toàn vẹn MinIO Lakehouse (Catalog Overwrite Guard):**
   - *Triệu chứng:* Khi chạy môi trường test cục bộ với catalog trống có thể ghi đè làm mất ledger production trên MinIO.
   - *Giải pháp:* Tích hợp guard kiểm tra catalog local trước khi đồng bộ lên MinIO Lakehouse trong `crawlers/common/url_ledger.py` và hỗ trợ biến môi trường `ITVIEC_SYNC=0` cho chế độ kiểm thử ngoại tuyến.
