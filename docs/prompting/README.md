# docs/prompting: prompt cho từng phase refactor pre-processing

Mỗi file là một prompt dán cho agent (Claude Code) để làm một phase. Prompt **trỏ về đặc tả**, không chép lại: đặc tả là luật, prompt là cách làm.

| Phase | Prompt | Đặc tả |
|---|---|---|
| P0 | `P0_pipeline_contract.md` | `docs/preprocessing/spec/P0_pipeline_contract.md` (đã làm 03/11/2026) |
| P1 | `P1_clean.md` | `docs/preprocessing/spec/P1_clean.md` (đã làm 03/11/2026, còn JEV: PRE-9) |
| P6 | `P6_monitoring_preprocessing.md` | `docs/monitoring/preprocessing_page_spec.md` (đã làm phần khung và bước Clean 03/11/2026) |
| P2 | `P2_integration.md` | `docs/preprocessing/spec/P2_integration.md` |
| P3 | `P3_transformation.md` | `docs/preprocessing/spec/P3_transformation.md` |
| P4 | `P4_normalization.md` | `docs/preprocessing/spec/P4_normalization.md` |
| P5 | `P5_encoding.md` | `docs/preprocessing/spec/P5_encoding.md` |

Thứ tự làm: P0 → P1 → P6 → P2 → P3 → P4 → P5. Sau mỗi phase, cập nhật trang Monitoring cho bước đó (cùng schema báo cáo, thường chỉ thêm khối riêng).

## Khuôn prompt

```text
1. Ngữ cảnh       vì sao làm, đọc file nào trước, số liệu hiện tại
2. Việc cần sửa   Input (đường dẫn, dạng) → Output (đường dẫn, cột, báo cáo)
3. Pseudo code    các bước theo thứ tự, đủ để review trước khi viết code thật
4. Ràng buộc      ranh giới bước, luật an toàn của repo, việc KHÔNG làm
5. Ví dụ          vài dòng trước → sau, đúng như test sẽ kiểm
6. Cách review    bạn và agent kiểm gì, bằng lệnh nào, ngưỡng đạt
```

## Quy trình mỗi phase

1. Bạn duyệt đặc tả.
2. Bạn duyệt prompt, chủ yếu là pseudo code và ví dụ.
3. Agent viết test trước theo mục "Ví dụ", rồi viết code.
4. Agent chạy `--dry-run` trên `glints` rồi trên cả 8 nguồn, gửi bảng số.
5. Cùng review theo mục 6 của prompt. Đạt thì chạy thật, ghi `docs/issue_log.md`, xóa mục PRE tương ứng trong `KNOWN_ISSUED.md`.

## Các cách review dùng chung

| Cách | Làm thế nào | Dùng khi |
|---|---|---|
| Đối chiếu số | `input.rows = output.rows + bỏ`; so với số đo trước trong `docs/preprocessing/data_issues_2026-11-03.md`; lệch > 5% phải giải thích | mọi phase |
| Xem mẫu | Lấy ngẫu nhiên với seed cố định 10–50 dòng bị bỏ hoặc bị sửa và 10 dòng giữ nguyên; bạn gán nhãn tay đúng/sai | luật có phán đoán (lọc IT, nhóm nghề, cấp bậc) |
| Trước → sau | Đặt cột `raw_*` cạnh cột mới cho 20 dòng | parse lương, ngày, kinh nghiệm |
| Chạy nhỏ trước | `glints` (331 tin) → một nguồn lớn → cả 8 | mọi phase |
| Test từng luật | Mỗi luật một test, dữ liệu nhỏ trong `tmp_path`; `make test` xanh | mọi phase |
| Xem trên trang | Trang `/preprocessing` ở 1440px và 390px; số trên trang khớp file JSON | sau P1 trở đi |
| Gán nhãn IT theo nguồn | Mỗi nguồn 50 tin `non_it` + 30 tin `can_kiem` trong `data/preprocessing/review/it_<nguồn>.csv`; bạn điền `nhan_tay`; đo độ đúng luật và JEV, tìm nguyên nhân (crawler / nguồn / phân loại) | P1 |
| Chấm bản dịch | 30 JD tiếng Anh, 2 model, bạn chấm 1–5 trong `translate_30.csv`; kiểm thuật ngữ không bị dịch | P3 |
| Ước tính tiền API | `--dry-run --use-api` ra số lần gọi và tiền; bạn duyệt rồi mới chạy thật | P1, P3, P4 |
| Hai lần chạy giống nhau | Chạy `--dry-run` hai lần, báo cáo giống nhau (trừ `generated_at`) | mọi phase |

## Luật chung cho mọi prompt

- Không commit. Không ghi lên R2: đẩy lên R2 là việc riêng, chạy thử trước, bạn đồng ý mới chạy.
- Config chỉ trong `.env`, không in giá trị.
- Raw bất biến: không sửa `data/<nguồn>/raw/`.
- Không bật Airflow scheduler.
- JEV và LLM chỉ gọi khi có `--use-api`, có cache, khóa trong `.env`: `OPENCODE_API_KEY` (JEV qua OpenCode Console), `GEMINI_API_KEY` (dịch bằng Gemini). Chỉ gửi nội dung tin tuyển dụng.
