# KIẾN TRÚC TÍCH HỢP ĐA NGUỒN (MASTER INTEGRATION SPECIFICATION - V2)
## VN-IT-Job-Mining: Phân Nhóm Chuẩn Hóa Theo Đề Xuất Mới

---

## 1. Triết lý Thiết kế Kiến trúc Mới

Dựa trên yêu cầu tái cấu trúc để tối ưu hóa cho các bước xử lý hạ nguồn (Transformation, Missing/Outlier, Feature Engineering & Data Mining), hệ thống phân tách schema tích hợp thành:
1. **Các Khóa Định danh Phẳng (Top-Level Flat Identifiers)**: Đứng độc lập ở cấp gốc, không bị nhốt trong nhóm con để làm khóa chính (Primary Keys) truy vấn đa sàn.
2. **Nhóm `company` (Độc lập)**: Tập trung toàn bộ thuộc tính của Doanh nghiệp / Nhà tuyển dụng (tên, quy mô, trụ sở, logo ảnh, website, lĩnh vực).
3. **6 Nhóm Nghiệp vụ Cốt lõi**: `địa điểm`, `skills`, `JD`, `salary`, `date`, `extract`.
4. **Nhóm `other` (Tính năng Bổ trợ)**: Lưu trữ các trường đặc thù, cờ trạng thái (flags), metadata phân loại ngành nghề từ sàn phục vụ các thuật toán lọc và phân cụm ở bước sau.

---

## 2. Bảng Schema Chi tiết Theo Phân Nhóm Mới

### Khóa Định danh Toàn cục (Top-Level Flat Identifiers - Không nhóm)
| Tên trường phẳng | Kiểu dữ liệu | Ý nghĩa |
| :--- | :--- | :--- |
| `job_id_global` | `str` | Khóa duy nhất toàn hệ thống (`<source>_<source_job_id>`) |
| `source_platform` | `str` | Tên sàn tuyển dụng (careerviet, glints, itviec, jobsgo, topcv, topdev, vieclam24h, vietnamworks) |
| `source_job_id` | `str` | Mã định danh gốc của bài đăng từ sàn |
| `source_url` | `str` | Đường dẫn trực tiếp đến tin tuyển dụng gốc |
| `crawled_at` | `str` | Thời điểm bot thu thập dữ liệu (ISO 8601) |

---

### Bảng 8 Nhóm Thuộc tính Tích hợp
| Nhóm | Tên trường | Kiểu dữ liệu | Ý nghĩa & Mô tả |
| :--- | :--- | :--- | :--- |
| **1. COMPANY** | `company_name` | `str / null` | Tên pháp nhân / công ty tuyển dụng |
| | `company_scale` | `str / null` | Quy mô nhân sự (ví dụ: '100-499 nhân viên') |
| | `company_address` | `str / null` | Địa chỉ trụ sở chính của công ty |
| | `company_url` | `str / null` | Website công ty hoặc link trang hồ sơ tuyển dụng |
| | `company_logo_image` *(Trường ẩn)* | `str / null` | URL ảnh đại diện / CDN Logo của doanh nghiệp |
| | `company_industry` | `str / null` | Lĩnh vực kinh doanh của doanh nghiệp |
| **2. ĐỊA ĐIỂM** | `raw_location_text` | `str / null` | Tỉnh/thành phố tóm tắt (Hà Nội, TP.HCM,...) |
| | `working_locations` | `list[str]` | Danh sách tất cả chi nhánh / điểm làm việc cụ thể |
| | `geo_coordinates` *(Trường ẩn)* | `dict / null` | Tọa độ GPS `{lat: float, lon: float}` nếu sàn cung cấp |
| **3. SKILLS** | `skills_list` | `list[str]` | Mảng danh sách các kỹ năng, công nghệ, ngôn ngữ IT |
| **4. JD** | `job_title` | `str` | Chức danh công việc tuyển dụng |
| | `raw_description_text` | `str / null` | Mô tả chi tiết nhiệm vụ và trách nhiệm |
| | `raw_requirements_text`| `str / null` | Yêu cầu năng lực, chuyên môn, kinh nghiệm |
| | `benefits_list` | `list[str]` | Mảng danh sách chế độ phúc lợi, đãi ngộ |
| **5. SALARY** | `raw_salary_text` | `str / null` | Chuỗi mức lương hiển thị nguyên bản |
| | `salary_currency` *(Trường ẩn)* | `str / null` | Đơn vị tiền tệ gốc ("VND", "USD") |
| | `is_salary_visible` *(Trường ẩn)*| `bool / null` | Cờ công khai lương hay thỏa thuận |
| **6. DATE** | `raw_posted_date` | `str / null` | Ngày đăng tuyển đầu tiên |
| | `raw_updated_at` | `str / null` | Ngày cập nhật tin tuyển dụng gần nhất |
| | `raw_deadline` | `str / null` | Hạn chót nhận hồ sơ ứng tuyển |
| **7. EXTRACT** | `raw_work_mode` | `str / null` | Hình thức làm việc (Onsite, Remote, Hybrid) |
| | `raw_seniority_text` | `str / null` | Cấp bậc chuyên môn (Intern, Junior, Senior, Lead,...) |
| | `raw_experience_text` | `str / null` | Số năm kinh nghiệm yêu cầu |
| | `raw_education_text` | `str / null` | Trình độ học vấn / Bằng cấp (Đại học, Cao đẳng,...) |
| | `raw_headcount` | `str / int / null`| Chỉ tiêu / số lượng tuyển dụng |
| | `raw_working_time` | `str / null` | Thời gian làm việc trong ngày/tuần (giờ hành chính...) |
| | `raw_age_text` | `str / null` | Giới hạn độ tuổi tuyển dụng |
| | `raw_gender_text` | `str / null` | Yêu cầu về giới tính |
| **8. OTHER** | `raw_category_text` | `str / null` | Ngành nghề / Phân loại vị trí từ sàn |
| | `is_content_image` *(Trường ảo)*| `bool / null` | Cờ nhận diện tin tuyển dụng là ảnh banner (TopDev) |
| | `auxiliary_features` | `dict / null` | Các cờ đặc thù (hot job, urgent, tracking, v.v.) |

---

## 3. Mục lục 8 Nguồn Dữ liệu Chi tiết

1. [`01_careerviet_integration_spec.md`](./01_careerviet_integration_spec.md)
2. [`02_glints_integration_spec.md`](./02_glints_integration_spec.md)
3. [`03_itviec_integration_spec.md`](./03_itviec_integration_spec.md)
4. [`04_jobsgo_integration_spec.md`](./04_jobsgo_integration_spec.md)
5. [`05_topcv_integration_spec.md`](./05_topcv_integration_spec.md)
6. [`06_topdev_integration_spec.md`](./06_topdev_integration_spec.md)
7. [`07_vieclam24h_integration_spec.md`](./07_vieclam24h_integration_spec.md)
8. [`08_vietnamworks_integration_spec.md`](./08_vietnamworks_integration_spec.md)
