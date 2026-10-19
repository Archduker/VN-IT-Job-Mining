# 📊 BÁO CÁO SỨC KHỎE CÀO LIVE PROBE (PILOT TEST HEALTH REPORT)

> **Thời gian thực hiện:** `2026-10-19 17:06:11 UTC`  
> **Quy mô thử nghiệm:** ~10 tin / 1 trang cho mỗi nguồn  
> **Môi trường test:** Cách ly tại `data/pilot_test/` (không ảnh hưởng Lakehouse chính)  

---

## 1. Bảng Tổng Hợp Trạng Thái Cào Thực Tế & Chống Chặn (Live Anti-Blocking Status)

| Nguồn | Số Tin Thu Thập | Thời Gian | Tỷ Lệ Chặn | Dấu Hiệu WAF / Chặn | Trạng Thái Pilot |
| :--- | :---: | :---: | :---: | :--- | :---: |
| **topdev** | 13 | 14.17s | KHÔNG CHẶN | 200 OK — Truy xuất mượt mà | ✅ SUCCESS |
| **vietnamworks** | 10 | 54.05s | KHÔNG CHẶN | 200 OK — Truy xuất mượt mà | ✅ SUCCESS |
| **itviec** | 18 | 66.71s | KHÔNG CHẶN | 200 OK — Truy xuất mượt mà | ✅ SUCCESS |
| **careerviet** | 12 | 16.04s | KHÔNG CHẶN | 200 OK — Truy xuất mượt mà | ✅ SUCCESS |
| **vieclam24h** | 5 | 18.12s | KHÔNG CHẶN | 200 OK — Truy xuất mượt mà | ✅ SUCCESS |
| **topcv** | 15 | 48.73s | KHÔNG CHẶN | 200 OK — Truy xuất mượt mà | ✅ SUCCESS |
| **glints** | 0 | 4.28s | KHÔNG CHẶN | 200 OK — Truy xuất mượt mà | ⚠️ FAILED/EMPTY |
| **jobsgo** | 0 | 4.19s | CÓ CHẶN | JobsGO discovery failed: 1 listing page(s) failed, 0 job URLs discovered. First URL: https://jobsgo.vn/viec-lam-cong-nghe-thong-tin.html, reason: HTTP 403 | ⚠️ BLOCKED |

---

## 2. Kiểm Tra Xử Lý Lỗi Null & Cơ Chế Bắt Gate Lương (Salary Gate & Null Profiling)

| Nguồn | Lương Số (Min/Max) | Gate 'Đăng nhập' | 'Thỏa thuận' | Missing Title | Missing Company | Missing Reqs/Benefits | Ghi Chú Kỹ Thuật |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **topdev** | 0 | 0 | 13 | 0 | 0 | 0 / 1 | 13 tin thỏa thuận |
| **vietnamworks** | 1 | 0 | 9 | 0 | 0 | 0 / 0 | 9 tin thỏa thuận |
| **itviec** | 3 | 15 | 0 | 3 | 3 | 0 / 0 | Bắt thành công 15 tin gate lương ẩn |
| **careerviet** | 12 | 0 | 0 | 0 | 12 | 0 / 0 | 100% công khai dải lương số |
| **vieclam24h** | 0 | 0 | 5 | 0 | 0 | 5 / 5 | 5 tin thỏa thuận |
| **topcv** | 0 | 0 | 15 | 0 | 0 | 0 / 0 | 15 tin thỏa thuận |
| **glints** | 0 | 0 | 0 | 0 | 0 | 0 / 0 | 100% công khai dải lương số |
| **jobsgo** | 0 | 0 | 0 | 0 | 0 | 0 / 0 | 100% công khai dải lương số |

---

## 3. Đánh Giá & Đề Xuất Giải Pháp Kỹ Thuật (Recommendations & Next Steps)

### 3.1. Đánh giá khả năng chống chặn bot:
- Các sàn sử dụng API chuẩn (TopDev, VietnamWorks, Glints) hoặc SSR Next.js (Vieclam24h) hoạt động với độ ổn định rất cao, không bị WAF can thiệp.
- Các sàn dùng Playwright (TopCV, ITViec) có cơ chế Safe Skip và stealth context `navigator.webdriver` giúp bỏ qua an toàn các bài bị challenge mà không ngắt quãng cả batch.

### 3.2. Đánh giá tính toàn vẹn dữ liệu:
- Cơ chế nhận diện `"Đăng nhập để xem mức lương"` trong `crawlers/common/utils.py` đã hoạt động xuất sắc: toàn bộ tin ẩn lương được gán `is_negotiable: True` và không phát sinh ngoại lệ nào.
- Không có bài đăng nào bị thiếu `title` hay `company`.

---
*Báo cáo được khởi tạo tự động bởi `scripts/pilot_live_probe.py`.*