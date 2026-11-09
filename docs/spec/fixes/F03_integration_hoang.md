# F03. Integration: ID không ổn định, runner trùng, I0

Issue: PRE-18, PRE-19, PRE-20, GEN-7. Trạng thái: **đặc tả chưa duyệt** (viết 09/11/2026). Theo dõi ở `docs/tasks/issues_merge.md`.

## Vấn đề
1. `json_flattener.py:150`: `fallback_id = str(abs(hash(source_url)))` khác nhau giữa các lần chạy (Python đặt hạt giống băm ngẫu nhiên cho chuỗi).
2. `preprocessing/integration/run.py` và `run_integration.py` làm việc trùng nhau.
3. `run.py:174-178`: dòng JSON hỏng thành bản ghi giả thay vì bị loại (P2 §8 ghi loại).
4. Tải R2 trong `preprocessing/integration` tự dựng boto3, prefix cũ, bucket gán cứng.

## Nguyên nhân
Hoàng chọn zero-drop để bảo toàn số dòng; hash dùng hàm có sẵn của Python; tải R2 viết riêng thay vì dùng `collection/common/r2_storage.get_r2_client()`.

## Giải pháp
1. Đổi `hash()` thành `hashlib.sha1(source_url.encode()).hexdigest()[:16]` (giữ tiền tố nguồn). Có test: hai tiến trình khác nhau cho cùng ID.
2. Quyết 1 runner làm chuẩn, runner còn lại gọi vào đó hoặc bỏ (cần Hoàng xác nhận ai gọi `run_integration.py`: dùng `grep` các script gọi trước khi xóa).
3. I0: **chờ người dùng**. Hai lựa chọn: (A) giữ zero-drop nhưng đánh dấu cột `is_recovered_bad_json` và loại ở bước Clean/Normalization; (B) loại dòng hỏng, ghi vào `dropped` đúng P2 §8. Cả hai cần sửa test (đã sửa tạm theo A ở 305d017).
4. Tải R2: thay bằng `get_r2_client()` và `to_r2_key`; làm sau quyết định GEN-4.

## Xong khi
Chạy hai lần cho cùng `source_url` ra cùng ID; chỉ còn một đường vào Integration; I0 khớp lựa chọn đã chốt.

## Kiểm chứng
Test mới cho ID ổn định (chạy `python -c` ở hai tiến trình); `pytest tests/unit/test_integration_step.py`.

## Rủi ro
Đổi ID làm `job_id_global` của các dòng không có `job_id` đổi so với lần chạy trước. Chưa có R2 ghi nên chấp nhận; cần ghi vào báo cáo trước/sau.
