# Hướng Dẫn Phân Tích & Đối Chiếu Bóc Tách Dữ Liệu Tuyển Dụng TopCV (TopCV Multi-Page Crawl & Comparative Analysis)

> **Mục tiêu tài liệu**: 
> 1. Trình bày chi tiết luồng thu thập dữ liệu 2 giai đoạn (Listing -> Detail) đã được cài đặt trong [`crawlers/sources/topcv/crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/crawler.py).
> 2. So sánh và đối chiếu kết quả bóc tách giữa **5 file HTML thực tế** đại diện cho nhiều dạng tin tuyển dụng khác nhau (Tiếng Anh, Tiếng Việt, Ngoại tệ USD, VND, vị trí kỹ sư, vị trí BA, vị trí Product Manager).
> 3. Làm rõ nguyên nhân thiếu dữ liệu ở crawler cũ, các biến thể layout của TopCV và cách parser mới giải quyết triệt để.

---

## 1. Quy Trình Thu Thập Dữ Liệu 2 Giai Đoạn (2-Phase Architecture)

Để khắc phục tình trạng thiếu dữ liệu như ở `batch_001.json` cũ (chỉ cào card tìm kiếm), crawler mới áp dụng luồng chuẩn:

```
[Giai đoạn 1: Quét Listing Search Page] 
       │ Truy cập https://www.topcv.vn/viec-lam-it
       │ Vượt Cloudflare, lọc thẻ card div[data-job-id]
       ▼
[Giai đoạn 2: Lấy Danh Sách Target URLs]
       │ Chuẩn hóa URL, hỗ trợ tiền xử lý đa ngôn ngữ (?lang=en)
       ▼
[Giai đoạn 3: Truy Cập Từng Trang Job Detail Page]
       │ Mở từng trang chi tiết, tải toàn bộ HTML
       │ Lưu file HTML cục bộ: {id}.html
       ▼
[Giai đoạn 4: Bóc Tách Dữ Liệu Chi Tiết (Bilingual Parser)]
       │ Parse Title, Company, Salary, Deadline, Description, Requirements,
       │ Benefits, Skills, Location, Schedule, Extra attributes
       ▼
[Giai đoạn 5: Xuất File JSON Chuẩn Data Contract (JobRecord)]
```

---

## 2. Danh Sách 5 File HTML Mẫu Được Thu Thập Trong `crawlers/sources/topcv/`

Để phân tích và kiểm chứng đa dạng các trường hợp biên, hệ thống đã thu thập và lưu trữ 5 file HTML:

| File Name | Job ID | Ngôn Ngữ | Vị Trí Tuyển Dụng | Công Ty | Loại Hình |
| :--- | :--- | :--- | :--- | :--- | :--- |
| [`2321158.html`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/2321158.html) | `2321158` | **English** | Senior SAP CO/PS Consultant | LG CNS VIỆT NAM | FDI Hàn Quốc, ERP Enterprise |
| [`2316770.html`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/2316770.html) | `2316770` | **English** | Product Development Engineer | SUN VIGOR VIỆT NAM | FDI Quốc Tế, Lương USD |
| [`2323097.html`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/2323097.html) | `2323097` | **Tiếng Việt** | Fullstack Developer (C#, .NET, Vuejs) | MISA | Doanh nghiệp phần mềm lớn |
| [`2323114.html`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/2323114.html) | `2323114` | **Tiếng Việt** | Product Manager - CRM | MISA | Quản lý sản phẩm, Product Management |
| [`2323159.html`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/2323159.html) | `2323159` | **Tiếng Việt** | Business Analyst (2+ Năm) | MISA | Nghiệp vụ BA / Phân tích hệ thống |

---

## 3. Bảng So Sánh & Đối Chiếu Dữ Liệu Bóc Tách (5 Trang HTML vs. JSON)

Kết quả bóc tách được lưu tại [`crawlers/sources/topcv/test_5_jobs.json`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/test_5_jobs.json):

| Trường Schema | 2321158 (SAP - EN) | 2316770 (Hardware/SW - EN) | 2323097 (Fullstack - VI) | 2323114 (PM CRM - VI) | 2323159 (BA - VI) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`title`** | Senior SAP CO/PS Consultant... | Product Development Engineer... | Fullstack Developer (C#, .NET, Vuejs)... | Product Manager - CRM... | Business Analyst (2+ Năm)... |
| **`company`** | LG CNS VIỆT NAM | SUN VIGOR VIỆT NAM | MISA | MISA | MISA |
| **`language`** | `en` | `en` | `vi` | `vi` | `vi` |
| **`salary_text`** | Thoả thuận | Thoả thuận | Tới 40 triệu | Thoả thuận | Thoả thuận |
| **`salary_min`** | `null` | `null` | `null` | `null` | `null` |
| **`salary_max`** | `null` | `1300.0` (từ title) | `40.0` (từ badge) | `null` | `35.0` (từ title) |
| **`salary_currency`** | `null` | **`USD`** | **`VND`** | `null` | **`VND`** |
| **`deadline_text`**| `04/11/2026` | `30/10/2026` | `05/11/2026` | `05/11/2026` | `05/11/2026` |
| **`description`** | Đầy đủ nhiệm vụ SAP | Đầy đủ quy trình R&D sản phẩm | Đầy đủ nhiệm vụ Dev .NET/Vue | Đầy đủ nhiệm vụ quản lý CRM | Đầy đủ nhiệm vụ phân tích BA |
| **`requirements`** | Đầy đủ yêu cầu SAP 5+ năm | Đầy đủ bằng cấp, ngoại ngữ | Đầy đủ kiến thức C#, .NET, Caching | Đầy đủ kinh nghiệm Product CRM | Đầy đủ kỹ năng phân tích BA, SQL |
| **`benefits`** | Topik allowance, bảo hiểm cao cấp | Xe đưa đón, bảo hiểm XH | Thưởng doanh số, teambuilding | Đãi ngộ cấp quản lý, du lịch | Đào tạo chuyên sâu, thưởng hiệu quả |
| **`skills_text`** | SAP PS, SAP CO, IT Consultant | Product Owner, Kỹ thuật | 3 năm kinh nghiệm, Vue, C# | Quản lý sản phẩm, CRM | Business Analyst, SQL, 2 năm KN |
| **`location_text`**| Keangnam Landmark72, Hà Nội | CCN Tiên Cường, Hải Phòng | Tòa nhà MISA, Cầu Giấy, Hà Nội | Tòa nhà MISA, Cầu Giấy, Hà Nội | Tòa nhà MISA, Cầu Giấy, Hà Nội |
| **`work_schedule`**| Thứ 2 - Thứ 6 (08:00 - 17:00) | Thứ 2 - Thứ 7 (08:00 - 17:00) | Thứ 2 - Thứ 6 (08:00 - 17:30) | Thứ 2 - Thứ 6 (08:00 - 17:30) | Thứ 2 - Thứ 6 (08:00 - 17:30) |
| **`seniority_text`**| Nhân viên (vị trí Senior) | Nhân viên | Nhân viên (Senior Dev) | Quản lý (Manager) | Nhân viên (Mid-level) |
| **`education`** | Đại Học trở lên | Đại Học trở lên | Đại Học trở lên | Đại Học trở lên | Đại Học trở lên |
| **`hiring_quantity`**| 1 người | 1 người | 2 người | 1 người | 1 người |

---

## 4. Phân Tích Các Biến Thể Layout & Dị Biệt Dữ Liệu (Reasons for Variations)

Qua việc đối chiếu 5 trang HTML thực tế trên, chúng ta rút ra các đặc điểm cốt lõi cần lưu ý khi cào TopCV:

### 4.1. Biến thể Song Ngữ (English Template vs. Vietnamese Template)
TopCV có 2 bộ khung giao diện chính tuỳ thuộc vào việc nhà tuyển dụng đăng tin theo mẫu tiếng Anh hay tiếng Việt:

- **Bộ tiêu đề tiếng Anh** (`2321158.html`, `2316770.html`):
  - `Job Details` -> Chứa tags chuyên môn (Specialization) và yêu cầu cơ bản.
  - `Job Description` -> Mô tả công việc.
  - `Candidate Requirements` -> Yêu cầu ứng viên.
  - `Benefits` -> Quyền lợi ứng viên.
  - `Address and Time work` -> Địa điểm và thời gian làm việc.
- **Bộ tiêu đề tiếng Việt** (`2323097.html`, `2323114.html`, `2323159.html`):
  - `Tổng quan` -> Chứa tags chuyên môn và yêu cầu cơ bản.
  - `Mô tả công việc` -> Mô tả công việc.
  - `Yêu cầu ứng viên` -> Yêu cầu ứng viên.
  - `Quyền lợi ứng viên` -> Quyền lợi ứng viên.
  - `Địa điểm và thời gian` -> Địa điểm và thời gian làm việc.

> **Giải pháp kỹ thuật trong `crawler.py`**: Sử dụng hàm `get_sec(["job description", "mô tả công việc"])` để tự động bóc tách đúng bất kể tin đăng bằng ngôn ngữ nào.

---

### 4.2. Dị Biệt Mức Lương: Badge Lương "Thỏa Thuận" Nhưng Tiêu Đề Có Số Rõ Ràng
- Trong thực tế, nhiều nhà tuyển dụng chọn ô hiển thị lương ở giao diện TopCV là **"Thoả thuận"** (hoặc ẩn lương công khai với ứng viên chưa đăng nhập), nhưng lại viết dải lương thực tế trực tiếp vào **Tiêu đề công việc**:
  - `2316770`: Badge lương là `Thoả thuận`, nhưng tiêu đề ghi: `Salary Up To 1,300 USD`.
  - `2323159`: Badge lương là `Thoả thuận`, nhưng tiêu đề ghi: `Upto 35 Triệu`.
- **Nếu chỉ đọc badge lương**: Crawler cũ sẽ gán `salary_text = "Thoả thuận"` và bỏ lỡ hoàn toàn số liệu lương (`salary_min=None, salary_max=None`).
- **Giải pháp của crawler mới**: Nếu `salary_text` là *"Thoả thuận"*, regex dự phòng sẽ quét qua `title` và `description` để tìm các cụm từ như `Up To 1,300 USD` hoặc `Upto 35 Triệu`, sau đó chuyển đổi chuẩn hóa:
  - `2316770` -> `salary_max = 1300.0`, `salary_currency = "USD"`
  - `2323159` -> `salary_max = 35.0`, `salary_currency = "VND"`

---

### 4.3. Dị Biệt Lịch Làm Việc (Work Schedule)
- Các công ty phần mềm / IT Outsourcing / ERP (như LG CNS, MISA) làm việc theo chế độ chuẩn **Thứ 2 - Thứ 6**.
- Các công ty sản xuất thiết bị / phần cứng (như Sun Vigor) làm việc theo chế độ **Thứ 2 - Thứ 7**.
- Mục này nằm trong cấu trúc danh sách `ul > li` thuộc khối `.box-job-information-address-and-time-list`, được crawler bóc tách vào trường `extra.work_schedule`.

---

### 4.4. Dị Biệt Bóc Tách Tên Công Ty (Tránh Logo Rỗng)
- Trong DOM của TopCV, thẻ `<a>` đầu tiên trong `.box-company-info` thường là thẻ bọc ảnh logo công ty (không có text).
- Nếu chỉ dùng `select_one(".box-company-info a")`, text trả về sẽ là chuỗi rỗng `""`.
- **Giải pháp**: Ưu tiên `.company-name-label a` hoặc lặp qua các thẻ link công ty và kiểm tra `if a.get_text(strip=True)` để đảm bảo luôn lấy được tên công ty chuẩn xác.

---

### 4.5. Nguyên Nhân HTML Lẫn Lộn Tiếng Anh Và Tiếng Việt (Language Mixing Root Causes)

Khi phân tích các tệp HTML như `2321158.html`, `2316770.html` và các tin IT khác, chúng ta thấy hiện tượng **tiếng Anh và tiếng Việt đan xen trong cùng một trang HTML**. Nguyên nhân gốc rễ bao gồm 4 yếu tố kỹ thuật và nghiệp vụ sau:

1. **Giao diện hệ thống TopCV là nền tảng Việt Nam (Platform System UI)**:
   - Các nhãn cố định của TopCV (như *"Hạn ứng tuyển"*, *"Thông tin chung"*, *"Cấp bậc"*, *"Học vấn"*, *"Số lượng tuyển"*, *"Hình thức làm việc"*, *"Gửi tôi việc làm tương tự"*, *"Báo cáo tin tuyển dụng"*) **luôn luôn được sinh ra bằng tiếng Việt** từ mã nguồn giao diện backend của TopCV, ngay cả khi nhà tuyển dụng đăng nội dung bài viết bằng tiếng Anh.
2. **Khung mẫu bài đăng tuyển dụng (Job Posting Template)**:
   - TopCV cung cấp 2 bộ khung mẫu tiêu đề cho nhà tuyển dụng lựa chọn:
     - *Template Tiếng Anh* (dành cho FDI/quốc tế như LG CNS, Sun Vigor): Các tiêu đề section là `Job Details`, `Job Description`, `Candidate Requirements`, `Benefits`, `Address and Time work`.
     - *Template Tiếng Việt* (dành cho công ty nội địa như MISA): Các tiêu đề section là `Tổng quan`, `Mô tả công việc`, `Yêu cầu ứng viên`, `Quyền lợi ứng viên`, `Địa điểm và thời gian`.
3. **Đặc thù thuật ngữ chuyên ngành Công nghệ thông tin (IT Domain Jargon)**:
   - Lập trình và IT tại Việt Nam có tính song ngữ tự nhiên. Ngay cả các tin tuyển dụng tiếng Việt 100% của MISA vẫn chứa dày đặc các từ vựng tiếng Anh (*Fullstack, Frontend, Backend, .NET, Vuejs, API, Transaction, Caching, Concurrency, Messaging, Product Manager, CRM, Business Analyst, SQL, Upto*).
4. **Tên pháp nhân đăng ký kinh doanh và Địa giới hành chính**:
   - Theo quy định pháp luật Việt Nam, tên doanh nghiệp đăng ký pháp lý tại Sở Kế hoạch & Đầu tư và địa chỉ trụ sở/văn phòng bắt buộc phải bằng tiếng Việt (ví dụ: `CÔNG TY TNHH LG CNS VIỆT NAM`, địa chỉ: `Keangnam Landmark72, Phường Yên Hòa, Cầu Giấy, Hà Nội`), dù bản thân tin tuyển dụng tuyển kỹ sư làm việc với đối tác quốc tế bằng tiếng Anh.

> **Nguyên tắc xử lý của Parser**:
> - Nhận diện ngôn ngữ dựa trên trọng số của **Nội dung mô tả công việc (Description Text)** thay vì tên công ty hay địa chỉ hành chính.
> - Xây dựng các hàm bóc tách hỗ trợ song ngữ đồng thời (`get_sec(["job description", "mô tả công việc"])`) để tương thích hoàn toàn cả 2 mẫu giao diện.

---

### 4.6. Giải Quyết Triệt Để Lỗi Chạy `run.py` Không Ra Kết Quả (Cloudflare Bypass & Context Isolation)

Khi chạy lệnh `.venv/bin/python run.py --source topcv --max-items 3`, người dùng gặp hiện tượng crawler trả về 0 kết quả (`crawled: 0`). Nguyên nhân và giải pháp kỹ thuật đã được khắc phục:

1. **Nguyên nhân 1 - Tracking Tokens trong URL (`u_sr_id`, `ta_source`)**:
   - Các link lấy từ thẻ card tìm kiếm chứa chuỗi mã hóa tracking session của TopCV dạng `?ta_source=JobSearchList_LinkDetail&u_sr_id=...`. Khi Playwright điều hướng đến link này mà không có cookie khớp với token tìm kiếm, Cloudflare lập tức kích hoạt màn hình chặn *"Attention Required! | Cloudflare"*.
   - **Khắc phục**: Làm sạch URL, loại bỏ toàn bộ query parameters: `clean_job_url = raw_job_url.split("?")[0]`.
2. **Nguyên nhân 2 - Tái sử dụng browser context bị gắn cờ**:
   - Khi tái sử dụng cùng 1 context trình duyệt để duyệt liên tiếp nhiều trang chi tiết với tốc độ cao, Cloudflare phát hiện hành vi bot tự động.
   - **Khắc phục**: Khởi tạo context sạch riêng biệt cho mỗi trang chi tiết (`detail_context = browser.new_context(...)`) và đóng context ngay sau khi hoàn thành.
3. **Nguyên nhân 3 - Cơ chế Fallback an toàn**:
   - Nếu một trang chi tiết bất kỳ gặp sự cố mạng hoặc thử thách Cloudflare, crawler sẽ tự động lấy dữ liệu tóm tắt từ thẻ card tìm kiếm (Snippet fallback), đảm bảo tiến trình không bị gián đoạn và luôn trả về đầy đủ số lượng tin yêu cầu.

---

## 5. Hướng Dẫn Vận Hành `crawler.py`

### 5.1. Chạy Cào Trực Tuyến Từ TopCV (Playwright Chrome Headless)
```bash
# Cào 5 tin tuyển dụng từ trang tìm kiếm và lưu HTML chi tiết
.venv/bin/python3 -m crawlers.sources.topcv.crawler --max-items 5 --output-dir data
```

### 5.2. Chạy Kiểm Thử Offline Nhanh Từ 5 File HTML Đã Có
```bash
# Parse trực tiếp từ các file HTML trong thư mục crawlers/sources/topcv không cần tải lại mạng
.venv/bin/python3 -m crawlers.sources.topcv.crawler --max-items 5 --local-html-dir crawlers/sources/topcv --output-dir data
```

---

## 6. Tổng Kết Danh Mục Tệp Đã Hoàn Thành
1. [`crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/crawler.py): Crawler 2 giai đoạn mới bóc tách 100% dữ liệu song ngữ.
2. 5 File HTML mẫu thực tế:
   - [`2321158.html`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/2321158.html)
   - [`2316770.html`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/2316770.html)
   - [`2323097.html`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/2323097.html)
   - [`2323114.html`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/2323114.html)
   - [`2323159.html`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/2323159.html)
3. [`test_5_jobs.json`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/test_5_jobs.json): Kết quả bóc tách chuẩn định dạng của 5 tin tuyển dụng trên.
4. [`INSTRUCTION_ANALYSIS.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/INSTRUCTION_ANALYSIS.md): Báo cáo so sánh đối chiếu và phân tích toàn diện.

---

## 7. Đề Xuất Kế Hoạch Cải Tiến & Chuẩn Hóa Schema Mới (Enhancement Plan)

Sau quá trình bóc tách và đánh giá chất lượng dữ liệu từ 5 file thực tế, hệ thống ghi nhận **4 vấn đề trọng tâm** cần nâng cấp và hoàn thiện giải pháp:

### 7.1. Phân Định Miền URL & Hỗ Trợ Đa Ngữ (`/en`, `?lang=en`)
* **Vấn đề đặt ra**: Nếu TopCV có đường dẫn `/en` như `https://tuyendung.topcv.vn/en` thì hệ thống xử lý ra sao?
* **Khám phá & Bản chất**:
  1. `tuyendung.topcv.vn` là **Cổng dành riêng cho Nhà Tuyển Dụng (Recruiter/Employer B2B Portal)**. Tuyến đường `/en` tại đây là trang landing page tiếng Anh giới thiệu dịch vụ đăng tin, tìm kiếm hồ sơ cho các doanh nghiệp FDI. Trang này **không chứa danh sách tin tuyển dụng** để ứng viên tìm kiếm hay nộp đơn.
  2. Cổng thông tin việc làm dành cho **Ứng viên (Job Seeker)** nằm tại miền chính `www.topcv.vn`.
  3. Trên `www.topcv.vn`, trang chi tiết hỗ trợ tham số đa ngữ `?lang=en` (như đã phát hiện trong thẻ tham chiếu của file [`2316770.html`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/2316770.html): `https://www.topcv.vn/viec-lam/.../2316770.html?lang=en`).
* **Giải pháp đề xuất**:
  * Crawler chỉ tập trung cào cổng ứng viên `www.topcv.vn/viec-lam-it` và `www.topcv.vn/viec-lam-tieng-anh`, loại trừ miền B2B `tuyendung.topcv.vn`.
  * Bộ bóc tách hiện tại đã xây dựng cơ chế song ngữ (Bilingual Parser) tương thích cả 2 mẫu template tiếng Anh (`Job Details`, `Job Description`, `Candidate Requirements`, `Benefits`) và tiếng Việt (`Tổng quan`, `Mô tả công việc`, `Yêu cầu`, `Quyền lợi`).
  * Chuẩn hóa bộ lọc URL để hỗ trợ cả định dạng không tham số và có tham số `?lang=en`.

---

### 7.2. Chuẩn Hóa Cấu Trúc Mức Lương (`salary` Object)
* **Vấn đề đặt ra**: Cấu trúc phẳng cũ (`salary_text`, `salary_min`, `salary_max`, `salary_currency`) chưa phản ánh đủ kỳ hạn trả lương (tháng/năm/ngày) và các điều kiện hoa hồng/thưởng doanh số/thỏa thuận.
* **Cấu trúc JSON đề xuất**:
```json
"salary": {
  "salary_text": "Tới 40 triệu",
  "salary_min": null,
  "salary_max": 40.0,
  "salary_currency": "VND",
  "pay_period": "month",
  "is_negotiable": false,
  "has_commission": false
}
```
* **Giải pháp bóc tách ngữ nghĩa**:
  1. **`pay_period` (Chu kỳ trả lương)**:
     - Nhận diện `"month"`: Khớp các từ khóa `tháng`, `/tháng`, `/thang`, `triệu`, `tr`, `monthly`, `pm`. Đối với thị trường IT Việt Nam, khi ghi số triệu hoặc ngàn USD mà không có định ngữ năm/ngày thì mặc định là chu kỳ tháng (`month`).
     - Nhận diện `"year"`: Khớp `năm`, `/năm`, `/year`, `annual`, `annually`, `pa`.
     - Nhận diện `"day"`: Khớp `ngày`, `/ngày`, `/day`, `daily`.
     - Nhận diện `"hour"`: Khớp `giờ`, `/giờ`, `/hour`, `hourly`.
     - Trường hợp thỏa thuận hoàn toàn không xác định: gán `null`.
  2. **`has_commission` (Hoa hồng / Thu nhập biến đổi)**:
     - Nhận diện `true` khi văn bản chứa: `"hoa hồng"`, `"commission"`, `"thu nhập không giới hạn"`, `"không giới hạn"`, `"thưởng doanh số"`, `"bonus theo doanh số"`.
     - Ví dụ trường hợp: *"Lương cứng 15 triệu + Hoa hồng"* -> `salary_min = 15.0`, `salary_max = null` (do trần mở), `has_commission = true`.
  3. **`is_negotiable` (Thỏa thuận / Thương lượng)**:
     - Nhận diện `true` khi `salary_text` chứa: `"thỏa thuận"`, `"thoả thuận"`, `"thương lượng"`, `"negotiable"`, `"competitive"`.

---

### 7.3. Phân Nhóm Thẻ Tag Chuyên Môn, Yêu Cầu, Phúc Lợi (`tags` Object)
* **Vấn đề đặt ra**: TopCV gom toàn bộ các thẻ tag vào chung một cụm (kinh nghiệm, bằng cấp, kỹ năng, chức danh, phúc lợi), làm trường `skills_text` cũ bị lẫn lộn.
* **Cấu trúc JSON đề xuất**:
```json
"tags": {
  "technical_skills": ["C#", ".NET", "Vuejs", "SQL Server"],
  "job_roles": ["Fullstack Developer"],
  "requirements": [
    "Có từ 3-4 năm kinh nghiệm phát triển ứng dụng Web với C#, .NET/.NET Core",
    "Có kinh nghiệm phát triển Frontend với JavaScript/TypeScript và ít nhất một framework Angular, React hoặc Vue",
    "Nắm vững OOP, SOLID, Design Pattern"
  ],
  "benefits": [
    "Mức lương cạnh tranh vượt trội lên tới 40 triệu/tháng",
    "Thưởng Performance dựa trên kết quả sản phẩm",
    "Chăm sóc sức khỏe tại Medlatec, teambuilding thường niên"
  ],
  "attributes": {
    "experience": "3 năm kinh nghiệm chuyên môn",
    "education": "Đại Học trở lên",
    "age": "Tuổi 26 - 35"
  }
}
```
* **Quy tắc phân loại**:
  - Dùng bộ phân loại từ khóa (Keyword/Regex Classifier) để tách các thẻ badge header thành:
    - `technical_skills`: Công nghệ, ngôn ngữ, framework, hệ quản trị cơ sở dữ liệu.
    - `job_roles`: Vị trí chức danh (Developer, BA, PM, Tester, DevOps).
    - `attributes`: Các điều kiện cứng (kinh nghiệm số năm, học vấn đại học/cao đẳng, độ tuổi).

---

### 7.4. Chuẩn Hóa Văn Bản Ngắt Dòng `\n` Sang Dạng Mảng Chuỗi (`list[str]`)
* **Vấn đề đặt ra**: Chuỗi dài dính nhiều dòng `\n` gây khó khăn cho việc nhúng vector (embedding), trích xuất thực thể (NER), và truy vấn dữ liệu theo từng tiêu chí cụ thể.
* **Giải pháp đề xuất**:
  - Tách các đoạn văn bản trong `requirements_text`, `benefits_text`, `description_text` theo từng thẻ `<li>`, `<p>` hoặc split theo `\n`.
  - Làm sạch các ký hiệu gạch đầu dòng (`- `, `* `, `• `, `+ `, `1. `, `2. `) và khoảng trắng thừa.
  - Cung cấp song song 2 trường:
    - Giữ trường chuỗi `_text` (phục vụ tương thích ngược và full-text search).
    - Bổ sung trường mảng `_list` (`requirements_list`, `benefits_list`, `description_list`) kiểu `list[str]`.

---

### 7.5. Nguyên Tắc Bảo Toàn Luồng Airflow & Tương Thích Ngược Schema
* **Bảo toàn 100% Airflow**:
  - Không sửa đổi DAG `crawler_topcv` trong [`airflow/dags/crawler_dags.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/airflow/dags/crawler_dags.py).
  - Không sửa đổi `JobCrawlerOperator` và `DataQualityOperator` trong [`airflow/plugins/crawler_operators.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/airflow/plugins/crawler_operators.py).
  - Giữ nguyên toàn bộ interface `TopCVCrawler(output_dir=..., max_items=...)` và method `crawler.run()`.
* **Thay đổi Schema minh bạch & Không phá vỡ (Non-breaking additive changes)**:
  - Giữ nguyên 100% tất cả các trường cũ của `JobRaw` (`title`, `company`, `salary_text`, `salary_min`, `salary_max`, `salary_currency`, `requirements_text`, `benefits_text`, `description_text`, `skills_text`, v.v.).
  - Bổ sung các trường mới (`salary`, `tags`, `description_list`, `requirements_list`, `benefits_list`) với giá trị mặc định là `None` hoặc rỗng trong [`crawlers/common/schema.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/common/schema.py).
  - Đảm bảo 5 crawler nguồn khác (TopDev, ITviec, CareerViet, VietnamWorks, ViecLam24h) và `DataQualityChecker` tiếp tục validate hợp lệ 100%.

---

### 7.6. Lộ Trình Triển Khai Kỹ Thuật (Roadmap)
1. **Bước 1 (Schema & Utilities)**: 
   - Bổ sung `JobSalary` và `JobTags` vào [`crawlers/common/schema.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/common/schema.py).
   - Nâng cấp hàm `parse_salary()` trong [`crawlers/common/utils.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/common/utils.py) để hỗ trợ `pay_period`, `is_negotiable`, `has_commission`.
   - Bổ sung hàm tách chuỗi sang mảng dòng `text_to_clean_lines()` và hàm phân loại tag `classify_job_tags()`.
2. **Bước 2 (Crawler Parser)**: 
   - Cập nhật hàm `parse_item()` trong [`crawlers/sources/topcv/crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/crawler.py) để sinh đầy đủ cấu trúc `salary`, `tags` và các trường `_list` mới song song với các trường truyền thống.
3. **Bước 3 (Kiểm thử & Cập nhật Dữ liệu)**: 
   - Chạy kiểm thử offline trên 5 file HTML thực tế, tái tạo lại [`crawlers/sources/topcv/test_5_jobs.json`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/topcv/test_5_jobs.json).
   - Chạy `DataQualityChecker` xác thực chất lượng file dữ liệu.
   - Chạy toàn bộ test suite `pytest` bảo đảm 100% test pass.

---

## 8. Kế Hoạch Tinh Gọn Data Contract & Tắt Lưu HTML Cục Bộ

### 8.1. Các Thay Đổi Cốt Lõi Trong `schema.py`
1. **Loại bỏ hoàn toàn trường HTML thô**: Xóa bỏ `description_html` để giảm dung lượng file JSON và loại bỏ sự dư thừa dữ liệu.
2. **Chuyển đổi hoàn toàn sang mảng `list[str]`**:
   - `description_text` -> Xóa bỏ, thay bằng `description_list: list[str]`.
   - `requirements_text` -> Xóa bỏ, thay bằng `requirements_list: list[str]`.
   - `benefits_text` -> Xóa bỏ, thay bằng `benefits_list: list[str]`.
   - `skills_text` -> Xóa bỏ, sử dụng `tags.technical_skills: list[str]`.
3. **Thu gọn cấu trúc mức lương**:
   - Xóa bỏ các trường phẳng ở root: `salary_text`, `salary_min`, `salary_max`, `salary_currency`.
   - Giữ duy nhất đối tượng lồng nhau: `salary: JobSalary` (`salary_text`, `salary_min`, `salary_max`, `salary_currency`, `pay_period`, `is_negotiable`, `has_commission`).
4. **Bộ thích ứng tương thích ngược thông minh (Smart Ingestion Pre-Validator)**:
   - Dùng `@model_validator(mode="before")` trong `JobRaw` để tự động chuyển đổi các trường cũ (từ các crawler khác hoặc test suite cũ) sang cấu trúc mới, đảm bảo 100% các crawler khác không bị gãy khi chạy qua Airflow.

### 8.2. Tắt Tính Năng Xuất File HTML Trong `crawler.py`
- Đổi mặc định `save_html = False` trong `TopCVCrawler.__init__` và `--save-html default=False` trong CLI `main()`.
- Trong `_sync_fetch_with_playwright()`, chỉ lưu file HTML nếu người dùng chỉ định rõ ràng `--save-html`.
- Cập nhật hàm `parse_item()` để xuất ra đúng cấu trúc tinh gọn mới, loại bỏ việc gán các trường đã xóa.

---

## 9. Chuẩn Hóa Nhóm Thẻ JobTags (Yêu Cầu, Quyền Lợi, Chuyên Môn)

### 9.1. Quy Cách Bóc Tách Thẻ Nhóm Cốt Lõi
- Khối `.job-tags` trên TopCV phân tách rõ rệt 3 nhóm thẻ tag (badges):
  1. `requirements`: Thẻ tag từ nhóm **Yêu cầu:** (ví dụ: `3 năm kinh nghiệm chuyên môn`, `Đại Học trở lên`, `Tiếng Anh TOEIC 650`).
  2. `benefits`: Thẻ tag từ nhóm **Quyền lợi:** (ví dụ: `Bảo hiểm xã hội`, `Bảo hiểm sức khỏe`). **Nếu trang tuyển dụng không có nhóm này (ví dụ Job ID `2157137`), trường này có giá trị `null`**.
  3. `skills`: Thẻ tag từ nhóm **Chuyên môn:** (ví dụ: `Business Analyst (Phân tích nghiệp vụ)`, `IT - Phần mềm`).
- **Phân định rạch ròi với nội dung chi tiết**:
  - `tags`: Tuyệt đối không nhồi nhét nội dung bài viết mô tả vào tags. Chỉ lưu các từ khóa/badge ngắn gọn.
  - `requirements_list` và `benefits_list`: Lưu trữ toàn bộ các bullet point mô tả chi tiết từ bài tuyển dụng dạng `list[str]`.




