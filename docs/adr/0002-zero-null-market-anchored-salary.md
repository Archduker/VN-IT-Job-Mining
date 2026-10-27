# ADR 0002: Bù Khuyết Lương Zero-Null Bằng Khung Neo Thị Trường & Gemini Agent

- **Trạng thái:** Đã Chấp Thuận (Accepted)  
- **Ngày quyết định:** 2026-10-27  
- **Người đề xuất:** Nhóm Tiền Xử Lý Dữ Liệu (Preprocessing Engineering Team)  
- **Phạm vi ảnh hưởng:** `preprocessing/missing_outlier/`, `data/curated/`

---

## 1. Ngữ Cảnh & Vấn Đề (Context)

Trong thị trường tuyển dụng CNTT tại Việt Nam, một tỷ lệ lớn các bài đăng không công khai dải lương minh bạch mà ghi "Thỏa thuận", "Thương lượng", hoặc để trống trường lương.  
Hiện tượng này thuộc nhóm khuyết thiếu có chủ đích (**MNAR - Missing Not At Random**), bởi các doanh nghiệp thường đàm phán mức lương dựa trên trình độ thực tế của ứng viên hoặc giữ bí mật chính sách đãi ngộ.

Nếu áp dụng các phương pháp tiền xử lý truyền thống:
- **Xóa bỏ các hàng thiếu lương (Drop Rows):** Sẽ làm mất đi hơn 50% dữ liệu quý giá về công nghệ, kỹ năng, và cấp bậc tuyển dụng của thị trường.
- **Điền Mean/Median thô sơ:** Sẽ làm sai lệch phân phối thực tế, ví dụ gán mức lương trung vị 20 triệu cho một vị trí Director hoặc gán 20 triệu cho vị trí Thực tập sinh (Intern).

Nhóm cần một giải pháp thông minh bảo toàn dữ liệu nhưng vẫn đảm bảo tính thực tế của dải lương thị trường và hoàn thành mục tiêu Zero-Null lương phục vụ mô hình hóa.

---

## 2. Quyết Định Kiến Trúc (Decision)

1. **Thuật Toán Market Anchor Matrix 2 Chiều (`MarketAnchorCalculator`):**
   - Tính toán trước ma trận trung vị lương `(median_min, median_max)` từ tất cả các bài đăng có mức lương công khai, nhóm theo 2 chiều: `(source_platform, standardized_seniority)`.
   - Thiết lập cơ chế Fallback 4 tầng:
     1. Khớp chính xác `(platform, seniority)`.
     2. Khớp theo `seniority` trên toàn thị trường.
     3. Khớp theo `platform`.
     4. Giá trị cơ sở toàn thị trường (Global Baseline).

2. **Kết Hợp Gemini All-in-One Preprocessing Agent Với Khung Neo Thị Trường:**
   - Cung cấp ngữ cảnh khung neo của `MarketAnchorCalculator` trực tiếp vào Prompt của Gemini Agent.
   - Mô hình Gemini đọc toàn bộ nội dung chi tiết bài đăng (yêu cầu số năm kinh nghiệm, công nghệ khó hay dễ, quy mô công ty) kết hợp với khung neo để ước lượng mức lương sát thực nhất.

3. **Gắn Cờ Nguồn Gốc Minh Bạch & Bảo Toàn Bản Chất MNAR:**
   - Mọi bản ghi được bù khuyết lương đều đánh dấu rõ ràng `salary_source = "predicted"`.
   - Giữ nguyên cờ `is_salary_negotiable = true` để phục vụ các bài toán phân tích hành vi tuyển dụng.

---

## 3. Hệ Quả & Lợi Ích (Consequences)

### Tích cực:
- **Zero-Null hoàn hảo:** 100% bản ghi trong Golden Master Dataset đều có dải lương số hợp lệ (`salary_min_vnd`, `salary_max_vnd`), sẵn sàng cho các thuật toán phân tích định lượng.
- **Sát với thực tế thị trường:** Mức lương dự đoán bám sát theo cấp bậc và sàn tuyển dụng, không bị hiện tượng ảo giác (hallucination) vượt khỏi quy luật cung cầu.
- **Minh bạch nguồn gốc dữ liệu:** Các nhà khoa học dữ liệu có thể dễ dàng lọc riêng nhóm lương thực tế (`salary_source == "explicit_range"`) hoặc nhóm lương dự đoán (`salary_source == "predicted"`) tùy theo mục đích nghiên cứu.

### Tiêu cực & Biện pháp giảm thiểu:
- Phụ thuộc vào chất lượng dữ liệu của các tin có lương minh bạch để xây dựng ma trận neo.  
  *Biện pháp:* Dữ liệu từ 8 sàn có hơn 3,000 tin minh bạch về lương, tạo nên cỡ mẫu (sample size) đủ lớn và có ý nghĩa thống kê cao.
