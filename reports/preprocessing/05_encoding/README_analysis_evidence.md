# Evidence P5 còn dùng

Bắt đầu từ [handoff05](../../../docs/preprocessing/encoding/05_p5_handoff_2026-11-08.md). Run dữ liệu lấy từ [manifest canonical](../../../data/preprocessing/05_encoding/artifact_manifest.json), hiện là p5_2026-11-09_cohort_v1 với 5.104 included IDs.

| Thư mục | Vai trò còn dùng |
|---|---|
| snapshot_audit_2026-11-08/ | Input offline: manifest và 8 partitions bất biến |
| p5_2026-11-09_cohort_v1/ | Metrics/validation/manifest/delivery/tests và 31-ID assessments/read logs |
| scope_review_2026-11-09_v1/ | 3 approval files ràng buộc hash, rules/outside-queue evidence, 54-ID assessments/family questions |
| approval_package_v1/, approval_package_v2/ | Semantic proposal/alias/entity/group evidence; trial matrices và debug/test logs dư đã retire |
| review_2026-11-08/ | Hai CSV gốc candidate_generated và candidate_decisions, không sửa |
| p4_k_decision_evidence_v1/ | Chỉ field contract còn được audit P3–P4 tham chiếu |
| p5_2026-11-09_frozen_v2/ | Parent metrics/vocabulary, quyết định nghiệm thu trước và scope evidence/protected-input hashes |
| refactor_2026-11-09/ | Chỉ files kiểm chứng có sẵn được cập nhật cho _01; không thêm baseline/archive/report mới |

Output canonical ở data/. Một full history bundle 5.177 có checksum nằm ở data/preprocessing/05_encoding_history/ và vẫn được runner kiểm trước publish. Các path đã retire được ghi SHA/đích gộp trong manifest.refactor và change_inventory.json; trạng thái trước đợt _01 truy từ commit baseline. Không diễn giải đường dẫn của log/provenance lịch sử là input hiện hành, không sửa hash cũ để che việc retire.
