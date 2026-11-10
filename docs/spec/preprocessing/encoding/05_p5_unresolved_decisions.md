# Danh Mục Các Vấn Đề Thiết Kế Chưa Được Quyết Định (Unresolved Decisions)

> **Ghi chú 10/11/2026:** JEV, OpenJev và Qwen đã bỏ; cột xác suất `*_prob` không còn. Cờ thay thế: `it_rule_level`, `seniority_can_kiem`, `job_family_can_kiem` (xem `docs/spec/preprocessing/spec/P5_encoding.md`).

> **Mã tài liệu:** `P5-UNRESOLVED-DECISIONS-04` (Phiên bản 2.0 — Hiệu chỉnh bằng chứng & Phân loại chuẩn xác)  
> **Người thực hiện:** Hồng Phát (P5 Owner)  
> **Giai đoạn:** Chuẩn bị & Phân tích (Analysis & EDA Preparation — No Implementation)  
> **Mục tiêu:** Liệt kê minh bạch các điểm nghẽn, mâu thuẫn đặc tả và các vấn đề thiết kế cần được thảo luận, thống nhất cùng Trưởng nhóm và các thành viên phụ trách downstream trước khi tiến hành đóng băng code triển khai.

---

## 1. Bảng Tổng Hợp Các Vấn Đề Cần Thống Nhất

| STT | Vấn đề thiết kế cốt lõi | Hiện trạng mâu thuẫn / Chưa xác nhận | Căn cứ tài liệu | Bằng chứng cần có từ P4 EDA | Phân loại | Bên liên quan |
|:---:|---|---|---|---|:---:|:---:|
| **D1** | **Phương pháp tuyển chọn 230 kỹ năng** | Task 05 yêu cầu đúng 230 skills; `SPEC-06 §5.1` nói chọn top $K \in [100, 200]$; code cũ chọn động $\le 200$. | `05_phat_encoding_and_matrices.md` §1; `SPEC-06 §5.1`; `P5_encoding.md` §4 | Bảng xếp hạng tần suất thực tế của toàn bộ kỹ năng từ file P4. | **Conflict** | Phát, Phúc (Mining) |
| **D2** | **Quan hệ giữa chiều rộng 230 cột và ngưỡng tần suất $\ge 20$** | Nếu số kỹ năng đạt $\ge 20$ ít hơn hoặc nhiều hơn 230, xử lý fallback như thế nào? | `05_phat_encoding_implementation_contract.md` §2; `SPEC-06 §5.1` | Phân phối tần suất kỹ năng thực tế (CDF), số lượng kỹ năng tại các mốc tần suất 20, 15, 10. | **Conflict** | Phát, Nhóm trưởng |
| **D3** | **Có mở rộng taxonomy chuẩn `skills.json` không** | `skills.json` hiện chỉ có 40 keys, không bao quát đủ 230 kỹ năng. | `preprocessing/dictionaries/skills.json`; `preprocessing/normalization/text_cleaner.py` dòng 269 | Danh sách các kỹ năng ngoài 40 keys có tần suất cao xuất hiện trong dữ liệu P4. | **Conflict** | Phát, Duy (P4) |
| **D4** | **Có áp dụng hạn ngạch (quota) theo 6 nhóm ngành không** | Task 05 ghi cân đối 6 nhóm; `skills.json` không có trường group; chọn Top-K tự nhiên có thể thiên lệch nhóm Web. | `05_phat_encoding_and_matrices.md` §1; `SPEC-06 §3.1` | Tỷ lệ cơ cấu kỹ năng theo 6 nhóm từ kết quả EDA. | **Recommendation** | Phát, Phúc (Mining) |
| **D5** | **Quy ước dấu gạch dưới tiền tố cột kỹ năng (`skill_` vs `skill__`)** | Task 05 dùng 1 dấu gạch dưới `skill_<slug>`; `P5_encoding.md` dùng 2 dấu gạch dưới `skill__<slug>`; `SPEC-07` dùng `c.replace("skill_", "")`. | `05_phat_encoding_and_matrices.md` dòng 20; `P5_encoding.md` dòng 29; `SPEC-07` dòng 263 | Kiểm chứng Python semantics về cắt chuỗi hiển thị trên FP-Growth. | **Conflict** | Phát, Phúc (Mining) |
| **D6** | **Thiết kế lưu trữ Ma trận Đồng xuất hiện (Co-occurrence)** | Task 05 gọi `skill_cooccurrence.parquet`; SPEC-06 gọi `matrix_skill_cooccurrence.parquet`. Cần chốt dạng Wide (230x230) hay Long (Edge-list)? | `05_phat_encoding_and_matrices.md` §1; `SPEC-06 §5.2`; `SPEC-09` | Yêu cầu trực quan hóa đồ thị mạng kỹ năng trên Dashboard (`SPEC-09`). | **Conflict** | Phát, Sơn (Observatory) |
| **D7** | **Phạm vi và quyền sở hữu Ma trận TF-IDF** | Task 05 yêu cầu 2.000–3.000 features; P5 spec bảo không làm tại P5; SPEC-07 chỉ cần $K=100$. | `05_phat_encoding_and_matrices.md` §1; `P5_encoding.md` §4; `SPEC-07 §3.1` | Nhu cầu thực tế của mô hình K-Means của Phúc và dung lượng lưu trữ trên đĩa. | **Conflict** | Phát, Phúc (Mining) |
| **D8** | **Quyền sở hữu tệp `curated_flat_golden_jobs.parquet`** | Task 05 giao P5 xuất bản; nhưng P0/P4 spec quy định P4 xuất bản Golden, P5 chỉ đọc. | `05_phat_encoding_and_matrices.md` §1 dòng 28; `P0_pipeline_contract.md` §1; `P5_encoding.md` §1, §5 | Hợp đồng pipeline `P0_pipeline_contract.md`. | **Conflict** | Phát, Duy (P4), Thuận |
| **D9** | **Đồng nhất tiền tố biến giải thích cho Random Forest (`SPEC-07`)** | SPEC-07 dùng `sen_`, `loc_`, `jf_`; P5 đang sinh `seniority_ord`, `tinh__`, `job_family__`. | `SPEC-07` dòng 322; `preprocessing/encoding/run.py` | Script huấn luyện Random Forest tại SPEC-07 / SPEC-13. | **Conflict** | Phát, Phúc (Mining) |

---

## 2. Chi Tiết Từng Vấn Đề & Các Phương Án Thảo Luận

### Vấn Đề D1 & D2: Phương Pháp Tuyển Chọn 230 Kỹ Năng & Xử Lý Ngưỡng Tần Suất

#### 1. Bối cảnh
* **[Fact] (Căn cứ: Approved Decision 2026-11-07 trong `05_phat_encoding_implementation_contract.md` §2):** Chiều rộng ma trận kỹ năng $X$ bắt buộc phải có đúng 230 cột nhị phân, và ma trận đồng xuất hiện $C = X^T X$ kích thước $230 \times 230$.
* **[Conflict]:** `SPEC-06 §5.1` quy định chọn top $K \in [100, 200]$ kỹ năng có tần suất $\ge 20$ lần. Tài liệu phê duyệt chưa xác định quy tắc lựa chọn cụ thể nếu số kỹ năng đạt $\ge 20$ trên dữ liệu thật khác 230.

#### 2. Các phương án kỹ thuật thảo luận
* **Phương án A (Top-K Tần Suất Tuyệt Đối):** Sau khi có dataset P4, đếm tần suất toàn bộ các kỹ năng phân biệt, lấy đúng 230 kỹ năng có tần suất cao nhất từ trên xuống dưới.
  - *Ưu điểm:* Hoàn toàn tự nhiên, phản ánh đúng dữ liệu thực tế của thị trường tuyển dụng.
  - *Nhược điểm:* Các kỹ năng thuộc nhóm Web/Lập trình cơ bản có thể chiếm áp đảo, khiến các nhóm chuyên biệt (như Security, Cloud, AI/Data) có ít đại diện.
* **Phương án B (Taxonomy Cố Định Có Hạn Ngạch 6 Nhóm):** Phân bổ quota cố định cho 6 nhóm (ví dụ: 35 Ngôn ngữ, 55 Frameworks, 35 Databases, 45 Cloud/DevOps, 35 Tools/QA, 25 Softskills/Data) như đề xuất tại `skills_taxonomy_230.py`. Trong từng nhóm, chọn các kỹ năng có tần suất cao nhất trên dữ liệu P4; nếu nhóm nào không đủ thì bổ sung các kỹ năng chuẩn ngành có tần suất thấp hơn.
  - *Ưu điểm:* Đảm bảo tính đa dạng và toàn diện cho đối tượng sinh viên IT, tương thích cao với 12 Job Families.
  - *Nhược điểm:* Cần duy trì metadata phân nhóm cho từng kỹ năng.

#### 3. Bằng chứng cần có từ P4 EDA
* **[Unverified]:** Bảng phân tích CDF tần suất kỹ năng và số lượng kỹ năng phân biệt của từng nhóm trong 6 nhóm công nghệ.

---

### Vấn Đề D3: Mở Rộng Taxonomy Chuẩn `skills.json`

#### 1. Bối cảnh
* **[Fact] (Căn cứ: `preprocessing/dictionaries/skills.json`):** Tệp chỉ có 40 keys. Ở bước P4 (`preprocessing/normalization/run.py` dòng 156), hàm `canonicalize_skills` chỉ chuẩn hóa các kỹ năng nằm trong 40 keys này, các kỹ năng khác giữ nguyên chuỗi text thô.

#### 2. Câu hỏi cần thống nhất
* Nhóm dự án có đồng ý mở rộng file `skills.json` từ 40 keys lên danh mục đầy đủ các kỹ năng IT hay không?
* Hay giữ nguyên `skills.json` ở P4, và việc ánh xạ vào 230 kỹ năng chuẩn sẽ do riêng tầng P5 thực hiện qua từ điển nội bộ của P5?

#### 3. Khuyến nghị kỹ thuật
* **[Recommendation]:** Nên chuẩn hóa taxonomy dùng chung cho toàn bộ dự án (`skills.json`) để cả P3 (bóc tách từ JD), P4 (chuẩn hóa) và P5 (mã hóa) đều dùng chung một bộ từ điển, tránh sự phân mảnh logic giữa các bước.

---

### Vấn Đề D5: Quy Ước Đặt Tên Cột Multi-Hot & Cột Gom

#### 1. Bối cảnh & Kiểm chứng Python Semantics
* **[Fact] (Căn cứ: Python Semantics & `SPEC-07` dòng 260):**  
  Đoạn mã chọn cột trong `SPEC-07` là:
  ```python
  skill_cols = [c for c in self.features_df.columns if c.startswith("skill_")]
  skill_df = self.features_df[skill_cols].astype(bool)
  skill_df.columns = [c.replace("skill_", "") for c in skill_cols]
  ```
  Xét biểu thức Python:
  ```python
  "skills__other_count".startswith("skill_")  # Trả về: False
  ```
  Ký tự thứ 6 là `'s'`, khác `'_'`. Do đó, `skills__other_count` **không bị** `startswith("skill_")` bắt nhầm.
* **[Conflict] (Căn cứ: Task 05 dòng 20 vs `P5_encoding.md` dòng 29 vs `SPEC-07` dòng 263):**  
  Mâu thuẫn nằm ở quy ước 1 dấu gạch dưới (`skill_<slug>`) hay 2 dấu gạch dưới (`skill__<slug>`):
  - Task 05 §1 dòng 20 quy định tiền tố `skill_<slug>` (ví dụ: `skill_python`, `skill_react`).
  - `P5_encoding.md` §4 và code cũ dùng `skill__<slug>` (2 dấu gạch dưới).
  - Khi chạy `SPEC-07` dòng 263: Lệnh `c.replace("skill_", "")` nếu gặp `skill__python` sẽ biến thành `_python` (bị thừa dấu gạch dưới ở đầu tên kỹ năng trên biểu đồ FP-Growth).
  - Nếu lập trình viên vô tình đặt tên cột gom là `skill__other_count` (số ít, 2 gạch dưới), thì `"skill__other_count".startswith("skill_")` sẽ bằng `True` và bị bắt nhầm.

#### 2. Khuyến nghị kỹ thuật
* **[Recommendation]:**
  1. Thống nhất đặt tên 230 cột kỹ năng là `skill_<slug>` (1 dấu gạch dưới) để `c.replace("skill_", "")` trích xuất chính xác tên slug sạch không dấu gạch dưới thừa.
  2. Cột gom ngoài top đặt tên là `skills__other_count` (theo đúng `P5_encoding.md` dòng 29) hoặc `other_skills_count`. Cả hai tên này đều đảm bảo `startswith("skill_") == False`.

---

### Vấn Đề D6: Thiết Kế Lưu Trữ Ma Trận Đồng Xuất Hiện (Skill Co-occurrence)

#### 1. Bối cảnh
* **[Fact] (Căn cứ: Task 05 §1; `SPEC-06 §5.2`):** Cả hai tài liệu đều yêu cầu ma trận đồng xuất hiện vuông đối xứng $\mathbf{C} = \mathbf{X}^T \mathbf{X}$ ($230 \times 230$).
* **[Conflict]:** Tên file trong Task 05 là `skill_cooccurrence.parquet`, trong khi `SPEC-06 §5.2` gọi là `matrix_skill_cooccurrence.parquet`.

#### 2. Các phương án lưu trữ thảo luận
* **Phương án A (Wide Matrix Parquet):** Bảng $230 \times 230$, index và columns là 230 tên cột kỹ năng. Phù hợp cho đại số tuyến tính và tính toán ma trận.
* **Phương án B (Long Format / Edge-List Parquet):** Bảng 3 cột: `source_skill`, `target_skill`, `cooccurrence_count` (chỉ lưu các cặp có trọng số $> 0$). Phù hợp để vẽ đồ thị mạng kỹ năng trên Dashboard (`SPEC-09`).
* **[Recommendation]:** P5 xuất bản bảng Wide làm artifact chuẩn; cung cấp hàm tiện ích chuyển sang Edge-list khi phân hệ Monitoring của Sơn cần nạp dữ liệu đồ thị.

---

### Vấn Đề D7: Phạm Vi Và Thiết Kế Không Gian TF-IDF

#### 1. Bối cảnh & Mâu thuẫn
* **[Conflict] (Căn cứ đối chiếu):**
  - Task 05 §1 yêu cầu trích xuất 2.000–3.000 features n-gram.
  - `P5_encoding.md` §4 quy định: *"Văn bản JD không mã hóa ở đây (TF-IDF/embedding làm ở phần phân tích)"*.
  - `SPEC-07 §3.1` (K-Means của Phúc) chỉ yêu cầu $K = 100$ đặc trưng n-gram quan trọng nhất.

#### 2. Khuyến nghị phân định trách nhiệm
* **[Recommendation]:** Không gộp 2.000–3.000 cột TF-IDF vào `features.parquet` để tránh làm phình to tập dữ liệu dạng bảng. Cung cấp module tiện ích `tfidf_extractor.py` trong `preprocessing/encoding/` để nhóm Data Mining chủ động sử dụng theo nhu cầu thuật toán.

---

### Vấn Đề D8: Quyền Sở Hữu Tệp `curated_flat_golden_jobs.parquet`

#### 1. Bối cảnh & Mâu thuẫn
* **[Conflict] (Căn cứ: Task 05 §1 dòng 28 vs `P5_encoding.md` §1, §5):**
  - Task 05 liệt kê `data/curated/curated_flat_golden_jobs.parquet` vào danh sách đầu ra của P5.
  - `P5_encoding.md` §1, §5 quy định: *"Bộ golden (output P4) vẫn là bản cho người đọc. Encoding chỉ đọc bộ golden, không sửa nó."*

#### 2. Khuyến nghị phân định trách nhiệm
* **[Recommendation]:** Trách nhiệm đóng gói tệp Golden Dataset thuộc về **P4** (`all.parquet` sau khi làm phẳng và chuẩn hóa). P5 chỉ đóng gói Feature Store số học (`features.parquet`) và các ma trận đặc trưng.

---

### Vấn Đề D9: Đồng Nhất Tiền Tố Đặc Trưng Cho Random Forest (`SPEC-07`)

#### 1. Bối cảnh & Mâu thuẫn
* **[Conflict] (Căn cứ: `SPEC-07` dòng 322 vs `preprocessing/encoding/run.py`):**
  - Trong `SPEC-07` dòng 322, mô hình hồi quy lương dùng bộ lọc:
    ```python
    feature_cols = [c for c in df_valid.columns if c.startswith(("skill_", "exp_", "sen_", "loc_", "jf_"))]
    ```
  - Trong khi đó, P5 sinh ra: `seniority_ord` (không có `sen_`), `job_family__<slug>` (không có `jf_`), `tinh__<slug>` (không có `loc_`).

#### 2. Khuyến nghị kỹ thuật
* **[Recommendation]:** P5 và Phúc (Mining) cần thống nhất danh bạ tên cột đặc trưng bảng trước khi chạy mô hình hồi quy định giá lương để tránh lỗi thiếu biến đầu vào.

---

## 3. Các Bước Tiếp Theo Dành Cho Thành Viên Phát

1. **Gửi bộ 4 tài liệu phân tích đã hiệu chỉnh** cho Trưởng nhóm và các thành viên liên quan (Duy - P4, Phúc - Mining, Sơn - Monitoring).
2. **Chờ tệp `all.parquet` từ bước P4:** Tuyệt đối không tự ý sinh số liệu mock hay triển khai code trước khi có dữ liệu thật.
3. **Thực thi Kế hoạch EDA 7 hạng mục:** Ngay khi có dữ liệu P4, chạy script phân tích để lấy bằng chứng thực nghiệm giải quyết dứt điểm các quyết định D1 đến D9.
4. **Họp thống nhất và đóng băng thiết kế:** Sau khi có sự đồng thuận chính thức, mới chuyển sang giai đoạn hoàn thiện code cuối cùng.
