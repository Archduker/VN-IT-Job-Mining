# Việc Làm 24h Crawler (Công Nghệ Thông Tin)

- **Nguồn:** Việc Làm 24h (https://vieclam24h.vn)
- **Listing URL:** `https://vieclam24h.vn/tim-kiem-viec-lam-nhanh?career_ids[]=1` (CNTT)
- **Công cụ:** requests + BeautifulSoup4 (bóc tách SSR `__NEXT_DATA__`)
- **Data Contract:** Chuẩn Schema v1 (`JobRecord` với `_meta` và `raw`)

---

## 1. Cách Vận Hành

```bash
# 1. Chạy qua CLI runner (30 tin)
python run.py --source vieclam24h --max-items 30

# 2. Chạy module trực tiếp
python -m crawlers.sources.vieclam24h.crawler --max-items 50
```
