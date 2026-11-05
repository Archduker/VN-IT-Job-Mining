# Báo cáo định hướng lại đồ án

Đề tài: **Tích hợp và khai phá dữ liệu thị trường lao động phục vụ phân tích nghề nghiệp và kỹ năng trong IT**.

**Bản dùng chính hiện tại:** [Báo cáo tổng hợp Cleaning và Preprocessing (.docx)](bao_cao_tong_hop_cleaning_preprocessing.docx). [Bản Markdown tổng hợp](bao_cao_tong_hop_cleaning_preprocessing.md).

Bản tổng hợp có một trang bìa, một phần mở đầu, một mục lục, hai phần xử lý chính, kết luận và tài liệu tham khảo chung. Chương, bảng và hình được đánh số liên tục. Hai bản độc lập dưới đây được giữ làm nguồn biên soạn:

| Báo cáo nguồn | Bản Word trước khi gộp | Bản nguồn |
|---|---|---|
| Khảo sát dữ liệu và Data Cleaning | [01_bao_cao_data_cleaning.docx](01_bao_cao_data_cleaning.docx) | [Markdown](01_bao_cao_data_cleaning.md) |
| Tích hợp và Data Preprocessing | [02_bao_cao_data_preprocessing.docx](02_bao_cao_data_preprocessing.docx) | [Markdown](02_bao_cao_data_preprocessing.md) |

Báo cáo được soạn ngày 05/11/2026 từ code, EDA và báo cáo lịch sử trong repository, sau đó gộp theo yêu cầu thành phiên bản 2.0. Nội dung đề xuất thiết kế lại; không tuyên bố đã chạy pipeline mới hay kiểm chứng dữ liệu R2 hiện tại. Thông tin trường, lớp, giảng viên và sinh viên để trống để người thực hiện điền.

Bản Word dùng khổ A4, Times New Roman, nội dung 12 pt, bảng 10–11 pt, lề trái 3 cm, các lề còn lại 2 cm. Đây là bố cục học thuật thông dụng, chưa phải mẫu riêng của trường. Bảng có hàng tiêu đề lặp, sơ đồ được nhúng thành hình và chân trang có số trang tự động.

Mục lục chứa trường TOC của Word, kèm danh sách chương hiển thị sẵn. Sau khi chỉnh sửa, chọn toàn bộ bằng **Ctrl+A**, nhấn **F9**, chọn cập nhật toàn bộ mục lục nếu Word hỏi. Đường dẫn bằng chứng nội bộ được in theo repository để vẫn đọc được khi gửi riêng file Word; liên kết web được giữ để truy cập nguồn.

## Tạo lại file Word

Script xuất tài liệu cần `python-docx` và `Pillow` trong môi trường Python đang dùng; không cần thêm chúng vào dependency chạy crawler. Sau khi sửa Markdown, chạy từ thư mục project:

```bash
python3 scripts/build_course_reports.py
```

Script ghép nội dung từ hai Markdown nguồn, cập nhật bản Markdown tổng hợp và xuất một DOCX tổng hợp. Các chỉnh sửa trực tiếp trong Word hoặc Markdown tổng hợp sẽ bị thay khi tạo lại; cần sửa hai Markdown nguồn hoặc phần biên tập gộp trong script. Script không chạy pipeline hoặc truy cập R2. Sơ đồ trong script là bản trình bày tương ứng với Mermaid; khi đổi quy trình cần cập nhật cả hai biểu diễn.
