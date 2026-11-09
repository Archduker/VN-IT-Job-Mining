# Monitoring: trang Pre-processing theo từng bước

> **Cập nhật 04/11/2026: dự án bỏ hẳn model/LLM (JEV qua OpenCode, Gemini).** Mọi đoạn trong file này nói về JEV, LLM, GenAI, dịch JD, `--use-api`, cache hay sổ tiền API đã hết hiệu lực. Thay bằng luật if-else: xem `docs/spec/preprocessing/spec/P0_pipeline_contract.md` mục 6 và `docs/issue_log.md` L-28.

> Trạng thái: **đặc tả, chờ duyệt** (03/11/2026). Làm ngay sau P1 (Clean), rồi mở rộng sau mỗi phase P2–P5.
> Prompt: `docs/prompting/P6_monitoring_preprocessing.md`. Hợp đồng dữ liệu: `docs/spec/preprocessing/spec/P0_pipeline_contract.md` mục 4.

## 1. Ngữ cảnh

- Trang `/preprocessing` hiện tại (`monitoring/frontend/src/pages/PreprocessingPage.tsx`) chỉ có một bảng đọc health card cuối (`reports/<nguồn>/<nguồn>_quality_health_card.json`, qua `monitoring/backend/app/services/pipeline_report_service.py`). Trang không cho thấy bước nào làm gì.
- Thống kê vấn đề dữ liệu 03/11 (`docs/spec/preprocessing/data_issues_2026-11-03.html`) là bản chụp tay, không tự cập nhật.
- Yêu cầu:
  - Số liệu phải **đồng bộ với dữ liệu thật**.
  - Đi theo UX của trang Raw (`monitoring/frontend/src/pages/RawReportPage.tsx`): nhìn tổng trước, chọn nguồn để đi sâu.
  - Thấy 5 bước đúng thứ tự, thấy dữ liệu nào sẽ xử lý và xử lý thế nào, rồi sang bước sau thấy được thay đổi.
  - Trang xem JSON từng nguồn ở trang Raw đã ổn, giữ nguyên.

## 2. Nguyên tắc dữ liệu

- **Backend chỉ đọc báo cáo bước** `reports/preprocessing/<bước>/<nguồn>.json` và `_all.json` do pipeline ghi (schema P0 mục 4). Không tính lại từ parquet, không gõ tay số, không ước lượng. Đây là quy tắc "số thật" trong `monitoring/CLAUDE.md`.
- Thiếu file thì trả `available=false` kèm lệnh để tạo (`python scripts/run_preprocessing.py --step <bước> --source <nguồn> --dry-run`). Không điền 0.
- Báo cáo `mode="dry_run"` hiện là **"Sẽ xử lý"**, `mode="applied"` hiện là **"Đã xử lý"**, kèm `generated_at` và `code_version`.
- Báo cáo bước sau cũ hơn bước trước (input đã đổi sau lần chạy) thì gắn nhãn **"Cần chạy lại"**.

## 3. Bố cục trang (từ tổng đến chi tiết)

```text
┌ Dải 5 bước (luôn ở trên cùng) ─────────────────────────────────────────────┐
│ [01 Clean] → [02 Integration] → [03 Transformation] → [04 Norm.] → [05 Enc.]│
│  14.292→10.5xx   10.5xx→10.5xx     …                                         │
│  Đã xử lý         Sẽ xử lý          Chưa chạy                                │
└──────────────────────────────────────────────────────────────────────────────┘
┌ Tầng 1: Tổng của bước đang chọn (8 nguồn) ──────────────────────────────────┐
│ StatCard: input · output · bị bỏ · bị sửa                                    │
│ Biểu đồ cột chồng: dòng bị bỏ theo luật × nguồn                              │
│ Bảng luật: mã, tên, hành động (bỏ/gắn cờ/sửa), số dòng, % input              │
│ Heatmap độ phủ trường × nguồn (trước | sau bước)                             │
└──────────────────────────────────────────────────────────────────────────────┘
┌ Tầng 2: Chọn nguồn (dùng lại SourcePicker) ─────────────────────────────────┐
│ Input của bước này = output bước trước (link về bước trước)                  │
│ Mỗi luật: số dòng bị tác động + tối đa 3 ví dụ trước → sau (có link tin gốc) │
│ Độ phủ từng trường trước/sau (thanh đôi), ô thay đổi được tô nổi             │
│ Output → "xem ở bước sau" (chuyển sang bước kế, giữ nguồn đang chọn)         │
└──────────────────────────────────────────────────────────────────────────────┘
```

- Chọn bước và chọn nguồn ghi lên URL (`/preprocessing?step=01_clean&source=topdev`) để gửi link được.
- **Khối riêng của bước Clean: "Kiểm tin ngoài IT"** (đặc tả P1 mục C4b):
  - theo từng nguồn: số `it`, `non_it`, `can_kiem`;
  - độ đúng của luật và của JEV trên mẫu bạn đã gán nhãn (chưa gán thì hiện "chưa có nhãn");
  - nguyên nhân chính: (a) crawler kéo sai, (b) nguồn đăng lẫn, (c) phân loại sai;
  - chính sách đang áp dụng: "chưa duyệt, không bỏ tin" hoặc ngưỡng và ngày duyệt;
  - 3 ví dụ mỗi nhóm, có link tin.
- **Khối API**, ở mọi bước có gọi JEV hoặc LLM: model, số lần gọi, số lần trúng cache, chi phí. Không dùng API thì hiện lý do.
- Gán nhãn tay làm ngoài trang, trong file CSV `data/preprocessing/review/`. Pipeline đọc nhãn rồi ghi kết quả vào báo cáo, trang chỉ đọc báo cáo. Nút gán nhãn trên trang để việc sau.
- Mỗi bước có thêm khối riêng ghi trong đặc tả phase (mục 6 của P1–P5), ví dụ phễu Clean, bảng "chữ → số" kinh nghiệm ở P3, histogram lương ở P4. Khối riêng vẫn đọc từ báo cáo bước. Thiếu số thì pipeline ghi thêm vào `rules[].examples` hoặc khóa `extra` của báo cáo, không cho backend tự tính.

## 4. API

| Endpoint | Trả về |
|---|---|
| `GET /api/v1/preprocessing/steps` | 5 bước theo thứ tự: `step`, `available`, `mode`, `generated_at`, `input_rows`, `output_rows`, `stale` (đọc `_all.json` của từng bước) |
| `GET /api/v1/preprocessing/steps/{step}` | `_all.json` của bước + tóm tắt 8 nguồn (input, output, bỏ theo luật) |
| `GET /api/v1/preprocessing/steps/{step}/{source}` | báo cáo của một nguồn, nguyên schema P0 |

- `{step}` chỉ nhận 5 giá trị cố định; `{source}` qua `require_source` (`monitoring/backend/app/core/`). Giá trị khác trả 404, không ghép thẳng vào đường dẫn file.
- Service mới `monitoring/backend/app/services/preprocessing_step_service.py`, router thêm vào `monitoring/backend/app/api/v1/endpoints/preprocessing/cleaning.py`.
- `GET /preprocessing/metrics` cũ giữ đến khi P5 xong, vì trang Processing và Master Dashboard còn đọc health card.

## 5. Frontend

- `PreprocessingPage.tsx` viết lại theo bố cục mục 3. Component mới trong `monitoring/frontend/src/components/preprocessing/`: `StepStrip`, `StepOverview`, `RuleTable`, `FieldFillCompare`, `RuleExamples`.
- Dùng lại: `SourcePicker` (`components/raw/`), `Card`, `StatCard`, `SectionTitle`, `TableShell`, `pct`, `fmt`, `useAsync`, token màu và quy tắc 390px trong `monitoring/CLAUDE.md`.
- Ví dụ trước → sau: chữ gốc gạch, giá trị mới tô màu nhấn, chữ dài cắt ở 120 ký tự, có nút mở đủ.

## 6. Tiêu chí xong và cách review

- Có báo cáo Clean thật thì dải bước hiện đúng input/output; các bước chưa chạy hiện "Chưa chạy" kèm lệnh.
- Số trên trang khớp số trong file JSON (mở cạnh nhau, so 3 ô).
- Xóa một file báo cáo thì trang hiện "chưa có", không lỗi trắng trang.
- Test backend: service đọc báo cáo mẫu trong `tmp_path`; bước hoặc nguồn lạ trả 404; thiếu file trả `available=false`.
- `npm run build` qua. Playwright ở 1440px và 390px: không tràn ngang, không lỗi console.

## 7. Ngoài phạm vi

- Nút "chạy bước này" trên trang: không làm. Trang chỉ đọc; chạy pipeline bằng lệnh.
- Gán nhãn IT ngay trên trang: để sau, hiện dùng CSV.
- Bảng "khai báo trường" ở trang Raw (thay phần phân tích đơn biến): việc riêng, chưa chốt.
