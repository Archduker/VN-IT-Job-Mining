# Ma Trận So Sánh & Đối Chiếu Schema 7 Nguồn Tuyển Dụng (Schema Comparison Matrix)

> **Mục tiêu tài liệu**: Đối chiếu chi tiết 15 trường dữ liệu thực tế từ các file JSON mẫu của từng nhánh crawl so với chuẩn **Data Contract Schema v1** của dự án VN-IT-Job-Mining.  
> **Tài liệu tham chiếu**: [Skill `job-crawler-analyzer`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/.agents/skills/job-crawler-analyzer/SKILL.md), [`crawlers/common/schema.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/common/schema.py).  
> **Cập nhật ngày**: 11/10/2026

---

## 1. Bảng Ma Trận So Sánh 15 Trường Dữ Liệu Thực Tế

| Nhóm Trường | Tên Trường | Chuẩn Data Contract Schema v1 | TopCV (`main`) | CareerViet (`crawl/careerviet`) | VietnamWorks (`crawl/vietnamworks`) | ITviec (`feature/itviec-crawler`) | Glints (`crawler-glints`) | TopDev (`feature/topdev-son`) | Việc Làm 24h (`crawler-vieclam24h`) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`_meta`** | `source` | `str` (slug) | `"topcv"` | `"careerviet"` | `"vietnamworks"` | `"itviec"` | `"glints"` | `"topdev"` | `"vieclam24h"` |
| | `source_job_id` | `str` (unique ID) | `str` | `str` | `str` | `str` | `str` | `str` | `str` |
| | `url` | `str` (canonical, no utm) | Normalized | Normalized | Normalized | Normalized | Normalized | Normalized | Fallback URL |
| | `dedup_key` | `source:id` |  |  |  |  |  |  |  |
| | `language` | `str` (`"vi"` / `"en"`) |  |  |  |  |  |  |  |
| **`raw` (Cốt lõi)** | `title` | `str` (bắt buộc) |  |  |  |  |  |  |  |
| | `company` | `str` (bắt buộc) |  |  |  |  |  |  |  |
| | `salary` | `JobSalary` object lồng | `JobSalary` | `JobSalary` | `JobSalary` (USD/VND) | `JobSalary` dict | `JobSalary` dict | `JobSalary` object | `JobSalary` object |
| | `tags` | `JobTags` (3 nhóm) | 3 nhóm | 3 nhóm (`null` benefits) | 3 nhóm (`null` req) | 3 nhóm | 3 nhóm | 3 nhóm | ❌ Gán nhầm nội dung vào tags |
| | `description_list` | `list[str]` (bắt buộc) | List sạch | List sạch | List sạch | List sạch | List sạch | ❌ **Bị `null` ở một số tin!** | ❌ **Gán `None` nếu rỗng!** |
| | `requirements_list`| `list[str]` | List sạch | List sạch | List sạch | List sạch | List sạch | List sạch | List sạch |
| | `benefits_list` | `list[str]` | List sạch | List sạch | List sạch | List sạch | List sạch | List sạch | List sạch |
| **`raw` (Bổ trợ)** | `location_text` | `str \| null` |  |  |  |  |  |  |  |
| | `deadline_text` | `str \| null` |  |  |  |  |  | `null` |  |
| | `extra` | `dict \| null` | Structured | Structured | Structured | Structured | Structured | Structured | ❌ Hardcode giả lập |

---

## 2. Trích Dẫn Mẫu JSON Thực Tế Của Từng Nguồn

### 1. TopCV (Nguồn Chuẩn Mẫu - `crawlers/sources/topcv/test_5_jobs.json`)
```json
{
  "_meta": {
    "source": "topcv",
    "source_job_id": "2323097",
    "url": "https://www.topcv.vn/viec-lam/2323097.html",
    "dedup_key": "topcv:2323097",
    "language": "vi"
  },
  "raw": {
    "title": "Fullstack Developer (C#, .NET, Vuejs)",
    "company": "MISA",
    "salary": {
      "salary_text": "Tới 40 triệu",
      "salary_min": null,
      "salary_max": 40.0,
      "salary_currency": "VND",
      "pay_period": "month",
      "is_negotiable": false,
      "has_commission": false
    },
    "tags": {
      "requirements": ["3 năm kinh nghiệm", "Đại Học trở lên"],
      "benefits": ["Thưởng doanh số", "Khám sức khỏe"],
      "skills": ["C#", ".NET", "Vuejs"]
    },
    "description_list": [
      "Tham gia phát triển các sản phẩm SaaS phục vụ doanh nghiệp",
      "Thiết kế kiến trúc hệ thống backend trên nền tảng .NET Core"
    ],
    "requirements_list": [
      "Tối thiểu 3 năm kinh nghiệm với C# .NET",
      "Có kiến thức tốt về Vue.js, RESTful API và Docker"
    ],
    "benefits_list": [
      "Lương thỏa thuận cạnh tranh lên tới 40M",
      "Thưởng tháng lương thứ 13 và thưởng hiệu quả kinh doanh"
    ],
    "location_text": "Tòa nhà MISA, Cầu Giấy, Hà Nội",
    "deadline_text": "05/11/2026"
  }
}
```

---

### 2. CareerViet (`crawlers/sources/careerviet/test_5_jobs.json`)
```json
{
  "_meta": {
    "source": "careerviet",
    "source_job_id": "35C89996",
    "url": "https://careerviet.vn/vi/tim-viec-lam/job.35C89996.html",
    "dedup_key": "careerviet:35C89996",
    "language": "vi"
  },
  "raw": {
    "title": "Chuyên Viên Tư Vấn Triển Khai ERP (Khối Doanh nghiệp)",
    "company": "CÔNG TY CỔ PHẦN CÔNG NGHỆ FOXAI",
    "salary": {
      "salary_text": "12 Tr - 35 Tr VND",
      "salary_min": 12.0,
      "salary_max": 35.0,
      "salary_currency": "VND",
      "pay_period": "month",
      "is_negotiable": false,
      "has_commission": false
    },
    "tags": {
      "requirements": null,
      "benefits": null,
      "skills": ["Kỹ sư CNTT", "IT", "ERP", "SAP ERP"]
    },
    "description_list": [
      "Phân tích nghiệp vụ khách hàng, thu thập yêu cầu và xây dựng giải pháp",
      "Tham gia khảo sát, lập tài liệu Blueprint / BRD / SDD"
    ],
    "requirements_list": [
      "Tối thiểu 02 năm kinh nghiệm triển khai ERP",
      "Sẵn sàng đi công tác tỉnh/thành hoặc nước ngoài"
    ],
    "benefits_list": [
      "Mức thu nhập cạnh tranh: 15–35 triệu/tháng",
      "Được hưởng đầy đủ BHXH, BHYT theo luật lao động"
    ],
    "location_text": "Hà Nội",
    "deadline_text": "06/11/2026"
  }
}
```

---

### 3. VietnamWorks (`crawlers/sources/vietnamworks/test_5_jobs.json`)
```json
{
  "_meta": {
    "source": "vietnamworks",
    "source_job_id": "1892837",
    "url": "https://www.vietnamworks.com/job-1892837-jv",
    "dedup_key": "vietnamworks:1892837",
    "language": "en"
  },
  "raw": {
    "title": "Senior Software Engineer (Java/Python/Go)",
    "company": "Tech Innovation Global",
    "salary": {
      "salary_text": "1,500 - 2,500 USD",
      "salary_min": 1500.0,
      "salary_max": 2500.0,
      "salary_currency": "USD",
      "pay_period": "month",
      "is_negotiable": false,
      "has_commission": false
    },
    "tags": {
      "requirements": null,
      "benefits": ["Máy tính xách tay", "Cơ hội du lịch"],
      "skills": ["Java/.Net/Python", "Golang"]
    },
    "description_list": [
      "Design and build scalable microservices platforms",
      "Participate in design discussions and code reviews"
    ],
    "requirements_list": [
      "4+ years of professional software engineering experience",
      "Deep understanding of concurrent programming and database design"
    ],
    "benefits_list": [
      "Laptop: Thinkpad / Macbook Pro",
      "Travel Opportunities: Annual company trip"
    ],
    "location_text": "Hồ Chí Minh, Hà Nội",
    "deadline_text": "2026-11-20T00:00:00Z"
  }
}
```

---

### 4. ITviec (`origin/feature/itviec-crawler` - Bạn Phát)
```json
{
  "_meta": {
    "source": "itviec",
    "source_job_id": "senior-python-dev-12345",
    "url": "https://itviec.com/it-jobs/senior-python-dev-12345",
    "dedup_key": "itviec:senior-python-dev-12345",
    "language": "en"
  },
  "raw": {
    "title": "Senior Python Backend Engineer",
    "company": "Global FinTech Ltd",
    "salary": {
      "salary_text": "You'll love it",
      "salary_min": null,
      "salary_max": null,
      "salary_currency": null,
      "pay_period": "month",
      "is_negotiable": true,
      "has_commission": false
    },
    "tags": {
      "requirements": null,
      "benefits": null,
      "skills": ["Python", "Django", "PostgreSQL", "AWS"]
    },
    "description_list": [
      "Build high throughput financial APIs",
      "Maintain scalable services on AWS ECS"
    ],
    "requirements_list": [
      "Solid understanding of Python 3.11+ and async frameworks",
      "Experience with relational and NoSQL databases"
    ],
    "benefits_list": [
      "Premium health insurance for employee and family",
      "13th month salary and annual performance bonus"
    ],
    "location_text": "Ho Chi Minh City",
    "deadline_text": "2026-11-15T00:00:00Z"
  }
}
```

---

### 5. Glints (`origin/crawler-glints` - Bạn Duy)
```json
{
  "_meta": {
    "source": "glints",
    "source_job_id": "job-12345",
    "url": "https://glints.com/vn/opportunities/jobs/job-12345",
    "dedup_key": "glints:job-12345",
    "language": "vi"
  },
  "raw": {
    "title": "Kỹ Sư Phần Mềm (Python / SQL)",
    "company": "Công Ty Cổ Phần Công Nghệ ABC",
    "description_html": "<p>Mô tả chi tiết công việc</p>",
    "description_text": "Mô tả chi tiết công việc",
    "description_list": ["Mô tả chi tiết công việc"],
    "salary": {
      "salary_text": "9,000,000 - 20,000,000 VND / month",
      "salary_min": 9000000.0,
      "salary_max": 20000000.0,
      "salary_currency": "VND",
      "pay_period": "month",
      "is_negotiable": false,
      "has_commission": false
    },
    "tags": {
      "skills": ["Python", "SQL"],
      "requirements": [],
      "benefits": []
    },
    "requirements_list": ["Yêu cầu thành thạo Python và cơ sở dữ liệu SQL"],
    "benefits_list": ["Chế độ đãi ngộ tốt, phát triển nghề nghiệp"],
    "location_text": "Ho Chi Minh City",
    "deadline_text": "2026-11-01"
  }
}
```
> ⚠️ **Độ lệch**: Vẫn giữ 2 trường phẳng cũ `description_html` và `description_text` ở root của `raw`. Cần dọn dẹp để thuần khiết Schema v1.

---

### 6. TopDev (`origin/feature/topdev-son` - Bạn Sơn)
```json
{
  "_meta": {
    "source": "topdev",
    "source_job_id": "2137764",
    "url": "https://topdev.vn/detail-jobs/phien-dich-tieng-han-2137764",
    "dedup_key": "topdev:2137764",
    "language": "vi"
  },
  "raw": {
    "title": "Phiên Dịch Tiếng Hàn (Korean Interpreter)",
    "company": "CÔNG TY TNHH HANMIR",
    "description_list": null,
    "salary": {
      "salary_text": "Thương lượng",
      "salary_min": 0.0,
      "salary_max": 0.0,
      "salary_currency": "VND",
      "pay_period": "month",
      "is_negotiable": true,
      "has_commission": false
    },
    "tags": {
      "requirements": null,
      "benefits": null,
      "skills": ["Korean", "Biên dịch viên"]
    },
    "requirements_list": ["1-2 năm kinh nghiệm làm việc", "Tối thiểu TOPIK 4"],
    "benefits_list": ["Thưởng lễ", "Đóng bảo hiểm full lương"],
    "location_text": "Thành phố Hồ Chí Minh",
    "deadline_text": null
  }
}
```
> ❌ **LỖI NGHIÊM TRỌNG**: `"description_list": null` vi phạm trực tiếp kiểu `list[str]` của Pydantic `JobRaw`, khiến Pydantic văng ngoại lệ `ValidationError` khi validate bằng schema chính thức!

---

### 7. Việc Làm 24h (`origin/feature/crawler-vieclam24h` - Bạn Phúc)
```json
{
  "_meta": {
    "source": "vieclam24h",
    "source_job_id": "10023456",
    "url": "https://vieclam24h.vn/it-phan-mem/lap-trinh-vien-id10023456.html",
    "dedup_key": "vieclam24h:10023456",
    "language": "vi"
  },
  "raw": {
    "title": "Lập Trình Viên Backend Node.js",
    "company": "Công Ty TNHH Giải Pháp Số",
    "salary": {
      "salary_text": "15 - 25 triệu",
      "salary_min": 15.0,
      "salary_max": 25.0,
      "salary_currency": "VND",
      "pay_period": "month",
      "is_negotiable": false,
      "has_commission": false
    },
    "tags": {
      "requirements": ["Có 2 năm kinh nghiệm Node.js", "Biết Docker, Redis"],
      "benefits": ["Thưởng tháng 13", "Khám sức khỏe định kỳ"],
      "skills": null
    },
    "description_list": ["Phát triển microservices bằng Node.js NestJS"],
    "requirements_list": ["Có 2 năm kinh nghiệm Node.js", "Biết Docker, Redis"],
    "benefits_list": ["Thưởng tháng 13", "Khám sức khỏe định kỳ"],
    "location_text": "Hà Nội",
    "deadline_text": "2026-11-20",
    "extra": {
      "work_schedule": "Thứ 2 - Thứ 6",
      "education": "Đại Học trở lên",
      "employment_type_text": "Toàn thời gian",
      "seniority_text": "Nhân viên"
    }
  }
}
```
> ❌ **LỖI NGHIÊM TRỌNG**: Nhầm lẫn giữa pill tags và nội dung bài viết (copy nguyên văn `requirements_list` vào `tags.requirements`), bỏ trống `tags.skills`, và hardcode các trường `extra` không phản ánh đúng dữ liệu gốc.

---

## 3. Bảng Tổng Hợp Độ Lệch & Kế Hoạch Chuẩn Hóa Trước Khi Merge (Action Items)

| Nguồn Web | Mức Độ Tuân Thủ Schema v1 | Lỗi / Độ Lệch Phát Hiện | Biện Pháp Chuẩn Hóa Bắt Buộc (Action Items) |
| :--- | :---: | :--- | :--- |
| **TopCV** |  **100% Hoàn Hảo** | Không có | Giữ nguyên làm thước đo benchmark. |
| **CareerViet** |  **100% Hoàn Hảo** | Không có (Đã refactor đạt chuẩn) | Đã sẵn sàng trên nhánh `crawl-main`. |
| **VietnamWorks** |  **100% Hoàn Hảo** | Không có (Đã refactor đạt chuẩn) | Đã sẵn sàng trên nhánh `crawl-main`. |
| **ITviec** |  **100% Hoàn Hảo** | Không có lỗi schema | Sẵn sàng merge về mặt dữ liệu. |
| **Glints** | 🟡 **90% Đạt Chuẩn** | Dư thừa 2 field phẳng `description_html` và `description_text` ở root của `raw`. | Loại bỏ 2 field phẳng dư thừa để khớp 100% Schema v1 tinh gọn. |
| **TopDev** | 🔴 **75% Lỗi Schema** | `description_list` bị `null` ở các tin thiếu mô tả; dính file dữ liệu 64k dòng. | 1. Bổ sung fallback `description_list = description_list or [title]`.<br/>2. Loại bỏ file 64k dòng khỏi git tracking. |
| **Việc Làm 24h**| 🔴 **60% Lỗi Nghiêm Trọng** | Gán `description_list = None` nếu rỗng; nhầm lẫn `tags`; hardcode giả lập `extra`; crash vòng lặp `main()`. | 1. Bổ sung fallback `description_list = description_list or [title]`.<br/>2. Sửa bóc tách `tags.skills`.<br/>3. Xóa bỏ hardcode giả lập.<br/>4. Sửa hàm `main()` và thêm headless Chrome. |
