# JobsGO Crawler (Công Nghệ Thông Tin)

- **Nguồn:** JobsGO (https://jobsgo.vn)
- **Trang listing IT:** `https://jobsgo.vn/viec-lam-cong-nghe-thong-tin.html`
- **Phân trang:** `?page=2`, `?page=3` ... cho đến trang cuối cùng
- **Trang detail:** `https://jobsgo.vn/viec-lam/<slug>-<id>.html`
- **Công cụ:** Playwright Chrome (Stealth) + BeautifulSoup4
- **Data Contract:** Chuẩn TopCV (`JobRecord` với `_meta` và `raw`)

---

## 1. Kiểm Tra Kỹ Thuật & Phòng Vệ (Anti-bot)

| Hạng mục | Kết quả & Giải pháp |
|---|---|
| **WAF / Anti-Bot** | ⚠️ Cloudflare Turnstile (`Just a moment...` / HTTP 403 khi dùng HTTP client thông thường) |
| **Giải pháp Vượt WAF** | ✅ Playwright Headless Chrome với `--disable-blink-features=AutomationControlled` và init script `navigator.webdriver = undefined` |
| **Phân trang** | ✅ Nhận diện `ul.pagination li.next.disabled` để tự động kết thúc ở trang cuối cùng |
| **Làm sạch URL** | Bỏ tracking query parameters (`ref_component=job_list__item`) giữ lại URL định danh chuẩn |
| **Lưu trữ HTML** | Hỗ trợ cờ `--save-html` (mặc định tắt `False` để tối ưu dung lượng) |

---

## 2. Ánh Xạ Schema & Thuộc Tính Mở Rộng (`extra`)

- **Mức lương (`salary`)**: Chuẩn hoá cấu trúc lồng nhau `JobSalary` (`salary_min`, `salary_max`, `salary_currency`, `pay_period`, `is_negotiable`, `has_commission`).
- **Thẻ tags (`tags`)**:
  - `skills`: Danh sách chip kỹ năng (`API Testing`, `Postman`, `Selenium`...).
  - `requirements`: `null`.
  - `benefits`: `null` (Quy tắc bắt buộc: Nếu không có badge nhóm quyền lợi riêng, đặt `null`, không đưa văn bản dài vào thẻ).
- **Làm sạch dòng (`list[str]`)**: `description_list`, `requirements_list`, `benefits_list` được làm sạch triệt để ký tự bullet (`•`, `-`, `*`).
- **Trường mở rộng (`extra`)**:
  - `work_schedule`: Thời gian làm việc (ví dụ: `Từ Thứ 2 đến Thứ 6 (08:00 - 17:00)`).
  - `education`: Bằng cấp yêu cầu (ví dụ: `Đại Học trở lên`).
  - `experience`: Kinh nghiệm yêu cầu (ví dụ: `1 - 2 năm`).
  - `hiring_quantity`: Số lượng tuyển (ví dụ: `3`).
  - `industry`: Lĩnh vực hoạt động công ty.
  - `company_address`: Địa chỉ trụ sở công ty.
  - `career`: Ngành nghề tuyển dụng.
  - `detailed_location`: Địa điểm làm việc chi tiết.

---

## 3. Cách Vận Hành

```bash
# 1. Chạy qua CLI runner (Mặc định 5 tin)
python run.py --source jobsgo --max-items 5

# 2. Chạy cào toàn bộ danh sách cho đến trang cuối cùng
python run.py --source jobsgo --max-items 0

# 3. Chạy trực tiếp module crawler
python -m crawlers.sources.jobsgo.crawler --max-items 10

# 4. Kiểm tra chất lượng dữ liệu (Data Quality Check)
python -c "
from crawlers.common.data_quality import DataQualityChecker
checker = DataQualityChecker('crawlers/sources/jobsgo/test_5_jobs.json')
result = checker.check()
assert result['passed'] is True
print('✅ Data Quality Check: PASSED')
"
```
