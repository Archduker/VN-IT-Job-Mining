# Bước 01: Clean

> Code: `preprocessing/clean/run.py` (`clean_source`, `cross_source_dedup`, `review_sample`, `run`); `preprocessing/common/it_filter.py` (`classify`, `classify_unknown`), `raw_reader.py` (`read_raw`, `snapshot_order`); chính sách `preprocessing/clean/it_policy.json`, `scope_keywords.json`.
> Lệnh: `python scripts/run_preprocessing.py --step clean --source all [--dry-run]`.
> Dữ liệu mẫu: [`samples/01_clean.json`](samples/01_clean.json) (chạy lại 18/11/2026 sau các quyết định L-50, code `591391b`).
> Prompt: [`docs/prompting/preprocessing/01_clean.md`](../../prompting/preprocessing/01_clean.md); bộ lọc IT mới (19/11): [`01_clean_it_filter.md`](../../prompting/preprocessing/01_clean_it_filter.md).
> **Bản sửa 19/11 (người dùng duyệt 19/11):** C4a ba tầng theo định nghĩa "vai trò IT" (mục 2.1), dùng từ điển kỹ năng v2; nghiệm thu lấy precision IT làm chỉ số chính (mục 6). Chạy thật bước 01 với luật mới ngày 19/11: số ở mục 2, 4, 6 là của lần chạy này.

## 1. Mục đích

- Chỉ giữ **tin IT thật, còn nội dung, mỗi tin một snapshot**.
- Tiêu chí: **accuracy** (đúng phạm vi IT), **uniqueness** (một tin một dòng), **timeliness** (giữ bản cào mới nhất, ghi lần cào đầu).
- Phục vụ cả 5 SD. Tin ngoài IT làm sai mọi tỷ lệ (nhóm nghề, kỹ năng, lương), và tin trùng thì bị đếm hai lần.
- Bước này **không** sửa `raw_payload` và **không** làm phẳng ra file. Làm phẳng chỉ chạy trong bộ nhớ để đọc tiêu đề, công ty, JD.

## 2. Luật

Số tin là của lần chạy lại 18/11 (sau khi thêm C9 và đổi luật chọn bản giữ của C7).

| Mã | Điều kiện | Hành động | Số tin |
|---|---|---|---|
| C3 | Bản ghi test (`job-<chữ>-<số>`), thiếu `job_id` hoặc `source_url`, hoặc `metadata.source` khác nguồn đang đọc | drop | 0 |
| C1 | Một `job_id` có nhiều snapshot: giữ bản lớn nhất theo `snapshot_order` (`scraped_at`, rồi `version`). Tin trùng ngay trong file batch cũng tính ở đây | drop | 1.987 |
| C2 | Tin trong file batch cũ đã có file riêng thì bỏ bản batch. Chưa có file riêng thì giữ bản batch (L-25) | drop | 616 (toàn vieclam24h) |
| C4a | Phân loại IT, chỉ gắn nhãn, **ba tầng** (đặc tả duyệt 19/11; code nối vào `clean/run.py` và chạy thật 19/11). **Tầng 0** (`excluded_role`): tiêu đề thuộc nhóm **không phải IT, loại hoàn toàn** ở mục 2.1 (sales/marketing thuần kể cả presales, thiết kế đồ họa, kỹ sư điện/cơ khí, nhúng/IoT, AV, pháp chế dữ liệu, giảng dạy, quản lý vận hành/sản phẩm không làm kỹ thuật) → `non_it`; tầng 1, tầng 2, chuyên mục sàn, tên công ty đều không được lật lại, trừ ngoại lệ đã duyệt ở mục 2.1. **Tầng 1** (`classify`): từ khóa tiêu đề và kỹ năng (gồm nhãn chuyên môn ở `category_tags`), khớp từ nguyên vẹn, ra `it`, `non_it`, `unknown`; danh sách từ khóa sửa theo định nghĩa mục 2.1 (thêm "an toàn thông tin", "an ninh thông tin", "pentest"…). **Tầng 2** (`classify_unknown`), chỉ khi tầng 1 ra `unknown`, dùng 4 tín hiệu: (a) số kỹ năng thuộc **nhóm lõi IT** của `processing/dictionaries/skills_v2.json` khớp trong JD (matcher của bước 08, `matcher_from_v2`); (b) số kỹ năng nhóm `security`; (c) nhóm nghề suy từ tiêu đề (`classify_job_family_rule`); (d) chuyên mục sàn (`raw_category_text`) có từ IT, **chỉ là tín hiệu phụ** (phương án C): chỉ cộng khi đi cùng (a). Danh sách nhóm lõi và các ngưỡng nằm trong `preprocessing/dictionaries/it_filter_v2.json` (`approved` = true mới dùng), chọn trên tập tune của C4b, **ưu tiên precision IT**. Danh sách `TECH_SKILLS` viết tay cũ bị bỏ. **Luật tầng 2 đã duyệt 19/11 (phương án B):** `it` khi (có nhóm nghề và core ≥ 2) hoặc core ≥ 8 hoặc (tin itviec có chuyên mục IT); nhánh bảo mật riêng và chuyên mục ở sàn khác tắt | flag | 19/11: 6.050 tin `non_it` (luật cũ 18/11: 5.424). So đầu ra 18/11: 4.621 → 4.103; 624 tin IT cũ thành `non_it` (tầng 0: 251, tầng 1: 4, tầng 2: 369), 107 tin mới vào (tầng 1: 27, tầng 2: 80); danh sách `data/preprocessing/review/it_filter_flips_2026-11-19.csv`, người dùng chấp nhận 19/11 |
| C4c | Bỏ tin có `it_status` nằm trong `it_policy.json[<nguồn>].drop`. Chính sách được duyệt 09/11; cả 8 nguồn đều bỏ `non_it`. `can_kiem` không bao giờ bị bỏ tự động | drop | 6.050 |
| C5 | JD (mô tả + yêu cầu) dưới **50 từ** (`MIN_JD_WORDS`, chốt 10/11) | drop | 155 |
| C8 | CTV ở tiêu đề hoặc đa cấp ở tiêu đề + JD, theo `scope_keywords.json`. Mã lý do `S3_CTV_TITLE`, `S3_MULTI_LEVEL` | drop | 10 |
| C9 | Ngày đăng (`raw_posted_date`, parse bằng `parse_date` của bước 03) trước `STUDY_START` = 2026-09-01: ngoài kỳ nghiên cứu "tin đăng từ tháng 9". Tin không có ngày đăng thì giữ. Người dùng chốt 18/11 (L-50). Mã lý do `BEFORE_STUDY_WINDOW` | drop | 185 |
| C6 | Trùng trong cùng nguồn theo `dedup_key` = `company_norm \| title_norm` (không có tỉnh và tuần cào, L-40). Giữ bản `crawled_at` mới nhất; nếu bằng nhau thì giữ bản có nhiều trường có giá trị hơn (`filled`) | drop | 140 |
| C7 | Trùng khác nguồn theo cùng `dedup_key`. Chọn bản giữ bằng `c7_winner`, chung luật với D5 của bước 01b (người dùng chốt 18/11): `filled` lớn nhất → sàn uy tín hơn (`PLATFORM_AUTHORITY`) → `crawled_at` mới nhất → `job_id` nhỏ nhất. Bản bị bỏ ghi vào `also_on` của bản giữ, dạng `nguồn:job_id` | drop | 115 |
| C4b | Mẫu gán nhãn tay để đo độ đúng của C4a (mục 6). Không đổi dữ liệu | — | 643 nhãn |

**Theo nguồn** (vào → ra):

| Nguồn | Vào | C1 | C2 | C4c | C5 | C8 | C9 | C6 | C7 | Ra |
|---|---|---|---|---|---|---|---|---|---|---|
| careerviet | 660 | 18 | 0 | 185 | 0 | 0 | 0 | 20 | 22 | 415 |
| glints | 331 | 0 | 0 | 57 | 0 | 1 | 100 | 3 | 8 | 162 |
| itviec | 911 | 1 | 0 | 48 | 0 | 1 | 0 | 33 | 15 | 813 |
| jobsgo | 1.597 | 57 | 0 | 882 | 21 | 3 | 11 | 52 | 41 | 530 |
| topcv | 2.749 | 75 | 0 | 1.231 | 133 | 4 | 1 | 12 | 13 | 1.280 |
| topdev | 3.890 | 1.108 | 0 | 2.588 | 0 | 1 | 0 | 4 | 5 | 184 |
| vieclam24h | 1.276 | 0 | 616 | 525 | 0 | 0 | 1 | 0 | 10 | 124 |
| vietnamworks | 1.947 | 728 | 0 | 534 | 1 | 0 | 72 | 16 | 1 | 595 |
| **Tổng** | **13.361** | 1.987 | 616 | 6.050 | 155 | 10 | 185 | 140 | 115 | **4.103** |

- TopDev bị bỏ 2.588/2.782 tin ở C4c: crawler kéo sai phạm vi, vì API bỏ qua `category_ids=1` (bằng chứng trong `it_policy.json`).
- Cặp nguồn trùng nhiều nhất ở C7 là topcv → jobsgo: 43 tin.
- C9 bỏ nhiều nhất ở glints (100 tin): glints ghi `createdAt` là ngày tạo tin lần đầu, có tin từ 07/2023 vẫn mở. vietnamworks 82 tin, phần lớn đăng tháng 8/2026.
- So lần chạy 18/11 (luật cũ, ra 4.621): C4c bỏ thêm 626 tin, chủ yếu topcv (+296: đồ họa, sales, thiết kế không rõ IT) và vietnamworks (+119); các luật sau C4c bỏ ít hơn vì tin đã bị loại trước. 624 tin IT cũ thành `non_it`, 107 tin mới vào (danh sách ở dòng C4a).
- Lần chạy đầu 18/11: C9 mới bỏ 197 tin; C6 còn 189 (trước 200) và C7 còn 127 (trước 135) vì tin ngoài kỳ bị bỏ trước khi khử trùng. C4a không đổi (5.424), vì nhãn chuyên môn TopCV vẫn được đưa vào bộ lọc qua `category_tags`.

### 2.1. Định nghĩa "tin IT" (người dùng chốt 19/11)

- **Tin IT = vai trò IT:** người làm trực tiếp với hệ thống CNTT. Gồm lập trình, kiểm thử, dữ liệu, AI/ML, hạ tầng, mạng, cloud, DevOps, bảo mật, hỗ trợ kỹ thuật IT, BA/PM/PO của dự án IT. Theo Q5, Q6: kỹ sư tự động hóa, và vai trò phân tích dữ liệu ở ngành khác có dùng Python/SQL (phân tích định lượng, kế hoạch mạng bay) cũng là IT.
- **Không phải tin IT, loại hoàn toàn** (C4c bỏ, không giữ lại để gắn cờ), **kể cả khi công ty là công ty IT hay tin nằm trong chuyên mục IT**:
  - sales, kinh doanh, marketing thuần (bán phần mềm, bán cloud mà không làm kỹ thuật);
  - thiết kế đồ họa;
  - kỹ sư điện, cơ khí;
  - theo Q1–Q4, Q7, Q8: presales / technical sales (kể cả cloud), DPO và privacy compliance, kỹ sư AV (nghe nhìn), kỹ sư nhúng / IoT / firmware, trợ giảng – giảng dạy, quản lý vận hành và product growth không làm kỹ thuật.
- Khi phải đổi chác giữa giữ tin IT và giữ dữ liệu sạch: **ưu tiên sạch** (precision IT).
- Chuyên mục sàn chỉ là tín hiệu phụ: không tự quyết, không cứu được tin ở nhóm loại hoàn toàn.

**Ca ranh giới** (tin thật trong 643 nhãn C4b). Cột "Theo định nghĩa" chỉ ghi ca mà định nghĩa đã nói rõ; ca chưa rõ để ở bảng câu hỏi, không tự suy diễn.

| Tin | Nguồn | Theo định nghĩa |
|---|---|---|
| Postsale Security Engineer | careerviet | IT (bảo mật) |
| Chuyên viên An Toàn Thông tin; Chuyên viên An ninh thông tin - Pentester | careerviet | IT (bảo mật) |
| Nhân Viên Monitoring (SOC: firewall, IDS/IPS, EDR) | jobsgo | IT (bảo mật, vận hành) |
| Trưởng Phòng IT (Sản xuất, Tiếng Trung) | jobsgo | IT (hạ tầng) |
| Kỹ Sư Triển Khai Hệ Thống | jobsgo | IT (triển khai hệ thống) |
| Quản Lý Dự Án Công Nghệ; Project Manager Assistant (dự án phần mềm) | jobsgo, careerviet | IT (PM dự án IT) |
| Business Development (công ty phần mềm, bán AWS/Azure/GCP) | careerviet | Không IT, loại (sales thuần) |
| Nhân Viên Thiết Kế; Chuyên Viên Thiết Kế (đồ họa, bao bì) | topcv | Không IT, loại (thiết kế đồ họa) |
| Kỹ Sư Thiết Kế Điện; Nhân Viên Thiết Kế Hệ Thống Điện, Điện Nhẹ, BMS/SCADA | vieclam24h | Không IT, loại (kỹ sư điện) |

**Ca ranh giới đã hỏi** (người dùng trả lời 19/11: "Q5 IT, Q6 IT, còn lại không IT"):

| # | Tin | Nguồn | Vì sao từng chưa rõ | Chốt |
|---|---|---|---|---|
| Q1 | Cloud Technical Sales / PreSales | jobsgo | Vừa "sales" (loại) vừa "presales kỹ thuật IT" (giữ) | Không IT |
| Q2 | Phụ Trách Bảo Vệ Dữ Liệu (DPO); Privacy Compliance – Junior | topcv | Pháp chế dữ liệu hay bảo mật thông tin | Không IT |
| Q3 | Kỹ Sư Cấu Hình triển khai hệ thống AV; AVVC Events Engineer - Tech Lounge & AV | vietnamworks, itviec | Thiết bị nghe nhìn: điện tử hay hạ tầng IT | Không IT |
| Q4 | Kỹ Sư IoT; Kỹ sư nhúng (firmware) | topcv | Gần kỹ sư điện tử; định nghĩa chưa nhắc nhúng/IoT | Không IT |
| Q5 | KỸ SƯ TỰ ĐỘNG HÓA (dùng C++, Python, SQL) | careerviet | Tự động hóa công nghiệp (cơ khí/điện) hay lập trình | IT |
| Q6 | Chuyên viên phân tích định lượng rủi ro (Python, MATLAB); Nhân viên Kế Hoạch Mạng Bay (Python, SQL) | careerviet, vietnamworks | Dùng công cụ dữ liệu nhưng vai trò là nghiệp vụ tài chính / hàng không | IT |
| Q7 | Research and Teaching Assistant in Business Analytics | vietnamworks | Giảng dạy + phân tích dữ liệu | Không IT |
| Q8 | Operations Manager; Senior/Lead Business Ownership (Product & Growth) ở công ty công nghệ | topcv, itviec | Quản lý vận hành/sản phẩm, không rõ có làm với hệ thống IT | Không IT |

**Ca ranh giới khi soát nhãn C4b** (người dùng trả lời 19/11: "H1,H6 IT, còn lại không IT"):

| # | Nhóm | Chốt |
|---|---|---|
| H1 | UI/UX designer (thiết kế giao diện phần mềm) | IT |
| H2 | Kiểm thử, thiết kế phần cứng, chip (Design Verification, FPGA) | Không IT |
| H3 | Kỹ sư dịch vụ bảo trì máy | Không IT |
| H4 | Kỹ thuật viên viễn thông lắp đặt wifi, cáp quang | Không IT |
| H5 | Kỹ thuật viên sửa máy tính, laptop, IT phần cứng (khác IT helpdesk / IT support nội bộ) | Không IT |
| H6 | Kỹ sư phần mềm nhúng cho tự động hóa (Q5 thắng Q4) | IT |
| H7 | Lập kế hoạch, báo cáo tài chính có dùng SQL (không tính theo Q6) | Không IT |
| H8 | Giám đốc quản lý tài sản nợ – có (ALM) ngân hàng | Không IT |
| H9 | Product marketing kiêm Product Owner | Không IT |

Lập trình PLC cho máy tự động không tính theo Q5 (người dùng bác đề xuất đổi nhãn, 19/11).

## 3. Quy trình xử lý

Thứ tự thực thi trong `clean_source`. Report vẫn ghi luật theo thứ tự mã.

1. `read_raw(data/<nguồn>/raw/)` đọc mọi snapshot `<id>_v<N>.json` và file batch cũ, bỏ qua `_index`, `_quality`, `_listing`, `_listing_failures`. `input.rows` = số snapshot + số tin trong file batch.
2. **C3** chạy trước khi gom theo `job_id`, vì bản ghi thiếu `job_id` thì không gom được.
3. Ghi **lần cào đầu** của mỗi `job_id`: `first_seen[job_id]` = `scraped_at` nhỏ nhất trên mọi snapshot và file batch. Việc này phải làm trước C1, vì C1 bỏ snapshot cũ (PRE-37).
4. **C1** chọn snapshot mới nhất. **C2** bỏ bản batch đã có file riêng.
5. Làm phẳng trong bộ nhớ bằng `flatten_raw_job_record(env, nguồn)`, chỉ để đọc khóa. Không ghi ra file.
6. **C4a** (tầng 0 → tầng 1 → tầng 2, mục 2) gắn khối `metadata.clean` cho mọi tin: `snapshot_file`, `it_rule`, `it_rule_level`, `it_status`, `dedup_key`, `also_on` = [], `first_scraped_at`.
7. **C4c** bỏ theo chính sách. **C5** bỏ JD ngắn. **C8** bỏ CTV và đa cấp. **C9** bỏ tin đăng trước kỳ nghiên cứu (đặt trước C6 để tin ngoài kỳ không được chọn làm bản giữ). Tin bị C5, C8, C9 bỏ được ghi vào `data/preprocessing/rejected/01_clean/<nguồn>.jsonl`.
8. **C6** khử trùng trong nguồn.
9. Sau khi xong cả 8 nguồn: **C7** (`cross_source_dedup`, bản giữ do `c7_winner` chọn) khử trùng khác nguồn và điền `also_on`.
10. **C4b** (`review_sample`): nếu file `data/preprocessing/review/it_<nguồn>.csv` chưa có nhãn thì xuất mẫu (seed 42); đã có nhãn thì chỉ đọc nhãn để đo, **không bao giờ ghi đè**.
11. `check_conserved()` cho từng nguồn: `vào = ra + Σ bỏ`. Sai ở một nguồn thì dừng cả bước, chưa nguồn nào được ghi.
12. Ghi `data/preprocessing/01_clean/<nguồn>.jsonl`, report từng nguồn và `_all.json`. Chạy lẻ một nguồn thì report vào `reports/preprocessing/_partial/`, và CLI từ chối chạy thật.

## 4. Input → Output

| | Đường dẫn | Định dạng | Số dòng 18/11 |
|---|---|---|---|
| Input | `data/<nguồn>/raw/<YYYY-MM-DD>/<id>_v<N>.json` (+ `batch_001.json` của vieclam24h, `raw_batch.json` của vietnamworks) | JSON envelope `{metadata, raw_payload}` | 13.361 bản ghi |
| Output | `data/preprocessing/01_clean/<nguồn>.jsonl` | jsonl, mỗi dòng một envelope | 4.103 |
| Bị loại (C5, C8, C9) | `data/preprocessing/rejected/01_clean/<nguồn>.jsonl` | jsonl: `source`, `job_id`, `rule`, `reason`, `source_url`, `job_title` | 397 |
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
| `it_rule_level` | 0, 1 hoặc 2 (0 = nhóm loại hoàn toàn, thêm 19/11) |
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
| C9 | glints `02ab8190…` (Performance Tester) | `raw_posted_date` "2023-07-14T05:17:27.342Z" | bỏ, `BEFORE_STUDY_WINDOW` |
| C9 | glints `10adb15c…` (Fullstack Developer) | "2026-05-13T07:14:13.131Z" | bỏ |
| C6 | glints `05decc01…` | khóa `kết nối nhân lực worklink\|kỹ thuật viên it phần mềm - kcn long đức - đồng nai` | bỏ, giữ `83fe5651…` |
| C7 | glints `091b32f4…` | khóa `kinh doanh f88\|chuyên viên cao cấp rủi ro gian lận (fraud risk data analyst)` | bỏ, giữ `jobsgo:29391080129` |

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Cách | Kết quả 19/11 |
|---|---|---|
| Luật bảo toàn | `checks.rows_conserved` trong `_all.json` và từng nguồn | Đạt (13.361 = 4.103 + 9.258) |
| So với lần trước | `scripts/visualize_preprocessing_steps.py` so luật với report trong git HEAD | Khác 18/11 do luật C4a mới (mục 2) |
| Độ đúng bộ lọc IT (C4b) | 643 nhãn trong `data/preprocessing/review/it_<nguồn>.csv`, đo bằng `validation_metrics` | Xem bảng dưới |
| Test | `pytest tests/unit/test_clean_step.py` | Xanh (gồm `first_scraped_at`, `test_c9_out_of_study_window`, `test_c7_keeps_most_complete_then_most_authoritative`) |
| Trang | `docs/presentation/preprocessing_steps/01_clean.html` | Có |

**Nghiệm thu bộ lọc IT từ 19/11:**

- Nhãn C4b được soát lại theo định nghĩa mục 2.1 (file nhãn đổi `data/preprocessing/gold/it_review/relabel_2026-11-19.csv`, người dùng duyệt trước khi áp).
- Chia nhãn: tập **tune** 70% để chọn ngưỡng, tập **giữ lại** 30% để báo số nghiệm thu (phân tầng theo nguồn, seed 42).
- Chỉ số chính: **precision IT** trên tập giữ lại, kèm khoảng tin cậy Wilson 95%. Báo kèm độ đúng chung, recall IT, precision non-IT, theo tầng và theo nguồn.
- Đo bằng `scripts/eval_it_filter.py` (chỉ đọc), ghi `data/preprocessing/review/it_filter_eval.json`.
- Đích ≥ 95%. Chưa đạt thì báo thật số cho người dùng quyết, không hạ đích.

**Kết quả luật mới (phương án B, 19/11), nhãn phiên bản 2 (168 IT, 475 không IT):**

| Tập | n | Đúng chung | Precision IT | Recall IT | Precision non-IT |
|---|---|---|---|---|---|
| Giữ lại | 192 | 94,8% [90,7; 97,2] | **97,6% [87,7; 99,6]** | 82,0% | 94,0% |
| Cả 643 | 643 | 95,0% [93,1; 96,5] | 95,3% [90,7; 97,7] | 85,1% | 94,9% |
| Luật cũ, giữ lại | 192 | 93,2% | 93,0% [81,4; 97,6] | | |

- Theo tầng (cả 643): tầng 0 đúng 99,6% (265 tin), tầng 1 95,7% (211), tầng 2 86,8% (167).
- Theo nguồn (cả 643, precision IT / recall IT): topcv 100% / 87,1%; topdev 100% / 83,3%; vieclam24h 100% / 100%; itviec 97,4% / 92,7%; careerviet 94,7% / 78,3%; jobsgo 92,9% / 76,5%; vietnamworks 90,9% / 74,1%; glints 90,0% / 94,7%.
- Precision IT trên tập giữ lại đạt đích; đúng chung trên tập giữ lại 94,8%, thấp hơn đích 0,2 điểm; cận dưới khoảng tin cậy đều dưới 95%. Đóng PRE-12 hay không do người dùng quyết.


**Độ đúng bộ lọc IT trên 643 nhãn (luật cũ, nhãn phiên bản 1, 18/11; để so):**

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

- **Trạng thái:** có code; chạy thật 18/11 trên tập raw đang có trên R2, chạy lại cùng ngày sau các quyết định L-50 (C9, luật bản giữ C7, `category_tags`). Chạy thật lần nữa 19/11 với bộ lọc IT ba tầng (ra 4.103 tin).
- **Chỗ thiếu so với bảng Silver:**
  - Bộ lọc IT (19/11): precision IT 97,6% trên tập giữ lại, đúng chung 94,8%. Recall IT còn thấp ở vietnamworks (74,1%) và jobsgo (76,5%): luật ưu tiên sạch nên bỏ nhầm một phần tin IT (PRE-12).
  - Khóa C6, C7 chỉ gồm công ty + tiêu đề, nên tin cùng công ty mà tên viết khác ("MBBANK" và "Ngân hàng TMCP Quân đội") vẫn lọt (PRE-33).
- **Làm lại bộ lọc IT (19/11):** đo thử trên 240 tin tầng 2: luật cũ đúng 0,821; chỉ đếm kỹ năng kỹ thuật v2 đúng 0,40–0,80 (v2 có cả Excel, CAD, cơ khí); chỉ đếm nhóm lõi IT tối đa khoảng 0,82; luật cũ + "≥ 4 kỹ năng bảo mật" 0,85; chuyên mục sàn chỉ đáng tin ở itviec (24 IT / 1 không IT), vieclam24h 0 IT / 23 không IT. Vì vậy luật mới phối hợp 4 tín hiệu thay vì chỉ đếm kỹ năng.
- **Việc mở:** PRE-12, PRE-33, PRE-35.
