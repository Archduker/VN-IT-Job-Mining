# issues_merge: việc phát sinh sau khi merge 7 nhánh vào `sprint/pipeline-delivery`

Cập nhật 09/11/2026. Nguồn: `docs/tasks/review_truoc_merge_2026-11-09.md` (mục 7, đã đánh số lại) và kết quả merge Phase 1.

Quy trình mỗi issue: **merge → issues_merge (file này) → đặc tả giải pháp (`docs/spec/fixes/<mã>.md`) → prompt (`docs/prompting/issues/` hoặc `docs/prompting/merge/`) → code → review (người dùng + một agent độc lập)**. Cột "Bước" ghi bước đã xong.

Trạng thái: `mở` / `chờ quyết định` / `đã sửa` / `bỏ`. Chưa issue nào qua review.

## 1. Kết quả merge (Phase 1)

| Nhánh | Người | Cách merge | Xung đột | Ghi chú |
|---|---|---|---|---|
| `feature/monitoring-observatory` | Sơn | `--no-ff` | không | |
| `feature/p1-clean-dedup` | Tài | `--no-ff` | 1 (docstring đường dẫn) | giữ bản mới |
| `feature/p2-integration-flatten` | Hoàng | `--no-ff` | không | test fail đã sửa (305d017) |
| `feature/p5-encoding-matrices` | Phát (đã chứa Duy `9b33a05`) | `--no-ff` | 17 (docs, AGENTS, provinces, r2_export, encoding/run) | giữ bản sprint, gộp `GOLD_KEYS` |
| `feature/p3-p4-transform-normalize` | Duy | không cần | - | đã nằm trong Phát |
| `feature/mining-algorithms` | Phúc | `--no-ff` | không | |
| `feature/collection-hotfixes` | Khoa | patch qua `merge/khoa-collection-hotfixes` | không chung lịch sử | 3 crawler + 4 test contract |

Test sau merge (bỏ qua `tests/test_golden_field_preservation.py`): 440 pass, 6 skip, 2 fail, 5 error. Sau commit 305d017 test Hoàng đã pass; còn lại là MERGE-3, MERGE-4, PRE-27.

## 2. Quyết định đã có

| Mã | Quyết định | Người quyết |
|---|---|---|
| D1 | Chấp nhận `it_policy.json` (Tài, 5.409 tin non_IT bị loại) nguyên trạng. Sau này dùng model phân loại lại các tin bị loại (PRE-15) | người dùng |
| D2 | Tên tỉnh: "TP. Hồ Chí Minh". **Cấp bậc: 5 cấp của Duy (chốt 09/11, tài liệu đã sửa, code còn lệch: PRE-22)**. 12 nhóm của Duy, không có UI/UX (chuyển vào Frontend), giữ Embedded | người dùng |
| D3 | Cohort của Phát: chấp nhận tạm (A), xem lại sau phân tích kỹ năng (PRE-28) | người dùng |
| D4 | Đường `features.parquet`: chưa chốt, gắn GEN-4/GEN-9 | - |
| D5 | Khoa: áp patch lên nhánh mới (đã làm) | người dùng |
| D6 | Thêm `mlxtend`, `shap`, `hdbscan` vào `requirements.txt` (đã làm, 78bebfc) | người dùng |
| D7 | Rủi ro chấp nhận: số liệu chưa kiểm chứng, git phình `reports/05_encoding`, cohort. Có kế hoạch dọn sau | người dùng |
| D8 | Chưa ai ghi lên R2; mọi ghi/xóa R2 vẫn dry-run + chờ đồng ý | người dùng |
| D9 | I0 (PRE-18): bỏ dòng JSON hỏng + ghi "đã bỏ" | người dùng 09/11 |
| D10 | Tên cột cấp bậc: giữ cả `seniority_level` và `seniority_ord`, cùng thang 0–4 | người dùng 09/11 |
| D11 | TopDev: bỏ lọc IT ở thu thập (SCRAPE-18); nghỉ giữa request nâng lên 2,0–4,5 s (SCRAPE-13) | người dùng 09/11 |
| D12 | Cho phép OpenJev làm tầng phụ phân loại IT (đã sửa `preprocessing/CLAUDE.md`) | người dùng 09/11 |
| D13 | Xóa nhánh `hotfix` (đã làm); push khi đặc tả xong; dời `docs/preprocessing/encoding` vào `docs/spec/preprocessing/encoding` (đã làm); PRE-11 và R2 đem ra nhóm | người dùng 09/11 |

## 3. Danh sách issue

Cột "Chờ" = cần quyết định nào trước khi sửa. "Mức": C chặn chạy/CI, B lệch spec hoặc sai dữ liệu, A dọn dẹp/ghi chú.

### 3.1 Phát sinh từ merge (mã MERGE)

| Mã | Nội dung | Người | Mức | Chờ | Trạng thái |
|---|---|---|---|---|---|
| MERGE-1 | Nhiều thông báo merge thiếu dòng đồng tác giả (chỉ lịch sử, không sửa) | - | A | - | bỏ (ghi nhận) |
| MERGE-2 | Đường dẫn docs cũ (`docs/preprocessing/...`) còn trong file mới của Tài, Hoàng, Phát | Tài, Hoàng, Phát | A | - | mở |
| MERGE-3 | 3 file test mining lỗi collect và 2 lỗi `salary_model` vì venv chưa cài `mlxtend`/`shap`/`hdbscan` | Phúc | C | - | đã sửa 09/11: cài bằng `uv pip install --python .venv/bin/python`, cả bộ test 465 pass |
| MERGE-4 | `test_outlier_ratio_follows_quantile` fail (thiếu `hdbscan`) | Phúc | C | - | đã sửa 09/11 (cùng MERGE-3) |
| MERGE-5 | Hai file báo cáo của Hoàng đặt sai chỗ (gốc repo, `preprocessing/integration/`) | Hoàng | A | - | đã sửa (305d017: dời vào `docs/reports/03_hoang_bao_cao_integration.md`) |
| MERGE-6 | `json_flattener.py` có BOM đầu file | Hoàng | A | - | đã sửa (305d017) |
| MERGE-7 | Test `test_integration_output_contract_and_conservation` fail: test không patch `OUT_DIR`, và kỳ vọng I0 "loại dòng hỏng" trong khi code giữ dòng hỏng thành bản ghi (zero-drop) | Hoàng | C | PRE-18 | đã sửa phần test (305d017); phần thiết kế I0 còn ở PRE-18 |
| MERGE-8 | Nhánh Khoa: 13 file chỉ đổi quyền thực thi và việc xóa `tests/data/test_integration_step.py` không đưa vào sprint | Khoa | A | - | bỏ (có chủ ý, ghi nhận) |
| MERGE-9 | `sync_cloud_lakehouse.py --download --source X` chỉ tải `url_ledger/X`, không tải `raw/X` (prefix đặt cứng theo `url_ledger/`, `scripts/sync_cloud_lakehouse.py` ~dòng 164). Mô tả `CLAUDE.md` và `--help` ngụ ý tải cả nguồn | - | B | - | mở |
| MERGE-10 | Sơn đẩy thêm `ef05bb8` (10/11: EDA và Collection đọc R2). Đã merge vào sprint (`2b6e35d`), không xung đột. Nhưng 4 test integration của chính nhánh Sơn fail (cũng fail khi chạy riêng trên nhánh của Sơn): `test_collection_without_data_has_no_invented_numbers` (KeyError `has_data`), `test_collection_counts_raw_and_merges_airflow_runs` (KeyError `days`), `test_eda_charts_from_staging_parquet` (3 so với 2), `test_monitor_eda_r2::test_empty_remote_has_no_local_fallback` (mong `NO_DATA`, code trả `NO_STAGING_DATA`). Test cũ chưa theo code mới | Sơn | C | hỏi Sơn sửa test hay code | mở |

### 3.2 Chuyển từ review (mã đề xuất trong KNOWN_ISSUED)

| Mã | Nội dung ngắn | Người | Mức | Chờ | Trạng thái |
|---|---|---|---|---|---|
| SCRAPE-18 | TopDev lọc IT bằng `it_filter` import ngược từ `preprocessing`; API vẫn trả 14.572 tin | Khoa | B | - | mở |
| GEN-5 | Nhánh Khoa không chung lịch sử | Khoa | A | - | đã xử lý bằng patch (D5), giữ ghi nhận |
| PRE-15 | `it_policy.json` loại non_IT bằng bằng chứng tổng hợp; kế hoạch dùng model phân loại lại | Tài | B | D1 | chờ quyết định |
| PRE-16 | Integration chưa đọc đầu ra Dedup `01b_deduplication`; 5.177 lệch 4.897 | Tài | B | - | mở |
| PRE-17 | Snapshot `reports/preprocessing/01_clean`, `01b_deduplication` là kết quả `f693b30`, không phải code đã sửa | Tài | B | - | mở |
| GEN-6 | Test ledger `test_latest_status_change_wins_between_workers` fail trên Windows (liên quan SCRAPE-17) | Tài | B | - | mở |
| PRE-18 | I0 đổi từ drop sang modify: dòng hỏng thành bản ghi giả, trái P2 §8; `run()` đổi `dry_run` mặc định | Hoàng | B | thiết kế I0 (người dùng chưa hiểu, cần giải thích lại) | chờ quyết định |
| PRE-19 | `source_job_id` dùng `abs(hash(...))`, không ổn định giữa các lần chạy | Hoàng | C | - | mở |
| PRE-20 | Hai runner trùng (`run.py`, `run_integration.py`); thiếu test I2-I5; 5.177 vs 8.378 chưa giải thích | Hoàng | B | - | mở |
| GEN-7 | Tải R2 tự dựng boto3, prefix cũ, bucket gán cứng trong `preprocessing/integration` | Hoàng | B | GEN-4 | chờ quyết định |
| PRE-21 | Pipeline đặc trưng của Duy ghi trùng `04_normalization/all.parquet`; chưa nối vào `run.py` | Duy | B | - | mở |
| PRE-22 | Lệch spec Duy: đã chốt 5 cấp, tài liệu đã sửa; còn sửa code về thang 5 cấp; Embedded vs UI/UX chưa chốt | Duy | B | Embedded/UI-UX | mở (phần tài liệu xong) |
| PRE-23 | Lỗi parse tái hiện được: "tối thiểu 10 triệu", "2 tỷ", "Không yêu cầu", "Điện Biên Phủ", Python/PHP Developer, UI/UX | Duy | B | - | mở |
| PRE-24 | Test P3/P4 nằm ngoài `testpaths`, `make test` không chạy; chạy chung lỗi `tests/conftest.py:42` | Duy | C | - | mở |
| PRE-25 | `ledger.csv` bị `.gitignore` nhưng `cohort.py`, `finalize_cohort.py` đọc nó | Phát | C | - | mở |
| PRE-26 | 95 file lớn/pickle/npz/notebook HTML trong `reports/preprocessing/05_encoding` | Phát | A | D7 (dọn sau) | mở |
| PRE-27 | `tests/test_golden_field_preservation.py` import module không tồn tại; 12 lỗi ruff UP038 | Phát | C | - | mở |
| PRE-28 | Cohort P5 5.104/5.177, 5.092 chưa duyệt, 17,1% không có kỹ năng, sparsity 98,15% | Phát | B | D3 | chờ quyết định |
| MINE-1 | Mining chưa chạy trên dữ liệu thật; số liệu báo cáo là dữ liệu giả (`mining/synthetic.py`) | Phúc | B | - | mở |
| MINE-2 | Thiếu thư viện trong requirements | Phúc | C | - | đã sửa (78bebfc) và đã cài vào venv |
| MINE-3 | `test_outlier_ratio_follows_quantile` phụ thuộc `hdbscan` | Phúc | C | - | đã sửa 09/11 (cùng MERGE-3) |
| MINE-4 | Khoảng k chưa thống nhất (task 6-12, checklist 4-14, spec 07 3-15); code dùng 4-14 | Phúc | B | - | chờ quyết định |
| MINE-5 | `load_mart_from_parquet.py` biến cột list thành chuỗi; chưa có bảng `skill_salary_shap_values` | Phúc | B | - | mở |
| MINE-6 | SHAP không phải nhân quả; `seniority_level` 0-4 gộp Thực tập và Mới tốt nghiệp (ghi chú báo cáo đồ án) | Phúc | A | PRE-22 | mở |
| VIZ-6 | `/insights` chưa kiểm với Mart thật | Sơn | B | - | mở |
| VIZ-7 | Chưa chạy `./start_monitoring.sh --check` và kiểm 390 px; bundle JS 778 kB | Sơn | A | - | mở |
| GEN-8 | Mẫu báo cáo nghiệm thu chưa điền ở Duy, Phúc, Sơn | Duy, Phúc, Sơn | A | - | mở |
| GEN-9 | Spec 10 ghi `gold/features.parquet`; encoding/mining dùng đường khác. Gộp vào GEN-4 | Phát, Phúc | B | D4, GEN-4 | chờ quyết định |

### 3.3 Mục cũ cần cập nhật (đã có trong KNOWN_ISSUED)

SCRAPE-11, SCRAPE-13, SCRAPE-14, SCRAPE-16, VIZ-3, VIZ-5 (xóa vì Sơn đã làm): xem `KNOWN_ISSUED.md`. GEN-4 (layout R2) giữ nguyên "chưa chốt".

## 4. Nhánh ngoài bảng task: bỏ

Không merge, không xóa (quyết định người dùng 09/11/2026: không còn dùng).

| Nhánh | Trạng thái |
|---|---|
| `feature/crawls_all` | bỏ |
| `feature/deduplication-linkage` | bỏ |
| `feature/itviec-crawler` | bỏ |
| `feature/missing-values` | bỏ |
| `feature/outliers-quality` | bỏ |
| `feature/vietnamworks-raw-batch` | bỏ |
| `pre-processing` | bỏ |
| `preprocessing/transform` | bỏ |
| `hotfix` (local, `83f8432`) | đã xóa 09/11 (commit đã nằm trong sprint) |

Đã nằm trong sprint từ trước: `crawls/*`, `feature/topdev-son`, `fix/known-issues-p1`.

## 5. Tiến độ theo quy trình

Chưa có issue nào qua bước 3 (đặc tả), 4 (prompt), 5 (code) trừ các mục "đã sửa" ở trên; chưa mục nào qua review.
