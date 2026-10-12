# TopCV Crawler (Công Nghệ Thông Tin)

- **Nguồn:** TopCV (https://www.topcv.vn)
- **Trang listing IT:** `https://www.topcv.vn/tim-viec-lam-cong-nghe-thong-tin-cr257`
- **Công cụ:** Playwright Chrome Headless + BeautifulSoup4
- **Cơ chế thu thập:** 2 giai đoạn (Listing -> Detail)
- **Data Contract:** Chuẩn Schema v1 (`JobRecord` với `_meta` và `raw`)

---

## 1. Phòng Vệ Anti-bot & Vượt Cloudflare

- **Thách thức:** TopCV áp dụng Cloudflare Challenge (`Attention Required!`).
- **Giải pháp:** Playwright Chrome với cờ `--disable-blink-features=AutomationControlled`, `--no-sandbox`, User-Agent chuẩn và context sạch cho từng trang chi tiết.
- **Hỗ trợ chạy Offline:** Tùy chọn `--local-html-dir` cho phép nạp các file HTML đã tải sẵn để parse tức thì không cần mạng.

---

## 2. Cách Vận Hành

```bash
# 1. Chạy qua CLI runner (5 tin)
python run.py --source topcv --max-items 5

# 2. Chạy module trực tiếp
python -m crawlers.sources.topcv.crawler --max-items 10

# 3. Chạy với thư mục HTML offline
python -m crawlers.sources.topcv.crawler --local-html-dir path/to/htmls
```
