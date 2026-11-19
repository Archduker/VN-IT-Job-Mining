# ĐẶC TẢ PRE-PROCESSING (bước 00–04)

> **Dự án:** VN-IT-Job-Mining. Đề tài: "Tích hợp và khai phá dữ liệu thị trường lao động phục vụ phân tích nghề nghiệp và kỹ năng trong IT".
> **Phiên bản:** 3.1.0, ngày 18/11/2026. **Trạng thái:** 3.0.0 đã duyệt 17/11/2026 (chặng 2). Bản 3.1.0 tách đặc tả chi tiết từng bước sang `docs/spec/preprocessing/`; các luật mới trong đó (03 T3b, T6.5, T9; 04 N14 sửa, N19, M4 sửa, S1) chờ duyệt.
> **Thay cho:** bản 2.0 (đặc tả theo thiết kế 13 bước), các file P0–P4 và PH0–PH7 trong `docs/spec/preprocessing/spec/`, và các file thiết kế cũ trong `docs/spec/preprocessing/`.
> **Quan hệ với tài liệu khác:** mã bước, thư mục và đường dẫn lấy theo [spec 03](03_data_mining_lifecycle.md) mục 3.1. Mục tiêu lấy theo [`docs/target/`](../target/00_de_tai.md). Processing (bước 07–12) đặc tả ở [spec 06](06_processing_spec.md).

## 0. Cách đọc

- **Nguồn sự thật**, xếp theo thứ tự ưu tiên:
  1. Code: `scripts/run_preprocessing.py` (`CHAIN`, `MODULES`), `preprocessing/common/__init__.py` (`STEPS`), `preprocessing/<bước>/run.py`.
  2. Report của lần chạy thật gần nhất: `reports/preprocessing/<bước>/_all.json`.
  3. Đặc tả cũ, chỉ lấy phần còn khớp với code.
- **Số liệu trong file này** lấy từ report chạy thật ngày 10–11/11/2026 (`code_version` 37bb865), trừ khi ghi ngày khác. Số của lần chạy 18/11 nằm trong file từng bước. Dữ liệu đang được làm sạch tiếp (PRE-35), nên các số này sẽ đổi.
- **Mỗi bước** có một file đặc tả chi tiết trong `docs/spec/preprocessing/`, theo cùng một khuôn 7 mục (mục 3). File này giữ hợp đồng chung (mục 2), bảng sạch cuối và bảng Silver (mục 4).
- Mã luật có tiền tố theo bước: `C` (01), `D` (01b), `I` (02), `T` (03), `N` và `M` (04). `M` là các luật xử lý thiếu và ngoại lai, gộp vào 04.

## 1. Pre-processing phục vụ SD nào

Pre-processing biến raw của 8 sàn thành **một bảng sạch**, mỗi dòng là một tin IT duy nhất. Mọi SD đều đọc bảng này, trực tiếp hoặc qua Processing.

| Cột trong bảng sạch | Bước tạo | SD dùng |
|---|---|---|
| `job_family` (10 nhóm + Other) | 04 N3 | SD1, SD2 (luật theo nghề), SD3 (đối chiếu cụm), SD4, SD5 |
| `seniority`, `seniority_level` (5 cấp) | 04 N2, M3c | SD1, SD2, SD4, SD5 (lọc tin người mới) |
| `tinh_chinh` (34 tỉnh) | 04 N1, N13 | SD1, SD4 |
| `work_mode` | 04 | SD1 |
| `posted_month` | 03 (chưa có, PRE-37) | SD1 |
| `salary_min_vnd`, `salary_max_vnd`, `is_negotiable`, `salary_status`, các cờ ngoại lai | 03 T2, 04 N6–M8 | SD1, SD4 |
| `exp_min_years`, `exp_source` | 03 T4, 04 M4 | SD1, SD4, SD5 |
| `skills_std` | 03 T7, 04 N4 | SD2, SD4, SD5 (Processing 08 rút lại kỹ năng từ JD) |
| `description_clean`, `requirements_clean`, bản dịch `*_vi` | 03 T6, T6b | SD3 (qua 07, 09, 12) |
| `company_key` | 04 N18 | SD4 (chia train/test theo công ty, bước M5) |
| `source_platform`, `also_on` | 01, 02 | Mọi SD (đếm theo nguồn, truy vết) |

Pre-processing **không** trả lời câu hỏi nào của SD. Nhiệm vụ của nó là làm cho dữ liệu đạt 5 tiêu chí: completeness, accuracy, consistency, timeliness, uniqueness.

## 2. Hợp đồng chung

### 2.1. Chuỗi bước

```text
data/<nguồn>/raw/                      (raw, bất biến)
  │  00 profiling     chỉ đọc, đo trước và sau làm sạch
  ▼  01 clean          lọc tin IT, bỏ tin rác, chọn snapshot; vẫn giữ dạng envelope, file theo nguồn
  ▼  01b deduplication khử trùng 3 tầng; vẫn file theo nguồn
  ▼  02 integration    làm phẳng về 18 trường chung, gộp 8 nguồn vào một all.parquet
  ▼  03 transformation làm sạch ký tự, parse số và ngày, nhận ngôn ngữ, dịch EN→VI, rút kỹ năng, tách địa điểm
  ▼  04 normalization  đưa về danh mục chuẩn; xử lý thiếu và ngoại lai bằng cờ
data/preprocessing/04_normalization/all.parquet   (bảng sạch, mục 4)
```

- Lệnh chạy: `python scripts/run_preprocessing.py --step <bước>|all --source <nguồn>|all [--dry-run] [--translate]`. Lệnh này chạy cả Processing (07–12) nếu chọn `all`.
- **Output của bước N là input duy nhất của bước N+1.** Chỉ bước 01 đọc raw.
- **Thứ tự không được đảo.** Lý do ở spec 03 mục 4.
- Từ bước 02 trở đi, dữ liệu 8 nguồn nằm chung một file `all.parquet`, có cột `source_platform`. Chạy thật mà thiếu nguồn thì driver dừng, vì sẽ ghi đè `all.parquet` bằng một phần dữ liệu (`run_chain`).
- Dry-run chỉ đọc và ghi report, không ghi dữ liệu. Nếu thiếu đầu ra của bước trước, bước đó báo `INPUT_MISSING`, không điền 0.
- Chạy lẻ một nguồn thì report ghi vào `reports/preprocessing/_partial/<bước>/`, không đè report chính.
- Pre-processing chỉ ghi trên máy. Muốn đẩy lên R2 thì dùng `scripts/push_preprocessing_to_r2.py` (chạy thử trước, người dùng duyệt rồi mới `--push`).

### 2.2. Layout file

| Bước | Dữ liệu | Bản ghi bị loại | Report |
|---|---|---|---|
| 00 | — | — | `reports/preprocessing/00_profiling/{before_clean,after_clean}/` |
| 01 | `data/preprocessing/01_clean/<nguồn>.jsonl` | `data/preprocessing/rejected/01_clean/<nguồn>.jsonl` | `reports/preprocessing/01_clean/<nguồn>.json`, `_all.json` |
| 01b | `data/preprocessing/01b_deduplication/<nguồn>.jsonl`, `golden_master_jobs.parquet`, `duplicates_audit.csv` | (trong `duplicates_audit.csv`) | `reports/preprocessing/01b_deduplication/…` |
| 02 | `data/preprocessing/02_integration/all.parquet` | `data/preprocessing/rejected/02_integration/<nguồn>.jsonl` | `reports/preprocessing/02_integration/…` |
| 03 | `data/preprocessing/03_transformation/all.parquet` | — (không bỏ dòng) | `reports/preprocessing/03_transformation/…` |
| 04 | `data/preprocessing/04_normalization/all.parquet` | — (không bỏ dòng) | `reports/preprocessing/04_normalization/…`, `anomalies.json` |

- `data/preprocessing/` không đưa vào git. `reports/preprocessing/` có trong git, vì Monitoring đọc thư mục này.
- Mẫu gán nhãn tay nằm ở `data/preprocessing/review/it_<nguồn>.csv`. File nào đã có nhãn thì không bao giờ bị ghi đè.
- Bộ gold 100 JD nằm ở `data/preprocessing/gold/gold_labels.json`, gắn với mẫu `e58bceb3a5`. Không dựng lại mẫu, vì làm vậy nhãn sẽ không còn khớp (PRE-33).

### 2.3. Report của bước

Mọi bước ghi report theo một schema chung, dựng bằng `preprocessing/common/step_report.py`. Các khóa: `step`, `source`, `mode` (`dry_run` hoặc `applied`), `generated_at`, `code_version`, `input`, `output`, `dropped[]`, `rules[]`, `fields[]`, `checks`, `api`, `extra`, `samples`.

- **Luật bảo toàn:** `input.rows = output.rows + Σ dropped[].rows`. Nếu sai thì cả bước dừng và không nguồn nào được ghi.
- `rules[]`: mỗi luật có `id`, `name`, `action` (`drop`, `flag`, `modify`), `rows_affected`, `by_source`, và tối đa 3 ví dụ trước → sau có link tin. Ví dụ được chọn ổn định, nên chạy lại vẫn ra cùng ví dụ.
- `fields[]`: độ phủ của từng trường, trước và sau bước.
- `samples`: mẫu trước → sau (seed 42) do driver gắn thêm vào.
- `api`: bước nào có dùng model thì ghi tên và phiên bản model. Bước không dùng model ghi `used: false`.

### 2.4. Ranh giới bước

| Bước | Được làm | Không được làm |
|---|---|---|
| 01 | Bỏ dòng (snapshot cũ, test, ngoài IT theo chính sách đã duyệt, JD ngắn, CTV/đa cấp, trùng khóa); gắn cờ vào `metadata.clean` | Sửa `raw_payload`, làm phẳng, parse |
| 01b | Bỏ dòng trùng; gắn `metadata.dedup`, `merged_from`, `duplicate_of` | Sửa nội dung trường |
| 02 | Ánh xạ trường, làm phẳng, đọc dự phòng (JSON-LD), kiểm schema; bỏ dòng hỏng JSON hoặc sai schema | Parse số, đổi tiền, bù giá trị |
| 03 | Ép kiểu, parse, làm sạch chữ, nhận ngôn ngữ, dịch, rút kỹ năng và phúc lợi, tách địa điểm | Bỏ dòng, cap ngoại lai, log, ghi đè cột `raw_*` |
| 04 | Ánh xạ về danh mục chuẩn, suy giá trị thiếu **có cờ**, gắn cờ ngoại lai, winsorize ra cột riêng, log | Bỏ dòng, ghi đè cột gốc, bù lương bằng trung bình hoặc trung vị |

### 2.5. Dùng model

- Phân loại IT, chuẩn hóa và xử lý thiếu đều dùng **luật if-else và từ điển**. Lý do: chạy lại ra cùng kết quả, không tốn chi phí, không cần khóa API.
- Có đúng hai model có sẵn, cả hai chạy local:

  | Model | Bước | Việc | Ghim phiên bản |
  |---|---|---|---|
  | fastText `lid.176` | 03 T6 | Nhận diện ngôn ngữ JD (`vi`, `en`, `other`) | sha256 của file model ghi trong report |
  | `VietAI/envit5-translation` | 03 T6b | Dịch description và requirements tiếng Anh sang tiếng Việt | commit `840bc88104d5…` (`preprocessing/translation/core.py`) |

- JEV, OpenJev, Qwen, Gemini đã bỏ (L-28). Muốn thêm model khác phải được người dùng đồng ý.

## 3. Các bước

Từ 18/11/2026, đặc tả chi tiết của từng bước nằm trong `docs/spec/preprocessing/` ([mục lục](preprocessing/README.md)), mỗi bước một file theo cùng khuôn 7 mục:

1. Mục đích.
2. Luật.
3. Quy trình xử lý theo thứ tự trong code.
4. Input → output.
5. Dữ liệu mẫu của lần chạy thật, gồm tin mẫu xuyên suốt `topcv_2325743`.
6. Kiểm tra.
7. Chỗ thiếu.

Luật chi tiết chỉ ghi ở file của bước, không chép lại ở đây. Prompt để làm hoặc làm lại từng bước nằm trong `docs/prompting/preprocessing/`.

| Bước | Mục đích | Code | Đầu vào → đầu ra | Lần chạy thật gần nhất | Đặc tả chi tiết |
|---|---|---|---|---|---|
| 00 Profiling | Đo thiếu và chất lượng chữ trước và sau làm sạch | `scripts/profile_sources.py` | raw, bảng 03 → `reports/preprocessing/00_profiling/` | 10/11 (chạy lại sau 03 mới) | [00_profiling.md](preprocessing/00_profiling.md) |
| 01 Clean | Giữ tin IT (định nghĩa "vai trò IT", bộ lọc ba tầng dùng từ điển kỹ năng v2: đặc tả 19/11 chờ duyệt), còn nội dung, mỗi tin một snapshot; ghi lần cào đầu | `preprocessing/clean/run.py` | `data/<nguồn>/raw/` → `01_clean/<nguồn>.jsonl` | 18/11: 13.361 → 4.621 | [01_clean.md](preprocessing/01_clean.md) |
| 01b Deduplication | Khử trùng theo nội dung JD (3 tầng, MinHash + Jaccard ≥ 0,85, cùng công ty) | `preprocessing/deduplication/run.py` | `01_clean/` → `01b_deduplication/<nguồn>.jsonl` | 18/11: 4.799 → 4.672 | [01b_deduplication.md](preprocessing/01b_deduplication.md) |
| 02 Integration | Làm phẳng 8 schema về 30 cột, gộp `all.parquet` | `preprocessing/integration/run.py` | `01b_deduplication/` → `02_integration/all.parquet` | 18/11: 4.672 → 4.671 | [02_integration.md](preprocessing/02_integration.md) |
| 03 Transformation | Làm sạch chữ, ngôn ngữ, dịch, parse lương, ngày, kinh nghiệm, kỹ năng, phúc lợi, địa điểm; trích JD (T9, chờ duyệt) | `preprocessing/transformation/run.py` | `02_integration/` → `03_transformation/all.parquet` | 18/11 không dịch: 4.671 → 4.671 | [03_transformation.md](preprocessing/03_transformation.md) |
| 04 Normalization | Danh mục chuẩn, chọn giá trị cuối, cờ thiếu và ngoại lai | `preprocessing/normalization/run.py` | `03_transformation/` → `04_normalization/all.parquet` | 10–11/11 | [04_normalization.md](preprocessing/04_normalization.md) |
| Silver | Chọn cột, đổi tên tiếng Anh (mục 4.4) | chưa có (PRE-39) | bảng 04 → `silver.parquet` | — | [silver.md](preprocessing/silver.md) |

## 4. Bảng sạch cuối (Golden Master)

### 4.1. Tên và vị trí (người dùng duyệt 17/11/2026)

Hiện có ba file cùng mang nghĩa "golden", dễ nhầm:

| File | Do ai ghi | Hiện trạng |
|---|---|---|
| `data/curated/curated_flat_golden_jobs.parquet` | Pipeline cũ `scripts/run_staging_integration_pipeline.py` | Chuỗi mới không ghi file này. Vẫn được đọc bởi `mining/config.py` (`DEFAULT_GOLDEN`), `scripts/load_mart_from_parquet.py` (nạp Postgres cho trang Insights), `scripts/create_golden_master_eda_notebook.py` |
| `data/preprocessing/01b_deduplication/golden_master_jobs.parquet` | Bước 01b | Bản hợp nhất sau khử trùng, **chưa làm phẳng, chưa làm sạch**. Không bước nào sau đọc |
| `data/preprocessing/04_normalization/all.parquet` | Bước 04 | Đầu ra cuối của chuỗi mới. `mining/config.py` dùng làm dự phòng; Processing 10 đọc file này |

**Quyết định** (code chưa sửa, việc ghi ở PRE-39):

1. **Bảng sạch cuối = `data/preprocessing/04_normalization/all.parquet`.** Trong tài liệu gọi là "bảng 04" hoặc Golden Master. Không chép sang tên khác.
2. Bỏ tên `data/curated/curated_flat_golden_jobs.parquet`:
   - `mining/config.py`: `DEFAULT_GOLDEN` trỏ về bảng 04, bỏ `FALLBACK_GOLDEN`;
   - `scripts/load_mart_from_parquet.py` và `scripts/create_golden_master_eda_notebook.py` đọc bảng 04.
3. Đổi tên file của 01b thành `golden_records.parquet`, để không trùng nghĩa với bảng sạch cuối.
4. `scripts/run_staging_integration_pipeline.py` là pipeline cũ: đánh dấu là cũ trong `scripts/CLAUDE.md`. Xóa hay giữ thì hỏi riêng ở chặng 5, vì Monitoring vẫn đọc health card do nó sinh ra (`reports/curated_golden_dataset_health_card.json`).
5. Trên R2, bảng 04 vẫn được đẩy vào `curated/preprocessing/` bằng `scripts/push_preprocessing_to_r2.py` (đã có, không đổi).

Spec 03 mục 6 đã ghi theo quyết định này.

### 4.2. Ngày đăng: `posted_month` thay `posted_date` (người dùng chốt 17/11, PRE-37)

- **Bảng sạch không có cột ngày đăng đầy đủ.** Bảng 04 bỏ `posted_date` và `raw_posted_date`. Hai cột này vẫn có ở bảng 02 và 03 để truy vết; bước 01b dùng ngày đăng trong envelope để chọn bản giữ.
- **Cột thay thế** (tạo ở bước 03):
  - `posted_month` (`YYYY-MM`): tháng của `posted_date` nếu nguồn có; nếu không có thì lấy tháng của `first_crawled_at`.
  - Không có cột nguồn tháng: người dùng bỏ `posted_month_source` ngày 17/11 (mục 4.4).
- **Phải là lần cào đầu tiên.** Bước 01 đang chọn snapshot mới nhất (`raw_reader.latest_envelopes`), nên một tin cào lại sau 21 ngày sẽ bị dời sang tháng sau. Vì vậy phải mang `first_crawled_at` qua bước 02.
- **Phạm vi:** tin đăng từ tháng 9, cào trong tháng 10–11/2026. Tháng 9 chỉ có tin từ những nguồn ghi ngày đăng (topcv không có tin nào ở tháng 9), nên khi BI so tháng 9 với tháng 10–11 thì chỉ dùng các nguồn ghi ngày đăng cho gần hết tin (vietnamworks, careerviet, vieclam24h, itviec, glints, jobsgo: 96–100%); bỏ topcv (0%) và topdev (40,4%), vì tin thiếu ngày đăng của hai nguồn này mang tháng cào. Đo trên Bronze 17/11: 1.629 tin đăng tháng 9 (vietnamworks 445, jobsgo 567, itviec 304, vieclam24h 144, careerviet 102, glints 67). Số tin mỗi tháng phụ thuộc lịch cào, nên chỉ so cơ cấu, không so tổng.
- `crawled_at` (lần cào gần nhất) vẫn giữ. `days_to_deadline` ở Processing 10 tính từ cột này.
- `deadline_date` vẫn giữ ở bảng 04, không vào bảng target (mục 4.4).

### 4.3. Thiếu dữ liệu: chiến lược

| Trường | Cơ chế thiếu | Cách xử lý | Lý do |
|---|---|---|---|
| Lương "thỏa thuận" | MNAR (vị trí cao, hoặc tuyển số lượng lớn lương thấp, hay giấu lương) | Không điền. `is_negotiable = true`, số để NaN. SD4 phương án A chỉ train trên tin có lương; tin thỏa thuận được ước tính ở bước M5, không điền vào bảng sạch | Điền trung bình hoặc trung vị tạo một đỉnh giả và kéo lệch phân phối |
| Cấp bậc | MAR (phụ thuộc nguồn, tiêu đề) | Suy từ số năm kinh nghiệm, gắn `level_inferred` | Luôn phân biệt được giá trị gốc với giá trị suy ra |
| Kinh nghiệm | MAR | Intern/Fresher thiếu thì điền 0, gắn `exp_inferred`. Các trường hợp khác để null | |
| Tỉnh | Phần lớn MCAR, tỷ lệ nhỏ | Lấy từ ô địa chỉ khác (N13); không ra thì `tinh_status = unknown` | |
| Kỹ năng | Nguồn không có trường kỹ năng | Rút từ JD bằng từ điển (T7). Processing 08 rút lại trên từng section | |

Mọi giá trị suy ra đều có cờ hoặc cột `*_source`. SD nào cần dữ liệu gốc thì tự lọc theo cờ.

### 4.4. Bảng target (Silver) (người dùng chốt 17/11/2026, bổ sung 18/11/2026)

Bảng 04 là bảng làm việc: giữ mọi cột trung gian, cờ và bản sao để truy vết, nên có hàng trăm cột với tên lẫn Việt và Anh. Người dùng bảng sạch (BI, Monitoring, báo cáo) cần một bảng gọn hơn. Quyết định:

- Thêm một bước cuối ghi `data/preprocessing/04_normalization/silver.parquet`: **chọn cột và đổi tên sang tiếng Anh**, không tính lại giá trị. Bảng 04 `all.parquet` giữ nguyên, vì Processing 07–10 và Mining đang đọc theo tên cột cũ; chuyển dần sang bảng target sau (PRE-39).
- Tên trường tiếng Anh, ở dạng gốc và gọn nhất. Mỗi khái niệm một cột; bản phụ không vào bảng target.
- **Bổ sung 18/11 (người dùng chốt):** 26 trường thay 22.
  - Thêm 3 cờ mà SD1 cần để báo số trung thực: `seniority_inferred` (câu 1.2), `exp_inferred` (câu 1.5: không so kinh nghiệm theo cấp bậc khi kinh nghiệm được điền từ chính cấp bậc), `salary_outlier` (câu 1.4: bỏ tin ngoại lai trước khi tính trung vị).
  - Thêm `employment_type`, bỏ điều kiện "chỉ khi trích được 100%". Tin không rõ để null, BI hiện "Không rõ".
  - Cả 4 cột chép thẳng từ bảng 04, không tính lại.

| Trường | Kiểu | Ý nghĩa | Lấy từ cột bảng 04 | SD |
|---|---|---|---|---|
| `job_id` | string | Mã tin, duy nhất, dạng `<nguồn>_<mã trên sàn>` | `job_id_global` | tất cả |
| `source` | string | Sàn của tin | `source_platform` | SD1 |
| `url` | string | Link gốc | `source_url` | truy vết |
| `title` | string | Tiêu đề đã làm sạch | `job_title_clean` | SD1, SD3 |
| `title_canonical` | string, null | Chức danh chuẩn theo `job_titles.json`; null nếu không khớp (55% tin, 10/11) | `title_canonical` | SD1 |
| `job_family` | string | 10 nhóm + Other | `job_family` | tất cả |
| `seniority` | string, null | Intern/Fresher, Junior, Middle, Senior, Lead/Manager; null nếu không rõ | `seniority` | SD1, SD4, SD5 |
| `seniority_inferred` | bool | true nếu cấp bậc do bước 04 suy ra (từ tiêu đề, kinh nghiệm, loại hợp đồng), không lấy từ ô của sàn | `level_inferred` | SD1 (1.2) |
| `exp_min_years` | float, null | Năm kinh nghiệm tối thiểu; "Không yêu cầu" = 0 | `exp_min_years` | SD1, SD4, SD5 |
| `exp_max_years` | float, null | Năm kinh nghiệm tối đa; "Trên 3 năm" = null | `exp_max_years` | SD1 |
| `exp_inferred` | bool | true nếu `exp_min_years` được điền cận dưới theo cấp bậc (M4), không lấy từ ô của sàn hay JD | `exp_inferred` | SD1 (1.5), SD4 |
| `salary_min` | float, null | Lương thấp nhất, VND/tháng, đã đổi tiền tệ và chặn ngoại lai | `salary_min_vnd_capped` | SD1, SD4 |
| `salary_max` | float, null | Lương cao nhất, VND/tháng | `salary_max_vnd_capped` | SD1, SD4 |
| `salary_negotiable` | bool | Tin ghi "thỏa thuận"; khi đó min/max là null. Giữ để phân biệt với tin parse lương lỗi | `is_negotiable` | SD1, SD4 |
| `salary_outlier` | bool | true nếu lương ngoại lai theo IQR từng cấp bậc (N6). `salary_min/max` đã kẹp ở phân vị 1–99 nhưng tin ngoại lai vẫn còn, nên SD1 bỏ các tin này khi tính trung vị | `is_outlier_salary` | SD1 (1.4, 1.5), SD4 |
| `province` | string, null | Tỉnh/thành chính, 34 tỉnh sau sáp nhập | `tinh_chinh` | SD1 |
| `work_mode` | string | `onsite`, `hybrid`, `remote`, `unknown` | `work_mode` | SD1 |
| `employment_type` | string, null | `full_time`, `part_time`, `contract`, `internship`; null nếu ô của sàn và JD đều không có (đo 18/11: 6,6%, gần hết topdev) | `employment_type` (04 N19) | SD1 |
| `company` | string | Tên công ty đã chuẩn hóa | `company_norm` | SD1 |
| `company_id` | string | Khóa gộp các cách viết của một công ty (rapidfuzz `token_sort` ≥ 90); dùng đếm công ty và chia train/test theo công ty ở SD4 | `company_key` | SD1, SD4 |
| `skills` | list[string] | Kỹ năng chuẩn | `skills_std` → **đổi sang bước 08** (`job_skills.parquet`, từ điển `skills_v2.json`; người dùng chốt K8.9 ngày 18/11). Vì vậy Silver được ghi sau bước 08 | SD1–SD5 |
| `benefits` | list[string] | Phúc lợi chuẩn theo `dictionaries/benefits.json` ([02_integration.md](preprocessing/02_integration.md), PRE-41) | `benefits_std` | SD1 |
| `description` | string | Mô tả công việc, đã bỏ HTML | `description_clean` | SD3 |
| `requirements` | string | Yêu cầu ứng viên, đã bỏ HTML | `requirements_clean` | SD3, SD5 |
| `language` | string | Ngôn ngữ JD: `vi`, `en`, `other` | `language` | truy vết |
| `posted_month` | string | Tháng đăng `YYYY-MM` (mục 4.2) | `posted_month` (PRE-37) | SD1 |

**Trường ngoài target** (vẫn ở bảng 04 để truy vết, không vào `silver.parquet`):

| Trường | Lý do |
|---|---|
| `headcount` | Chưa SD nào dùng; 2.773 tin có số (10/11) |
| `deadline_date` | Là ngày tin đóng, không thay được ngày đăng (gộp vào `posted_month` sẽ dời tin sang tháng sau). Processing 10 vẫn đọc từ bảng 04 để tính `days_to_deadline` |
| `posted_month_source` | Người dùng bỏ khỏi target 17/11. So tháng 9 với tháng 10–11 theo luật nguồn ở mục 4.2 |
| `crawled_at` | Đã có `posted_month` |
| `salary_min_vnd`, `salary_max_vnd` (chưa chặn), `log_salary_*`, `salary_currency_raw`, `salary_period_raw`, `salary_source`, `salary_suspect`, `salary_status`, `salary_out_of_range`, `salary_iqr_*` | Bản trung gian và cờ chất lượng. Bản log do Processing 10 tự tính. `salary_status` suy được từ `salary_min/max` + `salary_negotiable`. `is_outlier_salary` đã vào target (`salary_outlier`) từ 18/11 |
| `locations`, `tinh_cu`, `tinh_key`, `tinh_source`, `tinh_status`, `remote`, `ngoai_vn` | Chi tiết địa điểm; target chỉ cần `province` và `work_mode` |
| `seniority_level`, `seniority_source`, `seniority_can_kiem`, `exp_source`, `exp_conflict`, `exp_min_years_parsed`, `work_mode_source`, `employment_type_source` | Mã số, nguồn giá trị và cờ phụ (`level_inferred`, `exp_inferred` đã vào target từ 18/11) |
| `job_family_source`, `job_family_can_kiem`, `job_family_generic_title`, `job_title_core`, `title_match_score`, `title_tech_hint` | Cờ và bước trung gian của luật N3 |
| `raw_*`, `*_norm`, `*_fold`, `*_vi*`, `translation_status`, `language_conf`, `language_rule`, `skills_list`, `skills_clean`, `benefits_list`, `flags` | Chữ gốc và bản phụ để so khớp, dịch, truy vết |

## 5. Kiểm tra chung

- **Luật bảo toàn** ở mọi bước và mọi nguồn (report `checks.rows_conserved`).
- **Phễu dữ liệu** (dùng cho báo cáo và Monitoring), lần chạy 10/11:

  | Sau bước | Số tin |
  |---|---|
  | Raw (snapshot + tin trong batch) | 13.361 |
  | 01 clean | 4.799 |
  | 01b deduplication | 4.672 |
  | 02 integration | 4.671 |
  | 03 transformation | 4.671 |
  | 04 normalization | 4.671 |

- **Bộ gold 100 JD** dùng để đo bước 01 (IT hay không IT) và các parser ở bước 03, 04 (lương, kinh nghiệm, cấp bậc, địa điểm). Hiện mới đo phần Processing (`scripts/eval_gold_processing.py`). Phần Pre-processing chưa có script đo.
- Test: `tests/unit/test_clean_step.py` và các test theo bước trong `tests/unit/`. Mỗi luật nên có ít nhất một test.

## 6. Chỗ lệch cần biết

| Chỗ lệch | Ảnh hưởng | Xử lý |
|---|---|---|
| Bước 01 vẫn khử trùng theo khóa công ty + tiêu đề (C6, C7: 335 tin), sau đó 01b mới khử trùng theo nội dung (D5: 127 tin) | Khử trùng nằm ở hai bước. C6 gộp mọi tin cùng công ty và cùng tiêu đề, kể cả khác tỉnh | Giữ như code. Ghi nhận rủi ro: cùng tên vị trí ở hai tỉnh bị coi là một tin |
| N13 lấy tỉnh từ trụ sở công ty khi địa điểm làm việc không ra tỉnh. Report có ví dụ "Nhật Bản" → TP. Hà Nội, "Long Thành" → TP. Hồ Chí Minh (Long Thành thuộc Đồng Nai) | Tin làm việc ở nước ngoài bị đếm vào tỉnh trụ sở; có thể sai tỉnh (SD1, SD4) | PRE-38: kiểm 656 tin N13; tin `ngoai_vn` không lấy tỉnh từ trụ sở |
| Report 04 ghi tên luật N3 là "16 nhóm + Other"; docstring `normalization/run.py` cũng vậy | Chỉ sai nhãn. Đầu ra đã là 10 nhóm (L-47) | Sửa chuỗi tên luật khi chạy lại 04 |
| Docstring `transformation/run.py` ghi "không dịch, không gọi model nào" | Sai: 03 có dịch (T6b) và dùng fastText | Sửa docstring |
| `STEPS` còn `05_encoding`; `reports/preprocessing/05_encoding/` có 70 file (PRE-26) | Chuỗi chạy thêm một bước đã bị bước 10 thay thế | Bỏ khỏi `STEPS` (đề xuất spec 03 mục 7, đã duyệt). Ghi ở PRE-39 |
| Docstring và comment trong code trỏ tới `docs/spec/preprocessing/spec/P*.md` | Sau khi xóa các file đó (mục 7), các trỏ này sẽ chết | Đổi sang `docs/spec/05_preprocessing_spec.md` mục tương ứng (PRE-39) |
| Bản 00 `after_clean` đo trên bản 03 cũ | Bảng "trước và sau" lệch vài chục tin | Chạy lại 00 sau mỗi lần chạy lại 03 |

## 7. Tài liệu đã gộp vào spec này

**18/11/2026:** đặc tả chi tiết các bước 00–04 và bảng Silver tách lại thành file riêng trong `docs/spec/preprocessing/` (mục 3), theo yêu cầu của người dùng, để mỗi bước có quy trình, input → output và dữ liệu mẫu. Bảng luật cũ của mục 3 (bản 3.0.0) xem bằng `git show 7aa63a2:docs/spec/05_preprocessing_spec.md`.

Nội dung còn đúng của các file dưới đây đã nằm trong spec này. Người dùng duyệt và các file đã bị xóa ngày 17/11/2026; muốn xem bản cũ thì dùng `git show <commit>:<đường dẫn>`. Cùng đợt đã xóa các bản sao P0–P4 trong `docs/prompting/draft/` và `docs/prompting/preprocessing/`.

- `docs/spec/preprocessing/spec/P0_pipeline_contract.md`, `P1_clean.md`, `P2_integration.md`, `P3_transformation.md`, `P4_normalization.md`.
- `docs/spec/preprocessing/spec/PH0`–`PH7`.
- `docs/spec/preprocessing/00_architecture_overview.md`, `05_post_integration_master_pipeline.md`, `integration/`, `transformation/`, `missing_outlier/`, `normalization/`.
- Thiết kế 13 bước cũ, bước 0–6 (`git show HEAD:"Tiền xử lý dữ liệu JD ngành IT cho Data Mining.md"`).

P5, PH8, PH9 và `docs/spec/preprocessing/encoding/` thuộc Processing, sẽ gộp vào spec 06 ở chặng 3.
