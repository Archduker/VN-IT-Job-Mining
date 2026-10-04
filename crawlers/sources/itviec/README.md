# ITviec crawler

- **Owner:** Phát
- **URL gốc:** https://itviec.com
- **Trang listing:** `https://itviec.com/viec-lam-it/<location>`
- **Trang detail:** `https://itviec.com/viec-lam-it/<slug>`
- **Trạng thái:** Chưa bắt đầu

## Kiểm tra kỹ thuật (2026-10-04)

| Hạng mục | Kết quả |
|---|---|
| `robots.txt` | ✅ Cực kỳ thoáng: chỉ cấm `/subscriptions/new` |
| WAF | ⚠️ Cloudflare nhưng cấu hình mở, không chặn HTTP request |
| HTTP status | ✅ 200 OK (listing + detail) |
| SSR | ✅ Dữ liệu job render sẵn trong HTML |
| Sitemap | ✅ `https://itviec.com/dunggiatminh.xml` |

## Ghi chú parser

- Listing có ~307 job link trên trang kết quả (bao gồm nav links)
- Detail page chứa đầy đủ mô tả, kỹ năng, công ty
- Tham gia thử nghiệm Browser Use + Ollama cùng Thuận (500 tin)

## Cách chạy

```bash
python run.py --source itviec --max-items 30
```
