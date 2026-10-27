# KỊCH BẢN THUYẾT TRÌNH CHI TIẾT (SPEAKER PRESENTATION SCRIPT)
## Đề án: Kiến Trúc Tiền Xử Lý Dữ Liệu Đa Nguồn & Xây Dựng Bộ Dữ Liệu Vàng (VN-IT-Job-Mining)
**Thời lượng chuẩn:** 12 – 15 phút | **Quy mô:** 15 Slides | **Đối tượng:** Hội đồng Giảng viên môn Khai phá Dữ liệu (Data Mining)

---

## Bảng Phân Bổ Thời Gian Tổng Thể (Pacing Timeline)

```text
+-------------------+---------------------------------------------------------+-----------------+
| Chặng             | Nội dung các Slide                                      | Khung Thời Gian |
+-------------------+---------------------------------------------------------+-----------------+
| Chặng 1: Mở đầu   | Slide 01 -> Slide 03: Đặt vấn đề, Bệnh án dữ liệu thô   | 00:00 - 02:45   |
| Chặng 2: Nền tảng | Slide 04 -> Slide 06: Integration, Cascade Regex, FX    | 02:45 - 05:30   |
| Chặng 3: Thống kê | Slide 07 -> Slide 09: Sneaky Null, Winsorization, Loop  | 05:30 - 08:30   |
| Chặng 4: Đột phá  | Slide 10 -> Slide 12: Gemini Agent, Anchors, Khử trùng  | 08:30 - 11:30   |
| Chặng 5: Đóng gói | Slide 13 -> Slide 15: Target Schema, QA 5/5, Kết luận  | 11:30 - 14:00   |
+-------------------+---------------------------------------------------------+-----------------+
```

---

## Chi Tiết Kịch Bản Từng Slide (Slide-by-Slide Script)

### SLIDE 01: Tiêu Đề Đề Tài & Sứ Mệnh
* **Thời gian:** `00:00 - 00:45` (45 giây)
* **Thị giác màn hình:** Tên đề án, quy mô 10,024 bản ghi thô $\rightarrow$ 8,967 bản ghi Golden Master, danh xưng nhóm.
* **Lời thoại người thuyết trình:**
  > *"Kính thưa quý Thầy Cô trong Hội đồng và toàn thể các bạn học viên!  
  > Trong quy trình khai phá tri thức từ dữ liệu (KDD), giai đoạn tiền xử lý luôn chiếm từ **70% đến 80% thời gian** và đóng vai trò quyết định đến độ tin cậy của mọi mô hình học máy phía sau. Với phương châm **'Garbage In, Garbage Out'**, nếu dữ liệu đầu vào bị bẩn, méo mó hoặc chứa đầy nhiễu ngụy trang, thì mọi thuật toán khai phá dù hiện đại đến đâu cũng sẽ rút ra những kết luận sai lệch.  
  > Hôm nay, đại diện cho nhóm nghiên cứu đề án **VN-IT-Job-Mining**, em xin trân trọng trình bày về: **Kiến trúc Tiền xử lý Dữ liệu Đa nguồn và Quy trình Xây dựng Bộ Dữ Liệu Vàng**. Bài báo cáo sẽ minh chứng cách nhóm đã chuyển hóa thành công hơn 10.000 bài đăng tuyển dụng thô từ 8 sàn công nghệ lớn nhất Việt Nam thành một bộ dữ liệu vàng đạt chuẩn RFC 8259, sẵn sàng phục vụ cho các thuật toán khai phá chuyên sâu."*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Nhấn mạnh cụm từ **"70% đến 80% thời gian"**, **"Garbage In, Garbage Out"** và **"Bộ Dữ Liệu Vàng"**.
  * **Điểm ngắt nghỉ:** `[NGẮT NGHỈ 1.5 GIÂY]` sau câu mở đầu chào Hội đồng để tạo sự tập trung của phòng thi.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: Con số 10,024 ➔ 8,967]` để người nghe lập tức nắm được quy mô mẫu thực nghiệm.

---

### SLIDE 02: Bối Cảnh Thực Tế & Thách Thức Dữ Liệu IT
* **Thời gian:** `00:45 - 01:45` (60 giây)
* **Thị giác màn hình:** Danh sách 8 sàn, 5 vấn đề cốt lõi (dị thể, lương ẩn, sneaky nulls, ngoại lai bóc nhầm SĐT, trùng lặp).
* **Lời thoại người thuyết trình:**
  > *"Thưa Thầy Cô, khi bắt tay vào phân tích dữ liệu thực tế thu thập từ 8 sàn tuyển dụng hàng đầu như TopCV, VietnamWorks, ITviec, TopDev... nhóm nhận thấy dữ liệu không hề sạch sẽ như trong các tập dữ liệu mẫu giáo trình. Dữ liệu thô tồn tại 5 'căn bệnh' nghiêm trọng:  
  > Thứ nhất, **tính dị thể cực kỳ cao**: có sàn trả về API cấu trúc lồng nhau 3-4 tầng, có sàn nhét toàn bộ thông tin vào một bảng DOM chuỗi, có sàn lại giấu dữ liệu trong thẻ JSON-LD ẩn.  
  > Thứ hai là bài toán **Lương ẩn**: hơn 65% bài đăng ghi ở tiêu đề là 'Lương Thỏa thuận', nhưng thực chất doanh nghiệp lại viết cụ thể dải lương trong phần mô tả công việc.  
  > Thứ ba là hiện tượng **Null trá hình**: các sàn sử dụng các chuỗi như 'Cạnh tranh', số 0, hoặc chuỗi rỗng để đại diện cho ô trống, làm vô hiệu hóa hoàn toàn các hàm kiểm tra null tiêu chuẩn của thư viện dữ liệu.  
  > Thứ tư là **ngoại lai nhập liệu do bóc tách nhầm**: ví dụ câu văn có số điện thoại của HR bị regex bắt nhầm thành mức lương lên tới hàng trăm triệu đồng.  
  > Và cuối cùng là tình trạng **bài đăng trùng lặp xuyên sàn** do một vị trí được HR đăng tải đồng thời trên nhiều nền tảng."*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Gằn giọng dứt khoát ở các cụm từ: **"Dị thể cực kỳ cao"**, **"Lương ẩn"**, **"Null trá hình"**, **"Ngoại lai bóc nhầm"**.
  * **Điểm ngắt nghỉ:** `[NGẮT NGHỈ 1 GIÂY]` giữa mỗi căn bệnh dữ liệu để Hội đồng kịp theo dõi slide.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: 2 cột so sánh Thách thức Cấu trúc vs Nhiễu Nhập liệu]`.

---

### SLIDE 03: Kiến Trúc Pipeline Hiện Đại & Ranh Giới Đanh Thép
* **Thời gian:** `01:45 - 02:45` (60 giây)
* **Thị giác màn hình:** Sơ đồ khối ASCII 4 giai đoạn, Ma trận ranh giới đanh thép (Ironclad Boundaries).
* **Lời thoại người thuyết trình:**
  > *"Để giải quyết triệt để 5 thách thức trên mà không làm vỡ cấu trúc hệ thống, nhóm đã quy hoạch toàn bộ quy trình theo tiêu chuẩn **CRISP-DM nâng cấp ELT hiện đại**, chia làm 4 giai đoạn liên hoàn khép kín.  
  > Điểm mấu chốt ở đây là nhóm thiết lập **Khế ước Ranh giới đanh thép (Ironclad Boundaries)**:  
  > Giai đoạn 1 là **Integration**: chỉ làm nhiệm vụ đọc dữ liệu thô, ép phẳng cấu trúc JSON và ánh xạ trường chung, tuyệt đối không được tự tiện parse lương hay xóa dòng.  
  > Giai đoạn 2 là **Transformation**: tập trung bóc tách kiểu dữ liệu số, chuẩn hóa tiền tệ và trích xuất lương.  
  > Giai đoạn 3 là **Missing & Outlier**: bóc trần null giả mạo, kiểm định ngoại lai và ứng dụng AI đọc hiểu văn bản để bù đắp giá trị thiếu.  
  > Và Giai đoạn 4 là **Deep Normalization**: khử trùng lặp thực thể xuyên sàn và đóng gói cấu trúc Target Schema chuẩn mực.  
  > Ranh giới phân định rạch ròi này giúp ngăn chặn hoàn toàn hiện tượng chồng chéo logic và bảo toàn tính toàn vẹn của dữ liệu qua từng chặng."*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Nhấn mạnh cụm từ **"Khế ước Ranh giới đanh thép"**, **"Tuyệt đối cấm"**.
  * **Điểm ngắt nghỉ:** `[NGẮT NGHỈ 1 GIÂY]` sau câu kết về việc ngăn chặn chồng chéo logic.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: Dải mũi tên điều hướng từ GĐ 1 ➔ GĐ 2 ➔ GĐ 3 ➔ GĐ 4]`.

---

### SLIDE 04: Giai Đoạn 1 - Tích Hợp Schema & Ép Phẳng JSON
* **Thời gian:** `02:45 - 03:45` (60 giây)
* **Thị giác màn hình:** Khóa `job_id_global`, thuật toán Recursive Flattener, bảng đối chiếu 8 nguồn.
* **Lời thoại người thuyết trình:**
  > *"Đi vào Giai đoạn 1 - Tích hợp Schema. Đầu vào của chúng em là 10.024 bản ghi dạng phong bì thô (RawJobEnvelope).  
  > Để xóa bỏ sự phức tạp của các cấu trúc JSON lồng nhau, nhóm phát triển thuật toán **Recursive JSON Flattener**. Thuật toán này tự động duyệt đệ quy qua các dictionary, mảng danh sách kỹ năng, quyền lợi và các đối tượng JSON-LD ngầm để kéo phẳng tất cả về một tầng duy nhất.  
  > Đồng thời, để quản trị dòng dõi trên toàn hệ thống, nhóm sinh một khóa định danh toàn cục duy nhất: `job_id_global` bằng cách ghép tên sàn với mã ID gốc. Toàn bộ các trường dữ liệu dị thể được ánh xạ vào 8 nhóm thuộc tính cốt lõi.  
  > Tại giai đoạn này, nhóm tuân thủ nghiêm ngặt nguyên tắc **Deterministic 100%**: không dùng AI dự đoán, không drop bất kỳ bản ghi nào, bảo toàn 10,024 bản ghi thô nguyên vẹn sang giai đoạn sau."*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Nhấn mạnh **"Recursive JSON Flattener"**, **"Deterministic 100%"** và **"Bảo toàn nguyên vẹn 10,024 bản ghi"**.
  * **Điểm ngắt nghỉ:** `[NGẮT NGHỈ 1 GIÂY]` trước khi chuyển sang công thức `job_id_global`.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: Công thức sinh khóa định danh toàn cầu job_id_global]`.

---

### SLIDE 05: Giai Đoạn 2 - Cascade Salary Parser & Bóc Tách Kiểu
* **Thời gian:** `03:45 - 04:45` (60 giây)
* **Thị giác màn hình:** Sơ đồ 3 tầng Cascade Salary Parser, tỷ lệ tăng trưởng từ 35.2% lên 58.6%.
* **Lời thoại người thuyết trình:**
  > *"Bước sang Giai đoạn 2 - Chuyển hóa dữ liệu và bóc tách kiểu. Điểm đột phá kỹ thuật đầu tiên của nhóm nằm ở bộ bóc tách lương: **Cascade Salary Parser**.  
  > Trong thực tế, nếu chỉ dựa vào trường lương ở phần thông tin chung, chúng ta sẽ mất đi 65% dữ liệu vì bài đăng ghi 'Thỏa thuận'. Nhóm đã giải quyết bài toán này bằng cơ chế phân tầng 3 lớp:  
  > Lớp 1 quét tiêu đề và dải lương khai báo. Nếu không có hoặc ghi thỏa thuận, hệ thống sẽ kích hoạt ngay Lớp 2: bộ quét Regex chuyên sâu quét toàn bộ văn bản mô tả (JD) và yêu cầu để tìm kiếm các dải lương ẩn.  
  > Nếu phát hiện bài đăng ghi lương theo năm, ví dụ 300 đến 500 triệu/năm, Lớp 3 sẽ tự động kích hoạt phép chia cho 12 tháng để quy đồng chu kỳ.  
  > Nhờ cơ chế này, tỷ lệ bài đăng có dữ liệu định lượng số học đã tăng vọt từ **35.2% lên tới 58.6%**, trong khi cờ đánh dấu bài đăng gốc ghi thỏa thuận vẫn được lưu giữ minh bạch để phục vụ phân tích hành vi tuyển dụng."*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Nhấn mạnh cụm từ **"Tăng vọt từ 35.2% lên 58.6%"**.
  * **Điểm ngắt nghỉ:** `[NGẮT NGHỈ 1 GIÂY]` khi mô tả chuyển dịch từ Lớp 1 xuống Lớp 2.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: Sơ đồ dòng chảy 3 tầng Lớp 1 ➔ Lớp 2 ➔ Lớp 3]`.

---

### SLIDE 06: Giai Đoạn 2 - Chuẩn Hóa Ngoại Tệ & Chu Kỳ Lương
* **Thời gian:** `04:45 - 05:30` (45 giây)
* **Thị giác màn hình:** Tỷ giá USD fixed 25,400, tích hợp API Frankfurter cho SGD, tính lưu vết Lineage.
* **Lời thoại người thuyết trình:**
  > *"Đối với các bài đăng bằng ngoại tệ, nhóm nhận diện hai loại tiền tệ chính xuất hiện trên thị trường IT Việt Nam là USD và Đô la Singapore (SGD).  
  > Nhóm áp dụng tỷ giá tham chiếu 25.400 VND cho 1 USD. Riêng đối với đồng SGD, thay vì áp một tỷ giá tĩnh thiếu căn cứ, nhóm tích hợp trực tiếp **API Frankfurter** để truy vấn tỷ giá hối đoái chéo SGD/USD theo đúng ngày đăng tin tuyển dụng, sau đó nhân với tỷ giá dự án để ra mức lương VND chính xác nhất theo dòng thời gian.  
  > Toàn bộ các giá trị gốc, đơn vị tiền tệ gốc và thông tin tỷ giá áp dụng đều được bảo lưu độc lập trong các trường `salary_original` để đảm bảo tính kiểm chứng khoa học."*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Nhấn mạnh **"API Frankfurter"** và **"Bảo lưu độc lập giá trị gốc"**.
  * **Điểm ngắt nghỉ:** `[NGẮT NGHỈ 1 GIÂY]` sau khi nêu xong công thức tỷ giá SGD.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: Hộp công thức quy đổi tỷ giá lịch sử SGD]`.

---

### SLIDE 07: Giai Đoạn 3 - Bóc Trần 9+ Sneaky Null Markers & Cơ Chế MNAR
* **Thời gian:** `05:30 - 06:30` (60 giây)
* **Thị giác màn hình:** Bảng 9 dạng null trá hình, định nghĩa cơ chế MNAR, cờ `is_salary_negotiable`.
* **Lời thoại người thuyết trình:**
  > *"Thưa Thầy Cô, một trong những đóng góp học thuật quan trọng của nhóm nằm ở Giai đoạn 3: Phân biệt chính xác bản chất của dữ liệu khuyết thiếu.  
  > Hệ thống đã xây dựng bộ quét nhận diện **9+ dạng Null trá hình** bao gồm các chuỗi văn bản như 'Thương lượng', 'Cạnh tranh', số 0, hoặc chuỗi rỗng.  
  > Về mặt lý thuyết xác suất thống kê, lương thỏa thuận là cơ chế **MNAR - Missing Not At Random (Khuyết thiếu có chủ đích)**. Doanh nghiệp giấu lương để có lợi thế đàm phán hoặc bảo mật nội bộ, chứ không phải do hệ thống ghi nhận bị lỗi ngẫu nhiên.  
  > Do đó, nhóm ban hành quy tắc cấm tuyệt đối: **Không được điền giá trị trung bình (Mean) hay trung vị (Median) vào các ô lương thỏa thuận**. Hành vi đó sẽ làm phẳng phân phối lương và tạo ra những kết luận sai lệch nghiêm trọng. Nhóm bảo toàn trạng thái null của số lương và đánh dấu cờ `is_salary_negotiable = True` để nghiên cứu như một biến phân loại độc lập."*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Nhấn mạnh thuật ngữ học thuật **"MNAR - Missing Not At Random"** và lệnh cấm **"Tuyệt đối CẤM điền Mean/Median"**.
  * **Điểm ngắt nghỉ:** `[NGẮT NGHỈ 2 GIÂY]` ngay sau khi giải thích lý do tại sao cấm fillna để Hội đồng thấm thía luận điểm phương pháp luận.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: Dòng chữ cảnh báo CẤM ĐIỀN MEAN/MEDIAN màu đỏ]`.

---

### SLIDE 08: Giai Đoạn 3 - Kiểm Định Ngoại Lai & Winsorization
* **Thời gian:** `06:30 - 07:30` (60 giây)
* **Thị giác màn hình:** Công thức IQR, ranh giới Winsorization P1-P99 (4 triệu $\rightarrow$ 120 triệu VND), Zero Record Loss Policy.
* **Lời thoại người thuyết trình:**
  > *"Song song với dữ liệu khuyết thiếu là bài toán xử lý ngoại lai (Outliers).  
  > Dữ liệu lương sau khi bóc tách tồn tại những điểm cực đoan do nhập liệu sai: ví dụ mức lương 500 nghìn đồng/tháng hoặc mức lương lên đến 2 tỷ đồng/tháng. Nhóm áp dụng phương pháp khoảng tứ phân vị **IQR (Interquartile Range)** để xác định ranh giới bất thường.  
  > Tuy nhiên, thay vì áp dụng giải pháp truyền thống là xóa bỏ dòng dữ liệu (Drop rows), nhóm đề xuất chính sách: **Zero Record Loss Policy**.  
  > Bởi vì trong khai phá dữ liệu IT, một tin tuyển dụng dù có mức lương ngoại lai thì các trường thông tin về Kỹ năng công nghệ, Cấp bậc, Địa điểm của nó vẫn cực kỳ quý giá. Nếu xóa dòng, ta sẽ làm méo mó kết quả phân tích kỹ năng ở mục tiêu SD3.  
  > Vì vậy, nhóm áp dụng kỹ thuật **Winsorization tại phân vị 1% và 99%**, kéo các giá trị cực đoan về ngưỡng an toàn từ 4 triệu đến 120 triệu đồng/tháng. Toàn bộ 100% bản ghi đều được bảo toàn trọn vẹn."*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Nhấn mạnh **"Zero Record Loss Policy"** và **"Winsorization tại phân vị 1% và 99%"**.
  * **Điểm ngắt nghỉ:** `[NGẮT NGHỈ 1.5 GIÂY]` sau câu hỏi gợi mở về việc tại sao không được xóa dòng.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: Dải số 4 triệu ➔ 120 triệu VND và con số bảo toàn 100% bản ghi]`.

---

### SLIDE 09: Giai Đoạn 3 - Vòng Lặp Phản Hồi & Heuristic Scrubber
* **Thời gian:** `07:30 - 08:30` (60 giây)
* **Thị giác màn hình:** Minh họa lỗi SĐT biến thành lương 243 triệu, lỗi `1*** USD`, sơ đồ Cyclic Loop.
* **Lời thoại người thuyết trình:**
  > *"Điểm đặc sắc của quy trình tiền xử lý hiện đại là **Vòng lặp phản hồi thích ứng (Cyclic Feedback Loop)**, chứng minh Data Mining không phải quy trình một chiều cứng nhắc.  
  > Khi thực hiện kiểm định ngoại lai ở Bước 3, hệ thống phát hiện 2 ca lỗi dị biệt rất thú vị:  
  > Ca thứ nhất: Trong JD có câu 'Liên hệ Ms. Khánh Lương, SĐT 0243.936.6990' $\rightarrow$ bộ regex do thấy chữ Lương đứng trước cụm số đã bóc nhầm đầu số 0243 thành mức lương 243 triệu VND!  
  > Ca thứ hai: JD ghi 'Lương từ 1\*\*\* USD' $\rightarrow$ hệ thống bóc chữ số 1 và nhân tỷ giá thành mức lương 25.400 VND!  
  > Ngay lập tức, nhóm đã gửi tín hiệu hồi quy từ Bước 3 ngược về Bước 2, phát triển bộ lọc **Heuristic Scrubber**. Bộ lọc này nhận diện đầu số điện thoại Việt Nam và ký tự che giấu để reset các trường hợp bắt nhầm về null an toàn trước khi chạy thống kê. Nhờ đó, tính chính xác của dải lương được hoàn thiện ở mức tối đa."*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Hơi nở nụ cười nhẹ, giọng sinh động khi kể ca lỗi **"Ms. Khánh Lương SĐT 0243..."** và **"1*** USD"**.
  * **Điểm ngắt nghỉ:** `[NGẮT NGHỈ 1 GIÂY]` sau khi kể xong ca lỗi để Hội đồng cùng bật cười thích thú trước case study thực tế.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: Mũi tên vòng lặp phản hồi ngược từ Bước 3 về Bước 2]`.

---

### SLIDE 10: Giai Đoạn 3.5 - Gemini All-in-One Preprocessing Agent
* **Thời gian:** `08:30 - 09:30` (60 giây)
* **Thị giác màn hình:** Bảng 4 nhiệm vụ song hành của Gemini Agent, module Checkpoint Store.
* **Lời thoại người thuyết trình:**
  > *"Sau khi hoàn thiện tầng thống kê, nhóm triển khai bước đột phá AI: **Gemini All-in-One Preprocessing Agent** sử dụng mô hình Gemini 1.5 Flash.  
  > Thay vì thực hiện nhiều lượt gọi API riêng lẻ gây tốn kém chi phí token và độ trễ, nhóm thiết kế một prompt chuyên sâu thực thi đồng thời 4 nhiệm vụ trong 1 lần duyệt duy nhất:  
  > Thứ nhất: Phân loại kỹ năng 3 lớp: Hard skills chuẩn tiếng Anh, Soft skills tiếng Việt và Domain skills nghiệp vụ.  
  > Thứ hai: Bổ sung các thuộc tính khuyết thiếu như số năm kinh nghiệm, 7 cấp bậc Seniority chuẩn, trình độ học vấn và phát hiện trạng thái làm việc thứ 7.  
  > Thứ ba: Dự đoán mức lương thị trường có cơ sở khoa học.  
  > Thứ tư: Tự động dịch thuật các bài đăng tiếng Anh sang tiếng Việt để chuẩn hóa ngữ nghĩa toàn tập dữ liệu.  
  > Đặc biệt, hệ thống đi kèm module **Checkpoint Store** ghi nhận tiến trình theo từng dòng JSONL, giúp hệ thống có thể tạm dừng và tiếp tục xử lý mượt mà khi gặp sự cố mạng hoặc giới hạn hạn ngạch API."*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Nhấn mạnh cụm từ **"Single-pass (1 lần duyệt duy nhất)"** và **"Phân loại kỹ năng 3 lớp"**.
  * **Điểm ngắt nghỉ:** `[NGẮT NGHỈ 1 GIÂY]` khi chuyển giữa 4 nhiệm vụ của Agent.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: Khối Checkpoint Store và 3 nhánh kỹ năng Hard - Soft - Domain]`.

---

### SLIDE 11: Giai Đoạn 3.5 - Market Anchor Calculator
* **Thời gian:** `09:30 - 10:30` (60 giây)
* **Thị giác màn hình:** Sơ đồ 4 cấp mỏ neo thị trường, cơ chế khóa ảo giác của LLM.
* **Lời thoại người thuyết trình:**
  > *"Một câu hỏi phản biện rất lớn đặt ra cho việc dùng AI trong tiền xử lý là: 'Làm thế nào để đảm bảo LLM không tự ý bịa đặt (hallucination) mức lương khi dự đoán?'  
  > Để giải quyết triệt để vấn đề này, nhóm đã sáng tạo ra module **Market Anchor Calculator**.  
  > Trước khi gửi dữ liệu cho Gemini, hệ thống tính toán sẵn ma trận mỏ neo thị trường dựa trên trung vị mức lương thực tế theo từng cặp `[Sàn Tuyển Dụng x Cấp Bậc]`.  
  > Hệ thống áp dụng cơ chế tra cứu phân cấp 4 tầng: nếu sàn và cấp bậc có đủ từ 15 mẫu lương thực trở lên, lấy mỏ neo cấp 1. Nếu không đủ, lùi dần về trung vị cấp bậc, trung vị sàn hoặc khung sàn lý thuyết của ngành IT.  
  > Gemini bắt buộc phải neo dự đoán của mình xung quanh dải mỏ neo này và chỉ được phép tinh chỉnh dựa trên độ khó công nghệ. Nhờ đó, 100% mức lương dự đoán đều nằm vững chắc trong biên độ phân phối thực tế của thị trường."*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Nhấn mạnh **"Khóa chặt ảo giác (Hallucination Lock)"** và **"Mỏ neo thị trường 4 cấp"**.
  * **Điểm ngắt nghỉ:** `[NGẮT NGHỈ 1.5 GIÂY]` sau câu hỏi phản biện mở đầu để tạo sự kịch tính.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: 4 bậc thang phân cấp Cấp 1 ➔ Cấp 2 ➔ Cấp 3 ➔ Cấp 4]`.

---

### SLIDE 12: Giai Đoạn 4 - Khử Trùng Lặp Ngữ Nghĩa Xuyên Sàn
* **Thời gian:** `10:30 - 11:30` (60 giây)
* **Thị giác màn hình:** Quy trình Blocking $\rightarrow$ Text Embeddings Cosine Similarity $\ge 0.82$, kết quả loại 1,057 bài trùng.
* **Lời thoại người thuyết trình:**
  > *"Bước vào Giai đoạn 4, nhóm thực hiện bài toán **Khử trùng lặp thực thể xuyên sàn (Cross-Platform Entity Resolution)**.  
  > Cùng một vị trí tuyển dụng ví dụ như Senior Java Developer tại Hà Nội thường được doanh nghiệp đăng lên cả TopCV, VietnamWorks và ITviec với câu từ được xào nấu khác nhau đôi chút. Nếu giữ nguyên, việc đếm tần suất kỹ năng sẽ bị thổi phồng sai lệch.  
  > Nếu so sánh cặp đôi toàn bộ 10.000 bài đăng, chi phí tính toán sẽ là $\mathcal{O}(N^2)$ với gần 100 triệu phép tính. Nhóm đã áp dụng kỹ thuật **Blocking**: chỉ so khớp các bài đăng có cùng tên công ty chuẩn hóa và cùng tỉnh thành.  
  > Sau đó, nhóm tính toán độ tương đồng **Cosine Similarity** trên vector nhúng văn bản mô tả công việc. Với ngưỡng thực nghiệm $\ge 0.82$, hệ thống phát hiện chính xác các bài đăng trùng lặp và tiến hành hợp nhất thành một 'Bản ghi Vàng' duy nhất, ưu tiên giữ lại các trường có độ chi tiết cao nhất.  
  > Kết quả: Nhóm đã loại bỏ chính xác **1,057 bài đăng trùng lặp**, tương đương 10.54% dữ liệu dư thừa."*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Nhấn mạnh con số **"Loại bỏ 1,057 bài đăng trùng lặp (10.54%)"** và công thức **"Cosine Similarity >= 0.82"**.
  * **Điểm ngắt nghỉ:** `[NGẮT NGHỈ 1 GIÂY]` khi chuyển từ kỹ thuật Blocking sang phép đo Cosine.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: Con số giảm trừ 1,057 bài trùng và ngưỡng 0.82]`.

---

### SLIDE 13: Giai Đoạn 4 - Target Schema Chuẩn 11 Khóa Tinh Gọn
* **Thời gian:** `11:30 - 12:15` (45 giây)
* **Thị giác màn hình:** Đoạn JSON mẫu 11 khóa canonical, dọn dẹp sạch cờ kỹ thuật và cột `raw_*`.
* **Lời thoại người thuyết trình:**
  > *"Sau khi khử trùng lặp và làm giàu dữ liệu, module `TargetSchemaFormatter` tiến hành đóng gói đầu ra cuối cùng về chuẩn **Target Schema 11 Khóa Gốc Tinh Gọn**.  
  > 11 khóa gốc này bao gồm: `job_id_global`, `source_platform`, `source_url`, `job_info`, `company`, `locations`, `salary`, `skills`, `requirements`, `jd_text` và `date`.  
  > Tất cả các cột thô mang tiền tố `raw_*`, các cờ trung gian phục vụ debug như `is_stub_jd`, `quality_score`, `is_outlier_capped` đều được tinh giản triệt để. Dữ liệu địa điểm được phân cấp về 63 tỉnh thành, kỹ năng được tách rạch ròi thành 3 mảng Hard, Soft và Domain skills.  
  > Cấu trúc này vừa bảo đảm tính toàn vẹn thông tin, vừa tối ưu hóa hoàn hảo cho các truy vấn của DuckDB và các dataframe của Pandas."*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Nhấn mạnh **"11 Khóa Gốc Tinh Gọn"** và **"Xóa sạch 100% cột raw_*"**.
  * **Điểm ngắt nghỉ:** `[NGẮT NGHỈ 1 GIÂY]` sau khi liệt kê các nhóm thông tin.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: Đoạn code JSON mẫu 11 khóa chuẩn]`.

---

### SLIDE 14: Kiểm Định Chất Lượng Đường Ống (QA 5/5 PASSED) & Trước vs Sau
* **Thời gian:** `12:15 - 13:15` (60 giây)
* **Thị giác màn hình:** Bảng điểm 5/5 PASSED, bảng so sánh Trước vs Sau (Độ phủ lương 100%, Skewness giảm từ 5.8 về 0.42).
* **Lời thoại người thuyết trình:**
  > *"Để đảm bảo tính nghiêm ngặt về mặt kỹ thuật phần mềm và khoa học dữ liệu, nhóm đã xây dựng bộ kiểm thử chất lượng tự động gồm 5 bài kiểm tra chuyên sâu trong `reports/qa/qa_pipeline_report.md` và đạt kết quả **5/5 PASSED tuyệt đối**:  
  > Check 1 bảo đảm tính kế thừa dòng dõi dữ liệu 100%.  
  > Check 2 chứng minh bộ dữ liệu đạt chuẩn **100% PURE JSON RFC 8259**, quét sâu đệ quy không còn bất kỳ hằng số NaN nào gây lỗi parser.  
  > Check 3, 4, 5 xác nhận sự tuân thủ tuyệt đối cấu trúc Target Schema, tính nguyên vẹn của chính sách MNAR và các luật chất lượng ngoại lai QR1-QR5.  
  > Nhìn vào bảng so sánh Trước vs Sau trên màn hình: Tỷ lệ bao phủ mức lương và kinh nghiệm đạt mức 100% tuyệt đối, độ lệch phân phối lương (Skewness) từ mức lệch phải nghiêm trọng lớn hơn 5.8 đã được kéo về mức 0.42 đạt chuẩn phân phối chuẩn qua phép biến đổi Log-transform. Bộ dữ liệu đã hoàn toàn sạch sẽ và sẵn sàng."*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Giọng dõng dạc, tự hào ở cụm từ **"5/5 PASSED tuyệt đối"**, **"100% PURE JSON RFC 8259"**, **"Skewness kéo từ 5.8 về 0.42"**.
  * **Điểm ngắt nghỉ:** `[NGẮT NGHỈ 1.5 GIÂY]` sau khi đọc xong con số 5/5 PASSED.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: Huy hiệu PASSED màu xanh lá và hàng chỉ số Skewness]`.

---

### SLIDE 15: Kết Luận & Sẵn Sàng Cho 5 Mục Tiêu Chiến Lược SD1 — SD5
* **Thời gian:** `13:15 - 14:00` (45 giây)
* **Thị giác màn hình:** Tóm tắt 4 đóng góp chính, liên kết 5 mục tiêu SD1-SD5, lời cảm ơn.
* **Lời thoại người thuyết trình:**
  > *"Kính thưa Thầy Cô và các bạn,  
  > Tóm lại, giai đoạn Tiền xử lý dữ liệu của nhóm đã hoàn thành xuất sắc sứ mệnh được giao:  
  > Chuyển đổi thành công 10.024 bản ghi thô dị thể thành **8.967 bản ghi Bộ Dữ Liệu Vàng độc bản**, hoàn thành trọn vẹn mục tiêu nền tảng **SD1: Tích hợp dữ liệu thị trường lao động IT**.  
  > Nền tảng dữ liệu vàng này đã sẵn sàng mở đường cho các phân tích chuyên sâu tiếp theo của đề án: từ phân loại 12 Job Family ở **SD2**, khai phá luật kết hợp kỹ năng FP-Growth ở **SD3**, đến việc đối chiếu khoảng cách đào tạo Đại học ở **SD4** và xây dựng hệ thống khuyến nghị lộ trình nghề nghiệp ở **SD5**.  
  > Nhóm em xin chân thành cảm ơn quý Thầy Cô đã chú ý lắng nghe và rất mong nhận được những nhận xét, góp ý quý báu từ Hội đồng ạ!"*
* **Cử chỉ & Nhấn mạnh (Speaking Tips):**
  * **Điểm cần nhấn giọng:** Nhấn mạnh **"Hoàn thành trọn vẹn SD1"**, **"Sẵn sàng cho SD2 đến SD5"**.
  * **Điểm ngắt nghỉ:** Cúi đầu chào nhẹ, giọng chân thành, tươi vui khi nói lời cảm ơn.
  * **Điểm trỏ tay vào slide:** `[TRỎ TAY VÀO SLIDE: Bản đồ 5 mục tiêu SD1 ➔ SD5 và Logo nhóm]`.

---

## Bộ Câu Hỏi Phản Biện Dự Phòng Của Hội Đồng & Hướng Dẫn Trả Lời (Anticipated Q&A Defense)

### Câu Hỏi 1: *"Tại sao nhóm lại KHÔNG XÓA DÒNG khi gặp outlier lương? Có phải nhóm ngại mất dữ liệu không?"*
* **Bản chất cốt lõi cần trả lời:**  
  * Không phải là ngại mất dữ liệu, mà phương pháp luận khoa học đòi hỏi phải **Phân tích căn nguyên gốc rễ (Root Cause Analysis)** xem: *Tại sao giá trị đó lại bị coi là outlier?* trước khi quyết định xử lý cơ học!
* **3 Nhóm Nguyên Nhân Ngoại Lai Thực Tế Mà Nhóm Đã Chứng Minh:**
  1. **Ngoại lai cao (High Outlier - ví dụ 100M - 250M VND):**  
     Đây thường là các vị trí tuyển dụng cấp cao: **Senior Lead, Solution Architect, Engineering Director, CTO**, hoặc các doanh nghiệp FDI công nghệ thanh toán gói thu nhập bằng ngoại tệ.  
     $\rightarrow$ *Đây là dữ liệu THỰC TẾ và CỰC KỲ GIÁ TRỊ*, phản ánh đúng đỉnh trần của thị trường IT Việt Nam. Nếu xóa dòng này, ta sẽ làm biến mất phân khúc nhân sự cao cấp và làm sai lệch hoàn toàn bức tranh phân bổ cấp bậc ở mục tiêu SD2!
  2. **Ngoại lai thấp (Low Outlier - ví dụ 1M - 4M VND):**  
     Đây thường là các vị trí **Intern / Thực tập sinh** nhận tiền hỗ trợ phụ cấp thực tập (stipend) hoặc sinh viên làm part-time.  
     $\rightarrow$ *Đây là mức lương hợp lệ ở phân khúc nhập môn*, chứ không phải lỗi dữ liệu. Nếu xóa đi, ta sẽ làm mất toàn bộ tập mẫu của sinh viên mới ra trường – đối tượng nghiên cứu trọng tâm của đề án ở mục tiêu SD4!
  3. **Ngoại lai do Lỗi Kỹ thuật / Tin rác (Noise & Extraction Artifacts):**  
     Bóc nhầm số điện thoại (ví dụ: `0243...` thành 243 triệu) hoặc chuỗi che giấu (`1*** USD`).  
     $\rightarrow$ Với trường hợp này, nhóm dùng **Heuristic Scrubber** để reset trường lương về `null` và bật cờ `is_salary_negotiable = True` chứ **vẫn kiên quyết KHÔNG XÓA DÒNG**, bởi vì bài đăng đó vẫn chứa trọn vẹn thông tin về Kỹ năng công nghệ (Hard Skills) mà thị trường đang cần!
* **Kết luận phương pháp:**  
  Chính sách **Zero Record Loss Policy** kết hợp với kỹ thuật **Winsorization tại phân vị 1% và 99%** vừa khống chế được phương sai cho các mô hình định lượng, vừa bảo toàn 100% mẫu cho bài toán khai phá kỹ năng ở SD3.

---

### Câu Hỏi 2: *"Tại sao nhóm không dùng các hàm `dropna()` hay `fillna(mean)` có sẵn của Pandas cho nhanh gọn mà phải xây dựng cả một pipeline phức tạp?"*
* **Trọng tâm trả lời:**
  * Khẳng định việc dùng `dropna()` sẽ vi phạm nghiêm trọng tính toàn vẹn dữ liệu: trong bài toán IT, một tin khuyết lương vẫn chứa danh mục kỹ năng (Skills) quý giá. Xóa dòng sẽ làm sai lệch phân phối kỹ năng của thị trường.
  * Việc điền `fillna(mean)` trên cột lương vi phạm giả định thống kê vì lương thỏa thuận là biến **MNAR (Missing Not At Random)**. Doanh nghiệp giấu lương có chủ đích (thường là các vị trí cao cấp hoặc ngân sách đặc biệt). Điền mean/median sẽ làm biến dạng độ lệch Skewness và triệt tiêu tính phương sai thực tế.

---

### Câu Hỏi 3: *"Bản chất toán học của Winsorization là gì và tại sao lại chọn phân vị 1% - 99% mà không dùng quy tắc 3-Sigma hay 1.5 IQR để cắt bỏ?"*
* **Trọng tâm trả lời:**
  * Quy tắc 3-Sigma ($\mu \pm 3\sigma$) dựa trên giả định dữ liệu tuân theo **Phân phối chuẩn (Normal Distribution)**. Tuy nhiên, phân phối lương thực tế bị lệch phải rất nặng (Skewness > 5.8), khiến cho độ lệch chuẩn $\sigma$ bị thổi phồng, ranh giới 3-Sigma bị mất tác dụng.
  * IQR ($Q_1 - 1.5\text{IQR}$ đến $Q_3 + 1.5\text{IQR}$) được dùng để nhận diện ngoại lai nhưng nếu loại bỏ sẽ gây mất mát mẫu.
  * Winsorization tại $P_1$ và $P_{99}$ kéo các điểm ngoại lai số học cực đoan (lỗi nhập liệu 500k hoặc 2 tỷ) về cận an toàn (4 triệu và 120 triệu), giúp bảo toàn số lượng mẫu $N$ cố định, hỗ trợ các mô hình học máy yêu cầu độ ổn định phương sai.

---

### Câu Hỏi 4: *"Làm thế nào nhóm kiểm soát được hiện tượng ảo giác (Hallucination) của Gemini khi làm giàu dữ liệu và dự đoán lương?"*
* **Trọng tâm trả lời:**
  * Nhóm áp dụng kỹ thuật **Human-in-the-loop kết hợp Market Anchor Calculator**:
    1. Toàn bộ prompt được ràng buộc chặt chẽ bằng JSON Schema nghiêm ngặt (`response_schema`), từ chối mọi phản hồi tự do dạng văn bản.
    2. Dự đoán lương bắt buộc phải lấy mỏ neo từ ma trận trung vị có sẵn của sàn và cấp bậc. Gemini chỉ có vai trò điều chỉnh hệ số dựa trên độ khó công nghệ chứ không được tự sinh số ngẫu nhiên.
    3. Trước khi chạy diện rộng, nhóm đã chạy Pilot đối chứng 20 mẫu, kiểm định độ lệch sai số và ký biên bản nghiệm thu (Sign-off) đạt chuẩn mới đưa vào pipeline chính thức.

---

### Câu Hỏi 5: *"Tại sao nhóm lại chọn ngưỡng Cosine Similarity là 0.82 trong khử trùng lặp mà không phải 0.90 hay 0.75?"*
* **Trọng tâm trả lời:**
  * Ngưỡng 0.82 là kết quả của quá trình **thực nghiệm kiểm định chéo (Empirical Validation)** trên tập mẫu gán nhãn:
    - Nếu chọn ngưỡng cao $\ge 0.90$: Bị bỏ sót rất nhiều tin trùng lặp vì các HR khi đăng chéo giữa TopCV và VietnamWorks thường thay đổi lời chào đầu hoặc thêm bớt một vài dòng chế độ đãi ngộ.
    - Nếu chọn ngưỡng thấp $\le 0.75$: Bắt đầu xuất hiện hiện tượng gộp nhầm các vị trí tuyển dụng khác nhau trong cùng một công ty (ví dụ: gộp nhầm vị trí Java Developer với vị trí DevOps Engineer vì cả hai đều có chung phần giới thiệu công ty và yêu cầu làm việc nhóm).
    - Ngưỡng 0.82 kết hợp với điều kiện tiên quyết (Blocking: trùng tên công ty chuẩn hóa và cùng tỉnh thành) đạt chỉ số F1-Score tối ưu nhất.

---

### Câu Hỏi 6: *"Tại sao trong báo cáo QA nhóm lại nhấn mạnh việc cấm định dạng Parquet và CSV để chuyển sang 100% PURE JSON RFC 8259?"*
* **Trọng tâm trả lời:**
  * CSV không hỗ trợ cấu trúc dữ liệu phân cấp phức tạp (như danh sách các kỹ năng `hard_skills`, địa chỉ chi tiết đa văn phòng), nếu ép về CSV sẽ phải dùng ký tự ngăn cách như dấu phẩy hoặc chấm phẩy, rất dễ gây lỗi phân rã (parsing error) khi bản thân nội dung chứa dấu phẩy.
  * Parquet tuy tối ưu cho phân tích cột nhưng là định dạng nhị phân, thiếu tính minh bạch trực quan khi bàn giao dữ liệu cho các bên kiểm toán hoặc các ứng dụng web hiển thị.
  * Chuẩn **RFC 8259** bảo đảm tính tương thích tối đa trên mọi nền tảng lập trình (Python, JavaScript, Go, R), đồng thời loại bỏ hoàn toàn các ký tự `NaN` phi chuẩn vốn thường gây crash các bộ phân tích cú pháp JSON nghiêm ngặt.
