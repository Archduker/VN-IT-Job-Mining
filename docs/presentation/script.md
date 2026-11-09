# Kịch bản thuyết trình: Tiền xử lý dữ liệu việc làm IT

Sinh bởi `python scripts/build_slides.py`, cùng số với `docs/presentation/slides.html`. Sửa lời trong script rồi chạy lại, đừng sửa file này bằng tay.

**Thời lượng gợi ý:** khoảng 1 phút mỗi slide, tổng khoảng 23 phút, chưa tính hỏi đáp. Trong slide bấm N để xem lời nói.

**Dàn bài:**

  - Slide 1. Tiền xử lý dữ liệu việc làm IT Việt Nam
- **Nội dung**
  - Slide 2. Bố cục bài trình bày
- **Vấn đề dữ liệu**
  - Slide 3. Dữ liệu vào: 14 nghìn bản ghi nhưng chỉ 10,7 nghìn tin
  - Slide 4. Dữ liệu raw có 11 nhóm vấn đề
  - Slide 5. Ví dụ raw thật (1): sai phạm vi, sai giá trị
  - Slide 6. Ví dụ raw thật (2): cùng một thông tin, mỗi nguồn ghi một kiểu
  - Slide 7. Tin ngoài IT lẫn vào dữ liệu
  - Slide 8. Trùng lặp: thêm điều kiện thì bớt trùng giả
  - Slide 9. Độ phủ trường: mỗi nguồn có một bộ trường khác nhau
  - Slide 10. Lương: bộ parse cũ đọc sai đơn vị
  - Slide 11. Địa điểm, cấp bậc, kỹ năng, ngày tháng: mỗi nguồn một kiểu
- **Quy trình xử lý**
  - Slide 12. Pipeline 5 bước: số dòng vào → ra mỗi bước
  - Slide 13. 1. Clean: bỏ bản cũ, trùng, ngoài IT, JD quá ngắn
  - Slide 14. 2. Integration: gộp 8 nguồn về một schema 18 trường
  - Slide 15. 3. Transformation: bóc lương, ngôn ngữ, địa điểm
  - Slide 16. 4. Normalization: cấp bậc, nhóm nghề, kỹ năng chuẩn
  - Slide 17. 5. Encoding: bảng đặc trưng cho mô hình
  - Slide 18. Đối chiếu: vấn đề nào được giải ở bước nào
- **Đánh giá**
  - Slide 19. Ưu điểm
  - Slide 20. Nhược điểm: dữ liệu còn 5 lỗ hổng
  - Slide 21. Hướng khắc phục
  - Slide 22. Xin ý kiến thầy: chọn hướng xử lý trước khi làm mô hình
  - Slide 23. Kết luận

## Slide 1. Tiền xử lý dữ liệu việc làm IT Việt Nam

**Nói:**

- Em chào thầy và các bạn. Em xin trình bày phần tiền xử lý dữ liệu của đề tài khai phá việc làm IT từ 8 trang tuyển dụng.
- Đầu vào là 14.292 bản ghi raw, đầu ra là 5.177 tin IT đã làm sạch với 230 cột đặc trưng.
- Mọi con số trên slide đều sinh tự động từ báo cáo của pipeline, thầy hỏi số nào em chỉ được file gốc.

**Thầy có thể hỏi:**

- *Tại sao chỉ 8 nguồn?*  
  Đây là 8 trang có lượng tin IT lớn và cào được ổn định; danh sách SOURCES trong preprocessing/common.
- *Số liệu lấy lúc nào?*  
  Ngày ghi trên slide là generated_at của báo cáo bước Encoding.

**Lấy số ở đâu:**

- `reports/preprocessing/01_clean/_all.json (input.rows, output.rows)`
- `reports/preprocessing/05_encoding/_all.json (extra.total_columns)`

*Chuyển ý → slide 2: Bố cục bài trình bày*

## Slide 2. Bố cục bài trình bày · Nội dung

**Nói:**

- Bài gồm ba phần: vấn đề của dữ liệu raw, quy trình 5 bước xử lý, và tự đánh giá kết quả.
- Mỗi bước xử lý đều chỉ rõ nó giải vấn đề nào ở phần 1; phần đánh giá nêu cả ưu điểm lẫn nhược điểm, kèm việc cụ thể để khắc phục.
- Cuối bài em có vài câu muốn xin ý kiến thầy trước khi làm mô hình.

**Thầy có thể hỏi:**

- *Trình bày bao lâu?*  
  Khoảng 1 phút mỗi slide; phần vấn đề và quy trình là chính, phần đánh giá ngắn hơn.

**Lấy số ở đâu:**

- `scripts/build_slides.py → SECTIONS`

*Chuyển ý → slide 3: Dữ liệu vào: 14 nghìn bản ghi nhưng chỉ 10,7 nghìn tin*

## Slide 3. Dữ liệu vào: 14 nghìn bản ghi nhưng chỉ 10,7 nghìn tin · Vấn đề dữ liệu

**Kết luận trên slide:** 14.292 bản ghi nhưng chỉ 10.758 tin khác nhau → phải giữ bản mới nhất và bỏ bản trùng trước.

**Nói:**

- Phần 1 là vấn đề dữ liệu: trước khi xử lý, em đo xem raw sai ở đâu và sai bao nhiêu.
- Cột trên cùng là mọi bản ghi raw đang có trên R2.
- Bỏ 1.547 tin chép lại trong file batch cũ thì còn 12.745 file từng tin.
- Một tin cào lại khi đã đổi nội dung thì có thêm phiên bản, nên chỉ có 10.758 tin khác nhau.
- Đây là lý do bước Clean phải giữ bản mới nhất trước khi làm gì khác.

**Thầy có thể hỏi:**

- *Raw có bị sửa không?*  
  Không. Raw là bất biến; mọi sửa nằm ở pre-processing.
- *Phiên bản mới sinh ra khi nào?*  
  Khi hash JSON chuẩn hóa của tin đổi (CDC trong collection/common/url_ledger.py).
- *Số theo từng nguồn đâu?*  
  Bảng 'Số tin theo nguồn' trong docs/spec/preprocessing/data_issues_2026-11-03.html.

**Lấy số ở đâu:**

- `docs/presentation/data/raw_issues_before.json → total_jobs, sources.<nguồn>.files`
- `reports/preprocessing/01_clean/_all.json → input.rows`
- `docs/spec/preprocessing/data_issues_2026-11-03.html (bảng theo nguồn)`

*Chuyển ý → slide 4: Dữ liệu raw có 11 nhóm vấn đề*

## Slide 4. Dữ liệu raw có 11 nhóm vấn đề · Vấn đề dữ liệu

**Nói:**

- Thống kê trên 10.758 tin raw (bản mới nhất mỗi tin), em gom được 11 nhóm vấn đề.
- Mỗi thẻ có một con số đo được trên raw để thấy độ lớn của vấn đề.
- Bốn vấn đề mức Cao là tin ngoài IT, ngày đăng tương đối, trùng lặp và lương sai, vì chúng làm sai thẳng kết quả phân tích.
- Hai slide sau là ví dụ raw thật để thầy thấy tận mắt.

**Thầy có thể hỏi:**

- *Đo các số này thế nào?*  
  Script scripts/report_data_issues.py đọc raw, lấy bản mới nhất mỗi tin, làm phẳng rồi đếm; kết quả lưu ở raw_issues_before.json.
- *Mức Cao/TB/Thấp dựa vào đâu?*  
  Cao là làm sai kết quả phân tích; A1, A2, B, D theo docs/spec/preprocessing/data_issues_2026-11-03.md, các nhóm còn lại do em đánh giá.
- *Tin ngoài IT ước lượng thế nào?*  
  Theo từ khóa tiêu đề, nên chỉ để thấy độ lớn; phân loại thật làm ở bước Clean và kiểm bằng nhãn tay.

**Lấy số ở đâu:**

- `docs/presentation/data/raw_issues_before.json`
- `docs/spec/preprocessing/data_issues_2026-11-03.md, .html`

*Chuyển ý → slide 5: Ví dụ raw thật (1): sai phạm vi, sai giá trị*

## Slide 5. Ví dụ raw thật (1): sai phạm vi, sai giá trị · Vấn đề dữ liệu

**Kết luận trên slide:** Không xử lý thì thống kê sẽ đếm cả việc kế toán, lương 2.000 USD thành 50 nghìn đồng, một công ty thành hai.

**Nói:**

- Đây là giá trị copy nguyên từ raw, không qua xử lý.
- Tin kế toán, kinh doanh nằm trong dữ liệu IT vì TopDev bỏ qua bộ lọc ngành.
- Lương USD bị đọc nhầm dấu phân cách hàng nghìn nên 2.000 USD còn vài chục nghìn đồng.
- Tên công ty viết hoa khác nhau thì máy đếm thành hai công ty.

**Thầy có thể hỏi:**

- *Kiểm ví dụ này ở đâu?*  
  Link gốc của tin ngoài IT nằm trong raw_issues_before.json → sources.topdev.title.non_it_examples; mở trang là thấy.
- *Sao không sửa ở lúc cào?*  
  Raw giữ nguyên để kiểm lại được; sửa ở pre-processing. Riêng phạm vi TopDev thì đã ghi việc sửa crawler.
- *“Đăng 6 giờ trước” lấy đâu?*  
  Trường posted_at_raw của ITviec; 855 tin có dạng này (docs/spec/preprocessing/data_issues_2026-11-03.md, A2).

**Lấy số ở đâu:**

- `docs/presentation/data/raw_issues_before.json → title.non_it_examples, salary.parsed_under_1m_examples, company.example, sneaky_null`

*Chuyển ý → slide 6: Ví dụ raw thật (2): cùng một thông tin, mỗi nguồn ghi một kiểu*

## Slide 6. Ví dụ raw thật (2): cùng một thông tin, mỗi nguồn ghi một kiểu · Vấn đề dữ liệu

**Kết luận trên slide:** Cùng một thông tin nhưng mỗi nguồn một kiểu → phải chuẩn hóa về một dạng chung trước khi phân tích.

**Nói:**

- Cùng là TP.HCM nhưng mỗi nguồn ghi một kiểu, có nguồn ghi cả địa chỉ đường phố.
- Cấp bậc mỗi nguồn một bộ từ, ITviec không có trường này.
- Kinh nghiệm có dạng số tháng, dạng khoảng, dạng chữ.
- Trường kỹ năng ở TopCV, JobsGO, Vieclam24h thực ra là ngành nghề, có cả tên công ty bị cắt.

**Thầy có thể hỏi:**

- *Ví dụ lấy thế nào?*  
  Là giá trị phổ biến nhất của mỗi nguồn (trường top) trong raw_issues_before.json.
- *Không chuẩn hóa thì sao?*  
  Không gom nhóm, không so giữa các nguồn được; ví dụ đếm tin theo tỉnh sẽ ra 5 dòng cho TP.HCM.

**Lấy số ở đâu:**

- `docs/presentation/data/raw_issues_before.json → sources.<nguồn>.location.top, seniority.top, experience.top, skills.top`

*Chuyển ý → slide 7: Tin ngoài IT lẫn vào dữ liệu*

## Slide 7. Tin ngoài IT lẫn vào dữ liệu · Vấn đề dữ liệu

**Kết luận trên slide:** Không lọc thì 82% tin TopDev là ngoài IT → Clean bỏ 5.514 tin (C4c) sau khi kiểm bằng nhãn tay.

**Nói:**

- TopDev có 82% tiêu đề ngoài IT, ví dụ Kế toán trưởng, Nhân viên kinh doanh.
- Nguyên nhân: API TopDev bỏ qua tham số category_ids=1, có hay không có đều ra 14.572 tin.
- Bước Clean phân loại bằng luật if-else 2 tầng: tầng 1 xét từ khóa tiêu đề; tin chưa quyết được thì tầng 2 xét nhóm nghề và số kỹ năng trong JD.
- Gán nhãn tay 541 tin để đo độ đúng, rồi mới bỏ 5.514 tin ngoài IT.

**Thầy có thể hỏi:**

- *Sao không bỏ hết TopDev?*  
  Vẫn có tin IT thật; sau phân loại còn 230 tin IT TopDev.
- *Luật đúng bao nhiêu?*  
  Tầng 1 đúng 303/304; tầng 2 khó hơn, đúng 194/237.
- *Tầng 2 là gì?*  
  Tiêu đề thuộc 1 trong 12 nhóm nghề IT và JD có ít nhất 2 kỹ năng công nghệ thì là IT; ngưỡng 2 cho kết quả tốt nhất khi thử 2–6.
- *Sao không dùng model AI?*  
  Luật if-else giải thích được từng quyết định, không phụ thuộc dịch vụ ngoài; độ đúng đo bằng nhãn tay.

**Lấy số ở đâu:**

- `reports/preprocessing/01_clean/_all.json → extra.review, extra.it_levels, rules C4a/C4c`
- `data/preprocessing/review/it_<nguồn>.csv (nhãn tay)`
- `preprocessing/common/it_filter.py (classify, classify_unknown)`

*Chuyển ý → slide 8: Trùng lặp: thêm điều kiện thì bớt trùng giả*

## Slide 8. Trùng lặp: thêm điều kiện thì bớt trùng giả · Vấn đề dữ liệu

**Kết luận trên slide:** Clean bỏ 3.413 bản ghi trùng (C1, C2, C6, C7); so trùng chỉ đúng khi tỉnh đã chuẩn hóa.

**Nói:**

- Luật trùng: cùng công ty, cùng tiêu đề, cùng tỉnh, cùng tuần đăng.
- Chỉ so tiêu đề + công ty thì 171 nhóm trùng khác nguồn; thêm tỉnh thì còn 9, vì mỗi nguồn ghi thành phố một kiểu.
- Thêm điều kiện cùng tuần đăng vì công ty hay đăng lại cùng vị trí sau vài tháng: đó là đợt tuyển mới, không phải bản trùng.
- Nên phải chuẩn hóa tỉnh trước rồi mới so trùng.

**Thầy có thể hỏi:**

- *Tin trùng khác nguồn thì giữ bản nào?*  
  Giữ một bản, ghi các nguồn còn lại vào cột also_on (C7).
- *Thiếu ngày đăng thì sao?*  
  TopCV, TopDev không có ngày đăng nên dùng tuần cào.

**Lấy số ở đâu:**

- `raw_issues_before.json → dedup`
- `reports/preprocessing/01_clean/_all.json → rules C1, C2, C6, C7; extra.cross_source_pairs`

*Chuyển ý → slide 9: Độ phủ trường: mỗi nguồn có một bộ trường khác nhau*

## Slide 9. Độ phủ trường: mỗi nguồn có một bộ trường khác nhau · Vấn đề dữ liệu

**Kết luận trên slide:** Giữ 18 trường dùng chung được; 6 trường chỉ 1–2 nguồn có thì bỏ (I1), null trá hình về null (T1, I5).

**Nói:**

- Ô là phần trăm tin có giá trị của trường đó ở nguồn đó; xanh là đủ, đỏ là thiếu.
- Luật: trích được thì lấy, không thì để null; chỉ giữ trường có ở ít nhất 3 nguồn.
- Ô đỏ ở TopDev và ITviec là do flattener chưa đọc đúng chỗ, đã sửa ở luật I2, I3.

**Thầy có thể hỏi:**

- *Sao không bù giá trị thiếu?*  
  Bù sẽ tạo số giả; giữ null và có cột missing ở bước Encoding (E5).
- *Null trá hình là gì?*  
  Giá trị như '0' hay chuỗi rỗng mà thật ra là thiếu, ví dụ VietnamWorks education = '0' ở 309 tin.

**Lấy số ở đâu:**

- `raw_issues_before.json → field_matrix`
- `reports/preprocessing/02_integration/_all.json → fields (fill_pct_in/out)`

*Chuyển ý → slide 10: Lương: bộ parse cũ đọc sai đơn vị*

## Slide 10. Lương: bộ parse cũ đọc sai đơn vị · Vấn đề dữ liệu

**Kết luận trên slide:** Bộ parse cũ đọc sai 251 tin, bộ mới còn 0 → lương dùng được để thống kê.

**Nói:**

- Biểu đồ là số tin bộ parse cũ đọc sai ở từng nguồn; bộ mới chạy lại trên cùng raw thì còn 0 tin sai.
- Lỗi chính: dấu phân cách hàng nghìn bị đọc thành dấu thập phân, nên 2.000 USD chỉ còn vài chục nghìn đồng.
- Bảng bên phải là ví dụ thật: chuỗi lương trong raw, bộ cũ đọc thành gì, bộ mới đọc thành gì.
- Bộ mới chỉ nhận số có đơn vị tiền, đọc nguyên số có dấu phân cách, chặn lương tháng ngoài 1–500 triệu.

**Thầy có thể hỏi:**

- *Lương thỏa thuận xử lý sao?*  
  Giữ trống và cờ is_negotiable, không bù.
- *USD đổi thế nào?*  
  Tỉ giá cố định 25.400 VND/USD, ghi trong salary_parser.py.
- *Cột 'bộ mới đọc' lấy đâu?*  
  Script gọi parse_salary_cascade trên đúng chuỗi raw đó lúc tạo slide, không gõ tay.
- *Ngưỡng 500 triệu ở đâu ra?*  
  Lương tháng IT ở Việt Nam trên 500 triệu gần như không có; số trên đó là parse sai, nên để trống và gắn cờ salary_suspect.

**Lấy số ở đâu:**

- `raw_issues_before.json → sources.<nguồn>.salary.parsed_under_1m_examples`
- `preprocessing/transformation/salary_parser.py → parse_salary_cascade`
- `reports/preprocessing/03_transformation/_all.json → rules T2, T2f`

*Chuyển ý → slide 11: Địa điểm, cấp bậc, kỹ năng, ngày tháng: mỗi nguồn một kiểu*

## Slide 11. Địa điểm, cấp bậc, kỹ năng, ngày tháng: mỗi nguồn một kiểu · Vấn đề dữ liệu

**Kết luận trên slide:** Chưa chuẩn hóa thì không so được giữa các nguồn → bóc tách (T3, T4, T7, T8) rồi quy chuẩn (N1–N4).

**Nói:**

- Bốn biểu đồ cho bốn nhóm vấn đề. ITviec và VietnamWorks ghi địa chỉ đường phố, phải tách ra tỉnh và phường.
- Cấp bậc mỗi nguồn một bộ từ, ITviec, Glints không có.
- Kỹ năng ở TopCV, JobsGO, Vieclam24h lẫn danh mục ngành và câu dài.
- TopCV, TopDev không có ngày đăng.

**Thầy có thể hỏi:**

- *Phường/xã lấy theo danh mục nào?*  
  3.321 phường/xã sau sáp nhập 2025 từ thanglequoc/vietnamese-provinces-database (MIT), file wards_34.json.
- *Quận huyện đâu?*  
  Bỏ hẳn vì sau 2025 không còn cấp huyện.
- *Cấp bậc chuẩn có mấy bậc?*  
  6 bậc: Thực tập, Mới tốt nghiệp, Junior, Middle, Senior, Trưởng nhóm/Quản lý; không xác định thì để trống.

**Lấy số ở đâu:**

- `raw_issues_before.json → sources.<nguồn>.location / seniority / skills / dates`

*Chuyển ý → slide 12: Pipeline 5 bước: số dòng vào → ra mỗi bước*

## Slide 12. Pipeline 5 bước: số dòng vào → ra mỗi bước · Quy trình xử lý

**Kết luận trên slide:** 14.292 bản ghi raw → 5.177 tin sạch; mọi dòng bị bỏ đều có luật và lý do.

**Nói:**

- Phần 2 là quy trình: 5 bước nối tiếp, mỗi bước giải một số vấn đề vừa nêu.
- Chỉ bước Clean bỏ dòng; bốn bước sau giữ nguyên số dòng, chỉ sửa và thêm cột.
- Mỗi bước ghi báo cáo theo luật bảo toàn: số vào bằng số ra cộng số bỏ.
- Từ Integration, 8 nguồn gộp thành một bảng all.parquet có cột source_platform.
- Dòng '←' là vấn đề mà bước đó giải.

**Thầy có thể hỏi:**

- *Kiểm bảo toàn dòng ở đâu?*  
  Trường checks.rows_conserved trong mỗi _all.json, hiện đang true.
- *Sao gộp ở Integration?*  
  Từ đó các nguồn cùng schema, xử lý chung một lần; báo cáo vẫn giữ số theo nguồn (by_source).
- *Silver, gold nằm đâu?*  
  R2 bucket vn-it-jobs: bronze raw/<nguồn>/…, silver staging/<nguồn>/preprocessing/<bước>.*, gold curated/preprocessing/features.parquet.
- *Cho thầy xem dữ liệu?*  
  Mở ./start_monitoring.sh, vào http://127.0.0.1:5173: trang Raw cho bronze; trang Pre-processing chọn bước, bấm một dòng để xem đủ trường (đọc thẳng từ R2).
- *Máy và R2 có khớp không?*  
  python scripts/push_preprocessing_to_r2.py (không cờ chỉ so, không ghi); lần kiểm gần nhất 34/34 khớp.

**Lấy số ở đâu:**

- `reports/preprocessing/<bước>/_all.json → input.rows, output.rows, checks`
- `python scripts/push_preprocessing_to_r2.py (chạy không cờ chỉ so máy với R2)`

*Chuyển ý → slide 13: 1. Clean: bỏ bản cũ, trùng, ngoài IT, JD quá ngắn*

## Slide 13. 1. Clean: bỏ bản cũ, trùng, ngoài IT, JD quá ngắn · Quy trình xử lý

**Kết luận trên slide:** Clean giữ 36,2% bản ghi; phần bỏ chủ yếu là bản trùng và tin ngoài IT.

**Nói:**

- Bỏ nhiều nhất là tin ngoài IT (5.514) và bản cũ (1.987).
- Tin ngoài IT: tầng 1 (từ khóa tiêu đề) xếp 2.112 tin, tầng 2 (nhóm nghề + kỹ năng JD) xếp 3.417 tin.
- C5 bỏ 188 tin có JD dưới 30 từ, không đủ nội dung để phân tích.
- Còn lại 5.177 tin.

**Thầy có thể hỏi:**

- *Sao ITviec vẫn còn vài tin ngoài IT?*  
  Chính sách đã duyệt cho ITviec là không bỏ tin nào vì đây là trang chuyên IT; tin bị luật xếp ngoài IT vẫn giữ.
- *Tin bị bỏ có xem lại được không?*  
  Có, mỗi luật lưu ví dụ (examples) trong báo cáo và hiện trên trang Monitoring.

**Lấy số ở đâu:**

- `reports/preprocessing/01_clean/_all.json`
- `python scripts/run_preprocessing.py --step clean --source all --dry-run`

*Chuyển ý → slide 14: 2. Integration: gộp 8 nguồn về một schema 18 trường*

## Slide 14. 2. Integration: gộp 8 nguồn về một schema 18 trường · Quy trình xử lý

**Kết luận trên slide:** Từ đây mọi nguồn dùng chung một schema → các bước sau xử lý một lần cho cả 8 nguồn.

**Nói:**

- Integration làm phẳng envelope của từng nguồn về cùng 18 trường.
- Sửa 874 tin ITviec lấy ngày từ JSON-LD thay cho 'Đăng 6 giờ trước', và 71 tin TopDev lấy ngày đăng, kinh nghiệm.
- I4 bỏ tag SEO, ngành nghề khỏi kỹ năng ở 1.030 tin.

**Thầy có thể hỏi:**

- *I0 bằng 0 nghĩa là gì?*  
  Không có dòng JSON hỏng; luật vẫn chạy và tô đỏ trên Monitoring nếu có.
- *Sao vẫn 5.177 dòng?*  
  Integration không bỏ tin, chỉ đổi dạng.

**Lấy số ở đâu:**

- `reports/preprocessing/02_integration/_all.json`
- `preprocessing/integration/json_flattener.py`

*Chuyển ý → slide 15: 3. Transformation: bóc lương, ngôn ngữ, địa điểm*

## Slide 15. 3. Transformation: bóc lương, ngôn ngữ, địa điểm · Quy trình xử lý

**Kết luận trên slide:** Không còn lương sai đơn vị; 1.395 JD tiếng Anh được nhận đúng và vẫn rút được kỹ năng.

**Nói:**

- Biểu đồ so cùng dữ liệu trước và sau khi sửa các lỗi tìm được khi review.
- Lương chỉ lấy từ tiêu đề khi có đơn vị tiền, nên từ 676 còn 22 tin, bỏ các số trong mã tin, năm.
- Ngôn ngữ chỉ xét JD: dưới 1% chữ có dấu tiếng Việt là tiếng Anh; bỏ nhãn bilingual.
- Phường/xã chỉ nhận khi có trong danh mục mới của đúng tỉnh.

**Thầy có thể hỏi:**

- *Sao không dịch JD tiếng Anh?*  
  Dự án không dùng model; từ điển kỹ năng song ngữ nên JD tiếng Anh vẫn rút được kỹ năng, cột language cho biết ngôn ngữ.
- *Sao tiếng Anh tăng?*  
  1.583 tin bilingual cũ được xếp lại theo JD; phần lớn là tiếng Việt có vài từ tiếng Anh.
- *Ngưỡng 1% ở đâu ra?*  
  Để chịu được tiêu đề mục song ngữ kiểu 'Bằng cấp / Education' trong JD tiếng Anh.

**Lấy số ở đâu:**

- `reports/preprocessing/03_transformation/_all.json → rules T2–T8, extra.language_distribution`
- `docs/presentation/data/before_review.json`

*Chuyển ý → slide 16: 4. Normalization: cấp bậc, nhóm nghề, kỹ năng chuẩn*

## Slide 16. 4. Normalization: cấp bậc, nhóm nghề, kỹ năng chuẩn · Quy trình xử lý

**Kết luận trên slide:** Phân bố cấp bậc hợp lý lại (Middle không còn chiếm đa số) → số liệu theo cấp bậc dùng phân tích được.

**Nói:**

- Trước đây 54% tin bị xếp Middle vì 'Nhân viên' bị hiểu là Middle; giờ còn 13,5%.
- Không xác định được cấp bậc thì để trống, không đoán.
- Kỹ năng C trước khớp cả chữ C đơn lẻ nên có ở 6.912 tin; nay chỉ nhận C/C++, 'ngôn ngữ C'.
- Luật mâu thuẫn gắn cờ 635 tin: Senior mà dưới 2 năm kinh nghiệm, Thực tập mà từ 3 năm, hoặc có nhóm nghề mà JD không có kỹ năng nào.

**Thầy có thể hỏi:**

- *Sao 'Không rõ' nhiều?*  
  700 tin không ghi cấp bậc ở raw, tiêu đề hay số năm kinh nghiệm; để trống trung thực hơn đoán.
- *12 nhóm nghề gồm gì?*  
  Backend, Frontend, Fullstack, Mobile, Data/AI, DevOps/Cloud, QA/QC, Bảo mật, Hệ thống/Mạng, BA, PM, UI/UX; còn lại là Khác.
- *IQR làm gì?*  
  Lương ngoài [Q1 − 1,5·IQR; Q3 + 1,5·IQR] gắn cờ is_outlier_salary (113 tin), không xóa.

**Lấy số ở đâu:**

- `reports/preprocessing/04_normalization/_all.json → rules N1–N7`
- `data/preprocessing/04_normalization/all.parquet (cột seniority, skills_std)`

*Chuyển ý → slide 17: 5. Encoding: bảng đặc trưng cho mô hình*

## Slide 17. 5. Encoding: bảng đặc trưng cho mô hình · Quy trình xử lý

**Kết luận trên slide:** Đầu ra cuối là bảng 5.177 dòng × 230 cột, lưu tầng gold trên R2.

**Nói:**

- Mô hình chỉ đọc được số, nên bước cuối đổi mọi trường thành các cột số; mỗi cột như vậy gọi là một cột đặc trưng.
- Cấp bậc là thứ bậc 0–5, chưa rõ là −1; nhóm nghề one-hot; tỉnh và kỹ năng multi-hot.
- Trường số giữ nguyên và có cờ thiếu giá trị đi kèm.

**Thầy có thể hỏi:**

- *Sao chỉ 200 kỹ năng?*  
  Lấy kỹ năng phổ biến nhất để ma trận không quá thưa; danh sách trong encoding_dictionary.json.
- *Độ thưa 97% có sao không?*  
  Bình thường với multi-hot kỹ năng; mô hình dùng ma trận thưa.

**Lấy số ở đâu:**

- `reports/preprocessing/05_encoding/_all.json`
- `data/preprocessing/05_encoding/features.parquet, encoding_dictionary.json`

*Chuyển ý → slide 18: Đối chiếu: vấn đề nào được giải ở bước nào*

## Slide 18. Đối chiếu: vấn đề nào được giải ở bước nào · Quy trình xử lý

**Nói:**

- Bảng đọc theo hai chiều: mỗi vấn đề ở slide 4 đều có bước giải, và mọi luật trong 5 bước đều giải ít nhất một vấn đề.
- Cột kết quả là số tin thật mà bước đó bỏ hoặc sửa, lấy từ báo cáo của bước.

**Thầy có thể hỏi:**

- *Kết quả lấy từ đâu?*  
  rows_affected của luật trong reports/preprocessing/<bước>/_all.json; mã luật: A1: C4c; A2: I2; A3: I3; B: C1, C2, C6, C7; C: T1; D: T2; E: N1; F: N2; G: N4; H: T3; I: C5.
- *Có luật nào bằng 0?*  
  C3 (bản ghi lỗi) và I0 (JSON hỏng) bằng 0: luật chặn an toàn, lần chạy này không gặp bản ghi lỗi.
- *Làm sao chắc không sót?*  
  Hàm check_links() trong build_slides.py so bảng vấn đề với danh sách luật của 5 báo cáo; lệch thì không tạo slide.

**Lấy số ở đâu:**

- `scripts/build_slides.py → ISSUE_TO_RULES, SOLVE, check_links()`
- `reports/preprocessing/<bước>/_all.json → rules[].rows_affected`

*Chuyển ý → slide 19: Ưu điểm*

## Slide 19. Ưu điểm · Đánh giá

**Kết luận trên slide:** Kết quả xử lý kiểm chứng được bằng số và chạy lại được, không dựa vào cảm tính.

**Nói:**

- Phần 3, em tự đánh giá kết quả: ưu điểm, nhược điểm và hướng khắc phục.
- Trước hết là sáu điểm mạnh; điểm nào cũng có con số kiểm được.
- Quan trọng nhất là truy vết: báo cáo mỗi bước ghi số vào bằng số ra cộng số bỏ, nên không có dòng nào mất mà không rõ lý do.
- Luật lọc IT không đặt theo cảm tính: tầng 1 đúng 303/304 tin trên mẫu gán nhãn tay.
- Các lỗi gốc như lương sai đơn vị và cấp bậc lệch về Middle đã sửa tận gốc ở bộ parse, không vá tay.
- Thiếu thì để trống và gắn cờ, không bù số giả; và toàn bộ là luật if-else nên ai chạy lại cũng ra đúng số này.

**Thầy có thể hỏi:**

- *Bảo toàn dòng kiểm ở đâu?*  
  Trường checks.rows_conserved trong mỗi reports/preprocessing/<bước>/_all.json, cả 5 bước đều true.
- *Sao không bù giá trị thiếu?*  
  Bù sẽ tạo số giả, nhất là nhãn lương; giữ trống và có cột cờ thiếu giá trị ở bước Encoding.
- *Chạy lại toàn bộ thế nào?*  
  python scripts/run_preprocessing.py --step all --source all, rồi python scripts/build_slides.py.

**Lấy số ở đâu:**

- `reports/preprocessing/<bước>/_all.json → checks.rows_conserved`
- `reports/preprocessing/01_clean/_all.json → extra.review`
- `docs/presentation/data/raw_issues_before.json, before_review.json (số trước sửa)`

*Chuyển ý → slide 20: Nhược điểm: dữ liệu còn 5 lỗ hổng*

## Slide 20. Nhược điểm: dữ liệu còn 5 lỗ hổng · Đánh giá

**Kết luận trên slide:** Lỗ hổng lớn nhất là lương (55% thiếu) → cần chốt cách xử lý trước khi chọn mô hình.

**Nói:**

- Ngược lại, em cũng nói thẳng nhược điểm: dữ liệu đưa vào mô hình còn năm lỗ hổng, đo trên cùng bảng 5.177 tin.
- Lớn nhất là lương: 55% tin để lương thỏa thuận, nên mô hình lương chỉ có 2.348 tin có nhãn.
- Nhóm nghề 'Khác' chiếm 11%; 875 tin là IT do luật tầng 2 quyết, độ đúng thấp hơn tầng 1.
- Dữ liệu cũng lệch: tập trung ở Hà Nội, TP.HCM và vài nguồn lớn.
- Slide sau là việc em sẽ làm cho từng lỗ hổng.

**Thầy có thể hỏi:**

- *Sao không bù lương thiếu luôn?*  
  Bù bằng trung bình sẽ tạo nhãn giả cho mô hình lương; em muốn thầy chọn hướng ở slide xin ý kiến.
- *'Khác' gồm gì?*  
  Tin IT không khớp 12 nhóm theo luật tiêu đề, ví dụ IT support, ERP, kỹ sư nhúng; xem cột job_family trong all.parquet.
- *Lệch vùng có sao không?*  
  Mô hình sẽ học chủ yếu thị trường Hà Nội, TP.HCM; kết luận cho tỉnh khác kém tin cậy.

**Lấy số ở đâu:**

- `data/preprocessing/04_normalization/all.parquet → salary_min_vnd/salary_max_vnd, job_family, it_rule_level, language, seniority, tinh_chinh, source_platform`
- `reports/preprocessing/05_encoding/_all.json → extra.total_columns, extra.skills_sparsity`

*Chuyển ý → slide 21: Hướng khắc phục*

## Slide 21. Hướng khắc phục · Đánh giá

**Kết luận trên slide:** Ưu tiên lương và luật IT tầng 2 vì ảnh hưởng trực tiếp đến nhãn mô hình.

**Nói:**

- Mỗi dòng là một nhược điểm, việc cụ thể em sẽ làm, và con số để biết đã xong.
- Lương: không bù trung bình vì sẽ tạo nhãn giả; mô hình lương học trên 2.348 tin có lương.
- Luật IT tầng 2 còn sai khoảng 18%: cách sửa là gán thêm nhãn tay rồi chỉnh luật, vẫn không dùng model.
- Hai việc này làm trước vì chúng quyết định nhãn của mô hình; vài hướng em chưa chắc nên xin ý kiến thầy ở slide sau.

**Thầy có thể hỏi:**

- *Tin bị bỏ nhầm thì sao?*  
  Danh sách tin bị bỏ nằm trong báo cáo Clean (C4c); gán thêm nhãn tay vào data/preprocessing/review/ rồi chỉnh luật tầng 2.
- *Sao không dịch JD tiếng Anh?*  
  Từ điển kỹ năng có cả tiếng Anh và tiếng Việt nên vẫn rút được kỹ năng; dịch cần model, dự án đã bỏ model.
- *230 cột thưa 97,2% thì sao?*  
  Mô hình dùng ma trận thưa; nếu cần thì giảm chiều bằng SVD hoặc chỉ giữ top 50 kỹ năng.

**Lấy số ở đâu:**

- `data/preprocessing/04_normalization/all.parquet → salary_min_vnd, job_family, it_rule_level, language, seniority, tinh_chinh`
- `reports/preprocessing/01_clean/_all.json → extra.review`

*Chuyển ý → slide 22: Xin ý kiến thầy: chọn hướng xử lý trước khi làm mô hình*

## Slide 22. Xin ý kiến thầy: chọn hướng xử lý trước khi làm mô hình · Đánh giá

**Nói:**

- Đây là các hướng em chưa tự quyết được: mỗi thẻ là một lỗ hổng, kèm hai hướng em đang cân nhắc.
- Em muốn thầy góp ý hướng nào hợp với mục tiêu đề tài, hoặc gợi ý hướng khác.
- Câu em ưu tiên hỏi nhất là số 1 (lương) và số 2 (độ đúng luật IT), vì ảnh hưởng trực tiếp đến dữ liệu đưa vào mô hình.

**Thầy có thể hỏi:**

- *Em định dùng mô hình gì?*  
  Còn tùy hướng xử lý: dự đoán lương là hồi quy; phân nhóm nghề là phân loại; khai phá kỹ năng có thể dùng luật kết hợp.
- *Em nghiêng về hướng nào?*  
  Lương: A, học trên tin có lương để khỏi nhãn giả. Luật IT: A nếu thầy chấp nhận sai số khoảng 18%, B nếu cần chính xác hơn.
- *Sao không làm cả hai rồi so?*  
  Được, nếu thầy đồng ý thì em chạy cả A và B rồi báo cáo chênh lệch.

**Lấy số ở đâu:**

- `data/preprocessing/04_normalization/all.parquet`
- `data/preprocessing/05_encoding/features.parquet, encoding_dictionary.json`
- `reports/preprocessing/01_clean/_all.json → extra.review`

*Chuyển ý → slide 23: Kết luận*

## Slide 23. Kết luận · Đánh giá

**Nói:**

- Tóm lại, từ 14.292 bản ghi raw của 8 trang, em thu được 5.177 tin IT sạch với 230 cột đặc trưng.
- Cả 11 nhóm vấn đề đều có luật xử lý, số liệu kiểm được trong báo cáo từng bước và trên Monitoring.
- Bước tiếp theo là mô hình: hồi quy cho lương, phân loại cho nhóm nghề, luật kết hợp cho kỹ năng, theo hướng thầy góp ý.
- Phần trình bày của em đến đây là hết. Em cảm ơn thầy và các bạn đã lắng nghe, em xin nhận câu hỏi và góp ý.

**Thầy có thể hỏi:**

- *Em định dùng mô hình gì?*  
  Dự đoán lương là hồi quy; phân nhóm nghề là phân loại; khai phá kỹ năng dùng luật kết hợp (Apriori/FP-Growth).
- *Cho thầy xem dữ liệu thật?*  
  ./start_monitoring.sh, mở http://127.0.0.1:5173: trang Raw cho bronze, trang Pre-processing cho silver/gold, bấm một dòng để xem đủ trường.

**Lấy số ở đâu:**

- `reports/preprocessing/01_clean/_all.json (input.rows, output.rows)`
- `reports/preprocessing/05_encoding/_all.json (extra.total_columns)`

## Việc còn tồn đọng (ghi chú cho mình, không chiếu)

- Luật IT tầng 2 đúng 81,9% (194/237 tin gán nhãn); gán thêm nhãn tay để chỉnh luật nếu cần độ đúng cao hơn.
- TopDev: cần cào lại để có ngày đăng, kinh nghiệm; crawler cũng đang cào cả tin ngoài IT vì API bỏ qua bộ lọc ngành.
- ITviec giữ mọi tin theo chính sách đã duyệt, kể cả 11 tin luật xếp ngoài IT.
- Mô hình: chờ thầy chọn hướng cho lương thiếu (55%), độ đúng luật IT, nhóm nghề 'Khác' (11%), giảm chiều, lệch vùng (PRE-11).
- Mức Cao/TB/Thấp của các nhóm thiếu trường, địa điểm, cấp bậc, kỹ năng, ngày, văn bản là tự đánh giá; tài liệu gốc chưa ghi.
