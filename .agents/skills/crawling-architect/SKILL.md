---
name: crawling-architect
description: >-
  Chuyên gia kiến trúc hệ thống thu thập dữ liệu tuyển dụng chuẩn Modern Data Stack.
  Chuyên sâu về: cào Raw As-Is (Zero Information Loss, cào 100% trường đặc thù của từng web),
  lưu trữ MinIO Object Storage theo phân tầng Data Lakehouse, cơ chế Change Data Capture (CDC)
  & Content Hashing versioning (giải quyết triệt để bài toán sửa đổi tin tuyển dụng),
  vượt anti-bot, xoay tua User-Agent, exponential backoff và polite crawling.
---

# Crawling Architect Skill

Kỹ năng này trang bị cho AI Agent năng lực thiết kế, đánh giá, kiểm thử và xây dựng các crawler đạt chuẩn công nghiệp, tuân thủ nguyên lý Modern ELT (Extract & Load Raw As-Is) cho dự án VN-IT-Job-Mining.

---

## 1. Nguyên Tắc Cốt Tử: Zero Information Loss (Cào Raw As-Is)

Khi xây dựng crawler cho bất kỳ nguồn nào (TopCV, TopDev, ITViec, VietnamWorks, CareerViet, Vieclam24h, Glints, JobsGO), Agent **tuyệt đối không được**:
- Tự ý format hoặc ép kiểu dữ liệu ở bước cào (Ví dụ: parse lương thành số, drop các chuỗi text "Thỏa thuận").
- Bỏ qua các trường dữ liệu mà bản thân cảm thấy "không cần thiết" (Ví dụ: ngày hết hạn, badge phúc lợi, tên người liên hệ, class name đặc trưng của web).
- Cố tình nhồi nhét vào một schema đích quá sớm.

### Quy định đầu ra của Crawler:
Mỗi bài đăng tuyển dụng cào về phải là một file JSON theo mẫu Envelope:
```json
{
  "metadata": {
    "job_id": "<mã định danh duy nhất của sàn>",
    "source": "<tên sàn, viết thường: topcv, itviec, ...>",
    "source_url": "<canonical url của bài đăng>",
    "scraped_at": "<ISO8601 UTC timestamp>",
    "scraper_version": "2.0.0",
    "version": 1,
    "content_hash": "<SHA256 hex string>",
    "http_status": 200
  },
  "raw_payload": {
    "<tên_trường_gốc_hoặc_selector_1>": "giá trị gốc",
    "<tên_trường_gốc_hoặc_selector_2>": ["giá trị 1", "giá trị 2"],
    "<raw_html_blocks>": "..."
  }
}
```

---

## 2. Kiến Trúc Lưu Trữ MinIO Object Storage

Agent cấu hình và tương tác với MinIO thông qua S3-compatible client (`boto3` trong Python hoặc `mc` CLI):

### Phân cấp thư mục trong bucket `vn-it-jobs`:
- `raw/<source>/<YYYY-MM-DD>/<job_id>_v<version>.json`: Chứa bản ghi thô nguyên bản của từng bài đăng.
- `catalog/job_catalog_<source>.parquet`: Chứa bảng trạng thái vòng đời tin (CDC Catalog).

### Mẫu kết nối Python chuẩn MinIO:
```python
import boto3
import os
from botocore.client import Config

def get_minio_client():
    endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
    access_key = os.getenv("MINIO_ROOT_USER", "minioadmin")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1"
    )
```

---

## 3. Cơ Chế Change Data Capture (CDC) & Content Hashing

Giải quyết triệt để bài toán: **"Nếu nhà tuyển dụng cập nhật/chỉnh sửa tin tuyển dụng thì sao?"**

### 3.1. Hàm băm nội dung ổn định (`calculate_content_hash`)
```python
import hashlib
import json

def calculate_content_hash(raw_payload: dict) -> str:
    # Trích xuất các trường nội dung cốt lõi phản ánh bản chất công việc
    content_dict = {
        "title": str(raw_payload.get("title") or raw_payload.get("box-header-job__title") or "").strip(),
        "salary": str(raw_payload.get("salary") or raw_payload.get("box-header-job__salary--title") or "").strip(),
        "experience": str(raw_payload.get("experience") or raw_payload.get("job-detail__box--experience") or "").strip(),
        "desc": str(raw_payload.get("description") or raw_payload.get("job-detail__box--description_html") or "").strip(),
        "reqs": str(raw_payload.get("requirements") or raw_payload.get("job-detail__box--requirements_html") or "").strip(),
        "tags": sorted([str(t) for t in (raw_payload.get("badge_tags") or raw_payload.get("skills") or [])])
    }
    normalized_str = json.dumps(content_dict, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(normalized_str.encode("utf-8")).hexdigest()
```

### 3.2. Logic cập nhật Catalog & Versioning
Khi quét qua một tin tuyển dụng:
1. Tính `new_hash = calculate_content_hash(raw_payload)`.
2. Tra cứu `job_id` trong Catalog:
   - **Chưa có:** Tạo record mới $\rightarrow$ `version = 1`, `status = "NEW"`, `first_seen_at = now()`, `last_seen_at = now()`. Lưu file `<job_id>_v1.json` vào MinIO `/raw/`.
   - **Đã có:**
     - Nếu `new_hash == current_content_hash`: Nội dung không đổi $\rightarrow$ Chỉ cập nhật `last_seen_at = now()`, `status = "ACTIVE"`. Không tạo snapshot mới.
     - Nếu `new_hash != current_content_hash`: **Nhà tuyển dụng đã sửa tin!** $\rightarrow$ `version = latest_version + 1`, `status = "UPDATED"`, `updated_at = now()`. Lưu snapshot mới `<job_id>_v<version>.json` vào MinIO.
3. Cuối chu kỳ cào: Các tin có `last_seen_at < (now - 7 days)` được cập nhật `status = "CLOSED"`.

---

## 4. Kỹ Thuật Chống Chặn & Độ Tin Cậy Cao (Anti-Bot & Fault-Tolerance)

Agent áp dụng các biện pháp sau trong mọi crawler:
1. **Header chuẩn trình duyệt:** Sử dụng User-Agent thực, chấp nhận `accept-language: vi-VN,vi;q=0.9,en-US;q=0.8`.
2. **Polite Request Jitter:** Sleep ngẫu nhiên `1.5 - 3.5s` giữa các lượt tải trang chi tiết.
3. **Phát hiện Cloudflare:** Nếu phản hồi có chuỗi `"cf-browser-verification"` hoặc status code 403/503 $\rightarrow$ Chuyển hướng sang Playwright Stealth hoặc báo lỗi cảnh báo rõ ràng.
4. **Không làm chết crawler khi gặp 1 bài viết lỗi:** Mọi thao tác parse chi tiết phải bọc trong `try...except`, ghi log lỗi và tiếp tục bài tiếp theo.
