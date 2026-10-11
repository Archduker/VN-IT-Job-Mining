# Kế Hoạch Kiểm Toán & Lộ Trình Merge Chi Tiết (Audit & Merge Action Plan)

> **Mục tiêu**: Báo cáo tổng hợp kết quả kiểm toán 4 nhánh thành viên, thiết lập ma trận đánh giá chất lượng, và đưa ra quy trình merge code chi tiết từng bước cho Nhóm trưởng phê duyệt.  
> **Người lập**: Ban Kiểm Toán & Quản Trị Hệ Thống VN-IT-Job-Mining  
> **Ngày lập**: 11/10/2026

---

## 1. Ma Trận Đánh Giá Chất Lượng 4 Nhánh Thành Viên

| Tiêu Chí Đánh Giá | ITviec (Phát - `a85c815`) | Glints (Duy - `539aaee`) | TopDev (Sơn - `6dc0b52`) | Việc Làm 24h (Phúc - `7681c66`) |
| :--- | :---: | :---: | :---: | :---: |
| **Kế thừa BaseCrawler** |  Chuẩn (Tách class sạch) |  Chuẩn (Đủ checkpoint) |  Chuẩn | ⚠️ Cần sửa lỗi `main()` |
| **Data Contract Schema v1** |  100% Khớp (`JobSalary`, `JobTags`) |  100% Khớp |  Khớp logic bóc tách | ❌ Lỗi `description_list = None` |
| **Độ sạch mã nguồn** |  Rất cao (Modular architecture) |  Cao (Type hints, docstrings) |  Khá | ⚠️ Cần gỡ bỏ hardcode `extra` |
| **Bộ Unit Tests** |  Đầy đủ trong `itviec/tests/` | ⚠️ Có test nhưng sai thư mục |  Chưa có unit test riêng | ❌ Chưa có unit test riêng |
| **Rủi ro xung đột / Dữ liệu** | 🟢 Thấp (Tương thích `run.py`) | 🟢 Thấp (Không đụng code cũ) | 🔴 Cao (Dính file 64k dòng) | 🟡 Trung bình (Cần sửa driver & loop) |
| **Khuyến nghị phê duyệt** | **DUYỆT MERGE NGAY** | **DUYỆT MERGE (SỬA PATH TEST)** | **DUYỆT (LỌC BỎ FILE DATA)** | **SỬA LỖI TRƯỚC KHI MERGE** |

---

## 2. Báo Cáo Phân Tích Kỹ Thuật Từng Web Tương Ứng

Nhóm trưởng có thể xem phân tích kỹ thuật sâu cho từng nguồn tại:
- [`docs/crawl/itviec.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawl/itviec.md) — Báo cáo chi tiết nhánh ITviec của bạn Phát.
- [`docs/crawl/glints.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawl/glints.md) — Báo cáo chi tiết nhánh Glints của bạn Duy.
- [`docs/crawl/topdev.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawl/topdev.md) — Báo cáo chi tiết nhánh TopDev của bạn Sơn.
- [`docs/crawl/vieclam24h.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawl/vieclam24h.md) — Báo cáo chi tiết nhánh Việc Làm 24h của bạn Phúc.
- [`docs/crawl/crawl_data_issues.md`](file:///home/billtran/Desktop/Learning/UTH/VN-IT-Job-Mining/docs/crawl/crawl_data_issues.md) — Nhật ký chi tiết các sự cố và bất thường dữ liệu.

---

## 3. Lộ Trình & Thứ Tự Ưu Tiên Merge Code

Để đảm bảo nhánh `main` luôn hoạt động ổn định và không phát sinh lỗi hồi quy (regression), đề xuất quy trình merge theo thứ tự rủi ro tăng dần:

```
[Nhánh crawl-main]
       │
       ├──► 1. Merge crawl/careerviet (Sau khi refactor xong)
       │
       ├──► 2. Merge crawl/vietnamworks (Sau khi refactor xong)
       │
       ├──► 3. Merge origin/feature/itviec-crawler (Rủi ro thấp nhất, code rất sạch)
       │
       ├──► 4. Merge origin/crawler-glints (Di chuyển test/unit -> tests/unit/)
       │
       ├──► 5. Merge origin/feature/topdev-son (Loại bỏ file batch_001.json 64k dòng)
       │
       ├──► 6. Merge origin/feature/crawler-vieclam24h (Hotfix lỗi main & headless trước khi merge)
       │
       ▼
[Chạy Full Regression Suite pytest tests/]
       ▼
[Fast-Forward / Merge crawl-main -> main]
```

---

## 4. Các Lệnh Git Thực Thi Cho Từng Bước

### Bước 1 & 2: Merge 2 nguồn do Lead refactor
```bash
git checkout crawl-main
git merge crawl/careerviet --no-ff -m "merge: refactor careerviet crawler to schema v1"
git merge crawl/vietnamworks --no-ff -m "merge: refactor vietnamworks crawler to schema v1"
```

### Bước 3: Merge ITviec (Bạn Phát)
```bash
git merge origin/feature/itviec-crawler --no-ff -m "merge: integrate itviec crawler refactor by Phat"
```

### Bước 4: Merge Glints (Bạn Duy) & Chuẩn hóa thư mục test
```bash
git merge origin/crawler-glints --no-ff -m "merge: add glints crawler by Duy"
# Di chuyển test sang tests/unit/
mkdir -p tests/unit
mv test/unit/test_glints_crawler.py tests/unit/test_glints_crawler.py
rm -rf test/
git add tests/unit/test_glints_crawler.py test/
git commit -m "fix(glints): standardize test path to tests/unit/test_glints_crawler.py"
```

### Bước 5: Merge TopDev (Bạn Sơn) & Loại bỏ file 64k dòng
```bash
git merge origin/feature/topdev-son --no-ff -m "merge: topdev parser improvements by Son"
# Loại bỏ file batch_001.json 64k dòng khỏi git index
git rm -f crawlers/sources/topdev/batch_001.json
git commit -m "chore(topdev): remove 64k-line raw json data from git tracking"
```

### Bước 6: Merge Việc Làm 24h (Bạn Phúc) & Hotfix
```bash
git merge origin/feature/crawler-vieclam24h --no-ff -m "merge: integrate vieclam24h crawler by Phuc"
# Áp dụng hotfix: sửa main() loop và headless options
git commit -m "fix(vieclam24h): fix main execution loop and add headless chrome options"
```

---

## 5. Kế Hoạch Xác Minh Hồi Quy Cuối Cùng (Final Verification)
Sau khi hoàn tất toàn bộ 6 bước merge:
```bash
# 1. Kiểm tra toàn bộ unit tests
pytest tests/ -v
pytest crawlers/sources/itviec/tests/ -v

# 2. Kiểm tra DataQualityChecker cho toàn bộ các crawler
python -c "
from crawlers.common.data_quality import DataQualityChecker
import glob
files = glob.glob('crawlers/sources/**/test_5_jobs.json', recursive=True)
for f in files:
    res = DataQualityChecker(f).check()
    print(f, res)
    assert res['passed'] is True
"
```
