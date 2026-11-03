# Known Issues

Danh sách việc còn tồn đọng, cập nhật ngày 03/11/2026 trên nhánh `fix/known-issues-p1`. Xử lý xong mục nào thì chuyển sang `docs/issue_log.md` theo khuôn Lỗi → Nguyên nhân → Cách xử lý → Kiểm chứng (xem `docs/CLAUDE.md`), rồi xóa khỏi đây.

Thứ tự làm của dự án: **web scraping → trực quan hóa dữ liệu → pre-processing**. Phần pre-processing để sau, chưa sửa.

## 1. Web scraping

Kiểm tra dữ liệu bằng `python scripts/audit_raw_data.py --r2` (ghi `reports/data_audit_<ngày>.md`, không đưa vào git). Lần chạy 03/11/2026: 0 vấn đề mức cao.

**SCRAPE-1. Chưa kiểm tra với Airflow thật**

- Phạm vi: trạng thái Phase 1 đọc từ `task_instance`, Phase 2 đọc từ `dag_run` (`monitoring/backend/app/services/airflow_service.py`), thẻ Airflow trên header.
- Hiện trạng: R2 đã kết nối và tải đủ dữ liệu về máy. PostgreSQL của Airflow chưa chạy được vì user chưa có quyền docker.
- Cách xử lý: `sudo usermod -aG docker $USER`, đăng nhập lại, rồi chạy `./start_monitoring.sh`.

**SCRAPE-5. Raw TopDev cũ thiếu kinh nghiệm, cấp bậc và ngày đăng**

- Nguyên nhân: pha detail lưu raw từ API chi tiết với `DETAIL_FIELDS`, mà danh sách này thiếu `experiences_str`, `job_levels_str`, `published`. Đã sửa ngày 02/11 trong `collection/sources/topdev/crawler.py` và kiểm tra bằng một lần gọi API thật.
- Hiện trạng: raw đã cào vẫn thiếu (F5 21%, F6 0%, F8 29%). Tin nào được cào lại sẽ có đủ; lần cào lại đầu tiên sẽ sinh version mới vì hash đổi.

**SCRAPE-7. Glints chưa được cào lại từ 20/10**

- Ảnh hưởng: 331 tin, sẽ đến hạn cào lại hàng loạt từ 10/11.

**SCRAPE-8. Tin CLOSED vẫn được lưu raw mới**

- Ví dụ: VietnamWorks `2118352` CLOSED ("page not found") từ 20/10, nhưng có raw ngày 01/11.
- Cần xem: tin đăng lại hay crawler lưu raw trước khi kiểm tra tin đã đóng. Ledger giữ CLOSED theo quy tắc.

**SCRAPE-11. Discovery lỗi toàn trang mà vẫn báo thành công (7 nguồn còn lại)**

- TopCV đã sửa ngày 03/11 (tiêu chuẩn C14, `DiscoveryError`). 7 nguồn còn lại chưa kiểm; làm cùng contract test của từng nguồn.

**SCRAPE-12. Việc nhỏ thấy khi cào thử 03/11**

- JobsGO: sau khi chạy xong in `RuntimeError: Event loop is closed` lúc đóng nodriver; dữ liệu đã lưu đủ, chỉ là lỗi dọn dẹp.
- Glints: trang 1 của API chỉ trả 4 tin, cả 4 ngoài phạm vi IT, nên discovery đăng ký 0 URL. Cần xem cách lọc danh mục.

**SCRAPE-13. Thời gian nghỉ giữa request lệch chuẩn 2.0–4.5 giây (C10)**

- JobsGO 1.5–3.0 giây; VietnamWorks 1.2–2.2 giây và `time.sleep(0.3)` cố định giữa các trang; TopDev 1.0–2.5 giây (gọi API).
- CareerViet nghỉ qua `HttpClient` (`DelayConfig` 2–5 giây), đúng chuẩn, nhưng `tests/contract/standards.check_random_pause` chỉ tìm lời gọi `polite_sleep` hoặc `uniform` nên sẽ báo nhầm.
- Cần quyết: nâng lên chuẩn, hoặc ghi ngoại lệ có lý do cho nguồn gọi API. Làm cùng contract test của từng nguồn.

**SCRAPE-14. Contract test cho 6 nguồn còn lại**

- Đã có: TopDev, TopCV. Còn: VietnamWorks, CareerViet, Vieclam24h, ITviec, Glints, JobsGO. Mỗi nguồn cần 3 mẫu thật trong `tests/fixtures/<nguồn>/` (xem `tests/CLAUDE.md`).

**SCRAPE-15. TopDev cào cả tin ngoài IT**

- `collection/sources/topdev/crawler.py:_fetch_listing` gửi `category_ids=1` (ghi chú "1 = IT"), nhưng API `/td/v2/jobs` bỏ qua tham số này: có hay không đều trả 14.572 tin, trang 1 giống 50/50 (đo 03/11/2026).
- Ảnh hưởng: bước Clean (P1) xếp 1.123/2.782 tin TopDev là ngoài IT, 1.497 tin cần kiểm. Trong 30 tin cần kiểm đã gán nhãn có 29 tin ngoài IT. Pre-processing chỉ lọc được phần đã cào, mỗi lượt cào vẫn tốn request cho tin không dùng.
- Cách xử lý: tìm tham số lọc ngành đúng của API (hoặc lọc theo danh mục trên trang), sửa Discovery, kèm contract test.

**SCRAPE-16. 297 tin TopCV cào ngày 22–26/10 không có JD trong raw**

- Raw của các tin này chỉ có tiêu đề, công ty, lương, địa điểm; không có trường mô tả hay yêu cầu nào (không phải lỗi làm phẳng: không có trường chữ nào dài hơn 300 ký tự). 244 tin là trang `/viec-lam/`, 53 tin là trang `/brand/`. Có cả tin IT thật (ví dụ "Embedded Systems Engineer").
- Hiện tại: bước Clean bỏ các tin này theo luật C5 (JD dưới 30 từ).
- Cách xử lý: tìm vì sao crawler TopCV không lấy được JD trong 22–26/10, rồi đưa các tin này về `PENDING` để cào lại (chạy thử, gửi số liệu, chờ đồng ý vì ghi lên R2). Bản cào mới sẽ tự thay bản cũ qua luật C1.

## 2. Trực quan hóa dữ liệu

**VIZ-3. Các trang báo cáo đang hiện số của lần chạy pipeline ngày 25/10**

- Vị trí: `reports/` trong git, đọc qua `monitoring/backend/app/services/pipeline_report_service.py`
- Ảnh hưởng: số là thật, nhưng mang các lỗi của pre-processing cũ (xem mục 3). Mỗi trang có ghi giờ chạy pipeline.
- Cách xử lý: tự hết khi làm xong mục 3 và chạy lại pipeline.

**VIZ-5. `CrawlingPage.tsx` quá dài**

- Vị trí: `monitoring/frontend/src/pages/CrawlingPage.tsx` (khoảng 890 dòng)
- Cách xử lý: tách thành các component trong `components/`.

## 3. Pre-processing (để sau)

Code sửa cho PRE-1 và PRE-2 đã viết xong và có test, đang cất trong git stash "preprocessing: so khớp theo từ + chuẩn hóa sau imputer (hoãn)". Lấy lại bằng `git stash list` rồi `git stash apply stash@{N}`.

**PRE-1. Phân loại theo chuỗi con làm sai nhóm nghề, cấp bậc, thành phố**

- Vị trí: `classify_job_family`, `normalize_seniority`, `normalize_city` trong `preprocessing/normalization/text_cleaner.py`; heuristic trong `preprocessing/missing_outlier/genai_text_imputer.py`
- Ảnh hưởng: "ba" khớp trong "backend", "soc" khớp trong "associate", "intern" khớp trong "international". Bộ golden có 1.214 tin BA/Product, phần lớn là xếp sai.
- Cách xử lý: so khớp theo từ nguyên vẹn (có trong stash).

**PRE-2. Chuẩn hóa chạy trước imputer**

- Vị trí: `scripts/run_staging_integration_pipeline.py`
- Ảnh hưởng: nhóm nghề, thành phố, cấp bậc được tính trước khi imputer bù giá trị, nên giá trị bù không được dùng. Từ commit `a87b2c1`, CareerViet và JobsGO để `skills_list` rỗng cho imputer bù, nên nhóm nghề của hai nguồn này chỉ còn dựa vào title.
- Cách xử lý: chuẩn hóa sau imputer (có trong stash).

**PRE-3. Tên thành phố không dấu chưa được gộp**

- Vị trí: `normalize_city`
- Ảnh hưởng: có cả "Hà Nội" (2.111) và "Ha Noi" (509), "Hồ Chí Minh" (1.741) và "Ho Chi Minh" (351).
- Cách xử lý: bỏ dấu trước khi so khớp.

**PRE-4. Dữ liệu đã xử lý cần chạy lại**

- Vị trí: `data/staging/`, `data/curated/` trên R2, `reports/` trong git
- Ảnh hưởng: chưa phản ánh phần làm phẳng đã sửa ở commit `a87b2c1` (CareerViet, JobsGO, TopDev), cũng như PRE-1 đến PRE-3.
- Cách xử lý: làm PRE-1 đến PRE-3, chạy `python scripts/run_staging_integration_pipeline.py`, so số trước và sau, rồi mới đẩy lên R2.

**PRE-6. Kỹ năng của CareerViet và JobsGO lấy sai trường**

- Vị trí: `_flatten_careerviet`, `_flatten_jobsgo` trong `preprocessing/integration/json_flattener.py`
- Ảnh hưởng: CareerViet lấy `job-tags` (tag SEO của trang) làm kỹ năng, JobsGO lấy `occupations` (ngành nghề). Trang Raw cảnh báo F7 ở hai nguồn này.
- Lưu ý khi sửa: đã thử bỏ hai trường này ở commit `a87b2c1`, nhưng phải hoàn tác. Khi `skills_list` rỗng, nhóm nghề chỉ còn dựa vào title, và mọi bản ghi của hai nguồn đều phải gọi imputer. Cần làm cùng PRE-2 (chuẩn hóa sau imputer), và chỉ gọi imputer khi thiếu trường khác ngoài kỹ năng.

**PRE-7. Làm phẳng TopDev chưa đọc ngày đăng và kinh nghiệm từ JSON-LD**

- Vị trí: `_flatten_topdev` trong `preprocessing/integration/json_flattener.py`
- Ảnh hưởng: `raw_posted_date` chỉ đọc `recalled_at`, `created_at` (luôn rỗng). Raw có `published.date`, `date_posted` và `job_posting_jsonld.experienceRequirements` nhưng không được dùng. Trang Raw đã đọc các trường này.

**PRE-9. Chạy JEV cho bước Clean**

- Bước Clean (P1) đã chạy thật bằng luật từ khóa, chưa có JEV vì `.env` chưa có `OPENROUTER_API_KEY`.
- Ảnh hưởng: 4.300 tin ở nhóm "cần kiểm" (`can_kiem`) đi tiếp sang các bước sau, gồm 1.497 tin TopDev mà phần lớn là ngoài IT (SCRAPE-15).
- Cách xử lý: thêm khóa, chạy `python scripts/run_preprocessing.py --step clean --source all --dry-run --use-api` để xem ước tính (lần đo 03/11: 10.964 lần gọi, khoảng 0,18 USD; tài khoản giới hạn 1 USD), rồi chạy lại không có `--dry-run`. Sau đó gán nhãn mẫu mới (file review chưa có nhãn sẽ được chọn lại theo kết quả JEV) và xem lại `it_policy.json`.

## 4. Chung

**GEN-1. Khoảng 1.300 lỗi ruff tồn đọng** ở `collection/` và `tests/`. Dọn thành một lượt riêng.

**GEN-2. `README.md` và `TASKS.md` lệch code.** Chi tiết ở mục "Known mismatches" trong `CLAUDE.md`.

**GEN-3. Dọn code theo `docs/code_quality.md`.** Báo cáo (`make quality`) liệt kê import thừa, hàm không ai gọi, module không ai import, hàm trùng logic và trùng tên. Người dùng duyệt từng mục (xóa, gộp hay giữ) rồi mới sửa. Báo cáo không bắt được chỗ tự tạo `boto3.client(...)`; các chỗ đó đã chuyển qua `get_r2_client()` (`docs/issue_log.md` L-24).
