# 📋 Bảng Chuẩn Đầu Ra Chấm Điểm (Submission Scoring Rubric) & Báo Cáo Thẩm Định Nhánh

> **Dự án**: VN-IT-Job-Mining — Khai phá Dữ liệu Tuyển dụng IT Việt Nam  
> **Căn cứ tài liệu**: [`TASKS.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/TASKS.md), [`docs/02_crawling_architecture_guide.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/02_crawling_architecture_guide.md), Skill `collection-submission`  
> **Nhánh kiểm toán**: Toàn bộ 6 nhánh feature (`origin/feature/*`, `origin/crawler-glints`, `origin/tai_eda`)  
> **Người thẩm định**: Lead Data Architect & Antigravity Pair-Programming  
> **Ngày ban hành**: 19/10/2026

---

## PHẦN 1: KHUNG THANG ĐIỂM CHUẨN ĐẦU RA 100 ĐIỂM (DEFINITION OF DONE - DOD)

Thang điểm được xây dựng chuẩn mực dựa trên 7 tiêu chí nghiệm thu bắt buộc (DoD) trong tài liệu dự án, kèm điểm thưởng (Bonus) và điểm trừ kỷ luật (Penalty).

### 1.1. Bảng Trọng Số 7 Tiêu Chí Cốt Lõi (100 Điểm)

| STT | Tiêu chí DoD | Trọng số | Chi tiết cách tính điểm | Phương pháp kiểm định |
| :---: | :--- | :---: | :--- | :--- |
| **TC1** | **Kiến trúc Two-Phase Crawler** | **20 điểm** | • **10đ**: Có hàm `discover_urls()` duyệt phân trang/danh mục không giới hạn thời gian và lưu danh sách vào URL Ledger (`catalog_master.json` / `manifests`).<br>• **10đ**: Có hàm `crawl_details()` đọc từ Ledger, bóc tách dữ liệu chi tiết và cập nhật trạng thái. | Kiểm tra AST mã nguồn: tìm kiếm hàm `discover_urls` và `crawl_details` hoặc phương thức tương đương gọi `UrlLedger`. |
| **TC2** | **Safe Skip & Chịu Lỗi An Toàn** | **10 điểm** | • **5đ**: Bọc khối `try...except` quanh từng item/URL riêng lẻ.<br>• **5đ**: Khi gặp lỗi mạng (404, 500, Timeout), ghi log cảnh báo và `continue` sang bài kế tiếp, tuyệt đối không làm crash toàn bộ tiến trình cào. | Chạy thử nghiệm trên URL lỗi hoặc kiểm tra luồng xử lý ngoại lệ trong vòng lặp cào. |
| **TC3** | **Quản Lý Vòng Đời & Re-crawl 21 Ngày** | **10 điểm** | • **5đ**: Cập nhật trạng thái bài đăng (`PENDING`, `DONE`, `FAILED`).<br>• **5đ**: Có logic lọc thời gian `last_scraped_at <= now() - 21 days` để chỉ cào lại các bài viết đã đủ tuổi $\ge 21$ ngày. | Kiểm tra logic so sánh `datetime` / `timedelta(days=21)` trong mã nguồn crawler. |
| **TC4** | **Bộ Mẫu Thử Nghiệm Đa Định Dạng (Samples)** | **20 điểm** | • **7đ**: Tối thiểu 3 file `.html` thô (hoặc web snapshot) trong `crawlers/sources/<source>/samples/`.<br>• **7đ**: Tối thiểu 3 file `.json` tương ứng, tuân thủ đúng Envelope Schema v1, JSON parse hợp lệ.<br>• **3đ**: Đa dạng layout (tin tiêu chuẩn, tin Hot/VIP, tin lương thỏa thuận/ngoại tệ).<br>• **3đ**: Có file `samples/README.md` ghi chú URL gốc và selector mapping. | Kiểm tra thư mục `crawlers/sources/<source>/samples/`, phân tích cú pháp JSON và nội dung file. |
| **TC5** | **Đồng Bộ Lakehouse Đa Tầng (MinIO & Cloudflare R2)** | **10 điểm** | • **5đ**: Mã nguồn có module hoặc script tích hợp lưu trữ đẩy lên MinIO Lakehouse.<br>• **5đ**: Dữ liệu URL Ledger và Raw Snapshots được xác nhận tồn tại trên MinIO bucket `vn-it-jobs` hoặc Cloudflare R2. | Kiểm tra import/sử dụng `minio_storage.py` hoặc script đồng bộ `sync_cloud_lakehouse.py`. |
| **TC6** | **Tài Liệu Phân Tích Kiến Trúc Web** | **15 điểm** | • **5đ**: Tồn tại file `docs/crawl/<source>.md`.<br>• **5đ**: Độ dài $> 500$ bytes, có cấu trúc rõ ràng.<br>• **5đ**: Có phân tích kỹ thuật thực chất: cơ chế render (SSR/SPA/API), vượt WAF/chống bot, container selector để băm HTML Clean Hash. | Đọc và đánh giá nội dung tài liệu kỹ thuật. |
| **TC7** | **Bộ 2 Báo Cáo Chất Lượng Dữ Liệu** | **15 điểm** | • **8đ**: Báo cáo kiểm kê trường dữ liệu `reports/<source>_inventory.md` tuân thủ mẫu `templates/raw_crawl_inventory_template.md`.<br>• **7đ**: Báo cáo phân tích EDA sơ bộ `reports/<source>_eda.md` tuân thủ mẫu `templates/preliminary_eda_template.md`. | Kiểm tra file tồn tại trong `reports/` và kiểm tra đối soát với template chuẩn. |
| **TỔNG**| **ĐIỂM TIÊU CHUẨN CƠ BẢN** | **100 điểm** | **Mức đạt chuẩn nghiệm thu (Pass): $\ge 70$ điểm** | |

---

### 1.2. Thang Điểm Thưởng (Bonus) & Điểm Trừ (Penalty)

| Loại | Điểm | Điều kiện áp dụng |
| :---: | :---: | :--- |
| **BONUS** | **+5 điểm** | Kế thừa trực tiếp `BaseCrawler` từ `crawlers/base/base_crawler.py`, tuân thủ đúng giao thức `fetch_items()` / `parse_item()`. |
| **BONUS** | **+5 điểm** | Viết Unit Test chuyên biệt trong `tests/unit/test_<source>_crawler.py` đạt 100% Passed. |
| **BONUS** | **+10 điểm** | Đóng góp pipeline nâng cao cho toàn hệ thống (EDA, tiền xử lý preClean, trực quan hóa notebooks, tài liệu Excalidraw). |
| **PENALTY** | **-10 điểm** | Commit trực tiếp file dữ liệu lớn ($> 1$ MB hoặc $> 50,000$ dòng) vào git index thay vì đưa vào Lakehouse/Cloud. |
| **PENALTY** | **-5 điểm** | Sử dụng thư viện cồng kềnh đã bị cấm/deprecated (ví dụ: Selenium) đối với các website hỗ trợ HTTP SSR hoặc API. |
| **PENALTY** | **-5 điểm** | Commit file rác, file tạm hệ thống hoặc thư mục cá nhân (`.qoder/`, `__pycache__/`, `.DS_Store`, v.v.). |

---

## PHẦN 2: BẢNG TỔNG HỢP ĐIỂM THẨM ĐỊNH TỪNG THÀNH VIÊN

*(Đánh giá trên mã nguồn mới nhất tại các nhánh feature độc lập)*

| Thành viên | Nguồn phụ trách | TC1 (20) | TC2 (10) | TC3 (10) | TC4 (20) | TC5 (10) | TC6 (15) | TC7 (15) | Bonus | Penalty | Tổng điểm | Kết quả DoD |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Thuận** *(Leader)* | **TopCV** | 20 | 10 | 10 | 20 | 10 | 15 | 15 | +5 | -5 | **100 / 100** | 🟢 **ĐẠT (PASS)** — *Giữ nguyên, không sửa* |
| **Sơn** | **TopDev** | 0 | 5 | 0 | 0 | 0 | 15 | 0 | 0 | -10 *(data 3MB)* | **10 / 100** | ❌ **CHƯA ĐẠT** — *Cần sửa ở Chặng 2* |
| **Phúc** | **Vieclam24h** | 0 | 5 | 0 | 0 | 0 | 0 | 0 | +5 *(Base)* | -5 *(Selenium)* | **5 / 100** | ❌ **CHƯA ĐẠT** — *Cần sửa ở Chặng 2* |
| **Phát** | **ITViec** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | -5 *(.qoder rác)* | **-5 / 100** | ❌ **CHƯA ĐẠT** — *Chờ Phát nộp, tạm không sửa* |
| **Khoa** | **VietnamWorks**| 0 | 5 | 0 | 0 | 0 | 15 | 0 | +5 *(Base)* | -10 *(data 9MB)*| **15 / 100** | ❌ **CHƯA ĐẠT** — *Cần sửa ở Chặng 2* |
| **Tài** | **CareerViet** | 0 | 5 | 0 | 0 | 0 | 15 | 0 | +15 *(EDA+Base)* | 0 | **35 / 100** | ❌ **CHƯA ĐẠT** — *Cần sửa ở Chặng 2* |
| **Duy** | **Glints & JobsGO**| 0 | 5 | 0 | 0 | 0 | 0 | 0 | +5 *(Base)* | 0 | **10 / 100** | ❌ **CHƯA ĐẠT** — *Cần sửa ở Chặng 2* |

> [!NOTE]
> **Quy định phạm vi can thiệp kỹ thuật trong Chặng 2:**
> - **TopCV (Thuận)**: Đã đạt chuẩn tuyệt đối 100/100, có đủ bộ samples đa định dạng (3 HTML + 3 JSON), Two-Phase và báo cáo $\rightarrow$ **Không cần sửa đổi**.
> - **ITViec (Phát)**: Nhánh cá nhân chưa hoàn thiện đẩy lên $\rightarrow$ **Chỉ ghi nhận điểm thẩm định, tạm thời chưa sửa mã nguồn ở Chặng 2** để bạn Phát tiếp tục hoàn thiện trên nhánh của mình.
> - **5 nguồn cần chuẩn hóa tập trung**: TopDev, Vieclam24h, VietnamWorks, CareerViet, Glints & JobsGO.

---

## PHẦN 3: ĐÁNH GIÁ CHI TIẾT TỪNG THÀNH VIÊN & HƯỚNG DẪN KHẮC PHỤC KÈM CODE

---

### 1. 🟡 SƠN — Nguồn: `TopDev` (Nhánh: `origin/feature/topdev-son`)

#### A. Điều đã làm được (Strengths)
1. Bóc tách trực tiếp hệ thống REST API v2 của TopDev (`https://api.topdev.vn/td/v2/jobs`) rất chuyên nghiệp.
2. Cào được đa dạng 6 danh mục nghề nghiệp IT (`JOB_CATEGORY_IDS = (1, 14, 27, 33, 50, 61)`).
3. Đã viết tài liệu phân tích kỹ thuật rất chi tiết tại [`docs/crawl/topdev.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawl/topdev.md).
4. Áp dụng chuẩn làm sạch HTML bullet qua `BeautifulSoup` và ghi file nguyên tử (`Atomic Write`).

#### B. Điều chưa làm & Thiếu sót nghiêm trọng (Gaps)
1. **Chưa kế thừa `BaseCrawler`:** Lớp `TopDevCrawler` được viết độc lập, không tuân thủ chuẩn pipeline của dự án.
2. **Chưa phân tách Two-Phase:** Toàn bộ quá trình quét danh mục và lấy chi tiết bị gộp vào một hàm `crawl()` duy nhất; không có `discover_urls()` và `crawl_details()`.
3. **Chưa có URL Ledger:** Không tạo `catalog_master.json` và file nhật ký `manifest_YYYY-MM-DD.jsonl`.
4. **Chưa có cơ chế Re-crawl 21 ngày:** Không quản lý trạng thái `PENDING` / `DONE` và không kiểm tra tuổi thọ tin.
5. **Thư mục mẫu rỗng:** `crawlers/sources/topdev/samples/` chỉ có file `.gitkeep`.
6. **Lỗi kỷ luật commit data lớn:** Đã commit trực tiếp file `batch_001.json` (3.13 MB, 64,948 dòng) vào git tracking.
7. **Thiếu 2 báo cáo:** Không có `reports/topdev_inventory.md` và `reports/topdev_eda.md`.

#### C. Hướng dẫn khắc phục & Code Snippet mẫu

**Bước 1:** Loại bỏ ngay file data lớn khỏi git index:
```bash
git rm --cached crawlers/sources/topdev/batch_001.json
echo "crawlers/sources/topdev/*.json" >> .gitignore
git commit -m "fix(git): remove large batch_001.json from tracking"
```

**Bước 2:** Tái cấu trúc lớp crawler kế thừa `BaseCrawler` và tách biệt 2 Pha:

```python
# crawlers/sources/topdev/crawler.py
from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.url_ledger import UrlLedger
from crawlers.common.schema import JobRecord
import logging

log = logging.getLogger("topdev.crawler")

class TopDevCrawler(BaseCrawler):
    source_name = "topdev"
    crawler_version = "1.0.0"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ledger = UrlLedger(source="topdev")

    def discover_urls(self) -> list[str]:
        """Pha 1: Quét danh mục API TopDev, lấy toàn bộ Job IDs ghi vào URL Ledger."""
        new_urls = []
        for cat_id in JOB_CATEGORY_IDS:
            page = 1
            while True:
                resp = self._get_json(LISTING_URL, {"category_ids": cat_id, "page": page})
                jobs = resp.get("data", [])
                if not jobs:
                    break
                for job in jobs:
                    job_url = job.get("detail_url") or f"https://topdev.vn/jobs/{job.get('id')}"
                    # Ghi nhận vào sổ cái URL Ledger
                    if self.ledger.add_url(job_url, preliminary_title=job.get("title")):
                        new_urls.append(job_url)
                page += 1
        self.ledger.save_manifest()
        return new_urls

    def crawl_details(self, url: str) -> JobRecord | None:
        """Pha 2: Bóc tách chi tiết tin từ URL Ledger, bọc Safe Skip an toàn."""
        try:
            job_id = self._extract_id_from_url(url)
            payload = self._fetch_detail(job_id)
            record = self.parse_item(payload)
            self.ledger.mark_done(url, content_hash=record.metadata.content_hash)
            return record
        except Exception as exc:
            log.warning(f"Safe Skip URL lỗi {url}: {exc}")
            self.ledger.mark_failed(url, reason=str(exc))
            return None
```

---

### 2. 🔴 PHÚC — Nguồn: `Vieclam24h` (Nhánh: `origin/feature/crawler-vieclam24h`)

#### A. Điều đã làm được (Strengths)
1. Đã kế thừa đúng chuẩn `BaseCrawler` và tuân thủ Envelope Schema v1.
2. Xây dựng logic chuẩn hóa lương, loại bỏ trùng lặp và làm sạch text rất cẩn thận.
3. Có cơ chế atomic write và hỗ trợ checkpoint.

#### B. Điều chưa làm & Thiếu sót nghiêm trọng (Gaps)
1. **Lỗi kiến trúc nặng — Dùng Selenium:** Vieclam24h sử dụng Next.js SSR hoàn toàn có thể bóc tách qua HTTP nhanh gấp 30 lần. Selenium gây chậm, tốn RAM và crash trên môi trường Docker Linux không có GUI.
2. **Chưa phân tách Two-Phase:** Dồn toàn bộ việc tìm kiếm qua ô search React và duyệt DOM vào `fetch_items()`.
3. **Chưa có URL Ledger & Re-crawl 21 ngày:** Không quản lý sổ cái URL và không kiểm tra thời gian cào lại.
4. **Thiếu toàn bộ bộ hồ sơ nghiệm thu:** Không có samples (thư mục rỗng), thiếu `docs/crawl/vieclam24h.md`, thiếu 2 báo cáo `reports/vieclam24h_inventory.md` và `_eda.md`.

#### C. Hướng dẫn khắc phục & Code Snippet mẫu

**Loại bỏ hoàn toàn Selenium — Bóc tách thẻ `<script id="__NEXT_DATA__">`:**

```python
# crawlers/sources/vieclam24h/crawler.py
import json
import httpx
from bs4 import BeautifulSoup
from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.url_ledger import UrlLedger

class ViecLam24hCrawler(BaseCrawler):
    source_name = "vieclam24h"
    crawler_version = "2.0.0"

    def discover_urls(self) -> list[str]:
        """Pha 1: Quét danh mục IT qua SSR Next.js sạch sẽ không dùng Selenium."""
        discovered = []
        for cat in ["tim-viec-lam-it-phan-mem-c10001", "tim-viec-lam-it-phan-cung-mang-c10002"]:
            url = f"https://vieclam24h.vn/{cat}?page=1"
            resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            next_data = soup.find("script", id="__NEXT_DATA__")
            if next_data:
                payload = json.loads(next_data.string)
                job_list = payload["props"]["pageProps"]["initialState"]["jobs"]["list"]
                for j in job_list:
                    link = f"https://vieclam24h.vn/{j['slug']}-id{j['id']}.html"
                    self.ledger.add_url(link, preliminary_title=j.get("title"))
                    discovered.append(link)
        self.ledger.save_manifest()
        return discovered

    def crawl_details(self, url: str):
        """Pha 2: Tải HTML chi tiết, parse JSON-LD hoặc __NEXT_DATA__ với Safe Skip."""
        try:
            resp = httpx.get(url, timeout=10.0)
            soup = BeautifulSoup(resp.text, "html.parser")
            data_script = soup.find("script", id="__NEXT_DATA__")
            job_data = json.loads(data_script.string)["props"]["pageProps"]["jobDetail"]
            record = self.parse_item(job_data)
            self.ledger.mark_done(url)
            return record
        except Exception as e:
            log.warning(f"Safe Skip Vieclam24h {url}: {e}")
            self.ledger.mark_failed(url)
            return None
```

---

### 3. 🔴 PHÁT — Nguồn: `ITViec` (Nhánh: `origin/feature/itviec-crawler`)

#### A. Điều đã làm được (Strengths)
1. Nhận diện được các vấn đề kỹ thuật của ITViec (Cloudflare, JSON-LD, 3 reasons to join us) trong file ghi chú.
2. Có lưu 1 file HTML probe ban đầu (`probe_listing.html`).

#### B. Điều chưa làm & Thiếu sót nghiêm trọng (Gaps)
1. **CHƯA CÓ MÃ NGUỒN CRAWLER:** File `crawlers/sources/itviec/crawler.py` hoàn toàn rỗng (**0 lines**). Phát chưa viết bất kỳ dòng mã thực thi nào.
2. **Không có bộ samples:** Chỉ có 1 file probe lẻ loi, thiếu 2 file HTML và toàn bộ 3 file JSON tương ứng.
3. **Commit thư mục rác:** Commit thư mục `.qoder/` với 28 file markdown không liên quan vào repo.
4. **Thiếu 100% hồ sơ nghiệm thu:** Không có `docs/crawl/itviec.md`, không có 2 báo cáo `reports/`.

#### C. Hướng dẫn khắc phục & Code Snippet mẫu

**Bước 1:** Dọn dẹp thư mục rác `.qoder/`:
```bash
git rm -r .qoder/
echo ".qoder/" >> .gitignore
git commit -m "chore: remove qoder cache from repository"
```

**Bước 2:** Viết mới toàn diện mã nguồn crawler ITViec:

```python
# crawlers/sources/itviec/crawler.py
import json
import httpx
from bs4 import BeautifulSoup
from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.schema import JobRecord, JobMetadata, JobRaw, JobSalary, JobTags
from crawlers.common.url_ledger import UrlLedger

class ItviecCrawler(BaseCrawler):
    source_name = "itviec"
    crawler_version = "1.0.0"

    def discover_urls(self) -> list[str]:
        """Pha 1: Quét 4 thị trường trọng điểm của ITViec (HCM, Hà Nội, Đà Nẵng, Remote)."""
        cities = ["ho-chi-minh-hcm", "ha-noi", "da-nang", "remote"]
        discovered = []
        for city in cities:
            page = 1
            while page <= 10:
                url = f"https://itviec.com/it-jobs/{city}?page={page}"
                # Header chống nén lỗi brotli và vượt Cloudflare nhẹ
                headers = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip, deflate"}
                resp = httpx.get(url, headers=headers)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("div.job-card")
                if not cards:
                    break
                for card in cards:
                    link_tag = card.select_one("h3.title a")
                    if link_tag and link_tag.get("href"):
                        full_url = "https://itviec.com" + link_tag["href"]
                        self.ledger.add_url(full_url, preliminary_title=link_tag.text.strip())
                        discovered.append(full_url)
                page += 1
        self.ledger.save_manifest()
        return discovered

    def crawl_details(self, url: str) -> JobRecord | None:
        """Pha 2: Bóc tách JSON-LD JobPosting và khối '3 reasons to join us'."""
        try:
            resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            json_ld = soup.find("script", type="application/ld+json")
            if not json_ld:
                raise ValueError("Không tìm thấy JSON-LD JobPosting")
            data = json.loads(json_ld.string)
            
            # Trích xuất 3 reasons to join us đặc thù của ITViec
            reasons = [li.text.strip() for li in soup.select("div.reasons-to-join-us ul li")]
            return self._build_record(url, data, reasons)
        except Exception as e:
            log.warning(f"Safe Skip ITViec {url}: {e}")
            self.ledger.mark_failed(url)
            return None
```

---

### 4. 🟡 KHOA — Nguồn: `VietnamWorks` (Nhánh: `origin/feature/vietnamworks-raw-batch`)

#### A. Điều đã làm được (Strengths)
1. Tận dụng rất tốt API tìm kiếm chính thức: `https://ms.vietnamworks.com/job-search/v1.0/search`.
2. Có bộ lọc từ khóa IT toàn diện (hơn 25 từ khóa chuyên ngành).
3. Có tài liệu phân tích kỹ thuật rất tốt tại [`docs/crawl/vietnamworks.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawl/vietnamworks.md).
4. Đã thu thập được tập dữ liệu raw thực tế cực lớn.

#### B. Điều chưa làm & Thiếu sót nghiêm trọng (Gaps)
1. **Chưa phân tách Two-Phase:** `fetch_items()` thực hiện đồng thời vừa search hits vừa xuất bản ghi, không tách biệt khâu URL Discovery và Detail Extraction.
2. **Chưa có URL Ledger & Re-crawl 21 ngày:** Không lưu vào `url_ledger/manifests/`.
3. **Lỗi commit dữ liệu quá lớn:** Commit file `data/vietnamworks/raw/2026-10-16/raw_batch.json` nặng **9.3 MB** (hơn 226,000 dòng JSON) vào git repo.
4. **Bộ samples chưa chuẩn:** Thư mục `samples/` chỉ có `.gitkeep`, thiếu 3 cặp file mẫu chuẩn tên (`sample_standard_job`, `sample_hot_vip_job`, `sample_negotiable_salary`).
5. **Thiếu 2 báo cáo:** Chưa nộp `reports/vietnamworks_inventory.md` và `_eda.md`.

#### C. Hướng dẫn khắc phục & Code Snippet mẫu

**Bước 1:** Dỡ bỏ file dữ liệu lớn khỏi git:
```bash
git rm --cached data/vietnamworks/raw/2026-10-16/raw_batch.json
echo "data/vietnamworks/raw/" >> .gitignore
git commit -m "fix(git): remove 9.3MB raw batch from git tracking"
```

**Bước 2:** Bổ sung hàm Two-Phase và kết nối URL Ledger:

```python
# crawlers/sources/vietnamworks/crawler.py
class VietnamWorksCrawler(BaseCrawler):
    source_name = "vietnamworks"
    crawler_version = "1.0.0"

    def discover_urls(self) -> list[str]:
        """Pha 1: Quét Algolia Search API lấy danh sách Job IDs & URLs đẩy vào Ledger."""
        discovered = []
        for query in IT_QUERIES:
            for page in range(10): # Vét cạn danh mục
                payload = {"query": query, "page": page, "hitsPerPage": 50}
                resp = httpx.post(API_URL, json=payload).json()
                hits = resp.get("data", [])
                if not hits:
                    break
                for hit in hits:
                    job_url = f"https://www.vietnamworks.com/{hit['jobUrl']}-{hit['jobId']}-jv"
                    if self.ledger.add_url(job_url, preliminary_title=hit.get("jobTitle")):
                        discovered.append(job_url)
        self.ledger.save_manifest()
        return discovered

    def crawl_details(self, url: str) -> JobRecord | None:
        """Pha 2: Đọc từ Ledger, gọi API lấy full payload kèm Safe Skip."""
        try:
            job_id = self._extract_job_id(url)
            # Lấy thông tin chi tiết và bóc tách
            record = self._fetch_and_parse(job_id)
            self.ledger.mark_done(url)
            return record
        except Exception as e:
            log.warning(f"Safe Skip VietnamWorks {url}: {e}")
            self.ledger.mark_failed(url)
            return None
```

---

### 5. 🟡 TÀI — Nguồn: `CareerViet` (Nhánh: `origin/tai_eda`)

#### A. Điều đã làm được (Strengths)
1. Đã kế thừa đúng chuẩn `BaseCrawler` và tuân thủ Envelope Schema v1.
2. **Đóng góp xuất sắc về EDA:** Xây dựng toàn bộ pipeline phân tích dữ liệu chuyên nghiệp (`crawlers/preprocessing/eda/`, `preClean/`), 2 Jupyter Notebooks, hệ thống biểu đồ và tài liệu kiến trúc Excalidraw.
3. Đã có tài liệu phân tích kỹ thuật tại [`docs/crawl/careerviet.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawl/careerviet.md).

#### B. Điều chưa làm & Thiếu sót nghiêm trọng (Gaps)
1. **Crawler CareerViet chưa phân tách Two-Phase:** Quá trình cào SSR và bóc tách dồn vào 1 luồng trong `fetch_items()`.
2. **Chưa có URL Ledger & Re-crawl 21 ngày.**
3. **Thư mục mẫu rỗng:** `crawlers/sources/careerviet/samples/` chỉ có file `.gitkeep`.
4. **Thiếu 2 báo cáo:** Chưa có `reports/careerviet_inventory.md` và `reports/careerviet_eda.md`.

#### C. Hướng dẫn khắc phục & Code Snippet mẫu

```python
# crawlers/sources/careerviet/crawler.py
class CareerVietCrawler(BaseCrawler):
    source_name = "careerviet"
    crawler_version = "1.0.0"

    def discover_urls(self) -> list[str]:
        """Pha 1: Quét danh mục CNTT lấy toàn bộ URL bài đăng."""
        discovered = []
        for page in range(1, self.max_pages + 1):
            url = f"{BASE_URL}{CATEGORY_PATH}?page={page}"
            resp = self.http_client.get(url)
            soup = BeautifulSoup(resp.text, "html.parser")
            job_links = soup.select("div.job-item a.job-title")
            if not job_links:
                break
            for a in job_links:
                link = urljoin(BASE_URL, a.get("href"))
                if self.ledger.add_url(link, preliminary_title=a.text.strip()):
                    discovered.append(link)
        self.ledger.save_manifest()
        return discovered

    def crawl_details(self, url: str) -> JobRecord | None:
        """Pha 2: Bóc tách SSR HTML chi tiết, tính Clean Container Hash trên div.job-detail."""
        try:
            resp = self.http_client.get(url)
            record = self.parse_item_from_html(resp.text, url)
            self.ledger.mark_done(url, content_hash=record.metadata.content_hash)
            return record
        except Exception as e:
            log.warning(f"Safe Skip CareerViet {url}: {e}")
            self.ledger.mark_failed(url)
            return None
```

---

### 6. 🔴 DUY — Nguồn: `Glints & JobsGO` (Nhánh: `origin/crawler-glints`)

#### A. Điều đã làm được (Strengths)
1. Khai thác chuẩn GraphQL API (`searchJobsV3`) của Glints.
2. Trích xuất rất tốt thẻ JSON-LD `JobPosting` nhúng trong HTML chi tiết.
3. Xử lý chuẩn hóa số học chống lỗi scientific notation trong mức lương.

#### B. Điều chưa làm & Thiếu sót nghiêm trọng (Gaps)
1. **THIẾU HOÀN TOÀN SÀN JOBSGO:** Duy được giao 2 sàn (Glints & JobsGO) nhưng trong nhánh chỉ có Glints; chưa viết bất kỳ dòng code nào cho JobsGO.
2. **Chưa phân tách Two-Phase & URL Ledger:** Chưa có hàm `discover_urls()` và quản lý catalog URL.
3. **Chưa có cơ chế Re-crawl 21 ngày.**
4. **Samples rỗng:** Không có 3 cặp file HTML + JSON cho Glints và JobsGO.
5. **Thiếu toàn bộ tài liệu:** Không có `docs/crawl/glints_jobsgo.md` và 2 báo cáo `reports/`.

#### C. Hướng dẫn khắc phục & Code Snippet mẫu

**Viết mới crawler cho JobsGO (`crawlers/sources/jobsgo/crawler.py`):**

```python
# crawlers/sources/jobsgo/crawler.py
import httpx
from bs4 import BeautifulSoup
from crawlers.base.base_crawler import BaseCrawler
from crawlers.common.url_ledger import UrlLedger

class JobsGoCrawler(BaseCrawler):
    source_name = "jobsgo"
    crawler_version = "1.0.0"

    def discover_urls(self) -> list[str]:
        """Pha 1: Quét danh mục việc làm CNTT JobsGO."""
        discovered = []
        page = 1
        while page <= 15:
            url = f"https://jobsgo.vn/viec-lam-it.html?page={page}"
            resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                break
            soup = BeautifulSoup(resp.text, "html.parser")
            job_items = soup.select("div.h-job-item h3 a")
            if not job_items:
                break
            for item in job_items:
                link = item.get("href")
                self.ledger.add_url(link, preliminary_title=item.text.strip())
                discovered.append(link)
            page += 1
        self.ledger.save_manifest()
        return discovered

    def crawl_details(self, url: str):
        """Pha 2: Bóc tách chi tiết SSR JobsGO, Safe Skip bắt lỗi."""
        try:
            resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"})
            record = self._parse_jobsgo_dom(resp.text, url)
            self.ledger.mark_done(url)
            return record
        except Exception as e:
            log.warning(f"Safe Skip JobsGO {url}: {e}")
            self.ledger.mark_failed(url)
            return None
```

---

## PHẦN 4: HƯỚNG DẪN TỰ ĐỘNG CHẤM ĐIỂM BẰNG SCRIPT

Để chấm điểm tự động cho bất kỳ sàn nào hoặc toàn bộ dự án, chạy lệnh:

```bash
# Chấm điểm 1 sàn cụ thể
python3 .agents/skills/collection-submission/scripts/verify_submission.py --source topdev

# Chấm điểm toàn bộ 7 sàn tuyển dụng
python3 .agents/skills/collection-submission/scripts/verify_submission.py --all
```
