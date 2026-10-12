# TopDev Crawler (Công Nghệ Thông Tin)

- **Nguồn:** TopDev (https://topdev.vn)
- **API URL:** `https://api.topdev.vn/td/v2/jobs`
- **Công cụ:** requests + BeautifulSoup4
- **Cơ chế:** Thu thập qua REST API công khai
- **Data Contract:** Chuẩn Schema v1 (`JobRecord` với `_meta` và `raw`)

---

## 1. Cách Vận Hành

```bash
# 1. Chạy qua CLI runner (30 tin)
python run.py --source topdev --max-items 30

# 2. Chạy module trực tiếp
python -m crawlers.sources.topdev.crawler --max-items 50
```
