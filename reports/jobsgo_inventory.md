# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ (RAW CRAWL INVENTORY) — JOBSGO

> **Nguồn phụ trách:** JobsGO (`https://jobsgo.vn`)
> **Kiến trúc:** Two-Phase Decoupled Crawler kết hợp Dual-Engine (`curl_cffi` + `playwright`)
> **Chuẩn dữ liệu:** Zero Information Loss (SD1) & Data Contract
> **Đặc tả trường:** Bóc tách 100% trường dữ liệu theo `neccessary.md`
> **Đường dẫn lưu trữ:** `minio://vn-it-jobs/url_ledger/jobsgo/` và `minio://vn-it-jobs/raw/jobsgo/`

---

## 1. Bảng Kiểm Kê Chi Tiết 100% Trường Dữ Liệu Bóc Tách (Zero Information Loss)

| STT | Tên trường trong `raw_payload` | Kiểu dữ liệu | Tỷ lệ hiện diện | Tỷ lệ Null | Giá trị mẫu đối soát (`neccessary.md`) | Ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `title` | String | 100% | 0% | `"Kỹ Sư Tích Hợp IoT - Lương Cứng Từ 25 - 35 Triệu..."` | Tiêu đề bài tuyển dụng |
| 2 | `company` | String | 100% | 0% | `"Công Ty Cổ Phần Fsi Việt Nam"` | Tên đơn vị tuyển dụng |
| 3 | `company_field` | String | 95% | 5% | `"Kinh doanh, xuất nhập khẩu hóa chất và thiết bị điện."` | Lĩnh vực hoạt động doanh nghiệp |
| 4 | `company_address` | String | 90% | 10% | `"Số 226 Võ Chí Công, phường Xuân La, quận Tây Hồ..."` | Địa chỉ trụ sở công ty |
| 5 | `salary_raw` | String | 100% | 0% | `"35 - 40 triệu VNĐ"` / `"Thỏa thuận"` | Mức lương thô nguyên bản |
| 6 | `location` | String | 100% | 0% | `"Hà Nội"` | Tỉnh / Thành phố làm việc chung |
| 7 | `experience` | String | 98% | 2% | `"Trên 3 năm"` | Số năm kinh nghiệm yêu cầu |
| 8 | `education` | String | 95% | 5% | `"Đại Học trở lên"` | Trình độ học vấn / Bằng cấp |
| 9 | `deadline_raw` | String | 98% | 2% | `"04/11/2026 (Còn 15 ngày)"` | Hạn nộp hồ sơ ứng tuyển |
| 10 | `working_time` | String | 90% | 10% | `"Từ Thứ 2 đến Thứ 6 (08:00 - 17:15), Thứ 7 (08:00 - 12:00)"` | Thời gian làm việc trong tuần |
| 11 | `working_places` | List[String] | 95% | 5% | `["Số 226 Võ Chí Công... (Trước sáp nhập: ... | Sau sáp nhập: ...)"]` | Địa chỉ làm việc chi tiết kèm ghi chú sáp nhập |
| 12 | `occupations` | List[String] | 98% | 2% | `["Lập Trình - Phát Triển Phần Mềm", "Cơ Điện - M&E", "Điện Tử - Vi Mạch - Bán Dẫn"]` | Danh sách ngành nghề liên quan |
| 13 | `description_bullets` | List[String] | 100% | 0% | 5 gạch đầu dòng mô tả công việc | Các nhiệm vụ và trách nhiệm chính |
| 14 | `requirements_bullets`| List[String] | 100% | 0% | 6 gạch đầu dòng yêu cầu công việc | Kỹ năng, công nghệ, kinh nghiệm |
| 15 | `benefits_bullets` | List[String] | 100% | 0% | 7 gạch đầu dòng quyền lợi | Lương thưởng, đào tạo, bảo hiểm |
| 16 | `general_info.employment_type` | String | 100% | 0% | `"Toàn thời gian"` | Hình thức làm việc |
| 17 | `general_info.job_level` | String | 98% | 2% | `"Nhân Viên/Chuyên Viên"` | Cấp bậc chuyên môn |
| 18 | `general_info.posted_date` | String | 100% | 0% | `"05/10/2026"` | Ngày đăng tin tuyển dụng |
| 19 | `general_info.hiring_quantity` | String | 95% | 5% | `"2"` | Số lượng ứng viên cần tuyển |

---

## 2. Kiểm Soát Metadata, Tính Toàn Vẹn & Quản Lý Phiên Bản (CDC)

- **Trường `metadata.content_hash`:**
  - Băm SHA-256 trên toàn vẹn chuỗi Canonical JSON của `raw_payload`.
  - Tuân thủ quy tắc: **chỉ lưu duy nhất 1 trường `content_hash`** trong `metadata`.
- **Trường `metadata.language`:** Nhận diện tự động `"vi"` hoặc `"en"` qua `detect_language`.
- **Phát hiện bài đăng trùng lặp (Repost Detection):** Đối soát `content_hash` trong URL Ledger. Nếu trùng nội dung với bài đăng khác, ghi nhận liên kết `repost_of_url_hash` mà không sinh snapshot mới để tối ưu dung lượng Lakehouse.
- **Chu kỳ Re-crawl:** Thiết lập mốc 21 ngày với cơ chế `is_due_for_recrawl`.
