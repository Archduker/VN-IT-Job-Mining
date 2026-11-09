Tiếp tục P5 từ:
- 06_p5_execution_contract.md
- 07_p5_execution_report.md
- 08_p5_scope_review.md
- scope_decisions_proposed.csv và scope_review_queue.csv.

MỤC TIÊU
Chốt cohort theo quyết định Phát đã duyệt, chạy lại đầy đủ P5,
cập nhật EDA và hoàn thiện gói bàn giao. Không mở rộng review vô hạn.

1. QUYẾT ĐỊNH PHÁT ĐÃ DUYỆT

- Duyệt27ID exclude_proposed và8ID retain_proposed trong bản scope review
  đã gửi. Xác minh đúng phiên bản/file/hash trước khi áp dụng;
  không áp tự động lên một danh sách đã thay đổi.
- Loại khỏi cohort IT đợt này:
  + Thiết kế quảng cáo, bao bì, in ấn thuần túy.
  + PLC/HMI thuần điều khiển công nghiệp.
  + Khảo sát/lắp đặt, thi công trạm viễn thông.
- Giữ khi nhiệm vụ rõ:
  software, UI/UX sản phẩm số, firmware/embedded software,
  lập trình plugin/game.
- Ca thiếu bằng chứng: unresolved/quarantine, không đưa vào cohort
  Mining chính; không ghi thành confirmed non-IT.
- Review nốt31ca P1_family_conflict_candidate chưa review.
-410ca P2 chưa review: giữ trong cohort với trạng thái
  retained_unreviewed, không gọi là verified IT hoặc dataset sạch.
- Giữ nguyên snapshot P4 và frozen vocabulary230/order.
- Chưa sửa job_family; các nghi vấn nhãn giữ trong sidecar.
- Giữ các policy encoding/TF-IDF/Golden đã duyệt ở execution contract.

2. PHẠM VI VÀ BẢO TOÀN

Đọc AGENTS.md, contract và source hiện tại.
Kiểm git status/diff, bảo toàn thay đổi người dùng.

Được sửa P5, tests, EDA và tài liệu liên quan để hoàn thành nhiệm vụ.
Không sửa P3/P4, shared dictionary, Mining hoặc bộ lọc upstream.
Không dùng LLM/model để tự động phân loại dataset; không dịch JD.
Không gọi/upload cloud, apply/drop stash, commit/push.
Chưa refactor/dọn thư mục lớn trong lượt này.

Bảo toàn:
- Snapshot5177 và manifest.
- Bộ artifacts5177 hiện có cùng contract/evidence.
- Frozen vocabulary và các quyết định review trước.

Trước thay canonical artifacts, lưu một bản lịch sử có checksum.
Không tạo nhiều bộ dữ liệu trùng không cần thiết.

3. HOÀN TẤT SCOPE REVIEW CÓ GIỚI HẠN

- Áp quyết định đã duyệt cho27loại/8giữ.
- Giải quyết19unresolved theo policy ở mục1.
- Review đủ31ca ưu tiên còn lại bằng toàn bộ nội dung sẵn có.
- Không mở rộng sang410ca P2 trong lượt này.

Từ khóa chỉ tạo queue, không tự là quyết định loại.
Dựa nhiệm vụ thực tế; không dùng job_family, ngành công ty,
tên công cụ hoặc một từ software/Python làm ground truth.

Với31ca mới, Phát cho phép áp policy đã duyệt:
- Nhiệm vụ rõ phù hợp→include.
- Nhiệm vụ rõ thuộc nhóm ngoài scope đã định→exclude.
- Thiếu/mâu thuẫn bằng chứng→quarantine.
Nếu gặp một loại ranh giới mới chưa có policy, quarantine,
không tự mở rộng phạm vi.

Giữ ID, nhiệm vụ chính, field/quote ngắn, reason và policy reference.
Phân biệt assessment của Agent với nhãn gold do người gán.
Không sửa job_family; ghi đề xuất riêng nếu có.

4. TẠO COHORT LEDGER

Lưu ledger mới có version/hash trong repository.
Mỗi ID snapshot có:
job_id_global | disposition | review_status | reason |
evidence_reference | decision_reference.

disposition:
- include
- exclude
- quarantine

review_status phân biệt:
- retained_reviewed
- retained_unreviewed
- excluded_by_approved_policy
- unresolved_quarantined

Job ngoài targeted queue vẫn giữ, ghi not_flagged_by_targeted_rules;
không gọi là đã review toàn bộ.

Kiểm:
- Mỗi ID xuất hiện đúng một lần.
- Ba tập include/exclude/quarantine rời nhau.
- N_P4=5177=N_include+N_exclude+N_quarantine.
- Không mất ID hoặc tự thêm ID.
- Báo phân bổ theo source.

Giữ records loại/quarantine trong snapshot gốc hoặc sidecar auditable;
không xóa P4.

5. CHẠY LẠI P5 TRÊN COHORT INCLUDE

Input logic là snapshot gốc + ledger đã duyệt.
Lọc cohort trước mọi phép fit/aggregate phụ thuộc dữ liệu.

- Giữ230canonical/column/order; không chọn lại topK.
- Nếu skill thành zero-column: giữ cột và báo rõ,
  không thay skill dự phòng để làm đẹp.
- Counts trong frozen vocabulary ban đầu là reference counts;
  lưu riêng observed counts của cohort mới, không sửa lịch sử.
- Freeze lại top10location theo cohort cho run mới và ghi dictionary;
  mapping skill không thay.
- Refit TF-IDF trên cohort mới bằng cấu hình/stopwords đã duyệt,
  giữ sparse, không tự fallback nếu V<2000 hoặc lỗi.
- Tính lại features,C,Golden,TF-IDF/rows/terms/IDF,
  unmatched,quality,dictionary,validation và manifest.
- Không tái dùng aggregate/TF-IDF của5177jobs như kết quả cohort mới.

Bốn canonical paths:
data/curated/curated_flat_golden_jobs.parquet
data/preprocessing/05_encoding/features.parquet
data/preprocessing/05_encoding/skill_cooccurrence.parquet
data/preprocessing/05_encoding/encoding_dictionary.json

Các artifacts phụ thuộc ở cùng output P5 theo contract.
Stage và validate trước khi thay canonical bundle.
Chỉ thay sau khi bộ mới nhất quán; bộ cũ đã được bảo toàn.
Không trộn artifacts của hai cohort.

6. THỐNG NHẤT ENTRYPOINT AN TOÀN

Kiểm execute.py,run_encoding.py và driver năm bước:
- Chỉ có một implementation full-bundle được dùng để bàn giao.
- Entry point cũ không được âm thầm ghi prototype lên canonical bundle.
- Trong phạm vi P5:delegate về runner chung khi đủ explicit config,
  hoặc fail trước mọi ghi với hướng dẫn lệnh hiện hành.
- Không refactor driver/P4 chung ngoài scope.
- Thêm regression tests cho lệnh legacy có nguy cơ overwrite.

Frozen vocabulary,stopwords và decision ledger là runtime assets:
giữ đường dẫn ổn định, dùng repo-relative references.
Lưu decision record trong repository, không phụ thuộc file Downloads.
Không di chuyển hàng loạt báo cáo/code ở lượt này.

7. KIỂM CHỨNG

Tests/data checks:
- Ledger partition đầy đủ, không overlap, không loại nhầm retained IDs.
- Rows/IDs/order của features,Golden,TF-IDF rows bằng cohort include.
- Không có excluded/quarantined ID trong bộ Mining chính.
-230binary columns; từng bit khớp lookup; zero columns được báo.
-C:int64,230×230,labels/order/symmetry/diagonal/bounds,
 independent job-ID intersection counts.
- Missing/unknown/anomalies theo contract.
- Golden giữ toàn bộ P4 attrs của included IDs,
  nested/null/schema/values sau roundtrip.
- TF-IDF row alignment,finite/nonnegative,norms,
 vocabulary/config/IDF reconstruct roundtrip.
- Quality/audit columns được tách khỏi recommended predictors.
- Manifest/cohort/vocabulary/config/source hashes khớp.

Chạy tests/lint liên quan.
Kiểm Python3.12 trong môi trường riêng nếu khả dụng;
không thay Python hệ thống/venv chính hàng loạt.
Nếu chưa kiểm chứng được, báo UNVERIFIED, không tự nâng thành PASS.
Phân biệt lỗi toàn repo có sẵn với regression do lượt này.

8. CẬP NHẬT EDA CUỐI

Giữ EDA cũ như historical evidence; không ghi nhầm là cohort cuối.
Tạo/cập nhật notebook bàn giao có provenance rõ,
chạy toàn bộ bằng kernel mới và xuất HTML đồng bộ.

Chỉ tập trung:
-5177input→include/exclude/quarantine, theo source/review status.
- Frequency/skill-per-job/missing/all-zero trên cohort mới.
- Coverage với mẫu số và biểu diễn rõ.
- Hard/soft/group metadata và19group chưa khớp nếu còn.
- Co-occurrence và TF-IDF summary.
- So sánh trước/sau các metric chính.
- Zero-column skills,remaining anomalies và giới hạn scope review.

Không suy rộng thành toàn thị trường Việt Nam.
Không gọi410P2 hoặc jobs ngoài queue là đã được xác nhận IT.
Không cần phân tích thêmK hoặc chạy ML.

9. BÀN GIAO VÀ ĐIỀU KIỆN HOÀN THÀNH

Cập nhật execution contract/report thành trạng thái hiện hành,
đưa bản5177 xuống lịch sử, không xóa evidence.
Lưu:
- Cohort ledger và scope review bổ sung.
- Validation/test/lint/performance logs.
- Artifact manifest và trước/sau metrics.
- Notebook/HTML đã chạy.
- Hướng dẫn ngắn cho downstream đọc đúng bộ output.

Báo cáo cuối phải nêu:
- Ninput/include/exclude/quarantine và review coverage.
- Danh sách file reuse/created/replaced cùng canonical paths.
- Vocabulary/order giữ nguyên,zero columns nếu có.
- Kết quả validation,TF-IDF width,performance và môi trường.
- Lineage upstream chưa xác minh,scope review chưa toàn diện,
  Python3.12/whole-repo tests còn giới hạn nào.
- Những việc còn chặn nghiệm thu, nếu có.

Không coi việc loại một số job là đã sửa bộ lọc upstream.
Không tự đánh verified IT cho toàn cohort.
Chỉ ghi acceptance/P5 complete theo các điều kiện thực sự đã đạt;
nếu còn blocker, ghi cụ thể, không dừng ở “đã tạo file”.

Thực hiện đến chạy lại artifacts và EDA trong phạm vi đã duyệt,
không dừng ở kế hoạch hoặc xin lại các quyết định đã chốt.
