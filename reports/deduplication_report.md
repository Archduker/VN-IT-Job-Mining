# Deduplication & Record Linkage Report

> **Trạng thái:** Đã xây dựng module và unit tests; ma trận số liệu thực tế sẽ được sinh sau khi chạy trên bảng đã chuẩn hóa. Chưa tuyên bố đạt Precision ≥ 90% khi chưa có bộ cặp thực tế gán nhãn.

## 1. Phạm vi

- **Nội sàn:** phát hiện các bài đăng có khả năng là repost của cùng một vị trí.
- **Xuyên sàn:** liên kết bài đăng tương ứng giữa TopCV, TopDev, VietnamWorks, ITviec, CareerViet, Vieclam24h, Glints và JobsGO.
- **Đầu vào:** bảng phẳng sau Transformation, Text & Skill Processing, Missing Values và Outlier & Quality Rules.
- **Đầu ra:** `cluster_id` và nhãn trùng lặp trên từng bản ghi; sau đó một Golden Record cho mỗi cluster cùng dữ liệu provenance.

## 2. Bệnh án EDA — Trụ cột 3

Đã đối chiếu `collection/reports/EDA_<source>.ipynb` cho cả tám nguồn bằng cùng logic trích xuất như `scripts/read_eda_diagnosis.py`.

| Nguồn | WHAT — phát hiện | Hệ quả cho thuật toán |
|---|---|---|
| CareerViet | EDA ghi nhận 0% trùng vật lý và 0% trùng `job_id`; trùng lặp logic dựa trên `title + company + map` khoảng **10,4%**. Cùng công ty có thể tuyển nhiều slot cùng tiêu đề. | Địa chỉ chi tiết thiếu 34,2%; 13 bản ghi không có `detail-box`. Không gộp chỉ bằng company/title/city; cần bằng chứng JD hoặc skills. |
| Glints | Trùng khóa định danh gần 0 nhờ SHA-256/URL Ledger; trùng lặp logic có thể do tuyển nhiều slot hoặc đăng lại khoảng chu kỳ 14 ngày. | Phân biệt duplicate vật lý với duplicate logic; giữ timestamp và nguồn gốc. |
| ITviec | EDA mô tả pattern tương tự: trùng khóa ID gần 0, nhưng vẫn có nhiều slot hoặc repost theo chu kỳ khoảng 14 ngày; khoảng 74,7% salary UI bị ẩn. | Không dùng title-only hay salary để ghép; cần similarity nội dung hoặc skills. |
| JobsGO | EDA mô tả trùng khóa ID gần 0; logic duplicate có thể do nhiều slot/repost. | Ghép theo khóa chuẩn và kiểm chứng ngữ nghĩa. |
| TopCV | EDA mô tả trùng khóa ID gần 0; logic duplicate có thể do nhiều slot/repost. | Cần ba khóa Blocking và bằng chứng nội dung. |
| TopDev | EDA mô tả trùng khóa ID gần 0; logic duplicate có thể do nhiều slot/repost. | So khớp văn bản JD và danh sách kỹ năng sau chuẩn hóa. |
| Vieclam24h | EDA mô tả trùng khóa ID gần 0; logic duplicate có thể do nhiều slot/repost. | Không sửa Raw As-Is; tránh tự suy diễn khóa bị thiếu. |
| VietnamWorks | EDA mô tả trùng khóa ID gần 0; logic duplicate có thể do nhiều slot/repost. | Mức lương không dùng làm điều kiện chính để ghép bản ghi. |

> Lưu ý: phần mô tả lặp lại ở bảy notebook là chẩn đoán định tính; không được hiểu là đã đo được tỷ lệ trùng chéo thực tế. Các kết quả định lượng phải được sinh từ lần chạy trên dữ liệu đầu vào thực tế.

**Quy mô theo notebook EDA:** CareerViet 599, Glints 331, ITviec 692, JobsGO 1.520, TopCV 1.717, TopDev 2.758, Vieclam24h 619 và VietnamWorks 1.154 (tổng 9.390 bản ghi thô được các notebook mô tả). Đây là quy mô Raw/EDA, không phải số liệu sau chuẩn hóa hoặc kết quả dedup.

EDA-First review kiểm tra Field Inventory, năm trụ cột WHAT—WHY—HOW và Chương 7 của từng notebook. Trụ cột 3 là căn cứ chính về duplicate; Completeness/Validity/Distribution/Bias được dùng để lưu ý thiếu khóa, chất lượng nội dung và tránh dùng salary/skills thô sai cách.

## 3. Quy tắc Record Linkage

1. **Blocking:** `(normalized_company, primary_city, standardized_job_family)`. Nếu một trường khóa không có giá trị đáng tin cậy, bản ghi được giữ riêng và ghi vào `blocking_missing_details`; module không tự bù khóa.
2. **Title matching:** Jaro-Winkler `>= 0.88`. So sánh cả thứ tự gốc và phiên bản token đã sắp xếp để giảm nhạy với cách đảo vị trí từ.
3. **Content matching:** ngoài ngưỡng tiêu đề, ít nhất một trong hai kênh phải có Cosine Similarity `>= 0.88`: (a) JD dùng embedding `all-MiniLM-L6-v2` nếu model đã được cache local; nếu chưa có model, dùng TF-IDF fallback và ghi nhận backend; (b) danh sách kỹ năng dùng TF-IDF cosine.
4. **Clustering:** các cặp đã được xác nhận tạo thành đồ thị; connected components được gán `cluster_id` ổn định. Module liên kết không xóa bất kỳ bản ghi nào.
5. **Hai cấp độ:** `match_type=intra_platform_repost` nếu cùng sàn, `cross_platform_duplicate` nếu khác sàn. Cluster đa nguồn có thêm bản ghi lặp trong cùng sàn được gắn `mixed_intra_and_cross_platform`.

## 4. Golden Record Survivorship

- Ưu tiên cụm thành viên có dải lương số học rõ nhất; không tự parse salary text trong bước này.
- Ưu tiên danh sách skills phong phú nhất, sau đó mô tả JD dài/đầy đủ nhất.
- Hợp nhất các trường list (bao gồm `skills_list`, `benefits_list`) theo cách giữ thứ tự ổn định và loại trùng không phân biệt hoa thường.
- Chọn mô tả/yêu cầu dài nhất cho từng trường văn bản riêng biệt; các trường scalar khác chỉ lấy thành viên khác nếu giá trị của bản ghi đại diện đang thiếu.
- Thêm `is_duplicate`, `duplicate_count`, `source_platforms`, `duplicate_job_ids`, `survivor_job_id` và `duplicate_member_records_json`. Trường JSON này giữ snapshot của tất cả bản ghi thành viên, giúp truy xuất cả giá trị xung đột và ngăn mất thông tin.

`duplicate_count` là số thành viên được đại diện trong cụm, bao gồm cả bản ghi đại diện. Cụm singleton có `duplicate_count=1` và `is_duplicate=False`.

## 5. Ma trận trùng chéo 8 sàn

Ma trận 8 × 8 được sinh bởi `render_deduplication_report(metrics)` sau khi chạy `link_duplicate_records(df)` trên dữ liệu chuẩn hóa. Ma trận gồm:

- **Count:** số cặp đã xác nhận giữa mỗi cặp sàn; đối xứng.
- **Rate:** ma trận theo hướng hàng → cột. Ô `A → B` là tỷ lệ bản ghi của sàn A có ít nhất một cặp trùng đã xác nhận với sàn B, chia cho tổng bản ghi của sàn A. Do mẫu số khác nhau, ma trận tỷ lệ có thể không đối xứng; ma trận Count vẫn đối xứng.
- **Intra-platform rate:** số bản ghi tham gia ít nhất một cặp được xác nhận giữa hai bài cùng sàn, chia cho tổng bản ghi sàn đó. Báo cáo tách riêng count nội sàn và xuyên sàn; một bản ghi có thể tham gia cả hai loại nếu cluster chứa nhiều repost và nhiều nguồn.

**Chưa có số liệu thực tế trong repository hiện tại**, vì bước này chưa được chạy với DataFrame đã qua các bước tiền xử lý trước đó. Không dùng số liệu EDA mô tả để giả làm kết quả thuật toán.

## 6. Tiêu chuẩn nghiệm thu

- Precision cặp trùng `>= 90%` trên bộ cặp mẫu được gán nhãn thủ công. Ngưỡng 0,88 là tham số, không tự chứng minh DoD.
- Không xóa bản ghi đầu vào trong module Linkage.
- Golden Record lưu lại toàn bộ member snapshots trong `duplicate_member_records_json`, hợp nhất list skills/benefits, và cung cấp danh sách nguồn/các ID thành viên.
- Unit tests nằm tại `tests/test_deduplication.py`; sau khi tích hợp vào máy dự án, chạy `pytest tests/ -v`.

## 7. Cách chạy mẫu

```python
from preprocessing.deduplication import link_duplicate_records, resolve_golden_records, render_deduplication_report

linked_df, metrics = link_duplicate_records(normalized_df)
golden_df = resolve_golden_records(linked_df)
with open("reports/deduplication_report.md", "w", encoding="utf-8") as f:
    f.write(render_deduplication_report(metrics))
```
