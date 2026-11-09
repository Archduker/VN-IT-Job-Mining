# P5 — bản đồ mã nguồn

Bắt đầu ở [tài liệu bàn giao](../../docs/preprocessing/encoding/05_p5_handoff_2026-11-08.md). Policy/schema ở contract06; số liệu và kiểm chứng ở report07. Manifest canonical xác định run hiện hành, không dùng tên script review để chọn input hoặc vocabulary.

## Luồng chạy hiện hành

```text
snapshot manifest + 8 P4 partitions
    → execution_io.load_snapshot (SHA/schema/values)
    → cohort.apply_ledger (include trước fit/aggregate)
    → execute.run_execution
        ├── candidate_lookup + execution_features → X/features/C
        ├── execution_tfidf → sparse TF-IDF + rows/terms/config
        └── Golden + sidecars → stage/validate → manifest cuối
```

| File/thư mục | Vai trò |
|---|---|
| `execute.py` | Full-bundle CLI/API duy nhất; xem lệnh trong handoff |
| `execution_io.py` | Loader lossless, validation, helpers freeze dùng khi chuẩn bị assets |
| `execution_features.py`, `execution_tfidf.py` | Encoding E1–E8/C và TF-IDF theo contract |
| `candidate_lookup.py` | Strict lookup dùng bởi runner hiện hành dù tên/docstring còn từ giai đoạn candidate |
| `cohort.py`, `cohort_assessments.py` | Áp/kiểm ledger ràng buộc hash; assessments theo ID của đợt review |
| `assets/` | Frozen vocabulary, stopwords, ledger và decision record; không chọn lại topK |
| `run.py`, `run_encoding.py` | Compatibility entrypoints, thiếu config thì fail trước ghi |
| `build_cohort_notebook.py` | Tạo EDA và HTML bằng kernel mới; hỗ trợ `--output-dir`, `--kernel-cwd` |
| `finalize_cohort.py` | Finalizer của run cohort_v1; cập nhật metadata/evidence, không phải lệnh read-only tổng quát |

## Các file review/lịch sử giữ tại đường dẫn cũ

| Nhóm | File | Vì sao giữ |
|---|---|---|
| Snapshot/audit | `audit_p4_snapshot.py`, `review_snapshot.py` | Nguồn phương pháp audit; script audit có thể truy cập R2, không dùng thay loader offline |
| Quyết định input/K | `analyze_p4_input_and_k.py`, `compare_vocabulary.py` | Truy vết dữ liệu và quyết định trước khi freeze; không chạy lại chọn K trong pipeline |
| Candidate v1/v2 | `prepare_approval_package.py`, `prepare_approval_package_v2.py`, `validate_approval_package.py`, `short_candidate_review.py`, `vocabulary_scope_v2.py` | Proposal/alias/entity evidence; có tests và các quyết định cần truy vết |
| Scope review | `scope_review.py`, `scope_review_annotations.py` | Queue và assessment trước ledger; không phải nhãn gold hoặc bộ lọc upstream mới |
| EDA/cleanup trước | `build_review_notebook.py`, `check_p5_cleanup_equivalence.py`, `finalize_execution_evidence.py` | Tái lập phương pháp cũ với source tương ứng; không chạy finalizer 5.177 lên bundle 5.104 |
| Prototype/shared helpers | `run.encode_dataset`, `skills_taxonomy_230.py`, `tfidf_extractor.py` | Callers audit/tests còn dùng; helpers/stopword provenance cũng được runner hiện hành tham chiếu |

Không di chuyển hàng loạt các module này: có imports, root suy theo `__file__.parents[2]`, đường dẫn ghép theo run và source hashes trong manifest. Xóa/đổi vị trí chỉ vì ít caller sẽ làm mất bằng chứng hoặc làm sai tái lập. Script lịch sử không được xem là lệnh hiện hành; nhiều script cố ý từ chối ghi đè evidence đã có, một số phụ thuộc API prototype đã bị chặn.

## Test và ranh giới P4

Tests tập trung tại [tests/unit](../../tests/unit/), gồm `test_encoding_approval_package.py` được chuyển nguyên nội dung từ `preprocessing/encoding/tests/test_approval_package.py`. Không còn test riêng trong source tree.

P5 không parse/cap/log salary lại, không chuẩn hóa province lại, không re-extract JD/skills hoặc sửa job_family. Kiểm schema, Arrow null-type union và mapping raw employment sang cột one-hot là xử lý riêng cho encoding. Giữ các nhánh này; không có bằng chứng cho phép gỡ chúng như xử lý trùng P4.

Đường dẫn output canonical và cách gọi full runner giữ nguyên. Xem [hướng dẫn notebook](../../notebooks/README.md) cho Restart Kernel → Run All và dependencies công cụ tùy chọn.
