# Known Issues

Danh sách việc còn tồn đọng, cập nhật ngày 09/11/2026 sau khi merge 7 nhánh thành viên vào `sprint/pipeline-delivery`. Danh sách việc phát sinh từ merge, người phụ trách và trạng thái xử lý: `docs/tasks/issues_merge.md`. Xử lý xong mục nào thì chuyển sang `docs/issue_log.md` theo khuôn Lỗi → Nguyên nhân → Cách xử lý → Kiểm chứng (xem `docs/CLAUDE.md`), rồi xóa khỏi đây.

Thứ tự làm của dự án: **web scraping → trực quan hóa dữ liệu → pre-processing**.

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

**SCRAPE-11. Discovery lỗi toàn trang mà vẫn báo thành công (5 nguồn còn lại)**

- TopCV, TopDev, VietnamWorks đã có `DiscoveryError` (tiêu chuẩn C14; nhánh Khoa, VietnamWorks chưa có test). Còn CareerViet, Vieclam24h, ITviec, Glints, JobsGO chưa kiểm; làm cùng contract test của từng nguồn.

**SCRAPE-12. Việc nhỏ thấy khi cào thử 03/11**

- JobsGO: sau khi chạy xong in `RuntimeError: Event loop is closed` lúc đóng nodriver; dữ liệu đã lưu đủ, chỉ là lỗi dọn dẹp.
- Glints: trang 1 của API chỉ trả 4 tin, cả 4 ngoài phạm vi IT, nên discovery đăng ký 0 URL. Cần xem cách lọc danh mục.

**SCRAPE-13. Thời gian nghỉ giữa request lệch chuẩn 2.0–4.5 giây (C10)**

- JobsGO 1.5–3.0 giây; VietnamWorks 1.2–2.2 giây và `time.sleep(0.3)` cố định giữa các trang; TopDev 1.0–2.5 giây (gọi API).
- CareerViet nghỉ qua `HttpClient` (`DelayConfig` 2–5 giây), đúng chuẩn, nhưng `tests/contract/standards.check_random_pause` chỉ tìm lời gọi `polite_sleep` hoặc `uniform` nên sẽ báo nhầm.
- Cần quyết: nâng lên chuẩn, hoặc ghi ngoại lệ có lý do cho nguồn gọi API. Làm cùng contract test của từng nguồn.
- Cập nhật 09/11: `standards.check_random_pause` đã nhận `DelayConfig` nhưng chỉ kiểm tên hàm; TopDev, VietnamWorks, JobsGO vẫn dưới 2,0–4,5 giây.

**SCRAPE-14. Contract test cho 6 nguồn còn lại**

- Đã có: TopDev, TopCV. Nhánh Khoa (09/11) chỉ thêm test cấu trúc cho 8 nguồn, chưa có fixture/parser test cho 6 nguồn dưới. Còn: VietnamWorks, CareerViet, Vieclam24h, ITviec, Glints, JobsGO. Mỗi nguồn cần 3 mẫu thật trong `tests/fixtures/<nguồn>/` (xem `tests/CLAUDE.md`).

**SCRAPE-15. TopDev cào cả tin ngoài IT**

- `collection/sources/topdev/crawler.py:_fetch_listing` gửi `category_ids=1` (ghi chú "1 = IT"), nhưng API `/td/v2/jobs` bỏ qua tham số này: có hay không đều trả 14.572 tin, trang 1 giống 50/50 (đo 03/11/2026).
- Ảnh hưởng: bước Clean (P1) xếp 1.123/2.782 tin TopDev là ngoài IT, 1.497 tin cần kiểm. Trong 30 tin cần kiểm đã gán nhãn có 29 tin ngoài IT. Pre-processing chỉ lọc được phần đã cào, mỗi lượt cào vẫn tốn request cho tin không dùng.
- Cách xử lý: tìm tham số lọc ngành đúng của API (hoặc lọc theo danh mục trên trang), sửa Discovery, kèm contract test.

**SCRAPE-16. 297 tin TopCV cào ngày 22–26/10 không có JD trong raw**

- Raw của các tin này chỉ có tiêu đề, công ty, lương, địa điểm; không có trường mô tả hay yêu cầu nào (không phải lỗi làm phẳng: không có trường chữ nào dài hơn 300 ký tự). 244 tin là trang `/viec-lam/`, 53 tin là trang `/brand/`. Có cả tin IT thật (ví dụ "Embedded Systems Engineer").
- Hiện tại: bước Clean bỏ các tin này theo luật C5 (JD dưới 30 từ).
- Cập nhật 09/11: nhánh Khoa có fallback 4 tầng cho TopCV, chưa kiểm trên HTML thật, chưa có script backfill.
- Cách xử lý: tìm vì sao crawler TopCV không lấy được JD trong 22–26/10, rồi đưa các tin này về `PENDING` để cào lại (chạy thử, gửi số liệu, chờ đồng ý vì ghi lên R2). Bản cào mới sẽ tự thay bản cũ qua luật C1.

**SCRAPE-18. TopDev lọc IT bằng `it_filter` import ngược từ `preprocessing`** (mới, nhánh Khoa)

- `collection` import từ `preprocessing` đảo chiều phụ thuộc; API `/td/v2/jobs` vẫn trả 14.572 tin dù lọc (liên quan SCRAPE-15). Chưa quyết: giữ bộ lọc ở thu thập hay chỉ lọc ở Clean.

**SCRAPE-17. Test ledger còn lỗi trên máy cục bộ**

- Kiểm chứng 08/11: full unit và chạy riêng `tests/unit/test_url_ledger_dedup.py` đều lỗi tại dòng 229: mong DONE, nhận FAILED; chạy riêng 9 đạt / 1 lỗi. Log trong artifact `nov08_recheck/ledger.txt`.
- `save_catalog` dùng `mem_ts >= disk_ts`; khi timestamp bằng nhau, worker lưu sau có thể ghi đè trạng thái thay đổi sau. Test dùng `tmp_path`, không dùng raw của dự án.
- Chưa đủ bằng chứng kết luận mọi Windows đều lỗi, đồng hồ luôn có độ phân giải 2,1 ms, hoặc rủi ro sản xuất thấp. Lead báo pass trên nhánh của lead; chưa tự kiểm chứng nhánh đó.
- Ngoài Task #2, thuộc `collection/` – Task #1. Gửi log cho lead để tái hiện và quyết định xử lý; không sửa Collection trong lượt này.
- Review 09/11 (GEN-6): trên Linux test pass, trên Windows fail; nguyên nhân gốc vẫn là `mem_ts >= disk_ts` ở trên.

## 2. Trực quan hóa dữ liệu

**VIZ-3. Các trang báo cáo đang hiện số của lần chạy pipeline ngày 25/10**

- Vị trí: `reports/` trong git, đọc qua `monitoring/backend/app/services/pipeline_report_service.py`
- Ảnh hưởng: số là thật, nhưng mang các lỗi của pre-processing cũ (xem mục 3). Mỗi trang có ghi giờ chạy pipeline.
- Cách xử lý: tự hết khi làm xong mục 3 và chạy lại pipeline.
- Cập nhật 09/11: Market Insights đã đọc PostgreSQL Mart (nhánh Sơn); các trang báo cáo cũ vẫn dùng `reports/` ngày 25/10. VIZ-5 đã xong, xóa.

**VIZ-6. `/insights` chưa kiểm với dữ liệu Mart thật** (nhánh Sơn)

- Mart rỗng, test mock query. Chưa chạy được với dữ liệu thật.

**VIZ-7. Chưa kiểm giao diện sau merge** (nhánh Sơn)

- Chưa chạy `./start_monitoring.sh --check` và kiểm 390 px; bundle JS 778 kB cần tách code (code-split).


## 3. Pre-processing

PRE-1 đến PRE-7 đã hết khi chuyển sang pipeline 5 bước (`docs/issue_log.md` L-27); PRE-9, PRE-10 (JEV, dịch) hết vì đã bỏ model (L-28). Còn lại:

**PRE-11. Chờ chốt hướng cho bước mô hình**

- Số đo 04/11/2026 trên `data/preprocessing/04_normalization/all.parquet` (5.177 tin): 55% thiếu lương (thỏa thuận), 17% tin IT do luật tầng 2 quyết (tầng 2 đúng 81,9% trên nhãn tay), 13% cấp bậc không rõ, 11% nhóm nghề "Khác", 74% tin ở Hà Nội + TP.HCM, ma trận kỹ năng thưa 97,2%.
- Đã đưa thành 5 câu hỏi A/B ở slide cuối `docs/presentation/slides.html` để xin ý kiến thầy. Chưa chọn hướng nào.

**PRE-12. Chưa có nhãn hợp lệ để nghiệm thu bộ lọc IT**

- Đếm trực tiếp 08/11: 643 dòng review, 100 dòng tầng 1 dự đoán IT, 0 nhãn. Chưa kiểm tra R2 trong lượt này; không kết luận nhãn lịch sử đã mất toàn dự án.
- Lead gán nhãn, AI không tự điền. Ghi chú policy 331/339 và 42/47 không thay nhãn từng tin.
- Wilson cộng dồn chưa hiệu chỉnh phân tầng và thiếu nhãn; `--status` không tự kết luận nghiệm thu. Lead yêu cầu tỷ lệ ≥95% kèm khoảng tin cậy, chưa chốt điều kiện cận dưới ≥95%.
- Cần chốt dân số, trọng số và cách đánh giá cả precision IT lẫn nhóm thực sự bị loại; dự đoán non_it không đồng nghĩa bị C4c loại khi `drop=[]`. Gán riêng 100 tin tầng 1 không đủ đóng hai chỉ tiêu.
- Số học và lệnh tăng mẫu tại `docs/tasks/02_tai_clean_and_deduplication.md` §5.8.2. Giữ nguyên mẫu hiện tại chờ quyết định.

**PRE-13. Tầng 2 dùng "nhóm nghề tự suy" thay cho chuyên mục sàn mà SPEC-05 §2.4 nêu**

- `docs/spec/05_preprocessing_spec.md` §2.4 (dòng 107–109, 113): tin chức danh mơ hồ chỉ là IT khi **danh mục nghề nghiệp thuộc nhóm CNTT ĐỒNG THỜI ≥ 2 kỹ năng IT**; dòng 100 nêu lý do là sàn tổng hợp xếp nhầm tin kế toán/nhân sự/telesale vào mục IT → "danh mục" trong đặc tả là **chuyên mục do sàn cấp**.
- Code (`preprocessing/common/it_filter.py:86-95`) thỏa đúng cấu trúc điều kiện nhưng vế thứ nhất lấy từ `classify_job_family_rule(title, skills)` (12 nhóm, suy từ tiêu đề + JD), **không đọc** `raw_category_text`. Vì hai tín hiệu khác nhau nên số của script lead (431/842 không khớp từ điển chuyên mục) không mô tả quyết định thực tế của bộ lọc; cần nhãn để biết chênh lệch thật là bao nhiêu.
- Trở ngại nếu muốn dùng đúng chuyên mục sàn: `company_industry` của TopCV là trường công ty; ngữ nghĩa các trường industry khác còn phải kiểm theo nguồn. Chưa đo số loại nhầm bằng nhãn thật.
- Lead chốt: (A) gate bằng chuyên mục sàn sau khi Integration chuẩn hóa trường này; (B) miễn trừ có ghi dấu trong §2.4 và dùng nhóm nghề tự suy cho tới khi có trường chuyên mục; hoặc (C) chuyên mục chỉ là tín hiệu ưu tiên, không dùng để loại.
- Script lead trên 842 dự đoán IT tầng 2: 101 category rỗng, 310 khớp từ khóa, 431 không khớp. Regex mở rộng: 428 khớp, 313 không khớp; chênh 118, Glints góp 26.
- Đây là phép dò từ khóa, không phải nhãn IT thật. 414 bị loại chỉ đúng nếu dùng chính regex mở rộng làm gate. Không khẳng định 5/8 sàn là ngành công ty, 366 là mã VSIC xác minh, hoặc 669 là độ phủ ngành nghề đúng.
- Probe CareerViet tìm `industry` thấy 2/57, trong khi flattener lấy “Ngành nghề” có 55/57 giá trị. Bằng chứng và giới hạn ở `docs/tasks/02_tai_clean_and_deduplication.md` §5.8.1.
- Theo `traloi.md`, Tài giữ `common/it_filter` nếu lead chọn gate; Hoàng hỗ trợ schema nếu cần trường chuyên mục mới. Chưa thay bộ lọc/SPEC, chưa chạy lại snapshot.

**PRE-14. Văn bản ADR-04 chưa thống nhất với chuẩn lead đã chọn**

- Lead đã chọn SPEC-05 §3.2 và bắc cầu trong `traloi.md`; ADR-04 cục bộ vẫn mô tả blocking không Title_Group và Jaccard ≥0,80 AND cosine ≥0,75. Cần đồng bộ văn bản, không hỏi lại lựa chọn đã chốt.
- Probe trên audit: 81/131 dropped, 14/55 review-band, 2/3 transitive-link đạt điều kiện kép với tokenizer của probe. Không áp dụng cho 7 transitive-dropped vì điểm cosine là điểm qua trung gian.
- Không suy ra thêm 14 cụm hoặc tách 50 cặp: cần chạy lại blocking, TF-IDF và đồ thị. Q5 vẫn cần nhãn người đọc JD; chọn thuật toán không xác định trùng thật. Chi tiết task §5.8.5.
- Chưa kiểm remote trong lượt này; file có trong HEAD không chứng minh bản cập nhật ADR/bắc cầu lead nói đã được xuất bản.

**PRE-15. `it_policy.json` loại non_IT bằng bằng chứng tổng hợp** (Tài)

- Loại 5.409 tin, chưa có nhãn từng tin. Quyết định 09/11: chấp nhận nguyên trạng. Kế hoạch sau: dùng model phân loại lại các tin bị loại để lấy lại tin IT bị loại nhầm. Chưa làm; trái với dòng "không dùng model" của `preprocessing/CLAUDE.md`, cần người dùng cho phép lại khi bắt đầu.

**PRE-16. Integration chưa đọc đầu ra Dedup `01b_deduplication`** (Tài)

- Báo cáo Integration 5.177 lệch 4.897 của Dedup. Cần nối đúng đầu vào hoặc ghi lý do.
- Đo lại 09/11: chạy `python -m preprocessing.clean.run --source all` trên raw đã tải từ R2 ra 5.077 tin (VietnamWorks 800), báo cáo Hoàng ghi 5.177 (VietnamWorks 900). Chênh 100 tin chưa giải thích; chưa đoán nguyên nhân.

**PRE-17. Snapshot báo cáo của Tài là kết quả cũ** (Tài)

- `reports/preprocessing/01_clean`, `01b_deduplication` ghi đè 17 file JSON bằng kết quả `f693b30`, không phải code đã sửa. Cần chạy lại pipeline trước khi tin các số đó.

**PRE-18. I0 đổi từ "drop" sang "modify"** (Hoàng)

- `preprocessing/integration/run.py:174-178`: dòng JSON hỏng thành một bản ghi giả (tiêu đề là 80 ký tự của dòng hỏng) thay vì bị loại, trái P2 §8. `run()` đổi `dry_run` mặc định thành False. Test đã sửa theo hành vi mới (305d017); cần quyết thiết kế cuối: giữ zero-drop hay trả lại "loại + ghi dropped".

**PRE-19. `source_job_id` dùng `abs(hash(...))`** (Hoàng)

- `hash()` của Python thay đổi theo mỗi lần chạy (PYTHONHASHSEED), nên id không ổn định. Đổi sang hàm băm cố định (hashlib).

**PRE-20. Hai runner Integration trùng, thiếu test** (Hoàng)

- `run.py` và `run_integration.py` trùng việc; thiếu test cho I2–I5; con số 5.177 vs 8.378 chưa giải thích.

**PRE-21. Pipeline đặc trưng của Duy ghi trùng `04_normalization/all.parquet`** (Duy)

- Chưa nối vào `run.py` của bước 4.

**PRE-22. Lệch spec giữa cẩm nang Duy và SPEC-06/P4** (Duy)

- **Đã chốt 09/11/2026: dùng 5 cấp của Duy** (Intern/Fresher 0, Junior 1, Middle 2, Senior 3, Lead/Manager 4, -1 chưa rõ). Tài liệu đã sửa theo: SPEC-03, SPEC-06 §2.2, SPEC-10, `docs/spec/preprocessing/spec/P4` và `P5`, `normalization/04_scaling_and_taxonomy.md`, `README.md`, `docs/presentation/script.md`, hai prompt nháp P4/P5. Chưa đụng vào code.
- **Việc còn lại (code vẫn dùng thang 6 nhãn):** `preprocessing/encoding/run.py:50-58` (`SENIORITY_ORDER`, cột `seniority_ord` 0–5), `preprocessing/encoding/execution_features.py:40`, `preprocessing/normalization/run.py:103` và `text_cleaner.py:24` (nhãn "Trưởng nhóm/Quản lý"), `mining/config.py:81`, `mining/data_io.py` (adapter 0–4 → 0–5), `mining/synthetic.py`, `docs/tasks/06_phuc_data_mining_algorithms.md`. Phải thống nhất về `seniority_level` 0–4 trước khi chạy lại pipeline, nếu không `seniority_ord` (Phát) và `seniority_level` (Duy) lệch nhau.

- Đã chốt: tên tỉnh "TP. Hồ Chí Minh" (theo spec). Chưa sửa code.
- Cấp bậc, 6 cấp (SPEC-06 §2.2) so với 5 cấp (Duy, `experience_parser.py:61`):

| Mã | 6 cấp (spec) | 5 cấp (Duy) |
|---|---|---|
| 0 | Thực tập | Intern/Fresher (gộp) |
| 1 | Mới tốt nghiệp/Fresher | Junior |
| 2 | Junior | Middle |
| 3 | Middle | Senior |
| 4 | Senior | Lead/Manager |
| 5 | Trưởng nhóm/Quản lý | - |
| -1 | Chưa rõ | Chưa rõ |

  Mã từ Junior trở đi lệch một bậc, nên so sánh trực tiếp hai bản sẽ sai.
- Đo độ bao quát 09/11/2026 (raw tải từ R2 về `data/`, bản mới nhất mỗi job, 10.758 tin của 8 nguồn, **trước khi lọc IT**). Chỉ dùng chữ (tiêu đề + nhãn cấp bậc của sàn), chưa dùng số năm kinh nghiệm. Cột 6 cấp là ánh xạ tạm do mình viết (từ khóa "thực tập/intern" → 0, "fresher/mới tốt nghiệp/graduate" → 1, còn lại theo luật của Duy dời một bậc), không phải code của ai trong nhóm:

| Nhãn | 5 cấp (Duy) | 6 cấp (spec) |
|---|---|---|
| Chưa rõ (−1) | 7.249 (67,4%) | 7.229 (67,2%) |
| Thực tập / Fresher gộp (5 cấp: 0) | 700 (6,5%) | - |
| Thực tập (6 cấp: 0) | - | 587 (5,5%) |
| Mới tốt nghiệp/Fresher (6 cấp: 1) | - | 140 (1,3%) |
| Junior | 78 (0,7%) | 74 (0,7%) |
| Middle | 99 (0,9%) | 99 (0,9%) |
| Senior | 825 (7,7%) | 824 (7,7%) |
| Lead/Quản lý | 1.807 (16,8%) | 1.805 (16,8%) |

  Kết luận từ số đo: hai cách bao quát gần như bằng nhau (cùng ~67% chưa rõ nếu chỉ dùng chữ); 6 cấp chỉ khác ở việc tách 700 tin thành 587 thực tập + 140 mới tốt nghiệp. Cấp "Mới tốt nghiệp" chỉ 1,3% tin, nhóm nhỏ cho mining. Phần "chưa rõ" giảm khi dùng năm kinh nghiệm (PRE-11 đo 13% sau bước này). Lý do chữ thiếu: nhãn sàn thường chung chung (TopCV "Nhân viên" 1.979/2.674; VietnamWorks "Nhân viên" 978/1.219; JobsGO "Nhân Viên/Chuyên Viên" 1.250/1.540); TopDev (2.780/2.782), ITviec và Glints (không có nhãn) gần như không có nhãn sàn. Lệch nhỏ 700 vs 587+140 do hai bộ luật khác nhau, cần kiểm lại khi chốt.
  Không đo được: độ đúng của nhãn (không có nhãn tay), và tỷ lệ sau khi lọc IT và dùng năm kinh nghiệm. Script đo ở scratchpad phiên làm việc, chưa đưa vào repo.
- Số đo (09/11, 5.077 tin IT sau Clean, theo tiêu đề): UI/UX 48 tin (0,9%), Embedded/nhúng/firmware 71 tin (1,4%). Duy có nhóm Embedded + Product và không có UI/UX; spec gốc ngược lại. Xem `docs/tasks/cho_quyet_dinh.md` mục 2.
- Embedded và UI/UX: chưa hiểu rõ vấn đề nên **chưa chốt** (người dùng 09/11), giữ mở. Cần giải thích lại và đo trên dữ liệu trước. Cần xem cách Duy và spec xếp hai nhóm này rồi đếm trên dữ liệu.

**PRE-23. Lỗi parse tái hiện được** (Duy)

- "tối thiểu 10 triệu", "2 tỷ", "Không yêu cầu", "Điện Biên Phủ" (bị hiểu thành tỉnh), Python/PHP Developer, UI/UX bị phân nhóm sai.

**PRE-24. Test P3/P4 nằm ngoài `testpaths`** (Duy)

- `make test` không chạy chúng; chạy chung gây lỗi `tests/conftest.py:42`.

**PRE-25. `ledger.csv` bị `.gitignore` (`*.csv`)** (Phát)

- `cohort.py`, `finalize_cohort.py` đọc nó nên clone sạch không chạy lại được.

**PRE-26. `reports/preprocessing/05_encoding` phình git** (Phát)

- 95 file (pickle ~2,3 MB, npz, notebook HTML, `profiling.json` 19k dòng), trái quy tắc về `reports/` trong `CLAUDE.md`. Người dùng chấp nhận tạm, dọn sau.

**PRE-27. `tests/test_golden_field_preservation.py` lỗi collect** (Phát)

- Import module không tồn tại. Có thêm 12 lỗi ruff UP038 dù báo cáo ghi "Ruff pass".

**PRE-28. Cohort P5** (Phát)

- Giữ 5.104/5.177 tin (62 bị loại, 11 cách ly); 5.092 tin chưa duyệt; 17,1% (873) không có kỹ năng nào trong bộ 230; độ thưa 98,15%, ngoài khoảng 95–98% của task 05. Số lấy từ báo cáo của Phát, chưa kiểm chứng. Chưa quyết: chấp nhận, hay chỉnh bộ lọc/bộ kỹ năng.

## 3b. Data Mining

**MINE-1. Mining chưa chạy trên dữ liệu thật** (Phúc)

- Số liệu trong báo cáo là dữ liệu giả từ `mining/synthetic.py`.

**MINE-2. Thư viện mining chưa cài trong venv**

- `mlxtend`, `shap`, `hdbscan` đã khai trong `requirements.txt` (09/11); venv chưa cài nên 3 file test mining lỗi collect và 2 lỗi `salary_model`.

**MINE-3. `test_outlier_ratio_follows_quantile` fail khi thiếu `hdbscan`** (rơi về fallback sklearn).

**MINE-4. Khoảng k chưa thống nhất:** task 6–12, checklist 4–14, spec 07 3–15; code dùng 4–14.

**MINE-5. `load_mart_from_parquet.py` biến cột list thành chuỗi;** chưa có bảng `skill_salary_shap_values`.

**MINE-6. Ghi chú cho báo cáo đồ án:** SHAP không phải quan hệ nhân quả; `seniority_level` 0–4 gộp Thực tập và Mới tốt nghiệp (liên quan PRE-22).

## 4. Chung

**GEN-1. Khoảng 1.300 lỗi ruff tồn đọng** ở `collection/` và `tests/`. Dọn thành một lượt riêng.

**GEN-2. `README.md` và `docs/tasks/legacy_TASKS.md` lệch code.** Chi tiết ở mục "Known mismatches" trong `CLAUDE.md`.

**GEN-3. Dọn code theo `docs/code_quality.md`.** Báo cáo (`make quality`) liệt kê import thừa, hàm không ai gọi, module không ai import, hàm trùng logic và trùng tên. Người dùng duyệt từng mục (xóa, gộp hay giữ) rồi mới sửa. Báo cáo không bắt được chỗ tự tạo `boto3.client(...)`; các chỗ đó đã chuyển qua `get_r2_client()` (`docs/issue_log.md` L-24).

**GEN-6. Test ledger khác kết quả giữa Windows và Linux.** Cùng nguyên nhân SCRAPE-17.

**GEN-7. Code tải R2 tự dựng trong `preprocessing/integration`.** Dùng boto3 riêng, prefix cũ, bucket gán cứng, không qua `get_r2_client()`. Sửa cùng quyết định GEN-4.

**GEN-8. Mẫu báo cáo nghiệm thu chưa điền** ở `docs/tasks/` của Duy, Phúc, Sơn (mục 5 của mẫu).

**GEN-9. Đường `features.parquet` chưa thống nhất.** Spec 10 ghi `gold/features.parquet`; Phát ghi local `data/preprocessing/05_encoding/features.parquet` và đẩy `curated/preprocessing/features.parquet`; Phúc đọc `data/curated/...` và `data/preprocessing/05_encoding/features.parquet`. Quyết định 09/11: chưa chốt, gộp vào GEN-4. Khi layout R2 đổi, hai bên sẽ lệch nhau.

## 5. Chưa chốt

**GEN-4. Layout R2 chưa chốt (chờ biết các bạn trong nhóm đang lưu vào đâu)**

- Hiện trạng (liệt kê R2 ngày 09/11/2026, 12.989 object): `raw/` 12.826, `url_ledger/` 64, `staging/` 32 (8 nguồn × 4 bước), `curated/` 2, và các prefix ngoài hệ thống bốn tầng: `quality/` 26, `integration/` 18, `transformation/` 18, `silver/` 3 file JSON.
- Đích dự kiến theo `docs/spec/10_architecture.md`: giữ `raw/` và `url_ledger/` (Bronze); `silver/all.parquet`; `gold/gold_master_jobs.parquet`, `gold/features.parquet`, `gold/matrices/`. Chưa sửa tài liệu, chưa đụng R2.
- Đã sửa trong code (chưa merge, chưa chạy trên R2): `R2_LAYER_PREFIX` trong `collection/common/r2_storage.py` ánh xạ `staging` → `silver`, `curated` → `gold`, giữ `raw` và `url_ledger`; `scripts/migrate_lakehouse_layout.py --prefix-map` (chạy thử mặc định, chép rồi đối chiếu Size/ETag mới xóa).
- Còn lệch spec 10:
  - `canonicalize_lakehouse_key` từ chối `silver/all.parquet` (tầng staging/silver bắt buộc có tên nguồn ở cấp 2).
  - `preprocessing/common/r2_export.py` và `scripts/push_preprocessing_to_r2.py` vẫn đẩy 32 file theo nguồn thay vì một `silver/all.parquet`.
  - Gold đang là `gold/preprocessing/features.parquet`, spec ghi `gold/features.parquet`.
  - `scripts/push_integration_to_r2.py` ghi `integration/...` ngoài bốn tầng.
- Đã quyết (người dùng): xóa `quality/`, `integration/`, `transformation/`; bỏ 32 file `staging/` trên R2, chỉ giữ `silver/all.parquet`; 3 file `silver/*.json` chuyển sang parquet (chưa mở xem nội dung, chưa biết file nào thay được `all.parquet`).
- Cần quyết: các bạn khác đang đọc/ghi prefix nào (hỏi nhóm trước khi xóa hay chuyển); cách nhập `silver/all.parquet`; có đổi tên gold theo spec không.
- Cách xử lý: chốt xong thì sửa code còn lệch, cập nhật `docs/spec/10_architecture.md`, `docs/guides/cloud_r2_setup_guide.md`, `.agents/skills/r2-lakehouse-guide/SKILL.md`, `collection/CLAUDE.md`, `scripts/CLAUDE.md`, `AGENTS.md`; chạy `migrate_lakehouse_layout.py --prefix-map` chạy thử, gửi số liệu, chờ đồng ý rồi mới `--apply`.
