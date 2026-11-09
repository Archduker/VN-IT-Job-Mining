# Trình Phát quyết định: Input P4 và K — 08/11/2026

**Trạng thái:** phân tích/candidate, chưa approved. Source HEAD `f438090`; không sửa producer, shared dictionary, encoder width hoặc dữ liệu chuẩn. Bằng chứng kèm theo ở [thư mục CSV/JSON](../../../reports/preprocessing/05_encoding/p4_k_decision_evidence_v1/summary.json).

## Quyết định 1 — Input P4

**Input đã xác minh:** tám partition P4 có SHA256 khớp manifest, 5177 jobs/IDs duy nhất/tám nguồn. Chọn snapshot này làm mốc vì có đủ bytes + schema + ID để tái lập, không vì đã được Phát phê duyệt hay đại diện toàn thị trường. Report P2/P3/P4 cùng khai 5177 rows, code_version7dee2a4; metadata P4 cùng generated-at2026-11-03T17:13:07Z. Tuy nhiên **không có Parquet P2/P3 local để so tập IDs**, manifest không bind commit nguồn: commit tạo bytes P4 **chưa xác minh**. Không liên hệ dataset9824 lịch sử với snapshot này, không suy nguyên nhân giảm dòng từ tổng số.

| Phương án | Khả thi/giới hạn | Đề xuất |
|---|---|---|
| Giữ snapshot và driver năm bước | Khớp P5 hiện tại: skills_std, seniority6bậc, locations structured, log VND/outlier/date/clean text | Dùng làm baseline/evidence lịch sử; không chứng nhận đã dùng logic mới |
| Tích hợp chọn lọc extractor mới vào contract năm bước | Giữ các field P5; cần giữ unknown candidates và version mapping | **Khuyến nghị để bàn giao lâu dài**, sau khi Phát duyệt policy unknown và taxonomy |
| Dùng consolidated mới | Chỉ skills_extracted92, seniority5bậc, city scalar, salary triệuVND; thiếu nhiều field P5 | Cần hoàn thiện producer hoặc phê duyệt contract mới; không chỉ rename |
| Adapter không mất nghĩa | Có thể đổi alias tên/đơn vị khi đầy đủ metadata | Không khôi phục Intern/Fresher, multi-location hoặc skill đã gộp từ scalar |

**Bằng chứng mới:** vì thiếu P2/P3, không chạy rebuild upstream. Đã gọi pure extractors trên raw/clean fields còn giữ trong P4; đây là **supplemental**, không phải output P4 chính thức. Replay cũ khớp baseline ở5177/5177jobs. Trên cùng IDs, mới có91 canonical/4533jobs có skill; baseline4760giá trị tự do/4765jobs có skill. Có457jobs mất toàn bộ skill và225jobs trước rỗng nay có skill. Khác tên không đồng nghĩa mất/thêm năng lực thực; chưa có precision/recall labels.

Taxonomy mới chứa92canonical; hàm chỉ append canonical trong danh sách nên **vocabulary quan sát ≤92** nếu dùng riêng extractor này. Không thể làm nguồn duy nhất cho230skill quan sát. TensorFlow/PyTorch mới có97/108jobs, baseline exact-name0/0; REST API1370→570; Automation Test201→0, Automation Testing35→0; HTML/CSS299→291; Agile/Scrum951 chuyển sang Agile / Scrum800. Khác biệt gồm context matching và alias grouping; không tự phục hồi từ kết quả gộp. Collision c/c++ được lookup báo ambiguous nhưng extractor có thể phát cả C,C++.

**Schema đề xuất bàn giao:** giữ ID/source; skills_std là canonical **đã duyệt**, thêm skills_candidates/unmatched metadata tách riêng và evidence/normalization_version; structured locations; seniority6nhãn+unknown; exp bounds; salary VND/capped/log và outlier flags; dates/headcount/clean text. Không điền0 để che missing. Chi tiết producer/type/nullability tại [field contract CSV](../../../reports/preprocessing/05_encoding/p4_k_decision_evidence_v1/p4_p5_field_contract.csv).

**Patch producer cần Phát duyệt, chưa áp dụng:** `skill_normalizer.py` bổ sung output evidence/unmatched metadata ngoài known canonicals; `normalization/run.py:process_source_records` tích hợp extractor mới nhưng không discard candidate tags; `transformation/run.py` giữ cleaner/date/headcount; không bỏ salary/log/location tương thích cũ. Trích theo field để tránh ghép ngữ cảnh sai. Muốn đủ230canonical phải review/chuẩn hóa ứng viên quan sát và mở rộng catalog theo quyết định, không thêm skill không xuất hiện. Sau đó tạo P3/P4candidate từ **P2 cùng snapshot/IDs đã xác minh**, paths mới, chạy lại frequency/EDA/K/group/source coverage/shortlist/mapping và input/roundtrip tests. Chưa có P2 nên rebuild thật còn thiếu dữ liệu, không phải chờ người khác phê duyệt thay Phát.

## Quyết định 2 — K

**Nguồn yêu cầu:** trong lịch sử HEAD truy được, xuất hiện từ commit `80eadc1` (author06/11, replay08/11; bản trước rebase83f8432): task05 yêu cầu230, SPEC/ADR cũng nói230/97.2%sparsity nhưng chưa tìm được run/dictionary/manifest chứng minh vì sao chọn230. Cùng bản SPEC-06§5.1 vẫn ghi topK100–200/frequency≥20. Contract approval07/11 chỉ chốt **width230**, không chốt danh sách hoặc bỏ threshold. Không suy ý định tác giả.

Ba đối tượng khác nhau: prototype230 đã chạy có81cột0; raw top230 không cột0 và có coverage; canonical230cuối **chưa có**. Shortlist129 là đề xuất theo bộ lọc cũ, không phải129đã approved; hiện0accept/0reject/4760chưa review. `unreviewed_high_frequency.csv` liệt kê top300chưa duyệt theo frequency, không ưu tiên tên prototype: SQL1762, REST API1370, Machine Learning1016 đều chưa có quyết định semantics.

**Tái tính baseline**, mẫu số5177jobs/33136cặp job–giá trị, dedup từng job; tie frequency giảm/name tăng:

| K | Job coverage | Pair coverage | Frequency biên |
|---:|---:|---:|---:|
|100|83.813%|66.619%|35|
|150|85.764%|70.470%|20|
|200|87.406%|73.108%|15|
|230|87.889%|74.402%|13|
|250|88.236%|75.157%|12|
|300|89.028%|76.759%|10|

200→230 tăng **0.483điểm% job /1.295điểm% pair**; 230→250:0.348/0.754; 230→300:1.140/2.357. CSV kèm ties, group counts và source denominators. Group mapping mới chỉ proposed/UNCLASSIFIED. Scenario case-spelling-only có cùng số liệu, **không phải canonicalization đầy đủ**. Không so pair coverage giữa raw33136pairs và new92có27325pairs như cùng đại lượng. Số152đạt≥20 là trên baseline, không kết luận bất khả thi sau mapping khác chưa thực hiện.

**Chưa đủ căn cứ chọn K tối ưu.** Giữ230 trung thực vì contract/task hiện hành; EDA chỉ định lượng trade-off, không phê duyệt canonical list hoặc chất lượng Mining. Phát cần đặt trước các tiêu chí `job_coverage_min`, `pair_coverage_min`, `support_min`, lợi ích tối thiểu cho30cột và yêu cầu nhóm/kỹ năng chuyên biệt; chưa tự chọn ngưỡng theo kết quả để hợp thức hóa230. K khác chỉ là phương án đổi contract sau khi review semantics/downstream, không đề xuất thay width lượt này.

**Phân quyền kết luận:** Agent có thể kiểm checksum/ID, dedup, tính coverage và chạy harness paths riêng. **Phát duyệt** input chính thức, policy unknown/catalog, labels/units, tiêu chíK và vocabulary/version. **Chưa biết** lineage P2/P3→P4, precision canonical/unclassified và ảnh hưởng Mining; cần dữ liệu/đánh giá cụ thể. Không ưu tiên tên prototype chỉ vì có sẵn dictionary.

**Tái lập:** từ repo chạy `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m preprocessing.encoding.analyze_p4_input_and_k`; script tạo thư mục candidate `reports/preprocessing/05_encoding/p4_k_decision_evidence_v1/` và fail nếu đã tồn tại, tránh overwrite. Khi chạy lại hãy đổi tên thư mục candidate trong bản copy script. CSV same-ID giữ original metadata, baseline, legacy replay, new extraction và unmatched; ví dụ chỉ có ID/ngữ cảnh ngắn. Hai CSV quyết định/generator và snapshot không sửa. Không R2/ML/production/stash/git mutations.
