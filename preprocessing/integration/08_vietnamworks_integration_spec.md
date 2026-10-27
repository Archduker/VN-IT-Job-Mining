# ĐẶC TẢ TÍCH HỢP NGUỒN: VIETNAMWORKS (08)
## Hệ thống Tiền xử lý & Khai thác Dữ liệu VN-IT-Job-Mining (Phân nhóm Mới)

---

## 1. Tổng quan Nguồn & Đặc tính Dữ liệu Thô

- **Tên nguồn (Source Platform)**: `vietnamworks`
- **Kiểu dữ liệu cào (Payload Type)**: Enterprise REST Search API (Hơn 100 trường phân loại)
- **Khóa Envelope chính**: `metadata` (hoặc `_meta`) và `raw_payload` (hoặc `raw`).
- **Tổng số trường thô ghi nhận**: ~103 trường cấp 1 (và các cấu trúc con lồng nhau).

---

## 2. Phân loại Ánh xạ Theo Kiến trúc Mới

### Khóa Định danh Phẳng (Top-Level Flat Identifiers)
- **`job_id_global`**: Khóa toàn cục kết hợp (`vietnamworks_<id>`)
- **`source_platform`**: `vietnamworks`
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


- **Thông tin công ty (`company`)**: Tên công ty (`companyName`), quy mô (`companySize`), và ẢNH LOGO CÔNG TY (`companyLogo` CDN URL).
- **TỌA ĐỘ ĐỊA LÝ GPS (`địa điểm`)**: Cung cấp `workingLocations[].geoLoc` với `{lat: ..., lon: ...}` và `nearestGeoLoc`.
- **MỨC LƯƠNG CÓ CẤU TRÚC SẴN (`salary`)**: Tách sẵn `salaryMin`, `salaryMax`, `salaryCurrency` ("VND" / "USD"), `isSalaryVisible`.
- **CHỈ TIÊU & ĐỘ TUỔI & HỌC VẤN (`extract`)**: `numberOfRecruits`, `rangeAge`, `highestDegreeId`, `yearsOfExperience`.
- **Nhóm `other`**: Cung cấp `industriesV3` ("IT Software/SaaS"), cờ ưu tiên `isMobileHotJob`, `isTopPriority`, `isUrgentJob` phục vụ phân tích độ "sốt" của tin tuyển dụng.
        

---

## 4. Dữ liệu Mẫu Thực tế (Sample JSON Data)

### 4.1. Mẫu Envelope Thô Ban đầu (Raw JSON Envelope)
Lấy trực tiếp từ tệp: `data/vietnamworks/raw/2026-10-16/raw_batch.json`

```json
{
  "metadata": {
    "job_id": "2111943",
    "source": "vietnamworks",
    "source_url": "https://www.vietnamworks.com/marketing-manager-it-domain-required-1790335677535733406-2111943-jv",
    "scraped_at": "2026-10-16T15:13:11.510902+00:00",
    "scraper_version": "0.5.0",
    "content_hash": "964b124c1144e1f2b708ffe400a98f82f85218f9cf2b1a6e19fa74aa470658f1"
  },
  "raw_payload": {
    "jobId": 2111943,
    "jobTitle": "Marketing Manager (IT Domain required)",
    "jobUrl": "https://www.vietnamworks.com/marketing-manager-it-domain-required-1790335677535733406-2111943-jv",
    "userId": 3272245,
    "companyLogo": "https://images.vietnamworks.com/pictureofcompany/14/10459636.png",
    "companyUrl": "",
    "alias": "marketing-manager-it-domain-required-1790335677535733406",
    "createdOn": "2026-09-25T17:05:38+07:00",
    "approvedOn": "2026-09-25T18:27:57+07:00",
    "approvedOnText": "Đăng 21 ngày trước",
    "prettyApprovedOn": "21 ngày trước",
    "expiredOn": "2026-10-25T23:59:59+07:00",
    "lastUpdatedOn": "2026-09-30T18:39:06+07:00",
    "lastSyncedOn": "2026-10-16T07:19:30+07:00",
    "companyName": "Nakivo",
    "companyId": 170721,
    "companyProfile": "NAKIVO Inc. is a privately held company that develops data protection and site recovery software for SMB and enterprise market since 2012.\r\n\r\nThe solution developed by the company, NAKIVO Backup & Replication, is used by over 15,000 companies worldwide to protect their critical data in virtualized and hybrid environments. NAKIVO has a global presence with over 4,000 channel partners in 140+ countries. Close to 300 hosting, managed, and cloud service providers are currently using NAKIVOs software to deliver VM BaaS, RaaS, and DRaaS to their customers. NAKIVO has an impressive track record of 5-star community reviews and over 97% customer satisfaction with support, and has also won a Best of VMworld 2018” Gold Award for Data Protection at VMworld 2018 US. Customers trust us and we aim to deliver on that trust.\r\n\r\nAt Nakivo, we are offering employees with young, dynamic and flat organization chart, where your ideas can instantly reach your team leader or even CEO just by clicks. The Nakivo team in Vietnam has been changing very fast in the recent years, we have grown from a group of 6 engineers to the current team size of 70 and we are expecting to grow even more in the next following years. \r\n\r\nWe welcome and embrace people, regardless of their background, religion, nationality or gender, but focus on diversity, contribution, determination and work ethic. At Nakivo, we are trying to improve everyday, to become a competitive choice for talented people, by offering\r\n\r\nFlexible working hours: Office opens from 6.00 AM to 10.00 PM\r\nPrivate health care package\r\nPremium health care check\r\nGift (cash/voucher) for every special occasion: New Year's Eve, Tet holidays, International Women's Day, International Children's Day, Mid-Autumn Festival and Birthday\r\nUp to 15 ann
... (truncated for readability)
```

### 4.2. Mẫu sau khi Tích hợp Chuẩn hóa (Tổ chức theo Kiến trúc Mới)
Bản ghi đã được phân loại rõ ràng theo Header phẳng + 8 nhóm thuộc tính:

```json
{
  "identifiers": {
    "job_id_global": "vietnamworks_2111943",
    "source_platform": "vietnamworks",
    "source_job_id": "2111943",
    "source_url": "https://www.vietnamworks.com/marketing-manager-it-domain-required-1790335677535733406-2111943-jv",
    "crawled_at": "2026-10-16T15:13:11.510902+00:00"
  },
  "company": {
    "company_name": "Nakivo",
    "company_scale": "100-499",
    "company_address": "TGI Building, 208 Đường Nguyễn Trãi, Phạm Ngũ Lão, Quận 1, Thành phố Hồ Chí Minh, Việt Nam",
    "company_url": null,
    "company_logo_image": "https://images.vietnamworks.com/pictureofcompany/14/10459636.png",
    "company_industry": null
  },
  "location": {
    "raw_location_text": null,
    "working_locations": [
      "TGI Building, 208 Nguyen Trai, Ben Thanh Ward, Ho Chi Minh City",
      "TGI Building, 208 Đường Nguyễn Trãi, Phạm Ngũ Lão, Quận 1, Thành phố Hồ Chí Minh, Việt Nam"
    ],
    "geo_coordinates": {
      "lat": 0,
      "lon": 0
    }
  },
  "skills": {
    "skills_list": [
      "B2B Marketing",
      "SEO",
      "PR Content",
      "Digital Marketing",
      "ROI Analysis"
    ]
  },
  "jd": {
    "job_title": "Marketing Manager (IT Domain required)",
    "raw_description_text": "<p>● Build and lead NAKIVO’s global lead generation and field marketing strategy</p><p>● Own marketing performance across partner programs, Lunch &amp; Learns, tradeshows, webinars, and face-to-face events</p><p>● Transform events into measurable pipeline and revenue-generating activities with clear follow-up processes and accountability</p><p>● Develop and execute scalable reseller and distributor marketing programs to acquire new partners and...",
    "raw_requirements_text": "<p><strong>Required Qualifications: </strong></p><p>● Fluent English (written and spoken)</p><p>● 10+ years of B2B marketing experience in global technology companies</p><p>● 5+ years of leadership experience managing high-performing marketing teams</p><p>● Proven success in channel marketing, partner marketing, and lead generation</p><p>● Strong experience driving measurable pipeline growth through events, tradeshows, partner campaigns, and field marketing</p><p>● Deep understanding of...",
    "benefits_list": [
      "Healthcare Plan",
      "15-18 annual leaves, 5 sick leave"
    ]
  },
  "salary": {
    "raw_salary_text": "Thương lượng",
    "salary_currency": "USD",
    "is_salary_visible": false
  },
  "date": {
    "raw_posted_date": "2026-09-25T17:05:38+07:00",
    "raw_updated_at": "2026-09-30T18:39:06+07:00",
    "raw_deadline": "2026-10-25T23:59:59+07:00"
  },
  "extract": {
    "raw_work_mode": null,
    "raw_seniority_text": "Trưởng phòng",
    "raw_experience_text": "10 năm",
    "raw_education_text": "Cử nhân / Đại học",
    "raw_headcount": "1",
    "raw_working_time": null,
    "raw_age_text": "Không hiển thị",
    "raw_gender_text": "Không hiển thị"
  },
  "other": {
    "raw_category_text": "Phần Mềm CNTT/Dịch vụ Phần mềm",
    "is_content_image": null,
    "auxiliary_features": {
      "isMobileHotJob": true,
      "isTopPriority": false
    }
  }
}
```

---
*Tài liệu được cập nhật theo quy chuẩn Kiến trúc Mới của VN-IT-Job-Mining.*
