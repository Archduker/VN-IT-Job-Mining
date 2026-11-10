# P5 scope review — 09/11/2026, chờ Phát duyệt

> **Ghi chú 10/11/2026:** JEV, OpenJev và Qwen đã bỏ; cột xác suất `*_prob` không còn. Cờ thay thế: `it_rule_level`, `seniority_can_kiem`, `job_family_can_kiem` (xem `docs/spec/preprocessing/spec/P5_encoding.md`).

Đã review **54 job**: đủ **36 job AutoCAD** và18ca ưu tiên ngoài nhóm này. Đề xuất **27 loại /8 giữ /19 chưa rõ**; riêng AutoCAD là **18 loại /3 giữ /15 chưa rõ**. Mọi `decision` trống, chưa có quyết định được duyệt. **Không loại toàn bộ36job, không bỏ cột AutoCAD, không sửa P4/job_family/vocabulary/artifact chuẩn. P5 vẫn pending acceptance.**

Evidence run: `reports/preprocessing/05_encoding/scope_review_2026-11-09_v1/`.

- [scope_decisions_proposed.csv](../../../reports/preprocessing/05_encoding/scope_review_2026-11-09_v1/scope_decisions_proposed.csv):54đề xuất theo ID, nhiệm vụ chính, quote/field, lý do, certainty, scope_status/family_status riêng và ôdecisiontrống.
- [scope_review_queue.csv](../../../reports/preprocessing/05_encoding/scope_review_2026-11-09_v1/scope_review_queue.csv): **495 ứng viên** dedup ID, rule/evidence/ITcounter-signals/review_state. Còn **441 chưa review**, gồm31ca ưu tiên nghi lệchfamily và410ca khác. Không tuyên bố toàn snapshot sạch.
- [boundary_cases.csv](../../../reports/preprocessing/05_encoding/scope_review_2026-11-09_v1/boundary_cases.csv): từng ID ranh giới, lựa chọn include/exclude, hệ quả và khuyến nghị chưa áp dụng.
- `family_decisions_proposed.csv`: đánh giá family riêng cho54job; chỉ3đề xuất nhãn thay thế, chưa sửa dữ liệu.
- [impact_preview.json](../../../reports/preprocessing/05_encoding/scope_review_2026-11-09_v1/impact_preview.json): scenario **chưa duyệt**, chỉ loại27ID exclude_proposed trong RAM.
- `scope_rule_hits.csv`, `rules.json`, `reviewed_full_texts.md`, `full_text_review_log.json`, `annotations_proposed.json`, `summary.json`, `provenance.json`, `validation.json`, logs/tests: bằng chứng đầy đủ và cách tái lập.

## Cách rà soát và giới hạn evidence

Đọc đầy đủ title, description/requirements hiện có trong snapshot, skills và metadata của từng job được review; không chỉ đọc quanh AutoCAD. Với36seed, raw và clean description/requirements tương đương nội dung sau chuẩn hóa whitespace; hashes cả4field lưu trong log. Một số VietnamWorks đã có dấu rút gọn trong chính raw snapshot, ví dụ Structural BIM Modeler `vietnamworks_2109724`; không thể khôi phục đoạn thiếu và không bịa thêm nhiệm vụ. Packet giữ nguyên toàn bộ nội dung có sẵn.

Luật tất định tìm civil/construction, cơ khí/HVAC, CAD/BIM/không gian, CNC, PLC, telecom site và graphic marketing. job_family chỉ dùng tạo ưu tiên review mâu thuẫn; không là ground truth. Công ty/ngành không là tiêu chí loại. ITcounter-signals chỉ giúp đối chiếu, không tự chứng nhận bằng một từ Python/software/AI. Mỗi hit giữ rule_id,field,match,offset và excerpt; validation kiểm lại source substring.

Đây là **đánh giá đề xuất của Agent**, không phải nhãn tay Phát đã duyệt hoặc precision/recall được đo. Script không gọi LLM/model, không dịch JD, không tự sinh quyết định từ regex. Các đề xuất theo ID nằm trong file annotations tường minh. Queue có false positives có chủ đích: C# Developer ở Khu CNC Hòa Lạc vẫn được đề xuất giữ sau đọc nhiệm vụ backend/API; CNC ở địa danh không phải gia công.

## 27 ID đề xuất loại, có bằng chứng nhiệm vụ ngoài phạm vi

Quote/field và lý do từng ID ở CSV; đây **chưa phải danh sách loại đã được Phát duyệt**.

| ID | Hoạt động thực tế được quan sát |
|---|---|
| topcv_2301984 | Đường chạy dao,phay/tiện CNC,dao cụ/đồ gá |
| topcv_2329663 | 3Dbooth/sân khấu,vật liệu và giám sát thi công sự kiện |
| topcv_2118497 | Bản vẽ lắp ráp/chế tạo cơ khí,file cắt CNC |
| topcv_1839052 | Vận hành CNC,cắt gọt nội thất,bảo dưỡng máy |
| topcv_2238406 | Hồ sơ thầu/hợp đồng,văn thư,hậu cần; Back-End không phải backend software |
| topdev_2137540 | Thiết kế/lắp khuôn mẫu và sản phẩm nhựa |
| topdev_2138775 | Shopdrawing,tủ điện/hệ thống lạnh/MEP |
| topdev_2139278 | Tank,bồn,ống Duct,bản vẽ cơ khí/BOM |
| topdev_2139387 | CADnội thất,đo công trường,nhà thầu xây dựng |
| topdev_2139432 | Điều phối hồ sơ kiến trúc/kết cấu/MEP/pháp lý công trình |
| topdev_2139461 | Công viên/sân vườn,cây trồng,thi công cảnh quan |
| vietnamworks_2096707 | Tiến độ thi công công trường metro |
| vietnamworks_2097667 | QAQCthi công cầu đường/đường sắt |
| vietnamworks_2111632 | Chất lượng vật liệu,cấu kiện,hạng mục thi công |
| vietnamworks_2111637 | QAQChạ tầng,hồ sơ chất lượng công trình |
| vietnamworks_2118647 | Shopdrawing/kiến trúc công trường,không softwarearchitect |
| vietnamworks_2118846 | Kiểm vật liệu/công trình và nghiệm thu |
| vietnamworks_2119724 | QCgia công nhà xưởng,khối lượng quyết toán |
| vietnamworks_2120222 | QMS/ITP,vật liệu/ nghiệm thu sân bay |
| vietnamworks_2120824 | QS/QCkhối lượng xây dựng và thanh toán |
| vietnamworks_2106020 | QAQCthi công,vật tư,thí nghiệm/hoàn công |
| vietnamworks_2111654 | QAQCxây dựng công nghiệp/nhà máy |
| vietnamworks_2120681 | Hồ sơ vật tư,nhật ký công trường,bản vẽ hoàn công |
| glints_9509fef0-e8a3-497f-9444-9c800dfc87e9 | Thẩm định GMP,nguyên liệu,điều kiện sản xuất thuốc |
| glints_d8e0e752-7e09-4f9d-b6a8-c8c3e9fed581 | Shopdrawing,hoàn công,hồ sơ nghiệm thu/công trường |
| jobsgo_29090237384 | QAQCvật liệu,thi công/lắp nội thất công trình |
| jobsgo_29238642275 | QAQCđường giao thông,nền móng,cầu cống |

Không dùng Adobe/AutoCAD/GMP/companysector tự nó làm lý do: các đề xuất trên dựa nhiệm vụ thực tế. Ví dụ glintsQA dược bị đề xuất loại vì kiểm nguyên liệu/sản xuất thuốc; glintsQA công trường có metadata Automation Testing/SRE nhưng duties hoàn công không phải software QA. Không sửa những tag đó ở lượt này.

## Các ca giữ và family cần duyệt riêng

3AutoCADđề xuất giữ: `topcv_2321477`, `topcv_2321737`, `topcv_2024907`, vì có nhiệm vụ thiết kế **giao diện website/landing page** cụ thể; ghi rõ mixed marketing, không lấy ngành công ty để loại.

5ca giữ khác: `topcv_2326869` có SIT/UAT,SSO/RBAC/API vàbugs phần mềm; `careerviet_35C84857` phát triển C#backend/API; `topcv_2178117` phát triển firmware/FreeRTOS; `topdev_2136553` phát triển WMS/WCS/backend; `jobsgo_29014330774` phát triển Command/Plugin BIM/CAD C#/C++ và sửa mã nguồn. BIM/CAD/cơ khí/PLC trong JD không tự đủ để loại những job phát triển software này.

| ID | Scope đề xuất | Family hiện tại → đề xuất riêng |
|---|---|---|
| topcv_2178117 | retain_proposed | Backend→Khác: enum hiện thiếu Embedded; cần Phát chốt nhãn, không tự tạo family mới |
| topdev_2136553 | retain_proposed | Kiểm thử(QA/QC)→Backend: phát triển kiến trúc/backend là nhiệm vụ chính, QA là phối hợp |
| jobsgo_29014330774 | retain_proposed | Backend→Khác: plugin/desktop CAD, chưa chứng minh backend service |

`Khác` ở đây là đề xuất trong taxonomy hiện hữu, không phải ground truth hoặc quyết định xóa job đúng phạm vi. Các ca ngoài phạm vi có family sai được đánh dấu riêng, không ép đặt familyITmới cho chúng.

## Quyết định ranh giới thực sự cần Phát

| Nhóm/hoạt động quan sát | Lựa chọn và hệ quả | Khuyến nghị chưa áp policy |
|---|---|---|
| Graphic/advertising vs product UI;16ca đã review | Bao gồm marketing/print rộng sẽ giữ thêm designer và ảnh hưởng Adobe/softskill demand; loại marketing-only vẫn phải giữ ca trực tiếp làm UI | Chốt12ca graphic-only còn unresolved;3mixedUI đề xuất giữ; eventspatial3D1ca đề xuất loại |
| PLC/IT-OT;3ca | IncludePLC/HMI mở cohort sang điều khiển dây chuyền; excludePLC-only không được xóa software WMS chỉ vì tích hợp PLC | 2PLC-focused chưa rõ: vietnamworks_2115888,careerviet_35C32FB4; softwarelead đề xuất giữ |
| Telecom site;2ca | Bao gồm RAN/towerinstallation khác với chỉ software/networkoperation; không áp theo ngành công ty | Phát chốt vietnamworks_2116490,careerviet_35C81470; duties là khảo sát/lắp antenna/BBU/RRU/cáp,QCsite |
| Embedded vs machining;6ca | Firmwarecode là hoạt động IT; CAM/CNCtoolpaths/vận hành máy là hoạt động khác | Giữ firmwareleader;5ca gia công/khuôn/cơ khí đề xuất loại theo ID, không loại toàn bộ hardware |
| BIM vs software;2ca | Plugin coding khác dựng structuralmodel; Python tag không đủ để chứng nhận | Giữ jobsgo plugin; vietnamworks_2109724 còn unresolved vì source rút gọn |
| Hardwaretest;1ca | Includeequipmenttest rộng hơn software/firmwaretesting | vietnamworks_2113565 kiểm cycle-driving thiết bị bán dẫn, thiếu thông tin phần mềm; cần Phát chốt |
| Mechanical automation;1ca | Includeengineeringautomation khi coding là nhiệm vụ chính, hoặc excludeCAD/material-only | vietnamworks_2118384 còn unresolved: source rút gọn,Python/VBA chỉ metadata |

Các lựa chọn chi tiết theo từng ID trong boundary_cases.csv; chưa áp lựa chọn nào để tạo cohort.

## Impact preview — chỉ scenario chưa duyệt trong RAM

Chỉ mask27ID exclude_proposed, giữ toàn bộ19unresolved/8retain và các job chưa review; dùng X hiện có đã kiểm với frozen lookup, **không chạy lại encoding/TF-IDF chính thức**, không xuất datasetscenario. Giữ230cột/thứ tự/vocabulary, không refit/chọn dự phòng.

**5177input =5150cohort_proposed +27excluded_proposed**. Đây không phải cohort cuối đã duyệt; canonical artifacts vẫn5177job.

| Source | Trước | Sau scenario |
|---|---:|---:|
| TopCV |1561|1556|
| TopDev |227|221|
| VietnamWorks |900|888|
| JobsGO |683|681|
| Glints |271|269|
| CareerViet |448|448|
| ITviec |905|905|
| Vieclam24h |182|182|

- AutoCAD **36→18job**, không bị loại cột; **không có cột mới thành zero**.
- Jobcoverage **4277/5177=82,6154% →4257/5150=82,6602%**. Tỷ lệ thay đổi cả tử/mẫu số, không là bằng chứng snapshot đã sạch.
- Sparsity **98,1654%→98,1580%**, cùng230cột.
-10skill giảm: AutoCAD36→18;Agile/Scrum953→952;English315→314;AutomationTesting227→226;Communication165→164;AdobePhotoshop72→71;ProblemSolving66→65;TeamManagement58→57;Leadership56→55;ProcessImprovement8→7. Chi tiết ở JSON, không sửa officialfrequency.

## Kiểm chứng, tái lập và bước sau duyệt

Script `preprocessing/encoding/scope_review.py`; explicit per-IDreview log `scope_review_annotations.py`. Input vẫn8partitions/5177 với manifest SHA `dd93db5c08b533725bd086315325c70ed37a8027b7149fc8327e5a6d3ca34ea4`. Provenance ghi snapshot/vocabulary/script/annotations/rules hashes và Python3.14.4/Pandas/NumPy. **84file protected** (P4snapshot,canonical artifacts,pending manifest,v1/v2/evidence/quyết định cũ) nguyên checksum. Validation kiểm quote/match offsets,queueuniqueness,36seedcoverage,blank decisions và tính lại impact.

**30tests liên quan pass** (4scope-review tests mới+26lookup tests), Ruff pass; logs ở `tests_scope.xml/.log`, `lint.log`. Không claim whole-repo tests pass (6importerrors đã ghi ở report07, không sửa ngoài scope). Không có cloud/model/translation/commit/push, không thay jobfamily hoặc vocabulary.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m preprocessing.encoding.scope_review \
  --output reports/preprocessing/05_encoding/scope_review_2026-11-09_v1 --validate
```

Validator chỉ tái kiểm evidence; builder từ chối output đã có. Sau Phát duyệt ID và policy ranh giới: tạo ledger include/exclude/familydecisions có version/hash, giải trình mọi ID. Contractcohortmới phải ghi **Noutput=Ncohort_approved;Ninput_P4=Ncohort_approved+Nexcluded_approved**; không tiếp tục claim bảo toàn5177output ở tập đã lọc. Chạy EDAcohortđãduyệt và tính lại features,C,Golden,TF-IDF/rows/vocabulary/IDF,sidecars,dictionary/provincecounts,manifest; giữ230skillorder và báo zero nếu có. Kiểm keys/values/schema/cohortledger trước bàn giao. **Lượt này dừng trước mọi thao tác loại dòng/ghi đè canonical; Phát duyệt danh sách và policy trước.**
