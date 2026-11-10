# Kết quả đánh nhãn Tài 76–100

File hiện hành: gold_labels_tai_76_100.json. 25 tin đúng phạm vi, 21 tin đủ 8 trường; 4 tin còn thông tin không thể biểu diễn hoặc chưa xác minh. Đây là nhãn do LLM tạo và đối chiếu, không phải nhãn thủ công đã được con người duyệt.

## Đã xử lý tiếp

- Ưu tiên kinh nghiệm tối thiểu ghi cụ thể trong JD hơn thẻ tóm tắt: 76=8; 78=7; 80=1; 81=5; 83=2; 89=3; 95=5; 99=3 năm.
- Tin 80 và 83: chọn Thỏa thuận theo JD; giữ thông tin khoảng lương mâu thuẫn trong provenance.
- Tin 79: Hybrid theo lịch làm việc trong JD. Tin 82: onsite theo phân loại trực tiếp của trang nguồn, 1 ngày remote/tháng được giữ là quyền lợi.
- Đã đối chiếu tỉnh cho các tin 78, 82, 86, 87, 88 qua trang Glints tương ứng; URL nằm trong provenance.
- Tin 86: Không ghi mức kinh nghiệm TỐI THIỂU vì nguồn chỉ nêu dưới một năm; không tự gán 0.
- Tin 90: tối đa 30.000 USD/năm là tổng đãi ngộ quảng cáo, không phải lương cơ bản. File giữ đúng số, tiền và kỳ, kèm cờ xem lại về phạm vi lương.
- Các nhóm kỹ năng có quan hệ lựa chọn giữ tên ghép ngoài danh mục; không tách thành nhiều yêu cầu bắt buộc độc lập.

## Bốn tin còn vướng

- 89, Trưởng Phòng Công Nghệ (Lark): lương tóm tắt 20–25 triệu VNĐ, nội dung ghi tổng thu nhập 25–30tr; không xác minh được kỳ trả. salary=null.
- 95, IT Team Leader: lương 15–30 triệu VNĐ, không xác minh được kỳ trả. salary=null.
- 96, Full Stack Developer Intern tại Ấn Độ: lương khoảng/đến 4 triệu VND nhưng không có kỳ; địa điểm ngoài Việt Nam không có lựa chọn trong danh mục 34 tỉnh. salary=null và location.provinces=null. KHÔNG gán tỉnh Việt Nam hay Không ghi để che địa điểm Ấn Độ.
- 97, Chuyên Viên Phân Tích Nghiệp Vụ: JD ghi Upto 30M/tháng nhưng không ghi tiền tệ; trang nguồn có nhãn Thỏa thuận. Không đủ căn cứ ghi số có tiền tệ, cũng không bỏ thông tin số bằng cách chọn Không ghi. salary=null.

Các mục này cần quy ước của nhóm về kỳ lương mặc định, tiền tệ mặc định, xử lý xung đột và mã hóa địa điểm nước ngoài. Không thể biến thành đủ 25/25 mà không bổ sung quy ước hoặc sửa hợp đồng nhãn.

## Nạp vào công cụ

1. Mở scripts/gold_labeler.html.
2. Nạp đúng gold_sample.json trong Downloads (sample_id e58bceb3a5).
3. Xuất bản nhãn hiện có để sao lưu, nếu bạn đã tự làm.
4. Bấm Nạp nhãn cũ và chọn gold_labels_tai_76_100.json.
5. File đã chứa các đoạn Section, kỹ năng và nhãn được xác định; không cần nhập lại.

Lưu ý: công cụ hiện không khôi phục flags khi Nạp nhãn cũ. Các tin cần chú ý: 89, 90, 95, 96, 97. File không sửa mẫu hoặc nhãn 1–75, chưa được push Git.
