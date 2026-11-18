# Prompt 01b: Deduplication (chạy lại trên đầu ra 01 ngày 18/11)

> Đặc tả: [`docs/spec/preprocessing/01b_deduplication.md`](../../spec/preprocessing/01b_deduplication.md). Dữ liệu mẫu: `docs/spec/preprocessing/samples/01b_deduplication.json`.
> Prompt này viết lại ngày 18/11/2026 sao cho chạy lại ra **đúng kết quả lần chạy 18/11**: 4.799 → 4.672. Code khử trùng 3 tầng đã làm ở PH4 (10/11, `docs/prompting/PH4_khu_trung_3_tang_minhash.md`); lần này **không sửa luật**.

## 1. Ngữ cảnh

**Đọc trước:**

- Đặc tả bước 01b (mục 2 luật và cách chọn bản giữ, mục 3 quy trình).
- `preprocessing/deduplication/CLAUDE.md`: các bẫy đã kiểm chứng về ngày, repost D2, `duplicate_count` và `lineage_rows`, NFC trước boilerplate, audit nối gián tiếp.
- Code: `preprocessing/deduplication/{run,intra_source,inter_source,minhash,blocking,text_norm}.py`; tham số `preprocessing/dictionaries/dedup_policy.json`.

**Vì sao làm:** bước 01 vừa chạy lại trên tập raw R2 (4.799 tin). Bước 02 đọc đầu ra 01b, nên phải dựng lại 01b trước.

**Số liệu lần trước** (10/11): 4.799 → 4.672; D5 127; 108 cụm (27 khác sàn); D7 168.

## 2. Việc cần sửa

**Input:** `data/preprocessing/01_clean/<nguồn>.jsonl`.

**Output:**

- `data/preprocessing/01b_deduplication/<nguồn>.jsonl`;
- `golden_master_jobs.parquet` (+ `.jsonl`);
- `duplicates_audit.csv`;
- `reports/preprocessing/01b_deduplication/<nguồn>.json` + `_all.json`;
- trang `docs/presentation/preprocessing_steps/01b_deduplication.html`.

**Các bước:**

1. Dry-run 8 nguồn, so số với lần 10/11.
2. Chạy thật 8 nguồn.
3. Sinh trang (`scripts/visualize_preprocessing_steps.py --step 01b_deduplication`).
4. Gửi người dùng: số vào/ra theo nguồn, cụm khác sàn, cặp vùng xét lại. **Dừng chờ người dùng xem** trước khi chạy 02.

## 3. Pseudo code

```text
items = load_items(8 nguồn)                   # flatten + content_hash + blocking_key
enrich: text_fold, sha1, company_slug, shingles(5), title_key
D1: cdc_chain_audit(raw)                      # chỉ đo
D0: gom (nguồn, job_id) → pick_winner
D2: trong sàn, gom (sha1, company_slug) → repost_records
D3: build_blocks
D4 + D5: cặp = exact_cross_pairs ∪ MinHash/LSH candidates
         J = exact_jaccard(shingles)          # không dùng ước lượng MinHash
         đạt nếu J ≥ 0,85 và company_slug bằng nhau, khác rỗng
         clusters = union_find(cặp đạt)
         win = pick_cross_winner(cụm)         # uy tín sàn → đầy đủ → mới nhất → job_id
D6: fuse(cụm) → golden record, metadata.dedup
D7: cặp J ≥ 0,70 không bị loại → audit
check_conserved ; ghi
```

## 4. Ràng buộc

- Không đổi `dedup_policy.json` (ngưỡng 0,85, seed 42). Chỉ đổi khi người dùng có kết quả chấm 50 cặp.
- Không sửa nội dung trường. Không đụng raw, R2, `01_clean/`.
- Chạy thiếu sàn chỉ được dry-run, và file toàn dự án mang hậu tố `.partial`.
- Không đưa nội dung JD vào `reports/`.
- Commit chỉ report, trang và file của việc này. Không commit `data/`. Không push.

## 5. Ví dụ (thành test)

Lấy từ dữ liệu thật ngày 18/11.

| Đầu vào | Kết quả mong đợi | Test |
|---|---|---|
| topcv `1013348` và `1629932`: cùng công ty, JD gần giống, khác tiêu đề | D5 loại `1013348`, `title_differs` = true chỉ là cờ | `tests/unit/test_deduplication_step.py::test_cung_san_gan_trung_cung_cong_ty_bi_loai_va_title_differs_chi_la_co` |
| topcv `1506721` và một tin topdev cùng công ty, J ≥ 0,85 | D5 khác sàn, giữ bản topdev (uy tín hơn) | `::test_authority_theo_thứ_tự_uy_tín_đặc_tả`, `::test_pick_cross_winner_giữ_bản_cào_mới_nhất_khi_ngang_uy_tín_và_độ_đầy_đủ` |
| topcv `2315776` và `2315819` "Pod Designer", J = 1,0, khác `company_slug` | Không loại; D7 `same_company` = false | `::test_cong_cong_ty_chan_cap_j_cao_khac_cong_ty_va_chi_ghi_d7` |
| A~B, B~C | Một cụm, C có `linked_via` = B | `::test_pipeline_transitive_audit` |
| Tin mẫu `topcv_2325743` | Đi qua nguyên vẹn, `cluster_size` 1, `blocking_key` `eaera_HN_backend` | — (kiểm trên dữ liệu thật) |
| Chạy 2 lần cùng seed | Cùng danh sách giữ | `::test_chay_hai_lan_cung_seed_giu_cung_danh_sach` |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Dry-run | `python scripts/run_preprocessing.py --step deduplication --source all --dry-run` | Bảo toàn |
| Chạy thật | `python scripts/run_preprocessing.py --step deduplication --source all` | 4.799 → 4.672, D5 127 |
| Truy vết | `extra.lineage_rows` = số input | 4.799 |
| Ngày | `extra.unparsed_dates` | 0 |
| Cặp gần ngưỡng | `python scripts/build_dedup_pairs_sample.py`, người dùng chấm 50 cặp | Precision ≥ 95% (chưa chấm) |
| Test | `pytest tests/unit/test_deduplication_step.py -q` | Xanh |
| Trang | `01b_deduplication.html` ở 1100px và 390px | Không tràn ngang |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| 1 | Duyệt đặc tả | 10–11/11, 17/11 | Luật 3 tầng duyệt ở PH4 (10/11); 50 cặp người dùng xem 11/11 ("ổn rồi"), chưa chấm từng cặp. Spec 05 v3.0.0 mục 3.2 duyệt 17/11 | `7aa63a2` |
| 2 | Duyệt prompt | 10/11 | Prompt PH4. Lần chạy lại 18/11 đi tắt vì không đổi luật | — |
| 3 | Test rồi code | 10/11 | Code PH4. Không đổi code ngày 18/11 | — |
| 4 | Dry-run | 18/11 | Dry-run 8 nguồn trên đầu ra 01 mới: 4.799 → 4.672, trùng lần 10/11 | — |
| 5 | Review, chạy thật | 18/11 | Chạy thật sau khi người dùng duyệt 01 ("oke làm (a) đi rồi chạy tiếp 01b"). Trang `01b_deduplication.html` | `863415c` |
| 5 | (tiếp) | 18/11 | Chạy lại sau khi bổ sung 48 nhãn C4b và `first_scraped_at`; số không đổi | `eb06083` |
