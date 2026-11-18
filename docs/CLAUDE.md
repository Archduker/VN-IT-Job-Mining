# docs/CLAUDE.md

Bản đồ tài liệu. Khi tài liệu mâu thuẫn với code thì tin code; với crawler thì bảng tiêu chuẩn C1–C14 trong `collection/CLAUDE.md` là bản chính thức.

## Cây thư mục

| Thư mục / file | Nội dung | Ghi chú |
|---|---|---|
| `target/` | Đề tài và 5 mục tiêu SD1–SD5: `00_de_tai.md` (bối cảnh, vì sao chọn 5 SD), `01`–`05` (mỗi SD gồm câu hỏi, dữ liệu, cách trả lời, tiêu chí đánh giá) | **Đọc trước tiên.** Spec, code và báo cáo phải phục vụ các mục tiêu ở đây |
| `spec/` | Đặc tả dự án `01_product_spec.md` … `13_working_documentation.md` | Chuẩn hiện hành. **`03_data_mining_lifecycle.md` là tài liệu mô tả quy trình**: nối SD1–SD5 với từng bước (mã bước, thư mục code, đầu vào, đầu ra). Spec 05 (pre-processing), 06 (processing), 07 (mining), 08 (đánh giá) đặc tả chi tiết từng bước và phải dùng đúng mã bước của spec 03 |
| `spec/crawl/<nguồn>.md` | Phân tích từng nguồn | Nhật ký lúc làm crawler. Ô "Hiện trạng 03/11/2026" ở đầu file là phần đúng với code; phần dưới có thể cũ |
| `spec/preprocessing/` | **Đặc tả chi tiết từng bước 00–04 và bảng Silver** (từ 18/11/2026), mỗi bước một file theo khuôn 7 mục; `samples/<bước>.json` là dữ liệu mẫu do `scripts/build_step_samples.py` sinh. `scripts/report_data_issues.py` cũng ghi `data_issues_2026-11-03.*` vào đây | Spec 05 giữ hợp đồng chung và bảng Silver; luật chi tiết chỉ ghi ở file bước. Thiết kế P0–P5, PH0–PH9 cũ đã xóa 17/11/2026 |
| `spec/monitoring/` | Đặc tả trang Pre-processing | `preprocessing_page_spec.md` |
| `spec/fixes/` | Đề bài sửa lỗi F01–F13 | Thực chất là việc cần làm; về sau nên chuyển sang `tasks/` |
| `guides/` | Hướng dẫn kỹ thuật | `01_modern_data_mining_overview.md` (thiết kế ban đầu), `02_crawling_architecture_guide.md`, `two_phase_r2_crawler_playbook.md`, `crawler_output_checklist.md`, `crawler_analysis_methodology.md`, `cloud_r2_setup_guide.md`, `03_airflow_guide.md`, `03_eda_and_integration_guide.md`, `git_workflow.md` |
| `tasks/` | Phân công và hướng dẫn theo người | `README.md` là mục lục; `legacy_TASKS.md` là kế hoạch gốc (cũ) |
| `prompting/` | Prompt cho agent, một prompt mỗi phase (PH0–PH9) | Khuôn và bảng phase → mục spec trong `prompting/README.md` |
| `reports/` | Báo cáo môn học (.md, .docx) | Sinh bằng `scripts/build_course_reports.py` |
| `presentation/` | Slide và kịch bản | Sinh bằng `scripts/build_slides.py`; `slides_raw_problems.html` (vấn đề raw đo trên R2) sinh bằng `scripts/report_raw_problems_r2.py` |
| `issue_log.md` | Nhật ký lỗi đã xử lý | Lỗi → Nguyên nhân → Cách xử lý → Kiểm chứng |
| `code_quality.md` | Chất lượng code | Sinh tự động bằng `make quality`; không sửa tay |

Việc còn mở nằm ở `docs/KNOWN_ISSUED.md`.

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
