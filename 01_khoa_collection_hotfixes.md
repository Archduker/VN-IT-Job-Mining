# BÁO CÁO NGHIỆM THU: COLLECTION & CRAWLER HOTFIXES

- **Người thực hiện:** Khoa
- **Nhánh Git:** `feature/collection-hotfixes`
- **Thư mục liên quan:** `collection/`, `tests/contract/`
- **Ngày hoàn thành:** 08/11/2026
- **Trạng thái:** Hoàn thành toàn diện, 50/50 Contract Tests đạt chuẩn (PASSED).

---

## 1. TỔNG QUAN KẾT QUẢ THỰC HIỆN

| Mã công việc | Hạng mục | Trạng thái | File tác động chính |
| :--- | :--- | :--- | :--- |
| **SCRAPE-5** | Sửa lỗi TopDev thiếu metadata (kinh nghiệm F5, cấp bậc F6, ngày đăng F8) | ✅ Hoàn thành | `collection/sources/topdev/crawler.py`<br>`monitoring/backend/app/core/feature_targets.py` |
| **SCRAPE-15** | Lọc tin ngoài IT cho TopDev (do API bỏ qua `category_ids=1`) | ✅ Hoàn thành | `collection/sources/topdev/crawler.py`<br>`tests/contract/test_topdev_contract.py` |
| **SCRAPE-16** | Sửa lỗi TopCV rỗng JD ở 297 tin cào ngày 22–26/10 (`/viec-lam/` & `/brand/`) | ✅ Hoàn thành | `collection/sources/topcv/crawler.py`<br>`tests/contract/test_topcv_contract.py` |
| **SCRAPE-11 / C14** | TopDev raise `DiscoveryError` khi không lấy được trang danh sách nào | ✅ Hoàn thành | `collection/sources/topdev/crawler.py`<br>`tests/contract/test_topdev_contract.py` |
| **SCRAPE-13 / C10** | Chuẩn hóa kiểm tra nghỉ ngẫu nhiên `check_random_pause` (CareerViet `DelayConfig`) | ✅ Hoàn thành | `tests/contract/standards.py` |
| **C1–C14 Suite** | Hoàn thiện bộ Contract Tests C1–C14 kiểm tra offline toàn bộ 8 nguồn sàn | ✅ Hoàn thành | `tests/contract/test_all_sources_contract.py` |

---

## 2. CHI TIẾT KỸ THUẬT & GIẢI PHÁP TRIỂN KHAI

### 2.1. SCRAPE-5: Khắc phục TopDev thiếu Metadata (F5, F6, F8)
* **Nguyên nhân gốc:** Pha Detail lưu dữ liệu thô từ API endpoint chi tiết `/td/v2/jobs/{id}` thông qua danh sách `DETAIL_FIELDS`. Danh sách này trước đây thiếu trường kinh nghiệm (`experiences_str`), cấp bậc (`job_levels_str`) và ngày đăng (`published`). Dù API listing và giao diện web có các trường này nhưng bản raw snapshot lại bị thiếu.
* **Giải pháp kỹ thuật:**
  1. Đảm bảo `DETAIL_FIELDS` trong `collection/sources/topdev/crawler.py` yêu cầu đầy đủ các trường: `job_levels_str`, `job_levels_arr`, `experiences_str`, `job_types_str`, `contract_types_str`, `published`.
  2. Tại hàm `build_raw_payload_from_api()`, loại bỏ trường `published.since` (chuỗi tương đối đổi theo ngày cào như *"3 ngày trước"*) nhằm bảo toàn nguyên tắc băm hash CDC ổn định (chuẩn C5).
  3. Khớp nối với `RAW_PATHS["topdev"]` trong `monitoring/backend/app/core/feature_targets.py`:
     - **F5 (Kinh nghiệm):** Khớp qua `raw_payload.experiences_str`, `experience`.
     - **F6 (Cấp bậc):** Khớp qua `raw_payload.job_levels_str`.
     - **F8 (Ngày đăng):** Khớp qua `raw_payload.published.date`, `date_posted`.
* **Kế hoạch xử lý dữ liệu cũ trên R2:**
  - Đối với các tin đã cào trước ngày 02/11 còn thiếu F5, F6, F8 trong raw, khi crawler chạy lại ở chu kỳ Re-crawl 21 ngày hoặc chạy bổ sung `--retry-failed`, crawler sẽ tự động lấy payload chi tiết mới, sinh `content_hash` mới và cập nhật version `_v2`.

---

### 2.2. SCRAPE-15: Lọc tin ngoài IT cho TopDev ở pha Discovery
* **Nguyên nhân gốc:** API `/td/v2/jobs` của TopDev bỏ qua query parameter `category_ids=1`. Cho dù có truyền tham số hay không thì API luôn trả về ~14.500 tin của mọi ngành (kế toán, tài xế, telesales, marketing, tạp vụ...). Hậu quả là bước Clean (P1) phải lọc bỏ 1.123 / 2.782 tin, gây lãng phí request và làm ô nhiễm URL ledger cũng như raw snapshots.
* **Giải pháp kỹ thuật:**
  1. Tích hợp trực tiếp bộ luật phân loại IT chuẩn `classify(title, skills)` từ `preprocessing.common.it_filter` vào hàm `discover_urls()` của `TopDevCrawler`.
  2. Bổ sung tham số `filter_it: bool = True` vào `discover_urls()`. Với mỗi bài đăng từ API listing:
     ```python
     title = job.get("title", "")
     skills_arr = job.get("skills_arr") or []
     if isinstance(skills_arr, list):
         skills_val = [s.get("title") if isinstance(s, dict) else str(s) for s in skills_arr]
     else:
         skills_val = [s.strip() for s in str(job.get("skills_str") or "").split(",") if s.strip()]

     # SCRAPE-15: Chặn tin ngoài IT (kế toán, tài xế, telesales...) đưa vào ledger
     if filter_it and classify(title, skills_val) == "non_it":
         log.debug("[TopDev] Bỏ qua tin ngoài IT (SCRAPE-15): %s", title)
         continue
     ```
  3. Chỉ những tin là `it` hoặc `unknown` (cần xét sâu hơn) mới được gọi `ledger.register_url()` và ghi vào manifest.
* **Kiểm chứng:** Viết test `test_scrape15_filter_non_it_jobs_in_discovery` trong `tests/contract/test_topdev_contract.py`: mock API trả về danh sách hỗn hợp (Golang Developer, Kế toán tổng hợp, Tài xế giao hàng), kết quả xác nhận crawler loại bỏ 100% tin ngoài IT và chỉ đăng ký tin Golang vào ledger.

---

### 2.3. SCRAPE-16: Khắc phục TopCV rỗng JD ở 297 tin (`/viec-lam/` & `/brand/`)
* **Nguyên nhân gốc:**
  - 297 tin TopCV cào ngày 22–26/10 có `description_bullets` và `requirements_bullets` đều rỗng (dù tiêu đề, lương, địa điểm vẫn có).
  - Gồm 244 tin URL dạng `/viec-lam/` và 53 tin URL dạng `/brand/`.
  - Cơ chế cũ chỉ tìm `.box-job-information-detail-item__title` với chuỗi cố định `"Mô tả công việc"`, bị thất bại khi:
    - Tiêu đề viết hoa: `MÔ TẢ CÔNG VIỆC:`, `CHI TIẾT CÔNG VIỆC`, `JOB DESCRIPTION`.
    - Trang thương hiệu `/brand/` sử dụng layout khác không có class `.box-job-information-detail-item`.
    - Khi selector DOM không khớp, crawler cũ chỉ fallback về 3 class cố định và hoàn toàn bỏ quên khối Schema.org JSON-LD có sẵn trong trang.
* **Giải pháp kỹ thuật (4 tầng bóc tách kiên cố):**
  Nâng cấp hàm `build_raw_payload()` trong `collection/sources/topcv/crawler.py`:
  1. **Tầng 1 (Container chuẩn):** Khớp container `.box-job-information-detail-item` không phân biệt hoa thường với từ khóa mở rộng (`mô tả công việc`, `mô tả`, `job description`, `yêu cầu ứng viên`, `yêu cầu công việc`, `quyền lợi`, `benefits`).
  2. **Tầng 2 (Header linh hoạt & Brand layout):** Quét các thẻ tiêu đề (`h2`, `h3`, `h4`, `div`, `p`) khớp ngữ nghĩa tiêu đề mục, sau đó bóc tách bullets từ container cha hoặc thẻ kế tiếp (`find_next_sibling`).
  3. **Tầng 3 (Legacy & Brand selectors):** Bổ sung các selector layout doanh nghiệp: `.job-description`, `#job-description`, `.job-detail__description`, `.box-job-description`, `.job-data`.
  4. **Tầng 4 (JSON-LD Fallback):** Khi DOM bị stripped hoặc không bóc tách được bullet nào, tự động parse thẻ `<script type="application/ld+json">` (`JobPosting`), trích xuất toàn bộ description HTML thành các bullets chất lượng cao.
* **Kiểm chứng:** Viết test `test_scrape16_empty_jd_fallback_recovery` và `test_scrape16_jsonld_fallback` trong `tests/contract/test_topcv_contract.py`, đảm bảo khôi phục 100% nội dung JD.

---

### 2.4. Hoàn thiện Bộ Contract Tests C1–C14 & Chuẩn C10, C14
1. **Tiêu chuẩn C10 (Thời gian nghỉ ngẫu nhiên):**
   - File: `tests/contract/standards.py`.
   - Cải tiến hàm `check_random_pause()` để nhận diện thêm cơ chế nghỉ ngẫu nhiên của `HttpClient` qua `DelayConfig` (như `CareerVietCrawler`), tránh báo lỗi giả.
2. **Tiêu chuẩn C14 (Discovery Error Handling - SCRAPE-11):**
   - Triển khai chuẩn C14 vào `TopDevCrawler`: nếu tất cả các trang listing của pha Discovery đều gặp lỗi (ví dụ API sập 500, mạng timeout), hàm `discover_urls()` sẽ raise `DiscoveryError` để Airflow báo đỏ, không âm thầm trả về danh sách rỗng báo thành công.
   - Bổ sung 2 test cases: `test_c14_discovery_fails_when_all_pages_fail` và `test_c14_discovery_partial_failure_is_ok`.
3. **Bộ test C1–C14 cho cả 8 sàn:**
   - Tạo mới `tests/contract/test_all_sources_contract.py` chạy offline kiểm định toàn diện:
     - **C1:** Cả 8 nguồn (`topcv`, `topdev`, `vietnamworks`, `careerviet`, `vieclam24h`, `itviec`, `glints`, `jobsgo`) đều cung cấp `discover_urls()` và `crawl_details()`.
     - **C2:** URL canonicalization làm sạch 100% tracking (`utm_*`, `ref`, `source`).
     - **C3:** Vòng đời ledger chuyển đổi đúng `PENDING -> DONE -> RECHECK_DUE (21 ngày)`, cơ chế `--retry-failed` chỉ lấy tin `FAILED`.
     - **C6:** Tin repost trùng content_hash chỉ đánh dấu repost, không sinh raw file trùng lặp.
     - **C8:** Layout key R2 `raw/<source>/<YYYY-MM-DD>/<job_id>_v<N>.json` hợp lệ trên toàn bộ 8 nguồn.
     - **C10:** Cả 8 module crawler đều có cơ chế nghỉ ngẫu nhiên giữa các request.
     - **C14:** Định nghĩa và xử lý đúng ngoại lệ `DiscoveryError`.

---

## 3. KẾT QUẢ KIỂM THỬ THỰC TẾ (TEST SUITE VERIFICATION)

Lệnh thực thi kiểm thử offline:
```bash
python -m pytest tests/contract/ -v
```

Kết quả: **50/50 tests PASSED (100% thành công)**:
```text
tests/contract/test_all_sources_contract.py::test_c1_all_crawlers_two_phase[topcv-TopCVCrawler] PASSED
tests/contract/test_all_sources_contract.py::test_c1_all_crawlers_two_phase[topdev-TopDevCrawler] PASSED
tests/contract/test_all_sources_contract.py::test_c1_all_crawlers_two_phase[vietnamworks-VietnamWorksCrawler] PASSED
tests/contract/test_all_sources_contract.py::test_c1_all_crawlers_two_phase[careerviet-CareerVietCrawler] PASSED
tests/contract/test_all_sources_contract.py::test_c1_all_crawlers_two_phase[vieclam24h-ViecLam24hCrawler] PASSED
tests/contract/test_all_sources_contract.py::test_c1_all_crawlers_two_phase[itviec-ItviecCrawler] PASSED
tests/contract/test_all_sources_contract.py::test_c1_all_crawlers_two_phase[glints-GlintsCrawler] PASSED
tests/contract/test_all_sources_contract.py::test_c1_all_crawlers_two_phase[jobsgo-JobsGoCrawler] PASSED
tests/contract/test_all_sources_contract.py::test_c10_all_crawlers_random_pause[topcv-collection.sources.topcv.crawler] PASSED
tests/contract/test_all_sources_contract.py::test_c10_all_crawlers_random_pause[topdev-collection.sources.topdev.crawler] PASSED
tests/contract/test_all_sources_contract.py::test_c10_all_crawlers_random_pause[vietnamworks-collection.sources.vietnamworks.crawler] PASSED
tests/contract/test_all_sources_contract.py::test_c10_all_crawlers_random_pause[careerviet-collection.sources.careerviet.crawler] PASSED
tests/contract/test_all_sources_contract.py::test_c10_all_crawlers_random_pause[vieclam24h-collection.sources.vieclam24h.crawler] PASSED
tests/contract/test_all_sources_contract.py::test_c10_all_crawlers_random_pause[itviec-collection.sources.itviec.crawler] PASSED
tests/contract/test_all_sources_contract.py::test_c10_all_crawlers_random_pause[glints-collection.sources.glints.crawler] PASSED
tests/contract/test_all_sources_contract.py::test_c10_all_crawlers_random_pause[jobsgo-collection.sources.jobsgo.crawler] PASSED
tests/contract/test_all_sources_contract.py::test_c8_all_sources_r2_layout[topcv] PASSED
tests/contract/test_all_sources_contract.py::test_c8_all_sources_r2_layout[topdev] PASSED
tests/contract/test_all_sources_contract.py::test_c8_all_sources_r2_layout[vietnamworks] PASSED
tests/contract/test_all_sources_contract.py::test_c8_all_sources_r2_layout[careerviet] PASSED
tests/contract/test_all_sources_contract.py::test_c8_all_sources_r2_layout[vieclam24h] PASSED
tests/contract/test_all_sources_contract.py::test_c8_all_sources_r2_layout[itviec] PASSED
tests/contract/test_all_sources_contract.py::test_c8_all_sources_r2_layout[glints] PASSED
tests/contract/test_all_sources_contract.py::test_c8_all_sources_r2_layout[jobsgo] PASSED
tests/contract/test_all_sources_contract.py::test_c2_clean_canonical_url PASSED
tests/contract/test_all_sources_contract.py::test_c3_ledger_lifecycle PASSED
tests/contract/test_all_sources_contract.py::test_c6_repost_handling PASSED
tests/contract/test_all_sources_contract.py::test_c14_discovery_error_type PASSED
tests/contract/test_topcv_contract.py::test_c1_two_phase PASSED
tests/contract/test_topcv_contract.py::test_c4_c11_envelope_and_features PASSED
tests/contract/test_topcv_contract.py::test_c5_hash_is_stable PASSED
tests/contract/test_topcv_contract.py::test_c7_c8_safe_skip_and_r2_layout PASSED
tests/contract/test_topcv_contract.py::test_c9_ledger_sync_failure_is_reported PASSED
tests/contract/test_topcv_contract.py::test_c10_random_pause PASSED
tests/contract/test_topcv_contract.py::test_scrape10_default_engine_is_curl_cffi PASSED
tests/contract/test_topcv_contract.py::test_c14_discovery_fails_when_no_listing_page_works PASSED
tests/contract/test_topcv_contract.py::test_c14_partial_listing_failure_is_ok PASSED
tests/contract/test_topcv_contract.py::test_c14_listing_without_new_jobs_is_ok PASSED
tests/contract/test_topcv_contract.py::test_c14_run_py_exit_code_on_discovery_error PASSED
tests/contract/test_topcv_contract.py::test_scrape16_empty_jd_fallback_recovery PASSED
tests/contract/test_topcv_contract.py::test_scrape16_jsonld_fallback PASSED
tests/contract/test_topdev_contract.py::test_c1_two_phase PASSED
tests/contract/test_topdev_contract.py::test_c4_c11_envelope_and_features PASSED
tests/contract/test_topdev_contract.py::test_c5_hash_ignores_relative_dates PASSED
tests/contract/test_topdev_contract.py::test_c7_c8_safe_skip_and_r2_layout PASSED
tests/contract/test_topdev_contract.py::test_c9_ledger_sync_failure_is_reported PASSED
tests/contract/test_topdev_contract.py::test_c10_random_pause PASSED
tests/contract/test_topdev_contract.py::test_scrape15_filter_non_it_jobs_in_discovery PASSED
tests/contract/test_topdev_contract.py::test_c14_discovery_fails_when_all_pages_fail PASSED
tests/contract/test_topdev_contract.py::test_c14_discovery_partial_failure_is_ok PASSED
======================== 50 passed, 1 warning in 3.66s ========================
```

---

## 4. HƯỚNG DẪN QUY TRÌNH RE-CRAWL & ĐỒNG BỘ R2 AN TOÀN

Khi chạy cào lại 297 tin TopCV và làm mới tin TopDev trên môi trường production:
1. **Chạy Re-crawl thử nghiệm với số lượng nhỏ (Safe Dry-Run):**
   ```bash
   # Cào chi tiết tối đa 5 tin TopCV để kiểm tra chất lượng raw
   python run.py --source topcv --phase detail --limit 5
   ```
2. **Kiểm tra độ đầy đủ của raw vừa cào:**
   ```bash
   python scripts/audit_raw_data.py --r2
   ```
3. **Đồng bộ Ledger và Raw Snapshots lên Cloudflare R2:**
   ```bash
   # Đồng bộ có kiểm soát, bảo đảm tính nhất quán giữa Ledger và Raw
   python run.py --source topcv --phase sync --sync-r2
   ```
