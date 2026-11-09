# F08. Thu thập: SCRAPE-18, ledger, sync --source

Issue: SCRAPE-11, SCRAPE-13, SCRAPE-14, SCRAPE-17/GEN-6, SCRAPE-18, MERGE-9. Trạng thái: **đặc tả chưa duyệt** (viết 09/11/2026). Theo dõi ở `docs/tasks/issues_merge.md`.

## Vấn đề
1. `collection` import ngược `preprocessing.common.it_filter` (SCRAPE-18).
2. `scripts/sync_cloud_lakehouse.py --download --source X` chỉ tải `url_ledger/X` (prefix gán cứng ở dòng ~164), không tải `raw/X` (MERGE-9).
3. Test ledger `test_latest_status_change_wins_between_workers` pass trên Linux, fail trên Windows (`save_catalog` dùng `mem_ts >= disk_ts`).
4. SCRAPE-11/13/14: discovery/delay/contract test cho các nguồn còn lại.

## Giải pháp
1. SCRAPE-18: **chờ quyết**: giữ lọc ở thu thập hay chỉ lọc ở Clean. Nếu bỏ: xóa import và để API trả đủ; nếu giữ: chuyển `it_filter` sang `collection/common/` để hết phụ thuộc ngược.
2. MERGE-9: đổi prefix tải thành `raw/`, `url_ledger/` (cả hai) khi có `--source`; thêm test với client giả.
3. Ledger: dùng `>` thay `>=` hoặc so sánh thêm số phiên bản (cần Tài tái hiện trên Windows trước, không sửa mù).
4. SCRAPE-11/13/14: làm cùng contract test từng nguồn (xem `tests/CLAUDE.md`), mỗi nguồn một commit.

## Xong khi
Mỗi mục có test; `pytest tests/contract tests/unit/test_url_ledger_dedup.py` xanh.

## Rủi ro
Đụng `collection/` ảnh hưởng crawler đang chạy; không cào thật và không ghi R2 trong các issue này.
