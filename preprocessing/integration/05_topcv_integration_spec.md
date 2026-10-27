# ĐẶC TẢ TÍCH HỢP NGUỒN: TOPCV (05)
## Hệ thống Tiền xử lý & Khai thác Dữ liệu VN-IT-Job-Mining (Phân nhóm Mới)

---

## 1. Tổng quan Nguồn & Đặc tính Dữ liệu Thô

- **Tên nguồn (Source Platform)**: `topcv`
- **Kiểu dữ liệu cào (Payload Type)**: Rich Extracted Envelope (Tags, Bullets, Overview, General Info)
- **Khóa Envelope chính**: `metadata` (hoặc `_meta`) và `raw_payload` (hoặc `raw`).
- **Tổng số trường thô ghi nhận**: ~21 trường cấp 1 (và các cấu trúc con lồng nhau).

---

## 2. Phân loại Ánh xạ Theo Kiến trúc Mới

### Khóa Định danh Phẳng (Top-Level Flat Identifiers)
- **`job_id_global`**: Khóa toàn cục kết hợp (`topcv_<id>`)
- **`source_platform`**: `topcv`
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


- **Thông tin công ty (`company`)**: `company` (tên), `company_scale` (quy mô), `company_address` (trụ sở), `company_industry` (ngành nghề).
- **Trường ẩn trong `general_info` & `overview_tags` (`extract`)**: Độ tuổi (`raw_age_text` như 'Tuổi 22 - 30'), Giới tính (`raw_gender_text`), Chỉ tiêu (`raw_headcount`), Cấp bậc, Học vấn.
- **Hệ thống Tags phong phú**: Phân rã `required_skills`, `industry_knowledge` vào `skills_list`; `welfare_tags`, `allowance_tags` vào `benefits_list`.
- **Nhóm `other`**: Lưu thông tin `Mức độ cạnh tranh` và `Kinh nghiệm quản lý` từ `general_info` hỗ trợ Feature Engineering.
        

---

## 4. Dữ liệu Mẫu Thực tế (Sample JSON Data)

### 4.1. Mẫu Envelope Thô Ban đầu (Raw JSON Envelope)
Lấy trực tiếp từ tệp: `data/topcv/raw/2026-10-20/2319343_v1.json`

```json
{
  "metadata": {
    "job_id": "2319343",
    "source": "topcv",
    "source_url": "https://www.topcv.vn/viec-lam/nhan-vien-kinh-doanh-web-app-luong-cung-khong-phu-thuoc-doanh-so-lam-viec-tai-quan-tan-binh-ho-chi-minh/2319343.html",
    "scraped_at": "2026-10-20T18:44:13.840558+00:00",
    "scraper_version": "2.0.0",
    "version": 1,
    "language": "vi",
    "content_hash": "3e3fa3540eb8ef216006a99b2ada4bdaee900eb1db76c9fcc21f5613cb126325"
  },
  "raw_payload": {
    "title": "Nhân Viên Kinh Doanh - Web/App - Lương Cứng Không Phụ Thuộc Doanh Số - Làm Việc Tại Quận Tân Bình, Hồ Chí Minh",
    "company": "CÔNG TY TNHH GIẢI PHÁP CÔNG NGHỆ SỐ VN",
    "salary_raw": "10 - 30 triệu",
    "location": "Hồ Chí Minh",
    "experience": "Không yêu cầu",
    "deadline_raw": "01/11/2026",
    "overview_tags": {
      "Yêu cầu": [
        "Không yêu cầu kinh nghiệm chuyên môn",
        "Tuổi 18 - 30",
        "Cao Đẳng trở lên",
        "Phát âm chuẩn",
        "Diễn đạt trôi chảy"
      ],
      "Quyền lợi": [
        "Có hỗ trợ Data",
        "Bảo hiểm xã hội",
        "Du lịch hàng năm"
      ],
      "Chuyên môn": [
        "Kinh doanh phần mềm",
        "Thương mại điện tử",
        "Marketing / Quảng cáo",
        "Quan hệ công chúng",
        "B2B",
        "B2C",
        "Direct Sales",
        "Telesales",
        "Online Sales"
      ]
    },
    "description_bullets": [
      "Tiếp nhận, sàng lọc danh sách khách hàng tiềm năng từ các chiến dịch Marketing để phân loại khách hàng có nhu cầu sử dụng dịch vụ để lấy thông tin cần thiết tư vấn dịch vụ.",
      "Phối hợp với các bộ phận vận hành để làm kế hoạch, báo giá dịch vụ cho khách hàng sau đó tiến hành thương lượng ký hợp đồng.",
      "Gọi điện thoại/ gửi email giới thiệu công ty và sản phẩm/ dịch vụ đến các khách hàng tiềm năng.",
      "Thuyết phục khách hàng sử dụng sản phẩm/dịch vụ, tạo dựng lòng tin của khách hàng với doanh nghiệp.",
      "Công ty hỗ trợ 100% data sẵn",
      "Địa chỉ làm việc: Lầu 6, Tòa Nhà Kicotrans, Phường Tân Sơn Hòa, Tp. HCM (Phường 2, Quận Tân Bình cũ)"
    ],
    "requirements_bullets": [
      "Không yêu cầu kinh nghiệm",
      "Được đào tạo bài bản về kiến thức bán hàng và kiến thức chuyên môn.",
      "Tốt nghiệp Cao Đẳng trở lên.",
      "Yêu thích công việc bán hàng, giao tiếp với khách hàng",
      "Năng động, cầu tiến, ham học hỏi, khả năng tập trung cao.",
      "Biết sử dụng MS Office, Email, Mạng xã hội Facebook, Zalo, Skype.",
      "Giao tiếp tốt, ngoại hình ưa nhìn là một lợi thế."
    ],
    "industry_knowledge": [
      "Thương mại điện tử",
      "Marketing / Quảng cáo",
      "Quan hệ công chúng"
    ],
    "required_skills": [
      "Kỹ năng giao tiếp",
      "Kỹ năng đàm phán",
      "Kỹ năng Thuyết phục",
      "kỹ năng quản lý thời gian",
      "Kỹ Năng Lập Kế Hoạch Và Tổ Chức"
    ],
    "benefits_bullets": [
      "Hỗ trợ 100% Data khách hàng",
      "Đào tạo học việc nếu chưa có kinh nghiệm.",
      "Lương hỗ trợ học việc: 5.000.000 đ / thán
... (truncated for readability)
```

### 4.2. Mẫu sau khi Tích hợp Chuẩn hóa (Tổ chức theo Kiến trúc Mới)
Bản ghi đã được phân loại rõ ràng theo Header phẳng + 8 nhóm thuộc tính:

```json
{
  "identifiers": {
    "job_id_global": "topcv_2319343",
    "source_platform": "topcv",
    "source_job_id": "2319343",
    "source_url": "https://www.topcv.vn/viec-lam/nhan-vien-kinh-doanh-web-app-luong-cung-khong-phu-thuoc-doanh-so-lam-viec-tai-quan-tan-binh-ho-chi-minh/2319343.html",
    "crawled_at": "2026-10-20T18:44:13.840558+00:00"
  },
  "company": {
    "company_name": "CÔNG TY TNHH GIẢI PHÁP CÔNG NGHỆ SỐ VN",
    "company_scale": "25-99 nhân viên",
    "company_address": "Tòa Nhà D-Head, 371 Nguyễn Kiệm, P.3, Gò Vấp, TP.HCM",
    "company_url": null,
    "company_logo_image": null,
    "company_industry": "Hoạt động dịch vụ máy tính và công nghệ thông tin khác"
  },
  "location": {
    "raw_location_text": "Hồ Chí Minh",
    "working_locations": [
      "Hồ Chí Minh: Lầu 6, Tòa Nhà Kicotrans Tp. HCM (Quận Tân Bình Cũ), Phường Tân Sơn Hòa (Phường Tân Sơn Hòa thuộc quận Tân Bình cũ)"
    ],
    "geo_coordinates": null
  },
  "skills": {
    "skills_list": [
      "Kinh doanh phần mềm",
      "Thương mại điện tử",
      "Marketing / Quảng cáo",
      "Quan hệ công chúng",
      "B2B",
      "B2C",
      "Direct Sales",
      "Telesales",
      "Online Sales",
      "Kỹ năng giao tiếp",
      "Kỹ năng đàm phán",
      "Kỹ năng Thuyết phục",
      "kỹ năng quản lý thời gian",
      "Kỹ Năng Lập Kế Hoạch Và Tổ Chức"
    ]
  },
  "jd": {
    "job_title": "Nhân Viên Kinh Doanh - Web/App - Lương Cứng Không Phụ Thuộc Doanh Số - Làm Việc Tại Quận Tân Bình, Hồ Chí Minh",
    "raw_description_text": "Tiếp nhận, sàng lọc danh sách khách hàng tiềm năng từ các chiến dịch Marketing để phân loại khách hàng có nhu cầu sử dụng dịch vụ để lấy thông tin cần thiết tư vấn dịch vụ.\nPhối hợp với các bộ phận vận hành để làm kế hoạch, báo giá dịch vụ cho khách hàng sau đó tiến hành thương lượng ký hợp đồng.\nGọi điện thoại/ gửi email giới thiệu công ty và sản phẩm/ dịch vụ đến các khách hàng tiềm năng.\nThuyết phục khách hàng sử dụng sản phẩm/dịch vụ, tạo dựng lòng tin của khách hàng với doanh nghiệp.\nCông ty hỗ trợ 100% data sẵn\nĐịa chỉ làm việc: Lầu 6, Tòa Nhà Kicotrans, Phường Tân Sơn Hòa, Tp. HCM (Phường 2, Quận Tân Bình cũ)",
    "raw_requirements_text": "Không yêu cầu kinh nghiệm\nĐược đào tạo bài bản về kiến thức bán hàng và kiến thức chuyên môn.\nTốt nghiệp Cao Đẳng trở lên.\nYêu thích công việc bán hàng, giao tiếp với khách hàng\nNăng động, cầu tiến, ham học hỏi, khả năng tập trung cao.\nBiết sử dụng MS Office, Email, Mạng xã hội Facebook, Zalo, Skype.\nGiao tiếp tốt, ngoại hình ưa nhìn là một lợi thế.",
    "benefits_list": [
      "Có hỗ trợ Data",
      "Bảo hiểm xã hội",
      "Du lịch hàng năm",
      "Phụ cấp thâm niên",
      "Thưởng tháng 13",
      "Team building",
      "Thưởng hiệu quả làm việc",
      "Cước điện thoại",
      "Xăng xe",
      "Hỗ trợ 100% Data khách hàng",
      "Đào tạo học việc nếu chưa có kinh nghiệm.",
      "Lương hỗ trợ học việc: 5.000.000 đ / tháng",
      "Tổng thu nhập lên tới 30.000.000 đ/ tháng",
      "Ký Hợp đồng sau thời gian thử việc.",
      "Được đào tạo về kỹ năng về quy trình bán hàng",
      "Tham gia Team Building, YEP Party hàng năm cùng công ty",
      "Tham gia đầy đủ Bảo Hiểm Xã Hội và các phúc lợi khác do nhà nước quy định.",
      "Làm việc trong môi trường năng động.",
      "Xét thăng tiến sau 06 tháng làm việc.",
      "Được đào tạo, nâng cao nghiệp vụ thường xuyên."
    ]
  },
  "salary": {
    "raw_salary_text": "10 - 30 triệu",
    "salary_currency": "VND",
    "is_salary_visible": true
  },
  "date": {
    "raw_posted_date": null,
    "raw_updated_at": null,
    "raw_deadline": "01/11/2026"
  },
  "extract": {
    "raw_work_mode": "Làm việc tại văn phòng / Onsite",
    "raw_seniority_text": "Nhân viên",
    "raw_experience_text": "Không yêu cầu",
    "raw_education_text": "Cao Đẳng trở lên",
    "raw_headcount": "10 người",
    "raw_working_time": "Thứ 2 - Thứ 6 (từ 08:00 đến 17:00)\nThứ 7 (từ 08:00 đến 12:00)\nChủ nhật nghỉ",
    "raw_age_text": "Tuổi 18 - 30",
    "raw_gender_text": null
  },
  "other": {
    "raw_category_text": "Hoạt động dịch vụ máy tính và công nghệ thông tin khác",
    "is_content_image": null,
    "auxiliary_features": {}
  }
}
```

---
*Tài liệu được cập nhật theo quy chuẩn Kiến trúc Mới của VN-IT-Job-Mining.*
