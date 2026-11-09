# F11. Monitoring chưa kiểm sau merge

Issue: VIZ-6, VIZ-7. Trạng thái: **đặc tả chưa duyệt** (viết 09/11/2026). Theo dõi ở `docs/tasks/issues_merge.md`.

## Vấn đề
`/insights` chưa kiểm với Mart thật (Mart rỗng); chưa chạy `./start_monitoring.sh --check` và kiểm 390 px; bundle JS 778 kB.

## Giải pháp
1. `./start_monitoring.sh --check` (không in giá trị `.env`, không bật Airflow scheduler).
2. Nạp Mart bằng `scripts/load_mart_from_parquet.py` vào Postgres docker (sau F10/MINE-5), kiểm `/insights`.
3. Kiểm giao diện ở 1440 px và 390 px.
4. Code-split bằng `React.lazy` cho trang nặng.

## Xong khi
Mỗi bước có bằng chứng (log hoặc ảnh chụp); `npm run build` thành công.

## Rủi ro
Cần docker (SCRAPE-1: user chưa có quyền docker).
