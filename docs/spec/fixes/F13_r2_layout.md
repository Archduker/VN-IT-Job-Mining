# F13. Layout R2 (GEN-4) và đường features

Issue: GEN-4, GEN-7, GEN-9. Trạng thái: **đặc tả chưa duyệt** (viết 09/11/2026). Theo dõi ở `docs/tasks/issues_merge.md`.

## Vấn đề
R2 hiện còn `raw/`, `url_ledger/`, `staging/`, `curated/`, `quality/`, `integration/`, `transformation/`, `silver/*.json`. Đích spec 10: `raw/`, `url_ledger/`, `silver/all.parquet`, `gold/{gold_master_jobs.parquet, features.parquet, matrices/}`. Chi tiết và danh sách chỗ lệch ở `KNOWN_ISSUED.md` GEN-4.

## Trạng thái
Người dùng chưa chốt (cần biết các bạn đọc/ghi prefix nào). Không đặc tả cách làm cho tới khi chốt.

## Các bước sau khi chốt (đã quyết một phần)
1. Sửa code còn lệch: `canonicalize_lakehouse_key` chấp nhận `silver/all.parquet`; `r2_export.py` và `push_preprocessing_to_r2.py` đẩy một file; tên gold theo spec; `push_integration_to_r2.py`.
2. Sửa tài liệu R2 (`docs/spec/10_architecture.md`, `docs/guides/cloud_r2_setup_guide.md`, `.agents/skills/r2-lakehouse-guide/SKILL.md`, `collection/CLAUDE.md`, `scripts/CLAUDE.md`, `AGENTS.md`).
3. `scripts/migrate_lakehouse_layout.py --prefix-map` chạy thử, gửi số liệu, chờ đồng ý, rồi mới `--apply`. Việc xóa `quality/`, `integration/`, `transformation/` và 32 file `staging/` cũng chỉ sau dry-run và đồng ý.

## Rủi ro
Ghi/xóa R2 không hoàn tác được; luôn dry-run trước.
