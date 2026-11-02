# docs/CLAUDE.md

Bản đồ tài liệu. Khi tài liệu mâu thuẫn với code thì tin code; với crawler thì bảng tiêu chuẩn C1–C14 trong `collection/CLAUDE.md` là bản chính thức.

## Tài liệu theo phần

| Phần | File | Ghi chú |
|---|---|---|
| Nhật ký lỗi đã xử lý | `issue_log.md` | Lỗi → Nguyên nhân → Cách xử lý → Kiểm chứng |
| Chất lượng code | `code_quality.md` | Sinh tự động bằng `make quality`; không sửa tay |
| Tổng quan | `01_modern_data_mining_overview.md` | Thiết kế ban đầu; phần CDC có ghi chú theo code |
| Crawler | `02_crawling_architecture_guide.md`, `two_phase_r2_crawler_playbook.md`, `crawler_output_checklist.md` | Đã cập nhật 03/11/2026 |
| Phân tích từng nguồn | `crawl/<nguồn>.md` | Nhật ký phân tích lúc làm crawler. Ô "Hiện trạng 03/11/2026" ở đầu file là phần đúng với code; phần dưới có thể cũ |
| Phương pháp phân tích nguồn | `guides/crawler_analysis_methodology.md` | |
| R2 | `cloud_r2_setup_guide.md` | Đã cập nhật 03/11/2026 |
| Airflow | `03_airflow_guide.md` | Đã cập nhật 03/11/2026 |
| EDA, integration | `03_eda_and_integration_guide.md`, `tasks/` | |
| Pre-processing | `preprocessing/` | `00_architecture_overview.md` là luật ranh giới các bước |
| Lịch sử | `archive/` | Không sửa, không dùng làm căn cứ |

Việc còn mở nằm ở `KNOWN_ISSUED.md` (thư mục gốc), không nằm trong `docs/`.

## Khi sửa xong một lỗi

1. Thêm một mục vào `issue_log.md`, đúng mục (Thu thập, Dữ liệu, Monitoring, Testing), mã `L-<số tiếp theo>`, theo khuôn:
   ```
   ### L-xx. <Tên lỗi ngắn> (<mã cũ trong KNOWN_ISSUED nếu có>)
   - **Lỗi:** thấy gì, ở đâu, số liệu.
   - **Nguyên nhân:** vì sao, chỉ ra file hoặc hàm.
   - **Cách xử lý:** sửa gì; dữ liệu đã sửa lại thế nào.
   - **Còn lại:** (nếu có) phần chưa xong, trỏ về mã trong KNOWN_ISSUED.
   - **Kiểm chứng:** test nào, lệnh nào chứng minh.
   ```
2. Xóa mục đó khỏi `KNOWN_ISSUED.md`.
3. Nếu lỗi là một bẫy dễ lặp lại, thêm một dòng vào `CLAUDE.md` của thư mục liên quan.
4. Sửa tài liệu nào mô tả sai hành vi cũ.

Không viết báo cáo rời trong `reports/`: thư mục đó chứa kết quả pipeline mà Monitoring đọc. Báo cáo audit (`reports/data_audit_*`) được bỏ khỏi git.

## Văn phong

Tài liệu viết bằng tiếng Việt. Đường dẫn trong tài liệu là đường dẫn tương đối trong repo, không dùng `file:///` hay đường dẫn tuyệt đối trên máy cá nhân.
