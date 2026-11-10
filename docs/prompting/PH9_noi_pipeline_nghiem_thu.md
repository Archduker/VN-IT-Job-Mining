# Prompt PH9: nối pipeline, Monitoring, chạy thử/chạy thật, nghiệm thu, đẩy `pipeline/` lên R2

> **Nháp, chờ bạn duyệt.** Các điểm **[CẦN CHỐT]** D1–D6 (và P1, P2 của PH8) phải chốt trước khi giao prompt. Chỗ ghi "[ĐỀ XUẤT]" là mặc định nếu bạn không đổi. **Prompt này chỉ cho phép ghi R2 sau khi người dùng đồng ý bằng lời cho đúng danh sách key đã liệt kê.**

## 1. Ngữ cảnh

Đọc trước:
- `docs/spec/preprocessing/spec/PH9_noi_pipeline_nghiem_thu.md` (mục 2 là hiện trạng đã đo; mục 3–4 là việc và quy trình).
- Spec PH0–PH8 trong `docs/spec/preprocessing/spec/`, `P0_pipeline_contract.md` (schema báo cáo), `docs/spec/monitoring/preprocessing_page_spec.md`.
- `Tiền xử lý dữ liệu JD ngành IT cho Data Mining.md` mục 3.3, 4.3, 4.4, 5.
- Code: `scripts/run_preprocessing.py`, `preprocessing/common/__init__.py` (`STEPS`, `SOURCES`), `preprocessing/common/step_report.py`, `preprocessing/common/r2_export.py` (`PIPELINE_STEPS`, `pipeline_key`, `plan_objects`), `scripts/push_preprocessing_to_r2.py`, `collection/common/r2_storage.py` (`canonicalize_lakehouse_key`), `monitoring/backend/app/services/preprocessing_step_service.py`, `monitoring/frontend/src/pages/PreprocessingPage.tsx`, `monitoring/CLAUDE.md`, `scripts/CLAUDE.md`, `processing/CLAUDE.md`.

Hiện tại (đo 10/11/2026, mục 2 spec):
- Driver chạy 5 bước; chưa có bước `processing/`; `STEPS` cố định 5 giá trị được import ở nhiều nơi.
- Báo cáo 03/04 trên máy cũ (03/11, 5.177 dòng); `01_clean` có 5.077 tin (09/11); `02_integration/` trống.
- `pipeline_key` có nhưng không ai gọi; push hiện chỉ đẩy `staging/<nguồn>/preprocessing/*` và `curated/preprocessing/*`, không đẩy `pipeline/`.
- Monitoring backend chỉ nhận 5 bước, không có khối phễu.

## 2. Việc cần sửa

**Thứ tự bắt buộc: A (code, test) → B (chạy thử) → C (chạy thật local) → D (ghi nhận) → E (R2, chỉ khi được đồng ý).**

**A. Code**
1. Driver theo D1 ([ĐỀ XUẤT] `scripts/run_pipeline.py` mới + một danh sách bước duy nhất; `run_preprocessing.py` giữ hành vi cũ cho 5 bước). Cờ: `--from`, `--to`, `--source`, `--dry-run`, `--stage`. Bước chưa làm in "chưa làm" và dừng, như hiện tại. Luật bảo toàn kiểm sau mỗi bước.
2. `reports/pipeline/funnel.json` ghép từ `_all.json` mỗi bước (chỉ số đã có trong báo cáo; không đọc parquet).
3. `preprocessing/common/r2_export.py`: `PIPELINE_STEPS` thêm bước `processing/` (tên: P1 của PH8); `plan_objects()` thêm object `pipeline/<bước>/<tên file>` dùng `pipeline_key` (và `rejected`, `translation` nếu đã có từ PH0/PH5); metadata object ghi `generated_at` + số dòng như hiện tại. `scripts/push_preprocessing_to_r2.py` giữ nguyên nguyên tắc: không `--push` = chạy thử.
4. Monitoring backend: `preprocessing_step_service` lấy danh sách bước từ cùng nguồn sự thật với driver, đọc báo cáo `processing/` theo D4 ([ĐỀ XUẤT] `reports/processing/<bước>/`); bước lạ 404; thiếu file `available=false` kèm lệnh; thêm endpoint đọc `funnel.json` (thiếu thì `available=false`).
5. Monitoring frontend: `StepStrip` hiện mọi bước; khối "Phễu dữ liệu"; khối model (tên + phiên bản + số JD dịch + số trúng cache nếu có báo cáo dịch, còn lại "không dùng model (luật if-else)"); khối riêng 07/08/09 theo spec PH9 3.3, đọc `extra` từ báo cáo. Dùng lại component, token màu, quy tắc 390px.
6. Ghim version các gói đã cài và đã được bạn đồng ý (PH0, PH8) vào `requirements.txt`; **không** `pip install`.
7. Test mới (trước code): xem mục 5.

**B. Chạy thử toàn chuỗi (`--dry-run`)** theo D3 ([ĐỀ XUẤT] bước thiếu đầu vào báo `INPUT_MISSING` kèm bước cần chạy; không điền 0): `glints` trước, rồi 8 nguồn. Gửi bảng vào/ra từng bước, danh sách bước báo `INPUT_MISSING`. Dừng ở đây nếu có bước vi phạm bảo toàn.

**C. Chạy thật, chỉ ghi local** (`data/preprocessing/`, `data/processing/`, `reports/`): từng nguồn rồi 8 nguồn, hai lần để so hash. Điền bảng nghiệm thu (spec 4.3) bằng số thật; ô chưa đo ghi "chưa đo" kèm lý do. Không có cột mục tiêu. Nếu có file nhãn gold, chạy `scripts/eval_gold_processing.py` (PH8) và đưa kết quả vào báo cáo; không có thì "chưa có nhãn".

**D. Ghi nhận**: mục `L-<số kế tiếp>` trong `docs/issue_log.md` cho từng lỗi sửa được từ PH0–PH8 (đọc `git log` và các spec để liệt kê; không bịa lỗi); xóa mục tương ứng khỏi `KNOWN_ISSUED.md`; **không** xóa mục PRE nào chưa được giải quyết thật; thêm mục mở mới nếu có. Cập nhật `preprocessing/CLAUDE.md`, `processing/CLAUDE.md`, `scripts/CLAUDE.md`, `monitoring/CLAUDE.md` nếu đổi.

**E. R2 `pipeline/`** (chỉ sau khi A–D xong và bạn đồng ý):
1. Liệt kê chỉ đọc xác nhận `pipeline/.keep` đã có (bạn upload tay).
2. Chạy thử `python scripts/push_preprocessing_to_r2.py` (không `--push`), gửi bảng key mới/lệch/khớp (số dòng, kích thước, `generated_at`) và danh sách key sẽ ghi.
3. **Dừng. Chờ bạn viết đồng ý rõ cho đúng danh sách đó.** Không có đồng ý thì kết thúc ở đây và báo.
4. Có đồng ý: `--push` (không `--apply`, không cờ khác); chạy lại bản thử, kỳ vọng mọi key "khớp"; báo kết quả. Không xóa object, không đụng `raw/`, `url_ledger/`.

## 3. Pseudo code

```text
# driver
STEPS_ALL = đọc từ một nơi duy nhất (preprocessing + processing)
run(from_, to_, sources, dry_run):
    for step in STEPS_ALL[from_..to_]:
        if step không có module: in "chưa làm"; return 1
        reports = module.run(sources, dry_run)
        for nguồn, r in reports: kiểm r.input == r.output + r.dropped, sai thì in và return 2
        in "step nguồn: input → output (mode)"
    ghi funnel.json từ các _all.json (chỉ khi không dry_run hoặc luôn ghi theo mode, theo D3)

# funnel
funnel = [{"step": s, "input": all.input.rows, "output": all.output.rows, "dropped": all.dropped, "top_rule": ...} for s in STEPS_ALL if báo cáo có]

# push plan
plan_objects(): ... + [{"key": pipeline_key(step, name), "path": data/.../name, ...} for mỗi bảng gộp đã tồn tại]
push: không --push → liệt kê; có --push → ghi chỉ key mới/lệch
```

## 4. Ràng buộc

- Raw bất biến; không sửa `collection/`; không cào; không bao giờ chạy `airflow scheduler`.
- **Mọi ghi/xóa R2 phải dry-run trước và có đồng ý rõ của người dùng; agent không tự thêm `--push`, `--apply`.** Chạy thử cũng chỉ đọc.
- Không in giá trị `.env`; không đưa secret vào log hay báo cáo; so cấu hình bằng hash nếu cần.
- Không cài gói, không commit.
- Không gõ tay số vào Monitoring, không `Math.random`; thiếu báo cáo thì trạng thái rỗng trung thực.
- Không đổi tên cột/giá trị đã có; không xóa file dữ liệu local; `data/` và `rejected/` không vào git; `reports/` không chứa toàn văn JD.
- Không tự quyết D1–D6; dùng [ĐỀ XUẤT] nếu bạn không đổi và ghi rõ trong báo cáo.
- Không hạ ngưỡng nghiệm thu; không đạt thì báo số.

## 5. Ví dụ (thành test; dùng dữ liệu thật hoặc fixture thật, ghi nguồn)

| Tình huống | Kết quả mong đợi |
|---|---|
| Driver `--step` một bước chưa có module | in "chưa làm", mã thoát khác 0, không chạy bước sau |
| Báo cáo giả lập (dựng từ `StepReport` thật trong `tmp_path`) có `input != output + dropped` | driver dừng, in bước và nguồn |
| `funnel.json` từ hai `_all.json` mẫu | số khớp từng báo cáo; thiếu bước nào thì bước đó vắng, không điền 0 |
| `GET steps/<bước lạ>` | 404 |
| `GET steps/07_sections` khi chưa có báo cáo | `available=false` + lệnh tạo |
| `pipeline_key("07_sections", "all.parquet")` (tên theo P1) | `pipeline/07_sections/all.parquet`; bước lạ ném `ValueError` |
| `canonicalize_lakehouse_key("pipeline/.keep")` | bị từ chối (PH0) |
| `plan_objects()` khi chưa có file local | không liệt kê key `pipeline/` đó (không tạo object ma) |
| `push_preprocessing_to_r2.py` không `--push` | không có lời gọi `put_object`/`upload` (kiểm bằng client giả trong test, không dùng mạng) |
| Chạy 8 nguồn hai lần (local) | hash parquet mỗi bước trùng |
| `npm run build`, Playwright 1440 và 390 px trên `/preprocessing` | không tràn ngang, không lỗi console |

## 6. Cách review

| Kiểm | Lệnh / cách | Đạt |
|---|---|---|
| Test | `pytest tests/unit -q`, `pytest tests/integration/test_preprocessing_steps_api.py -q` | xanh |
| Bảo toàn | `python scripts/run_pipeline.py --source all --dry-run`, rồi chạy thật | `in = out + dropped` mọi bước, mọi nguồn |
| Số thật | mở `reports/.../_all.json` cạnh trang Monitoring, so 3 ô và funnel | khớp |
| Rỗng trung thực | xóa tạm một báo cáo (bản sao) | trang hiện "chưa có", không trắng |
| Nghiệm thu | bảng 4.3 spec điền bằng số | đủ hàng; ô chưa đo có lý do |
| Gold | `scripts/eval_gold_processing.py` (nếu có nhãn) | section ≥ 90%, F1 ≥ 0,85, hoặc "chưa có nhãn" |
| R2 thử | `push_preprocessing_to_r2.py` không `--push` | bảng key; mình xem, chưa ghi gì |
| R2 thật | chỉ sau đồng ý bằng lời | chạy lại thử: tất cả "khớp"; không object nào bị xóa |
| Ghi nhận | `docs/issue_log.md`, `KNOWN_ISSUED.md`, các `CLAUDE.md` | mục mới đúng khuôn; mục PRE chưa giải quyết còn nguyên |
| Git | `git status`, `git diff --stat` | không đụng `collection/`, raw; không file dữ liệu, `.env` trong git |

## Yêu cầu bổ sung: mẫu trước/sau
Thêm khối `samples` vào báo cáo mỗi bước (seed 42, vài tin mỗi nguồn, ưu tiên tin bị đổi; có `job_id`, nguồn, giá trị trước/sau của trường bị đổi). Monitoring và slide phải xem được. Xem spec PH9, mục "Yêu cầu bổ sung".
