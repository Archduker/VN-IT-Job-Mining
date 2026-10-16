# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ (RAW CRAWL INVENTORY)

> **Người thực hiện:** [Tên thành viên]  
> **Nguồn phụ trách:** [Tên website, ví dụ: TopCV / TopDev / VietnamWorks ...]  
> **Nhánh Git:** `crawls/[tenweb]`  
> **Ngày hoàn thành cào:** [YYYY-MM-DD]  
> **Tổng số bài đăng cào được (Raw Records):** [Số lượng, ví dụ: 2,500]  
> **Đường dẫn thư mục MinIO / Local:** `minio://vn-it-jobs/raw/[source]/` hoặc `data/raw/[source]/`

---

## 1. Danh Sách 100% Trường Dữ Liệu Gốc Đã Thu Thập (Field Inventory)

| STT | Tên trường gốc (Key JSON / Selector Class) | Kiểu dữ liệu gốc | Tỷ lệ xuất hiện (%) | Tỷ lệ Null (%) | Ví dụ giá trị mẫu | Mô tả ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `box-header-job__title` | String | 100% | 0% | `"Senior Python Developer"` | Tiêu đề bài đăng |
| 2 | `box-header-job__salary--title` | String | 100% | 0% | `"Từ 25 - 40 triệu"` hoặc `"Thỏa thuận"` | Mức lương hiển thị trên tiêu đề |
| 3 | `company_name` | String | 100% | 0% | `"FPT Software"` | Tên công ty tuyển dụng |
| 4 | `job-detail__box--experience` | String | 92% | 8% | `"3 năm"` | Số năm kinh nghiệm yêu cầu |
| 5 | `badge_tags` | List[String] | 85% | 15% | `["Python", "Django", "Docker"]` | Thẻ kỹ năng / phúc lợi gắn kèm |
| 6 | `job-detail__box--description_html` | HTML String | 100% | 0% | `"<p>Mô tả công việc...</p>"` | Toàn văn mô tả công việc |
| 7 | `job-detail__box--requirements_html`| HTML String | 98% | 2% | `"<p>Yêu cầu ứng viên...</p>"` | Toàn văn yêu cầu ứng viên |
| 8 | `job-detail__box--benefits_html` | HTML String | 95% | 5% | `"<p>Quyền lợi được hưởng...</p>"` | Quyền lợi & đãi ngộ |
| 9 | `raw_deadline` | String | 78% | 22% | `"30/11/2026"` | Hạn nộp hồ sơ |
| ... | ... | ... | ... | ... | ... | ... |

*(Điền đầy đủ tất cả các trường mà nguồn của bạn có, không được bỏ sót bất kỳ trường nào)*

---

## 2. Thống Kê Cơ Chế CDC & Versioning

- **Số lượng tin mới hoàn toàn (Version 1 - NEW):** ... tin
- **Số lượng tin phát hiện có chỉnh sửa nội dung (Version > 1 - UPDATED):** ... tin
- **Số lượng tin giữ nguyên (ACTIVE - Unchanged):** ... tin
- **Số lượng tin đã đóng / hết hạn (CLOSED):** ... tin

---

## 3. Các Vấn Đề Kỹ Thuật Đã Gặp & Giải Pháp
- **Anti-bot / Rate limit:** (Mô tả nếu có bị chặn 429/403 và cách xử lý delay/header)
- **Cấu trúc DOM bất thường:** (Mô tả các bài đăng có layout khác biệt)
- **Tốc độ cào trung bình:** ... requests/giây hoặc ... phút/1000 tin.
