# Prompt PH4: khử trùng lặp 3 tầng với MinHash (bước 01b, bước 4 của file thiết kế)

> **Nháp, chờ bạn duyệt.** Các điểm **[CẦN CHỐT]** (C1-C9) trong spec phải được chốt trước khi giao prompt này cho agent code. Chỗ nào ghi "[ĐỀ XUẤT]" là mặc định nếu bạn không đổi.

## 1. Ngữ cảnh

Đọc trước:
- `docs/spec/preprocessing/spec/PH4_khu_trung_3_tang_minhash.md` (mục 2 là hiện trạng đã đo; mục 3-4 là quyết định và luật).
- `Tiền xử lý dữ liệu JD ngành IT cho Data Mining.md` bước 4, mục 3.2, 4.3.
- `docs/spec/preprocessing/spec/P0_pipeline_contract.md` (mục 4 schema báo cáo, mục 7 ranh giới), `PH2_schema_va_lam_sach_ky_tu.md` (cột `text_fold`).
- `preprocessing/deduplication/CLAUDE.md` (các bẫy đã kiểm chứng: ngày, repost D2 truyền tới master, `duplicate_count` vs `lineage_rows`, NFC trước boilerplate, audit nối gián tiếp).
- Code: `preprocessing/deduplication/{run,text_norm,intra_source,inter_source,blocking,verify_delivery}.py`, `preprocessing/common/{step_report,text_clean}.py`, `preprocessing/common/__init__.py` (`STEPS`), `preprocessing/integration/run.py` (`IN_DIR`), `tests/unit/test_deduplication_step.py`, `tests/unit/test_cross_deduplicator.py`.

Hiện tại (đã đo 10/11/2026 trên `data/preprocessing/01_clean/*.jsonl`, 5.077 tin):
- 01b hiện dùng SHA-256 canonical JSON (D2 cùng sàn, D4 liên sàn) và TF-IDF char 3..5 + cosine 0.85 chỉ khác sàn (D5). Báo cáo 07/11: 5.077 → 4.897 (D2 54, D4 9, D5 117).
- `01b_deduplication` **không nằm trong `STEPS`**; `02_integration` đọc thẳng `01_clean/`. Đầu ra dedup hiện không được bước sau dùng.
- Đo bằng `datasketch` (shingle 5 từ, 128 perm, `seed=42`): tầng 1 trùng 0; tầng 2 `sha1(fold)` 84 nhóm / 103 tin; tầng 3 J ≥ 0.85: 396 cặp (294 cùng sàn, 102 khác sàn), 261 cụm, 319 tin loại được; 108/396 cặp khác slug công ty; dải 0.80-0.90 có 115 cặp.
- Chưa biết bao nhiêu trong 319 là trùng thật: chỉ bạn chấm mới trả lời.

## 2. Việc cần sửa

**Input:** `data/preprocessing/01_clean/<nguồn>.jsonl` (envelope). **Output:** `data/preprocessing/01b_deduplication/<nguồn>.jsonl` (bản giữ, `metadata.dedup` thêm `sources`), `golden_master_jobs.parquet`, `duplicates_audit.csv`, `data/preprocessing/rejected/01b_deduplication/<nguồn>.jsonl`, `reports/preprocessing/01b_deduplication/<nguồn>.json` + `_all.json`.

1. `preprocessing/dictionaries/dedup_policy.json` (mới, [ĐỀ XUẤT]): `num_perm=128`, `shingle_words=5`, `threshold=0.85`, `review_band=[0.70,0.85)`, `seed=42`, `version`. Code đọc file, không hardcode.
2. `preprocessing/deduplication/minhash.py` (mới): `fold_text(flat)` (dùng `text_clean.clean_text` + `text_norm.fold`, không viết bản fold mới); `sha1_fold(text)`; `shingles(text, k)`; `minhash_candidates(items)` (LSH sinh ứng viên); `exact_jaccard(a, b)`.
3. `inter_source.py` / `run.py`: thay `cross_source_pairs` (TF-IDF) bằng cặp ứng viên MinHash **đã tính Jaccard chính xác**; áp cổng cùng `company_slug` (C3) và quy tắc cùng sàn (C4); D2/D4 chuyển sang `sha1(fold_text)`; thêm D0 (tầng 1) và D7 (flag cặp không loại). Giữ `pick_winner`, `pick_cross_winner`, `fuse`, union-find, dòng truy vết `linked_via`.
4. Đưa `01b_deduplication` vào `STEPS` (giữa 01 và 02), `scripts/run_preprocessing.py` và `02_integration` đọc đầu ra 01b (C1). **Đổi số tin vào của 02**: không chạy 02-05 trong phase này, chỉ chạy `--dry-run` và báo.
5. Báo cáo: mục 5 của spec (`extra.dedup`, `tier_counts`, `pairs_by_band`, so sánh cũ/mới).
6. `scripts/build_dedup_pairs_sample.py` (mới): lấy mẫu có seed ghi `data/preprocessing/gold/dedup_pairs_sample.json` (git-ignore) cho công cụ `.html` chấm của PH1 (C5). Không tự chấm.

## 3. Pseudo code

```text
run(sources, dry_run):
    items = load_items(8 nguồn)                         # như hiện tại
    # D0 tầng 1
    for (src,jid) trùng: giữ pick_winner, drop D0
    for it in items: it.fold = fold_text(it.flat); it.sha = sha1(it.fold)
    # D2 / D4 tầng 2
    nhóm theo it.sha: nếu nhóm > 1:
        cùng sàn: drop D2 (giữ pick_winner)
        khác sàn: drop D4 (giữ pick_cross_winner)
    # D5 tầng 3 trên survivors
    M = {it: MinHash(num_perm, seed) trên shingles(it.fold, 5)}
    cand = LSH(threshold = review_band thấp nhất).query cho mọi it   # ứng viên
    for (a,b) in cand:
        j = exact_jaccard(shingles(a), shingles(b))                  # KHÔNG dùng ước lượng MinHash
        scores[pair(a,b)] = j
    for (a,b,j) in scores:
        if j >= 0.85 và company_slug(a) == company_slug(b) và đủ điều kiện C4:
            hits.append(a,b,j)
        elif j >= 0.70: flag D7 (audit)
    clusters = union_find(hits); win = pick_*_winner(cluster)
    mỗi bản còn lại: drop D5 {kept=win, jaccard, linked_via}, title_differs = (title_key khác)
    D6 fuse; ghi sources = ["src:jid" mọi thành viên]
    rejected = mọi bản drop với duplicate_of, drop_rule, jaccard
    report.check_conserved()                                         # in = out + dropped
```

## 4. Ràng buộc

- Không sửa raw, không sửa `01_clean/`, không động tới R2, không chạy Airflow scheduler, không commit.
- Không cài gói mới (`datasketch 2.0.0` đã có trong `.venv`; nếu `requirements.txt` thiếu thì chỉ đề xuất dòng pin, hỏi bạn).
- Không dùng model. Không cắt boilerplate, không dịch.
- Ngưỡng chỉ đổi sau khi có kết quả chấm của bạn; mặc định đúng file thiết kế.
- Không đưa nội dung JD hay `raw_line` vào `reports/` (tracked bằng git). `rejected/` và `gold/` không vào git.
- Test không dùng dữ liệu giả: dựng cặp từ tin thật trong `tests/fixtures/<nguồn>/` (hoặc chuỗi thật ghi lại từ `01_clean`, ghi `job_id` nguồn trong chú thích) rồi biến đổi tối thiểu (xóa một câu, đổi một câu). Số kỳ vọng đo từ chính module trước khi viết vào test.
- Sửa test cũ nào khẳng định hành vi TF-IDF/cosine thì ghi lý do trong summary.
- Giữ nguyên mã luật D1, D2, D4, D5, D6 (đổi nghĩa D5 thì cập nhật chữ trong báo cáo).
- Xong thì ghi `docs/issue_log.md` (`L-` kế tiếp) và cập nhật `preprocessing/deduplication/CLAUDE.md` nếu có bẫy mới.

## 5. Ví dụ (thành test)

| Đầu vào | Kết quả mong đợi |
|---|---|
| Hai envelope cùng `(source, job_id)` | D0 giữ bản `pick_winner`, bản kia vào `rejected` với `duplicate_of` |
| JD thật, cùng văn bản nhưng bản B là `unicodedata.normalize("NFD", A)` | cùng `sha1(fold)` → D2 (cùng sàn) hoặc D4 (khác sàn) |
| JD thật A (≥ 300 từ) và B = A bỏ một câu | J ≥ 0.85, cùng công ty → D5 drop, `jaccard` ghi trong audit |
| A và B = A, thay 30% câu | J < 0.85 → không loại; nếu J ≥ 0.70 thì có dòng D7 |
| Hai tin J ≥ 0.85 nhưng khác `company_slug` | không loại, D7 ghi `same_company = false` |
| Hai tin cùng sàn, cùng công ty, J ≥ 0.85, khác tỉnh/`title_key` (C4) | không loại, D7 `title_differs = true` |
| A~B, B~C (A~C dưới ngưỡng) | một cụm, C bị loại có `linked_via = B` |
| Chạy hai lần cùng `seed` | danh sách `job_id` giữ lại giống hệt |
| `rows_in` | `= rows_out + dropped` ở mọi nguồn |
| Tin ngắn (< 5 từ sau fold) | một shingle, không lỗi; không bị gộp với tin dài chỉ vì đồng bộ tập rỗng |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit -q` | xanh |
| Bảo toàn | `python -m preprocessing.deduplication.run --dry-run`, rồi chạy thật | `input = output + dropped` mọi nguồn; `rejected` khớp số dòng |
| So cũ/mới | báo cáo `extra`: số tin cũ loại, mới giữ; cũ giữ, mới loại | có số, bạn xem danh sách 20 tin đổi (seed 42) |
| Tái lập | chạy 2 lần, so hash danh sách `job_id_global` | giống hệt |
| Số liệu spec | so `tier_counts`, `pairs_by_band` với spec mục 2.2 (84 nhóm tầng 2; 396 cặp ≥ 0.85) | khác thì ghi lý do (cổng công ty, dữ liệu đổi) |
| **Precision** | bạn chấm 50 cặp gần ngưỡng bằng công cụ `.html` (C5) | ≥ 95% |
| Chuỗi | `git diff` trên `STEPS`, `02_integration/run.py` | chỉ đổi theo C1 đã duyệt |
| Git | `git status` | không có file dữ liệu/rejected/gold trong git |
| Ranh giới | `git diff --stat` | không đụng `collection/`, R2, raw |
