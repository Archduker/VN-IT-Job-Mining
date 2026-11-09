# F10. Mining chưa chạy dữ liệu thật

Issue: MINE-1, MINE-4, MINE-5, MINE-6. Trạng thái: **đặc tả chưa duyệt** (viết 09/11/2026). Theo dõi ở `docs/tasks/issues_merge.md`.

## Vấn đề
Số liệu báo cáo của Phúc là dữ liệu giả (`mining/synthetic.py`); khoảng k lệch giữa task 6–12, checklist 4–14, spec 07 3–15 (code dùng 4–14); `scripts/load_mart_from_parquet.py` biến cột list thành chuỗi; chưa có bảng `skill_salary_shap_values`.

## Giải pháp
1. Sau F05 và F06 (thang cấp bậc, đường vào), chạy mining trên `features.parquet` thật với `data/`; thay số trong báo cáo, bỏ chữ "dữ liệu giả".
2. MINE-4: người dùng chọn một khoảng k; ghi vào spec 07 và sửa hai tài liệu còn lại.
3. MINE-5: đổi cột list sang JSON/ARRAY Postgres, thêm bảng SHAP theo `scripts/sql/init_mart_schema.sql`; kiểm bằng test với DB mock.
4. MINE-6: thêm ghi chú giới hạn (SHAP không phải nhân quả) vào báo cáo đồ án.

## Chờ
GEN-4/GEN-9 (đường `features.parquet`), F05.

## Rủi ro
Chạy mining lần đầu có thể lộ lỗi thật; tách issue riêng.
