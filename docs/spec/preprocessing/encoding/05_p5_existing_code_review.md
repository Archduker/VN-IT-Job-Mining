# Báo Cáo Đánh Giá Hiện Trạng Mã Nguồn P5 & Kiểm Tra Taxonomy

> **Mã tài liệu:** `P5-CODE-REVIEW-02` (Phiên bản 2.0 — Hiệu chỉnh bằng chứng & Phân loại chuẩn xác)  
> **Người thực hiện:** Hồng Phát (P5 Owner)  
> **Giai đoạn:** Chuẩn bị & Phân tích (Analysis & EDA Preparation — No Implementation)  
> **Phạm vi đánh giá:** 4 tệp mã nguồn P5 (`skills_taxonomy_230.py`, `run_encoding.py`, `run.py`, `tfidf_extractor.py`) và tệp từ điển `preprocessing/dictionaries/skills.json`.

---

## 1. Kiểm Tra & Đánh Giá Hiện Trạng Taxonomy Kỹ Năng (`skills.json`)

### 1.1. Cấu trúc hiện tại của `preprocessing/dictionaries/skills.json`
* **[Fact] (Căn cứ: Kiểm tra trực tiếp tệp `skills.json` dòng 1–244):** Tệp hiện tại chứa **đúng 40 canonical skill keys** (ví dụ: `Python`, `Java`, `React`, `Docker`, `Kubernetes`, `AWS`, `Machine Learning`,...).
* **[Fact] (Căn cứ: Cấu trúc JSON):** Dữ liệu tổ chức dạng phẳng `dict[str, list[str]]`, trong đó:
  - Khóa (Key): Tên kỹ năng chuẩn (Canonical Name, viết hoa).
  - Giá trị (Value): Mảng các chuỗi biến thể (Aliases / Synonyms / Framework con).
* **[Fact]:** `skills.json` hiện tại **không có trường phân nhóm** (chưa phân chia thành 6 nhóm IT như mô tả trong `SPEC-06 §3.1`).
* **[Conflict]:** Một số canonical keys trong `skills.json` gom nhiều công nghệ riêng biệt vào một nhóm (ví dụ: key `"Machine Learning"` chứa cả `"tensorflow"`, `"pytorch"`, `"scikit-learn"`). Trong khi đó, ở tầng khai phá luật kết hợp (`SPEC-07 §2.3`), `PyTorch` và `TensorFlow` là các công nghệ độc lập cần được phân tích riêng biệt để tìm combo kỹ năng chuyên sâu.

### 1.2. Khả năng ánh xạ giữa dữ liệu P4 và Taxonomy
* **[Fact] (Căn cứ: `preprocessing/normalization/text_cleaner.py` dòng 269–293):**  
  Hàm chuẩn hóa tại P4 (`canonicalize_skills`) sử dụng `skills.json` để ánh xạ từ `skills_clean` về `skills_std`. Nếu kỹ năng không thuộc 40 keys, nó được giữ nguyên dạng chuỗi text thô:
  ```python
  canon = lookup.get(s_clean.lower(), s_clean)
  ```
* **[Fact]:** Dữ liệu `skills_std` mà P4 xuất ra sẽ là một tập hợp hỗn hợp: gồm 40 kỹ năng chuẩn đã canonicalize và các chuỗi kỹ năng tự do chưa qua chuẩn hóa.

### 1.3. Lỗ hổng kỹ thuật đối với yêu cầu "Multi-Hot có chính xác 230 cột"
* **[Fact] (Căn cứ: Approved Decision 2026-11-07 trong `05_phat_encoding_implementation_contract.md` §2):** Ma trận kỹ năng $X$ bắt buộc phải có **chính xác 230 cột nhị phân**.
* **[Conflict]:** `skills.json` chỉ có 40 keys. Do đó, nếu chỉ dựa vào taxonomy hiện tại, không thể đạt được 230 cột kỹ năng mà không có cơ chế mở rộng taxonomy hoặc chọn lọc từ tần suất thực tế.
* **[Unverified]:** Khi chưa có dataset P4 thật, hoàn toàn chưa thể xác minh có bao nhiêu kỹ năng trên thị trường tuyển dụng đạt ngưỡng tần suất $\ge 20$ tin để đưa vào danh mục 230. Mọi danh sách 230 kỹ năng được hardcode trước khi chạy Data Profiling đều chỉ mang tính chất **Prototype / Giả định kỹ thuật**.

---

## 2. Đánh Giá Chi Tiết 4 Tệp Mã Nguồn P5 Hiện Tại

> **Lưu ý đồng bộ tên file [Fact]:** Trong yêu cầu nhiệm vụ, tên tệp được gọi là `skill_taxonomy_230.py` (số ít), trong khi tệp thực tế đang lưu trên đĩa là `preprocessing/encoding/skills_taxonomy_230.py` (số nhiều có chữ `'s'`). Báo cáo này đánh giá tệp thực tế trên đĩa.

---

### 2.1. Đánh giá tệp `preprocessing/encoding/skills_taxonomy_230.py`

#### 1. Mục đích và chức năng hiện tại
* **[Fact]:** Định nghĩa danh mục mẫu gồm 230 kỹ năng IT phân bổ theo 6 nhóm ngành công nghệ của `SPEC-06 §3.1`:
  - 35 Ngôn ngữ lập trình (`programming_languages`)
  - 55 Framework & Thư viện (`frameworks_libraries`)
  - 35 Cơ sở dữ liệu & Streaming (`databases_streaming`)
  - 45 Đám mây, Hạ tầng, An ninh & DevOps (`cloud_devops_security`)
  - 35 Công cụ, Kiến trúc, Giao thức & QA (`tools_architecture_qa`)
  - 25 Phương pháp luận, Kỹ năng mềm & Data/AI (`methodologies_softskills_data`)
* **[Fact]:** Cung cấp danh sách thứ tự cố định `ORDERED_SKILL_COLUMNS` và bảng tra cứu `SKILL_LOOKUP_MAP`.

#### 2. Logic xử lý chính
* **[Fact]:** Sử dụng `NamedTuple` `SkillEntry(index, canonical, slug, column_name, group, aliases)` lưu metadata.
* **[Fact]:** Tên cột tiền tố `skill_<slug>` (chữ thường, ngăn cách 1 dấu gạch dưới).

#### 3. Những giả định thiết kế đang được sử dụng
* **[Unverified]:** Giả định rằng 230 kỹ năng này sẽ có tần suất xuất hiện đủ lớn trên dữ liệu thật của 8 sàn.
* **[Recommendation]:** Giả định hạn ngạch phân bổ số lượng cố định cho 6 nhóm (35, 55, 35, 45, 35, 25) để đảm bảo tính bao quát, nhưng đây chưa phải là quy định bắt buộc trong SPEC gốc.

#### 4. Mức độ phù hợp với đặc tả hiện tại
* **[Fact]:** Đáp ứng chính xác yêu cầu chiều rộng 230 cột và bao phủ 6 nhóm của `docs/tasks/05_phat_encoding_and_matrices.md` §1.
* **[Conflict]:** `SPEC-06 §5.1` ban đầu chỉ định top $K \in [100, 200]$; danh mục 230 kỹ năng là quyết định mới hơn (Approved Decision 2026-11-07).

#### 5. Những điểm cần kiểm tra lại sau khi có dữ liệu P4
* **[Unverified]:** Cần đo tần suất thực tế của 230 kỹ năng này trên dataset P4 để phát hiện các kỹ năng có tần suất $= 0$ (cột toàn số 0).

#### 6. Đề xuất
* **[Recommendation]:** **GIỮ LÀM PROTOTYPE THAM CHIẾU**, cập nhật danh sách kỹ năng chính thức sau khi hoàn thành đợt Data Profiling trên dataset P4 thật.

---

### 2.2. Đánh giá tệp `preprocessing/encoding/run.py`

#### 1. Mục đích và chức năng hiện tại
* **[Fact]:** Là module thực thi chính của Bước 05 trong chuỗi tiền xử lý.
* **[Fact]:** Đọc `all.parquet`, mã hóa 8 bộ luật E1–E8, tính ma trận đồng xuất hiện, ghi nhận báo cáo `StepReport`.

#### 2. Logic xử lý chính
* **[Fact]:** Cài đặt các luật:
  - `E1`: Ordinal Seniority (0–5, Chưa rõ = -1).
  - `E2`: One-hot `job_family`, `source_platform`, `employment_type`.
  - `E3`: Multi-hot Top 10 tỉnh/thành + `tinh__other` + cờ `remote`, `ngoai_vn`.
  - `E4`: Multi-hot 230 cột kỹ năng (`uint8`, $\{0, 1\}$) + `other_skills_count` (`int32`).
  - `E5`: Giữ các cột số liên tục (`log_salary`, `exp`, `headcount`) + cờ `__missing`.
  - `E6`: Cờ nhị phân `is_negotiable`, `is_outlier_salary`.
  - `E7`: Đặc trưng thời gian (`posted_month`, `days_to_deadline`) + cờ `__missing`.
  - `E8`: Cờ luật kiểm toán (`it_rule_level__2`, `seniority_can_kiem`, `job_family_can_kiem`).
* **[Fact]:** `compute_skill_cooccurrence()`: Tính toán ma trận $\mathbf{C} = \mathbf{X}^T \mathbf{X}$ kích thước $230 \times 230$, kiểm tra $\mathbf{C} == \mathbf{C}^T$ và $\text{diag}(\mathbf{C}) == \sum \mathbf{X}$.

#### 3. Những giả định thiết kế đang được sử dụng
* **[Unverified]:** Giả định các cột đầu vào (`seniority`, `job_family`, `skills_std`, `locations`) có cấu trúc hợp lệ và không bị biến dạng kiểu dữ liệu qua lưu trữ Parquet.
* **[Recommendation]:** Thiết kế cột đếm kỹ năng ngoài top tên là `other_skills_count` để phân biệt hoàn toàn với các cột kỹ năng nhị phân.
* **[Fact]:** Như đã kiểm chứng tại mục 4.1 của `05_p5_specification_analysis.md`, biểu thức `"skills__other_count".startswith("skill_")` trong Python trả về `False`. Do đó tên gốc `skills__other_count` vốn không bị selector của FP-Growth bắt nhầm; việc đổi sang `other_skills_count` là một khuyến nghị cải thiện độ rõ ràng (readability) chứ không phải để sửa một lỗi ngữ nghĩa Python có thật.

#### 4. Mức độ phù hợp với đặc tả hiện tại
* **[Fact]:** Rất cao: Tuân thủ bảo toàn số dòng ($N_{out} = N_{in}$), 100% cột là số học (trừ `job_id_global`), có báo cáo kiểm toán `StepReport`.

#### 5. Những điểm cần kiểm tra lại sau khi có dữ liệu P4
* **[Unverified]:** Cần kiểm tra hiệu năng tính toán và dung lượng RAM khi chạy trên toàn bộ tập dữ liệu thật.

#### 6. Đề xuất
* **[Recommendation]:** **GIỮ LÀM NỀN TẢNG THIẾT KẾ CHÍNH (CORE ENGINE)**.

---

### 2.3. Đánh giá tệp `preprocessing/encoding/run_encoding.py`

#### 1. Mục đích và chức năng hiện tại
* **[Fact]:** Script CLI độc lập cho phép người dùng chạy riêng Bước 5 với các tùy chọn `--source` và `--apply` (mặc định dry-run).

#### 2. Logic xử lý chính
* **[Fact]:** Nhận tham số từ dòng lệnh, gọi `run()`, in kết quả tóm tắt và kiểm tra cờ `checks.rows_conserved`.

#### 3. Những giả định thiết kế đang được sử dụng
* **[Recommendation]:** Giả định kỹ sư vận hành cần lệnh tắt độc lập `python preprocessing/encoding/run_encoding.py` như nêu trong Task 05 §3.

#### 4. Mức độ phù hợp với đặc tả hiện tại
* **[Fact]:** Hoàn toàn phù hợp với yêu cầu nghiệm thu CLI của Task 05.

#### 5. Đề xuất
* **[Recommendation]:** **GIỮ NGUYÊN**.

---

### 2.4. Đánh giá tệp `preprocessing/encoding/tfidf_extractor.py`

#### 1. Mục đích và chức năng hiện tại
* **[Fact]:** Tiện ích trích xuất không gian đặc trưng n-gram từ mô tả công việc bằng `TfidfVectorizer` của Scikit-learn.

#### 2. Logic xử lý chính
* **[Fact]:** Ghép `description_clean` và `requirements_clean`, loại bỏ stopwords Anh - Việt, trích xuất n-gram $(1, 2)$ với `max_features = 3000`. Tự động bỏ qua an toàn nếu thiếu cột text.

#### 3. Những giả định thiết kế đang được sử dụng
* **[Conflict]:** Giả định downstream cần 3.000 đặc trưng (theo `SPEC-06 §5.3` và Task 05), mâu thuẫn với `SPEC-07 §3.1` (chỉ yêu cầu $K=100$).
* **[Conflict]:** Giả định P5 phụ trách sinh tệp TF-IDF, mâu thuẫn với `P5_encoding.md` §4 (giao TF-IDF cho phần phân tích).

#### 4. Đề xuất
* **[Recommendation]:** **GIỮ DƯỚI DẠNG UTILITY MODULE**, không nhúng TF-IDF vào `features.parquet`. Việc có xuất file `tfidf_features.parquet` hay không cần thống nhất chính thức cùng nhóm Data Mining.

---

## 3. Bảng Tổng Hợp Kiểm Tra Hiện Trạng Mã Nguồn

| Tệp mã nguồn | Trạng thái kỹ thuật | Phân loại bằng chứng | Rủi ro chính | Đề xuất hành động |
|---|---|:---:|---|---|
| `skills_taxonomy_230.py` | Hoạt động tốt | **Fact & Recommendation** | Danh mục 230 kỹ năng đang là giả định, có thể có kỹ năng tần suất $= 0$ | **Giữ làm Prototype**, cập nhật sau EDA |
| `run.py` | Hoạt động tốt, Pass unit tests | **Fact** | Phụ thuộc vào kiểu dữ liệu vật lý của `all.parquet` | **Giữ làm Core Engine** |
| `run_encoding.py` | Hoạt động tốt | **Fact** | Không có | **Giữ nguyên** làm CLI runner |
| `tfidf_extractor.py` | Hoạt động tốt | **Conflict & Recommendation** | Mâu thuẫn ranh giới phân định trách nhiệm với Mining | **Giữ dạng Utility** |
