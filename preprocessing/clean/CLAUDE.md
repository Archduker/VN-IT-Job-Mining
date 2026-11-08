# Clean: bảo toàn snapshot và bằng chứng nhãn

- CLI từ chối applied khi chạy lẻ. Dry-run lẻ ghi báo cáo vào `reports/preprocessing/_partial/01_clean/`; không ghi đè `_all.json` hoặc báo cáo từng sàn chính.
- API `run(sources, dry_run)` giữ hợp đồng tập nguồn tùy chọn của orchestrator. Người gọi applied chịu trách nhiệm cung cấp đầy đủ nguồn; không dùng API applied lẻ để debug.
- `it_policy.json` là quyết định duyệt drop và ghi chú lịch sử, không phải tập nhãn từng job. Không tuyên bố precision đạt từ các tỷ lệ ghi trong evidence.
- Báo riêng precision IT, precision non_IT, recall IT và TP/FP/TN/FN. Thiếu nhãn phải trả null với `reason=NO_LABELS`.
- Wilson cộng dồn là tham khảo trên mẫu đã trả lời, chưa hiệu chỉnh phân tầng hoặc thiếu nhãn; không tự kết luận nghiệm thu toàn dân số hay gán yêu cầu cận dưới cho lead. `non_it` không đồng nghĩa mọi dòng thực sự bị C4c loại.
- CLI tạo mẫu phải tôn trọng `--source`; `--level1-it` chỉ hợp lệ cùng `--resample-review` và không âm.
- `drop=[]` chỉ bỏ qua C4c. C5/C6/C7 vẫn có thể loại dòng; không khẳng định toàn bộ non_IT còn sống ở output.
- Đếm trường thiếu bằng số bản ghi thật: phần trăm làm tròn 100% không chứng minh không có null.
- Gate category IT của SPEC-05 thuộc common/it_filter và cần lead phối hợp; không tự sửa mã của thành viên khác.
