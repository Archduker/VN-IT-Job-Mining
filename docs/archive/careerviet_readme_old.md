# CareerViet crawler

- **Owner:** Tài
- **URL gốc:** https://careerviet.vn
- **Trang listing IT:** `https://careerviet.vn/viec-lam/cntt-phan-mem-c1-vi.html`
- **Trang detail:** `https://careerviet.vn/vi/tim-viec-lam/<slug>.<id>.html`
- **Trạng thái:** Chưa bắt đầu

## Kiểm tra kỹ thuật (2026-10-04)

| Hạng mục | Kết quả |
|---|---|
| `robots.txt` | ✅ Cho phép bot thường. Chỉ cấm trang lưu/in CV, API nội bộ |
| WAF | ✅ OpenResty, không có Cloudflare |
| HTTP status | ✅ 200 OK (listing + detail) |
| SSR | ✅ 50 thẻ tin/trang render sẵn trong HTML |
| Sitemap | ✅ `https://careerviet.vn/sitemap/sitemap.xml` |

## Ghi chú parser

- Listing trả 100 job link (50 thường + 50 premium)
- Detail link: `/vi/tim-viec-lam/<slug>.<id>.html`

## Cách chạy

```bash
python run.py --source careerviet --max-items 30
```
