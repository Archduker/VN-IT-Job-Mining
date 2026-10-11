# Hướng Dẫn Phân Tích & Đối Chiếu Bóc Tách Dữ Liệu Tuyển Dụng CareerViet (CareerViet Crawl & Comparative Analysis)

> **Nhánh thực hiện**: `crawl/careerviet`  
> **Người thực hiện**: Nhóm trưởng (Team Leader)  
> **Nguồn tuyển dụng**: CareerViet (`https://careerviet.vn`)  
> **Phiên bản chuẩn**: Data Contract Schema v1, Kế thừa `BaseCrawler`  
> **Trạng thái**:  **HOÀN THÀNH REFACTOR 100% & PASS DATA QUALITY CHECKER**

---

## 1. Kiến Trúc Thu Thập Dữ Liệu (Crawler Architecture)

CareerViet áp dụng cơ chế **Server-Side Rendering (SSR)** truyền thống, không sử dụng WAF chặn IP quá gắt gao như Cloudflare, cho phép thu thập qua thư viện HTTP tiêu chuẩn (`requests` / `urllib` / `HttpClient`).

Phiên bản refactor mới hỗ trợ 2 chế độ:
1. **Chế độ trực tuyến (Online)**:
   - Quét listing danh mục CNTT: `https://careerviet.vn/viec-lam/cntt-phan-mem-c1-vi.html`.
   - Thu thập danh sách `job_links` từ selector `div.job-item a.job-title, a[href*='/tim-viec-lam/']`.
   - Tải chi tiết từng trang qua `HttpClient` với độ trễ jitter ngẫu nhiên `1.0s - 2.5s`.
   - Lưu trữ mã HTML (`--save-html`) vào thư mục `crawlers/sources/careerviet/sample_htmls/{job_id}.html`.
2. **Chế độ ngoại tuyến (Offline `--local-html-dir`)**:
   - Tải và parse trực tiếp từ các file HTML đã lưu để phục vụ kiểm thử đơn vị, CI/CD và kiểm toán chất lượng tức thì mà không cần kết nối mạng.

```
[Listing Page: /viec-lam/cntt-phan-mem-c1-vi.html]
                  │
                  ▼
         [Trích xuất Job URLs]
                  │
                  ├── Online: HttpClient tải HTML chi tiết
                  └── Offline: Đọc từ --local-html-dir
                  │
                  ▼
            [parse_item()]
                  ├── Title: h1.title, .job-title
                  ├── Company: a.job-company-name, a.employer
                  ├── Salary: parse_salary_detail() -> JobSalary
                  ├── Tags: classify_job_tags() -> JobTags (null benefits rule)
                  ├── Description/Req/Ben: text_to_clean_lines() (lọc bullet •, -, *)
                  └── Language: detect_language() -> _meta.language
```

---

## 2. Bảng Đối Chiếu 5 Tin Tuyển Dụng Thực Tế (HTML vs. JSON Output)

Dữ liệu được kiểm chứng thực tế tại [`crawlers/sources/careerviet/test_5_jobs.json`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/careerviet/test_5_jobs.json):

| Trường Schema | 35C89996 (ERP Consultant - VI) | 35C8737C (IP Network - EN) | 35C87378 (Transmission - EN) | 35C87374 (IP Engineer - EN) | 35C81470 (Site Solution - EN) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`title`** | Chuyên Viên Tư Vấn Triển Khai ERP | IP Network Engineer | Transmission Engineer | IP Engineer | [URGENT] Site Solution Engineer |
| **`company`** | CÔNG TY CỔ PHẦN CÔNG NGHỆ FOXAI | ZTE HK LIMITED | ZTE HK LIMITED | ZTE HK LIMITED | ZTE HK LIMITED |
| **`language`** | `vi` | `en` | `en` | `en` | `en` |
| **`salary_text`** | `12 Tr - 35 Tr VND` | `Cạnh tranh` | `Cạnh tranh` | `Cạnh tranh` | `Cạnh tranh` |
| **`salary_min`** | `12.0` | `null` | `null` | `null` | `null` |
| **`salary_max`** | `35.0` | `null` | `null` | `null` | `null` |
| **`salary_currency`** | `VND` | `null` | `null` | `null` | `null` |
| **`is_negotiable`** | `False` | `False` | `False` | `False` | `False` |
| **`deadline_text`** | `06/11/2026` | `08/11/2026` | `08/11/2026` | `08/11/2026` | `08/11/2026` |
| **`location_text`** | Hà Nội | Hà Nội | Hà Nội | Hà Nội | Hà Nội |
| **`description_list`** | 5 dòng nhiệm vụ ERP sạch | 8 dòng nhiệm vụ IP sạch | 7 dòng nhiệm vụ truyền dẫn sạch | 6 dòng nhiệm vụ IP sạch | 8 dòng nhiệm vụ hạ tầng sạch |
| **`requirements_list`**| 5 dòng yêu cầu bằng cấp/SQL | 5 dòng yêu cầu CCNA/CCNP | 5 dòng yêu cầu thiết bị mạng | 5 dòng yêu cầu hạ tầng IP | 6 dòng yêu cầu giải pháp trạm |
| **`benefits_list`** | 9 dòng phúc lợi FOXAI | Đầy đủ đãi ngộ ZTE | Đầy đủ đãi ngộ ZTE | Đầy đủ đãi ngộ ZTE | Đầy đủ đãi ngộ ZTE |
| **`tags.skills`** | `["Kỹ sư CNTT", "IT", "ERP", ...]` | `["Kỹ sư CNTT", "IT Network"]` | `["Transmission", "Telecom"]` | `["IP", "Networking"]` | `["Site Engineer", "Telecom"]` |
| **`tags.benefits`** | `null` (tuân thủ quy tắc) | `null` | `null` | `null` | `null` |

---

## 3. Các Điểm Khác Biệt & Xử Lý Biên Kỹ Thuật

1. **Chuẩn hóa mức lương có đơn vị `Tr`**:
   - Chuỗi gốc: `12 Tr - 35 Tr VND` $\rightarrow$ Hàm `parse_salary_detail` đã nhận diện chính xác `12.0` và `35.0` triệu VND, chu kỳ `month`.
   - Chuỗi lương `Cạnh tranh` $\rightarrow$ Được lưu nguyên văn, `salary_min = None, salary_max = None`.
2. **Quy tắc thẻ Tags Phúc lợi (`tags.benefits = None`)**:
   - CareerViet không có cụm pill tag riêng biệt cho quyền lợi (mà đưa vào section mô tả bài viết). Theo quy tắc nghiệp vụ trong Skill, hệ thống tuyệt đối không nhét văn bản bài viết vào tag, mà gán `tags.benefits = null`.
3. **Làm sạch Bullet rác**:
   - Văn bản gốc chứa các ký tự `•`, `-`, `*`, `1.`, `2)`. Hàm `text_to_clean_lines` đã bóc tách từng dòng sạch, sẵn sàng cho bước Embedding và NLP.

---

## 4. Kết Quả Kiểm Định Chất Lượng (Data Quality Result)

Chạy kiểm tra tự động qua `DataQualityChecker`:
```text
Data Quality Passed for crawlers/sources/careerviet/test_5_jobs.json:
- total_records: 5
- valid_schema_records: 5 (100.0%)
- unique_keys: 5 (100.0%)
- missing_titles: 0
- missing_companies: 0
- missing_descriptions: 0
- passed: True
```
