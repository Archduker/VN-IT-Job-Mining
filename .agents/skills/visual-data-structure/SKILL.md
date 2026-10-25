---
name: eda-notebook-architect
description: >-
  Chuyên gia kiến tạo, bảo trì và kiểm định toàn diện 8 Jupyter Notebooks EDA đơn nguồn (collection/collection/reports/EDA_<source>.ipynb) cho hệ thống VN-IT-Job-Mining.
  Hiện thực hóa chuẩn mực: 5 trụ cột chất lượng dữ liệu thô (Completeness, Validity, Uniqueness, Distribution, Bias),
  mô hình chẩn đoán kỹ thuật WHAT - WHY - HOW, bóc trần null marker trá hình, chuẩn hóa dải lương đa tiền tệ (VND/USD),
  và trực quan hóa 100% inline chất lượng cao (plt.show() base64) bảo toàn nguyên lý Zero Information Loss.
---
# 📓 EDA Notebook Architect Skill
Kỹ năng này quy định quy chuẩn kỹ thuật toàn diện, phương pháp luận thực thi và mã nguồn tự động hóa để xây dựng, tái tạo và kiểm định **8 file Jupyter Notebooks EDA đơn nguồn (`collection/collection/reports/EDA_<source>.ipynb`)** cho hệ sinh thái dữ liệu tuyển dụng IT tại Việt Nam (**VN-IT-Job-Mining**).
---
## 1. Triết Lý Thiết Kế & Nền Tảng Kỹ Thuật
Mỗi notebook trong thư mục `collection/reports/` phải tuân thủ nghiêm ngặt 4 nguyên tắc chỉ đạo:
1. **Khám Phá Đi Lên Từ Câu Hỏi (Inquiry-Driven Framework):**  
   - Notebook **không phải là bản tin thị trường hay phân tích kinh tế vĩ mô**.  
   - Notebook là **"Kính hiển vi chẩn đoán chất lượng dữ liệu thô"**, tập trung kiểm kê lỗi kỹ thuật, đo độ lệch, và đưa ra khuyến nghị tiền xử lý theo chuẩn [01_huong_dan_eda_nhom_3_nguoi.md](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/docs/tasks/01_huong_dan_eda_nhom_3_nguoi.md).
2. **Nguyên Lý Bảo Toàn Thông Tin Tuyệt Đối (Zero Information Loss):**  
   - Dữ liệu nạp trực tiếp từ Lakehouse snapshot thông qua `scripts.lakehouse_loader.load_raw_source_dataframe`.  
   - Giữ nguyên vẹn cả hai thành phần của phong bì dữ liệu thô: `metadata` (mã băm SHA-256, URL gốc, phiên bản crawler) và `raw_payload` (100% trường nguyên bản của từng sàn).
3. **Mô Hình Chẩn Đoán 3 Tầng WHAT — WHY — HOW:**  
   - Dưới mỗi biểu đồ và bảng kiểm kê, bắt buộc phải có khối Markdown chẩn đoán kỹ thuật theo cẩm nang [02_huong_dan_insight_va_so_sanh_nguon.md](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/docs/tasks/02_huong_dan_insight_va_so_sanh_nguon.md):
     - **WHAT:** Sàn này thiếu gì? Lỗi ở đâu? Tỷ lệ khuyết thiếu bao nhiêu?
     - **WHY:** Do thiết kế form UI của sàn, chiến lược kinh doanh của sàn hay do hạn chế crawler?
     - **HOW:** Hậu quả nếu không xử lý và chiến lược bù trừ/tiền xử lý (Imputation, Winsorization, Log-transform, Master Source Priority).
4. **Trực Quan Hóa 100% Inline (No Disk Clutter):**  
   - Biểu đồ phải được render trực tiếp bên trong notebook bằng `plt.show()` (mã hóa Base64 png inline).  
   - Không xuất file ảnh rời rác vào thư mục gốc trừ khi có yêu cầu đặc thù phục vụ xuất bản báo cáo.
---
## 2. Cấu Trúc 7 Chương Chuẩn Mực Trong Mỗi Notebook
Mỗi file `collection/collection/reports/EDA_<source>.ipynb` bắt buộc chứa đủ 7 chương logic:
```
collection/collection/reports/EDA_<source>.ipynb
├── Chương 0: Header, Ngữ Cảnh & Bản Ghi JSON Thô Mẫu (Raw Envelope: Metadata + Payload)
├── Chương 1: Khảo Sát Cấu Trúc Nguyên Bản & Kiểm Kê Trường (Field Inventory Table)
├── Chương 2: Trụ Cột 1 — Độ Hoàn Thiện & Bóc Trần Null Marker Trá Hình (Completeness)
├── Chương 3: Trụ Cột 2 — Tính Hợp Lệ, Ép Kiểu & Bóc Tách Cấu Trúc Phức Hợp (Validity)
├── Chương 4: Trụ Cột 3 — Tính Duy Nhất & Phát Hiện Trùng Lặp 3 Tầng (Uniqueness)
├── Chương 5: Trụ Cột 4 — Hình Thái Phân Phối, Độ Lệch & Ngoại Lai Định Lượng (Distribution)
├── Chương 6: Trụ Cột 5 — Độ Thiên Lệch & Tính Mất Cân Bằng Mẫu (Bias & Class Balance)
└── Chương 7: Bệnh Án Dữ Liệu Toàn Nguồn & Bản Thiết Kế Tiền Xử Lý (Health Card & Blueprint)
```
---