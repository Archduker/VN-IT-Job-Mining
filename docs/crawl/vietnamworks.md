# Hướng Dẫn Phân Tích & Đối Chiếu Bóc Tách Dữ Liệu Tuyển Dụng VietnamWorks (VietnamWorks Search API & Data Contract Mapping)

> **Nhánh thực hiện**: `crawl/vietnamworks`  
> **Người thực hiện**: Nhóm trưởng (Team Leader)  
> **Nguồn tuyển dụng**: VietnamWorks (`https://www.vietnamworks.com`)  
> **Giao thức**: Search API (`https://ms.vietnamworks.com/job-search/v1.0/search`)  
> **Phiên bản chuẩn**: Data Contract Schema v1, Kế thừa `BaseCrawler`  
> **Trạng thái**:  **HOÀN THÀNH REFACTOR 100% & PASS DATA QUALITY CHECKER**

---

## 1. Kiến Trúc Thu Thập Dữ Liệu (Crawler Architecture)

VietnamWorks là cổng thông tin việc làm lâu đời và quy mô lớn nhất tại Việt Nam. Thay vì cào HTML phân mảnh dễ bị chặn bot, crawler sử dụng trực tiếp **Search Microservice API chính thức**:
`POST https://ms.vietnamworks.com/job-search/v1.0/search`

### Ưu thế vượt trội của giải pháp Search API:
- **Tốc độ cao**: 1 request lấy về tới 50 jobs đầy đủ chi tiết HTML (`jobDescription`, `jobRequirement`).
- **Không lo Cloudflare Turnstile**: Endpoint này phục vụ trực tiếp cho Search Container của trang chủ.
- **Dữ liệu cấu trúc có sẵn**: Trả về trực tiếp mảng `skills`, `benefits`, dải lương số `salaryMin`, `salaryMax`, chuỗi `prettySalary`.

```
[Search API: ms.vietnamworks.com/job-search/v1.0/search]
                         │
                         ▼
             [fetch_items(): Payload JSON]
                         │
                         ▼
                   [parse_item()]
                         ├── Title: item["jobTitle"]
                         ├── Company: item["companyName"]
                         ├── Salary: kết hợp prettySalary + salaryMin/Max -> JobSalary
                         ├── Tags: skills + benefits -> JobTags
                         ├── Description/Requirements: text_to_clean_lines()
                         └── Language: detect_language() -> _meta.language
```

---

## 2. Bảng Đối Chiếu Dữ Liệu Thực Tế (API Payload vs. Schema v1)

Dữ liệu được kiểm chứng thực tế tại [`crawlers/sources/vietnamworks/test_5_jobs.json`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/vietnamworks/test_5_jobs.json):

| Trường Schema | Job 1 (Senior Software Eng - EN) | Job 2 (Senior Mobile Flutter - EN) | Job 3 (Senior Backend Java - EN) | Job 4 (Fullstack C#/.NET - VI) | Job 5 (Data Engineer - EN) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`title`** | Senior Software Engineer (Java/Python/Go) | Senior Mobile Developer (Flutter) | Senior Backend Developer (Java) | Kỹ Sư Fullstack (C#, .NET, Angular) | Senior Data Engineer (Spark, AWS) |
| **`company`** | Tech Innovation Global | VinaApp Solutions | FinTech Pioneer Corp | FPT Information System | BigData Global Ltd |
| **`language`** | `en` | `en` | `en` | `vi` | `en` |
| **`salary_text`** | `Thương lượng` | `1,500 - 2,500 USD` | `25 - 45 Triệu VND` | `Thương lượng` | `2,000 - 3,500 USD` |
| **`salary_min`** | `null` | `1500.0` | `25.0` | `null` | `2000.0` |
| **`salary_max`** | `null` | `2500.0` | `45.0` | `null` | `3500.0` |
| **`salary_currency`** | `null` | **`USD`** | **`VND`** | `null` | **`USD`** |
| **`deadline_text`** | `2026-11-20T00:00:00Z` | `2026-11-15T00:00:00Z` | `2026-11-25T00:00:00Z` | `2026-11-30T00:00:00Z` | `2026-11-10T00:00:00Z` |
| **`description_list`** | Danh sách nhiệm vụ kiến trúc microservices sạch | Danh sách tính năng app mobile sạch | Danh sách thiết kế high-throughput APIs sạch | Danh sách phát triển web enterprise sạch | Danh sách xây dựng Data Lake sạch |
| **`requirements_list`**| 4+ năm kinh nghiệm Java/Python | 3+ năm Flutter/Dart, Bloc | 4+ năm Java Spring Boot, Kafka | 3+ năm .NET Core, SQL Server | 4+ năm PySpark, Hadoop, AWS |
| **`benefits_list`** | Laptop, Du lịch, Thưởng KPI | Mac M3, Bảo hiểm cao cấp | Thưởng dự án, Tháng 13 | Đào tạo chứng chỉ quốc tế | Remote allowance, Thưởng ESOP |
| **`tags.skills`** | `["Java/.Net/Python", "Golang"]` | `["Flutter", "Dart", "Mobile"]` | `["Java", "Spring Boot", "Kafka"]` | `[".NET", "C#", "Angular"]` | `["Python", "Spark", "AWS"]` |
| **`tags.benefits`** | `["Máy tính xách tay", "Cơ hội du lịch"]`| `["Bảo hiểm sức khỏe"]` | `["Thưởng thành tích"]` | `["Đào tạo chuyên môn"]` | `["Làm việc linh hoạt"]` |

---

## 3. Các Điểm Kỹ Thuật Đã Tối Ưu Hóa

1. **Khử Bullet và Thẻ HTML Rác**:
   - `jobDescription` và `jobRequirement` từ API chứa các thẻ `<p>`, `<ul>`, `<li>` và các ký tự bullet `•`, `-`.
   - Đã làm sạch triệt để bằng `text_to_clean_lines`, trả về mảng chuỗi thuần túy sẵn sàng cho bước Tokenize & Clean.
2. **Chuẩn Hóa Thẻ Tags 3 Nhóm**:
   - `tags.skills`: Trích xuất từ mảng `skills` với trường `skillName`.
   - `tags.benefits`: Trích xuất từ mảng `benefits` với trường `benefitNameVI` (hoặc `benefitName`).
   - `tags.requirements`: VietnamWorks không có pill tags cho yêu cầu $\rightarrow$ Gán `None` đúng quy tắc.
3. **Chế độ Ngoại Tuyến `--local-json-file`**:
   - Cho phép truyền file JSON snapshot đã lưu để phục vụ test ngoại tuyến mà không cần kết nối mạng.

---

## 4. Kết Quả Kiểm Định Chất Lượng (Data Quality Result)

Chạy kiểm tra tự động qua `DataQualityChecker`:
```text
Data Quality Passed for crawlers/sources/vietnamworks/test_5_jobs.json:
- total_records: 5
- valid_schema_records: 5 (100.0%)
- unique_keys: 5 (100.0%)
- missing_titles: 0
- missing_companies: 0
- missing_descriptions: 0
- passed: True
```
