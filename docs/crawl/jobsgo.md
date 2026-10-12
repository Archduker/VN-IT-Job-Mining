# Báo Cáo Phân Tích & Bóc Tách Dữ Liệu Tuyển Dụng JobsGO (jobsgo.vn)

> **Mục tiêu tài liệu**:
> 1. Trình bày chi tiết luồng thu thập dữ liệu 2 giai đoạn (Listing -> Detail) cho nguồn JobsGO.
> 2. Phân tích cấu trúc DOM trang chi tiết việc làm CNTT, giải pháp vượt Cloudflare Turnstile bằng Playwright.
> 3. Chuẩn hóa dữ liệu theo Data Contract dự án VN-IT-Job-Mining (tiêu đề, công ty, lương lồng nhau, danh sách mô tả, yêu cầu, quyền lợi và các trường mở rộng trong `extra`).

---

## 1. Quy Trình Thu Thập Dữ Liệu 2 Giai Đoạn

```
[Giai đoạn 1: Quét Phân Trang Listing]
       │ Mở https://jobsgo.vn/viec-lam-cong-nghe-thong-tin.html(?page=N)
       │ Bật Playwright Stealth (webdriver = undefined)
       │ Thu thập danh sách Job IDs & URL (/viec-lam/<slug>-<id>.html)
       │ Tự dừng khi chạm trang cuối (li.next.disabled)
       ▼
[Giai đoạn 2: Lọc Trùng Lặp Checkpoint]
       │ Bỏ qua các job_id đã có trong CheckpointManager
       ▼
[Giai đoạn 3: Tải Trang Chi Tiết Job Detail]
       │ Truy cập URL chi tiết từng tin tuyển dụng
       │ Dùng domcontentloaded + wait 2.5s để vượt Cloudflare & tránh timeout
       ▼
[Giai đoạn 4: Bóc Tách DOM Bằng BeautifulSoup]
       │ Bóc tách Title, Company, Salary, Location, Deadline
       │ Chuẩn hóa Description, Requirements, Benefits thành list[str] sạch
       │ Trích xuất Skills tags và các trường mở rộng trong extra
       ▼
[Giai đoạn 5: Xuất File JSON Chuẩn Data Contract (JobRecord)]
```

---

## 2. Bảng Ánh Xạ Phần Tử DOM Sang Data Contract

| Trường dữ liệu | Vị trí Selector trên JobsGO | Xử lý & Chuẩn hóa |
|---|---|---|
| `_meta.source` | Cố định `"jobsgo"` | Nguồn định danh |
| `_meta.source_job_id` | Regex `[-_/](\d+)\.html` | ID tin tuyển dụng (ví dụ: `29277790532`) |
| `_meta.url` | Canonical URL | Làm sạch query tracking `ref_component` |
| `raw.title` | `h1.job-title, h1` | Text sạch tiêu đề |
| `raw.company` | `.card-company h6, h6.fw-semibold` | Tên công ty |
| `raw.salary` | `ul.job-info-list li:-soup-contains('Mức lương') strong` | `parse_salary_detail` $\rightarrow$ `JobSalary` lồng nhau |
| `raw.tags` | Thẻ chip `Kỹ năng:` | `JobTags(skills=[...], requirements=null, benefits=null)` |
| `raw.description_list` | `h3:-soup-contains('Mô tả') + div` | `text_to_clean_lines` (loại bỏ bullet `•`, `-`) |
| `raw.requirements_list` | `h3:-soup-contains('Yêu cầu') + div` | `text_to_clean_lines` (loại bỏ bullet `•`, `-`) |
| `raw.benefits_list` | `h3:-soup-contains('Quyền lợi') + div` | `text_to_clean_lines` (loại bỏ bullet `•`, `-`) |
| `raw.location_text` | `ul.job-info-list li:-soup-contains('Địa điểm') strong` | Tỉnh/Thành phố chính (e.g. `Hà Nội`) |
| `raw.deadline_text` | Thẻ `Hạn nộp hồ sơ:` | Ngày hết hạn sạch (bỏ đoạn `(Còn X ngày)`) |
| `raw.posted_date_text` | Sidebar `Ngày đăng tuyển:` | Ngày đăng (e.g. `09/10/2026`) |
| `raw.employment_type_text` | Sidebar `Loại hình:` | Loại hình (e.g. `Toàn thời gian`) |
| `raw.seniority_text` | Sidebar `Cấp bậc:` | Cấp bậc (e.g. `Nhân Viên/Chuyên Viên`) |
| `raw.extra` | Nhiều vị trí DOM | Xem chi tiết bên dưới 👇 |

---

## 3. Các Trường Mở Rộng Trong `raw.extra`

- `work_schedule`: Thời gian làm việc (ví dụ: `Từ Thứ 2 đến Thứ 6 (08:00 - 17:00)`).
- `education`: Bằng cấp yêu cầu (ví dụ: `Đại Học trở lên`).
- `experience`: Kinh nghiệm yêu cầu (ví dụ: `1 - 2 năm`).
- `hiring_quantity`: Số lượng tuyển dụng (ví dụ: `3`).
- `industry`: Lĩnh vực hoạt động công ty.
- `company_address`: Địa chỉ trụ sở công ty.
- `career`: Ngành nghề chi tiết (ví dụ: `Kiểm Thử Phần Mềm`).
- `detailed_location`: Địa điểm làm việc cụ thể chi tiết.

---

## 4. Kiểm Thử & Đảm Bảo Chất Lượng

Dữ liệu cào thực tế từ JobsGO được thẩm định qua `DataQualityChecker`:
- File mẫu: [`crawlers/sources/jobsgo/test_5_jobs.json`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/jobsgo/test_5_jobs.json)
- Tỷ lệ hợp lệ schema: **100%**
- Tỷ lệ duy nhất (unique rate): **100%**
- Unit test tự động: [`tests/unit/test_jobsgo_crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/tests/unit/test_jobsgo_crawler.py)
