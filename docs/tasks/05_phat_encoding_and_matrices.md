# 🔢 CẨM NANG NHIỆM VỤ: FEATURE ENCODING & MATRICES
## THÀNH VIÊN PHỤ TRÁCH: HỒNG PHÁT

> **Hạn chót hoàn thành (Deadline):** **19:00 PM Chủ Nhật**  
> **Thư mục thực hiện chính (Folder Ownership):**  
> - `preprocessing/encoding/` (Mã hóa nhị phân 230 cột kỹ năng, sinh ma trận đồng xuất hiện, TF-IDF matrix, xuất bản tầng Gold)  
> **Nhánh Git cá nhân:** `feature/p5-encoding-matrices`  
> **Nhánh hợp nhất (Merge Destination):** `sprint/pipeline-delivery`  
> **Tài liệu đặc tả đối chiếu:** [`docs/spec/06_processing_spec.md`](../spec/06_processing_spec.md), [`docs/spec/07_mining_spec.md`](../spec/07_mining_spec.md), [`docs/spec/10_architecture.md`](../spec/10_architecture.md)

---

## 1. Mục Tiêu & Các Vấn Đề Cốt Lõi Cần Giải Quyết

Phát chịu trách nhiệm chốt chặn công đoạn cuối cùng của chuỗi Tiền xử lý (Bước 5: Encoding) để tạo ra tập dữ liệu **Golden Master Parquet** và các ma trận đặc trưng số hóa sẵn sàng cho nhóm Data Mining huấn luyện mô hình:

1. **Mã Hóa Nhị Phân Ma Trận 230 Cột Kỹ Năng (Multi-Hot Binary Encoding):**
   - Từ mảng kỹ năng đã bóc tách `skills_extracted`, chọn lọc danh mục **230 kỹ năng IT chuẩn** (bao quát đầy đủ 6 nhóm: Ngôn ngữ lập trình, Frameworks, Cơ sở dữ liệu, Cloud/DevOps, Công cụ, Kỹ năng mềm).
   - Mã hóa thành ma trận nhị phân $M \times 230$ (giá trị $1$ nếu bài đăng yêu cầu kỹ năng, $0$ nếu không).
   - Đặt tên cột tiền tố chuẩn hóa (ví dụ: `skill_python`, `skill_react`, `skill_docker`, `skill_aws`...).
2. **Xây Dựng Ma Trận Đồng Xuất Hiện Kỹ Năng (Skill Co-occurrence Matrix):**
   - Tính toán ma trận vuông đối xứng kích thước $230 \times 230$:
     $$\mathbf{C} = \mathbf{X}^T \mathbf{X}$$
   - Trong đó phần tử $C_{ij}$ biểu thị số lượng bài đăng tuyển dụng đồng thời yêu cầu cả kỹ năng $i$ và kỹ năng $j$. Ma trận này là đầu vào trực tiếp cho việc vẽ Network Graph và phân tích cộng đồng công nghệ.
3. **Trích Xuất Ma Trận Văn Bản TF-IDF Phục Vụ Phân Cụm:**
   - Dùng `TfidfVectorizer` (Scikit-learn) trích xuất không gian đặc trưng văn bản từ trường `job_description` + `job_requirements` (giới hạn Top 2.000 – 3.000 từ khóa sau khi lọc bỏ stopwords song ngữ Anh - Việt).
4. **Xuất Bản Tệp Tầng Gold (Feature Store):**
   - Xuất bản tệp hoàn chỉnh: `data/curated/curated_flat_golden_jobs.parquet` (kết hợp các thuộc tính bài đăng và 230 cột kỹ năng).
   - Xuất bản tệp đặc trưng số: `data/preprocessing/05_encoding/features.parquet`.
   - Lưu trữ danh bạ ánh xạ index $\rightarrow$ tên kỹ năng: `data/preprocessing/05_encoding/encoding_dictionary.json`.

---

## 2. Khung Prompt Chuẩn Hóa Dành Cho AI Agent

Khi Phát làm việc với AI Agent (Claude Code / Cursor / Antigravity), **hãy copy và sử dụng prompt mẫu sau**:

```markdown
Bạn là Kỹ sư Mã hóa Dữ liệu (Data Encoding & Feature Engineer) phụ trách dự án VN-IT-Job-Mining.

### 1. NGỮ CẢNH & MỤC TIÊU:
Nhiệm vụ của tôi là hoàn thiện Bước 5 trong pipeline tiền xử lý: Triển khai Multi-Hot Encoding cho 230 cột kỹ năng IT, sinh ma trận đồng xuất hiện (Skill Co-occurrence Matrix 230x230), trích xuất ma trận TF-IDF cho văn bản JD, và xuất bản tệp dữ liệu vàng Golden Master Parquet sẵn sàng cho nhóm Data Mining. Tham khảo đặc tả kỹ thuật tại docs/spec/06_processing_spec.md và docs/spec/07_mining_spec.md.

### 2. RÀNG BUỘC KỸ THUẬT (CONSTRAINTS):
- Chỉ được can thiệp vào mã nguồn trong thư mục: `preprocessing/encoding/`.
- Tối ưu hóa bộ nhớ RAM: Vì ma trận 230 cột có độ thưa (sparsity) cao (~97%), phải sử dụng định dạng nhị phân kiểu uint8/int8 hoặc sparse matrix của Scipy khi tính toán, xuất ra file Parquet nén Snappy.
- Đảm bảo tính tái lập 100%: Thứ tự các cột kỹ năng phải được cố định tuyệt đối qua tệp `encoding_dictionary.json`.
- Tuân thủ Python 3.12, sử dụng Scikit-learn, Numpy, Pandas / Polars.

### 3. HỢP ĐỒNG ĐẦU VÀO / ĐẦU RA:
- Đầu vào: File Parquet tầng Normalization `data/preprocessing/04_normalization/all.parquet`.
- Đầu ra:
  * `data/curated/curated_flat_golden_jobs.parquet` (Bảng dữ liệu vàng tích hợp)
  * `data/preprocessing/05_encoding/features.parquet` (Bảng đặc trưng huấn luyện)
  * `data/preprocessing/05_encoding/skill_cooccurrence.parquet` (Ma trận 230x230)
  * `data/preprocessing/05_encoding/encoding_dictionary.json` (Bảng tra cứu)

### 4. YÊU CẦU THỰC HIỆN:
Hãy lập Plan chi tiết cho việc chọn lọc 230 kỹ năng, thuật toán vector hóa, sau đó thực hiện mã nguồn và kiểm chứng kích thước, độ thưa của ma trận.
```

---

## 3. Checklist Thực Hiện & Tự Kiểm Chứng (Self-Verification)

- [ ] **Bước 1 (Chọn lọc 230 kỹ năng):** Đếm tần suất các kỹ năng trích xuất được từ tầng Normalization; chọn ra Top 230 kỹ năng có độ phủ tốt nhất, phân bổ đều trên cả 6 nhóm danh mục.
- [ ] **Bước 2 (Multi-Hot Matrix Test):** Kiểm tra ma trận nhị phân:
  * Số cột đúng bằng 230 (tiền tố `skill_`).
  * Giá trị chỉ gồm $\{0, 1\}$.
  * Kiểm tra độ thưa: Sparsity $=\frac{\text{Số giá trị 0}}{\text{Tổng số phần tử}} \approx 95\% - 98\%$.
- [ ] **Bước 3 (Co-occurrence Test):** Kiểm tra tính đối xứng của ma trận đồng xuất hiện: $\mathbf{C} = \mathbf{C}^T$. Phần tử đường chéo $C_{ii}$ đúng bằng số lần xuất hiện của kỹ năng $i$.
- [ ] **Bước 4 (Xuất bản Parquet Gold):** Chạy driver mã hóa:
  ```bash
  python preprocessing/encoding/run_encoding.py
  ```
  Kiểm tra kích thước file Parquet đầu ra nén tốt ($< 25\text{MB}$) và đọc thử bằng Pandas trong $< 0.3\text{s}$.
- [ ] **Bước 5 (Linting):** Chạy `ruff check preprocessing/encoding/`.

---

## 4. Mẫu Báo Cáo Nghiệm Thu Bàn Giao (Delivery Report Template)

*Sau khi hoàn thành, Phát điền thông tin vào mẫu dưới đây và dán vào mô tả Pull Request khi merge vào `sprint/pipeline-delivery`:*

```markdown
### BÁO CÁO NGHIỆM THU: FEATURE ENCODING & MATRICES
- **Người thực hiện:** Hồng Phát
- **Nhánh làm việc:** `feature/p5-encoding-matrices`
- **Thư mục can thiệp:** `preprocessing/encoding/`

#### 1. Vấn Đề Gặp Phải (Problems Encountered):
- [Mô tả thách thức khi quản lý ma trận thưa 230 chiều hoặc tối ưu RAM khi sinh file]

#### 2. Nguyên Nhân Gốc Rễ (Root Cause):
- [Giải thích hiện tượng phình to dữ liệu nếu không nén cột]

#### 3. Giải Pháp Kỹ Thuật Đã Triển Khai (Solution Implemented):
- [Trình bày thuật toán Multi-Hot, nhân ma trận đồng xuất hiện và xuất Parquet Snappy]

#### 4. Bằng Chứng Tự Kiểm Chứng (Verification Proof):
- Kích thước tập dữ liệu vàng Golden Master: [...] dòng $\times$ [...] cột
- Số lượng cột kỹ năng được mã hóa nhị phân: 230 cột
- Độ thưa của ma trận kỹ năng (Sparsity): [...]%
- Kích thước file Parquet trên đĩa: [...] MB
- Top 5 cặp kỹ năng có tần suất đồng xuất hiện cao nhất:
  1. [Kỹ năng A] - [Kỹ năng B]: ... tin
  2. [Kỹ năng C] - [Kỹ năng D]: ... tin

#### 5. Vấn Đề Còn Tồn Đọng (Remaining Issues / Blockers):
- [Ghi rõ nếu có kỹ năng quan trọng nào bị bỏ sót, hoặc ghi "Không còn"]
```
