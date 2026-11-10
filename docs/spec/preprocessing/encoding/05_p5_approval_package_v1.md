# P5 — gói duyệt triển khai v1 (08/11/2026)

> **Ghi chú 10/11/2026:** JEV, OpenJev và Qwen đã bỏ; cột xác suất `*_prob` không còn. Cờ thay thế: `it_rule_level`, `seniority_can_kiem`, `job_family_can_kiem` (xem `docs/spec/preprocessing/spec/P5_encoding.md`).

**Khuyến nghị duy nhất:** dùng nguyên snapshot P4 5.177 job đã kiểm SHA, giữ producer/extractor của driver năm bước cho đợt này; P5 chỉ ánh xạ theo vocabulary riêng sau khi Phát duyệt. Không tích hợp extractor mới ở đợt này. Đây là gói đề xuất, **P5 chưa hoàn thành**.

Đã duyệt qua yêu cầu agent_04: contract đầy đủ driver năm bước, đúng 230 cột kỹ năng, 230 không được coi là K tối ưu, bảo toàn evidence/quyết định tay, không sửa producer P4 hoặc vocabulary production. Mọi chính sách bổ sung bên dưới vẫn là **Engineering Recommendation / Unresolved Decision**. Các SPEC gốc không bị sửa.

## 1. Báo cáo chất lượng extractor và nguồn input

**Current Repository State.** Driver `scripts/run_preprocessing.py` gọi `transformation.run` rồi `normalization.run`. Extractor cũ `transformation/skill_extractor.py:extract_skills` lấy metadata + clean JD thành `skills_clean`; P4 `normalization/text_cleaner.py:canonicalize_skills` tạo `skills_std`, giữ giá trị chưa biết. Từ điển cũ 40 canonical không phải giới hạn số giá trị metadata được bảo toàn.

Luồng consolidated `transformation/pipeline.py` gọi extractor mới `skill_normalizer.py`, dùng taxonomy 92 canonical, tạo `skills_extracted`. Nó không phải producer tương đương của full contract: khác seniority, đơn vị salary, location; thiếu clean text/log/date/headcount/flags cần thiết. Probe encoder hiện tại lỗi `KeyError: skills_std`; đổi tên một cột không sửa được khác biệt ngữ nghĩa.

**Evidence:** `reports/preprocessing/05_encoding/p4_k_decision_evidence_v1/` có `extractor_comparison_same_ids.csv`, `targeted_counts.csv`, `targeted_examples.csv`, `summary.json`. Replay pure functions cũ từ field giữ lại khớp snapshot 5.177/5.177 job. Extractor mới trên cùng ID/retained raw tạo 91 canonical quan sát, 4.533 job có skill, 27.325 cặp job–skill; 457 job mất toàn bộ skill và 225 job từ rỗng có skill. Baseline: 4.760 giá trị, 4.765 job có skill, 33.136 cặp. Đây là khác biệt biểu diễn, **không phải precision/recall với gold label** hoặc rebuild từ P2.

| Trường hợp | Snapshot/cũ | Mới | Diễn giải, không tự sửa |
|---|---:|---:|---|
| TensorFlow exact | 0 | 97 | Cũ gộp broad Machine Learning; không suy ngược framework |
| PyTorch exact | 0 | 108 | Tương tự; mới không chứng minh toàn bộ kết quả đúng |
| REST API | 1.370 | 570 | Alias/điều kiện trích xuất thay đổi; xem từng ID trong evidence |
| Automation Test | 201 | 0 | Taxonomy mới không giữ tên này; không mặc định không có demand |
| Automation Testing | 35 | 0 | Đề xuất chung canonical với Automation Test, cần duyệt |
| HTML/CSS | 299 | 291 | Mới gộp HTML hoặc CSS; không được hiểu là yêu cầu cả hai |
| Agile/Scrum | 951 | 0 | Tên mới Agile / Scrum có 800 job; tên và coverage cùng đổi |

**TensorFlow 4→0 đã giải thích:** trên cùng snapshot, đếm substring không phân biệt hoa thường `tensorflow` là 4 job; cả bốn chỉ có `Tensorflow Serving`. Đếm exact `TensorFlow`, kể cả casefold exact, là 0. Không có bằng chứng mất bốn job TensorFlow canonical. CSV kiểm tra từng ID: `approval_package_v1/tensorflow_count_explanation.csv`. Đề xuất giữ TensorFlow Serving riêng; ứng viên này nằm dự phòng, không suy ra TensorFlow.

**P2/P3 thật:** chưa tìm thấy `data/preprocessing/02_integration/all.parquet` hoặc `03_transformation/all.parquet` local. Reports lịch sử cùng 5.177 dòng/code_version `7dee2a4` không chứng minh parity ID hay gắn commit với bytes. Không tuyên bố đã rebuild P4 từ P2. Snapshot tám partition có source_platform và 62 cột, ID unique/non-null; manifest SHA `dd93db5c08b533725bd086315325c70ed37a8027b7149fc8327e5a6d3ca34ea4`. Dùng nguyên bytes local trong `snapshot_audit_2026-11-08/`; không cần cloud hoặc đổi canonical input chuẩn để thử P5.

**Bảo toàn metadata unknown:** giữ nguyên `skills_list`, `skills_clean`, `skills_std` và raw/clean JD trong snapshot/P4; P5 không sửa chúng. Mapping đề xuất là lớp riêng, chỉ match whole skill value/casefold; không substring extract JD, không biến mọi tag thành canonical. Các giá trị không có rule được đưa vào `unresolved_observed_values.csv`, sau triển khai là sidecar unmatched theo job; chỉ đếm other, không tự tạo cột. Nếu sau này dùng extractor mới, cần thiết kế riêng kênh unknown/evidence và kiểm P2/P3; không đưa thay đổi đó vào đợt này.

## 2. Vocabulary cụ thể để duyệt

Thư mục `reports/preprocessing/05_encoding/approval_package_v1/`:

| File | Nội dung |
|---|---|
| `vocabulary_proposed.csv` | 230 đề xuất, canonical/aliases/group/jobs/rationale/issue/status/decision |
| `vocabulary_reserves.csv` | 14 dự phòng, cùng schema; không tự thay thế skill bị bác |
| `all_curated_proposals.csv` | Tổng 244 ứng viên quan sát có rule rõ |
| `mapping_proposed.json` | Rules đề xuất, không phải dictionary production |
| `unresolved_observed_values.csv` | Giá trị chưa nhận: ambiguous/role/domain/chưa có rule; chưa phải reject tay |
| `tensorflow_count_explanation.csv` | Bốn ID và hai định nghĩa đếm |
| `summary.json` | Counts, checksum input và hai file quyết định được bảo vệ |
| `proposal_builder_source.py.txt` | Bản source chính xác lúc tạo evidence, hash khớp summary |
| `ambiguities_for_review.csv` | Composite/broad/distinct-product quan sát, count và đề xuất xử lý riêng |
| `validation.json` | Kiểm lại từng CSV từ snapshot, bảo toàn hashes, no alias/slug collision; chỉ PASS review evidence |
| `pytest_review.xml`, `pytest_existing.xml` | 4 tests review và 23 tests P5 hiện có đều pass |

Nguồn là snapshot `skills_std`, không chỉ tên trong prototype. Rules do agent đề xuất, chưa phải taxonomy được xác thực ngữ nghĩa. Một canonical chỉ được nhận nếu có ít nhất một whole value tương ứng thực sự quan sát. `jobs` là hợp các ID sau alias, không cộng tần suất alias; mỗi job tính một lần. Chọn theo jobs giảm dần, canonical tăng dần khi hòa. Nhóm là nhóm kỹ năng sáu loại, **không phải job_family**. Không áp quota bằng nhau: phân bố đề xuất 22 ngôn ngữ, 11 framework/library, 18 database/caching, 33 cloud/devops, 97 tools/architecture/protocols, 49 methodology/soft skills. Một số nhóm rộng chứa concept; Phát cần duyệt phạm vi IT/soft skill của chúng.

**138/230 đề xuất có dưới 20 job**. Đủ 230 ứng viên quan sát, nhưng chưa đủ cơ sở gọi chúng là 230 canonical đã duyệt hoặc đáp ứng SPEC ≥20. Không dùng claim “152 raw value ≥20” làm kết quả sau mapping. Khuyến nghị đợt này: cho phép ngoại lệ ≥1 job với duyệt từng skill; không padding, không tự hạ ngưỡng ngầm. Nếu Phát giữ ≥20 hoặc bác nhiều mục mà dự phòng không đủ, dừng và báo thiếu; không tự lấp đầy.

Các trường hợp cần tách/chưa nhận: C/C++ (không tự chia thành hai), HTML/CSS và Agile/Scrum (composite, không suy ra từng thành phần), Machine Learning (broad upstream, không tách TensorFlow/PyTorch), TensorFlow Serving (khác TensorFlow), role/domain/tag dài chưa có rule (không gọi là canonical). Danh sách chi tiết và số job nằm ở CSV, không tự đánh dấu reject/approved. Mọi `decision` của vocabulary vẫn trống. Hai `candidate_generated.csv`, `candidate_decisions.csv` cũ giữ nguyên checksum.

## 3. Patch dự kiến sau duyệt

Không cần sửa producer P3/P4 cho phương án này. Không áp patch vocabulary production ở lượt hiện tại.

| File/hàm | Patch cụ thể đề xuất | Kiểm thử |
|---|---|---|
| `encoding/run.py:encode_dataset`, `skills_taxonomy_230.py` | Nhận frozen vocabulary artifact có version/hash; bỏ phụ thuộc prototype khi chạy candidate; validate đúng 230, alias owner duy nhất, slug duy nhất; giữ E1–E8 | Alias union, C#/C/C++, unknown/null/empty, duplicate ID, vocabulary thiếu/collision, missing flags |
| `encoding/run.py:run`, `run_encoding.py` | Cho explicit snapshot manifest/input và output candidate; fail nếu output tồn tại; merge partition giữ schema/order; không đổi `IN_FILE` chuẩn | 8 source SHA/schema/count; output existing fail; không đọc stale production |
| `encoding/tfidf_extractor.py:extract_tfidf_space` | Chỉ clean description+requirements, CSR trực tiếp, stopword asset đóng băng; persist rows/names/IDF/config; không silently SKIPPED thành success | Null/empty JD, duplicate raw+clean không double count, empty vocabulary fail, fit/transform roundtrip |
| Runner/export trong `encoding/` | Golden candidate join 1:1 ID; dictionary/schema/sidecars và manifest cuối; không sửa common R2 exporter | Keys/schema/hash và failure không để manifest success/stale artifacts |

Đầu ra candidate đề xuất: `data/preprocessing/p5_candidates/<run_id>/05_encoding/` và `.../<run_id>/curated/curated_flat_golden_jobs.parquet`; adapter P4 gộp nếu cần ở `.../<run_id>/04_normalization/all.parquet`. Chưa tạo dataset ở các đường dẫn này. Không ghi đè `data/preprocessing/04_normalization/all.parquet` hoặc Golden chuẩn. Bản [contract dự thảo](encoding_contract_draft_v1.md) quy định schema và điều kiện kiểm.

## 4. Kế hoạch triển khai/nghiệm thu sau Phát duyệt

1. Ghi quyết định riêng của Phát và hash vocabulary đã chọn; không sửa file quyết định cũ. Kiểm tra còn đủ đúng 230, mỗi canonical có evidence và aliases không tranh ownership. Bất kỳ thay đổi snapshot đều làm counts/shortlist cần kiểm lại.
2. Triển khai loader/validation và candidate runner theo patch table; không đổi P4/shared taxonomy. Review-only tests khi tạo gói nằm trong `preprocessing/encoding/tests/`; đợt refactor đã chuyển nguyên nội dung sang `tests/unit/test_encoding_approval_package.py` để được collection mặc định.
3. Chạy offline tests; chạy full candidate trên 5.177 job đã kiểm SHA, đối chiếu X theo từng ID/alias, C int64, TF-IDF row alignment, Golden roundtrip và manifest. Chạy lại cùng input/config ra cùng logical data/hash artifact deterministic; timestamps tách khỏi content identity.
4. Kiểm feature subsets cho FP-Growth, clustering và RF; không chạy ML trong lượt này. Đo sparsity, file size/read time thật so task; không hứa trước 95–98%, <25MB/<0.3s. Nếu không đạt, ghi số thật và yêu cầu ngoại lệ trước nghiệm thu.
5. Chỉ xác nhận P5 hoàn thành khi artifacts thật đều pass, các quyết định semantics được ghi, chạy Python 3.12 theo SPEC, và bàn giao feature mapping/TF-IDF/Golden không còn mâu thuẫn. Python hiện có 3.14.4 chưa thay cho chứng minh 3.12. Không tự publish/commit/push/cloud.

## 5. Giới hạn còn giữ công khai

Không có nhãn tay đánh giá precision extractor. Không xác nhận snapshot là P4 mới nhất trên R2 hoặc biết producer commit từ report đơn thuần. Các counts chỉ ràng buộc bytes snapshot được hash. Khuyến nghị dùng snapshot cho đợt này là quyết định input còn cần Phát duyệt, không phải chứng nhận nguồn P2/P3. Nội dung lịch sử trong handoff giữ làm evidence, không thay thế quyết định mới.

## 6. Kiểm chứng đã chạy và cách tái lập

Đã chạy kiểm tra tám SHA/source/row counts/unique IDs; tái tính toàn bộ 244 ứng viên bằng hợp job IDs và so chính xác cả ba CSV; no alias/slug collision cho230; mọi entry được quan sát và mọi decision trống; checksum hai file cũ nguyên vẹn. `validation.json` lưu hashes gói hiện tại. Ruff toàn `preprocessing/encoding/` pass. Unit tests: **4 review +23 hiện có pass**, Python3.14.4; chưa kiểm Python3.12. Đây không phải nghiệm thu X/C/TF-IDF/Golden theo vocabulary mới vì chưa triển khai chúng.

Từ repo root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m preprocessing.encoding.validate_approval_package
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_encoding_approval_package.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_encoding_step.py tests/unit/test_encoding_safety.py tests/unit/test_vocabulary_comparison.py
ruff check --no-cache preprocessing/encoding/
```

Validation tái tính từ snapshot và kiểm CSV hiện có, không ghi lại vocabulary. Builder `prepare_approval_package.py` cố ý fail khi thư mục output tồn tại để bảo toàn evidence; bản source gốc lưu cùng gói, bản hiện tại chỉ tách statement cho RuffE702, kết quả mapping đã so lại bằng validator. Validator ghi lại `validation.json` và bảng ambiguity xác định từ source; không chạm quyết định tay hoặc production.

Hai lần gọi pytest ban đầu không chạy tests (sai tên file; sau đó hook `tests/conftest.py` không chấp nhận collection chung ngoài `tests/`). Giữ log XML thất bại `test_results.xml`/`pytest_validated.xml`; sau đó tách hai lượt đúng như lệnh trên, kết quả 4 và23pass ở hai XML chính. Không thay hook repository để né lỗi.
