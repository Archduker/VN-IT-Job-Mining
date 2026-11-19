# Nhãn kiểm định bộ lọc IT (C4b)

- 643 tin mẫu do bước 01 Clean chọn (`preprocessing/clean/run.py` `review_sample`, seed cố định), một file mỗi nguồn.
- Cột `nhan_tay` (`it` / `non_it`, trống = chưa chắc) do **Claude gán ngày 18/11/2026** (cột `nguoi_gan = claude`), theo rubric trong
  `preprocessing/clean/label_review.py`: chỉ nhìn tiêu đề và kỹ năng, không xem `it_rule` / `it_status` của luật.
- Người dùng kiểm: toàn bộ tin mà nhãn khác luật và 10% tin cùng ý với luật (`docs/presentation/preprocessing_steps/c4b_kiem_mau.html`).
  Tỷ lệ đồng ý ghi vào đây khi kiểm xong.
- Bản làm việc là `data/preprocessing/review/it_<nguồn>.csv` (bị git bỏ qua); bản này là bản lưu để không mất nhãn khi dọn `data/`.
  Khôi phục: chép các file `it_*.csv` ở đây về `data/preprocessing/review/` rồi chạy lại bước 01.

## Phiên bản 2 (19/11/2026): soát lại theo định nghĩa "vai trò IT"

- Định nghĩa và ca ranh giới: `docs/spec/preprocessing/01_clean.md` mục 2.1 (người dùng chốt 19/11, gồm Q1–Q8 và H1–H9).
- `relabel_2026-11-19.csv`: mọi tin được xem lại, nhãn cũ, đề xuất, lý do, độ chắc và quyết định cuối (`quyet_dinh`, `ai_quyet`).
  - 21 đề xuất của Claude được duyệt, 1 bị bác (dòng 376, lập trình PLC giữ `non_it`).
  - Nhóm H do người dùng quyết: H1 UI/UX designer và H6 nhúng cho tự động hóa là IT; H2 phần cứng/chip, H3 kỹ sư dịch vụ bảo trì máy, H4 kỹ thuật viên viễn thông lắp đặt wifi/FTTH, H5 kỹ thuật viên sửa máy tính/laptop, H7 kế hoạch/báo cáo tài chính có dùng SQL, H8 giám đốc ALM ngân hàng, H9 product marketing kiêm PO là không IT.
  - 26 nhãn trong `it_*.csv` đổi (`nguoi_gan` = `claude_v2` hoặc `nguoi_dung`). Sau khi đổi: 168 IT, 475 không IT.
- `split_2026-11-19.csv`: tập `tune` (451) để chọn luật, tập `giu_lai` (192) để báo số nghiệm thu. Phân tầng theo nguồn và nhãn, 30% mỗi tầng, `random_state` 42. Không chỉnh luật theo tin của tập giữ lại.
