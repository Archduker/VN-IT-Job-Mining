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

### Bước 3: Thu Thập Thô Nguyên Bản (DOM-Native Class Name & Partitioning / SD1)

> [!CAUTION]
> **QUY TẮC CỐT LÕI (ZERO INFORMATION LOSS - SD1)**:
> Tại Tầng Cào Thô (Raw Crawl Tier):
> 1. **Key trường = Chính xác CSS Class Name trong DOM**: Không tự đặt tên trường trừu tượng (`title`, `company`, `salary`), mà lấy trực tiếp tên class (`box-header-job__title`, `box-company-info`, `box-header-job__salary--title`, `job-tags`, `box-job-information-detail-item__text`).
> 2. **TUYỆT ĐỐI KHÔNG dùng hậu tố `__html` hay `_html`**: Không nhồi nhét mã HTML cồng kềnh; giá trị văn bản được lưu trực tiếp dưới key class text (`box-job-information-detail-item__text`) với ngắt dòng và bullet nguyên bản.
> 3. **Phân khối theo cây DOM ("Phân ra")**: Phân chia `raw_payload` theo các khối container cha (Header, Left Body, Right Body).

#### 1. Quy chuẩn Trích xuất Tầng Thô (Raw Tier Payload Theo Class Name)
```json
{
  "box-header-job": {
    "box-header-job__title": "Chuyên viên Tư vấn Đầu tư",
    "box-company-info": "Công ty cổ phần chứng khoán FPT",
    "box-header-job__salary--title": "Thoả thuận",
    "box-header-job-list-info": {
      "Địa điểm": "Hà Nội",
      "Kinh nghiệm": "Không yêu cầu",
      "Hạn ứng tuyển": "31/08/2016"
    },
    "box-group-button-apply": "Hết hạn ứng tuyểnXem việc làm liên quan",
    "box-header-job__warning-employer-data-protection": "..."
  },
  "job-detail__body-left": {
    "box-job-information-detail-item__overview": {
      "job-tags": {
        "Yêu cầu:": ["Không yêu cầu kinh nghiệm chuyên môn"]
      }
    },
    "box-job-information-detail-item__job-description": {
      "box-job-information-detail-item__text": "- Tìm kiếm và duy trì mối quan hệ với khách hàng;\n- Thực hiện các nghiệp vụ môi giới chứng khoán;\n- Tư vấn đầu tư cho khách hàng..."
    },
    "box-job-information-required-candidate": {
      "box-job-information-detail-item__text": "- Nam/Nữ tuổi từ 22;\n- Tốt nghiệp đại học khối kinh tế, tài chính..."
    },
    "box-job-information-benefit": {
      "box-job-information-detail-item__text": "- Nhân viên được lựa chọn sẽ có cơ hội làm việc trong môi trường năng động...\n- Tháng lương thứ 13..."
    },
    "box-job-information-address-and-time": {
      "box-job-information-address-and-time-list": {
        "Địa điểm làm việc": "Hà Nội",
        "Hạn ứng tuyển": "31/08/2016"
      }
    }
  },
  "job-detail__body-right": {
    "box-job-information-general-info": {
      "Cấp bậc": "Nhân viên",
      "Số lượng tuyển": "Không giới hạn",
      "Loại hình làm việc": "Toàn thời gian"
    },
    "box-company-info-detail": {
      "company-name-label": "Công ty cổ phần chứng khoán FPT",
      "Quy mô": "100-499 nhân viên",
      "Địa điểm": "Tòa Nhà 52 Lạc Long Quân, Tây Hồ, Hà Nội."
    }
  }
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

### Bước 5: Tích Hợp BaseCrawler, Cấu Trúc Lưu Trữ & Bảo Vệ Airflow
- Kế thừa `BaseCrawler`.
- **Cấu trúc lưu trữ chuẩn hóa**: Toàn bộ dữ liệu của nguồn phải lưu đúng trong `data/<source>/`:
  - `data/<source>/url_ledger/catalog_master.json` & `manifests/manifest_YYYY-MM-DD.jsonl`
  - `data/<source>/raw/YYYY-MM-DD/{job_id}_v{version}.json`
  - `data/<source>/samples/sample_standard_job.html` & `.json`
- **MinIO Lakehouse**: Đồng bộ qua `self.ledger.sync_to_minio()` lên `minio://vn-it-jobs/url_ledger/<source>/`. Người dùng xem trên Web Console UI: `http://localhost:9001` (User: `minioadmin` / Pass: `minioadmin`) hoặc CLI `python scripts/view_urls.py --source <source> [--minio]`.
- **Chống chặn bot**: Tích hợp `crawlers.common.anti_blocking` với `polite_sleep` (ngẫu nhiên 3.0s - 5.5s) và `human_like_interaction`.
- Đặt `save_html = False` làm giá trị mặc định để không lưu rác HTML.
- **Không bao giờ sửa đổi Airflow DAGs hay Operators** (`airflow/dags/`, `airflow/plugins/`).

