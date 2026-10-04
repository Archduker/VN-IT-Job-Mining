# TopCV crawler

- **Owner:** Thuận
- **URL gốc:** https://www.topcv.vn
- **Trang listing IT:** `https://www.topcv.vn/tim-viec-lam-cong-nghe-thong-tin-cr257`
- **Trạng thái:** Chưa bắt đầu

## Kiểm tra kỹ thuật (2026-10-04)

| Hạng mục | Kết quả |
|---|---|
| `robots.txt` | ✅ Cho phép trang tìm kiếm (chỉ cấm CV, profile) |
| WAF | ❌ **Cloudflare Turnstile** — chặn mọi request tự động (HTTP 403) |
| HTTP status | ❌ 403 Forbidden (cả listing, detail, sitemap) |
| Headless Chrome | ❌ Cũng bị chặn bởi Cloudflare Challenge |

## Phương án xử lý

- **Không dùng** requests + BS4 (bị chặn 100%)
- Thử **Playwright** với profile trình duyệt thật, tốc độ như người dùng bình thường
- Thử **Browser Use + Ollama** (nhánh thử nghiệm cùng Phát)
- Quota giảm: chỉ cào ~1.000 tin (các nguồn khác gánh bù)
- **Tuyệt đối không bypass CAPTCHA** — tuân thủ quy tắc đạo đức dự án

## Cách chạy

```bash
python run.py --source topcv --max-items 30
```
