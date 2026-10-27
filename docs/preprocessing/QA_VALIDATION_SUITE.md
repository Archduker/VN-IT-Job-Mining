# QUY CHUẨN KIỂM ĐỊNH CHẤT LƯỢNG DỮ LIỆU VÀNG: QA VALIDATION SUITE
*(Data Quality Assurance & Contract Validation Guide)*

> **Module kiểm định:** [`preprocessing/qa/run_qa_checks.py`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/preprocessing/qa/run_qa_checks.py)  
> **Bộ Unit Tests:** [`tests/test_qa_pipeline.py`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/tests/test_qa_pipeline.py)  
> **Báo cáo kết quả:** [`reports/qa/qa_pipeline_report.md`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/reports/qa/qa_pipeline_report.md) & [`reports/qa/qa_pipeline_report.json`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/reports/qa/qa_pipeline_report.json)

---

## 1. Mục Đích & Nguyên Tắc Vận Hành

Trong Modern Data Mining, chất lượng của dữ liệu đầu vào quyết định trực tiếp tới độ tin cậy của các thuật toán phân tích phía sau (Garbage In, Garbage Out).  
Hệ thống **QA Validation Suite** được thiết lập như một cánh cổng kiểm định chất lượng bắt buộc (**Quality Gate**) trước khi dữ liệu được coi là **Bộ Dữ Liệu Vàng (Golden Master Dataset)**.

### Bộ 5 Khế Ước Dữ Liệu (5 Data Contracts):

```text
+----------------------------------------------------------------------------------------------------+
|                               5 TRỤ CỘT KIỂM ĐỊNH CHẤT LƯỢNG (QA SUITE)                             |
+----------------------------------------------------------------------------------------------------+
|  [CHECK 1: NGUỒN GỐC & TỒN TẠI (LINEAGE & EXISTENCE)]                                              |
|  * Kiểm tra đầy đủ các tệp artifact của pipeline.                                                  |
|  * Số lượng bản ghi xuyên suốt các bước không bị thất thoát hoặc rò rỉ ID ảo.                     |
|                                                                                                    |
|  [CHECK 2: CHUẨN MỰC PURE RFC 8259 JSON (PURE JSON STANDARDS)]                                     |
|  * Quét đệ quy toàn bộ JSON tree: Nghiêm cấm token NaN, Infinity, -Infinity.                       |
|  * Cấm hoàn toàn định dạng tệp .parquet hoặc .csv trong phân tầng Preprocessing.                   |
|                                                                                                    |
|  [CHECK 3: KHẾ ƯỚC DỮ LIỆU VÀNG SẠCH (ZERO-RAW & CLEAN JD)]                                        |
|  * 100% không còn trường thô (raw_payload, raw_html).                                              |
|  * Mô tả JD sạch sẽ, không dính tiền tố lặp thừa ("Mô tả công việc:").                             |
|                                                                                                    |
|  [CHECK 4: KHẾ ƯỚC PHÂN LOẠI KỸ NĂNG (SKILLS & EXTRACT CONTRACT)]                                  |
|  * Đảm bảo đủ 4 phân nhóm kỹ năng: primary_tech_stack, required, preferred, soft_skills.           |
|  * Mảng kỹ năng phải là chữ thường, loại bỏ khoảng trắng thừa.                                     |
|                                                                                                    |
|  [CHECK 5: NGOẠI LAI & ĐIỂM CHẤT LƯỢNG (OUTLIERS & QUALITY GOVERNANCE)]                             |
|  * Ràng buộc Zero-null lương: Không có bản ghi nào bị null lương số.                              |
|  * Dải lương hợp lý (min > 0, max >= min, không có lương âm hoặc phi thực tế).                     |
|  * Điểm chất lượng trung bình của toàn bộ dataset đạt >= 0.70.                                     |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Chi Tiết 5 Bài Kiểm Tra (Check Specifications)

### Check 1: Nguồn Gốc & Sự Tồn Tại Của Dữ Liệu (`Lineage & Existence`)
- **Tệp kiểm tra:**  
  - `data/curated/golden_master.json`
  - `data/curated/curated_flat_golden_jobs.json`
  - `data/missing_outlier/raw_for_normalization.json`
- **Tiêu chí:**
  - Tất cả các file artifact bắt buộc phải tồn tại trên đĩa.
  - Số lượng bản ghi của `golden_master.json` và `curated_flat_golden_jobs.json` phải trùng khớp 100% (ví dụ: 8,967 bản ghi).
  - Mọi `job_id_global` trong dữ liệu vàng đều phải có nguồn gốc từ tập hợp ID của `raw_for_normalization.json` (Zero ID Leakage).

### Check 2: Chuẩn Mực PURE RFC 8259 JSON (`Pure JSON Standards`)
- **Nguyên lý kiểm định:**
  - RFC 8259 quy định JSON chỉ hỗ trợ các giá trị: `object`, `array`, `string`, `number`, `true`, `false`, `null`.
  - Nghiêm cấm sự xuất hiện của `NaN` (Not a Number), `Infinity` hoặc các token không chuẩn do thư viện Pandas/Numpy xuất ra khi thiếu giá trị.
- **Tiêu chí:**
  - Quét token bằng regex nhị phân trên toàn bộ nội dung file JSON thô.
  - Quét đệ quy từng khóa và giá trị trong cấu trúc dữ liệu nạp vào Python.
  - Đảm bảo trong thư mục `data/curated/` và `data/missing_outlier/` không có bất kỳ file nào có đuôi mở rộng `.parquet` hoặc `.csv`.

### Check 3: Khế Ước Dữ Liệu Vàng Sạch (`Golden Master Contract Zero-Raw`)
- **Tiêu chí:**
  - Không tồn tại bất kỳ khóa thô nào ở cấp gốc: Cấm `raw_payload`, `raw_html`, `job_data_raw`.
  - Tỷ lệ thiếu mô tả công việc (`jd_text.description` hoặc `description_text`) phải bằng **0%**.
  - Kiểm tra làm sạch văn bản: Loại bỏ hoàn toàn các tiền tố lặp thừa thường gặp khi cào dữ liệu (`"Mô tả công việc:"`, `"Yêu cầu ứng viên:"`, `"Quyền lợi:"`).

### Check 4: Hợp Đồng Phân Loại Kỹ Năng (`Skills & Extract Contract`)
- **Tiêu chí:**
  - Thuộc tính `skills` phải chứa đầy đủ 4 nhóm phân cấp: `primary_tech_stack`, `required_technical`, `preferred_skills`, `soft_skills`.
  - Toàn bộ kỹ năng phải là danh sách chuỗi chữ thường đã được chuẩn hóa (loại bỏ ký tự lạ, chuẩn hóa tên công nghệ như `c#`, `c++`, `node.js`).
  - Tối thiểu 85% bản ghi có ít nhất 1 kỹ năng được trích xuất thành công.

### Check 5: Quản Trị Ngoại Lai & Điểm Chất Lượng (`Outliers & Quality Governance`)
- **Tiêu chí:**
  - **Zero-Null Lương:** 100% bản ghi có `salary_min_vnd > 0` và `salary_max_vnd >= salary_min_vnd`.
  - **Kiểm soát dải lương:** Không có mức lương âm, không có mức lương phi lý dưới 1,000,000 VND/tháng cho kỹ sư IT hoặc vượt trần phi thực tế mà không có lý do.
  - **Điểm chất lượng (Data Quality Score):** Mỗi bản ghi được chấm điểm từ 0.0 đến 1.0 dựa trên độ đầy đủ thông tin (tiêu đề, công ty, địa điểm, dải lương, kỹ năng, kinh nghiệm). Điểm trung bình toàn bộ dataset phải đạt $\ge 0.70$.

---

## 3. Hướng Dẫn Thực Thi (CLI Execution)

### 3.1. Chạy Kiểm Định QA Trực Tiếp
Lệnh chạy toàn bộ 5 bài kiểm tra trên tập dữ liệu Vàng hiện tại:

```bash
# Kích hoạt môi trường ảo
source .venv/bin/activate

# Thực thi kiểm định QA toàn trình
python preprocessing/qa/run_qa_checks.py
```

### 3.2. Chạy Thông Qua Pytest (TDD Verification)
Bộ test tự động hóa toàn bộ 5 khế ước với 17 test cases độc lập:

```bash
# Chạy bộ test QA pipeline
pytest tests/test_qa_pipeline.py -v
```

---

## 4. Báo Cáo Chất Lượng Dữ Liệu Mẫu (Audit Report)

Khi chạy xong, hệ thống tự động xuất bản 2 tệp báo cáo chi tiết:
1. **Báo cáo trực quan (Markdown):** [`reports/qa/qa_pipeline_report.md`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/reports/qa/qa_pipeline_report.md)
2. **Báo cáo số liệu máy đọc (JSON):** [`reports/qa/qa_pipeline_report.json`](file:///run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/reports/qa/qa_pipeline_report.json)

### Trích Đoạn Báo Cáo Thực Tế Đạt Chuẩn 5/5:

```text
================================================================================
                    QA PIPELINE VALIDATION AUDIT REPORT
================================================================================
Generated At: 2026-10-27T14:48:30+07:00
Target File: data/curated/golden_master.json
Total Golden Records: 8,967

[CHECK 1: LINEAGE & EXISTENCE]           --> [PASSED] (8,967 / 8,967 matched, 0 ID leaks)
[CHECK 2: PURE RFC 8259 JSON]           --> [PASSED] (0 NaN tokens, 0 Parquet, 0 CSV)
[CHECK 3: ZERO RAW & CLEAN JD]          --> [PASSED] (0 raw fields, 0% missing JD)
[CHECK 4: SKILLS & EXTRACT CONTRACT]    --> [PASSED] (100% compliant tri-level skills)
[CHECK 5: OUTLIERS & QUALITY SCORE]     --> [PASSED] (0 null salaries, Avg Score: 0.884)

OVERALL STATUS: 5/5 CHECKS PASSED (100% PRODUCTION READY)
================================================================================
```
