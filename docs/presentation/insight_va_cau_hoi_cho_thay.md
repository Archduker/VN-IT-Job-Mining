# Insight biểu đồ đầu vào Processing và câu hỏi cho thầy

> Biểu đồ: `docs/presentation/processing_input.html`. Số lấy từ bảng `04_normalization` (4.671 tin), báo cáo từng bước và các lần chạy đã ghi trong `docs/issue_log.md`.
> Ký hiệu: ✓ = đã kiểm trên dữ liệu; ? = giả thuyết, chưa kiểm.

## Đính chính (số trong các lần trả lời trước có chỗ sai)
- Số người tuyển thiếu 100% ở **itviec, careerviet, glints, topdev** (vietnamworks 0%). Ngày đăng thiếu 100% ở topcv, 67% ở topdev. Hạn nộp và loại hình việc làm thiếu 100% ở topdev. Kỹ năng thiếu nhiều nhất ở jobsgo (36%) và careerviet (19%).
- Lương thiếu theo sàn (số đúng): vietnamworks 78%, itviec 76%, topdev 75%, careerviet 72%, topcv 52%, jobsgo 50%, glints 40%, vieclam24h 9%.

## A. Insight 10 biểu đồ
1. **Phễu:** 13.361 → 4.799 (01_clean) → 4.672 (khử trùng) → 4.671 (tích hợp; chuẩn hóa không bỏ tin). Còn lại 35,0%. Số 13.361 là số đầu vào theo báo cáo 01_clean, chưa đối chiếu với số tin raw thật.
2. **Lý do loại ở 01_clean (tổng 8.562):** ngoài IT 5.424 (63%), giữ snapshot mới nhất 1.987 (là bản cũ của cùng tin, không phải mất tin), batch cũ 616, trùng cùng nguồn 200, JD dưới 50 từ 187, trùng liên sàn 135, CTV/đa cấp 13.
3. **Thiếu theo trường:** lương 2.851 (61,0%), số người tuyển 1.898 (40,6%), ngày đăng 1.692 (36,2%), nhóm Other 707 (15,1%), cấp bậc 388, phúc lợi 342, kỹ năng 292. Mô tả và yêu cầu gần như đủ.
4. **Heatmap theo sàn:** thiếu phụ thuộc vào sàn, không ngẫu nhiên (xem phần đính chính).
5. **Ngôn ngữ:** 3.390 tiếng Việt, 1.274 tiếng Anh (27,3%), 7 khác.
6. **Dịch EN→VI:** 1.052 thành công, 222 lỗi (17,4% số tin tiếng Anh).
7. **Độ dài mô tả:** lệch phải, trung vị 857 ký tự, p90 2.328.
8. **Bullet mỗi tin:** trung vị 23. Cột nhô ở 3 bullet là 401 tin, trong đó 399 là careerviet.
9. **Kỹ năng mỗi tin:** trung vị 5; 292 tin không có kỹ năng; 23,7% dưới 3 kỹ năng.
10. **Bảng minh chứng:** giá trị gốc → giá trị chuẩn hóa. Dòng lương gốc "You'll love it" được để trống đúng, không bịa số.

## B. Vấn đề, bằng chứng, đề xuất của mình, câu hỏi cho thầy

### Pre-processing
**PP1. Lương thiếu 61%**
- ✓ Bằng chứng: 2.515 tin "thỏa thuận"; 713 tin có chữ nhưng không ra số (589 "You'll love it", 91 "Công ty không công khai thông tin", 13 "Đăng nhập để xem mức lương"); 320 tin chỉ có min hoặc max; 1.835 tin không có trường lương. Tức là sàn ẩn lương, không phải lỗi parse.
- Hệ quả: phân tích lương chỉ trên 1.820 tin (39%) và lệch về các sàn công khai lương.
- Đề xuất: không điền số; giữ `salary_status` làm đặc trưng; ghi rõ thiên lệch chọn mẫu; nếu cần ước lượng thì làm riêng và gắn cờ.
- Câu hỏi: khi dữ liệu thiếu không ngẫu nhiên (ẩn lương theo sàn), có nên impute không, và dùng phương pháp nào (median theo nhóm nghề × cấp bậc, hồi quy, hay giữ missing-indicator)? Nói về thiên lệch chọn mẫu trong báo cáo thế nào?

**PP2. Thiếu theo sàn**
- ✓ Số người tuyển, ngày đăng, hạn nộp, loại hình thiếu 100% ở những sàn cụ thể. ? Khả năng cao là sàn không cung cấp trường đó (chưa kiểm trên raw).
- Đề xuất: đánh dấu "sàn không cung cấp" tách khỏi "tin không ghi"; không dùng các trường này làm đặc trưng chung cho phân cụm.
- Câu hỏi: với trường vắng cả một sàn, nên bỏ cột, giữ cờ, hay chuẩn hóa theo sàn?

**PP3. Careerviet không có xuống dòng**
- ✓ `raw_description_text` của careerviet có 0 dấu xuống dòng (các sàn khác 6–32 dòng mỗi tin), nên bước 07 chỉ ra 3 bullet mỗi tin (399/400 tin). Raw bất biến nên phải sửa ở tiền xử lý.
- Đề xuất: tách theo tiêu đề mục, dấu gạch đầu dòng hoặc số thứ tự trong chuỗi, rồi tách câu; đo lại trên bộ nhãn vàng.
- Câu hỏi: với nguồn mất cấu trúc, nên tách câu bằng luật hay bằng thư viện NLP tiếng Việt, và đánh giá chất lượng tách thế nào?

**PP4. Nhóm Other 15,1% (707 tin)**
- ✓ Tiêu đề phổ biến: "triển khai phần mềm", "tư vấn phần mềm", "kỹ sư phần mềm" (chung), "gán nhãn dữ liệu", "kỹ sư tự động hóa". ? Nguyên nhân: 10 nhóm không có chỗ cho tư vấn/triển khai và tiêu đề quá chung; còn 87 mục từ điển chưa duyệt.
- Đề xuất: duyệt từ điển, thêm luật cho nhóm tư vấn/triển khai, sau đó thử gán bằng kNN trên vector e5 từ các tin đã có nhãn.
- Câu hỏi: gán nhãn bằng luật hay bằng mô hình, và đo độ đúng thế nào khi chỉ có 100 JD nhãn vàng?

**PP5. Dịch lỗi 222 tin**
- ✓ itviec 112, vietnamworks 42, glints 28, careerviet 17, topcv 12, jobsgo 6, topdev 4, vieclam24h 1; tin lỗi dài hơn (trung bình 2.106 so với 1.441 ký tự). ? Hàm `is_valid` loại bản dịch nếu placeholder, số hoặc tỉ lệ độ dài lệch; chưa xác nhận đây là nguyên nhân.
- Đề xuất: thống kê tiêu chí nào loại bản dịch, thử nới tỉ lệ độ dài; so cụm có và không dịch để biết e5 đa ngôn ngữ có cần bản dịch không.
- Câu hỏi: kiểm chất lượng dịch máy khi không có bản tham chiếu nên dùng tiêu chí nào? Có cần dịch khi model embedding đã đa ngôn ngữ?

### Processing
**PR1. Trích kỹ năng yếu**
- ✓ F1 = 0,27 trên 100 JD nhãn vàng (đo phiên trước, chưa chạy lại; chỉ tính kỹ năng `via=text`, nhãn ngoài taxonomy 230 kỹ năng tính là bỏ sót); 292 tin không có kỹ năng; 23,7% dưới 3 kỹ năng; jobsgo thiếu 36%.
- Đề xuất: bổ sung kỹ năng thường gặp chưa có trong taxonomy, thêm khớp bằng độ giống e5, rồi đo lại F1.
- Câu hỏi: F1 dựa trên taxonomy cố định có công bằng không, và trích kỹ năng nên dùng luật, NER hay so khớp ngữ nghĩa?

**PR2. Chỉ 27,5% tin đủ 6 trường chính** (lương, kinh nghiệm, cấp bậc, tỉnh, ít nhất 1 kỹ năng, có nhóm nghề)
- Đề xuất: dùng cột `__missing`; phân cụm chỉ trên kỹ năng + e5 (không dính lương, kinh nghiệm); phân tích lương chỉ trên tập có lương.
- Câu hỏi: với Mining không giám sát, nên chọn complete-case, imputation hay missing-indicator?

**PR3. Phân cụm yếu**
- ✓ K-Means k=10: Silhouette 0,10 (dữ liệu xáo cột khoảng 0,04), Davies-Bouldin 2,49; Elbow không có khuỷu gãy, Silhouette không có đỉnh trong k = 2–20; cụm 1 chứa 292/293 tin không có kỹ năng, cụm 9 là cụm nhiều kỹ năng (trung vị 15), tức một phần cụm tách theo số kỹ năng; ARI với nhóm nghề 0,07.
- Đề xuất: lọc tin không kỹ năng, thử IDF cho kỹ năng, thử giảm chiều (UMAP) trước khi phân cụm, báo thêm độ ổn định.
- Câu hỏi: Silhouette khoảng 0,1 có chấp nhận được với dữ liệu văn bản thưa không, và nên biện luận số cụm bằng chỉ số nào ngoài Silhouette và Elbow?

**PR4. Dùng nhãn nghề làm thước đo**
- ✓ Nhãn nghề do luật tạo (không phải nhãn thật); Web chiếm 40% (1.853 tin); ARI/NMI chỉ tính trên 3.964 tin khác Other.
- Câu hỏi: có hợp lý khi dùng nhãn do luật làm "ground truth" để đánh giá cụm không giám sát không?

## C. Cách hỏi thầy (3 bước cho mỗi câu)
1. Nêu hiện tượng kèm số.
2. Nói rõ điều mình đã kiểm (✓) và chưa kiểm (?).
3. Nêu đề xuất của mình rồi hỏi: "Thầy thấy hướng này có ổn không, hay có cách chuẩn hơn?"
