# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ (RAW CRAWL INVENTORY)

> **Người thực hiện:** Tài  
> **Nguồn phụ trách:** CareerViet (`careerviet.vn`)  
> **Nhánh Git:** `crawls/careerviet` (HEAD = `f977ffb`, + uncommitted: A1 comment, C3 `--phase sync`, C1 push script)  
> **Ngày lập báo cáo:** 2026-10-16  
> **Tổng số URL đã phát hiện (ledger):** **1029** (`c1=611`, `c37_digital_mkt=281`, `keyword:developer=92`, `c61=45`), **100 % PENDING**  
> **Tổng số envelope raw (Phase 2 default):** **0** — **CHỜ ONLINE lượt 1**  
> **Envelope cục bộ tham khảo:** 20 file trong `data/careerviet/_dryrun/raw/2026-10-16/` (từ dry-run cũ của Tài, **không** nằm trong `DEFAULT_RAW_DIR` của crawler)  
> **Đường dẫn Local:** `data/careerviet/raw/<YYYY-MM-DD>/<job_id>_v<version>.json`  
> **Đường dẫn MinIO (đích):** `s3://vn-it-jobs/raw/careerviet/<YYYY-MM-DD>/<job_id>_v<version>.json` (đẩy bằng `scripts/push_raw_to_minio.py`, xem §5)  
> **Ledger MinIO:** `s3://vn-it-jobs/url_ledger/careerviet/` (`--phase sync`, xem docs/crawl/careerviet.md §13.1)

---

## 1. Danh Sách 100 % Trường Dữ Liệu Gốc Đã Thu Thập (Field Inventory)

Envelope CareerViet có **2 tầng**: `metadata` (8 khóa) và `raw_payload` (8 khóa CSS selector). **Raw As-Is**: không tách bullet, không chuẩn hoá, không parse lương.

### 1.1. `metadata` (8 khóa — xác thực bằng `build_raw_envelope`, `crawler.py`)

| STT | Key (`metadata.*`) | Kiểu | Tần suất dự kiến (%) | % Null dự kiến | Ví dụ (lấy từ `crawlers/sources/careerviet/samples/35C81470_v1.json`) | Ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `job_id` | String | 100 % | 0 % | `"35C81470"` | ID hex 8 ký tự trích từ URL (`extract_job_id`). |
| 2 | `source` | String | 100 % | 0 % | `"careerviet"` | Tên nguồn (hardcode trong crawler). |
| 3 | `source_url` | String (URL) | 100 % | 0 % | `"https://careerviet.vn/vi/tim-viec-lam/urgent-site-solution-..."` | URL chi tiết tin (canonical). |
| 4 | `scraped_at` | String (ISO-8601 UTC) | 100 % | 0 % | `"2026-10-16T13:05:09.222100+00:00"` | Thời điểm cào (timezone-aware). |
| 5 | `scraper_version` | String | 100 % | 0 % | `"1.0.0-raw-envelope"` | Phiên bản schema envelope (bất biến toàn cycle). |
| 6 | `version` | String (int-as-str) | 100 % | 0 % | `"1"` | Version CDC, `curr_ver + 1` nếu `content_hash` đổi. |
| 7 | `content_hash` | String (SHA-256, 64 hex) | 100 % | 0 % | `"485187ae5defb72da82cca8167a75b1cdca5f64384bd35f14e641a39f6dd..."` | Text hash của `.job-detail-page` (đã decompose script/style/iframe/noscript/svg). Repost detection + version bump. |
| 8 | `source_category` | String | 100 % | 0 % | `"keyword:developer"` (khác: `"c1"`, `"c37_digital_mkt"`, `"c61"`) | Bucket URL-Discovery. **KHÔNG** dùng làm nhãn IT (xem §8.1 docs crawl). |

### 1.2. `raw_payload` (8 khóa — selector CSS gốc, giữ nguyên cây DOM)

| STT | Key (`raw_payload.*`) | Kiểu | Tần suất dự kiến (%) | % Null dự kiến | Ví dụ (3 samples) | Ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `title` | String | kỳ vọng 100 % | CHỜ ONLINE | `"[URGENT] Site Solution Engineer"` (35C81470) · `"Nhân Viên IT (Tiếng Trung, làm tại Quảng Ninh)"` (35C833DD) · `"Transmission Engineer"` (35C87378) | Tiêu đề tin, selector `h1.title`. |
| 2 | `job-company-name` | String | kỳ vọng 100 % | CHỜ ONLINE | `"CÔNG TY TNHH CÔNG NGHỆ HUAWEI VIỆT NAM"` · `"Headhunter HRchannels Group"` · `"CÔNG TY TNHH CÔNG NGHỆ HUAWEI VIỆT NAM"` | Tên nhà tuyển dụng, selector `a.job-company-name`. |
| 3 | `detail-box` | List[dict] (mỗi dict ≈ 1 khối `div.detail-box`) | kỳ vọng 100 % | CHỜ ONLINE | độ dài **9–10** ở cả 3 mẫu | Toàn văn 4 khối `div.detail-box` (Mô tả / Yêu cầu / Quyền lợi / Thông tin khác) — **không** tách bullet, **không** parse JSON con. |
| 4 | `detail-row` | List[dict] (mỗi dict ≈ 1 hàng `div.detail-row`) | kỳ vọng 100 % | CHỜ ONLINE | **6** (35C81470) · **5** (35C833DD) · **6** (35C87378) | Bảng thông tin rút gọn (Kinh nghiệm / Bằng cấp / Số lượng / Hạn nộp / Địa điểm / …). **Biến thể 5 vs 6** → dẫn tới 4 tổ hợp layout (§8.5 docs crawl). |
| 5 | `job-tags` | List[String] | **46.7 %** ở 30 HTML cục bộ (14/30 = no-tag) | CHỜ ONLINE (dự kiến ~53 % null) | **[]** (35C81470 no-tag) · **2 tags** (35C833DD) · **4 tags** (35C87378) | Kỹ năng / phúc lợi, selector `.job-tags`. **Raw As-Is**: giữ nguyên thứ tự hiển thị, không dedup. |
| 6 | `map` | String | **100 %** ở 30/30 HTML (luôn có `.map`) | 0 % (dự kiến) | `"Hà Nội"` (35C81470) · `"Quảng Ninh, Hải Phòng, Hải Dương"` (35C833DD) · `"Hà Nội"` (35C87378) | Địa điểm làm việc, selector `.map`. **Raw As-Is**: giữ nguyên chuỗi ngăn `,`, chưa tách thành list. |
| 7 | `Ngành nghề` | List[String] | kỳ vọng 100 % (nhãn luôn hiển thị) | CHỜ ONLINE | độ dài **1** ở cả 3 mẫu (vd. `["CNTT - Phần mềm"]`) | Ngành nghề do NTD gán. **Đây là trường QUYẾT ĐỊNH IT** khi Data Integration (KHÔNG dùng `source_category`, xem §8.1 docs crawl). |
| 8 | `job-posting-schema` | dict (JSON-LD `schema.org/JobPosting`) | **100 %** ở 30/30 (3 script JSON-LD mỗi trang) | 0 % (dự kiến) | dict có **20–21** khóa con chuẩn hóa (`title`, `hiringOrganization`, `jobLocation`, `validThrough`, `baseSalary`, …) | JSON-LD nhúng trong `<script type="application/ld+json">`. **Raw As-Is**: giữ nguyên dict, KHÔNG trích `baseSalary` thành `salary_min/max` ở tầng raw (mục đó thuộc Data Integration). |

> **Ghi chú**: `%` dự kiến tính trên 3 mẫu (`samples/`) + 30 HTML (`data/raw/careerviet/html/`). Số liệu **thật** chỉ có sau khi chạy online lượt 1 → điền vào §1 sau khi `python -X utf8 scripts/careerviet_raw_stats.py` trả kết quả trên `data/careerviet/raw/`.

---

## 2. Thống Kê Cơ Chế CDC & Versioning

**CHỜ ONLINE** — Phase 2 chưa chạy trên `data/careerviet/raw/`. Sau lượt 1 (20 tin c37), điền:

| Loại | Bộ đếm | Định nghĩa (theo `_process_detail_record`) |
| :--- | :---: | :--- |
| NEW (Version 1) | CHỜ ONLINE | Ledger chưa từng có `content_hash` trùng → tạo envelope `_v1.json`, `latest_version=1`. |
| UPDATED (Version > 1) | CHỜ ONLINE | Cùng `url_hash`, `content_hash` **đổi** → envelope `_v<N>.json` (`N = curr + 1`), `latest_version += 1`. |
| ACTIVE (Unchanged) | CHỜ ONLINE | Cùng `url_hash`, `content_hash` **không đổi** → ghi đè `last_scraped_at`, KHÔNG bump version, KHÔNG sinh file mới. |
| REPOST (trùng cross-URL) | CHỜ ONLINE | `find_by_content_hash` có bản ghi DONE khác `url_hash` với cùng `content_hash` → tag `"repost"`, **không** sinh file mới. |
| CLOSED | CHỜ ONLINE | Job đã gỡ / 410 / 404 → status `CLOSED` trong ledger (không có envelope mới). |

**Bằng chứng công cụ** đã kiểm thử hồi quy: `tests/unit/test_careerviet_raw_envelope.py` (5 test atomic-write + version bump), `test_careerviet_samples.py` (13 test 3 cặp HTML/JSON offline), `test_careerviet_selection.py` (8 test selection + preview + non-5xx Safe Skip), `test_careerviet_block_detect.py` (13 test `_detect_block` + **Ngưỡng B — 5xx liên tiếp**, 5 test a–e).

---

## 3. Các Vấn Đề Kỹ Thuật Đã Gặp & Giải Pháp

### 3.1. Anti-bot / Rate limit

- **Delay + single-thread**: `DelayConfig(min_delay=2.0, max_delay=5.0)`, chỉ tính từ request #2 → **12–60 phút** cho 720 request online.
- **User-Agent rotation**: 7 UA pool (Chrome/Firefox/Safari/Edge) qua `HttpClient` (file dùng chung, không sửa).
- **429 / 403 (chặn tức thì)**: `_is_blocking(exc)` → `break` cả đợt, **giữ PENDING** (không `mark_failed`), dump HTML bằng chứng vào `data/careerviet/_blocked/<job_id>.html` (exclusive `open(...,"x")`, **không ghi đè**).
- **Captcha / trang vỏ rỗng**: `_detect_block(html)` 2 điều kiện (**thiếu `.job-detail-page`** VÀ **có tín hiệu tường minh** trong title/text/`.captcha-box`) sau `decompose(script,style,iframe,noscript,svg)` — sửa `test_detect_block_captcha_in_script` ở `f977ffb` (30/30 false-positive → 0/30).
- **Bão 5xx (Phương án B, `CONSECUTIVE_SERVER_ERROR_STOP=3`)**: 3 lỗi 5xx (500/502/503/504) **liên tiếp** → `break`, buffer cuối **giữ PENDING**; 5xx rời rạc → flush FAILED (Safe Skip).
- **Timeout / ConnectionError**: Safe Skip, mark_failed + continue (không tăng bộ đếm 5xx).
- **`http_client.py` tự retry ×3** (status_forcelist = 429/500/502/503/504, `backoff_factor=1.0`): 1 lần crawler thấy 5xx = **4 request** thực tế. Chuỗi 3-tin-5xx ≈ 12 request + 9–60 s backoff → **rủi ro leo thang** (docs crawl §8.3).

**Trạng thái hiện tại**: `data/careerviet/_blocked/` **không tồn tại** (0/0 false-block trên 30 HTML local).

### 3.2. Cấu trúc DOM bất thường

- **CareerViet CHỈ có 1 template DOM** (30/30 HTML cùng selector — xem docs/crawl/careerviet.md §8.5).
- **4 tổ hợp biến thể** (không phải layout khác): `detail-row` 5–6 × `job-tags` present/absent. Bảng 4 mẫu đại diện (`35C81470`, `35C848E9`, `35C833DD`, `35C87378`) nằm ở docs crawl §8.5.
- `div.detail-box` = 4 hằng số, `h1.title` = 1, `a.job-company-name` = 1, `.map` = 1, JSON-LD script = 3, iframe = 0, badge hot/vip = 0. **Như vậy**: không có "bài đăng layout khác biệt" để mô tả ở mục này.
- **Đề xuất miễn DoD 4 phần "3 layout"** (xem docs/crawl §8.5) — vì nguồn SSR đồng nhất, không tồn tại 3 layout.

### 3.3. Tốc độ cào

**CHỜ ONLINE** — dự tính trên `DelayConfig(2–5s)`:

- Trung bình **3.5 s/request** → **~17 phút/300 request** (17 phút cho 20 tin online + 3 UA rotation).
- Nếu có 1 lần 5xx storm (3 liên tiếp): crawler dừng → cộng thêm ~9–12 s backoff ×3 + ~6–15 s delay giữa các request = **~30–60 s**.
- Con số thực sẽ điền sau lượt online qua log `INFO` + stopwatch.

---

## 4. Giới Hạn Đã Biết (tóm tắt, chi tiết ở docs/crawl/careerviet.md §8)

- **HTTP status không lưu trong envelope** (`raise_on_status=True` làm request 4xx/5xx **không** tạo envelope) → bằng chứng 200 chỉ có trong log `INFO`.
- **`http_client.py` retry ×3** (file dùng chung) → hệ quả §3.1.
- **c37 là bucket hỗn hợp IT + không-IT** (281 URL c37 được nap **CÓ CHỦ ĐÍCH** qua `--include-c37`, commit `1470de0`). **Integration** dùng `raw_payload["Ngành nghề"]` để lọc IT, **không** dùng `metadata.source_category`.
- **Không có `salary_min` / `salary_max` số học ở tầng raw** → EDA số học (ngoại lai) thuộc tầng Data Integration (xem `reports/careerviet_eda.md`).

---

## 5. Lưu Trữ MinIO (C4)

### 5.1. Cấu trúc đích (`s3://vn-it-jobs/`)

```
raw/
  careerviet/
    <YYYY-MM-DD>/
      <job_id>_v<version>.json      # push_raw_to_minio.py
url_ledger/
  careerviet/
    catalog_master.json             # UrlLedger.sync_to_minio()
    manifests/manifest_<date>.jsonl
    category_by_job_id.json
```

### 5.2. Thứ tự lệnh (sau khi được duyệt)

> **Máy Tài KHÔNG có Docker** → MinIO chạy bằng **AIStor** (file thực thi `minio.exe`). `<DATA_DIR>` và `<DUONG_DAN_LICENSE>` là **bí mật cá nhân**, đặt **ngoài repo**, **KHÔNG commit**, **KHÔNG dán** vào docs/log/commit (agent **không** đọc hay in). `docker compose` / `scripts/start_minio.sh` **chỉ** dùng trên máy khác có Docker.
>
> **Đường dẫn repo chứa dấu cách** (`d:\ĐH\Năm 3\Học kỳ 1\Khai thác dữ liệu\crawl data\VN-IT-Job-Mining`) → mọi `cd` và tham số `--local-dir`/`--license` **phải bọc nháy kép**.

```powershell
# (0) Di chuyen den repo (boc nhay vi duong dan co dau cach):
cd "d:\ĐH\Năm 3\Học kỳ 1\Khai thác dữ liệu\crawl data\VN-IT-Job-Mining"

# (1) Start MinIO AIStor (Tai chay tay; agent KHONG goi, KHONG ket noi that):
minio.exe server <DATA_DIR> --console-address ":9001" --license <DUONG_DAN_LICENSE>
curl.exe http://localhost:9000/minio/health/live   # HTTP 200 -> san sang

# (2) Đồng bộ ledger (không gọi mạng ngoài trường)
python -X utf8 -m crawlers.sources.careerviet.crawler --phase sync

# (3) Dry-run đẩy raw envelope (kiểm tra key mapping, không cần boto3)
python -X utf8 scripts/push_raw_to_minio.py `
  --source careerviet --local-dir data/careerviet `
  --prefix raw/careerviet --dry-run --verbose

# (4) Upload thật (idempotent, head_object trước put)
python -X utf8 scripts/push_raw_to_minio.py `
  --source careerviet --local-dir data/careerviet `
  --prefix raw/careerviet --verify-sha
```

**Phương án phụ** (máy khác có Docker): Linux/macOS `bash scripts/start_minio.sh`; Windows PowerShell `docker compose -f docker-compose.minio.yml up -d`. `docker-compose.minio.yml` vẫn giữ trong repo làm tham chiếu.

### 5.3. An toàn

- **Idempotent**: mặc định `--no-clobber` → `SKIPPED_EXISTS` khi key đã tồn tại (qua `head_object`).
- **Bí mật** (`MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`) đọc từ env, **không bao giờ in** raw value; `--verbose` chỉ in dạng mask (`mini***dmin`).
- **License AIStor là bí mật cá nhân**: file `.json` cấp cho máy Tài, **đặt ngoài repo** (ví dụ `D:\secrets\aistor-license.json`), **KHÔNG commit**, **KHÔNG dán** đường dẫn hay nội dung vào docs / log / issue / commit message. Agent **không** đọc, **không** in.
- **Không có Docker trên máy Tài**: mọi lệnh ở §5.2 dùng `minio.exe server ... --license ...`; `docker-compose.minio.yml` và `scripts/start_minio.sh` chỉ còn là **phương án phụ** cho máy khác có Docker.
- **Chỉ 4 biến môi trường được phép dùng**: `MINIO_ENDPOINT`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_BUCKET` (khớp `scripts/setup_minio.py:18-21` và `crawlers/common/url_ledger.py:318-321`). **KHÔNG** tự đặt tên mới (`MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_REGION`).
- **Đường dẫn repo có dấu cách**: `cd "d:\ĐH\Năm 3\Học kỳ 1\Khai thác dữ liệu\crawl data\VN-IT-Job-Mining"` phải bọc nháy kép; PowerShell ≥ 7 nên `$env:MINIO_ROOT_PASSWORD = Read-Host -AsSecureString "..."` thay vì đặt plain-text trong script.
- **Lệch docs/code**: docs/02 §3.3 ghi `catalog_master.parquet`; `crawlers/common/url_ledger.py` ghi **`.json`** (converter parquet **chưa có**, thuộc file dùng chung → chỉ ghi nhận tại đây, **KHÔNG sửa** ở turn này).

---

**Kết luận**: Field inventory **đã điền đủ 16/16** (8 metadata + 8 raw_payload) với ví dụ thật từ `samples/` + 30 HTML local. CDC counts + % null thực đo + tốc độ: **CHỜ ONLINE lượt 1**. DoD 4 đề xuất miễn (phần "3 layout") — evidence §8.5 docs crawl. Storage MinIO đã thiết kế + script + doc §13.
