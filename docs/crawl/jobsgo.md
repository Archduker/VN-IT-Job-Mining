# JobsGO Raw Crawler — Architecture & Exceptions

## Source and listing coverage

- Listing entry: `https://jobsgo.vn/viec-lam-cong-nghe-thong-tin.html`.
- Detail pattern observed on the public site: `/viec-lam/<slug>-<numeric-id>.html`.
- Phase 1 follows pagination links associated with the listing route, saves every listing page HTML to MinIO (plus a Base64 sidecar of original response bytes when available) and registers each matching detail URL in the URL Ledger.
- A job link is accepted only when the path matches `/viec-lam/[^/]+-<numeric-id>.html`; category SEO links such as `/viec-lam-cong-nghe-thong-tin.html` do not match this detail pattern.

## Raw fields and detail sections observed

Public detail pages expose labels/sections such as `Mức lương`, `Địa điểm`, `Kinh nghiệm`, `Bằng cấp`, `Hạn nộp hồ sơ`, `Thời gian làm việc`, `Chi Tiết Công Việc`, `Mô tả công việc`, `Yêu cầu công việc`, `Quyền lợi được hưởng`, `Ngành nghề`, `Loại hình`, `Cấp bậc`, `Ngày đăng tuyển`, `Số lượng tuyển` and sometimes `Yêu cầu độ tuổi`. Layout is allowed to vary; **Raw Zone stores the complete HTML response** and does not depend on all labels being present.

## Content hash / CDC

- Hash algorithm: SHA-256 over normalized visible text from the first available detail container selector (`.job-detail`, `#job-detail`, `main`, then `body`) plus a stable projection of listing title/company metadata.
- The selector is recorded in `_meta.container_selector_for_hash`; HTML under `raw.html` remains unmodified; the snapshot also includes `body_bytes_base64` when the HTTP response exposes raw body bytes.
- Dynamic script/style/iframe/svg content and common relative-time/view labels are excluded from the hash input to reduce false updates.
- Numeric salary parsing is intentionally **not** part of the raw crawler. Salary text stays in HTML/card context and should be standardized in Staging.

## MinIO layout

```text
url_ledger/jobsgo/catalog_master.json
url_ledger/jobsgo/catalog_master.parquet
url_ledger/jobsgo/discovery_miss_counts.json
url_ledger/jobsgo/manifests/manifest_YYYY-MM-DD.jsonl
raw/jobsgo/_listing/YYYY-MM-DD/page_0001.html and `.body_base64.txt` when response bytes are exposed
raw/jobsgo/_listing/YYYY-MM-DD/<job_id>_<url_hash>_<capture_time>.json
raw/jobsgo/_listing/current/<job_id>.json
raw/jobsgo/YYYY-MM-DD/<job_id>_v<version>.json
```

The JSON catalog is the transactional source of truth used to bootstrap UrlLedger; Parquet is a mirror for analysis when `pyarrow` is installed. Manifest JSONL entries are append-only by day.

## Exceptions and safety

- Pagination has no structured `hasMore` field. If `--max-pages` is specified, the discovery is always treated as partial and missing-cycle counts are not changed. If page metadata reports more rows than the last visited page range, the run is also marked partial.
- HTTP 404/410 means CLOSED; other non-200 responses are FAILED and the next URL is still processed.
- A URL absent from three consecutive complete discovery runs is marked CLOSED. The threshold is configurable using `CRAWL_CLOSE_MISSING_CYCLES`.
- Respect rate limits; the crawler delays each request. Do not add login bypass or defeat access controls.

## Test fixtures

`crawlers/sources/jobsgo/samples/` contains three explicitly synthetic HTML/JSON fixture pairs representing salary range, salary negotiation, and single-bound salary layouts. They validate parser/pipeline behavior; they are not evidence of live crawl counts.
