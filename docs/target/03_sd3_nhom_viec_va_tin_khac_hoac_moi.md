# SD3 · Nhóm việc thật sự và tin khác hoặc mới

> Tầng 2: khai phá không giám sát (phân cụm, tìm điểm khác biệt). Đề tài và bối cảnh: [00_de_tai.md](00_de_tai.md).

## 1. Bài toán nói đơn giản

Tên nghề trên tin chưa chắc phản ánh việc thật:

- Hai tin cùng tên "Software Engineer" có thể là hai việc khác hẳn nhau.
- Hai tin tên khác nhau có thể là cùng một việc.

Hiện tại dự án gán nhóm nghề bằng luật dựa trên tiêu đề và kỹ năng, gồm 10 nhóm + Other.

SD3 làm ngược lại: **bỏ qua tên nghề, chỉ nhìn nội dung tin** (JD và kỹ năng), rồi để máy tự gom những tin giống nhau thành nhóm. Sau đó so các nhóm máy tìm ra với 10 nhóm nghề gán bằng luật:

- **Khớp:** nhóm nghề gán bằng luật phản ánh đúng thị trường.
- **Lệch:** có nghề lai (ví dụ vừa làm dữ liệu vừa làm backend), nghề ngách, hoặc tin bị gán sai nhóm.

Những tin **không giống nhóm nào** gọi là tin **khác hoặc mới**:

- **Mới:** tổ hợp kỹ năng hoặc tiêu đề chưa thuộc nhóm nghề nào. Đây có thể là kiểu việc mới đang xuất hiện.
- **Khác:** tin có yêu cầu khác hẳn mặt bằng chung, ví dụ đòi quá nhiều kỹ năng, cấp thấp mà đòi nhiều năm kinh nghiệm, hoặc lương lệch xa so với cấp bậc. Người tìm việc nên đọc kỹ những tin này.

## 2. Câu hỏi cần trả lời

| Mã | Câu hỏi |
|---|---|
| 3.1 | Nếu chỉ dựa vào nội dung JD và kỹ năng, thị trường chia thành mấy nhóm việc? Mỗi nhóm là việc gì (kỹ năng đặc trưng, tiêu đề hay gặp, cấp bậc và lương công khai điển hình)? |
| 3.2 | Các nhóm máy tìm ra khớp hay lệch với 10 nhóm nghề gán bằng luật ở đâu? Có những nghề lai, nghề ngách nào? Bao nhiêu tin có vẻ bị gán sai nhóm nghề? |
| 3.3 | Những tin nào khác hoặc mới so với mặt bằng? Mỗi tin thuộc loại "mới" hay "khác", và vì sao? |

## 3. Dữ liệu dùng

| Cột | Dùng cho |
|---|---|
| Embedding e5 của JD (bước 12, `reports/processing/12_e5`) | Biểu diễn nội dung tin thành vector để đo độ giống nhau (3.1). TF-IDF đã bỏ 17/11 (spec 07 mục 4) |
| Ma trận kỹ năng multi-hot (`10_features`) | Ghép vào vector nội dung (3.1); mô tả nhóm (3.1). Tin không trích được kỹ năng nào từ JD bị loại khỏi phân cụm (spec 07 mục 4) |
| `job_family` | Chỉ dùng để **so sánh** ở câu 3.2, không đưa vào phân cụm |
| `seniority`, `exp_min_years`, số kỹ năng, `salary_*` | Mô tả nhóm (3.1); tìm tin loại "khác" (3.3) |
| `job_title_clean` | Mô tả nhóm và đọc tay |

## 4. Cách trả lời

- **3.1, gom nhóm:**
  - Bỏ các tin không trích được kỹ năng nào từ JD (ghi số tin bị bỏ), vì nếu giữ chúng sẽ tự gom thành một nhóm chỉ do thiếu kỹ năng.
  - Biến mỗi tin thành một vector, gồm nội dung JD (e5) ghép với kỹ năng. Giảm chiều bằng SVD/PCA (`reduce_svd`) để bỏ bớt nhiễu.
  - Chạy **K-Means**: chia tin thành k nhóm, mỗi tin về nhóm có tâm gần nhất. Hiện `mining/config.py` chốt k = 10 (`k_fixed`), và vẫn quét k từ 2 đến 20 để báo chỉ số Silhouette cho từng k. Silhouette càng gần 1 thì nhóm càng tách bạch.
  - Chạy **HDBSCAN** song song: tự tìm số nhóm dựa trên mật độ, nhóm nhỏ nhất 25 tin. Tin không đủ gần nhóm nào được để riêng.
  - Mỗi nhóm được mô tả bằng top kỹ năng, top tiêu đề, phân bố cấp bậc và trung vị lương công khai (`profile_clusters`). Người làm dự án đặt tên nhóm dựa trên phần mô tả này.
- **3.2, so với nhóm nghề:**
  - Lập bảng chéo nhóm máy tìm × `job_family`.
  - Đo mức khớp bằng hai chỉ số:
    - **ARI:** 1 là khớp hoàn toàn, 0 là ngẫu nhiên.
    - **NMI:** đo hai cách chia chung bao nhiêu thông tin.
  - Đọc bảng chéo để tìm ba trường hợp:
    - **Nghề lai:** một nhóm máy tìm trải đều trên 2 nhóm nghề trở lên.
    - **Nghề ngách:** một nhóm nghề bị máy tách thành nhiều nhóm con.
    - **Tin có vẻ bị gán sai:** tin nằm sâu trong nhóm máy tìm của nghề A nhưng lại mang nhãn nghề B.
- **3.3, tin khác hoặc mới:** gộp hai nguồn (phương pháp kỹ thuật là anomaly detection):
  - **Isolation Forest:** chấm điểm mức "dễ bị tách riêng" của mỗi tin dựa trên số kỹ năng, kinh nghiệm, cấp bậc và lương. Hiện lấy 3% tin có điểm cao nhất (`contamination` = 0,03).
  - **Tin HDBSCAN để riêng:** không thuộc nhóm nào.

  Mỗi tin được ghi một mã lý do (`_reason_codes` trong `mining/anomaly.py`) và xếp vào một trong hai loại:
  - **Mới:** tin HDBSCAN để riêng nhưng có các trường bình thường. Đây là tổ hợp nội dung chưa có nhóm.
  - **Khác:** tin có mã lý do về số kỹ năng, kinh nghiệm so với cấp bậc, hoặc lương so với cấp bậc.

## 5. Đầu ra

| Đầu ra | Dạng |
|---|---|
| Bảng nhóm việc (3.1) | Bảng: mã nhóm, tên đặt tay, số tin, top kỹ năng, top tiêu đề, phân bố cấp, trung vị lương công khai |
| Nhãn nhóm cho từng tin | Cột `cluster_id` gắn theo `job_id` |
| Bảng chéo nhóm × `job_family` và ARI/NMI (3.2) | Bảng và heatmap |
| Danh sách tin khác hoặc mới (3.3) | Bảng: `job_id`, tiêu đề, công ty, loại (mới/khác), mã lý do, điểm. Cột theo `ANOMALY_COLUMNS` trong `mining/anomaly.py` |
| Biểu đồ | Scatter 2D sau PCA, tô màu theo nhóm máy tìm và theo `job_family`, đặt cạnh nhau |

## 6. Cách biết đã trả lời đúng

- **Độ tách nhóm:** báo Silhouette và Davies–Bouldin. Hiện Silhouette chỉ 0,10 với k = 10 (MINE-1, L-47). Ngưỡng chấp nhận chờ chốt ở PRE-36.
- **Độ ổn định:** chạy lại với 5 seed khác nhau. ARI giữa các lần chạy phải ≥ 0,8 (đề xuất, chờ chốt PRE-36), tức là nhóm không đổi lung tung.
- **Kích thước nhóm:** không có nhóm nào dưới 1% số tin (đề xuất, chờ chốt PRE-36), trừ nhóm "để riêng" của HDBSCAN.
- **Không tách theo số lượng kỹ năng:** nhóm không được chỉ phản ánh tin nhiều hay ít kỹ năng. Hiện đang bị lỗi này (L-47). Phải kiểm bằng trung vị số kỹ năng của từng nhóm.
- **Kiểm tay:** đọc 20 tin "khác hoặc mới" ngẫu nhiên. Ghi tỷ lệ tin đúng là khác hoặc mới thật, so với tin chỉ do dữ liệu bị parse lỗi.

## 7. Những gì không trả lời được

- **"Nghề mới đang nổi" theo nghĩa xu hướng:** chỉ có 2 tháng dữ liệu. "Mới" ở đây nghĩa là chưa thuộc nhóm nào, không phải đang tăng.
- **Tin nào là lừa đảo hay tin ảo:** "khác" chỉ là khác mặt bằng, không phải kết luận về độ tin cậy của nhà tuyển dụng.
- **Tên nhóm đúng tuyệt đối:** tên nhóm do người đặt dựa trên mô tả, nên có tính chủ quan. Mọi tên đều phải kèm top kỹ năng và top tiêu đề để người đọc tự kiểm.

## 8. Code và spec liên quan

- Code:
  - `mining/clustering.py`: `build_vector_space`, `reduce_svd`, `scan_k`, `run_hdbscan`, `profile_clusters`, `cluster_jobs`.
  - `mining/anomaly.py`: `build_anomaly_space`, `detect_anomalies`.
  - `mining/config.py`: các tham số.
- Embedding: `processing/` (bước 12).
- Spec: `docs/spec/07_mining_spec.md` mục 3.3 (M3) và 3.4 (M4), `docs/spec/08_evaluation_spec.md` mục 3.3.
- Chất lượng dữ liệu cần cho SD3: PRE-35, PRE-34, MINE-1, MINE-7 trong `docs/KNOWN_ISSUED.md` (MINE-4 đã đóng ở L-48: k = 10).
