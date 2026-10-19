# BÁO CÁO KIỂM KÊ TRƯỜNG DỮ LIỆU THÔ (RAW CRAWL INVENTORY)

> **Người thực hiện:** Tài  
> **Nguồn phụ trách:** CareerViet (`careerviet.vn`)  
> **Nhánh Git:** `crawls/careerviet` (HEAD = `4701af8`)  
> **Ngày lập khung báo cáo:** 2026-10-16 · **Cập nhật số liệu:** 2026-10-18 (sau online)  
> **Tổng số URL đã phát hiện (ledger):** **1029** (`c1=611`, `c37_digital_mkt=281`, `keyword:developer=92`, `c61=45`), **DONE = 1029** (100 %), **PENDING = 0**, **FAILED = 0**, **RECHECK_DUE = 0**  
> **REPOST (nội dung trùng URL khác, không sinh envelope):** **11** record (1.07 % ledger)  
> **Tổng số envelope raw (Phase 2 default):** **1018** (`data/careerviet/raw/2026-10-16/`), tất cả `_v1.json` (chưa re-crawl 21 ngày)  
> **Thời gian crawl online thực đo:** 2026-10-16 17:09:58 UTC → 18:27:00 UTC (**4622 s = 77 phút**, TB **4.54 s/tin**)  
> **Envelope rác (bị `_detect_block` chặn):** **0** (`data/careerviet/_blocked/` = 0 file)  
> **Đối chiếu:** `1029 (ledger DONE) − 11 (repost) = 1018 (envelope)` ✓  
> **Envelope cục bộ tham khảo:** 20 file trong `data/careerviet/_dryrun/raw/2026-10-16/` (từ dry-run cũ của Tài, **không** nằm trong `DEFAULT_RAW_DIR` của crawler)  
> **Đường dẫn Local:** `data/careerviet/raw/<YYYY-MM-DD>/<job_id>_v<version>.json`  
> **Đường dẫn MinIO (đích):** `s3://vn-it-jobs/raw/careerviet/<YYYY-MM-DD>/<job_id>_v<version>.json` (đẩy bằng `scripts/push_raw_to_minio.py`, xem §5)  
> **Ledger MinIO:** `s3://vn-it-jobs/url_ledger/careerviet/` (`--phase sync`, xem docs/crawl/careerviet.md §13.1)

---

## 1. Danh Sách 100 % Trường Dữ Liệu Gốc Đã Thu Thập (Field Inventory)

Envelope CareerViet có **2 tầng**: `metadata` (8 khóa) và `raw_payload` (8 khóa CSS selector). **Raw As-Is**: không tách bullet, không chuẩn hoá, không parse lương.

### 1.1. `metadata` (8 khóa — xác thực bằng `build_raw_envelope`, `crawler.py`)

| STT | Key (`metadata.*`) | Kiểu | Tần suất thực đo (%) | % Null thực đo | Ví dụ (lấy từ `crawlers/sources/careerviet/samples/35C81470_v1.json`) | Ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `job_id` | String | 100 % | 0 % | `"35C81470"` | ID hex 8 ký tự trích từ URL (`extract_job_id`). |
| 2 | `source` | String | 100 % | 0 % | `"careerviet"` | Tên nguồn (hardcode trong crawler). |
| 3 | `source_url` | String (URL) | 100 % | 0 % | `"https://careerviet.vn/vi/tim-viec-lam/urgent-site-solution-..."` | URL chi tiết tin (canonical). |
| 4 | `scraped_at` | String (ISO-8601 UTC) | 100 % | 0 % | `"2026-10-16T13:05:09.222100+00:00"` | Thời điểm cào (timezone-aware). |
| 5 | `scraper_version` | String | 100 % | 0 % | `"1.0.0-raw-envelope"` | Phiên bản schema envelope (bất biến toàn cycle). |
| 6 | `version` | String (int-as-str) | 100 % | 0 % | `"1"` | Version CDC, `curr_ver + 1` nếu `content_hash` đổi. |
| 7 | `content_hash` | String (SHA-256, 64 hex) | 100 % | 0 % | `"485187ae5defb72da82cca8167a75b1cdca5f64384bd35f14e641a39f6dd..."` | Text hash của `.job-detail-page` (đã decompose script/style/iframe/noscript/svg). Repost detection + version bump. |
| 8 | `source_category` | String | 100 % | 0 % | `"keyword:developer"` (khác: `"c1"`, `"c37_digital_mkt"`, `"c61"`) | Bucket URL-Discovery. **KHÔNG** dùng làm nhãn IT (xem §8.1 docs crawl). |

### 1.2. `raw_payload` (8 khóa — selector CSS gốc, text phẳng nguyên văn)

| STT | Key (`raw_payload.*`) | Kiểu | Tần suất thực đo (%) | % Null thực đo | Ví dụ (3 samples) | Ý nghĩa nghiệp vụ |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | `title` | String | **98.23 %** (1000/1018) | **1.77 %** (18/1018) | `"[URGENT] Site Solution Engineer"` (35C81470) · `"Nhân Viên IT (Tiếng Trung, làm tại Quảng Ninh)"` (35C833DD) · `"Transmission Engineer"` (35C87378) | Tiêu đề tin, selector `h1.title`. |
| 2 | `job-company-name` | String | **98.33 %** (1001/1018) | **1.67 %** (17/1018) | `"CÔNG TY TNHH CÔNG NGHỆ HUAWEI VIỆT NAM"` · `"Headhunter HRchannels Group"` · `"CÔNG TY TNHH CÔNG NGHỆ HUAWEI VIỆT NAM"` | Tên nhà tuyển dụng, selector `a.job-company-name`. |
| 3 | `detail-box` | **List[String]** (mỗi phần tử = 1 dòng `<li>` nguyên văn) | **97.64 %** (994/1018) | **2.36 %** (24/1018) | độ dài **9–10** (`[]` ở 24 tin) — vd `"Lương Lương: 15 - 25 Triệu VND"`, `"Kinh nghiệm 2 - 6 Năm"` | **Hộp metadata** (Lương / Kinh nghiệm / Cấp bậc / Hình thức / Ngày cập nhật / Hết hạn nộp / Ngành nghề), selector `.detail-box li`. **KHÔNG phải nội dung mô tả** — JD nằm ở `detail-row`. Giữ nguyên văn, có trùng lặp 2 lần (render desktop + mobile). |
| 4 | `detail-row` | **Dict[String: String]** (mỗi key = heading section, value = text phẳng) | **99.90 %** (1017/1018) | **0.10 %** (1/1018) | số key **6** (35C81470) · **5** (35C833DD) · **6** (35C87378) | **NỘI DUNG CÔNG VIỆC**: `{"Mô tả Công việc": ..., "Yêu Cầu Công Việc": ..., "Phúc lợi": ..., "Thông tin khác": ..., "Gợi ý hồ sơ": ..., "Địa điểm làm việc": ...}`. Selector `.detail-row, .job-description`. **Biến thể 5 vs 6 key** → 4 tổ hợp layout (§8.5 docs crawl). |
| 5 | `job-tags` | List[String] | **79.96 %** (814/1018) | **20.04 %** (204/1018) | **[]** (35C81470 no-tag) · **2 tags** (35C833DD) · **4 tags** (35C87378) | Kỹ năng / phúc lợi, selector `.job-tags`. **Raw As-Is**: giữ nguyên thứ tự hiển thị, không dedup. **Ít hơn dự kiến** (ước ~46.7 % từ 14/30 HTML local). |
| 6 | `map` | String | **97.64 %** (994/1018) | **2.36 %** (24/1018) | `"Hà Nội"` (35C81470) · `"Quảng Ninh, Hải Phòng, Hải Dương"` (35C833DD) · `"Hà Nội"` (35C87378) | Địa điểm làm việc, selector `.map`. **Raw As-Is**: giữ nguyên chuỗi ngăn `,`, chưa tách thành list. **Khác dự kiến** (ước 0 %). |
| 7 | `Ngành nghề` | List[String] | **97.64 %** (994/1018) | **2.36 %** (24/1018) | độ dài **1** ở cả 3 mẫu (vd. `["CNTT - Phần mềm"]`) | Ngành nghề do NTD gán. **Đây là trường QUYẾT ĐỊNH IT** khi Data Integration (KHÔNG dùng `source_category`, xem §8.1 docs crawl). |
| 8 | `job-posting-schema` | dict (JSON-LD `schema.org/JobPosting`) | **100 %** (1018/1018) | **0 %** | dict có **20–21** khóa con chuẩn hóa (`title`, `hiringOrganization`, `jobLocation`, `validThrough`, `baseSalary`, …) | JSON-LD nhúng trong `<script type="application/ld+json">`. **Raw As-Is**: giữ nguyên dict, KHÔNG trích `baseSalary` thành `salary_min/max` ở tầng raw (mục đó thuộc Data Integration). |

> **Ghi chú**: % **thực đo** trên 1018 envelope online qua `python -X utf8 scripts/careerviet_report_fill.py` (khoá `null_rate_by_payload_key`) và `python -X utf8 scripts/careerviet_eda_charts.py`. Trước đây khung báo dùng % **dự kiến** từ 3 mẫu + 30 HTML local (`data/raw/careerviet/html/`); một số trường có độ lệch đáng kể:
>
> - `job-tags`: dự kiến **46.7 % null** (14/30 HTML local) → thực đo **20.04 % null** (204/1018). Các tin online crawl **có tag hơn hẳn** tập mẫu.
> - `map`: dự kiến **0 % null** (30/30 có) → thực đo **2.36 % null** (24/1018). Một số tin không ghi địa điểm.
> - `Ngành nghề`: dự kiến **0 % null** (nhãn luôn hiển thị) → thực đo **2.36 % null** (24/1018). **Trùng hợp đúng 24 tin** với `detail-box` rỗng và `map` rỗng → cùng một nhóm tin tối giản **không có block metadata**; hệ quả: **24 tin này không thể phân loại IT** bằng rule `Ngành nghề` (xem §3.4 báo cáo EDA).
> - `job-posting-schema`: **100 % đầy đủ** — SSR đồng nhất như dự kiến; khóa con `description` cũng **1018/1018** (không rỗng).

**Phân bố thật số phần tử / số key** (đo trực tiếp trên 1018 envelope):

| Khóa | Phân bố độ dài |
| :--- | :--- |
| `detail-box` (List) | `0` → **24**, `9` → **104**, `10` → **890** |
| `detail-row` (Dict) | `0` → **1**, `5` key → **279**, `6` key → **729**, `7` key → **9** |

**Tần suất từng heading trong `detail-row`** (1018 envelope) — evidence cho bước tách section ở Data Integration:

| Heading (`detail-row` key) | Số tin | % |
| :--- | :---: | :---: |
| `Phúc lợi` | 1017 | 99.90 % |
| `Yêu Cầu Công Việc` | 1017 | 99.90 % |
| `Thông tin khác` | 1017 | 99.90 % |
| `Gợi ý hồ sơ` | 1017 | 99.90 % |
| `Mô tả Công việc` | **1013** | **99.51 %** |
| `Địa điểm làm việc` | 728 | 71.51 % |
| `JOB TAGS / SKILLS:` | 16 | 1.57 % |
| `section_2` (fallback, heading rỗng) | 4 | 0.39 % |
| `Video Tuyển Dụng` | 3 | 0.29 % |

---

## 2. Thống Kê Cơ Chế CDC & Versioning

**Số thực đo** trên 1029 ledger record + 1018 envelope (`python -X utf8 scripts/careerviet_report_fill.py`, khoá `cdc_from_ledger`, **mutually exclusive**):

| Loại | Bộ đếm | Định nghĩa (theo `_process_detail_record`) |
| :--- | :---: | :--- |
| **NEW (Version 1)** | **1018** | Ledger chưa từng có `content_hash` trùng → tạo envelope `_v1.json`, `latest_version=1`. **Tất cả** 1018 envelope hiện tại đều **v1** (chưa re-crawl 21 ngày). |
| UPDATED (Version > 1) | **0** | Cùng `url_hash`, `content_hash` **đổi** → envelope `_v<N>.json` (`N = curr + 1`), `latest_version += 1`. **0** vì chưa tới chu kỳ re-crawl 21 ngày. |
| ACTIVE (Unchanged) | **0** | Cùng `url_hash`, `content_hash` **không đổi** → ghi đè `last_scraped_at`, KHÔNG bump version. **0** vì crawl một đợt, chưa có re-crawl. |
| **REPOST (trùng cross-URL)** | **11** | `find_by_content_hash` có bản ghi DONE khác `url_hash` với cùng `content_hash` → tag `"repost"`, **không** sinh file mới. **11/1029 = 1.07 %** — bằng chứng cơ chế repost hoạt động thật khi online. |
| CLOSED | **0** | Job đã gỡ / 410 / 404 → status `CLOSED` trong ledger (không có envelope mới). **0** vì crawl một đợt ngắn. |
| FAILED | **0** | Safe Skip (timeout, parse error, 5xx rời rạc). **0** → crawl **sạch 100 %**. |
| PENDING | **0** | Giữ PENDING sau 429/403 hoặc chuỗi 5xx cuối. **0** → không block, không bão 5xx. |
| **TỔNG LEDGER** | **1029** | `DONE=1029` (trong đó `repost_of_url_hash != null`: **11**), `PENDING=0`, `FAILED=0`, `RECHECK_DUE=0`. |

**Đối chiếu**: `1029 − 11 = 1018 envelope` ✓

**Bằng chứng công cụ** đã kiểm thử hồi quy: `tests/unit/test_careerviet_raw_envelope.py` (5 test atomic-write + version bump), `test_careerviet_samples.py` (13 test 3 cặp HTML/JSON offline), `test_careerviet_selection.py` (8 test selection + preview + non-5xx Safe Skip), `test_careerviet_block_detect.py` (13 test `_detect_block` + **Ngưỡng B — 5xx liên tiếp**, 5 test a–e), `test_careerviet_report_fill.py` (16 test **CDC mutually exclusive**, gồm `test_cdc_from_ledger_repost_not_double_counted`).

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

**Trạng thái sau online lượt 1** (2026-10-16 → 2026-10-17): `data/careerviet/_blocked/` **= 0 file**, `FAILED = 0`, `PENDING = 0` → **không gặp** 429/403/captcha/bão-5xx trong 1018 request online thực tế. `test_detect_block_captcha_in_script` (`f977ffb`) được xác nhận **giữ nguyên hiệu lực** khi chạy online (không false-positive, không false-negative).

### 3.2. Cấu trúc DOM bất thường

- **CareerViet CHỈ có 1 template DOM** (30/30 HTML cùng selector — xem docs/crawl/careerviet.md §8.5).
- **4 tổ hợp biến thể** (không phải layout khác): số **key của `detail-row`** 5–6 (thực đo: 279 tin 5 key, 729 tin 6 key, 9 tin 7 key) × `job-tags` present/absent (204 tin rỗng). Bảng 4 mẫu đại diện (`35C81470`, `35C848E9`, `35C833DD`, `35C87378`) nằm ở docs crawl §8.5.
- `div.detail-box` = 4 hằng số, `h1.title` = 1, `a.job-company-name` = 1, `.map` = 1, JSON-LD script = 3, iframe = 0, badge hot/vip = 0. **Như vậy**: không có "bài đăng layout khác biệt" để mô tả ở mục này.
- **Đề xuất miễn DoD 4 phần "3 layout"** (xem docs/crawl §8.5) — vì nguồn SSR đồng nhất, không tồn tại 3 layout.

### 3.3. Tốc độ cào

**Thực đo trên lượt online 2026-10-16 → 2026-10-17** (qua `metadata.scraped_at` của 1018 envelope):

- **Envelope đầu**: `2026-10-16T17:09:58.471588+00:00`.
- **Envelope cuối**: `2026-10-16T18:27:00.154857+00:00`.
- **Tổng thời gian crawl**: **4622 s = 77.0 phút**.
- **Trung bình giữa 2 envelope**: **4.54 s/tin** (khớp `DelayConfig(2.0–5.0 s)` trung bình 3.5 s + parse time 1.0 s).
- **Số lượng request thực tế**: ~1029 URL (1018 NEW + 11 REPOST) x 1 request = ~1029 HTTP GET, **không retry**, **không bão 5xx**.
- **Không có 5xx storm** nên `CONSECUTIVE_SERVER_ERROR_STOP=3` không kích hoạt trong lượt này.

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

**Kết luận**: Field inventory **đã điền đủ 16/16** (8 metadata + 8 raw_payload) với **% null thực đo trên 1018 envelope** (xem §1.2). CDC thực: **NEW=1018, UPDATED=0, ACTIVE=0, REPOST=11, CLOSED=0, FAILED=0, PENDING=0** (xem §2). Tốc độ thực: **77 phút / 1018 envelope / 4.54 s TB** (xem §3.3). DoD 4 đề xuất miễn (phần "3 layout") — evidence §8.5 docs crawl. Storage MinIO đã thiết kế + script + doc §13; `--phase sync` + `push_raw_to_minio.py` còn chờ `MINIO_*` env.
