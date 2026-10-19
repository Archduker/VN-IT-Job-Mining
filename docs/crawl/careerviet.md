# Hướng Dẫn Kỹ Thuật Cào CareerViet (CareerViet Crawl Guide)

> **Nhánh**: `crawls/careerviet`
> **Nguồn**: CareerViet — `https://careerviet.vn` (SSR HTML, không API công khai)
> **Crawler**: `crawlers/sources/careerviet/crawler.py` — `CareerVietCrawler`
> **`CRAWLER_VERSION`**: `0.5.0` (hằng số trong `crawler.py`)
> **Trạng thái**: Phase 1 **HOÀN THÀNH** (ledger 1.029 URL, 100% PENDING). Phase 2 **CHƯA chạy online**.

Tài liệu này chỉ mô tả **hành vi thật của code** tại HEAD `f977ffb` (nhánh `crawls/careerviet`).
Mọi con số đều lấy từ code / lệnh chạy thật trên máy Windows 25H2 + Python 3.12.9.

---

## 1. Kiến Trúc Hai Pha (Two-Phase Decoupled Crawler)

Hệ thống tách **URL Discovery** (Pha 1) và **Detail Extraction** (Pha 2) thành hai vòng đời
độc lập, nối với nhau qua **UrlLedger** (MinIO-style). Nhờ đó, số lượng URL tìm được
**không bị giới hạn bởi** tốc độ / ngân sách thời gian cào chi tiết.

```
[Pha 1: URL DISCOVERY]                        [Pha 2: DETAIL EXTRACTION]
   (khong gioi han thoi gian)                     (doc ledger, tai chi tiet)
        |                                               |
        v                                               v
 Quet listing (c1/c61/keyword)                   Select PENDING/RECHECK_DUE
        |                                               |
        v                                               v
 extract_job_id(url) -> jid                       Filter -> Shuffle -> Limit
        |                                               |
        v                                               v
 ledger.register_url(url, jid)                    HttpClient.get_html(url)
        |                                               |
        v                                               v
 save_catalog() + manifest_<date>.jsonl           _detect_block(html)
                                                        |
                                                        v
                                                  _process_detail_record
                                                        |
                                                        v
                                                  raw envelope -> data/careerviet/raw/<date>/{jid}_v{n}.json
                                                        |
                                                        v
                                                  ledger.mark_done(...)
```

**Chuyển giao giữa hai pha** chỉ qua ledger (`url_hash -> record`), không qua bộ nhớ.

---

## 2. Cấu Trúc Ledger Và Trạng Thái

### 2.1. Đường dẫn mặc định (`crawler.py` dòng 54–58)

| Khóa | Giá trị hằng số | Ý nghĩa |
| :--- | :--- | :--- |
| `DEFAULT_LEDGER_DIR` | `data/careerviet/url_ledger` | nơi 3 tệp ledger reside |
| `DEFAULT_RAW_DIR` | `data/careerviet/raw` | nơi envelope `{jid}_v{n}.json` |
| `CATEGORY_MAP_FILENAME` | `category_by_job_id.json` | bản đồ phái sinh `jid -> source_category` |
| `URL_FILE_GLOBS` | `urls_c1_*.json`, `urls_c61_*.json`, `urls_developer_*.json` | **chỉ 3 nhóm IT**; `c37_digital_mkt` loại ở Bước 1 (xem §8.1) |

### 2.2. Ba tệp ledger

- `catalog_master.json` — bản ghi đầy đủ, key = `url_hash`, value = record dict (job_id, canonical_url, status, latest_version, content_hash, first_scraped_at, last_scraped_at, error_message, repost_of_url_hash…).
- `manifests/manifest_<YYYY-MM-DD>.jsonl` — **JSONL append-only** cho phép phát hiện incremental (mỗi lần chạy ghi 1 dòng trạng thái).
- `category_by_job_id.json` — bản đồ phẳng phái sinh từ Phase-1 URL files, chỉ dùng cho **filter `--source-category`** ở Pha 2.

### 2.3. Tập trạng thái (`crawlers/common/url_ledger.py` dòng 31, 220–292)

```
PENDING  ->  DONE  ----(sau 21 ngay)---->  RECHECK_DUE  ->  (chay lai) -> DONE
    \                     \
     \                     -> FAILED  (Safe Skip, KHONG duoc lay lai tu dong)
      -> CLOSED (tin da xuong, phat hien qua _detect_block + 410/404)
```

- `get_pending_or_due_records(recheck_days=21)` **duyệt theo thứ tự chèn**, **không** trả `FAILED` (nghĩa là `FAILED` mất vĩnh viễn nếu không can thiệp tay).
- Khi một `DONE` quá 21 ngày, `get_pending_or_due_records` **đổi tại chỗ** status trong bộ nhớ sang `RECHECK_DUE`.
- `mark_done(...)` luôn ghi `content_hash`, `latest_version += 1` (nếu `content_hash` đổi), và `last_scraped_at`.

### 2.4. Số liệu ledger THẬT hiện có (truy vấn đọc, không sửa)

```
Tong so url_hash: 1029
Status: {PENDING: 1029}
source_category (qua category_by_job_id.json):
  c1: 611,  c37_digital_mkt: 281,  keyword:developer: 92,  c61: 45
So envelope raw (data/careerviet/raw/): 0   (Phase 2 CHUA chay online)
```

---

## 3. Raw Envelope (Dữ Liệu Thô Nguyên Văn)

Mỗi tin chi tiết tải thành công sinh **một envelope JSON** tại
`data/careerviet/raw/<YYYY-MM-DD>/<job_id>_v<version>.json` (**không** có tiền tố
`dt=`, theo `crawler.py:722` — `date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")`); cấu trúc 2 tầng:

### 3.1. `metadata` — **đúng 8 khóa** (xác thực bằng `build_raw_envelope`)

```
1. job_id            -- id trich tu URL (extract_job_id)
2. source            -- "careerviet"
3. source_url        -- canonical_url cua ledger
4. scraped_at        -- thoi diem tai (UTC ISO)
5. scraper_version   -- "0.5.0" (CRAWLER_VERSION)
6. version           -- so nguyen tang dan theo content_hash
7. content_hash      -- sha1/sha2 (ham hash_container_text) tren .job-detail-page
8. source_category   -- "c1" / "c61" / "keyword:developer" / "c37_digital_mkt"
```

### 3.2. `raw_payload` — giữ **nguyên selector lớp CSS** của Careerviet

Các khóa quan sát được trên 3 cặp mẫu (`samples/`):
```
title, job-company-name, detail-box, detail-row, job-tags, map,
"Ngành nghề", job-posting-schema
```

- **KHÔNG đổi tên**, **KHÔNG làm sạch**, **KHÔNG chuẩn hóa** tại tầng raw.
- Khóa `"Ngành nghề"` là tên tiếng Việt có dấu — giữ nguyên, dùng cho bước kiểm tra IT ở §8.2.

---

## 4. `content_hash`, Repost, Version

Hàm `container_text_for_hash` + `hash_container_text` (`crawler.py` dòng 623–624):

1. `BeautifulSoup(html).select_one(".job-detail-page")` -> lấy `.get_text()`.
2. Loại `<script>`, `<style>`, `<iframe>`, `<noscript>`, `<svg>` trước khi trích text.
3. Nén khoảng trắng (`\s+ -> " "`).
4. Nếu `--exclude-volatile-dates = True` (MẶC ĐỊNH): **tạm bỏ** dòng "Cập nhật"/"Hết hạn" trước khi băm (tránh đổi hash vì ngày).
5. Hash chuỗi đã rút gọn -> `content_hash`.

Nhánh xử lý trong `_process_detail_record` (dòng 618–657):

| Điều kiện | Kết quả |
| :--- | :--- |
| `find_by_content_hash(hash)` trả record **khác url_hash** đã `DONE` | **`repost`** — `mark_done` với `repost_of_url_hash`, **KHÔNG ghi file mới** |
| `rec.content_hash == hash` **và** `curr_ver > 0` | **`same_content`** — giữ nguyên `latest_version`, ghi đè envelope cùng `v{n}` (atomic, no-clobber mặc định) |
| Nội dung đổi | **`version bump`** — `new_ver = curr_ver + 1`, ghi envelope `v{new}` |

---

## 5. Cơ Chế An Toàn Khi Gọi Mạng

### 5.1. Delay + single-thread

`_online_client()` (`crawler.py` dòng 117–125) luôn tạo `HttpClient` với:
- `DelayConfig(min_seconds=2.0, max_seconds=5.0)` — **chỉ áp dụng từ request thứ 2** (request #1 delay 0).
- Một `requests.Session` duy nhất, vòng lặp `for rec in candidates:` **tuần tự một luồng**.
- `timeout=25`.

User-Agent xoay vòng từ pool 7 UA trình duyệt thật trong `crawlers/common/http_client.py`
(`_USER_AGENTS`); **KHÔNG in cookie/token** khi debug.

### 5.2. Ma trận xử lý lỗi (nhánh online, `crawler.py` dòng 780–849)

| Lỗi | Hành vi | Trạng thái ledger sau đó | Ghi chú |
| :--- | :--- | :--- | :--- |
| HTTP **429 / 403** | **`break` tức thì**, `_dump_blocked_page` | tin đang xử lý **`PENDING`** (KHÔNG `mark_failed`) | Log `GAP 429/403 -> DUNG an toan, GIU PENDING` |
| HTTP **200** nhưng `_detect_block = True` (captcha/Access Denied/Just a moment + **thiếu** `.job-detail-page`) | **`break` tức thì**, `_dump_blocked_page` | **`PENDING`** | Chữ `captcha` trong `<script>` của trang **TỐT** (còn `.job-detail-page`) **KHÔNG bị tính** |
| HTTP **500/502/503/504** (SERVER_ERROR_STATUSES) — **rời rác** (< N liên tiếp) | `continue`; buffer `buf.append(rec)`; flush thành `FAILED` khi có tin **thành công** **kế tiếp**, hoặc khi hết vòng mà chưa đủ N | `FAILED` (Safe Skip) | Log `Loi 5xx <jid> (HTTP <s>) -> vao chuoi lien tiep (k/3), chua mark_failed` |
| HTTP **500/502/503/504** — **đủ N = 3 liên tiếp** (`CONSECUTIVE_SERVER_ERROR_STOP`) | **`break` cả đợt**; 3 tin trong buffer ở lại `PENDING`, **KHÔNG** `mark_failed` | `PENDING` | Log `DUNG do chuoi 5xx lien tiep (3 tin: [<a>,<b>,<c>]) -> GIU PENDING, khong mark_failed` |
| Lỗi **không phải 5xx** (timeout, connection reset) | `mark_failed` + `continue`; **đồng thời flush buffer 5xx** (ngắt chuỗi) + reset bộ đếm | `FAILED` | Safe Skip cổ điển |
| Lỗi parse sau khi fetch 200 | `mark_failed` + `continue`; flush buffer (chuỗi 5xx bị ngắt vì ta đã có 200) | `FAILED` | `Safe Skip (online parse)` |

### 5.3. Thư mục `_blocked/` (dump bằng chứng, KHÔNG phải raw)

`_dump_blocked_page(job_id, html, reason)` (`crawler.py` dòng 170+):
- Đường dẫn: `Path(self.raw_dir).parent / "_blocked" / f"{job_id}.html"`.
- Ghi bằng **`open(dest, "x")` (exclusive)** → **KHÔNG ghi đè**, bắt `FileExistsError` và log.
- **KHÔNG nằm trong `raw/`**, KHÔNG phải envelope, KHÔNG tham gia `content_hash`.

### 5.4. Lưu ý: `HttpClient` TỰ retry 3 lần (giới hạn §8.3)

`crawlers/common/http_client.py` `RetryConfig` dùng `status_forcelist=(429, 500, 502, 503, 504)`,
`max_retries=3`, `backoff_factor=1.0` (1s → 2s → 4s) + `raise_on_status=True`.
Nghĩa là: khi crawler **nhìn thấy** một `HTTPError` 429/5xx, `requests` **đã âm thầm thử lại 3 lần**
cho chính request đó. Với Ngưỡng B (3 × 5xx liên tiếp), tổng số request phát sinh trước khi `break`
thực tế là **~9 request** (3 lần × 3 tin) — **vẫn có giới hạn**, nhưng cần hiểu khi tính chi phí.

---

## 6. Cờ CLI (main, `crawler.py` dòng 870–907)

### 6.1. Các cờ chính

| Cờ | Kiểu | Ý nghĩa |
| :--- | :--- | :--- |
| `--phase {discovery,details,view,sync}` | enum | Mặc định `details`. `view` = đọc ledger in thống kê, **KHÔNG** gọi mạng. `sync` = đồng bộ ledger → MinIO, **KHÔNG** gọi mạng ngoài trường (C3). |
| `--online` | flag | **BẮT BUỘC** để gọi mạng. Không có → preview/offline. |
| `--local-html-dir <DIR>` | str | Chạy offline từ HTML đã lưu; **KHÔNG gọi mạng**. |
| `--source-category <CAT>` | **lặp** (`action="append"`) | Chỉ chọn record có `category_by_job_id[jid] == CAT`. Dùng nhiều lần để cộng nhóm. |
| `--shuffle` | flag | Xáo bằng `random.Random(seed).shuffle(selected)` (rng **riêng**, không đụng global). |
| `--seed <int>` | int | **BẮT BUỘC đi kèm `--shuffle`**. Thiếu → `parser.error("--shuffle can kem --seed <so_nguyen>")`. |
| `--limit <int>` | int | Cắt SAU lọc + xáo (thứ tự: **filter → shuffle → cut**). |
| `--exclude-volatile-dates / --no-exclude-volatile-dates` | bool (`BooleanOptionalAction`) | Mặc định `True`: bỏ nhãn "Cập nhật/Hết hạn" khi băm. |
| `--ledger-dir`, `--raw-dir`, `--category-map`, `--urls-dir`, `--max-pages`, `--sync-minio`, `--checkpoint-dir`, `--max-items`, `--output-dir` | | còn lại như help string. |

### 6.2. Thứ tự chọn ứng viên (`_select_pending`, dòng 659–693)

1. `pending = ledger.get_pending_or_due_records(21)` (thứ tự chèn, chỉ PENDING/RECHECK_DUE/DONE quá hạn).
2. Nếu có `--source-category` → **loc** theo `cat_map`. Nếu **rỗng** → `ValueError` thông báo các nhóm khả dụng + **DỪNG, không gọi mạng, không lưu ledger**.
3. Nếu `--shuffle` → **xáo** (deterministic theo `--seed`).
4. Nếu `--limit` → **cắt**.

Trước khi fetch, crawler **in** ra stdout:
```
[CareerViet] SELECTION mode=<online|offline|preview> so_it=<n>
[CareerViet] SELECTION job_ids=[...]
[CareerViet] SELECTION category_distribution={...}
```

### 6.3. Preview (chạy không `--online` không `--local-html-dir`)

`log.info PREVIEW` + `return stats` **TRƯỚC** khi `save_catalog()` → ledger **KHÔNG đổi** (SHA-256 của `catalog_master.json`, `category_by_job_id.json`, `manifests/manifest_*.jsonl` được xác nhận `KHONG_DOI=True` trong dry-select thật ngày 2026-10-16).

---

## 7. Quy Ước Raw As-Is (Nguyên Văn, Không Làm Sạch)

Tầng raw **KHÔNG được**:
- Chuẩn hóa tiêu đề / tên công ty / viết tắt / hoa thường.
- Tách bullet, loại `•`, `-`, `*`.
- Đổi tên key CSS (ví dụ `job-company-name` → `company`).
- Parse `salary_text` thành `salary_min`/`salary_max` (làm ở tầng **Clean / Integration**, không phải raw).
- Sửa dấu chính tả trong chuỗi `"Ngành nghề"` (kể cả ký tự U+FF0C trong `test_5_jobs.json` — mẫu đối chiếu lịch sử, **giữ nguyên**).

Toàn bộ tiền xử lý nằm ở bước **Data Integration** (`data-integration-miner`),
không phải crawler. Crawler **chỉ ghi nguyên văn HTML** (thông qua payload keys) + metadata tối thiểu.

Ghi file bằng `_atomic_write_json` (tmp + `os.replace`) → không hỏng một nửa khi tiến trình bị kill giữa chừng.

---

## 8. Giới Hạn Đã Biết

### 8.1. `c37_digital_mkt` Là Bucket Hỗn Hợp

- **Không đồng nhất** với "Digital Marketing". 281 URL của bucket này do script Phase-1 cũ gắn nhãn; thực tế **có tin `Ngành nghề = "CNTT - Phần mềm"` nằm trong c37**.
- **Bằng chứng mẫu thật** (`samples/35C833DD`): `source_category = "c37_digital_mkt"` **nhưng** `payload."Ngành nghề" = ["CNTT - Phần mềm"]`.
- **Không suy rộng** tỉ lệ CNTT của 3 mẫu sang 281 tin — chỉ có thể đo sau khi chạy online.
- Khi Phase-2 kết thúc, bước **Integration** phải dùng `"Ngành nghề"` từ `raw_payload`, **không dùng** `source_category` để quyết định IT.
- **281 URL c37** được nap **CÓ CHỦ ĐÍCH** qua `scripts/import_careerviet_urls_to_ledger.py --include-c37` (commit `1470de0`); **KHÔNG** nằm trong glob mặc định của `URL_FILE_GLOBS` (chỉ c1, c61, developer). Comment `crawler.py` (dong 57) **đã được cập nhật** (A1) để ghi rõ quyết định này. Mục đích nap c37: đo **tỉ lệ IT** của bucket lai sau dot chay online.

### 8.2. HTTP Status **Không** Lưu Trong Envelope

Envelope **chỉ tồn tại khi fetch thành công** (`raise_on_status=True` làm request không-2xx raise **trước khi** `_process_detail_record`). Vì vậy:
- Không có cột `http_status` trong envelope.
- `scripts/careerviet_it_check.py` hiển thị `200 (suy ra)` — **đây là suy luận**, không phải dữ liệu thô.
- Khi cần **bằng chứng 200**, `_blocked/` **không** chứa tin thành công; chỉ có log `INFO` ở lần chạy.

### 8.3. `http_client.py` Tự Retry 3 Lần (Như §5.4)

- Là file **dùng chung**, **không sửa**.
- Crawler Careerviet **thừa hưởng** hành vi này; muốn đổi phải thương lượng toàn nhóm.
- Hệ quả: **một lần 503** thực chất = 4 request (1 + 3 retry). **Chuỗi 3-tin-503** = ~12 request + ~9–60 s backoff.

### 8.4. Số Mẫu Kiểm Thử Offline

- 3 cặp HTML + JSON trong `crawlers/sources/careerviet/samples/` (theo convention của nhóm).
- 30 HTML trong `data/raw/careerviet/html/` — là **bộ kiểm tra hồi quy** cho `_detect_block` (0/30 false-positive ở tiêu chí mới).
- **Không suy ra** tỉ lệ CNTT thị trường từ 3 hay 30 mẫu.

### 8.5. CareerViet chỉ có 1 Template DOM (Liên Quan DoD 4)

Kết quả quét **30/30** trang HTML trong `data/raw/careerviet/html/` (16/10/2026):

- **1 template duy nhất** — tất cả đều có sẵn: `.job-detail-page` (×2), `h1.title` (×1), `a.job-company-name` (×1), `div.detail-box` (×4), `.map` (×1), JSON-LD (×3), iframe = 0, badge hot/vip = 0, nhãn `"Ngành nghề"` = **có**.
- **Biến thể** (KHÔNG phải layout khác): số `div.detail-row` = **5 hoặc 6**; `.job-tags` = **0 (no-tag)** hoặc **≥1 (co tag)** → **4 tổ hợp**:

| Tổ hợp       | Số tin /30 | `job_id` đại diện | Nguồn file |
|--------------|-----------:|-------------------|------------|
| no-tag row=6 | 13         | `35C81470`        | `crawlers/sources/careerviet/samples/` (keyword:developer) |
| no-tag row=5 | 5          | `35C848E9`        | `data/careerviet/_dryrun/raw/2026-10-16/35C848E9_v1.json` + `data/raw/careerviet/html/35C848E9.html` (c1) |
| tag row=5    | 5          | `35C833DD`        | `crawlers/sources/careerviet/samples/` (c37_digital_mkt) |
| tag row=6    | 2          | `35C87378`        | `crawlers/sources/careerviet/samples/` (keyword:developer) |

**DoD 4 (TASKS.md mục 4)** yêu cầu “3 mẫu HTML đại diện cho 3 layout khác nhau”. CareerViet **không có** 3 layout khác nhau (chỉ 1 template). **Đề xuất xin miễn DoD 4 (phần “3 layout”)** với lý do:

- Nguồn SSR đồng nhất một template (không A/B, không badge hot/vip, không iframe) — bằng chứng: 30/30 mẫu trùng lặp selector.
- Thay bằng nop **4 mẫu** ở bảng trên (3 trong `samples/` + 1 trong `data/`), minh họa đủ **4 tổ hợp biến thể** (tag × row). **KHÔNG cần cào thêm**.
- Nếu thay ngân không cho miễn: nop 3 mẫu `samples/` (3 tổ hợp phổ biến nhất) + ghi chú §8.5 này.

---

## 9. Lệnh Chạy Tham Chiếu (đã chạy online 2026-10-16 → 2026-10-17)

### 9.1. Backup ledger THẬT trước khi online (bắt buộc)

Backup ghi vào `data/careerviet/backup/` **để tận dụng `.gitignore` mục `data/`** hiện có (tránh vô tình `git add .` commit backup zip chứa 1029 URL).

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path data/careerviet/backup | Out-Null
Compress-Archive -Path data/careerviet/url_ledger `
  -DestinationPath "data/careerviet/backup/careerviet_ledger_$stamp.zip"
Get-FileHash data/careerviet/url_ledger/catalog_master.json -Algorithm SHA256 `
  | Tee-Object -FilePath "data/careerviet/backup/hash_$stamp.txt"
```

> **Ghi chú `.gitignore`** (file dùng chung — **agent KHÔNG tự sửa**): nếu Tài muốn giữ thư mục backup ở **top-level** `backup/` (thay vì `data/careerviet/backup/`), cần thêm dòng `backup/` và `*.bak` vào `.gitignore` để tránh commit ledger backup. Đề xuất đã ghi ở cuối §5 của `reports/careerviet_inventory.md`.

### 9.2. Dry-select preview (KHÔNG gọi mạng, đã chạy 2026-10-16)

```powershell
python -X utf8 -m crawlers.sources.careerviet.crawler --phase details `
  --source-category c37_digital_mkt --shuffle --seed 20261016 --limit 20
```

Kết quả (in ra stdout, ledger **KHÔNG đổi SHA-256**): 20 `job_id`, phân bố `{c37_digital_mkt: 20}`.

### 9.3. Lệnh online lượt 1 (dự kiến → **đã chạy**, xem §9.4)

Tài đã chạy với phạm vi **rộng hơn** lệnh dự kiến bên dưới (toàn bộ PENDING, không `--limit 20`, không lọc `--source-category`):

```powershell
python -X utf8 -m crawlers.sources.careerviet.crawler --phase details --online `
  --source-category c37_digital_mkt --shuffle --seed 20261016 --limit 20
```

Sau chạy, ba lệnh kiểm tra:
```powershell
python -X utf8 -m crawlers.sources.careerviet.crawler --phase view
python -X utf8 scripts/careerviet_raw_stats.py
python -X utf8 scripts/careerviet_it_check.py
```

### 9.4. Kết quả online lượt 1 (2026-10-16 → 2026-10-17)

**Trạng thái: HOÀN THÀNH — crawl sạch, 0 lỗi.** Tài đã chạy `python -X utf8 -m crawlers.sources.careerviet.crawler --phase details --online` với phạm vi **toàn bộ 1009 PENDING** (không giới hạn 20, không lọc `--source-category`), kết quả **1018 envelope + 11 repost**.

**Lệnh tái lập** (chỉ đọc local, **không** gọi mạng):

```powershell
python -X utf8 scripts/careerviet_raw_stats.py
python -X utf8 scripts/careerviet_it_check.py
python -X utf8 scripts/careerviet_report_fill.py --json
python -X utf8 scripts/careerviet_eda_charts.py    # sinh 16 bieu do + chu thich 3 phan
```

**Số thực đo**:

| Chỉ số | Giá trị | Ghi chú |
| :--- | ---: | :--- |
| Envelope sinh (`data/careerviet/raw/2026-10-16/`) | **1018** | tất cả `_v1.json` |
| Thời gian crawl | 17:09:58 UTC → 18:27:00 UTC = **77.0 phút** | qua `metadata.scraped_at` 1018 envelope |
| TB / tin | **4.54 s** | khớp `DelayConfig(2.0–5.0 s)` |
| Ledger DONE | **1029 / 1029** | 100 % |
| Ledger PENDING / FAILED / RECHECK_DUE | **0 / 0 / 0** | crawl sạch |
| `data/careerviet/_blocked/` | **0 file** | không 429/403/captcha |
| **CDC NEW** | **1018** | version 1, không repost |
| **CDC UPDATED / ACTIVE / CLOSED** | **0 / 0 / 0** | chưa re-crawl 21 ngày |
| **CDC REPOST** | **11** | `content_hash` trùng URL khác, `repost_of_url_hash != null`, **không** sinh envelope |
| Đối chiếu | `1029 − 11 = 1018` ✓ | |
| Phiên bản phân bố | `{1: 1018}` | chưa v2+ |

**Cấu trúc `raw_payload` đối chiếu bằng envelope thật** (đọc local, sửa trong lượt 2026-10-18): `detail-box` = **`List[str]`** (các dòng `<li>` metadata: Lương / Kinh nghiệm / Cấp bậc / Hình thức / Ngày cập nhật / Hết hạn nộp; độ dài `0`→24 tin, `9`→104, `10`→890), **KHÔNG phải** mô tả công việc. JD thật nằm trong `detail-row` = **`Dict[str,str]`** (số key `0`→1, `5`→279, `6`→729, `7`→9; heading `Mô tả Công việc` 1013/1018, `Yêu Cầu Công Việc`/`Phúc lợi`/`Thông tin khác`/`Gợi ý hồ sơ` 1017, `Địa điểm làm việc` 728). Bản đầy đủ trùng trong `job-posting-schema.description` (**1018/1018**). Chi tiết: `reports/careerviet_inventory.md` §1.2 và `reports/careerviet_eda.md` §1.1.

**Tỉ lệ IT** (`raw_payload["Ngành nghề"]` chứa `"CNTT"` hoặc `"Phần mềm"`):

| Bucket | Số tin | IT | % IT |
| :--- | ---: | ---: | ---: |
| `c1` | 602 | 398 | **66.1 %** |
| `c37_digital_mkt` | 279 | 136 | **48.7 %** |
| `keyword:developer` | 92 | 43 | **46.7 %** |
| `c61` | 45 | 14 | **31.1 %** |
| **Tổng** | **1018** | **591** | **58.1 %** |

=> Bucket `c37` có **48.7 % IT / 51.3 % non-IT** → xác nhận quyết định `--include-c37` (commit `1470de0`) là **cần thiết** để đo tỉ lệ thật. Data Integration **phải** dùng `Ngành nghề`, **KHÔNG** dùng `source_category` (docs/crawl §8.1).

**`content_hash` đổi giữa hai version**: **chưa có** vì chưa re-crawl sau 21 ngày (`RECHECK_DUE = 0`). Khi re-crawl, `_process_detail_record` sẽ phân nhánh `same_content` vs `new_version` theo `content_hash`.

**Báo cáo chi tiết** (cùng repo, cập nhật lượt 2026-10-18):

- [`reports/careerviet_inventory.md`](../../reports/careerviet_inventory.md) — field inventory + % null thực đo 8 trường.
- [`reports/careerviet_eda.md`](../../reports/careerviet_eda.md) — EDA sơ bộ (null, CDC, IT ratio, top tags/locations/companies, so sánh IT vs ngoài IT) + nhúng 16 biểu đồ.
- [`reports/careerviet_eda_charts.md`](../../reports/careerviet_eda_charts.md) — 16 biểu đồ + chú thích **Quan sát / Ý nghĩa / Hạn chế** tự động sinh bởi `scripts/careerviet_eda_charts.py`.
- Ảnh PNG: `reports/figures/careerviet/01_bucket_supply.png` … `16_ledger_cdc.png` (16 file, cùng 1 style, mỗi ảnh có dòng nguồn riêng).

---

## 10. Test Tự Động (pytest)

```
python -X utf8 -m pytest -q
```

Kết quả thực đo **tại HEAD `4701af8` + working tree** (2026-10-18):

```
1 failed, 297 passed in 58.05s
  FAILED tests/unit/test_url_ledger.py::test_url_ledger_default_storage_dir
    ('data\\topcv\\url_ledger'.endswith('data/topcv/url_ledger') == False)
    # Windows path separator, co SAN, thuoc file dung chung -> KHONG sua o day.
```

Subset CareerViet + push_raw_to_minio (lệnh:
`python -X utf8 -m pytest -q (Get-ChildItem tests/unit/test_careerviet_*.py | Select-Object -ExpandProperty FullName) tests/unit/test_push_raw_to_minio.py`):
**151 passed / 0 failed** (tăng từ 104 khi `test_careerviet_eda_charts.py` đi từ 12 lên **59** test ở lượt 2026-10-18; trước đó 52 → 92 khi thêm `report_fill`, `sync_phase`, `push_raw_to_minio`).

> Biến thể chọn bằng `-k` (`pytest tests/unit -k "careerviet or push_raw"`) ra **161 passed / 137 deselected** vì gom thêm `test_import_careerviet_urls.py` (9 test) + 1 test `careerviet` trong `test_crawlers.py`. Con số chuẩn để đối chiếu vẫn là **151** theo lệnh nêu trên.

| File test | Số test | Nội dung chính |
| :--- | ---: | :--- |
| `test_careerviet_crawler.py` | 2 | parse item, extract job_id |
| `test_careerviet_raw_envelope.py` | 5 | metadata 8 khóa, atomic write, version |
| `test_careerviet_two_phase.py` | 7 | discover/details offline, stats key |
| `test_careerviet_samples.py` | 13 | 3 cặp mẫu HTML/JSON hồi quy |
| `test_careerviet_selection.py` | 8 | filter/shuffle/seed, 429 break, preview no-write, non-5xx FAILED |
| `test_careerviet_block_detect.py` | 13 | `_detect_block` 3 kịch bản + **Ngưỡng 5xx Phương án B (a-e)** |
| `test_careerviet_raw_stats.py` | 4 | script thống kê envelope đọc raw |
| `test_careerviet_it_check.py` | 5 | script đọc `Ngành nghề`, CNTT detection |
| `test_careerviet_sync_phase.py` | 4 | `--phase sync` delegate `sync_to_minio`, argparse chap nhan `sync` |
| `test_careerviet_report_fill.py` | 16 | scan envelope, % null, ti le CNTT, **CDC mutually exclusive** (repost khong trùng NEW) |
| `test_push_raw_to_minio.py` | 15 | dry-run, no-clobber, `--job-id`, password khong log, anh xa `dt=` va bare date |
| `test_careerviet_eda_charts.py` | 59 | 16 biểu đồ + chú thích 3 phần: `flat_text` (hồi quy `&` không đóng entity), `pick_section`, `decorate` tự xuống dòng/thu nhỏ tiêu đề, audit chữ bằng `fig.get_tightbbox` trên cả 16 ảnh, biểu đồ 15 đọc `detail-row` KHÔNG `detail-box`, `skip()` cho mẫu mỏng, `pct` trả `n/a` thay vì bịa số; tmp_path, không mạng |
| **Tổng subset** | **151** | (0 fail; tổng 12 file test ở bảng trên) |

---

## 11. Trạng Thái Repo Tham Chiếu

- `HEAD = 4701af8` — `docs(careerviet): MinIO = AIStor (minio.exe --license), Docker chi la phu` (**đã commit & push**, 2026-10-17)
- `origin/crawls/careerviet = 4701af8` → local **đồng nhất** origin (`0 ahead / 0 behind`).
- Chuỗi 8 commit đã push (xem `git log --oneline 719e05f^..HEAD`): `1470de0`, `74f643b`, `f977ffb`, `4bf8b1b`, `9e6462d`, `b9cca20`, `315a04c`, `4701af8`.
- Working tree **chưa commit** (lượt 2026-10-18):
  - Modified: `reports/careerviet_eda.md` (424 dòng — §4 dựng lại theo 16 biểu đồ + bảng §4.17), `reports/careerviet_inventory.md` (202 dòng), `docs/crawl/careerviet.md` (§9 + §9.4 + §10 + §11 + §12 cập nhật).
  - Untracked: `scripts/careerviet_eda_charts.py` (1363 dòng — 16 biểu đồ, `decorate()` đo-lại-sau-`tight_layout`, `flat_text` đã vá `close()`), `tests/unit/test_careerviet_eda_charts.py` (694 dòng, 59 test), `reports/figures/careerviet/*.png` (16 file), `reports/careerviet_eda_charts.md` (136 dòng, script sinh).

---

## 12. Việc Còn Lại (TODO)

**Đã xong trong các lượt offline gần nhất** (chờ commit):

- [x] A1 comment `crawler.py` dòng 57 khớp thực tế c37.
- [x] A2 docs §2.4 + §8.1 + §8.5 (1 template DOM + bảng 4 mẫu) + xin miễn DoD 4.
- [x] A3 `reports/careerviet_inventory.md` (202 dòng — **đã điền số thật** từ 1018 envelope, không còn ô CHỜ ONLINE).
- [x] A4 `reports/careerviet_eda.md` (424 dòng — **đã điền số thật** + nhúng 16 biểu đồ + bảng tổng hợp IT vs ngoài IT §4.17).
- [x] A6 `scripts/careerviet_report_fill.py` + test (16 pass, CDC mutually exclusive).
- [x] C1 `scripts/push_raw_to_minio.py` (361 dòng, 14 cờ, env var khớp `setup_minio.py` + `url_ledger.py`).
- [x] C2 `tests/unit/test_push_raw_to_minio.py` (15 pass, mock boto3).
- [x] C3 `--phase sync` + `sync_ledger_to_minio()` trong `crawler.py`.
- [x] C4 docs §13 MinIO (bucket, key, thứ tự lệnh, Windows docker, idempotent).
- [x] C5 đề xuất `.gitignore` `backup/` + `*.bak` (agent KHÔNG tự sửa file dùng chung).
- [x] E1 `scripts/careerviet_eda_charts.py` sinh **16 biểu đồ** + `reports/careerviet_eda_charts.md` (chú thích 3 phần Quan sát / Ý nghĩa / Hạn chế cho từng biểu đồ, mẫu mỏng thì ghi `skip` thật thay vì vẽ số bịa).
- [x] E2 vá hiển thị + số liệu (lượt 2026-10-18): tiêu đề/phụ đề dài **tự xuống dòng/thu nhỏ** theo bề rộng thật còn lại (đo `ax._left_title`, tính cả colorbar, và **đo lại sau `tight_layout`** vì chỗ còn lại thu hẹp khi đặt chữ); `flat_text` gọi `close()` để giữ chữ có `&` không đóng entity ("Nhân viên C&B") — trước đó 3 `title` + 5 `job-company-name` bị đếm nhầm thành rỗng, làm lệch cả biểu đồ 04 và số công ty ở biểu đồ 11 (490 → **494**, khớp §1.1). Test: `tests/unit/test_careerviet_eda_charts.py` (**59 case**, gồm audit tự động quét cả 16 ảnh xem chữ tràn biên/đè colorbar).

**Còn lại**:

- [x] Chạy online lượt 1 (2026-10-16 → 2026-10-17): **1018 envelope / 1029 DONE / 11 REPOST / 0 FAILED / 0 BLOCKED**, 77 phút, TB 4.54 s/tin (xem §9.4).
- [x] Điền §9.4 + `reports/careerviet_inventory.md` + `reports/careerviet_eda.md` bằng số liệu thật (`careerviet_report_fill.py` + `careerviet_eda_charts.py`).
- [ ] `--phase sync` + `push_raw_to_minio.py` sau khi Tài khởi động **AIStor** `minio.exe server <DATA_DIR> --console-address ":9001" --license <DUONG_DAN_LICENSE>` và export 4 env `MINIO_*` (xem §13.1 + §13.3).
- [ ] cân nhắc **Re-crawl 21 ngày** qua `--phase details` (ledger tự convert `DONE -> RECHECK_DUE`) → tạo `UPDATED` / `ACTIVE` cho §9.4.
- [ ] Viết Clean layer ánh xạ `raw_payload -> Common Target Schema` (bên `data-integration-miner`).
- [ ] Quyết định có mở rộng `_is_blocking` sang `504` hay không (hiện **không**; xem §5.2).
- [ ] Đề xuất `.gitignore` thêm `backup/` + `*.bak` (Tài tự tay nếu chấp nhận).

---

## 13. MinIO — Cấu Trúc Bucket, Đẩy Raw Envelope, Đồng Bộ Ledger

Theo `docs/01_modern_data_mining_overview.md` §3 và `docs/02_crawling_architecture_guide.md` §3.1, bucket `vn-it-jobs` có 4 zone:

```
s3://vn-it-jobs/
  url_ledger/
    careerviet/
      catalog_master.json             # UrlLedger.sync_to_minio()
      manifests/manifest_<date>.jsonl
  raw/
    careerviet/
      <YYYY-MM-DD>/
        <job_id>_v<version>.json      # push_raw_to_minio.py (§13.2)
  staging/   # chưa dùng cho CareerViet
  curated/   # chưa dùng cho CareerViet
```

**Lệch giữa docs/02 và code (ghi nhận, KHÔNG sửa)**: `docs/02` §3.3 ghi `catalog_master.parquet`; `crawlers/common/url_ledger.py` ghi **`.json`** (không có converter parquet). Thuộc **file dùng chung** → chỉ ghi nhận tại đây.

### 13.1. Đồng Bộ Ledger (đã có sẵn, không cần script mới)

`UrlLedger.sync_to_minio()` (`crawlers/common/url_ledger.py:306`) upload `catalog_master.json` + `manifests/*.jsonl` lên prefix `url_ledger/<source>/`. CareerViet vốn có cờ `--sync-minio` trong `--phase details` / `--phase discovery`.

**Chạy riêng, không cần cào lại** (thêm A-turn C3): `--phase sync` gọi `crawler.sync_ledger_to_minio()`.

```powershell
python -X utf8 crawlers/sources/careerviet/crawler.py --phase sync
# -> [sync] ledger -> MinIO: OK
```

Yêu cầu MinIO đang chạy. **Máy Tài KHÔNG có Docker** → chạy **AIStor** (file thực thi `minio.exe` trên Windows). Cách **chính**:

```powershell
# Duong dan repo co dau cach va tieng Viet co dau -> PHAI boc nhay khi cd
cd "d:\ĐH\Năm 3\Học kỳ 1\Khai thác dữ liệu\crawl data\VN-IT-Job-Mining"

# Bat AIStor Server (DATA_DIR va LICENSE duoc Tai giu NGOAI repo):
minio.exe server <DATA_DIR> --console-address ":9001" --license <DUONG_DAN_LICENSE>

# Kiem tra S3 API da san sang (Console web o :9001):
curl.exe http://localhost:9000/minio/health/live
```

- `<DATA_DIR>` – thư mục AIStor ghi object; **khuyên đặt ngoài repo** (ví dụ `D:\minio-data\`) để `git add .` không quét nhầm.
- `<DUONG_DAN_LICENSE>` – file license `.json` **cá nhân** AIStor, đối xử **như credentials**:
  - **Ngoài repo**, **KHÔNG commit**, **KHÔNG dán** đường dẫn hay nội dung vào docs / log / issue / commit message.
  - Agent **không** đọc, **không** in nội dung hay đường dẫn license.
  - Khi đổi máy, Tài tự copy file; người khác tự xin license riêng.

**Phương án phụ** – **chỉ** khi máy **có** Docker (máy Tài hiện tại **KHÔNG** dùng):
- Linux/macOS: `bash scripts/start_minio.sh` (wrapper gọi `docker compose up -d`, đợi health-check 15 s, rồi chạy `python3 scripts/setup_minio.py` tạo bucket + `.keep` marker).
- Windows PowerShell (máy khác có Docker): `docker compose -f docker-compose.minio.yml up -d`.

`docker-compose.minio.yml` giữ nguyên trong repo làm tham chiếu cho người dùng sau; docs/02 vẫn mô tả Docker.

Cấu hình kết nối **chỉ qua 4 biến môi trường**: `MINIO_ENDPOINT`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_BUCKET`. **KHÔNG hardcode** giá trị ở code / test / docs / log / commit message (mặc định nằm trong `scripts/setup_minio.py:18-21` – file dùng chung, agent **KHÔNG sửa**). PowerShell ≥ 7: `$env:MINIO_ROOT_PASSWORD = Read-Host -AsSecureString "MinIO password"` → map sang env cho tiến trình con (agent **không** in ra).

> **Đường dẫn repo chứa dấu cách**: workspace `d:\ĐH\Năm 3\Học kỳ 1\Khai thác dữ liệu\crawl data\VN-IT-Job-Mining` có nhiều dấu cách và dấu tiếng Việt. Mọi lệnh `cd`, tham số `--local-dir`, `--license`, `--data-dir` **phải bọc nháy kép** (`cd "..."`), nếu không PowerShell báo `A positional parameter cannot be found...` (coi mỗi từ là tham số riêng).

### 13.2. Đẩy Raw Envelope Lên MinIO (script mới)

Vì `sync_to_minio` **chỉ** upload ledger (không raw), ta viết `scripts/push_raw_to_minio.py` đẩy raw envelope local → MinIO.

**Ánh xa key**: `data/careerviet/raw/<date>/<jid>_v<n>.json` → `raw/careerviet/<date>/<jid>_v<n>.json` (docs/01 §3, docs/02 §3.1). Script `push_raw_to_minio.py` **chap nhan ca 2 khai niem thu muc local** (thua nhận bare `<YYYY-MM-DD>` của CareerViet crawler **và** `dt=<YYYY-MM-DD>` của convention Hive/topcv), nhung **luôn loai bo `dt=`** khi sinh S3 key để khớp docs/01.

**Cờ CLI** (đủ dùng):

| Cờ | Mặc định | Ý nghĩa |
|----|----------|---------|
| `--source` | `careerviet` | Tên source (đổi để tái sử dụng cho nguồn khác) |
| `--local-dir` | `data/careerviet` | Gốc chưa `raw/` và `url_ledger/` |
| `--prefix` | `raw/careerviet` | Prefix S3 đích |
| `--bucket` | env `MINIO_BUCKET` | Overide bucket |
| `--endpoint` | env `MINIO_ENDPOINT` | Overide endpoint |
| `--date` | (lặp) | Lọc theo ngày `YYYY-MM-DD` (khớp cả `raw/<date>/` **và** `raw/dt=<date>/`) |
| `--job-id` | (lặp) | Lọc job id cụ thể |
| `--no-clobber` | **BẬT** | Head `head_object`, nếu key đã có → `SKIPPED_EXISTS` |
| `--overwrite` | TẮT | Buộc `put_object` (ghi đè) |
| `--dry-run` | TẮT | In danh sách key, **không upload**, **không cần boto3** |
| `--include-ledger` | TẮT | Kèm luôn `url_ledger/careerviet/*` |
| `--max-files` | ∞ | Giới hạn N file (in case test) |
| `--verify-sha` | TẮT | Sau upload: `head_object` đối chiếu ETag (MD5 khi single-part; multipart ETag không phải MD5 → cảnh báo + bỏ qua) |
| `--verbose` | TẮT | Log access-key đã mask (`min***in`) |

**An toàn bí mật**:
- `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` đọc từ env, **không bao giờ in** giá trị (kể cả `--verbose`, chỉ in `access_key=<4 đầu>***<4 cuối>`).
- `boto3` lazy import — chạy `--dry-run` **không cần** cài boto3.

### 13.3. Thứ Tự Lệnh Đầy Đủ (sau khi MinIO được duyệt)

```powershell
# 1. Start MinIO AIStor (may Tai KHONG co Docker). Tai chay tay;
#    agent **KHONG** goi, **KHONG** ket noi MinIO that. DATA_DIR va
#    DUONG_DAN_LICENSE duoc Tai giu NGOAI repo (khong commit).
minio.exe server <DATA_DIR> --console-address ":9001" --license <DUONG_DAN_LICENSE>
curl.exe http://localhost:9000/minio/health/live   # (ky vong: HTTP 200, body rong)

# 2. Dong bo ledger (khong goi mang ngoai truong; khong can Phase 1/2)
python -X utf8 -m crawlers.sources.careerviet.crawler --phase sync

# 3. Dry-run day raw (kiem tra key mapping, khong can boto3)
python -X utf8 scripts/push_raw_to_minio.py `
  --source careerviet --local-dir data/careerviet `
  --prefix raw/careerviet --dry-run --verbose

# 4. Upload that (idempotent, mac dinh --no-clobber)
python -X utf8 scripts/push_raw_to_minio.py `
  --source careerviet --local-dir data/careerviet `
  --prefix raw/careerviet --verify-sha

# 5. doi chieu tren MinIO console
aws --endpoint-url http://localhost:9000 s3 ls s3://vn-it-jobs/raw/careerviet/ --recursive
```

Hoặc dùng MinIO client `mc ls local/vn-it-jobs/raw/careerviet/`.

> **Môi trường thực tế của Tài**: máy **không có Docker** → chạy **AIStor** (`minio.exe server ... --license ...`). File license `.json` là **bí mật cá nhân**, đặt **ngoài repo**, **KHÔNG commit**, **KHÔNG dán** đường dẫn hay nội dung vào docs / log / issue / commit message (agent **không** bao giờ đọc hay in). `docker-compose.minio.yml` và `scripts/start_minio.sh` **chỉ còn là phương án phụ** cho máy khác có Docker; máy Tài **KHÔNG** dùng lệnh `docker compose`. Connection config **chỉ** qua 4 env: `MINIO_ENDPOINT`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_BUCKET`.

### 13.4. Test Tự Động Cho Push Script

`tests/unit/test_push_raw_to_minio.py` **mock boto3**, không kết nối MinIO thật.
5 assertion chính:
- `--dry-run` → **không** gọi `put_object`.
- `--no-clobber` mặc định → `head_object` OK (key tồn tại) → bỏ qua, `put_object` không gọi.
- `--job-id` lọc đúng danh sách `<jid>_v<n>.json`.
- **Password** và secret **không** xuất hiện trong `caplog` / stdout.
- **Ánh xa key**: `dt=<date>/<jid>_v<n>.json` **và** `<date>/<jid>_v<n>.json` (ca 2 kieu folder local) → `raw/careerviet/<date>/<jid>_v<n>.json` (script luôn loai bo `dt=` khi sinh key).
