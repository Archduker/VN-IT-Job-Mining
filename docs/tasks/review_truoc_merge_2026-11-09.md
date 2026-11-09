# Review 7 nhánh thành viên trước khi merge vào `sprint/pipeline-delivery`

Ngày review: 09/11/2026. Nhánh đích: `sprint/pipeline-delivery` (HEAD `bfaa076`).
Cách làm: mỗi người một reviewer độc lập, chỉ đọc. Test chạy trong worktree riêng (Python 3.12.14, mạng chặn, đã gỡ sau khi xong), thử merge bằng `git merge-tree` (không ghi). Không merge, không push, không động R2 hay `.env`. Số ahead/behind được đo lại bằng `git rev-list` khi tổng hợp.

> Giới hạn chung: không có thư mục `data/` nên **không ai chạy lại được pipeline trên dữ liệu thật**. Mọi số liệu nghiệm thu trong nhánh (5.177, 4.897, 5.104×292, R²…) là lời khai của tác giả, chưa được kiểm chứng. Bản đầy đủ từng người nằm ở Phụ lục.

## 1. Kết luận nhanh

| Người | Nhánh | Ahead/Behind | Test (worktree) | Merge thử vào sprint | Kết luận |
|---|---|---|---|---|---|
| Khoa | `feature/collection-hotfixes` | 2 / 139 (**không chung lịch sử**) | 160 pass, 1 skip | Không thể merge thường; `--merge-base=0cfa1b0` sạch nhưng xóa file người khác | **Không merge nguyên nhánh.** Áp patch 7 file lên nhánh mới từ sprint |
| Tài | `feature/p1-clean-dedup` | 3 / 0 | unit 180 pass, 1 skip; Clean+Dedup 90 pass | Sạch | **Merge sau khi** điền nghiệm thu (precision chưa đo) và lead quyết `it_policy.json` |
| Hoàng | `feature/p2-integration-flatten` | 3 / 2 | **1 fail** (hồi quy do nhánh), 118 pass, 5 skip | Sạch | **Merge sau khi sửa** hồi quy và các thay đổi hành vi trái spec |
| Duy | `feature/p3-p4-transform-normalize` | 1 / 2 | 67 pass (test của Duy), unit 110 pass | Sạch | **Merge sau khi sửa** (ghi trùng đường ra, chưa nối vào 5 bước, lỗi parser) |
| Phát | `feature/p5-encoding-matrices` | 4 / 2 | encoding 72 pass; unit 175 pass; 1 file test lỗi collect | Xung đột ở `docs/tasks/05_*.md` | **Merge sau khi sửa** (git phình 95 file, `ledger.csv` bị ignore, ruff) |
| Phúc | `feature/mining-algorithms` | 1 / 0 | 43 pass, 1 fail, 2 error (3 file không chạy do thiếu `mlxtend`/`shap`/`hdbscan`) | Sạch | **Merge sau khi sửa** (thiếu thư viện; số liệu là dữ liệu giả) |
| Sơn | `feature/monitoring-observatory` | 8 / 0 | 229 pass, 6 skip, 0 fail; `npm run build` ok | Sạch | **Merge được** |

Thuận (Lead): nhánh chính là sprint, không review riêng.

## 2. Nhánh `hotfix`

- **`hotfix` local (commit `83f8432`)**: là tổ tiên của sprint (`git merge-base --is-ancestor hotfix HEAD` đúng), không có commit riêng. Không có gì để merge; chỉ cần quyết định xóa hoặc giữ tên nhánh (chưa thao tác).
- **`feature/collection-hotfixes` (Khoa)** là nhánh hotfix thật:
  - Không chung lịch sử với sprint. Commit gốc `c565177` (08/11) là snapshot 381 file không có parent. Tác giả chép cây thư mục rồi `git init`.
  - Thay đổi thật của Khoa so với `0cfa1b0`: 22 file; trong đó 3 crawler (topcv, topdev, vietnamworks) + 4 file `tests/contract/`.
  - Tác dụng phụ ngoài ý muốn: xóa `tests/data/test_integration_step.py` (của người khác), 14 file mất bit thực thi (gồm `run.py`, `start_monitoring.sh`), báo cáo nghiệm thu đặt ở gốc repo.
  - Tiêu chí: **đạt** C14 `DiscoveryError` cho TopDev (có test) và VietnamWorks (chưa có test), lọc IT ở Discovery (SCRAPE-15, nhưng API vẫn trả hết tin, `collection` import ngược từ `preprocessing`); **một phần** SCRAPE-16 (selector TopCV 4 tầng, test bằng HTML tự soạn, chưa có script đưa 297 tin về `PENDING`); **chưa đạt** SCRAPE-14 (chỉ test cấu trúc, không có fixture cho 6 nguồn), SCRAPE-13 (thời gian nghỉ vẫn lệch), SCRAPE-11 (2/7 nguồn); SCRAPE-5 không có thay đổi.
  - Cách đưa vào sprint đề xuất (chưa làm): tạo nhánh mới từ sprint rồi áp riêng 7 file của Khoa (hoặc nhờ Khoa tạo lại nhánh). **Không** dùng `--allow-unrelated-histories` (20 xung đột add/add vô nghĩa).

## 3. Thứ tự merge đề xuất và xung đột chéo

Đã thử merge từng cặp nhánh bằng `git merge-tree` (6 nhánh trừ Khoa):

- **Sạch với nhau:** mọi cặp trừ các cặp có Phát.
- **Xung đột chỉ ở file hướng dẫn `docs/tasks/*.md`:** nhánh Phát mang bản cũ của các file này (add/add) nên xung đột với Tài (`02_*`), Phúc (`06_*`), Sơn (`07_*`). Cách xử lý: giữ bản của sprint hoặc của chủ file. Không có xung đột code.
- Nhánh Phát đã **chứa sẵn commit của Duy** (`9b33a05`), nên merge Phát thì phần của Duy vào luôn; merge Duy sau đó là no-op.

Thứ tự đề xuất (nhỏ rủi ro trước):
1. Sơn (merge được ngay; lưu ý nó xóa VIZ-5 khỏi `KNOWN_ISSUED.md`).
2. Tài, sau khi điền mẫu nghiệm thu §4 ("precision chưa đo") và lead quyết `it_policy.json`.
3. Hoàng, sau khi sửa hồi quy test và bỏ thay đổi trái spec (I0, `dry_run`, id bằng `hash()`).
4. Duy (cùng gói với Phát nếu cần), sau khi chốt các điểm lệch spec và sửa lỗi parser.
5. Phát, sau khi dọn `reports/preprocessing/05_encoding` (95 file) và xử lý `ledger.csv`.
6. Phúc, sau khi bổ sung thư viện và ghi rõ số liệu là dữ liệu giả.
7. Khoa: nhánh mới từ sprint + patch 7 file.

Lưu ý: nhóm Hoàng/Duy/Phát cùng chạm chuỗi tiền xử lý (`04_normalization/all.parquet`, `r2_export.py`); nên merge tuần tự và chạy lại `make test` sau mỗi nhánh, không merge gộp.

## 4. Việc cần lead quyết (trước khi merge)

1. `it_policy.json` của Tài: loại 5.409 tin bằng bằng chứng tổng hợp, chưa có nhãn từng tin. Chấp nhận rủi ro bằng văn bản hay đo bằng nhãn?
2. Lệch spec của Duy: 5 hay 6 cấp bậc; Embedded hay UI/UX; "Hồ Chí Minh" hay "TP. Hồ Chí Minh".
3. Cohort của Phát: 5.104/5.177 job, 5.092 job chưa duyệt, sparsity 98,15% (ngoài khoảng 95-98% của task).
4. Đường đầu vào của mining (Phúc) và đường ra của encoding (Phát) so với spec 10 (`gold/...` trên R2): gắn với **GEN-4** (layout R2 chưa chốt).
5. Nhánh của Khoa: nhờ tạo lại hay áp patch.
6. Cho Phúc thêm `mlxtend`, `shap`, `hdbscan` vào `requirements.txt` (đổi phụ thuộc chung của cả nhóm).

## 5. Rủi ro tổng hợp

- Số liệu chưa kiểm chứng ở mọi nhánh (không có `data/`).
- Báo cáo nghiệm thu không khớp thực tế: Hoàng nêu file không có trong nhánh (`all.parquet`, `_all.json`); Phát ghi "Ruff pass" nhưng có 12 lỗi UP038; snapshot báo cáo của Tài là kết quả cũ (`f693b30`). Duy và Phúc không có hoặc không điền báo cáo nghiệm thu (Phúc: số liệu là dữ liệu giả).
- Hoàng và Phát đụng R2 ngoài `get_r2_client()` hoặc thêm khóa mới vào `GOLD_KEYS` (liên quan GEN-4). Chưa ai ghi lên R2.
- Git phình: 95 file trong `reports/preprocessing/05_encoding` (pickle ~2,3 MB, npz, notebook HTML, `profiling.json` 19k dòng), trái quy tắc về `reports/` trong `CLAUDE.md`.
- Nhánh Tài ghi đè 17 file JSON snapshot trong `reports/preprocessing/`.

## 6. Nhánh ngoài bảng task (chỉ ghi nhận, chưa review)

Đã nằm trong sprint (và main): `crawls/all`, `crawls/careerviet`, `crawls/glints-jobsgo`, `crawls/topcv`, `crawls/vieclam24h`, `feature/topdev-son`, `fix/known-issues-p1`.
Chưa merge và không có trong bảng: `feature/crawls_all`, `feature/deduplication-linkage`, `feature/itviec-crawler`, `feature/missing-values`, `feature/outliers-quality`, `feature/vietnamworks-raw-batch`, `pre-processing`, `preprocessing/transform`. Cần hỏi chúng thuộc ai và còn dùng không.

## 7. Đề xuất cập nhật `KNOWN_ISSUED.md` (chưa sửa file đó)

Các reviewer mỗi người tự đặt mã nên bị trùng nhau. Dưới đây là bảng đã **đánh số lại** để không trùng với mã đang có (SCRAPE-1…16, VIZ-3/5, PRE-11, GEN-1…4) và với các mã mà nhánh Tài tự thêm (PRE-12, PRE-13, PRE-14, SCRAPE-17). Mã chỉ là đề xuất, đổi được.

**Cập nhật mục có sẵn**
- SCRAPE-11: TopCV, TopDev, VietnamWorks đã có `DiscoveryError` (nhánh Khoa; VietnamWorks chưa có test). Còn CareerViet, Vieclam24h, ITviec, Glints, JobsGO.
- SCRAPE-13: `standards.check_random_pause` đã nhận `DelayConfig` nhưng chỉ kiểm tên hàm; TopDev, VietnamWorks, JobsGO vẫn dưới 2,0–4,5 s.
- SCRAPE-14: nhánh Khoa chỉ thêm test cấu trúc cho 8 nguồn, chưa có fixture/parser test cho 6 nguồn.
- SCRAPE-16: có fallback 4 tầng trong nhánh Khoa nhưng chưa kiểm trên HTML thật, chưa có script backfill.
- VIZ-3: Market Insights đã đọc PostgreSQL Mart; các trang báo cáo cũ vẫn dùng `reports/` ngày 25/10. VIZ-5: xóa (Sơn đã làm).

**Mục mới**

| Mã đề xuất | Nội dung | Nguồn |
|---|---|---|
| SCRAPE-18 | TopDev lọc IT bằng `it_filter` import ngược từ `preprocessing`; API vẫn trả 14.572 tin | Khoa |
| GEN-5 | `feature/collection-hotfixes` không chung lịch sử; mất bit thực thi 14 file; thiếu `tests/data/test_integration_step.py` | Khoa |
| PRE-15 | `it_policy.json` loại non_IT bằng bằng chứng tổng hợp, chưa kiểm từng tin | Tài |
| PRE-16 | Integration chưa đọc đầu ra Dedup (`01b_deduplication`); báo cáo Integration 5.177 lệch 4.897 | Tài |
| PRE-17 | Snapshot `reports/preprocessing/01_clean`, `01b_deduplication` là kết quả `f693b30`, không phải code đã sửa | Tài |
| GEN-6 | Test ledger `test_latest_status_change_wins_between_workers` fail trên Windows, pass trên Linux (`save_catalog` dùng `mem_ts >= disk_ts`) | Tài |
| PRE-18 | I0 đổi từ "drop" sang "modify": dòng JSON hỏng thành bản ghi giả, trái P2 §8; `run()` đổi `dry_run` mặc định thành False | Hoàng |
| PRE-19 | `source_job_id` dùng `abs(hash(...))`, không ổn định giữa các lần chạy | Hoàng |
| PRE-20 | Hai runner trùng (`run.py`, `run_integration.py`); thiếu test I2-I5; 5.177 vs 8.378 chưa giải thích | Hoàng |
| GEN-7 | Code tải R2 tự dựng boto3, prefix cũ, bucket gán cứng trong `preprocessing/integration` (liên quan GEN-4) | Hoàng |
| PRE-21 | Pipeline đặc trưng của Duy ghi trùng `04_normalization/all.parquet`; chưa nối vào `run.py` | Duy |
| PRE-22 | Lệch spec giữa cẩm nang Duy và SPEC-06/P4 (5 vs 6 cấp bậc, Embedded vs UI/UX, tên tỉnh) | Duy |
| PRE-23 | Lỗi parse tái hiện được: "tối thiểu 10 triệu", "2 tỷ", "Không yêu cầu", "Điện Biên Phủ", Python/PHP Developer, UI/UX | Duy |
| PRE-24 | Test P3/P4 nằm ngoài `testpaths` nên `make test` không chạy; chạy chung gây lỗi `tests/conftest.py:42` | Duy |
| PRE-25 | `ledger.csv` bị `.gitignore` (`*.csv`) nhưng `cohort.py`, `finalize_cohort.py` đọc nó; clone sạch không chạy lại được | Phát |
| PRE-26 | `reports/preprocessing/05_encoding` có 95 file lớn/pickle/npz/notebook HTML trong git | Phát |
| PRE-27 | `tests/test_golden_field_preservation.py` import module không tồn tại; 12 lỗi ruff UP038 | Phát |
| PRE-28 | Cohort P5 5.104/5.177, 5.092 job chưa duyệt, 17,1% job không có kỹ năng, sparsity 98,15% | Phát |
| MINE-1 | Mining chưa chạy trên dữ liệu thật; số liệu báo cáo là dữ liệu giả (`mining/synthetic.py`) | Phúc |
| MINE-2 | `requirements.txt` thiếu `mlxtend`, `shap`, `hdbscan`; 3 file test mining lỗi collect | Phúc |
| MINE-3 | `test_outlier_ratio_follows_quantile` fail khi thiếu `hdbscan` (fallback sklearn) | Phúc |
| MINE-4 | Khoảng k chưa thống nhất (task 6-12, checklist 4-14, spec 07 3-15); code dùng 4-14 | Phúc |
| MINE-5 | `load_mart_from_parquet.py` biến cột list thành chuỗi; chưa có bảng `skill_salary_shap_values` | Phúc |
| MINE-6 | SHAP không phải quan hệ nhân quả; `seniority_level` 0-4 gộp Thực tập và Mới tốt nghiệp (ghi chú cho báo cáo đồ án) | Phúc |
| VIZ-6 | `/insights` chưa kiểm với dữ liệu Mart thật (Mart rỗng, test mock query) | Sơn |
| VIZ-7 | Chưa chạy `./start_monitoring.sh --check` và kiểm 390 px; bundle JS 778 kB cần code-split | Sơn |
| GEN-8 | Mẫu báo cáo nghiệm thu trong `docs/tasks/*.md` chưa điền ở Duy, Phúc, Sơn (mục 5) | Duy, Phúc, Sơn |
| GEN-9 | Spec 10 ghi `gold/features.parquet` trên R2; encoding và mining đang dùng `data/curated` và `data/preprocessing/05_encoding`. Gộp vào quyết định GEN-4 (thêm `skill_cooccurrence.parquet` vào `GOLD_KEYS`) | Phát, Phúc |

Ghi chú: nhánh Tài tự thêm PRE-12 (thiếu nhãn), PRE-13 (category gate), PRE-14 (ADR-04 lệch SPEC-05), SCRAPE-17; khi merge, giữ các mục này và dùng bảng trên cho phần còn lại để không trùng mã.

## 8. Chưa kiểm tra được

- Pipeline đầu-cuối và mọi con số trên dữ liệu thật (không có `data/`, không dùng R2).
- Cào thật (TopCV trên HTML thật), `start_monitoring.sh --check`, 390 px, `/insights` với Mart thật.
- Quét secret chỉ làm trên phần diff (Khoa, Duy); Phát và Tài chưa quét nội dung JSON/báo cáo từng dòng.
- Lý do 1 test bị skip ở nhánh Khoa; nguyên nhân lỗi ledger trên Windows.

---

# Phụ lục: báo cáo đầy đủ của từng reviewer

Nội dung nguyên văn các báo cáo (tiêu đề đã hạ cấp một bậc). Mã `KNOWN_ISSUED` trong phụ lục là mã do từng reviewer tự đặt; dùng bảng đánh số lại ở mục 7.


## Phụ lục Khoa (feature/collection-hotfixes)

### Review nhánh origin/feature/collection-hotfixes (Khoa)

Người review: KHOA. Reviewer chỉ đọc; không sửa repo, không đụng R2/.env. Worktree test đã xóa.

#### Tóm tắt

- Nhánh KHÔNG chung lịch sử với sprint: `git merge-base` rỗng. Gốc nhánh là một commit snapshot (`c565177`) chứa nguyên 381 file, tạo ngày 08/11/2026 lúc 15:47. Commit này gộp snapshot repo (khớp gần nhất với `0cfa1b0`, merge `fix/known-issues-p1` ngày 05/11) với thay đổi của Khoa. Commit thứ hai `e8718e1` chỉ thêm C14 cho VietnamWorks (+12 dòng).
- Thay đổi thật của Khoa, tính so với `0cfa1b0`: 22 file, +666/-183. Gồm 3 crawler (topcv, topdev, vietnamworks), 4 file `tests/contract/`, 1 file báo cáo đặt sai chỗ, cùng các thay đổi phụ ngoài phạm vi (xem Rủi ro).
- Test: 160 passed, 1 skipped, 0 failed (`tests/contract` + `tests/unit`).
- Nội dung chạy được và test xanh, nhưng 3 trong 4 mục của task chưa đạt tiêu chí nghiệm thu: SCRAPE-14, SCRAPE-13 và phần "cào bù" của SCRAPE-16 (chi tiết ở mục Tồn đọng). SCRAPE-5 không có thay đổi mới (xem dưới).
- Merge thử: với base `0cfa1b0` thì sạch, không xung đột. Nếu không chỉ định base thì git từ chối (unrelated histories), còn `--allow-unrelated-histories` cho 20 xung đột add/add vô nghĩa.

#### Lịch sử nhánh (bước 2)

```
* e8718e1 Anh Khoa 2026-11-08 feat(vietnamworks): add C14 DiscoveryError handling and update docs
* c565177 Anh Khoa 2026-11-08 feat(collection): hotfixes for TopDev metadata (SCRAPE-5), IT filtering (SCRAPE-15), TopCV empty JD (SCRAPE-16) and contract tests C1-C14   (ROOT, 0 parent)
```

- Ahead/behind so với `origin/sprint/pipeline-delivery`: 2 / 139 theo tin nhắn của caller. Tôi đo lại: sprint hơn nhánh 2 commit docs (`83f8432`, `c1555c0`, 06/11) so với `0cfa1b0`. "Behind 139" là do git đếm toàn bộ lịch sử sprint mà nhánh không có.
- Khoa không branch từ sprint. Khoa chép working tree (có thể là export hoặc zip), `git init` rồi commit một lần. Hệ quả:
  - Mất lịch sử, nên không blame được.
  - Mất bit thực thi của 14 file.
  - Thiếu mọi file mới thêm vào sprint sau 05/11.
- `git diff --stat sprint nhánh` cho "65 files, +666/-7053". Phần lớn là do nhánh cũ hơn, không phải Khoa xóa:
  - 36 file D: `docs/spec/*` (13), `docs/tasks/*` (9), `docs/reports` (7), v.v. Đây là file sprint thêm sau `0cfa1b0`.
  - 7 file R100: `docs/prompting/draft/` do sprint đổi tên.
  - `AGENTS.md`, `agents.md`, `scripts/build_course_reports.py`, `scripts/load_mart_from_parquet.py`, `scripts/sql/init_mart_schema.sql`: sprint thêm sau `0cfa1b0`, nhánh không có.
  - `docker-compose.yml`: sprint đã sửa.
- Thay đổi riêng của Khoa (diff với `0cfa1b0`):

| File | +/- | Phạm vi |
|---|---|---|
| collection/sources/topcv/crawler.py | +176/-39 | trong phạm vi |
| collection/sources/topdev/crawler.py | +34/-4 | trong phạm vi |
| collection/sources/vietnamworks/crawler.py | +12 | trong phạm vi |
| tests/contract/standards.py | +3/-2 | trong phạm vi |
| tests/contract/test_all_sources_contract.py | +128 (mới) | trong phạm vi |
| tests/contract/test_topcv_contract.py | +54 | trong phạm vi |
| tests/contract/test_topdev_contract.py | +78 | trong phạm vi |
| 01_khoa_collection_hotfixes.md (gốc repo) | +181 | NGOÀI phạm vi, sai vị trí |
| bit thực thi 755→644 của 14 file (run.py, start_monitoring.sh, monitoring/run_all.sh, scripts/*.sh, scripts/*.py, verify_submission.py) | 0 dòng | NGOÀI phạm vi, ngoài ý muốn |
| tests/data/test_integration_step.py | -138 (xóa) | NGOÀI phạm vi, xem Rủi ro |

#### Đã làm (đối chiếu tiêu chí)

- C14 DiscoveryError, TopDev: `collection/sources/topdev/crawler.py` thêm `pages_ok` và `first_error`; sau vòng lặp, `if pages_ok == 0 and first_error: raise DiscoveryError`. Trang lỗi một phần vẫn pass. Có 2 test: `test_c14_discovery_fails_when_all_pages_fail` và `test_c14_discovery_partial_failure_is_ok`. ĐẠT.
- C14, VietnamWorks: cùng cơ chế ở 3 vòng quét, điều kiện `online and pages_ok == 0 and first_error`. Không có test nào cho VietnamWorks, chỉ có commit. Đoạn nhánh `online=False` (đọc file local) không raise, hợp lý.
- C14 `DiscoveryError` đã tồn tại trong `collection/common/url_ledger.py` (từ sửa TopCV 03/11). `test_c14_discovery_error_type` chỉ kiểm tra lớp kế thừa RuntimeError, không kiểm tra hành vi crawler nào.
- SCRAPE-15, TopDev lọc IT:
  - Cách làm: lọc ở Discovery bằng `preprocessing.common.it_filter.classify(title, skills)`; bỏ tin `non_it` trước khi `register_url`. Tham số `filter_it=True` mặc định.
  - Test: `test_scrape15_filter_non_it_jobs_in_discovery`, 3 tin (Golang giữ lại, Kế toán và Tài xế bị bỏ).
  - Điểm mạnh: có test, chỉ bỏ tin chắc chắn `non_it`; `unknown` vẫn đi qua nên ít mất tin IT.
  - Điểm yếu: không tìm tham số API đúng như task yêu cầu ("tìm đúng tham số lọc hoặc lọc sơ bộ", nên cách này chấp nhận được). Nhưng request vẫn tốn cho cả 14.572 tin vì API vẫn trả toàn bộ; chỉ tiết kiệm ledger và detail. Chưa đo tỷ lệ trên 1 trang thật (bước 2 checklist). Collection import từ `preprocessing/`, tức collection phụ thuộc preprocessing; import đặt sai thứ tự (chen giữa các import `collection.*`).
- SCRAPE-16, TopCV JD rỗng: viết lại mục mô tả, yêu cầu và quyền lợi trong `build_raw_payload` thành 4 tầng (container chuẩn không phân biệt hoa/thường → header h2/h3/h4/div/p → selector cũ → JSON-LD JobPosting). Có 2 test (`test_scrape16_empty_jd_fallback_recovery`, `test_scrape16_jsonld_fallback`) dùng HTML tự soạn.
  - Chưa chứng minh được nguyên nhân gốc: không có fixture của trang `/viec-lam/` hay `/brand/` bị rỗng thật, bước 3 checklist "thử trên 1 fixture bị rỗng cũ" không được làm. Test dựng HTML giả định, không phải HTML từ 297 tin thật.
  - Các từ khóa rất rộng: `"yêu cầu"` (6.1), `"mô tả"` (5.1), `"chế độ"` (8.1). Có thể khớp nhầm khối khác (ví dụ "Yêu cầu" trong tiêu đề phụ).
  - Mã lặp: 3 khối giống hệt nhau cho mô tả/yêu cầu/quyền lợi, `except Exception: pass` nuốt lỗi JSON-LD.
  - Dòng dài, ruff báo 75 lỗi trên 3 crawler + tests/contract (nhiều lỗi có sẵn từ trước; không đo riêng phần mới).
  - Phần "đưa 297 tin về PENDING để cào bù (Auto-Backfill)": KHÔNG có script hay lệnh nào trong diff. CHƯA LÀM.
- SCRAPE-5, TopDev metadata: không có thay đổi nào cho `DETAIL_FIELDS` trong nhánh. Theo `KNOWN_ISSUED.md`, code đã sửa ngày 02/11 trên sprint rồi. Bước 1 (cào thử 1 URL thật) không có bằng chứng trong báo cáo. KHÔNG kiểm chứng được CDC tạo version mới.
- SCRAPE-14, contract test 6 nguồn còn lại: CHƯA ĐẠT.
  - `test_all_sources_contract.py` chỉ chạy các kiểm tra cấu trúc trên 8 nguồn: C1 (có `discover_urls`/`crawl_details`), C10 (AST tìm lời gọi pause), C8 (key R2 mẫu tự tạo), cộng C2/C3/C6 trên ledger giả `test_src` và lớp C14.
  - Không có fixture hay parser test nào cho VietnamWorks, CareerViet, Vieclam24h, ITviec, Glints, JobsGO. `tests/fixtures/` vẫn chỉ có `topcv` và `topdev` (mỗi nguồn 3 file). Task yêu cầu "dựa trên fixtures offline", `tests/CLAUDE.md` yêu cầu 3 mẫu thật mỗi nguồn.
  - Các test C2/C3/C6/C14 trong file này không phụ thuộc nguồn nào, nên chúng không chứng minh gì về 6 nguồn. Có rủi ro đếm sai: "50 test contract pass" tạo ấn tượng đã phủ 8 nguồn.
- SCRAPE-13 (C10):
  - `standards.check_random_pause` được nới để chấp nhận `DelayConfig`. Sửa này đúng với CareerViet (đã nêu trong KNOWN_ISSUED).
  - Nhưng nó đồng thời làm VietnamWorks/TopDev/JobsGO "pass" mà vẫn lệch chuẩn 2.0–4.5 s: TopDev `polite_sleep(0.3, 0.7)` ở discovery và `DelayConfig(1.5, 3.0)`; VietnamWorks vẫn `time.sleep(0.3)` cố định; JobsGO 1.5–3.0. Không có quyết định "nâng chuẩn" hay "ghi ngoại lệ có lý do". Kiểm tra chỉ xem tên hàm, không xem giá trị.
- SCRAPE-11 (C14 cho 7 nguồn còn lại): chỉ làm TopDev và VietnamWorks (2/7). Còn CareerViet, Vieclam24h, ITviec, Glints, JobsGO.

#### Tồn đọng

1. SCRAPE-14: thiếu fixture và contract test thật cho 6 nguồn (xem trên).
2. SCRAPE-11: còn 5 nguồn chưa có `DiscoveryError`; VietnamWorks chưa có test.
3. SCRAPE-13: chưa quyết định chuẩn hay ngoại lệ; test chỉ bị nới.
4. SCRAPE-16: chưa có script đưa 297 tin về PENDING (cần dry-run và phê duyệt trước khi ghi R2); chưa xác minh trên HTML thật; chưa tìm nguyên nhân gốc thật.
5. SCRAPE-15: chưa đo tỷ lệ IT trên 1 trang thật; chưa tìm tham số API.
6. SCRAPE-5: chưa có bằng chứng cào thử.
7. Không có báo cáo nghiệm thu đúng mẫu `docs/tasks/01_khoa_collection_hotfixes.md` mục 4 trong PR; `01_khoa_collection_hotfixes.md` ở gốc repo đã được viết nhưng không vào đúng chỗ. Tôi chỉ đọc đầu file (tiêu đề, "Người thực hiện: Khoa"), chưa đối chiếu từng con số trong đó.

#### Rủi ro

- Lịch sử khác gốc: không merge nhánh này thẳng (xem Merge thử).
- `tests/data/test_integration_step.py` (138 dòng) bị xóa so với `0cfa1b0` và sprint. Đây là file của người khác, ngoài phạm vi (`tests/contract/` và `collection/`); khả năng cao do chép tree thiếu hoặc xóa nhầm. Merge 3 chiều sẽ xóa file này khỏi sprint, nên phải loại ra. (Tôi không xác minh lý do xóa.)
- 14 file mất bit thực thi (`run.py`, `start_monitoring.sh`, `monitoring/run_all.sh`, `scripts/*.sh`, ...). Merge 3 chiều sẽ làm `./start_monitoring.sh` mất quyền chạy trên sprint (Makefile/README gọi trực tiếp). Phải loại ra.
- File báo cáo `01_khoa_collection_hotfixes.md` đặt ở gốc repo, ngoài phạm vi; nên chuyển vào `docs/` hoặc dán vào mô tả PR.
- Collection → preprocessing: `collection/sources/topdev/crawler.py` import `preprocessing.common.it_filter`. Đảo chiều phụ thuộc so với kiến trúc (collection → R2 → preprocessing). Nếu `it_filter` đổi thì crawler gãy. Đã xác nhận file tồn tại trên nhánh.
- Rủi ro chức năng TopCV: selector lỏng ("yêu cầu", "mô tả", "chế độ") có thể ghi sai nội dung vào raw mới. Raw mới là bất biến, và CDC sẽ sinh version mới khi hash đổi cho mọi tin TopCV được cào lại, ngay cả tin trước đó đã đủ JD. Cần chạy trên fixture thật trước khi cào diện rộng.
- Không thấy: secret/.env, đổi prefix R2, đổi schema dùng chung (`collection/common/*` không bị sửa), file dữ liệu lớn mới. Lưu ý: nhánh chứa sẵn các notebook EDA gần 900 KB (`collection/reports/EDA_*.ipynb`) nhưng chúng cũng có trong `0cfa1b0`, không phải của Khoa. Tôi chỉ quét từ khóa secret trong phần diff của Khoa (không có kết quả); không quét toàn bộ 381 file.

#### Kết quả test

Lệnh: `.venv/bin/python -m pytest tests/contract tests/unit -q -p no:cacheprovider` trong worktree `--detach origin/feature/collection-hotfixes`.

- Kết quả: 160 passed, 1 skipped, 0 failed, 1 warning (Pydantic deprecation) trong 3.15 s.
- `tests/contract` riêng: 50 passed.
- 1 skipped ở `tests/unit/test_text_preprocessing_and_metrics.py`; không điều tra lý do, nên không thể nói là do môi trường hay do nhánh.
- `import collection` xác nhận lấy từ worktree (không phải repo chính).
- Chưa chạy: `tests/integration`, `tests/data`, cào thử thật (mạng bị chặn, không có phê duyệt).
- Ruff: 75 lỗi trên 3 crawler đã sửa + `tests/contract`. Không tách riêng phần dòng Khoa thêm.

#### Merge thử

- `git merge-tree --write-tree origin/sprint/pipeline-delivery origin/feature/collection-hotfixes` → `fatal: refusing to merge unrelated histories`.
- Với `--allow-unrelated-histories`: 20 xung đột add/add (verify_submission.py, 3 crawler, docker-compose.yml, run.py, các script, standards.py, 2 file test contract, ...). Đây là xung đột giả do không có base; vô nghĩa để giải.
- Với `--merge-base=0cfa1b0` (gốc thực tế của snapshot): sạch, không xung đột, trên cả `origin/sprint/pipeline-delivery` (`c1555c0`) và local `sprint/pipeline-delivery` (`bfaa076`, hơn origin 1 commit "normalize r2"). `standards.py` và `vietnamworks/crawler.py` bị cả hai bên sửa, vẫn gộp sạch.
- Nhưng gộp sạch sẽ kéo theo: xóa `tests/data/test_integration_step.py`, mất bit thực thi 14 file, thêm file `01_khoa_collection_hotfixes.md` ở gốc.

Đề xuất đưa vào sprint (không thực hiện):
1. Cherry-pick KHÔNG khả thi cho `c565177` (là root, không có parent, chứa cả snapshot). Thay vào đó, lấy patch đúng các file của Khoa: `git diff 0cfa1b0 origin/feature/collection-hotfixes -- collection/ tests/contract/` rồi `git apply` lên nhánh con của sprint; hoặc `git checkout origin/feature/collection-hotfixes -- <7 file>` (do người merge làm, trên nhánh mới từ sprint). Đây là cách tốt nhất vì tránh 3 tác dụng phụ ở trên.
2. Với `e8718e1` (commit 2) hoàn toàn có thể cherry-pick: cùng `0cfa1b0` làm base và chỉ sửa vietnamworks (nhưng nó phụ thuộc `DiscoveryError` có sẵn trong sprint, đã có).
3. Yêu cầu Khoa rebase/tạo lại nhánh từ `sprint/pipeline-delivery` rồi chỉ commit 7 file của mình. PR sau đó sẽ có lịch sử sạch.
4. Không dùng `--allow-unrelated-histories`.

#### Kết luận

MERGE SAU KHI SỬA. Hotfix được ưu tiên, nhưng nhánh phải làm lại cách đưa vào, và 2 hạng mục chưa đạt. Việc cần làm trước khi merge:
1. Tạo lại nhánh từ sprint (hoặc áp patch của 7 file) để không xóa `tests/data/test_integration_step.py`, không mất bit thực thi, chuyển báo cáo khỏi gốc repo.
2. Thêm test cho `DiscoveryError` của VietnamWorks (hoặc ghi rõ chưa có).
3. Sửa tuyên bố nghiệm thu: SCRAPE-14, SCRAPE-13 và phần PENDING backfill của SCRAPE-16 là chưa xong; test_all_sources chỉ phủ cấu trúc.
4. Chạy `build_raw_payload` trên HTML TopCV thật (fixture mới) để xác nhận selector và nới lỏng từ khóa nếu khớp nhầm.

Phần hotfix SCRAPE-15 và C14 cho TopDev hợp lý, có test, có thể nhận ngay sau bước 1. Hạng mục còn thiếu nên ghi vào KNOWN_ISSUED (dưới) chứ không chặn merge phần đã đúng. Nếu muốn, chia thành: (a) merge ngay topdev + vietnamworks + topcv selector, (b) giữ SCRAPE-13/14/16-backfill mở.

#### Không kiểm tra được

- Không cào thử thật (mạng bị chặn, và chưa có phê duyệt cho R2): không biết tỷ lệ IT thật sau lọc, không biết TopCV selector mới có lấy được JD trên 297 tin thật.
- Không điều tra vì sao `tests/data/test_integration_step.py` bị xóa, hay lý do 1 test skipped.
- Không so từng dòng `01_khoa_collection_hotfixes.md` với số liệu thật.
- Không quét secret trên toàn bộ 381 file, chỉ phần diff của Khoa.
- Không xác minh Khoa dùng công cụ gì để tạo snapshot; "chép working tree rồi init" là suy luận từ cấu trúc git.

#### Đề xuất cập nhật KNOWN_ISSUED.md

Sửa các mục có sẵn và thêm mục mới theo khuôn hiện có:

**SCRAPE-14 (cập nhật). Contract test cho 6 nguồn còn lại**

- Hiện trạng: nhánh `feature/collection-hotfixes` thêm `tests/contract/test_all_sources_contract.py` nhưng chỉ kiểm tra cấu trúc C1/C8/C10 trên 8 nguồn; chưa có fixture hay parser test cho VietnamWorks, CareerViet, Vieclam24h, ITviec, Glints, JobsGO.
- Cách xử lý: thêm 3 mẫu thật vào `tests/fixtures/<nguồn>/` và test parse cho từng nguồn (xem `tests/CLAUDE.md`).

**SCRAPE-11 (cập nhật). Discovery lỗi toàn trang mà vẫn báo thành công**

- Hiện trạng: TopCV (03/11), TopDev và VietnamWorks (08/11, nhánh hotfix) đã raise `DiscoveryError`; VietnamWorks chưa có test. Còn CareerViet, Vieclam24h, ITviec, Glints, JobsGO.

**SCRAPE-13 (cập nhật). Thời gian nghỉ lệch chuẩn (C10)**

- Hiện trạng: `standards.check_random_pause` đã nhận `DelayConfig`, nhưng chỉ kiểm tra tên hàm, không kiểm tra giá trị; TopDev, VietnamWorks, JobsGO vẫn dưới 2.0–4.5 s.
- Cách xử lý: quyết nâng chuẩn hay ghi ngoại lệ có lý do; cho check đọc giá trị min/max.

**SCRAPE-16 (cập nhật). 297 tin TopCV không có JD**

- Hiện trạng: `build_raw_payload` đã có fallback 4 tầng (nhánh hotfix, chưa merge); chưa kiểm trên HTML thật, chưa có script đưa 297 tin về `PENDING`.
- Cách xử lý: lấy fixture `/viec-lam/` và `/brand/` rỗng thật, nới hoặc siết từ khóa, sau đó chạy dry-run backfill, gửi số liệu và chờ đồng ý trước khi ghi R2.

**SCRAPE-17. TopDev lọc IT bằng `it_filter` phụ thuộc ngược sang preprocessing**

- Hiện trạng: `collection/sources/topdev/crawler.py` import `preprocessing.common.it_filter.classify` để bỏ tin `non_it` ở Discovery; API vẫn trả toàn bộ 14.572 tin nên request vẫn tốn.
- Nguyên nhân: chưa tìm được tham số lọc ngành của `/td/v2/jobs`.
- Cách xử lý: tìm tham số API đúng (hoặc lọc theo danh mục trang); nếu giữ `it_filter`, chuyển sang `collection/common/` để tránh phụ thuộc ngược. Chưa đo tỷ lệ IT trên trang thật.

**GEN-1. Nhánh `feature/collection-hotfixes` không chung lịch sử với sprint**

- Hiện trạng: nhánh bắt đầu từ commit snapshot `c565177` (root), mất bit thực thi 14 file và thiếu `tests/data/test_integration_step.py`.
- Nguyên nhân: nhánh tạo bằng cách chép cây thư mục rồi `git init`, không branch từ sprint.
- Cách xử lý: áp patch riêng 7 file của Khoa vào nhánh mới từ sprint; không merge trực tiếp.

## Phụ lục Tài (feature/p1-clean-dedup)

### Review nhánh feature/p1-clean-dedup (Phan Nhật Tài) — người review: TÀI

#### Tóm tắt
3 commit (f693b30, 52abf35, 8505c6b), 34 file, +4424/-288. Code Clean 2 tầng + Dedup 2 lớp (D2 nội sàn theo canonical hash, liên sàn blocking + TF-IDF cosine >= 0,85, Union-Find) đã có và khớp SPEC-05 §3.2 kể cả "gộp bắc cầu". 90 test Clean/Dedup đạt, full unit 180 đạt/1 skip, ruff phạm vi sạch, merge thử không xung đột. NHƯNG tiêu chí "Precision IT >= 95%" CHƯA đo được (0 nhãn) và tác giả tự khai rõ là chưa đóng.

#### Đã làm (bằng chứng)
- Lọc IT 2 tầng tất định, không LLM: `preprocessing/clean/run.py:22` dùng `common/it_filter.classify` + `classify_unknown`; C4a gắn nhãn (run.py:158-166), C4c chỉ loại theo `it_policy.json` (run.py:182-189), C5 JD < 30 từ (run.py:33,192). Không sửa `common/it_filter`.
- Khử trùng nội sàn: D2 trong `deduplication/intra_source.py`; CDC tách `hop_same_version` / `hop_version_not_bumped`.
- Liên sàn: `blocking.py` (Company_Location_TitleGroup, dòng 90), `inter_source.py:30` COSINE_THRESHOLD=0.85, Union-Find (dòng 132-148), hợp S1∪S2 (dòng 221). Bắc cầu ghi `transitive-link`/`transitive-dropped` trong duplicates_audit.csv. Test biên: `tests/unit/test_deduplication_step.py:487` (A-B=0,85; B-C=0,9; A-C=0,8).
- Số liệu thật khai: 13.365 raw -> 5.077 Clean -> 4.897 Golden Master; Clean loại C1=1987, C2=616, C3=4, C4c=5409, C5=188, C6=71, C7=13; Dedup D2=54, D4=9, D5=117. Báo cáo JSON trong `reports/preprocessing/01_clean` và `01b_deduplication` (có `_all.json` + 8 sàn). Tôi KHÔNG chạy lại trên dữ liệu thật (không có data/ trong worktree, cấm mạng/R2) nên số này chỉ là lời khai, chưa tái lập được.
- Phương trình bảo toàn: báo cáo khai đúng ở cả 8 sàn mỗi bước; tôi chỉ xác nhận có test bảo toàn, không tái tính trên data thật.

#### Tồn đọng
1. Precision IT >= 95%: mẫu 643 dòng / 0 nhãn; chưa đo. Nghiệm thu mục "Bước 2" chưa đạt (tác giả tự thừa nhận, §3 và PRE-12).
2. `it_policy.json` đang bật drop non_it cho các sàn (C4c loại 5.409 tin) với "evidence" là ghi chú tổng hợp (vd "79/80", "42/47") không kèm nhãn từng tin; chính báo cáo của Tài nói không dùng chúng làm bằng chứng. Tức là quyết định loại 5.409 tin chưa có bằng chứng kiểm chứng lại. File này không đổi trong diff (đã có sẵn ở nhánh gốc).
3. Category gate SPEC-05 §2.4: code dùng nhóm nghề suy từ tiêu đề+JD, không đọc chuyên mục sàn (PRE-13, chờ lead chốt A/B/C).
4. Integration chưa đọc đầu ra Dedup (01b); pipeline cuối chưa nối. Report snapshot trong repo là kết quả f693b30, tác giả nói chưa phải kết quả mã đã sửa (xem rủi ro).
5. Hai cặp biên Tinh Vân/Nasani chưa duyệt nghiệp vụ (Q5). ADR-04 §3.2 chưa đồng bộ với SPEC-05 (PRE-14) — thuộc docs/spec của lead.
6. Báo cáo nghiệm thu mẫu §4 (5 mục: Vấn đề/Nguyên nhân/Giải pháp/Bằng chứng/Tồn đọng) KHÔNG được điền vào mẫu; thay vào đó là §3 + §5 dạng nhật ký dài. Cần dán đúng mẫu vào PR.

#### Rủi ro
- File ngoài thư mục được giao: `KNOWN_ISSUED.md` (+33, chỉ thêm SCRAPE-17, PRE-12/13/14), `docs/issue_log.md` (+49, thêm L-29..L-31), `docs/tasks/02_...md` (tài liệu task của chính Tài, OK), 17 file `reports/preprocessing/01_clean|01b_deduplication/*.json` (output, được theo dõi trong git, nhưng ghi đè snapshot 01_clean cũ), `tests/unit/test_clean_step.py`, `test_deduplication_step.py` (test mới, hợp lý). Không có file xóa, không sửa `common/`, `integration/`, `collection/`. Cần lead đồng ý việc đụng KNOWN_ISSUED/issue_log (task doc tự nói "ngoài phạm vi sửa của Tài"; thực tế vẫn sửa -> bất nhất, nhưng chỉ thêm mục).
- Báo cáo JSON `reports/` được commit là snapshot lịch sử f693b30, không phải kết quả của code mới (task doc §5.1) -> số trong repo có thể lệch với code sau fix (vd `hop_version_not_bumped=15` định nghĩa sai ở snapshot). Monitoring đọc các file này -> hiển thị số cũ/sai định nghĩa tới khi chạy lại. Cần chạy lại và commit snapshot mới sau khi merge.
- Dữ liệu lớn/secret: reports 01b ~68K, không thấy data lớn; tôi không quét secret chuyên sâu, chỉ thấy diff thuần mã/JSON/markdown (không kiểm từng dòng JSON báo cáo).
- Mâu thuẫn SPEC-05 mới chốt (b80045e): KHÔNG mâu thuẫn — cosine 0,85, blocking có Title_Group, Union-Find bắc cầu, có audit `transitive-link`, đúng §3.2.B.6. ADR-04 cũ (Jaccard>=0,8 và cosine>=0,75) vẫn lệch, nhưng code theo SPEC-05 là đúng lựa chọn lead.
- Số liệu §5.8.1 (842/101/310/431...) từ script probe, tác giả đã ghi rõ không phải nhãn; không dùng làm tiêu chí.
- Chưa kiểm: cosine đúng hay sai trên cặp thật (cần người đọc JD), chất lượng phân loại IT thực tế, Windows vs Linux khác biệt.

#### Kết quả test (worktree detached tại origin/feature/p1-clean-dedup, venv chung, mạng chặn)
- `tests/unit/test_clean_step.py` + `test_deduplication_step.py`: 90 passed (35 + 55).
- `tests/unit` toàn bộ: 180 passed, 1 skipped, 0 failed. (Tác giả khai 1 fail test ledger `test_latest_status_change_wins_between_workers` trên Windows; trên Linux của tôi test này đạt -> SCRAPE-17 có thể chỉ do môi trường; tôi không xác nhận nguyên nhân.)
- `ruff check` phạm vi clean/, deduplication/, 2 file test: All checks passed.
- Không chạy tests/contract, integration, và không chạy lại pipeline trên dữ liệu thật (không có data/).
- Đã `git worktree remove --force` wt_tai.

#### Merge thử
`git merge-tree --write-tree origin/sprint/pipeline-delivery origin/feature/p1-clean-dedup` -> chỉ trả hash cây (6d9eb0ac...), không báo CONFLICT. Không có file xung đột.

#### Kết luận
**MERGE SAU KHI SỬA**: (1) dán đúng Mẫu Báo Cáo Nghiệm Thu (§4) vào mô tả PR, ghi trung thực "Precision IT chưa đo, 0 nhãn"; (2) lead/Tài chốt cách xử lý `it_policy.json`: hoặc gán nhãn đủ để đo, hoặc ghi rõ chấp nhận rủi ro loại 5.409 tin theo evidence tổng hợp (không kiểm chứng được); (3) sau merge chạy lại Clean+Dedup và commit lại snapshot `reports/` bằng code mới (hiện là snapshot cũ). Phần code/test/logic dedup không có lỗi chặn merge. Nếu lead chấp nhận mục (2) là việc nghiệm thu riêng, có thể MERGE ĐƯỢC ngay về mặt kỹ thuật vì không xung đột và test xanh.

#### Đề xuất cập nhật KNOWN_ISSUED.md
Nhánh đã tự thêm PRE-12 (thiếu nhãn), PRE-13 (category gate), PRE-14 (ADR-04), SCRAPE-17. Đề xuất thêm theo khuôn `**MÃ. Tiêu đề**` + gạch đầu dòng:
- **PRE-15. `it_policy.json` đang loại non_IT 8 sàn bằng bằng chứng tổng hợp chưa tái kiểm** — C4c loại 5.409 tin; evidence "79/80, 42/47..." không có nhãn từng tin; cần đo bằng nhãn PRE-12 hoặc lead chấp nhận rủi ro bằng văn bản.
- **PRE-16. Integration chưa đọc đầu ra Dedup (01b_deduplication)** — Integration vẫn đọc 01_clean; cần Hoàng/lead nối; báo cáo Integration 03/11 (5177 dòng) lệch 4897 của Golden Master.
- **PRE-17. Snapshot `reports/preprocessing/01_clean|01b_deduplication` là kết quả f693b30, không phải code đã sửa** — chạy lại sau merge, commit snapshot mới.
- **GEN-5. Test ledger `test_latest_status_change_wins_between_workers` fail trên Windows, pass trên Linux** (cập nhật SCRAPE-17: có thể đổi tên thành lỗi phụ thuộc nền tảng, `save_catalog` dùng `mem_ts >= disk_ts`).

## Phụ lục Hoàng (feature/p2-integration-flatten)

### Review nhánh feature/p2-integration-flatten (Hoàng)

#### Tóm tắt
3 commit (48e94de, df7e2ab, 402e937) của dohoangdeptrailaanh123-coder. Sửa 4 file trong preprocessing/integration/ (__init__, json_flattener, run, run_integration) và thêm 2 bản báo cáo trùng nhau. Có 1 test unit đang qua trên nhánh sprint bị làm hỏng, và nhiều chỗ lời khai không khớp với repo.

#### Đã làm
- json_flattener.py (+243/-): thêm chịu lỗi (try/except về _flatten_generic), đọc thêm khóa dự phòng (company dict, salary dict của Glints, skills dạng dict), `_clean_str` loại "none/null/nan" và dict/list.
- run.py: thêm `ensure_p1_data_from_r2`; dòng JSON hỏng không bị bỏ nữa mà thay bằng bản ghi giả; `dry_run` mặc định đổi True -> False.
- run_integration.py: viết lại gần như hoàn toàn thành runner riêng (~400 dòng, từ điển chẩn đoán Null, R2), xuất cùng all.parquet như run.py.
- Báo cáo nghiệm thu: file `03_hoang_integration_and_flattening.md` ở gốc repo và bản sao trong preprocessing/integration/.

#### Tồn đọng / lệch so với lời khai và spec
1. Báo cáo nói bàn giao `data/preprocessing/02_integration/all.parquet`, `reports/.../_all.json` và `docs/preprocessing/integration/03_hoang_...md`. Không có file nào trong nhánh (diff chỉ 6 file). Không kiểm chứng được 5.177 dòng; spec P2 ghi 8.378 -> 8.378 (03/11). Hai con số lệch nhau, báo cáo không giải thích.
2. Báo cáo đặt sai chỗ: yêu cầu là docs/tasks/ (hoặc dán vào PR), nhánh lại đặt ở gốc repo và trong preprocessing/integration/ (ngoài phạm vi thư mục được giao, thêm rác).
3. Mâu thuẫn spec P2 mục 8: I0 phải là luật "drop" đếm dòng JSON hỏng kèm ví dụ; nhánh đổi thành "modify" và nhét bản ghi giả (title = 80 ký tự đầu dòng hỏng) vào all.parquet -> dữ liệu rác chảy xuống P3-P5, còn nghĩa "rows_out = rows_in" bị đạt bằng cách tạo dòng giả.
4. `dry_run` mặc định False trong `run()`: gọi không tham số sẽ ghi file. Đổi hành vi so với spec/driver.
5. `abs(hash(source_url))` làm `source_job_id`/`job_id_global` khi thiếu id: `hash()` của str đổi theo PYTHONHASHSEED nên id không ổn định giữa các lần chạy, ảnh hưởng dedup/ledger. Phải dùng hash cố định (sha1/md5).
6. Task nói tiêu chí "kiểm tra 8 nguồn, ruff": không có bằng chứng chạy ruff, không có test mới nào (0 file test thêm), spec P2 mục 7 yêu cầu mỗi luật I2-I5 một test. Không thể xác minh phần chạy thực tế vì không có dữ liệu trong nhánh và không đụng R2.
7. Thêm BOM (U+FEFF) vào đầu json_flattener.py.
8. Hai runner trùng chức năng (run.py và run_integration.py); không rõ cái nào là chính. `__init__` nhập cả hai. `run_integration.py` ở sprint có API `integrate_single_source(source, ...)` khác chữ ký với bản nhánh (`integrate_single_source(source_name)`) nên ai gọi theo chữ ký cũ sẽ vỡ (không tìm thấy nơi nào khác trong repo import chúng, grep hạn chế).
9. Không kiểm tra được từng cột flatten của 8 nguồn với fixture thật (chỉ chạy test sẵn có).

#### Rủi ro
- R2: `ensure_p1_data_from_r2` (cả 2 file) tự tạo client boto3 bằng biến môi trường, đi vòng `get_r2_client()` (vi phạm quy tắc "mọi kết nối qua r2_storage"), thử các prefix cũ (`preprocessing/01_clean/...`, `01_clean/...`, `data/...`) không thuộc layout `raw/ url_ledger/ staging/ curated/` (liên quan GEN-4), bucket mặc định hard-code "vn-it-jobs". Chỉ có thao tác đọc (head/download), không thấy ghi/xóa; `scripts/push_integration_to_r2.py` KHÔNG bị đụng (không có trong diff).
- Nuốt lỗi: `except Exception: continue/ _flatten_generic` che lỗi thật, dòng hỏng thành dữ liệu rác, không có chỉ báo trong output.
- Không có dữ liệu lớn hay secret trong diff (chỉ code/md). Không xóa file của người khác; schema 18 trường + khóa giữ nguyên (chưa kiểm cột ALL_OUTPUT_COLUMNS đầy đủ vì không đổi).
- Nhánh gốc cũ: behind 2, ahead 3.

#### Kết quả test
Chạy trong worktree detach (mạng chặn): `pytest tests/unit tests/data/test_integration_step.py tests/integration/test_preprocessing_pipeline.py tests/integration/test_pipeline_reports.py`
- Nhánh Hoàng: 1 failed, 118 passed, 5 skipped. Fail: tests/unit/test_integration_step.py::test_integration_output_contract_and_conservation (OSError: thư mục đích không tồn tại, vì run.py giờ mkdir `OUT_DIR` thay vì `OUT_FILE.parent`, mà test monkeypatch OUT_FILE).
- Nhánh sprint (đối chứng): 119 passed, 5 skipped. => hồi quy do nhánh này gây ra.
Chưa chạy toàn bộ suite, chưa chạy ruff, chưa chạy pipeline thật.

#### Merge thử
`git merge-tree --write-tree` sạch, không xung đột (tree 2ad57d79...). Không có xung đột văn bản, nhưng không có nghĩa merge an toàn (hồi quy test ở trên).

#### Kết luận
MERGE SAU KHI SỬA:
1. Sửa hồi quy test (mkdir `OUT_FILE.parent` thay `OUT_DIR`).
2. Hoàn lại I0 thành "drop" (không tạo bản ghi giả) hoặc sửa cả spec/test có chủ ý.
3. Thay `hash()` bằng hash cố định.
4. `dry_run` mặc định True như cũ.
5. Bỏ code R2 tự chế (dùng `get_r2_client()` hoặc bỏ hẳn, tải bằng `sync_cloud_lakehouse.py`); gộp/bỏ run_integration.py trùng lặp.
6. Xóa hai file báo cáo nằm sai chỗ, đưa báo cáo vào docs/tasks/PR với số liệu thật (kèm lệnh), thêm test cho I2-I5, bỏ BOM, rebase lên sprint.

#### Đề xuất KNOWN_ISSUED.md
- PRE-HOANG-1 (đặt mã tiếp theo theo quy ước hiện có, ví dụ PRE-n): I0 giả bản ghi thay vì drop, mâu thuẫn P2 mục 8.
- PRE-n+1: `source_job_id` dùng `hash()` không ổn định giữa các lần chạy.
- GEN-5: code tải R2 ngoài `get_r2_client()` và prefix cũ trong preprocessing/integration (liên quan GEN-4).
- PRE-n+2: hai runner trùng (run.py / run_integration.py), cần chọn một.
- PRE-n+3: thiếu test cho luật I2-I5; số liệu 5.177 vs 8.378 chưa giải thích.

## Phụ lục Duy (feature/p3-p4-transform-normalize)

### Review nhánh Duy: feature/p3-p4-transform-normalize

Người review: DUY. Phạm vi: `preprocessing/transformation/`, `preprocessing/normalization/`, `preprocessing/dictionaries/`.
Commit: 9b33a05 (duynkh9326-hub, 07/11/2026 17:48) "feat(preprocessing): implement P3-P4 transformation and normalization". Ahead 1, behind 2 so với origin/sprint/pipeline-delivery (2 commit thiếu chỉ là docs/tasks, docs/spec, 2 script `scripts/build_course_reports.py`, `scripts/load_mart_from_parquet.py`, `scripts/sql/init_mart_schema.sql`; không đụng thư mục của Duy).

#### Tóm tắt
Nhánh thêm một pipeline "đặc trưng" song song (`transformation/pipeline.py`) với parser lương mới, parser kinh nghiệm/seniority 0-4, phân loại 12 Job Family, chuẩn hóa tỉnh, trích kỹ năng theo taxonomy, kèm 67 test. Test của nhánh đều qua và merge sạch. Phần parse lương và 34 tỉnh đạt các ca trong cẩm nang. Có 4 vấn đề thật: (1) pipeline mới ghi cùng đường dẫn `data/preprocessing/04_normalization/all.parquet` với `normalization/run.py` chính thức; (2) code mới KHÔNG được nối vào `run.py` của P3/P4, nên pipeline 5 bước vẫn dùng parser cũ; (3) cẩm nang Duy lệch SPEC-06/P4 (5 cấp bậc thay vì 6, Embedded thay UI/UX, tên tỉnh không có "TP."); (4) không có báo cáo nghiệm thu nào kèm theo, nên mọi con số (tỷ lệ lương, thỏa thuận, 50 JD) không có nguồn để đối chiếu.

#### Đã làm (có bằng chứng)
Danh sách file (git diff --name-status): 18 file, tất cả nằm trong 3 thư mục được giao. KHÔNG có file ngoài thư mục, không có file bị xóa, không có file dữ liệu lớn (JSON lớn nhất: `skills_taxonomy.json` 18,7 KB, `provinces_34.json` 11 KB), grep không thấy secret.

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Parse lương, 4 ca cẩm nang | Đạt (tôi chạy thật): "15 - 20 triệu" 15/20/17.5; "$1,500 - $3,000" 38.1/76.2/57.15; "Lên đến 40 triệu" None/40/40; "Thỏa thuận" negotiable, min/max None | `transformation/salary_parser.py` `parse_salary` (dòng ~265-320); test `test_feature_engineering.py:34-35` |
| USD 25.400, năm /12, ngày x22, giờ x160 | Đạt | `salary_parser.py:25-31`, `_period_factor` |
| Không impute lương thỏa thuận | Đạt: min/max/avg = None, `is_negotiable=True`; "Thương lượng" ghi đè cờ crawler False; Subset A/B | `pipeline.py` `partition_salary_subsets`, `_is_negotiable` |
| Lương "Up to"/"Từ" | Đạt: Up to 50M -> max 50; Từ 20tr -> min 20; Up to 2,000 USD -> 50.8 | chạy thật |
| Kinh nghiệm min/max | Đạt một phần, xem Tồn đọng | `experience_parser.py` `parse_experience_range` |
| 34 tỉnh | `provinces_34.json` có đúng 34 tỉnh, giữ nguyên `key`/`name`/`old`, chỉ thêm alias + `canonical`, `code`, `special_values` (so với bản trên sprint: không mất `name`, `old`, alias nào). TP HCM, Sài Gòn, HN, Hòa Lạc, Bình Dương, Vũng Tàu, Quảng Nam, Nam Định, Ninh Thuận, Hải Dương đều ra đúng tỉnh mới | chạy `location_normalizer.normalize_location`; `location_normalizer.py:32-34` ép đúng 34 |
| Taxonomy kỹ năng | 6 category, 92 kỹ năng (`get_taxonomy_skill_count()`), alias golang/go->Go, k8s->Kubernetes, reactjs->React đạt | chạy thật |
| Tránh bắt nhầm "Go" trong "Good communication" | Đạt: "Good communication, go to market, we go beyond" -> [] | chạy thật; test `:179` |
| 12 Job Family | Đủ 12 tên theo cẩm nang (có Embedded) | `job_family_classifier.py:11-14` |
| Fullstack cần cả backend + frontend skill | Đạt | `job_family_classifier.py` + test `:230-233` |
| Ruff | 7 lỗi UP038 trong các file nhánh đổi (không tự sửa được); cả 2 thư mục còn 206 lỗi (đa số UP006/UP007 ở file cũ như run.py, cross_deduplicator.py) | `ruff check` |

#### Tồn đọng (lời khai trong nhánh vs code)

1. **Va chạm đường ra / luồng kép.** `transformation/pipeline.py` mặc định đọc `data/preprocessing/02_integration/all.parquet` và ghi `data/preprocessing/04_normalization/all.parquet` (`pipeline.py` `run_pipeline`, `main`). `normalization/run.py:33-36,332` (bước P4 chính thức của `scripts/run_preprocessing.py`) cũng ghi đúng file đó, đọc từ `03_transformation/all.parquet`. Chạy `run_transformation.py` sẽ ghi đè kết quả P4 chính thức bằng schema khác (10 cột Duy, bỏ qua P3 và mọi cột P4). Cẩm nang cho phép đường dẫn này nhưng không biết đã có P3/P4 chính thức.
2. **Code mới chưa nối vào pipeline chính.** `git diff` không đổi `transformation/run.py` hay `normalization/run.py`. `run.py` P3 vẫn import `parse_salary_cascade` từ `salary_parser`, giờ là re-export của `salary_parser_legacy.py` (bản cũ, chỉ đổi kiểu type hint). `parse_salary` mới, `normalize_location`, `classify_job_family`, `normalize_seniority` chỉ được `pipeline.py` và test gọi. Hệ quả: các sửa T2a-T2f của P3 (nếu có) nằm ở bản legacy, còn parser mới là nhánh phụ chưa dùng trong 5 bước.
3. **Lệch spec, README_DUY.md tự thừa nhận.** Cấp bậc: Duy 0-4 (Intern và Fresher gộp, -1 = chưa rõ) so với SPEC-06 mục 2.2 và P4 §3 là 6 nhãn. 12 nhóm: Duy có Embedded + Product, bỏ "Thiết kế UI/UX" (SPEC-06 dòng 65, P4 §3). Kết quả chuẩn hóa tỉnh dùng `canonical` ("Hồ Chí Minh") trong khi `preprocessing/common/province.py` (dùng chung) và P4 dùng `name` ("TP. Hồ Chí Minh"), nên 2 pipeline sinh 2 tên khác nhau cho cùng tỉnh. Cần chốt trước khi merge; nhánh không tự quyết được.
4. **Lỗi parse lương còn thấy khi chạy thật:** "Mức lương tối thiểu 10 triệu" -> min=max=10 (không nhận "tối thiểu" là cận dưới); "2 tỷ" -> 2.0 triệu (không hỗ trợ "tỷ", sai 1000 lần); "35 triệu/năm" -> 2,92 (đúng theo luật /12, nhưng đây là cách ghi lương năm có thể là lương tháng nhầm). Không phát hiện regex "tu" lỏng gây sai trong các ca đã thử, nhưng `_LOWER_PREFIX_RE` dùng `search` không neo (`salary_parser.py:50`), có rủi ro khớp nhầm; chưa kiểm chứng trên dữ liệu thật.
5. **Kinh nghiệm:** "Không yêu cầu" -> (None, None, unparsed), seniority -1 (P3 T4 yêu cầu 0-0). "Dưới một năm kinh nghiệm" (ví dụ F1 trong P3) -> unparsed. "Không yêu cầu kinh nghiệm" -> (0.0, None) qua `parse_experience_range` (pipeline dùng hàm này) nhưng (0.0, 0.0) qua wrapper `parse_experience` (run.py dùng): hai nơi cho hai kết quả. Tiêu chí P3 "ít nhất 90% giá trị chữ parse được" không có số đo.
6. **Job Family:** "Python Developer", "PHP Developer" -> None; "UI/UX Designer" -> None; "Software Engineer" + skill [C, C++] -> Embedded (dễ sai: tin backend C++ thành Embedded). Chưa có kiểm tay 50 tin (P4 §7: >= 90%). `job_family` None nằm trong cột kết quả, không có nhãn "Khác".
7. **Kỹ năng:** "Languages: C, R, Go" -> [] (quá bảo thủ, mất recall). `validate_taxonomy()` báo "Ambiguous alias 'c/c++'" (alias trùng 2 kỹ năng). Chưa chạy `audit_skill_samples.py` với 50 JD thật.
8. **Vị trí test.** 67 test nằm ở `preprocessing/transformation/tests/`, ngoài `testpaths = ["tests"]` (pyproject.toml:12) nên `make test` / CI không chạy chúng; ngoài ra chạy chung với `tests/` làm `tests/conftest.py:42` văng INTERNALERROR (phải chạy riêng). Quy ước `tests/README.md` là tests/unit.
9. **Địa điểm:** "Điện Biên Phủ" (tên đường) -> "Điện Biên"; "Điện Biên Phủ, Bình Thạnh, Hồ Chí Minh" -> "Nhiều địa điểm" (sai). Đây là lỗi đã ghi trong P4 §8 và vẫn lặp lại. Địa điểm nước ngoài (Singapore, Tokyo) -> None, không có cờ `ngoai_vn`; "Remote" trả chuỗi "Remote" thay vì `tinh_thanh=null + remote=true` như P4.
10. **Không có báo cáo nghiệm thu.** `docs/tasks/04_...md` ở cả 2 nhánh chỉ có mẫu trống. `README_DUY.md` không có số liệu thật; chính README ghi dữ liệu thử nghiệm chỉ 937 dòng (Glints 5, TopDev 1, VietnamWorks 931), 5 nguồn khác rỗng. Các con số mà cẩm nang yêu cầu (tỷ lệ lương, ~55% thỏa thuận, median, số JD kiểm) CHƯA có và tôi không thể tái tạo: thư mục `data/preprocessing/` và `data/integration/` không tồn tại trong repo cục bộ.
11. Cờ `salary_under_1m`, `salary_source`, `flags` của P3 và các cột P4 (`seniority_can_kiem`, `salary_suspect`, winsorize) không có trong nhánh; nhánh không đụng tới các cột này.

#### Rủi ro
- Ghi đè `04_normalization/all.parquet` (mục 1). Chỉ xảy ra khi chạy `run_transformation.py` thủ công; không có dữ liệu bị mất trong git.
- `provinces_34.json` là file dùng chung với `preprocessing/common/province.py`: schema chỉ thêm khóa, `name`/`old`/`aliases` không bị xóa (đã so từng tỉnh), và test tests/unit + integration trên cây đã merge vẫn qua. Alias mới (vd. "Hòa Lạc", "Thủ Đức") có thể đổi kết quả P3 `location_parser` trên dữ liệu thật; chưa so sánh được vì không có dữ liệu.
- Lệch tên tỉnh/cấp bậc giữa hai pipeline (mục 3) sẽ gây lỗi âm thầm ở P5 Encoding và Monitoring nếu cả hai cùng sinh cột.
- Không có dữ liệu lớn, không có secret, không xóa file của người khác, không đổi schema Parquet dùng chung của pipeline chính (vì code mới chưa nối vào).
- Branch là một commit duy nhất 3.519 dòng thêm, khó review/revert từng phần.

#### Kết quả test (thực tế)
- Worktree tại commit nhánh 9b33a05: `pytest preprocessing/transformation/tests -q` -> **67 passed**, 0 fail, 0 skip. `pytest tests/unit` -> **110 passed, 1 skipped**.
- Worktree cây đã merge thử (origin/sprint c1555c0 + nhánh, `git merge --no-commit`, đã hủy): `pytest tests/unit tests/integration` -> **206 passed, 3 skipped**; `pytest preprocessing/transformation/tests` -> **67 passed**.
- Không chạy: `tests/contract`, `tests/data`, test cần mạng hoặc cần `data/`; không chạy pipeline thật vì thiếu dữ liệu; không chạy `audit_skill_samples.py`, `run_normalization.py`.
- Ca biên (ngoài test của Duy) do tôi chạy trực tiếp bằng script ngắn trong worktree; kết quả ở mục Tồn đọng.
- Đã `git worktree remove --force` cả 2 worktree; `git worktree list` chỉ còn repo chính; `git status` sạch.

#### Merge thử
`git merge-tree --write-tree origin/sprint/pipeline-delivery origin/feature/p3-p4-transform-normalize` -> trả về tree 0eb1232415821e39c9b32f3e12849fa8075430b7, **không có xung đột**. (Xác nhận bằng `git merge --no-commit` trong worktree tạm: "Automatic merge went well".)

#### Kết luận
**MERGE SAU KHI SỬA** (việc tối thiểu):
1. Đổi đường ra mặc định của `transformation/pipeline.py` sang một thư mục khác (vd. `data/preprocessing/features_duy/`) HOẶC nối nó vào `run.py` của P3/P4; không để hai đường cùng ghi `04_normalization/all.parquet`.
2. Chốt với nhóm (Thuận/người giữ SPEC-06): 5 hay 6 cấp bậc, Embedded hay UI/UX, tên tỉnh có "TP." hay không; ghi quyết định vào spec.
3. Sửa 3 lỗi parse đã tái hiện: "tối thiểu", "tỷ", "Không yêu cầu"/"Dưới một năm kinh nghiệm" (cộng thêm test).
4. Chuyển test sang `tests/unit/` (hoặc thêm vào `testpaths`) để `make test` chạy được.
5. Điền báo cáo nghiệm thu vào mô tả PR bằng số đo thật từ dữ liệu (kể cả khi chỉ có 937 dòng, phải ghi rõ).
Không cần chặn vì rủi ro dữ liệu/secret: không có.

#### Đề xuất cập nhật KNOWN_ISSUED.md (mục 3 Pre-processing; mã PRE-1..PRE-11 đang dùng, PRE-12 trở đi còn trống)
- **PRE-12.** Pipeline đặc trưng của Duy (`transformation/pipeline.py`) ghi trùng `data/preprocessing/04_normalization/all.parquet` với `normalization/run.py`; chưa nối vào 5 bước chính. Chọn: tách đường ra hoặc tích hợp.
- **PRE-13.** Lệch spec giữa cẩm nang Duy và SPEC-06/P4: 5 vs 6 cấp bậc, Embedded vs UI/UX, tên tỉnh "Hồ Chí Minh" vs "TP. Hồ Chí Minh". Cần quyết định thống nhất.
- **PRE-14.** `salary_parser.parse_salary`: không nhận "tối thiểu" làm cận dưới, không hỗ trợ "tỷ" (2 tỷ -> 2 triệu).
- **PRE-15.** `experience_parser`: "Không yêu cầu" và "Dưới một năm kinh nghiệm" -> unparsed; `parse_experience_range` và `parse_experience` trả max khác nhau cho "Không yêu cầu kinh nghiệm".
- **PRE-16.** `job_family_classifier`: Python/PHP Developer, UI/UX -> None; skill C+C++ -> Embedded; chưa có kiểm tay 50 tin (>= 90%).
- **PRE-17.** `location_normalizer`: tên đường "Điện Biên Phủ" -> Điện Biên / "Nhiều địa điểm"; nước ngoài không có cờ `ngoai_vn`.
- **PRE-18.** Test của P3/P4 mới nằm ngoài `testpaths` nên `make test` không chạy; chạy chung với `tests/` làm `tests/conftest.py:42` lỗi.
- **GEN-5.** Mẫu báo cáo nghiệm thu trong `docs/tasks/*.md` chưa điền; các số liệu (tỷ lệ lương, thỏa thuận, 50 JD) chưa có nguồn.

#### Không kiểm tra được
- Toàn bộ số liệu thật (tỷ lệ lương parse được, % thỏa thuận, phân phối lương, độ đúng nhóm nghề, precision kỹ năng trên 50 JD): không có `data/` cục bộ, nhánh không kèm báo cáo.
- Hành vi pipeline đầu-cuối (`prepare_silver.py`, `run_transformation.py`, `run_normalization.py`): chưa chạy vì thiếu parquet đầu vào; chỉ chạy từng hàm.
- Ruff trên "chỉ dòng đổi": tôi chỉ đếm theo file; không phân tách lỗi cũ/mới trong file đã có.
- Không đọc nội dung PR (nếu có) trên GitHub; lời khai nghiệm thu chỉ lấy từ `README_DUY.md` và commit.
- Tôi đã không kiểm chứng toàn bộ 888 dòng taxonomy từng alias; chỉ các ca nêu trên.

## Phụ lục Phát (feature/p5-encoding-matrices)

### Review nhánh feature/p5-encoding-matrices (Hồng Phát) - P5 Encoding & Matrices

#### Tóm tắt
Nhánh có 1 commit riêng của Phát (0e17b9c "Xử lý encoding", 12:44 09/11) cộng 3 commit của người khác (Duy P3-P4 9b33a05; Bill 80eadc1, f438090 - spec/task). Code encoding có thật và test sạch (72 test encoding pass), nhưng: (1) toàn bộ file dữ liệu đầu ra (golden, features, co-occurrence, dictionary, TF-IDF) KHÔNG nằm trong git nên không kiểm chứng được số liệu báo cáo; (2) ledger.csv mà runtime bắt buộc đọc bị .gitignore (*.csv) nên không có trong nhánh -> không tái lập được từ nhánh; (3) đẩy ~123k dòng artifact review/notebook/pickle/npz vào git, ngoài phạm vi "chỉ preprocessing/encoding/"; (4) lệch báo cáo nghiệm thu: số cột/dòng 5104 (không phải toàn bộ P4 5177), chưa dùng mẫu báo cáo trong task. Kết luận: MERGE SAU KHI SỬA.

#### Ahead/behind, merge-base
- `origin/sprint...origin/feature`: sprint hơn 2, nhánh hơn 4. Merge-base 0cfa1b0.
- Commit của nhánh: 0e17b9c hongphatde "Xử lý encoding" (165 file, +123.884/-506); f438090 BillTran update sspec; 80eadc1 BillTran spec for project and assign tasks; 9b33a05 duynkh9326-hub P3-P4.
- Sprint có 2 commit mà nhánh chưa có: c1555c0 "update sspec", 83f8432 "spec for project and assign tasks" (cùng nội dung với f438090/80eadc1 nhưng hash khác -> nhánh dựng trên bản commit khác; tổng 225 file/+134k theo `A...B` gồm cả phần của Bill và Duy).
- Lưu ý: so sánh dùng origin/sprint/pipeline-delivery (local HEAD bfaa076 "normalize r2" mới hơn; không đối chiếu với local).

#### Đã làm (bằng chứng)
Chỉ tính commit 0e17b9c:
- `preprocessing/encoding/` (36 file): execute.py (runner full-bundle), execution_features.py, execution_io.py, execution_tfidf.py, cohort.py, finalize_cohort.py, skills_taxonomy_230.py, tfidf_extractor.py, run_encoding.py (delegate), assets/frozen_vocabulary_v1.json (230 canonical, expected_task_width=230), jd_stopwords_v1.json. Nhiều script review/approval-package/notebook builder (không phải runtime).
- Test mới: tests/unit/test_encoding_{approval_package,candidate_lookup,cohort,execution,safety,scope_review}.py, test_vocabulary_comparison.py, sửa test_encoding_step.py.
- Đối chiếu tiêu chí task 05:
  - Multi-hot 230 cột: có frozen vocabulary 230 mục (file đọc được). Báo cáo 07_p5_execution_report.md khai 5104x230 uint8, sparsity 98,1472% (ngoài khoảng 95-98% của task; chênh nhẹ, có giải thích 82,9% job có >=1 kỹ năng) - KHÔNG kiểm chứng được vì data/ không có trong git.
  - Co-occurrence 230x230 int64, top5 SQL-REST API 819, SQL-Python 599... - lời khai, không kiểm chứng được (không có parquet). Test execution có kiểm đối xứng/đường chéo theo báo cáo (chưa đọc từng assert).
  - TF-IDF 5104x3000 (đúng 2000-3000): lời khai.
  - features.parquet / encoding_dictionary.json / skill_cooccurrence.parquet: đúng đường dẫn task (data/preprocessing/05_encoding/). Golden: data/curated/curated_flat_golden_jobs.parquet (5104x292) đúng tên hiện hành trong CLAUDE.md. Nhưng spec 10_architecture.md (dòng 42-44, 112) ghi `gold/gold_master_jobs.parquet`, `gold/features.parquet`, `gold/matrices/` -> không khớp cả task lẫn code (mâu thuẫn spec nội bộ, không phải lỗi riêng Phát).
  - Bước 4 (driver `python preprocessing/encoding/run_encoding.py`): không chạy được thuần; run_encoding chỉ delegate khi có đủ config (manifest, vocabulary, stopwords, ledger, decision-record, history root), thiếu thì fail. Khác lệnh đơn giản trong task. Không chạy thật (cần data, tránh ghi).
  - Bước 5 ruff: báo cáo ghi "Ruff pass"; thực tế `ruff check preprocessing/encoding/` trên nhánh cho 12 lỗi UP038 (isinstance tuple) tại analyze_p4_input_and_k.py:29, audit_p4_snapshot.py:61, candidate_lookup.py:47/76/81, execution_features.py:68, execution_io.py:55/62/65/70, review_snapshot.py:58, run.py:124. Lời khai "pass" sai với ruff của .venv (có thể khác cấu hình/phiên bản; không xác định được).
  - Báo cáo nghiệm thu: không dán theo mẫu task (thiếu mục Vấn đề/Nguyên nhân/Giải pháp theo đúng cấu trúc, thiếu "Không còn" cho tồn đọng); báo cáo tự nhận KHÔNG claim P5 complete (Python 3.12 UNVERIFIED). Thực tế .venv của repo là Python 3.12.14 và 72 test pass ở đây -> điểm "UNVERIFIED" có thể đóng được.
- Cohort: lọc 5177 P4 -> 5104 include (62 exclude, 11 quarantine) theo quyết định tay/agent; 5092 job "retained_unreviewed", nhãn không phải human gold. Đây là thay đổi phạm vi dữ liệu so với yêu cầu task (M x 230 trên toàn Normalization): cần Bill/Thuận xác nhận chấp nhận cohort lọc.

#### Tồn đọng
1. ledger.csv không có trong git (bị `.gitignore:35 *.csv`), trong khi cohort.py:135,210 và finalize_cohort.py:33 đọc nó -> clone sạch không chạy được execute; test cohort có thể dùng fixture riêng (6 test pass).
2. Output không commit/không push R2 (hợp lý), nhưng nghĩa là không ai ngoài máy Phát kiểm được số liệu; chưa thấy script/CI kiểm lại.
3. tests/test_golden_field_preservation.py (mới, 285 dòng) lỗi collection: `ModuleNotFoundError: preprocessing.normalization.target_schema_formatter` (module không tồn tại ở nhánh; báo cáo cũng thừa nhận). Đặt ở tests/ gốc, không thuộc phạm vi tests/unit.
4. 12 lỗi ruff UP038 (xem trên).
5. Sparsity 98,15% ngoài khoảng 95-98% trong task (nhẹ, cần Bill duyệt).
6. Cột "unmatched" skills: 17,1% job không có kỹ năng nào trong 230 (873 all-zero) - chấp nhận được nhưng nên ghi vào KNOWN_ISSUED.
7. Chưa kiểm nội dung thật của từng test (chỉ chạy pass), chưa kiểm số liệu EDA, chưa mở notebook.

#### Rủi ro
- File lớn/nhị phân vào git: reports/preprocessing/05_encoding/ có 95 file ~87.6k dòng; notebooks/eda_p5_encoding.html (9.5k dòng, ~1,2 MB), eda_p5_final_cohort.html (9k dòng); `cleanup_review_2026-11-08/p5_before_cleanup.pkl` (~2,3 MB, pickle - rủi ro thực thi mã khi load) và `approval_package_v2/skill_matrix_review.npz`; profiling.json 19k dòng, git_diff_before.patch 1,1k dòng, references_before.txt, reference_matches_all_surfaces.txt (~6k dòng). Trái quy tắc CLAUDE.md "reports/ chỉ chứa output pipeline mà monitoring đọc; không để báo cáo ad-hoc". Làm phình repo vĩnh viễn.
- Ngoài thư mục được giao (preprocessing/encoding/): preprocessing/common/r2_export.py (thêm skill_cooccurrence.parquet vào GOLD_KEYS -> đường ra R2 curated/preprocessing/..., chỉ mở rộng map; không chạy upload ở review), tests/*, docs/preprocessing/encoding/ (16 file), docs/issue_log.md (+8), notebooks/ (4 file + README), reports/preprocessing/05_encoding/ (95 file), docs/tasks/05_phat_encoding_and_matrices.md (sửa dòng 54; CONFLICT, xem dưới), docs/tasks/05_phat_encoding_implementation_contract.md (file mới).
- Các file ngoài của người khác nằm trong nhánh nhưng không phải của Phát: toàn bộ preprocessing/transformation|normalization|dictionaries (Duy), docs/spec/*, docs/tasks/*, docs/prompting/draft/*, docs/reports/*, AGENTS.md/agents.md, docker-compose.yml, scripts/build_course_reports.py, scripts/load_mart_from_parquet.py, scripts/sql/init_mart_schema.sql (phần Bill/Duy/khác; cần xác định nguồn trước khi merge để tránh ghi đè bản sprint).
- Không thấy secret/.env trong cây git (quét tên file .env/secret: không có; chưa grep nội dung toàn bộ).
- Không xóa file người khác trong commit của Phát (diff-filter=D trống ở A...B).
- Schema dùng chung: GOLD_KEYS (r2_export) mở rộng; schema golden/features do Phát định nghĩa nhưng chưa kiểm khớp với consumer (Mining/Phúc, Monitoring/Sơn, load_mart).
- Giám sát: spec 10 vs đường dẫn thực tế (gold/ vs data/curated + data/preprocessing/05_encoding) cần thống nhất trước khi Mining đọc.

#### Kết quả test (worktree detach nhánh, .venv Python 3.12.14, mạng chặn)
- `pytest tests/unit/test_encoding_*.py tests/unit/test_vocabulary_comparison.py`: 72 passed, 0 fail, 0 skip (1,49s).
- `pytest tests/unit` toàn bộ: 175 passed, 1 skipped (2,54s).
- `pytest tests/test_golden_field_preservation.py`: 1 error collection (target_schema_formatter không tồn tại).
- `ruff check preprocessing/encoding/`: 12 lỗi UP038.
- Không chạy: tests/integration, contract, make test toàn repo (báo cáo nói có 6 lỗi collection sẵn có, không tự xác minh); không chạy execute.py (cần data + ledger.csv).
- Worktree đã gỡ (--force).

#### Merge thử (`git merge-tree --write-tree origin/sprint/pipeline-delivery origin/feature/p5-encoding-matrices`)
- Xung đột duy nhất: `docs/tasks/05_phat_encoding_and_matrices.md` (add/add). Khác biệt thực sự: dòng 54 - bản nhánh làm mất đường dẫn (``  rỗng thay cho `data/preprocessing/05_encoding/features.parquet`); nên giữ bản sprint.
- Còn lại tự gộp sạch (trên cơ sở sprint origin, không phải local HEAD).

#### Kết luận
**MERGE SAU KHI SỬA**:
1. Gỡ khỏi git: p5_before_cleanup.pkl, skill_matrix_review.npz, notebooks HTML/ipynb lớn, git_diff_before.patch, reference_matches_all_surfaces.txt, profiling.json và các thư mục review lịch sử (đưa ra ngoài hoặc zip/R2 sau khi được duyệt); chỉ giữ evidence tối thiểu pipeline/monitoring đọc.
2. Đưa ledger.csv vào git (ép `git add -f` hoặc đổi sang .json/negate .gitignore) hoặc ghi rõ cách lấy; để clone sạch chạy được.
3. Giải quyết xung đột task doc (giữ bản sprint, dòng 54).
4. Sửa/loại tests/test_golden_field_preservation.py (import hỏng) hoặc chuyển thành tests/unit có skip.
5. Sửa 12 lỗi ruff UP038 hoặc bỏ lời khai "Ruff pass".
6. Rebase lên sprint hiện tại (tránh commit Bill trùng hash khác) và tách phần của Duy/Bill khỏi PR của Phát.
7. Nộp báo cáo nghiệm thu theo mẫu task; Bill xác nhận chấp nhận cohort 5104 và sparsity 98,15%; chạy lại execute trên máy khác (hoặc Thuận) để xác nhận số liệu.
8. Bill/Phát chốt đường dẫn gold: spec 10 (gold/...) vs data/curated + data/preprocessing/05_encoding.

#### Đề xuất cập nhật KNOWN_ISSUED.md
- PRE-P5-01: ledger.csv bị .gitignore, P5 không tái lập từ clone sạch.
- PRE-P5-02: reports/preprocessing/05_encoding chứa file lớn/pickle/npz/notebook HTML trong git (cần dọn, quy tắc reports/).
- PRE-P5-03: tests/test_golden_field_preservation.py import preprocessing.normalization.target_schema_formatter không tồn tại.
- PRE-P5-04: cohort P5 5104/5177 job, 5092 retained_unreviewed, 11 quarantine; chưa có upstream filter; job_family chưa sửa.
- PRE-P5-05: 17,1% job không có kỹ năng nào trong 230 (873 all-zero); sparsity 98,15% ngoài 95-98%.
- PRE-P5-06: 12 lỗi ruff UP038 trong preprocessing/encoding.
- GEN-xx: spec 10_architecture (gold/...) lệch đường dẫn thực tế data/curated + data/preprocessing/05_encoding.
- GEN-xx: GOLD_KEYS trong r2_export đã thêm skill_cooccurrence (đường ra R2 curated/preprocessing/), cần duyệt dry-run trước khi upload.

#### Không kiểm tra được
Số liệu data (5104x292, 98,15%, top5 pair, kích thước 14,8MB, 0,109s) do không có data trong git; đọc nội dung từng test/EDA; tests/integration & contract; grep secret trong nội dung; tác động lên Mining/Monitoring/load_mart; chạy execute.py.

## Phụ lục Phúc (feature/mining-algorithms)

### Review nhánh feature/mining-algorithms (Phúc) - thư mục mining/

Commit duy nhất: `920cec1 Phạm Nguyễn Minh Phúc, 08/11/2026: "Xong thuật toán, đợi dữ liệu thật"` (ahead 1 so với sprint). 19 file, +2643 dòng, toàn bộ là file mới (A) trừ 1 file docs (M).

#### Tóm tắt
Code đủ 4 thuật toán (FP-Growth phân tầng, K-Means + PCA 3D + HDBSCAN/GLOSH, Random Forest + TreeSHAP, Isolation Forest) cùng lớp hợp đồng dữ liệu, sanity S-01..S-06 và 7 file test. Mọi số liệu trong báo cáo nghiệm thu đến từ dữ liệu GIẢ do tác giả tự sinh (`mining/synthetic.py`). Cột "Dữ liệu thật" đều ghi "[chờ dữ liệu thật]". Vì vậy chưa có tiêu chí nghiệm thu nào được chứng minh trên dữ liệu thật. Code sẵn sàng, kết quả thì chưa.

#### Đã làm (bằng chứng)
- File ngoài thư mục được giao (`mining/`): chỉ `tests/unit/test_mining_*.py` (7 file, hợp lý) và `docs/tasks/06_phuc_data_mining_algorithms.md` (điền báo cáo nghiệm thu, hợp lý). Không đụng requirements, không đụng collection/monitoring.
- Không có file dữ liệu/lớn trong git. `mining/artifacts/.gitignore` chặn mọi artifact (`*`, trừ `.gitignore`). File lớn nhất trong repo là notebook cũ trên sprint, không phải của nhánh này. Quét `AKIA|secret|password|api_key` trong `mining/`: không có kết quả.
- FP-Growth: `mining/association.py` (mlxtend `fpgrowth`/`association_rules`). Macro `min_sup=0.05`, micro `0.02` cho từng job_family có >= 100 tin, lọc Conf >= 0.60 và Lift > 1.20 (theo báo cáo mục 3; ngưỡng ở `mining/config.py`). Có conviction (vô hạn ghi null) và cosine. Đủ cột `antecedents, consequents, support, confidence, lift, job_family_scope`. Khớp spec 07 §5.3.
- K-Means + PCA + Silhouette: `mining/clustering.py`. Quét k 4..14, chọn Silhouette cao nhất trong số k >= 8 (đáp ứng "8 cụm" của spec 08), có Davies-Bouldin, ARI/NMI. Xuất `pca_x, pca_y, pca_z, cluster_id, cluster_name, is_outlier, glosh_outlier_score`. HDBSCAN: dùng thư viện `hdbscan` nếu có (GLOSH thật), nếu không rơi về `sklearn.HDBSCAN` với `1 - probabilities_` (xấp xỉ, `clustering.py:124-136`, có ghi vào metrics).
- Random Forest + SHAP: `mining/salary_model.py`. Subset A (bỏ Thỏa thuận, `salary_suspect`, ngoài 1-500 triệu, lệch > 3 lần trung vị cùng cấp), `log1p(salary_avg)`, holdout 20%, 5-fold CV (GroupKFold nếu có dup_group_id), có baseline, `assert_no_leakage`. TreeSHAP lấy trung bình phi trên các tin CÓ kỹ năng đó, `is_reliable` khi sample >= 30, marginal = baseline*(e^phi - 1). Đúng công thức spec. Lưu `trained_salary_rf_model.joblib`.
- Anomaly: `mining/anomaly.py` (Isolation Forest + GLOSH, có reason_code, detected_by). Đủ cột `job_anomalies`.
- Đầu vào: `mining/config.py:17-20` đọc `data/curated/curated_flat_golden_jobs.parquet` (thiếu thì fallback `data/preprocessing/04_normalization/all.parquet`) và `data/preprocessing/05_encoding/features.parquet`. Khớp đúng task 06; KHÔNG đọc `gold/features.parquet` hay R2 như sơ đồ trong spec 10 (spec 10 là kiến trúc mục tiêu; đây là chỗ lệch đã có sẵn giữa spec 10 và task 06, không phải lỗi riêng của Phúc). Khi thiếu `features.parquet`, mining tự dựng ma trận kỹ năng từ `skills_extracted` (theo báo cáo mục 5). `COLUMN_ALIASES` + `MiningContractError` để dừng nếu sai hợp đồng.
- Số liệu báo cáo (giả, 1.500 tin): 798 luật (42 macro), Silhouette 0,470 (k=14), DB 0,937, R2 0,912 (baseline 0,692), MAE 3,77 triệu, Std(R2) 0,0084, sanity 6/6, bắt 18/18 tin bất thường cài sẵn. Tác giả ghi rõ đây là dữ liệu giả và "không dùng để báo cáo". Tôi KHÔNG chạy lại pipeline để xác minh các con số này (thiếu mlxtend/shap; không có dữ liệu thật; chạy synthetic cũng cần mlxtend).

#### Tồn đọng
1. Chưa chạy trên dữ liệu thật: toàn bộ cột "Dữ liệu thật" trống; "Top 3 luật theo Lift" và "Top 5 kỹ năng tăng lương" cũng "[chờ dữ liệu thật]". Các tiêu chí nghiệm thu (>= 30 luật, Silhouette >= 0,28, R2 >= 0,60, MAE <= 4,5 triệu, S-01..S-06) CHƯA đạt/chứng minh.
2. Checklist 6 bước trong task file vẫn để `[ ]` (chưa tick); chưa xác nhận 4 parquet + joblib sinh trên dữ liệu thật; chưa có `mining_metrics.json` thật.
3. Mục 1 task ghi k 6-12, checklist ghi 4-14, spec 07 ghi 3-15: code quét 4-14 (Phúc đã tự nêu). Cần lead chốt.
4. Báo cáo nghiệm thu nêu "61 pass" và "ruff sạch" nhưng môi trường tôi thiếu thư viện nên không xác nhận được (xem Kết quả test).
5. Bước đánh giá Trục 2 (đối chuẩn TopDev/ITviec, S-04/S-06 trên dữ liệu thật) và `reports/skill_gap_report.md` (15% ma trận nghiệm thu) không thuộc nhánh này.
6. Phúc tự nêu cần lead: `scripts/load_mart_from_parquet.py` làm cột list (antecedents/consequents) thành chuỗi; chưa có bảng mart cho `skill_salary_shap_values`.

#### Rủi ro
- Phụ thuộc chưa có trong requirements: `mlxtend`, `shap` (bắt buộc import ở module level: `association.py:19`; nên `import mining.run_mining_pipeline` lỗi ngay khi thiếu), `hdbscan` (tùy chọn nhưng đổi ngữ nghĩa GLOSH). `requirements.txt` hiện chỉ có `scikit-learn`, `scipy`, `pyarrow`. Nhánh không sửa requirements, nên merge xong `make test` sẽ lỗi collect 3 file test trên môi trường hiện tại (venv chính cũng không có các thư viện này).
- Kết quả giả: rủi ro nếu ai lấy số 0,912/0,470 từ báo cáo để viết đồ án. Cần ghi rõ trong KNOWN_ISSUED.md và gắn nhãn trong báo cáo. Giảm nhẹ: output synthetic ghi vào `artifacts/_synthetic/` và metrics có `"synthetic": true`.
- Dữ liệu giả cài sẵn đáp án rồi tìm lại: R2 0,912 và "tìm lại đủ 3 luật" chỉ chứng minh code đúng, không chứng minh chất lượng mô hình trên thị trường thật.
- Test phụ thuộc môi trường: `test_outlier_ratio_follows_quantile` fail khi không có `hdbscan` (xem dưới), tức test gắn với thư viện tùy chọn.
- Không phát hiện secret hay dữ liệu lớn trong git.

#### Kết quả test
Môi trường: venv chính `.venv`, mạng chặn, không cài thêm. Thiếu: `mlxtend`, `shap`, `hdbscan`. Có: scikit-learn, joblib.
- Chạy cả 7 file: 3 file lỗi collect vì `ModuleNotFoundError: mlxtend` (`test_mining_association.py`, `test_mining_pipeline.py`, `test_mining_sanity.py`) = thiếu môi trường, không phải lỗi code; không chạy được.
- Chạy 4 file còn lại (`anomaly`, `clustering`, `data_io`, `salary_model`): **43 pass, 1 fail, 2 error**.
  - FAIL `test_mining_clustering.py::test_outlier_ratio_follows_quantile`: tỉ lệ outlier 0,0767 so với mong đợi 0,03 ± 0,01. Nguyên nhân khả dĩ là nhánh fallback `sklearn.HDBSCAN` (không có `hdbscan`) cho điểm xấp xỉ; tôi chưa kiểm chứng bằng cách chạy với `hdbscan` nên coi là chưa xác định, nhiều khả năng do môi trường.
  - ERROR `test_mining_salary_model.py::test_model_beats_baseline_and_reports_targets` và `::test_shap_recovers_planted_premiums`: `ModuleNotFoundError: shap` (thiếu môi trường).
- Chưa chạy: số test tổng của tác giả "61 pass". Phần đã chạy được = 46 test trong 4 file; 3 file còn lại không chạy. Không chạy ruff (không yêu cầu; không xác nhận được "ruff sạch").
- Worktree tạm đã gỡ; repo chính không đổi.

#### Merge thử
`git merge-tree --write-tree origin/sprint/pipeline-delivery origin/feature/mining-algorithms`: không xung đột (trả tree 8a8228b4ee143f0cc765f8153d621827e77037bd, không có dòng CONFLICT). Mọi file là thêm mới; file duy nhất sửa là `docs/tasks/06_phuc_data_mining_algorithms.md` (sprint chưa đổi file này sau điểm tách nhánh).

#### Kết luận
**MERGE SAU KHI SỬA**:
1. Thêm `mlxtend`, `shap` (và nên cân nhắc `hdbscan`, `joblib` nếu chưa có) vào `requirements.txt`/`requirements-dev.txt`, hoặc import lazy + `pytest.importorskip` để `make test` không vỡ; sau đó chạy lại đủ 7 file test trong môi trường đủ thư viện và xác nhận 61 pass.
2. Ghi rõ trong báo cáo nghiệm thu là các số liệu hiện chỉ là dữ liệu giả, và mục nghiệm thu chưa đạt cho tới khi chạy dữ liệu thật; không đánh dấu hoàn thành task 06.
3. Sửa hoặc đánh dấu `test_outlier_ratio_follows_quantile` để không phụ thuộc có `hdbscan`.
Nếu lead chấp nhận "code xong, nghiệm thu dữ liệu thật để sau" thì phần code an toàn để merge sau khi xử lý mục 1, vì chỉ thêm file mới.

#### Đề xuất cập nhật KNOWN_ISSUED.md
- **MINE-01**: Mining chưa chạy trên dữ liệu thật; mọi số liệu trong báo cáo task 06 là dữ liệu giả. Cần chạy `python mining/run_mining_pipeline.py` khi có `features.parquet` + golden và điền lại bảng nghiệm thu (>= 30 luật, Silhouette >= 0,28, R2 >= 0,60, MAE <= 4,5 triệu, S-01..S-06).
- **MINE-02**: `requirements.txt` thiếu `mlxtend`, `shap`, `hdbscan`; `make test` lỗi collect 3 file test mining trên môi trường hiện tại.
- **MINE-03**: `test_outlier_ratio_follows_quantile` fail khi thiếu `hdbscan` (fallback sklearn xấp xỉ GLOSH).
- **MINE-04**: Khoảng k chưa thống nhất (task: 6-12 / checklist: 4-14 / spec 07: 3-15); code đang dùng 4-14.
- **MINE-05**: `scripts/load_mart_from_parquet.py` biến cột list (antecedents, consequents) thành chuỗi; chưa có bảng mart `skill_salary_shap_values`.
- **GEN-01**: Spec 10 mô tả mining đọc `gold/features.parquet` trên R2, còn task 06/code đọc `data/curated/...` và `data/preprocessing/05_encoding/features.parquet` (local). Cần thống nhất một hợp đồng đầu vào.
- **MINE-06**: SHAP không thể hiện quan hệ nhân quả (kỹ năng đi kèm kỹ năng lương cao cũng có phi dương); cần ghi chú trong báo cáo đồ án. Thang cấp bậc `seniority_level` 0-4 gộp Thực tập và Mới tốt nghiệp.

#### Không kiểm tra được
Chạy lại pipeline (synthetic hoặc thật) và các con số báo cáo; 3 file test cần mlxtend; test cần shap; hành vi với `hdbscan` thật; ruff; có `features.parquet`/golden thật cùng schema hay không (không đụng dữ liệu/R2).

## Phụ lục Sơn (feature/monitoring-observatory)

### Review nhánh feature/monitoring-observatory (Sơn)

#### Tóm tắt
8 commit (sonbnUTH, 08/11), +1334/-900, 25 file. Tách CrawlingPage.tsx (913 -> 25 dòng), thêm API /api/v1/insights (4 endpoint, đọc PostgreSQL Mart), trang /insights (heatmap lương, luật FP-Growth, scatter 2D/3D), 6 test mới. Không đụng R2, crawler, preprocessing.

#### Đã làm (bằng chứng)
- Tách component: monitoring/frontend/src/components/crawling/ có CrawlTriggerCard, LedgerStatusTable, LakehouseHealthCard, RealtimeLogStream + hook useCrawlingState + 5 file phụ. CrawlingPage.tsx 25 dòng (<200).
- API: monitoring/backend/app/api/v1/endpoints/insights.py, services/insights_service.py (SQL tham số hóa, readonly, connect_timeout 3s, statement_timeout 5s; rỗng -> EMPTY/NO_DATA/data null; lỗi DB -> 503 MART_UNAVAILABLE không lộ DSN). Đăng ký ở router.py.
- Lương chia 1.000.000 -> triệu VNĐ, loại thỏa thuận và ngoài 1–500 triệu.
- Frontend MarketInsightsPage.tsx: bộ lọc tỉnh/cấp bậc/nhóm nghề, 12 job family chuẩn, bảng luật có lọc support/confidence/lift/antecedent/scope (Macro/Micro); CareerClusterScatterCard.tsx 2D/3D (SVG, kéo xoay, zoom), pca_z null thì khóa 3D, không bịa Z.
- Không có Math.random hay `any` trong diff frontend (grep). Không có node_modules/dist/file lớn mới trong git.

#### Tồn đọng
- Bước 4 checklist (./start_monitoring.sh --check, duyệt trình duyệt) chưa tick; báo cáo của Sơn tự ghi chưa chạy trên Linux/Py3.12.
- Chưa kiểm chứng heatmap/rules/scatter với dữ liệu thật (Mart rỗng; chờ artifacts Phúc). Tôi cũng không kiểm tra được vì không chạm DB.
- Mẫu báo cáo nghiệm thu mục 5 chưa điền (chỉ có mục 6 mô tả); ruff toàn backend còn 355 findings cũ (không phải lỗi mới; 2 file mới qua ruff: đã xác nhận).
- Heatmap ở frontend không nhắc "IQR" ngoài tooltip/details (nhấn vào ô mới thấy P25–P75); heatmap là bảng màu, chấp nhận được.
- Endpoint /insights chưa có test với PostgreSQL thật (chỉ mock `query`), SQL chưa được test thực thi trong CI.
- Test mới dùng unittest chứ không dùng marker pytest; vẫn chạy được dưới pytest.
- Chưa kiểm 390px/1440px; chỉ tin báo cáo của Sơn (Playwright). Không kiểm tra được.

#### Rủi ro
- Ngoài thư mục giao: KNOWN_ISSUED.md (xóa mục VIZ-5 - hợp lý vì đã xử lý, nhưng file thuộc lead), docker-compose.yml (POSTGRES_PUBLISHED_PORT, mặc định vẫn 5432: an toàn, được phép theo Q&A), docs/issue_log.md (L-29), docs/tasks/07, monitoring/CLAUDE.md, tests/integration/test_monitor_insights.py (được phép). Không xóa file người khác.
- API /insights không auth: thống nhất Zero-Auth theo yêu cầu; dữ liệu chỉ đọc; filter dùng bound parameter (test có). Bundle JS 778 kB (cảnh báo, không lỗi).
- Mật khẩu POSTGRES_PASSWORD mặc định "" trong code (đọc từ .env); không có secret trong diff.
- R2/GEN-4: nhánh không sửa r2_client.py hay source_report_service.py nên không động đến mapping prefix R2; insights chỉ dùng PostgreSQL, không dùng đường dẫn R2. GEN-4 không bị ảnh hưởng.
- Báo cáo ghi dữ liệu Mart cổng 15432 qua .env local (không commit): đồng đội dùng mặc định 5432.
- Số bịa: không phát hiện (không random, không hardcode số liệu; chỉ các nhóm nghề chuẩn hardcode làm nhãn hàng).

#### Kết quả test (worktree detach, venv repo chính, Python 3.12)
- `-k "monitor or api or mining or insight"` (tests/integration + tests/unit): 40 passed, 1 skipped.
- Toàn bộ `tests`: 229 passed, 6 skipped, 0 fail (5s).
- `npm run build` (node_modules symlink từ repo chính, không cài): thành công, chỉ cảnh báo chunk >500 kB; dist không commit.
- `ruff check` 2 file backend mới: pass.
- Không chạy: start_monitoring.sh, Playwright/390px, truy vấn PostgreSQL thật.

#### Merge thử
`git merge-tree --write-tree` với origin/sprint/pipeline-delivery: sạch, không xung đột (tree 8276beb). Working tree sprint hiện sạch (không có thay đổi chưa commit ở monitoring/), nhánh không sửa r2_client.py/source_report_service.py nên không xung đột với mapping prefix R2.

#### Kết luận
MERGE ĐƯỢC. Khuyến nghị (không chặn): Sơn điền mẫu báo cáo mục 5 vào PR, chạy ./start_monitoring.sh --check và nạp thử Mart bằng parquet thật trước/sau merge.

#### Đề xuất cập nhật KNOWN_ISSUED.md
- Giữ việc xóa VIZ-5 (đã xong).
- VIZ-3: cập nhật thành "Market Insights đã đọc Mart; các trang báo cáo cũ vẫn dùng reports/ ngày 25/10".
- VIZ-6 (mới): Chưa kiểm chứng /insights với dữ liệu Mart thật (heatmap/rules/scatter 3D); chờ artifacts của Phúc.
- VIZ-7 (mới): Chưa chạy ./start_monitoring.sh --check và kiểm 390px trên Linux/Py3.12; bundle JS 778 kB cần code-split.
- GEN-4: không đổi.
