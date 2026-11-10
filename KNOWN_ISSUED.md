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

**SCRAPE-8. Tin CLOSED vẫn được lưu raw mới**

- Ví dụ: VietnamWorks `2118352` CLOSED từ 20/10 nhưng có raw ngày 01/11. Code hiện kiểm `is_job_closed_or_expired` sau khi tải trang (`collection/sources/vietnamworks/crawler.py:944`). Chưa biết tin đăng lại hay crawler cũ; cần dữ liệu R2.
- Cách xử lý: bỏ qua tin đã `CLOSED` trong ledger trước khi tải, kèm test.

**SCRAPE-11. Discovery lỗi toàn trang mà vẫn báo thành công (5 nguồn)**

- Chỉ TopCV, TopDev, VietnamWorks có `DiscoveryError` (C14; VietnamWorks chưa có test). CareerViet, Vieclam24h, ITviec, Glints, JobsGO chưa có; làm cùng contract test từng nguồn.

**SCRAPE-12. Việc nhỏ khi cào thử 03/11**

- JobsGO: in `RuntimeError: Event loop is closed` lúc đóng nodriver (`collection/sources/jobsgo/crawler.py:617`, `asyncio.run` ở `:624`); dữ liệu đã lưu đủ.
- Glints: trang 1 API chỉ trả 4 tin ngoài IT nên discovery đăng ký 0 URL. Cần xem cách lọc danh mục (cần API thật).

**SCRAPE-13. Thời gian nghỉ giữa request lệch chuẩn 2,0–4,5 giây (C10)**

- JobsGO 1,5–3,0 s; VietnamWorks 1,2–2,2 s và `time.sleep(0.3)` cố định; TopDev 1,0–2,5 s. **Đã chốt 09/11: nâng cả ba lên 2,0–4,5 s** (hệ quả: cào chậm hơn).
- `tests/contract/standards.check_random_pause` mới kiểm tên hàm, chưa kiểm ngưỡng số; sẽ báo nhầm CareerViet (nghỉ qua `DelayConfig`).

**SCRAPE-14. Contract test cho 6 nguồn còn lại**

- Đã có fixture TopDev, TopCV (`tests/fixtures/`). Còn VietnamWorks, CareerViet, Vieclam24h, ITviec, Glints, JobsGO; mỗi nguồn cần 3 mẫu thật (xem `tests/CLAUDE.md`), cần mạng.

**SCRAPE-15. TopDev cào cả tin ngoài IT; lọc IT còn import ngược từ `preprocessing`** (gộp SCRAPE-15, 18)

- `topdev/crawler.py:_fetch_listing` gửi `category_ids=1` nhưng API `/td/v2/jobs` bỏ qua tham số này (đo 03/11: có hay không đều 14.572 tin). Mỗi lượt cào vẫn tốn request cho tin không dùng.
- **Đã chốt 09/11: bỏ lọc IT ở bước thu thập, để bước Clean lọc.** Còn việc gỡ `from preprocessing.common.it_filter import classify` (`:44`), `filter_it` (`:1620`) và bước lọc (`:1657`), sửa contract test. Tìm tham số lọc ngành đúng của API cần gọi thật.

**SCRAPE-17. Test ledger khác kết quả giữa Windows và Linux** (gộp GEN-6)

- `save_catalog` dùng `mem_ts >= disk_ts` (`collection/common/url_ledger.py:399`); khi timestamp bằng nhau, worker lưu sau ghi đè trạng thái thay đổi sau. Test `tests/unit/test_url_ledger_dedup.py` (dòng 229–241): trên Linux pass, trên Windows fail (mong DONE, nhận FAILED). Chưa tự kiểm chứng nhánh của lead.
- Cách xử lý: phá thế hòa bằng độ ưu tiên trạng thái hoặc bộ đếm đơn điệu; đụng ledger nên cần duyệt.

## 2. Trực quan hóa dữ liệu

**VIZ-6. `/insights` chưa kiểm với dữ liệu Mart thật** (nhánh Sơn)

- Mart rỗng, test mock query.

**VIZ-7. Chưa kiểm giao diện sau merge** (nhánh Sơn)

- Chưa chạy `./start_monitoring.sh --check` và kiểm 390 px; bundle JS 778 kB cần tách code. Tiêu đề trang vẫn ghi "5 bước" (`monitoring/frontend/src/App.tsx`); lệnh tạo báo cáo cho bước 07–09 trên giao diện còn trống.

## 3. Pre-processing và Processing

Các mục PRE-1…PRE-10, 16–19, 22, 28, 29 đã đóng hoặc bị phương án mới thay (L-27, L-28, L-36, L-38); PRE-13 và PRE-15 gộp vào PRE-12; PRE-14 viết lại thành việc đồng bộ ADR-04. Số PRE-30 và PRE-31 để trống.

**PRE-11. Chờ chốt hướng cho bước mô hình**

- Số đo cũ 04/11 (5.177 tin): 55% thiếu lương, 13% cấp bậc không rõ, 11% nhóm "Khác", 74% ở Hà Nội + TP.HCM, ma trận kỹ năng thưa 97,2%. Chưa đo lại sau PH9 (4.798 tin; nhóm Other nay 1.832 vì `job_titles.json` chưa duyệt).
- Đã đưa thành 5 câu hỏi A/B ở slide cuối `docs/presentation/slides.html` để xin ý kiến thầy. Chưa chọn hướng.

**PRE-12. Bộ lọc IT: nghiệm thu và cổng tầng 2**

- Có 643 nhãn tay (182 IT, 461 không IT); độ đúng luật 92,4%, tầng 2 IT 55/71, chưa tính khoảng tin cậy; yêu cầu lead ≥95% kèm khoảng tin cậy chưa chốt điều kiện cận dưới. Chi tiết `docs/presentation/van_de_can_chot.html` mục 4 và `docs/tasks/02_tai_clean_and_deduplication.md` §5.8.
- Tầng 2 (`preprocessing/common/it_filter.py:86-95`) dùng nhóm nghề tự suy từ tiêu đề + JD, không đọc `raw_category_text` như SPEC-05 §2.4. Lead chưa chọn (A) gate bằng chuyên mục sàn, (B) miễn trừ có ghi dấu, hay (C) chuyên mục chỉ là tín hiệu ưu tiên.
- Đã quyết 10/11: không dùng model để phân loại IT, chấp nhận nguyên trạng các tin bị loại.

**PRE-14. Văn bản ADR-04 còn mô tả thuật toán cũ**

- `docs/spec/11_technical_decisions.md` ADR-04 mô tả Jaccard + cosine TF-IDF; code đã chuyển sang MinHash (PH4, `dedup_policy.json`). Cần đồng bộ văn bản.

**PRE-20. Hai runner Integration trùng, thiếu test I2–I5**

- `preprocessing/integration/run.py` (đang dùng) và `run_integration.py` (404 dòng, còn `boto3.client`). Đề xuất xóa `run_integration.py` sau khi kiểm không còn chỗ gọi.

**PRE-21. Pipeline đặc trưng cũ của Duy ghi trùng `04_normalization/all.parquet`**

- `preprocessing/transformation/pipeline.py` (`:159,212`) và `run_transformation.py` ghi cùng file với bước 04 mới và còn dùng nhãn "Chưa rõ" (`text_cleaner.normalize_seniority`). Đã chốt 10/11: vô hiệu hóa, giữ code.

**PRE-23. Hai lỗi parse lương còn lại**

- `parse_salary("tối thiểu 10 triệu")` ra min=max=10 (`single_value`), đúng ra là cận dưới (`lower_bound`, max rỗng). `parse_salary("2 tỷ")` ra 2,0 triệu, đúng ra 2.000 triệu (`preprocessing/transformation/salary_parser.py`). "Điện Biên Phủ" và "Không yêu cầu" đã đúng.

**PRE-24. Test P3/P4 nằm ngoài `testpaths`**

- `preprocessing/transformation/tests/test_feature_engineering.py` không chạy trong `make test` (`pyproject.toml` `testpaths = ["tests"]`); chạy chung gây lỗi `tests/conftest.py:42`.

**PRE-25. `ledger.csv` bị `.gitignore` (`*.csv`)**

- `preprocessing/encoding/cohort.py`, `finalize_cohort.py` đọc nó nên clone sạch không chạy lại được. Đã chốt: chưa sửa, pipeline mới không dùng cohort.

**PRE-26. `reports/preprocessing/05_encoding` phình git**

- 70 file được track, 4,6 MB (pickle, npz, notebook HTML), trái quy tắc về `reports/`. Người dùng chấp nhận tạm.

**PRE-27. `tests/test_golden_field_preservation.py` lỗi collect**

- Import `preprocessing.normalization.target_schema_formatter`, module này không tồn tại (đã kiểm 10/11).

**PRE-32. Bước 05 encoding chưa nằm trong chuỗi `run_preprocessing`**

- Driver ghi `SKIPPED` (writer cũ bị tắt, cần tham số tường minh của `preprocessing.encoding.execute`). Mining cần ma trận số từ bước này.

**PRE-33. Việc chờ người dùng**

- Gán nhãn 100 JD gold (`scripts/gold_labeler.html`, mẫu `data/preprocessing/gold/gold_sample.json`): chưa có thì không đo được F1 kỹ năng, độ đúng section, precision phúc lợi. Mẫu có thể đổi khi chuỗi dịch ghi lại bảng 04.
- Duyệt từ điển JSON: `abbreviations.json`, `job_titles.json` (chưa duyệt thì nhiều tin vào Other), `scope_keywords.json`, các file candidate ở `processing/dictionaries/` (sao bản duyệt sang `section_headings.json`, `priority_cues.json`, `short_aliases.json`). `no_translate.json` đã duyệt đề xuất 10/11.
- Chấm 50 cặp dedup: `data/preprocessing/review/dedup_pairs_sample.csv`, cột `nhan_tay` (`trung`/`khac`).
- Kiểm tay 50 JD dịch sau khi dịch xong (`scripts/build_translation_review_sample.py`). Lỗi đã biết: mô hình làm rơi dấu "+" ("5+ years" → "5 năm") và đổi định dạng số.
- Chọn ngưỡng `min_df` (đề xuất 10–20, mặc định dự kiến 15).
- Chốt: Data Analyst/BI thuộc nhóm Data Science/AI hay không; suy cấp bậc Intern/Fresher cho ~317 tin itviec có kinh nghiệm "0,8 năm (10 tháng)".

## 3b. Data Mining

**MINE-1. Mining chưa chạy trên dữ liệu thật**

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
- Còn lệch: `canonicalize_lakehouse_key` từ chối `staging/all.parquet` (bắt buộc tên nguồn ở cấp 2); `features.parquet` đang ở `curated/preprocessing/features.parquet` (spec 10 ghi `gold/features.parquet`) và `mining/config.py` đọc local `data/preprocessing/05_encoding/features.parquet`; `scripts/push_integration_to_r2.py` ghi `integration/...` ngoài 5 tiền tố.

**GEN-7. Code tải R2 tự dựng trong `preprocessing/integration`**

- `integration/run.py:102-104` và `run_integration.py:161-163` gọi `boto3.client` trực tiếp, bucket mặc định `vn-it-jobs` gán cứng, không qua `get_r2_client()`.

**GEN-8. Mẫu báo cáo nghiệm thu chưa điền** ở `docs/tasks/` của Duy, Phúc, Sơn (mục 5 của mẫu).

**GEN-10. 4 test integration fail từ merge nhánh Sơn (MERGE-10)**

- `test_monitor_eda_r2::test_empty_remote_has_no_local_fallback`, hai test collection trong `test_monitor_endpoints`, `test_pipeline_reports::test_eda_charts_from_staging_parquet` (chi tiết `docs/tasks/issues_merge.md`). Cần kiểm lại có đúng thuộc MERGE-10 không.
