---
name: job-crawler-analyzer
description: >-
  Chuyên gia phân tích và bóc tách dữ liệu tuyển dụng từ bất kỳ nguồn web nào.
  Tiếp nhận 1 URL nguồn, 1 file HTML thô đại diện (DOM), và 1 file kết quả JSON mong muốn;
  tự động phân tích kiến trúc mạng, chống bot, trích xuất lương lồng nhau, phân chia 3 nhóm thẻ tags
  (Yêu cầu, Quyền lợi, Chuyên môn với quy tắc null), làm sạch văn bản bullet và ánh xạ vào Data Contract.
---

# Job Crawler Analyzer Skill

Kỹ năng này trang bị cho AI Agent năng lực phân tích toàn diện một nguồn tuyển dụng bất kỳ để thiết kế parser đạt chuẩn Data Contract dự án VN-IT-Job-Mining.

---

## 1. Đầu Vào Tiêu Chuẩn (Input Specification)

Khi người dùng cung cấp hoặc yêu cầu phân tích một nguồn tuyển dụng, bạn cần 3 thông tin đầu vào:
1. `source_url`: URL bài đăng mẫu (Ví dụ: `https://.../viec-lam/...`).
2. `raw_html`: File HTML hoặc chuỗi DOM đại diện đã tải về của bài đăng.
3. `target_json`: File hoặc cấu trúc JSON mẫu mong muốn (Target Data Contract).

---

## 2. Quy Trình Bóc Tách 5 Bước (Standard Procedure)

### Bước 1: Khảo Sát Kiến Trúc Mạng & Phòng Vệ
- **Xác định loại Render**:
  - Chạy `curl -A "<user_agent>" "<url>"`. Nếu có văn bản bài viết $\rightarrow$ **SSR** (`requests` / `httpx`).
  - Nếu trả về rỗng hoặc bị Cloudflare Challenge (`Attention Required!`) $\rightarrow$ **Playwright Headless Chrome** (`--disable-blink-features=AutomationControlled`, `--no-sandbox`).
  - Tìm kiếm API ẩn trên tab Network $\rightarrow$ Ưu tiên cào qua REST API nếu có.
- **Làm sạch URL**: Bỏ tracking token (`utm_*`, `u_sr_id`, `ta_source`) giữ lại canonical URL.

### Bước 2: Bóc Tách DOM Bằng BeautifulSoup
Luôn áp dụng cơ chế tìm kiếm an toàn (Safe Extraction) với nhiều selector dự phòng:
```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html_content, "html.parser")

# Tiêu đề
title_el = soup.select_one("h1.box-header-job__title, h1.title, h1")
title = title_el.get_text(separator=" ", strip=True) if title_el else None

# Công ty
company_el = soup.select_one(".company-name-label a, .company-name-label, .company")
company = company_el.get_text(strip=True) if company_el else None
```

### Bước 3: Chuẩn Hóa Lương & Phân Nhóm Thẻ Tags

#### 1. Mức Lương Lồng Nhau (`JobSalary`)
Dùng hàm `parse_salary_detail(salary_text, title)`:
- `salary_min`: Lương tối thiểu (số thực triệu VNĐ hoặc USD).
- `salary_max`: Lương tối đa (số thực triệu VNĐ hoặc USD).
- `salary_currency`: `"VND"` hoặc `"USD"`.
- `pay_period`: `"month"`, `"year"`, `"day"`, hoặc `"hour"`.
- `is_negotiable`: `True` nếu có từ khóa *"Thỏa thuận"*, *"Cạnh tranh"*, *"Negotiable"*.
- `has_commission`: `True` nếu có từ khóa *"hoa hồng"*, *"thưởng KPI"*, *"commission"*.
- *Fallback*: Nếu mức lương hiển thị là *"Thỏa thuận"* nhưng tiêu đề có ghi số tiền (ví dụ: *"Dev Python Upto 35 Triệu"*), tự động quét regex từ tiêu đề!

#### 2. Phân Nhóm Thẻ Tags (`JobTags`)
Quét các nhóm `.job-tags__group` hoặc badge container:
```python
tag_requirements = []
tag_benefits = []
tag_skills = []
found_benefits_group = False

for group in soup.select(".job-tags .job-tags__group"):
    g_title = group.select_one(".job-tags__group-name").get_text(strip=True).lower()
    items = [a.get_text(strip=True) for a in group.select(".item") if not a.get_text(strip=True).startswith("+")]
    
    if any(k in g_title for k in ["yêu cầu", "requirement"]):
        tag_requirements.extend(items)
    elif any(k in g_title for k in ["quyền lợi", "benefit", "phúc lợi"]):
        found_benefits_group = True
        tag_benefits.extend(items)
    elif any(k in g_title for k in ["chuyên môn", "specialization", "skill"]):
        tag_skills.extend(items)

tags = {
    "requirements": tag_requirements if tag_requirements else None,
    "benefits": tag_benefits if (found_benefits_group and tag_benefits) else None,
    "skills": tag_skills if tag_skills else None,
}
```
> **QUY TẮC BẮT BUỘC**: Nếu trang không có nhóm thẻ quyền lợi $\rightarrow$ `benefits: null`. Tuyệt đối không nhồi nhét văn bản bài viết vào `tags`.

#### 3. Làm Sạch Dòng Văn Bản (`list[str]`)
Dùng hàm `text_to_clean_lines(content)` để bóc tách:
- `description_list`: Danh sách các dòng mô tả công việc sạch.
- `requirements_list`: Danh sách các dòng yêu cầu ứng viên sạch.
- `benefits_list`: Danh sách các dòng quyền lợi sạch.
Loại bỏ hoàn toàn các ký tự bullet đầu dòng: `•`, `-`, `*`, `+`, `1.`, `2)`.

### Bước 4: Kiểm Soát Chất Lượng Dữ Liệu
Chạy kiểm tra bắt buộc qua `DataQualityChecker`:
```bash
python -c "
from crawlers.common.data_quality import DataQualityChecker
checker = DataQualityChecker('crawlers/sources/<source>/test_5_jobs.json')
result = checker.check()
assert result['passed'] is True
assert result['schema_valid_rate'] == 100.0
assert result['unique_rate'] == 100.0
"
```

### Bước 5: Tích Hợp BaseCrawler & Bảo Vệ Airflow
- Kế thừa `BaseCrawler`.
- Đặt `save_html = False` làm giá trị mặc định để không lưu rác HTML.
- **Không bao giờ sửa đổi Airflow DAGs hay Operators** (`airflow/dags/`, `airflow/plugins/`).
