# Giải thích slide 11–21 (SD3, SD4, SD5, đánh giá, kết luận)

Tài liệu cho người trình bày slide 11–21 của `final_slides.html`, viết để người không học IT cũng hiểu được. Mọi con số lấy từ lần chạy thật ngày 22/11/2026, gồm 3.718 tin IT, tháng 9–11/2026, nguồn `mining/artifacts/mining_metrics.json`. Câu hỏi của thầy trong file này là **câu hỏi dự kiến**, không phải câu thầy đã hỏi.

**Cách dùng:**
- **Phần 1** là từ điển thuật ngữ. Đọc trước một lần.
- **Phần 2** đi từng slide. Mỗi slide có 5 mục:
  1. Slide nói gì.
  2. Đọc biểu đồ và con số.
  3. Lời thoại gợi ý.
  4. Câu hỏi dự kiến.
  5. Điểm yếu nên nói trước.
- **Phần 3** chuẩn bị riêng cho phần "chưa rõ" ở slide 15.
- **Phần 4** là bảng tra nhanh mọi con số.

---

## Phần 1. Từ điển thuật ngữ

### Dữ liệu

| Thuật ngữ | Giải thích đời thường | Ví dụ trong đề tài |
|---|---|---|
| Tin tuyển dụng, JD | Một bài đăng tuyển người. JD (job description) là phần mô tả công việc và yêu cầu | "Java Developer (>5 YOE)" trên VietnamWorks |
| Công cụ (K-tool) | Tên một phần mềm, ngôn ngữ hay sản phẩm cụ thể mà tin đòi | java, docker, figma, excel |
| Khái niệm (K-concept) | Một mảng kiến thức, không phải sản phẩm cụ thể | kiểm thử API, microservices, phân tích nghiệp vụ |
| Kỹ năng mềm (K-soft) | Thái độ, giao tiếp, ngoại ngữ | phối hợp, chủ động, tiếng Anh |
| Nhóm nghề (`job_family`) | Nhãn nghề nhóm gán bằng luật if-else, đọc từ chức danh và nội dung tin. Không dùng AI để gán | Web, Bridge (BA/PM), Data/AI, Tester… |
| Cấp bậc | Intern/Fresher → Junior → Middle → Senior → Lead/Manager | |
| Thỏa thuận | Tin không ghi lương. 2.105/3.718 tin là thỏa thuận | |
| MNAR (thiếu không ngẫu nhiên) | Dữ liệu thiếu có quy luật chứ không do may rủi. Cấp càng cao càng hay giấu lương, nên trung vị lương của cấp cao bị thấp hơn thực tế | Lead có 57,7% tin thỏa thuận |

### Biểu diễn tin thành số

| Thuật ngữ | Giải thích đời thường | Ví dụ trong đề tài |
|---|---|---|
| Vector | Một dãy số đại diện cho một tin, để máy tính so tin này với tin kia | |
| e5 (multilingual-e5-base) | Một mô hình ngôn ngữ có sẵn, đọc đoạn mô tả và yêu cầu của tin rồi trả về 768 con số, giống "dấu vân tay nội dung". Hai tin viết về cùng loại việc thì dấu vân tay gần nhau, kể cả khi dùng chữ khác nhau. Chỉ dùng để biến chữ thành số, không dùng để gán nghề | |
| SVD, PCA | Kỹ thuật nén nhiều cột thành ít cột mà vẫn giữ phần thông tin chính, giống chụp ảnh 2D của một vật 3D | SVD nén khoảng 1.600 cột còn 60 cột để phân cụm. PCA nén còn 2–3 trục để vẽ |

### Phân cụm và đo chất lượng cụm (SD3)

| Thuật ngữ | Giải thích đời thường | Ví dụ trong đề tài |
|---|---|---|
| Phân cụm (clustering) | Để máy tự xếp các tin giống nhau vào chung nhóm, **không cho trước đáp án**. Giống xếp quần áo trong tủ mà không có nhãn | |
| K-Means, k | K-Means là một cách phân cụm: chọn k "tâm", mỗi tin về tâm gần nhất, rồi dời tâm vào giữa nhóm và lặp lại. k là số cụm muốn có | k = 10 |
| seed, `n_init` | seed là "hạt giống ngẫu nhiên" quyết định điểm xuất phát. `n_init` = 150 nghĩa là thử 150 điểm xuất phát rồi giữ kết quả tốt nhất | |
| Silhouette | Điểm từ −1 đến 1. Gần 1 là các cụm tách nhau rõ, gần 0 là ranh giới giữa các cụm mờ | Ở đây là 0,075 |
| ARI | Độ giống nhau giữa hai cách chia nhóm: 1 là giống hệt, 0 là giống như chia ngẫu nhiên | Dùng để kiểm cụm có ổn định không khi đổi seed |
| NMI | Cũng đo độ giống giữa hai cách chia, từ 0 đến 1 | So cụm với nhóm nghề gán bằng luật |
| Lift | Kỹ năng xuất hiện trong cụm nhiều gấp mấy lần so với toàn thị trường | Lift 5 nghĩa là gấp 5 lần, kỹ năng "đặc trưng" của cụm |

### Phát hiện tin bất thường (SD3)

| Thuật ngữ | Giải thích đời thường | Ví dụ trong đề tài |
|---|---|---|
| Isolation Forest (IF) | Thuật toán tìm điểm lạ. Nó cắt ngẫu nhiên dữ liệu nhiều lần, tin nào bị tách riêng ra sau ít nhát cắt thì là tin lạ, giống người đứng lẻ loi giữa đám đông. Ở đây nhìn cùng lúc: kinh nghiệm, lương, lương so với cấp, số công cụ, cấp | |
| Contamination 3% | Tham số bảo IF đánh dấu khoảng 3% tin lạ nhất trong số tin biết cấp | |
| HDBSCAN, GLOSH | HDBSCAN tìm các vùng dày đặc tin. GLOSH chấm điểm tin nào nằm ngoài rìa vùng dày của nó, tức là có hồ sơ kỹ năng ít gặp | |
| Phân vị P95, P99 | P95 là mức mà 95% tin nằm dưới | P99 số công cụ là 27, nghĩa là chỉ 1% tin đòi hơn 27 công cụ |
| Mã lý do | Nhãn giải thích vì sao tin bị coi là lạ | `TOO_MANY_SKILLS` (đòi quá nhiều công cụ), `SALARY_TOO_LOW_FOR_LEVEL` (lương thấp bất thường so với cấp) |

### Mô hình lương (SD4)

| Thuật ngữ | Giải thích đời thường | Ví dụ trong đề tài |
|---|---|---|
| Random Forest | Mô hình dự đoán gồm hàng trăm "cây quyết định". Mỗi cây hỏi chuỗi câu như "kinh nghiệm > 3 năm? có docker?" rồi đoán lương; kết quả là trung bình của các cây | |
| Baseline | Cách đoán đơn giản nhất để so sánh. Mô hình chỉ có giá trị nếu thắng baseline | Lấy trung vị lương cùng cấp và cùng nghề |
| MAE | Sai số tuyệt đối trung bình, đơn vị triệu đồng/tháng | MAE 6,1 nghĩa là trung bình đoán lệch 6,1 triệu |
| R² | Mô hình giải thích được bao nhiêu phần sự khác nhau về lương, từ 0 đến 1 | 0,56 là khoảng 56% |
| Thang log | Lấy log lương trước khi học, để chênh 10 → 20 triệu được coi ngang 30 → 60 triệu, và vài tin lương rất cao không kéo lệch mô hình | |
| Chia theo công ty, rò rỉ | Tin của một công ty chỉ nằm ở phần học hoặc phần thi, không nằm cả hai. Nếu không, mô hình "học thuộc" lương của công ty đó rồi được thi lại chính công ty đó, nên điểm cao giả | |
| SHAP | Cách chia điểm dự đoán cho từng yếu tố, giống chia công khi cả nhóm cùng làm. Nó cho biết trong mức lương đoán ra, phần nào do kinh nghiệm, phần nào do cấp, phần nào do từng kỹ năng | |
| Bootstrap, khoảng tin cậy 95% | Lấy mẫu lại dữ liệu nhiều lần (200 lần) để xem con số dao động bao nhiêu | Khoảng 0,41–0,70 triệu nghĩa là con số thật nhiều khả năng nằm trong đó |

### Lộ trình học (SD5) và nghiệm thu

| Thuật ngữ | Giải thích đời thường | Ví dụ trong đề tài |
|---|---|---|
| coverage@10 | Lấy 10 công cụ đầu lộ trình rồi đếm: bao nhiêu phần trăm tin cho người mới mà người học xong 10 công cụ đó đáp ứng ít nhất 70% công cụ tin đòi | |
| Chia 80/20 | Tính lộ trình trên 80% tin, kiểm trên 20% còn lại. Hai bên lệch quá 10 điểm thì lộ trình chưa ổn định, ghi "tham khảo" | |
| Cổng nghiệm thu | Ngưỡng đặt trước (chốt 22/11). Đạt thì dùng kết quả để kết luận, không đạt thì ghi rõ lý do | |

---

## Phần 2. Từng slide

### Slide 11. "10 cụm việc IT: bấm từng cụm để xem"

**Slide nói gì.** Máy tự chia 3.718 tin thành 10 nhóm việc dựa trên nội dung tin, không dựa vào nhãn nghề có sẵn.

**Đọc biểu đồ:**
- Mỗi chấm là một tin, mỗi màu là một cụm.
- Bấm tên cụm thì cụm đó sáng lên và hiện bảng thông tin. Bấm "Tất cả" để xem lại toàn bộ.
- Nút 3D cho xoay hình bằng chuột.
- Trục PC1, PC2 (PC3) là các trục PCA, không có đơn vị. Chúng chỉ là hướng "nhìn" đẹp nhất.

**Lời thoại gợi ý.** "Mỗi tin được biến thành một dãy số từ ba nguồn: công cụ, khái niệm và nội dung câu chữ (mô hình e5). Rồi thuật toán K-Means xếp các tin gần nhau vào cùng cụm. Nhóm em chốt 10 cụm. Thầy có thể bấm từng cụm để thấy cụm đó nằm ở đâu và đặc trưng bởi công cụ gì. Các chấm chồng lên nhau một phần, vì nghề IT thật sự giao nhau: một người Web cũng dùng SQL, một BA cũng dùng Jira như Tester."

**Câu hỏi dự kiến:**
- *Sao các cụm chồng lên nhau, vậy có phải chia sai?* Hình chỉ giữ khoảng 12% thông tin (3 trục PCA giữ 12% phương sai). Cụm thật được tính trên 60 chiều, nén từ khoảng 1.600 cột. Ép xuống 2–3 trục để vẽ thì bị chồng, giống bóng hai người đứng trước sau trùng nhau trên tường. Độ tốt của cụm được đo bằng số ở slide 14, không đo bằng mắt trên hình.
- *Trọng số ba nguồn là bao nhiêu?* Công cụ 0,15, khái niệm 0,15, e5 0,70. e5 nặng hơn vì nó đọc cả câu chữ: tin viết sơ sài, ít tên công cụ vẫn được xếp đúng loại việc.
- *Vì sao 9 tin không có trong hình?* 9 tin không có kỹ năng kỹ thuật nào nên không đưa vào phân cụm (3.709/3.718).

**Điểm yếu nói trước.** Hình là minh họa, không phải bằng chứng. Bằng chứng nằm ở slide 13–14.

### Slide 12. Bảng hồ sơ 10 cụm

**Slide nói gì.** Mỗi cụm có bao nhiêu tin, nghề nào chiếm đa số, công cụ đặc trưng, số công cụ mỗi tin và lương trung vị.

**Đọc bảng:**
- "Nghề đa số 73%": 73% tin trong cụm thuộc nghề đó (gán bằng luật).
- "Công cụ đặc trưng (lift)": công cụ xuất hiện trong cụm nhiều hơn hẳn so với toàn thị trường. Đây không phải công cụ phổ biến nhất.
- Tên cụm được đặt tự động theo luật:
  - "Ít công cụ" nếu trung vị ≤ 1 công cụ/tin.
  - "Hỗn hợp" nếu nghề đông nhất dưới 40%.
  - Còn lại lấy tên nghề chiếm đa số.
- Lương là trung vị lương công bố. Chỉ ghi khi cụm có ≥ 30 tin có lương.

**Lời thoại gợi ý.** "Cụm DevOps/Cloud đòi nhiều công cụ nhất, trung vị 14 công cụ mỗi tin, với argocd, helm, terraform, và lương trung vị 30 triệu. Cụm hạ tầng (C1) và cụm văn phòng (C5, word, excel) trả thấp nhất, 15–16 triệu. Có 3 cụm 'Hỗn hợp', nghĩa là không nghề nào chiếm quá 40%: đó là các tin đa năng."

**Câu hỏi dự kiến:**
- *C0 "Hỗn hợp" mà lương cao nhất (31,8 triệu)?* C0 gom tin đòi nền rộng (aws, git, java, sql) ở nhiều nghề, thường là tin cấp Middle trở lên đòi làm được nhiều việc. "Hỗn hợp" nói về nghề, không nói về trình độ.
- *C8 "Ít công cụ" là nghề gì?* Không phải một nghề. Đây là các tin viết JD ngắn, gần như không nêu công cụ: thiết kế, mobile, BA viết sơ sài. Máy gom chúng lại vì cùng "ít thông tin". Nhóm em đặt tên rõ để không ai hiểu nhầm là nghề mới.
- *Lift là gì?* Xem Phần 1. Ví dụ: argocd ít gặp trên toàn thị trường nhưng gặp nhiều trong C9, nên lift cao.

**Điểm yếu nói trước.** Một cụm (C8) phản ánh cách viết tin hơn là loại việc.

### Slide 13. Cụm so với nhóm nghề gán bằng luật

**Slide nói gì.** Đặt 10 cụm (do máy tìm) cạnh 12 nhóm nghề (do luật gán) để xem chỗ nào khớp, chỗ nào nội dung tin cho góc nhìn khác.

**Đọc heatmap.** Mỗi hàng là một cụm, mỗi cột là một nghề. Ô càng đậm thì càng nhiều tin của cụm đó thuộc nghề đó. Rê chuột vào ô để xem số tin.

**Lời thoại gợi ý.** "Có ba phát hiện:
1. Data/AI tách làm hai: nhóm học sâu (pytorch, tensorflow, langchain) và nhóm phân tích BI (tableau, power_bi, sql). Hai việc khác nhau nhưng luật gom chung một nghề.
2. Web tách theo stack: cụm Java/Spring gần như thuần Web.
3. Luật xếp 'IT Manager' vào Bridge, nhưng nội dung JD nói về windows server, mạng, phần cứng nên rơi vào cụm hạ tầng. Ở doanh nghiệp Việt, 'Trưởng phòng CNTT' chủ yếu là quản lý hạ tầng."

**Câu hỏi dự kiến:**
- *NMI có e5 là 0,32, bỏ e5 là 0,47. Sao không bỏ e5 cho cao hơn?* NMI cao nghĩa là cụm giống nhãn luật hơn. Mục tiêu SD3 là tìm góc nhìn **khác** nhãn luật. Nếu cụm giống hệt nhãn thì phân cụm không cho thêm gì. e5 làm cụm theo nội dung thật của công việc, nhờ đó mới thấy hai kiểu Data/AI và IT Manager.
- *Có bao nhiêu tin "có vẻ gán sai"?* 13 tin có nghề khác nghề đa số của cụm và nằm gần tâm cụm. Kiểm tay thì 6 tin là IT Manager, đúng như giải thích ở trên.
- *Vậy luật gán nghề sai à?* Không hẳn. Luật đọc chức danh, cụm đọc nội dung. Hai cách bổ sung cho nhau; cụm không thay nhãn nghề.

**Điểm yếu nói trước.** Ranh giới nghề IT chồng lấn, nên không có cách chia nào khớp 100%.

### Slide 14. Chất lượng phân cụm

**Slide nói gì.** Cụm ổn định khi chạy lại, nhưng ranh giới giữa các cụm mờ ở mọi số cụm k.

**Đọc biểu đồ:**
- **Biểu đồ trái:** quét k từ 2 đến 20, silhouette chỉ dao động 0,075–0,10. Không có k nào làm các cụm tách rõ hẳn.
- **Biểu đồ phải:** chạy lại K-Means với 4 seed khác (43–46) rồi so với seed 42. ARI lần lượt 0,79 / 0,78 / 0,79 / 0,94, trung bình **0,826**, đạt ngưỡng 0,8.
- Cụm nhỏ nhất chiếm 4,3% số tin (ngưỡng ≥ 1%). Không cụm nào chỉ gom tin theo "nhiều hay ít kỹ năng".

**Lời thoại gợi ý.** "Câu hỏi đầu tiên với phân cụm là 'chạy lại có ra như cũ không'. Đổi điểm xuất phát ngẫu nhiên 4 lần, kết quả giống lần đầu trung bình 83%, đạt ngưỡng 80% đã đặt trước. Silhouette thấp, khoảng 0,08, nhưng thấp ở **mọi** k từ 2 đến 20. Như vậy ranh giới mờ là tính chất của dữ liệu nghề IT, không phải do nhóm chọn k sai."

**Câu hỏi dự kiến:**
- *Silhouette 0,075 có quá thấp không?* Thấp, và nhóm em không giấu: chỉ báo cáo, không dùng làm cổng nghiệm thu (chốt 22/11). Lý do: dữ liệu văn bản nhiều chiều và nghề giao nhau. Bằng chứng là quét k = 2…20 không có k nào vượt 0,10.
- *Vì sao chọn k = 10?* k được chốt từ trước theo mục tiêu diễn giải: đủ chi tiết để tách các nghề chính, không quá vụn. Vì silhouette gần như phẳng theo k, đổi k không làm cụm tốt hơn rõ rệt.
- *Seed là gì, vì sao phải thử nhiều seed?* K-Means bắt đầu từ điểm ngẫu nhiên. Nếu đổi seed mà ra cụm khác hẳn thì kết luận không đáng tin. Nhóm còn tăng `n_init` lên 150 (thử 150 điểm xuất phát mỗi lần) để kết quả ổn định. Với 50 thì ARI chỉ 0,79.
- *Sao seed 46 tới 0,94 còn các seed khác 0,78–0,79?* Silhouette thấp cho thấy nhiều tin nằm giữa hai cụm. Các tin này đổi cụm tùy điểm xuất phát, nên ARI dao động. Nhóm em chưa đo riêng từng cụm đổi bao nhiêu; nếu thầy hỏi sâu thì nói đây là việc có thể đo thêm.

**Điểm yếu nói trước.** Silhouette thấp. Trả lời bằng biểu đồ quét k như trên.

### Slide 15. Tin "khác hoặc mới"

**Slide nói gì.** 233 tin (6,3%) có hồ sơ bất thường. Loại "khác", tức tin có lý do cụ thể, là đáng tin. Loại "mới" và "chưa rõ" không đủ để kết luận có nghề mới.

**Đọc con số:**
- Isolation Forest gắn cờ 104 tin, GLOSH 112 tin, 3 tin cả hai cùng bắt. Thêm 20 tin do **luật** gắn cờ: tin không rõ cấp bậc nhưng có lý do cụ thể, chẳng hạn lương ngoại lai. Cộng lại: 101 + 109 + 3 + 20 = 233.
- Ba loại:
  - **khác (97 tin):** có mã lý do đọc được. Kiểm tay 8/8 đúng.
  - **mới (102 tin):** GLOSH thấy hồ sơ kỹ năng ít gặp, còn lương, kinh nghiệm, số công cụ đều bình thường so với cùng cấp. Kiểm tay chỉ 2/9 đúng là ngách thật (quant rủi ro, Odoo). Còn lại là JD viết chung chung.
  - **chưa rõ (34 tin):** phần còn lại. Xem **Phần 3**.

**Lời thoại gợi ý.** "Nhóm em dùng hai thuật toán tìm điểm lạ: Isolation Forest nhìn lương, kinh nghiệm, số công cụ; GLOSH nhìn hồ sơ kỹ năng. Mỗi tin lạ được gắn mã lý do. Ví dụ tin DevOps đòi 32 công cụ, hay tin fresher backend đòi 25 công cụ. Loại có mã lý do kiểm tay đúng 8/8 nên dùng được. Loại 'mới' chỉ đúng 2/9, đa số là tin viết sơ sài, nên nhóm em **không** kết luận có nghề mới trong kỳ này."

**Câu hỏi dự kiến.** Xem Phần 3.

### Slide 16. Mô hình lương

**Slide nói gì.** Random Forest đoán lương tốt hơn cách đoán đơn giản 16,7%. Kinh nghiệm và cấp bậc quyết định phần lớn lương.

**Đọc con số:**
- **Sai số:** MAE 6,1 triệu so với baseline 7,3 triệu, tức (7,33 − 6,10) / 7,33 = 16,7% tốt hơn. Cổng nghiệm thu là ≥ 10%.
- **Độ giải thích:** R² 0,56 trên tập thi; kiểm chéo 5 lần cho 0,59 ± 0,03. Kết quả ổn định giữa các lần chia.
- **Dữ liệu học:** 1.458 tin, gồm 1.622 tin có lương trừ 20 tin thỏa thuận có ghi số, 83 tin lương nghi vấn và 61 tin lương lệch cấp quá 3 lần. Trong đó 1.159 tin để học, 299 tin để thi. 869 công ty, không công ty nào nằm cả hai phía.
- **Ước lương cho tin thỏa thuận:** 2.085 tin "thỏa thuận" được đoán lương kèm khoảng P10–P90, gắn nhãn "ước tính" và không trộn với lương thật.
- **Tỷ trọng SHAP:**

  | Nhóm yếu tố | Tỷ trọng |
  |---|---|
  | Kinh nghiệm | 42,1% |
  | Cấp bậc | 24,7% |
  | Khái niệm | 12,2% |
  | Nguồn tin | 7,8% |
  | Công cụ | 5,8% |
  | Nghề | 5,1% |
  | Tỉnh | 2,1% |

**Lời thoại gợi ý.** "Baseline đơn giản nhất là lấy lương giữa của cùng cấp, cùng nghề. Mô hình phải thắng nó ít nhất 10%, và thắng 16,7%. Để không ăn gian, nhóm chia dữ liệu theo công ty: công ty nào ở phần học thì không có ở phần thi. Khi chia điểm cho từng yếu tố bằng SHAP, kinh nghiệm và cấp bậc chiếm 67%; các công cụ cộng lại chỉ khoảng 6%."

**Câu hỏi dự kiến:**
- *R² 0,56 có thấp không?* Với lương từ tin tuyển dụng thì đây là mức hợp lý. Tin không ghi quy mô công ty, ngân sách, kỹ năng thật của ứng viên. Chỉ 44% tin công bố lương, và cấp cao hay giấu lương (MNAR). R² nhóm em chỉ báo cáo, cổng chính là thắng baseline.
- *Sao "Nguồn tin" (sàn đăng) lại ảnh hưởng lương 7,8%?* Mỗi sàn có tập khách khác nhau. Trung vị lương công bố theo sàn: ITviec 38,7 triệu, VietnamWorks 30, TopCV 22,5, TopDev và CareerViet 20, Glints 17,5, Vieclam24h 15,75, JobsGO 15,5. Nhóm em đưa sàn vào làm biến kiểm soát, để phần chênh này không bị tính nhầm cho kỹ năng.
- *Ước tính lương cho 2.085 tin thỏa thuận có tin được không?* Chỉ để tham khảo. 1.274 tin có cảnh báo, vì thuộc nhóm mô hình sai nhiều: cấp không rõ, Senior, DevOps/Cloud, Security, IoT, tin từ ITviec và VietnamWorks. Khoảng P10–P90 rộng: độ rộng trung vị khoảng 20 triệu. Nhóm không trộn số ước tính vào thống kê lương ở SD1.
- *Slide 5 ghi 2.105 tin thỏa thuận, sao ở đây 2.085?* 2.105 là số tin thỏa thuận. 20 tin trong đó vẫn ghi số lương trong nội dung, nên bỏ khỏi phần ước tính để tránh mâu thuẫn.

**Điểm yếu nói trước.** Chỉ 44% tin có lương. Mô hình học trên phần có lương, phần thỏa thuận có thể khác.

### Slide 17. Kỹ năng đáng tiền

**Slide nói gì.** Mỗi công cụ riêng lẻ chỉ gắn với thêm dưới 0,6 triệu/tháng. Lương đi theo kinh nghiệm và cấp; kỹ năng là "vé vào cửa".

**Đọc biểu đồ:**
- Mỗi thanh là số triệu đồng/tháng gắn với việc tin có công cụ đó, kèm khoảng tin cậy 95% (bootstrap 200 lần). n là số tin có lương chứa công cụ đó.
- Công thức: giá trị = 21,3 triệu (lương nền của mô hình) × (e^φ − 1). Ở đây φ là điểm SHAP trung bình của công cụ trên các tin có nó. Ví dụ kubernetes có φ = 0,021, nên 21,3 × (e^0,021 − 1) ≈ 0,46 triệu.
- Chỉ định giá công cụ có ≥ 30 tin có lương: 77 công cụ.

**Lời thoại gợi ý.** "Cao nhất là cisco 0,55 triệu, kubernetes 0,46, cpp 0,42, docker 0,33. So với chênh lương giữa hai cấp liền nhau thì rất nhỏ: Junior lên Middle +7 triệu, Middle lên Senior +15 triệu. Thông điệp cho sinh viên: một công cụ thêm không làm lương nhảy vọt; kinh nghiệm thật mới làm."

**Câu hỏi dự kiến:**
- *Vậy học Kubernetes thì lương tăng 0,46 triệu?* Không. Đây là **liên hệ thống kê** trên tin công bố lương, **không phải nhân quả**. Mô hình chỉ thấy tin có Kubernetes đi cùng mức lương hơi cao hơn, sau khi đã tính kinh nghiệm và cấp. Nó không chứng minh việc học Kubernetes làm lương tăng.
- *"claude", "cursor" là gì?* Công cụ lập trình có AI hỗ trợ. Chúng xuất hiện trong JD từ 2026, n = 73 và 48 tin.
- *Sao giá trị nhỏ vậy mà vẫn có ý nghĩa?* Khoảng tin cậy không chứa 0. Ví dụ docker 0,28–0,37, nên liên hệ là dương và ổn định, chỉ là nhỏ.

**Điểm yếu nói trước.** SHAP chia điểm giữa các yếu tố tương quan. Cấp và kinh nghiệm đi cùng nhau nên chia điểm cho nhau.

### Slide 18. Lộ trình cho người mới (ví dụ nghề Web)

**Slide nói gì.** Từ 192 tin Web cho Intern/Fresher và Junior, xếp những gì nên học trước, học theo gói nào, và gì để sau.

**Đọc slide:**
- **Bước 1, nền:** javascript (40% tin đòi), git, sql, java, python.
- **Bước 2, theo gói:** thứ tự lấy từ luật kết hợp SD2. Ví dụ học docker trước rồi mới tới kubernetes, vì tin đòi kubernetes hầu như cũng đòi docker.
- **Chưa nên đầu tư sớm:** graphql, jenkins… phổ biến ở Senior/Lead gấp 3–14 lần so với tin người mới.
- **Điểm xếp hạng** = nhu cầu × (1 + giá trị SHAP chuẩn hóa). Kỹ năng vừa được nhiều tin đòi vừa gắn với lương cao thì lên đầu.
- **Bảng 8 nghề:** cov@10 của lộ trình so với baseline "top 10 công cụ toàn thị trường". Cả 8 nghề đều hơn baseline. "Ổn định" hay "tham khảo" theo phép chia 80/20:

  | Nghề | Lệch 80/20 | Đánh giá |
  |---|---|---|
  | Bridge | 4,5 điểm | ổn định |
  | Data/AI | 4,9 điểm | ổn định |
  | Tester | 8,5 điểm | ổn định |
  | Web | 3,9 điểm | ổn định |
  | Design | 11,6 điểm | tham khảo |
  | DevOps/Cloud | 10,1 điểm | tham khảo |
  | Infra/Support | 10,8 điểm | tham khảo |
  | Security | 11,0 điểm | tham khảo |

**Lời thoại gợi ý.** "Một lộ trình phải trả lời được: học gì trước, theo thứ tự nào, cái gì chưa cần. Mỗi kỹ năng trong lộ trình truy được về ba nguồn: bao nhiêu tin đòi, luật gói SD2 và giá trị SHAP SD4."

**Câu hỏi dự kiến:**
- *Web cov@10 chỉ 0,06, có quá thấp không?* Thấp vì tin Web đòi rất đa dạng (React, Angular, Java, .NET, PHP…). 10 công cụ không thể đáp ứng ≥ 70% yêu cầu của phần lớn tin. Vì thế nhóm em đề xuất học **theo gói** chứ không theo một danh sách chung. Dù vậy lộ trình vẫn gấp khoảng 3,7 lần baseline (0,06 so với 0,016).
- *Infra/Support 193 tin mà vẫn "tham khảo"?* Tiêu chí là độ lệch giữa phần tính và phần kiểm (10,8 điểm > 10), không phải số tin. Tin Infra rất khác nhau giữa các công ty (mạng, máy chủ, hỗ trợ người dùng).
- *Kỹ năng mềm thì sao?* Xếp riêng, không trộn với công cụ. Với Web: phối hợp 45%, chủ động 43%, ham học 38%.

**Điểm yếu nói trước.** 4/8 nghề chỉ "tham khảo" vì ít tin người mới.

### Slide 19. Đánh giá và nghiệm thu

**Slide nói gì.** Mọi cổng nghiệm thu đặt trước đều đạt. Những chỉ số chưa tốt được ghi rõ lý do, không giấu.

**Lời thoại gợi ý.** "Cổng nghiệm thu là ngưỡng đặt **trước** khi xem kết quả, chốt ngày 22/11:
- SD3: ARI ≥ 0,8.
- SD4: thắng baseline ≥ 10%.
- SD5: lộ trình hơn baseline.
- Sanity S-01 đến S-06: các kiểm tra hợp lý cơ bản, ví dụ lương tăng theo cấp, tổng mỗi bảng đúng 3.718.

Tất cả đều đạt. Bên phải là những điểm còn yếu và vì sao."

**Câu hỏi dự kiến:**
- *Ngưỡng do ai đặt, có đặt sau khi thấy kết quả không?* Ngưỡng lấy theo tài liệu mục tiêu (`docs/target/`), chốt ngày 22/11. Silhouette và R² được chuyển sang "chỉ báo cáo", có ghi lý do trong nhật ký L-60.
- *"Chạy lại ra cùng số" nghĩa là gì?* Cố định seed 42 và ghi mã băm (sha256) của dữ liệu đầu vào. Ai chạy lại trên cùng dữ liệu cũng ra cùng số.

### Slide 20. Câu trả lời cho năm câu hỏi

**Slide nói gì.** Mỗi mục tiêu SD1–SD5 có một câu trả lời ngắn.

**Lời thoại gợi ý.** Đọc từng dòng, nhấn số chính:
- **SD1:** Hà Nội và TP.HCM chiếm 89% số tin; người mới chiếm 29%, lương 13,5 triệu so với 26,5 triệu ở Middle trở lên.
- **SD2:** kỹ năng đi theo gói, như java ⇒ spring_boot.
- **SD3:** 10 nhóm việc ổn định nhưng ranh giới mờ; không thấy nghề mới.
- **SD4:** kinh nghiệm và cấp chiếm 67%, mỗi kỹ năng dưới 0,6 triệu.
- **SD5:** lộ trình cho 8 nghề, 4 nghề ổn định.

**Câu hỏi dự kiến:**
- *"Không thấy nghề mới" có chắc không?* Chỉ chắc trong phạm vi dữ liệu này: một kỳ 3 tháng, chỉ có phía nhà tuyển dụng. Loại "mới" chỉ đúng 2/9 khi kiểm tay, nên nhóm em không đủ bằng chứng để nói là có.

### Slide 21. Gợi ý cho sinh viên IT

**Slide nói gì.** Ba lời khuyên rút ra từ dữ liệu:
- Học nền chung: SQL, Python, Git, Linux.
- Học theo gói của nghề mình chọn.
- Tích lũy kinh nghiệm thật sớm.

**Lời thoại gợi ý.** Nối mỗi lời khuyên với bằng chứng:
- Nền chung có ở hầu hết các nghề (SD2, SD5).
- Gói kỹ năng là từ luật kết hợp (SD2).
- Kinh nghiệm chiếm 42% trong mô hình lương, còn một kỹ năng lẻ dưới 0,6 triệu (SD4).

**Câu hỏi dự kiến:**
- *Hướng phát triển tiếp?*
  - Thu thập thêm các kỳ sau để so theo thời gian.
  - Đo lại độ đúng của nhóm nghề trên một mẫu độc lập.
  - Lấy tỉnh theo nơi làm việc thay vì trụ sở công ty.

---

## Phần 3. Slide 15, phần "chưa rõ": cách báo cáo với thầy

### 3.1. "Chưa rõ" là gì

Mỗi tin bị gắn cờ được xếp vào 1 trong 3 loại, theo luật trong `mining/anomaly.py`, hàm `classify_kind`:

| Loại | Điều kiện | Số tin |
|---|---|---|
| khác | Có **mã lý do cụ thể**: quá nhiều công cụ, fresher quá nhiều công cụ, lương quá thấp hoặc quá cao so với cấp, lương ngoại lai | 97 |
| mới | GLOSH gắn cờ (hồ sơ kỹ năng ít gặp), **và** kinh nghiệm, lương, số công cụ đều nằm trong khoảng P5–P95 của cùng cấp, tức "mọi thứ bình thường, chỉ bộ kỹ năng lạ" | 102 |
| **chưa rõ** | Bị gắn cờ nhưng **không đủ điều kiện** cho hai loại trên | 34 |

34 tin "chưa rõ" gồm:
- **29 tin** do Isolation Forest gắn cờ, nhưng không tin nào vượt ngưỡng của mã lý do nào (mã chung `ISOLATION_GENERIC`).
- **5 tin** do GLOSH gắn cờ, nhưng có ít nhất một trong ba trường (kinh nghiệm, lương, số công cụ) nằm ngoài P5–P95 của cấp. Vì vậy không xếp được vào "mới" (mới đòi mọi thứ bình thường), cũng không vào "khác" (không vượt ngưỡng mã).

### 3.2. Phát hiện chính: "chưa rõ" là nhóm giáp ngưỡng

Đo lại trên `job_anomalies.parquet` (lệnh chỉ đọc, 24/11) với 29 tin Isolation Forest:

| Cấp | Số tin | Số công cụ | Ngưỡng mã lý do |
|---|---|---|---|
| Intern/Fresher | 14 | 11–17 | `FRESHER_TOO_MANY_SKILLS`: > 17 |
| Senior | 4 | 25–27 | `TOO_MANY_SKILLS`: > 27 |
| Lead/Manager | 11 | 7–27 | `TOO_MANY_SKILLS`: > 27; lương > 3 lần trung vị cấp |

- **23/29 tin** có số công cụ nằm trong **top 10%** của chính cấp đó, và 28/29 nằm trong top 20%.
- Tin còn lại ("Java Tech Lead, offer upto 70tr", 7 công cụ) có lương gấp **2,33 lần** trung vị cấp, sát ngưỡng 3 lần.
- Hai tin fresher có lương gấp 2,92 và 3,00 lần trung vị cấp. Ngưỡng là "lớn hơn 3", nên chưa vượt.

**Giải thích:** Isolation Forest nhìn **tổ hợp** nhiều yếu tố cùng lúc. Một fresher đòi 16 công cụ **và** lương khá cao là tổ hợp hiếm, dù từng yếu tố chưa vượt ngưỡng riêng. Luật mã lý do thì xét từng yếu tố một. Vì vậy các tin này "lạ" theo máy nhưng chưa có mã để gọi tên.

### 3.3. Kiểm tay

Mẫu kiểm tay là 20 tin chọn ngẫu nhiên phân tầng (seed 42), trong đó 3 tin "chưa rõ". File: `data/preprocessing/review/mining_hand_check_2211.csv`.

| Tin | Đánh giá |
|---|---|
| Kỹ thuật viên IT phần mềm, KCN Long Đức, 15 công cụ, fresher | Đúng là lạ: fresher đòi nhiều |
| AI Engineer (All Level), 16 công cụ | Đúng là lạ: ghi "all level" nhưng đòi nhiều |
| Head of AI & Data, 11 công cụ, 10 năm kinh nghiệm | Không lạ: hồ sơ bình thường của cấp cao |

Kết quả 2/3. **Mẫu chỉ 3 tin nên không đủ để kết luận tỷ lệ đúng.** Nói thẳng điều này với thầy.

### 3.4. Câu trả lời mẫu, khoảng 30 giây

> "Chưa rõ là 34 tin máy thấy lạ nhưng không gán được lý do cụ thể. Nhóm em tách riêng thay vì ép vào 'khác' hay 'mới', để không gán nhãn sai. Khi xem lại, gần hết là tin **giáp ngưỡng**: 23 trên 29 tin đòi số công cụ thuộc top 10% của cấp mình, chẳng hạn fresher đòi 15–17 công cụ trong khi ngưỡng là trên 17. Isolation Forest bắt được vì nó nhìn tổ hợp nhiều yếu tố, còn luật mã lý do xét từng yếu tố. Nhóm em **không** dùng nhóm này để kết luận. Kết luận ở slide chỉ dựa vào loại 'khác', loại đã kiểm tay đúng 8/8."

### 3.5. Câu hỏi tiếp theo có thể gặp

**Vì sao không hạ ngưỡng cho "chưa rõ" thành "khác"?**
Ngưỡng lấy theo phân vị của dữ liệu (P99 số công cụ toàn bộ, P95 cho người mới), không đặt số tùy ý. Hạ ngưỡng để "đẹp số" là chỉnh ngưỡng theo kết quả. Nhóm em giữ ngưỡng và báo cáo nhóm giáp ngưỡng riêng.

**Vì sao "mới" chỉ đúng 2/9?**
GLOSH bắt hồ sơ kỹ năng ít gặp. Nhưng nhiều tin "ít gặp" chỉ vì viết sơ sài, kiểu "Nhân viên IT" nêu 2 công cụ, chứ không phải nghề mới. Hai tin đúng là ngách thật: quant rủi ro ngân hàng và lập trình Odoo. Vì vậy nhóm em không kết luận có nghề mới.

**Contamination 3% mà sao có 6,3%?**
3% chỉ áp cho Isolation Forest, trên tin biết cấp: 104 tin. Tổng 233 tin là hợp của ba cách bắt:
- Isolation Forest: 104 tin.
- GLOSH: 112 tin, trùng 3 tin với Isolation Forest.
- Luật: 20 tin chưa rõ cấp có lý do cụ thể.

274 tin không rõ cấp không đưa vào Isolation Forest. Lý do: trước đây Isolation Forest bắt chủ yếu "tin thiếu cấp" chứ không phải tin lạ thật (quyết định 1.B, 20/11).

**Nếu có thêm thời gian, nhóm sẽ làm gì?**
- Kiểm tay đủ 34 tin "chưa rõ". Số tin ít, làm được trong một buổi.
- Thêm mã lý do "giáp ngưỡng", ví dụ số công cụ trong top 10% của cấp, để nhóm này có tên.

---

## Phần 4. Bảng tra nhanh con số

### Slide 11–15 (SD3)

| Slide | Con số | Ý nghĩa | Nguồn (`mining_metrics.json`) |
|---|---|---|---|
| 11 | 3.709 / 3.718 | Tin được phân cụm (9 tin không có kỹ năng kỹ thuật) | `clustering.n_clustered` |
| 11 | 0,15 / 0,15 / 0,70 | Trọng số công cụ / khái niệm / e5 | `clustering.vector_space.block_weights` |
| 11 | 12% | Phần thông tin giữ lại khi vẽ 3 trục PCA | `clustering.pca_cumulative_variance_3d` |
| 12 | 10 cụm, 158–728 tin | Hồ sơ cụm | `clustering.clusters` |
| 13 | NMI 0,32 (bỏ e5 0,47) | Độ giống cụm ↔ nghề | `clustering.nmi_vs_job_family`, `without_e5` |
| 13 | 13 tin, 6 IT Manager | Tin "có vẻ gán sai" | `clustering.n_family_mismatch`, `sd3_mismatch_hand_check.csv` |
| 14 | Silhouette 0,075 (k = 2…20: 0,075–0,10) | Độ tách cụm | `clustering.silhouette`, `k_scan` |
| 14 | ARI 0,826 (0,791 / 0,779 / 0,794 / 0,939) | Ổn định: seed 42 so với 43–46 | `clustering.stability` |
| 14 | 4,3% | Cụm nhỏ nhất | `clustering.min_cluster_share` |
| 15 | 233 = 101 + 109 + 3 + 20 | Chỉ IF + chỉ GLOSH + cả hai + luật | `anomaly.n_flagged`, `n_isolation_forest`, `n_glosh`, `n_both`, `n_rule_unknown_level` |
| 15 | 97 / 102 / 34 | Khác / mới / chưa rõ | `anomaly.kind_counts` |
| 15 | 27 và 17 | Ngưỡng số công cụ (P99 toàn bộ, P95 người mới) | `anomaly.thresholds_used` |

### Slide 16–18 (SD4, SD5)

| Slide | Con số | Ý nghĩa | Nguồn (`mining_metrics.json`) |
|---|---|---|---|
| 16 | MAE 6,105 so với 7,332; +16,7% | Sai số mô hình so với baseline | `salary.holdout`, `baseline_level_family`, `mae_gain_vs_baseline` |
| 16 | R² 0,557, CV 0,589 ± 0,029 | Độ giải thích | `salary.holdout.r2_log`, `cv_r2_mean`, `cv_r2_std` |
| 16 | 1.458 = 1.159 + 299; 869 công ty, chồng 0 | Dữ liệu học và thi | `salary.subset`, `n_train`, `n_test`, `n_companies_overlap` |
| 16 | 2.085 ước tính, 1.274 có cảnh báo | Lương đoán cho tin thỏa thuận | `salary.estimates` |
| 17 | 21,3 triệu; 77 kỹ năng; bootstrap 200 | Công thức giá trị kỹ năng | `salary.shap` |
| 18 | cov@10 và lệch 80/20 từng nghề | Lộ trình | `recommend.families` |

Tóm lại, file này có 4 phần: từ điển thuật ngữ, giải thích từng slide 11–21, chuẩn bị riêng cho "chưa rõ" ở slide 15, và bảng tra số. Số ở slide 14, 15, 16 đã được sửa ngày 24/11 để khớp với kết quả chạy.
