# ĐẶC TẢ TÍCH HỢP NGUỒN: VIECLAM24H (07)
## Hệ thống Tiền xử lý & Khai thác Dữ liệu VN-IT-Job-Mining (Phân nhóm Mới)

---

## 1. Tổng quan Nguồn & Đặc tính Dữ liệu Thô

- **Tên nguồn (Source Platform)**: `vieclam24h`
- **Kiểu dữ liệu cào (Payload Type)**: Categorized Dictionary Payload
- **Khóa Envelope chính**: `metadata` (hoặc `_meta`) và `raw_payload` (hoặc `raw`).
- **Tổng số trường thô ghi nhận**: ~13 trường cấp 1 (và các cấu trúc con lồng nhau).

---

## 2. Phân loại Ánh xạ Theo Kiến trúc Mới

### Khóa Định danh Phẳng (Top-Level Flat Identifiers)
- **`job_id_global`**: Khóa toàn cục kết hợp (`vieclam24h_<id>`)
- **`source_platform`**: `vieclam24h`
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


- **Thông tin công ty (`company`)**: Nằm gọn trong object `company` gồm `company.name`, `company.size` (quy mô), `company.address`.
- **Trường ẩn trong `general_info` (`extract`)**: `level` (cấp bậc), `hiring_quantity` (chỉ tiêu), `working_type` (loại hình).
- **Địa điểm làm việc cụ thể (`địa điểm`)**: Nằm trong `working_address` và `general_info.workplaces`.
- **Nhóm `other`**: Lưu `keywords` (mảng từ khóa tìm kiếm) và danh mục ngành để lọc tin chéo.
        

---

## 4. Dữ liệu Mẫu Thực tế (Sample JSON Data)

### 4.1. Mẫu Envelope Thô Ban đầu (Raw JSON Envelope)
Lấy trực tiếp từ tệp: `data/vieclam24h/raw/2026-10-20/200969132_v1.json`

```json
{
  "metadata": {
    "job_id": "200969132",
    "source": "vieclam24h",
    "source_url": "https://vieclam24h.vn/dien-dien-tu-dien-lanh/me-linh-ky-thuat-ha-tang-khong-yeu-cau-kinh-nghiem-thu-nhap-12-16m-c41p210000160id200969132.html",
    "scraped_at": "2026-10-20T12:55:06.493635+00:00",
    "scraper_version": "2.0.0",
    "version": 1,
    "content_hash": "0e020fe10efc278334bdc69730bd563e38a1b28aabb66386ca731e9f3812873d",
    "canonical_hash": "0e020fe10efc278334bdc69730bd563e38a1b28aabb66386ca731e9f3812873d",
    "field_hashes": {
      "title": "f897f66ad7e09437010a3a88ff9b754ad15df3799799052164327c8b4f6c5ec5",
      "salary": "ba525ddf44accce55759c8138e53f40d8cef346e49a1883899a8ff3740514723",
      "deadline": "23b04a84b0aba1edc22c3c77dae06999c420e033acd8a93c655822282e8d56f4",
      "location_summary": "6ac69af836de8007fe7da283ce10821ab484ae1af98a30ae13b0b23914a0bb79",
      "experience_summary": "928cf20bd7530106e089c2d85a7daf0f51ce74223c869403970f24482cf851a8",
      "description": "7d9b79c83a0c9233a1cd218c0eb6cfa769e85aae25e4344b857fecc53cf7199a",
      "requirements": "7b137c2a99cbcddd579a6ede6e075dfcb95d3ee0e901701f12b5c7400976ba79",
      "benefits": "98ebd842a9ace1b3fd52c0fa18ae25502afbc0e04cfd25a4aea8dc512ad9aa9f",
      "working_time": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "working_address": "4de15e199d2565fef650e231de5779b204c3e8f5120c2b01847c95e06981df9d",
      "general_info": "7963a5b09522fb2987813048d666069b7a64e3e3426a163bf6a461b0809e7b0e",
      "keywords": "28cfc44ff7887d69b47a91389e484dd48be1c02fa8b3613f8231994e0a6e0579",
      "company": "96ed848813cecbc549826d5ab91c1d4ea7ed3e3c25caa610064e59d03202bc5a"
    }
  },
  "raw_payload": {
    "title": "[Mê Linh] Kỹ Thuật Hạ Tầng - Không Yêu Cầu Kinh Nghiệm - Thu Nhập 12-16M",
    "salary": "12 - 16 triệu",
    "deadline": "30/11/2026",
    "location_summary": "Hà Nội",
    "experience_summary": "Chưa có kinh nghiệm",
    "description": [
      "Triển khai, lắp đặt và bảo trì hệ thống đài trạm, cáp hạ tầng viễn thông",
      "Vận hành, bảo dưỡng định kỳ nhà trạm; nâng cấp, thay thế thiết bị khi cần",
      "Kiểm tra, xử lý sự cố kỹ thuật liên quan đến mạng lưới viễn thông",
      "Thực hiện các công việc ngoại vi: treo cáp, hạ ngầm cáp, hàn nối cáp quang",
      "Cấp tín hiệu cho các tuyến truyền dẫn",
      "Đo kiểm, xác định điểm lỗi trên sợi cáp quang bằng thiết bị chuyên dụng",
      "Thực hiện các công việc theo phân công của quản lý"
    ],
    "requirements": [
      "Nam, 20 – 35 tuổi, sức khỏe tốt, sẵn sàng",
      "làm việc thực tế tại hiện trường",
      "Tốt nghiệp Trung cấp trở lên đa dạng các ngành nghề ưu tiên mảng kỹ thuật",
      ": Điện tử viễn thông, CNTT, Điện – Điện tử, Tự động hóa hoặc liên quan…",
      "Ứng viên trái ngành có cơ hội khi có kinh nghiệm làm công việc kỹ thuật thực tế",
      "Mở rộng với sinh viên năm cuối chờ tốt nghiệp",
      "Không yêu cầu kinh nghiệm – được đào tạo bài bản về công việc",
      "Có tin
... (truncated for readability)
```

### 4.2. Mẫu sau khi Tích hợp Chuẩn hóa (Tổ chức theo Kiến trúc Mới)
Bản ghi đã được phân loại rõ ràng theo Header phẳng + 8 nhóm thuộc tính:

```json
{
  "identifiers": {
    "job_id_global": "vieclam24h_200969132",
    "source_platform": "vieclam24h",
    "source_job_id": "200969132",
    "source_url": "https://vieclam24h.vn/dien-dien-tu-dien-lanh/me-linh-ky-thuat-ha-tang-khong-yeu-cau-kinh-nghiem-thu-nhap-12-16m-c41p210000160id200969132.html",
    "crawled_at": "2026-10-20T12:55:06.493635+00:00"
  },
  "company": {
    "company_name": "Công Ty Cổ Phần Viễn Thông Fpt",
    "company_scale": null,
    "company_address": "Tầng 18 Tòa nhà FPT Tower, số 10 Phạm Văn Bạch, Q.Cầu Giấy, Hà Nội, Việt Nam.",
    "company_url": null,
    "company_logo_image": null,
    "company_industry": null
  },
  "location": {
    "raw_location_text": "Hà Nội",
    "working_locations": [
      "Tầng 18 Tòa nhà FPT Tower, số 10 Phạm Văn Bạch, Q.Cầu Giấy, Hà Nội, Việt Nam.",
      "Hà Nội : Mê Linh, Xã Mê Linh (Huyện Mê Linh | Huyện Mê Linh, Hà Nội, Vĩnh Phúc cũ)",
      "Hà Nội : Mỹ Đức, Xã Mỹ Đức (Huyện Mỹ Đức, Hà Nội cũ)",
      "Hà Nội : Thanh Oai, Xã Thanh Oai (Huyện Thanh Oai, Hà Nội cũ)",
      "Hà Nội : Thường tín, Xã Thường Tín (Huyện Thường Tín, Hà Nội cũ)",
      "Hà Nội : Thạch thất, Xã Thạch Thất (Huyện Thạch Thất, Hà Nội cũ)"
    ],
    "geo_coordinates": null
  },
  "skills": {
    "skills_list": [
      "kỹ thuật cơ sở hạ tầng",
      "Mê Linh",
      "kỹ sư hạ tầng",
      "huyện mê linh",
      "không yêu cầu kinh nghiệm",
      "kỹ sư hạ tầng đô thị",
      "kỹ sư thiết kế hạ tầng",
      "huyện mê linh tỉnh vĩnh phúc",
      "không cần kinh nghiệm",
      "kế toán không yêu cầu kinh nghiệm",
      "Điện - Điện tử - Điện lạnh",
      "Công Ty Cổ Phần Viễn ..."
    ]
  },
  "jd": {
    "job_title": "[Mê Linh] Kỹ Thuật Hạ Tầng - Không Yêu Cầu Kinh Nghiệm - Thu Nhập 12-16M",
    "raw_description_text": "Triển khai, lắp đặt và bảo trì hệ thống đài trạm, cáp hạ tầng viễn thông Vận hành, bảo dưỡng định kỳ nhà trạm; nâng cấp, thay thế thiết bị khi cần Kiểm tra, xử lý sự cố kỹ thuật liên quan đến mạng lưới viễn thông Thực hiện các công việc ngoại vi: treo cáp, hạ ngầm cáp, hàn nối cáp quang Cấp tín hiệu cho các tuyến truyền dẫn Đo kiểm, xác định điểm lỗi trên sợi cáp quang bằng thiết bị chuyên dụng Thực hiện các công việc theo phân công của quản lý",
    "raw_requirements_text": "Nam, 20 – 35 tuổi, sức khỏe tốt, sẵn sàng làm việc thực tế tại hiện trường Tốt nghiệp Trung cấp trở lên đa dạng các ngành nghề ưu tiên mảng kỹ thuật : Điện tử viễn thông, CNTT, Điện – Điện tử, Tự động hóa hoặc liên quan… Ứng viên trái ngành có cơ hội khi có kinh nghiệm làm công việc kỹ thuật thực tế Mở rộng với sinh viên năm cuối chờ tốt nghiệp Không yêu cầu kinh nghiệm – được đào tạo bài bản về công việc Có tinh thần trách nhiệm, kỷ luật và chủ động trong công việc Có định hướng phát triển lâu dài trong lĩnh vực kỹ thuật viễn thông Tư duy “Khách hàng là trọng tâm”",
    "benefits_list": [
      "Thu nhập 12 – 16 triệu/tháng, thu nhập năm lên đến 250 triệu Được đào tạo chuyên môn thực tế, có người hướng dẫn trực tiếp Cơ hội phát triển lên Trưởng nhóm kỹ thuật Lương tháng 13, thưởng thi đua, thưởng nhân viên xuất sắc năm Làm việc tại doanh nghiệp quy mô lớn trong lĩnh vực viễn thông hàng đầu Việt Nam Tham gia đầy đủ BHXH, BHYT, BHTN, KPCĐ khi ký HĐ chính thức Hưởng các chương trình phúc lợi: bảo hiểm sức khỏe TINcare, khám sức khỏe định kỳ, nghỉ mát, teambuilding… Môi trường làm việc chuyên nghiệp, ổn định, lâu dài"
    ]
  },
  "salary": {
    "raw_salary_text": "12 - 16 triệu",
    "salary_currency": "VND",
    "is_salary_visible": true
  },
  "date": {
    "raw_posted_date": "20/10/2026",
    "raw_updated_at": null,
    "raw_deadline": "30/11/2026"
  },
  "extract": {
    "raw_work_mode": null,
    "raw_seniority_text": "Nhân viên",
    "raw_experience_text": "Chưa có kinh nghiệm",
    "raw_education_text": null,
    "raw_headcount": "20",
    "raw_working_time": null,
    "raw_age_text": null,
    "raw_gender_text": null
  },
  "other": {
    "raw_category_text": "Điện - Điện tử - Điện lạnh / IT Phần cứng - Mạng / IT Phần mềm",
    "is_content_image": null,
    "auxiliary_features": {
      "keywords": [
        "kỹ thuật cơ sở hạ tầng",
        "Mê Linh",
        "kỹ sư hạ tầng",
        "huyện mê linh",
        "không yêu cầu kinh nghiệm",
        "kỹ sư hạ tầng đô thị",
        "kỹ sư thiết kế hạ tầng",
        "huyện mê linh tỉnh vĩnh phúc",
        "không cần kinh nghiệm",
        "kế toán không yêu cầu kinh nghiệm",
        "Điện - Điện tử - Điện lạnh",
        "Công Ty Cổ Phần Viễn ..."
      ]
    }
  }
}
```

---
*Tài liệu được cập nhật theo quy chuẩn Kiến trúc Mới của VN-IT-Job-Mining.*
