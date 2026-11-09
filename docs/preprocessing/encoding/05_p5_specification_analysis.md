# Báo Cáo Phân Tích Đặc Tả & Hợp Đồng Dữ Liệu P5 (Feature Encoding & Matrices)

> **Mã tài liệu:** `P5-SPEC-ANALYSIS-01` (Phiên bản 2.0 — Hiệu chỉnh bằng chứng & Phân loại chuẩn xác)  
> **Người thực hiện:** Hồng Phát (P5 Owner)  
> **Giai đoạn:** Chuẩn bị & Phân tích (Analysis & EDA Preparation — No Implementation)  
> **Căn cứ tài liệu:** `AGENTS.md`, `SPEC-01` đến `SPEC-13`, `docs/preprocessing/spec/P0_pipeline_contract.md`, `P4_normalization.md`, `P5_encoding.md`, `preprocessing/CLAUDE.md`, `docs/tasks/05_phat_encoding_and_matrices.md`, `docs/tasks/05_phat_encoding_implementation_contract.md`.

---

## 1. Vị Trí Của P5 Trong Toàn Bộ Pipeline

Trong kiến trúc Medallion Lakehouse của hệ thống **VN-IT-Job-Mining**, chuỗi tiền xử lý gồm 5 bước tất định (Deterministic Preprocessing, Zero-LLM theo quyết định `L-28`):
$$\text{P1 (Clean)} \longrightarrow \text{P2 (Integration)} \longrightarrow \text{P3 (Transformation)} \longrightarrow \text{P4 (Normalization)} \longrightarrow \mathbf{P5\ (Encoding)}$$

- **[Fact] (Căn cứ: `docs/preprocessing/spec/P0_pipeline_contract.md` §1):** P5 là bước chuyển giao giữa tầng Dữ liệu phẳng đã chuẩn hóa (Silver/Gold Human-Readable) và tầng Mô hình hóa học máy (Data Mining Feature Store).
- **[Fact] (Căn cứ: `docs/preprocessing/spec/P5_encoding.md` §1, §3):** P4 hoàn thiện bộ dữ liệu chuẩn hóa dạng chữ và dải số thô. P5 nhận dữ liệu từ P4 để số hóa toàn bộ không gian thuộc tính thành ma trận số học (`features.parquet`), sinh từ điển mã hóa (`encoding_dictionary.json`).
- **[Fact] (Căn cứ: `docs/tasks/05_phat_encoding_and_matrices.md` §1 và `05_phat_encoding_implementation_contract.md` §2):** Quyết định ngày 07/11/2026 đã phê duyệt ma trận kỹ năng $X$ có đúng 230 cột nhị phân và ma trận đồng xuất hiện $C = X^T X$ kích thước $230 \times 230$.

---

## 2. Hợp Đồng Dữ Liệu Đầu Vào Từ P4 (`all.parquet`)

### 2.1. Đường dẫn và định dạng dữ liệu
- **[Fact] (Căn cứ: `docs/preprocessing/spec/P5_encoding.md` §2; `preprocessing/encoding/run.py` dòng 35):** Đầu vào chuẩn của P5 là `data/preprocessing/04_normalization/all.parquet`.
- **[Fact] (Căn cứ: Kiểm tra hệ thống tệp ngày 08/11/2026):** Tệp `data/preprocessing/04_normalization/all.parquet` hiện **chưa tồn tại cục bộ** do bước P4 đang trong quá trình thực hiện.
- **[Unverified]:** Cấu trúc Arrow schema vật lý và kiểu nén chính xác của file P4 chưa thể kiểm chứng trên dữ liệu thật.

### 2.2. Danh mục các trường dữ liệu P5 sử dụng

| Tên trường | Kiểu dữ liệu logic | Nguồn gốc tạo ra | Phân loại | Căn cứ đặc tả & Ghi chú kiểm chứng |
|---|---|---|:---:|---|
| `job_id_global` | `string` | P1 $\rightarrow$ P2 | **Fact** | `docs/preprocessing/spec/P5_encoding.md` §3; `preprocessing/encoding/run.py` dòng 87. Khóa chính duy nhất, non-null. |
| `seniority` | `string` | P4 (`classify_seniority`) | **Fact** | `docs/preprocessing/spec/P5_encoding.md` §4 (E1); `preprocessing/normalization/run.py` dòng 39, 167. 6 bậc chuẩn tiếng Việt hoặc `"Chưa rõ"`. |
| `job_family` | `string` | P4 (`classify_job_family_rule`) | **Fact** | `docs/preprocessing/spec/P5_encoding.md` §4 (E2); `preprocessing/normalization/run.py` dòng 40, 183. 12 nhóm nghề chuẩn + `"Khác"`. |
| `source_platform` | `string` | P1 $\rightarrow$ P2 | **Fact** | `docs/preprocessing/spec/P5_encoding.md` §4 (E2); `preprocessing/common/__init__.py` dòng 24. Thuộc 8 sàn tuyển dụng. |
| `raw_employment_type` | `string` / nullable | P1 $\rightarrow$ P2 | **Fact** | `preprocessing/encoding/run.py` dòng 65, 126. Chuỗi hình thức làm việc từ metadata. |
| `locations` | `list[dict]` | P3 $\rightarrow$ P4 | **Conflict / Unverified** | `P5_encoding.md` §4 (E3) mô tả `locations[].tinh_key`. Tuy nhiên, nếu tệp Parquet lưu trữ `locations` dưới dạng chuỗi JSON string thì phép duyệt `hasattr(val, "__iter__")` trong Python sẽ duyệt từng ký tự thay vì từng dict. Cần xác nhận lại kiểu dữ liệu vật lý sau khi P4 xuất file. |
| `skills_std` | `list[str]` | P4 (`canonicalize_skills`) | **Conflict** | `P5_encoding.md` §4 (E4) và `SPEC-06 §3.1`. P4 chuẩn hóa dựa trên `skills.json` (hiện có 40 keys). Nếu P4 chỉ giữ các kỹ năng thuộc 40 keys này, `skills_std` sẽ không thể cung cấp đủ 230 kỹ năng chuẩn mà không có sự đồng bộ từ điển. |
| `log_salary_min`, `log_salary_max` | `float` / nullable | P4 (`apply_global_salary_normalizations`) | **Fact** | `P5_encoding.md` §4 (E5); `preprocessing/normalization/run.py` dòng 42. Giá trị số thực log hoặc NaN. Không impute mean/median (theo `AGENTS.md` và `SPEC-05 §4.2`). |
| `exp_min_years`, `exp_max_years` | `float` / nullable | P3 (`parse_experience_years`) | **Fact** | `P5_encoding.md` §4 (E5); `preprocessing/transformation/run.py` dòng 36. Giữ NaN và sinh cờ missing. |
| `headcount` | `float` / nullable | P2 $\rightarrow$ P3 | **Fact** | `P5_encoding.md` §4 (E5); `preprocessing/encoding/run.py` dòng 261. |
| `is_negotiable`, `is_outlier_salary` | `bool` / `int` | P3 & P4 | **Fact** | `P5_encoding.md` §4 (E6); `preprocessing/normalization/run.py` dòng 42. Cờ nhị phân 0/1. |
| `posted_date`, `deadline_date` | `string` (ISO date) | P1 $\rightarrow$ P3 | **Fact** | `P5_encoding.md` §4 (E7); `preprocessing/encoding/run.py` dòng 287. Trích xuất `posted_month`, `days_to_deadline`. |
| `it_rule_level`, `seniority_can_kiem`, `job_family_can_kiem` | `int` / `bool` | P1 & P4 | **Fact** | `preprocessing/encoding/run.py` dòng 308; thay thế cho xác suất JEV cũ theo chính sách Zero-LLM (L-28). |
| `description_clean`, `requirements_clean` | `string` | P3 | **Conflict** | Task 05 §1 gọi `job_description + job_requirements`; P3 sinh `description_clean` và `requirements_clean`. Xem mục 4.2. |

---

## 3. Hợp Đồng Đầu Ra Của P5

### 3.1. Bảng đặc trưng số học: `data/preprocessing/05_encoding/features.parquet`
* **[Fact] (Căn cứ: `docs/preprocessing/spec/P5_encoding.md` §3, §7):** Một dòng ứng với một bài tuyển dụng ($N_{out} = N_{in}$). Cột `job_id_global` làm khóa, mọi cột còn lại là số (`uint8`, `int8`, `int32`, `float32`).
* **[Fact] (Căn cứ: `docs/tasks/05_phat_encoding_implementation_contract.md` Approved Decision 2026-11-07):** Ma trận kỹ năng $X$ có đúng 230 cột nhị phân.

### 3.2. Ma trận đồng xuất hiện kỹ năng: `data/preprocessing/05_encoding/skill_cooccurrence.parquet`
* **[Fact] (Căn cứ: `docs/tasks/05_phat_encoding_and_matrices.md` §1; `docs/spec/06_processing_spec.md` §5.2):** Ma trận vuông đối xứng $230 \times 230$, công thức $\mathbf{C} = \mathbf{X}^T \mathbf{X}$.
* **[Conflict]:** Task 05 §1 đặt tên file là `skill_cooccurrence.parquet`, trong khi `SPEC-06 §5.2` đặt tên là `matrix_skill_cooccurrence.parquet`.

### 3.3. Từ điển mã hóa: `data/preprocessing/05_encoding/encoding_dictionary.json`
* **[Fact] (Căn cứ: `docs/preprocessing/spec/P5_encoding.md` §3, §5):** Chứa thông tin ánh xạ giải mã ngược (Seniority map, danh sách cột One-hot, Top 10 tỉnh, danh bạ 230 kỹ năng, tên cột gom kỹ năng ngoài top).

### 3.4. Báo cáo kiểm toán: `reports/preprocessing/05_encoding/_all.json`
* **[Fact] (Căn cứ: `docs/preprocessing/spec/P0_pipeline_contract.md` §4):** Báo cáo JSON ghi nhận các luật E1–E8, kiểm tra `checks.rows_conserved == True`.

---

## 4. Kiểm Chứng Bằng Chứng & Phản Biện Các Mâu Thuẫn Đặc Tả

### 4.1. Kiểm chứng kỹ thuật về tiền tố `skill_` và selector FP-Growth (`SPEC-07`)

* **[Fact] (Căn cứ: Python Semantics & `docs/spec/07_mining_spec.md` dòng 260):**  
  Đoạn mã chọn cột trong `SPEC-07`:
  ```python
  skill_cols = [c for c in self.features_df.columns if c.startswith("skill_")]
  skill_df = self.features_df[skill_cols].astype(bool)
  skill_df.columns = [c.replace("skill_", "") for c in skill_cols]
  ```
  Xét biểu thức logic trong Python:
  ```python
  "skills__other_count".startswith("skill_")  # KẾT QUẢ: False
  ```
  Do ký tự thứ 6 của `"skills__other_count"` là chữ cái `'s'`, biểu thức trả về `False`. **Vì vậy, nhận định trước đây cho rằng `skills__other_count` bị selector `startswith("skill_")` bắt nhầm là KHÔNG CHÍNH XÁC.**

* **[Conflict] (Căn cứ: `docs/tasks/05_phat_encoding_and_matrices.md` dòng 20 vs `docs/preprocessing/spec/P5_encoding.md` dòng 29 vs `docs/spec/07_mining_spec.md` dòng 263):**  
  Mâu thuẫn thực sự nằm ở **quy ước dấu gạch dưới và việc cắt chuỗi**:
  1. Task 05 (§1, dòng 20) dùng ví dụ 1 dấu gạch dưới: `skill_python`, `skill_react`.
  2. `P5_encoding.md` (mục 4, E2 & E4) và code cũ dùng 2 dấu gạch dưới: `job_family__<slug>`, `skill__<slug>`, `skills__other_count`.
  3. Trong `SPEC-07` dòng 263: Đoạn code `c.replace("skill_", "")` nếu gặp cột dạng `skill__python` (2 dấu gạch dưới) sẽ biến đổi thành `_python` (bị thừa dấu gạch dưới ở đầu tên kỹ năng khi vẽ báo cáo).
  4. Nếu lập trình viên vô tình đặt tên cột đếm là `skill__other_count` (số ít, 2 dấu gạch dưới như các cột kỹ năng), khi đó `"skill__other_count".startswith("skill_")` sẽ trả về `True` và bị bắt nhầm.
* **[Recommendation]:** Để tên kỹ năng sạch sẽ khi hiển thị trên đồ thị FP-Growth và tránh mọi rủi ro bắt nhầm:
  - 230 cột kỹ năng nên thống nhất dùng tiền tố `skill_<slug>` (khớp Task 05 và `c.replace("skill_", "")`).
  - Cột đếm kỹ năng ngoài top nên giữ nguyên là `skills__other_count` (theo `P5_encoding.md`) hoặc `other_skills_count` để không bao giờ khớp tiền tố `skill_`.

### 4.2. Mâu thuẫn quyền sở hữu và kích thước TF-IDF

* **[Conflict] (Căn cứ đối chiếu 4 tài liệu):**
  1. `docs/tasks/05_phat_encoding_and_matrices.md` §1: Yêu cầu P5 dùng `TfidfVectorizer` trích xuất Top 2.000 – 3.000 từ khóa từ `job_description + job_requirements`.
  2. `docs/spec/06_processing_spec.md` §5.3: Yêu cầu `max_features = 3000` thuộc tính n-gram $(1, 2)$.
  3. `docs/preprocessing/spec/P5_encoding.md` §4: Quy định: *"Văn bản JD không mã hóa ở đây (TF-IDF/embedding làm ở phần phân tích)"*.
  4. `docs/spec/07_mining_spec.md` §3.1: Module K-Means của Phúc chỉ yêu cầu $K = 100$ đặc trưng n-gram quan trọng nhất.
* **[Recommendation]:** Không gộp các cột TF-IDF vào `features.parquet` vì sẽ làm tăng kích thước tệp không cần thiết cho các thuật toán tabular (FP-Growth, Random Forest). Tách TF-IDF thành utility riêng hoặc artifact độc lập nếu nhóm Mining yêu cầu.

### 4.3. Quyền sở hữu tệp `curated_flat_golden_jobs.parquet`

* **[Conflict] (Căn cứ: Task 05 §1 dòng 28 vs `docs/preprocessing/spec/P5_encoding.md` §1, §5):**
  - Task 05 ghi P5 xuất bản `data/curated/curated_flat_golden_jobs.parquet`.
  - `P5_encoding.md` §1, §5 khẳng định: *"Bộ golden (output P4) vẫn là bản cho người đọc. Encoding chỉ đọc bộ golden, không sửa nó."*
* **[Recommendation]:** P4 chịu trách nhiệm xuất bản Golden Dataset cho người đọc; P5 chỉ xuất bản Feature Store (`features.parquet`) và các ma trận đặc trưng.

### 4.4. Mâu thuẫn tiền tố đặc trưng cho mô hình Random Forest (`SPEC-07`)

* **[Conflict] (Căn cứ: `docs/spec/07_mining_spec.md` dòng 322 vs `preprocessing/encoding/run.py` dòng 93, 108, 179):**
  - Trong `SPEC-07` dòng 322, mã nguồn tham chiếu lọc:
    ```python
    feature_cols = [c for c in df_valid.columns if c.startswith(("skill_", "exp_", "sen_", "loc_", "jf_"))]
    ```
  - Trong khi đó, P5 hiện tại sinh ra: `seniority_ord` (không có `sen_`), `job_family__<slug>` (không có `jf_`), `tinh__<slug>` (không có `loc_`).
* **[Recommendation]:** Cần thống nhất danh bạ tên cột đầu vào của Random Forest giữa P5 và Mining trước khi chạy thử nghiệm mô hình hồi quy lương.

---

## 5. Kết Luận & Giới Hạn Của Báo Cáo

1. **[Fact]:** Mọi nhận định kỹ thuật trong báo cáo này đều đã được đối chiếu trực tiếp với mã nguồn và văn bản đặc tả hiện hành.
2. **[Unverified]:** Số lượng kỹ năng thực tế đạt tần suất $\ge 20$ và phân bổ giữa 6 nhóm ngành công nghệ hoàn toàn chưa thể xác định do dataset P4 chưa sẵn sàng.
3. **Giới hạn:** Báo cáo dừng lại ở phân tích và phản biện; không tự ý thay đổi code triển khai hay quyết định các vấn đề còn bỏ ngỏ.
