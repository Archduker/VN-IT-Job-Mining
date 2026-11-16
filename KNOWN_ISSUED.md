# Known Issues

Việc còn tồn đọng, rà lại ngày 10/11/2026 sau đợt pipeline PH0–PH9 (bằng chứng các mục đã đóng ở `docs/issue_log.md` L-38). Danh sách việc phát sinh từ merge 7 nhánh: `docs/tasks/issues_merge.md`. Xử lý xong mục nào thì chuyển sang `docs/issue_log.md` theo khuôn Lỗi → Nguyên nhân → Cách xử lý → Kiểm chứng (xem `docs/CLAUDE.md`), rồi xóa khỏi đây.

Thứ tự làm của dự án: **web scraping → trực quan hóa dữ liệu → pre-processing**.

## 1. Web scraping

Kiểm tra dữ liệu bằng `python scripts/audit_raw_data.py --r2` (ghi `reports/data_audit_<ngày>.md`, không đưa vào git).

**SCRAPE-1. Chưa kiểm tra với Airflow thật**

- Trạng thái Phase 1 đọc từ `task_instance`, Phase 2 từ `dag_run` (`monitoring/backend/app/services/airflow_service.py`). PostgreSQL của Airflow chưa chạy được vì user chưa có quyền docker.
- Cách xử lý: `sudo usermod -aG docker $USER`, đăng nhập lại, rồi `./start_monitoring.sh`.

**SCRAPE-5. Dữ liệu cũ chờ cào lại** (gộp SCRAPE-5, 7, 16; cần ghi R2 nên phải có đồng ý)

- TopDev: raw cũ thiếu kinh nghiệm, cấp bậc, ngày đăng (F5 21%, F6 0%, F8 29%). Code đã sửa 02/11 (`DETAIL_FIELDS`); tin nào cào lại sẽ có đủ, lần đầu sinh version mới vì hash đổi.
- Glints: 331 tin chưa cào lại từ 20/10, đến hạn hàng loạt từ 10/11.
- TopCV: 297 tin cào 22–26/10 không có JD trong raw (244 trang `/viec-lam/`, 53 trang `/brand/`, có cả tin IT thật). Bước Clean đang bỏ theo luật C5. Nhánh Khoa có fallback 4 tầng, chưa kiểm trên HTML thật, chưa có script backfill. Cách xử lý: tìm vì sao không lấy được JD, đưa về `PENDING` để cào lại (chạy thử, gửi số liệu, chờ đồng ý).

**SCRAPE-13. Thời gian nghỉ giữa request lệch chuẩn 2,0–4,5 giây (C10)**

- JobsGO 1,5–3,0 s; VietnamWorks 1,2–2,2 s và `time.sleep(0.3)` cố định; TopDev 1,0–2,5 s. **Đã chốt 09/11: nâng cả ba lên 2,0–4,5 s** (hệ quả: cào chậm hơn).
- `tests/contract/standards.check_random_pause` mới kiểm tên hàm, chưa kiểm ngưỡng số; sẽ báo nhầm CareerViet (nghỉ qua `DelayConfig`).

**SCRAPE-14. Contract test cho 6 nguồn còn lại**

- Đã có fixture TopDev, TopCV (`tests/fixtures/`). Còn VietnamWorks, CareerViet, Vieclam24h, ITviec, Glints, JobsGO; mỗi nguồn cần 3 mẫu thật (xem `tests/CLAUDE.md`), cần mạng.

**SCRAPE-15. TopDev cào cả tin ngoài IT; lọc IT còn import ngược từ `preprocessing`** (gộp SCRAPE-15, 18)

- `topdev/crawler.py:_fetch_listing` gửi `category_ids=1` nhưng API `/td/v2/jobs` bỏ qua tham số này (đo 03/11: có hay không đều 14.572 tin). Mỗi lượt cào vẫn tốn request cho tin không dùng.
- **Đã chốt 09/11: bỏ lọc IT ở bước thu thập, để bước Clean lọc.** Còn việc gỡ `from preprocessing.common.it_filter import classify` (`:44`), `filter_it` (`:1620`) và bước lọc (`:1657`), sửa contract test. Tìm tham số lọc ngành đúng của API cần gọi thật.

## 2. Trực quan hóa dữ liệu

**VIZ-6. `/insights` chưa kiểm với dữ liệu Mart thật** (nhánh Sơn)

- Mart rỗng, test mock query.

**VIZ-7. Chưa kiểm giao diện sau merge** (nhánh Sơn)

- Chưa chạy `./start_monitoring.sh --check` và kiểm 390 px; bundle JS 778 kB cần tách code. Tiêu đề trang vẫn ghi "5 bước" (`monitoring/frontend/src/App.tsx`); lệnh tạo báo cáo cho bước 07–09 trên giao diện còn trống.

## 3. Pre-processing và Processing

Các mục PRE-1…PRE-10, 16–19, 22, 28, 29 đã đóng hoặc bị phương án mới thay (L-27, L-28, L-36, L-38); PRE-13 và PRE-15 gộp vào PRE-12; PRE-14 viết lại thành việc đồng bộ ADR-04. Số PRE-30 và PRE-31 để trống.

**PRE-12. Bộ lọc IT: nghiệm thu và cổng tầng 2**

- Có 643 nhãn tay (182 IT, 461 không IT); độ đúng luật 92,4%, tầng 2 IT 55/71, chưa tính khoảng tin cậy; yêu cầu lead ≥95% kèm khoảng tin cậy chưa chốt điều kiện cận dưới. Chi tiết `docs/presentation/van_de_can_chot.html` mục 4 và `docs/tasks/02_tai_clean_and_deduplication.md` §5.8.
- Tầng 2 (`preprocessing/common/it_filter.py:86-95`) dùng nhóm nghề tự suy từ tiêu đề + JD, không đọc `raw_category_text` như SPEC-05 §2.4. Lead chưa chọn (A) gate bằng chuyên mục sàn, (B) miễn trừ có ghi dấu, hay (C) chuyên mục chỉ là tín hiệu ưu tiên.
- Đã quyết 10/11: không dùng model để phân loại IT, chấp nhận nguyên trạng các tin bị loại.

**PRE-25. `ledger.csv` bị `.gitignore` (`*.csv`)**

- `preprocessing/encoding/cohort.py`, `finalize_cohort.py` đọc nó nên clone sạch không chạy lại được. Đã chốt: chưa sửa, pipeline mới không dùng cohort.

**PRE-26. `reports/preprocessing/05_encoding` phình git**

- 70 file được track, 4,6 MB (pickle, npz, notebook HTML), trái quy tắc về `reports/`. Người dùng chấp nhận tạm.

**PRE-34. Bước 10–12 chưa làm và chưa có đánh giá**

- Code 10, 10b, 10c, 10d, 12 đã xong và chạy thật 11/11 (L-44). Bước 11 (train/test) bỏ có chủ đích vì mining unsupervised; e5 đã xong (L-45).
- Việc xử lý sau: đánh giá hiệu quả 10–12 (min_df, ngưỡng bin lương, đặc trưng 10c có ích cho cụm/luật không, TF-IDF so với e5). Tiêu chí chọn đặc trưng ngoài min_df chưa chốt.
- Tách bullet (bước 07): 399/400 tin careerviet chỉ ra đúng 3 bullet (mỗi section một khối, luật S7.2) nên bullet và e5 của careerviet thô hơn các sàn khác (trung vị chung 23 bullet/tin). Chưa tìm nguyên nhân (HTML bị làm phẳng ở 02/04 hay luật tách chưa bắt được dấu ngắt dòng của careerviet).
- Cờ mâu thuẫn cấp bậc ↔ kinh nghiệm (`seniority_can_kiem`, 115 tin ≈ 2,5%): giữ thành cột ở `10_features`, không bỏ dòng; Mining tự lọc.
- Dịch EN→VI: 222/1.274 tin tiếng Anh vẫn `failed` (giữ bản gốc); chạy lại 03 không thêm cache mới (34.195 dòng không đổi), nguyên nhân chưa rõ (`is_valid` trong `preprocessing/translation/core.py`).

**PRE-33. Việc chờ người dùng**

- Gán nhãn 100 JD gold: **đã xong 11/11** (4 file người dùng gửi, gộp thành `data/preprocessing/gold/gold_labels.json`, qua `load_gold`). Không dựng lại `gold_sample.json` (nhãn gắn mẫu `e58bceb3a5`; dựng lại là mất khớp). Số đo sơ bộ: section 84,5%, phúc lợi P 0,97/R 0,60, kỹ năng F1 0,27 (nghi một phần do so khớp tên kỹ năng với slug); cần xem lại cách đo kỹ năng và 5 cờ `flags` của file 76–100.
- Duyệt từ điển JSON: `abbreviations.json`, `job_titles.json` (53 mục đã duyệt 11/11, 87 mục còn `approved: false`), `scope_keywords.json`, các file candidate ở `processing/dictionaries/` (sao bản duyệt sang `section_headings.json`, `priority_cues.json`, `short_aliases.json`). `no_translate.json` đã duyệt đề xuất 10/11.
- 50 cặp dedup: người dùng duyệt "ổn rồi" 11/11 (không chấm từng cặp); sinh lại bằng `scripts/build_dedup_pairs_sample.py`. Hướng chưa làm: chuẩn hóa tên công ty (MBBANK = Ngân hàng TMCP Quân đội) để bắt các cặp khác nguồn.
- Kiểm tay 50 JD dịch sau khi dịch xong (`scripts/build_translation_review_sample.py`). Lỗi đã biết: mô hình làm rơi dấu "+" ("5+ years" → "5 năm") và đổi định dạng số.
- Chọn ngưỡng `min_df` (đề xuất 10–20, mặc định dự kiến 15).
- Đã chốt 11/11: Data Analyst/BI thuộc Data Science/AI; dưới 1 năm kinh nghiệm là Intern/Fresher (mặc định; kiểm lại ~317 tin itviec "0,8 năm (10 tháng)" sau khi chạy lại 04).

## 3b. Data Mining

**MINE-1. Mining đã chạy thật lần đầu (11/11), kết quả cụm yếu, chưa đánh giá**

- Chạy fp, cluster, anomaly trên 4.671 tin (L-46): Silhouette 0,091, DB 2,63, ARI với nhóm nghề 0,056; sanity 4/6 fail (Flutter→Dart conf 0,375; React→JS|TS 0,654; lương Senior < Middle; tỉ lệ lương HN/HCM). Chưa rõ do dữ liệu hay ngưỡng kiểm; chưa chỉnh tham số. Bước `salary` (Random Forest + SHAP) là supervised, lệch quy trình chuẩn, chưa chạy và chưa quyết bỏ hay giữ.
- Dòng cũ bên dưới (số giả từ `synthetic.py`) chỉ đúng cho báo cáo trước đó.
- 11/11 (L-47): 10 family, K-Means k=10: Silhouette 0,10, DB 2,49, ARI 0,07; cụm 1 chứa 292/293 tin không có kỹ năng, cụm 9 là cụm nhiều kỹ năng (trung vị 15): phân cụm một phần tách theo số kỹ năng. Chưa thử IDF cho kỹ năng, chưa lọc tin không có kỹ năng.

- Số trong báo cáo là dữ liệu giả từ `mining/synthetic.py`. Nhãn đã căn theo 5 cấp, 12 nhóm + Other nhưng chưa chạy trên `04_normalization/all.parquet` thật.

**MINE-4. Khoảng k chưa thống nhất:** task 6–12, checklist 4–14, spec 07 3–15; code dùng 4–14. Người dùng chưa quyết.

**MINE-5. `load_mart_from_parquet.py` biến cột list thành chuỗi;** chưa có bảng `skill_salary_shap_values`. Script và `scripts/build_slides.py` còn dùng nhãn cũ ("Khác", 6 bậc).

**MINE-6. Ghi chú cho báo cáo đồ án:** SHAP không phải quan hệ nhân quả; `seniority_level` 0–4 gộp Thực tập và Mới tốt nghiệp.

## 4. Chung

**GEN-1. Khoảng 1.300 lỗi ruff tồn đọng** ở `collection/` và `tests/`. Dọn thành một lượt riêng.

**GEN-2. `README.md` và `docs/tasks/legacy_TASKS.md` lệch code.** Chi tiết ở "Known mismatches" trong `CLAUDE.md`.

**GEN-3. Dọn code theo `docs/code_quality.md`** (`make quality`): import thừa, hàm không ai gọi, module không ai import. Người dùng duyệt từng mục trước khi sửa.

**GEN-4. Layout R2: còn lệch spec 10 và chưa đẩy kết quả PH9**

- Đã chốt và làm 10/11 (L-33): R2 chỉ còn `url_ledger/ raw/ staging/ curated/ pipeline/`. `r2_export.plan_objects()` liệt kê key `pipeline/<bước>/...`. Chưa push `staging/ curated/ pipeline/` (cần dry-run, rồi người dùng duyệt); người dùng cần tự upload `pipeline/.keep` ở dashboard Cloudflare.
- Còn lệch: `canonicalize_lakehouse_key` từ chối `staging/all.parquet` (bắt buộc tên nguồn ở cấp 2); `features.parquet` đang ở `curated/preprocessing/features.parquet` (spec 10 ghi `gold/features.parquet`) và `mining/config.py` đã đọc `data/processing/10_features/features.parquet` (L-46); `scripts/push_integration_to_r2.py` ghi `integration/...` ngoài 5 tiền tố.

**GEN-7. Code tải R2 tự dựng trong `preprocessing/integration`**

- `integration/run.py:102-104` và `run_integration.py:161-163` gọi `boto3.client` trực tiếp, bucket mặc định `vn-it-jobs` gán cứng, không qua `get_r2_client()`.

**GEN-8. Mẫu báo cáo nghiệm thu chưa điền** ở `docs/tasks/` của Duy, Phúc, Sơn (mục 5 của mẫu).

**GEN-10. 4 test integration fail từ merge nhánh Sơn (MERGE-10)**

- `test_monitor_eda_r2::test_empty_remote_has_no_local_fallback`, hai test collection trong `test_monitor_endpoints`, `test_pipeline_reports::test_eda_charts_from_staging_parquet` (chi tiết `docs/tasks/issues_merge.md`). Cần kiểm lại có đúng thuộc MERGE-10 không.
