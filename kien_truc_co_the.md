# Kế hoạch chốt: kiến trúc và quy trình cào

## 1. Kiến trúc tổng thể (giai đoạn thu thập)

```
6 laptop, mỗi người 1 crawler (Python + requests/BeautifulSoup)
        │  checkpoint, delay, retry, log
        ▼
Ghi file local: data/<source>/dt=YYYY-MM-DD/batch_<id>.jsonl
        │
        ▼  upload tự động (boto3)
AWS S3 (data lake, lớp RAW, chỉ ghi thêm, không sửa)
  s3://<bucket>/raw/source=topdev/dt=2026-10-07/batch_001.jsonl
  s3://<bucket>/raw/source=itviec/dt=.../...
        │
        ▼
Telegram: báo cáo cuối mỗi lần chạy (số tin mới, tổng, lỗi)

[Sau này] Clean/Dedup liên nguồn → Curated (S3 hoặc MongoDB) → EDA → Model
```

Các quyết định cụ thể:

| Hạng mục | Chốt | Lý do |
|---|---|---|
| Định dạng | **JSONL** (mỗi dòng một tin) thay vì một file JSON lớn | Ghi nối thêm được, lỗi giữa chừng không hỏng cả file, đọc bằng pandas/DuckDB/Mongo đều dễ |
| Lưu trữ chính | **S3**, partition theo `source` và `dt` | Cả 6 người cùng ghi mà không đụng nhau |
| MongoDB | **Chưa dùng ở giai đoạn này** | 6 người ghi chung vào một DB cần hạ tầng chung và quản lý quyền. S3 đơn giản hơn. Khi sang phân tích thì nạp vào Mongo (Atlas M0 miễn phí) hoặc dùng DuckDB đọc thẳng JSONL |
| MinIO | **Bỏ qua** | MinIO là "S3 tự dựng trên máy mình", dùng khi không có cloud. Bạn đã có AWS S3 nên không cần. Chỉ hữu ích nếu muốn test upload offline |
| Lịch chạy | Task Scheduler (Windows) hoặc cron (Mac/Linux) trên từng laptop | Miễn phí |

**Lưu ý S3 để không mất tiền:** kiểm tra gói free tier/credit của tài khoản AWS, đặt **Budget alert** ngay. Dữ liệu 10.000 tin toàn văn chỉ vài chục MB nên chi phí lưu trữ gần như bằng 0, nhưng nên có cảnh báo. Mỗi thành viên dùng **IAM user riêng**, chỉ có quyền ghi vào prefix của nguồn mình, và **không commit access key lên git** (dùng file `.env` + `.gitignore`).

## 2. Hợp đồng dữ liệu chung (phần bạn nên giữ chắc)

Bạn cào "tất cả rồi phân tích sau" là ổn, nhưng 6 người cào 6 trang khác nhau thì phải có **khung chung tối thiểu** để sau này gộp được. Mỗi bản ghi gồm hai phần:

```json
{
  "_meta": {
    "source": "topdev",
    "source_job_id": "12345",
    "url": "https://...",
    "dedup_key": "topdev:12345",
    "crawled_at": "2026-10-07T09:30:00+07:00",
    "batch_id": "2026-10-07_topdev_001",
    "crawler_version": "0.1.0"
  },
  "raw": {
    "title": "...", "company": "...", "salary_text": "...",
    "location_text": "...", "skills_text": "...",
    "description_html": "...", "description_text": "...",
    "...mọi trường khác của trang đó, giữ nguyên chữ gốc..."
  }
}
```

- Phần `raw`: mỗi người tự quyết theo trang của mình, **giữ nguyên văn**, không chuẩn hóa (lương vẫn là chuỗi "15-25 triệu").
- Phần `_meta`: **bắt buộc giống nhau** ở cả 6 nguồn.
- Nên lưu thêm `description_html` gốc, vì sau này nếu cần trích lại kỹ năng hoặc yêu cầu thì không phải cào lại.

## 3. Xử lý trùng lặp (yêu cầu của bạn)

Chia hai tầng:

1. **Trùng trong cùng một nguồn (xử lý ngay lúc cào):** mỗi crawler giữ file `seen_ids.txt` (hoặc đọc danh sách ID đã có), chỉ cào tin có `source_job_id`/URL chuẩn hóa chưa gặp. Việc này cũng giúp tiết kiệm request. URL cần chuẩn hóa (bỏ tham số tracking `utm_*`, bỏ dấu `/` cuối).
2. **Trùng giữa các nguồn (xử lý sau, ở lớp curated):** cùng một tin đăng ở ITviec và TopDev. Dùng khóa kiểu hash(công ty chuẩn hóa + tiêu đề chuẩn hóa + địa điểm), có thể bổ sung so khớp gần đúng (fuzzy) sau.

Lớp RAW giữ cả bản trùng, chỉ **gắn dedup_key** để lớp sau loại. Như vậy bạn "không bị trùng" ở dữ liệu cuối mà vẫn không mất dữ liệu gốc.

## 4. Quy trình cào chuẩn cho mỗi crawler

1. Đọc checkpoint (trang/ID đang cào dở, danh sách đã thấy).
2. Lấy danh sách tin (trang listing) → lọc tin mới.
3. Vào từng trang chi tiết, parse bằng BeautifulSoup, ghi một dòng JSONL.
4. Delay ngẫu nhiên 2-5 giây giữa các request, retry có backoff, đặt User-Agent rõ ràng, tôn trọng robots.txt.
5. Ghi checkpoint sau mỗi N tin để mất điện hoặc tắt máy vẫn chạy tiếp được.
6. Kết thúc: upload file lên S3, gửi báo cáo Telegram.
7. Nếu cấu trúc HTML đổi và parse lỗi: ghi cả HTML thô vào thư mục `errors/` và báo Telegram, không bỏ qua im lặng.

Mọi crawler nên chạy theo cùng một giao diện lệnh để bạn điều phối dễ:

```
python run.py --source topdev --max-items 300
```

Phần dùng chung (`crawlers/common/`): HTTP client có delay/retry, ghi JSONL, checkpoint, uploader S3, Telegram notifier, logging. **Bạn nên là người viết (hoặc kiểm duyệt) module này** rồi cả nhóm import dùng, vì đó chính là "điểm lõi" của hệ thống. Các thư mục `crawlers/sources/<tên>/` chỉ cần viết phần parse riêng cho từng trang.

## 5. Tự động chạy theo lịch

Vì là laptop cá nhân (có thể tắt máy), đừng đặt "một lần/tuần". Hãy **chạy ngắn, chạy thường xuyên**, nhờ checkpoint nên lần nào chạy cũng tiếp tục đúng chỗ:

- Mỗi laptop chạy **1 lần/ngày** vào giờ máy hay bật (vd 21:00), mỗi lần có quota (vd 100-200 tin).
- **Windows:** Task Scheduler, thêm tùy chọn "Run task as soon as possible after a scheduled start is missed" để máy tắt thì bật lên là chạy bù.
- **Mac/Linux:** `crontab`, ví dụ `0 21 * * * cd ~/project && python run.py --source topdev --max-items 200`.
- **Rerun một tuần cụ thể:** vì dữ liệu đã partition theo `dt` và `batch_id`, chỉ cần chạy lại với tham số ngày, ghi vào partition tương ứng. Lớp raw append-only nên không mất gì.

## 6. Quota và mốc thời gian

Tính nhanh: cần 10.000 tin unique, cào dư ~30% do trùng → khoảng **13.000 bản ghi raw**, chia 6 nguồn ≈ **2.200 tin/nguồn**. Nếu cào trong 5 tuần thì khoảng **450 tin/nguồn/tuần** (~65 tin/ngày), rất nhẹ nếu delay hợp lý.

Nhưng 6 nguồn **không đều**: trang dễ cào (TopDev, ITviec, CareerViet, VietnamWorks) nên gánh nhiều hơn, trang khó (LinkedIn, TopCV) gánh ít hơn. Đừng chia đều cứng, hãy theo dõi tổng.

| Tuần | Việc chính |
|---|---|
| 1 | Chốt schema `_meta`, viết `common/`, mỗi người xong bản crawler chạy được. **Demo T4**: mẫu dữ liệu từ 6 nguồn trên S3 |
| 2-5 | Cào theo lịch, theo dõi tiến độ qua Telegram, sửa crawler khi trang đổi |
| 5 | Chốt đủ số lượng, dừng cào, kiểm tra chất lượng mẫu |
| 6 | Clean, dedup liên nguồn, đặt bài toán ML từ dữ liệu thực tế |
| 7-8 | EDA, huấn luyện model, báo cáo |

Lưu ý: bạn muốn "phân tích sau", nhưng **bài toán ML nên được chốt muộn nhất ở tuần 3**. Lý do là cách đặt bài toán (ví dụ phân loại vị trí, dự đoán khoảng lương, gom cụm kỹ năng) quyết định bạn có đủ trường dữ liệu hay chưa (nếu dự đoán lương mà 60% tin ghi "thỏa thuận" thì 10.000 mẫu không đủ). Cào xong rồi mới phát hiện thiếu trường thì rất tốn.

## 7. Chuẩn bị demo T4 cho thầy

- Mỗi nguồn có ít nhất vài chục đến vài trăm bản ghi thật trên S3.
- Một bảng đếm số bản ghi theo nguồn (script đếm theo `source`/`dt`).
- 1-2 bản ghi JSON mẫu của mỗi nguồn để thầy thấy dữ liệu thật.
- Sơ đồ kiến trúc (phần 1) và quy trình cào (phần 4).
- Một ảnh chụp thông báo Telegram để minh họa phần giám sát.
- Bước kiểm tra mẫu: script lấy ngẫu nhiên 20 bản ghi/nguồn để bạn đọc bằng mắt.

## 8. Rủi ro cần nói rõ

- **LinkedIn:** phần lớn nội dung cần đăng nhập, điều khoản cấm cào mạnh và hay khóa tài khoản. Nên chỉ cào trang việc làm công khai (không đăng nhập), tốc độ thấp, và chấp nhận quota nhỏ. **Không dùng tài khoản cá nhân** để cào.
- **TopCV và Cloudflare:** mình không hướng dẫn cách vượt/bypass Cloudflare, vì đó là cơ chế bảo vệ mà trang chủ động đặt ra. Nếu trang chặn, các hướng hợp lý là: kiểm tra có sitemap hoặc API công khai không, thử trình duyệt thật (Playwright) với tốc độ như người dùng bình thường, hoặc giảm quota/bỏ nguồn đó và để 5 nguồn còn lại bù vào. Với mục tiêu 10.000 mẫu thì mất một nguồn khó vẫn ổn.
- **Code do agent viết:** cần đọc lại phần delay/retry (agent hay quên hoặc đặt quá nhanh gây bị chặn IP) và đảm bảo không có access key trong code.
- **Dữ liệu cá nhân:** bạn cào hết, nên trong `description` có thể có email/SĐT người đăng. Lớp raw giữ nguyên là ổn cho nội bộ, nhưng **không đẩy S3 ở chế độ public** và không đăng dữ liệu thô lên GitHub.

---

Bạn gửi nốt phần thông tin các nguồn sau cũng được. Bước tiếp theo bạn muốn mình làm trước phần nào: **(a)** viết khung `common/` (schema, checkpoint, uploader S3, Telegram) để cả nhóm dùng chung, hay **(b)** checklist chi tiết cho buổi demo T4?