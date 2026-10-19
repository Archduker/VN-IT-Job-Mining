# ITViec Job Samples Overview (DoD Deliverable TC4)

Thư mục này chứa 3 cặp file mẫu đối chứng đại diện cho 3 cấu trúc bài đăng tuyển dụng thực tế trên sàn **ITviec** (`https://itviec.com`), phục vụ kiểm thử đơn vị, thẩm định bộ bóc tách (parser) và nghiệm thấu chuẩn đầu ra (Definition of Done):

---

## 1. Danh Sách Các Cặp File Mẫu

### 1. `sample_standard_job.html` & `sample_standard_job.json`
- **Loại hình:** Tin tuyển dụng tiêu chuẩn (Standard Job).
- **Đặc điểm:** Mức lương công khai bằng VNĐ (`30 - 45 triệu`), cấu trúc thẻ `h1`, `div.employer-name`, khối `section.job-content` chứa đầy đủ 3 mục tiêu chuẩn: *Mô tả công việc*, *Yêu cầu công việc*, và *Tại sao bạn sẽ yêu thích làm việc tại đây*.
- **JSON-LD:** Nhúng đầy đủ cấu trúc `@type: JobPosting` với `baseSalary` (VND: 30,000,000 - 45,000,000).

### 2. `sample_hot_vip_job.html` & `sample_hot_vip_job.json`
- **Loại hình:** Tin tuyển dụng Hot / VIP / Spotlight (`HOT / VIP JOB`).
- **Đặc điểm:** Header nổi bật với badge VIP `div.vip-spotlight` và dải lương công khai bằng USD (`2,500 - 3,500 USD`). Cung cấp danh sách kỹ năng chuyên môn sâu (Cloud/DevOps/IaC) và các chế độ đãi ngộ quốc tế mở rộng.
- **JSON-LD:** Chứa `baseSalary` (USD: 2,500 - 3,500) và đầy đủ danh mục `skills`.

### 3. `sample_negotiable_salary.html` & `sample_negotiable_salary.json`
- **Loại hình:** Tin tuyển dụng có mức lương ẩn / Thỏa thuận (Gate / Negotiable Salary).
- **Đặc điểm:** Mức lương hiển thị là `"Đăng nhập để xem mức lương"` (chuỗi gate đặc trưng của ITViec). Kiểm thử khả năng bắt fallback an toàn, không sinh lỗi parse lương hay crash crawler.
- **JSON-LD:** Cấu trúc JobPosting chuẩn, trường `baseSalary` để `null`/thỏa thuận theo đúng nguyên tắc Raw-First.

---

## 2. Hướng Dẫn Mapping Selectors & Trích Xuất Dữ Liệu

| Trường thông tin | Selector CSS / Nguồn dữ liệu | Cơ chế bóc tách & Fallback |
| :--- | :--- | :--- |
| **Tiêu đề (`title`)** | `h1` hoặc `h1.job-details__title` | Ưu tiên thẻ `h1` trong DOM; fallback sang `jsonld["title"]`. |
| **Công ty (`company_name`)** | JSON-LD `hiringOrganization.name` hoặc `div.employer-name` | Ưu tiên JSON-LD chính xác, chống dính sidebar "Nhà tuyển dụng nổi bật". |
| **URL Công ty (`company_url`)** | Anchor trong `div.employer-name` hoặc `div.jd-main` | So khớp token slug hoặc text tên công ty; trả về `null` nếu không có cơ sở. |
| **Lương hiển thị (`salary_display_text`)** | `[class*='salary' i]` | Lọc bỏ link khảo sát/báo cáo lương; nhận diện token triệu/usd/thỏa thuận. |
| **Dải lương Data Layer (`salary_range`)** | Attribute `data-jobs--save-data-layer-value` | Đọc JSON data-layer phân tích công khai từ `div.jd-main`. |
| **Phần nội dung (`sections`)** | `section.job-content` -> `h2` + các thẻ con | Trích xuất dạng từ điển các mảng chuỗi văn bản sạch (bullet lines). |
| **JSON-LD gốc (`job_posting_jsonld`)** | `script[type="application/ld+json"]` | Bảo toàn nguyên vẹn cấu trúc JSON-LD `@type=JobPosting` (Zero Information Loss). |
| **Content Hash (`content_hash`)** | `section.job-content` + Canonical JSON-LD | Mã băm SHA256 lai phát hiện biến động nội dung hoặc repost. |
