# Bước 01: Clean

> Code: `preprocessing/clean/run.py` (`clean_source`, `cross_source_dedup`, `review_sample`, `run`); `preprocessing/common/it_filter.py` (`classify`, `classify_unknown`), `raw_reader.py` (`read_raw`, `snapshot_order`); chính sách `preprocessing/clean/it_policy.json`, `scope_keywords.json`.
> Lệnh: `python scripts/run_preprocessing.py --step clean --source all [--dry-run]`.
> Dữ liệu mẫu: [`samples/01_clean.json`](samples/01_clean.json) (lần chạy 18/11/2026, `code_version` eb06083).
> Prompt: [`docs/prompting/preprocessing/01_clean.md`](../../prompting/preprocessing/01_clean.md).

## 1. Mục đích

- Chỉ giữ **tin IT thật, còn nội dung, mỗi tin một snapshot**.
- Tiêu chí: **accuracy** (đúng phạm vi IT), **uniqueness** (một tin một dòng), **timeliness** (giữ bản cào mới nhất, ghi lần cào đầu).
- Phục vụ cả 5 SD. Tin ngoài IT làm sai mọi tỷ lệ (nhóm nghề, kỹ năng, lương), và tin trùng thì bị đếm hai lần.
- Bước này **không** sửa `raw_payload` và **không** làm phẳng ra file. Làm phẳng chỉ chạy trong bộ nhớ để đọc tiêu đề, công ty, JD.

## 2. Luật

Số tin là của lần chạy 18/11.

| Mã | Điều kiện | Hành động | Số tin |
|---|---|---|---|
| C3 | Bản ghi test (`job-<chữ>-<số>`), thiếu `job_id` hoặc `source_url`, hoặc `metadata.source` khác nguồn đang đọc | drop | 0 |
| C1 | Một `job_id` có nhiều snapshot: giữ bản lớn nhất theo `snapshot_order` (`scraped_at`, rồi `version`). Tin trùng ngay trong file batch cũng tính ở đây | drop | 1.987 |
| C2 | Tin trong file batch cũ đã có file riêng thì bỏ bản batch. Chưa có file riêng thì giữ bản batch (L-25) | drop | 616 (toàn vieclam24h) |
| C4a | Phân loại IT, chỉ gắn nhãn, hai tầng. **Tầng 1** (`classify`): từ khóa tiêu đề và kỹ năng, khớp theo từ nguyên vẹn, ra `it`, `non_it` hoặc `unknown`. **Tầng 2** (`classify_unknown`), chỉ chạy khi tầng 1 ra `unknown`: tiêu đề thuộc một nhóm nghề và JD có ít nhất 2 kỹ năng. Từ yếu đứng một mình ("kỹ thuật", "engineer", "security") không đủ để tính là IT | flag | 5.424 tin `non_it` |
| C4c | Bỏ tin có `it_status` nằm trong `it_policy.json[<nguồn>].drop`. Chính sách được duyệt 09/11; cả 8 nguồn đều bỏ `non_it`. `can_kiem` không bao giờ bị bỏ tự động | drop | 5.424 |
| C5 | JD (mô tả + yêu cầu) dưới **50 từ** (`MIN_JD_WORDS`, chốt 10/11) | drop | 187 |
| C8 | CTV ở tiêu đề hoặc đa cấp ở tiêu đề + JD, theo `scope_keywords.json`. Mã lý do `S3_CTV_TITLE`, `S3_MULTI_LEVEL` | drop | 13 |
| C6 | Trùng trong cùng nguồn theo `dedup_key` = `company_norm \| title_norm` (không có tỉnh và tuần cào, L-40). Giữ bản `crawled_at` mới nhất; nếu bằng nhau thì giữ bản có nhiều trường có giá trị hơn (`filled`) | drop | 200 |
| C7 | Trùng khác nguồn theo cùng `dedup_key`. Giữ bản có `filled` lớn nhất (bằng nhau thì theo thứ tự `SOURCES`); bản bị bỏ ghi vào `also_on` của bản giữ, dạng `nguồn:job_id` | drop | 135 |
| C4b | Mẫu gán nhãn tay để đo độ đúng của C4a (mục 6). Không đổi dữ liệu | — | 643 nhãn |

**Theo nguồn** (vào → ra):

| Nguồn | Vào | C1 | C2 | C4c | C5 | C8 | C6 | C7 | Ra |
|---|---|---|---|---|---|---|---|---|---|
| careerviet | 660 | 18 | 0 | 189 | 0 | 0 | 19 | 25 | 409 |
| glints | 331 | 0 | 0 | 56 | 0 | 1 | 6 | 14 | 254 |
| itviec | 911 | 1 | 0 | 15 | 0 | 1 | 36 | 16 | 842 |
| jobsgo | 1.597 | 57 | 0 | 787 | 22 | 3 | 92 | 49 | 587 |
| topcv | 2.749 | 75 | 0 | 935 | 164 | 5 | 20 | 13 | 1.537 |
| topdev | 3.890 | 1.108 | 0 | 2.552 | 0 | 2 | 6 | 6 | 216 |
| vieclam24h | 1.276 | 0 | 616 | 475 | 0 | 1 | 0 | 11 | 173 |
| vietnamworks | 1.947 | 728 | 0 | 415 | 1 | 0 | 21 | 1 | 781 |
| **Tổng** | **13.361** | 1.987 | 616 | 5.424 | 187 | 13 | 200 | 135 | **4.799** |

- TopDev bị bỏ 2.552/2.782 tin ở C4c: crawler kéo sai phạm vi, vì API bỏ qua `category_ids=1` (bằng chứng trong `it_policy.json`).
- Cặp nguồn trùng nhiều nhất ở C7 là topcv → jobsgo: 43 tin.

## 3. Quy trình xử lý

Thứ tự thực thi trong `clean_source`. Report vẫn ghi luật theo thứ tự mã.

1. `read_raw(data/<nguồn>/raw/)` đọc mọi snapshot `<id>_v<N>.json` và file batch cũ, bỏ qua `_index`, `_quality`, `_listing`, `_listing_failures`. `input.rows` = số snapshot + số tin trong file batch.
2. **C3** chạy trước khi gom theo `job_id`, vì bản ghi thiếu `job_id` thì không gom được.
3. Ghi **lần cào đầu** của mỗi `job_id`: `first_seen[job_id]` = `scraped_at` nhỏ nhất trên mọi snapshot và file batch. Việc này phải làm trước C1, vì C1 bỏ snapshot cũ (PRE-37).
4. **C1** chọn snapshot mới nhất. **C2** bỏ bản batch đã có file riêng.
5. Làm phẳng trong bộ nhớ bằng `flatten_raw_job_record(env, nguồn)`, chỉ để đọc khóa. Không ghi ra file.
6. **C4a** gắn khối `metadata.clean` cho mọi tin: `snapshot_file`, `it_rule`, `it_rule_level`, `it_status`, `dedup_key`, `also_on` = [], `first_scraped_at`.
7. **C4c** bỏ theo chính sách. **C5** bỏ JD ngắn. **C8** bỏ CTV và đa cấp. Tin bị C5, C8 bỏ được ghi vào `data/preprocessing/rejected/01_clean/<nguồn>.jsonl`.
8. **C6** khử trùng trong nguồn.
9. Sau khi xong cả 8 nguồn: **C7** (`cross_source_dedup`) khử trùng khác nguồn và điền `also_on`.
10. **C4b** (`review_sample`): nếu file `data/preprocessing/review/it_<nguồn>.csv` chưa có nhãn thì xuất mẫu (seed 42); đã có nhãn thì chỉ đọc nhãn để đo, **không bao giờ ghi đè**.
11. `check_conserved()` cho từng nguồn: `vào = ra + Σ bỏ`. Sai ở một nguồn thì dừng cả bước, chưa nguồn nào được ghi.
12. Ghi `data/preprocessing/01_clean/<nguồn>.jsonl`, report từng nguồn và `_all.json`. Chạy lẻ một nguồn thì report vào `reports/preprocessing/_partial/`, và CLI từ chối chạy thật.

## 4. Input → Output

| | Đường dẫn | Định dạng | Số dòng 18/11 |
|---|---|---|---|
| Input | `data/<nguồn>/raw/<YYYY-MM-DD>/<id>_v<N>.json` (+ `batch_001.json` của vieclam24h, `raw_batch.json` của vietnamworks) | JSON envelope `{metadata, raw_payload}` | 13.361 bản ghi |
| Output | `data/preprocessing/01_clean/<nguồn>.jsonl` | jsonl, mỗi dòng một envelope | 4.799 |
| Bị loại (C5, C8) | `data/preprocessing/rejected/01_clean/<nguồn>.jsonl` | jsonl: `source`, `job_id`, `rule`, `reason`, `source_url`, `job_title` | 200 |
| Mẫu gán nhãn | `data/preprocessing/review/it_<nguồn>.csv`; bản lưu trong git ở `data/preprocessing/gold/it_review/` | csv: `job_id`, `source_url`, `job_title`, `skills`, `it_rule`, `it_rule_level`, `it_status`, `nhan_tay` | 643 |
| Report | `reports/preprocessing/01_clean/<nguồn>.json`, `_all.json` | schema chung (spec 05 mục 2.3); `extra.review`, `extra.cross_source_pairs`, `extra.it_policy`, `extra.it_levels` | — |

**Schema đầu ra:**

- Khóa cấp 1: `metadata`, `raw_payload`. `raw_payload` giữ nguyên như raw.
- `metadata` gồm: `job_id`, `source`, `source_url`, `scraped_at`, `scraper_version`, `version`, `language`, `content_hash`, `clean`.
- `metadata.clean` gồm:

| Khóa | Ý nghĩa |
|---|---|
| `snapshot_file` | File raw đã chọn (`<ngày>/<id>_v<N>.json`) |
| `it_rule` | Kết quả tầng 1: `it`, `non_it`, `unknown` |
| `it_rule_level` | 1 hoặc 2 |
| `it_status` | Nhãn cuối sau tầng 2 |
| `dedup_key` | `company_norm\|title_norm` |
| `also_on` | Danh sách `nguồn:job_id` bị C7 gộp vào tin này |
| `first_scraped_at` | Lần cào đầu (thêm 18/11, L-49) |

## 5. Dữ liệu mẫu

### 5a. Tin mẫu `topcv_2325743`

```text
Raw: 2 snapshot
  data/topcv/raw/2026-10-20/2325743_v1.json   version 1   scraped_at 2026-10-20T18:44:44Z   content_hash 858497f5…
  data/topcv/raw/2026-11-01/2325743_v2.json   version 2   scraped_at 2026-11-01T15:04:01Z   content_hash 29d0469f…

C1  → giữ v2 (snapshot_order lớn hơn); v1 bị bỏ, đếm vào C1 của topcv (75 tin)
C4a → tiêu đề "Backend Developer" khớp từ khóa IT ở tầng 1
C4c, C5, C8, C6, C7 → không dính
```

`metadata.clean` ở đầu ra:

```json
{
  "snapshot_file": "2026-11-01/2325743_v2.json",
  "it_rule": "it", "it_rule_level": 1, "it_status": "it",
  "dedup_key": "eaera|backend developer",
  "also_on": [],
  "first_scraped_at": "2026-10-20T18:44:44.698712+00:00"
}
```

`raw_payload` (trích các trường đơn, giữ nguyên): `title` "Backend Developer", `company` "CÔNG TY TNHH EAERA VIỆT NAM", `salary_raw` "400 - 900 USD", `experience` "1 năm", `location` "Hà Nội", `date_posted` "2026-10-08", `deadline_raw` "20/11/2026", `working_time` "Thứ 2 - Thứ 6 (từ 09:00 đến 18:30)…". Danh sách 25 khóa nằm trong `samples/01_clean.json` → `trace.raw_payload_keys`.

### 5b. Ví dụ theo luật

Lấy từ `rules[].examples` của report.

| Luật | Tin | Trước | Sau |
|---|---|---|---|
| C1 | topcv `1714047` | `2026-10-22/1714047_v1.json` | `2026-11-01/1714047_v2.json` (giữ) |
| C2 | vieclam24h `100160858` | `2026-10-20/batch_001.json` | bỏ: đã có file riêng |
| C4a, C4c | glints `0435cda1…` | "HCM925-KỸ THUẬT VIÊN KHUÔN - KCX TÂN THUẬN (KHÔNG KINH NGHIỆM)" | `non_it` → bỏ |
| C4a, C4c | glints `07ec34c7…` | "[BD651] Kỹ sư Cải tiến - Kỹ thuật/Cơ khí/Điện - KCN VSIP1" | `non_it` → bỏ |
| C5 | topcv `1448528` (Embedded Systems Engineer) | JD rỗng | bỏ, lý do `JD_SHORT` |
| C8 | topcv `1251851` | "Cộng Tác Viên Thiết Kế" | bỏ, `S3_CTV_TITLE` |
| C6 | glints `05decc01…` | khóa `kết nối nhân lực worklink\|kỹ thuật viên it phần mềm - kcn long đức - đồng nai` | bỏ, giữ `83fe5651…` |
| C7 | glints `091b32f4…` | khóa `kinh doanh f88\|chuyên viên cao cấp rủi ro gian lận (fraud risk data analyst)` | bỏ, giữ `jobsgo:29391080129` |

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Cách | Kết quả 18/11 |
|---|---|---|
| Luật bảo toàn | `checks.rows_conserved` trong `_all.json` và từng nguồn | Đạt (13.361 = 4.799 + 8.562) |
| So với lần trước | `scripts/visualize_preprocessing_steps.py` so luật với report trong git HEAD | Trùng lần chạy 10/11 |
| Độ đúng bộ lọc IT (C4b) | 643 nhãn trong `data/preprocessing/review/it_<nguồn>.csv`, đo bằng `validation_metrics` | Xem bảng dưới |
| Test | `pytest tests/unit/test_clean_step.py` | Xanh (gồm `first_scraped_at`) |
| Trang | `docs/presentation/preprocessing_steps/01_clean.html` | Có |

**Độ đúng bộ lọc IT trên 643 nhãn:**

- Ai gán nhãn: Claude gán theo rubric của `label_review.py`, chỉ nhìn tiêu đề và kỹ năng. Người dùng bổ sung 48 nhãn trống ngày 18/11.
- Tổng: TP 148, FP 23, TN 436, FN 36.
- Precision IT **86,5%**, precision non-IT 92,4%, recall IT 80,4%, đúng chung 90,8%.
- Đích theo thiết kế là ≥ 95%, nên **chưa đạt** (PRE-12).

| Nguồn | Nhãn | Precision IT | Precision non-IT | Recall IT |
|---|---|---|---|---|
| topcv | 109 | 81,1% | 86,1% | 75,0% |
| topdev | 84 | 100% | 98,7% | 83,3% |
| vietnamworks | 94 | 84,6% | 92,6% | 81,5% |
| careerviet | 80 | 82,4% | 88,9% | 66,7% |
| vieclam24h | 84 | 50,0% | 100% | 100% |
| itviec | 48 | 97,6% | 33,3% | 91,1% |
| glints | 48 | 100% | 96,6% | 95,0% |
| jobsgo | 96 | 76,5% | 89,9% | 61,9% |

## 7. Trạng thái, chỗ thiếu, việc mở

- **Trạng thái:** có code; chạy thật 18/11 trên tập raw đang có trên R2.
- **Chỗ thiếu so với bảng Silver:**
  - Bộ lọc IT chưa đạt 95%. Recall IT thấp ở jobsgo (61,9%) và careerviet (66,7%), tức là bỏ nhầm tin IT. Tầng 2 chưa đọc `raw_category_text` (PRE-12).
  - Khóa C6, C7 chỉ gồm công ty + tiêu đề, nên tin cùng công ty mà tên viết khác ("MBBANK" và "Ngân hàng TMCP Quân đội") vẫn lọt (PRE-33).
- **Việc mở:** PRE-12, PRE-33, PRE-35.
