# Bước 01b: Deduplication

> Code: `preprocessing/deduplication/run.py` (`load_items`, `enrich`, `pick_cross_winner`, `run`), `intra_source.py` (`pick_winner`, `apply_d2`, CDC), `inter_source.py` (`build_blocks`, `exact_cross_pairs`, `clusters`, `fuse`, `PLATFORM_AUTHORITY`), `minhash.py`, `blocking.py`, `text_norm.py`; tham số `preprocessing/dictionaries/dedup_policy.json`.
> Lệnh: `python scripts/run_preprocessing.py --step deduplication --source all [--dry-run]`.
> Dữ liệu mẫu: [`samples/01b_deduplication.json`](samples/01b_deduplication.json) (chạy lại 18/11/2026 sau các quyết định L-50, code `591391b`).
> Prompt: [`docs/prompting/preprocessing/01b_deduplication.md`](../../prompting/preprocessing/01b_deduplication.md).

## 1. Mục đích

- Mỗi vị trí tuyển dụng thật chỉ còn một dòng (tiêu chí **uniqueness**), kể cả khi cùng một tin được đăng ở nhiều sàn hoặc đăng lại với `job_id` khác.
- Bước 01 đã khử trùng theo khóa công ty + tiêu đề (C6, C7). Bước này bắt các trường hợp khóa đó bỏ sót, bằng cách so **nội dung JD**.
- Còn trùng thì tần suất kỹ năng (SD1, SD2) bị đếm hai lần, và cùng một JD có thể nằm ở cả tập train lẫn test (SD4).
- Bước này không sửa nội dung trường.

## 2. Luật

Tham số trong `dedup_policy.json`:

- `shingle_words` 5, `num_perm` 128, `seed` 42;
- `threshold` 0,85, `review_band` [0,70; 0,85);
- cổng công ty: `company_slug` bằng nhau và không rỗng.

Số tin là của lần chạy lại 18/11 (đầu vào 01 đã bỏ tin ngoài kỳ C9; D5 chọn bản giữ theo luật mới).

| Mã | Điều kiện | Hành động | Số tin |
|---|---|---|---|
| D1 | Kiểm chuỗi version CDC trong raw: mỗi lần cào lại có thật sự đổi nội dung không. Chỉ đo | flag | 1.987 bước nhảy version |
| D0 | Tầng 1: trùng (`nguồn`, `job_id`). Đây là lưới an toàn, vì 01 đã khử. Giữ theo `pick_winner`: nhiều trường nhất, rồi bản cào mới nhất, rồi `job_id` | drop | 0 |
| D2 | Tầng 2, cùng sàn: `sha1(text_fold)` trùng và cùng `company_slug`. Bản bị bỏ ghi vào `repost_records` | drop | 0 |
| D3 | Gán blocking key `company_slug_mãTỉnh_nhómTiêuĐề` cho mọi bản còn sống | flag | — |
| D4 | Tầng 2, khác sàn: như D2 | drop | 0 |
| D5 | Tầng 3: MinHash/LSH chỉ để **sinh cặp ứng viên**; mọi cặp phải qua Jaccard chính xác trên shingle 5 từ. Cặp có J ≥ 0,85 **và** cùng `company_slug` thì bị loại, cả cùng sàn lẫn khác sàn. Gộp bắc cầu bằng Union-Find | drop | 125 |
| D6 | Hợp nhất golden record cho mỗi cụm (`fuse`): bản giữ có `merged_from` | flag | 106 cụm (27 cụm khác sàn) |
| D7 | Cặp có J từ 0,70 nhưng không bị loại (khác công ty, hoặc dưới 0,85): chỉ ghi vào audit | flag | 164 |

**Chọn bản giữ trong một cụm D4/D5** (`pick_cross_winner`), chung luật với C7 của bước 01 (người dùng chốt 18/11, L-50):

1. Bản có nhiều trường có giá trị nhất (tiêu chí completeness).
2. Rồi sàn uy tín nhất theo `PLATFORM_AUTHORITY`: itviec > topdev > vietnamworks > topcv > careerviet > glints > jobsgo > vieclam24h.
3. Rồi bản cào mới nhất; bằng nhau hết thì `job_id` nhỏ nhất.

Trước 18/11, uy tín sàn xét trước độ đầy đủ. Đổi vì hai bước chọn bản giữ khác nhau thì cùng một cặp trùng có thể ra bản giữ khác nhau, và bản nhiều trường hơn có ích hơn cho SD1–SD5.

Ngày được parse theo ISO và `dd/mm/yyyy`, ngày không có múi giờ quy về +07, rồi so theo UTC. Không sort chuỗi ngày.

**Theo nguồn** (vào → ra):

| Nguồn | Vào | D5 bỏ | Ra | D6 cụm | D7 cặp |
|---|---|---|---|---|---|
| careerviet | 410 | 9 | 401 | 9 | 5 |
| glints | 162 | 8 | 154 | 5 | 4 |
| itviec | 842 | 28 | 814 | 32 | 12 |
| jobsgo | 582 | 39 | 543 | 21 | 49 |
| topcv | 1.536 | 13 | 1.523 | 24 | 63 |
| topdev | 217 | 16 | 201 | 5 | 10 |
| vieclam24h | 171 | 9 | 162 | 5 | 4 |
| vietnamworks | 701 | 3 | 698 | 5 | 17 |
| **Tổng** | **4.621** | **125** | **4.496** | 106 | 164 |

So lần chạy đầu 18/11: D5 bỏ thêm ở itviec (24 → 28) và topdev (14 → 16), bớt ở topcv (17 → 13) và vietnamworks (7 → 3), vì bản topcv, vietnamworks thường nhiều trường hơn nên nay được giữ.

**Phân bố cặp theo Jaccard:**

| Khoảng J | Số cặp | Ghi chú |
|---|---|---|
| [0,85; 1] | 214 | Chỉ cặp cùng công ty bị loại; các cặp còn lại bị cổng công ty chặn |
| [0,80; 0,90) | 87 | |
| [0,70; 0,85) | 95 | |

## 3. Quy trình xử lý

1. `load_items`: đọc `data/preprocessing/01_clean/<nguồn>.jsonl`, làm phẳng trong bộ nhớ, tính `content_hash_norm` và `blocking_key`.
2. `enrich` tính các khóa:
   - `text_fold` = gấp dấu và làm sạch của tiêu đề + yêu cầu + mô tả;
   - `fhash` = `sha1(text_fold)`;
   - `company_slug`;
   - shingle 5 từ;
   - `title_key`.
3. **D1**: `cdc_chain_audit` đọc chuỗi version trong raw. Chỉ ghi `extra.cdc`.
4. **D0**: gom theo (`nguồn`, `job_id`), giữ bằng `pick_winner`.
5. **D2**: trong từng sàn, gom theo `fhash` + `company_slug`.
6. **D3**: `build_blocks` cho các bản còn sống.
7. **D4 + D5**:
   - lấy cặp `sha1` trùng khác sàn (`exact_cross_pairs`) và cặp ứng viên MinHash/LSH (`candidate_pairs`);
   - tính Jaccard chính xác cho từng cặp;
   - đánh dấu cặp đạt (`J ≥ 0,85` và cùng công ty);
   - gộp cụm bằng Union-Find;
   - chọn bản giữ bằng `pick_cross_winner`;
   - bản nối gián tiếp (A~B, B~C nên C bị loại) ghi thêm `linked_via` và một dòng truy vết riêng.
8. **D6**: `fuse` hợp nhất mỗi cụm thành golden record:
   - lương lấy từ bản có khoảng số trước bản "Thỏa thuận" (`_pick_salary`);
   - kỹ năng là hợp của mọi bản;
   - tên công ty và mô tả lấy bản dài nhất.

   Ghi `metadata.dedup` cho bản giữ và cho bản bị loại. Dữ liệu đi tiếp sang 02 là envelope của bản giữ; golden record chỉ nằm trong `golden_master_jobs.parquet`.
9. **D7** và audit: mọi cặp đạt, cặp trong vùng xét lại và dòng truy vết gián tiếp được ghi vào `duplicates_audit.csv`.
10. Luật bảo toàn theo từng nguồn. Ghi dữ liệu và report.
11. Chạy thiếu sàn chỉ được dry-run. Khi đó file toàn dự án mang hậu tố `.partial`.

## 4. Input → Output

| | Đường dẫn | Định dạng | Số dòng 18/11 |
|---|---|---|---|
| Input | `data/preprocessing/01_clean/<nguồn>.jsonl` | jsonl envelope | 4.621 |
| Output | `data/preprocessing/01b_deduplication/<nguồn>.jsonl` | jsonl envelope, thêm `metadata.dedup` | 4.496 |
| Golden record | `data/preprocessing/01b_deduplication/golden_master_jobs.parquet` (+ `.jsonl`) | một dòng một master | 4.496 |
| Audit | `data/preprocessing/01b_deduplication/duplicates_audit.csv` | csv: `kind`, `rule`, `job_id_a`, `title_a`, `url_a`, `job_id_b`, `title_b`, `url_b`, `jaccard`, `same_company`, `title_differs`, `same_source`, `blocking_key`, `kept_job_id`, `linked_via` | cặp đạt + vùng xét lại + 5 dòng gián tiếp |
| Report | `reports/preprocessing/01b_deduplication/` | `extra`: `tier_counts`, `pairs_by_band`, `clusters`, `cross_platform_clusters`, `cdc`, `unparsed_dates`, `lineage_rows`, … | — |

**`metadata.dedup` của bản giữ:**

| Khóa | Ý nghĩa |
|---|---|
| `content_hash_norm` | Hash nội dung sau làm phẳng |
| `text_fold_sha1` | Khóa tầng 2 |
| `blocking_key` | Khóa D3 |
| `master_id` | Mã golden record (uuid5) |
| `cluster_size`, `duplicate_count` | Số bản trong cụm sau D2 |
| `merged_from` | `nguồn:job_id` của các bản bị gộp |
| `sources` | Mọi `nguồn:job_id` thuộc master, gồm cả repost |
| `repost_records` | Bản đăng lại cùng sàn (D2) |

Bản bị loại không có trong output. Vết của nó nằm trong audit: `dropped_by`, `kept_job_id`, `duplicate_of`, `kept_url`, `jaccard`.

## 5. Dữ liệu mẫu

### 5a. Tin mẫu `topcv_2325743`

Tin này không trùng tin nào, nên đi qua nguyên vẹn. `metadata.clean` giữ như bước 01, và có thêm:

```json
"dedup": {
  "content_hash_norm": "4496aeca2656…",
  "text_fold_sha1": "f909556b681b8ecec94b6ec8bab0e722fc523b46",
  "blocking_key": "eaera_HN_backend",
  "master_id": "61870720-f45c-5fe5-9bf7-dbdb3e78a4fa",
  "cluster_size": 1, "duplicate_count": 1,
  "merged_from": [], "sources": ["topcv:2325743"], "repost_records": null
}
```

### 5b. Ví dụ theo luật

| Luật | Bản bị loại / cặp | Bản giữ / kết quả |
|---|---|---|
| D5 cùng sàn | topcv `1013348` "Trưởng phòng giải pháp CNTT" | topcv `1629932` "Chuyên viên tư vấn giải pháp CNTT". Cùng công ty, JD gần như giống hệt (J ≥ 0,85) dù khác tiêu đề, nên cờ `title_differs` = true |
| D5 khác sàn | topdev `2138328` "Business Analyst" (J = 0,951) | topcv `1506721` "Business Analyst ERP (Lead Phân Tích Nghiệp Vụ)": bản topcv nhiều trường hơn nên được giữ. Trước 18/11 luật uy tín giữ bản topdev |
| D6 | glints `00b4d332…` "Kỹ thuật viên IT phần mềm – KCN Long Đức" | `master_id` `0879983d…`, `merged_from` các bản cùng cụm |
| D7 | topcv `1975529`, J = 0,856 | Không loại vì khác công ty; chỉ vào audit |
| D7 | topcv `2315776` và `2315819` "Pod Designer", J = 1,0 | Không loại: `same_company` = false. Hai tin cùng nội dung nhưng tên công ty khác nhau |

## 6. Kiểm tra và nghiệm thu

| Kiểm tra | Cách | Kết quả 18/11 |
|---|---|---|
| Luật bảo toàn | `checks.rows_conserved` | Đạt (4.621 = 4.496 + 125) |
| Truy vết đủ | Mỗi input của 01 có đúng một tham chiếu trong `source_job_ids` hoặc `repost_records` (`lineage_rows`) | 4.621 dòng truy vết = 4.621 input |
| Ngày không parse được | `extra.unparsed_dates` | 0 |
| Độ đúng cặp gần ngưỡng | 50 cặp từ `scripts/build_dedup_pairs_sample.py` (seed 42, 25 cặp [0,85; 0,90) bị loại + 25 cặp [0,80; 0,85) không bị loại); đích precision ≥ 95% | Người dùng duyệt 11/11 ("ổn rồi") nhưng chưa chấm từng cặp, nên chưa có con số |
| Test | `pytest tests/unit/test_deduplication_step.py` | Xanh (gồm `test_pick_cross_winner_độ_đầy_đủ_trước_uy_tín`) |
| Trang | `docs/presentation/preprocessing_steps/01b_deduplication.html` | Có |

## 7. Trạng thái, chỗ thiếu, việc mở

- **Trạng thái:** có code; chạy thật 18/11, chạy lại cùng ngày sau các quyết định L-50.
- **Chỗ thiếu:**
  - Cổng công ty chặn các cặp J ≥ 0,85 khác tên công ty. 214 cặp đạt ngưỡng, nhưng chỉ cặp cùng `company_slug` bị loại. Cùng công ty mà tên viết khác thì vẫn còn trùng (PRE-33).
  - Chưa có precision trên 50 cặp đã chấm.
- **Việc mở:** PRE-33, PRE-35.
