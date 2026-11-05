# ⚙️ CẨM NANG NHIỆM VỤ: TRANSFORMATION & NORMALIZATION
## THÀNH VIÊN PHỤ TRÁCH: DUY

> **Hạn chót hoàn thành (Deadline):** **19:00 PM Chủ Nhật**  
> **Thư mục thực hiện chính (Folder Ownership):**  
> - `preprocessing/transformation/` (Bóc tách lương `salary_parser.py`, kinh nghiệm `experience_parser.py`)  
> - `preprocessing/normalization/` (Chuẩn hóa 34 tỉnh/thành, phân loại 12 Job Family)  
> - `preprocessing/dictionaries/` (Bộ từ điển kỹ năng `skills.json`, tỉnh thành `provinces_34.json`, alias mapping)  
> **Nhánh Git cá nhân:** `feature/p3-p4-transform-normalize`  
> **Nhánh hợp nhất (Merge Destination):** `sprint/pipeline-delivery`  
> **Tài liệu đặc tả đối chiếu:** [`docs/spec/06_processing_spec.md`](../spec/06_processing_spec.md), [`docs/spec/05_preprocessing_spec.md`](../spec/05_preprocessing_spec.md)

---

## 1. Mục Tiêu & Các Vấn Đề Cốt Lõi Cần Giải Quyết

Duy chịu trách nhiệm về "Trái tim tính toán thuộc tính" (Bước 3 & Bước 4 trong chuỗi tiền xử lý). Đây là khâu biến đổi chuỗi văn bản tự do thành các thuộc tính số học và định danh chuẩn mực:

1. **Chuẩn Hóa Mức Lương Khoa Học (`salary_parser.py`):**
   - *Bóc tách dải lương:* Xử lý các mẫu câu phức tạp: "15 - 25 triệu", "1.000 - 2.500 USD", "Up to 50M", "Từ 20tr", "Thỏa thuận", "Thương lượng".
   - *Quy chuẩn đơn vị duy nhất:* **Triệu VNĐ / Tháng** (`salary_min`, `salary_max`, `salary_avg = (min + max)/2`).
   - *Tỷ giá quy đổi:* Cố định **1 USD = 25.400 VNĐ**. Lương năm chia 12, lương ngày nhân 22.
   - *Xử lý 55% lương Thỏa thuận:* **Tuyệt đối cấm gán mean/median giả tạo**. Đánh dấu cờ `is_negotiable = True` và tách phân tầng rõ ràng (Subset A có lương số dùng mô hình hóa lương; Subset B toàn bộ dữ liệu dùng khai phá kỹ năng).
2. **Chuẩn Hóa Kinh Nghiệm & Cấp Bậc (Seniority):**
   - Bóc tách số năm kinh nghiệm (`exp_min_years`, `exp_max_years`).
   - Gán cấp bậc chuẩn hóa (Seniority Level: 0 = Intern/Fresher, 1 = Junior, 2 = Middle, 3 = Senior, 4 = Lead/Manager).
3. **Chuẩn Hóa Địa Lý 34 Tỉnh Thành Mới:**
   - Sử dụng từ điển `provinces_34.json` để chuẩn hóa các biến thể chuỗi ("TP HCM", "TP. Hồ Chí Minh", "Sài Gòn", "HN", "Hà Nội", "Hòa Lạc") về tên chuẩn cấp tỉnh/thành phố.
4. **Chuẩn Hóa 12 Nhóm Ngành IT & Bộ Từ Điển Kỹ Năng (Skill Taxonomy):**
   - Gán nhãn 12 Job Family chuẩn: Backend, Frontend, Fullstack, Mobile, DevOps/Cloud, Data/AI, QA/QC, Security, BA, Product, System, Embedded.
   - Sử dụng từ điển kỹ năng có phân cấp (Category $\rightarrow$ Canonical Skill $\rightarrow$ Aliases). Chuẩn hóa các alias: `golang`/`go` $\rightarrow$ `Go`, `k8s` $\rightarrow$ `Kubernetes`, `reactjs` $\rightarrow$ `React`. Trích xuất mảng kỹ năng sạch `skills_extracted`.

---

## 2. Khung Prompt Chuẩn Hóa Dành Cho AI Agent

Khi Duy làm việc với AI Agent (Claude Code / Cursor / Antigravity), **hãy copy và sử dụng prompt mẫu sau**:

```markdown
Bạn là Kỹ sư Kỹ thuật Đặc trưng (Feature Engineering & Transformation Specialist) phụ trách dự án VN-IT-Job-Mining.

### 1. NGỮ CẢNH & MỤC TIÊU:
Nhiệm vụ của tôi là hoàn thiện Bước 3 và Bước 4 trong pipeline: Bóc tách và chuẩn hóa mức lương (salary_parser.py), kinh nghiệm/cấp bậc, chuẩn hóa địa danh theo 34 tỉnh thành mới, phân loại 12 Job Family và chuẩn hóa kỹ năng qua bộ từ điển taxonomy. Tham khảo đặc tả kỹ thuật tại docs/spec/06_processing_spec.md.

### 2. RÀNG BUỘC KỸ THUẬT (CONSTRAINTS):
- Chỉ được can thiệp vào mã nguồn trong thư mục: `preprocessing/transformation/`, `preprocessing/normalization/`, `preprocessing/dictionaries/`.
- Tuyệt đối KHÔNG gán giá trị trung bình/trung vị giả tạo cho các tin có lương "Thỏa thuận" (~55% bài đăng). Bắt buộc phân tầng (Stratified Partitioning) để bảo toàn phân phối thật.
- Chuẩn hóa đơn vị lương duy nhất: Triệu VNĐ / Tháng (1 USD = 25.400 VNĐ).
- Xử lý kỹ năng tên ngắn (C, R, Go, AI) bằng Regex Context-Aware Boundary Matching để tránh nhận diện nhầm từ tiếng Anh thông thường.

### 3. HỢP ĐỒNG ĐẦU VÀO / ĐẦU RA:
- Đầu vào: File Parquet tầng Silver `data/preprocessing/02_integration/all.parquet`.
- Đầu ra: File Parquet tầng Transformation & Normalization `data/preprocessing/04_normalization/all.parquet` bổ sung các cột: `salary_min`, `salary_max`, `salary_avg`, `is_negotiable`, `exp_min_years`, `seniority_level`, `city_normalized`, `job_family`, `skills_extracted`.

### 4. YÊU CẦU THỰC HIỆN:
Hãy lập Plan chi tiết từng hàm xử lý (salary regex, experience parser, skill taxonomy lookup), sau đó thực hiện và chạy kiểm thử với các ca biên phức tạp.
```

---

## 3. Checklist Thực Hiện & Tự Kiểm Chứng (Self-Verification)

- [ ] **Bước 1 (Salary Parser Test):** Viết unit test cho các ca lương khó:
  * "15 - 20 triệu" $\rightarrow$ min: 15.0, max: 20.0, avg: 17.5
  * "$1,500 - $3,000" $\rightarrow$ min: 38.1, max: 76.2, avg: 57.15
  * "Lên đến 40 triệu" $\rightarrow$ min: None, max: 40.0, avg: 40.0
  * "Thỏa thuận" $\rightarrow$ is_negotiable = True, min/max = None
- [ ] **Bước 2 (Location Normalizer):** Kiểm tra tỷ lệ map thành công địa chỉ vào danh mục 34 tỉnh/thành, đảm bảo không có địa chỉ bị null vô lý.
- [ ] **Bước 3 (Skill Taxonomy Matching):** Kiểm tra bộ trích xuất kỹ năng trên 50 tin JD mẫu: Đảm bảo không bắt nhầm chữ "Go" trong "Good communication" thành ngôn ngữ Go.
- [ ] **Bước 4 (Chạy toàn trình Bước 3 & 4):**
  ```bash
  python preprocessing/transformation/run_transformation.py
  python preprocessing/normalization/run_normalization.py
  ```
- [ ] **Bước 5 (Linting):** Chạy `ruff check preprocessing/transformation/ preprocessing/normalization/`.

---

## 4. Mẫu Báo Cáo Nghiệm Thu Bàn Giao (Delivery Report Template)

*Sau khi hoàn thành, Duy điền thông tin vào mẫu dưới đây và dán vào mô tả Pull Request khi merge vào `sprint/pipeline-delivery`:*

```markdown
### BÁO CÁO NGHIỆM THU: TRANSFORMATION & NORMALIZATION
- **Người thực hiện:** Duy
- **Nhánh làm việc:** `feature/p3-p4-transform-normalize`
- **Thư mục can thiệp:** `preprocessing/transformation/`, `preprocessing/normalization/`, `preprocessing/dictionaries/`

#### 1. Vấn Đề Gặp Phải (Problems Encountered):
- [Mô tả các mẫu câu lương dị biệt hoặc các từ khóa kỹ năng dễ nhận diện nhầm]

#### 2. Nguyên Nhân Gốc Rễ (Root Cause):
- [Giải thích sự phức tạp của ngôn ngữ tự nhiên trong JD]

#### 3. Giải Pháp Kỹ Thuật Đã Triển Khai (Solution Implemented):
- [Trình bày regex cascade trong salary_parser.py và context-boundary trong skill extraction]

#### 4. Bằng Chứng Tự Kiểm Chứng (Verification Proof):
- Tỷ lệ tin bóc tách lương thành công (có số cụ thể): [...]% (trung bình thị trường: ~45%)
- Tỷ lệ tin thỏa thuận (is_negotiable = True): [...]% (khoảng ~55%)
- Phân phối phổ lương sau chuẩn hóa (Triệu VNĐ): Min: ... | Median: ... | Max: ...
- Số lượng kỹ năng chuẩn hóa trong từ điển: [...] kỹ năng
- Số lượng Job Family được gán nhãn: 12 nhóm

#### 5. Vấn Đề Còn Tồn Đọng (Remaining Issues / Blockers):
- [Ghi rõ nếu còn ca đặc biệt nào chưa parse được, hoặc ghi "Không còn"]
```
