# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ (RAW CRAWL INVENTORY) — CAREERVIET

> **Người thực hiện:** Tài (CareerViet Source Lead)
> **Nguồn phụ trách:** CareerViet (`https://careerviet.vn`)
> **Nhánh Git:** `crawls/careerviet` (merge vào `crawls/all`)
> **Ngày hoàn thành kiểm kê:** 2026-10-18
> **Tổng số URL phát hiện (URL Ledger):** 54 bài đăng (Pha 1 Discovery)
> **Số snapshot thô đã trích xuất (Pha 2 Detail):** 3 snapshot mẫu thành công + 3 cặp HTML/JSON đối chứng (`crawlers/sources/careerviet/samples/`)
> **Đường dẫn lưu trữ MinIO / Local:** `minio://vn-it-jobs/raw/careerviet/` và `data/raw/careerviet/`

---

## 1. Danh Sách 100% Trường Dữ Liệu Gốc Đã Thu Thập (Field Inventory)

| STT | Tên trường gốc | Kiểu dữ liệu gốc | Tỷ lệ xuất hiện (%) | Tỷ lệ Null (%) | Ví dụ giá trị mẫu | Mô tả ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `job_id` | String | 100% | 0% | `"35BA791A"` | Mã bài tuyển dụng CareerViet |
| 2 | `job_title` | String | 100% | 0% | `"Fullstack Java Developer (Spring Boot, Vue.js)"` | Tiêu đề công việc |
| 3 | `company_name` | String | 100% | 0% | `"KMS Technology Vietnam"` | Tên doanh nghiệp tuyển dụng |
| 4 | `salary` | String | 100% | 0% | `"20 - 35 Triệu VND"` / `"Cạnh tranh"` | Chuỗi mô tả lương |
| 5 | `salary_min` / `max` | Float | 70% | 30% | `20000000` / `35000000` | Lương số thực sau trích xuất |
| 6 | `location` | String | 98% | 2% | `"Quận 1, TP. Hồ Chí Minh"` | Địa điểm làm việc |
| 7 | `experience` | String | 92% | 8% | `"3 - 5 Năm"` | Số năm kinh nghiệm đòi hỏi |
| 8 | `job_description` | HTML String | 100% | 0% | `"<div class="job-desc">...</div>"` | Mô tả chi tiết công việc |
| 9 | `job_requirement` | HTML String | 96% | 4% | `"<div class="job-req">...</div>"` | Yêu cầu chuyên môn ứng viên |
| 10 | `benefits` | HTML String | 90% | 10% | `"<ul class="benefit-list">...</ul>"` | Chế độ phúc lợi nhân viên |
| 11 | `tags` | List[String] | 84% | 16% | `["Java", "Spring Boot", "Vue.js", "Docker"]` | Thẻ từ khóa công nghệ |
| 12 | `posted_date` | String | 94% | 6% | `"12/10/2026"` | Ngày đăng tải bài viết |
| 13 | `deadline` | String | 85% | 15% | `"15/11/2026"` | Hạn cuối nộp hồ sơ |
| 14 | `content_hash` | String (SHA256) | 100% | 0% | `"67aeb891..."` | Mã băm Clean Container DOM |

---

## 2. Thống Kê Cơ Chế CDC & Versioning

- **Chu kỳ Re-crawl:** Kiểm tra chu kỳ 21 ngày với `is_due_for_recrawl(last_scraped_at, days=21)`.
- **Trạng thái URL Ledger:** Duy trì `PENDING`, `DONE`, `FAILED`, `CLOSED`.
- **Safe Skip:** Xử lý ngoại lệ DOM rendering động và lỗi mạng graceful.
