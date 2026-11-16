# Kịch bản thuyết trình, slide 6: Pre-processing · 01 Clean

> Lấy từ slide #6 của `slides/index.html` (số trong `data.json` của bộ slide, khớp báo cáo `01_clean`). Thời lượng khoảng 4 phút.
> **[Thao tác]** = việc cần bấm trên slide. Chỗ ghi *(chưa kiểm)* là điều mình chưa xác minh, đừng khẳng định với thầy.

## 0. Một câu mở (15 giây)
"Slide này là bước Clean đầu tiên: từ 13.361 bản ghi raw, mình bỏ những tin **không dùng được** cho phân tích. Tin trùng nằm ở slide sau."

## 1. Tổng quan Before/After (40 giây) — **[Thao tác]** bấm Before, rồi After
- **Before:** 13.361 bản ghi raw. Trong đó chỉ **7.737** là còn dùng được; còn lại 3 loại bị bỏ: **ngoài IT 5.424**, **JD rỗng hoặc ngắn 187**, **CTV và đa cấp 13**.
- **After:** còn 7.737 tin, đã bỏ 5.624 bản ghi (42,1%). Trong số bị bỏ, **ngoài IT chiếm 96,4%**: vấn đề chính của bước này là sàn tổng hợp đăng nhiều tin không phải IT.
- Nhắc để thầy khỏi hiểu nhầm: "7.737 vẫn còn **3.065 bản trùng** (bản cũ, trùng cùng sàn, khác sàn, gần giống). Mình xử lý ở slide Deduplication, nên cuối cùng còn 4.672 rồi 4.671 sau tích hợp." Trong báo cáo code, bước `01_clean` ghi đầu ra 4.799 vì các luật trùng C1, C2, C6, C7 cũng chạy trong bước này; slide tách ra cho dễ hiểu.

## 2. Tab "Ngoài IT" (1 phút 30 giây) — **[Thao tác]** bấm tab "Ngoài IT"
- **Vấn đề:** sàn tổng hợp đăng cả kế toán, kỹ thuật cơ khí, bán hàng... vào mục IT. 5.424 tin bị bỏ.
- **Cách làm, luật hai tầng, không dùng LLM:**
  - Tầng 1 theo tiêu đề: có từ khóa IT (developer, devops, data, qa...) thì gắn IT; có từ khóa loại trừ (kế toán, lái xe...) thì gắn ngoài IT.
  - Tầng 2 theo ngữ cảnh, dùng khi tiêu đề chung chung: chỉ coi là IT nếu mục nghề thuộc CNTT **và** JD có từ 2 kỹ năng IT trở lên.
- **Đánh giá bằng 643 tin gán tay:** gắn "ngoài IT" đúng 93,6% (442 đúng, 30 là IT thật bị gắn nhầm); gắn "IT" đúng 88,9% (152 đúng, 19 thực ra ngoài IT); bắt được 83,5% tin IT thật (152 trên 182).
- **Nói thẳng điểm yếu:** "Mẫu gán tay lấy theo tầng, tăng số tin ngoài IT, nên đây chỉ là **ước lượng**, không đại diện toàn bộ 13.361 tin. Và 83,5% nghĩa là có khoảng 16,5% tin IT thật có thể bị bỏ nhầm. Đây là điểm em muốn xin ý kiến thầy."
- Ví dụ thật bị gắn ngoài IT (đã gán tay xác nhận): "Chief Accountant" (VietnamWorks), "Trưởng nhóm Marketing" (TopDev), "Nhân viên Kinh doanh" (JobsGO), "Graphic Designer" (TopCV).
- Chính sách bỏ ngoài IT được duyệt riêng cho từng nguồn (09/11/2026).

## 3. Tab "JD rỗng, ngắn" (45 giây) — **[Thao tác]** bấm tab "JD rỗng, ngắn"
- **Vấn đề:** tin không có mô tả thì không rút được kỹ năng. **Cách làm:** bỏ tin dưới **50 từ** (mô tả cộng yêu cầu). Ngưỡng này em chốt ngày 10/11/2026, trước đó là 30.
- **Số liệu:** 187 tin bị bỏ, trong đó **173 tin rỗng hoàn toàn (0 từ)** và 14 tin có 1 đến 49 từ.
- **Theo nguồn:** TopCV 164, JobsGO 22, VietnamWorks 1. "Gần như toàn bộ JD rỗng nằm ở TopCV." *(nguyên nhân TopCV trả JD rỗng: chưa kiểm, có thể do trang chi tiết lỗi lúc cào hoặc tin bị khóa.)*
- Ví dụ thật có ít từ: "IT Project Manager (Tiếng Nhật N2)" chỉ 12 từ, "Senior UI/UX Designer" 8 từ (JobsGO).

## 4. Tab "CTV, đa cấp" (30 giây) — **[Thao tác]** bấm tab "CTV, đa cấp"
- 13 tin bị bỏ, khớp từ khóa theo ranh giới từ, không phân biệt hoa thường. Cả 13 tin đều khớp ở **nhóm tiêu đề** ("cộng tác viên", "ctv"); nhóm nội dung ("đa cấp", "mlm"...) khớp 0 tin.
- Theo nguồn: TopCV 5, JobsGO 3, TopDev 2, còn lại mỗi nguồn 1 hoặc 0.
- Lưu ý: luật này chỉ là danh sách từ khóa cố định, không có đánh giá độ đúng như luật ngoài IT.

## 5. Tab "Làm sạch văn bản" (30 giây) — **[Thao tác]** bấm tab "Làm sạch văn bản"
- Việc này thuộc nhóm làm sạch trong tài liệu, nhưng **trong code chạy ở bước 03 (Transformation)**, nên số tin lấy từ báo cáo bước 03.
- Bóc thẻ HTML và entity: 10 tin. Chuẩn hóa Unicode NFC: 34 tin. Bỏ ký tự ẩn (zero-width, BOM): 28 tin. Thống nhất gạch đầu dòng: **1.526 tin**.

## 6. Chốt (15 giây)
"Sau Clean còn 7.737 tin thuộc phạm vi và đủ nội dung. Rủi ro lớn nhất của bước này là **bỏ nhầm tin IT thật**, vì vậy mình đo bằng 643 tin gán tay và báo cả điểm yếu."

## Câu thầy có thể hỏi và cách trả lời
| Câu hỏi | Trả lời (bám số thật) |
|---|---|
| Sao không dùng LLM hay mô hình để lọc IT? | Dự án chọn luật hai tầng để tái lập được và kiểm tra được từng quyết định; đo bằng 643 tin gán tay. Mô hình có thể tăng độ bắt tin IT, nhưng em chưa thử (chưa kiểm). |
| 83,5% recall có đủ không? | Em xem là điểm yếu: ước lượng từ mẫu lấy theo tầng, nên có thể lệch. Em đề xuất nới tầng 2 hoặc xem lại 30 tin IT bị gắn nhầm để thêm từ khóa. Xin ý kiến thầy. |
| Vì sao đổi ngưỡng 30 thành 50 từ? | Em chốt ngày 10/11/2026; dưới 50 từ gần như không rút được kỹ năng. Số 173 trong 187 tin bị bỏ là rỗng hoàn toàn nên đổi ngưỡng ảnh hưởng ít (chỉ khác ở nhóm 14 tin có 1–49 từ). |
| Vì sao 13.361 mà cuối cùng chỉ còn 4.671? | 5.624 tin ngoài phạm vi (slide này) và 3.065 tin trùng (slide sau) = 8.689; 13.361 − 8.689 = 4.672, thêm 1 tin lỗi schema khi tích hợp nên còn 4.671. |
| 13.361 có phải tổng số tin đã cào không? | Đó là số đầu vào theo báo cáo bước Clean; em chưa đối chiếu với số file raw thật trên R2 (chưa kiểm). |
