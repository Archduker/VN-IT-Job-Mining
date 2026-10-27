# ĐẶC TẢ QUY CHUẨN DỮ LIỆU VÀNG: TARGET SCHEMA 11 KHÓA
*(Golden Master Target Schema 11 Keys Specification & Data Dictionary)*

> **Phiên bản:** 2.0 (Modern Data Mining Standard)  
> **Áp dụng cho:** `data/curated/golden_master.json` và `data/curated/curated_flat_golden_jobs.json`  
> **Nguyên tắc cốt lõi:**  
> 1. **100% PURE RFC 8259 JSON:** Cấm tuyệt đối giá trị `NaN`, `Infinity`, cấm lưu trữ file `.parquet` hay `.csv` trong phân tầng Preprocessing.  
> 2. **Cấu trúc phẳng phân cấp 2 tầng (Strict 2-Level Nested):** Đúng 11 khóa root ở tầng 1, toàn bộ thuộc tính chi tiết nằm ở tầng 2.  
> 3. **Zero-Null Lương (Complete Salary Coverage):** Không có giá trị null ở trường lương; các tin thỏa thuận hoặc thiếu lương được dự đoán qua ma trận Market Anchor kết hợp Gemini (`salary_source = "predicted"`).  
> 4. **100% Tiếng Việt Chuẩn Hóa:** Toàn bộ tiêu đề, mô tả, yêu cầu và phúc lợi bằng tiếng Anh đều được tự động dịch sang tiếng Việt sạch thẻ HTML, gắn cờ `language = "vi"`.

---

## 1. Danh Sách 11 Khóa Gốc (Root Keys Overview)

Toàn bộ các bản ghi trong `data/curated/golden_master.json` đều tuân thủ chính xác 11 khóa cấp 1 sau:

| STT | Khóa Gốc (Root Key) | Kiểu Dữ Liệu | Số Thuộc Tính Con | Ý Nghĩa Khai Phá Dữ Liệu |
| :---: | :--- | :--- | :---: | :--- |
| 1 | `job_id_global` | `string` | 0 | Định danh duy nhất toàn cục dạng `<platform>_<id>` xuyên suốt pipeline |
| 2 | `source_platform` | `string` | 0 | Nguồn sàn tuyển dụng (TopCV, ITviec, VietnamWorks, TopDev...) |
| 3 | `source_url` | `string` | 0 | Đường dẫn URL chính tắc (Canonical URL) phục vụ Data Lineage |
| 4 | `job_info` | `object` | 4 | Thông tin công việc cơ bản: tiêu đề, vai trò, hình thức làm việc |
| 5 | `company` | `object` | 3 | Thông tin doanh nghiệp: tên, lĩnh vực hoạt động, quy mô nhân sự |
| 6 | `locations` | `object` | 4 | Thông tin địa lý: tỉnh/thành phố chính, địa chỉ cụ thể, tọa độ geo |
| 7 | `salary` | `object` | 4 | Dải lương chuẩn VND (Zero-null), cờ thỏa thuận và nguồn gốc lương |
| 8 | `skills` | `object` | 4 | Phân tầng kỹ năng 3 lớp: công nghệ lõi, kỹ thuật yêu cầu, kỹ năng bổ trợ, kỹ năng mềm |
| 9 | `requirements` | `object` | 5 | Tiêu chí tuyển dụng: cấp bậc chuẩn hóa, số năm kinh nghiệm, học vấn, độ tuổi |
| 10 | `jd_text` | `object` | 4 | Nội dung chi tiết bài đăng (tiếng Việt sạch HTML): mô tả, yêu cầu, phúc lợi, ngôn ngữ |
| 11 | `date` | `object` | 3 | Các mốc thời gian: ngày đăng, ngày cào, ngày hết hạn |

---

## 2. Từ Điển Dữ Liệu Chi Tiết (Data Dictionary)

### 2.1. Nhóm Khóa Định Danh & Nguồn Gốc

#### 1. `job_id_global` (`string`, Bắt buộc)
- **Mô tả:** Khóa chính toàn cục xác định duy nhất bài đăng trên toàn bộ 8 sàn.
- **Quy tắc tạo:** Ghép từ mã sàn viết thường và ID gốc: `<source_platform>_<original_id>`.
- **Ví dụ:** `"vietnamworks_1892011"`, `"itviec_senior-python-dev-1234"`.

#### 2. `source_platform` (`string`, Bắt buộc)
- **Mô tả:** Tên sàn tuyển dụng nguồn nơi bài đăng được thu thập.
- **Giá trị Enum:** `itviec`, `topcv`, `vietnamworks`, `topdev`, `jobsgo`, `careerbuilder`, `glints`, `vieclam24h`.

#### 3. `source_url` (`string`, Bắt buộc)
- **Mô tả:** Đường dẫn URL trực tiếp tới tin tuyển dụng gốc.
- **Ràng buộc:** Đã được loại bỏ các tham số tracking (`utm_*`, `fbclid`).

---

### 2.2. Nhóm Thuộc Tính Công Việc (`job_info`)

```json
"job_info": {
  "title": "Senior Python Backend Engineer",
  "job_role": "Backend Engineer",
  "working_model": "hybrid",
  "work_format": "full_time"
}
```

| Trường Con | Kiểu Dữ Liệu | Giá Trị Cho Phép (Enum / Format) | Diễn Giải |
| :--- | :--- | :--- | :--- |
| `title` | `string` | Chuỗi văn bản tiếng Việt sạch | Tiêu đề công việc được chuẩn hóa, loại bỏ các tag rác như [HOT], (Urgent) |
| `job_role` | `string` | 12 Nhóm vai trò chuẩn (Backend, Frontend, Fullstack, DevOps, Data/AI...) | Vai trò phân loại phục vụ phân cụm nghề nghiệp |
| `working_model`| `string` | `onsite`, `hybrid`, `remote`, `unspecified` | Chế độ làm việc tại văn phòng hay từ xa |
| `work_format` | `string` | `full_time`, `part_time`, `internship`, `freelance`, `unspecified` | Hình thức hợp đồng tuyển dụng |

---

### 2.3. Nhóm Thuộc Tính Doanh Nghiệp (`company`)

```json
"company": {
  "name": "Tập Đoàn Công Nghệ FPT",
  "industry": "Phần mềm & Dịch vụ CNTT",
  "size_range": "1000+"
}
```

| Trường Con | Kiểu Dữ Liệu | Diễn Giải |
| :--- | :--- | :--- |
| `name` | `string` | Tên công ty đầy đủ, loại bỏ tiền tố/hậu tố viết tắt không cần thiết |
| `industry` | `string` | Ngành nghề hoạt động của doanh nghiệp |
| `size_range` | `string` | Quy mô nhân sự (ví dụ: `1-50`, `50-200`, `200-500`, `500-1000`, `1000+`, `unspecified`) |

---

### 2.4. Nhóm Thuộc Tính Địa Lý (`locations`)

```json
"locations": {
  "primary_city": "Hồ Chí Minh",
  "addresses": ["Tòa nhà FPT Tân Thuận, Quận 7, TP.HCM"],
  "geo_coordinates": [
    {"lat": 10.7412, "lon": 106.7214}
  ],
  "all_locations": ["Hồ Chí Minh", "Đà Nẵng"]
}
```

| Trường Con | Kiểu Dữ Liệu | Ràng Buộc & Diễn Giải |
| :--- | :--- | :--- |
| `primary_city` | `string` | Tên tỉnh/thành phố chính chuẩn hóa theo danh mục 63 tỉnh thành Việt Nam (ví dụ: `Hồ Chí Minh`, `Hà Nội`, `Đà Nẵng`...) |
| `addresses` | `list[string]` | Danh sách địa chỉ trụ sở/chi nhánh cụ thể |
| `geo_coordinates`| `list[object]` | Tọa độ địa lý vĩ độ (`lat`) và kinh độ (`lon`) |
| `all_locations`| `list[string]` | Toàn bộ các tỉnh thành mà tin tuyển dụng áp dụng |

---

### 2.5. Nhóm Thuộc Tính Lương (`salary`) - Quy Chuẩn Zero-Null

> [!IMPORTANT]
> **Khế Ước Zero-Null Lương:**  
> Không chấp nhận bất kỳ giá trị `null` nào tại các trường số của `salary`. Dữ liệu thiếu lương hoặc ghi lương thỏa thuận (`is_salary_negotiable = true`) sẽ được điền thông số lương ước lượng thị trường qua thuật toán Market Anchor Matrix kết hợp Gemini, đồng thời đánh dấu `salary_source = "predicted"`.

```json
"salary": {
  "salary_min_vnd": 35000000.0,
  "salary_max_vnd": 55000000.0,
  "is_salary_negotiable": false,
  "salary_source": "explicit_range"
}
```

| Trường Con | Kiểu Dữ Liệu | Ràng Buộc | Ý Nghĩa & Nguồn Gốc |
| :--- | :--- | :--- | :--- |
| `salary_min_vnd` | `float` | `> 0.0` | Mức lương tối thiểu (VND/tháng). Nếu gốc là USD, đã quy đổi theo tỷ giá cố định 25,400. |
| `salary_max_vnd` | `float` | `>= salary_min_vnd` | Mức lương tối đa (VND/tháng). |
| `is_salary_negotiable`| `boolean` | `true` hoặc `false` | Cờ bảo toàn bản chất MNAR (Missing Not At Random): tin gốc có phải là lương thỏa thuận hay không |
| `salary_source` | `string` | Enum bên dưới | Nguồn gốc tạo ra mức lương |

#### Bảng Phân Loại `salary_source`:
1. `explicit_range`: Tin tuyển dụng ghi rõ dải lương 2 đầu (ví dụ: 20 triệu - 35 triệu).
2. `explicit_min`: Tin chỉ ghi mức sàn tối thiểu (ví dụ: Từ 30 triệu). Mức max được ước tính theo tỷ lệ dải lương chuẩn.
3. `explicit_max`: Tin chỉ ghi mức trần tối đa (ví dụ: Lên đến 50 triệu). Mức min được ước tính ngược.
4. `predicted`: Tin ghi "Thương lượng" hoặc khuyết lương; dải lương được dự đoán hoàn toàn dựa trên sự kết hợp giữa khung Market Anchor `(platform, seniority)` và mô hình Gemini.

---

### 2.6. Nhóm Kỹ Năng (`skills`) - Phân Tầng 3 Lớp Chuyên Biệt

```json
"skills": {
  "primary_tech_stack": ["python", "django", "fastapi"],
  "required_technical": ["postgresql", "redis", "docker", "restful api"],
  "preferred_skills": ["kubernetes", "aws", "kafka"],
  "soft_skills": ["làm việc nhóm", "tư duy giải quyết vấn đề", "tiếng anh giao tiếp"]
}
```

| Trường Con | Kiểu Dữ Liệu | Định Dạng | Vai Trò Trong Data Mining |
| :--- | :--- | :--- | :--- |
| `primary_tech_stack` | `list[string]` | Chữ thường, phân cách bởi dấu phẩy | 1 đến 5 ngôn ngữ/framework lõi quyết định vị trí công việc |
| `required_technical` | `list[string]` | Chữ thường | Danh sách kỹ thuật bắt buộc phải có để ứng tuyển |
| `preferred_skills` | `list[string]` | Chữ thường | Kỹ năng ưu tiên, điểm cộng khi ứng tuyển |
| `soft_skills` | `list[string]` | Tiếng Việt chữ thường | Kỹ năng mềm, khả năng thích ứng và ngoại ngữ |

---

### 2.7. Nhóm Yêu Cầu Tuyển Dụng (`requirements`)

```json
"requirements": {
  "standardized_seniority": "senior",
  "years_experience_min": 4.0,
  "years_experience_max": 7.0,
  "education_level": "bachelor",
  "age_range": "25-35"
}
```

| Trường Con | Kiểu Dữ Liệu | Ràng Buộc & Enum | Diễn Giải |
| :--- | :--- | :--- | :--- |
| `standardized_seniority`| `string` | `intern`, `fresher`, `junior`, `middle`, `senior`, `lead`, `manager`, `director`, `unspecified` | Cấp bậc chuyên môn đã chuẩn hóa về chữ thường |
| `years_experience_min` | `float` | `>= 0.0` | Số năm kinh nghiệm tối thiểu yêu cầu (ví dụ: 0.0 cho Fresher, 3.0 cho Senior) |
| `years_experience_max` | `float` | `>= years_experience_min` hoặc `null` | Số năm kinh nghiệm tối đa |
| `education_level` | `string` | `high_school`, `college`, `bachelor`, `master`, `doctorate`, `unspecified` | Yêu cầu bằng cấp học vấn tối thiểu |
| `age_range` | `string` | `unspecified` hoặc dạng `min-max` | Độ tuổi ứng viên nếu bài đăng có quy định |

---

### 2.8. Nhóm Nội Dung Văn Bản JD (`jd_text`)

> [!NOTE]
> **Quy Chuẩn Ngôn Ngữ & Làm Sạch:**  
> Toàn bộ thẻ HTML (`<p>`, `<div>`, `<li>`...) đã được bóc tách và loại bỏ hoàn toàn. Các tiền tố thừa như "Mô tả công việc:", "Yêu cầu:", "Quyền lợi:" đã được cắt tỉa sạch sẽ. Nếu bài đăng gốc bằng tiếng Anh, Gemini Agent sẽ dịch nội dung sang tiếng Việt và đặt `language = "vi"`.

```json
"jd_text": {
  "description": "Phát triển và bảo trì các hệ thống backend chịu tải cao sử dụng Python và FastAPI...",
  "requirements": "Tối thiểu 3 năm kinh nghiệm lập trình backend. Nắm vững cơ sở dữ liệu quan hệ PostgreSQL...",
  "benefits": "Lương tháng 13, thưởng hiệu quả kinh doanh. Bảo hiểm sức khỏe cao cấp, hỗ trợ thiết bị làm việc...",
  "language": "vi"
}
```

---

### 2.9. Nhóm Thời Gian (`date`)

```json
"date": {
  "posted_date": "2026-03-15",
  "crawled_date": "2026-03-20",
  "expired_date": "2026-04-15"
}
```

| Trường Con | Kiểu Dữ Liệu | Định Dạng Chuẩn | Diễn Giải |
| :--- | :--- | :--- | :--- |
| `posted_date` | `string` | ISO 8601 `YYYY-MM-DD` | Ngày nhà tuyển dụng đăng tin lên sàn |
| `crawled_date`| `string` | ISO 8601 `YYYY-MM-DD` | Ngày crawler của hệ thống thu thập bài đăng |
| `expired_date`| `string` | ISO 8601 `YYYY-MM-DD` hoặc `null` | Ngày hết hạn nhận hồ sơ |

---

## 3. Cấu Trúc Bảng Phẳng (Flat View Mapping)

Bên cạnh file cấu trúc đa tầng `golden_master.json`, hệ thống đồng thời xuất bản tệp bảng phẳng duy nhất [`data/curated/curated_flat_golden_jobs.json`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/data/curated/curated_flat_golden_jobs.json) thông qua phương thức `to_flat_target_record()` của [`TargetSchemaFormatter`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/preprocessing/normalization/target_schema_formatter.py):

| Tên Cột Phẳng (Flat Column) | Khóa Gốc Nguồn | Kiểu Dữ Liệu Phẳng |
| :--- | :--- | :--- |
| `job_id_global` | `job_id_global` | `string` |
| `source_platform` | `source_platform` | `string` |
| `source_url` | `source_url` | `string` |
| `job_title` | `job_info.title` | `string` |
| `job_role` | `job_info.job_role` | `string` |
| `working_model` | `job_info.working_model` | `string` |
| `company_name` | `company.name` | `string` |
| `primary_city` | `locations.primary_city` | `string` |
| `salary_min_vnd` | `salary.salary_min_vnd` | `float` |
| `salary_max_vnd` | `salary.salary_max_vnd` | `float` |
| `is_salary_negotiable`| `salary.is_salary_negotiable` | `bool` |
| `salary_source` | `salary.salary_source` | `string` |
| `primary_tech_stack` | `skills.primary_tech_stack` | `list[string]` |
| `required_technical` | `skills.required_technical` | `list[string]` |
| `preferred_skills` | `skills.preferred_skills` | `list[string]` |
| `standardized_seniority`| `requirements.standardized_seniority`| `string` |
| `years_experience_min`| `requirements.years_experience_min` | `float` |
| `years_experience_max`| `requirements.years_experience_max` | `float` |
| `jd_description` | `jd_text.description` | `string` |
| `posted_date` | `date.posted_date` | `string` |

---

## 4. Ví Dụ Bản Ghi Chuẩn Mẫu (Complete Golden JSON Record)

```json
{
  "job_id_global": "itviec_senior-python-dev-1029",
  "source_platform": "itviec",
  "source_url": "https://itviec.com/it-jobs/senior-python-backend-engineer",
  "job_info": {
    "title": "Senior Python Backend Engineer",
    "job_role": "Backend Engineer",
    "working_model": "hybrid",
    "work_format": "full_time"
  },
  "company": {
    "name": "Tech Corp Vietnam",
    "industry": "Software Services",
    "size_range": "200-500"
  },
  "locations": {
    "primary_city": "Hồ Chí Minh",
    "addresses": [
      "Quận 1, TP. Hồ Chí Minh"
    ],
    "geo_coordinates": [
      {
        "lat": 10.7769,
        "lon": 106.7009
      }
    ],
    "all_locations": [
      "Hồ Chí Minh"
    ]
  },
  "salary": {
    "salary_min_vnd": 35000000.0,
    "salary_max_vnd": 55000000.0,
    "is_salary_negotiable": false,
    "salary_source": "explicit_range"
  },
  "skills": {
    "primary_tech_stack": [
      "python",
      "fastapi",
      "django"
    ],
    "required_technical": [
      "postgresql",
      "docker",
      "redis"
    ],
    "preferred_skills": [
      "aws",
      "kubernetes"
    ],
    "soft_skills": [
      "tư duy logic",
      "làm việc nhóm"
    ]
  },
  "requirements": {
    "standardized_seniority": "senior",
    "years_experience_min": 4.0,
    "years_experience_max": 7.0,
    "education_level": "bachelor",
    "age_range": "unspecified"
  },
  "jd_text": {
    "description": "Tham gia thiết kế và triển khai kiến trúc backend vi dịch vụ...",
    "requirements": "Có ít nhất 4 năm kinh nghiệm thực chiến với Python và hệ quản trị CSDL...",
    "benefits": "Gói bảo hiểm sức khỏe quốc tế, thưởng tháng 13 và review lương 2 lần/năm...",
    "language": "vi"
  },
  "date": {
    "posted_date": "2026-03-20",
    "crawled_date": "2026-03-22",
    "expired_date": "2026-04-20"
  }
}
```
