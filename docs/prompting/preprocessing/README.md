# Prompting log pre-processing (từ 18/11/2026)

Mỗi file là **một prompt dán cho agent** (Claude Code) để làm hoặc làm lại một bước pre-processing, kèm **Log** ghi lại bước đó đã đi qua quy trình 5 bước thế nào. Bước đã làm xong thì prompt được viết sao cho chạy lại ra **đúng kết quả đã có**: cùng lệnh, cùng tham số, cùng số liệu kỳ vọng.

- Prompt **trỏ về đặc tả**, không chép lại luật. Đặc tả là luật, prompt là cách làm.
- Đặc tả chi tiết: `docs/spec/preprocessing/<bước>.md`. Hợp đồng chung: `docs/spec/05_preprocessing_spec.md`.
- Các prompt PH0–PH9 ở thư mục cha là lịch sử (viết 10/11, trỏ về đặc tả đã xóa).

| Bước | Prompt | Đặc tả | Trạng thái 18/11 |
|---|---|---|---|
| 01 Clean | [`01_clean.md`](01_clean.md) | [`01_clean.md`](../../spec/preprocessing/01_clean.md) | Đã chạy thật 18/11 |
| 01b Deduplication | [`01b_deduplication.md`](01b_deduplication.md) | [`01b_deduplication.md`](../../spec/preprocessing/01b_deduplication.md) | Đã chạy thật 18/11 |
| 02 Integration | [`02_integration.md`](02_integration.md) | [`02_integration.md`](../../spec/preprocessing/02_integration.md) | Đã sửa (L-49), chạy thật 18/11 |
| 03 Transformation | [`03_transformation.md`](03_transformation.md) | [`03_transformation.md`](../../spec/preprocessing/03_transformation.md) | Luật mới chờ duyệt (bước 1–2 của quy trình) |
| 04 Normalization + 00 Profiling + Silver | [`04_normalization.md`](04_normalization.md) | [`04_normalization.md`](../../spec/preprocessing/04_normalization.md), [`00_profiling.md`](../../spec/preprocessing/00_profiling.md), [`silver.md`](../../spec/preprocessing/silver.md) | Chưa làm |

## Khuôn prompt (6 phần, như `docs/prompting/README.md`)

```text
1. Ngữ cảnh       vì sao làm, đọc file nào trước, số liệu hiện tại
2. Việc cần sửa   Input (đường dẫn, dạng) → Output (đường dẫn, cột, báo cáo)
3. Pseudo code    các bước theo thứ tự, đủ để review trước khi viết code thật
4. Ràng buộc      ranh giới bước, luật an toàn của repo, việc KHÔNG làm
5. Ví dụ          vài dòng trước → sau, đúng như test sẽ kiểm
6. Cách review    bạn và agent kiểm gì, bằng lệnh nào, ngưỡng đạt
```

Cuối mỗi file có thêm mục **Log**.

## Quy trình 5 bước (Log ghi theo đúng 5 bước này)

| # | Bước | Ai làm | Ghi vào Log |
|---|---|---|---|
| 1 | Duyệt đặc tả (`docs/spec/preprocessing/<bước>.md`) | Người dùng | Ngày, quyết định (trích ngắn nguyên văn), commit đặc tả |
| 2 | Duyệt prompt, chủ yếu pseudo code và ví dụ | Người dùng | Ngày, chỗ sửa |
| 3 | Viết test trước theo mục "Ví dụ", rồi viết code | Agent | Test, file code, commit |
| 4 | Chạy `--dry-run` trên `glints`, rồi trên cả 8 nguồn, gửi bảng số | Agent | Số vào/ra, số theo luật |
| 5 | Cùng review theo mục 6; đạt thì chạy thật, ghi `docs/issue_log.md`, xóa mục trong `docs/KNOWN_ISSUED.md` | Cả hai | Ngày chạy thật, số liệu, commit, mã `L-`, trang trình bày |

Bước nào chưa đi qua thì ghi "chưa". Bước nào đi tắt (ví dụ chạy lại mà không sửa luật) thì ghi rõ là đi tắt và vì sao.
