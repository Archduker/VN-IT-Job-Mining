# PH1. Bộ gold 100 JD và báo cáo profiling (bước 0 + mục 4.1)

> Trạng thái: **đã chốt các điểm cần hỏi (10/11/2026)**; prompt: `docs/prompting/PH1_gold_va_profiling.md`, chờ bạn duyệt. Chưa có code.
> **[ĐỀ XUẤT]** = mình đoán. **[CẦN CHỐT]** = mình không biết.

## 1. Mục tiêu

1. Có số đo hiện trạng cho cả 8 nguồn trước khi sửa tiếp (bước 0).
2. Có bộ gold 100 JD do bạn tự gán, dùng đo bước 3 (IT hay không), bước 5 (parser), bước 7 (section), bước 8 (kỹ năng). Chỉ dùng để đánh giá, không train.

## 2. Phần A. Báo cáo profiling

Theo file thiết kế bước 0:
- `ydata-profiling` trên 500 tin mỗi nguồn (lấy ngẫu nhiên có `seed` cố định) → báo cáo HTML.
- Script đo tỉ lệ thiếu theo trường × nguồn, vẽ heatmap màu.
- Đo thêm: tỉ lệ còn HTML, tỉ lệ NFD, tỉ lệ không dấu.
- Đầu ra: `reports/preprocessing/00_profiling/` (HTML + JSON số liệu) = bảng "trước xử lý".

Mình **không biết** `ydata-profiling` có chạy được với pandas 3.1.1 đang cài; sẽ kiểm lúc cài và báo nếu không (phương án thay thế: chỉ làm heatmap và các tỉ lệ bằng pandas, bỏ HTML của ydata). **[ĐÃ CHỐT]** nếu ydata không chạy được thì thay bằng heatmap và các tỉ lệ bằng pandas.

Nguồn dữ liệu đọc: dữ liệu sau Integration (`data/preprocessing/02_integration/`, đã có trên máy) hoặc làm phẳng trực tiếp từ raw. **[ĐỀ XUẤT]** dùng 02_integration vì đã có cột chuẩn; nhược điểm: đã qua Clean (đã bỏ tin ngoài IT và tin trùng), nên không phản ánh toàn bộ raw. **[ĐÃ CHỐT: đo cả hai]** một báo cáo "trước Clean" (làm phẳng trực tiếp từ raw, mới nhất mỗi `job_id`) và một báo cáo "sau Clean" (`02_integration`), để so được Clean làm thay đổi gì.

## 3. Phần B. Công cụ gán nhãn gold 100 JD

### 3.1. Chọn mẫu
- 100 JD chia 8 nguồn, khoảng 12–13 mỗi nguồn; chọn ngẫu nhiên với `seed` cố định, ghi `seed` và danh sách `job_id` vào file mẫu để tái lập.
- **[ĐÃ CHỐT: trước lọc IT]** (lấy từ raw mới nhất mỗi `job_id`). Nếu chỉ lấy tin đã qua lọc IT thì không đo được "IT hay không IT" ở bước 3. **[ĐỀ XUẤT]** lấy từ tin trước Clean (gồm cả tin ngoài IT) để đo được cả hai.
- Có chèn JD tiếng Anh theo tỉ lệ tự nhiên (khoảng 24,2%) để sau này đo được bước dịch.

### 3.2. Gán gì trên mỗi JD (theo file thiết kế mục 4.1)
| Trường nhãn | Dùng đo | Cách gán trên giao diện |
|---|---|---|
| IT / không IT | bước 3 | 2 nút |
| Lương (min, max, đơn vị, thỏa thuận hay không) | bước 5 | ô nhập, có nút "thỏa thuận" |
| Kinh nghiệm (số năm tối thiểu) | bước 5 | ô số hoặc "không ghi" |
| Cấp bậc (5 cấp hoặc "không rõ") | bước 5 | chọn một |
| Địa điểm (tỉnh trong 34 tỉnh, Remote/Hybrid) | bước 5 | chọn từ danh sách |
| Ranh giới 5 section (`mo_ta / yeu_cau / uu_tien / phuc_loi / khac`) | bước 7 | bôi đen đoạn văn rồi chọn section |
| Kỹ năng (từ taxonomy), mỗi kỹ năng bắt buộc hay ưu tiên | bước 8 | chọn từ gợi ý + gõ thêm |

Nhãn có thể làm dần: lưu từng JD, tiếp tục lần sau. **[CHỐT THEO CÁCH HIỂU CỦA MÌNH, bạn sửa nếu sai]** bạn nói "cách nào làm một cái dùng được nhiều": mình hiểu là gán **đủ 7 trường cho cả 100 JD** (kể cả JD không IT, trường nào JD không có thì để "không ghi") để một bộ nhãn dùng cho mọi bước. Giao diện cho phép bỏ qua trường và đánh dấu "chưa gán".

### 3.3. Công cụ
- Một file `.html` mở trực tiếp trên trình duyệt (không máy chủ), giao diện gọn, nạp file mẫu JSON, xuất file nhãn JSON. Bạn nói "không cần cố định nơi lưu file nhãn": **[ĐỀ XUẤT]** nhãn được tự lưu trong `localStorage` của trình duyệt trong lúc gán và có nút "Xuất JSON" để tải về; bạn tự chọn nơi cất file.
- Tên và vị trí file `.html`: **[ĐỀ XUẤT]** `scripts/gold_labeler.html`; file mẫu sinh bởi `scripts/build_gold_sample.py` (đọc dữ liệu, ghi `data/preprocessing/gold/gold_sample.json`, git-ignore).
- Giao diện: chạy được ở rộng 390 px; phím tắt; hiện tiến độ x/100; hiện JD gốc (HTML đã làm sạch nhẹ) cạnh biểu mẫu; tối/sáng theo hệ thống.
- Không tái dùng `scripts/label_tool.py` cho phần này (nó gán IT/non-IT bằng CSV theo nguồn, khác mục đích); chỉ tham khảo cách đọc dữ liệu.

### 3.4. Cách dùng nhãn về sau
Mỗi phase đo bằng hàm so khớp nhãn gold với đầu ra (đặc tả từng phase ghi rõ). PH1 chỉ làm đến chỗ có file nhãn đúng schema và một hàm đọc/kiểm schema nhãn.

## 4. Tiêu chí xong

- Báo cáo profiling có đủ 8 nguồn, đúng schema, tái lập được (cùng `seed` cho cùng kết quả).
- `gold_sample.json` đủ 100 JD, mỗi nguồn 12–13.
- File `.html` mở được, gán, lưu lại khi tải lại trang, xuất JSON; kiểm trên 390 px.
- Test: kiểm schema nhãn; kiểm `build_gold_sample.py` cho cùng mẫu khi cùng `seed`.
- Bạn gán xong 100 JD (việc của bạn) thì PH1 mới "đóng"; các phase sau dùng được nhãn dần theo tiến độ.

## 5. Không làm

Không tự gán nhãn thay bạn; không dùng model gán nhãn; không ghi dữ liệu lên R2; không đưa nhãn vào git trừ khi bạn nói.
