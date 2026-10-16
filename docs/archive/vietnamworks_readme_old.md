# VietnamWorks crawler

- **Owner:** Khoa
- **URL gốc:** https://www.vietnamworks.com
- **Trang listing IT:** `https://www.vietnamworks.com/viec-lam-it-phan-mem-i35-vn`
- **Trang detail:** `https://www.vietnamworks.com/<slug>-<id>-jd`
- **Trạng thái:** Chưa bắt đầu

## Kiểm tra kỹ thuật (2026-10-04)

| Hạng mục | Kết quả |
|---|---|
| `robots.txt` | ✅ Cho phép trang tìm kiếm và detail. Chỉ cấm profile, ứng tuyển, ajax |
| WAF | ✅ Nginx, không có Cloudflare |
| HTTP status | ✅ 200 OK (cả listing lẫn detail) |
| SSR | ✅ Dữ liệu job render sẵn trong HTML |
| Sitemap | ✅ `https://www.vietnamworks.com/sitemap/sitemap.xml` |

## Ghi chú parser

- Listing page trả SSR nhưng có ít anchor tag (~15), cần kiểm tra có API JSON hoặc pagination param không.
- Detail URL có format `/<job-slug>-<id>-jd`, trả HTML ~65KB, chứa đủ thông tin job.
- Cần bỏ tracking params `utm_campaign_navi`, `utm_medium_navi`, `utm_source_navi` khi chuẩn hóa URL.

## Cách chạy

```bash
python run.py --source vietnamworks --max-items 30
```
