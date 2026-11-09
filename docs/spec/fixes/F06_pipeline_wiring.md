# F06. Nối bước Dedup và Normalization, làm mới snapshot

Issue: PRE-16, PRE-17, PRE-21. Trạng thái: **đặc tả chưa duyệt** (viết 09/11/2026). Theo dõi ở `docs/tasks/issues_merge.md`.

## Vấn đề
- Integration chưa đọc đầu ra Dedup `01b_deduplication` (5.177 so với 4.897).
- Snapshot `reports/preprocessing/01_clean`, `01b_deduplication` là kết quả của commit `f693b30`, không phải code đã sửa.
- Pipeline đặc trưng của Duy ghi trùng `04_normalization/all.parquet`, chưa nối vào `run.py`.

## Nguyên nhân
Ba nhánh làm song song, mỗi người giữ đường ra/vào riêng; chưa ai làm bước nối.

## Giải pháp
1. Xác định (bằng đọc code) đường nào Dedup ghi và Integration đọc; nối bằng một hằng số đường dẫn, không thêm tầng mới. Hỏi Tài/Hoàng nếu hai bên hiểu hợp đồng khác nhau.
2. Hai bước 04 (Normalization của Duy và pipeline đặc trưng) không được cùng ghi một file: đổi tên đầu ra pipeline đặc trưng hoặc gộp vào `run.py` (hỏi Duy).
3. Sau khi nối, chạy lại `--dry-run` trên `glints`, rồi 8 nguồn, so số với báo cáo cũ; **chỉ khi đó** ghi đè snapshot `reports/preprocessing/`.

## Xong khi
Số dòng vào/ra mỗi bước khớp luật `input = output + bị bỏ`; không còn hai bước ghi cùng file.

## Kiểm chứng
`python scripts/run_preprocessing.py --dry-run` và đối chiếu bảng số; `data/` đã có raw đủ 8 nguồn (đã tải 09/11).

## Rủi ro
Ghi đè `reports/` ảnh hưởng trang Monitoring; không đẩy lên R2 trong issue này.
