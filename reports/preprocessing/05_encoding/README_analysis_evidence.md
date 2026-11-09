# Bằng chứng phân tích P5 đã đưa vào repository

Điểm bắt đầu hiện hành: [handoff P5](../../../docs/preprocessing/encoding/05_p5_handoff_2026-11-08.md).
Run lấy từ [manifest canonical](../../../data/preprocessing/05_encoding/artifact_manifest.json):
`p5_2026-11-09_cohort_v1`, 5.104 include từ snapshot 5.177.

| Thư mục | Vai trò |
|---|---|
| `p5_2026-11-09_cohort_v1/` | Evidence artifact/cohort hiện hành; bản manifest phải khớp canonical |
| `refactor_2026-11-09/` | Baseline hashes, search/import audit, tests/lint, temporary-run comparison và EDA re-execution |
| `scope_review_2026-11-09_v1/` | Queue/proposals trước khi áp policy; quyết định thực tế ở runtime ledger |
| `p5_2026-11-09_frozen_v2/` | Run 5.177 trước cohort; output cũ resolve qua history_manifest |
| `approval_package_v1/`, `approval_package_v2/` | Vocabulary proposals/decisions/alias evidence được giữ nguyên |

Các mục dưới là bằng chứng lịch sử. Không chọn vocabulary hoặc output hiện hành
bằng cách lấy file tên tương tự trong các thư mục này.

- `p4_k_decision_evidence_v1/`: CSV/JSON so sánh extractor, contract và K; giữ nguyên bytes từ lần phân tích.
- `cleanup_review_2026-11-08/`: baseline pickle, kết quả equivalence và JUnit trước/sau cleanup; đây là evidence lịch sử, không phải output production.
- `snapshot_audit_2026-11-08/` và `review_2026-11-08/`: evidence/snapshot đã có, không thay đổi khi sắp xếp file.

Script tại `preprocessing/encoding/analyze_p4_input_and_k.py` và `check_p5_cleanup_equivalence.py`; tài liệu tại `docs/preprocessing/encoding/p5_input_k_decisions.md`, `review_p3_p4_after_pull.md` và báo cáo đầu mối.

Không chạy lại script để ghi đè evidence hiện có. Pickle chỉ được đọc khi tin cậy nguồn; không phải định dạng input chuẩn P5. Các bản nguồn trong workspace Codex vẫn được giữ lại. Chưa commit hoặc push.
