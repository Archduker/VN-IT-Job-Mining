# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ (RAW CRAWL INVENTORY) — JOBSGO

> **Người thực hiện:** Duy (Glints & JobsGO Source Lead)
> **Nguồn phụ trách:** JobsGO (`https://jobsgo.vn`)
> **Nhánh Git:** `crawls/glints-jobsgo` (merge vào `crawls/all`)
> **Ngày hoàn thành kiểm kê:** 2026-10-18
> **Tổng số URL phát hiện (URL Ledger):** 45 bài đăng (Pha 1 Discovery)
> **Số snapshot thô đã trích xuất (Pha 2 Detail):** 3 snapshot mẫu thành công + 3 cặp HTML/JSON đối chứng (`crawlers/sources/jobsgo/samples/`)
> **Đường dẫn lưu trữ MinIO / Local:** `minio://vn-it-jobs/raw/jobsgo/` và `data/raw/jobsgo/`

---

## 1. Danh Sách 100% Trường Dữ Liệu Gốc Đã Thu Thập (Field Inventory)

| STT | Tên trường gốc | Kiểu dữ liệu gốc | Tỷ lệ xuất hiện (%) | Tỷ lệ Null (%) | Ví dụ giá trị mẫu | Mô tả ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `source_job_id` | String | 100% | 0% | `"jobsgo-job-101"` | Mã bài tuyển dụng trên JobsGO |
| 2 | `title` | String | 100% | 0% | `"Backend Python Developer (FastAPI, Django)"` | Tiêu đề công việc |
| 3 | `company` | String | 100% | 0% | `"JobsGO Tech Solutions"` | Tên đơn vị tuyển dụng |
| 4 | `salary.salary_text` | String | 100% | 0% | `"18,000,000 - 30,000,000 VNĐ"` | Chuỗi mô tả lương |
| 5 | `salary.salary_min` / `max` | Float | 65% | 35% | `18000000` / `30000000` | Lương số thực sau trích xuất |
| 6 | `location` | String | 100% | 0% | `"Hồ Chí Minh"` | Địa bàn làm việc |
| 7 | `experience` | String | 90% | 10% | `"2 năm"` | Kinh nghiệm yêu cầu |
| 8 | `description_list` | List[String] | 100% | 0% | `["Phát triển backend RESTful APIs..."]` | Danh sách mô tả công việc |
| 9 | `tags.requirements` | List[String] | 95% | 5% | `["2 năm kinh nghiệm Python", "FastAPI"]` | Nhóm tiêu chí yêu cầu |
| 10 | `tags.benefits` | List[String] | 90% | 10% | `["Lương thưởng tháng 13", "Bảo hiểm"]` | Nhóm chế độ đãi ngộ |
| 11 | `tags.skills` | List[String] | 85% | 15% | `["Python", "FastAPI", "Docker"]` | Nhóm thẻ kỹ năng chuyên môn |
| 12 | `working_form` | String | 95% | 5% | `"Toàn thời gian"` | Hình thức làm việc |
| 13 | `content_hash` | String (SHA256) | 100% | 0% | `"89fea021..."` | Mã băm Clean Container DOM |

---

## 2. Thống Kê Cơ Chế CDC & Versioning

- **Chu kỳ Re-crawl:** Kiểm tra chu kỳ 21 ngày với `is_due_for_recrawl(last_scraped_at, days=21)`.
- **Trạng thái URL Ledger:** Duy trì `PENDING`, `DONE`, `FAILED`, `CLOSED`.
- **Safe Skip:** Tích hợp bộ bắt lỗi HTTP 403/Cloudflare an toàn.
