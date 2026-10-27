# ADR 0001: Chuẩn Hóa Target Schema 11 Khóa & 100% PURE RFC 8259 JSON

- **Trạng thái:** Đã Chấp Thuận (Accepted)  
- **Ngày quyết định:** 2026-10-27  
- **Người đề xuất:** Nhóm Tiền Xử Lý Dữ Liệu (Preprocessing Engineering Team)  
- **Phạm vi ảnh hưởng:** `preprocessing/`, `data/curated/`, `reports/`

---

## 1. Ngữ Cảnh & Vấn Đề (Context)

Ban đầu, dữ liệu sau khi tích hợp từ 8 sàn tuyển dụng (`itviec`, `topcv`, `vietnamworks`, `topdev`, `jobsgo`, `careerbuilder`, `glints`, `vieclam24h`) có hơn 20 cột phẳng lẫn lộn với các thuộc tính lồng nhau tùy tiện.  
Đồng thời, quá trình tiền xử lý cũ xuất bản các tệp định dạng `.parquet` và `.csv`, dẫn đến việc xuất hiện các giá trị đặc thù như `NaN`, `null`, `Infinity`, gây xung đột với tiêu chuẩn dữ liệu RFC 8259 của REST API và làm phức tạp hóa quá trình phân tích đa nền tảng.

Do đó, nhóm kỹ thuật cần một cấu trúc dữ liệu chuẩn mực duy nhất:
1. Có tính phân cấp logic rõ ràng, dễ bảo trì, dễ mở rộng.
2. Tuân thủ 100% chuẩn Pure JSON (RFC 8259) không có bất kỳ token phi chuẩn nào.
3. Đồng thời hỗ trợ xuất bản bản ghi phẳng (Flat View) cho các thuật toán học máy (Machine Learning/Data Mining) mà không làm mất cấu trúc ngữ nghĩa gốc.

---

## 2. Quyết Định Kiến Trúc (Decision)

1. **Chuẩn hóa Target Schema Đúng 11 Khóa Gốc (Root Keys):**
   Mọi bản ghi dữ liệu vàng đều phải có chính xác 11 khóa cấp 1 sau:
   - `job_id_global`
   - `source_platform`
   - `source_url`
   - `job_info`
   - `company`
   - `locations`
   - `salary`
   - `skills`
   - `requirements`
   - `jd_text`
   - `date`

2. **Áp dụng Nguyên Tắc 100% PURE RFC 8259 JSON:**
   - Cấm hoàn toàn các token `NaN`, `Infinity`, `-Infinity`. Mọi giá trị số không xác định phải được thay bằng `null` hoặc giá trị mặc định hợp lệ theo hợp đồng dữ liệu.
   - Loại bỏ định dạng `.parquet` và `.csv` khỏi phân tầng tiền xử lý. Lưu trữ chính thức tại:
     - Dạng phân cấp (Nested): [`data/curated/golden_master.json`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/data/curated/golden_master.json)
     - Dạng bảng phẳng (Flat View): [`data/curated/curated_flat_golden_jobs.json`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/data/curated/curated_flat_golden_jobs.json)

3. **Cơ Chế Định Dạng Tập Trung Qua [`TargetSchemaFormatter`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/preprocessing/normalization/target_schema_formatter.py):**
   Mọi chuyển đổi cấu trúc schema bắt buộc phải đi qua class `TargetSchemaFormatter` để đảm bảo tính nhất quán (Single Point of Truth).

---

## 3. Hệ Quả & Lợi Ích (Consequences)

### Tích cực:
- **Tính nhất quán tuyệt đối:** Toàn bộ thành viên nhóm và các notebook phân tích đều đọc dữ liệu với cùng một cấu trúc chuẩn.
- **Tương thích hoàn hảo với Web & API:** JSON hợp lệ 100% theo RFC 8259 cho phép nạp trực tiếp vào Dashboard React/FastAPI mà không gặp lỗi parse JSON.
- **Tiện lợi cho Data Mining:** Bản ghi phẳng `curated_flat_golden_jobs.json` sẵn sàng nạp thẳng vào DuckDB, Polars hoặc Scikit-Learn mà không cần qua bước trích xuất JSON phức tạp.

### Tiêu cực & Biện pháp giảm thiểu:
- Dung lượng file JSON lớn hơn so với Parquet nhị phân nén.  
  *Biện pháp:* Dữ liệu sau khi nén zip hoặc lưu trên Object Storage vẫn đạt tỷ lệ nén cao, đồng thời tốc độ parse JSON trong Python 3.12 đủ nhanh cho quy mô hàng chục nghìn bản ghi.
