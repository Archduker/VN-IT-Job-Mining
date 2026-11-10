# Báo cáo thực thi P5 — cohort_v1, ngày 09/11/2026

> **Ghi chú 10/11/2026:** JEV, OpenJev và Qwen đã bỏ; cột xác suất `*_prob` không còn. Cờ thay thế: `it_rule_level`, `seniority_can_kiem`, `job_family_can_kiem` (xem `docs/spec/preprocessing/spec/P5_encoding.md`).

Đã áp quyết định của Phát, chạy lại đầy đủ P5 và EDA trên **5.104 job include**. Bộ canonical đã được thay sau validation; bản 5.177 job được lưu lịch sử có checksum. Không còn chờ quyết định cũ về 36 job AutoCAD.

**Chưa tự xác nhận P5 complete:** Python 3.12 còn UNVERIFIED theo yêu cầu môi trường của SPEC. Sáu lỗi collection của toàn repo vẫn là giới hạn sẵn có ngoài P5, không phải regression mới. Xem [Contract hiện hành](06_p5_execution_contract.md) và manifest.acceptance_details.

Run ID: `p5_2026-11-09_cohort_v1`. Evidence/logs: `reports/preprocessing/05_encoding/p5_2026-11-09_cohort_v1/`.

## 1. Cohort đã chốt theo policy

**5.177 P4 = 5.104 include + 62 exclude + 11 quarantine.** Mỗi ID xuất hiện đúng một lần; ba tập rời nhau. Output chỉ gồm include, theo thứ tự P4.

- Xác minh và áp đúng 27 exclude/8 retain Phát duyệt. Fingerprint CSV: `1ebb40b8f66daa58c38e34bd3a1d66d6a82fb6beb8e577277ee5e3fc39bd3b08`; queue: `8a848bf1f4a2dbf0bf3b5605485127057a52c037fa11d80901eddf2ea961045e`. Annotations cũng được kiểm hash/nội dung.
- Giải quyết 19 unresolved cũ: **16 exclude, 3 quarantine**.
- Đọc đủ nội dung có sẵn của 31 P1 còn lại: **4 include, 19 exclude, 8 quarantine**. Mỗi assessment có nhiệm vụ, field/quote, reason, family assessment và policy reference; không mở rộng sang 410 P2.
- Tổng cộng **85 ID đã review**: 12 include-reviewed, 62 exclude và 11 quarantine. Đây là Agent áp policy hoặc quyết định được Phát duyệt, **không phải human gold labels**.
- Trong include có **5.092 retained_unreviewed**: 410 P2 và 4.682 job ngoài queue (`not_flagged_by_targeted_rules`). Không gọi toàn cohort là verified IT hoặc dataset sạch.
- Quarantine không được đưa vào Mining chính, nhưng vẫn có trong snapshot/ledger và không bị ghi thành confirmed non-IT. Các ranh giới mới như BMS/DCIM, ELV vừa mạng vừa thi công, hardware/module QA, CFD, mixed AI–PLC và technical sales được quarantine thay vì tự mở policy.

| Source | P4 | Include | Exclude | Quarantine |
|---|---:|---:|---:|---:|
| TopCV | 1561 | 1542 | 19 | 0 |
| TopDev | 227 | 220 | 6 | 1 |
| VietnamWorks | 900 | 861 | 31 | 8 |
| JobsGO | 683 | 681 | 2 | 0 |
| Glints | 271 | 269 | 2 | 0 |
| CareerViet | 448 | 446 | 2 | 0 |
| ITviec | 905 | 905 | 0 | 0 |
| Vieclam24h | 182 | 180 | 0 | 2 |

File để kiểm tra: [ledger](../../../preprocessing/encoding/assets/cohort_v1/ledger.csv), [version/hash](../../../preprocessing/encoding/assets/cohort_v1/ledger.meta.json), [decision record](../../../preprocessing/encoding/assets/cohort_v1/decision_record.json). Review bổ sung nằm trong p1_assessments.csv, p1_full_available_texts.md, p1_full_text_review_log.json và resolved_previous19.csv của run.

Không sửa job_family. Nghi vấn và đề xuất nhãn vẫn ở sidecars; nhãn nguồn không phải ground truth.

## 2. Runtime assets và bản lịch sử

Runtime chỉ đọc đường dẫn trong repository:

- `preprocessing/encoding/assets/frozen_vocabulary_v1.json`
- `preprocessing/encoding/assets/jd_stopwords_v1.json`
- `preprocessing/encoding/assets/cohort_v1/{ledger.csv,ledger.meta.json,decision_record.json,authorization_agent07.md}`

Không phụ thuộc file Downloads. Frozen vocabulary giữ nguyên bytes, 230 canonical, column names và order; SHA `583e9ba0c3662eb8c66d62a47fc6994d58f2d4b7e685b08dc0bf7f0c8e786602`. Counts 5.177 trong vocabulary là reference; observed counts mới lưu riêng.

Ledger SHA: `62b575a7f9a8379c053724d1636acee55587f770a8f05d52e0b0895244f333d7`. Decision-record SHA: `8857aae3a16c93c77aab2fc7fff5ec6cf2fd0f2c98a772fb1519d5b43c529d66`. Snapshot manifest vẫn có SHA `dd93db5c08b533725bd086315325c70ed37a8027b7149fc8327e5a6d3ca34ea4`.

Một [historical bundle 5.177](../../../data/preprocessing/05_encoding_history/p5_2026-11-09_frozen_v2/history_manifest.json) được lưu **trước** sửa/replace, gồm canonical bundle, Contract/report và source/tests liên quan. history_manifest ánh xạ original→archived paths để kiểm checksum cũ. Không tạo thêm nhiều bản dataset trùng; snapshot, gói v1/v2, scope review và các quyết định cũ giữ nguyên.

## 3. Artifact bàn giao

| Canonical path | Status | Kết quả |
|---|---|---|
| [Golden](../../../data/curated/curated_flat_golden_jobs.parquet) | **REPLACED+VALID** | 5104×292: 62 thuộc tính P4 + 230 skills |
| [Features](../../../data/preprocessing/05_encoding/features.parquet) | **REPLACED+VALID** | 5104×314; X là 5104×230 uint8 |
| [Co-occurrence](../../../data/preprocessing/05_encoding/skill_cooccurrence.parquet) | **REPLACED+VALID** | 230×230 int64, có labelled index/columns |
| [Dictionary](../../../data/preprocessing/05_encoding/encoding_dictionary.json) | **REPLACED+VALID** | Mapping, cohort counts, top10, audit/predictor selectors |

TF-IDF CSR float32 **5104×3000**, rows/terms/IDF/config, unmatched và quality cũng REPLACED+VALID. Validation/manifest ghi lại cho cohort. delivery.json và inventory_before.json liệt kê đầy đủ.

Lọc ledger **trước mọi fit/aggregate**. Chỉ tái dùng snapshot, frozen vocabulary, stopwords và evidence/decisions phù hợp; không lấy aggregate hay TF-IDF của 5.177 làm kết quả mới. Top10 location được freeze lại theo cohort.

Bộ mới được stage, validate, bàn giao rồi kiểm lại. Old success manifest được gỡ trước khi thay file; manifest mới chỉ ghi sau kiểm canonical. Golden giữ schema/values/nested/null của đúng P4 included IDs. Không có excluded/quarantined ID trong features, Golden hoặc TF-IDF rows.

## 4. Entry point và lệnh chạy

Chỉ **execute.py** là implementation full-bundle. run_encoding.py delegate khi có config đầy đủ; `--apply`/`--source` legacy fail trước ghi. run.py:run cũng chỉ delegate khi đủ manifest, vocabulary, stopwords, ledger, decision, output, evidence và history. Driver năm bước thiếu config sẽ fail rõ ở P5, không ghi prototype; không sửa shared driver/P4.

Mã mới: cohort_assessments.py, cohort.py, build_cohort_notebook.py, finalize_cohort.py và runtime assets. Đã sửa P5 execute/run/run_encoding/execution_features và tests liên quan; source/test trước sửa có trong lịch sử. Không sửa P3/P4, shared dictionary, Mining, upstream filter hoặc R2 exporter; không cloud/stash/commit/push.

Lệnh đã chạy từ repo root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m preprocessing.encoding.execute \
  --input-manifest reports/preprocessing/05_encoding/snapshot_audit_2026-11-08/manifest.json \
  --vocabulary preprocessing/encoding/assets/frozen_vocabulary_v1.json \
  --stopwords preprocessing/encoding/assets/jd_stopwords_v1.json \
  --cohort-ledger preprocessing/encoding/assets/cohort_v1/ledger.csv \
  --decision-record preprocessing/encoding/assets/cohort_v1/decision_record.json \
  --output-root data \
  --evidence-root reports/preprocessing/05_encoding/p5_2026-11-09_cohort_v1 \
  --history-root data/preprocessing/05_encoding_history/p5_2026-11-09_frozen_v2 --publish
```

Dry-run cùng config có `--dry-run` trả 5104 rows và không ghi dataset/manifest. Completed evidence_root không được ghi đè. Run mới cần evidence ID mới và bản lịch sử khớp bộ đang thay; không giả dùng lịch sử 5.177 làm backup một cohort khác.

## 5. Kiểm chứng và EDA

**68 tests liên quan pass, Ruff pass.** Đã kiểm ledger partition/retained IDs, IDs/order của output, từng bit X, C int64 và independent job-ID intersections, Golden lossless, TF-IDF reconstruction/norms, missing/anomalies và logical reproducibility. Audit/quality/target-derived salary columns tách khỏi recommended predictors.

Môi trường: Python 3.14.4, NumPy 2.5.4, Pandas 3.1.0, Arrow 26.0.0, SciPy 1.18.1, sklearn 1.9.1. **Python 3.12 UNVERIFIED**: không tìm thấy runtime riêng trong các môi trường/paths đã kiểm, không thay Python hệ thống hay venv chính. Full `make test` còn 6 collection errors như trước: 5 integration imports thiếu sqlalchemy và test Golden cũ import target_schema_formatter không tồn tại. Không claim whole-repo pass.

[Notebook mới](../../../notebooks/eda_p5_final_cohort.ipynb) và [HTML đồng bộ](../../../notebooks/eda_p5_final_cohort.html) đã chạy bằng kernel mới: **6 code cells, 0 errors, 2 plots**. Kernel dùng đúng phiên bản NumPy/Pandas của artifact runtime. Lần đầu bị kẹt startup trong sandbox, đã dừng riêng tiến trình và chạy lại với loopback cục bộ; không cloud. EDA cũ giữ làm lịch sử. Không thêm phân tích K/ML hoặc suy rộng toàn thị trường.

| Metric | Historical 5177 | Include 5104 |
|---|---:|---:|
| Covered jobs | 4277/5177 = 82,6154% | 4231/5104 = 82,8956% |
| Canonical pairs | 21845 | 21750 |
| Source-value pairs | 33136 | 32793 |
| Matched source pairs | 21978 | 21882 |
| All-zero jobs | 900 | 873 |
| Empty skills | 412 | 407 |
| Unmatched-only jobs | 488 | 466 |
| Sparsity | 98,1654% | 98,1472% |
| Zero columns | 0 | 0 |
| Frequency <20 | 137 | 138 |

AutoCAD **36→3**, đều là ba ID mixed web UI được Phát duyệt giữ. Không bỏ cột. Hard/soft vẫn 214/16; sáu nhóm 22/17/5/21/55/91 và 19 group=null giữ nguyên metadata. Còn 8 deadline inverse và 1 experience-range inverse, giữ source và gắn audit flags.

Runner đo **15,225 giây**, gồm validation/repro/warm-read stage, không gồm tests/freeze/EDA/report. Golden **14,830246 MB**, features 0,331995 MB, C 0,181936 MB, TF-IDF NPZ 4,653756 MB. Pandas median của 5 warm reads: Golden **0,109395s**, features 0,025232s, C 0,016035s; đạt <25MB/<0.3s trong môi trường này, không claim cold cache hay mọi máy.

Top5 cặp, bỏ diagonal và đối xứng trùng: SQL–REST API 819, SQL–Python 599, SQL–NoSQL 545, REST API–Git 533, SQL–Git 507. Metrics/performance/logs đầy đủ ở run folder.

## 6. Handoff và giới hạn

Đọc manifest và ledger hash trước; dùng dictionary.skill_columns làm X. Đọc C bằng Pandas để giữ index; ghép sparse TF-IDF bằng tfidf_rows.job_id_global. Golden chỉ là P4 included +230. Job_family giữ nguồn, nghi vấn ở sidecars. Supervised RF/SHAP phải loại target/audit và fit preprocessing train-only.

Policy cohort đã áp xong. **5.092 job vẫn chưa được xác nhận IT**, 11 quarantine không phải confirmed non-IT; loại 73 ID khỏi Mining cohort không có nghĩa đã sửa upstream filter. Upstream producer lineage chưa xác minh, family chưa sửa, assessments không phải human gold.

Phần triển khai/cohort/artifacts/EDA đã bàn giao. Không tự ghi P5 complete khi Python 3.12 còn UNVERIFIED hoặc chưa có ngoại lệ nghiệm thu phù hợp. Sáu lỗi toàn repo là giới hạn ngoài P5 được báo công khai. final_integrity.json và manifest.acceptance_details phân biệt technical PASS với acceptance.

<a id="p5-refactor"></a>

## 7. Refactor cấu trúc và kiểm chứng — 09/11/2026

Đợt refactor dùng **Python dự án 3.14.4** theo yêu cầu Phát. Run vẫn là `p5_2026-11-09_cohort_v1`; cả 10 artifact dữ liệu và validation report canonical được **REUSED, checksum không đổi**. Không thay cohort, vocabulary/order, logic nghiệp vụ hoặc trạng thái nghiệm thu. Bắt đầu tại [handoff P5](05_p5_handoff_2026-11-08.md), nơi có cây thư mục và lệnh kiểm vào thư mục tạm.

### Thay đổi đường dẫn và tài liệu

| File trước | File sau / hành động | Lý do |
|---|---|---|
| `preprocessing/encoding/tests/test_approval_package.py` | Chuyển nguyên bytes sang `tests/unit/test_encoding_approval_package.py`; bỏ thư mục tests rỗng trong source | 4 tests được collection mặc định, dùng hook repository |
| Handoff05 dài, trộn trạng thái cũ | Giữ đường dẫn, rút gọn thành điểm bắt đầu; bản nguyên nội dung ở [handoff lịch sử](05_p5_handoff_history_2026-11-09.md) | Bảo toàn liên kết và quyết định; không lẫn proposal/5.177 với trạng thái hiện hành |
| Thiếu chỉ dẫn vai trò | Thêm [code README](../../../preprocessing/encoding/README.md), [notebook README](../../../notebooks/README.md); cập nhật README evidence hiện có | Các thư mục cùng dẫn về handoff; contract06 giữ policy, report07 giữ số liệu |
| Notebook giả định cwd là repo root | Cùng `eda_p5_final_cohort.ipynb/.html` | Tự tìm root, thêm sys.path trước import, chọn run theo manifest |
| Builder chỉ tạo lần đầu tại canonical, inject ROOT và tools path cố định | Cùng `build_cohort_notebook.py`, thêm `--output-dir`/`--kernel-cwd` | Tái tạo vào `/tmp`, bảo vệ cặp đã có; kiểm được bootstrap thật từ `notebooks/` |
| Pin cả môi trường review cho notebook | Thêm `requirements-notebook.txt` cho nbformat/nbclient/nbconvert | Giữ Pandas/NumPy runtime; requirements-review lịch sử giữ nguyên |
| 10 `.pyc` không tracked trong `preprocessing/encoding/__pycache__/` | Xóa sau khi xác minh source và compile lại thành công trong `/tmp` | Cache tái sinh, không phải evidence duy nhất; danh sách ở cache_cleanup.json |

Không xóa script Python review/nghiệp vụ hoặc dataset. XML/log lịch sử giữ path test cũ vì phản ánh lần chạy trước; tài liệu tái lập v1 cập nhật path mới. Không có thay đổi path canonical hoặc cách gọi full runner cho downstream; chỉ đổi path test và mở rộng CLI builder notebook.

### Các file phải giữ và ranh giới P4

Giữ snapshot, frozen assets, ledger/decisions, gói v1/v2, scope proposals, history 5.177 và EDA cũ nguyên SHA. TF-IDF matrix/rows/terms/config, unmatched, quality, validation và manifest là sidecars cần cho tái lập/alignment, không phải file tạm.

Giữ các helper candidate/K/scope/EDA cũ, `skills_taxonomy_230.py`, `run.encode_dataset` và `tfidf_extractor.py`: còn callers/tests, source hashes, stopword provenance hoặc phương pháp cần truy vết. `candidate_lookup.py` thực tế thuộc luồng frozen dù tên/docstring còn nói candidate. `check_p5_cleanup_equivalence.py` và `finalize_execution_evidence.py` gắn với source/bundle cũ; không dùng chúng trên canonical cohort mới. Chưa chứng minh được chúng hết giá trị nên không xóa hoặc di chuyển hàng loạt.

Không tìm thấy `.tmp/.bak/.orig/.swp` trong các thư mục P5 được khảo sát. Đã phân loại **27 module**, lưu imports/path literals và **890 hits rg** trên code/tests/docs/scripts/config/metadata, gồm đường dẫn ghép theo ROOT/run ID. Repo không có `.github/` để cập nhật CI. Không sửa tên/path trong XML/manifest lịch sử chỉ để che việc chuyển file.

P5 không parse/cap/log salary lại, không chuẩn hóa province/skills hoặc sửa job_family lại. Validation schema và Arrow null-type union bảo vệ Golden lossless; top10/ordinal/one-hot/missing indicators là encoding. `_normalize_employment_type` ánh xạ raw label sang categories, chưa có bằng chứng snapshot được P4 cấp trường tương đương. Prototype `run.encode_dataset` còn callers audit/tests và semantics khác frozen runner. Không đủ căn cứ để gỡ các nhánh này như xử lý trùng P4; core source hashes giữ nguyên.

### Kết quả kiểm chứng

- **72 P5 tests pass** (68 trước + 4 tests chuyển vào collection), **Ruff pass**. Không sửa testpaths/hook/driver chung.
- Full entrypoint `python -m preprocessing.encoding.run_encoding` chạy explicit config vào `/tmp`, không `--publish`, khoảng **16,968 giây**. **10/10 artifact tái tạo giống bytes và logical data** với canonical; không thay dataset. Validation metadata của run tạm khác đường dẫn/status là dự kiến.
- Dùng lại `execute.validate_bundle` kiểm X 230 binary uint8, C 230×230 int64/labels/order/intersections, ID/row alignment, Golden lossless, TF-IDF reconstruction và sidecars. Coverage **4.231/5.104**, canonical pairs **21.750**, zero-column **0**, giống trước refactor.
- Đã tái hiện lỗi cwd của notebook cũ. Sau sửa, kernel mới bắt đầu tại `notebooks/`, không inject repo root qua môi trường; **6 cells, 0 errors**, `covered` đúng thứ tự. HTML sinh từ notebook vừa chạy. Bản notebook/HTML, manifest và builder trước refactor lưu ở evidence `before/`; đồng bộ SHA EDA mới trong cả hai manifests. EDA 5.177 lịch sử giữ nguyên.
- **164 file được bảo vệ không đổi SHA**: P3/P4/shared dictionaries, snapshot, runtime assets, quyết định/gói review, history và các thay đổi có sẵn của người dùng. Không sửa R2, Mining, shared driver, task hoặc `preprocessing/common/r2_export.py`.
- Toàn repository vẫn đúng **6 collection errors như trước**: 5 integration modules thiếu sqlalchemy và legacy Golden test thiếu target_schema_formatter. Không phát sinh collection regression do chuyển tests; không claim whole-repo pass.

Evidence: [refactor_2026-11-09](../../../reports/preprocessing/05_encoding/refactor_2026-11-09/), gồm baseline 288 file/git diff trước sửa, artifact_equivalence.json, structure_inventory.json, cache_cleanup.json, tests/lint/EDA logs và post_refactor_integrity.json. Không thêm bản sao dataset vào repo; output kiểm chứng ở `/tmp`.

Python 3.14.4 đã kiểm cho refactor theo yêu cầu; Python 3.12 vẫn **UNVERIFIED** theo SPEC. Lineage/scope vẫn có giới hạn ở phần 6. Refactor pass không tự đổi acceptance/P5 complete.
