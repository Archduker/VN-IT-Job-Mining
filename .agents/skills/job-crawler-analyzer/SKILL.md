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

### Bước 3: Thu Thập Thô Nguyên Bản (Raw As-Is / SD1 Zero Information Loss) vs Chuẩn Hóa (Harmonization / SD2 & SD3)

> [!CAUTION]
> **QUY TẮC CỐT LÕI (ZERO INFORMATION LOSS - SD1)**:
> Tại Tầng Cào Thô (Raw Crawl Tier):
> - **TUYỆT ĐỐI KHÔNG can thiệp kiểu dữ liệu quá sớm**: Không tự ý xóa thẻ HTML, không ép văn bản thành danh sách dòng sạch (`requirements_list: list[str]`), không ép mức lương `"Thoả thuận"` thành số `null`.
> - **Bắt buộc lưu 100% trường dữ liệu và thẻ tags**: Giữ nguyên toàn văn khối HTML (`description_html`, `requirements_html`, `benefits_html`), giữ nguyên chuỗi mức lương gốc (`salary_raw`), giữ trọn vẹn phân cấp nhóm thẻ (`tag_groups: dict[str, list[str]]`).

#### 1. Quy chuẩn Trích xuất Tầng Thô (Raw Tier Payload)
```python
raw_payload = {
    "title": title_raw,
    "company_name": company_raw,
    "salary_raw": salary_raw,
    "header_list_info": {"Địa điểm": "...", "Kinh nghiệm": "...", "Hạn nộp": "..."},
    "tag_groups": {"Yêu cầu:": [...], "Chuyên môn:": [...]},
    "description_html": str(soup.select_one(".job-description")),
    "description_raw": soup.select_one(".job-description").get_text(separator="\n", strip=True),
    "requirements_html": str(soup.select_one(".job-requirements")),
    "requirements_raw": soup.select_one(".job-requirements").get_text(separator="\n", strip=True),
    "benefits_html": str(soup.select_one(".job-benefits")),
    "benefits_raw": soup.select_one(".job-benefits").get_text(separator="\n", strip=True),
    "address_and_time_raw": {...},
    "general_info_raw": {...},
    "company_details_raw": {...}
}
```

#### 2. Quy chuẩn Tầng Chuẩn Hóa (Data Harmonization Tier - SD2/SD3)
*Chỉ thực hiện ở pipeline xử lý Staging/Curated, KHÔNG áp dụng đè lên file snapshot cào thô:*
- Dùng `parse_salary_detail(salary_raw, title)` để bóc tách `JobSalary` (min, max, currency, is_negotiable).
- Dùng `classify_job_tags()` để chia 3 nhóm thẻ (`skills`, `requirements`, `benefits`).
- Dùng `text_to_clean_lines()` nếu cần danh sách bullet sạch phục vụ trích xuất NLP/LLM.

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
