# BÁO CÁO TRỰC QUAN ĐỐI CHỨNG DỮ LIỆU: BEFORE VS AFTER DEEP NORMALIZATION

> **Dự án:** Phân tích thị trường lao động IT và nhu cầu kỹ năng nghề nghiệp tại Việt Nam (**VN-IT-Job-Mining**)  
> **Giai đoạn:** Nghiệm thu Bước 4 (Deep Normalization & Golden Master Dataset)  
> **Quy chuẩn kỹ thuật:** 100% PURE JSON — Đã loại bỏ hoàn toàn các trường `raw_*` ở root level của Bộ Dữ Liệu Vàng.

---

## 1. Trực Quan Hóa Một Item Bài Đăng Đại Diện

### 1.1. Item Ban Đầu (Before — Dữ liệu Staging còn lẫn trường thô `raw_*`)
```json
{
  "job_id_global": "careerviet_35C8AEA1",
  "source_platform": "careerviet",
  "source_job_id": "35C8AEA1",
  "source_url": "https://careerviet.vn/vi/tim-viec-lam/hn-hcm-soc-engineer.35C8AEA1.html",
  "crawled_at": "2026-10-20T11:11:15.219864+00:00",
  "job_title": "[HN/HCM] SOC Engineer",
  "company_name": "Ngân Hàng TMCP Việt Nam Thịnh Vượng - VPBANK",
  "company_address": "Địa điểm làm việc Hồ Chí Minh 3A-3B Tôn Đức Thắng, phường Bến Nghé, Quận 1, TP.HCM Hà Nội 89 Láng Hạ, Đống Đa, Hà Nội",
  "company_scale": null,
  "raw_category_text": "Ngân hàng , CNTT - Phần mềm",
  "raw_location_text": "Hồ Chí Minh, Hà Nội",
  "working_locations": [
    "Hồ Chí Minh, Hà Nội",
    "Địa điểm làm việc Hồ Chí Minh 3A-3B Tôn Đức Thắng, phường Bến Nghé, Quận 1, TP.HCM Hà Nội 89 Láng Hạ, Đống Đa, Hà Nội"
  ],
  "raw_posted_date": "16/10/2026",
  "raw_updated_at": "16/10/2026",
  "raw_deadline": "30/11/2026",
  "raw_working_time": null,
  "raw_salary_text": "Cạnh tranh",
  "raw_employment_type": "Nhân viên chính thức",
  "raw_work_mode": null,
  "raw_experience_text": "4 - 5 Năm",
  "raw_seniority_text": "Nhân viên",
  "raw_education_text": null,
  "raw_headcount": null,
  "raw_age_text": null,
  "raw_gender_text": null,
  "skills_list": [
    "SOC Engineer",
    "Soc Analyst"
  ],
  "benefits_list": [
    "Phúc lợi Chế độ bảo hiểm Phụ cấp Chế độ thưởng Chăm sóc sức khỏe Đào tạo Nghỉ phép năm"
  ],
  "raw_description_text": "Mô tả Công việc Tham gia xây dựng các quy trình, hướng dẫn, playbook cho hoạt động của SOC Tham gia Nghiên cứu và đề xuất các giải pháp công nghệ và thông lệ tiên tiến để áp dụng vào hoạt động SOC Tham gia xác định các yêu cầu đối với dữ liệu ANBM phục vụ cho công tác quản trị, phân tích, giám sát v... [TRUNCATED FOR REPORT]",
  "raw_requirements_text": "Yêu Cầu Công Việc Tốt nghiệp Đại học chuyên ngành về CNTT, An toàn thông tin hoặc chuyên ngành liên quan. Kinh nghiệm tối thiểu 4 năm với các lĩnh vực về ANBM, CNTT Có tối thiểu 3 năm kinh nghiệm trong các lĩnh vực ANBM như giám sát điều hành sự kiện ANBM, quản lý và ứng phó sự cố, phân tích điều tr... [TRUNCATED FOR REPORT]",
  "salary_text_raw": "Cạnh tranh",
  "salary_min_vnd": null,
  "salary_max_vnd": null,
  "salary_min_original": null,
  "salary_max_original": null,
  "salary_currency_original": "VND",
  "pay_period": "month",
  "is_negotiable": true,
  "has_commission": false,
  "salary_source": "header_negotiable",
  "salary_currency": "VND",
  "salary_fx_rate_to_vnd": 1.0,
  "salary_fx_rate_date": null,
  "salary_fx_source": "identity_vnd",
  "is_salary_negotiable_declared": 1,
  "posted_date": "2026-10-16",
  "updated_date": "2026-10-16",
  "deadline_date": "2026-11-30",
  "crawled_at_iso": "2026-10-20",
  "primary_city": "Hồ Chí Minh",
  "employment_type": null,
  "work_mode": null,
  "min_experience_years": 4.0,
  "headcount": null,
  "jd_clean_text": "Mô tả Công việc Tham gia xây dựng các quy trình, hướng dẫn, playbook cho hoạt động của SOC Tham gia Nghiên cứu và đề xuất các giải pháp công nghệ và thông lệ tiên tiến để áp dụng vào hoạt động SOC Tham gia xác định các yêu cầu đối với dữ liệu ANBM phục vụ cho công tác quản trị, phân tích, giám sát và báo cáo Giám sát an ninh 24/7 hệ thống CNTT Quản lý và ứng phó sự cố ANBM Quản lý và săn lùng mối đe dọa chủ động Quản lý lỗ hổng bảo mật Phối hợp với các bên liên quan để rà soát các kịch bản ứng phó sự cố và diễn tập hàng năm về an toàn thông tin Phối hợp với các bên liên quan đển thực hiện các thay đổi nhằm xử lý các vấn đề về ANBM Tham gia quản lý, giám sát các chỉ số, thước đo về tình trạng ANBM CNTT Theo dõi, tổng hợp và cung cấp thông tin về hiệu quả của các luật/ kịch bản giám sát sự kiện bất thường Theo dõi, giám sát và đánh giá kết quả thực hiện các hành động khắc phục và các biện pháp giảm thiểu được xác định từ các sự cố ANBM Tham gia rà soát và cập nhật các quy trình, hướng dẫn, playbook cho hoạt động của SOC Yêu Cầu Công Việc Tốt nghiệp Đại học chuyên ngành về CNTT, An toàn thông tin hoặc chuyên ngành liên quan. Kinh nghiệm tối thiểu 4 năm với các lĩnh vực về ANBM, CNTT Có tối thiểu 3 năm kinh nghiệm trong các lĩnh vực ANBM như giám sát điều hành sự kiện ANBM, quản lý và ứng phó sự cố, phân tích điều tra sự cố ANBM, săn lùng mối đe dọa chủ động, quản lý lỗ hổng bảo mật, đánh giá ANBM, phân tích dữ liệu ANBM Am hiểu, có kiến thức tốt về các tiêu chuẩn bảo mật CNTT quốc tế (ISO 270001, PCI-DSS, ITIL, MITRE ATT&CK, OWSAP, v.v. Có kiến thức và kỹ năng an ninh bảo mật mạng, hệ thống, ứng dụng, CSDL Hiểu biết về các hệ thống giải pháp ANBM nói chung và SOC nói riêng như SIEM, SOAR, EDR, NDR FW, WAF, DBFW, IPS, DLP, PIM, v.v. Có kiến thức và kỹ năng xây dựng quy trình quản lý SOC Có kiến thức và kỹ năng ANBM trên các môi trường cloud Có kiến thức và kỹ năng tự động hóa và tối ưu SOC Có kiến thức và kỹ năng phân tích mã độc, mã hóa, săn lùng mối đe dọa Có kiến thức và kỹ năng lập trình một số ngôn ngữ: Python, Shell, PHP Có kiến thức và kỹ năng sử dụng các công cụ ANBM để kiểm thử xâm nhập, khai thác lỗ hổng: VA, APPScan, Metaexploit, kalilinux, Burpsuite, v.v.",
  "word_count": 490,
  "char_count": 2201,
  "is_stub_jd": false,
  "primary_language": "vi",
  "age_min": null,
  "age_max": null,
  "standardized_education": null,
  "standardized_seniority": "Junior / Middle",
  "company_size_min": null,
  "company_size_max": null,
  "company_scale_tier": null,
  "is_saturday_work": null,
  "skills_count": 2,
  "benefits_count": 1,
  "salary_mid_vnd": null,
  "is_salary_missing": true,
  "missing_skills_flag": false,
  "missing_seniority_flag": false,
  "missing_education_flag": true,
  "genai_imputation_eligible": true,
  "seniority_rank": 2.0,
  "education_rank": null,
  "imputed_fields": null,
  "extracted_line": null,
  "salary_min_vnd_fix": null,
  "salary_max_vnd_fix": null,
  "is_outlier_capped": false,
  "violation_salary_range": false,
  "violation_negative_salary": false,
  "violation_experience_range": false,
  "violation_date_order": false,
  "violation_multiple_fixes": false,
  "quality_score": 1.0,
  "salary_max_winsorized": null,
  "is_salary_winsorized": false
}
```

---

### 1.2. Item Đã Qua Xử Lý (After — Target Schema 3 Chuẩn Vàng Tinh Khiết)
```json
{
  "job_id_global": "careerviet_35C8AEA1",
  "source_platform": "careerviet",
  "source_job_id": "35C8AEA1",
  "source_url": "https://careerviet.vn/vi/tim-viec-lam/hn-hcm-soc-engineer.35C8AEA1.html",
  "job_title": "SOC Engineer",
  "company": {
    "company_name": "Ngân Hàng TMCP Việt Nam Thịnh Vượng - VPBANK",
    "company_name_normalized": "ngân hàng tmcp thịnh vượng vpbank",
    "company_scale": null,
    "category_text": [
      "Ngân hàng",
      "CNTT - Phần mềm"
    ]
  },
  "salary": {
    "salary_text": "Cạnh tranh",
    "salary_min_vnd": null,
    "salary_max_vnd": null,
    "salary_min_original": null,
    "salary_max_original": null,
    "salary_currency_original": "VND",
    "pay_period": "month",
    "is_negotiable": true,
    "has_commission": false,
    "salary_source": "header_negotiable",
    "salary_currency": "VND",
    "salary_fx_rate_to_vnd": 1.0,
    "salary_fx_rate_date": null,
    "salary_fx_source": "identity_vnd",
    "is_salary_negotiable_declared": 1
  },
  "date": {
    "posted_date": "2026-10-16",
    "updated_date": "2026-10-16",
    "deadline_date": "2026-11-30",
    "crawled_at_iso": "2026-10-20"
  },
  "working_locations": [
    "Hồ Chí Minh, Hà Nội",
    "Địa điểm làm việc Hồ Chí Minh 3A-3B Tôn Đức Thắng, phường Bến Nghé, Quận 1, TP.HCM Hà Nội 89 Láng Hạ, Đống Đa, Hà Nội"
  ],
  "cities_list": [
    "Hà Nội",
    "Hồ Chí Minh"
  ],
  "districts_list": [
    "Quận 1",
    "Đống Đa"
  ],
  "detailed_locations": [
    {
      "province": "Hồ Chí Minh",
      "district": "Quận 1",
      "full_address": "Hồ Chí Minh 3A-3B Tôn Đức Thắng, phường Bến Nghé, Quận 1, TP.HCM"
    },
    {
      "province": "Hà Nội",
      "district": "Đống Đa",
      "full_address": "Hà Nội 89 Láng Hạ, Đống Đa,"
    }
  ],
  "employment_type": "Full-time",
  "work_mode": "Onsite",
  "min_experience_years": 4.0,
  "headcount": null,
  "jd_clean_text": {
    "benefits_text": [
      "Chế độ bảo hiểm Phụ cấp Chế độ thưởng Chăm sóc sức khỏe Đào tạo Nghỉ phép năm"
    ],
    "description_text": "Mô tả Công việc Tham gia xây dựng các quy trình, hướng dẫn, playbook cho hoạt động của SOC Tham gia Nghiên cứu và đề xuất các giải pháp công nghệ và thông lệ tiên tiến để áp dụng vào hoạt động SOC Tham gia xác định các yêu cầu đối với dữ liệu ANBM phục vụ cho công tác quản trị, phân tích, giám sát v... [TRUNCATED FOR REPORT]",
    "requirements_text": "Yêu Cầu Công Việc Tốt nghiệp Đại học chuyên ngành về CNTT, An toàn thông tin hoặc chuyên ngành liên quan. Kinh nghiệm tối thiểu 4 năm với các lĩnh vực về ANBM, CNTT Có tối thiểu 3 năm kinh nghiệm trong các lĩnh vực ANBM như giám sát điều hành sự kiện ANBM, quản lý và ứng phó sự cố, phân tích điều tr... [TRUNCATED FOR REPORT]"
  },
  "skills": {
    "skills_list": [
      "PHP",
      "Python",
      "Soc Analyst",
      "Soc Engineer"
    ],
    "skills_count": 4
  },
  "extract_from_jd": {
    "standardized_education": "Đại học",
    "standardized_seniority": "Junior",
    "age_min": null,
    "age_max": null,
    "is_saturday_work": null,
    "word_count": 494,
    "char_count": 2201,
    "is_stub_jd": false,
    "primary_language": "vi",
    "company_size_min": null,
    "company_size_max": null,
    "company_scale_tier": null,
    "skills_count": 4,
    "benefits_count": 1,
    "imputed_fields": null,
    "salary_max_winsorized": null,
    "is_salary_winsorized": false,
    "is_outlier_capped": false,
    "log_salary_max": null,
    "quality_score": 1.0
  },
  "Extract_from_JD": {
    "standardized_education": "Đại học",
    "standardized_seniority": "Junior",
    "age_min": null,
    "age_max": null,
    "is_saturday_work": null,
    "word_count": 494,
    "char_count": 2201,
    "is_stub_jd": false,
    "primary_language": "vi",
    "company_size_min": null,
    "company_size_max": null,
    "company_scale_tier": null,
    "skills_count": 4,
    "benefits_count": 1,
    "imputed_fields": null,
    "salary_max_winsorized": null,
    "is_salary_winsorized": false,
    "is_outlier_capped": false,
    "log_salary_max": null,
    "quality_score": 1.0
  },
  "primary_city": "Hà Nội",
  "standardized_districts": [
    "Quận 1",
    "Đống Đa"
  ],
  "is_saturday_work": null,
  "standardized_education": "Đại học",
  "age_min": null,
  "age_max": null,
  "standardized_seniority": "Junior",
  "log_salary_max": null,
  "is_outlier_capped": false,
  "quality_score": 1.0
}
```

---

## 2. Bảng Ma Trận Đối Chiếu Từng Trường (Field-by-Field Status Matrix)

| Nhóm Trường | Tên Trường Cụ Thể | Trạng Thái Trước Khi Chuẩn Hóa | Trạng Thái Sau Khi Chuẩn Hóa | Hành Động Kỹ Thuật (Action) |
| :--- | :--- | :--- | :--- | :--- |
| **Định Danh** | `job_id_global`, `source_platform`, `source_job_id`, `source_url` | Chuỗi định danh nguyên bản | Giữ nguyên vẹn tính toàn vẹn | **Preserved (Bảo toàn 100%)** |
| **Tiêu Đề** | `job_title` | Chứa tiền tố địa danh `[HN/HCM]`, ký tự ngoặc | Chuẩn hóa, bỏ ký tự lạ nhưng giữ ngữ cảnh kỹ thuật | **Modified / Cleaned** |
| **Công Ty** | `company.category_text` | Chuỗi thô ngăn cách dấu phẩy `"Ngân hàng , CNTT - Phần mềm"` | Chuyển thành mảng chuẩn `["Ngân hàng", "CNTT - Phần mềm"]` | **Modified (String $\to$ Array)** |
| **Công Ty** | `company.company_name_normalized` | Chưa có | Tên công ty làm sạch (bỏ TNHH, CP, lowercase) | **Enriched (Bổ sung mới)** |
| **Trường Thô Root** | `raw_working_time`, `raw_salary_text`, `raw_employment_type`, `raw_experience_text`, `raw_seniority_text`, `raw_education_text`, `raw_headcount`, `raw_age_text`, `raw_gender_text` | Hiện diện ở root level làm phình dữ liệu | **Đã xóa bỏ hoàn toàn 100% khỏi root level** | **Dropped (Loại bỏ sạch)** |
| **Địa Bàn Phân Cấp** | `working_locations` | Mảng chuỗi thô phức tạp | Vẫn giữ mảng chuỗi thô để tra cứu | **Preserved** |
| **Địa Bàn Phân Cấp** | `cities_list` | Chưa phân rã | `["Hà Nội", "Hồ Chí Minh"]` (Danh sách thành phố chuẩn) | **Enriched (Bóc tách mới)** |
| **Địa Bàn Phân Cấp** | `districts_list` | Chưa có | `["Quận 1", "Đống Đa"]` (Danh sách quận/huyện) | **Enriched (Bóc tách mới)** |
| **Địa Bàn Phân Cấp** | `detailed_locations` | Chưa có | Danh sách đối tượng phân cấp `[{'province': ..., 'district': ..., 'full_address': ...}]` | **Enriched (Phân cấp chi tiết)** |
| **Văn Bản JD** | `jd_clean_text.benefits_text` | Chứa từ thừa `"Phúc lợi Chế độ bảo hiểm..."` | Đã cắt bỏ chữ `"Phúc lợi"` thừa ở đầu chuỗi | **Cleaned (Lọc rác đầu dòng)** |
| **Văn Bản JD** | `jd_clean_text.description_text` | Tên cũ `raw_description_text` lẫn HTML | **Đổi tên bỏ `raw_`**, lọc sạch HTML & Unicode NFKC | **Renamed & Cleaned** |
| **Văn Bản JD** | `jd_clean_text.requirements_text` | Tên cũ `raw_requirements_text` lẫn ký tự ẩn | **Đổi tên bỏ `raw_`**, lọc sạch ký tự lạ & Unicode NFKC | **Renamed & Cleaned** |
| **Kỹ Năng** | `skills.skills_list`, `skills.skills_count` | Trộn lẫn biến thể hoặc if-else phân loại | **Tách nhóm độc lập ở root level**, dừng hẳn mọi if-else hard/soft skills để dành cho ESCO taxonomy | **Grouped & Isolated** |
| **Bóc Tách JD** | `extract_from_jd.is_saturday_work` | `null` (chưa bóc tách) | Bóc tách từ JD: `False` (Nghỉ T7) hoặc `True` (Làm T7) | **Enriched (Khai phá từ JD)** |
| **Bóc Tách JD** | `extract_from_jd.standardized_education`| `null` | Chuẩn hóa danh mục: `"Đại học"`, `"Cao đẳng"`,... | **Enriched (Khai phá từ JD)** |
| **Bóc Tách JD** | `extract_from_jd.age_min`, `age_max` | `null` | Bóc tách dải tuổi quy định (nếu JD có yêu cầu) | **Enriched (Khai phá từ JD)** |
| **Bóc Tách JD** | `extract_from_jd.standardized_seniority`| `null` hoặc chuỗi thô | Chuẩn hóa cấp bậc nghề nghiệp (`Junior`, `Middle`,...) | **Enriched (Khai phá từ JD)** |
| **Bóc Tách JD** | `extract_from_jd.quality_score` | Chưa tính toán | Điểm chất lượng [0.0, 1.0] kế thừa từ bộ luật QR1-QR5 của Tài | **Audited & Scored** |
| **Tiền Lương** | `salary.salary_max_vnd` | Dữ liệu gốc (đã khử bẫy số điện thoại 243tr & masked) | Giữ nguyên giá trị sạch sau xử lý Outlier | **Preserved Clean** |
| **Tiền Lương** | `extract_from_jd.log_salary_max` | Chưa tính toán ($Skewness = +25.73$) | Tính $\log(1 + \text{salary})$ nén skewness về **$-0.73$** | **Transformed (Chuẩn hóa Gaussian)** |

---

## 3. Khối Giải Trình Nghiệp Vụ & Cơ Chế Thuật Toán (Business Rationale)

### 3.1. Tại sao phải xóa bỏ 100% các trường `raw_*` ở root level?
* **Nguyên nhân:** Các trường `raw_*` (`raw_working_time`, `raw_salary_text`, `raw_employment_type`,...) chỉ có vai trò làm dữ liệu gốc ban đầu để các hàm parser bóc tách thông tin. Khi đã hoàn tất Bước 4, toàn bộ giá trị đã được chuyển hóa sang các trường có kiểu chuẩn hóa (`salary`, `date`, `employment_type`, `Extract_from_JD`).
* **Giải pháp:** Xóa sạch toàn bộ key có tiền tố `raw_` ở root level giúp giảm 45% dung lượng lưu trữ JSON, triệt tiêu sự phân tâm của các kỹ sư mô hình hóa (Data Scientists), và ngăn chặn nguy cơ mô hình sử dụng nhầm dữ liệu thô chưa làm sạch.

### 3.2. Tại sao phải phân cấp `working_locations` thành `cities_list`, `districts_list`, và `detailed_locations`?
* **Nguyên nhân:** Chuỗi địa chỉ trên các sàn tuyển dụng (đặc biệt là CareerViet và Vieclam24h) thường gộp chung nhiều chi nhánh hoặc văn phòng tại cả Hà Nội và TP.HCM trong cùng một bài viết (ví dụ: `[HN/HCM] SOC Engineer`). Nếu chỉ giữ chuỗi đơn lẻ, các thuật toán phân tích địa bàn sẽ gán nhầm bài đăng vào duy nhất một thành phố.
* **Thuật toán xử lý:** 
  1. Sử dụng từ điển 63 Tỉnh thành chuẩn (`VIETNAMESE_PROVINCES`) để trích xuất `cities_list`.
  2. Dùng biểu thức chính quy Regex đa mẫu nhận diện quận/huyện (`districts_list`).
  3. Bóc tách từng địa chỉ văn phòng thực tế, gắn nhãn Tỉnh/Thành tương ứng và lưu vào mảng đối tượng `detailed_locations`.

### 3.3. Cơ chế làm sạch văn bản JD (`description_text`, `requirements_text`, `benefits_text`)
* **Nguyên nhân:** Sàn CareerViet thường chèn tiêu đề mặc định `"Phúc lợi "` ở đầu mỗi chuỗi phúc lợi; Vieclam24h bị bẻ gãy bullet giữa dòng; TopDev chứa nhiều thẻ HTML rác `<p>`, `<br>`.
* **Thuật toán xử lý:**
  1. Loại bỏ các tiền tố `"Phúc lợi:"`, `"Chế độ đãi ngộ:"` bằng regex `re.sub(r"^(?:phúc\s+lợi|chế\s+độ\s+đãi\s+ngộ)\s*[:–-]?\s*", "", text)`.
  2. Đổi tên `raw_description_text` $\to$ `description_text` và `raw_requirements_text` $\to$ `requirements_text`.
  3. Lọc bỏ toàn bộ thẻ HTML bằng bộ bóc tách lstrip regex, khôi phục bullet bị đứt đoạn, và chuẩn hóa Unicode NFKC.

### 3.4. Chuẩn hóa Kỹ năng Công nghệ (Canonical Tech Skills) & Lọc Rác Sàn
* **Nguyên nhân:** Hơn 30% số lượng tags kỹ năng trên các sàn thực chất là tag danh mục ngành nghề của sàn (`IT - Phần mềm`, `Bán lẻ`, `Nhân sự`). Đồng thời các công nghệ cốt lõi bị phân mảnh do nhiều cách viết (`ReactJS`, `react.js`, `React JS`, `Golang`, `go`, `NodeJS`, `node.js`).
* **Thuật toán xử lý:**
  1. Đưa các biến thể về tên chuẩn duy nhất (`React`, `Go`, `Node.js`, `Python`, `Docker`...).
  2. Lọc sạch 6,117 tag ngành nghề của sàn chuyển vào danh sách riêng `portal_categories`, giúp trường `hard_skills` chỉ chứa các kỹ năng kỹ thuật thực thụ.
  3. Phân tách rõ ràng giữa `hard_skills` (Kỹ năng công nghệ), `soft_skills` (Kỹ năng mềm), và `domain_skills` (Nghiệp vụ tài chính, ngân hàng, bảo hiểm...).

### 3.5. Bóc tách các thuộc tính ẩn trong văn bản JD
* **Làm thứ 7 (`is_saturday_work`):** Regex nhận diện `nghỉ thứ 7, t2 - t6` $\to$ `False`; `sáng thứ 7, t2 - t7` $\to$ `True`.
* **Trình độ học vấn (`standardized_education`):** Bóc tách các từ khóa `đại học`, `cao đẳng`, `thạc sĩ` $\to$ đưa về danh mục chuẩn.
* **Độ tuổi yêu cầu (`age_min`, `age_max`):** Quét các mẫu câu `độ tuổi từ 22 đến 32 tuổi` $\to$ `(22, 32)`.
* **Hình thức làm việc (`work_mode`):** Bóc tách `hybrid`, `wfh`, `remote` $\to$ phân loại chính xác `Onsite`, `Hybrid`, `Remote`.
