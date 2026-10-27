# ĐẶC TẢ TÍCH HỢP NGUỒN: CAREERVIET (01)
## Hệ thống Tiền xử lý & Khai thác Dữ liệu VN-IT-Job-Mining (Phân nhóm Mới)

---

## 1. Tổng quan Nguồn & Đặc tính Dữ liệu Thô

- **Tên nguồn (Source Platform)**: `careerviet`
- **Kiểu dữ liệu cào (Payload Type)**: HTML Scraper (Thẻ DOM, detail-box mảng chuỗi, detail-row đa khóa)
- **Khóa Envelope chính**: `metadata` (hoặc `_meta`) và `raw_payload` (hoặc `raw`).
- **Tổng số trường thô ghi nhận**: ~7 trường cấp 1 (và các cấu trúc con lồng nhau).

---

## 2. Phân loại Ánh xạ Theo Kiến trúc Mới

### Khóa Định danh Phẳng (Top-Level Flat Identifiers)
- **`job_id_global`**: Khóa toàn cục kết hợp (`careerviet_<id>`)
- **`source_platform`**: `careerviet`
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


- **Thông tin công ty (`company`)**: Bóc tách tên công ty từ `job-company-name`. Địa chỉ trụ sở lấy từ `detail-row['Địa điểm làm việc']`. Sàn không có quy mô công ty trên thẻ tóm tắt.
- **Trường ẩn trong `detail-box`**: Chứa mảng chuỗi nhãn `['Lương: Cạnh tranh', 'Kinh nghiệm: 3 - 5 Năm', 'Cấp bậc: Nhân viên', 'Hết hạn nộp: 20/11/2026', 'Ngày cập nhật 16/10/2026']`. Cần Regex để bóc tách: `raw_salary_text`, `raw_experience_text`, `raw_seniority_text`, `raw_deadline`, `raw_updated_at`.
- **Trường ẩn trong `detail-row`**: Bóc tách `Mô tả Công việc`, `Yêu Cầu Công Việc`, `Phúc lợi` (chuỗi phân tách bởi dấu chấm tròn hoặc xuống dòng).
- **Trường địa điểm**: Kết hợp từ `map` (chuỗi tóm tắt tỉnh thành) và `detail-row['Địa điểm làm việc']` (danh sách chi nhánh).
- **Nhóm `other`**: Lưu `Ngành nghề` (ví dụ: 'Ngân hàng , CNTT - Phần mềm') để hỗ trợ lọc non-IT ở bước Transformation.
        

---

## 4. Dữ liệu Mẫu Thực tế (Sample JSON Data)

### 4.1. Mẫu Envelope Thô Ban đầu (Raw JSON Envelope)
Lấy trực tiếp từ tệp: `data/careerviet/raw/2026-10-20/35C8AEA1_v1.json`

```json
{
  "metadata": {
    "job_id": "35C8AEA1",
    "source": "careerviet",
    "source_url": "https://careerviet.vn/vi/tim-viec-lam/hn-hcm-soc-engineer.35C8AEA1.html",
    "scraped_at": "2026-10-20T11:11:15.219864+00:00",
    "scraper_version": "1.0.0-raw-envelope",
    "version": 1,
    "content_hash": "5b0a1aeb1a1afc9a2d00f1324ba352d89a865b83fc40cb67e62c516d98911536",
    "canonical_hash": "5b0a1aeb1a1afc9a2d00f1324ba352d89a865b83fc40cb67e62c516d98911536",
    "field_hashes": {
      "title": "9f383350c01ee114703851ac71d7fb554ef7aafed1c08d25c1343d950300ac9a",
      "job-company-name": "56a068f3ace7d9bd7a00e4915712fc4fd1ad0166cc23a0504c305756430b1c7f",
      "detail-box": "62cdee91755b509865ae68e74b761ef3f63d4da8994e98cd4b1e32085bb1abd5",
      "detail-row": "1f729793e97a8c0c28c61ac5c95798d1ac95508e238ae464fa9239f4c352dbaa",
      "job-tags": "9f475320e6c9a540bb6ac8b588fa17e9e646e538bf5c1dcf27100587591f7e54",
      "map": "9306d050ce6ae03e18f95e665248dae82e7c5ccafb8e9ec3d88a34b5fcbc5d37",
      "Ngành nghề": "978e720fbc3697dc869854a607f7b9e58820a926e60c91a631c242d9cebee919"
    },
    "source_category": null
  },
  "raw_payload": {
    "title": "[HN/HCM] SOC Engineer",
    "job-company-name": "Ngân Hàng TMCP Việt Nam Thịnh Vượng - VPBANK",
    "detail-box": [
      "Ngày cập nhật 16/10/2026",
      "Ngành nghề Ngân hàng , CNTT - Phần mềm",
      "Hình thức Nhân viên chính thức",
      "Ngày cập nhật 16/10/2026",
      "Ngành nghề Ngân hàng , CNTT - Phần mềm",
      "Hình thức Nhân viên chính thức",
      "Lương Cạnh tranh",
      "Kinh nghiệm 4 - 5 Năm",
      "Cấp bậc Nhân viên",
      "Hết hạn nộp 30/11/2026"
    ],
    "detail-row": {
      "Phúc lợi": "Phúc lợi Chế độ bảo hiểm Phụ cấp Chế độ thưởng Chăm sóc sức khỏe Đào tạo Nghỉ phép năm",
      "Mô tả Công việc": "Mô tả Công việc Tham gia xây dựng các quy trình, hướng dẫn, playbook cho hoạt động của SOC Tham gia Nghiên cứu và đề xuất các giải pháp công nghệ và thông lệ tiên tiến để áp dụng vào hoạt động SOC Tham gia xác định các yêu cầu đối với dữ liệu ANBM phục vụ cho công tác quản trị, phân tích, giám sát và báo cáo Giám sát an ninh 24/7 hệ thống CNTT Quản lý và ứng phó sự cố ANBM Quản lý và săn lùng mối đe dọa chủ động Quản lý lỗ hổng bảo mật Phối hợp với các bên liên quan để rà soát các kịch bản ứng phó sự cố và diễn tập hàng năm về an toàn thông tin Phối hợp với các bên liên quan đển thực hiện các thay đổi nhằm xử lý các vấn đề về ANBM Tham gia quản lý, giám sát các chỉ số, thước đo về tình trạng ANBM CNTT Theo dõi, tổng hợp và cung cấp thông tin về hiệu quả của các luật/ kịch bản giám sát sự kiện bất thường Theo dõi, giám sát và đánh giá kết quả thực hiện các hành động khắc phục và các biện pháp giảm thiểu được xác định từ các sự cố ANBM Tham gia rà soát và cập nhật các quy trình, hướng dẫn, playbook cho hoạt động của SOC",
      "Yêu Cầu Công Việc": "Yêu Cầu Công Việc Tốt nghiệp Đại học chuyên ngành về CNTT, An toàn thông tin hoặc chuyên ngành liên quan. Kinh nghiệm tối thiểu 4 năm với 
... (truncated for readability)
```

### 4.2. Mẫu sau khi Tích hợp Chuẩn hóa (Tổ chức theo Kiến trúc Mới)
Bản ghi đã được phân loại rõ ràng theo Header phẳng + 8 nhóm thuộc tính:

```json
{
  "identifiers": {
    "job_id_global": "careerviet_35C8AEA1",
    "source_platform": "careerviet",
    "source_job_id": "35C8AEA1",
    "source_url": "https://careerviet.vn/vi/tim-viec-lam/hn-hcm-soc-engineer.35C8AEA1.html",
    "crawled_at": "2026-10-20T11:11:15.219864+00:00"
  },
  "company": {
    "company_name": "Ngân Hàng TMCP Việt Nam Thịnh Vượng - VPBANK",
    "company_scale": null,
    "company_address": "Địa điểm làm việc Hồ Chí Minh 3A-3B Tôn Đức Thắng, phường Bến Nghé, Quận 1, TP.HCM Hà Nội 89 Láng Hạ, Đống Đa, Hà Nội",
    "company_url": null,
    "company_logo_image": null,
    "company_industry": null
  },
  "location": {
    "raw_location_text": "Hồ Chí Minh, Hà Nội",
    "working_locations": [
      "Hồ Chí Minh, Hà Nội",
      "Địa điểm làm việc Hồ Chí Minh 3A-3B Tôn Đức Thắng, phường Bến Nghé, Quận 1, TP.HCM Hà Nội 89 Láng Hạ, Đống Đa, Hà Nội"
    ],
    "geo_coordinates": null
  },
  "skills": {
    "skills_list": [
      "SOC Engineer",
      "Soc Analyst"
    ]
  },
  "jd": {
    "job_title": "[HN/HCM] SOC Engineer",
    "raw_description_text": "Mô tả Công việc Tham gia xây dựng các quy trình, hướng dẫn, playbook cho hoạt động của SOC Tham gia Nghiên cứu và đề xuất các giải pháp công nghệ và thông lệ tiên tiến để áp dụng vào hoạt động SOC Tham gia xác định các yêu cầu đối với dữ liệu ANBM phục vụ cho công tác quản trị, phân tích, giám sát và báo cáo Giám sát an ninh 24/7 hệ thống CNTT Quản lý và ứng phó sự cố ANBM Quản lý và săn lùng mối đe dọa chủ động Quản lý lỗ hổng bảo mật Phối hợp với các bên liên quan để rà soát các kịch bản ứng phó sự cố và diễn tập hàng năm về an toàn thông tin Phối hợp với các bên liên quan đển thực hiện các thay đổi nhằm xử lý các vấn đề về ANBM Tham gia quản lý, giám sát các chỉ số, thước đo về tình trạng ANBM CNTT Theo dõi, tổng hợp và cung cấp thông tin về hiệu quả của các luật/ kịch bản giám sát sự kiện bất thường Theo dõi, giám sát và đánh giá kết quả thực hiện các hành động khắc phục và các biện pháp giảm thiểu được xác định từ các sự cố ANBM Tham gia rà soát và cập nhật các quy trình, hướng dẫn, playbook cho hoạt động của SOC",
    "raw_requirements_text": "Yêu Cầu Công Việc Tốt nghiệp Đại học chuyên ngành về CNTT, An toàn thông tin hoặc chuyên ngành liên quan. Kinh nghiệm tối thiểu 4 năm với các lĩnh vực về ANBM, CNTT Có tối thiểu 3 năm kinh nghiệm trong các lĩnh vực ANBM như giám sát điều hành sự kiện ANBM, quản lý và ứng phó sự cố, phân tích điều tra sự cố ANBM, săn lùng mối đe dọa chủ động, quản lý lỗ hổng bảo mật, đánh giá ANBM, phân tích dữ liệu ANBM Am hiểu, có kiến thức tốt về các tiêu chuẩn bảo mật CNTT quốc tế (ISO 270001, PCI-DSS, ITIL, MITRE ATT&CK, OWSAP, v.v. Có kiến thức và kỹ năng an ninh bảo mật mạng, hệ thống, ứng dụng, CSDL Hiểu biết về các hệ thống giải pháp ANBM nói chung và SOC nói riêng như SIEM, SOAR, EDR, NDR FW, WAF, DBFW, IPS, DLP, PIM, v.v. Có kiến thức và kỹ năng xây dựng quy trình quản lý SOC Có kiến thức và kỹ năng ANBM trên các môi trường cloud Có kiến thức và kỹ năng tự động hóa và tối ưu SOC Có kiến thức và kỹ năng phân tích mã độc, mã hóa, săn lùng mối đe dọa Có kiến thức và kỹ năng lập trình một số ngôn ngữ: Python, Shell, PHP Có kiến thức và kỹ năng sử dụng các công cụ ANBM để kiểm thử xâm nhập, khai thác lỗ hổng: VA, APPScan, Metaexploit, kalilinux, Burpsuite, v.v.",
    "benefits_list": [
      "Phúc lợi Chế độ bảo hiểm Phụ cấp Chế độ thưởng Chăm sóc sức khỏe Đào tạo Nghỉ phép năm"
    ]
  },
  "salary": {
    "raw_salary_text": "Cạnh tranh",
    "salary_currency": "VND",
    "is_salary_visible": true
  },
  "date": {
    "raw_posted_date": "16/10/2026",
    "raw_updated_at": "16/10/2026",
    "raw_deadline": "30/11/2026"
  },
  "extract": {
    "raw_work_mode": null,
    "raw_seniority_text": "Nhân viên",
    "raw_experience_text": "4 - 5 Năm",
    "raw_education_text": null,
    "raw_headcount": null,
    "raw_working_time": null,
    "raw_age_text": null,
    "raw_gender_text": null
  },
  "other": {
    "raw_category_text": "Ngân hàng , CNTT - Phần mềm",
    "is_content_image": null,
    "auxiliary_features": {}
  }
}
```

---
*Tài liệu được cập nhật theo quy chuẩn Kiến trúc Mới của VN-IT-Job-Mining.*
