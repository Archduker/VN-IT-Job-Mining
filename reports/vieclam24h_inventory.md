# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ (RAW CRAWL INVENTORY) — VIECLAM24H

> **Người thực hiện:** Phúc (Vieclam24h Source Lead)
> **Nguồn phụ trách:** Việc Làm 24h (`https://vieclam24h.vn`)
> **Nhánh Git:** `crawls/vieclam24h` (merge vào `crawls/all`)
> **Ngày hoàn thành kiểm kê:** 2026-10-18
> **Tổng số URL phát hiện (URL Ledger):** 78 bài đăng (Pha 1 Discovery)
> **Số snapshot thô đã trích xuất (Pha 2 Detail):** 3 snapshot mẫu thành công + 3 cặp HTML/JSON đối chứng (`crawlers/sources/vieclam24h/samples/`)
> **Đường dẫn lưu trữ MinIO / Local:** `minio://vn-it-jobs/raw/vieclam24h/` và `data/raw/vieclam24h/`

---

## 1. Danh Sách 100% Trường Dữ Liệu Gốc Đã Thu Thập (Field Inventory)

| STT | Tên trường gốc | Kiểu dữ liệu gốc | Tỷ lệ xuất hiện (%) | Tỷ lệ Null (%) | Ví dụ giá trị mẫu | Mô tả ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `job_id` | String | 100% | 0% | `"20019283"` | Mã định danh tin tuyển dụng |
| 2 | `job_title` | String | 100% | 0% | `"Lập Trình Viên .NET / C# (Backend, SQL Server)"` | Tiêu đề công việc |
| 3 | `employer_name` | String | 100% | 0% | `"Công ty Cổ phần Giải pháp Phần mềm Á Đông"` | Tên công ty tuyển dụng |
| 4 | `salary_range` | String | 100% | 0% | `"15 - 25 triệu"` / `"Thỏa thuận"` | Mức lương hiển thị dạng chuỗi |
| 5 | `salary_min` / `max` | Float | 68% | 32% | `15000000` / `25000000` | Mức lương số thực chuẩn hóa |
| 6 | `city_names` | List[String] | 100% | 0% | `["Hà Nội"]` | Thành phố làm việc |
| 7 | `job_description` | HTML String | 100% | 0% | `"<div class="desc">...</div>"` | Nội dung mô tả công việc |
| 8 | `job_requirement` | HTML String | 98% | 2% | `"<div class="req">...</div>"` | Yêu cầu đối với ứng viên |
| 9 | `benefit` | HTML String | 92% | 8% | `"<div class="bene">...</div>"` | Quyền lợi được hưởng |
| 10 | `career_tags` | List[String] | 86% | 14% | `[".NET", "C#", "SQL Server", "ASP.NET"]` | Ngành nghề / thẻ kỹ năng |
| 11 | `experience` | String | 94% | 6% | `"2 năm kinh nghiệm"` | Số năm kinh nghiệm đòi hỏi |
| 12 | `working_form` | String | 96% | 4% | `"Toàn thời gian cố định"` | Hình thức làm việc |
| 13 | `deadline` | String | 88% | 12% | `"30/11/2026"` | Hạn nộp hồ sơ |
| 14 | `content_hash` | String (SHA256) | 100% | 0% | `"54ecfa7129..."` | Băm container sạch chống trùng lặp |

---

## 2. Thống Kê Cơ Chế CDC & Versioning

- **Chu kỳ Re-crawl:** Kiểm tra chu kỳ 21 ngày với `is_due_for_recrawl(last_scraped_at, days=21)`.
- **Trạng thái URL Ledger:** Duy trì 4 trạng thái `PENDING`, `DONE`, `FAILED`, `CLOSED`.
- **Safe Skip:** Tách biệt ngoại lệ kết nối mạng và parser, đảm bảo pipeline vận hành bền bỉ.
