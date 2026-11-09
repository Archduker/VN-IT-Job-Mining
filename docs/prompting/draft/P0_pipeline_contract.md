# Prompt P0: khung pipeline 5 bước và báo cáo bước

> **Cập nhật 04/11/2026: dự án bỏ hẳn model/LLM (JEV qua OpenCode, Gemini).** Mọi đoạn trong file này nói về JEV, LLM, GenAI, dịch JD, `--use-api`, cache hay sổ tiền API đã hết hiệu lực. Thay bằng luật if-else: xem `docs/spec/preprocessing/spec/P0_pipeline_contract.md` mục 6 và `docs/issue_log.md` L-28.

## 1. Ngữ cảnh

Đọc trước: `docs/spec/preprocessing/spec/P0_pipeline_contract.md` (luật), `preprocessing/CLAUDE.md`, `scripts/report_data_issues.py` (hàm `latest_envelopes`).

Pipeline cũ (`scripts/run_staging_integration_pipeline.py`) chạy một mạch, không thấy được từng bước. P0 dựng khung cho 5 bước Clean → Integration → Transformation → Normalization → Encoding và schema báo cáo chung. **Chưa viết luật nào của các bước.**

## 2. Việc cần sửa

- **Input:** không có dữ liệu mới. Dùng `data/<nguồn>/raw/` để chạy thử bước Clean rỗng.
- **Output:**
  - `preprocessing/common/step_report.py` (mới): `StepReport` dựng báo cáo theo schema P0 mục 4, `check_conserved()`, `write(path)`.
  - `preprocessing/common/raw_reader.py` (mới): chuyển `latest_envelopes` từ `scripts/report_data_issues.py` sang đây; script cũ import lại từ đây.
  - `scripts/run_preprocessing.py` (mới): `--step`, `--source`, `--dry-run`.
  - `preprocessing/clean/run.py` (mới): `run(source, dry_run)` tạm chỉ đếm input, chưa có luật.
  - `preprocessing/common/api_cache.py` (mới): đọc/ghi cache theo hash ở `data/preprocessing/_cache/<loại>/`, cộng `calls`, `cache_hits`, `cost_usd` vào báo cáo. JEV (P1) và dịch (P3) dùng chung.
  - `scripts/run_preprocessing.py` có thêm cờ `--use-api`.
  - `.gitignore` thêm `data/preprocessing/`.

## 3. Pseudo code

```text
STEPS = ["01_clean", "02_integration", "03_transformation", "04_normalization", "05_encoding"]

main(args):
    steps = STEPS if args.step == "all" else [tên đầy đủ của args.step]
    sources = SOURCES if args.source == "all" else [args.source]
    for step in steps:                        # đúng thứ tự, không đảo
        reports = [module(step).run(src, dry_run=args.dry_run) for src in sources]
        write_all_report(step, reports)       # _all.json = cộng 8 nguồn

StepReport(step, source, mode):
    input_rows, output_rows, dropped[], rules[], fields[]
    add_rule(id, name, action, rows_affected, examples)   # examples: sắp theo job_id, lấy 3
    check_conserved():  input_rows == output_rows + sum(d.rows for d in dropped)  else raise
    write(): check_conserved(); ghi reports/preprocessing/<step>/<source>.json (UTF-8, indent 2)

clean.run(source, dry_run):
    envs, files = raw_reader.latest_envelopes(data/<source>/raw)
    report = StepReport("01_clean", source, "dry_run" if dry_run else "applied")
    report.input_rows = report.output_rows = len(envs)
    if not dry_run: ghi data/preprocessing/01_clean/<source>.jsonl
    report.write(); return report
```

## 4. Ràng buộc

- Không sửa `preprocessing/` cũ, ngoài việc import. Không sửa `run_staging_integration_pipeline.py`.
- `code_version` lấy từ `git rev-parse --short HEAD`. Lỗi thì ghi `"unknown"`, không dừng.
- Báo cáo không chứa đường dẫn tuyệt đối trên máy, chỉ đường dẫn tương đối trong repo.
- Không thêm thư viện mới (`requests` đã có).
- P0 chưa gọi API thật; chỉ dựng cache và khối `api` trong báo cáo (`used: false`).

## 5. Ví dụ

```text
$ python scripts/run_preprocessing.py --step clean --source glints --dry-run
01_clean glints: input 331 → output 331 (dry_run) → reports/preprocessing/01_clean/glints.json
```

Test (`tests/unit/test_step_report.py`):
- input 10, output 7, dropped 3 → ghi được;
- input 10, output 7, dropped 2 → `check_conserved` raise, không có file;
- examples 5 dòng → giữ 3 dòng có `job_id` nhỏ nhất;
- cache: ghi rồi đọc lại cùng hash ra cùng giá trị, `cache_hits` tăng 1.

## 6. Cách review

- Mở `reports/preprocessing/01_clean/glints.json`, so từng khóa với schema P0 mục 4.
- Chạy `--dry-run` hai lần: file giống nhau, trừ `generated_at`.
- `python scripts/report_data_issues.py` vẫn ra 10.758 tin sau khi chuyển `latest_envelopes`.
- `make test` xanh.
