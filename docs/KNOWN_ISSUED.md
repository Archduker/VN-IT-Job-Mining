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

- **Cập nhật 18/11:** nhãn C4b nay do Claude gán, cộng 48 nhãn người dùng bổ sung; chạy lại 01 trên tập raw R2. Độ đúng luật 90,8% (P_IT 86,5%, P_không IT 92,4%, R_IT 80,4%), vẫn dưới 95%. Chi tiết `docs/spec/preprocessing/01_clean.md`.
- Số cũ (10/11): 643 nhãn tay (182 IT, 461 không IT); độ đúng luật 92,4%, tầng 2 IT 55/71, chưa tính khoảng tin cậy; yêu cầu lead ≥95% kèm khoảng tin cậy chưa chốt điều kiện cận dưới. Chi tiết `docs/presentation/van_de_can_chot.html` mục 4 và `docs/tasks/02_tai_clean_and_deduplication.md` §5.8.
- Tầng 2 (`preprocessing/common/it_filter.py:86-95`) dùng nhóm nghề tự suy từ tiêu đề + JD, không đọc `raw_category_text` như SPEC-05 §2.4. Lead chưa chọn (A) gate bằng chuyên mục sàn, (B) miễn trừ có ghi dấu, hay (C) chuyên mục chỉ là tín hiệu ưu tiên.
- Đã quyết 10/11: không dùng model để phân loại IT, chấp nhận nguyên trạng các tin bị loại.

**PRE-25. `ledger.csv` bị `.gitignore` (`*.csv`)**

- `preprocessing/encoding/cohort.py`, `finalize_cohort.py` đọc nó nên clone sạch không chạy lại được. Đã chốt: chưa sửa, pipeline mới không dùng cohort.

**PRE-26. `reports/preprocessing/05_encoding` phình git**

- 70 file được track, 4,6 MB (pickle, npz, notebook HTML), trái quy tắc về `reports/`. Người dùng chấp nhận tạm.

**PRE-34. Bước 10–12 chưa làm và chưa có đánh giá**

- Code 10, 10b, 10c, 10d, 12 đã xong và chạy thật 11/11 (L-44). Bước 11 (train/test) bỏ có chủ đích vì mining unsupervised; e5 đã xong (L-45).
- Việc xử lý sau: đánh giá hiệu quả 10–12 (min_df, ngưỡng bin lương, đặc trưng 10c có ích cho cụm/luật không). TF-IDF đã bỏ 17/11 (MINE-7), nên không còn việc so TF-IDF với e5; bước 09 khi đó chỉ còn phục vụ `n_tokens` của 10c, xét có giữ không. Tiêu chí chọn đặc trưng ngoài min_df chưa chốt.
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
  - **18/11:** đã rõ nguyên nhân: "0,8 năm" là mức gom 10 tháng của `monthsOfExperience` trong JSON-LD itviec, không phải con số của tin. Người dùng chốt itviec lấy kinh nghiệm từ JD trước. Bước 03 T9c đã code (dry-run: 616/818 tin itviec có số năm từ JD); bước 04 M4 sẽ chọn. Kiểm lại sau khi chạy 04.
- Duyệt từ điển `preprocessing/dictionaries/jd_extraction.json`: **xong 18/11** (7 quyết định trong `decisions`).

**PRE-35. Dữ liệu chưa sạch 100% để phục vụ 5 tầng SD1–SD5** (mở 16/11/2026)

- 5 mục tiêu mới ở `docs/target/` (BI → không giám sát → train model) cần dữ liệu sạch 100%. Các số trong `docs/target/00_de_tai.md` mục 8 là ảnh chụp 10/11/2026 và sẽ đổi. **Tiêu chí "sạch" cho từng SD chưa chốt, chờ người dùng.**
- Chỗ đang chặn, theo SD (số lấy từ `reports/preprocessing/0{3,4}_*/_all.json` và các mục dẫn ra):
  - **SD1:**
    - Thiếu `seniority` ở 8,3% số tin.
    - 2.516 tin có cấp bậc tự suy ra (`level_inferred`).
    - 94 tin không xác định được tỉnh (`tinh_unknown`).
    - 258 tin cần kiểm lại `job_family`.
    - `posted_date` chỉ phủ 63,8%. Đã có cách thay: `posted_month` phủ 100% (dry-run 03 ngày 18/11, PRE-37). Tin đăng trước 09/2026 đã bị bỏ ở bước 01 (C9, L-50).
    - `work_mode` đang mặc định onsite khi có tỉnh. Bước 03 T9a đã code; chờ N14 mới ở bước 04.
    - Bộ lọc IT đúng 92,4%, chưa đạt ≥ 95% (PRE-12).
  - **SD2:**
    - Khoảng 7% số tin không có kỹ năng (`skills_std` phủ 92,9%).
    - Rút kỹ năng so với nhãn gold chỉ đạt F1 0,27 (PRE-33).
    - Sanity Flutter⇒Dart và React⇒JS|TS fail (MINE-1).
  - **SD3:**
    - Phân cụm đang tách theo số lượng kỹ năng của tin, không theo nội dung (MINE-1, L-47).
    - Bullet careerviet thô hơn các sàn khác.
    - 222 tin tiếng Anh dịch hỏng (PRE-34).
  - **SD4:**
    - Lương chỉ phủ 40,2% (min) và 44,5% (max).
    - Lương ngoại lai: 150 tin theo IQR từng cấp, 74 tin ngoài khoảng, 15 tin đáng ngờ.
    - Lương Senior thấp hơn Middle (MINE-1).
    - 115 tin có cấp bậc mâu thuẫn với kinh nghiệm (`seniority_can_kiem`).
    - Ngưỡng chuyển từ phương án A sang phương án B: xem PRE-36.
  - **SD5:**
    - Phụ thuộc SD2 và SD4.
    - Số tin Intern/Fresher/Junior ít.
    - Cần kiểm lại khoảng 317 tin itviec ghi "0,8 năm" (PRE-33). Đã có T9c (kinh nghiệm từ JD), chờ 04.
    - Tin thực tập ghi Full-time ở ô của sàn: 180 tin lệch (T9b), bước 04 N19 sẽ chọn internship.
- Cách xử lý:
  1. Người dùng chốt tiêu chí sạch cho từng SD.
  2. Sửa ở `preprocessing/` và `processing/`, rồi chạy lại pipeline.
  3. Cập nhật bảng ảnh chụp trong `docs/target/00_de_tai.md`.

**PRE-36. Ngưỡng nghiệm thu của SD1–SD5 chờ chốt** (mở 17/11/2026)

- Người dùng quyết định chưa cần chốt ngay. Các ngưỡng dưới đây đang ghi trong `docs/target/` với nhãn "đề xuất, chờ chốt PRE-36", và chỉ là đề xuất.
  - **Chung:** ô bảng có n < 30 thì ghi "ít dữ liệu".
  - **SD2:** kỹ năng hiếm là kỹ năng xuất hiện ở dưới 2% số tin, và có thêm lift ≥ 2 hoặc ≥ 60% số lần xuất hiện nằm ở tin Senior/Lead.
  - **SD3:** ARI giữa 5 lần chạy với seed khác nhau ≥ 0,8; không cụm nào dưới 1% số tin. Ngưỡng Silhouette và Davies–Bouldin chưa có đề xuất.
  - **SD4:**
    - Phương án A (hồi quy ra con số) đạt khi MAE thấp hơn baseline (trung vị cấp × nghề) ít nhất 10%. Nếu không đạt thì chuyển sang phương án B (đoán khung lương).
    - Kỹ năng có dưới 30 tin trong tập có lương thì không định giá.
    - Các ngưỡng đang có trong `mining/config.py` (R² ≥ 0,60, MAE ≤ 4,5 triệu, độ lệch chuẩn CV ≤ 0,05) cũng cần chốt lại theo SD4.
  - **SD5:** nghề phải có ≥ 30 tin cho người mới; kỹ năng có `demand` ≥ 5%; kỹ năng "để sau" khi tỷ lệ ở tin Senior gấp ≥ 3 lần ở tin người mới; coverage tính khi đáp ứng ≥ 70% số kỹ năng tin đòi; lệch giữa train và test ≤ 10 điểm phần trăm.
- Cách xử lý: chốt khi bắt đầu làm từng SD. Chốt xong thì sửa nhãn trong `docs/target/` và spec 08.

**PRE-37. `posted_month` thay `posted_date` trong dữ liệu sạch** (mở 17/11/2026)

- **Người dùng đã chốt 17/11:**
  - Dữ liệu sạch bỏ hẳn `posted_date` (ngày đầy đủ), chỉ giữ `posted_month` dạng `YYYY-MM`. Không có `posted_month_source` (người dùng bỏ 17/11).
  - Phạm vi thời gian là tin đăng từ tháng 9, cào trong tháng 10–11/2026.
- **Lý do:** `posted_date` chỉ phủ 63,8% (topcv 0%, topdev 32,7%; `reports/preprocessing/03_transformation/<nguồn>.json`). Trong khi đó `crawled_at` có ở mọi tin, và BI chỉ cần phân biệt theo tháng.
- **Việc code:**
  1. ~~Mang `first_crawled_at` qua bước 02~~: **xong 18/11** (bước 01 ghi `first_scraped_at`, bước 02 xuất `first_crawled_at`; L-49).
  2. ~~Bước 03 tạo `posted_month`~~: **code xong 18/11** (T3b; `first_crawled_at` đổi sang giờ Việt Nam). Dry-run 4.671 tin: 2.979 lấy từ ngày đăng, 1.692 từ lần cào đầu; 2026-10: 3.466, 2026-09: 943, 2026-08: 101, 2026-11: 81, trước 08/2026: 80 (76 là glints). Từ 18/11 bước 01 bỏ mọi tin trước 09/2026 (C9, L-50), và TopCV đọc thêm `date_posted` (102 tin). Còn chạy thật cùng lượt dịch.
  3. Bỏ `posted_date` khỏi bảng sạch sau bước 04. Bước 01b vẫn dùng `raw_posted_date` ở tầng trung gian.
  4. `processing/encoding/features.py:118` đổi đặc trưng `posted_month` sang cột mới. `days_to_deadline` (dòng 119) vẫn tính từ `crawled_at`, không đổi.
- **Lưu ý khi dùng:**
  - Tháng 9 chỉ có tin từ nguồn ghi ngày đăng (Bronze 17/11: 1.629 tin). Khi so tháng 9 với tháng 10–11 thì chỉ dùng các nguồn ghi ngày đăng cho gần hết tin (vietnamworks, careerviet, vieclam24h, itviec, glints, jobsgo: 96–100%); bỏ topcv (0%) và topdev (40,4%), vì tin thiếu ngày đăng của hai nguồn này mang tháng cào.
  - Số tin mỗi tháng phụ thuộc lịch cào, nên chỉ so cơ cấu.

**PRE-38. Tỉnh lấy từ trụ sở công ty có thể sai** (mở 17/11/2026)

- Luật N13 (bước 04) lấy tỉnh từ `raw_location_text`, rồi từ `company_address`, khi `locations` không ra tỉnh. Có 656 tin dùng luật này (`reports/preprocessing/04_normalization/_all.json`, 10/11).
- Ví dụ trong report: "Nhật Bản" → TP. Hà Nội (tin làm việc ở nước ngoài bị đếm vào tỉnh trụ sở); "Long Thành" → TP. Hồ Chí Minh (Long Thành thuộc Đồng Nai, nên ví dụ này có thể sai).
- Ảnh hưởng: SD1 (phân bố tỉnh), SD4 (tỉnh là đặc trưng của model lương).
- Việc cần làm: kiểm 656 tin N13; tin `ngoai_vn` không lấy tỉnh từ trụ sở; kiểm vì sao "Long Thành" ra TP. Hồ Chí Minh. Spec 05 mục 6.

**PRE-39. Dọn code theo spec 05 v3.0.0** (mở 17/11/2026)

- Bỏ `05_encoding` khỏi `STEPS` (`preprocessing/common/__init__.py`) và `MODULES` (`scripts/run_preprocessing.py`), vì bước 10 đã thay thế. Người dùng duyệt đề xuất ở spec 03 mục 7 ngày 17/11.
- Bảng sạch cuối, người dùng duyệt 17/11 (spec 05 mục 4.1):
  - Bảng sạch = `data/preprocessing/04_normalization/all.parquet`.
  - `mining/config.py` trỏ `DEFAULT_GOLDEN` về bảng 04 và bỏ `FALLBACK_GOLDEN`. `scripts/load_mart_from_parquet.py` và `scripts/create_golden_master_eda_notebook.py` đọc bảng 04.
  - Đổi `01b_deduplication/golden_master_jobs.*` thành `golden_records.*` (sửa `deduplication/run.py`, `verify_delivery.py`).
- Sửa docstring sai: ~~`transformation/run.py` ("không dịch, không gọi model")~~ (sửa 18/11), `normalization/run.py` và tên luật N3 ("16 nhóm"). Đổi các trỏ tới `docs/spec/preprocessing/spec/P*.md` sang `docs/spec/05_preprocessing_spec.md`.
- Bảng target (spec 05 mục 4.4, người dùng chốt 17/11): thêm bước ghi `data/preprocessing/04_normalization/silver.parquet` gồm 26 trường tên tiếng Anh (22 trường chốt 17/11, thêm `employment_type`, `seniority_inferred`, `exp_inferred`, `salary_outlier` ngày 18/11), chỉ chọn cột và đổi tên. Làm sau PRE-37 (cần `posted_month`). Sau đó chuyển Monitoring, BI rồi Processing sang đọc bảng này.
- `processing/encoding/features.py` còn import `SENIORITY_MAP`, `TOP_PROVINCES_K`, `to_col_slug` từ `preprocessing/encoding/run.py`. Chuyển 3 hằng số này sang `processing/` trước khi dọn `preprocessing/encoding/` (spec 06 mục 6).

**PRE-40. Processing: hai từ điển kỹ năng, report thiếu luật, chưa ghim phiên bản** (mở 17/11/2026)

- **Hai nguồn kỹ năng:** bước 03 T7 dùng `preprocessing/dictionaries/skills.json` để tạo `skills_std`; bước 08 dùng `processing/dictionaries/skills_taxonomy_230.json` để tạo `skill__*`. Cùng một tin có thể có hai danh sách kỹ năng khác nhau. Cần chọn một nguồn cho SD1–SD5 (đề xuất: 08, vì có section và mức bắt buộc), hoặc đồng bộ hai từ điển.
- **Report:** 07, 08, 09, 10, 12 có `rules` rỗng, nên Monitoring không thấy luật nào. 12_e5 ghi `api.used = false` dù có gọi model e5; 07–09 ghi "pipeline không dùng model". Cần ghi luật S7, K8, W9, 10b vào `rules`, và ghi tên model cho 12_e5.
- **Tái lập:** `intfloat/multilingual-e5-base` chưa ghim commit (`processing/extraction/embed.py`). `pyahocorasick`, `underthesea` chưa có trong `requirements*.txt`.
- **Phân biệt bắt buộc và ưu tiên chưa hoạt động:** chưa có `priority_cues.json` đã duyệt, nên không có bullet `uu_tien` và mọi kỹ năng đều `required`. Đây là việc duyệt từ điển (PRE-33), nhưng ảnh hưởng trực tiếp SD2 và SD5.

**PRE-41. Phúc lợi: từ điển chỉ 10 nhóm** (mở 17/11/2026)

- Phần tách item ở bước 02 đã sửa 18/11 (careerviet, topdev; L-49). Kiểm lại thì topcv, jobsgo, vieclam24h vốn đã tách đúng.
- Làm sạch từng item (NFC, ký tự ẩn, khoảng trắng): bước 03 T6.5 code xong 18/11, ra cột `benefits_clean` (dry-run sửa 1.147 tin).
- **Từ điển:** `preprocessing/dictionaries/benefits.json` chỉ có 10 nhóm, phúc lợi không khớp nhóm nào thì mất. Người dùng đồng ý mở rộng (17/11) để `benefits` kéo được hết phúc lợi. Cách làm: lấy top item của `benefits_list` theo nguồn, gom thành nhóm mới, người dùng duyệt danh sách nhóm.
- **Độ phủ `benefits_std` 10/11:** glints 74,4%, các nguồn khác 88–97% (`reports/preprocessing/03_transformation/<nguồn>.json`).

**PRE-42. `sync_cloud_lakehouse.py --download --source <nguồn>` chỉ tải ledger** (mở 17/11/2026)

- Khi có `--source`, prefix là `url_ledger/<nguồn>/` nên raw không được tải; không có `--source` thì tải cả `staging/`, `curated/`, `pipeline/`. Chưa có cách tải riêng Bronze (`raw/` + `url_ledger/`). Ngày 17/11 đã tải Bronze bằng script tạm (12.246 file).

## 3b. Data Mining

**MINE-1. Mining đã chạy thật lần đầu (11/11), kết quả cụm yếu, chưa đánh giá**

- Chạy fp, cluster, anomaly trên 4.671 tin (L-46): Silhouette 0,091, DB 2,63, ARI với nhóm nghề 0,056; sanity 4/6 fail (Flutter→Dart conf 0,375; React→JS|TS 0,654; lương Senior < Middle; tỉ lệ lương HN/HCM). Chưa rõ do dữ liệu hay ngưỡng kiểm; chưa chỉnh tham số. Bước `salary` (Random Forest + SHAP) chưa chạy. Đã chốt 16/11: giữ lại, và đây là bước chính thức của SD4 (`docs/target/04_sd4_gia_tri_ky_nang.md`).
- Dòng cũ bên dưới (số giả từ `synthetic.py`) chỉ đúng cho báo cáo trước đó.
- 11/11 (L-47): 10 family, K-Means k=10: Silhouette 0,10, DB 2,49, ARI 0,07; cụm 1 chứa 292/293 tin không có kỹ năng, cụm 9 là cụm nhiều kỹ năng (trung vị 15): phân cụm một phần tách theo số kỹ năng. Chưa thử IDF cho kỹ năng, chưa lọc tin không có kỹ năng.

- Số trong báo cáo là dữ liệu giả từ `mining/synthetic.py`. Nhãn đã căn theo 5 cấp, 12 nhóm + Other nhưng chưa chạy trên `04_normalization/all.parquet` thật.

**MINE-5. `load_mart_from_parquet.py` biến cột list thành chuỗi;** chưa có bảng `skill_salary_shap_values`. Script và `scripts/build_slides.py` còn dùng nhãn cũ ("Khác", 6 bậc).

**MINE-6. Ghi chú cho báo cáo đồ án:** SHAP không phải quan hệ nhân quả; `seniority_level` 0–4 gộp Thực tập và Mới tốt nghiệp.

**MINE-7. Code Mining chưa trả lời đủ câu hỏi của SD1–SD5** (mở 17/11/2026; chi tiết ở spec 07 mục 3, cột "Thiếu so với SD")

- **Thứ tự chạy:** thêm `bi` và `recommend` vào `STEPS` của `mining/run_mining_pipeline.py`, theo thứ tự `bi, fp, cluster, anomaly, salary, recommend` (đã duyệt ở spec 03 mục 7).
- **M1 (SD1):** chưa có `mining/bi.py`; kết quả ghi `mining/artifacts/sd1_*.json`, Monitoring chỉ đọc.
- **M2 (SD2):** chưa có bảng top 15 kỹ năng theo nghề (2.1), chưa chia luật theo cấp bậc (2.3), chưa tìm kỹ năng hiếm (2.4), chưa chạy kiểm độ ổn định khi đổi support.
- **M3 (SD3):** chưa đo ARI qua 5 seed, chưa kiểm trung vị số kỹ năng theo cụm, chưa xuất bảng chéo cụm × `job_family`, chưa có luật đánh dấu nghề lai, nghề ngách, tin có vẻ bị gán sai.
- **M4 (SD3):** chưa chia hai loại "mới" và "khác".
- **M5 (SD4):**
  - chia dữ liệu theo `dup_group_id` thay vì `company_key`, chưa phân tầng theo cấp;
  - baseline là model "cấp + kinh nghiệm", không phải trung vị cấp × nghề;
  - chưa có phương án B, chưa ước tính lương cho tin thỏa thuận (`salary_estimated_vnd`, khoảng P10–P90), chưa có MAE theo nhóm;
  - chưa chạy trên dữ liệu thật.
- **M6 (SD5):** chưa có `mining/recommend.py`.
- **Quyết định đã chốt 17/11 (spec 07 mục 4), code chưa làm:**
  - Bỏ TF-IDF: gỡ `build_tfidf`, `tfidf_weight` khỏi `mining/clustering.py` và `mining/config.py`; bỏ `12_tfidf` khỏi `PROCESSING_STEPS` (`scripts/run_preprocessing.py`), xóa `processing/extraction/vectorize.py` và test, xóa `data/processing/12_tfidf/`, `reports/processing/12_tfidf/`.
  - Kỹ năng mềm và ngoại ngữ: đánh dấu 8 slug (`communication`, `teamwork`, `problem_solving`, `logical_thinking`, `time_management`, `presentation`, `english`, `japanese`) trong `skills_taxonomy_230.json`; M1, M2 (top 15, kỹ năng hiếm) và M6 xếp hai danh sách riêng.
  - M3 loại tin không có kỹ năng nào sau khi trích từ JD (bước 08) trước khi phân cụm; ghi `n_dropped_no_skill` vào metrics (11/11: 292 tin).

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
