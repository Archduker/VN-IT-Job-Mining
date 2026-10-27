# ĐẶC TẢ TÍCH HỢP NGUỒN: GLINTS (02)
## Hệ thống Tiền xử lý & Khai thác Dữ liệu VN-IT-Job-Mining (Phân nhóm Mới)

---

## 1. Tổng quan Nguồn & Đặc tính Dữ liệu Thô

- **Tên nguồn (Source Platform)**: `glints`
- **Kiểu dữ liệu cào (Payload Type)**: Hybrid Container + JSON-LD (Schema.org JobPosting)
- **Khóa Envelope chính**: `metadata` (hoặc `_meta`) và `raw_payload` (hoặc `raw`).
- **Tổng số trường thô ghi nhận**: ~9 trường cấp 1 (và các cấu trúc con lồng nhau).

---

## 2. Phân loại Ánh xạ Theo Kiến trúc Mới

### Khóa Định danh Phẳng (Top-Level Flat Identifiers)
- **`job_id_global`**: Khóa toàn cục kết hợp (`glints_<id>`)
- **`source_platform`**: `glints`
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


- **Thông tin công ty (`company`)**: Tên công ty từ `company-name`. Ảnh logo (`company_logo_image`) nằm trong `job_posting_jsonld.hiringOrganization.logo`. Website công ty (`company_url`) nằm trong `hiringOrganization.sameAs`.
- **Trường ẩn trong JSON-LD**: `educationRequirements` (bằng cấp tối thiểu), `jobLocation.address` (tỉnh/thành, đường phố).
- **Hình thức làm việc (`raw_work_mode`)**: Chứa trong dòng đầu tiên của `requirements` (ví dụ: "Làm tại công ty", "Remote", "Làm việc kết hợp").
- **Kỹ năng dạng Pipe**: Chuỗi `skills` gốc có dạng `Kỹ năng | Istqb | Quality Control | Test Plan` được bóc tách thành mảng `skills_list`.
- **Nhóm `other`**: Lưu `industry` và `container_content` thô để hỗ trợ huấn luyện NLP ở bước sau.
        

---

## 4. Dữ liệu Mẫu Thực tế (Sample JSON Data)

### 4.1. Mẫu Envelope Thô Ban đầu (Raw JSON Envelope)
Lấy trực tiếp từ tệp: `data/glints/raw/2026-10-20/f28b7d28-bc1d-41bb-9e15-2d80bd4ca47c_v1.json`

```json
{
  "metadata": {
    "job_id": "f28b7d28-bc1d-41bb-9e15-2d80bd4ca47c",
    "source": "glints",
    "source_url": "https://glints.com/vn/opportunities/jobs/manual-tester-tieng-trung/f28b7d28-bc1d-41bb-9e15-2d80bd4ca47c",
    "scraped_at": "2026-10-20T11:36:52.203769+00:00",
    "scraper_version": "2.0.0",
    "version": 1,
    "content_hash": "91847092e6d69683919172b1d74ba7df928a0412de4080380a57e8a22fb6064b",
    "field_hashes": {
      "job-title": "a9236bb19edca16d87352003b2df6a1b992134f8776e8906174d94e8836f685a",
      "company-name": "c078259f26d874d285ded83e349230448b8a8083d86194ef30f5826be16500eb",
      "salary": "6992712b2a1fe4f2879aa0a4cde4f3e79d46ab53c3900105b0363da79edb1ce5",
      "description": "2dde821ab6bad966207935f66bafa3db21924e3b105da5505ef420b7018e324c",
      "requirements": "71376490d8f04879ab75d3f15a0649ae741507b3c53c3ea142d61ad451842a34",
      "benefits": "65383a9b9ebd310afd9f74c45106d52a1d318bf8764f2fe3b2dc54c1f82f5065",
      "skills": "aac1604fb5408b77ec97ca5883c8467ce5cc172219edae5e6dd3164d7d0ef0cc",
      "container_content": "5f0a321be2fe50c1103e373bcda6b187f37e089f70a7b55d9dbcda243404d6e6",
      "job_posting_jsonld": "e9e16c80290ae1693af6c4ca77daabf0a8ef119db2694955ec7e8ae4eda101b9"
    },
    "http_status": 200,
    "status": "DONE",
    "language": "vi"
  },
  "raw_payload": {
    "job-title": "Manual Tester (tiếng Trung)",
    "company-name": "SotaTek",
    "salary": "₫10.000.000-30.000.000/Tháng",
    "description": "Chi tiết công việc Manual Tester (tiếng Trung) tại SotaTek\nJob Description:\nWe are looking for a thorough\nSoftware Tester\n. You will ensure that newly developed products are ready to perform and result in repeat clientele.\nDesign independent test cases for each newly developed application.\nProvide feedback to developers about automated testing strategies, design fixes, and patches.\nPerform system load tests for new products.\nManage and train apprentices, junior testers, and new testers\nWork with other quality technicians to document the quality processes for replication in other locations.\nManage testing projects during each phase, according to the Software Development Life Cycle (SDLC).\nMake improvements to functionality, design, and usability of new products.\nRequirements:\nMust have:\nBachelor’s degree in computer science, engineering, or equivalent discipline.\nMinimum of 2 years of experience as a Manual QA/Tester.\nProficiency in Traditional Chinese, equivalent to HSK Level 4 or above.\nSolid understanding of the software development lifecycle.\nHands-on experience with functional testing, integration testing, regression testing, mobile testing, big data testing, cross platform testing, component testing, security testing, performance testing, UI/UX testing, A/B testing.\nNice to have:\nStrong analytical and problem solving abilities.\nTMap, ISEB, ISTQB certification is a plus.\nUp-to-date knowledge of the latest testing developments.\nExperience with AI tools or AI-assisted test
... (truncated for readability)
```

### 4.2. Mẫu sau khi Tích hợp Chuẩn hóa (Tổ chức theo Kiến trúc Mới)
Bản ghi đã được phân loại rõ ràng theo Header phẳng + 8 nhóm thuộc tính:

```json
{
  "identifiers": {
    "job_id_global": "glints_f28b7d28-bc1d-41bb-9e15-2d80bd4ca47c",
    "source_platform": "glints",
    "source_job_id": "f28b7d28-bc1d-41bb-9e15-2d80bd4ca47c",
    "source_url": "https://glints.com/vn/opportunities/jobs/manual-tester-tieng-trung/f28b7d28-bc1d-41bb-9e15-2d80bd4ca47c",
    "crawled_at": "2026-10-20T11:36:52.203769+00:00"
  },
  "company": {
    "company_name": "SotaTek",
    "company_scale": null,
    "company_address": "Tòa CIC ( Số 2 Nguyễn Thị Duệ, Yên Hòa, Cầu Giấy, Hà Nội ) & Tòa Goden Park (Số 2 Phạm Văn Bạch, Yên Hòa, Cầu Giấy, Hà Nội )",
    "company_url": "https://sotatek.com",
    "company_logo_image": "https://images.glints.com/unsafe/glints-dashboard.oss-ap-southeast-1.aliyuncs.com/company-logo/dd0b3ac359134639c75766fa6a6c72a2.jpg",
    "company_industry": null
  },
  "location": {
    "raw_location_text": "Quận Cầu Giấy",
    "working_locations": [
      "Tòa CIC ( Số 2 Nguyễn Thị Duệ, Yên Hòa, Cầu Giấy, Hà Nội ) & Tòa Goden Park (Số 2 Phạm Văn Bạch, Yên Hòa, Cầu Giấy, Hà Nội )"
    ],
    "geo_coordinates": null
  },
  "skills": {
    "skills_list": [
      "Istqb",
      "Quality Control",
      "Test Plan",
      "QA Testing",
      "Software Quality Assurance",
      "Regression Testing",
      "Tester",
      "Chinese Language",
      "Restful API",
      "Defect Management",
      "Quality Assurance"
    ]
  },
  "jd": {
    "job_title": "Manual Tester (tiếng Trung)",
    "raw_description_text": "Chi tiết công việc Manual Tester (tiếng Trung) tại SotaTek\nJob Description:\nWe are looking for a thorough\nSoftware Tester\n. You will ensure that newly developed products are ready to perform and result in repeat clientele.\nDesign independent test cases for each newly developed application.\nProvide feedback to developers about automated testing strategies, design fixes, and patches.\nPerform system load tests for new products.\nManage and train apprentices, junior testers, and new testers\nWork with other quality technicians to document the quality processes for replication in other locations.\nManage testing projects during each phase, according to the Software Development Life Cycle (SDLC).\nMake improvements to functionality, design, and usability of new products.\nRequirements:\nMust have:\nBachelor’s degree in computer science, engineering, or equivalent discipline.\nMinimum of 2 years of experience as a Manual QA/Tester.\nProficiency in Traditional Chinese, equivalent to HSK Level 4 or above.\nSolid understanding of the software development lifecycle.\nHands-on experience with functional testing, integration testing, regression testing, mobile testing, big data testing, cross platform testing, component testing, security testing, performance testing, UI/UX testing, A/B testing.\nNice to have:\nStrong analytical and problem solving abilities.\nTMap, ISEB, ISTQB certification is a plus.\nUp-to-date knowledge of the latest testing developments.\nExperience with AI tools or AI-assisted testing is a plus.\nCOMPENSATION & BENEFITS:\n🎯Flexible working regime and health care:\nFlexible timekeeping (from 8:00 - 9:00 to 17:30 - 18:30)\nMinimum 14 paid leaves per annum for all employees after probation\n01-day remote work per month\nA flexitime allowance of 90-180 minutes per month for employees\n01 hour paid leave per day for women having children under 12 months\nSocial insurance, health insurance, unemployment insurance and Bao Viet care insurance\n🎯Transparent and fair benefits:\nSaturday & Sunday OFF,  Overtime pay is 150%, 200%, 300% as per labor law;\nWork performance review 2 times/ year (in April and October)\n13th-month salary\nBonus Policy: Public holidays (2/9, 30/4, 1/5, 1/1,...); Personal Performances; Excellent Team; Performance bonus in Token of the project;..\nMen’s Day, Women’s Day, Children’s Day, Mid-Autumn Festival and other benefits under the provisions of the company\n🎯Dynamic environment and open culture:\nYear-end party, sports day, yearly company trip and quarterly team building,...with a generous budget\nSocialize with colleagues through monthly Happy Hour\nMonthly allowance when joining clubs: Soccer, Swimming, Yoga, Music,...\nNice & modern working space with young, dynamic & friendly colleagues and free coffee, tea, drinks,...\nFlat, open and sharing culture with friendly management team; outsourcing company with product mindset\n🎯Strong learning culture:\nFree training courses for technical and soft skills (presentation skills, communication skills, foreign language courses,...)\nAccount to log in to our online learning system, which contains thousands of valuable lectures (LMS)\nParticipate in workshops, seminars, tech talk,... with sharing from experts inside and outside the company\nWorking opportunities with technical gurus who built and operated world-class applications with millions of users.",
    "raw_requirements_text": "Mô tả công việc\nLàm tại công ty\n1 - 3 năm kinh nghiệm\nTối thiểu Cử Nhân",
    "benefits_list": [
      "Employee Award",
      "Wellness Facilities",
      "Team-building events",
      "Remote work options",
      "Annual Leave",
      "Laptop Provided",
      "Training/Certification",
      "Insurance",
      "Flexible Hours",
      "Transport Money",
      "Free Meals",
      "Career Path",
      "Health Insurance"
    ]
  },
  "salary": {
    "raw_salary_text": "₫10.000.000-30.000.000/Tháng",
    "salary_currency": "VND",
    "is_salary_visible": true
  },
  "date": {
    "raw_posted_date": "2026-06-26T07:26:48.83Z",
    "raw_updated_at": null,
    "raw_deadline": "2026-11-24"
  },
  "extract": {
    "raw_work_mode": "Làm tại công ty / Onsite",
    "raw_seniority_text": null,
    "raw_experience_text": "1 - 3 năm kinh nghiệm",
    "raw_education_text": "bachelor degree",
    "raw_headcount": null,
    "raw_working_time": null,
    "raw_age_text": null,
    "raw_gender_text": null
  },
  "other": {
    "raw_category_text": "QA Engineer",
    "is_content_image": null,
    "auxiliary_features": {}
  }
}
```

---
*Tài liệu được cập nhật theo quy chuẩn Kiến trúc Mới của VN-IT-Job-Mining.*
