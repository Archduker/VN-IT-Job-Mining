# JobsGO Crawl Samples & Field Mapping Guide

Thư mục này chứa bộ 3 mẫu HTML thô đại diện và 3 file JSON trích xuất tương ứng chuẩn DoD của nền tảng **JobsGO** (`jobsgo.vn`).

## Danh sách mẫu (3 cặp HTML + JSON)

1. **Chuẩn (Standard Job):**
   - HTML: `sample_standard_job.html`
   - JSON: `sample_standard_job.json`
   - Đặc điểm: Tin tuyển dụng tiêu chuẩn có khoảng lương cố định (VND), cấu trúc DOM thẻ `div.job-detail` cơ bản.

2. **HOT VIP / Tin nổi bật:**
   - HTML: `sample_hot_vip_job.html`
   - JSON: `sample_hot_vip_job.json`
   - Đặc điểm: Layout chứa huy hiệu VIP (`div.vip-badge`, `span.badge-vip`), mức lương cao, đãi ngộ bổ sung ESOP.

3. **Lương Thỏa thuận (Negotiable Salary):**
   - HTML: `sample_negotiable_salary.html`
   - JSON: `sample_negotiable_salary.json`
   - Đặc điểm: Mức lương thỏa thuận (`salary_min = None`, `salary_max = None`, `is_negotiable = True`), hình thức làm việc Remote/Hybrid.

## Quy tắc bóc tách và ánh xạ dữ liệu (Data Contract)
- **Zero Information Loss:** Lưu nguyên văn chuỗi HTML và trích xuất đầy đủ các trường chi tiết.
- **Tách 3 nhóm tags:**
  - `requirements`: Tiêu chí tuyển dụng từ `job-requirements`.
  - `benefits`: Chế độ đãi ngộ từ `job-benefits`.
  - `skills`: Danh sách từ khóa công nghệ trích xuất từ văn bản.
- **Xử lý lương:** Tách `salary_text`, quy đổi chuẩn min/max dạng số thực (`float`), gắn cờ `is_negotiable`.
