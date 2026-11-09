# docs/CLAUDE.md

Bản đồ tài liệu. Khi tài liệu mâu thuẫn với code thì tin code; với crawler thì bảng tiêu chuẩn C1–C14 trong `collection/CLAUDE.md` là bản chính thức.

## Cây thư mục

| Thư mục / file | Nội dung | Ghi chú |
|---|---|---|
| `spec/` | Đặc tả dự án `01_product_spec.md` … `13_working_documentation.md` | Chuẩn hiện hành của dự án |
| `spec/crawl/<nguồn>.md` | Phân tích từng nguồn | Nhật ký lúc làm crawler. Ô "Hiện trạng 03/11/2026" ở đầu file là phần đúng với code; phần dưới có thể cũ |
| `spec/preprocessing/` | Thiết kế pre-processing | `00_architecture_overview.md` là thiết kế cũ (4 bước). Refactor 5 bước Clean → Integration → Transformation → Normalization → Encoding: đặc tả trong `spec/preprocessing/spec/P0…P5` |
| `spec/monitoring/` | Đặc tả trang Pre-processing | `preprocessing_page_spec.md` |
| `guides/` | Hướng dẫn kỹ thuật | `01_modern_data_mining_overview.md` (thiết kế ban đầu), `02_crawling_architecture_guide.md`, `two_phase_r2_crawler_playbook.md`, `crawler_output_checklist.md`, `crawler_analysis_methodology.md`, `cloud_r2_setup_guide.md`, `03_airflow_guide.md`, `03_eda_and_integration_guide.md`, `git_workflow.md` |
| `tasks/` | Phân công và hướng dẫn theo người | `README.md` là mục lục; `legacy_TASKS.md` là kế hoạch gốc (cũ) |
| `prompting/` | Prompt cho agent, một prompt mỗi phase | Khuôn trong `prompting/README.md` |
| `reports/` | Báo cáo môn học (.md, .docx) | Sinh bằng `scripts/build_course_reports.py` |
| `presentation/` | Slide và kịch bản | Sinh bằng `scripts/build_slides.py` |
| `archive/` | Lịch sử | Không sửa, không dùng làm căn cứ |
| `issue_log.md` | Nhật ký lỗi đã xử lý | Lỗi → Nguyên nhân → Cách xử lý → Kiểm chứng |
| `code_quality.md` | Chất lượng code | Sinh tự động bằng `make quality`; không sửa tay |

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
