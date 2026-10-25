# Glints Raw Pipeline Addendum — URL Discovery, Cloudflare R2 and CDC

This file supplements the existing `docs/crawl/glints.md` audit document. The old `GlintsCrawler` and `JobRecord` normalization remain available, but the required Raw Zone path is routed through `GlintsRawPipeline` by `run.py` after running the supplied `install_overlay.py` integration helper.

## Listing API

- Endpoint: `https://glints.com/api/v2-alc/graphql?op=searchJobsV3`.
- Operation: `searchJobsV3`; pagination uses `variables.data.page` and `pageSize`.
- The exact GraphQL query and full response object returned to that query are stored per listing page as JSON under `raw/glints/_listing/YYYY-MM-DD/page_NNNN.json`.
- Each returned job object is also archived individually by date and under a `current/` object pointer for Phase 2 lookup. Repeated discovery runs use a capture-time suffix for historical keys so a second scan does not overwrite an earlier listing payload.
- The existing query selects only fields explicitly named in `crawlers/sources/glints/crawler.py`. The raw response is not truncated after it is returned, but the query does not promise to expose every field that might exist in Glints' internal GraphQL schema. The full detail HTML is stored as a second raw source of truth.

## Detail URL and HTML hash

- Constructed public URL pattern: `https://glints.com/vn/opportunities/jobs/<slugified-title>/<job-id>`.
- Preferred hash containers, in order: `.job-detail`, `[data-testid*='job-detail']`, `main`, `body`.
- Hash algorithm: SHA-256 over normalized visible text from the selected container and a stable projection of job listing fields. The original HTML is not modified before it is written to Cloudflare R2; when the HTTP library exposes response bytes, their Base64 representation is also kept in the snapshot for replay/audit.
- `Accept-Encoding: identity` is sent to avoid receiving Brotli in environments where the HTTP stack is not configured to decode it.

## CDC and Cloudflare R2

```text
url_ledger/glints/catalog_master.json
url_ledger/glints/catalog_master.parquet
url_ledger/glints/discovery_miss_counts.json
url_ledger/glints/manifests/manifest_YYYY-MM-DD.jsonl
raw/glints/_listing/YYYY-MM-DD/page_0001.json (includes original response-body Base64 when available)
raw/glints/_listing/YYYY-MM-DD/<job_id>_<url_hash>_<capture_time>.json
raw/glints/_listing/current/<job_id>.json
raw/glints/YYYY-MM-DD/<job_id>_v<version>.json
```

A new URL starts as PENDING. New/changed detail content is written as a snapshot before the catalog is marked DONE. Same-hash re-crawls do not write another snapshot. A new URL with an identical known content hash is linked through `repost_of_url_hash` instead of generating another detail snapshot. The default re-crawl interval is 21 days.

## Fixture layouts

`crawlers/sources/glints/samples/` contains three explicitly synthetic HTML/JSON fixture pairs: JSON-LD `JobPosting`, JSON-LD `@graph`, and an HTML variant with no JSON-LD. These are test fixtures, not collected production data.
