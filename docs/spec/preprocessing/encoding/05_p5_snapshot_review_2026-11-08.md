# P4 snapshot và rà soát P5 — 08/11/2026

> **Ghi chú 10/11/2026:** JEV, OpenJev và Qwen đã bỏ; cột xác suất `*_prob` không còn. Cờ thay thế: `it_rule_level`, `seniority_can_kiem`, `job_family_can_kiem` (xem `docs/spec/preprocessing/spec/P5_encoding.md`).

## Bằng chứng dữ liệu thật

Đã LIST/HEAD 24 object P2/P3/P4 trên R2 và GET tám object P4 bằng điều kiện IfMatch ETag. Không ghi cloud. Dữ liệu tải về nằm riêng tại `reports/preprocessing/05_encoding/snapshot_audit_2026-11-08/`, không ghi đè input chuẩn hoặc output P5.

`manifest.json` lưu key, ETag, SHA-256 bytes đã tải, size, schema Arrow và metadata từng nguồn. ETag chỉ dùng chống thay đổi trong lúc tải; không coi là SHA-256. Metadata tám P4 cùng generated-at `2026-11-03T17:13:07+00:00`, số dòng metadata bằng nội dung Parquet, từng partition chỉ chứa đúng nguồn tương ứng. Điều này xác minh snapshot P4 lưu trên R2 và tính nhất quán nội bộ, chưa phải kiểm toán lại từng record với Bronze.

Gộp trong RAM: **5177 dòng × 62 cột**, ID non-null/unique. Phân bổ: TopCV 1561; ITviec 905; VietnamWorks 900; JobsGO 683; CareerViet 448; Glints 271; TopDev 227; Vieclam24h 182.

Profiling thật tại `profiling.json` gồm null counts, tần suất skill theo số job (dedup trong mỗi job), distribution nguồn và thống kê prototype:

- 4760 giá trị skill phân biệt; 412 jobs không có skill.
- Skill frequency ≥5: 586; ≥10: 301; ≥20: **152**; ≥50: 68; ≥100: 45.
- Encoding prototype chạy trong RAM: 291 cột tổng, đúng 230 cột skill binary; giữ 5177 dòng.
- Prototype có **81 cột skill toàn 0**, sparsity **98.32075%**.
- Co-occurrence prototype 230×230 vượt kiểm tra symmetry/diagonal trong hàm hiện có.

Các kết quả prototype là kiểm tra thực nghiệm, chưa phê duyệt vocabulary và chưa nghiệm thu artifact file P5. Phân tích bổ sung offline tại `eda_relationships.json` có cross-tab/conditional rates của top 20 skills theo nghề, cấp bậc và nguồn; phân nhóm theo prototype được đánh dấu chưa phê duyệt. Chưa xác nhận từng tag tự do là skill hợp lệ; chưa xuất biểu đồ.

Độ phủ skill: 92.0417%; trung bình 6.4006, median 5 skill/job, min 0, max 43. Top 230 giá trị thô giữ 74.4025% lượt skill; skill ở hạng 230 có 13 jobs. Có 1 record đảo dải kinh nghiệm và 8 record deadline trước posted_date; cần Duy đánh giá, chưa tự loại/sửa. Phân tích nhóm prototype còn 12995 lượt skill chưa ánh xạ. Tie-break xếp hạng: tần suất giảm dần rồi tên skill tăng dần.

## Vocabulary trình duyệt

Danh sách xếp hạng ứng viên đầy đủ nằm ở `profiling.json:candidate_frequency`. Không coi top 230 giá trị tự do là 230 skill chuẩn. Kết quả 152 skill đạt ≥20 chứng minh không thể đồng thời chọn đúng 230 giá trị quan sát và áp dụng cứng ngưỡng ≥20 trên snapshot này.

Đề xuất để chủ nhiệm duyệt: giữ yêu cầu width=230, dùng tần suất làm bằng chứng sàng lọc; Phát phối hợp Duy chuẩn hóa các tag ngoài từ điển và duyệt vocabulary/version trước khi xét giữ skill dưới ngưỡng hoặc zero-frequency. Chưa triển khai lựa chọn này và chưa bổ sung taxonomy.

## Rà soát code và tests

`pytest tests/unit/test_encoding_step.py -q`: **10 passed**, 0.86s. Đây là unit tests fixture. Môi trường thực tế Python **3.14.4**, khác yêu cầu Python 3.12; chưa xác nhận compatibility 3.12. Ruff chưa cài (`No module named ruff`).

Các điểm cần xử lý trước nghiệm thu:

1. `run.py`: input không tồn tại vẫn ghi report conserved 0→0; CLI trả thành công. Cần phân biệt thiếu input với chạy thành công.
2. Source-filtered run dùng tổng số dòng input làm số output report trước khi lọc; có thể báo conservation sai và ghi đè output chung bằng tập con.
3. TF-IDF dùng `min_df=2` thay vì 5 trong SPEC-06, tự giảm xuống 1 cho corpus nhỏ; gọi trong P5 kể cả dry-run. Ownership/3000 vs100 chưa được giải quyết.
4. TF-IDF densify bằng `toarray()`; chưa kiểm tra chi phí RAM hoặc lưu sparse, chưa kiểm thử file roundtrip/job alignment trên dữ liệu thật.
5. Artifact TF-IDF cũ không được dọn hoặc đánh dấu stale khi lần chạy sau skip/error.
6. Co-occurrence kiểm width nhưng chưa kiểm tên/thứ tự bằng vocabulary chuẩn; đầu vào không được kiểm binary rõ ràng trước phép nhân.
7. Unit tests chưa bao phủ missing input, source subset, malformed arrays, column ordering/alias collisions và các tình huống TF-IDF skip/stale.
8. `skills_std` cho phép tag ngoài dictionary; các alias đã gộp upstream không thể tách lại chỉ bằng P5. Sáu nhóm/quota và tần suất còn cần duyệt.
9. Golden ownership, schema/tên ma trận và input Random Forest vẫn cần thống nhất với Duy/Phúc/Thuận. Không tự sửa module của họ.

## Trạng thái bàn giao

**P5 chưa hoàn thành.** Có input P4 thật để tiếp tục EDA và candidate review; chưa xuất bản artifact P5. Bước tiếp theo: hoàn tất EDA, duyệt vocabulary 230 và threshold policy, chốt interface TF-IDF/Golden/Mining, sau đó kiểm tra file artifact roundtrip, chất lượng và hiệu năng trên snapshot có checksum. Giữ nguyên các thay đổi source có sẵn; lần này chỉ thêm script audit và báo cáo.
