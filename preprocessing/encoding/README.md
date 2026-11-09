# P5 — luồng hiện hành

Bắt đầu tại [handoff05](../../docs/preprocessing/encoding/05_p5_handoff_2026-11-08.md), báo cáo bàn giao duy nhất. Policy/schema ở [contract06](../../docs/preprocessing/encoding/06_p5_execution_contract.md). Manifest canonical xác định run, không chọn input/vocabulary theo tên file thử nghiệm.

```text
snapshot manifest + 8 partitions
 → execution_io.load_snapshot → cohort.apply_ledger
 → execute.run_execution
   ├── candidate_lookup + execution_features → features/X/C
   ├── execution_tfidf → sparse TF-IDF/rows/terms/config
   └── Golden + sidecars → stage/validate → manifest cuối
```

| File | Vai trò |
|---|---|
| execute.py | Một full-bundle CLI/API; lệnh và input ở handoff |
| execution_io.py | SHA/schema/ID loader lossless, null/numeric validation và frozen-asset helpers |
| execution_features.py | E1–E8/C, dùng normalized fields, không parse/cap/log lại P4 |
| execution_tfidf.py | fit_text/reconstruct_transform cho full runner; API extract_tfidf_space chuyển từ tfidf_extractor.py, dùng chung sklearn fit helper |
| candidate_lookup.py | Whole-value canonical/explicit-alias lookup dùng trong runner frozen |
| cohort.py, cohort_assessments.py | Ledger/version/approval validation và nguồn assessment 31 ID, không là bộ lọc upstream |
| run.py, run_encoding.py | Compatibility entrypoints: delegate đủ config hoặc fail trước ghi; pure prototype APIs vẫn có tests/callers riêng |
| build_cohort_notebook.py | Kernel mới, --output-dir/--kernel-cwd; không overwrite notebook đã có |
| finalize_cohort.py | Kiểm artifact/history/EDA và cập nhật evidence; không phải lệnh read-only tổng quát |
| assets/ | Frozen230/order, stopwords, ledger, decision record; giữ nguyên bytes |

## Module còn giữ có phụ thuộc cụ thể

- prepare_approval_package.py: 4 observed-only/alias-union/collision review tests.
- prepare_approval_package_v2.py + vocabulary_scope_v2.py: canonical cases được strict-lookup tests import; per-entity/deferred-alias proposals có giá trị truy vết riêng.
- scope_review.py + scope_review_annotations.py: retrieval/impact regression tests và nguồn proposal theo ID; không dùng keyword làm scope decision tự động.
- compare_vocabulary.py: denominator/tie/manual-decision regression tests; không chọn K trong full runner.
- skills_taxonomy_230.py và run.encode_dataset: prototype API/tests; khác semantics frozen nên không thay ngầm hoặc làm publish path thứ hai.

Các standalone audit/K/review/EDA/prototype-finalizer không còn caller đã retire; không dùng hướng dẫn cũ để tạo lại chúng. Danh mục xóa/gộp và giới hạn ở handoff05. Tests hiện có trong tests/unit/. Không tạo thêm source/test/evidence để kể về việc dọn _01.
