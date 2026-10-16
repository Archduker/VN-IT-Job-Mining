---
name: crawling-architect
description: >-
  Chuyên gia kiến trúc hệ thống thu thập dữ liệu tuyển dụng chuẩn Modern Data Stack.
  Chuyên sâu về: cào Raw As-Is (Zero Information Loss, cào 100% trường đặc thù của từng web),
  kiến trúc Two-Phase Decoupled Crawler (URL Discovery không giới hạn thời gian & Detail Extraction),
  MinIO URL Ledger Manifests (JSONL/Parquet), Clean Container HTML Hashing, chu kỳ Re-crawl 21 ngày,
  cơ chế Safe Skip bắt lỗi an toàn và điều phối tự động qua Apache Airflow.
---

# Crawling Architect Skill

Kỹ năng này trang bị cho AI Agent năng lực thiết kế, đánh giá, kiểm thử và xây dựng các crawler đạt chuẩn công nghiệp, tuân thủ nguyên lý Modern ELT (Extract & Load Raw As-Is) cho dự án VN-IT-Job-Mining.

---

## 1. Đầu Vào Tiêu Chuẩn: File HTML Thô & Quy Trình 5 Bước Phân Tích DOM

Mọi bài toán xây dựng parser cho bất kỳ website tuyển dụng nào đều bắt đầu từ **1 file HTML thô đại diện (`sample.html`)** do người dùng hoặc crawler tải về.

### Quy trình tương tác giữa Thành viên & Agent:
1. **Bước 1 (Tiếp nhận đầu vào):** Người dùng cung cấp đường dẫn file HTML thô đại diện (ví dụ: `crawlers/sources/<tenweb>/samples/sample_standard_job.html`).
2. **Bước 2 (Chạy công cụ phân tích DOM tự động):**
   ```bash
   .venv/bin/python .agents/skills/crawling-architect/scripts/analyze_html_dom.py --html <path_to_html>
   ```
3. **Bước 3 (Dò tìm trường dữ liệu - Field Discovery):** Agent rà soát cây DOM và cấu trúc JSON-LD để xác định danh sách tất cả các trường có thể bóc tách:
   - Tiêu đề công việc (`title`)
   - Tên công ty (`company`)
   - Mức lương thô nguyên bản (`salary_raw`)
   - Hạn nộp hồ sơ (`deadline_raw`)
   - Kinh nghiệm & cấp bậc (`experience`, `level`)
   - Thẻ kỹ năng / tags (`badge_tags`)
   - Khối mô tả công việc, yêu cầu, quyền lợi (`description_html`, `requirements_html`, `benefits_html`)
4. **Bước 4 (Chỉ định Container Selector băm Hash):** Xác định thẻ cha bao bọc nội dung tuyển dụng (ví dụ: `div.job-detail`, `article`, `#job-detail`) để băm Clean Container HTML Hash, loại bỏ script/ads/views gây nhảy hash oan.
5. **Bước 5 (Sinh Parser Python):** Xuất mã nguồn parser Python bóc tách đầy đủ 100% các trường trên, không format sớm, lưu trữ đúng định dạng Envelope chuẩn.

---

## 2. Nguyên Tắc Cốt Tử: Zero Information Loss (Cào Raw As-Is)

Khi xây dựng crawler cho bất kỳ nguồn nào (TopCV, TopDev, ITViec, VietnamWorks, CareerViet, Vieclam24h, Glints, JobsGO), Agent **tuyệt đối không được**:
- Tự ý format hoặc ép kiểu dữ liệu ở bước cào (Ví dụ: parse lương thành số, drop các chuỗi text "Thỏa thuận").
- Bỏ qua các trường dữ liệu mà bản thân cảm thấy "không cần thiết" (Ví dụ: ngày hết hạn, badge phúc lợi, tên người liên hệ, class name đặc trưng của web).
- Cố tình nhồi nhét vào một schema đích quá sớm.

### Quy định đầu ra của Crawler (Raw Envelope):
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

## 3. Kiến Trúc Thu Thập 2 Pha Độc Lập (Two-Phase Decoupled Pipeline)

### Phase 1: URL Discovery (`discover_urls`)
- Quét qua tất cả các trang danh mục, tìm kiếm hoặc phân trang API.
- **Không giới hạn thời gian**, cào đến khi vét sạch toàn bộ link.
- Chuẩn hóa canonical URL (loại bỏ token tracking `utm_*`, `ref`).
- Lưu danh sách link tìm thấy vào file Manifest trên MinIO:
  `minio://vn-it-jobs/url_ledger/<source>/manifests/manifest_<YYYY-MM-DD>.jsonl`.

### Phase 2: Detail Extraction (`crawl_details`)
- Đọc danh sách URL từ MinIO `catalog_master.parquet`.
- Lọc các link thỏa mãn điều kiện cần cào:
  1. `status == "PENDING"` (chưa từng cào bao giờ).
  2. `status == "DONE"` VÀ `last_scraped_at <= now() - 21 days` (đã cào quá 21 ngày, cần kiểm tra lại độ tươi).
- **Cơ chế Safe Skip:** Bọc `try...except` quanh từng link. Nếu 1 URL bị 404, 500 hoặc timeout $\rightarrow$ Ghi log `status = "FAILED"`, tự động skip và chuyển ngay sang link tiếp theo, không ngắt quãng chương trình.

---

## 4. Thuật Toán Băm Khối Nội Dung (Clean Container HTML Hashing)

Để vừa không cần viết code parse chi tiết từng trường trước khi kiểm tra thay đổi, vừa tránh bị "nhảy hash oan" do thời gian server, lượt xem động hay mã CSRF:

```python
import hashlib
import re
from bs4 import BeautifulSoup

def calculate_html_hash(html_content: str, container_selector: str = "body") -> str:
    """
    Băm HTML khối nội dung chính, tự động loại bỏ các thành phần rác động:
    - Thẻ <script>, <style>, <iframe>, <noscript>, <svg>
    - Số lượt xem (views), timestamp hiển thị
    - Thuộc tính ngẫu nhiên (CSRF token, nonce)
    """
    soup = BeautifulSoup(html_content, "html.parser")
    target = soup.select_one(container_selector) or soup.body or soup
    
    # Xóa sạch các thẻ động gây nhảy hash oan
    for tag in target(["script", "style", "iframe", "noscript", "svg"]):
        tag.decompose()
        
    # Chuẩn hóa khoảng trắng
    clean_text = re.sub(r"\s+", " ", target.get_text(separator=" ", strip=True))
    return hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
```

---

## 5. Quản Lý Vòng Đời Trạng Thái & Xử Lý Repost

### Bảng trạng thái chuẩn:
- `PENDING`: Link mới ghi nhận, chờ cào chi tiết.
- `DONE`: Đã cào chi tiết thành công và lưu file vào MinIO.
- `RECHECK_DUE`: Đã cào $\ge 21$ ngày, đến hạn re-crawl.
- `FAILED`: Lỗi cào (404, timeout, bot block).
- `CLOSED`: Tin đã bị gỡ bỏ hoặc thông báo hết hạn.

### Xử lý kịch bản Repost (URL đổi, Nội dung giữ nguyên):
Khi cào xong một URL mới, tính `content_hash`:
- Nếu `content_hash` trùng khớp với một bản ghi đã có trong Catalog $\rightarrow$ Đây là hành vi Repost/Đổi link.
- Không tạo file snapshot mới làm phình to MinIO.
- Ghi nhận `repost_of_url_hash = <id_cũ>`, cập nhật `last_seen_at = now()`.

---

## 6. Danh Sách Kiểm Tra Khi Nộp Code Cào (Checklist)

Agent kiểm tra các điều kiện tiên quyết trước khi nghiệm thu crawler của từng thành viên:
- [ ] Đã phân tích file HTML mẫu đại diện bằng `analyze_html_dom.py`.
- [ ] Code tách bạch 2 hàm: `discover_urls()` và `crawl_details()`.
- [ ] Áp dụng đúng hàm `calculate_container_html_hash` với selector khối container chính của website.
- [ ] Trạng thái cào thành công lưu là `DONE`, chu kỳ re-crawl kiểm tra mốc 21 ngày.
- [ ] Có khối `try...except` bắt lỗi Safe Skip an toàn cho từng URL.
- [ ] Có đủ thư mục `samples/` chứa ít nhất 3 cặp file HTML thô đa định dạng + JSON tương ứng.
- [ ] Có file phân tích kiến trúc độc lập tại `docs/crawl/<tenweb>.md`.
