# preprocessing/CLAUDE.md

Ngữ cảnh khi làm việc với pre-processing. Thiết kế đầy đủ: `docs/spec/preprocessing/00_architecture_overview.md` (đọc ma trận ranh giới các bước trước khi chuyển logic giữa các bước).

Thứ tự làm của dự án là web scraping → trực quan hóa → pre-processing. **Phần này đang để sau:** chỉ sửa khi người dùng yêu cầu rõ.

**Refactor đang đặc tả (03/11/2026):** 5 bước Clean → Integration → Transformation → Normalization → Encoding, output bước trước là input bước sau, mỗi bước ghi báo cáo cho Monitoring. Đặc tả: `docs/spec/preprocessing/spec/`; prompt: `docs/prompting/`. Khi refactor xong, bảng "Cấu trúc" dưới đây sẽ thay đổi. Đã chốt: địa điểm theo 34 tỉnh sau sáp nhập (JSON 3 cấp); tin ngoài IT chỉ bỏ theo `preprocessing/clean/it_policy.json` do người dùng duyệt; **không dùng model/LLM nào** (04/11/2026): phân loại là luật if-else, không dịch JD.

## Pipeline 5 bước (đang làm)

- Driver `scripts/run_preprocessing.py`; mỗi bước là `preprocessing/<bước>/run.py` với `run(sources, dry_run)`. Đủ 5 bước, chạy thật 04/11/2026: 14.292 bản ghi raw → 5.177 tin IT.
- Bước Clean ghi theo nguồn (`01_clean/<nguồn>.jsonl`); **từ Integration dữ liệu gộp 8 nguồn trong một file `all.parquet`** (cột `source_platform`). Bước 03/04 `groupby` theo nguồn để báo cáo vẫn có số theo nguồn.
- Không ghi vào `data/curated/` (file golden của pipeline cũ). Đẩy silver/gold lên R2 bằng `scripts/push_preprocessing_to_r2.py` (bố cục trong `common/r2_export.py`).
- Phân loại IT là luật 2 tầng (`common/it_filter.py`: `classify` từ khóa tiêu đề, `classify_unknown` nhóm nghề + ≥ 2 kỹ năng JD); tầng 2 đúng khoảng 82% trên nhãn tay. Normalization gắn cờ `*_can_kiem` bằng luật mâu thuẫn. Không thêm lại lời gọi model khi người dùng chưa yêu cầu.
- Từ điển trong `dictionaries/`: `provinces_34.json`, `wards_34.json` (3.321 phường/xã mới, MIT, nguồn ghi trong file), `skills.json`, `benefits.json`. Tên kỹ năng ngắn (C, R, Go) chỉ được thêm kèm ngữ cảnh.
- `common/`: `step_report.py` (schema báo cáo, luật bảo toàn input = output + bị bỏ), `raw_reader.py`, `province.py` + `dictionaries/provinces_34.json`, `it_filter.py`.
- File mẫu gán nhãn `data/preprocessing/review/it_<nguồn>.csv` đã có nhãn tay thì không bao giờ bị ghi đè.

## Cấu trúc (pipeline cũ)

`preprocessing/` là thư viện các hàm theo bước; driver nằm ở `scripts/run_staging_integration_pipeline.py`, chạy từng nguồn rồi gộp:

| Bước | Thư mục | Việc |
|---|---|---|
| Integration | `integration/` | `json_flattener.py` làm phẳng raw theo `_flatten_<nguồn>`; `run_integration.py` chỉ chạy bước này |
| Transformation | `transformation/` | parse lương (`salary_parser.py`), làm sạch HTML và bullet |
| Missing / Outlier | `missing_outlier/` | null trá hình, bỏ JD rỗng, bù giá trị bằng luật (`genai_text_imputer.py`, tên cũ), cap outlier |
| Normalization | `normalization/` | chuẩn hóa text, log transform, khử trùng chéo nguồn |

Mỗi nguồn ra 3 file: `<nguồn>_flat_clean.parquet`, `reports/<nguồn>/<nguồn>_quality_health_card.json`, `reports/<nguồn>/<nguồn>_transformation_manifest.md`. Bộ golden là `data/curated/curated_flat_golden_jobs.parquet`.

## Quy tắc

- **Ranh giới bước là hợp đồng.** Integration không parse lương, không đổi tiền tệ, không bỏ dòng, không bù giá trị. Transformation không xóa outlier, không bù. Missing/Outlier không bù bằng mean hoặc median. Normalization không scale trước khi xử lý outlier.
- **EDA trước.** Luật của từng nguồn rút từ `collection/reports/EDA_<nguồn>.ipynb`. Đọc bằng `python scripts/read_eda_diagnosis.py --source <nguồn>`, không mở notebook (chứa ảnh base64 rất lớn).
- Lương thỏa thuận giữ `NaN` kèm cờ (MNAR). Outlier được cap, không xóa. Giá trị bù (bằng luật, pipeline cũ) có cờ `is_imputed_by_genai` (tên cũ, không còn gọi Gemini).
- **Raw là bất biến:** sửa cách đọc một trường thì sửa ở đây, không sửa file raw. Raw TopDev cũ thiếu F5, F6, F8 (SCRAPE-5) nên flattener phải chịu được trường vắng.
- `_flatten_<nguồn>` phải khớp `monitoring/backend/app/core/feature_targets.py` (`RAW_PATHS`). Đổi tên trường ở một bên thì sửa cả bên kia.
- Thêm nguồn mới: thêm `_flatten_<nguồn>` và tên nguồn vào `SOURCES` ở `run_staging_integration_pipeline.py`, `integration/run_integration.py`, `scripts/read_eda_diagnosis.py`.

## Dữ liệu đầu vào

- Đọc `data/<nguồn>/raw/`, nên chạy `python scripts/sync_cloud_lakehouse.py --download` trước.
- File batch cũ `data/vieclam24h/raw/2026-10-20/batch_001.json` và `data/vietnamworks/raw/2026-10-16/raw_batch.json` gom nhiều tin, trùng với file từng tin. Bước Clean đã khử trùng theo `job_id`, ưu tiên file từng tin (luật C2, `docs/issue_log.md` L-25).
- Repost không có file raw; ledger ghi `repost_of_url_hash`.

## Việc còn mở

`KNOWN_ISSUED.md` mục 3: PRE-11 (chờ chốt hướng cho mô hình). PRE-9, PRE-10 (JEV, dịch) hết vì đã bỏ model (L-28). PRE-1 đến PRE-7 của pipeline cũ đã hết (`docs/issue_log.md` L-27).

Chạy lại pipeline thì so số trước và sau, rồi mới đẩy lên R2 (`scripts/push_integration_to_r2.py`, `scripts/sync_cloud_lakehouse.py --upload`; cả hai đều ghi lên R2).
