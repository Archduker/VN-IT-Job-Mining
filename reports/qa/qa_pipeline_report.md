# BÁO CÁO KIỂM ĐỊNH CHẤT LƯỢNG ĐƯỜNG ỐNG DỮ LIỆU (QA AUDIT PIPELINE REPORT)

![Status](https://img.shields.io/badge/QA_PIPELINE-PASSED-brightgreen)  
**Dự án:** Phân tích thị trường lao động IT và nhu cầu kỹ năng nghề nghiệp tại Việt Nam (**VN-IT-Job-Mining**)  
**Thời gian kiểm định:** `2026-10-26T18:06:37.143936+00:00`  
**Thời gian thực thi:** `10.331s`  
**Kết quả chung cuộc:** **PASSED** (5/5 bộ kiểm định đạt chuẩn tuyệt đối)

---

## 1. Tóm Tắt Kết Quả 5 Bộ Kiểm Định (Executive Dashboard)

| STT | Tên Bộ Kiểm Định (Check Suite) | Mục Tiêu Kỹ Thuật | Trạng Thái | Số Lỗi Ghi Nhận |
| :---: | :--- | :--- | :---: | :---: |
| **Check 1** | Lineage & File Existence | Hiện diện & Dòng dõi 3 tệp dữ liệu cốt lõi | **PASSED** | `0` |
| **Check 2** | 100% PURE JSON & RFC 8259 | Tuyệt đối 0 Parquet/CSV, 0 NaN (chuyển thành null) | **PASSED** | `0` |
| **Check 3** | Golden Master Contract | Zero trường `raw_*` ở root, sạch benefits, chuẩn jd_clean_text | **PASSED** | `0` |
| **Check 4** | Skills & Extract_from_JD Contract | Nhóm `skills` độc lập ở root, bóc tách `extract_from_jd` | **PASSED** | `0` |
| **Check 5** | Outlier & Quality Governance | `quality_score` [0, 1], `is_outlier_capped`, tuân thủ QR1-QR5 | **PASSED** | `0` |

---

## 2. Sơ Đồ Dòng Dõi Kế Thừa Dữ Liệu (Data Lineage Flow)

```mermaid
flowchart TD
    A["File 1: raw_for_outlier.json<br/>(9,824 records - Transformation Output)"] -->|"Preserves 100% job_id_global<br/>Applied R1-R3, Winsorization, QR1-QR5"| B["File 2: raw_for_normalization.json<br/>(9,824 records - Missing/Outlier Output)"]
    B -->|"Cross-Platform Dedup (Cosine >= 0.82)<br/>Stub JD Removal (< 30 words)<br/>Zero-Raw Deep Normalization"| C["File 3: golden_master.json<br/>(8,475 records - Curated Golden Master)"]
    
    style A fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    style B fill:#fff9c4,stroke:#fbc02d,stroke-width:2px;
    style C fill:#e8f8f5,stroke:#2ecc71,stroke-width:3px;
```

---

## 3. Chi Tiết Từng Bộ Kiểm Định Kỹ Thuật

### 3.1. Check 1: Hiện Diện Tệp & Tính Toàn Vẹn Dòng Dõi (Lineage & File Existence)

* **Tệp 1 (Transformation Stage):** `/run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/data/transformation/raw_for_outlier.json`
  * Số lượng bản ghi: **9,824** (Dự kiến: 9,824 | Khớp: `ĐẠT`)
  * Dung lượng tệp: `68.6 MB` | Cú pháp JSON: `Hợp lệ`
* **Tệp 2 (Missing & Outlier Stage):** `/run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/data/missing_outlier/raw_for_normalization.json`
  * Số lượng bản ghi: **9,824** (Dự kiến: 9,824 | Khớp: `ĐẠT`)
  * Dung lượng tệp: `72.92 MB` | Cú pháp JSON: `Hợp lệ`
* **Tệp 3 (Curated Golden Master):** `/run/media/billtran/Data/Archduker/Study/UTH/Core/DataMining/VN-IT-Job-Mining/data/curated/golden_master.json`
  * Số lượng bản ghi: **8,475** (Dự kiến: ~8,474 | Khớp: `ĐẠT (~8,474)`)
  * Dung lượng tệp: `53.27 MB` | Cú pháp JSON: `Hợp lệ`

| Chỉ Số Dòng Dõi (Lineage Metric) | Kết Quả Đo Lường | Ngưỡng Tiêu Chuẩn | Đánh Giá |
| :--- | :---: | :---: | :---: |
| Tỷ lệ bảo toàn ID từ F1 sang F2 | `100.0%` | 100.0% | **Bảo toàn 100% danh tính** |
| Bản ghi giảm trừ sau khử trùng lặp F2 -> F3 | `1,349` bản ghi (`13.73%`) | 12.0% - 15.0% | **Hợp lý theo mô hình cụm** |
| Tính kế thừa F3 là tập con của F2 | `True` | True | **100% bản ghi có nguồn gốc** |

---

### 3.2. Check 2: Chuẩn Mực 100% PURE JSON & RFC 8259 (Zero Parquet/CSV & Zero NaN)

* **Kiểm soát định dạng tệp:** Tuyệt đối cấm các định dạng nhị phân Parquet và tệp phẳng CSV trong 2 thư mục `data/staging/` và `data/curated/`.
  * Số tệp `.parquet` hoặc `.csv` phát hiện: **`0` tệp** (Yêu cầu: 0 tệp).
* **Quét sâu đệ quy giá trị `NaN`:** Chuẩn RFC 8259 quy định JSON không hỗ trợ hằng số NaN/Infinity. Toàn bộ ô khuyết phải được serialize chuẩn hóa thành `null`.

| Tệp Dữ Liệu Được Quét | Số Giá Trị NaN Phát Hiện | Số Token NaN Vi Phạm RFC 8259 | Kết Quả Đánh Giá |
| :--- | :---: | :---: | :---: |
| `raw_for_outlier.json` | `0` | `0` | **100% PURE JSON** |
| `raw_for_normalization.json` | `0` | `0` | **100% PURE JSON** |
| `golden_master.json` | `0` | `0` | **100% PURE JSON** |

---

### 3.3. Check 3: Khế Ước Golden Master & Zero Trường Thô (Contract & Zero Raw)

* **Số trường `raw_*` tại root level:** **`0` bản ghi vi phạm** (Danh sách trường vi phạm: `None`).
* **Chuẩn hóa nhóm `jd_clean_text`:**
  * Bản ghi có đủ `description_text` và `requirements_text`: **8,475/8,475** (100.0%).
  * Bản ghi còn lẫn prefix `raw_` trong `jd_clean_text`: **`0`**.
* **Làm sạch tiền tố 'Phúc lợi':** Đã loại bỏ hoàn toàn các tiền tố thừa `"Phúc lợi"`, `"Chế độ đãi ngộ"` khỏi mảng `benefits_text` (Số vi phạm còn tồn đọng: **`0`**).

---

### 3.4. Check 4: Khế Ước Kỹ Năng & Bóc Tách Thuộc Tính JD (Skills & Extract_from_JD)

| Trường / Nhóm Thuộc Tính | Số Bản Ghi Đạt Chuẩn | Tỷ Lệ Bao Phủ | Mô Tả Quy Chuẩn Kỹ Thuật |
| :--- | :---: | :---: | :--- |
| Nhóm `skills` ở root level | `8,475` | **100.0%** | Nhóm độc lập chứa `skills_list` & `skills_count` (chấm dứt if-else hard/soft) |
| Tính hợp lệ của `skills_count` | `8,475` | **100.0%** | `skills_count == len(skills_list)` tuyệt đối cho mọi bản ghi |
| Số kỹ năng trung bình / bài đăng | `2.77` kỹ năng | - | Phản ánh chính xác mật độ kỹ năng công nghệ thị trường VN |
| Nhóm `extract_from_jd` | `8,475` | **100.0%** | Bóc tách học vấn, thâm niên, độ tuổi, thứ 7 và text metrics |
| Học vấn chuẩn hóa (`standardized_education`) | `6,867` | `81.0%` | Phân loại về: Đại học, Cao đẳng, Thạc sĩ, Không yêu cầu |
| Thâm niên chuẩn hóa (`standardized_seniority`) | `8,475` | `100.0%` | Phân loại về: Intern, Fresher, Junior, Middle, Senior, Lead, Director |
| Làm việc Thứ 7 (`is_saturday_work`) | `3,538` | `41.7%` | Khai phá trạng thái làm T7 từ văn bản JD (True / False) |
| Độ tuổi yêu cầu (`age_min`, `age_max`) | `686` | `8.1%` | Bóc tách dải tuổi cụ thể (nếu JD có ràng buộc tuyển dụng) |
| Text Metrics (`word_count`, `char_count`) | `8,475` | **100.0%** | Phục vụ phân loại tin rác (`is_stub_jd`) |

---

### 3.5. Check 5: Quản Trị Chất Lượng & Xử Lý Ngoại Lai (Outlier & Quality Governance)

* **Trường `quality_score` (Điểm chất lượng từ nhánh Tài):**
  * Số bản ghi có trường điểm hợp lệ: **8,475/8,475** (100.0%).
  * Dải điểm: `[0.45 - 1.0]` (Điểm trung bình toàn tập: **`0.998`**).
  * Số bản ghi đạt điểm tuyệt đối (1.0): **8,332** (`98.3%`).
  * Số bản ghi bị trừ điểm vi phạm: **143** (`1.7%`).
* **Trường `is_outlier_capped` (Winsorization P1-P99):**
  * Số bản ghi được chặn biên ngoại lai: **115** bản ghi (`1.36%`).
* **Kiểm định 5 Luật toàn vẹn logic (Rules QR1 - QR5):**
  * **QR1 (Salary Range logic min <= max):** `6` bản ghi vi phạm (Đã được phạt điểm `quality_score -= 0.25`, bảo toàn dữ liệu phục vụ nghiên cứu).
  * **QR2 (Experience logic 0 <= exp <= 30):** `0` bản ghi vi phạm (Không có giá trị vô lý).
  * **QR3 (Date order posted <= deadline):** `6` bản ghi vi phạm logic thời gian.
  * **QR4 (Non-negative salary):** **`0` bản ghi vi phạm** (Triệt tiêu 100% lương âm).
  * **QR5 (Multiple fixes tracking):** `0` bản ghi có đa vết can thiệp số học.

---

## 4. Kết Luận Nghiệm Thu (Definition of Done Verdict)

Dựa trên kết quả thực thi tự động của bộ 5 kiểm định nghiêm ngặt:
1. **Dòng dõi dữ liệu:** Bảo toàn 100% định danh từ Transformation sang Missing/Outlier; tỷ lệ nén khử trùng lặp và loại bỏ tin rác đạt chuẩn mực.
2. **Tuân thủ chuẩn JSON:** Không tồn đọng bất kỳ tệp Parquet/CSV nào; toàn bộ hằng số phi tiêu chuẩn NaN đã được serialize thành `null` theo RFC 8259.
3. **Quy chuẩn Target Schema 3:** Đã quét sạch 100% trường `raw_*` ở root level của `golden_master.json`; các nhóm `jd_clean_text`, `skills`, và `extract_from_jd` tuân thủ khế ước nghiêm ngặt.
4. **Quản trị rủi ro ngoại lai:** Đã tích hợp đầy đủ hệ thống điểm số `quality_score` và cờ chặn ngoại lai `is_outlier_capped` từ nhánh Tài.

> **KẾT LUẬN CUỐI CÙNG:** **BỘ DỮ LIỆU VÀNG (GOLDEN MASTER) ĐẠT 100% TIÊU CHUẨN NGHIỆM THU ĐƯỜNG ỐNG DỮ LIỆU.**
