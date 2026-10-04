  1. vietnam_it_recruitment_data_mining_project.md: Bản Đề cương học thuật (thiết kế tổng thể vòng đời CRISP-DM, mục tiêu dữ liệu, bài toán ML, kế hoạch nghiệm thu Tuần 9   
  với giảng viên).                                                                                                                                                           
  2. kien_truc_co_the.md: Bản Thiết kế kỹ thuật thực chiến (chi tiết cách 6 thành viên chạy 6 crawler trên laptop cá nhân, đẩy S3 qua boto3, quản lý checkpoint, tránh mất   
  tiền AWS, cấu trúc common/, báo Telegram).                                                                                                                                 
                                                                                                                                                                             
  Dưới đây là bảng tổng hợp các điểm bổ trợ lẫn nhau (cần gộp để đủ context) và 5 điểm "CẤN" (xung đột/chưa khớp) kèm phương án giải quyết để bạn lựa chọn chốt:             
  ──────                                                                                                                                                                     
  ### I. Những điểm khác biệt bổ trợ (Cần giữ cả 2 để trọn vẹn Context)                                                                                                      
                                                                                                                                                                             
  • Từ file đề cương học thuật:                                                                                                                                              
      • Giữ mục tiêu nghiên cứu & 4 câu hỏi nghiên cứu nghiệp vụ.                                                                                                                                                                                                  
      • Giữ định nghĩa chuẩn  các nhóm ngành thuộc IT và có bộ lọc để lọc theo IT nha .                                                                        
      • Giữ bài toán Machine Learning cụ thể (TF-IDF + Naive Bayes / SVM để phân loại vị trí) và kế hoạch 8 biểu đồ trực quan hóa (EDA).                                     
      • Giữ nhánh thử nghiệm AI Browser Use + Ollama (1000 tin để so sánh với parser truyền thống và làm  nhóm của it viec và topcv á).                                                                       
  • Từ file kiến trúc thực chiến:                                                                                                                                            
      • Giữ mô hình triển khai phân tán: 6 laptop cào độc lập ghi JSONL local → tự động upload S3 → báo cáo bot Telegram. Tui đang thắc mắc việt này để có thể thiết kế được schedule cho nhóm để kiểu mỗi máy sẽ cào rồi nộp ?
      Ha nếu như đơn giơn giản hơn thì có thể mõi b viết code cho 6 trang rồi tui dùng vps ec2 để chạy hết 6 trang thì b thấy sau.                          
      • Giữ thiết kế module dùng chung: crawlers/common/ (HTTP client, delay/retry, checkpoint, JSONL writer, S3 uploader). Giữ thiết kế batching và ELT nha                                                  
      • Giữ cơ chế bảo mật AWS: Mỗi thành viên 1 IAM User riêng chỉ có quyền ghi vào prefix nguồn của mình, đặt Budget Alert tránh mất tiền.                                 
      • Giữ cơ chế khử trùng lặp 2 tầng: Tầng 1 (ngay lúc cào bằng seen_ids.txt) và Tầng 2 (liên nguồn ở Curated layer).                                                     
                                                                                                                                                                             
  ──────                                                                                                                                                                     
  ### II. 5 Điểm "CẤN" (Xung đột giữa 2 file) & Phương án cho bạn chọn chốt                                                                                                  
                                                                                                                                                                             
  #### 🔴 Điểm cấn 1: Schema dữ liệu (Data Schema) lúc cào                                                                                                                   
                                                                                                                                                                             
  • File Đề cương: Đưa ra bảng phẳng gồm 19 trường đã chuẩn hóa (job_id, salary_min, salary_max, seniority, skills_normalized, role_group...).                               
  • File Kiến trúc: Đưa ra cấu trúc JSON 2 phần { "_meta": {...}, "raw": {...} }, trong đó phần raw giữ nguyên văn (kể cả HTML gốc, chuỗi lương "15-25 triệu" chưa tách số). đúng rồi giữ nguyên cho tui phần raw là phải kéo hế nha 
  • 👉 Vấn đề: Nếu bắt 6 crawler của 6 bạn lúc cào phải bóc tách ngay ra 19 trường (tính lương min/max, chuẩn hóa kỹ năng, gán role) thì crawler rất dễ gãy, lỗi cú pháp và  
  không còn dữ liệu gốc để sửa sai.                                                                                                                                          
  • 👉 Phương án giải quyết:                                                                                                                                                 
      • [Lựa chọn 1A - Khuyên dùng]: Tách làm 2 tầng schema chuẩn Data Engineering:                                                                                          
          • Tầng RAW (khi crawler chạy): Bắt buộc lưu schema { "_meta", "raw" } của kien_truc_co_the.md (giữ nguyên gốc, nhẹ, an toàn).                                      
          • Tầng STAGING / CURATED (sau khi cào xong, chạy script làm sạch chung): Chuyển đổi và làm sạch từ raw sang đúng bảng 19 trường của file đề cương để đưa vào huấn  
          luyện mô hình ML.                                                                                                                                                  
      • [Lựa chọn 1B]: Bắt buộc crawler chuẩn hóa và parse thẳng ra 19 trường ngay lúc cào.                                                                                  
                                                                                                                                                                             
  ──────                                                                                                                                                                     
  #### 🔴 Điểm cấn 2: Quy ước phân vùng đường dẫn trên S3 (Partitioning)                                                                                                     
                                                                                                                                                                             
  • File Đề cương: s3://<bucket>/raw/source=<source>/year=YYYY/month=MM/day=DD/ (chuẩn Hive 3 cấp thư mục).                                                                  
  • File Kiến trúc: s3://<bucket>/raw/source=<source>/dt=YYYY-MM-DD/batch_<id>.jsonl (gom ngày thành dt=YYYY-MM-DD).                                                         
  • 👉 Vấn đề: Hai định dạng thư mục khác nhau sẽ khiến script đọc dữ liệu sau này bị lệch path.                                                                             
  • 👉 Phương án giải quyết:                                                                                                                                                 
      • [Lựa chọn 2A]: Dùng source=<source>/dt=YYYY-MM-DD/batch_<id>.jsonl (gọn gàng, dễ quản lý file theo từng batch chạy của 6 máy).                                       
      • [Lựa chọn 2B]: Dùng source=<source>/year=YYYY/month=MM/day=DD/ (chuẩn AWS Athena / Data Lake truyền thống).                                                          
                                                                                                                                                                             
  ──────                                                                                                                                                                     
  #### 🔴 Điểm cấn 3: Tần suất cào (Cadence)                                                                                                                                 
                                                                                                                                                                             
  • File Đề cương: Chạy 3 lần/tuần (Thứ 2, 4, 6), thu thập 1.500–1.800 tin/tuần.                                                                                             
  • File Kiến trúc: Chạy hằng ngày (mỗi tối chạy 1 mẻ nhỏ 100–200 tin/máy), nhờ checkpoint nên máy cá nhân bật lên là chạy tiếp.                                             
  • 👉 Vấn đề: Máy tính sinh viên có thể tắt mở không cố định, nếu đặt lịch cứng 3 lần/tuần mà máy tắt sẽ bị hụt quota.                                                      
  • 👉 Phương án giải quyết:                                                                                                                                                 
      • [Lựa chọn 3A - Khuyên dùng]: Quy định: Linh hoạt hàng ngày, đảm bảo tổng chỉ tiêu tuần. Tức là mỗi thành viên tự lên lịch chạy hàng ngày theo batch nhỏ (100–150     
      tin/lần), miễn sao đạt mốc tối thiểu ~450 tin/người/tuần.                                                                                                              
      • [Lựa chọn 3B]: Cố định đúng 3 ngày (Thứ 2, 4, 6) như đề cương nộp trường.                                                                                            
                                                                                                                                                                             
  ──────                                                                                                                                                                     
  #### 🔴 Điểm cấn 4: Danh sách 6 nguồn tuyển dụng (Xử lý Cloudflare & Nguồn thay thế)                                                                                       
                                                                                                                                                                             
  • File Đề cương & crawlers/README.md: TopDev, LinkedIn, CareerViet, JobsGO, ITviec, TopCV.                                                                                 
  • File Kiến trúc: Nhắc tới cả VietnamWorks là trang dễ cào, đồng thời cảnh báo LinkedIn và TopCV rất khó cào.                                                              
  • Kết quả kiểm tra thực tế:                                                                                                                                                
      • CareerViet, TopDev, ITviec, VietnamWorks: 200 OK, chạy cực kỳ mượt mà với requests + BeautifulSoup.                                                                  
      • JobsGO & TopCV: Bị Cloudflare Turnstile CAPTCHA chặn 403 Forbidden ngay từ đầu (nếu cố bypass sẽ vi phạm quy tắc đạo đức mục 4 trong đề cương).                      
  • 👉 Vấn đề: 6 nguồn hiện tại có 2 nguồn bị WAF khóa chặt, trong khi VietnamWorks rất nhiều tin IT và không bị chặn thì chưa có ai phụ trách.
  • 👉 Phương án giải quyết:
      • [Lựa chọn 4A - Khuyên dùng]: Thay thế JobsGO bằng VietnamWorks. Với TopCV (bạn Thuận phụ trách): Thử nghiệm cào mẫu bằng Playwright/trình duyệt thật hoặc Browser Use +
      Ollama quota nhỏ; các nguồn còn lại gánh bù quota để đạt mốc 10.000 tin.
      • [Lựa chọn 4B]: Giữ nguyên 6 nguồn cũ, dùng Playwright bypass CAPTCHA cho TopCV và JobsGO.
  
  ──────
  #### 🔴 Điểm cấn 5: Tiến độ thời gian (Timeline) & Mốc "Demo Thứ 4"
  
  • File Đề cương: Lộ trình dàn đều 8 tuần (đến tận tuần 8 vẫn đang cào để đạt 10.000 tin).
  • File Kiến trúc: Đẩy nhanh: Cào dứt điểm trong 5 tuần đầu (đạt 10.000 tin ở tuần 5 rồi dừng cào), tuần 6 làm sạch/dedup, tuần 7–8 tập trung làm ML và Báo cáo. Ngoài ra có
  thêm mốc "Demo Thứ 4 Tuần 1" cho giảng viên.
  • 👉 Vấn đề: Nếu tuần 8 mới cào xong thì nhóm chắc chắn không kịp thời gian làm sạch, huấn luyện mô hình ML và làm slide thuyết trình Tuần 9.
  • 👉 Phương án giải quyết:
      • [Lựa chọn 5A - Khuyên dùng]: Lấy timeline của file kiến trúc: Dừng cào ở Tuần 5 (đủ 10.000 tin) để dành trọn vẹn tuần 6, 7, 8 cho Data Cleaning, Feature Engineering,
      Machine Learning và Dashboard. Bổ sung mốc Demo Thứ 4 Tuần 1 vào đề cương để lấy điểm tiến độ với thầy.
      • [Lựa chọn 5B]: Giữ tiến độ cào kéo dài 8 tuần như đề cương cũ.
  
  ──────
  ### Bạn hãy cho biết lựa chọn của bạn cho 5 điểm trên:
  
  • Điểm 1 (Schema): Chọn 1A (2 tầng RAW và Curated) 
  • Điểm 2 (S3 Path): Chọn 2A (dt=YYYY-MM-DD) 
  • Điểm 3 (Lịch chạy): Chọn 3A nhma theo tui nghĩ là mỗi máy sẽ mối cào và cuối tuàn nộp
  • Điểm 4 (Nguồn cào): Chọn 4A (Đưa VietnamWorks vào thay JobsGO/hỗ trợ) 
  • Điểm 5 (Tiến độ): Chọn 5A (Xong cào Tuần 5, có Demo T4) 
  