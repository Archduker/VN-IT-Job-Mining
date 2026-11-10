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

- Khi phân tích audit: cosine của transitive-dropped có thể là điểm qua linked_via, không phải điểm trực tiếp hai đầu dòng. Không suy số cụm tách/gộp từ số cạnh đổi điều kiện; phải chạy lại đồ thị.

## PH4 (10/11/2026)
- Tầng 3 là MinHash/LSH chỉ để sinh ứng viên; mọi cặp phải qua `minhash.exact_jaccard`. Cặp J >= 0.85 chỉ bị loại khi cùng `company_slug` không rỗng; khác công ty vào audit D7.
- Không dùng `id()` để suy thứ tự audit: cột a/b của một cặp phụ thuộc địa chỉ bộ nhớ (chỉ danh sách giữ/loại là tất định).
- 02_integration đọc `01b_deduplication/`; nên chạy thật 01b trước 02, nếu không 02 báo thiếu file.
- Tên khóa trong `metadata.dedup` đổi: `identity_hash` -> `text_fold_sha1`, `cosine` -> `jaccard`; `duplicate_of` ở bản bị loại.
