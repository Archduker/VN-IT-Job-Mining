# Vocabulary v2 — proposal, not approved

Báo cáo/đường dẫn gửi reviewer: [05_p5_vocabulary_v2_review.md](../../../../docs/preprocessing/encoding/05_p5_vocabulary_v2_review.md).

Đọc `vocabulary_proposed_v2.csv`, `ambiguities_for_review_v2.csv`, `context_evidence.csv`, `exclusions_and_replacements.csv`, `group_definitions.json` và `group_crosswalk.csv`; mapping máy đọc là `mapping_proposed_v2.json`. Có230proposals +6reserves;214hard/16soft,137mục<20,19group chưa khớp sạch. Decision trống, chưa approved.

`skill_matrix_review.npz` là X review5177×230, không phải full P5 features/Golden. Row IDs ở `job_rows.csv`, ordered columns ở mapping. Metrics ghi rõ mẫu số source-value pairs so canonical pairs. Validation kiểm snapshot SHA, bit/count/ID unions, excerpts và protected hashes.

49related tests và Ruff pass. Whole-repo offline tests có6collection errors ngoài phần này, xem logs; Python3.14.4 chưa thay xác minh3.12. V1/snapshot/quyết định tay/P4/production nguyên vẹn. Không xác nhận P5 hoàn thành.
