# Giải thích slide 11–21 (SD3, SD4, SD5, đánh giá, kết luận)

Tài liệu cho người trình bày slide 11–21 của `final_slides.html`, viết để người không học IT cũng hiểu được. Mọi con số lấy từ lần chạy thật trên 3.718 tin IT, tháng 9–11/2026, nguồn `mining/artifacts/mining_metrics.json`: SD3 (slide 11–15) chạy lại ngày 24–25/11 theo 7 nhóm nghề, không dùng e5; phần còn lại là lần chạy 22/11. Hai lần cùng đầu vào (sha256 khớp). Câu hỏi của thầy trong file này là **câu hỏi dự kiến**, không phải câu thầy đã hỏi.

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
| e5 (multilingual-e5-base) | Một mô hình ngôn ngữ có sẵn, đọc đoạn mô tả và yêu cầu của tin rồi trả về 768 con số, giống "dấu vân tay nội dung". Hai tin viết về cùng loại việc thì dấu vân tay gần nhau, kể cả khi dùng chữ khác nhau. Chỉ dùng để biến chữ thành số, không dùng để gán nghề | **Không dùng cho phân cụm SD3 từ 24/11**: e5 gom tin theo ngôn ngữ viết JD (tiếng Anh hay tiếng Việt) |
| SVD, PCA | Kỹ thuật nén nhiều cột thành ít cột mà vẫn giữ phần thông tin chính, giống chụp ảnh 2D của một vật 3D | SVD nén 829 cột (282 công cụ + 547 khái niệm) còn 60 cột để phân cụm. PCA nén còn 2–3 trục để vẽ |

### Phân cụm và đo chất lượng cụm (SD3)

| Thuật ngữ | Giải thích đời thường | Ví dụ trong đề tài |
|---|---|---|
| 7 nhóm nghề (`job_group`) | Software, QA/QC, Data & AI, Hạ tầng, Security, Product & Business, Support & Consulting. Gán bằng luật đọc chức danh, không dùng AI | Tin không thuộc nhóm nào vào nhóm "Khác" |
| Cụm con, vai trò con | Cụm máy tìm **trong** một nhóm, đặt tên theo vai trò con (Backend, Data Engineer…) khi ≥ 30% tin của cụm có tiêu đề khớp | 31 cụm con |
| Mục "Khác (JD ít thông tin)" | Tin của một nhóm ghi dưới 2 công cụ: không đủ thông tin để phân cụm nên giữ trong nhóm, ở mục riêng | 744 tin |
| Phân cụm (clustering) | Để máy tự xếp các tin giống nhau vào chung nhóm, **không cho trước đáp án**. Giống xếp quần áo trong tủ mà không có nhãn | |
| K-Means, k | K-Means là một cách phân cụm: chọn k "tâm", mỗi tin về tâm gần nhất, rồi dời tâm vào giữa nhóm và lặp lại. k là số cụm muốn có | k của mỗi nhóm = số vai trò con liệt kê trước (tổng 31) |
| seed, `n_init` | seed là "hạt giống ngẫu nhiên" quyết định điểm xuất phát. `n_init` = 150 nghĩa là thử 150 điểm xuất phát rồi giữ kết quả tốt nhất | |
| Silhouette | Điểm từ −1 đến 1. Gần 1 là các cụm tách nhau rõ, gần 0 là ranh giới giữa các cụm mờ | Ở đây là 0,07 (chỉ báo cáo) |
| ARI | Độ giống nhau giữa hai cách chia nhóm: 1 là giống hệt, 0 là giống như chia ngẫu nhiên | Dùng để kiểm cụm có ổn định không khi đổi seed |
| kNN (độ đúng) | Lấy 15 tin gần nhất của một tin, đoán nhãn theo đa số rồi xem đúng bao nhiêu. Cao nghĩa là các nhãn tách nhau rõ trong không gian | Dùng để so các bộ trọng số ở slide 14 |
| Lift | Kỹ năng xuất hiện trong cụm nhiều gấp mấy lần so với cả nhóm | Lift 5 nghĩa là gấp 5 lần, kỹ năng "đặc trưng" của cụm |

### Phát hiện tin bất thường (SD3)

| Thuật ngữ | Giải thích đời thường | Ví dụ trong đề tài |
|---|---|---|
| Isolation Forest (IF) | Thuật toán tìm điểm lạ. Nó cắt ngẫu nhiên dữ liệu nhiều lần, tin nào bị tách riêng ra sau ít nhát cắt thì là tin lạ, giống người đứng lẻ loi giữa đám đông. Ở đây nhìn cùng lúc: kinh nghiệm, lương, lương so với cấp, số công cụ, cấp | |
| Contamination 3% | Tham số bảo IF đánh dấu khoảng 3% tin lạ nhất trong số tin biết cấp | |
| HDBSCAN, GLOSH | HDBSCAN tìm các vùng dày đặc tin. GLOSH chấm điểm tin nào nằm ngoài rìa vùng dày của nó, tức là có hồ sơ kỹ năng ít gặp | |
| Phân vị P95, P99 | P95 là mức mà 95% tin nằm dưới | P99 số công cụ là 27, nghĩa là chỉ 1% tin đòi hơn 27 công cụ |
| Luật chốt nghề mới | Điều kiện đặt trước để gọi một tiêu đề là nghề mới: chưa có trong danh sách vai trò, ≥ 3 tin từ ≥ 2 công ty, nội dung xa mọi cụm, có ≥ 2 công cụ riêng | Kỳ này: 0 nghề mới, 2 nghề lai |
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

### Slide 11. "3.718 tin: 7 nhóm nghề, 31 cụm con và nhóm Khác"

**Slide nói gì.** Mỗi tin được xếp vào 1 trong 7 nhóm nghề bằng luật. Trong từng nhóm, máy tự chia nhỏ theo nội dung tin thành cụm con. Không tin nào bị bỏ.

**Đọc biểu đồ:**
- Mỗi chấm là một tin, màu là nhóm nghề. Nhóm Khác (ngoài 7 nhóm) màu xám.
- Bấm một nhóm thì các tin của nhóm đó tô theo cụm con, có số thứ tự trên hình, và bảng bên phải liệt kê từng cụm con (số tin, lương, công cụ đặc trưng).
- Tin ghi dưới 2 công cụ không có vị trí trên hình vì không đủ thông tin để đặt. Chúng được đếm ở mục "Khác (JD ít thông tin)" của nhóm.
- Trục PC1, PC2 (PC3) là trục PCA, không có đơn vị.

**3.718 tin chia như sau:**

| Phần | Số tin |
|---|---|
| Trong 31 cụm con (7 nhóm, ≥ 2 công cụ) | 2.620 |
| Mục "Khác (JD ít thông tin)" của 7 nhóm | 744 |
| Nhóm Khác (ngoài 7 nhóm) | 354 |

**Câu hỏi dự kiến:**
- *Trước đây là 3.709 tin được phân cụm, sao giờ ít hơn?* Bản cũ đưa mọi tin có ít nhất 1 kỹ năng vào phân cụm. Kết quả là một cụm lớn 728 tin chỉ gom tin "thiếu công cụ", không phải một nghề. Bản mới chỉ phân cụm tin có ≥ 2 công cụ, còn lại vẫn giữ trong nhóm của nó ở mục "Khác". Tổng vẫn đủ 3.718.
- *7 nhóm có phải máy tìm ra không?* Không. 7 nhóm lấy theo cách chia nghề IT phổ biến, gán bằng luật đọc chức danh (DBA vào Hạ tầng, IT Manager vào Product & Business). Máy chỉ tìm **vai trò con trong từng nhóm**.
- *Số cụm mỗi nhóm chọn thế nào?* Bằng số vai trò con nhóm em liệt kê trước khi chạy (Software 6, QA/QC 3, Data & AI 5, Hạ tầng 5, Security 4 nhưng hạ còn 3 vì mỗi cụm cần trung bình ≥ 30 tin, Product & Business 5, Support 4).

**Điểm yếu nói trước.** Hình chỉ giữ khoảng 21% thông tin (3 trục PCA). Độ tốt của cụm đo ở slide 14.

### Slide 12. Cụm con trong từng nhóm

**Slide nói gì.** 8 thẻ (7 nhóm + nhóm Khác). Mỗi thẻ liệt kê cụm con, số tin, lương trung vị, và mục Khác của nhóm.

**Đọc thẻ:**
- Tên cụm là vai trò con khi ≥ 30% tin của cụm có tiêu đề khớp vai trò đó. Nếu hai cụm cùng vai trò thì thêm 2 công cụ đặc trưng để phân biệt (ví dụ "Backend · hibernate/spring" và "Backend · entity_framework/dotnet_core").
- **Chữ cam** ("chưa khớp: html/css", "chưa khớp: cpp/csharp"): cụm máy tìm ra nhưng không khớp vai trò nào. Nhóm em để nguyên, không ép tên.
- Lương chỉ ghi khi cụm có ≥ 30 tin công bố lương.

**Con số chính:**

| | Cụm | Lương trung vị |
|---|---|---|
| Cao nhất | Backend Java/Spring | 30,0 tr |
| | AI GenAI (gemini, claude) | 28,5 tr |
| | DevOps/SRE, Automation Tester | 27,9 tr |
| Thấp nhất | IT Helpdesk (macos, windows) | 13,0 tr |
| | ERP/CRM · kubernetes/mysql | 17,2 tr |
| | Web html/css | 17,5 tr |

**Câu hỏi dự kiến:**
- *Sao Product & Business có tới 244 tin ở mục Khác?* Tin BA, PM thường mô tả bằng lời (phân tích yêu cầu, quản lý tiến độ), ít ghi tên công cụ, nên nhiều tin dưới ngưỡng 2 công cụ.
- *Cụm "chưa khớp: cpp/csharp" là gì?* Tin phần mềm đòi C++/C#, OOP, debug, với tiêu đề rất khác nhau ("Software Developer", "Kỹ sư Automation Software", BrSE, cả game designer). Không vai trò nào chiếm tới 30% cụm, nên giữ tên theo công cụ.
- *Cụm "chưa khớp: html/css" là gì?* Tin web html/css/javascript/php, tiêu đề lẫn Fullstack, Backend, Frontend. Đây là chỗ frontend "lẫn" vào: JD web nhỏ thường đòi cả front lẫn back.

### Slide 13. Vai trò con tìm được so với danh sách

**Slide nói gì.** So vai trò máy tìm được với danh sách vai trò đặt trước.

**Đọc hình:** xanh = vai trò có cụm riêng (×2 là hai cụm); viền xám = vai trò không thành cụm; cam = cụm ngoài danh sách (kèm số tin).

**Phát hiện:**
- **AI hai kiểu:** GenAI/agent (gemini, claude, openai_api, langgraph: 111 tin, 28,5 tr) và học sâu/thị giác máy (onnx, pytorch, cpp: 63 tin).
- **Data Analyst hai kiểu:** bảng tính (excel, google_sheets: 61 tin) và BI (looker, tableau, power_bi: 94 tin, 24,2 tr).
- **Software theo stack:** Java/Spring, .NET, Full-stack Node/Next. Frontend lẫn trong cụm web html/css.
- **Ngoài dự kiến:** cụm "QA Engineer" là QA chất lượng sản xuất (powerpoint, word, autocad), không phải kiểm thử phần mềm; Product & Business có cụm thiết kế đồ họa, video (premiere, illustrator).
- **Không thành cụm:** PO/PM, Scrum Master (viết JD giống BA); SOC, Pentester, Security Consultant (ít tin); Data Scientist, BI Developer (lẫn vào AI và DA); Game, Embedded (ít tin có ≥ 2 công cụ).

**Câu hỏi dự kiến:**
- *Vậy danh sách vai trò sai à?* Không. Danh sách là cách gọi tên nghề; cụm là cách JD thực sự mô tả công việc. Vai trò không thành cụm nghĩa là JD của nó viết giống một vai trò khác, hoặc quá ít tin.
- *Có ý nghĩa gì với sinh viên?* "Data Analyst" hay "AI Engineer" trên tin tuyển dụng là hai hướng học khác nhau. Đọc kỹ công cụ trong JD trước khi ứng tuyển.

### Slide 14. Chất lượng phân cụm

**Slide nói gì.** Cụm con ổn định ở cả 7 nhóm. Trọng số khối được chọn để cụm không bị tách theo ngôn ngữ viết JD.

**Đọc biểu đồ và bảng:**
- **Biểu đồ trái:** ARI giữa nhãn cụm của seed 42 và 4 seed khác (n_init 150), từng nhóm: Software 0,97; QA/QC 1,00; Data & AI 0,97; Hạ tầng 1,00; Security 0,89; Product 0,98; Support 0,95. Ngưỡng 0,8.
- **Bảng phải:** 5 bộ trọng số công cụ / khái niệm / e5. "Tách 7 nhóm" và "Tách vai trò con" là độ đúng kNN (lấy 15 tin gần nhất, đoán nhãn theo đa số). "Cụm ≥ 90% JD tiếng Anh" đếm số cụm gần như chỉ gồm tin tiếng Anh.
- **Thẻ:** ARI trung bình 0,97; cụm nhỏ nhất 7,4% số tin của nhóm nó (cổng ≥ 1%); silhouette 0,07 chỉ báo cáo.

**Chuyện e5 (nên kể, vì cho thấy nhóm kiểm kết quả thật):** bản 22/11 dùng e5 với trọng số 0,70. Khi vẽ bản đồ, tin tách thành hai mảng: một mảng gần như toàn JD tiếng Anh. Kiểm lại có 5 cụm ≥ 90% JD tiếng Anh (Backend aws/typescript, AI azure/aws, BA sql/jira, DevOps github_actions, Automation Tester). e5 đọc câu chữ nên nhạy với ngôn ngữ. Nhóm em thử thêm cách "trừ trung bình ngôn ngữ" (còn 1 cụm lệch) và "chỉ e5" (11 cụm lệch), rồi chọn **bỏ e5**: 0 cụm lệch, tách vai trò con 0,79, ARI thấp nhất 0,89.

**Câu hỏi dự kiến:**
- *Bỏ e5 thì bước tạo vector e5 có thừa không?* Với SD3 thì có. Vector e5 vẫn là đặc trưng của bước Processing, nhưng phân cụm vai trò dùng công cụ và khái niệm vì đây là mã chung cho cả hai ngôn ngữ.
- *Đổi trọng số sau khi thấy kết quả có phải chỉnh số cho đẹp không?* Lý do đổi là một lỗi đo được (cụm theo ngôn ngữ), không phải để tăng chỉ số. Bảng ghi cả các bộ không được chọn. Bộ được chọn có ARI thấp nhất (0,89) **thấp hơn** bộ cũ (0,90).
- *Cổng "cụm nhỏ nhất ≥ 1%" sao tính theo nhóm?* Cụm giờ được tìm trong từng nhóm, nên so với nhóm của nó mới đúng nghĩa. Thay đổi này ghi rõ là làm sau khi xem kết quả (24/11).

**Điểm yếu nói trước.** Security ARI 0,89, thấp nhất vì nhóm chỉ có 116 tin vào cụm.

### Slide 15. Tin "khác hoặc mới"

**Slide nói gì.** Hai phần. (1) Tin lạ: chủ yếu là JD đòi quá nhiều công cụ hoặc lương lệch cấp. (2) Nhóm Khác xét bằng luật chốt nghề mới: không thấy nghề mới.

**Đọc con số, phần tin lạ (M4):**
- 210 tin bị gắn cờ: Isolation Forest 104, GLOSH 86, cả hai 1, luật 21. Cộng: 103 + 85 + 1 + 21 = 210.
- **khác (97 tin):** có mã lý do. Hay gặp nhất: lương thấp bất thường so với cấp (31), fresher đòi quá nhiều công cụ (25), lương ngoại lai (16), đòi quá nhiều công cụ (15). Một tin có thể có nhiều mã. Kiểm tay 8/8 đúng.
- **chưa rõ (37 tin):** xem Phần 3.

**Đọc con số, phần nhóm Khác (354 tin):**

| Kết quả | Số tin |
|---|---|
| Nội dung giống một cụm có sẵn | 216 |
| JD ít thông tin (< 2 công cụ) | 115 |
| Lẻ, xa mọi cụm (tiêu đề chưa đủ tin để xét) | 20 |
| Nghề lai | 3 |
| Nghề mới | 0 |

**Luật chốt nghề mới** (đặt trước khi xem kết quả, code `mining/clustering.py`, hàm `classify_other`). Một tiêu đề trong nhóm Khác được xét theo thứ tự:
1. Tiêu đề chung chung ("Nhân viên IT") → không xét.
2. Khớp một vai trò trong danh sách → đã có.
3. Đếm đúng tiêu đề đó trên **toàn bộ dữ liệu**: dưới 3 tin hoặc dưới 2 công ty → **theo dõi**.
4. ≥ 50% tin của tiêu đề nằm xa mọi cụm và có ≥ 2 công cụ riêng → **nghề mới**.
5. Tin rải ra ≥ 2 nhóm, không nhóm nào ≥ 60%, và có ≥ 2 công cụ riêng → **nghề lai**.
6. Còn lại → **tên gọi khác** của nhóm gần nhất.

**Kết quả:**
- Nghề lai: Engineering Manager (Software + Support), Forward Deployed Engineer (Data & AI + Hạ tầng). Mỗi tiêu đề 3 tin từ 3 công ty.
- Tên gọi khác: Tech Lead, Technical Leader (Software); Data Architect (Data & AI); IT Supervisor (Support).
- Theo dõi: Analytics Engineer (1 tin), blockchain, playable ads, product engineer (2 tin mỗi loại).

**Lời thoại gợi ý.** "Một tiêu đề lạ chưa đủ để gọi là nghề mới. Nhóm em đặt luật từ trước: phải có ít nhất 3 tin từ 2 công ty, nội dung khác hẳn mọi cụm có sẵn, và có công cụ riêng. Áp luật này, kỳ này không có nghề mới; có 2 nghề lai và một danh sách theo dõi."

**Câu hỏi dự kiến:**
- *Analytics Engineer là nghề mới mà?* Trên thế giới là vai trò đang nổi. Trong dữ liệu kỳ này, tiêu đề đúng "Analytics Engineer" chỉ có 1 tin, nên theo luật chỉ "theo dõi". Muốn chốt cần thêm các kỳ sau.
- *Ngưỡng 3 tin, 2 công ty có tùy tiện không?* 2 công ty để loại trường hợp một công ty tự đặt tên riêng; 3 tin là mức tối thiểu để xem nội dung có khác cụm có sẵn không. Ngưỡng đặt trước khi chạy và ghi trong `mining/config.py`.
- *Loại "mới" của GLOSH trước đây đâu rồi?* Thay bằng luật nghề mới, vì kiểm tay loại "mới" của GLOSH chỉ đúng 2/9: phần lớn là tin viết sơ sài.

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
- *"Chạy lại ra cùng số" nghĩa là gì?* Cố định seed 42 và ghi mã băm (sha256) của dữ liệu đầu vào. Chạy lại trên **cùng máy** ra cùng số. Chạy trên máy khác (Windows ↔ Linux), Random Forest lệch nhẹ: MAE 6,105 ↔ 6,126; BI, luật kết hợp và phân cụm thì khớp.
- *Cổng SD3 có đổi sau khi thấy kết quả không?* Có hai thay đổi, đều ghi rõ: cụm nhỏ nhất ≥ 1% tính theo nhóm (vì cụm giờ tìm trong nhóm), và bỏ e5 (vì e5 tách theo ngôn ngữ). Ngưỡng ARI ≥ 0,8 giữ nguyên.

### Slide 20. Câu trả lời cho năm câu hỏi

**Slide nói gì.** Mỗi mục tiêu SD1–SD5 có một câu trả lời ngắn.

**Lời thoại gợi ý.** Đọc từng dòng, nhấn số chính:
- **SD1:** Hà Nội và TP.HCM chiếm 89% số tin; người mới chiếm 29%, lương 13,5 triệu so với 26,5 triệu ở Middle trở lên.
- **SD2:** kỹ năng đi theo gói, như java ⇒ spring_boot.
- **SD3:** 7 nhóm nghề tách thành 31 vai trò con ổn định; AI và Data Analyst đều có hai kiểu; không thấy nghề mới.
- **SD4:** kinh nghiệm và cấp chiếm 67%, mỗi kỹ năng dưới 0,6 triệu.
- **SD5:** lộ trình cho 8 nghề, 4 nghề ổn định.

**Câu hỏi dự kiến:**
- *"Không thấy nghề mới" có chắc không?* Chỉ chắc trong phạm vi dữ liệu này: một kỳ 3 tháng, chỉ có phía nhà tuyển dụng. Theo luật đặt trước, không tiêu đề nào đủ ≥ 3 tin, ≥ 2 công ty và nội dung khác hẳn mọi cụm. Analytics Engineer, blockchain… đang ở danh sách theo dõi.

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

Mỗi tin bị gắn cờ được xếp vào 1 loại theo luật trong `mining/anomaly.py`, hàm `classify_kind`:

| Loại | Điều kiện | Số tin |
|---|---|---|
| khác | Có **mã lý do cụ thể**: quá nhiều công cụ, fresher quá nhiều công cụ, lương quá thấp hoặc quá cao so với cấp, lương ngoại lai | 97 |
| **chưa rõ** | Bị gắn cờ nhưng **không vượt ngưỡng** của mã lý do nào | 37 |
| (mới, của GLOSH) | Hồ sơ kỹ năng ít gặp, mọi thứ khác bình thường. Không đưa lên slide nữa, thay bằng luật nghề mới vì kiểm tay chỉ đúng 2/9 | 76 |

37 tin "chưa rõ" gồm:
- **30 tin** do Isolation Forest gắn cờ (mã chung `ISOLATION_GENERIC`): 15 Intern/Fresher, 11 Lead/Manager, 4 Senior.
- **7 tin** do GLOSH gắn cờ nhưng có kinh nghiệm, lương hoặc số công cụ ngoài P5–P95 của cấp.

### 3.2. Phát hiện chính: "chưa rõ" là nhóm giáp ngưỡng

- **25/30 tin** Isolation Forest có số công cụ thuộc **top 10%** của chính cấp đó.
- Ngưỡng mã lý do (tính lại mỗi lần chạy): fresher > 17 công cụ (P95), mọi cấp > 27 công cụ (P99), lương > 3 lần trung vị cấp.
- Ví dụ: fresher đòi 15–17 công cụ, hoặc lương gần gấp 3 trung vị cấp nhưng chưa vượt.

**Giải thích:** Isolation Forest nhìn **tổ hợp** nhiều yếu tố cùng lúc. Một fresher đòi 16 công cụ **và** lương khá cao là tổ hợp hiếm, dù từng yếu tố chưa vượt ngưỡng riêng. Luật mã lý do thì xét từng yếu tố một.

### 3.3. Kiểm tay

Mẫu kiểm tay 22/11 (seed 42) có 3 tin "chưa rõ"; cả 3 vẫn là "chưa rõ" ở lần chạy 25/11. File: `mining/artifacts/sd3_anomaly_hand_check.csv`.

| Tin | Đánh giá |
|---|---|
| Kỹ thuật viên IT phần mềm, KCN Long Đức, 15 công cụ, fresher | Đúng là lạ: fresher đòi nhiều |
| AI Engineer (All Level), 16 công cụ | Đúng là lạ: ghi "all level" nhưng đòi nhiều |
| Head of AI & Data, 11 công cụ, 10 năm kinh nghiệm | Không lạ: hồ sơ bình thường của cấp cao |

Kết quả 2/3. **Mẫu chỉ 3 tin nên không đủ để kết luận tỷ lệ đúng.** Nói thẳng điều này với thầy. 8 tin "khác" đã kiểm tay cũng vẫn là "khác" (8/8).

### 3.4. Câu trả lời mẫu, khoảng 30 giây

> "Chưa rõ là 37 tin máy thấy lạ nhưng không gán được lý do cụ thể. Nhóm em tách riêng thay vì ép vào 'khác', để không gán nhãn sai. Khi xem lại, gần hết là tin **giáp ngưỡng**: 25 trên 30 tin đòi số công cụ thuộc top 10% của cấp mình, ví dụ fresher đòi 15–17 công cụ trong khi ngưỡng là trên 17. Nhóm em **không** dùng nhóm này để kết luận. Kết luận chỉ dựa vào loại 'khác', loại đã kiểm tay đúng 8/8."

### 3.5. Câu hỏi tiếp theo có thể gặp

**Vì sao không hạ ngưỡng cho "chưa rõ" thành "khác"?**
Ngưỡng lấy theo phân vị của dữ liệu (P99 số công cụ toàn bộ, P95 cho người mới). Hạ ngưỡng để "đẹp số" là chỉnh ngưỡng theo kết quả. Nhóm em giữ ngưỡng và báo cáo nhóm giáp ngưỡng riêng.

**Contamination 3% mà sao có 210 tin (5,6%)?**
3% chỉ áp cho Isolation Forest, trên tin biết cấp: 104 tin. Tổng 210 là hợp của ba cách bắt: Isolation Forest 104, GLOSH 86 (trùng 1 tin), luật 21 tin chưa rõ cấp có lý do cụ thể.

**Nếu có thêm thời gian?**
- Kiểm tay đủ 37 tin "chưa rõ".
- Thêm mã lý do "giáp ngưỡng" (số công cụ trong top 10% của cấp) để nhóm này có tên.

---

## Phần 4. Bảng tra nhanh con số

### Slide 11–15 (SD3)

| Slide | Con số | Ý nghĩa | Nguồn (`mining_metrics.json`) |
|---|---|---|---|
| 11 | 2.620 + 744 + 354 = 3.718 | Trong cụm con + mục Khác của 7 nhóm + nhóm Khác | `clustering.coverage` |
| 11 | 892 / 402 / 511 / 367 / 168 / 637 / 387 | Software / QA / Data & AI / Hạ tầng / Security / Product / Support | `clustering.group_counts` |
| 11 | 0,5 / 0,5 / 0 | Trọng số công cụ / khái niệm / e5 | `clustering.vector_space.block_weights` |
| 11 | 21% | Phần thông tin giữ lại khi vẽ 3 trục PCA | `clustering.pca_cumulative_variance_3d` |
| 12 | 31 cụm, 25–220 tin | Hồ sơ cụm con | `clustering.clusters` |
| 13 | 29/31 | Cụm khớp một vai trò trong danh sách | `clustering.n_sub_role_matched` |
| 14 | ARI 0,97 (thấp nhất Security 0,89) | Ổn định 5 seed theo nhóm | `clustering.stability`, `by_group` |
| 14 | 7,4% | Cụm nhỏ nhất so với nhóm của nó | `clustering.min_cluster_share` |
| 14 | 0,07 | Silhouette (chỉ báo cáo) | `clustering.silhouette` |
| 14 | 5 / 0 / 1 / 11 / 0 cụm | Cụm ≥ 90% JD tiếng Anh theo từng bộ trọng số | đo 24/11, `scripts/plot_weight_views.py` và chạy thử |
| 15 | 210 = 103 + 85 + 1 + 21 | Chỉ IF + chỉ GLOSH + cả hai + luật | `anomaly.n_flagged`, `n_isolation_forest`, `n_glosh`, `n_both`, `n_rule_unknown_level` |
| 15 | 97 / 37 | Khác / chưa rõ | `anomaly.kind_counts` |
| 15 | 216 / 115 / 20 / 3 / 0 | Nhóm Khác: giống cụm / JD ít thông tin / lẻ / nghề lai / nghề mới | `clustering.other.status_counts`, `sd3_other_roles.json` |

### Slide 16–18 (SD4, SD5)

| Slide | Con số | Ý nghĩa | Nguồn (`mining_metrics.json`) |
|---|---|---|---|
| 16 | MAE 6,105 so với 7,332; +16,7% | Sai số mô hình so với baseline | `salary.holdout`, `baseline_level_family`, `mae_gain_vs_baseline` |
| 16 | R² 0,557, CV 0,589 ± 0,029 | Độ giải thích | `salary.holdout.r2_log`, `cv_r2_mean`, `cv_r2_std` |
| 16 | 1.458 = 1.159 + 299; 869 công ty, chồng 0 | Dữ liệu học và thi | `salary.subset`, `n_train`, `n_test`, `n_companies_overlap` |
| 16 | 2.085 ước tính, 1.274 có cảnh báo | Lương đoán cho tin thỏa thuận | `salary.estimates` |
| 17 | 21,3 triệu; 77 kỹ năng; bootstrap 200 | Công thức giá trị kỹ năng | `salary.shap` |
| 18 | cov@10 và lệch 80/20 từng nghề | Lộ trình | `recommend.families` |

Tóm lại, file này có 4 phần: từ điển thuật ngữ, giải thích từng slide 11–21, chuẩn bị riêng cho "chưa rõ" ở slide 15, và bảng tra số. Phần SD3 (slide 11–15, 19, 20) cập nhật ngày 25/11 theo cách phân cụm 7 nhóm, không dùng e5.
