Làm việc trực tiếp trong repository VN-IT-Job-Mining. Đọc AGENTS.md áp dụng và
docs/tasks/05_phat_encoding_and_matrices.md trước khi sửa.

Nhiệm vụ: refactor và dọn cấu trúc P5 — Feature Encoding & Matrices để thành viên
tiếp nhận dễ tìm input, entry point, output, EDA và tài liệu bàn giao. Hãy khảo
sát rồi triển khai ngay các thay đổi có căn cứ. Với trường hợp còn thiếu bằng
chứng để xóa, giữ file và ghi rõ lý do trong báo cáo bàn giao.

1. Xác lập baseline từ repo và dữ liệu thực tế

- Kiểm tra git status và bảo toàn thay đổi đang làm của người dùng.
- Đọc execution contract, execution report, artifact manifest, validation report,
  notebook EDA cuối và code sinh artifact. Xác định run bàn giao hiện hành từ
  manifest và file thực tế. Phân biệt output hiện hành, lịch sử và file thử nghiệm.
- Ghi nhận entry point, input P4 thực sự được đọc, cohort ledger, vocabulary,
  artifact chính, artifact phụ bắt buộc và các tham chiếu giữa chúng.
- Dùng rg để kiểm tra import, đường dẫn và tên file trong code, tests, notebook,
  docs, scripts, config, CI và manifest. Kiểm tra cả đường dẫn ghép động từ thư mục
  hoặc run ID. Việc không tìm thấy tên file trong rg chưa đủ căn cứ để xóa.

2. Dọn theo vai trò của từng file

- Giữ luồng chạy P5 chính, test, vocabulary đã chốt, cohort ledger, manifest,
  validation và mọi file còn cần cho tái lập hoặc truy vết quyết định.
- Hợp nhất tài liệu trùng nội dung vào một điểm bắt đầu bàn giao P5. Ưu tiên cập
  nhật tài liệu hiện có. Từ đó dẫn tới lệnh chạy, đầu vào, artifact, notebook
  và phần lịch sử cần giữ.
- Dọn file tạm, bản sao dư thừa hoặc script thử nghiệm đã hết vai trò sau khi xác
  minh không còn tham chiếu, không phải đầu ra bắt buộc và không chứa bằng chứng
  duy nhất. Nếu file sinh tự động có thể tái tạo, xác minh lệnh tái tạo trước khi dọn.
- Rà preprocessing/encoding/ để tìm xử lý trùng với P4. Chỉ gỡ nhánh cũ khi
  chứng minh được nguồn dữ liệu chính thức, các caller và hành vi tương đương
  trên input hiện hành. Các bước validate schema hoặc chuyển đổi phục vụ riêng
  cho encoding có thể vẫn cần thiết dù trông giống xử lý P4.
- Kiểm tra toàn repo để cập nhật liên kết bị ảnh hưởng. Giới hạn việc sửa ngoài
  P5 ở các điểm tích hợp liên quan. Giữ nguyên dữ liệu nguồn P4, dữ liệu trên R2
  và các file thuộc nhiệm vụ khác.
- Nếu di chuyển file mà manifest, notebook hoặc script tham chiếu, cập nhật
  đồng bộ các bên sử dụng và kiểm tra lại khả năng truy vết. Ưu tiên giữ ổn định
  đường dẫn đầu ra mà nhóm đã thống nhất.

3. Bảo toàn hợp đồng đầu ra và kiểm chứng sau refactor

- Đối chiếu bốn đầu ra theo nhiệm vụ P5:
  data/curated/curated_flat_golden_jobs.parquet
  data/preprocessing/05_encoding/skill_cooccurrence.parquet
  data/preprocessing/05_encoding/features.parquet
  data/preprocessing/05_encoding/encoding_dictionary.json
  Tái sử dụng artifact hiện có nếu đúng vai trò và hợp đồng. Giữ các artifact
  TF-IDF, mapping hàng và metadata mà pipeline hoặc bàn giao còn sử dụng.
- Kiểm tra multi-hot có đúng 230 cột nhị phân. Co-occurrence có kích thước
  230 × 230, dùng cùng vocabulary và thứ tự. Kiểm tra alignment theo
  job_id_global, số dòng, coverage và checksum theo run hiện hành.
- Chạy test P5 và kiểm tra luồng đọc artifact qua entry point thực tế. Nếu cần
  tái tạo output để kiểm chứng, dùng thư mục tạm để so sánh với bản bàn giao.
- Dùng môi trường dự án Python 3.14.4. Restart Kernel rồi Run All notebook EDA
  cuối để kiểm tra tìm repo root, import package và thứ tự tạo biến như covered.
  Nếu notebook hoặc đường dẫn nguồn thay đổi, kiểm tra lại bản HTML bàn giao.
- Chỉ cập nhật trạng thái nghiệm thu khi có kết quả kiểm chứng tương ứng.
  Nếu thiếu dữ liệu, dependency hoặc quyền truy cập, ghi cụ thể mục chưa xác minh.
  Giữ nguyên vocabulary, cohort và logic nghiệp vụ trong đợt refactor này.

4. Báo cáo kết quả

Trong tài liệu bàn giao hiện có, cập nhật cây thư mục rút gọn và đường dẫn bắt
đầu cho người tiếp nhận. Khi trả kết quả, liệt kê file đã xóa, di chuyển hoặc hợp
nhất kèm lý do, các file trông dư nhưng phải giữ và các kiểm tra đã chạy cùng kết
quả. Với mọi thay đổi có thể ảnh hưởng người dùng downstream, ghi rõ đường dẫn
cũ và mới hoặc cách gọi mới.
