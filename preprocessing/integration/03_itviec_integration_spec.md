# ĐẶC TẢ TÍCH HỢP NGUỒN: ITVIEC (03)
## Hệ thống Tiền xử lý & Khai thác Dữ liệu VN-IT-Job-Mining (Phân nhóm Mới)

---

## 1. Tổng quan Nguồn & Đặc tính Dữ liệu Thô

- **Tên nguồn (Source Platform)**: `itviec`
- **Kiểu dữ liệu cào (Payload Type)**: IT Specialized Portal + JSON-LD + DataLayer
- **Khóa Envelope chính**: `metadata` (hoặc `_meta`) và `raw_payload` (hoặc `raw`).
- **Tổng số trường thô ghi nhận**: ~8 trường cấp 1 (và các cấu trúc con lồng nhau).

---

## 2. Phân loại Ánh xạ Theo Kiến trúc Mới

### Khóa Định danh Phẳng (Top-Level Flat Identifiers)
- **`job_id_global`**: Khóa toàn cục kết hợp (`itviec_<id>`)
- **`source_platform`**: `itviec`
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


- **Thông tin công ty (`company`)**: `company_name`, `company_url` (hồ sơ sàn), và `company_logo_image` lấy từ `job_posting_jsonld.hiringOrganization.logo`.
- **Mức lương Min-Max cấu trúc (`salary`)**: Một số bài đăng có cấu trúc `baseSalary` trong JSON-LD với `currency`, `minValue`, `maxValue`.
- **Cấu trúc `sections` linh hoạt (`JD`)**: Chứa `Mô tả công việc`, `Yêu cầu công việc`, `Tại sao bạn sẽ yêu thích làm việc tại đây` (benefits).
- **Hình thức làm việc (`raw_work_mode`)**: Bóc tách từ `work_model` ('At office', 'Hybrid', 'Remote').
- **Nhóm `other`**: Lưu `specialization` (chuyên môn hóa: Backend/Frontend/DevOps) và `industries` phục vụ khai phá phân cụm.
        

---

## 4. Dữ liệu Mẫu Thực tế (Sample JSON Data)

### 4.1. Mẫu Envelope Thô Ban đầu (Raw JSON Envelope)
Lấy trực tiếp từ tệp: `data/itviec/raw/2026-10-19/ho-chi-minh-full-stack-developer-reactjs-nodejs-one-tech-stop-vietnam-company-ltd-2723_v1.json`

```json
{
  "metadata": {
    "job_id": "ho-chi-minh-full-stack-developer-reactjs-nodejs-one-tech-stop-vietnam-company-ltd-2723",
    "source": "itviec",
    "source_url": "https://itviec.com/viec-lam-it/ho-chi-minh-full-stack-developer-reactjs-nodejs-one-tech-stop-vietnam-company-ltd-2723",
    "scraped_at": "2026-10-19T16:18:51.756841+00:00",
    "scraper_version": "2.0.0",
    "version": 1,
    "content_hash": "11c449c33dc0209b7e5240f63774b78b3c711760f173aade667d97f7e65e64a3",
    "content_hash_algo": "section.job-content+canonical-jsonld/v1",
    "hash_container": "section.job-content",
    "hash_jsonld_fields": [
      "baseSalary",
      "description",
      "employmentType",
      "experienceRequirements",
      "hiringOrganization",
      "jobBenefits",
      "jobLocation",
      "skills",
      "title",
      "validThrough"
    ],
    "http_status": 200
  },
  "raw_payload": {
    "title": "[Ho Chi Minh] Full-Stack Developer (ReactJS/ NodeJS)",
    "company_name": "ONE Tech Stop Vietnam Company Ltd",
    "company_url": "/nha-tuyen-dung/one-tech-stop-vietnam-company-ltd",
    "salary_display_text": "Đăng nhập để xem mức lương",
    "skill_tags": [
      "NodeJS, HTML, ReactJS, NextJS, TypeScript, SQL"
    ],
    "salary_range_datalayer": null,
    "sections": {
      "3 Lý do để gia nhập công ty": [
        "Performance Bonus",
        "Health care program for staff & dependants",
        "Well-being program"
      ],
      "Mô tả công việc": [
        "The developer will be involved in all phases of the product development cycle including requirements analysis, project estimation, detailed design, software development, testing, and deployment.",
        "He/she has A Good Mindset for Development schedule/Quality/Self-Study and is willing to learn new technologies.",
        "What you will do",
        "Perform development & testing features/bugs from backlog items.",
        "Response quickly to handle incidents if it happens.",
        "Build and maintain the CI/CD.",
        "Be Involved in Quality Assurance with good processes, practices, and analysis tools.",
        "Be Involved in developing Non-Functional Requirements (e.g. Performance, Security, Reliability, Maintainability…)",
        "Assists leaders to define Technical Backlog",
        "Be Involved in defining Roadmap and Risk Management.",
        "Responsible for being committed to the results to be delivered by his/her team and assists his/her teams in achieving such results.",
        "Responsible for objectively and effectively communicating with his/her counterparts, leaders, and team members",
        "Responsible for providing his/her team with feedback on their work.",
        "Developing ideas for new programs, products, or features by monitoring industry developments and trends."
      ],
      "Yêu cầu công việc": [
        "We are looking for the one who:",
        "Having experience in Web Front-end (HTML/CSS/JS),",
        "NextJS or ReactJS",
        "Having experienc
... (truncated for readability)
```

### 4.2. Mẫu sau khi Tích hợp Chuẩn hóa (Tổ chức theo Kiến trúc Mới)
Bản ghi đã được phân loại rõ ràng theo Header phẳng + 8 nhóm thuộc tính:

```json
{
  "identifiers": {
    "job_id_global": "itviec_ho-chi-minh-full-stack-developer-reactjs-nodejs-one-tech-stop-vietnam-company-ltd-2723",
    "source_platform": "itviec",
    "source_job_id": "ho-chi-minh-full-stack-developer-reactjs-nodejs-one-tech-stop-vietnam-company-ltd-2723",
    "source_url": "https://itviec.com/viec-lam-it/ho-chi-minh-full-stack-developer-reactjs-nodejs-one-tech-stop-vietnam-company-ltd-2723",
    "crawled_at": "2026-10-19T16:18:51.756841+00:00"
  },
  "company": {
    "company_name": "ONE Tech Stop Vietnam Company Ltd",
    "company_scale": null,
    "company_address": "Tòa nhà ETOWN 6 - 364 Cộng Hòa, Phường Tân Bình",
    "company_url": "/nha-tuyen-dung/one-tech-stop-vietnam-company-ltd",
    "company_logo_image": "https://itviec.com/rails/active_storage/representations/proxy/eyJfcmFpbHMiOnsiZGF0YSI6NjA4NjQyNSwicHVyIjoiYmxvYl9pZCJ9fQ==--513fdacc2aa26e127770f0c982a5164b9a304d3c/eyJfcmFpbHMiOnsiZGF0YSI6eyJmb3JtYXQiOiJwbmciLCJyZXNpemVfdG9fZml0IjpbMTcwLG51bGxdfSwicHVyIjoidmFyaWF0aW9uIn19--f02e0eabf9f34431b8e6312d2e4f969eef4fa3a8/OTSV%20Logo%20Sticker.png",
    "company_industry": null
  },
  "location": {
    "raw_location_text": "Quận Tân Bình",
    "working_locations": [
      "Tòa nhà ETOWN 6 - 364 Cộng Hòa, Phường Tân Bình"
    ],
    "geo_coordinates": null
  },
  "skills": {
    "skills_list": [
      "NodeJS",
      "HTML",
      "ReactJS",
      "NextJS",
      "TypeScript",
      "SQL",
      "NodeJS, HTML, ReactJS, NextJS, TypeScript, SQL"
    ]
  },
  "jd": {
    "job_title": "[Ho Chi Minh] Full-Stack Developer (ReactJS/ NodeJS)",
    "raw_description_text": "The developer will be involved in all phases of the product development cycle including requirements analysis, project estimation, detailed design, software development, testing, and deployment.\nHe/she has A Good Mindset for Development schedule/Quality/Self-Study and is willing to learn new technologies.\nWhat you will do\nPerform development & testing features/bugs from backlog items.\nResponse quickly to handle incidents if it happens.\nBuild and maintain the CI/CD.\nBe Involved in Quality Assurance with good processes, practices, and analysis tools.\nBe Involved in developing Non-Functional Requirements (e.g. Performance, Security, Reliability, Maintainability…)\nAssists leaders to define Technical Backlog\nBe Involved in defining Roadmap and Risk Management.\nResponsible for being committed to the results to be delivered by his/her team and assists his/her teams in achieving such results.\nResponsible for objectively and effectively communicating with his/her counterparts, leaders, and team members\nResponsible for providing his/her team with feedback on their work.\nDeveloping ideas for new programs, products, or features by monitoring industry developments and trends.",
    "raw_requirements_text": "We are looking for the one who:\nHaving experience in Web Front-end (HTML/CSS/JS),\nNextJS or ReactJS\nHaving experience in backend technology of\nNodeJS and TypeScript\nand frameworks available for\nNestJS\nDatabase programming or design skills, including relational database skills (SQL, etc.) and non-relational database skills (MongoDB, Redis, Cassandra, etc.).\nCODING: The code should be well documented and compliant with good practices, as well as the testing skill (Unit Test, Integration Test, User Acceptance Test, Automation Regression Test.\nRESTful API\nKnowledge of Programming Principles, Design Patterns, etc;\nWilling to learn new technology and have a product mindset.\nNice to have:\nExperience in cloud architecture/infrastructure, especially on GCP\nExperience with Docker;\nKnowledge about Continuous Integration, Continuous Delivery (CI/CD);\nFamiliar with working in an Agile environment;",
    "benefits_list": [
      "Performance Bonus",
      "Health care program for staff & dependants",
      "Well-being program",
      "More on OTSV – what is it like to work in OTSV?",
      "At OTSV, work is a form of self-fulfillment, we encourage staff to leave their comfort zone, think out of the box, and share their ideas without hesitation. As a team, we analyze and evaluate issues objectively to learn quickly from mistakes. We believe in ‘fail quick, success quick’ and strive to keep pace with the forefront of technology to digitize ONE’s business.",
      "In line with the Agile methodology, we have an open office concept with lots of meeting areas for spontaneous team meetings.",
      "We aim to make our staff feel as comfortable in the office as they would feel at home.",
      "You will love working here!",
      "Competitive salary",
      "Annual Increment",
      "13th-month salary",
      "Social Security co-contribution based on full gross salary",
      "Premium health care (Bao Viet Insurance) for employees & dependents (parents or spouse and children).",
      "Lunch allowance",
      "Free drinks, breakfast, and snacks.",
      "17 days of Annual Leave",
      "Annual health screening reimbursement: Up to 4,700,000 VND",
      "Well-being allowance: 13,800,000VND/year",
      "Training and education sponsorship: 38,000,000VND/year",
      "We value Teamwork and organization",
      "Team meals, gatherings, and other recreational and team bonding activities regularly."
    ]
  },
  "salary": {
    "raw_salary_text": "Đăng nhập để xem mức lương",
    "salary_currency": "VND",
    "is_salary_visible": true
  },
  "date": {
    "raw_posted_date": "2026-10-08",
    "raw_updated_at": null,
    "raw_deadline": "2026-11-12"
  },
  "extract": {
    "raw_work_mode": null,
    "raw_seniority_text": null,
    "raw_experience_text": "3.1 năm (37 tháng)",
    "raw_education_text": null,
    "raw_headcount": null,
    "raw_working_time": null,
    "raw_age_text": null,
    "raw_gender_text": null
  },
  "other": {
    "raw_category_text": "Information Technology",
    "is_content_image": null,
    "auxiliary_features": {}
  }
}
```

---
*Tài liệu được cập nhật theo quy chuẩn Kiến trúc Mới của VN-IT-Job-Mining.*
