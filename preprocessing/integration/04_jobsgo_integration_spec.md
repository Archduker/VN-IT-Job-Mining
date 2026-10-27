# ĐẶC TẢ TÍCH HỢP NGUỒN: JOBSGO (04)
## Hệ thống Tiền xử lý & Khai thác Dữ liệu VN-IT-Job-Mining (Phân nhóm Mới)

---

## 1. Tổng quan Nguồn & Đặc tính Dữ liệu Thô

- **Tên nguồn (Source Platform)**: `jobsgo`
- **Kiểu dữ liệu cào (Payload Type)**: Structured HTML Payload (Bullets mảng + General Info)
- **Khóa Envelope chính**: `metadata` (hoặc `_meta`) và `raw_payload` (hoặc `raw`).
- **Tổng số trường thô ghi nhận**: ~16 trường cấp 1 (và các cấu trúc con lồng nhau).

---

## 2. Phân loại Ánh xạ Theo Kiến trúc Mới

### Khóa Định danh Phẳng (Top-Level Flat Identifiers)
- **`job_id_global`**: Khóa toàn cục kết hợp (`jobsgo_<id>`)
- **`source_platform`**: `jobsgo`
- **`source_job_id`**: Mã ID tin tuyển dụng từ sàn
- **`source_url`**: Đường link bài đăng gốc
- **`crawled_at`**: Thời gian cào bài đăng

---

### Bảng Phân Nhóm Thuộc Tính
1. **Nhóm `company` (Doanh nghiệp Tuyển dụng)**:
   - `company_name`: Tên công ty
   - `company_scale`: Quy mô nhân sự công ty
   - `company_address`: Trụ sở chính công ty
   - `company_url`: Website / Trang tuyển dụng của công ty
   - `company_logo_image`: Link CDN ảnh logo công ty
   - `company_industry`: Lĩnh vực hoạt động kinh doanh

2. **Nhóm `địa điểm` (Location)**:
   - `raw_location_text`: Tỉnh/thành phố tóm tắt
   - `working_locations`: Mảng danh sách tất cả chi nhánh / điểm làm việc cụ thể
   - `geo_coordinates` *(Trường ẩn)*: Tọa độ GPS `{lat, lon}` nếu có

3. **Nhóm `skills` (Kỹ năng Công nghệ)**:
   - `skills_list`: Mảng các từ khóa kỹ năng, công nghệ, framework, tool IT

4. **Nhóm `JD` (Mô tả, Yêu cầu & Quyền lợi)**:
   - `job_title`: Tiêu đề công việc
   - `raw_description_text`: Mô tả chi tiết trách nhiệm
   - `raw_requirements_text`: Yêu cầu năng lực ứng viên
   - `benefits_list`: Danh sách các chế độ phúc lợi, đãi ngộ

5. **Nhóm `salary` (Lương & Tiền tệ)**:
   - `raw_salary_text`: Chuỗi mức lương hiển thị gốc
   - `salary_currency`: Đơn vị tiền tệ (VND / USD)
   - `is_salary_visible`: Cờ công khai lương hay thỏa thuận

6. **Nhóm `date` (Thời gian Tuyển dụng)**:
   - `raw_posted_date`: Ngày đăng tuyển
   - `raw_updated_at`: Ngày cập nhật tin tuyển dụng
   - `raw_deadline`: Hạn chót nộp hồ sơ

7. **Nhóm `extract` (Trường Ẩn / Phái sinh Tuyển dụng)**:
   - `raw_work_mode`: Onsite / Remote / Hybrid
   - `raw_seniority_text`: Cấp bậc chuyên môn
   - `raw_experience_text`: Số năm kinh nghiệm
   - `raw_education_text`: Trình độ học vấn / Bằng cấp
   - `raw_headcount`: Chỉ tiêu số lượng tuyển
   - `raw_working_time`: Giờ giấc làm việc
   - `raw_age_text`: Giới hạn độ tuổi
   - `raw_gender_text`: Yêu cầu giới tính

8. **Nhóm `other` (Tính năng Bổ trợ & Bước Tiếp theo)**:
   - `raw_category_text`: Ngành nghề bài đăng từ sàn
   - `is_content_image`: Cờ bài đăng bằng ảnh banner đồ họa
   - `auxiliary_features`: Các cờ trạng thái và metadata hỗ trợ phân tích bước tiếp theo

---

## 3. Khai thác Trường Ẩn & Trường Ảo Đặc thù


- **Thông tin công ty (`company`)**: `company` (tên), `company_field` (lĩnh vực), `company_address` (địa chỉ trụ sở).
- **Địa giới hành chính sáp nhập (`địa điểm`)**: Trường `working_places` lưu thông tin địa chỉ trước và sau sáp nhập (`Gia Lâm, Hà Nội (Trước sáp nhập: ... | Sau sáp nhập: ...)`).
- **Trường ẩn trong `general_info` (`extract`)**: `hiring_quantity` (chỉ tiêu), `job_level` (cấp bậc), `employment_type`.
- **Thời gian làm việc cố định (`raw_working_time`)**: Nằm trong trường `working_time`.
- **Nhóm `other`**: Lưu `occupations` (mảng nhóm nghề) hỗ trợ lọc dữ liệu IT đa chuyên ngành.
        

---

## 4. Dữ liệu Mẫu Thực tế (Sample JSON Data)

### 4.1. Mẫu Envelope Thô Ban đầu (Raw JSON Envelope)
Lấy trực tiếp từ tệp: `data/jobsgo/raw/2026-10-20/29104590387_v1.json`

```json
{
  "metadata": {
    "job_id": "29104590387",
    "source": "jobsgo",
    "source_url": "https://jobsgo.vn/viec-lam/ky-su-tu-dong-hoa-lap-trinh-plc-hmi-robot-gia-lam-ha-noi-29104590387.html",
    "scraped_at": "2026-10-20T20:13:35.513388+00:00",
    "scraper_version": "1.0.0",
    "version": 1,
    "language": "vi",
    "content_hash": "5c0f03c234ccd10067dc306c7b9b89ef32d237681bd22e24f253121e254cfe91"
  },
  "raw_payload": {
    "title": "Kỹ Sư Tự Động Hóa – Lập Trình PLC/HMI – Robot | Gia Lâm, Hà Nội",
    "company": "Công Ty Cổ Phần Chế Tạo Và Dịch Vụ Máy Công Nghiệp M-Sei",
    "company_field": "Kinh doanh",
    "company_address": "Số nhà 11D, ngách 80/14/31, tổ 2, phố Hoa Lâm, Phường Việt Hưng, Quận Long Biên, Thành phố Hà Nội, Việt Nam",
    "salary_raw": "12 - 20 triệu VNĐ",
    "location": "Hà Nội",
    "experience": "Không yêu cầu",
    "education": "Cao Đẳng trở lên",
    "deadline_raw": "29/10/2026 (Còn 8 ngày)",
    "working_time": "",
    "working_places": [
      "Gia Lâm, Hà Nội (Trước sáp nhập:Gia Lâm, Hà Nội |Sau sáp nhập:Gia Lâm, Hà Nội)"
    ],
    "occupations": [
      "Điện - Điện Công Nghiệp",
      "Phần Cứng - Lập Trình Nhúng",
      "Tự Động Hóa - Robot",
      "Cơ Khí - Chế Tạo Máy",
      "Cơ Điện Tử"
    ],
    "description_bullets": [
      "Thiết kế, lập trình, triển khai giải pháp tự động hóa cho khách hàng: robot công nghiệp, dây chuyền CNC, hệ thống điều khiển.",
      "Lập trình PLC, HMI; kết nối, đồng bộ dữ liệu giữa robot - máy CNC - hệ thống điều khiển.",
      "Tham gia các dự án chuyển giao công nghệ, đào tạo vận hành cho khách hàng.",
      "Nghiên cứu, cập nhật công nghệ tự động hóa mới để tư vấn giải pháp phù hợp"
    ],
    "requirements_bullets": [
      "Tốt nghiệp Đại học chuyên ngành Tự động hóa, Cơ điện tử, Điện - Điện tử hoặc chuyên ngành liên quan.",
      "Sinh viên mới ra trường có nền tảng tốt hoặc đã có kinh nghiệm lập trình PLC/robot công nghiệp.",
      "Ưu tiên ứng viên tốt nghiệp Đại học Bách Khoa Hà Nội hoặc các trường kỹ thuật uy tín khác.",
      "Tư duy logic tốt, khả năng tự học công nghệ mới nhanh.",
      "Đọc hiểu tài liệu kỹ thuật tiếng Anh"
    ],
    "benefits_bullets": [
      "Mức lương: Thỏa thuận theo năng lực.",
      "Được đào tạo bài bản về CNC, robot công nghiệp, hệ điều khiển Syntec/SZGH ngay từ đầu.",
      "Tham gia BHXH, BHYT, BHTN theo quy định của Nhà nước.",
      "Thưởng Lễ, Tết, thưởng theo hiệu quả công việc.",
      "Môi trường làm việc trẻ, năng động; lộ trình thăng tiến rõ ràng theo năng lực.",
      "Có cơ hội tham gia đào tạo, học tập thực tế tại đối tác nước ngoài (như các đợt đào tạo tại SZGH)"
    ],
    "general_info": {
      "employment_type": "Toàn thời gian",
      "job_level": "Nhân Viên/Chuyên Viên",
      "posted_date": "29/09/2026",
      "hiring_quantity": ""
    }
  }
}
... (truncated for readability)
```

### 4.2. Mẫu sau khi Tích hợp Chuẩn hóa (Tổ chức theo Kiến trúc Mới)
Bản ghi đã được phân loại rõ ràng theo Header phẳng + 8 nhóm thuộc tính:

```json
{
  "identifiers": {
    "job_id_global": "jobsgo_29104590387",
    "source_platform": "jobsgo",
    "source_job_id": "29104590387",
    "source_url": "https://jobsgo.vn/viec-lam/ky-su-tu-dong-hoa-lap-trinh-plc-hmi-robot-gia-lam-ha-noi-29104590387.html",
    "crawled_at": "2026-10-20T20:13:35.513388+00:00"
  },
  "company": {
    "company_name": "Công Ty Cổ Phần Chế Tạo Và Dịch Vụ Máy Công Nghiệp M-Sei",
    "company_scale": null,
    "company_address": "Số nhà 11D, ngách 80/14/31, tổ 2, phố Hoa Lâm, Phường Việt Hưng, Quận Long Biên, Thành phố Hà Nội, Việt Nam",
    "company_url": null,
    "company_logo_image": null,
    "company_industry": "Kinh doanh"
  },
  "location": {
    "raw_location_text": "Hà Nội",
    "working_locations": [
      "Gia Lâm, Hà Nội (Trước sáp nhập:Gia Lâm, Hà Nội |Sau sáp nhập:Gia Lâm, Hà Nội)"
    ],
    "geo_coordinates": null
  },
  "skills": {
    "skills_list": [
      "Điện - Điện Công Nghiệp",
      "Phần Cứng - Lập Trình Nhúng",
      "Tự Động Hóa - Robot",
      "Cơ Khí - Chế Tạo Máy",
      "Cơ Điện Tử"
    ]
  },
  "jd": {
    "job_title": "Kỹ Sư Tự Động Hóa – Lập Trình PLC/HMI – Robot | Gia Lâm, Hà Nội",
    "raw_description_text": "Thiết kế, lập trình, triển khai giải pháp tự động hóa cho khách hàng: robot công nghiệp, dây chuyền CNC, hệ thống điều khiển.\nLập trình PLC, HMI; kết nối, đồng bộ dữ liệu giữa robot - máy CNC - hệ thống điều khiển.\nTham gia các dự án chuyển giao công nghệ, đào tạo vận hành cho khách hàng.\nNghiên cứu, cập nhật công nghệ tự động hóa mới để tư vấn giải pháp phù hợp",
    "raw_requirements_text": "Tốt nghiệp Đại học chuyên ngành Tự động hóa, Cơ điện tử, Điện - Điện tử hoặc chuyên ngành liên quan.\nSinh viên mới ra trường có nền tảng tốt hoặc đã có kinh nghiệm lập trình PLC/robot công nghiệp.\nƯu tiên ứng viên tốt nghiệp Đại học Bách Khoa Hà Nội hoặc các trường kỹ thuật uy tín khác.\nTư duy logic tốt, khả năng tự học công nghệ mới nhanh.\nĐọc hiểu tài liệu kỹ thuật tiếng Anh",
    "benefits_list": [
      "Mức lương: Thỏa thuận theo năng lực.",
      "Được đào tạo bài bản về CNC, robot công nghiệp, hệ điều khiển Syntec/SZGH ngay từ đầu.",
      "Tham gia BHXH, BHYT, BHTN theo quy định của Nhà nước.",
      "Thưởng Lễ, Tết, thưởng theo hiệu quả công việc.",
      "Môi trường làm việc trẻ, năng động; lộ trình thăng tiến rõ ràng theo năng lực.",
      "Có cơ hội tham gia đào tạo, học tập thực tế tại đối tác nước ngoài (như các đợt đào tạo tại SZGH)"
    ]
  },
  "salary": {
    "raw_salary_text": "12 - 20 triệu VNĐ",
    "salary_currency": "VND",
    "is_salary_visible": true
  },
  "date": {
    "raw_posted_date": "29/09/2026",
    "raw_updated_at": null,
    "raw_deadline": "29/10/2026 (Còn 8 ngày)"
  },
  "extract": {
    "raw_work_mode": null,
    "raw_seniority_text": "Nhân Viên/Chuyên Viên",
    "raw_experience_text": "Không yêu cầu",
    "raw_education_text": "Cao Đẳng trở lên",
    "raw_headcount": null,
    "raw_working_time": null,
    "raw_age_text": null,
    "raw_gender_text": null
  },
  "other": {
    "raw_category_text": "Điện - Điện Công Nghiệp, Phần Cứng - Lập Trình Nhúng, Tự Động Hóa - Robot, Cơ Khí - Chế Tạo Máy, Cơ Điện Tử",
    "is_content_image": null,
    "auxiliary_features": {
      "occupations": [
        "Điện - Điện Công Nghiệp",
        "Phần Cứng - Lập Trình Nhúng",
        "Tự Động Hóa - Robot",
        "Cơ Khí - Chế Tạo Máy",
        "Cơ Điện Tử"
      ]
    }
  }
}
```

---
*Tài liệu được cập nhật theo quy chuẩn Kiến trúc Mới của VN-IT-Job-Mining.*
