# Prompt M0: Chuẩn bị đầu vào Mining

> Đặc tả: [`docs/spec/mining/M0_chuan_bi.md`](../../spec/mining/M0_chuan_bi.md) (M0.1–M0.9, đã duyệt 20/11). Hợp đồng chung: spec 07 mục 2.
> **Trạng thái:** viết 20/11, chờ duyệt prompt.

## 1. Ngữ cảnh

**Đọc trước:** đặc tả M0; `docs/target/06_yeu_cau_du_lieu.md` mục 2 (ba góc nhìn kỹ năng); `mining/config.py`, `mining/data_io.py`, `mining/run_mining_pipeline.py`, `mining/sanity.py`, `mining/synthetic.py`; `tests/unit/test_mining_data_io.py`, `test_mining_sanity.py`, `test_mining_pipeline.py`.

**Vì sao làm** (dry-run 20/11, code cũ):

- Code đọc `all.parquet` (lùi từ `data/curated/` không còn), không đọc Silver.
- Chỉ nạp khối `skill__`; e5 đọc khóa `all` (có phúc lợi).
- `STEPS` thiếu `bi`, `recommend`; TF-IDF còn code chết.
- S-04 ánh xạ cấp lệch một bậc nên báo fail sai; S-02, S-03 có ngưỡng trái quyết định 6.

M0 là nền chung: làm xong M0 thì M1–M6 chỉ đọc `MiningData`.

## 2. Việc cần sửa

**Input:**

- `data/preprocessing/04_normalization/silver.parquet` (3.916 × 26);
- `data/processing/10_features/features.parquet` (3.916 × 994), `encoding_dictionary.json`;
- `data/processing/12_e5/job_emb.npz` (khóa `job`).

**Output:**

- `MiningData` có `meta`, `skills` (K-tool), `concepts`, `soft`, `e5`. `meta` có thêm `n_tools`, `n_concepts`, `n_soft`, `salary_target_m`, `company_id`, `source_platform`, `seniority_inferred`, `posted_month`, `work_mode`, `employment_type`, `language`, `benefits`, `is_negotiable`, `salary_outlier`.
- `mining_metrics.json` khối `data`: `table_path`, `n_jobs`, `n_cols` theo khối, độ thưa, cột đã ánh xạ, sha256 của 4 đầu vào.
- `sanity_checks` có S-02 `info`, S-03 ngưỡng 0,60, S-04 đúng thang (Lead ghi riêng).

**File sửa:**

- `mining/config.py`: `DEFAULT_TABLE`, `COLUMN_ALIASES`, `SKILL_PREFIXES`, `CONCEPT_PREFIX`, `SOFT_PREFIX`, `OTHER_SKILL_SUFFIX`, `SanityParams`; bỏ `tfidf_*`.
- `mining/data_io.py`.
- `mining/run_mining_pipeline.py`: `STEPS`, `--table` (giữ `--golden` làm bí danh), `_sha256`.
- `mining/clustering.py`: gỡ `build_tfidf`.
- `mining/sanity.py`.
- `mining/synthetic.py`: sinh thêm cột Silver, `concept__`, `soft__`, `n_tools`, `salary_target_m`, `company_id`, e5 khóa `job`.
- **Mới** `mining/CLAUDE.md`.

## 3. Pseudo code

```
load_mining_data(table=DEFAULT_TABLE, features, enc_dict, e5):
    silver = read(table); thiếu file → FileNotFoundError (không lùi về file khác)
    meta, resolved = build_meta(silver)              # COLUMN_ALIASES: tên Silver đứng đầu
    feat = read(features); key job_id_global; trùng/thiếu tin → MiningContractError
    for khối, tiền tố in (skills, "skill__"), (concepts, "concept__"), (soft, "soft__"):
        cols = [c bắt đầu bằng tiền tố, c != tiền tố + "other_skill"]
        mat = feat[cols] căn theo meta.job_id (reindex); chỉ 0/1, không NaN
    meta[n_tools, n_concepts, n_soft, salary_target_m] = feat[...] căn theo job_id
    e5 = npz["job"] căn theo ids; thiếu khóa "job" hoặc thiếu tin → MiningContractError
    metrics.data.sha256 = {table, features, enc_dict, e5}

run_sanity_checks(meta, skills, shap):
    S-01 như cũ
    S-02: tính conf Flutter⇒Dart, status = "info" (không vào n_pass/n_fail/all_passed)
    S-03: React⇒JS|TS, ngưỡng SanityParams.s03_min_conf = 0.60
    S-04: tập lương = salary_target_m notna & !salary_outlier & !is_negotiable
          med theo seniority_ord ∈ {0,1,2,3} với nhãn SENIORITY_ORDER_LABELS[0..3]
          pass ⇔ đơn điệu tăng; values thêm lead = {median, n, negotiable_share} (ghi riêng, không xét)
    S-05, S-06 như cũ nhưng lương = salary_target_m
STEPS = ("bi","fp","cluster","anomaly","salary","recommend")   # bi/recommend: stub NotImplemented tới M1/M6
```

## 4. Ràng buộc

- Không tính lại `n_tools` hay `salary_target_m`: lấy từ bước 10.
- Nối theo id, không theo thứ tự dòng (Silver và features khác thứ tự).
- Không còn đường lùi về `data/curated/` hay `all.parquet`. `scripts/load_mart_from_parquet.py` không thuộc M0 (PRE-39).
- Bước `bi`/`recommend` chưa có code thì `--only bi` báo lỗi rõ "chưa làm (M1)", không chạy im lặng.
- Giữ được các test cũ còn đúng nghĩa (vị trí tỉnh, ánh xạ cấp). Test chỉ đúng với schema cũ (`_old_schema_golden`, `_duy_schema_golden`) thì đổi sang schema Silver, ghi trong Log.

## 5. Ví dụ (thành test)

| Đầu vào (dựng tay) | Kết quả mong đợi |
|---|---|
| Silver 3 tin, features cùng 3 id nhưng **đảo thứ tự** | `skills`, `n_tools` khớp từng tin theo id |
| features có `skill__python`, `skill__other_skill`, `concept__oop`, `soft__english` | `skills` = [python], `concepts` = [oop], `soft` = [english]; không cột `other_skill` |
| features thiếu 1 id của Silver | `MiningContractError` |
| npz chỉ có khóa `all` | `MiningContractError` nhắc khóa `job` |
| Đường dẫn bảng không tồn tại | `FileNotFoundError`, không đọc file khác |
| Lương theo cấp 0..4 = 10, 15, 22, 37, 30 (mỗi cấp ≥ 5 tin) | S-04 pass; `lead` ghi riêng 30 |
| Lương theo cấp 0..3 = 10, 22, 15, 37 | S-04 fail |
| Flutter 10 tin, Dart 4 trong đó | S-02 `info`, `all_passed` không bị ảnh hưởng |
| React 10 tin, JS/TS 6 trong đó | S-03 pass (0,60) |
| `--only bi` trước khi có M1 | exit ≠ 0, thông báo "chưa làm" |
| `--synthetic` | chạy đủ fp, cluster, anomaly, salary; synthetic có `concept__`, `soft__`, khóa `job` |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit/test_mining_*.py -q` | Xanh |
| Toàn bộ unit | `make test-fast` | Không thêm lỗi ngoài 2 lỗi có sẵn (tfidf, vulture) |
| Dry-run thật | `python -m mining.run_mining_pipeline --only fp,cluster,anomaly,salary --dry-run` | `table_path` = Silver; 3.916 tin; 290 / 561 / 62 cột; e5 `job` (3.916, 768); S-04 pass |
| Không ghi file | `git status`; `mining/artifacts/` không đổi giờ sửa | Sạch |
| Tài liệu | `mining/CLAUDE.md` có các bẫy; đặc tả M0 mục 5–6 có số | Có |

## Log

| # | Bước quy trình | Ngày | Việc đã làm, số liệu, quyết định | Commit |
|---|---|---|---|---|
| 1 | Duyệt đặc tả | 20/11 | Người dùng "approved" cả bộ `docs/spec/mining/` (M0.1–M0.9) | 1036a11 |
| 2 | Duyệt prompt | 20/11 | Người dùng "continue" sau khi nhận bộ prompt M0–M6 (coi là duyệt), không sửa | e230f28 |
| 3 | Test rồi code | 20/11 | Test viết lại theo schema Silver: `test_mining_data_io` (15 test: ba khối, nối theo id, khóa `job`, sha256, không lùi bảng), `test_mining_sanity` (S-02 info, S-03 0,60, S-04 thang 0–3 + Lead riêng, bỏ ngoại lai/thỏa thuận), `test_mining_pipeline` (`--only bi/recommend` trả 2, `--table`/`--golden`, đọc file Silver). Code: `config.py`, `data_io.py`, `sanity.py`, `run_mining_pipeline.py`, `clustering.py` (gỡ TF-IDF), `synthetic.py` (schema Silver, ba khối), `salary_model.py` (cờ `salary_outlier`), `mining/CLAUDE.md`. 71 test mining xanh. **Đi khác prompt:** synthetic chưa có e5 (trước đây cũng không có; test đọc file tự tạo npz khóa `job`); giữ `skills_from_lists` làm đường thử khi không có features | (commit này) |
| 4 | Dry-run | 20/11 | Trước khi sửa: đọc `all.parquet`, 290 cột, e5 `all`, sanity 2 pass / 3 fail / 1 bỏ qua. Sau khi sửa: Silver, 290 / 561 / 62 cột, e5 `job`, `n_tools` khớp bước 10; S-01 pass, S-02 info 0,394, S-03 pass 0,671, S-04 pass (10 < 15,5 < 22,5 < 37,5; Lead 30), **S-06 fail (HCM/khác 1,194)** vì nay bỏ 86 tin `salary_outlier` | |
| 5 | Review, chạy thật | 20/11 | Người dùng chốt S-06: "Keep 1.2, record fail". M0 không có artifact riêng; `make test-fast` (tests/unit): 647 pass, 2 lỗi có sẵn (tfidf, vulture). Ghi L-55 | d79288b |
