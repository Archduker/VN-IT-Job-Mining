---
name: r2-lakehouse-guide
description: >-
  Vận hành Cloudflare R2 Data Lakehouse của dự án VN-IT-Job-Mining: cấu hình .env, layout bucket
  vn-it-jobs (url_ledger, raw, staging, curated), các script đồng bộ, kiểm tra và sửa layout,
  và quy tắc an toàn khi ghi lên bucket dùng chung.
---

# R2 Lakehouse Guide

Dự án chỉ dùng **Cloudflare R2**; MinIO đã bỏ. Mọi kết nối đi qua `collection/common/r2_storage.py` (`get_r2_client`, `resolve_r2_endpoint`, `resolve_r2_bucket`). Không tự tạo `boto3.client` ở nơi khác.

## Cấu hình `.env`

```bash
R2_ACCOUNT_ID=...            # hoặc R2_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=vn-it-jobs
```

`S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME` được đọc làm dự phòng. Thiếu endpoint thì `get_r2_client()` báo lỗi rõ ràng, không kết nối localhost. Không in giá trị khóa; muốn so sánh thì so hash.

## Layout bucket

| Tầng | Key |
|---|---|
| Ledger | `url_ledger/<nguồn>/catalog_master.json`, `url_ledger/<nguồn>/manifests/manifest_<YYYY-MM-DD>.jsonl` |
| Raw | `raw/<nguồn>/<YYYY-MM-DD>/<job_id>_v<N>.json` |
| Staging | `staging/<nguồn>/...` |
| Curated | `curated/...` |

`canonicalize_lakehouse_key` là luật duy nhất cho key. Layout cũ `raw/crawling/<ngày>/<nguồn>/` được `normalize_legacy_key` chuyển về layout chuẩn.

## Script

```bash
python scripts/sync_cloud_lakehouse.py --status | --download | --upload [--source topcv]
python scripts/push_raw_to_r2.py --source topcv --dry-run   # đẩy raw rồi ledger; không đẩy ledger cũ hơn bản trên R2
python scripts/view_urls.py --source topcv --r2             # xem ledger trên R2
python scripts/audit_raw_data.py --r2                        # báo cáo chất lượng dữ liệu, chỉ đọc
python scripts/migrate_lakehouse_layout.py --r2              # chạy thử chuyển layout cũ; --apply để chạy thật
python scripts/reconcile_ledger_from_raw.py --source topcv   # chạy thử dựng lại ledger từ raw; --apply, --push
```

Crawler đồng bộ khi chạy với `--sync-r2` (tên cũ `--sync-minio` vẫn nhận).

## Quy tắc an toàn

- Ghi hoặc xóa trên R2 phải chạy thử trước và cần người dùng đồng ý.
- Raw và ledger phải lên cùng nhau; chỉ đẩy raw thì lần chạy sau sẽ cào lại (xem `collection/CLAUDE.md`).
- Trước khi ghi đè ledger trên R2, sao lưu bản hiện tại (`reconcile_ledger_from_raw.py --push` tự làm).
