# Prompting log Mining (từ 20/11/2026)

Mỗi file là **một prompt dán cho agent** (Claude Code) để làm một bước Mining, kèm **Log** theo quy trình 5 bước. Cùng khuôn với [`../preprocessing/README.md`](../preprocessing/README.md) và [`../processing/README.md`](../processing/README.md).

- Prompt **trỏ về đặc tả**, không chép lại luật. Đặc tả là luật (mã M0.x … M6.x), prompt là cách làm.
- Đặc tả chi tiết: [`docs/spec/mining/`](../../spec/mining/README.md) (đã duyệt 20/11). Hợp đồng chung: [`docs/spec/07_mining_spec.md`](../../spec/07_mining_spec.md). Nghiệm thu: [`docs/spec/08_evaluation_spec.md`](../../spec/08_evaluation_spec.md).
- **Thứ tự làm:** M0 → M1 → M2 → M3 → M4 → M5 → M6. Bước sau dùng kết quả bước trước (M5 cần baseline của M1; M6 cần M1, M2, M5).

| Bước | Prompt | Đặc tả | Code | Trạng thái 20/11 |
|---|---|---|---|---|
| M0 Chuẩn bị | [`M0_chuan_bi.md`](M0_chuan_bi.md) | [`M0_chuan_bi.md`](../../spec/mining/M0_chuan_bi.md) | `config.py`, `data_io.py`, `run_mining_pipeline.py`, `sanity.py`, `synthetic.py` | Xong 20/11 (d79288b, L-55) |
| M1 BI (SD1) | [`M1_bi.md`](M1_bi.md) | [`M1_bi.md`](../../spec/mining/M1_bi.md) | mới `bi.py` | Chạy thật 20/11; kiểm tay 20 tin còn mở |
| M2 Gói kỹ năng (SD2) | [`M2_fp_growth.md`](M2_fp_growth.md) | [`M2_fp_growth.md`](../../spec/mining/M2_fp_growth.md) | `association.py` | Code + dry-run 20/11; chờ xem ổn định, kiểm tay |
| M3 Nhóm việc (SD3) | [`M3_phan_cum.md`](M3_phan_cum.md) | [`M3_phan_cum.md`](../../spec/mining/M3_phan_cum.md) | `clustering.py` | Prompt duyệt 20/11 |
| M4 Tin khác hoặc mới (SD3) | [`M4_tin_khac_moi.md`](M4_tin_khac_moi.md) | [`M4_tin_khac_moi.md`](../../spec/mining/M4_tin_khac_moi.md) | `anomaly.py` | Prompt duyệt 20/11 |
| M5 Lương và SHAP (SD4) | [`M5_luong_shap.md`](M5_luong_shap.md) | [`M5_luong_shap.md`](../../spec/mining/M5_luong_shap.md) | `salary_model.py` | Prompt duyệt 20/11 |
| M6 Lộ trình (SD5) | [`M6_lo_trinh.md`](M6_lo_trinh.md) | [`M6_lo_trinh.md`](../../spec/mining/M6_lo_trinh.md) | mới `recommend.py` | Prompt duyệt 20/11 |

## Khuôn prompt (6 phần)

```text
1. Ngữ cảnh       vì sao làm, đọc file nào trước, số liệu hiện tại
2. Việc cần sửa   Input → Output (đường dẫn, cột, metrics)
3. Pseudo code    các bước theo thứ tự, đủ để review trước khi viết code thật
4. Ràng buộc      ranh giới bước, luật an toàn của repo, việc KHÔNG làm
5. Ví dụ          dữ liệu nhỏ dựng tay → kết quả, đúng như test sẽ kiểm
6. Cách review    kiểm gì, bằng lệnh nào, ngưỡng đạt
```

Cuối mỗi file có mục **Log**.

## Quy trình 5 bước (Log ghi theo đúng 5 bước này)

| # | Bước | Ai làm | Ghi vào Log |
|---|---|---|---|
| 1 | Duyệt đặc tả `docs/spec/mining/<bước>.md` | Người dùng | Ngày, quyết định, commit |
| 2 | Duyệt prompt (pseudo code, ví dụ) | Người dùng | Ngày, chỗ sửa |
| 3 | Viết test trước theo mục 5, rồi code | Agent | Test, file code, commit |
| 4 | `python -m mining.run_mining_pipeline --only <bước> --dry-run` trên dữ liệu thật, gửi bảng số | Agent | Số chính, sanity |
| 5 | Cùng review theo mục 6 của đặc tả; đạt thì chạy thật (ghi `mining/artifacts/`), điền mục 5–6 đặc tả, `docs/issue_log.md` nếu sửa lỗi, xóa phần đã xong trong `docs/KNOWN_ISSUED.md` (MINE-1, MINE-7) | Cả hai | Ngày chạy thật, sha256 đầu vào, số, commit, mã `L-` |

## Ràng buộc chung cho mọi prompt Mining

- Chỉ dữ liệu thật để báo số; `--synthetic` chỉ cho test (L-19). `random_state` 42.
- Mining chỉ đọc `data/` và ghi `mining/artifacts/` (không vào git). Không đẩy R2, không đụng Postgres, không bật Airflow scheduler.
- Test không ghi vào `data/`, `reports/`, `mining/artifacts/` thật (dùng `tmp_path`); chạy xong xem `git status`.
- Không sửa Silver, Processing, từ điển kỹ năng. Thấy lỗi dữ liệu thì ghi lại và hỏi.
- Ngưỡng trong code đặt ở `mining/config.py` (`*Params`), tên trùng mã luật của đặc tả trong comment.
- Có câu hỏi thì hỏi, không tự suy diễn. Đổi luật thì sửa đặc tả trước.
- Commit theo từng bước, chỉ file của bước đó; không push. Để nguyên 2 file gold đang bị xóa trong working tree.
