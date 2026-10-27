# ĐẶC TẢ TÍCH HỢP NGUỒN: TOPDEV (06)
## Hệ thống Tiền xử lý & Khai thác Dữ liệu VN-IT-Job-Mining (Phân nhóm Mới)

---

## 1. Tổng quan Nguồn & Đặc tính Dữ liệu Thô

- **Tên nguồn (Source Platform)**: `topdev`
- **Kiểu dữ liệu cào (Payload Type)**: Pure IT REST API Payload
- **Khóa Envelope chính**: `metadata` (hoặc `_meta`) và `raw_payload` (hoặc `raw`).
- **Tổng số trường thô ghi nhận**: ~30 trường cấp 1 (và các cấu trúc con lồng nhau).

---

## 2. Phân loại Ánh xạ Theo Kiến trúc Mới

### Khóa Định danh Phẳng (Top-Level Flat Identifiers)
- **`job_id_global`**: Khóa toàn cục kết hợp (`topdev_<id>`)
- **`source_platform`**: `topdev`
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


- **CỜ BÀI ĐĂNG DẠNG HÌNH ẢNH (`is_content_image`) TRONG NHÓM `other`**: Đây là trường ảo cực kỳ quan trọng! Giúp pipeline không drop nhầm tin tuyển dụng bằng ảnh banner đồ họa.
- **Thông tin công ty (`company`)**: Nằm trong `company` gồm `company_name`, `company_size` (quy mô công ty).
- **Địa chỉ có cấu trúc (`địa điểm`)**: Nằm trong `addresses` gồm `address_region_list`, `full_addresses`, `collection_addresses`.
- **Làm sạch HTML (`JD`)**: Bóc tách `responsibilities_original`, `requirements_original`, và `benefits_v2` (hoặc `benefits_original`).
- **Kỹ năng IT mảng sạch (`skills`)**: Trường `skills_arr` chứa mảng thẻ kỹ năng chuẩn.
        

---

## 4. Dữ liệu Mẫu Thực tế (Sample JSON Data)

### 4.1. Mẫu Envelope Thô Ban đầu (Raw JSON Envelope)
Lấy trực tiếp từ tệp: `data/topdev/raw/2026-10-20/2139491_v1.json`

```json
{
  "metadata": {
    "job_id": "2139491",
    "source": "topdev",
    "source_job_id": "2139491",
    "source_url": "https://topdev.vn/viec-lam/binh-duong-quan-ly-lop-hoc-part-time-cong-ty-co-phan-truong-hoc-cong-nghe-mindx-2139491",
    "scraped_at": "2026-10-20T17:07:30.142540+00:00",
    "scraper_version": "2.0.0",
    "crawler_version": "2.0.0",
    "version": 1,
    "content_hash": "b2f9e9bb46373304442077a9e91d492209db36d400b8c004c2ee38e986bb64dc",
    "language": "vi"
  },
  "raw_payload": {
    "id": 2139491,
    "title": "[Bình Dương] Quản Lý Lớp Học Part-time",
    "is_content_image": false,
    "is_content_image_enabled": false,
    "content": "<p style=\"text-align: justify;\"><span style=\"font-family: Roboto, Helvetica, Verdana, Arial, sans-serif; font-size: 15px;\"><strong>Địa điểm l&agrave;m việc:&nbsp;</strong></span></p>\r\n<ul>\r\n<li style=\"text-align: justify;\"><span style=\"font-family: Roboto, Helvetica, Verdana, Arial, sans-serif; font-size: 15px;\">76 Nguyễn An Ninh, P. Dĩ An, TP. Dĩ An - 76 Nguyễn An Ninh, P. Dĩ An, TP. Dĩ An, Th&agrave;nh Phố Dĩ An, B&igrave;nh Dương</span></li>\r\n</ul>",
    "benefits_v2": [
      {
        "description": "<ul>\r\n<li style=\"text-align: justify;\"><span style=\"font-family: Roboto, Helvetica, Verdana, Arial, sans-serif; font-size: 15px;\">Thu nhập cạnh tranh v&agrave; theo thỏa thuận: lương cơ bản 3 triệu VNĐ/th&aacute;ng</span></li>\r\n<li style=\"text-align: justify;\"><span style=\"font-family: Roboto, Helvetica, Verdana, Arial, sans-serif; font-size: 15px;\">Hưởng c&aacute;c chế độ, ch&iacute;nh s&aacute;ch ph&uacute;c lợi của C&ocirc;ng ty như dịp Lễ, Tết dương lịch, th&acirc;m ni&ecirc;n, sinh nhật, ốm đau, hiếu hỷ, &hellip;;</span></li>\r\n<li style=\"text-align: justify;\"><span style=\"font-family: Roboto, Helvetica, Verdana, Arial, sans-serif; font-size: 15px;\">C&aacute;c hoạt động chăm lo cho đời sống tinh thần: Sinh nhật c&aacute; nh&acirc;n, lễ, tết, team building, nghỉ m&aacute;t tổ chức định kỳ;</span></li>\r\n</ul>"
      }
    ],
    "owned_id": 91909,
    "company": "CÔNG TY CỔ PHẦN TRƯỜNG HỌC CÔNG NGHỆ MINDX",
    "skills_str": "Customer Service/Customer Support",
    "skills_arr": [
      "Customer Service/Customer Support"
    ],
    "addresses": {
      "address_region_ids": [
        "79"
      ],
      "address_region_array": [
        "Thành phố Hồ Chí Minh"
      ],
      "collection_addresses": [
        {
          "province": {
            "id": "79",
            "value": "Thành phố Hồ Chí Minh"
          },
          "street": "TP. Hồ Chí Minh",
          "district": {
            "id": null,
            "value": null
          },
          "latitude": null,
          "id": 207363,
          "ward": {
            "id": null,
            "value": null
          },
          "full_address": "TP. Hồ Chí Minh, Thành phố Hồ Chí Minh",
          "postal_code": "700000",
          "longitude": null
        }
      ],
      "full_addresses": [
        "TP. Hồ
... (truncated for readability)
```

### 4.2. Mẫu sau khi Tích hợp Chuẩn hóa (Tổ chức theo Kiến trúc Mới)
Bản ghi đã được phân loại rõ ràng theo Header phẳng + 8 nhóm thuộc tính:

```json
{
  "identifiers": {
    "job_id_global": "topdev_2139491",
    "source_platform": "topdev",
    "source_job_id": "2139491",
    "source_url": "https://topdev.vn/viec-lam/binh-duong-quan-ly-lop-hoc-part-time-cong-ty-co-phan-truong-hoc-cong-nghe-mindx-2139491",
    "crawled_at": "2026-10-20T17:07:30.142540+00:00"
  },
  "company": {
    "company_name": "CÔNG TY CỔ PHẦN TRƯỜNG HỌC CÔNG NGHỆ MINDX",
    "company_scale": null,
    "company_address": null,
    "company_url": null,
    "company_logo_image": null,
    "company_industry": null
  },
  "location": {
    "raw_location_text": "Thành phố Hồ Chí Minh",
    "working_locations": [
      "TP. Hồ Chí Minh, Thành phố Hồ Chí Minh"
    ],
    "geo_coordinates": null
  },
  "skills": {
    "skills_list": [
      "Customer Service/Customer Support"
    ]
  },
  "jd": {
    "job_title": "[Bình Dương] Quản Lý Lớp Học Part-time",
    "raw_description_text": "Hỗ trợ tiếp nhận học viên, quản lý danh sách học viên;\nChuẩn bị các cơ sở vật chất cần thiết để phục vụ cho các lớp học;\nHỗ trợ chăm sóc phụ huynh và học viên, tiếp nhận các ý kiến, phản hồi và xử lý trong phạm vi cho phép. - Xây dựng mối quan hệ thân thiết với phụ huynh và học viên;\nHỗ trợ hoạt động trong các buổi giao lưu và bảo vệ sản phẩm cuối khóa cho lớp học, hỗ trợ các chương trình, sự kiện diễn tại cơ sở;\nCác công việc khác như trực lễ tân, trực điện thoại, các công tác hỗ trợ khác được giao",
    "raw_requirements_text": "Yêu thích trẻ em, có tính cách hòa đồng, vui vẻ, thích giao tiếp và giúp đỡ mọi người;\nTrung thực, chăm chỉ, chu đáo, có trách nhiệm;\nCó laptop cá nhân;\nĐáp ứng thời gian làm việc trong khung giờ chiều tối các ngày trong tuần và thời gian làm việc cuối tuần T7 CN\nPhù hợp hoặc mong muốn rèn luyện để phù hợp với văn hóa của MINDX;\nCa linh động: từ 17h - 21h các ngày (không bắt buộc làm cuối tuần). 1 tuần làm tối thiểu 20-25 giờ",
    "benefits_list": [
      "Thu nhập cạnh tranh và theo thỏa thuận: lương cơ bản 3 triệu VNĐ/tháng\nHưởng các chế độ, chính sách phúc lợi của Công ty như dịp Lễ, Tết dương lịch, thâm niên, sinh nhật, ốm đau, hiếu hỷ, …;\nCác hoạt động chăm lo cho đời sống tinh thần: Sinh nhật cá nhân, lễ, tết, team building, nghỉ mát tổ chức định kỳ;"
    ]
  },
  "salary": {
    "raw_salary_text": "Thỏa thuận",
    "salary_currency": "VND",
    "is_salary_visible": false
  },
  "date": {
    "raw_posted_date": null,
    "raw_updated_at": null,
    "raw_deadline": null
  },
  "extract": {
    "raw_work_mode": null,
    "raw_seniority_text": null,
    "raw_experience_text": null,
    "raw_education_text": null,
    "raw_headcount": null,
    "raw_working_time": null,
    "raw_age_text": null,
    "raw_gender_text": null
  },
  "other": {
    "raw_category_text": null,
    "is_content_image": false,
    "auxiliary_features": {}
  }
}
```

---
*Tài liệu được cập nhật theo quy chuẩn Kiến trúc Mới của VN-IT-Job-Mining.*
