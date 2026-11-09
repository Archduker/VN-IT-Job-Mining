# P5 Execution Contract — cohort_v1, 09/11/2026

Contract hiện hành theo quyết định Phát trong [authorization_agent07.md](../../../preprocessing/encoding/assets/cohort_v1/authorization_agent07.md). Điểm bắt đầu duy nhất là [handoff05](05_p5_handoff_2026-11-08.md), đã gộp report07 và các bản nháp. Bản 5.177 trước đây giữ nguyên trong history bundle; đợt _01 chỉ retire trial/debug/duplicate có hash và căn cứ, không đổi policy của contract.

## 1. Input, cohort và quyền áp policy

Input logic = snapshot P4 bất biến 8 partitions + ledger được ràng buộc quyết định. Không sửa P3/P4, bộ lọc upstream, shared dictionary, Mining hay job_family.

**N_P4=5.177=N_include5.104+N_exclude62+N_quarantine11. Noutput=5.104**, không tiếp tục claim bảo toàn 5.177 dòng output. Mọi ID xuất hiện đúng một lần trong ledger, thứ tự theo P4; ba tập rời nhau. Exclude/quarantine vẫn truy vết trong snapshot/ledger, không xóa source. Quarantine không đồng nghĩa confirmed non-IT.

Phát duyệt đúng27exclude/8retain của scope_review_v1 sau kiểm SHA CSV/queue/annotations. Áp policy cho19unresolved cũ:16exclude,3quarantine. Đã đọc toàn bộ nội dung có sẵn của31P1 còn lại:4include,19exclude,8quarantine theo policy; boundary mới/mâu thuẫn/thiếu evidence không tự mở scope.

410P2 chưa review và4.682job ngoài queue giữ **retained_unreviewed**. Include gồm12retained_reviewed+5.092retained_unreviewed. Không gắn verified IT cho toàn cohort, không gọi đây là nhãn gold hoặc đã sửa upstreamfilter. 85ID đã được review có giới hạn; family assessments là sidecars riêng, không là ground truth.

## 2. Runtime assets ổn định trong repository

| Asset | Đường dẫn repo-relative |
|---|---|
| Snapshot manifest | reports/preprocessing/05_encoding/snapshot_audit_2026-11-08/manifest.json |
| Frozen skill vocabulary | preprocessing/encoding/assets/frozen_vocabulary_v1.json |
| Stopwords | preprocessing/encoding/assets/jd_stopwords_v1.json |
| Ledger + version/checksum | preprocessing/encoding/assets/cohort_v1/ledger.csv và ledger.meta.json |
| Quyết định + bản authorization | preprocessing/encoding/assets/cohort_v1/decision_record.json và authorization_agent07.md |

Runtime không đọc Downloads. Frozen vocabulary giữ nguyên bytes/version `p5-v2-oracle-database-2026-11-09`,230canonical/columns/order; parent jobs counts là reference5177, observed cohort counts lưu riêng trong dictionary/CSV. Oracle Database không nhận bare Oracle; HTML/CSS,Agile/Scrum giữ composite; MLbroad,TensorFlowServing riêng, không parent/fuzzy/substring/JD extraction. Canonical+explicit aliases match whole-value casefold; same-owner dedup, owner/slug collision fail. Không refit topK hoặc thay zero-column bằng dự phòng.

Ledger có job_id_global,disposition,review_status,reason,evidence_reference,decision_reference; status chỉ gồm retained_reviewed,retained_unreviewed,excluded_by_approved_policy,unresolved_quarantined. Các ID27/8 đã duyệt được loader kiểm không đảo disposition. Hash/version của approval và review gốc phải đúng; không áp lên danh sách đã đổi.

## 3. Loader và lọc trước fit

Kiểm SHA/schema/rows/source từng partition, đủ8sources, ID string nonempty unique, requiredfields/arrayelements đúng kiểu. Union Arrow null-only types lossless, không stringify/nan-fill nested. Giữ thứ tự manifest/partition và row_index. Dựng lại chỉ cột khác type khi cần; tránh Arrow Table.cast làm sai độ dài child trong nested-list/null struct.

Requiredfields theo full driver: ID/source,skills_std,locations,seniority,job_family,**raw_employment_type**,posted_date/deadline_date,description_clean/requirements_clean,it_rule_level; numeric log_salary_min/max,exp_min/max_years,headcount; boolean is_negotiable,is_outlier_salary,seniority_can_kiem,job_family_can_kiem. Không yêu cầu P4 có employment_type mới; nếu cả hai employmentfields có và khác thì fail conflict. Không đổi đơn vị/log/cap lương upstream.

Apply ledger vào Arrow table và DataFrame **trước mọi fit/aggregate**: top10province,features,C,TF-IDF,quality,frequencies vàGolden chỉ dùng include. Ordered-ID hash của cohort phải khớp ledger.meta. Không có excluded/quarantine ID trong Mining outputs.

## 4. Feature contract

features.parquet = key+ordered numeric features, hiện5.104×314, trong đó X=5.104×230uint8binary. Chỉ dictionary.skill_columns là X; audit/count/ID/metadata không thuộc X.

- E1:6senioritylabels giữ mapping0..5; Chưa rõ/null/unknown=-1, missing/unknown indicators.
- E2:JOB_FAMILIES+Khác,8sources,employment full_time/part_time/intern/other/missing. Raw employment mapping được ghi source/hàm. Unknown không masquerade knownlabel.
- E3:top10province theo distinct job count giảm,key tăng, freeze lại theo cohort; other/remote/foreign và nullable indicators.
- E4:null skills→bits0+missing; []→bits0+empty; outsidevocab→unmatched original/normalized sidecar+distinct casefold/job count. Không tự coi tagunknown là canonical.
- E5:numericfloat32,NaN+indicator,không impute/log/cap lần hai; Golden giữ giá trị nguồn.
- E6/E8:booleanunknown placeholder0+missing,không false đã quan sát; rule/review flags giữ provenance.
- E7:invaliddate→derivedNaN+reason; deadline<posted→daysNaN+flag. Expmin>max giữsource+flag,không swap.
- AutoCAD còn3job đã được giữ trong quyết định8; presence flag là **audit**, không còn là blocker “chưa duyệt36AutoCAD”. Không tự loại/thay skill.

Dictionary freeze enums/top10/order/dtype/source/formula, reference vocabulary và observed_cohort_skill_counts riêng. audit_columns tách khỏi recommended predictors; recommendationsalary loại ID,audit/missing/review flags và target-derived logsalary/is_negotiable. Downstream vẫn phải chọn target/cohort và fit train-only; job_family nguồn chưa được sửa.

## 5. C, Golden và TF-IDF

C=int64(X).T@int64(X),wide230×230int64; labelled index/columns theo vocabulary. PhysicalArrowcột index riêng không phải cột dữ liệu thứ231. Kiểm symmetry/nonnegative/diagonal/bounds và independent intersections của từng cặp job-IDset.

Golden=62P4attrs của includedIDs+230skills=5.104×292. Join1:1ID,cùngset/order; fail column collision,không suffix/drop/innerjoin mất dòng. Arrowroundtrip giữ schema/values/nested/null nguồn; không đưa mọi E1–E8 vàoGolden. ParquetSnappy.

TF-IDF refit **chỉ trên5.104include**, description_clean+'\\n'+requirements_clean,nullfield→empty,không raw+clean lặp/translation. CSRfloat32,ngram(1,2),min_df5,max_df.8,max_features3000,norml2,use_idf/smooth_idfTrue,sublinear_tf/binaryFalse,lowercaseTrue,strip_accentsNone,wordtokenpattern mặc định. Freeze stopwordasset/version/hash hiện có; không fallback/padding. ActualV3000; nếuV<2000 hoặc error phải báo, không nới ngầm.

Artifacts tfidf_matrix.npz; tfidf_rows.parquet(row_index,job_id_global); orderedterm/index/IDF JSON; fullconfig/stopwords/libraryversion/corpus/ledgerhash. Reconstruct transform trong tolerance2e-6; finite/nonnegative,norm0/1. Đây là full-corpus exploratory view, supervised Mining phải refit preprocessing train-only; Mining100ngram là view riêng.

## 6. Stage, history và đường dẫn chuẩn

Bốn canonicalpaths:
- data/curated/curated_flat_golden_jobs.parquet
- data/preprocessing/05_encoding/features.parquet
- data/preprocessing/05_encoding/skill_cooccurrence.parquet
- data/preprocessing/05_encoding/encoding_dictionary.json

TF-IDF,unmatched,quality,validation,manifest cùng05_encoding. Agent_05§10/agent_07§5 cho phép đường dẫnGolden này dù preprocessing/CLAUDE cũ cấm legacydata/curated; ngoại lệ đã ghi, không đổi path ngầm.

Một bản lịch sử5177cóchecksum ở `data/preprocessing/05_encoding_history/p5_2026-11-09_frozen_v2/`, gồm bundle,contract/report và executedsource trước sửa; history_manifest map original→archivedpaths. Giữ snapshot, decision files và semantic evidence nguyên bytes. Theo yêu cầu _01, trial/debug/duplicate đã được thay thế có thể retire; manifest.refactor.retired_paths ghi SHA trước xóa và đích gộp. Validator lịch sử resolve canonical cũ qua historymap; file retire chỉ được bỏ qua khi exact prior hash khớp retirement record. Thay đổi liên kết README tích hợp được ghi riêng trong updated_paths với cả before/after SHA; không sửa dữ liệu proposal/decision để vượt kiểm tra.

Tempstage→validate toàn bộ→kiểm historicalchecksum→gỡ old successmanifest trước đổi file→destination-local temp+rename→validate canonical mới→manifest cuối. Không công bố bundle trộn cohort; failure không có successmanifest mới. File đúng giữ nguyên, file sai chỉ thay khi backup/historical checksum đã khớp. Dry-run không ghi datasets hoặc successreport/manifest, không đè report cũ.

Manifest ghi ledger/decision/cohort/input/vocabulary/config/stopword/orderedIDs hashes,HEAD+dirty và executedsource,environment,artifactbytes/schema/logicalshape/checksum. producercommit=null khi lineage chưa xác minh. Current validation/acceptance tách biệt, không dùng stale aggregates/TF-IDF5177.

## 7. Một implementation, entrypoints an toàn

`python -m preprocessing.encoding.execute` là full implementation. run_encoding.py delegate về implementation này khi có explicitconfig; --apply/--source legacy bị chặn. run.py:run chỉ delegate khi đủ manifest,vocabulary,stopwords,ledger,decision,output,evidence,history; thiếu thì fail trước IO. Driver5bước chưa cấp config sẽ fail ởP5 với lệnh hướng dẫn, không ghi prototype; không refactor shared driver/P4/exporter.

## 8. Handoff và acceptance

FP-Growth dùng Xbool với denominator5.104 hoặc cohort con được khai báo. Clustering ghép sparseTF-IDF/X theoID,không tự đổi thuật toán/weights ởP5. RF/SHAP không lấy quality/audit hoặc salarytarget/derivedsalary làm predictor; job_family không phải goldlabel.

Notebook/HTML hiện hành `notebooks/eda_p5_final_cohort.ipynb/.html`, chạy kernelmới đủcells,provenance và datahash rõ. EDA5177 cũ đã retire theo _01; giữ parent metrics thực sự được notebook cuối đọc để so sánh. Không phân tíchK/ML hoặc suy ra toàn thị trường.

Data validation,68P5tests,Ruff và EDA đã pass. Python3.12 **UNVERIFIED** do không có môi trường riêng khả dụng trong các paths kiểm; không tự nâng PASS. Fullrepo vẫn6collectionerrors sẵn có ngoàiP5. Phần artifact/cohort/EDA đã bàn giao,nhưng không tự đánh acceptance/P5complete khi chưa xử lý xác minh3.12/ngoại lệ nghiệm thu phù hợp. Scope chưa toàn diện và upstream lineage/jobfamily vẫn là giới hạn công khai, không được gọi là đã sửa upstreamfilter.
