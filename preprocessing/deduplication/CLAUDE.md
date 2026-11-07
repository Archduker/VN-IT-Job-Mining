# Deduplication: các bẫy đã kiểm chứng

- Không sort chuỗi ngày để lấy min/max. Parse ISO và DD/MM/YYYY; quy ngày không timezone về +07, so UTC. Giá trị không parse được phải giữ trong `unparsed_dates`.
- `hop_same_version` không đồng nghĩa đổi nội dung: `hop_version_not_bumped` chỉ đếm cùng version VÀ canonical hash đổi.
- Repost D2 của thành viên thua liên sàn phải truyền đến master cuối; kiểm mọi input Clean có đúng một tham chiếu trong `source_job_ids` hoặc `repost_records`.
- `duplicate_count` chỉ đếm thành viên sau D2; `lineage_rows` bao gồm cả repost D2. Không dùng hai đại lượng thay thế nhau.
- Dry-run lẻ ghi báo cáo vào `reports/preprocessing/_partial/01b_deduplication/`; kiểm nội dung báo cáo chính không đổi, không chỉ kiểm có cờ partial.
- `pairs_audited` là số cặp lưu, không phải chi phí cosine. `cosine_pairs_computed` đếm cặp không thứ tự trong ma trận (không đường chéo); `cross_pairs_evaluated` đếm cặp khác sàn sau gate công ty.
- NFC phải chạy trước regex boilerplate. Test dạng NFD và NFC cùng văn bản.
- Test writer với trạng thái drop dựng sẵn không thay thế test pipeline quyết định merge và truy vết.
- `verify_delivery` tái chạy vào thư mục mới; không đụng raw, báo cáo chính, R2 hoặc scheduler.
