# F09. Bộ lọc IT và cohort

Issue: PRE-15, PRE-28, PRE-12, PRE-13. Trạng thái: **đặc tả chưa duyệt** (viết 09/11/2026). Theo dõi ở `docs/tasks/issues_merge.md`.

## Vấn đề
`it_policy.json` loại 5.409 tin non_IT bằng bằng chứng tổng hợp, chưa có nhãn từng tin. Cohort của Phát giữ 5.104/5.177, 5.092 tin chưa duyệt, 17,1% không có kỹ năng, độ thưa 98,15% (ngoài 95–98%).

## Các lựa chọn (không chọn thay người dùng)
- PRE-15: (A) giữ nguyên; (B) dùng model phân loại lại các tin bị loại: người dùng đã bỏ hướng này (10/11/2026, bỏ JEV/OpenJev), chỉ còn (A) hoặc sửa luật.
- PRE-28: (A) chấp nhận cohort và độ thưa; (B) nới bộ lọc; (C) mở rộng bộ kỹ năng để giảm 17,1% tin không có kỹ năng.

## Trả lời câu hỏi "nhãn tay để làm gì"
Nhãn tay là bộ đáp án dùng để đo độ đúng của luật hoặc model (precision/recall). Nếu thay bằng model mới thì vẫn cần: không có nhãn thì không biết model tốt hơn luật if-else hay không, nên không có căn cứ để thay.

## Việc chắc chắn làm được ngay
Gán nhãn mẫu theo `docs/tasks/02_tai_clean_and_deduplication.md` §5.8.2 (người dùng gán nhãn; agent không tự điền).

## Xong khi
Có nhãn mẫu, số đo độ đúng được ghi vào PRE-12; quyết định PRE-15/28 được ghi lại.
