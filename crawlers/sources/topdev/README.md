# TopDev crawler

- **Owner:** Sơn
- **URL gốc:** https://topdev.vn
- **Trang listing IT:** `https://topdev.vn/it-jobs`
- **Trang detail:** `https://topdev.vn/detail-jobs/<slug>`
- **Trạng thái:** Chưa bắt đầu

## Kiểm tra kỹ thuật (2026-10-04)

| Hạng mục | Kết quả |
|---|---|
| `robots.txt` | ✅ `Allow: /`, chỉ cấm `/job-seeker/login`, `/employers/search`, `/socket.io` |
| WAF | ⚠️ Cloudflare nhưng không chặn request thường |
| HTTP status | ✅ 200 OK (listing + detail) |
| SSR | ✅ Dữ liệu job render sẵn trong HTML |
| Sitemap | ✅ `https://topdev.vn/sitemap.xml` |

## Cách chạy

```bash
python run.py --source topdev --max-items 30
```
