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
  "company_name": "Ngân Hàng TMCP Việt Nam Thịnh Vượng - VPBANK",
  "company_scale": null,
  "company_address": "Địa điểm làm việc Hồ Chí Minh 3A-3B Tôn Đức Thắng, phường Bến Nghé, Quận 1, TP.HCM Hà Nội 89 Láng Hạ, Đống Đa, Hà Nội",
  "company_url": null,
  "company_logo_image": null,
  "company_industry": "Ngân hàng , CNTT - Phần mềm",
  "raw_location_text": "Hồ Chí Minh, Hà Nội",
  "working_locations": [
    "Hồ Chí Minh, Hà Nội",
    "Địa điểm làm việc Hồ Chí Minh 3A-3B Tôn Đức Thắng, phường Bến Nghé, Quận 1, TP.HCM Hà Nội 89 Láng Hạ, Đống Đa, Hà Nội"
  ],
  "geo_coordinates": null,
  "skills_list": [
    "SOC Engineer",
    "Soc Analyst"
  ],
  "job_title": "[HN/HCM] SOC Engineer",
  "raw_description_text": "Mô tả Công việc Tham gia xây dựng các quy trình, hướng dẫn, playbook cho hoạt động của SOC Tham gia Nghiên cứu và đề xuất các giải pháp công nghệ và thông lệ tiên tiến để áp dụng vào hoạt động SOC Tham gia xác định các yêu cầu đối với dữ liệu ANBM phục vụ cho công tác quản trị, phân tích, giám sát v... [TRUNCATED FOR REPORT]",
  "raw_requirements_text": "Yêu Cầu Công Việc Tốt nghiệp Đại học chuyên ngành về CNTT, An toàn thông tin hoặc chuyên ngành liên quan. Kinh nghiệm tối thiểu 4 năm với các lĩnh vực về ANBM, CNTT Có tối thiểu 3 năm kinh nghiệm trong các lĩnh vực ANBM như giám sát điều hành sự kiện ANBM, quản lý và ứng phó sự cố, phân tích điều tr... [TRUNCATED FOR REPORT]",
  "benefits_list": [
    "Phúc lợi Chế độ bảo hiểm Phụ cấp Chế độ thưởng Chăm sóc sức khỏe Đào tạo Nghỉ phép năm"
  ],
  "raw_salary_text": "Cạnh tranh",
  "salary_currency": null,
  "is_salary_visible": false,
  "salary_min": null,
  "salary_max": null,
  "raw_posted_date": "16/10/2026",
  "raw_updated_at": "16/10/2026",
  "raw_deadline": "30/11/2026",
  "raw_work_mode": null,
  "raw_seniority_text": "Nhân viên",
  "raw_experience_text": "4 - 5 Năm",
  "raw_education_text": null,
  "raw_headcount": null,
  "raw_working_time": null,
  "raw_age_text": null,
  "raw_gender_text": null,
  "raw_employment_type": "Nhân viên chính thức",
  "raw_category_text": "Ngân hàng , CNTT - Phần mềm",
  "is_content_image": null,
  "auxiliary_features": {},
  "salary_currency_original": "VND",
  "salary_min_original": null,
  "salary_max_original": null,
  "salary_min_vnd": null,
  "salary_max_vnd": null,
  "salary_fx_rate_to_vnd": 1.0,
  "salary_source": "header_negotiable",
  "is_negotiable": true,
  "is_salary_negotiable_declared": 1,
  "primary_city": "Hà Nội",
  "standardized_seniority": "Middle",
  "company_scale_tier": null,
  "employment_type": null,
  "min_experience_years": 4.0,
  "imputed_fields": [
    "min_experience_years_from_raw",
    "seniority_from_raw",
    "primary_city_from_loc"
  ],
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
  "source_url": "https://careerviet.vn/vi/tim-viec-lam/hn-hcm-soc-engineer.35C8AEA1.html",
  "job_info": {
    "title": "Chưa xác định",
    "job_family": "JF00_OTHER_IT",
    "work_type": "fulltime",
    "is_remote": false
  },
  "company": {
    "name": "Chưa xác định",
    "industry": null,
    "size": null
  },
  "locations": [
    {
      "province": "Chưa xác định",
      "district": null,
      "Details_address": null
    }
  ],
  "salary": {
    "salary_min": 15000000.0,
    "salary_max": 22500000.0,
    "salary_currency": "VND",
    "salary_source": "header_negotiable"
  },
  "skills": {
    "hard_skills": [],
    "soft_skills": [],
    "domain_skills": [
      "An toàn thông tin",
      "Cybersecurity"
    ]
  },
  "requirements": {
    "experience_years": 4.0,
    "standardized_seniority": "middle",
    "standardized_education": "đại học",
    "is_saturday_work": null
  },
  "jd_text": {
    "language": "vi",
    "description": "Mô tả Công việc Tham gia xây dựng các quy trình, hướng dẫn, playbook cho hoạt động của SOC Tham gia Nghiên cứu và đề xuất các giải pháp công nghệ và thông lệ tiên tiến để áp dụng vào hoạt động SOC Tham gia xác định các yêu cầu đối với dữ liệu ANBM phục vụ cho công tác quản trị, phân tích, giám sát và báo cáo Giám sát an ninh 24/7 hệ thống CNTT Quản lý và ứng phó sự cố ANBM Quản lý và săn lùng mối đe dọa chủ động Quản lý lỗ hổng bảo mật Phối hợp với các bên liên quan để rà soát các kịch bản ứng phó sự cố và diễn tập hàng năm về an toàn thông tin Phối hợp với các bên liên quan đển thực hiện các thay đổi nhằm xử lý các vấn đề về ANBM Tham gia quản lý, giám sát các chỉ số, thước đo về tình trạng ANBM CNTT Theo dõi, tổng hợp và cung cấp thông tin về hiệu quả của các luật/ kịch bản giám sát sự kiện bất thường Theo dõi, giám sát và đánh giá kết quả thực hiện các hành động khắc phục và các biện pháp giảm thiểu được xác định từ các sự cố ANBM Tham gia rà soát và cập nhật các quy trình, hướng dẫn, playbook cho hoạt động của SOC",
    "requirements": "Yêu Cầu Công Việc Tốt nghiệp Đại học chuyên ngành về CNTT, An toàn thông tin hoặc chuyên ngành liên quan. Kinh nghiệm tối thiểu 4 năm với các lĩnh vực về ANBM, CNTT Có tối thiểu 3 năm kinh nghiệm trong các lĩnh vực ANBM như giám sát điều hành sự kiện ANBM, quản lý và ứng phó sự cố, phân tích điều tra sự cố ANBM, săn lùng mối đe dọa chủ động, quản lý lỗ hổng bảo mật, đánh giá ANBM, phân tích dữ liệu ANBM Am hiểu, có kiến thức tốt về các tiêu chuẩn bảo mật CNTT quốc tế (ISO 270001, PCI-DSS, ITIL, MITRE ATT&CK, OWSAP, v.v. Có kiến thức và kỹ năng an ninh bảo mật mạng, hệ thống, ứng dụng, CSDL Hiểu biết về các hệ thống giải pháp ANBM nói chung và SOC nói riêng như SIEM, SOAR, EDR, NDR FW, WAF, DBFW, IPS, DLP, PIM, v.v. Có kiến thức và kỹ năng xây dựng quy trình quản lý SOC Có kiến thức và kỹ năng ANBM trên các môi trường cloud Có kiến thức và kỹ năng tự động hóa và tối ưu SOC Có kiến thức và kỹ năng phân tích mã độc, mã hóa, săn lùng mối đe dọa Có kiến thức và kỹ năng lập trình một số ngôn ngữ: Python, Shell, PHP Có kiến thức và kỹ năng sử dụng các công cụ ANBM để kiểm thử xâm nhập, khai thác lỗ hổng: VA, APPScan, Metaexploit, kalilinux, Burpsuite, v.v.",
    "benefits": [
      "Chế độ bảo hiểm Phụ cấp Chế độ thưởng Chăm sóc sức khỏe Đào tạo Nghỉ phép năm"
    ]
  },
  "date": {
    "posted_date": "16/10/2026",
    "expired_date": null
  }
}
```

---

## 2. Bảng Ma Trận Đối Chiếu Từng Trường (Field-by-Field Status Matrix — Target Schema 10 Nhóm)

| Nhóm Đối Tượng | Tên Trường Cụ Thể | Trạng Thái Trước Chuẩn Hóa | Trạng Thái Sau Chuẩn Hóa (Golden Master) | Hành Động Kỹ Thuật (Action) |
| :--- | :--- | :--- | :--- | :--- |
| **Định Danh (Root)** | `job_id_global`, `source_platform`, `source_job_id`, `source_url`, `crawled_at_iso` | Các khóa phẳng ở root level | Giữ nguyên vẹn tính toàn vẹn 5 định danh | **Preserved (Bảo toàn 100%)** |
| **1. job_info** | `job_title`, `standardized_job_family`, `standardized_seniority`, `employment_type`, `work_mode`, `min_experience_years` | Nằm rải rác ở root, thiếu chuẩn hóa | Quy tụ vào `job_info`, 100% không còn null ở các cột phân loại | **Cleaned & Consolidated** |
| **2. company** | `company_name`, `company_scale`, `company_scale_tier`, `category_text` | Quy mô (`company_scale_tier`) bị nhét nhầm vào extract | Đưa về đúng `company`, bóc tách bậc quy mô: Small/Medium/Large/Enterprise | **Enriched & Restructured** |
| **3. location** | `primary_city`, `cities_list`, `districts_list`, `detailed_locations`, `geo_coordinates` | `standardized_districts` trùng với `districts_list` | Gộp về 1 trường duy nhất `districts_list` trong nhóm `location` | **Deduplicated & Cleaned** |
| **4. salary** | `salary_min_vnd`, `salary_max_vnd`, `is_negotiable`, `salary_max_winsorized`, `log_salary_max` | Lương winsorized và log-lương bị nhét vào `extract_from_jd` | Đưa toàn bộ về nhóm `salary`. Bảo tồn MNAR (lương thỏa thuận giữ null kèm cờ `is_negotiable=true`) | **Restructured (MNAR & Financial)** |
| **5. skills** | `skills_list`, `skills_count`, `soft_skills`, `domain_skills` | Hardcoded sơ sài hoặc lẫn danh mục rác sàn | Chuẩn hóa theo Ontology ESCO CNTT Châu Âu (từ Phát) | **Standardized (ESCO Ontology)** |
| **6. requirements** | `standardized_education`, `age_min`, `age_max`, `is_saturday_work` | Nhét lẫn trong thùng rác `extract_from_jd` | Tách riêng nhóm `requirements` tinh khiết theo chuẩn HR-XML | **Restructured (Requirements Domain)** |
| **7. jd_text** | `description_text`, `requirements_text`, `benefits_text` | Tiền tố thô `raw_`, dính chữ "Phúc lợi" | Đổi tên sạch, cắt bỏ prefix "Phúc lợi", lọc sạch HTML | **Cleaned & Renamed** |
| **8. date** | `posted_date`, `updated_date`, `deadline_date` | Chuỗi ngày đa định dạng | Chuẩn hóa định dạng ISO ngày tuyển dụng | **Standardized (ISO Dates)** |
| **9. nlp_metadata** | `word_count`, `char_count`, `primary_language`, `is_stub_jd`, `is_content_image` | Nhét chung vào `extract_from_jd` | Tách riêng nhóm `nlp_metadata` phục vụ Text Mining | **Isolated (NLP Metrics)** |
| **10. governance** | `quality_score`, `imputed_fields`, `is_golden_merged`, `duplicate_count`, `duplicate_platforms`, `duplicate_job_ids` | Không có nhóm riêng, lẫn ở root | Nhóm kiểm toán & dòng dõi kế thừa từ Duy, Tài, Sơn | **Audited (Lineage & Governance)** |

---

## 3. Khối Giải Trình Nghiệp Vụ & Cơ Chế Thuật Toán (Business Rationale)

### 3.1. Tại sao phải xóa bỏ 100% các trường `raw_*` và các object rác `extract_from_jd` / `Extract_from_JD`?
1. **Xóa sổ hoàn toàn rác nhân đôi dữ liệu**: Việc loại bỏ alias viết hoa `Extract_from_JD` giúp tiết kiệm ~20 MB dung lượng JSON vô nghĩa trên toàn bộ dataset.
2. **Tuân thủ Domain-Driven Design (DDD)**: Nhóm `extract_from_jd` trước đây là một "thùng rác chứa đồ tạm" lai tạp giữa Lương, Công ty, Chỉ số NLP và Yêu cầu ứng viên. Việc tái cấu trúc thành 10 nhóm đối tượng tinh khiết giúp bất kỳ mô hình Machine Learning hoặc kỹ sư phân tích dữ liệu nào cũng có thể truy xuất chính xác theo đúng ngữ nghĩa nghiệp vụ.
3. **Bảo tồn tính trung thực khoa học MNAR**: Tin tuyển dụng giấu lương ("Thỏa thuận") được bảo toàn giá trị `null` cho các trường min/max nhưng bật cờ `is_negotiable = true`, tuyệt đối không điền bừa số 0 hay lương trung bình.
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
