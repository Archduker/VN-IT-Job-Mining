# P0. Khung pipeline và hợp đồng dữ liệu giữa các bước

> Trạng thái: **đặc tả, chờ duyệt** (03/11/2026). Chưa có code.
> Prompt để làm: `docs/prompting/P0_pipeline_contract.md`.

## 1. Ngữ cảnh

- Pipeline hiện tại (`scripts/run_staging_integration_pipeline.py`, 482 dòng) chạy một mạch, mỗi nguồn làm hết mọi việc trong một hàm `process_single_source`, chỉ ghi kết quả cuối. Không xem được bước nào bỏ bao nhiêu dòng, bước nào làm sai.
- Thứ tự cũ: integration → transformation → missing/outlier → normalization, khử trùng chéo nguồn ở cuối. Hệ quả:
  - TopDev ~80% tin ngoài IT (data_issues A1) đi qua mọi bước rồi mới lọc.
  - Tin trùng (B1–B3) cũng chỉ bị khử ở cuối, sau khi các bước trước đã xử lý chúng.
  - Chuẩn hóa chạy trước imputer (PRE-2).
- Monitoring chỉ đọc health card cuối, không thấy từng bước.

## 2. Quyết định chính

Năm bước, **đúng thứ tự, không đảo**:

```text
raw envelope (data/<nguồn>/raw/)
   │
   ▼  01 Clean           lọc phạm vi + khử trùng + bỏ rác, vẫn giữ dạng envelope
   ▼  02 Integration     làm phẳng về 18 trường chung, thiếu thì null
   ▼  03 Transformation  ép kiểu: lương số, ngày, số năm kinh nghiệm, text sạch; bù giá trị có cờ
   ▼  04 Normalization   thống nhất từ điển: thành phố, cấp bậc, nhóm nghề, kỹ năng; cap outlier, log lương
   ▼  05 Encoding        đổi sang số cho mô hình: one-hot, multi-hot, ordinal
```

- **Output của bước N là input duy nhất của bước N+1.** Không bước nào đọc lại `data/<nguồn>/raw/`, trừ Clean.
- Mỗi bước có hai chế độ:
  - `--dry-run`: chỉ đọc input, đếm luật nào sẽ tác động bao nhiêu dòng, ghi báo cáo. Không ghi dữ liệu. Monitoring dùng báo cáo này để hiện "sẽ xử lý gì".
  - chạy thật: ghi dữ liệu và báo cáo.

## 3. Layout file

| Bước | Dữ liệu (ghi trên máy) | Báo cáo (Monitoring đọc) |
|---|---|---|
| 01 Clean | `data/preprocessing/01_clean/<nguồn>.jsonl` (mỗi dòng một envelope) | `reports/preprocessing/01_clean/<nguồn>.json`, `…/_all.json` |
| 02 Integration | `data/preprocessing/02_integration/<nguồn>.parquet` | `reports/preprocessing/02_integration/…` |
| 03 Transformation | `data/preprocessing/03_transformation/<nguồn>.parquet` | `reports/preprocessing/03_transformation/…` |
| 04 Normalization | `data/preprocessing/04_normalization/<nguồn>.parquet`, gộp `all.parquet` | `reports/preprocessing/04_normalization/…` |
| 05 Encoding | `data/preprocessing/05_encoding/features.parquet`, `encoding_dictionary.json` | `reports/preprocessing/05_encoding/_all.json` |

- `_all.json` là báo cáo gộp 8 nguồn của bước đó. Các bước có việc chéo nguồn (khử trùng chéo nguồn ở Clean, gộp ở Normalization, Encoding) ghi vào đây.
- Bộ golden `data/curated/curated_flat_golden_jobs.parquet` (tên cũ, Monitoring đang đọc) = bản chép của `04_normalization/all.parquet`.
- `data/preprocessing/` không đưa vào git; `reports/preprocessing/` đưa vào git như các báo cáo pipeline khác.

## 4. Báo cáo bước (schema chung, mọi bước dùng)

Ví dụ lấy số TopDev đo 03/11: 3.890 snapshot, 2.782 tin sau khi giữ bản mới nhất.

```json
{
  "step": "01_clean",
  "source": "topdev",                 // hoặc "_all"
  "mode": "dry_run",                  // "dry_run" | "applied"
  "generated_at": "2026-11-03T10:00:00+00:00",
  "code_version": "<git short hash>",
  "input":  {"path": "data/topdev/raw/", "rows": 3890},
  "output": {"path": "data/preprocessing/01_clean/topdev.jsonl", "rows": 2782},
  "dropped": [{"rule": "C1", "reason": "Snapshot cũ của cùng job_id", "rows": 1108}],
  "rules": [
    {"id": "C1", "name": "Giữ snapshot mới nhất", "action": "drop",   // drop | flag | modify
     "rows_affected": 1108,
     "examples": [{"job_id": "topdev_123", "field": "snapshot_file", "before": "raw/2026-10-20/123_v1.json",
                   "after": "raw/2026-11-01/123_v2.json", "url": "https://topdev.vn/…"}]}
  ],
  "fields": [{"field": "job_title", "fill_pct_in": 100.0, "fill_pct_out": 100.0}],
  "checks": {"rows_conserved": true, "notes": []}
}
```

- **Luật bảo toàn:** `input.rows = output.rows + tổng dropped[].rows`. Sai thì bước dừng, không ghi output.
- `examples`: tối đa 3 ví dụ mỗi luật, lấy ổn định (sắp theo `job_id`) để hai lần chạy ra cùng ví dụ.
- `fields`: độ phủ trước và sau bước. Clean tính trên khóa đọc tạm (mục P1). Các bước sau tính trên cột thật.
- Mã luật có tiền tố theo bước: `C` Clean, `I` Integration, `T` Transformation, `N` Normalization, `E` Encoding.

## 5. Code

| Phần | Vị trí | Ghi chú |
|---|---|---|
| Driver mới | `scripts/run_preprocessing.py --step clean\|integration\|transformation\|normalization\|encoding\|all --source <nguồn>\|all [--dry-run]` | file mới |
| Ghi báo cáo bước | `preprocessing/common/step_report.py` | file mới: dựng dict theo schema trên, kiểm luật bảo toàn, ghi JSON |
| Đọc envelope mới nhất | dùng lại logic `latest_envelopes` trong `scripts/report_data_issues.py` (chuyển vào `preprocessing/common/raw_reader.py`) | không viết lại |
| Mỗi bước | `preprocessing/<bước>/run.py` có `run(source, dry_run) -> report` | |

Map thư mục cũ sang bước mới (chuyển dần trong từng phase, không chuyển hết một lúc):

| Code cũ | Về bước |
|---|---|
| `integration/json_flattener.py` | 02 Integration (Clean mượn để đọc khóa) |
| `missing_outlier/sneaky_null_detector.py` | 03 Transformation |
| `transformation/*` (lương, HTML, bullet, text_metrics) | 03 Transformation |
| `missing_outlier/genai_text_imputer.py` | không dùng trong pipeline 5 bước; bản cũ đã bỏ đường gọi Gemini, chỉ còn luật (mục 6) |
| `missing_outlier/outlier_handler.py` | 04 Normalization (cap trước khi log) |
| `normalization/text_cleaner.py`, `log_transformer.py` | 04 Normalization |
| `normalization/cross_deduplicator.py` | 01 Clean dùng luật chính xác; bản fuzzy để ở 04, chỉ bật nếu số liệu cho thấy cần |
| `transformation/text_metrics.filter_valid_clean_records` (bỏ JD rỗng) | 01 Clean |

`scripts/run_staging_integration_pipeline.py` giữ nguyên đến khi P5 xong và số liệu mới được duyệt, rồi mới xóa.

## 6. Không dùng model (cập nhật 04/11/2026)

Pipeline không gọi model hay LLM nào. Mọi phân loại là luật if-else, mọi chuẩn hóa là từ điển; chạy lại cho cùng kết quả, không tốn tiền, không cần khóa API. JEV (OpenCode) và Gemini đã bỏ (`docs/issue_log.md` L-28).

| Việc trước dùng model | Nay làm bằng |
|---|---|
| 01 Clean C4a: JEV hỏi tin có phải IT | Luật 2 tầng trong `preprocessing/common/it_filter.py`: tầng 1 từ khóa tiêu đề (`classify`); tin tầng 1 ra `unknown` thì tầng 2 (`classify_unknown`) xếp IT khi tiêu đề thuộc 12 nhóm nghề và JD có ≥ 2 kỹ năng. Lưu `it_rule_level` |
| 03 Transformation T6b, T6c: dịch JD tiếng Anh | Bỏ. Giữ `language`; kỹ năng rút bằng từ điển song ngữ |
| 04 Normalization N2b: JEV kiểm nhãn | Luật mâu thuẫn: Senior/Trưởng nhóm mà kinh nghiệm < 2 năm, Thực tập/Mới tốt nghiệp mà ≥ 3 năm → `seniority_can_kiem`; có nhóm nghề mà JD không có kỹ năng → `job_family_can_kiem` |
| 05 Encoding E8: xác suất JEV | Cờ 0/1 `it_rule_level__2`, `seniority_can_kiem`, `job_family_can_kiem` |

Báo cáo bước vẫn có khối `"api": {"used": false, "reason": "pipeline không dùng model (luật if-else)"}` để Monitoring đọc như cũ. Độ đúng của luật đo bằng nhãn tay (`data/preprocessing/review/it_<nguồn>.csv`), ghi ở `extra.review` của báo cáo Clean.

## 7. Ranh giới

| Bước | Được làm | Cấm |
|---|---|---|
| 01 Clean | bỏ dòng (trùng, test, JD rỗng), gắn cờ | sửa nội dung trường, làm phẳng output, **bỏ tin ngoài IT khi chưa có `it_policy.json` đã duyệt** (P1 C4c) |
| 02 Integration | ánh xạ trường, làm phẳng, đọc fallback (JSON-LD) | parse số, đổi tiền, bỏ dòng, bù giá trị |
| 03 Transformation | ép kiểu, parse lương/ngày/kinh nghiệm, null trá hình → null, bù có cờ | bỏ dòng, cap outlier, log |
| 04 Normalization | từ điển chuẩn, cap outlier, log, gộp nguồn | bỏ dòng (trừ fuzzy dedup nếu được bật), ghi đè nhãn gốc (giữ cột `raw_*`) |
| 05 Encoding | đổi sang số, ghi từ điển mã hóa | đổi giá trị đã chuẩn hóa |

## 8. Monitoring thấy gì

Báo cáo bước là nguồn số duy nhất. Đặc tả trang: `docs/spec/monitoring/preprocessing_page_spec.md`.

## 9. Tiêu chí xong

- `python scripts/run_preprocessing.py --step clean --source glints --dry-run` ghi được báo cáo đúng schema, chưa cần luật nào (rules rỗng, `output.rows = input.rows`).
- Test: báo cáo sai luật bảo toàn thì bước dừng; `examples` ổn định giữa hai lần chạy; schema có đủ khóa.
- `.gitignore` có `data/preprocessing/` (gồm cả `_cache/`).
- Test cache: cùng đầu vào gọi hai lần thì lần hai không gọi mạng (mock client).
