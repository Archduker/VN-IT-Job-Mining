# P5 — bàn giao vocabulary v2 (09/11/2026)

> **Ghi chú 10/11/2026:** JEV, OpenJev và Qwen đã bỏ; cột xác suất `*_prob` không còn. Cờ thay thế: `it_rule_level`, `seniority_can_kiem`, `job_family_can_kiem` (xem `docs/spec/preprocessing/spec/P5_encoding.md`).

**Đã hoàn thành gói review v2 theo yêu cầu agent_04 cập nhật.** Đủ **230 kỹ năng đề xuất**, từ pool236 kỹ năng có quan sát; còn6 dự phòng. Đây là **đề xuất của Agent**, không phải nhãn tay hoặc vocabulary đã được Phát duyệt. **P5 chưa hoàn thành.**

Phát đã duyệt phạm vi hard/soft skill, giữ snapshot5177 và full driver contract, đúng230cột; chưa duyệt từng mục/alias/ngưỡng. Không thay P3/P4, shared dictionary, Mining, vocabulary production; không ghi cloud, commit/push hoặc đè artifact chuẩn. Gói v1 và quyết định thủ công giữ nguyên hashes.

## File gửi reviewer

Toàn bộ gói: `reports/preprocessing/05_encoding/approval_package_v2/`.

| File | Dùng để duyệt/kiểm tra |
|---|---|
| [vocabulary_proposed_v2.csv](../../../reports/preprocessing/05_encoding/approval_package_v2/vocabulary_proposed_v2.csv) | 230 mục, số job, aliases, hard/soft, entity_type, scope_decision, nhóm, lý do riêng từng mục, ngoại lệ frequency; decision trống |
| [mapping_proposed_v2.json](../../../reports/preprocessing/05_encoding/approval_package_v2/mapping_proposed_v2.json) | Ordered mapping dùng trực tiếp bởi loader candidate; canonical không cần lặp trong aliases |
| `vocabulary_reserves_v2.csv` | 6 dự phòng; không tự thay mục bị bác |
| `scope_review_all_v1_and_new.csv` | Review toàn bộ244 mục v1 và9 rule mới, kể cả mục chưa đưa vào230 |
| `exclusions_and_replacements.csv` | 16 mục rời danh sách chính,16 mục vào; thay bằng ranking, không phải đồng nghĩa giữa mục cũ/mới |
| `ambiguities_for_review_v2.csv` | Vendor/domain/document/composite/broad và ba alias generalization chưa áp |
| `certifications_separate.csv` | CCNA, CCNP, CEH, ITIL Foundation, CISSP; không chuyển thành competence |
| `context_evidence.csv` | 88 trích đoạn/metadata evidence của30 term: ID, field, offset, excerpt; không trích xuất thêm skill |
| `group_definitions.json`, `group_crosswalk.csv` | Định nghĩa/crosswalk sáu nhóm và các trường hợp không khớp sạch |
| `canonical_lookup_deltas.csv` | 12 canonical thiếu trong aliases v1: đếm lại bằng alias-only và canonical+alias |
| `job_ids_by_canonical.json`, `job_rows.csv` | Full ID union từng owner và row order để đối chiếu counts |
| `skill_matrix_review.npz` | CSR uint8 5177×230, chỉ X review; không phải full features.parquet hoặc Gold |
| `unmatched_source_values.csv` | Whole source values casefold chưa match230; chưa phải canonical/reject |
| `metrics.json`, `validation.json`, `provenance.json` | Công thức/mẫu số, kiểm tra, input/code/checksums và môi trường |
| `tests_p5.xml/.log`, `tests_full_offline.xml/.log`, `lint.log` | Kết quả kiểm thử và giới hạn toàn repo |

## Thay đổi ý nghĩa so với v1

- Đề xuất tách khỏi230: **5 chứng chỉ** (CISSP trước đó ở dự phòng) và **6 nhãn tài liệu** BRD/SRS/Test Plan/Test Case/Use Case/User Story. Excerpts có các hoạt động viết/thực thi thật, nhưng không chứng minh mọi tagged job có cùng hoạt động; không tự đổi BRD→BRD authoring hoặc Test Case→test-case design.
- **Cisco, Juniper, SAP** giữ `review/unresolved`: một số excerpts nói vận hành thiết bị/sản phẩm nhưng bare ecosystem tag không xác định một competence duy nhất. SAP FICO, SAP Integration Suite và ABAP vẫn giữ riêng khi có explicit tag; không bật SAP parent.
- **ERP, CRM, Data Engineering** giữ `review/unresolved`, chưa đưa vào230. Excerpts lẫn triển khai, tên hệ thống, team và career domain; chưa gán nghĩa competence cho toàn bộ job. **Business Intelligence** giữ hard/technical_knowledge proposed, có context phát triển BI/dashboard; không đổi thành một job title.
- Giữ Adobe tools, Typography, UI/UX Design: đó là tool/knowledge/practice phù hợp IT design, không loại vì thuộc thiết kế. Evidence giữ ID/field/excerpt, không phải chứng nhận precision trên mọi job.
- Giữ HTML/CSS và Agile/Scrum dưới dạng composite; không tách thành phần/không hiểu là yêu cầu cả hai. Machine Learning giữ broad và giới hạn upstream grouping; TensorFlow Serving riêng và không suy TensorFlow.

Các mục mới vào230 gồm9 rule quan sát: **AutoCAD, Logical Reasoning, Creativity, Negotiation, Systems Thinking, Requirements Analysis, Security Audit, IT Governance, Collaboration**; canonical tiếng Anh có explicit nguồn tiếng Việt trong aliases/observed_source_values, không suy từ JD hoặc role. Bảy mục từ dự phòng v1: **Pandas, TensorFlow Serving, Unreal Engine, ASP.NET Core, DynamoDB, NumPy, Nuxt.js**. Tất cả chỉ retain_proposed, không approved. V2 không tự thêm mục từ phần unmatched để lấp số còn thiếu.

| Alias cần review | Xử lý v2 | Counts v1→v2 |
|---|---|---:|
| Collaboration→Teamwork | Không gộp; Collaboration có owner riêng | Teamwork104→97; Collaboration7 riêng |
| Cẩn thận→Attention to Detail | Defer broad-to-specific generalization; Cẩn thận chưa match | 9→3 |
| Prototype→Prototyping | Defer artifact-noun→activity; excerpts chỉ hỗ trợ từng job | 11→4 |

Không tự bật parent từ child. Các alias dịch/đổi tên khác vẫn là explicit equivalence **proposed**, không tuyên bố tất cả chỉ là khác cách viết.

## Lookup và kiểm chứng trên snapshot

`preprocessing/encoding/candidate_lookup.py` cung cấp một loader/lookup cho cả bit và count. `load_candidate_lookup(mapping_proposed_v2.json, expected_count=230)` được dùng trong candidate path; production `encode_dataset` hiện chưa đổi. Match whole value bằng casefold, canonical luôn là key, canonical/alias trùng cùng owner được dedup; collision alias hoặc slug giữa owner khác fail. Slug chỉ đặt tên cột, không làm lookup key. C/C++/C#/.NET giữ punctuation; không fuzzy/substring/JD extraction/parent propagation.

**12 canonical yêu cầu** đều được kiểm: Microsoft Azure, Google Cloud, Unit Testing, Large Language Models, Natural Language Processing, SQL Server, Time Management, Independent Working, Oracle, Product Roadmapping, Spring Boot, Requirements Elicitation. Canonical keys trước đó vắng trong exported aliases, nhưng **thêm canonical key không làm tăng job nào trên chính snapshot này**: các literal canonical tương ứng không xuất hiện ở source. CSV ghi delta0 và added_job_ids=[] cho từng mục. Unit tests chứng minh chúng vẫn match khi xuất hiện trong input, không nhầm delta0 thành loader không cần sửa. Counts v2 được tính lại từ đầu, không chép counts v1.

| Chỉ số | Kết quả và mẫu số |
|---|---|
| Input | 5177 unique IDs,8 partition khớp SHA/rows/source; không đổi snapshot |
| X review | 5177×230 uint8;0 cột zero;236 eligible observed proposals,6 reserves |
| Hard/soft | 214hard /16soft; metadata này không thêm vào features |
| Job coverage | 4277/5177 = **82,6154%**, gồm empty jobs trong mẫu số |
| Canonical pairs | 21845 selected /21854 trong pool236 valid proposed = **99,9588%**; không phải độ phủ tất cả skill canonical có thể có |
| Source-value pairs | 21978 matched /33136 distinct whole-value casefold/job = **66,3267%**; alias trước mapping có thể là hai source values |
| Unmatched source pairs | 11158; chưa thể coi là11158 canonical pairs hoặc reject |
| Sparsity | **98,1654%** = zero bits/(5177×230), hơi cao hơn khoảng tham khảo95–98% của task; không điều chỉnh dữ liệu để ép khoảng |
| Frequency <20 | **137/230**, ngoại lệ vẫn proposed:22 mục2–4job,71 mục5–9,44 mục10–19;40 mục20–49,13 mục50–99,40 mục≥100 |

Không dùng coverage raw top230 hoặc extractor92 để chứng nhận v2. Không có nhãn tay precision/recall; observed/proposed không đồng nghĩa đã xác thực ngữ nghĩa.

## Nhóm và các quyết định còn cần Phát

Giữ tên sáu nhóm cũ, không quota: Programming Languages22, Frameworks & Libraries17, Databases & Caching5, Cloud & DevOps21, Tools/Architecture/Protocols55, Methodologies & Soft Skills91. **19 mục chưa có task group sạch** để `group` rỗng và `group_status=unassigned_crosswalk_needed`; đó không phải nhóm thứ7. Bao gồm các kiến thức ML/model, Statistics, Algorithms/Data Structures, Data Warehousing, Business Intelligence và năng lực ngoại ngữ. Không gọi chúng là soft skill để lấp nhóm.

Kafka/RabbitMQ/Spark/Databricks/DBT chuyển sang Tools; các thực hành Data chuyển sang Methodologies. skill_type độc lập với group: hard methodology vẫn hard. Framework bucket kế thừa runtime/engine/serving-tool exceptions như Node.js/Unity/TensorFlow Serving; đó là giới hạn của crosswalk đề xuất, không khẳng định mọi mục trong nhóm đều là framework. Nhóm trong task “Kỹ năng mềm” và tên legacy “Methodologies & Soft Skills” không hoàn toàn tương đương; cần Phát duyệt crosswalk, không mở rộng nhãn task âm thầm.

| Quyết định thực sự còn lại | Khuyến nghị |
|---|---|
| 230 canonical và explicit aliases v2 | Duyệt/sửa từng mục; giữ quyết định riêng, không sửa file tay cũ |
| Vendor/ERP/CRM/Data Engineering, nhãn tài liệu và ba alias generalization | Giữ ngoài230 hoặc defer như bảng ambiguity; muốn đưa lại cần xác định nghĩa/tag scope và đếm lại, không đổi tên để suy competence |
| 19 task groups chưa khớp + hard methodologies trong nhóm legacy | Duyệt crosswalk/nhãn metadata; không thêm chúng thành features hoặc giả gọi knowledge là soft |
| 137 ngoại lệ dưới20 và sparsity98,1654% | Cho phép đề xuất có quan sát để duyệt tay; chưa coi đã bỏ yêu cầu≥20 hoặc đã đạt mọi checklist task |
| Các policy còn DRAFT của Encoding Contract | Missing/anomalies, TF-IDF3000 vs Mining100, Golden candidate/production handoff vẫn cần quyết định; xem Contract cập nhật |

## Tests, bảo toàn và tái lập

**49 tests P5 pass** (26 mới +23 hiện có), Ruff phần P5 và test mới pass. Tests cover12 canonical absent aliases, union/dedup/casefold, owner/slug collisions, C/C++/C#/.NET, no parent/fuzzy, malformed/null/empty, mapping order/width. Snapshot validator so CSV frequency với saved matrix, independent source-value match và full ID union; kiểm excerpt đúng field/offset, mẫu số metrics và protected hashes.

Đã thử `make test` offline theo convention: **6 collection errors**, năm integration imports thiếu `sqlalchemy`, và test Golden cũ import module không tồn tại `preprocessing.normalization.target_schema_formatter`. Không sửa dependency/shared module ngoài scope, không ghi đây là toàn repo pass. Môi trường Python3.14.4, chưa kiểm Python3.12. Unit fixtures chỉ kiểm logic, không dùng làm số liệu thực tế.

Tái kiểm từ repo root (không regenerate/overwrite vocabulary):

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m preprocessing.encoding.prepare_approval_package_v2 --validate
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_encoding_candidate_lookup.py tests/unit/test_encoding_step.py tests/unit/test_encoding_safety.py tests/unit/test_vocabulary_comparison.py
ruff check --no-cache preprocessing/encoding/ tests/unit/test_encoding_candidate_lookup.py
```

Builder mặc định từ chối output đã tồn tại, bảo toàn gói v2. Bản builder lúc generate lưu `generation_builder_source.py.txt` khớp provenance; validator hiện tại bổ sung kiểm metrics và đọc offset CSV dạng số float. Lần xuất đầu dừng ở validation offset519.0, không phải dữ liệu bị sửa; sau sửa parser đã validate lại gói, không ghi lại vocabulary. `validation.json` ghi hash validator hiện tại và hashes artifacts.

Sau Phát duyệt vocabulary/policy mới có thể nối loader này vào candidate runner đầy đủ để kiểm features/C/TF-IDF/Golden. Ma trận X review hiện tại chưa thay các artifact P5 đó và không đủ để xác nhận P5 hoàn thành.
