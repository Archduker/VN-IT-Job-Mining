# scripts/CLAUDE.md

Script vận hành và tiện ích. Trước khi chạy script nào, xem nó thuộc nhóm nào dưới đây. **Ghi hoặc xóa trên R2 phải chạy thử trước, gửi số liệu cho người dùng, và chỉ chạy thật khi người dùng đồng ý.**

## Chỉ đọc (chạy thoải mái)

| Script | Việc |
|---|---|
| `audit_raw_data.py [--r2]` | Báo cáo chất lượng raw và ledger ra `reports/data_audit_<ngày>.md` (không đưa vào git). Đọc kỹ cột "Ledger chậm hơn raw", "DONE thiếu raw" (đã trừ repost), "Raw ngoài ledger" |
| `report_data_issues.py` | Thống kê vấn đề dữ liệu raw sau làm phẳng (trùng lặp, độ phủ trường, lương, ngày…), ghi `docs/spec/preprocessing/data_issues_2026-11-03.html`. `compute()` trả dict để Monitoring dùng lại |
| `report_raw_problems_r2.py [--from-json]` | Đo vấn đề dữ liệu raw **trực tiếp trên R2** (chỉ `list_objects_v2` và `get_object`), ghi `docs/presentation/raw_problems_r2.json` và bộ slide `slides_raw_problems.html` (mục A vấn đề raw, mục B cách xử lý). `--from-json` dựng lại slide mà không gọi R2 |
| `read_eda_diagnosis.py --source <nguồn>` | Đọc luật EDA từ notebook mà không mở notebook |
| `report_skills_overview.py [--out]` | Đọc bảng 04, so kỹ năng phương án A (chỉ văn bản gốc) với B (gốc + bản dịch), ghi HTML tĩnh `data/processing/skills_overview.html` (DF, độ phủ, mức cắt min_df) |
| `plot_weight_views.py [--out]` | SD3: PCA 2D/3D của không gian phân cụm theo 4 bộ trọng số công cụ / khái niệm / e5, tô theo 7 nhóm và vai trò con, kèm độ đúng kNN; ghi `docs/presentation/weight_views.html` (L-62). Chỉ đọc dữ liệu trên máy |
| `visualize_raw_bronze.py [--source]` | Trực quan hóa Bronze trên máy (raw + ledger) của từng nguồn ra `docs/presentation/raw_bronze/<nguồn>.html` và `index.html`: tháng đăng, tháng cào, trạng thái ledger, khóa `raw_payload`, độ phủ 25 trường sau làm phẳng, top giá trị, phúc lợi, độ dài văn bản. Không gọi R2 |
| `visualize_preprocessing_steps.py [--step]` | Trực quan hóa từng bước 01 → 04 ra `docs/presentation/preprocessing_steps/`: số dòng theo nguồn, luật (so với report trong git HEAD), độ phủ từng trường theo nguồn đo trên `data/preprocessing/<bước>/`, mẫu trước/sau, phần `extra` của report. Bước chưa có đầu ra trên máy ghi "chưa chạy lại". Khung HTML dùng chung ở `_viz_html.py` |
| `mine_jd_phrases.py [--out]` | Gom câu ứng viên trong JD theo chủ đề (hình thức làm việc, loại hợp đồng, kinh nghiệm, giờ làm, lương) từ bảng 03 ra `data/preprocessing/jd_phrases/<chủ đề>.tsv`, để dựng từ điển |
| `build_step_samples.py [--job] [--step]` | Dựng dữ liệu mẫu cho đặc tả từng bước: `docs/spec/preprocessing/samples/<bước>.json` (số vào/ra theo nguồn, luật kèm ví dụ, schema, trạng thái của tin mẫu `topcv_2325743` ở bước đó). Bỏ qua bước chưa có đầu ra trên máy |
| `review_jd_dictionary.py` | Đo `preprocessing/dictionaries/jd_extraction.json` trên bảng 03 (số tin theo luật và nguồn, ca lệch raw ↔ JD) và sinh trang duyệt `docs/presentation/preprocessing_steps/jd_dictionary.html` |
| `review_skills_v2.py` | Đo `processing/dictionaries/skills_v2.json` (kể cả bản nháp) trên bảng 02 bằng matcher như bước 08 (alias đúng dấu, chặn cụm bằng cấp, chặn "Go-live"), ghi `data/processing/skill_candidates/skills_v2_measure.json` và trang duyệt `docs/presentation/processing_steps/skills_v2.html`. `build_skills_v2.py` (ghi trên máy) dựng từ điển từ các lô quyết định |
| `eval_it_filter.py [--rule old\|new\|both] [--grid]` | Đo bộ lọc IT (C4a) trên nhãn C4b: luật cũ, luật ba tầng theo `preprocessing/dictionaries/it_filter_v2.json` (đo được cả bản chưa duyệt), lưới ngưỡng tầng 2 trên tập tune. Đọc raw trên máy, ghi `data/preprocessing/review/it_filter_eval.json`. Chỉ chọn ngưỡng trên tập `tune`; tập `giu_lai` để báo số |
| `eval_skill_views.py [--out-json] [--out-csv]` | Đo ba góc nhìn kỹ năng (`skill_view`: all, technical, tool, concept, soft) theo ngưỡng T1–T6 của `docs/target/06_yeu_cau_du_lieu.md`, cả coverage@10 tin người mới. Đọc `job_skills.parquet` (cần cột `type`), Silver, bullet 07, dữ liệu ngoài `data/external/vnjt/`. Ghi `data/processing/skill_candidates/skill_views_eval.json` và 100 cặp đọc tay `tool_check_100.csv` (seed 42). CSV đã điền cột `dung` thì không ghi đè, chỉ tính T4 từ đó |
| `view_urls.py [--r2] [--status]` | Xem ledger trên máy hoặc trên R2 |
| `sync_cloud_lakehouse.py --status` | So máy với R2 |
| `sync_cloud_lakehouse.py --download [--source]` | Tải R2 về `data/` (chỉ ghi trên máy). Có `--source` thì **chỉ tải ledger**, không tải raw (PRE-42) |
| `lakehouse_loader.py` | Nạp raw thành DataFrame, có thể tải bù từ R2 |
| `migrate_lakehouse_layout.py [--r2]` | Không có `--apply` thì chỉ liệt kê key layout cũ sẽ được chuyển |
| `reconcile_ledger_from_raw.py --source <nguồn>` | Không có `--apply`/`--push` thì chỉ in kế hoạch |

## Ghi trên máy

| Script | Việc |
|---|---|
| `reconcile_ledger_from_raw.py --apply` | Dựng lại ledger từ raw: tạo bản ghi thiếu, cập nhật bản ghi có raw mới hơn. Không hạ `CLOSED`, không xóa bản ghi; repost cũ có snapshot mới thì bỏ `repost_of_url_hash` |
| `label_tool.py [--source] [--web] [--stats] [--auto-obvious] [--generate-policy]` | Tool gán nhãn tay cho review C4b (`data/preprocessing/review/it_<nguồn>.csv`), hỗ trợ TUI 1 phím bấm và Web UI nhanh |
| `propose_skill_types.py [--min-df 5] [--batch-size 150] [--check]` | Đề xuất nhãn `tool`/`concept` cho kỹ năng kỹ thuật của skills_v2 (K8.17): ghi lô `processing/dictionaries/skills_v2_decisions/types_t<NN>.json` (không ghi đè lô đã có) và trang `docs/presentation/processing_steps/skill_types.html`. Áp danh sách Claude đọc lại `types_claude.txt`. Bằng chứng ngoài đọc `data/external/vnjt/step07.jsonl` qua `_vnjt.py` (dữ liệu LLM sinh, không license: chỉ đối chiếu, không trộn vào từ điển, không đưa vào git) |
| `run_preprocessing.py --step <bước>\|all --source <nguồn>\|all [--dry-run] [--translate]` | **Driver chuẩn.** Chuỗi pre-processing 01→04 rồi Processing 07, 08, 10, 12_e5 (`CHAIN`; `12_e5` cần GPU và model e5 đã tải) (spec 05, 06). `09_tokens`, `12_tfidf` bỏ khỏi chuỗi 19/11; `STEPS` còn `05_encoding` (đã bỏ nhưng chưa gỡ code, PRE-39). 07 và 08 do một lần gọi, chạy một trong hai thì cả hai báo cáo được gắn mẫu (L-53). Ghi `data/preprocessing/<bước>/`, `reports/preprocessing/<bước>/` (Monitoring đọc), mẫu gán nhãn `data/preprocessing/review/`. Không gọi model: phân loại là luật if-else. Từ bước 02 dữ liệu gộp 8 nguồn trong một file `all.parquet` |
| `run_staging_integration_pipeline.py` | **Pipeline cũ, không dùng cho việc mới** (đánh dấu 17/11/2026). Chuỗi chuẩn là `run_preprocessing.py`. Script cũ ghi `data/staging/`, `data/curated/curated_flat_golden_jobs.parquet`, `reports/<nguồn>/`, theo nhãn cũ (12 Job Family, 6 bậc, 63 tỉnh) |
| `create_golden_master_eda_notebook.py` | Sinh notebook EDA cho bộ golden |
| `build_mining_charts.py [--inject]` | Vẽ biểu đồ từ `mining/artifacts/` (bản đồ tương tác 7 nhóm + Khác, thẻ cụm con theo nhóm, vai trò con so với danh sách, ARI theo nhóm, giá trị kỹ năng SHAP) ra `docs/presentation/charts/`; `--inject` chèn vào `docs/presentation/final_slides.html` giữa các chú thích `<!-- chart:<tên> -->`. Chạy lại sau mỗi lần chạy Mining |
| `build_slides.py [--save-before <parquet>]` | Sinh slide thuyết trình `docs/presentation/slides.html` từ báo cáo 5 bước, `docs/presentation/data/*.json` (số trước sửa) và `compute()` của `report_data_issues.py`. Dừng nếu bảng vấn đề ↔ luật (`ISSUE_TO_RULES`) lệch với luật trong báo cáo. Chạy lại sau mỗi lần chạy pipeline |

## Ghi hoặc xóa trên R2 (phải chạy thử và được đồng ý)

| Script | Chạy thử | Việc |
|---|---|---|
| `push_raw_to_r2.py` | `--dry-run` | Đẩy raw trên máy lên R2, rồi đẩy ledger qua `ledger_push_decision()` (từ chối khi catalog trên máy rỗng, bản R2 mới hơn, hoặc R2 có URL mà máy không có) |
| `reconcile_ledger_from_raw.py --push` | chạy không cờ | Ghi trên máy, sao lưu bản R2 vào `data/<nguồn>/url_ledger/backups/`, rồi đẩy |
| `reconcile_ledger_from_raw.py --source <nguồn> --register-batch-missing <file batch> --push` | bỏ `--push` | Kéo ledger từ R2, đăng ký `PENDING` cho tin trong file batch cũ chưa có file riêng và chưa có trong ledger, sao lưu rồi đẩy. Chạy thử xong thì `--push` thẳng: chạy `--apply` trước thì lần `--push` sau không còn gì để đẩy |
| `migrate_lakehouse_layout.py --r2 --apply` | bỏ `--apply` | Chép key layout cũ sang layout chuẩn, **xóa** key cũ |
| `sync_cloud_lakehouse.py --upload` | `--status` | Đẩy cả `data/` (gồm staging, curated) |
| `push_integration_to_r2.py` | — | Đẩy kết quả integration |
| `push_preprocessing_to_r2.py --push [--delete-obsolete]` | chạy không cờ | Đẩy output 3 giai đoạn: Pre-processing `staging/<nguồn>/preprocessing/<bước>.*` (bảng gộp tách theo nguồn) và `pipeline/02..04/` (gồm `silver.parquet`); Processing `pipeline/07_sections`, `08_skills`, `10_features`, `12_e5` (bỏ `cache/`); Mining `curated/mining/<file>` (cả `mining/artifacts/`). Chỉ đẩy key chưa có hoặc lệch (so `generated-at` và số dòng trong metadata). `--delete-obsolete` xóa key dưới `staging/`, `pipeline/`, `curated/` mà máy không còn sinh ra (không bao giờ đụng `raw/`, `url_ledger/`). Bố cục: `preprocessing/common/r2_export.py`. Đã đẩy lần đầu 23/11/2026 (78 object, xóa 5 key cũ của bước 05 và pipeline cũ) |
| `check_r2.py` (`make check-r2`) | — | Ghi rồi xóa ngay một key thử để kiểm quyền |
| `setup_cloud_storage.py` | — | Ghi khóa R2 vào `.env`, tạo bucket nếu chưa có |

**Bẫy `push_preprocessing_to_r2.py` (25/11, L-62):**
- Script so file bằng `generated-at` và số dòng, không so nội dung. Ghép lại artifact mà giữ `generated_at` cũ thì file đổi nội dung vẫn báo "khop".
- Script đẩy mọi thứ có trên máy. Máy có `data/preprocessing/02–04`, `07_sections` cũ hơn R2 thì `--push` sẽ đè bản cũ lên R2.
- Trước khi `--push`: so MD5 với ETag trên R2, và tải bản mới về máy trước.

## Cào thật (cần người dùng đồng ý)

- `drain_topcv_loop.py`: vòng lặp chạy nền, cứ 20 phút cào 30 tin TopCV và đẩy lên R2. Không chạy khi chưa được yêu cầu.
- `start_airflow.sh`, `airflow_ctl.sh`: bật scheduler, tức là cào thật. Xem `airflow/CLAUDE.md`.
- `setup_airflow.sh`, `setup_airflow_connections.py`, `setup_ec2.sh`: cài đặt môi trường.

## Lưu ý khi viết script mới

- Kết nối R2 qua `collection.common.r2_storage.get_r2_client()` và `resolve_r2_bucket()`. Không tự tạo `boto3.client` hay đọc biến môi trường riêng (ngoại lệ duy nhất: `setup_cloud_storage.py` thử khóa người dùng vừa nhập): ledger từng đọc khóa theo thứ tự khác với raw nên đẩy sai chỗ (`docs/issue_log.md` L-01).
- Key R2 đi qua `canonicalize_lakehouse_key`.
- Bước ghi thật đặt sau cờ `--apply` hoặc `--push`; mặc định là chạy thử.
- Không in giá trị trong `.env`; muốn so hai khóa thì so hash.
- Test script ở `tests/integration/`, dữ liệu trong `tmp_path`, R2 thì mock.
