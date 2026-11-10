# Encoding Contract v1 — DRAFT, chờ Phát duyệt

> **Ghi chú 10/11/2026:** JEV, OpenJev và Qwen đã bỏ; cột xác suất `*_prob` không còn. Cờ thay thế: `it_rule_level`, `seniority_can_kiem`, `job_family_can_kiem` (xem `docs/spec/preprocessing/spec/P5_encoding.md`).

> **09/11/2026 — superseded cho run đã thực thi:** đọc [06_p5_execution_contract.md](06_p5_execution_contract.md). Agent_05 đã duyệt các policy cần cho run và đường dẫn task; bản này giữ lịch sử, không dùng các mục “chưa duyệt” bên dưới để phủ định quyết định mới. Nghiệm thu vẫn chờ AutoCAD scope theo câu trả lời mới nhất của Phát.

## Cập nhật vocabulary v2 — 09/11/2026

Các nội dung cập nhật trong mục này thay cho vocabulary/input proposals v1 bên dưới; phần còn lại vẫn **DRAFT** nếu chưa được Phát duyệt. Gói v1/evidence/SPEC gốc giữ nguyên.

**Đã duyệt theo agent_04 cập nhật:** giữ snapshot5177 và full driver contract làm baseline đợt này; không tích hợp extractor mới/sửa P4. Phạm vi vocabulary là hard skills (technology/tool/technical knowledge/method/practice) và behavioral soft skills. Bare vendor/certification/document/domain/role không tự là skill. Đúng230cột vẫn là yêu cầu; chưa duyệt toàn bộ230mục hoặc ngoại lệ frequency.

**Vocabulary hiện hành để duyệt:** `reports/preprocessing/05_encoding/approval_package_v2/vocabulary_proposed_v2.csv`; mapping `mapping_proposed_v2.json`, version `p5-review-rules-v2`. 230proposed +6reserves từ236eligible observed; không dùng shortlist v1/prototype thay thế. Canonical/aliases phải match bằng helper candidate duy nhất `preprocessing/encoding/candidate_lookup.py`: whole-value casefold, canonical luôn được thêm làm key, aliases cùng owner dedup; alias/slug collision khác owner fail; slug chỉ dùng column name. Không strip punctuation/fuzzy/substring/parent propagation. Đây là thay đổi candidate/review; production encoder chưa đổi. JSON loader `load_candidate_lookup(path, expected_count=230)` và `encode_candidate_rows` đã được dùng cho X review và counts trên snapshot.

Mỗi item bổ sung `skill_type=hard|soft|unresolved`, `entity_type` theo enum trong yêu cầu, `scope_decision=retain_proposed|exclude_proposed|review`, lý do riêng; metadata không thành model features. Danh sách chính chỉ gồm retain_proposed hard/soft có job>0, index0..229; mọi decision trống/statusproposed. Nhóm độc lập skill_type/job_family, không quota. Crosswalk giữ sáu tên legacy; 19mục group=null là gap metadata cần duyệt, không phải nhóm thứ7/soft skill giả. `group_definitions.json`/`group_crosswalk.csv` và [báo cáo v2](05_p5_vocabulary_v2_review.md) nêu rõ giới hạn task “Kỹ năng mềm” so nhóm legacy có methodologies. Six-group coverage có thật nhưng không bảo đảm mọi hard skill khớp sạch một nhãn task.

HTML/CSS, Agile/Scrum giữ composite, không suy từng thành phần hoặc AND; Machine Learning broad không suy framework; TensorFlow Serving riêng. Không gộp Collaboration→Teamwork; Collaboration có owner riêng. Cẩn thận→Attention to Detail và Prototype→Prototyping defer, chưa áp trong mapping. Vendor Cisco/Juniper/SAP, ERP/CRM/Data Engineering đang review ngoài230; chứng chỉ và bare document tags tách riêng. Chỉ context review, không extract thêm từ JD. Canonical mới dịch tên từ source tiếng Việt có explicit alias/evidence, không mở rộng nghĩa để đủ width.

**Validation hiện có:** snapshot5177, Xreview5177×230 uint8,0zero columns;214hard/16soft;jobcoverage4277/5177;21845 canonical pairs trong selected vs21854 pool236;21978/33136 source-value-paircoverage;98,1654%sparsity. **137 mục dưới20** vẫn là ngoại lệ proposed, chưa ghi đè policy≥20. Sparsity hơi vượt khoảng task95–98%, cần xử lý deviation trước nghiệm thu. 12canonical yêu cầu đều match khi không nằm trong aliases (unit tests); canonical-key-only delta trên snapshot là0 cho cả12, có CSV/ID evidence. Frequency/bit/ID union dùng cùng loader; không dùng raw top230 để chứng nhận v2.

**Unresolved Decisions còn lại:** duyệt từng mục/alias và crosswalk nhóm; ngoại lệ tần suất/sparsity; missing/unknown/anomaly policies trong §1–3; TF-IDF ownership/view3000 vs100 trong §5; Golden candidate/production path trong §6. Baseline snapshot không còn là quyết định chờ duyệt; lineage P2/P3/sourcecommit và Python3.12 vẫn là giới hạn evidence. `skill_matrix_review.npz` không thay features/C/TF-IDF/Golden, chưa đủ nghiệm thu P5. 49related tests + Ruff pass; whole-repo `make test` có6collection errors ngoài thay đổi này (chi tiết logs v2), không claim toàn repo pass.

---

## Contract chi tiết — đọc cùng cập nhật v2 ở trên

Khởi tạo08/11, cập nhật09/11/2026. Đây là **Engineering Recommendation**, không cập nhật SPEC hay hợp thức hóa production hiện tại. Cơ sở: SPEC-01…13 đã phân tích trong `05_p5_specification_analysis.md`, task `docs/tasks/05_phat_encoding_and_matrices.md`, contract lịch sử `docs/tasks/05_phat_encoding_implementation_contract.md`, AGENTS, preprocessing/CLAUDE và yêu cầu agent_04 cập nhật. Full driver contract, width230, snapshot5177 và phạm vi hard/soft đã duyệt; danh sách/mapping/group cụ thể, ngoại lệ tần suất và các policy mới dưới đây chưa duyệt.

## 1. Input và producer

**SPEC Requirement / approved:** input logic `data/preprocessing/04_normalization/all.parquet`; không re-parse lương/location hoặc re-extract JD ở P5. **Baseline đợt này đã được Phát duyệt:** manifest tám partition P4 đã hash tại `reports/preprocessing/05_encoding/snapshot_audit_2026-11-08/manifest.json`, tổng 5.177 ID. Đây là snapshot lịch sử, không chứng nhận source commit hoặc upstream P2/P3 parity. Check SHA từng file trước đọc; key/source/rows/schema phải khớp; merge theo thứ tự manifest, giữ thứ tự trong partition; ghi `row_index` minh bạch. Fail khi ID duplicate/null hoặc schema cần thiết thiếu. Chạy candidate riêng, không thay canonical input chuẩn.

| Trường P4 | Kiểu/ý nghĩa | Producer full driver | Missing/type contract đề xuất |
|---|---|---|---|
| job_id_global | string, khóa toàn cục | P2 integration | Bắt buộc nonempty unique, không cast null thành string |
| source_platform | string enum 8 SOURCES | P2 | Bắt buộc hợp lệ và khớp partition |
| skills_list / skills_clean / skills_std | list<string> nullable | P2 metadata / P3 extract_skills / P4 canonicalize_skills | `skills_std` bắt buộc có cột; null khác []; scalar/list có phần tử null/non-string fail; không silently parse string |
| seniority | string nullable, 6 nhãn + Chưa rõ | P4 | Null/không biết→-1 kèm missing/unknown status; không đổi Intern/Fresher thành cùng mã |
| job_family | string nullable, JOB_FAMILIES | P4 | Freeze enum/version; missing/unknown khác nhãn hợp lệ bằng flags |
| employment_type | string nullable | P2/P4 passthrough | full_time/part_time/intern/other/missing; giữ raw trong P4 |
| locations | list<struct> nullable | P4 location normalizer | province/remote/foreign theo schema snapshot; không đổi scalar city thành list giả; missing flag riêng |
| log_salary_min/max | numeric nullable, log1p VND sau cap | P4 | Giữ NaN; finite nếu có; không log lần hai/đổi sang triệu |
| exp_min_years/max_years, headcount | numeric nullable | P3 parser, P4 passthrough | Giữ missing + indicator; không tự đảo range hoặc bù mean |
| is_negotiable, is_outlier_salary | boolean nullable | P3 salary / P4 IQR-cap | Cột phải tồn tại; null giữ trạng thái unknown bằng indicator |
| posted_date/deadline_date | date/parseable string nullable | P3 date parser | Parse invalid→derived NaN và quality reason, không sửa P4 |
| description_clean/requirements_clean | string nullable | P3 cleaner | Hai cột bắt buộc để TF-IDF; null→empty riêng từng field, ghi tỷ lệ missing |
| it_rule_level | integer nullable, rule level | P1→P4 passthrough | 1/2 hoặc unknown; không coi unknown là đã kiểm level1 |
| seniority_can_kiem/job_family_can_kiem | boolean nullable | P4 rule review | Null/missing không tự coi false |

Schema vật lý nested đầy đủ lấy từ manifest/Parquet, loader phải ghi Arrow schema hash sau hợp nhất; null-only/list<null> partition chỉ được cast sang kiểu đã chứng minh trong partition khác, không thay null bằng []. Field không dùng giữ nguyên ở Golden, không ép bỏ. Nếu cột bắt buộc thiếu thì fail contract, không tự tạo giá trị bù để chạy.

## 2. Ordered vocabulary và X

Nguồn đề xuất hiện hành: `approval_package_v2/vocabulary_proposed_v2.csv` (230) + dự phòng6; rules trong `mapping_proposed_v2.json`. Version proposal `p5-review-rules-v2`; bản approved tương lai phải là artifact mới có version, checksum, người/ngày duyệt, scope input hash và ordered items. Không lấy prototype230 hoặc shortlistv1 làm mặc định đã duyệt.

Mapping candidatev2 có mỗi item `index`0..229, `canonical`, `column`, `group` nullable, `aliases`, `jobs`, `skill_type`, `entity_type`, `scope_decision`, `reason`, statusproposed/decisiontrống; input hash ở cấp mapping. Approved artifact tương lai phải bổ sung decision_reference và version/hash ràng buộc. Thứ tự CSV jobs giảm/canonical tăng là thứ tự đề xuất; sau duyệt freeze, không chọn lại topK theo run. Sáu nhóm kỹ năng không ánh xạ job_family; bao phủ cả sáu, không quota cân bằng;19mục knowledge để nullgroup chờ crosswalk. Không gọi nullgroup là nhóm thứ7 hoặc soft skill. Điều này cần ngoại lệ rõ với câu “phân bổ đều” trong task §3.

Tên cột `skill_<slug>` theo task; dùng quy tắc hiện có `to_col_slug`: lowercase, C#→csharp, C++→cpp, .NET→dotnet, fold Unicode, nonalnum→underscore, strip. Cột trống/duplicate/collision phải fail trước ghi; không tự suffix hoặc gộp. Lưu cả canonical/column/index để consumer không tự suy slug.

Match whole value sau casefold, explicit alias theo artifact; không substring JD, không bỏ punctuation tùy tiện hoặc fuzzy match. Alias có hơn một owner fail. Job có cả hai alias chỉ bật một bit. X[i,j]=1 iff skills_std của job i có giá trị match alias/canonical j, else0; X uint8, N×230. Mỗi canonical đề xuất có observed_jobs>0; zero column ở tập dữ liệu tương lai vẫn giữ 230 và report, không bỏ cột. Tập fit nghiệm thu lần này không chấp nhận padding canonical chưa quan sát.

Null skills→230 bit0, `skills__missing=1`; []→bit0, missing0, empty1. Unknown/outsidevocab không phải missing: bits0 cho giá trị đó, `other_skills_count` là số distinct whole value casefold chưa match, không cộng alias trùng. Sidecar unmatched giữ ID, original_value, normalized_value, reason; không gọi là canonical hoặc thêm vào taxonomy. Báo riêng null/empty/unmatched_only. Chỉ `skill_` columns trong ordered array là X; quality fields dùng `skills__...` để tránh selector prefix nuốt nhầm.

## 3. Features và anomalies

`features.parquet`: `job_id_global:string` + numeric features, một dòng/ID cùng order input. Đúng230 uint8 skill columns, còn lại E1–E8 + quality indicators; **230 không phải tổng số cột features**. Snapshot encoder hiện tại 291 cột, draft có thêm unknown indicators nên không khóa tổng bằng291. Dictionary phải liệt kê chính xác ordered columns/dtypes/source/formula/missing policy; consumer dùng arrays, không suy từ tổng width.

E1 seniority_ord int8: Thực tập0, Mới tốt nghiệp1, Junior2, Middle3, Senior4, Trưởng nhóm/Quản lý5, Chưa rõ/null/unknown -1; thêm missing/unknown flag để phân biệt. E2 job_family theo frozen JOB_FAMILIES; source theo8SOURCES; employment theo5nhãn trên. Null/unknown có indicator, không masquerade một nhãn known. E3 top10 tỉnh xác định từ snapshot (dedup province/job, tie tên tăng), freeze list trong dictionary, other/remote/foreign theo locations; không refit ở transform. E4 theo §2. E5 năm numeric trong §1 float32 và __missing uint8. E6 hai boolean→0/1 và __missing; nếu unknown, giá trị mã0 chỉ là placeholder với flag1, không phải quan sát false. E7 posted_month float32 và days_to_deadline float32, mỗi cột có missing indicator. Deadline trước posted: days_to_deadline NaN + flag/reason. E8 it_rule_level__2 và hai review flags uint8 có missing indicators; missing không chứng nhận negative.

Kinh nghiệm min>max: giữ nguyên hai số, thêm `exp_range_invalid`, không tự swap hoặc sửa P4; consumer RF phải loại/resolve trước fit và ghi quyết định. Date invalid giữ P4raw và derived missing; date inverse không tạo days âm. MNAR salary thỏa thuận giữ NaN, không zero/impute. Outlier flag giữ cap từ P4, P5 không cap lại. Mọi coercion failure được đếm theo field/ID trong validation report. Thay đổi này so code hiện tại (fill missing flag=False) cần Phát duyệt; không tuyên bố đã áp dụng.

## 4. Skill co-occurrence

Tên task `skill_cooccurrence.parquet`; C=int64(X).T @ int64(X), không nhân uint8 rồi mới cast. Wide230×230; columns là ordered skill column names, row index là cùng ordered names được Parquet lưu index metadata; không thêm cột dữ liệu thứ231 để chứa label. Dictionary ghi cả canonical labels và column labels/order. C_ij=count distinct jobs có cả i,j, diagonal=count jobs có i. C đối xứng, nguyên≥0, diagonal≤N; C_ij≤min(C_ii,C_jj). Skill không xuất hiện→row/column0 giữ nguyên vị trí. Roundtrip phải trả đúng index, columns, int64; fixture >255 job bắt lỗi overflow.

## 5. TF-IDF theo task — đề xuất cụ thể

Input đúng `description_clean + '\n' + requirements_clean` của full contract, đại diện task job_description/job_requirements; không đồng thời nối raw+clean của cùng nội dung. P3 đã clean HTML/NFC; P5 lower qua vectorizer, không dịch/tokenizer LLM. Giữ accents, không stemming. Cột thiếu fail, null từng field→empty, row rỗng→zero vector; ghi số row rỗng.

Khuyến nghị SPEC-06 §5.3: analyzer=word, ngram_range=(1,2), min_df=5, max_df=.8, max_features=3000, norm=l2, use_idf=True, smooth_idf=True, sublinear_tf=False, binary=False, lowercase=True, strip_accents=None, token_pattern=`(?u)\b\w\w+\b`, dtype=float32. Default token pattern không biểu diễn riêng C/C++/C# đầy đủ; đây là giới hạn text view, không sửa X. `min_df` tính document count trên toàn snapshot. Stopwords dùng đúng tập hiện có COMMON_JD_STOPWORDS (dedup/sort), freeze thành `preprocessing/encoding/assets/jd_stopwords_v1.json` lúc triển khai, version/hash ghi manifest; chưa tự mở rộng danh sách.

CSR float32 lưu `tfidf_matrix.npz` (scipy save_npz); `tfidf_rows.parquet`: row_index:int64 0..N-1, job_id_global:string; `tfidf_vocabulary.json`: ordered index, feature_name=`tfidf_<index padded4>`, term:string, idf:number; `tfidf_config.json`: đầy đủ config, stopwords/version/hash, text fields, sklearn version, corpus hash. Persist đầy đủ vocabulary+IDF để reconstruct transform; không pickle untrusted object. Empty vocab/Error không được đánh success hoặc silently bỏ artifact. max_features là upper bound, actual V đo thật; nếu V<2000 thì báo deviation so task 2000–3000, chưa đạt nghiệm thu nếu chưa được duyệt ngoại lệ, không padding từ ngữ giả.

Mâu thuẫn SPEC-07 §3.1 K=100 ngram: đề xuất P5 cung cấp view tối đa3000; Mining nếu cần100 phải chọn view riêng/version riêng, không gọi100 là full P5 output. Cần Phát duyệt cách bàn giao này trước hoàn thành; không tự sửa SPEC-07.

## 6. Artifact và Golden

Tất cả dưới candidate root `data/preprocessing/p5_candidates/<run_id>/`, không đụng production. Đường dẫn chuẩn trong task chỉ là mục tiêu bàn giao tương lai, không cho phép ghi đè ở lượt này.

| Relative path | Format/schema | Vai trò/consumer |
|---|---|---|
| `05_encoding/features.parquet` | Key + E1–E8/flags, ordered numeric schema | Chính thức candidate; Mining dùng subsets đã khai báo |
| `05_encoding/skill_cooccurrence.parquet` | Wide230×230 int64 index/columns như §4 | Graph/community; không là transaction input FP-Growth |
| `05_encoding/encoding_dictionary.json` | version/status/input hashes/vocabulary/feature arrays/types/categories/location list/missing policies | Mapping chính thức của run |
| `05_encoding/tfidf_matrix.npz` | N×V CSR float32 | Clustering text view |
| `05_encoding/tfidf_rows.parquet` | row_index,job_id_global | Liên kết sparse row với X/Golden |
| `05_encoding/tfidf_vocabulary.json`, `tfidf_config.json` | §5 | Mapping/transform reproducible |
| `curated/curated_flat_golden_jobs.parquet` | Toàn bộ thuộc tính P4 + đúng230skill columns | Golden theo task, không thêm mọi featureE1–E8 vào Golden một cách ngầm định |
| `05_encoding/skill_unmatched.parquet` | job_id_global,original_value,normalized_value,reason | Intermediate/review, không tự làm model feature |
| `05_encoding/data_quality.parquet` | ID,field,reason,value_repr nullable | Intermediate anomalies/missing provenance |
| `05_encoding/validation_report.json` | check/status/count/evidence/reason | Acceptance evidence, không chứa số giả |
| `05_encoding/artifact_manifest.json` | Run metadata + current artifacts hashes | Ghi cuối, success chỉ khi toàn bộ required artifacts pass |

Parquet Snappy; data tables index=False trừ C có labelled index. Golden join one-to-one theo ID, assert same set/order/rows; fail column name collision thay vì suffix/drop P4field. Không inner join mất dòng, không sửa hoặc ghi đè P4. Giữ all attrs/nested/null của P4; nếu merge schema không lossless thì fail. Candidate Golden riêng không vi phạm lệnh không ghi legacy `data/curated` hiện hành trong preprocessing/CLAUDE.

Manifest ghi schema_version, run_id, status=candidate, input per-file key/ETag/SHA/rows/schema + parent manifest hash; code HEAD + dirty state + hashes files được thực thi; env Python/numpy/pandas/pyarrow/sklearn/scipy; vocabulary/config/stopword hashes; ordered job IDs hash; mỗi current artifact relative path/bytes/SHA256/shape/schema; checks và quyết định tham chiếu. Không bịa producer commit từ code_version report. Output root mới, fail if exists; partial fail không success manifest; chỉ current artifacts của run, không kê stale files. Timestamp không dùng làm content reproducibility criterion. Publish/copy về canonical paths là bước khác cần authorization, không thuộc candidate run.

## 7. Downstream compatibility

| Module | Input đúng | Điều kiện bắt buộc |
|---|---|---|
| FP-Growth | X boolean N×230 từ dictionary.skill_columns | Không ID/other_count/flags/TF-IDF/C; support denominator là job cohort đã khai báo, giữ all-zero jobs trong full cohort; filter subgroup phải ghi N mới |
| K-Means/HDBSCAN + PCA | X và/hoặc TF-IDF view theo SPEC/Mining quyết định | Join bằng ID, không zip sau sort/filter; freeze view/scale/weights/train config; sparse text dùng reducer phù hợp, không dense mù quáng; HDBSCAN không tự thay thuật toán đã chọn |
| Random Forest/SHAP | Features subset + salary target từ Golden, aligned ID | Loại target/log_salary_min/max và mọi biến dẫn xuất target khỏi predictors nếu dự đoán salary; giữ MNAR, xử lý missing và inverseexp rõ ở Mining; fit preprocessing train-only, SHAP cùng feature names/order |

P5 không tự quyết định salary target/cohort/weight/reducer/hyperparameters Mining. Manifest chỉ cung cấp đủ semantics để Mining quyết định. C là count aggregate, không thay per-job X. Nhóm vocabulary không phải job_family clustering hoặc ground-truth label.

## 8. Validation, tests và điều kiện nghiệm thu

Unit tests: exact alias/casefold và per-job union; empty/null/unmatched khác nhau; C/C++/C# slug, alias/slug collision fail; count>255; absent skill keeps column; categoryunknown/-1/flags; nullable numeric/negotiable; invalid date/negative days; inverse exp preserved+flag; empty/one doc TF-IDF fail/zero vector; stopwords hash/config transform roundtrip. Synthetic fixtures chỉ kiểm logic, không dùng làm số liệu báo cáo.

Integration/data validation trên snapshot thật: SHA8files; N5177=uniqueIDfeatures=rowsTFIDF=rowsGolden; order/key mapping exact; 230columns binary uint8; each bit đối chiếu input alias; all accepted skills observed; unmatched counts distinct; missing flags khớp source; C int64 shape/index/columns/symmetry/diagonal/bounds và so independent job counts; TF-IDF finite/nonnegative CSR, idf/name/index bijective, row norms0/1; Golden attrs null/schema/value equality với P4 sau roundtrip; JSON mapping đầy đủ; Snappy; manifest/checksum đủ current artifacts. Re-run không ghi đè evidence. Đo sparsity/size/read time thật và so task; không ép đẹp số.

Acceptance: quyết định §9 được ghi; Python3.12, lint/unit/integration pass; toàn bộ required artifacts từ dữ liệu thật pass; deviations task/spec đã được Phát xử lý; manual decisions/input vẫn nguyên; bàn giao downstream không còn semantics mơ hồ. Tests trên snapshot cũ/prototype hoặc review script không đủ để nói P5 hoàn thành.

## 9. Conflict & gap còn phải ghi quyết định

| Tài liệu/mục | Xung đột hoặc gap | Trạng thái và đề xuất |
|---|---|---|
| Task05 §1/§3 vs SPEC06 §5.1 và localP5 §4 | 230 vs K100–200, dynamic topK | Width230 đã duyệt; frozen ordered vocabulary đề xuất, không dynamic |
| SPEC06 §5.1, task05 §3 | ≥20, phân bổ đều sáu nhóm vs137v2proposed dưới20, nhóm không đều và19mục chưa khớp sạch taskgroup | Chưa duyệt ngoại lệ/ngữ nghĩa crosswalk; khuyến nghị observed≥1 + manual per-skill, bao phủ sáu nhóm không quota; nếu không duyệt phải làm lại shortlist, không padding hoặc ép knowledge thành softskill |
| Task05 §1 vs full driver/localP5 | skills_extracted vs skills_std | Full driver làm baseline đã duyệt; không rename consolidated output để giả tương thích |
| Task05 §1/§3 vs localP5 §4 | skill_ vs skill__, dictionary/order chưa cố định từ đầu | Đề xuất task prefix skill_, ordered mapping freeze; không claim bản cũ đã đúng |
| SPEC06 §5.3, task05 §1 vs SPEC07 §3.1 | TF-IDF3000/2000–3000 vs100 | Đề xuất fullview3000, Mining view100 riêng; cần quyết định bàn giao |
| localP5 phần không encode JD vs task05 §1 | Ownership TF-IDF | Đề xuất utility/export trong P5 theo task; chưa coi local SPEC tự hết hiệu lực |
| task05 §1 vs preprocessing/CLAUDE pipeline5bước | Golden data/curated vs không ghi Goldenlegacy | Candidate Golden riêng, bàn giao production path còn chưa duyệt |
| Code run.py E6/E8 vs missing semantics chưa quy định | Fill false cho flag null, thiếu provenance | Đề xuất placeholder+missing flags; không tự biến unknown thành negative |
| SPEC06 phần dịch JD; văn bản JEV/LLM trong local SPEC | Dịch/model vs policy04/11 noLLM | Chính sách hiện hành noLLM theo preprocessing/CLAUDE, localSPEC banner/P0§6/L28; không phục hồi đoạn cũ |
| Manifest snapshot/reports lịch sử | Thiếu verifiedP2/P3/sourcecommit/precision labels | Ghi unknown, không giải quyết bằng suy diễn; snapshot5177/full driver đã duyệt làm baseline đợt này, không yêu cầu duyệt lại |

Các schema sidecar, sparse filename, stopword version, unknown categorical và detailed manifest trên là engineering proposals vì SPEC chưa quy định đủ; không trình chúng như yêu cầu nghiệp vụ gốc.
