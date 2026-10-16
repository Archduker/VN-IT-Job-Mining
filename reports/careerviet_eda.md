# BÁO CÁO EDA SƠ BỘ TẠI NGUỒN (PRELIMINARY EDA REPORT)

> **Người thực hiện:** Tài  
> **Nguồn phân tích:** CareerViet (`careerviet.vn`)  
> **Nhánh Git:** `crawls/careerviet` (HEAD = `f977ffb`)  
> **Kích thước mẫu phân tích hiện có:** **0 envelope raw** ở `DEFAULT_RAW_DIR` (`data/careerviet/raw/`); 3 mẫu hồi quy ở `crawlers/sources/careerviet/samples/`; 20 envelope tham khảo ở `data/careerviet/_dryrun/raw/2026-10-16/` (từ dry-run cũ, **không** dùng để tính số liệu thị trường)  
> **Notebook thực hiện:** `notebooks/eda_preliminary_careerviet.ipynb` (dự kiến, **CHƯA tạo** — chờ dữ liệu online)  
> **Ngày lập khung báo cáo:** 2026-10-16  
> **Trạng thái:** **KHUNG CHỜ SỐ LIỆU ONLINE** — mọi ô `...` sẽ điền sau lượt 1 (20 tin `c37_digital_mkt` đã được lên lịch).

---

## 0. Ghi chú Phương pháp (Raw As-Is vs Data Integration)

**Tầng raw của CareerViet giữ NGUYÊN VĂN theo quy ước Raw As-Is** (docs/crawl/careerviet.md §7):

- **KHÔNG** có `salary_min` / `salary_max` (kiểu số) trong envelope; chỉ có `job-posting-schema.baseSalary` (dict JSON-LD) và text lương trong `title` / `detail-box`.
- **KHÔNG** tách bullet từ `detail-box` / `detail-row`; giữ nguyên cây DOM.
- **KHÔNG** dedup `job-tags`; **KHÔNG** chuẩn hóa `map` thành list tỉnh.
- **KHÔNG** dùng `source_category` (c1/c61/c37/keyword:developer) làm nhãn IT.

Vì vậy, **mục 2 (Outlier bằng giá trị số)** của template **không thể thực hiện ở tầng raw**; phải chạy sau bước **Data Integration** khi `salary_min` / `salary_max` đã được trích qua regex + JSON-LD → số. Mục này ở báo cáo hiện được **đánh dấu "SAU INTEGRATION"**.

**Phạm vi EDA sơ bộ** (tài liệu này):

- Đo **tỉ lệ null** + **phân bố frequency** của 8 khóa `raw_payload`.
- Đo **tỉ lệ IT** qua `raw_payload["Ngành nghề"]` (mục tiêu chính của bucket c37).
- Hiển thị **Top-10 kỹ năng** từ `job-tags`, **Top tỉnh** từ `map`.

Phân tích sâu (ma trận tương quan Pearson/Spearman, Isolation Forest ngoại lai, boxplot lương) nằm ở **báo cáo EDA chuyên sâu** (`eda-intelligence` skill), sau Integration.

---

## 1. Đánh Giá Khuyết Thiếu Dữ Liệu (Missing Values Analysis)

### 1.1. Bảng Tỷ Lệ Null Của Các Trường Quan Trọng (dự kiến đo sau online):

| Tên trường | Số lượng Null | Tỷ lệ Null (%) | Đánh giá mức độ | Phương án xử lý đề xuất |
| :--- | :---: | :---: | :--- | :--- |
| Tiêu đề (`title`) | CHỜ ONLINE | CHỜ ONLINE (dự kiến 0 %) | Tuyệt đối | Giữ nguyên. |
| Công ty (`job-company-name`) | CHỜ ONLINE | CHỜ ONLINE (dự kiến 0 %) | Tuyệt đối | Giữ nguyên. |
| Mô tả/Yêu cầu/Quyền lợi (`detail-box`, List[dict]) | CHỜ ONLINE | CHỜ ONLINE (dự kiến ~0 %) | Tuyệt đối | Integration tách 4 box theo heading text (Mô tả / Yêu cầu / Quyền lợi / Khác). |
| Bảng thuộc tính (`detail-row`, List[dict]) | CHỜ ONLINE | CHỜ ONLINE (dự kiến 0 %, 5–6 dòng) | Tuyệt đối | Integration trích `exp_min/max`, `education`, `deadline`, `location`. |
| Thẻ kỹ năng (`job-tags`) | CHỜ ONLINE | CHỜ ONLINE (dự kiến **~53 %** từ 30/30 HTML local: 14/30 = no-tag) | Trung bình → Cao | Few-shot LLM SD3 trích skills ngầm định từ `detail-box`. |
| Địa điểm (`map`) | CHỜ ONLINE | CHỜ ONLINE (dự kiến 0 %, luôn hiển thị) | Tuyệt đối | Tách chuỗi `,` → list, chuẩn hóa tên tỉnh. |
| Ngành nghề (`raw_payload["Ngành nghề"]`) | CHỜ ONLINE | CHỜ ONLINE (dự kiến <5 %) | Thấp | **Dùng làm Bộ LỌC IT** (rule: chứa "CNTT" hoặc "Phần mềm"). |
| JSON-LD (`job-posting-schema`) | CHỜ ONLINE | CHỜ ONLINE (dự kiến 0 %, 30/30 có) | Tuyệt đối | Trích `baseSalary` → `salary_min/max` (Integration). |
| Version (metadata `version`) | 0 (bắt buộc) | 0 % | Tuyệt đối | Đã kiểm 3/3 samples. |
| `content_hash` | 0 (bắt buộc) | 0 % | Tuyệt đối | Đã kiểm 3/3 samples. |
| `source_category` | 0 (bắt buộc) | 0 % | Tuyệt đối | **KHÔNG** dùng làm nhãn IT. |

### 1.2. Công cụ đo (sẽ chạy sau online):

```powershell
# Liệt kê envelope + %null + CDC counts + % CNTT
python -X utf8 scripts/careerviet_raw_stats.py
# Lọc IT qua "Ngành nghề"
python -X utf8 scripts/careerviet_it_check.py
```

---

## 2. Phân Tích Ngoại Lai (Outlier Analysis) Bằng Phương Pháp Giá Trị Số

### 2.1. **SAU INTEGRATION** (không áp dụng cho raw)

**Lý do**: Raw envelope CareerViet **không** có cột số `salary_min` / `salary_max`. Muốn đo IQR / Z-Score / Isolation Forest cho lương, phải chạy **sau** bước Data Integration khi JSON-LD `baseSalary` + regex text lương (`"25 - 40 triệu"`, `"Thỏa thuận"`) đã được chuẩn hóa về số.

Bảng sau đây sẽ được **điền từ dataset tích hợp**, không phải từ raw:

| Chỉ số thống kê | Lương Tối Thiểu (`salary_min`) | Lương Tối Đa (`salary_max`) |
| :--- | :---: | :---: |
| Giá trị nhỏ nhất (Min) | SAU INTEGRATION | SAU INTEGRATION |
| Phân vị 25% (Q1) | SAU INTEGRATION | SAU INTEGRATION |
| Trung vị (Median / Q2) | SAU INTEGRATION | SAU INTEGRATION |
| Phân vị 75% (Q3) | SAU INTEGRATION | SAU INTEGRATION |
| Giá trị lớn nhất (Max) | SAU INTEGRATION | SAU INTEGRATION |
| IQR = Q3 − Q1 | SAU INTEGRATION | SAU INTEGRATION |
| Lower Bound = Q1 − 1.5·IQR | SAU INTEGRATION | SAU INTEGRATION |
| Upper Bound = Q3 + 1.5·IQR | SAU INTEGRATION | SAU INTEGRATION |
| Số bản ghi Outlier | SAU INTEGRATION | SAU INTEGRATION |
| Tỷ lệ Outlier (%) | SAU INTEGRATION | SAU INTEGRATION |

### 2.2. Danh sách các bài đăng Outlier cực đoan (SAU INTEGRATION):

_Điền sau khi dataset tích hợp có `salary_min` / `salary_max`._

Gợi ý cách liệt kê:

1. `job_id`: ... — Tiêu đề: ... — `baseSalary` JSON-LD: ... — Text lương trong `title`: ... (Nhận định: Gõ nhầm USD↔VND / Nhầm năm↔tháng / Sai JSON-LD từ NTD / Lỗi parse).

**Rủi ro phát hiện sớm tại tầng raw** (không cần số): `job-posting-schema.baseSalary.validFrom` vượt `metadata.scraped_at` (tin tương lai) → loại qua rule tại Integration. **Không** có bằng chứng hiện tại.

---

## 3. Khảo Sát Phân Bố & Tần Suất Giá Trị Phân Loại

### 3.1. Top 10 Kỹ Năng / Thẻ Tag Xuất Hiện Nhiều Nhất

**CHỜ ONLINE** — sẽ đo bằng `Counter(itertools.chain(*payload["job-tags"]))` trên `data/careerviet/raw/`.

Ghi chú: 3 mẫu hiện có cho ra **6 tag** duy nhất (35C833DD: 2, 35C87378: 4, 35C81470: 0) — **chưa đủ** để xếp hạng.

### 3.2. Cơ Cấu Địa Điểm Làm Việc

**CHỜ ONLINE**. 3 mẫu local: 2× "Hà Nội", 1× "Quảng Ninh, Hải Phòng, Hải Dương" (multi-province, separator `,`) → chưa có ý nghĩa thống kê.

Dự kiến cách đếm: sau Integration tách `map` → list, one-hot mỗi tỉnh, frequency / total.

### 3.3. Phân Bố CDC (docs/careerviet.md §4)

| Tag (`_process_detail_record.outcome["tag"]`) | Bộ đếm |
| :--- | :---: |
| `success` (NEW/UPDATED) | CHỜ ONLINE |
| `active` (content_hash không đổi) | CHỜ ONLINE |
| `repost` (content_hash trùng với URL khác) | CHỜ ONLINE |
| `failed` (Safe Skip, exception không 5xx) | CHỜ ONLINE |
| `pending_kept` (5xx-storm break, giữ PENDING) | CHỜ ONLINE |

### 3.4. Phân Bố Ngành Nghề / Tỉ Lệ IT (mục tiêu chính của 281 c37)

**CHỜ ONLINE** — dự kiến đo qua:

```python
it_count = sum(1 for env in envelopes
               if any("CNTT" in s or "Phần mềm" in s
                      for s in env["raw_payload"]["Ngành nghề"]))
```

Kết quả cần điền vào docs/careerviet.md §9.4.

---

## 4. Hình Ảnh Trực Quan Hóa

**CHỜ ONLINE** — sẽ xuất từ notebook `notebooks/eda_preliminary_careerviet.ipynb` (CHƯA tạo, chờ dữ liệu):

- *Biểu đồ 1 (Phân phối):* Histogram `salary_min` / `salary_max` (SAU INTEGRATION, vì raw không có số).
- *Biểu đồ 2 (Quan hệ):* Scatter `exp_min` (trích từ `detail-row`) × `salary_max` (SAU INTEGRATION).
- *Biểu đồ 3 (Độ biến thiên):* Boxplot lương theo tỉnh (SAU INTEGRATION).
- *Biểu đồ 4 (Ma trận tương quan):* heatmap Pearson/Spearman các trường số (SAU INTEGRATION).
- *Biểu đồ 5 (Tần suất phân loại):* Bar chart Top-15 tag (có thể làm ở raw sau online, không cần Integration).

---

## 5. Kế Hoạch Điền Số

| Bước | Lệnh | Đầu ra |
| :---: | :--- | :--- |
| 1 | `python -X utf8 crawlers/sources/careerviet/crawler.py --limit 20 --source-category c37_digital_mkt --shuffle --seed 42 --online` *(CẦN DUYỆT MẠNG)* | 20 envelope `data/careerviet/raw/2026-10-16/` |
| 2 | `python -X utf8 scripts/careerviet_raw_stats.py` | %null, CDC counts |
| 3 | `python -X utf8 scripts/careerviet_it_check.py` | Tỉ lệ CNTT (Ngành nghề) |
| 4 | Điền §1.1, §2.1, §3.1, §3.2, §3.3, §3.4 + docs/careerviet.md §9.4 + `reports/careerviet_inventory.md` §1, §2, §3.3. | Báo cáo hoàn tất |
| 5 | `python -X utf8 crawlers/sources/careerviet/crawler.py --phase sync` | Ledger → MinIO `url_ledger/careerviet/` |
| 6 | `python -X utf8 scripts/push_raw_to_minio.py --source careerviet --local-dir data/careerviet --prefix raw/careerviet` | Envelope → MinIO `raw/careerviet/` |

---

**Kết luận khung**: EDA **sơ bộ** tại CareerViet có thể chạy ở tầng raw cho mục 1 (null) và §3.1/§3.2/§3.4 (frequency, tỉ lệ IT); **EDA số học** (mục 2 outlier, biểu đồ 1–4) **bắt buộc** sau Data Integration vì Raw As-Is không có `salary_min/max` (docs/careerviet.md §7). Mọi số liệu cụ thể: **CHỜ ONLINE lượt 1**.
