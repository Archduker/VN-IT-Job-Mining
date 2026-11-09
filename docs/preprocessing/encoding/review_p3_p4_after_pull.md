# Review P3–P4 sau cập nhật — tác động P5 (08/11/2026)

> Bản review lịch sử, nay được lưu trong repository. Các nhận định trạng thái worktree ở thời điểm review có thể đã thay đổi; xem [báo cáo đầu mối hiện hành](05_p5_handoff_2026-11-08.md).

## A. Phiên bản và phạm vi

- Repo: `/home/phat/Downloads/2026/Data_mining/Project_Data_Mining/VN-IT-Job-Mining`.
- Branch `feature/p5-encoding-matrices`; HEAD `f43809001d77c77f31bdf18d898e0faea7e81a44`.
- Reflog xác minh: mốc cũ `c1555c0`; 21:41:36 ICT rebase bắt đầu từ `origin/feature/p3-p4-transform-normalize` tại `9b33a05`, sau đó replay hai commit tài liệu `80eadc1`, `f438090`. Đây là rebase, không suy đoán một merge/pull khác. Commit của Duy: `9b33a05a89ba34e6947851b3bdc446b85a537a86`.
- `git diff c1555c0 HEAD -- preprocessing scripts docs/preprocessing`: 18 file, 3519 insertions/788 deletions; thay đổi ở P3/P4/dictionaries. Driver năm bước, `transformation/run.py`, `normalization/run.py`, `skill_extractor.py`, `text_cleaner.py` không đổi trực tiếp trong diff này.
- `git status --short`: không có tracked modifications; còn các file untracked P5/docs/notebook/audit/tests từ trước. `stash@{0}` chứa thay đổi tracked P5/r2_export/report/tests (4 file, 510 insertions/465 deletions). **Không pop/apply stash.**
- Trạng thái source thực tế P5: `encoding/run.py:51–53` là min_count20/max200; không có hàm compute_skill_cooccurrence của lượt trước. Do đó kết quả 23 tests/Ruff cũ không thể được xem là trạng thái kiểm chứng của worktree mới; các untracked tests/audit phụ thuộc hàm này cần đối chiếu trước chạy lại.

## B. Thay đổi đáng chú ý: tồn tại hai luồng

| Luồng thực tế | Call-site | Đường đi và tác động |
|---|---|---|
| Driver năm bước cũ | `scripts/run_preprocessing.py:24–28,48` | gọi `transformation.run.run` rồi `normalization.run.run`; P2→P3→P4 Parquet; vẫn dùng skills.json 40 canonical |
| Consolidated mới | `transformation/run_transformation.py:11–14` → `pipeline.main/run_pipeline` | P2→P4 trực tiếp, thêm 10 feature; không tạo output P3 của driver cũ |
| Validator mới | `normalization/run_normalization.py:15–37` | chỉ đọc/kiểm output consolidated, không chạy normalizer để tạo skills_std |

Pipeline mới dùng skill_normalizer, location_normalizer, experience_parser và job_family_classifier mới; driver cũ vẫn dùng extractor/text_cleaner cũ. Riêng experience_parser được thay ngay tại module path nên wrapper parse_experience mới **được driver cũ gọi**. Salary parser mới giữ parse_salary_cascade bằng re-export legacy (`salary_parser.py:18–24`); driver cũ chưa chuyển sang parse_salary mới. Legacy copy khác source cũ chủ yếu type hints/encoding qua diff đã đọc, không khẳng định byte-identical.

## C. Skill end-to-end và ca kiểm tra

**Luồng cũ:** `skills_list` + text description/requirements đã clean → `transformation.run.py:188–190` gọi `skill_extractor.extract_skills` → `skills_clean` → `normalization.run.py:155–157` gọi `text_cleaner.canonicalize_skills` → `skills_std`. Metadata ngoài dictionary giữ nếu không bị bộ lọc tag loại; text chỉ match dictionary. skills.json hiện **40 canonical/162 alias khai báo**, không phân nhóm. `_get_skills_lookup():254–265` dùng assignment nên có nguy cơ last-wins khi dictionary có collision; chưa chứng minh có collision thực trong file 40 mục này. Canonicalization bỏ trùng case-insensitive, giữ unknown string; scalar string trả [], malformed element được stringify.

**Luồng mới:** `ColumnConfig` chọn cột tên phù hợp đầu tiên trên toàn bảng (`pipeline.py:22–38,92–96`); không fallback từng row nếu cột ưu tiên đã tồn tại nhưng cell rỗng. `pipeline.py:119–133` dùng title + raw description + raw requirements + raw skills để extract trực tiếp → `skills_extracted`; không dùng skills_clean/skills_std. Không qua HTML cleaner ở luồng mới. Từ điển mới `skills_taxonomy.json` version1.0.0 có **92 canonical, 6 nhóm, 274 alias khai báo/268 alias sau fold**. Đây là capacity taxonomy, không phải số skill quan sát đủ230.

`skill_normalizer.py:92–145`: flatten field, casefold/bỏ dấu, match boundary/context, dedup canonical; unknown token không match bị loại khỏi kết quả (raw input vẫn giữ trong DataFrame). None/[]→[]; scalar Python→[Python]; dict có name Python được flatten và match; số123→[]; NumPy array Python/TensorFlow cũng match qua string representation, chưa phải kiểm tra array schema nghiêm ngặt.

Ca nhỏ đã gọi trực tiếp, chỉ chứng minh logic:

| Input | Luồng cũ canonicalize | Extractor mới |
|---|---|---|
| TensorFlow, PyTorch, Machine Learning | chỉ Machine Learning | ba canonical riêng |
| REST API / RESTful API | hai tên riêng nếu cả hai là metadata | REST API cho cả hai |
| Automation Test / Automation Testing | giữ hai tên riêng | [] cho từng tên; taxonomy không có canonical/alias tương ứng |
| Azure / Microsoft Azure | Azure | Microsoft Azure |
| GCP / Google Cloud Platform | GCP | Google Cloud |
| Kafka / Apache Kafka | Kafka | Kafka |
| HTML/CSS | HTML/CSS | HTML/CSS; riêng HTML hoặc CSS cũng kích hoạt canonical gộp này |
| Agile/Scrum | Agile/Scrum | Agile / Scrum; riêng Agile hoặc Scrum cũng kích hoạt canonical gộp |
| React, react, UnknownTool | React, UnknownTool | React; unknown không giữ trong extracted |
| c/c++ | không dùng để đánh giá thống kê | extract ra C và C++; taxonomy_lookup trả None vì collision |

`validate_taxonomy()` báo alias c/c++ thuộc C/C++. `taxonomy_lookup()` không silent last-wins, trả None khi nhiều đích; nhưng extract_skills có thể trả cả hai. Không được gọi điều đó là đã giải quyết hết ambiguity. `critical thinking` mới lookup/extract về Problem Solving; collision hai đích của prototype P5 là taxonomy khác và chưa được quyết định tự động theo source mới. Agile/Scrum lookup trả None nhưng extractor trả Agile / Scrum: lookup/extraction không hoàn toàn cùng semantics.

## D. Contract P4 → P5

Kiểu dưới đây là logic từ source/ca nhỏ; chưa phải Arrow schema của output mới tạo trên dữ liệu thật.

| Field P5 cần | Producer cũ / mới | Kiểu/ngữ nghĩa | Tương thích và bằng chứng |
|---|---|---|---|
| job_id_global, source_platform | input P2 giữ qua dict copy / DataFrame.copy | string nguồn; không tự sinh/sửa | new transform giữ ID/index trên ca index99; không validate ID non-null/unique hoặc source hợp lệ |
| raw_employment_type | P2 passthrough | nullable string | P5 đọc trực tiếp; new không tạo nếu input thiếu |
| skills_std | old canonicalize_skills; new không sinh | list canonical/unknown cũ | new chỉ skills_extracted; lệch trực tiếp |
| locations | old parse_locations + _normalize_locations; new chỉ city_normalized | old list dict tinh_key/remote/ngoai_vn; new string/special label | thiếu structured location để multi-hot P5; đa tỉnh thành Nhiều địa điểm làm mất chi tiết trong feature mới, raw vẫn giữ |
| seniority | old classify_seniority; new normalize_seniority | old nhãn 6 bậc/null; new seniority_level0..4/-1 | không đổi tên là tương thích được vì gộp Intern/Fresher và lệch ordinal |
| job_family | old classify_job_family_rule / new classify_job_family | old nhãn P5+Khác; new 12 nhãn handbook, unknown None | QA/QC, Security, BA, Product, System, Embedded lệch taxonomy P5; có nguy cơ one-hot all-zero |
| log_salary_min/max | old apply_global_salary_normalizations:264–266; new không sinh | log1p(VND capping) cũ | new salary_min/max/avg là triệuVND/tháng; tuyệt đối không đưa thẳng vào log cũ |
| exp_min_years/max_years | wrapper parse_experience cũ / parse_experience_range mới | float/null | mới reorder dải5–2 thành2–5; single new max None, wrapper old max=min; parse status không được pipeline lưu |
| headcount | old parse_headcount; new không sinh | numeric/null | chỉ có nếu input P2 đã chứa, không mặc định tương thích |
| is_negotiable | legacy cascade / parse_salary mới | bool / nullable boolean Pandas | giữ null lương khi negotiable; không impute |
| is_outlier_salary | old IQR/cap / new không sinh | bool | mới không thực hiện IQR/winsorize/log; không tự bổ sung 0 |
| posted_date/deadline_date | old process_dates; new không parse | old ISO/null; new chỉ passthrough nếu input có sẵn | chỉ raw_posted/raw_deadline từ P2 thì new không tạo ngày chuẩn |
| description_clean/requirements_clean | old _clean_text_field; new không sinh | old clean string/null | new đọc raw text; TF-IDF P5 không có input clean tương ứng |
| it_rule_level | P1/P2 passthrough | numeric | phụ thuộc input có, không do new tạo |
| seniority_can_kiem/job_family_can_kiem | old P4 flags; new không sinh | bool | P5 có thể mặc định0 khi thiếu; không đồng nghĩa đã kiểm nhãn |

**Tái hiện tương thích:** transform_dataframe ca một job tạo output mới; gọi encode_dataset hiện tại trên output đó → `KeyError: 'seniority'`. Đây là lỗi interface đã tái hiện, chưa phải thất bại thống kê trên dataset thật.

Salary probe `15–25 triệu`: new trả15/25/20, legacy15e6/25e6 (VND). `1000–2000USD`: new25.4/50.8 triệu. New pipeline không dùng JD salary fallback; không capping/log, không tạo salary_suspect. Missing/min/max giữ NaN. Đọc luồng old P4 cho thấy vẫn có IQR/winsor1–99%/log và hard1–500triệuVND.

Date probe old process_dates(08/11,01/11,crawl08/11) giữ đảo thứ tự và flag deadline_before_crawl; không có flag kiểm deadline<posted riêng. New pipeline không gọi parser ngày. Chín anomalies snapshot chưa thể được coi đã xử lý chỉ vì source experience mới reorder; cần chạy so sánh trên input raw mới để kiểm record thực.

New run_pipeline:158–205 bảo toàn row count, giữ index qua transform, nhưng không assert ID uniqueness/null; không có source-filter flag, không loại source lạ; ghi đè target mặc định P4 và hai subset, không dry-run/backup. Driver cũ có sources/dry_run nhưng vẫn ghi reports; subset với tổng input có thể fail conservation sau khi ghi reports từng nguồn. prepare_silver chỉ đổi format JSON→P2, có thể overwrite cùng path; không chứng minh JSON là input chuẩn.

## E. Snapshot 5177 và shortlist129

- 5177 lấy từ **tổng row count tám Parquet thực tế đã kiểm lại SHA256 theo manifest**, ID unique5177; số metadata rows cũng cộng5177. Báo cáo lịch sử `reports/preprocessing/04_normalization/_all.json:5–13` ghi code_version7dee2a4 và5177, generated_at2026-11-03T17:13:07Z.
- Manifest R2 snapshot chỉ có step/rows/generated-at, không có commit hoặc code hash ràng buộc trực tiếp bytes với source. Commit7dee2a4 tồn tại và là ancestor HEAD, nhưng **commit tạo snapshot: chưa xác minh**. Không suy từ cùng tên file hoặc ngày pull.
- Snapshot có skills_std/seniority/log/location schema cũ, không có skills_extracted/seniority_level/city_normalized. Chưa có bằng chứng được tạo bởi consolidated logic mới. Giữ nó như dataset phân tích lịch sử có checksum.
- README_DUY nói JSON937 records/3nguồn trong lần kiểm tra của tác giả; local hiện đo931 VietnamWorks. Không áp số937 của README vào file hiện tại.
- Shortlist129 được tính từ snapshot cũ + shared40/prototype P5, không phải taxonomy mới92. **129 và phần thiếu101 là kết quả của quy tắc shortlist cũ, không phải giới hạn kỹ năng trong source mới.** Không đổi vocabulary hoặc điền đủ230 từ tên taxonomy chưa quan sát.

## F. Vấn đề cũ và đề xuất

| Vấn đề | Trạng thái sau cập nhật | Việc tiếp theo Phát quyết định |
|---|---|---|
| Shared dictionary chỉ40, không nhóm | Có taxonomy mới92/6nhóm, nhưng luồng cũ vẫn40 | Chọn luồng hợp đồng chính thức |
| TF/PyTorch bị gộp | Giải quyết trong extractor mới; còn trong old skills_std | Không sửa P5 mapping để tự phục hồi; cần dữ liệu tái trích nếu chọn mới |
| REST/Azure/GCP/Kafka khác tên | New normalize nhất quán cho các ca đã thử | Thống nhất tên với P5, giữ version mapping |
| Automation Test/Testing | New không extract được, chưa giải quyết | Duyệt phạm vi taxonomy, không coi tự động bị loại là đúng |
| Alias collision | New lookup phát hiện c/c++, extractor multi-label | Quyết định semantics; không coi P5 prototype đã được duyệt |
| Exp đảo | New parser/wrapper sort được ca nhỏ | Xác minh lại đúng record thật; chưa ghi lại P4 |
| Dates đảo | Còn; new không parse date | Chọn policy derived missing/flag theo P5 contract |
| Feature interface/salary/seniority | Phát sinh split contract rõ rệt | Không chỉ rename vì thay đơn vị và mất thông tin cấp bậc |
| P5 fixes tracked lượt trước | Đang trong stash; worktree max200 | Review/khôi phục có chọn lọc chỉ khi Phát yêu cầu; không pop tự động |

**Đề xuất:** giữ nguyên snapshot5177 để tái lập EDA lịch sử. Phát chốt một entrypoint/contract trước; sau đó thử pipeline mới **trong thư mục riêng** từ P2 thật đã xác minh, output khác path P4 chuẩn, so row/ID/schema và skills trước/sau. Lượt này chỉ gọi hàm trên ca nhỏ, không chạy pipeline ghi dữ liệu. Nếu chọn new extractor, phải tái tạo P4 candidate (hoặc bước adapter/data materialization được Phát duyệt), chạy lại frequency, canonical mappings, candidate/full/priority, shortlist/reserves, K/threshold/source/group coverage, notebook/provenance và P5 input/roundtrip tests. Điều chỉnh P5 tên cột đơn thuần không đủ để tạo các field thiếu hoặc đổi salary/seniority đúng nghĩa.

Kiểm chứng: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest preprocessing/transformation/tests/test_feature_engineering.py -q -p no:cacheprovider` → **67 passed /0.36s**, Python3.14.4. Fixtures chỉ chứng minh logic, không phải chất lượng dữ liệu thật. Không kết luận Python3.12 hoặc acceptance P5. Không sửa source/shared dictionary, không gọi R2, không chạy lại pipeline ghi dữ liệu, không apply stash/commit/push. Báo cáo lưu ngoài repo trong workspace phiên này; mọi thay đổi local được giữ nguyên.
