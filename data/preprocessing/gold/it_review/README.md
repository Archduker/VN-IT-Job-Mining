# Nhãn kiểm định bộ lọc IT (C4b)

- 643 tin mẫu do bước 01 Clean chọn (`preprocessing/clean/run.py` `review_sample`, seed cố định), một file mỗi nguồn.
- Cột `nhan_tay` (`it` / `non_it`, trống = chưa chắc) do **Claude gán ngày 18/11/2026** (cột `nguoi_gan = claude`), theo rubric trong
  `preprocessing/clean/label_review.py`: chỉ nhìn tiêu đề và kỹ năng, không xem `it_rule` / `it_status` của luật.
- Người dùng kiểm: toàn bộ tin mà nhãn khác luật và 10% tin cùng ý với luật (`docs/presentation/preprocessing_steps/c4b_kiem_mau.html`).
  Tỷ lệ đồng ý ghi vào đây khi kiểm xong.
- Bản làm việc là `data/preprocessing/review/it_<nguồn>.csv` (bị git bỏ qua); bản này là bản lưu để không mất nhãn khi dọn `data/`.
  Khôi phục: chép các file `it_*.csv` ở đây về `data/preprocessing/review/` rồi chạy lại bước 01.
