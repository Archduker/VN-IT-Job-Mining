# Báo cáo Phân tích API / Dữ liệu Nguồn & Hướng dẫn Chạy tay Crawler (VN-IT-Job-Mining)

> **Dự án**: VN-IT-Job-Mining — Thu thập và Phân tích Dữ liệu Tuyển dụng CNTT Việt Nam  
> **Phiên bản tài liệu**: 1.0.0  
> **Cập nhật ngày**: 2026-10-08  
> **Đối tượng áp dụng**: Kỹ sư dữ liệu (Data Engineers), Người kiểm thử (QA/Reviewers), Vận hành (DevOps)  

---

## Mục lục

1. [Phần 1: Hướng dẫn Chạy tay Từng Crawler (Manual Run Guide)](#phần-1-hướng-dẫn-chạy-tay-từng-crawler-manual-run-guide)
   - [1.1 Chuẩn bị môi trường thực thi](#11-chuẩn-bị-môi-trường-thực-thi)
   - [1.2 Sử dụng bộ điều phối tập trung `run.py`](#12-sử-dụng-bộ-điều-phối-tập-trung-runpy)
   - [1.3 Chạy qua `Makefile`](#13-chạy-qua-makefile)
   - [1.4 Chạy trực tiếp từng Python module](#14-chạy-trực-tiếp-từng-python-module)
   - [1.5 Cấu trúc lưu trữ dữ liệu đầu ra](#15-cấu-trúc-lưu-trữ-dữ-liệu-đầu-ra)
   - [1.6 Xử lý lỗi và gỡ rối (Troubleshooting)](#16-xử-lý-lỗi-và-gỡ-rối-troubleshooting)
2. [Phần 2: Bảng Tổng hợp Ma trận Khả năng Bóc tách 6 Nguồn (Source Capability Matrix)](#phần-2-bảng-tổng-hợp-ma-trận-khả-năng-bóc-tách-6-nguồn-source-capability-matrix)
3. [Phần 3: Phân tích Chuyên sâu Dữ liệu & Sample JSON Thực tế của 6 Nguồn](#phần-3-phân-tích-chuyên-sâu-dữ-liệu--sample-json-thực-tế-của-6-nguồn)
   - [3.1 TopDev (REST API v2)](#31-topdev-rest-api-v2)
   - [3.2 VietnamWorks (Search API POST)](#32-vietnamworks-search-api-post)
   - [3.3 ITviec (Server-Rendered HTML & JSON-LD)](#33-itviec-server-rendered-html--json-ld)
   - [3.4 CareerViet (HTML Scraping)](#34-careerviet-html-scraping)
   - [3.5 Việc Làm 24h (Next.js SSR `__NEXT_DATA__`)](#35-việc-làm-24h-nextjs-ssr-__next_data__)
   - [3.6 TopCV (Playwright Browser + Card Extraction)](#36-topcv-playwright-browser--card-extraction)
4. [Phần 4: Hướng dẫn Quy trình và Câu lệnh Đối chiếu Kết quả Thực tế](#phần-4-hướng-dẫn-quy-trình-và-câu-lệnh-đối-chiếu-kết-quả-thực-tế)
   - [4.1 Lệnh CLI in đẹp (Pretty-print) JSON đa dòng từ file kết quả](#41-lệnh-cli-in-đẹp-pretty-print-json-đa-dòng-từ-file-kết-quả)
   - [4.2 Checklist 10 tiêu chí kiểm tra dữ liệu đầu ra (Data Quality QA)](#42-checklist-10-tiêu-chí-kiểm-tra-dữ-liệu-đầu-ra-data-quality-qa)

---

## Phần 1: Hướng dẫn Chạy tay Từng Crawler (Manual Run Guide)

### 1.1 Chuẩn bị môi trường thực thi

Hệ thống yêu cầu Python 3.12+ và môi trường ảo `.venv` đã cài đặt đầy đủ dependencies.

```bash
# 1. Di chuyển vào thư mục gốc dự án
cd /home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining

# 2. Kiểm tra môi trường ảo
python3 -m venv .venv
source .venv/bin/activate

# 3. Cài đặt các gói phụ thuộc (nếu chưa cài)
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Cài đặt Playwright Browser (cho TopCV)
playwright install chromium
```

> [!NOTE]
> Bạn có thể chạy trực tiếp bằng binary `.venv/bin/python` mà không cần kích hoạt môi trường ảo.

---

### 1.2 Sử dụng bộ điều phối tập trung `run.py`

File [`run.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/run.py) tại thư mục gốc là giao diện dòng lệnh thống nhất, tự động định tuyến đến crawler tương ứng, quản lý checkpoint và in ra thông số chạy cùng câu lệnh đối chiếu JSON.

#### Cú pháp chung:
```bash
.venv/bin/python run.py --source <TÊN_NGUỒN> [--max-items <SỐ_LƯỢNG>] [--output-dir <THƯ_MỤC>] [-v]
```

#### Các tùy chọn (Arguments):
| Tham số | Dạng ngắn | Mặc định | Ý nghĩa |
| :--- | :---: | :---: | :--- |
| `--source` | `-s` | *Bắt buộc* | Nguồn cần cào: `topdev`, `vietnamworks`, `itviec`, `careerviet`, `vieclam24h`, `topcv` |
| `--max-items` | `-m` | `30` | Số lượng tin mới tối đa trong 1 batch (dùng `1` hoặc `5` để test nhanh) |
| `--output-dir` | `-o` | `data` | Thư mục gốc lưu kết quả JSONL |
| `--checkpoint-dir`| - | `data/<source>` | Thư mục lưu file `checkpoint.json` |
| `--batch-id` | - | `None` | Mã định danh batch (mặc định tự sinh dạng `YYYY-MM-DD_<source>_<seq>`) |
| `--verbose` | `-v` | `False` | Hiển thị log mức độ DEBUG |

#### Bảng lệnh chạy nhanh (Quick Test - 1 tin mỗi nguồn):
```bash
# 1. TopDev (REST API)
.venv/bin/python run.py --source topdev --max-items 1

# 2. VietnamWorks (Search API POST)
.venv/bin/python run.py --source vietnamworks --max-items 1

# 3. ITviec (Listing & HTML/JSON-LD)
.venv/bin/python run.py --source itviec --max-items 1

# 4. CareerViet (HTML Scraping)
.venv/bin/python run.py --source careerviet --max-items 1

# 5. Việc Làm 24h (Next.js SSR)
.venv/bin/python run.py --source vieclam24h --max-items 1

# 6. TopCV (Playwright Browser)
.venv/bin/python run.py --source topcv --max-items 1
```

---

### 1.3 Chạy qua `Makefile`

Dự án cung cấp các mục tiêu tiện lợi qua Makefile (chạy mặc định 450 items cho batch lớn):

```bash
make crawl-topdev          # Chạy cào TopDev
make crawl-vietnamworks    # Chạy cào VietnamWorks
make crawl-itviec          # Chạy cào ITviec
make crawl-careerviet      # Chạy cào CareerViet
make crawl-vieclam24h      # Chạy cào Việc Làm 24h
make crawl-topcv           # Chạy cào TopCV
```

---

### 1.4 Chạy trực tiếp từng Python module

Nếu cần gỡ lỗi trực tiếp mã nguồn của từng crawler:

```bash
# TopDev
PYTHONPATH=. .venv/bin/python -m crawlers.sources.topdev.crawler --max-items 1

# VietnamWorks
PYTHONPATH=. .venv/bin/python -m crawlers.sources.vietnamworks.crawler --max-items 1

# ITviec
PYTHONPATH=. .venv/bin/python -m crawlers.sources.itviec.crawler --max-items 1

# CareerViet
PYTHONPATH=. .venv/bin/python -m crawlers.sources.careerviet.crawler --max-items 1

# Việc Làm 24h
PYTHONPATH=. .venv/bin/python -m crawlers.sources.vieclam24h.crawler --max-items 1

# TopCV
PYTHONPATH=. .venv/bin/python -m crawlers.sources.topcv.crawler --max-items 1
```

---

### 1.5 Cấu trúc lưu trữ dữ liệu đầu ra

Sau khi chạy, dữ liệu được phân vùng (partitioned) theo tiêu chuẩn Data Lake:
```text
data/
├── <source>/
│   ├── checkpoint.json                    <-- Quản lý danh sách ID đã thu thập
│   └── dt=YYYY-MM-DD/                     <-- Phân vùng theo ngày cào (Partition Date)
│       ├── batch_001.json                 <-- File dữ liệu chuẩn JSON mảng đối tượng (JSON văn bản không nén)
│       └── batch_002.json
```

File `.json` chứa danh sách đối tượng JSON (`[ { "_meta": ..., "raw": ... }, ... ]`), tuân thủ nghiêm ngặt schema [`JobRecord`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/common/schema.py).  
> [!IMPORTANT]
> **Định dạng file hoàn toàn không nén (Uncompressed Plain JSON)**: Tất cả file kết quả được lưu trữ dưới dạng text UTF-8 thông thường (plain text `.json`, không nén gzip/zip hay nhị phân và không phải jsonl nén). Bạn có thể mở trực tiếp bằng bất kỳ trình soạn thảo mã nguồn nào (VS Code, Sublime, Notepad, Vim) hoặc phân tích trực tiếp với Python `json.load` mà không cần bước giải nén.

---

### 1.6 Xử lý lỗi và gỡ rối (Troubleshooting)

| Tình huống | Nguyên nhân | Cách xử lý |
| :--- | :--- | :--- |
| **HTTP 429 Too Many Requests** | Gửi request quá nhanh khiến máy chủ giới hạn tần suất. | `HttpClient` có cơ chế tự động backoff retry (2s, 4s, 8s). Chờ 1–2 phút hoặc tăng khoảng cách delay trong crawler. |
| **Số tin thu thập bằng 0 (`crawled: 0, skipped: N`)** | Toàn bộ tin cào được đã có trong `checkpoint.json`. | Đây là tính năng chống cào trùng lặp. Muốn cào lại, xóa hoặc reset `data/<source>/checkpoint.json`. |
| **TopCV chạy lâu hoặc không thấy card** | Playwright đang khởi tạo trình duyệt Chrome headless. | Kiểm tra binary Chrome tại `/usr/bin/google-chrome` hoặc chạy `playwright install chromium`. |
| **Lỗi Import module khi chạy trực tiếp file** | Biến môi trường `PYTHONPATH` chưa nhận thư mục gốc. | Chạy với tiền tố `PYTHONPATH=. .venv/bin/python ...` hoặc sử dụng `run.py`. |

---

## Phần 2: Bảng Tổng hợp Ma trận Khả năng Bóc tách 6 Nguồn (Source Capability Matrix)

Dưới đây là ma trận đánh giá năng lực bóc tách dữ liệu thực tế từ 6 trang tuyển dụng IT hàng đầu (được kiểm chứng và đối chiếu từ các file `batch_001.json` thực tế sau khi cào):

| Tiêu chí | TopDev | VietnamWorks | ITviec | CareerViet | Việc Làm 24h | TopCV |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Giao thức lấy dữ liệu** | REST API v2 (`GET`) | Search API v1.0 (`POST`) | HTML + JSON-LD (`GET`) | HTML Scraping (`GET`) | Next.js SSR State (`GET`) | Playwright Browser (`DOM`) |
| **Độ ổn định kết nối** | Rất cao (API JSON) | Cực cao (API JSON) | Cao (Web SSR) | Cao (Web tĩnh/SSR) | Cao (SSR Script tag) | Trung bình (Tùy thuộc DOM/Browser) |
| **Mức lương số học (Min/Max)** | Có (`min`, `max`, `currency`) | Có (`salaryMin`, `salaryMax`) | Thường ẩn sau đăng nhập / JSON-LD | Có (trong badge / text) | Có (`salary_min`, `salary_max`) | Dạng text (ví dụ "15 - 35 triệu") |
| **Kỹ năng công nghệ (Skills)** | Có (`skills` mảng name) | Có (`skills` mảng skillName) | Có (JSON-LD & Tag badge) | Có (`.job-tags` / `.tag-item`) | Phân tích từ title / keywords | Có (Tag badge trên card) |
| **Kinh nghiệm làm việc** | Có (`experiences`) | Có (`yearsOfExperience`) | Có (`experience_requirements_jsonld`) | Có (`detail-box Kinh nghiệm`) | Có (`experience_name`) | Có (`class="exp"`) |
| **Cấp bậc / Seniority** | Có (`levels`) | Có (`jobLevelVI`, `jobLevel`) | Có trong tag / description | Có (`detail-box Cấp bậc`) | Có (`job_level_name`) | Thường nằm trong Title |
| **Địa điểm chi tiết** | Có (`addresses`) | Có (`workingLocations`) | Có (`jobLocation` chi tiết / JSON-LD) | Có (Thành phố / Quận) | Có (`places` city/district) | Có (`city-text`) |
| **Mô tả chi tiết (HTML/Text)** | Đầy đủ (`content`, HTML sạch) | Đầy đủ (`jobDescription`) | Đầy đủ (Tách 4 sections HTML/Text) | Đầy đủ (`detail-row` Mô tả) | Đầy đủ (`job_description_html`)| Thẻ Card HTML snippet |
| **Yêu cầu (Requirements)** | Có (`requirements_arr`) | Có (`jobRequirement`) | Có (Section Yêu cầu riêng) | Có (`detail-row` Yêu cầu) | Có (`job_requirement_html`) | Nằm trong Card snippet |
| **Phúc lợi (Benefits)** | Có (`benefits_v2` sạch thẻ HTML) | Có (`benefits` mảng) | Có (Section Phúc lợi riêng) | Có (`Phúc lợi` row) | Có (`benefits_html`) | Nằm trong Card snippet |
| **Hạn nộp hồ sơ (Deadline)** | Ẩn / Không rõ trong API | Có (`expiredOn`) | Có (`validThrough`) | Có (`Hết hạn nộp`) | Có (`expire_date`) | Có trên Card |
| **Cơ chế chống Bot / WAF** | Rate-limit nhẹ | Rate-limit nhẹ | Rate-limit vừa phải | Thấp | Thấp | **Cloudflare Challenge (Mạnh)** |

---

## Phần 3: Phân tích Chuyên sâu Dữ liệu & Sample JSON Thực tế của 6 Nguồn

Mỗi nguồn dưới đây bao gồm:
1. Thông tin giao thức, endpoint và cơ chế thu thập.
2. Danh mục các trường dữ liệu API/Website cung cấp (Field Inventory).
3. Đánh giá trường hiện tại crawler bóc tách vs trường tiềm năng mở rộng.
4. **Mẫu JSON thực tế đa dòng (Multi-line pretty-printed JSON với 2 spaces indent)** thu được trực tiếp từ môi trường chạy thực tế.

---

### 3.1 TopDev (REST API v2)

#### 1. Giao thức & Endpoint
- **URL Endpoint**: `https://api.topdev.vn/td/v2/jobs`
- **Method**: `GET`
- **Headers**:
  ```http
  Accept: application/json, text/plain, */*
  Referer: https://topdev.vn/viec-lam/tim-kiem
  User-Agent: Mozilla/5.0 ...
  ```
- **Tham số phân trang**: `page=1`, `page_size=15`, `fields[job]=id,title,slug,company,salary,skills,addresses,job_types,levels,experiences,published_at,refreshed_at,content,requirements_arr,requirements_original,responsibilities,responsibilities_original,benefits_v2`

#### 2. Danh mục trường dữ liệu (Field Inventory)
| Tên trường API | Kiểu dữ liệu | Ý nghĩa | Hiện trạng Crawler |
| :--- | :--- | :--- | :--- |
| `id` | Integer | ID tin tuyển dụng duy nhất | Lấy làm `_meta.source_job_id` |
| `title` | String | Chức danh công việc | Lấy làm `raw.title` |
| `slug` | String | Định danh đường dẫn URL | Dùng ghép `_meta.url` |
| `salary` | Object | Chứa `min`, `max`, `value`, `currency`, `is_negotiable` | Format thành chuỗi `raw.salary_text` |
| `company` | Object | Chứa `display_name`, `image_logo`, `slug`, `website` | Lấy tên làm `raw.company` |
| `skills` | Array | Mảng kỹ năng `{id, name_vi, name_en, ...}` | Ghép thành chuỗi `raw.skills_text` |
| `addresses` | Object | Mảng địa điểm `{address_region_list, ...}` | Lấy làm `raw.location_text` |
| `content` | String (HTML)| Nội dung mô tả công việc đầy đủ | Lấy làm `raw.description_html` / `text` |
| `requirements_arr` | Array | Mảng danh sách yêu cầu công việc | Ghép thành `raw.requirements_text` |
| `benefits_v2` | Array | Danh sách phúc lợi kèm icon | Ghép thành `raw.benefits_text` |
| `published_at` | String (ISO) | Thời gian đăng tuyển | Lấy làm `raw.posted_date_text` |
| `experiences` | Array | Cấp độ kinh nghiệm yêu cầu | Lấy làm `raw.experience_text` |
| `levels` | Array | Cấp bậc ứng viên (Junior/Senior/Lead) | Lấy làm `raw.seniority_text` |
| `job_types` | Array | Hình thức làm việc (Full-time, Part-time) | Lấy làm `raw.employment_type_text` |

#### 3. Tiềm năng khai thác thêm
- `salary.min` và `salary.max` dạng số nguyên có thể đưa trực tiếp vào `raw.extra.salary_min_num`, `raw.extra.salary_max_num` giúp phân tích phân phối lương mà không cần parser Regex.
- `company.image_logo` và `company.website` có thể lưu vào `raw.extra.company_logo` để trực quan hóa UI.

#### 4. Sample JSON Thực tế (Multi-line Pretty JSON)
```json
{
  "_meta": {
    "source": "topdev",
    "source_job_id": "2134039",
    "url": "https://topdev.vn/detail-jobs/hanoi-senior-automation-ai-system-engineer-zeder-viet-nam-2134039",
    "dedup_key": "topdev:2134039",
    "crawled_at": "2026-10-08T14:38:36.830581Z",
    "batch_id": "2026-10-08_topdev_001",
    "crawler_version": "0.2.0"
  },
  "raw": {
    "title": "[Hanoi] Senior Automation & AI System Engineer",
    "company": "ZEDER VIỆT NAM",
    "description_html": "<p style=\"text-align: justify;\"><span style=\"font-family: Roboto, Helvetica, Verdana, Arial, sans-serif; font-size: 15px;\"><strong>Zeder Corporation</strong> is hiring two <strong>Senior Automation &amp; AI System Engineer</strong> into our Automation and AI team in Hanoi. These are senior hands on engineering roles. You will take a business problem, scope it properly with the people who own the process, and then build and ship the solution yourself. The work covers three areas and you will move between all of them: conventional automation and system integration, agentic automation, and LLM assisted automation. A large part of the job is knowing which of the three a given problem actually calls for.</span></p>",
    "description_text": "Zeder Corporation is hiring two Senior Automation & AI System Engineer into our Automation and AI team in Hanoi. These are senior hands on engineering roles. You will take a business problem, scope it properly with the people who own the process, and then build and ship the solution yourself. The work covers three areas and you will move between all of them: conventional automation and system integration, agentic automation, and LLM assisted automation. A large part of the job is knowing which of the three a given problem actually calls for.",
    "salary_text": "Thương lượng",
    "location_text": "Thành phố Hà Nội",
    "skills_text": "JavaScript, Python, REST API, Jira, DevOps, AI, CI/CD",
    "posted_date_text": "",
    "employment_type_text": null,
    "seniority_text": null,
    "requirements_text": null,
    "benefits_text": "13 Months of Salary\n\nFull Paid for Social Insurance, plus Bao Viet Healthcare\n\n14 Days of Annual Leave\n\nInternal Training, External Training...\n\nLaptop, Monitor, Working Devices... are Provided\n\nTeam Building, Year End Party, Team Bonding...\n\nFDI Working Environment",
    "deadline_text": null,
    "extra": null,
    "experience_text": null
  }
}
```

---

### 3.2 VietnamWorks (Search API POST)

#### 1. Giao thức & Endpoint
- **URL Endpoint**: `https://ms.vietnamworks.com/job-search/v1.0/search`
- **Method**: `POST`
- **Request Body**:
  ```json
  {
    "query": "software developer",
    "filter": [],
    "ranges": [],
    "order": [],
    "hitsPerPage": 50,
    "page": 0
  }
  ```
- **Phân trang**: `hitsPerPage` (mặc định 50 tin/lần) và `page` (bắt đầu từ 0).

#### 2. Danh mục trường dữ liệu (Field Inventory)
VietnamWorks trả về hơn 100 trường trong mỗi đối tượng việc làm:
| Tên trường API | Kiểu dữ liệu | Ý nghĩa | Hiện trạng Crawler |
| :--- | :--- | :--- | :--- |
| `jobId` | Integer | ID công việc | Lấy làm `_meta.source_job_id` |
| `jobTitle` | String | Tên chức danh công việc | Lấy làm `raw.title` |
| `jobUrl` | String | Đường dẫn chi tiết | Lấy làm `_meta.url` |
| `companyName` | String | Tên công ty | Lấy làm `raw.company` |
| `companyLogo` | String (URL) | Logo công ty | Tiềm năng (`raw.extra.company_logo`) |
| `salaryMin` | Integer | Lương tối thiểu (số nguyên) | Tiềm năng (`raw.extra.salary_min`) |
| `salaryMax` | Integer | Lương tối đa (số nguyên) | Tiềm năng (`raw.extra.salary_max`) |
| `salaryCurrency` | String | Đơn vị tiền tệ (USD / VND) | Tiềm năng (`raw.extra.currency`) |
| `prettySalary` | String | Chuỗi lương hiển thị (vd: "1500 - 2500 USD") | Lấy làm `raw.salary_text` |
| `isSalaryVisible`| Boolean | Trạng thái công khai lương | Tiềm năng kiểm tra độ minh bạch |
| `skills` | Array | Danh sách `{skillId, skillName}` | Ghép thành `raw.skills_text` |
| `yearsOfExperience`| Integer | Số năm kinh nghiệm yêu cầu | Ghép thành `raw.experience_text` |
| `jobLevelVI` / `jobLevel` | String | Cấp bậc (Nhân viên / Trưởng nhóm / Quản lý) | Lấy làm `raw.seniority_text` |
| `workingLocations` | Array | Mảng địa điểm `{cityName, address}` | Lấy làm `raw.location_text` |
| `jobDescription` | String (HTML)| Mô tả công việc chi tiết | Lấy làm `raw.description_html` / `text` |
| `jobRequirement` | String (HTML)| Yêu cầu công việc | Lấy làm `raw.requirements_text` |
| `benefits` | Array | Danh sách phúc lợi `{benefitIconName, benefitValue}` | Lấy làm `raw.benefits_text` |
| `approvedOn` / `createdOn` | String (ISO) | Thời gian duyệt và đăng bài | Lấy làm `raw.posted_date_text` |
| `expiredOn` | String (ISO) | Hạn chót nộp hồ sơ | Lấy làm `raw.deadline_text` |

#### 3. Tiềm năng khai thác thêm
- Đây là nguồn có chất lượng dữ liệu số học cao nhất: có sẵn `salaryMin`, `salaryMax`, `yearsOfExperience` dưới dạng số nguyên, cực kỳ lý tưởng cho các mô hình hồi quy (Salary Regression Modeling) trong giai đoạn Analytics.

#### 4. Sample JSON Thực tế (Multi-line Pretty JSON)
```json
{
  "_meta": {
    "source": "vietnamworks",
    "source_job_id": "2092272",
    "url": "https://www.vietnamworks.com/manager-java-backend-developer-2092272-jv",
    "dedup_key": "vietnamworks:2092272",
    "crawled_at": "2026-10-08T14:38:45.282531Z",
    "batch_id": "2026-10-08_vietnamworks_001",
    "crawler_version": "0.2.0"
  },
  "raw": {
    "title": "Manager Java Backend Developer",
    "company": "Công Ty Cổ Phần Chứng Khoán KIS Việt Nam",
    "description_html": "<p>•\tDesign, build, and maintain scalable backend systems using Java 21+ / Spring Boot 3+.</p><p>•\tImplement microservices and APIs with a focus on performance, security, and resilience.</p><p>•\tOptimize queries and data pipelines (MySQL/MongoDB).</p><p>•\tIntegrate with messaging systems (Kafka, Redis Pub/Sub) and API gateways (Kong/Traefik).</p><p>•\tLead code reviews, refactoring, and architecture discussions.</p><p>•\tCollaborate with DevOps to deliver production-grade services on Docker/Docker...</p>",
    "description_text": "• Design, build, and maintain scalable backend systems using Java 21+ / Spring Boot 3+.\n• Implement microservices and APIs with a focus on performance, security, and resilience.\n• Optimize queries and data pipelines (MySQL/MongoDB).\n• Integrate with messaging systems (Kafka, Redis Pub/Sub) and API gateways (Kong/Traefik).\n• Lead code reviews, refactoring, and architecture discussions.\n• Collaborate with DevOps to deliver production-grade services on Docker/Docker...",
    "salary_text": "Thương lượng",
    "location_text": "Ho Chi Minh",
    "skills_text": "Computer Science, Information Technology, It, Java, Backend",
    "posted_date_text": "2026-09-14T17:00:37+07:00",
    "employment_type_text": "1",
    "seniority_text": "Trưởng phòng",
    "requirements_text": "• Bachelor’s degree in Information Technology, Management Information Systems, Computer Science, or a related field.\n• 5+ years of experience with Java backend development.\n• Strong knowledge of Spring Boot, RESTful APIs, asynchronous processing, and security standards (JWT/OAuth2).\n• Experience with RDBMS, query tuning, and caching strategies.\n• Hands-on with CI/CD (Jenkins, Git), containerization, and monitoring stacks (Prometheus, Grafana, Loki).\n• Familiar with cloud or...",
    "benefits_text": "Bonus, Healthcare Plan, Training, Awards, Travel Opportunities, Team Activities, Transportation, Others",
    "deadline_text": null,
    "extra": null,
    "experience_text": "5 năm kinh nghiệm"
  }
}
```

---

### 3.3 ITviec (Server-Rendered HTML & JSON-LD)

#### 1. Giao thức & Cơ chế
- **Listing URL**: `https://itviec.com/viec-lam-it?page=1`
- **Method**: `GET`
- **Cơ chế bóc tách kép (Dual-layer extraction)**:
  1. **Schema.org JSON-LD**: Thẻ `<script type="application/ld+json">` chứa cấu trúc `JobPosting` chuẩn hóa quốc tế.
  2. **DOM Section Blocks**: Trích xuất chi tiết các section `h2` ("Lý do bạn sẽ thích làm việc tại đây", "Mô tả công việc", "Yêu cầu", "Phúc lợi").

#### 2. Danh mục trường dữ liệu (Field Inventory)
| Tên trường | Nguồn dữ liệu | Ý nghĩa | Hiện trạng Crawler |
| :--- | :--- | :--- | :--- |
| `slug` | URL slug | Mã định danh dạng text | Lấy làm `_meta.source_job_id` |
| `title` | JSON-LD / `h1` | Tiêu đề tin tuyển dụng | Lấy làm `raw.title` |
| `company` | JSON-LD `hiringOrganization.name` | Tên công ty | Lấy làm `raw.company` |
| `salary_text`| HTML Badge | "Đăng nhập để xem mức lương" hoặc dải USD | Lấy làm `raw.salary_text` |
| `skills` | JSON-LD `skills` / Tag list | Danh sách tech stack | Ghép thành `raw.skills_text` |
| `jobLocation` | JSON-LD / HTML | Quận/huyện, Thành phố | Lấy làm `raw.location_text` |
| `datePosted` | JSON-LD | Ngày đăng tin | Lấy làm `raw.posted_date_text` |
| `validThrough`| JSON-LD | Hạn chót ứng tuyển | Lưu vào `raw.valid_through_text` |
| `sections` | HTML `h2` sections | Nội dung mô tả, yêu cầu, phúc lợi chia theo khối | Lưu đầy đủ cả HTML và Text |

#### 3. Tiềm năng khai thác thêm
- ITviec phân tách các section cực kỳ bài bản: có trường `industry`, `experience_requirements_jsonld`, `company_url`. Toàn bộ đều được crawler ITviec giữ nguyên vẹn trong payload `raw`.

#### 4. Sample JSON Thực tế (Multi-line Pretty JSON)
```json
{
  "_meta": {
    "source": "itviec",
    "source_job_id": "business-analyst-officer-motorist-pte-ltd-4823",
    "url": "https://itviec.com/viec-lam-it/business-analyst-officer-motorist-pte-ltd-4823",
    "dedup_key": "itviec:business-analyst-officer-motorist-pte-ltd-4823",
    "crawled_at": "2026-10-08T21:39:03+07:00",
    "batch_id": "2026-10-08_itviec_001",
    "crawler_version": "0.1.0"
  },
  "raw": {
    "title": "Business Analyst Officer",
    "company": "Motorist Pte Ltd",
    "salary_text": "Đăng nhập để xem mức lương",
    "location_text": "Hồ Chí Minh, Thành phố Thủ Đức",
    "skills_text": "Business Intelligence, Product Owner, Business Analysis, UI-UX, Product Management, Agile",
    "posted_date_text": "2026-10-08",
    "employment_type_text": "FULL_TIME",
    "seniority_text": null,
    "description_html": "Top 3 Reasons To Join Us\r\nHighly competitive salary and benefits package\r\nExcellent environment and team to help you grow.\r\nWe are Singapore's leading car portal\r\nThe Job\r\n<p>The Business Analyst based in Vietnam is responsible for gathering and documenting product requirements, analyzing and improving processes, engaging with stakeholders, and col... [đã rút gọn hiển thị]",
    "description_text": "Top 3 Reasons To Join Us\r\nHighly competitive salary and benefits package\r\nExcellent environment and team to help you grow.\r\nWe are Singapore's leading car portal\r\nThe Job\nThe Business Analyst based in Vietnam is responsible for gathering and documenting product requirements, analyzing and improving processes, engaging with stakeholders, and collabo... [đã rút gọn hiển thị]",
    "requirements_text": "Years of Experience:\n2 - 5 years as a Business Analyst (BA) / Product Manager (PM)\nSkills / Technical Knowledge:\n- UI/UX and User Flow Design\nExpert eye for clean, standardized user interfaces and consistent UX behavior.\nAbility to map and optimize end-to-end user journeys, ensuring smooth navigation and minimal friction.\nHands-on experience creati... [đã rút gọn hiển thị]",
    "company_url": "https://itviec.com/nha-tuyen-dung/mb-bank",
    "salary_jsonld": {
      "@type": "MonetaryAmount",
      "currency": "USD",
      "value": {
        "@type": "QuantitativeValue",
        "unitText": "MONTH",
        "value": "You'll love it"
      }
    },
    "job_location": [
      {
        "@type": "Place",
        "address": {
          "@type": "PostalAddress",
          "streetAddress": "lầu 12A ,258 Nam Kỳ Khởi Nghĩa",
          "addressLocality": "Thành phố Thủ Đức",
          "addressRegion": "Hồ Chí Minh",
          "postalCode": "700000",
          "addressCountry": "VN"
        }
      }
    ],
    "industry": "Information Technology",
    "valid_through_text": "2026-11-12",
    "experience_requirements_jsonld": {
      "@type": "OccupationalExperienceRequirements",
      "monthsOfExperience": 10
    },
    "requirements_html": "<p><strong>Years of Experience:</strong> 2 - 5 years as a Business Analyst (BA) / Product Manager (PM)</p><p><strong>Skills / Technical Knowledge:</strong></p><p>- UI/UX and User Flow Design</p><ul><li>Expert eye for clean, standardized user interfaces and consistent UX behavior.</li><li>Ability to map and optimize end-to-end user journeys, ensurin... [đã rút gọn hiển thị]",
    "benefits_html": "<p>At Motorist, we believe in work hard, play hard – We take pride in our fun and enjoyable working environment. You will get to work in Vietnam’s first professional large-scale co-working space located right in the heart of Saigon. You’ll also get to travel to Singapore for work-and-learn benefits, seize opportunities to upgrade your skills and fu... [đã rút gọn hiển thị]",
    "benefits_text": "At Motorist, we believe in work hard, play hard – We take pride in our fun and enjoyable working environment. You will get to work in Vietnam’s first professional large-scale co-working space located right in the heart of Saigon. You’ll also get to travel to Singapore for work-and-learn benefits, seize opportunities to upgrade your skills and futhe... [đã rút gọn hiển thị]",
    "sections_html": {
      "3 Lý do để gia nhập công ty": "<ul>\n<li>Highly competitive salary and benefits package</li>\n<li>Excellent environment and team to help you grow.</li>\n<li>We are Singapore's leading ...",
      "Mô tả công việc": "<p>The Business Analyst based in Vietnam is responsible for gathering and documenting product requirements, analyzing and improving processes, engagin...",
      "Yêu cầu công việc": "<p><strong>Years of Experience:</strong> 2 - 5 years as a Business Analyst (BA) / Product Manager (PM)</p><p><strong>Skills / Technical Knowledge:</st...",
      "Tại sao bạn sẽ yêu thích làm việc tại đây": "<p>At Motorist, we believe in work hard, play hard – We take pride in our fun and enjoyable working environment. You will get to work in Vietnam’s fir..."
    }
  }
}
```

---

### 3.4 CareerViet (HTML Scraping)

#### 1. Giao thức & Cơ chế
- **Listing URL**: `https://careerviet.vn/viec-lam/cntt-phan-mem-c1-vi.html`
- **Method**: `GET`
- **Cơ chế bóc tách**:
  1. Trích xuất danh sách link bài đăng từ trang danh mục CNTT.
  2. Bóc tách Job ID thông qua biểu thức Regex: `\.[A-Z0-9]{6,12}\.html` (ví dụ `.35C89DD7.html`).
  3. Tải trực tiếp trang HTML chi tiết và bóc tách các khối `.job-detail-page`, `h1.title`, `.detail-box` metadata (Lương, Kinh nghiệm, Cấp bậc, Hạn nộp), và các khối `.detail-row` (Mô tả, Yêu cầu, Phúc lợi).

#### 2. Danh mục trường dữ liệu (Field Inventory)
| Tên trường | CSS Selector / Nguồn | Ý nghĩa | Hiện trạng Crawler |
| :--- | :--- | :--- | :--- |
| `job_id` | Regex từ URL (`.35C89DD7`) | Mã định danh duy nhất | Lấy làm `_meta.source_job_id` |
| `title` | `h1` / `.title, .job-title` | Tên công việc chuẩn xác | Lấy làm `raw.title` |
| `company` | `a.employer, a.company` | Tên công ty tuyển dụng | Lấy làm `raw.company` |
| `salary` | `.detail-box li:has(Lương) p` | Mức lương (vd: "Cạnh tranh", "20 - 30 Triệu") | Lấy làm `raw.salary_text` |
| `location` | `div.map p a` / `li:has(Địa điểm) p` | Nơi làm việc | Lấy làm `raw.location_text` |
| `skills` | `.job-tags a, .tag-item` | Danh sách tag kỹ năng | Lấy làm `raw.skills_text` |
| `experience`| `li:has(Kinh nghiệm) p` | Yêu cầu số năm kinh nghiệm | Lấy làm `raw.experience_text` |
| `seniority` | `li:has(Cấp bậc) p` | Cấp bậc ứng viên | Lấy làm `raw.seniority_text` |
| `employment_type` | `li:has(Hình thức) p` | Loại hình hợp đồng | Lấy làm `raw.employment_type_text` |
| `posted_date` | `li:has(Ngày cập nhật) p` | Ngày cập nhật bài viết | Lấy làm `raw.posted_date_text` |
| `description` | `.detail-row:has(Mô tả)` | Toàn bộ HTML mô tả | Lấy làm `raw.description_html` / `text` |
| `requirements` | `.detail-row:has(Yêu cầu)` | Toàn bộ yêu cầu ứng tuyển | Lấy làm `raw.requirements_text` |
| `benefits` | `.detail-row:has(Phúc lợi)` | Các chế độ phúc lợi | Lấy làm `raw.benefits_text` |

#### 3. Tiềm năng khai thác thêm
- `CareerViet` có trường Hạn nộp hồ sơ (`li:has(Hết hạn nộp) p`) rất rõ ràng, có thể đưa vào `raw.deadline_text` để theo dõi vòng đời tin tuyển dụng (Job Lifecycle).

#### 4. Sample JSON Thực tế (Multi-line Pretty JSON)
```json
{
  "_meta": {
    "source": "careerviet",
    "source_job_id": "35C87374",
    "url": "https://careerviet.vn/vi/tim-viec-lam/ip-engineer.35C87374.html",
    "dedup_key": "careerviet:35C87374",
    "crawled_at": "2026-10-08T14:39:13.073148Z",
    "batch_id": "2026-10-08_careerviet_001",
    "crawler_version": "0.2.0"
  },
  "raw": {
    "title": "IP Engineer",
    "company": "CÔNG TY TNHH CÔNG NGHỆ HUAWEI VIỆT NAM",
    "description_html": "<div class=\"detail-row reset-bullet\"><h2 class=\"detail-title\">Mô tả Công việc</h2><div><p>• Design, implement Huawei enterprise network solutions (Backbone, Metro，WAN, SRV6，DCN).</p><p>• Provide technical support for  post-sales activities, including Design, deployment and migration.</p><p>• Perform installation, configuration, commissioning, and troubleshooting of Huawei enterprise products (Router, Switches, iMaster NCE, etc.).</p><p>• Proficient in core IP routing protocols, including OSPF, IS-IS, and BGP.Capable of solution design, deployment, and service migration based on the aforementioned IP protocols.</p><p>• Support enterprise customers in incident response, problem resolution, and performance tuning.</p><p>• Collaborate with R&amp;D and GTAC teams for complex issue escalation and product improvements.</p><p>• Conduct training, workshops, and knowledge transfer sessions for customers and partners.</p><p>• Prepare and maintain technical documentation, including design guides, operation manuals, and change records.</p></div></div>",
    "description_text": "Mô tả Công việc\n• Design, implement Huawei enterprise network solutions (Backbone, Metro，WAN, SRV6，DCN).\n• Provide technical support for post-sales activities, including Design, deployment and migration.\n• Perform installation, configuration, commissioning, and troubleshooting of Huawei enterprise products (Router, Switches, iMaster NCE, etc.).\n• Proficient in core IP routing protocols, including OSPF, IS-IS, and BGP.Capable of solution design, deployment, and service migration based on the aforementioned IP protocols.\n• Support enterprise customers in incident response, problem resolution, and performance tuning.\n• Collaborate with R&D and GTAC teams for complex issue escalation and product improvements.\n• Conduct training, workshops, and knowledge transfer sessions for customers and partners.\n• Prepare and maintain technical documentation, including design guides, operation manuals, and change records.",
    "salary_text": "Cạnh tranh",
    "location_text": "Hà Nội",
    "skills_text": null,
    "posted_date_text": "08/10/2026",
    "employment_type_text": "Nhân viên chính thức",
    "seniority_text": "Nhân viên",
    "requirements_text": "Yêu Cầu Công Việc• Education Background Requirements: Bachelor or higher, major: Telecommunications technology, or related fields.• 3–5 years of experience in enterprise networking or security solutions.• Solid knowledge of routing, switching, wireless, and security technologies.• Familiar with network automation and SDN platforms (Huawei iMaster NCE is a plus).• Understanding of enterprise cloud networking and security best practices.• Ability to perform complex troubleshooting and root cause analysis.• Able to communicate effectively in English both speaking and writing.• Family with Microsoft office, Excel, Power point.• Ability to adapt quickly to changing environments and manage parallel time-critical tasks.• Ability to multi-task in a fast-paced environment.• Ability to Travel as needed.WORKING TIME AND BENEFITS• Monday to Friday (08:30-18:00).• Short term and long-term award• Huawei online and offline aboard training.• Participating in full insurance benefits (health insurance, social insurance, unemployment insurance), the company supports 24/24 accident insurance and health care insurance for employees.• Professional working environment, multinational company, good career development opportunities. Cultural and sports activities, taking care of employees' health and life are organized periodically...• Salary: negotiable.",
    "benefits_text": "Phúc lợiChế độ bảo hiểmDu LịchChế độ thưởngChăm sóc sức khỏeĐào tạoTăng lương",
    "deadline_text": null,
    "extra": null,
    "experience_text": "3 - 5 Năm"
  }
}
```

---

### 3.5 Việc Làm 24h (Next.js SSR `__NEXT_DATA__`)

#### 1. Giao thức & Cơ chế
- **URL**: `https://vieclam24h.vn/tim-kiem-viec-lam-nhanh?key=it`
- **Method**: `GET`
- **Cơ chế bóc tách**:
  - Trang web được xây dựng trên nền tảng Next.js.
  - Dữ liệu hoàn chỉnh của danh sách bài đăng và chi tiết việc làm được nhúng sẵn dưới dạng JSON trong thẻ script:
    ```html
    <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"jobs":[...]}}}
    </script>
    ```
  - Crawler tải trang, dùng Regex / BeautifulSoup trích xuất chuỗi JSON này, phân giải trực tiếp thành Python dictionary mà không phải parse qua cấu trúc HTML UI dễ thay đổi.

#### 2. Danh mục trường dữ liệu (Field Inventory)
| Tên trường JSON | Kiểu dữ liệu | Ý nghĩa | Hiện trạng Crawler |
| :--- | :--- | :--- | :--- |
| `id` | Integer | ID tin tuyển dụng duy nhất | Lấy làm `_meta.source_job_id` |
| `title` | String | Tiêu đề tin tuyển dụng | Lấy làm `raw.title` |
| `title_slug` | String | Slug bài viết | Ghép URL `_meta.url` |
| `employer_info` | Object | `{id, name, logo, company_size, ...}` | Lấy tên làm `raw.company` |
| `salary_min` | Integer | Lương tối thiểu | Ghép thành `raw.salary_text` |
| `salary_max` | Integer | Lương tối đa | Ghép thành `raw.salary_text` |
| `salary_unit` | String | Đơn vị tiền tệ (VND) | Ghép thành `raw.salary_text` |
| `places` | Array | Mảng địa điểm `{city_name, district_name}` | Ghép thành `raw.location_text` |
| `job_description_html` | String (HTML)| Mô tả công việc chi tiết | Lấy làm `raw.description_html` |
| `job_requirement_html` | String (HTML)| Yêu cầu công việc | Lấy làm `raw.requirements_text` |
| `benefits_html` | String (HTML)| Chế độ đãi ngộ | Lấy làm `raw.benefits_text` |
| `experience_name` | String | Yêu cầu số năm kinh nghiệm | Lấy làm `raw.experience_text` |
| `job_level_name` | String | Cấp bậc công việc | Lấy làm `raw.seniority_text` |
| `expire_date` | String | Hạn nộp hồ sơ | Lấy làm `raw.deadline_text` |

#### 3. Tiềm năng khai thác thêm
- Lấy trực tiếp `salary_min` và `salary_max` dạng số nguyên vào `raw.extra` giúp không bị mất mát kiểu dữ liệu số học khi tính toán trung vị lương thị trường.

#### 4. Sample JSON Thực tế (Multi-line Pretty JSON)
```json
{
  "_meta": {
    "source": "vieclam24h",
    "source_job_id": "200958711",
    "url": "https://vieclam24h.vn/chuyen-vien-tu-van-bat-dong-san-co-luong-cung-lam-viec-tai-binh-thanh-id200958711.html",
    "dedup_key": "vieclam24h:200958711",
    "crawled_at": "2026-10-08T14:39:21.506382Z",
    "batch_id": "2026-10-08_vieclam24h_001",
    "crawler_version": "0.2.0"
  },
  "raw": {
    "title": "Chuyên Viên Tư Vấn Bất Động Sản - Có Lương Cứng - Làm Việc Tại Bình Thạnh",
    "company": "CÔNG TY TNHH HOÀNG PHÚ ĐIỀN GROUP",
    "description_html": "<p>Tuyển dụng Chuyên Viên Tư Vấn Bất Động Sản - Có Lương Cứng - Làm Việc Tại Bình Thạnh tại CÔNG TY TNHH HOÀNG PHÚ ĐIỀN GROUP</p>",
    "description_text": "Tuyển dụng Chuyên Viên Tư Vấn Bất Động Sản - Có Lương Cứng - Làm Việc Tại Bình Thạnh tại CÔNG TY TNHH HOÀNG PHÚ ĐIỀN GROUP",
    "salary_text": "12000000 - 50000000 VND",
    "location_text": null,
    "skills_text": null,
    "posted_date_text": "1791426049",
    "employment_type_text": "1",
    "seniority_text": "5",
    "requirements_text": "- Độ tuổi từ 18 đến 35.\n- Không yêu cầu kinh nghiệm, ứng viên sẽ được đào tạo bài bản từ đầu.\n- Đam mê kinh doanh, nhiệt huyết, có định hướng phát triển trong lĩnh vực bất động sản.\n- Kỹ năng giao tiếp, thuyết phục và đàm phán tốt.\n- Năng động, hòa đồng, có tinh thần ham học hỏi và cầu tiến.",
    "benefits_text": null,
    "deadline_text": null,
    "extra": null,
    "experience_text": "1"
  }
}
```

---

### 3.6 TopCV (Playwright Browser + Card Extraction)

#### 1. Giao thức & Cơ chế
- **URL**: `https://www.topcv.vn/viec-lam-it`
- **Cơ chế thu thập**: Trình duyệt Chromium tự động (Playwright) với cờ tắt Automation, nạp đầy đủ DOM trang kết quả.
- **Giải quyết thách thức Cloudflare Challenge & DOM Card Selector**:
  - TopCV áp dụng Cloudflare WAF nghiêm ngặt. Trình duyệt headless khởi chạy với các đối số `--disable-blink-features=AutomationControlled` và `--no-sandbox`, User-Agent máy tính chuẩn, viewport 1920x1080.
  - Trên mỗi thẻ `.job-item-search-result`, thẻ `<a>` đầu tiên là liên kết avatar/logo công ty (không chứa văn bản). Crawler đã được tối ưu hóa để duyệt qua các thẻ `a[href*='/viec-lam/']`, chọn thẻ chứa tiêu đề thực sự, tránh bị rỗng tiêu đề và bỏ sót bài đăng.

#### 2. Danh mục trường dữ liệu (Field Inventory)
| Tên trường | DOM Selector / Thuộc tính | Ý nghĩa | Hiện trạng Crawler |
| :--- | :--- | :--- | :--- |
| `job_id` | `data-job-id` / Regex URL | Mã số định danh bài viết | Lấy làm `_meta.source_job_id` |
| `title` | `a[href*='/viec-lam/']` (văn bản) | Tên chức danh công việc | Lấy làm `raw.title` |
| `company` | `.company-name, a.company, a[href*='/cong-ty/']` | Tên doanh nghiệp tuyển dụng | Lấy làm `raw.company` |
| `salary` | `.salary, .title-salary` | Mức lương hiển thị (vd: "15 - 35 triệu") | Lấy làm `raw.salary_text` |
| `location` | `.city-text, .address` | Thành phố làm việc | Lấy làm `raw.location_text` |
| `experience`| `.exp, span.exp` | Số năm kinh nghiệm yêu cầu | Lấy làm `raw.experience_text` |
| `html_snippet` | Thẻ card HTML | Khối HTML thô bao bọc card | Lấy làm `raw.description_html` |

#### 3. Tiềm năng khai thác thêm
- Có thể bổ sung bước click vào từng link bài đăng trong phiên Playwright để tải toàn văn trang chi tiết khi cần mở rộng nội dung mô tả công việc sang dạng văn bản dài.

#### 4. Sample JSON Thực tế (Multi-line Pretty JSON)
```json
{
  "_meta": {
    "source": "topcv",
    "source_job_id": "2323159",
    "url": "https://www.topcv.vn/viec-lam/business-analyst-2-nam-kinh-nghiem-upto-35-trieu/2323159.html?ta_source=JobSearchList_LinkDetail&u_sr_id=sXgYAZIGdo9tXQo6yCBrLcy5jY71GxuE2lfP4GsN_1791470366",
    "dedup_key": "topcv:2323159",
    "crawled_at": "2026-10-08T14:39:34.384341Z",
    "batch_id": "2026-10-08_topcv_001",
    "crawler_version": "0.2.0"
  },
  "raw": {
    "title": "Business Analyst (2+ Năm Kinh Nghiệm) - Upto 35 Triệu",
    "company": "Công ty Cổ phần MISA",
    "description_html": "<div class=\"job-item-search-result bg-highlight job-ta\" data-b-t=\"2\" data-box=\"BoxSearchResult\" data-job-id=\"2323159\" data-job-position=\"3\" data-u-sr-id=\"sXgYAZIGdo9tXQo6yCBrLcy5jY71GxuE2lfP4GsN_1791470366\">\n<div class=\"avatar\">\n<a aria-label=\"Business Analyst (2+ Năm Kinh Nghiệm) - Upto 35 Triệu\" href=\"https://www.topcv.vn/viec-lam/business-analyst-2-nam-kinh-nghiem-upto-35-trieu/2323159.html?ta_... [thẻ div card html rút gọn]",
    "description_text": "Tin mới\nNổi bật\n\n\nBusiness Analyst (2+ Năm Kinh Nghiệm) - Upto 35 Triệu\n\n\nCông ty Cổ phần MISA\n\n\nThoả thuận\n\nXem nhanh\n\n\nThoả thuận\n\n\nHà Nội\n\n\n2 năm\n\n\nBạn sẽ không nhìn thấy tin tuyển dụng này trên trang tìm kiếm\n\n\nHoàn tác\n\n\n2 năm kinh nghiệm chuyên mônBusiness Ana...+9\n\n\n2 năm kinh nghiệm...+9\n\n\nĐăng\n2 ngày trước\n\n\nỨng tuyển",
    "salary_text": "Thoả thuận",
    "location_text": "Hà Nội",
    "skills_text": null,
    "posted_date_text": "",
    "employment_type_text": null,
    "seniority_text": null,
    "requirements_text": null,
    "benefits_text": null,
    "deadline_text": null,
    "extra": null,
    "experience_text": "2 năm"
  }
}
```

---

## Phần 4: Hướng dẫn Quy trình và Câu lệnh Đối chiếu Kết quả Thực tế

### 4.1 Lệnh CLI in đẹp (Pretty-print) JSON đa dòng từ file kết quả

Sau khi chạy tay bất kỳ crawler nào, file kết quả `.json` sẽ được sinh ra tại `data/<source>/dt=YYYY-MM-DD/batch_001.json`.  
File kết quả được lưu dưới dạng **JSON thông thường không nén (Uncompressed plain text `.json`, không nén gzip hay zip, không phải file nén hay jsonl)**. File là một mảng JSON các bản ghi hoặc từng bản ghi độc lập. Để in đẹp ra màn hình dạng đa dòng thụt lề chuẩn 2 khoảng trắng để đối chiếu với tài liệu này, bạn sử dụng 1 trong các cách sau:

#### Cách 1: Sử dụng Python One-liner (Khuyên dùng, chạy được trên mọi máy tính không cần cài thêm tool)
```bash
# Thay thế đường dẫn file tương ứng
python -c "import json; print(json.dumps(json.load(open('data/topdev/dt=2026-10-08/batch_001.json'))[-1], indent=2, ensure_ascii=False))"
```

#### Cách 2: Sử dụng công cụ `jq` (Nếu hệ thống có cài đặt `jq`)
```bash
jq '.[-1]' data/topdev/dt=2026-10-08/batch_001.json
```

#### Lệnh xem mẫu cho toàn bộ 6 nguồn:
```bash
# 1. TopDev
python -c "import json; print(json.dumps(json.load(open('data/topdev/dt=2026-10-08/batch_001.json'))[-1], indent=2, ensure_ascii=False))"

# 2. VietnamWorks
python -c "import json; print(json.dumps(json.load(open('data/vietnamworks/dt=2026-10-08/batch_001.json'))[-1], indent=2, ensure_ascii=False))"

# 3. ITviec
python -c "import json; print(json.dumps(json.load(open('data/itviec/dt=2026-10-08/batch_001.json'))[-1], indent=2, ensure_ascii=False))"

# 4. CareerViet
python -c "import json; print(json.dumps(json.load(open('data/careerviet/dt=2026-10-08/batch_001.json'))[-1], indent=2, ensure_ascii=False))"

# 5. Việc Làm 24h
python -c "import json; print(json.dumps(json.load(open('data/vieclam24h/dt=2026-10-08/batch_001.json'))[-1], indent=2, ensure_ascii=False))"

# 6. TopCV
python -c "import json; print(json.dumps(json.load(open('data/topcv/dt=2026-10-08/batch_001.json'))[-1], indent=2, ensure_ascii=False))"
```

---

### 4.2 Checklist 10 tiêu chí kiểm tra dữ liệu đầu ra (Data Quality QA)

Khi bạn tự chạy tay và in kết quả, hãy dùng bảng kiểm tra 10 tiêu chí dưới đây để đánh giá chất lượng đầu ra:

| STT | Tiêu chí đánh giá | Trạng thái mong muốn | Cách nhận biết hợp lệ |
| :---: | :--- | :---: | :--- |
| **1** | **Khóa định danh nguồn (`_meta.source_job_id`)** | **Bắt buộc** | Chuỗi số hoặc slug duy nhất không được rỗng (ví dụ: `"2137254"`, `"35C89DD7"`). |
| **2** | **Đường dẫn URL bài viết (`_meta.url`)** | **Bắt buộc** | Bắt đầu bằng `https://`, không chứa tracking params dư thừa (`utm_*`). |
| **3** | **Khóa Dedup (`_meta.dedup_key`)** | **Bắt buộc** | Đúng định dạng `<source>:<source_job_id>` (ví dụ: `vietnamworks:2109777`). |
| **4** | **Tiêu đề tuyển dụng (`raw.title`)** | **Bắt buộc** | Tên chức danh sạch, không dính thẻ HTML, không bị nhầm sang tên mục (như "Phúc lợi" hay rỗng). |
| **5** | **Tên doanh nghiệp (`raw.company`)** | **Bắt buộc** | Tên công ty đầy đủ, không để giá trị rỗng hoặc `null`. |
| **6** | **Mức lương (`raw.salary_text`)** | Quan trọng | Có giá trị hiển thị rõ ràng (dải lương số hoặc `"Thương lượng"`, `"Cạnh tranh"`). |
| **7** | **Địa điểm làm việc (`raw.location_text`)** | Quan trọng | Tên thành phố hoặc tỉnh thành (Hà Nội, TP.HCM, Đà Nẵng). |
| **8** | **Kỹ năng công nghệ (`raw.skills_text`)** | Tùy chọn | Chuỗi phân cách dấu phẩy các tech stack (Python, Java, React, SQL...). |
| **9** | **Mô tả công việc (`raw.description_html` & `text`)** | **Bắt buộc** | `description_html` giữ nguyên cấu trúc thẻ định dạng; `description_text` bóc sạch thẻ HTML. |
| **10**| **Quản lý Checkpoint (`checkpoint.json`)** | **Bắt buộc** | File `data/<source>/checkpoint.json` được cập nhật thêm ID bài vừa cào, không bị ghi đè mất các ID trước đó. |

---

*Tài liệu được biên soạn phục vụ quy trình kiểm chuẩn dữ liệu tự động và chạy tay cho dự án VN-IT-Job-Mining.*
