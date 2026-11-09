# Review ngắn vocabulary P5 — proposed

- Có **129 canonical ứng viên có căn cứ tên từ shared dictionary/prototype và có quan sát thực tế**; còn thiếu ít nhất **101** so với 230. Đây chưa phải số skill hợp lệ đã được Phát duyệt; synonym/cross-taxonomy và nhóm còn cần rà soát nên số cuối có thể thấp hơn.
- `canonical_shortlist.csv`: đúng năm cột yêu cầu; số job tính bằng hợp các ID sau mapping, không cộng frequency alias gây đếm trùng. Chỉ gộp cách viết canonical không phân biệt hoa/thường và tám alias cùng công nghệ đã tồn tại trong repo. Không tự tách skill từ JD.
- `ambiguous_and_exclusions.csv`: các giá trị mơ hồ/collision/upstream gộp và đề xuất loại tag ngành/vị trí. Các lý do là đề xuất, không phải quyết định đã duyệt. Không phục hồi Machine Learning thành TensorFlow/PyTorch.
- `reserves.csv`: tối đa 30 giá trị quan sát dự phòng, unresolved; không dùng để lấp đủ 230. Tần suất cao không đủ để xác nhận skill.
- Nhóm trong shortlist lấy crosswalk sáu nhóm prototype, vẫn proposed; thiếu căn cứ thì ghi Chưa phân nhóm. Canonical dùng chung có thể khác phạm vi prototype nên cần Phát duyệt.
- Không có mục nào được tự đánh approved. Hai CSV gốc giữ nguyên bytes. Script tái lập: `.venv/bin/python -m preprocessing.encoding.short_candidate_review`.

## Input và xác thực

Snapshot: 8 partitions P4, 5177 jobs; SHA mỗi partition kiểm lại từ manifest; frequency toàn bộ candidate_generated khớp snapshot. SHA-256 CSV nguồn:
- candidate_generated.csv: `3a07620f3ef20e6cc50e62bc1486f47ffeddaa7b990775244dc04548d996b5d2`
- candidate_decisions.csv: `cba9dceec0a361912e4ea2543155472cc673a1609987451e32574e449379289d`
