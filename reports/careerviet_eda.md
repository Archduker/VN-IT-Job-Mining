# BÁO CÁO EDA SƠ BỘ TẠI NGUỒN (PRELIMINARY EDA REPORT)

> **Người thực hiện:** Tài  
> **Nguồn phân tích:** CareerViet (`careerviet.vn`)  
> **Nhánh Git:** `crawls/careerviet` (HEAD = `4701af8`)  
> **Kích thước mẫu phân tích:** **1018 envelope** ở `data/careerviet/raw/2026-10-16/` (từ **1029 ledger record DONE**, **11 record repost** phát hiện qua `content_hash` trùng URL khác → **không** sinh envelope; **0** record PENDING / FAILED / RECHECK_DUE)  
> **Thời gian crawl online:** 2026-10-16 17:09:58 UTC → 18:27:00 UTC (**4622 s = 77 phút**, trung bình **4.54 s/tin**, khớp `DelayConfig(2.0–5.0 s)`)  
> **Script sinh số:** `scripts/careerviet_report_fill.py --json` (null rate, CDC, IT ratio, top-N) + `scripts/careerviet_raw_stats.py` + `scripts/careerviet_it_check.py`  
> **Script sinh biểu đồ:** `scripts/careerviet_eda_charts.py` (16 PNG → `reports/figures/careerviet/`, chú thích 3 phần → `reports/careerviet_eda_charts.md`)  
> **Ngày cập nhật báo cáo:** 2026-10-18  
> **Trạng thái:** **HOÀN THÀNH EDA tại tầng raw** (mục 2 – outlier số học – **SAU INTEGRATION** vì Raw As-Is không có `salary_min` / `salary_max` dạng số)

---

## 0. Ghi chú Phương pháp (Raw As-Is vs Data Integration)

**Tầng raw của CareerViet giữ NGUYÊN VĂN theo quy ước Raw As-Is** (docs/crawl/careerviet.md §7):

- **KHÔNG** có `salary_min` / `salary_max` (kiểu số) trong envelope; chỉ có `job-posting-schema.baseSalary` (dict JSON-LD) và text lương trong `title` / `detail-box`.
- **KHÔNG** tách bullet từ `detail-box` (List[str] — hộp metadata) / `detail-row` (Dict[str,str] — các section JD); giữ nguyên văn bản phẳng theo selector gốc.
- **KHÔNG** dedup `job-tags`; **KHÔNG** chuẩn hóa `map` thành list tỉnh.
- **KHÔNG** dùng `source_category` (c1 / c61 / c37 / keyword:developer) làm nhãn IT.

Vì vậy, **mục 2 (Outlier bằng giá trị số)** của template **không thể thực hiện ở tầng raw**; phải chạy sau bước **Data Integration** khi `salary_min` / `salary_max` đã được trích qua regex + JSON-LD → số. Mục này ở báo cáo hiện được **đánh dấu "SAU INTEGRATION"**.

**Phạm vi EDA sơ bộ** (tài liệu này):

- Đo **tỉ lệ null** + **phân bố frequency** của 8 khóa `raw_payload` (mục 1).
- Đo **tỉ lệ IT** qua `raw_payload["Ngành nghề"]` (mục 3.4) — mục tiêu chính của 281 URL `c37` được nạp **có chủ đích** (commit `1470de0`).
- Hiển thị **Top-15 kỹ năng** từ `job-tags`, **Top tỉnh** từ `map`, **Top công ty** từ `job-company-name`, **phân phối** `baseSalary` VND/tháng và độ dài JD trong `detail-row` (mục 3 + mục 4).
- Phân tích CDC qua ledger (`NEW` / `UPDATED` / `REPOST`, mục 3.3 + biểu đồ 16).

Phân tích sâu (ma trận tương quan Pearson/Spearman, Isolation Forest ngoại lai, boxplot lương theo tỉnh) nằm ở **báo cáo EDA chuyên sâu** (`eda-intelligence` skill), sau Integration.

---

## 1. Đánh Giá Khuyết Thiếu Dữ Liệu (Missing Values Analysis)

### 1.1. Bảng Tỷ Lệ Null Của Các Trường Quan Trọng

**Thực đo trên 1018 envelope**, qua `python -X utf8 scripts/careerviet_report_fill.py` (khoá `null_rate_by_payload_key`):

| Tên trường | Số lượng Null | Tỷ lệ Null (%) | Đánh giá mức độ | Phương án xử lý đề xuất |
| :--- | :---: | :---: | :--- | :--- |
| Tiêu đề (`title`) | 18 / 1018 | **1.77 %** | Tuyệt đối (rất thấp) | Giữ nguyên. Integration có thể fallback `job-posting-schema.title` khi raw rỗng. |
| Công ty (`job-company-name`) | 17 / 1018 | **1.67 %** | Tuyệt đối | Fallback `job-posting-schema.hiringOrganization.name` tại Integration. |
| Hộp metadata (`detail-box`, `List[str]`) | 24 / 1018 | **2.36 %** | Tuyệt đối | Chứa Lương / Kinh nghiệm / Cấp bậc / Hình thức / Ngày cập nhật / Hết hạn nộp (KHÔNG phải mô tả công việc). 24 tin rỗng **trùng đúng** 24 tin `map` + `Ngành nghề` rỗng → nhóm tin tối giản không có block metadata. |
| Nội dung công việc (`detail-row`, `Dict[str,str]`) | 1 / 1018 | **0.10 %** | Tuyệt đối (gần như đầy đủ) | **Đây là JD thật**: key = heading (`Mô tả Công việc` 1013/1018, `Yêu Cầu Công Việc` 1017, `Phúc lợi` 1017, `Thông tin khác` 1017, `Gợi ý hồ sơ` 1017, `Địa điểm làm việc` 728). Integration tách theo heading, **không** cần regex DOM. |
| Thẻ kỹ năng (`job-tags`) | **204** / 1018 | **20.04 %** | Trung bình → Cao | **Ít hơn dự kiến** (ước ~46.7 % từ 14/30 HTML local). Few-shot LLM SD3 trích skills ngầm định từ `detail-row` cho 204 tin không tag. |
| Địa điểm (`map`) | 24 / 1018 | **2.36 %** | Tuyệt đối | Tách chuỗi `,` → list, chuẩn hóa tên tỉnh tại Integration. |
| Ngành nghề (`raw_payload["Ngành nghề"]`) | 24 / 1018 | **2.36 %** | Thấp | **Dùng làm Bộ LỌC IT** (rule: chứa `"CNTT"` hoặc `"Phần mềm"`). 24 tin rỗng **không phân loại được** → tạm tính vào non-IT (xem §3.4). |
| JSON-LD (`job-posting-schema`) | **0** / 1018 | **0.00 %** | Tuyệt đối (đầy đủ) | Trích `baseSalary` → `salary_min/max` (Integration). |
| Mô tả JSON-LD (`job-posting-schema.description`) | **0** / 1018 | **0.00 %** | Tuyệt đối (đầy đủ) | Bản HTML gốc của toàn bộ JD (median **2.149** ký tự text thuần). **Bằng chứng không mất thông tin mô tả ở tầng raw.** |

**Ghi chú**:

- **Không có envelope rác**: `data/careerviet/_blocked/` = **0 file** → `content_hash` trên **1018/1018** đều có `.job-detail-page` thật (xác nhận fix `f977ffb` giữ nguyên hiệu lực khi online, **không** false-positive, **không** false-negative).
- `job-posting-schema` **100 % đầy đủ** — bằng chứng Careerviet SSR nhúng JSON-LD đồng nhất (30/30 HTML local + 1018/1018 online).
- `job-tags` **20.04 %** null **thấp hơn nhiều** so với dự kiến 46.7 % (14/30 HTML local không tag) → các tin online crawl **có tag hơn hẳn** tập mẫu 30 HTML.
- **Lưu ý cấu trúc (đọc envelope thật để đối chiếu selector trong `raw_envelope.py:163-186`)**: `detail-box` = **List[str]** các dòng `<li>` metadata (Lương, Kinh nghiệm, Cấp bậc, Hình thức, Ngày cập nhật, Hết hạn nộp — có phần tử **lặp 2 lần** do render desktop + mobile); `detail-row` = **Dict[str, str]** mới là **nội dung công việc** theo heading. Tên hai khóa **dễ nhầm** — Integration phải map `detail-row` → `description`/`requirements`/`benefits`, **không** lấy `detail-box` làm mô tả.

### 1.2. Công cụ đo (đã chạy, tái lập được)

```powershell
# Liet ke envelope + %null + CDC counts + % CNTT
python -X utf8 scripts/careerviet_raw_stats.py
python -X utf8 scripts/careerviet_it_check.py
python -X utf8 scripts/careerviet_report_fill.py --json > data/careerviet/report_fill_20261018.json

# Sinh 16 bieu do + chu thich (da chay, dau ra o reports/figures/careerviet/*)
python -X utf8 scripts/careerviet_eda_charts.py
```

---

## 2. Phân Tích Ngoại Lai (Outlier Analysis) Bằng Phương Pháp Giá Trị Số

### 2.1. **SAU INTEGRATION** (không áp dụng cho raw)

**Lý do**: Raw envelope CareerViet **không** có cột số `salary_min` / `salary_max`. Muốn đo IQR / Z-Score / Isolation Forest cho lương, phải chạy **sau** bước Data Integration khi JSON-LD `baseSalary` + regex text lương (`"25 - 40 triệu"`, `"Thỏa thuận"`) đã được chuẩn hóa về số.

| Chỉ số thống kê | Lương Tối Thiểu (`salary_min`) | Lương Tối Đa (`salary_max`) |
| :--- | :---: | :---: |
| Giá trị nhỏ nhất (Min) | SAU INTEGRATION | SAU INTEGRATION |
| Phân vị 25 % (Q1) | SAU INTEGRATION | SAU INTEGRATION |
| Trung vị (Median / Q2) | SAU INTEGRATION | SAU INTEGRATION |
| Phân vị 75 % (Q3) | SAU INTEGRATION | SAU INTEGRATION |
| Giá trị lớn nhất (Max) | SAU INTEGRATION | SAU INTEGRATION |
| IQR = Q3 − Q1 | SAU INTEGRATION | SAU INTEGRATION |
| Lower Bound = Q1 − 1.5·IQR | SAU INTEGRATION | SAU INTEGRATION |
| Upper Bound = Q3 + 1.5·IQR | SAU INTEGRATION | SAU INTEGRATION |
| Số bản ghi Outlier | SAU INTEGRATION | SAU INTEGRATION |
| Tỷ lệ Outlier (%) | SAU INTEGRATION | SAU INTEGRATION |

### 2.2. Danh sách các bài đăng Outlier cực đoan (SAU INTEGRATION)

_Điền sau khi dataset tích hợp có `salary_min` / `salary_max`._

**Đọc sơ bộ tại tầng raw** (EDA, **không** parse ngược vào envelope) qua `scripts/careerviet_eda_charts.py`:

- **1018 / 1018 tin** (100 %) có `job-posting-schema.baseSalary` dict hợp lệ.
- **438 tin** (43.0 %) ở dạng **VND / tháng** (`unitText = MONTH` hoặc missing) có khoảng `minValue` / `maxValue` đọc được.
- **Trung vị: 17.5 triệu VND / tháng** (min 0.5, max 65.0 triệu).
- **Currency phân bố**: `VND` 893, `LTT` 98 (Lương thoả thuận), `USD` 17, `LCT` 10 (Lương cạnh tranh) — `LTT` / `LCT` không có số → bỏ qua trong histogram.
- Vẽ ở **Biểu đồ 5** (§4.5).

**Rủi ro phát hiện sớm tại tầng raw** (không cần số): `job-posting-schema.baseSalary.validFrom` vượt `metadata.scraped_at` (tin tương lai) → loại qua rule tại Integration. **Không** có bằng chứng hiện tại (1018/1018 `datePosted` ≤ 2026-10-16, khớp ngày crawl).

---

## 3. Khảo Sát Phân Bố & Tần Suất Giá Trị Phân Loại

### 3.1. Top 15 Kỹ Năng / Thẻ Tag Xuất Hiện Nhiều Nhất

**Thực đo trên 1018 envelope** (tổng **2480 tag khác nhau**, **204 tin** (20.04 %) không có tag):

| Hạng | Tag | Số tin |
| :---: | :--- | :---: |
| 1 | Marketer | 23 |
| 1 | Telesales | 23 |
| 1 | IT Engineer | 23 |
| 4 | Nhân viên Marketing | 22 |
| 5 | Marketing Executive | 20 |
| 5 | Sales Executive | 20 |
| 7 | Marketing Specialist | 19 |
| 8 | Customer services | 18 |
| 8 | IT Helpdesk | 18 |
| 10 | Nhân viên phòng kinh doanh | 17 |
| 10 | Chuyên Viên Kinh Doanh | 17 |
| 10 | lập trình viên | 17 |
| 10 | IT Staff | 17 |
| 14 | IT support | 16 |
| 15 | Nhân viên bán hàng | 15 |

**Nhận xét**:

- **Tag "Marketer" dẫn đầu** với 23 tin — phản ánh bucket `c37_digital_mkt` (279 tin, 27.4 % tổng) đang nằm trong tập dữ liệu và là bucket hỗn hợp. Data Integration sẽ dùng `Ngành nghề` để lọc IT (xem §3.4).
- **Không tag nào vượt 2.3 %** tổng mẫu (23/1018) → **phân bố tag rất dài đuôi** (long-tail), 2480 tag / 1018 tin ≈ **2.44 tag/tin**. Không có kỹ năng nào "phổ biến áp đảo".
- **Kỹ năng IT xuất hiện rải rác**: `IT Engineer` (23), `IT Helpdesk` (18), `lập trình viên` (17), `IT Staff` (17), `IT support` (16) — cần gộp đồng nghĩa ở Data Integration (vd `"IT Engineer"` ↔ `"Software Engineer"`, `"lập trình viên"` ↔ `"Developer"`).

### 3.2. Cơ Cấu Địa Điểm Làm Việc

**Thực đo trên 1018 envelope** (tổng **42 địa điểm** khác nhau):

| Hạng | Địa điểm | Số tin | % mẫu |
| :---: | :--- | :---: | :---: |
| 1 | Hồ Chí Minh | **454** | 44.6 % |
| 2 | Hà Nội | **445** | 43.7 % |
| 3 | Đồng Nai | 31 | 3.0 % |
| 4 | Bình Dương | 25 | 2.5 % |
| 5 | Bà Rịa - Vũng Tàu | 15 | 1.5 % |
| 6 | Đà Nẵng | 14 | 1.4 % |
| 7 | Long An | 13 | 1.3 % |
| 8 | Hải Phòng | 11 | 1.1 % |
| 9 | Bắc Ninh | 7 | 0.7 % |
| 10 | Tây Ninh | 6 | 0.6 % |

**Nhận xét**:

- **Hai thành phố lớn chiếm áp đảo**: Hồ Chí Minh + Hà Nội = **899 lượt**, tức **83,2 %** trong tổng 1.080 lượt (top 3 = 930 lượt = **86,1 %**). Con số **88,3 %** (899/1018) là **lẫn đơn vị** — tử số tính bằng *lượt* còn mẫu số tính bằng *tin* — nên báo cáo chỉ dùng 83,2 % / 86,1 %. Một tin ghi được nhiều tỉnh nên tổng lượt (1.080) > số tin (1.018); biểu đồ 7 vẽ theo lượt.
- **Kết luận**: thị trường IT việc làm tập trung **đô thị lớn**, phù hợp kỳ vọng.
- Raw giữ nguyên `map` dạng string (`"Hồ Chí Minh"` hoặc `"Quảng Ninh, Hải Phòng, Hải Dương"` multi-province). **Integration**: tách `,` → one-hot từng tỉnh, hoặc map lên `region` (North / Central / South).

### 3.3. Phân Bố CDC (docs/crawl/careerviet.md §4)

**Thực đo qua `scripts/careerviet_report_fill.py`** (`cdc_from_ledger`), **mutually exclusive** (mỗi record thuộc **đúng 1** nhóm, đã test `test_cdc_from_ledger_repost_not_double_counted`):

| Nhóm CDC | Bộ đếm | Định nghĩa (`_process_detail_record`) |
| :--- | :---: | :--- |
| **NEW (Version 1)** | **1018** | Ledger chưa từng có `content_hash` trùng → tạo envelope `_v1.json`, `latest_version = 1`. **Tất cả** envelope hiện tại đều v1 (chưa re-crawl 21 ngày). |
| UPDATED (Version > 1) | 0 | Cùng `url_hash`, `content_hash` đổi → `_v<N>.json` (`N = curr + 1`). **0** vì chưa re-crawl sau 21 ngày (`RECHECK_DUE` = 0). |
| ACTIVE (Unchanged) | 0 | Cùng `url_hash`, `content_hash` không đổi → ghi đè `last_scraped_at`, KHÔNG bump version. **0** vì chưa re-crawl. |
| **REPOST (cross-URL)** | **11** | `find_by_content_hash` thấy bản ghi DONE khác `url_hash` với cùng `content_hash` → tag `"repost"`, set `repost_of_url_hash`, **không** sinh envelope mới. **11/1029 = 1.07 %** — bằng chứng cơ chế repost hoạt động thật khi online. |
| CLOSED | 0 | Job đã gỡ / 410 / 404 → status `CLOSED`. **0** vì crawl một đợt ngắn, chưa có tin hết hạn. |
| FAILED | 0 | Lỗi Safe Skip (timeout, parse error, 5xx rời rạc). **0** → crawl **sạch 100 %**. |
| PENDING | 0 | Chuỗi 5xx-storm cuối bị break, giữ PENDING. **0** → không bão 5xx. |
| **TỔNG LEDGER** | **1029** | `DONE = 1029` (trong đó `repost_of_url_hash != null`: **11**), `PENDING = 0`, `FAILED = 0`, `RECHECK_DUE = 0`. |

**Đối chiếu**: `1029 (ledger DONE) − 11 (repost) = 1018 (envelope)` ✓

### 3.4. Phân Bố Ngành Nghề / Tỉ Lệ IT (mục tiêu chính của 281 URL `c37`)

**Rule** (`scripts/careerviet_it_check.py` + `careerviet_report_fill.py`): tin là IT nếu `raw_payload["Ngành nghề"]` (list) chứa chuỗi có `"CNTT"` **hoặc** `"Phần mềm"`. **Không** dùng `metadata.source_category` (xem docs/crawl §8.1).

**Tổng**: **591 / 1018 = 58.1 %** là IT, **427 non-IT = 41.9 %**.

> **Caveat thật cần lưu ý khi Integration**: trong 427 tin non-IT có **24 tin** (`2.36 %`) **null `Ngành nghề`** (đúng nhóm tin có `detail-box` rỗng — xem §1.1) → rule hiện tại **mặc định xếp chúng là non-IT** dù chưa có bằng chứng. Muốn chắc chắn, Integration có thể fallback sang `job-posting-schema.description` / tiêu đề cho 24 tin này.

**Chi tiết theo bucket cao** (từ `eda_charts` §2):

| Bucket | Số tin | IT | % IT trong bucket | Nhận xét |
| :--- | :---: | :---: | :---: | :--- |
| `c1` | 602 | 398 | **66.1 %** | Lớn nhất, chủ yếu IT. |
| `c37_digital_mkt` | 279 | 136 | **48.7 %** | Bucket hỗn hợp **mục tiêu của `--include-c37`** — **gần 1/2** không phải IT, chứng minh quyết định nạp c37 để đo tỉ lệ IT là **đúng hướng**. |
| `keyword:developer` | 92 | 43 | **46.7 %** | Từ khoá "developer" nhưng có cả "business developer" ngoài IT → tỉ lệ IT < 100 %. |
| `c61` | 45 | 14 | **31.1 %** | Bucket "khác", nhiều tin ngoài IT. |

**Top 10 tổ hợp ngành nghề** (từ `report_fill.py`, khoả `it_ratio.top_nganh`):

| # | Tổ hợp `Ngành nghề` | Số tin |
| :---: | :--- | :---: |
| 1 | `CNTT - Phần mềm` | 104 |
| 2 | `CNTT - Phần mềm , CNTT - Phần cứng / Mạng` | 77 |
| 3 | `Ngân hàng , CNTT - Phần mềm , CNTT - Phần cứng / Mạng` | 30 |
| 4 | `Tiếp thị / Marketing , Bán hàng / Kinh doanh , Tiếp thị trực tuyến` | 26 |
| 5 | `Tiếp thị / Marketing , Tiếp thị trực tuyến , Quảng cáo / Đối ngoại / Truyền Thông` | 26 |
| 6 | `Tiếp thị / Marketing , Tiếp thị trực tuyến , Thương mại điện tử` | 23 |
| 7 | `Bán lẻ / Bán sỉ , Bán hàng / Kinh doanh , Tiếp thị trực tuyến` | 23 |
| 8 | `Ngân hàng , Tài chính / Đầu tư , CNTT - Phần mềm` | 19 |
| 9 | `CNTT - Phần mềm , Ngân hàng` | 18 |
| 10 | `Ngân hàng , CNTT - Phần mềm` | 10 |

**Kết luận cho Data Integration**:

- Bộ lọc IT giữ lại **591 / 1018 = 58.1 %** bản ghi CareerViet, loại **427** tin không IT.
- Bucket `c37` có **48.7 % là IT** → nếu không có bộ lọc `Ngành nghề`, **51.3 % tin c37** sẽ làm nhiễu phân tích thị trường IT. **Khuyến nghị**: tích hợp qua `Ngành nghề` (không dùng `source_category`), khớp `docs/crawl §8.1`.

---

## 4. Hình Ảnh Trực Quan Hóa

**16 biểu đồ sinh tự động** bởi `scripts/careerviet_eda_charts.py` (mọi con số tính từ dữ liệu thật trên 1018 envelope + ledger; **không** bịa số liệu). Ảnh nằm ở `reports/figures/careerviet/`.

**Nguồn số của §4**: các mục dưới đây chép **nguyên văn** chú thích 3 phần mà script ghi vào [`reports/careerviet_eda_charts.md`](careerviet_eda_charts.md) — chạy lại script là cả hai file cùng cập nhật, không có con số gõ tay. Định dạng số theo quy ước tiếng Việt của script (`1.018`, `58,1%`). Mỗi mục gồm **Quan sát** (số đo được) / **Ý nghĩa** (với thị trường IT) / **Hạn chế** (thiên lệch dữ liệu).

### 4.0. Cover 5 họ biểu đồ bắt buộc (skill `eda-intelligence`)

| Họ biểu đồ | Trạng thái tại tầng raw | Biểu đồ áp dụng |
| :--- | :---: | :--- |
| **1. Phân phối (Distribution)** | **CÓ** | **5** (hist lương VND/tháng), **9** (Pareto tag toàn mẫu), **12** (Pareto phúc lợi), **13** (đường datePosted), **14** (Pareto hình thức) |
| **2. Quan hệ (Relationship)** | **CÓ — dạng định tính** | **3** (bucket × % IT), **8** (heatmap địa điểm × nhóm), **10** (tag: IT vs ngoài IT), **15** (độ dài JD: IT vs ngoài IT) |
| **3. Độ biến thiên (Dispersion / Variance)** | **CÓ — boxplot** | **6** (lương IT vs ngoài IT), **15** (độ dài JD theo nhóm) |
| **4. Ma trận tương quan (Pearson / Spearman)** | **CHƯA** (cần `salary_min` × `exp_min` × region dạng số) | SAU INTEGRATION |
| **5. Tần suất phân loại (Categorical Frequency & Pareto)** | **CÓ (đủ)** | **1, 2, 4, 7, 9, 11, 12, 14, 16** |

**Tổng kết**: **4 / 5** họ đo được ở tầng raw (họ 2 và 3 ở dạng **định tính / so sánh nhóm**, chưa phải quan hệ số học); họ **4 (tương quan số)** **bắt buộc** sau Data Integration. Boxplot lương theo **từng tỉnh** vẫn chưa vẽ được vì 40/42 địa phương quá mỏng (§4.7).

### 4.1. Biểu đồ 1 — Cơ cấu nguồn theo bucket URL-Discovery

![1. Cơ cấu nguồn theo bucket URL-Discovery](figures/careerviet/01_bucket_supply.png)

- **Quan sát:** c1 cho 602 tin (59,1%), c37 cho 279 tin (27,4%); đứng đầu là c1 + c37 đã chiếm 86,5% số tin.
- **Ý nghĩa:** Tỷ trọng này là hệ quả của việc chọn danh mục ở Phase 1 (độ rộng ngành của từng bucket), không phải độ nóng việc làm của thị trường.
- **Hạn chế:** Nhãn bucket lấy từ `metadata.source_category` - mỗi job_id chỉ mang một nhãn nên tổng cột đúng bằng số tin, nhưng chính crawler yêu cầu Data Integration KHÔNG dùng nó để lọc IT.

### 4.2. Biểu đồ 2 — Tỷ lệ IT / ngoài IT (donut 3 nhóm)

![2. Tỷ lệ IT / ngoài IT (donut 3 nhóm)](figures/careerviet/02_it_share_donut.png)

- **Quan sát:** IT 591 tin (58,1%), ngoài IT 403 tin (39,6%), và 24 tin (2,4%) rỗng 'Ngành nghề' được tách thành nhóm riêng thay vì gộp vào ngoài IT.
- **Ý nghĩa:** Sau bước lọc IT còn 427 tin không phải IT - đây là khối dữ liệu cần loại ở Phase 2, không phải 'phế liệu' bỏ quên.
- **Hạn chế:** Quy tắc khóa 'cntt/phan mem/phần mềm' có thể bỏ sót tin IT ghi ngành theo kỹ năng (Data, BA, QA...), đồng thời 24 tin tối giản không đủ căn cứ phân loại => 58,1% là cận dưới hợp lý, không phải tỷ lệ thị trường.

> **Cập nhật so với bản trước**: 24 tin null `Ngành nghề` trước đây bị gộp vào non-IT (§3.4 ghi "427 non-IT = 41,9 %") — này tách thành **3 nhóm**: 591 IT / 403 ngoài IT / 24 không phân loại. Tổng 427 tin không-IT-giữ-nguyên vẫn đúng.

### 4.3. Biểu đồ 3 — Tỷ lệ IT theo bucket

![3. Tỷ lệ IT theo bucket](figures/careerviet/03_it_ratio_bucket.png)

- **Quan sát:** c61: 31,1% IT (thấp nhất); c1: 66,1% IT (cao nhất); khoảng cách giữa 4 bucket lên tới 35 điểm phần trăm.
- **Ý nghĩa:** Bucket c1 là danh mục 'ruột' của mảng IT trên CareerViet, còn c61 chủ yếu đăng ngành ngoài IT.
- **Hạn chế:** Mỗi bucket là một quyết định chốt danh mục của Phase 1, không phải phép đo thị trường; so sánh tuyệt đối giữa các bucket dễ dẫn tới kết luận sai về nhu cầu tuyển dụng.

### 4.4. Biểu đồ 4 — Độ phủ / tỷ lệ trống từng trường

![4. Độ phủ / tỷ lệ trống từng trường](figures/careerviet/04_null_rate.png)

- **Quan sát:** Đứng đầu là Lương quy đổi được (VND/tháng) với 580 tin rỗng (57,0%), kế đến job-tags 204 tin (20,0%); trong khi đó `detail-box` chỉ rỗng ở 24 tin và `detail-row` rỗng ở 1 tin.
- **Ý nghĩa:** Các trường cần cho SD3/SD4 (tag, lương, map) có mức trống khác nhau nên không thể áp một ngưỡng hoàn thiện chung cho mọi mẫu.
- **Hạn chế:** Rỗng ở đây nghĩa là nguồn không cho giá trị trong SSR/JSON-LD; chưa đủ căn cứ kết luận lỗi trích xuất. Mức trống theo nhóm IT / ngoài IT được tách ở hình 10.

> **Đọc thêm**: ba cột giá trị **0** ở đáy biểu đồ (`job-posting-schema`, `description (JSON-LD)`, `baseSalary (JSON-LD)`) **không phải lỗi vẽ** — đó là bằng chứng ba trường này đầy đủ **1018/1018**. Đơn vị của biểu đồ là *số tin rỗng*, nên 0 = tốt nhất.

### 4.5. Biểu đồ 5 — Phân bố lương (toàn mẫu)

![5. Phân bố lương (toàn mẫu)](figures/careerviet/05_salary_hist.png)

- **Quan sát:** 438/1.018 tin (43,0%) đọc được lương; trung vị 17,5, tứ phân vị 12,875-22,75, nhỏ nhất 0,5, lớn nhất 65 (triệu VND/tháng); 57,0% tin không đủ dữ liệu lương, trong đó 555 tin chỉ ghi 'Lương cạnh tranh'/'Thỏa thuận' ở dòng `detail-box`.
- **Ý nghĩa:** Mặt bằng lương công khai trong mẫu dồn ở dải 12,875-22,75 triệu/tháng; tỷ lệ công khai lương khác nhau giữa hai nhóm (IT 33,3% tin có lương, ngoài IT 58,3%).
- **Hạn chế:** 57,0% tin không đủ dữ liệu lương là thiên lệch chọn lọc lớn: cùng một công việc, nhà tuyển dụng công khai lương có thể khác nhóm 'Thỏa thuận', nên không suy ra được mặt bằng lương chung của thị trường.

### 4.6. Biểu đồ 6 — Lương: IT vs ngoài IT (boxplot)

![6. Lương: IT vs ngoài IT (boxplot)](figures/careerviet/06_salary_box_it_vs_non.png)

- **Quan sát:** IT n = 197: trung vị 20, IQR 15-27,5, tối đa 65. Ngoài IT n = 235: trung vị 15, IQR 11,5-19,5, tối đa 60. Chênh lệch trung vị +33,3%.
- **Ý nghĩa:** Trong phần tin công khai lương của CareerViet, nhóm IT không chỉ có mức trung vị cao hơn mà còn có biên độ (IQR) rộng hơn - nhất quán với tính chuyên môn hóa và phân tầng bậc của việc IT.
- **Hạn chế:** So sánh chỉ chạy trên 432 tin có lương (42,4% mẫu); tỷ lệ công khai lương của hai nhóm có thể khác nhau và chưa kiểm định thống kê (Mann-Whitney/t) => coi là giả thuyết hướng, không phải kết luận toàn thị trường.

### 4.7. Biểu đồ 7 — Địa điểm làm việc

![7. Địa điểm làm việc](figures/careerviet/07_locations.png)

- **Quan sát:** Hồ Chí Minh 454 lượt (44,6%), Hà Nội 445 lượt (43,7%); tổng 1.080 lượt rải trên 42 địa phương, các tỉnh còn lại đều dưới 31 lượt.
- **Ý nghĩa:** Thị trường trong mẫu dồn ở hai địa bàn đầu bảng (83,2% lượt); 40 địa phương còn lại chỉ chiếm 16,8% lượt nên quá mỏng để phân tích vùng.
- **Hạn chế:** Một tin có thể ghi nhiều tỉnh (tách theo dấu phẩy) nên tổng lượt lớn hơn số tin; `map` rỗng ở 24 tin (2,4%).

> **Đơn vị của biểu đồ này là *lượt*, không phải *số tin*** — tổng 1.080 lượt trên 1.018 tin vì một tin ghi được nhiều tỉnh (xem lại §3.2).

### 4.8. Biểu đồ 8 — Địa điểm × nhóm IT (heatmap)

![8. Địa điểm × nhóm IT (heatmap)](figures/careerviet/08_location_group_heatmap.png)

- **Quan sát:** Hồ Chí Minh: 217 IT / 237 ngoài IT (47,8% IT); Hà Nội: 345 IT / 100 ngoài IT (77,5% IT). Hai cực của bảng là Hà Nội (77,5% IT) và Tây Ninh (16,7% IT, chỉ 6 tin).
- **Ý nghĩa:** Cơ cấu IT / ngoài IT chênh 29,7 điểm phần trăm giữa hai địa bàn dày nhất (Hồ Chí Minh so với Hà Nội) - căn cứ để chốt địa bàn khi phân tích cụm kỹ năng theo vùng.
- **Hạn chế:** Hàng chỉ bao phủ tin có `map`; 24 tin rỗng `map` trùng chính xác với 24 tin không phân loại được nên không bị trừ hai lần; các hàng mỏng (như Tây Ninh chỉ 6 tin) có tỷ lệ rất dễ đổi, và không suy được cung - cầu nhân lực của từng tỉnh từ một ảnh chụp.

### 4.9. Biểu đồ 9 — Tag kỹ năng toàn mẫu

![9. Tag kỹ năng toàn mẫu](figures/careerviet/09_tags_all_top.png)

- **Quan sát:** 2.480 tag khác nhau; cao nhất 'Marketer' 23 tin (2,3%), trong đó 21 tin ngoài nhóm IT; top 15 trải trên 28,0% số tin; 204 tin (20,0%) không có tag nào.
- **Ý nghĩa:** Bảng tag toàn mẫu KHÔNG phải 'bộ kỹ năng IT': 41,9% tin thuộc ngành khác, nên 10/15 tag đứng đầu xuất hiện ở tin ngoài IT nhiều hơn ở tin IT.
- **Hạn chế:** Tag là chuỗi thô của nguồn, chưa chuẩn hóa (khác biệt hoa/thường, synonym), nên tần suất một kỹ năng bị phân tán; đây là lý do Phase 2 phải tách `Technical skills` và chuẩn hóa từ điển.

### 4.10. Biểu đồ 10 — Tag trong 591 tin IT

![10. Tag trong 591 tin IT](figures/careerviet/10_tags_it_only_top.png)

- **Quan sát:** 1.410 tag xuất hiện trong tin IT, cao nhất 'IT Engineer' 23 tin (3,9%); ba tag đứng đầu: IT Engineer 23, IT Helpdesk 18, lập trình viên 17. Tin IT không có tag: 138 (23,4%) so với ngoài IT 62 (15,4%).
- **Ý nghĩa:** Độ phủ tag của nhóm IT thấp hơn nhóm ngoài IT (23,4% so với 15,4% tin trống), nên lọc IT bằng `job-tags` sẽ mất nhiều tin hơn lọc bằng 'Ngành nghề'.
- **Hạn chế:** Tag đầu bảng chỉ phủ 23/591 tin IT (3,9%) nên đuôi rất ngắn; không đủ chứng cứ để nói IT 'thiếu kỹ năng' hay so sánh kỹ năng giữa ngành.

### 4.11. Biểu đồ 11 — Nhà tuyển dụng

![11. Nhà tuyển dụng](figures/careerviet/11_companies_top.png)

- **Quan sát:** 494 tên khác nhau phủ 1.001 tin có tên; cao nhất Ngân Hàng TMCP Quân Đội với 37 tin (3,6%); 22,0% số tin nằm trong top 15.
- **Ý nghĩa:** Nhà đăng nhiều nhất chỉ chiếm 3,6% số tin, nên mẫu này mô tả thị trường 'việc đăng rải' hơn là hệ sinh thái quây quanh vài doanh nghiệp lớn.
- **Hạn chế:** Tên công ty chưa chuẩn hóa (công ty mẹ/con, sai chính tả) => `distinct company` chỉ là cận trên; 17 tin (1,7%) không có tên.

### 4.12. Biểu đồ 12 — Top 15 loại phúc lợi (`jobBenefits` JSON-LD)

![12. Top 15 heading phúc lợi](figures/careerviet/12_benefits_top.png)

- **Quan sát:** `jobBenefits` (JSON-LD, chuỗi phân tách dấu phẩy) tách được 15 loại trên 964 tin (94,7%); dẫn đầu Đào tạo 938 tin (97,3%), Chế độ bảo hiểm 936 tin (97,1%), hiếm nhất 'Du lịch nước ngoài' 122 tin, 'Xe đưa đón' 77 tin.
- **Ý nghĩa:** Các phúc lợi đứng đầu (Đào tạo, Chế độ bảo hiểm, Chế độ thưởng, Tăng lương) là chuẩn chung của mọi ngành, nên chúng không phải điểm khác biệt giữa việc IT và việc ngoài IT trong mẫu này.
- **Hạn chế:** Số liệu chỉ ghi nhận 'có/không nêu tên phúc lợi', không có giá trị tiền tệ hay mức độ; so sánh phúc lợi theo nhóm IT cần tách cấu trúc ở Phase 2.

### 4.13. Biểu đồ 13 — Ngày đăng tin (`datePosted` JSON-LD)

![13. Ngày đăng tin](figures/careerviet/13_date_posted.png)

- **Quan sát:** 1.018/1.018 tin có `datePosted`, trải từ 2026-09-15 đến 2026-10-16 (32 ngày); cao nhất 2026-10-15 với 171 tin (16,8%).
- **Ý nghĩa:** Phân bố ngày đăng phản ánh nhịp đăng tin của nguồn trong 32 ngày, đủ để mô tả khoảng thời gian thu thập chứ không đo được lưu lượng việc IT.
- **Hạn chế:** Mỗi lần crawl là một ảnh khoanh khác nhau; 11 tin repost mang ngày đăng cũ nên phân bố này bị già hóa nhân tạo.

### 4.14. Biểu đồ 14 — Hình thức làm việc

![14. Hình thức làm việc](figures/careerviet/14_employment_type.png)

- **Quan sát:** Nhân viên chính thức 976 tin (98,2%); tổng 4 loại hình, hiếm nhất 'Bán thời gian' 13 tin, 'Thời vụ/ Nghề tự do' 3 tin; trường này trống ở 24 tin (2,4%).
- **Ý nghĩa:** Trường phân loại chỉ có 4 mức và 0 lượt ghi hình thức linh hoạt (remote/hybrid/tại nhà), nên muốn đo tỷ lệ làm từ xa phải bóc từ `detail-row` ở Phase 2.
- **Hạn chế:** Giá trị là chuỗi thô của nguồn (một tin ghi nhiều loại, tách dấu phẩy nên tổng có thể vượt số tin); không kết luận được tỷ lệ remote của thị trường từ trường phân loại này.

> **Đổi phép đo so với bản trước**: biểu đồ cũ đọc `job-posting-schema.employmentType` ("FULL_TIME" 1000 tin), biểu đồ mới đọc dòng **"Hình thức" trong `detail-box`** (nguyên văn tiếng Việt của trang tin: "Nhân viên chính thức" 976 tin) — hai nguồn khác nhau nên số tuyệt đối khác nhau, tỷ lệ 98,2% trùng nhau là bất ngờ chứ không phải cùng một phép đo.

### 4.15. Biểu đồ 15 — Độ dài nội dung mô tả công việc (`detail-row["Mô tả Công việc"]`)

![15. Độ dài nội dung mô tả công việc](figures/careerviet/15_jd_length_groups.png)

- **Quan sát:** Section 'Mô tả Công việc' (key của `detail-row`) xuất ở 1.013/1.018 tin (99,5%); các section khác: 'Yêu Cầu Công Việc': 1.017 tin, 'Phúc lợi': 1.017 tin; trung vị IT 1.036 ký tự so với ngoài IT 962 (+7,7%); 491 tin (48,2%) dưới 1.000 ký tự. `description` JSON-LD đầy đủ ở 1.018/1.018 tin, trung vị 2.127 ký tự text thuần (đã bóc thẻ HTML).
- **Ý nghĩa:** Độ dài JD hầu như không phân biệt việc IT với việc ngoài IT; muốn tách hai nhóm phải dùng nội dung (từ điển kỹ năng, Job Family), không dùng dung lượng văn bản.
- **Hạn chế:** `detail-box` CHỈ là hộp metadata (rỗng ở 24 tin), JD thật nằm trong `detail-row` và `job-posting-schema.description`; độ dài text phẳng chưa tính thẻ HTML nên không so sánh được với token của mô hình ngôn ngữ.

> **Lưu ý về hai con số text thuần của `description` JSON-LD**: biểu đồ 15 (dùng `flat_text` của `careerviet_eda_charts.py`) cho trung vị **2.127**; §1.1 và `careerviet_report_fill.py` cho **2.149** (min 472 / max 10346 so với 468 / 10265). Khác nhau chỉ do quy ước whitespace khi bóc thẻ: `flat_text` **không chèn space tại biên giới tag** (`<p>a</p><p>b</p>` → `"ab"`), nên văn bản ngắn hơn một chút. Kết luận "không mất nội dung mô tả ở tầng raw" (1018/1018 có `description`) không đổi.

> **Lưu ý cấu trúc (giữ từ bản trước)**: biểu đồ này từng đo `detail-box` — nhưng `detail-box` **chỉ là hộp metadata** (Lương / Kinh nghiệm / Ngày cập nhật / Hình thức), **không phải** mô tả công việc. Script đã sửa để khớp cấu trúc envelope thật (`raw_envelope.py:170-185`).

### 4.16. Biểu đồ 16 — Ledger CDC (đối chiếu Phase 1)

![16. Ledger CDC (đối chiếu Phase 1)](figures/careerviet/16_ledger_cdc.png)

- **Quan sát:** catalog_master: 1.029 URL của careerviet, 1.029 DONE, 11 DONE + có `repost_of_url_hash`, 0 chưa DONE, 0 URL có `error_log`; 1.018 URL có `latest_version >= 1` = 1.018 envelope EDA.
- **Ý nghĩa:** Đẳng thức 1.029 URL - 11 repost = 1.018 envelope khớp chính xác với số tin đã đo; không có tin mất không rõ nguyên nhân và không có lỗi mạng tồn đọng.
- **Hạn chế:** Ledger là trạng thái tại thời điểm đọc; `manifests/*.jsonl` chỉ là ảnh chụp lúc phát hiện (vẫn ghi PENDING) nên không dùng nó để đo trạng thái crawl.

### 4.17. Tổng hợp so sánh IT vs ngoài IT (chỉ số đo từ 16 biểu đồ trên)

| Chỉ báo | Nhóm IT | Nhóm ngoài IT | Khoảng cách | Nguồn |
| :--- | :---: | :---: | :--- | :---: |
| Tin trong mẫu | 591 (58,1%) | 403 (39,6%) | 24 tin không phân loại tách riêng | H2 |
| Tỷ lệ công khai lương đọc được | 33,3% | 58,3% | IT công khai lương **ít hơn** | H5 |
| Trung vị lương (triệu VND/tháng) | 20 (n = 197) | 15 (n = 235) | **+33,3%** | H6 |
| IQR lương | 15–27,5 | 11,5–19,5 | IT rải rộng hơn | H6 |
| Tin trống `job-tags` | 138 (23,4%) | 62 (15,4%) | IT phủ tag **kém hơn** | H10 |
| Trung vị độ dài JD (ký tự) | 1.036 | 962 | +7,7% (gần như bằng nhau) | H15 |
| Cơ cấu IT theo địa bàn dày nhất | Hà Nội 77,5% IT | Hồ Chí Minh 47,8% IT | **29,7 điểm phần trăm** | H8 |

**Đọc bảng**: khác biệt lớn nhất giữa hai nhóm là **cách tin được đăng** (tỷ lệ công khai lương, độ phủ tag, địa bàn) chứ không phải **nội dung** (độ dài JD gần bằng nhau, phúc lợi đứng đầu giống nhau). Đây là căn cứ để Phase 2 **không** dùng dung lượng văn bản hay `job-tags` làm bộ lọc IT, mà giữ `Ngành nghề` + thêm từ điển kỹ năng.

---

## 5. Kế Hoạch Điền Số — Trạng Thái

| Bước | Lệnh | Trạng thái | Ghi chú |
| :---: | :--- | :---: | :--- |
| 1 | ~~`crawler --online --limit 20 --source-category c37`~~ | ✅ | Tài chạy online **toàn bộ PENDING** (không giới hạn 20), kết quả 16-17/10 → **1018 envelope**, 1029 DONE, 11 repost. |
| 2 | `python -X utf8 scripts/careerviet_raw_stats.py` | ✅ | null rate + CDC counts (xem §1.1, §3.3). |
| 3 | `python -X utf8 scripts/careerviet_it_check.py` | ✅ | Tỉ lệ CNTT `Ngành nghề` = 58.1 % (xem §3.4). |
| 4 | Điền §1.1, §3.1, §3.2, §3.3, §3.4 + `docs/crawl/careerviet.md §9.4` + `reports/careerviet_inventory.md` bằng số từ `careerviet_report_fill.py`. | ✅ (báo cáo này) | Mục 2 (outlier số) giữ SAU INTEGRATION. |
| 4b | `python -X utf8 scripts/careerviet_eda_charts.py` | ✅ (lượt 2026-10-18) | 16 biểu đồ ở `reports/figures/careerviet/`, inline ở §4. Ba sửa lớn: (1) biểu đồ 15 đo `detail-row` (JD thật) thay `detail-box` (metadata); (2) `flat_text` đã vá để giữ nguyên chữ có `&` không đóng entity ("Nhân viên C&B", "D&C") — trước đó 3 `title` + 5 `job-company-name` bị đếm nhầm thành rỗng; (3) tiêu đề/phụ đề dài tự xuống dòng theo bề rộng thật còn lại. Test hồi quy: `tests/unit/test_careerviet_eda_charts.py` (59 case, offline). |
| 5 | `python -X utf8 -m crawlers.sources.careerviet.crawler --phase sync` | ⏳ | Cần `MINIO_*` env vars (chưa set). |
| 6 | `python -X utf8 scripts/push_raw_to_minio.py --source careerviet …` | ⏳ | Cần `MINIO_*` env vars (chưa set). |

---

## 6. Ghi chú Chất lượng Crawl

- **0 envelope rác**: `_blocked/` = 0 file, `FAILED` = 0, `PENDING` = 0 → `_detect_block` (commit `f977ffb`, 2 điều kiện AND) **giữ nguyên hiệu lực khi online**, không false-positive (không chặn nhầm 200 OK thành captcha), không false-negative (không cho qua captcha thật).
- **Rủi ro R3 đã loại**: eyeball `raw_payload` trên envelope ngẫu nhiên → có **8 key** (`title`, `job-company-name`, `detail-box`, `detail-row`, `job-tags`, `map`, `Ngành nghề`, `job-posting-schema`) và `.job-detail-page` có nội dung thật. **Không** có envelope vỏ rỗng: `detail-row` đầy đủ ở **1017/1018**, `description` JSON-LD **1018/1018**. Nội dung JD dài nhất **6821** ký tự (section `Mô tả Công việc`) → không phải dữ liệu rác.
- **Tốc độ thực đo**: 1018 envelope trong 4622 s = **4.54 s/tin TB**, khớp `DelayConfig(2.0–5.0)` + parse time, **không có chuỗi 5xx** nên `CONSECUTIVE_SERVER_ERROR_STOP=3` không kích hoạt.
- **DoD 4 (3 layout)**: **bằng chứng phủ định** — Careerviet có 1 template DOM; 4 tổ hợp biến thể (`detail-row` × `job-tags`) đã có mẫu hồi quy; xem `docs/crawl/careerviet.md §8.5`.

---

**Kết luận**:

1. EDA tầng raw CareerViet **hoàn tất** với **1018 envelope / 42 địa điểm / 494 công ty / 2480 tag / 4 bucket / 11 repost**.
2. **58.1 %** là IT theo `Ngành nghề`; bucket c37 có **48.7 % IT / 51.3 % non-IT** — bằng chứng quyết định `--include-c37` (commit `1470de0`) là **cần thiết** để đo tỉ lệ này.
3. **Nội dung công việc được bảo toàn ở tầng raw**: `detail-row` (Dict heading→text) có ở **1017/1018**, `job-posting-schema.description` có ở **1018/1018** (median 2.149 ký tự text thuần theo `report_fill.py`; 2.127 theo `flat_text` của script vẽ — hai quy ước whitespace, xem §4.15). Lưu ý **`detail-box` ≠ mô tả** (chỉ là hộp metadata) — Integration phải map đúng (`raw_envelope.py:163-186`).
4. **So sánh IT vs ngoài IT (tổng hợp §4.17)**: lương trung vị nhóm IT **20** so với ngoài IT **15** triệu/tháng (**+33,3%**, nhưng chỉ trên 432 tin công khai lương = 42,4% mẫu); IT lại **kém minh bạch hơn** ở hai chiều còn lại: chỉ **33,3%** tin IT đọc được lương (ngoài IT 58,3%) và **23,4%** tin IT trống tag (ngoài IT 15,4%). Độ dài JD gần như bằng nhau (1.036 vs 962 ký tự, +7,7%) → không dùng dung lượng văn bản làm bộ lọc IT.
5. EDA số học (outlier, correlation, boxplot lương theo tỉnh) thuộc tầng Data Integration; **boxplot lương IT vs ngoài IT đã có ở tầng raw** (§4.6).
6. `--phase sync` + `push_raw_to_minio.py` còn chờ credentials `MINIO_*` để đưa 1018 envelope + ledger lên bucket `vn-it-jobs`.
