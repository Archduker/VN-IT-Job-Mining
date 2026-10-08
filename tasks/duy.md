# 📋 Bản Giao Việc Chi Tiết — Duy (Nguồn Mới: Glints Vietnam)

> **Dự án**: VN-IT-Job-Mining — Hệ thống Thu thập & Khai phá Dữ liệu Tuyển dụng IT Việt Nam  
> **Người thực hiện**: Duy (Thành viên mới tham gia dự án)  
> **Vai trò**: Crawler Developer — Phụ trách Xây dựng Nguồn Tuyển Dụng Mới: **Glints Vietnam** ([`https://glints.com/vn`](https://glints.com/vn))  
> **Ngày giao việc**: 2026-10-08  
> **Tài liệu gốc tham chiếu**: [`docs/crawler_api_analysis.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawler_api_analysis.md) | [`TASKS.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/TASKS.md)

---

## 🎯 1. Mục Tiêu & Công Việc Cần Làm

Chào mừng bạn Duy gia nhập nhóm! Để mở rộng độ phủ dữ liệu tuyển dụng IT tại Việt Nam, nhiệm vụ của bạn là **xây dựng một Crawler mới toanh từ đầu cho nền tảng Glints Vietnam** (`glints.com/vn`), tuân thủ chuẩn kiến trúc của dự án:

1. **Khảo sát Nguồn Glints**:
   - Glints là một trong những nền tảng tuyển dụng startup & tech phổ biến nhất Việt Nam hiện nay.
   - Glints cung cấp API phân trang tìm kiếm việc làm CNTT rất thân thiện (không bị Cloudflare chặn gắt như LinkedIn):
     * **Listing URL**: `https://glints.com/vn/opportunities/jobs/explore?country=VN&category=software-engineering`
     * **API Endpoint**: `https://glints.com/api/job-postings` (hoặc cào SSR Next.js JSON từ trang web).
2. **Xây dựng module Crawler chuẩn `BaseCrawler`**:
   - Tạo thư mục `crawlers/sources/glints/`.
   - Viết class `GlintsCrawler(BaseCrawler)` trong file `crawler.py`.
   - Viết tài liệu `README.md` hướng dẫn nguồn Glints.
3. **Bóc tách trường dữ liệu chuẩn xác**:
   - `id`: Mã định danh tin (`source_job_id`).
   - `title`: Tên chức danh công việc.
   - `company`: Tên công ty.
   - `salary`: Trích xuất rõ `salary_min`, `salary_max`, `salary_currency` (Glints thường có min/max rõ ràng).
   - `skills`: Danh sách tag kỹ năng.
   - `description_html` & `description_text`: Dọn sạch 100% thẻ HTML (`<p>`, `<span>`,...).
   - Định dạng xuống dòng: Đảm bảo các mục `AA,\nBB` được ngắt dòng sạch đẹp:
     ```text
     AA,
     BB
     ```
   - `posted_date_text`: Trích xuất ngày đăng (nếu có dạng "14 days left" thì tính lùi từ hạn nộp).
   - `language`: Tự động nhận diện bài đăng tiếng Việt (`"vi"`) hay tiếng Anh (`"en"`).
4. **Đầu ra**:
   - Xuất dữ liệu ra file mảng JSON: `data/glints/dt=YYYY-MM-DD/batch_001.json`.
5. **Tích hợp vào `run.py`**:
   - Thêm lựa chọn `--source glints` vào bộ điều phối tập trung [`run.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/run.py).

---

## 📂 2. File Sẽ Làm Việc

* **Thư mục tạo mới**: `crawlers/sources/glints/`
* **File crawler chính cần tạo**: [`crawlers/sources/glints/crawler.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/crawlers/sources/glints/crawler.py)
* **File tài liệu nguồn**: `crawlers/sources/glints/README.md`
* **File điều phối tập trung**: [`run.py`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/run.py) (khai báo thêm nguồn `glints`)
* **File test viết mới**: `tests/unit/test_glints_crawler.py`

---

## ⚙️ 3. Quy Trình Kỹ Thuật Bắt Buộc

Quy trình phát triển chuẩn 7 bước bắt buộc bạn phải tuân thủ:

```text
[BƯỚC 1] KÉO FILE HTML / GỌI API THỬ NGHIỆM TỪ GLINTS
   │     Dùng requests / curl tải về 1 bài đăng mẫu từ Glints để khảo sát cấu trúc.
   ▼
[BƯỚC 2] ĐỌC RA CÁC THÀNH PHẦN ĐƯỢC TRÍCH XUẤT
   │     Ghi chú rõ vị trí: title, company, salary_min, salary_max, skills, descriptions.
   ▼
[BƯỚC 3] SỬA CODE / XÂY DỰNG GlintsCrawler
   │     Kế thừa BaseCrawler, cài đặt 2 hàm bắt buộc:
   │     - fetch_items(): Lấy danh sách raw items từ Glints
   │     - parse_item(): Chuyển đổi item thành JobRecord chuẩn
   ▼
[BƯỚC 4] CHUẨN HÓA DỮ LIỆU
   │     Làm sạch HTML, chuẩn hóa ngắt dòng AA,\nBB, gán language: "vi"|"en".
   ▼
[BƯỚC 5] NẾU CÓ LỖI (Bị lỗi parse, thiếu trường, sót HTML)
   │     Mở lại file HTML/JSON thô, so sánh và fix bug.
   ▼
[BƯỚC 6] FIX & TỐI ƯU
   │     Chạy lặp lại cho đến khi cào thành công ít nhất 5 tin hoàn chỉnh không lỗi.
   ▼
[BƯỚC 7] RA ĐƯỢC BỘ JSON CHUẨN
         Sinh ra file batch_001.json là mảng JSON hợp lệ.
```

---

## 💻 4. Code Mẫu Khung Crawler Glints (Template Khởi Đầu Cho Bạn)

Bạn có thể dựa trên khung mã nguồn chuẩn sau để cài đặt:

```python
# -*- coding: utf-8 -*-
"""Crawler nguồn Glints Vietnam (https://glints.com/vn).

Owner: Duy (VN-IT-Job-Mining).
"""

from typing import Any, Dict, Generator, Optional
from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.http_client import HttpClient, DelayConfig
from crawlers.common.schema import JobRecord
from crawlers.common.utils import strip_html_tags, clean_text, detect_language

SOURCE = "glints"
CRAWLER_VERSION = "0.1.0"

class GlintsCrawler(BaseCrawler):
    source_name = SOURCE
    crawler_version = CRAWLER_VERSION

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.http_client = HttpClient(
            source=self.source_name,
            delay_config=DelayConfig(min_seconds=1.5, max_seconds=3.0),
        )

    def fetch_items(self) -> Generator[Dict[str, Any], None, None]:
        # TODO: Gọi endpoint API hoặc cào listing Glints
        pass

    def parse_item(self, item: Dict[str, Any]) -> Optional[JobRecord]:
        # TODO: Bóc tách trường, làm sạch HTML và trả về JobRecord.create(...)
        pass
```

---

## 📤 5. Output Kỳ Vọng & Tiêu Chuẩn Nghiệm Thu

1. **Lệnh chạy thử nghiệm hoàn chỉnh**:
   ```bash
   .venv/bin/python run.py --source glints --max-items 5 -v
   ```
2. **File đầu ra sinh ra**:
   `data/glints/dt=YYYY-MM-DD/batch_001.json`
3. **Mẫu bản ghi hợp lệ trong JSON**:
   ```json
   {
     "_meta": {
       "source": "glints",
       "source_job_id": "glints-fe-react-01",
       "url": "https://glints.com/vn/opportunities/jobs/frontend-react-developer",
       "dedup_key": "glints:glints-fe-react-01",
       "crawled_at": "2026-10-08T22:15:00Z",
       "batch_id": "2026-10-08_glints_001",
       "crawler_version": "0.1.0",
       "language": "en"
     },
     "raw": {
       "title": "Senior Frontend React Developer",
       "company": "Tech Innovations Vietnam",
       "description_html": "<p>We are seeking a talented Senior Frontend...</p>",
       "description_text": "We are seeking a talented Senior Frontend Developer.\nYou will collaborate with product designers and backend engineers.",
       "requirements_text": "3+ years experience with React.js and TypeScript,\nProficient in Redux and TailwindCSS,\nGood English communication.",
       "salary_text": "1,800 - 2,800 USD",
       "salary_min": 1800.0,
       "salary_max": 2800.0,
       "salary_currency": "USD",
       "location_text": "Ho Chi Minh City",
       "skills_text": "React, TypeScript, Redux, TailwindCSS",
       "posted_date_text": "2026-10-01"
     }
   }
   ```

---

## 🌿 6. Hướng Dẫn Git Workflow (Kéo Code, Tạo Nhánh & Push)

```bash
# 1. Kéo code mới nhất từ nhánh main
git checkout main
git pull origin main

# 2. Tạo nhánh làm việc cho nguồn Glints
git checkout -b feature/glints-crawler-duy

# 3. Code trong thư mục crawlers/sources/glints/ và run.py
# Chạy thử:
.venv/bin/python run.py --source glints --max-items 3 -v

# 4. Kiểm tra git status và commit
git status
git add crawlers/sources/glints/ run.py
git commit -m "feat(glints): implement glints crawler with json output and clean parser"

# 5. Đẩy nhánh lên GitHub
git push -u origin feature/glints-crawler-duy

# 6. Mở Pull Request vào main trên GitHub và nhờ @billtran review
```
