# Prompt P6: trang Monitoring Pre-processing theo từng bước

> **Cập nhật 04/11/2026: dự án bỏ hẳn model/LLM (JEV qua OpenCode, Gemini).** Mọi đoạn trong file này nói về JEV, LLM, GenAI, dịch JD, `--use-api`, cache hay sổ tiền API đã hết hiệu lực. Thay bằng luật if-else: xem `docs/preprocessing/spec/P0_pipeline_contract.md` mục 6 và `docs/issue_log.md` L-28.

## 1. Ngữ cảnh

Đọc trước:
- `docs/monitoring/preprocessing_page_spec.md`: bố cục, API, nguyên tắc số thật.
- `docs/preprocessing/spec/P0_pipeline_contract.md` mục 4: schema báo cáo.
- `monitoring/CLAUDE.md`: token màu, quy tắc 390px, quy tắc số thật.
- `monitoring/frontend/src/pages/RawReportPage.tsx`: mẫu UX tổng → nguồn.

Làm ngay sau P1, khi đã có `reports/preprocessing/01_clean/*.json` thật. Các bước chưa chạy hiện "Chưa chạy".

## 2. Việc cần sửa

- **Input:** `reports/preprocessing/<bước>/<nguồn>.json`, `_all.json`.
- **Output:**
  - Backend:
    - `monitoring/backend/app/services/preprocessing_step_service.py` (mới).
    - 3 endpoint `GET /api/v1/preprocessing/steps[/{step}[/{source}]]` trong `endpoints/preprocessing/cleaning.py`.
    - Schema Pydantic trong `app/schemas/`.
  - Frontend:
    - `PreprocessingPage.tsx` viết lại.
    - `components/preprocessing/{StepStrip,StepOverview,RuleTable,FieldFillCompare,RuleExamples,ItReviewPanel,ApiUsage}.tsx`.
    - Thêm vào `api/client.ts` và `types`.

## 3. Pseudo code

```text
# backend
STEPS = ("01_clean", "02_integration", "03_transformation", "04_normalization", "05_encoding")
ROOT = _reports_dir() / "preprocessing"                # cùng cách pipeline_report_service tìm reports/

list_steps():
    out = []
    for i, step in enumerate(STEPS):
        r = load_json_report(ROOT/step/"_all.json")          # dùng lại app.core.data_paths
        if r is None: out.append({step, available: False, command: f"python scripts/run_preprocessing.py --step {step[3:]} --dry-run"}); continue
        prev = out[i-1] if i else None
        stale = prev and prev.available and prev.generated_at > r.generated_at
        out.append({step, available: True, mode: r.mode, generated_at, input_rows, output_rows, stale})
    return out

get_step(step):           step not in STEPS → 404; trả _all.json + bảng 8 nguồn (input, output, bỏ theo luật)
get_step_source(step, s): step not in STEPS → 404; require_source(s); trả nguyên báo cáo hoặc available=False

# frontend
PreprocessingPage:
    step, source = đọc từ URL (?step=&source=), mặc định 01_clean, careerviet
    steps = useAsync(api.preprocessingSteps)
    <StepStrip steps selected=step onSelect=setStep/>          # 5 thẻ, có mũi tên, nhãn Sẽ/Đã xử lý/Chưa chạy/Cần chạy lại
    <StepOverview data=useAsync(api.preprocessingStep(step))/>  # StatCard + cột chồng bỏ theo luật × nguồn + RuleTable + heatmap
    <SourcePicker .../>                                         # dùng lại components/raw/SourcePicker
    <RuleExamples report=useAsync(api.preprocessingStepSource(step, source))/>
    <FieldFillCompare .../>
    link "Input = output của <bước trước>" và "Xem ở <bước sau>" giữ nguồn
    step == 01_clean → <ItReviewPanel report/>     # đọc rules C4a/C4b/C4c + khối review, policy
    report.api có → <ApiUsage api/>                 # model, calls, cache_hits, cost_usd
```

## 4. Ràng buộc

- Backend không đọc parquet và không tự tính số. Thiếu số thì sửa pipeline để ghi vào báo cáo.
- `{step}`, `{source}` được kiểm trước khi ghép vào đường dẫn file (chặn `../`).
- Giữ `GET /preprocessing/metrics` và `pipeline_report_service` cho trang Processing, Master Dashboard.
- Dùng component có sẵn, không thêm thư viện biểu đồ mới (đã có recharts).
- Không thêm nút chạy pipeline trên trang.

## 5. Ví dụ

| Tình huống | Trang hiện |
|---|---|
| Chỉ có báo cáo Clean `applied` | Thẻ 01 "Đã xử lý 14.292 → 10.5xx"; thẻ 02–05 "Chưa chạy" kèm lệnh |
| Clean chạy lại sau Integration | Thẻ 02 nhãn "Cần chạy lại" |
| `GET /steps/99_x` | 404 |
| `GET /steps/01_clean/abc` | 404 |
| Thiếu `topdev.json` | Tầng 2 hiện "Chưa có báo cáo cho TopDev" + lệnh |
| Clean chưa có `it_policy.json` | Khối "Kiểm tin ngoài IT" hiện "Chưa duyệt, không bỏ tin nào" và số `non_it` theo nguồn |
| Báo cáo `api.used=false` | Khối API hiện lý do (thiếu khóa / không bật `--use-api`) |

## 6. Cách review

- Test backend (`tests/integration/`, theo mẫu `test_monitoring_api.py`): báo cáo mẫu trong `tmp_path`, bước/nguồn lạ 404, thiếu file `available=false`, `stale` đúng.
- Mở trang cạnh file JSON, so 3 số bất kỳ.
- `npm run build` qua; Playwright 1440px và 390px: không tràn ngang, không lỗi console.
- Bạn đi thử luồng: bấm bước 01 → chọn TopDev → xem ví dụ C4 → bấm "xem ở bước sau".
