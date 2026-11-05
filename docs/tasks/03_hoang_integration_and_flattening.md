# 🧩 CẨM NANG NHIỆM VỤ: INTEGRATION & SCHEMA FLATTENING
## THÀNH VIÊN PHỤ TRÁCH: HOÀNG (THÀNH VIÊN MỚI)

> **Hạn chót hoàn thành (Deadline):** **19:00 PM Chủ Nhật**  
> **Thư mục thực hiện chính (Folder Ownership):**  
> - `preprocessing/integration/` (Chứa `json_flattener.py`, `run_integration.py`, logic schema mapping 8 sàn)  
> **Nhánh Git cá nhân:** `feature/p2-integration-flatten`  
> **Nhánh hợp nhất (Merge Destination):** `sprint/pipeline-delivery`  
> **Tài liệu đặc tả đối chiếu:** [`docs/spec/05_preprocessing_spec.md`](../spec/05_preprocessing_spec.md), [`docs/spec/06_processing_spec.md`](../spec/06_processing_spec.md), [`docs/spec/10_architecture.md`](../spec/10_architecture.md)

---

## 1. Mục Tiêu & Các Vấn Đề Cốt Lõi Cần Giải Quyết

Chào mừng Hoàng đến với nhóm! Nhiệm vụ của bạn là phụ trách **Bước 2 trong chuỗi tiền xử lý**: Đưa dữ liệu đa dạng từ 8 sàn tuyển dụng về một định dạng cấu trúc bảng thống nhất (**Target Schema**) tại tầng **Silver (Staging)**:

1. **Làm Phẳng Dữ Liệu Đa Nguồn (JSON Flattener):**
   - Mỗi sàn tuyển dụng có cấu trúc raw JSON khác nhau: TopDev trả API cấu trúc sâu, ITviec/TopCV cào từ DOM HTML, VietnamWorks dùng GraphQL.
   - Nhiệm vụ: Hoàn thiện `json_flattener.py` với các hàm trích xuất riêng biệt (`_flatten_topcv`, `_flatten_topdev`, `_flatten_vietnamworks`, v.v.) để bóc tách các trường lồng nhau thành các cột phẳng đơn giản.
2. **Hợp Nhất 8 Nguồn Về File Chuẩn `all.parquet`:**
   - Điều phối qua script `run_integration.py`: Đọc các tệp JSON thô sạch từ Bước 1, chạy qua bộ flattener, gộp lại thành một bảng dữ liệu thống nhất tại `data/preprocessing/02_integration/all.parquet`.
   - Lưu trữ định dạng **Apache Parquet (nén Snappy)** để tối ưu dung lượng và tăng tốc độ đọc cho các bước tiếp theo.
3. **Đảm Bảo Hợp Đồng Dữ Liệu (Data Contract Compliance):**
   - Mọi bản ghi trong `all.parquet` bắt buộc phải có đầy đủ các trường chuẩn:
     * `job_id` (string), `source_platform` (string - 1 trong 8 sàn), `title_raw` (string)
     * `company_name` (string), `location_raw` (string), `salary_raw` (string)
     * `experience_raw` (string), `job_description` (string), `job_requirements` (string)
     * `crawled_at` (datetime / ISO string)
4. **Kiểm Soát Tính Bảo Toàn Dữ Liệu:**
   - Tuyệt đối không để rơi rớt dữ liệu trong quá trình chuyển đổi. Xuất báo cáo tổng kết:
     $$\text{Tổng số file raw đầu vào} = \text{Số dòng ghi vào all.parquet} + \text{Số file lỗi format (kèm log chi tiết)}$$

---

## 2. Khung Prompt Chuẩn Hóa Dành Cho AI Agent

Khi Hoàng làm việc với AI Agent (Claude Code / Cursor / Antigravity), **hãy copy và sử dụng prompt mẫu sau**:

```markdown
Bạn là Kỹ sư Tích Hợp Dữ Liệu (Data Integration Engineer) phụ trách dự án VN-IT-Job-Mining.

### 1. NGỮ CẢNH & MỤC TIÊU:
Nhiệm vụ của tôi là hoàn thiện Bước 2 trong pipeline tiền xử lý: Làm phẳng dữ liệu JSON thô từ 8 sàn tuyển dụng IT (TopCV, TopDev, VietnamWorks, CareerViet, Vieclam24h, ITviec, Glints, JobsGO) và hợp nhất về một schema chuẩn hóa lưu tại `all.parquet`. Tham khảo đặc tả kỹ thuật tại docs/spec/05_preprocessing_spec.md và docs/spec/06_processing_spec.md.

### 2. RÀNG BUỘC KỸ THUẬT (CONSTRAINTS):
- Chỉ được can thiệp vào mã nguồn trong thư mục: `preprocessing/integration/`.
- Không chỉnh sửa file raw thô trên R2 hay local; raw data là tài sản bất biến (Immutable).
- Sử dụng PyArrow / Polars / Pandas để xuất file Parquet định dạng chuẩn, không để xảy ra hiện tượng cột bị ép kiểu hỗn tạp (mixed data types).
- Bắt buộc xử lý lỗi an toàn (Safe Parsing): Nếu một tin bị thiếu một trường nhỏ, gán giá trị None/null chứ không được để crash toàn bộ tiến trình gộp mẻ lớn.

### 3. HỢP ĐỒNG ĐẦU VÀO / ĐẦU RA:
- Đầu vào: Dữ liệu JSON thô tại `data/<source>/raw/`.
- Đầu ra: Tệp dữ liệu hợp nhất `data/preprocessing/02_integration/all.parquet` có đầy đủ schema chuẩn theo Data Contract.

### 4. YÊU CẦU THỰC HIỆN:
Hãy phân tích file json_flattener.py hiện có, lập Plan từng bước kiểm tra schema của từng sàn, sau đó thực hiện hoàn thiện và chạy script test kiểm chứng.
```

---

## 3. Checklist Thực Hiện & Tự Kiểm Chứng (Self-Verification)

- [ ] **Bước 1 (Đọc cấu trúc Raw):** Mở xem mẫu raw JSON của từng sàn trong `tests/fixtures/` để hiểu cấu trúc các trường lồng nhau.
- [ ] **Bước 2 (Kiểm tra Flattener):** Kiểm tra các hàm `_flatten_<source>` trong `preprocessing/integration/json_flattener.py`, đảm bảo trích xuất đúng trường tiêu đề, công ty, địa điểm, lương và mô tả.
- [ ] **Bước 3 (Chạy thử Integration):** Chạy lệnh gộp dữ liệu:
  ```bash
  python preprocessing/integration/run_integration.py
  ```
- [ ] **Bước 4 (Kiểm tra Schema & Data):** Dùng Python kiểm tra nhanh file Parquet vừa sinh ra:
  ```bash
  python -c "import pandas as pd; df = pd.read_parquet('data/preprocessing/02_integration/all.parquet'); print(df.info()); print(df.head(2))"
  ```
  Xác nhận: Có đủ 8 nguồn (`df['source_platform'].value_counts()`), không có cột lạ hay lỗi thiếu trường bắt buộc.
- [ ] **Bước 5 (Linting):** Chạy `ruff check preprocessing/integration/`.

---

## 4. Mẫu Báo Cáo Nghiệm Thu Bàn Giao (Delivery Report Template)

*Sau khi hoàn thành, Hoàng điền thông tin vào mẫu dưới đây và dán vào mô tả Pull Request khi merge vào `sprint/pipeline-delivery`:*

```markdown
### BÁO CÁO NGHIỆM THU: INTEGRATION & SCHEMA FLATTENING
- **Người thực hiện:** Hoàng
- **Nhánh làm việc:** `feature/p2-integration-flatten`
- **Thư mục can thiệp:** `preprocessing/integration/`

#### 1. Vấn Đề Gặp Phải (Problems Encountered):
- [Mô tả những sàn có cấu trúc JSON phức tạp hoặc trường dữ liệu bị thay đổi định dạng]

#### 2. Nguyên Nhân Gốc Rễ (Root Cause):
- [Giải thích sự sai lệch cấu trúc giữa các nguồn]

#### 3. Giải Pháp Kỹ Thuật Đã Triển Khai (Solution Implemented):
- [Mô tả các cập nhật trong json_flattener.py và run_integration.py]

#### 4. Bằng Chứng Tự Kiểm Chứng (Verification Proof):
- Đường dẫn file đầu ra: `data/preprocessing/02_integration/all.parquet`
- Tổng số bản ghi tích hợp: [...] dòng
- Phân bổ theo 8 nguồn:
  * TopCV: ... | TopDev: ... | VietnamWorks: ... | ITviec: ...
  * CareerViet: ... | Vieclam24h: ... | Glints: ... | JobsGO: ...
- Tỷ lệ hoàn thiện trường cốt lõi: Title: 100%, Company: 100%, JD: 100%

#### 5. Vấn Đề Còn Tồn Đọng (Remaining Issues / Blockers):
- [Ghi rõ nếu có nguồn nào cần lưu ý thêm, hoặc ghi "Không còn"]
```
