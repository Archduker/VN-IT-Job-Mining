# F12. Dọn tài liệu và báo cáo

Issue: MERGE-2, GEN-8, PRE-26. Trạng thái: **đặc tả chưa duyệt** (viết 09/11/2026). Theo dõi ở `docs/tasks/issues_merge.md`.

## Vấn đề
- Đường dẫn `docs/preprocessing/...` (cũ) còn trong `docs/preprocessing/encoding/*`, `preprocessing/encoding/{CLAUDE,README}.md`, `preprocessing/encoding/cohort.py`, `docs/tasks/05_phat_*` và `legacy_TASKS.md`.
- Báo cáo nghiệm thu của Duy, Phúc, Sơn chưa điền.
- 95 file lớn trong `reports/preprocessing/05_encoding` trong git.

## Giải pháp
1. Quyết thư mục tài liệu của Phát: giữ `docs/preprocessing/encoding/` hoặc dời vào `docs/spec/preprocessing/encoding/` (hỏi người dùng). Sau đó sửa đường dẫn bằng `grep -rn`.
2. Điền báo cáo nghiệm thu: mỗi người tự điền; agent chỉ nhắc, không bịa.
3. `reports/05_encoding`: người dùng đã chấp nhận tạm. Khi dọn: liệt kê file, người dùng chọn giữ/xóa; không xóa khi chưa duyệt (`cohort.py` kiểm hash một số file).

## Rủi ro
Xóa/dời file làm vỡ kiểm hash của `cohort.py` và liên kết trong docs.
