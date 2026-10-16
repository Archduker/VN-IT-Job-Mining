# ITviec crawler

- **Owner:** Phát
- **URL gốc:** https://itviec.com
- **Trang listing:** `https://itviec.com/viec-lam-it` (toàn quốc, phân trang `?page=2..N`, 20 tin/trang)
  và theo location: `https://itviec.com/viec-lam-it/<location>` (vd `ho-chi-minh`, `ha-noi`, `da-nang`)
- **Trang detail:** `https://itviec.com/viec-lam-it/<slug>`
- **Trạng thái:** ✅ **v0.1 đã implement + unit test OK** (2026-10-05). Đã chạy thử Level 1 (1 tin, JSONL hợp lệ). **CHỜ:** `crawlers/common/` (T-01) và `run.py` (T-02) của Thuận để nối entry point chung; chưa test Level 2 (20–50 tin).

## Kiểm tra kỹ thuật (2026-10-04, xác minh lại 2026-10-05)

| Hạng mục | Kết quả |
|---|---|
| `robots.txt` | ✅ Cực kỳ thoáng: chỉ cấm `/subscriptions/new` (crawler không đụng vào) |
| WAF | ⚠️ Cloudflare nhưng cấu hình mở, không chặn HTTP request |
| HTTP status | ✅ 200 OK (listing + detail + location pages) |
| SSR | ✅ Dữ liệu job render sẵn trong HTML, không cần JS |
| Sitemap | ✅ `https://itviec.com/dunggiatminh.xml` |

## Selector thực tế đang dùng (probe HTML 2026-10-05)

**Listing (`parser.parse_listing`):**
- Card job: `div.job-card` (20 card/trang).
- ID bền nhất: attribute `data-search--job-selection-job-slug-value` trên card → slug.
- Fallback: link tiêu đề `div.job-card h3 a[href]`.
- ⚠️ **Không** lấy mọi anchor trong card: skill tag cũng dẫn tới `/viec-lam-it/<skill>`
  (vd `/viec-lam-it/java?click_source=Skill+tag`) — phải scope vào `h3` / data-attribute.
- URL detail chuẩn hóa bằng `normalize_url()` (bỏ `utm_*`, `lab_feature`, `click_source`,
  fragment, `/` cuối — theo TASKS.md §4.2; giữ param `page` để phân trang).
- `source_job_id`: **slug là định danh ổn định của site** (bám trong URL, không đổi
  theo phiên; `data-job-key` UUID chỉ là impression-tracking theo request nên KHÔNG dùng).
  Layout lạ không lấy được slug → **SHA-256 của URL đã chuẩn hóa** (`stable_job_id()`,
  TASKS.md §4.2 "nếu không có thì hash URL"). `dedup_key = itviec:<source_job_id>`.

**Detail (`parser.parse_detail`):**
- Nguồn chính: **JSON-LD `@type=JobPosting`** (server-render, ổn định nhất). Fields dùng:
  `title`, `datePosted`, `validThrough`, `skills` (chuỗi phẩy), `description` (HTML gốc),
  `employmentType`, `hiringOrganization.name`, `jobLocation[]`, `baseSalary`,
  `jobBenefits`, `experienceRequirements`, `industry`.
- Section render: `div.paragraph` chứa `<h2>` — "Mô tả công việc" / "Yêu cầu công việc" /
  "Tại sao bạn sẽ yêu thích làm việc tại đây" (map substring, không hard-code vị trí).
  Toàn bộ section được giữ nguyên trong `raw.sections_html` để không mất dữ liệu.
- Company link: `a[href*="/nha-tuyen-dung/"]` → `company_url` (href nguyên văn).

## Cấu trúc `raw` — phân loại field theo TASKS.md §4.1

**11 field hợp đồng (đứng trước, đúng tên §4.1):**
`title, company, salary_text, location_text, skills_text, posted_date_text,
employment_type_text, seniority_text, description_html, description_text, requirements_text`

**Field RAW source-specific — nhóm A (nguyên văn từ trang, giữ):**
`company_url, salary_jsonld, job_location, industry, valid_through_text,
experience_requirements_jsonld, requirements_html, benefits_html, benefits_text, sections_html`

**Đã loại khỏi raw (nhóm B/C — 2026-10-05):**
- `skills` (list tách từ `skills_text`) → nhóm B: dẫn xuất/normalized, thuộc
  `skills_normalized` tầng Curated.
- `company_slug` → nhóm B: cắt ra từ URL, dễ suy lại ở ELT.
- `url` → nhóm C: trùng `_meta.url` (chuẩn của contract).
- KHÔNG bao giờ có ở tầng RAW: `salary_min/max`, `role_group`, seniority suy diễn.

## Quy tắc RAW (data contract TASKS.md §4)

- `_meta` đủ 7 khóa chuẩn, `dedup_key = "itviec:<source_job_id>"`, `crawled_at` +07:00.
- `raw` giữ nguyên văn, **không chuẩn hóa downstream**: không tách lương số,
  không normalize location/skills, không suy luận role_group.
- `description_html` = HTML gốc nguyên văn từ JSON-LD của site, **không xóa tag**.
- `description_text` / `requirements_text` / `benefits_text` = plain text sạch
  (strip tags + decode HTML entity — đúng quyền hạn §4.2 của tầng RAW).
- Field text (`title`, `company`, `skills_text`, `salary_text`…): chỉ bỏ khoảng
  trắng thừa đầu/cuối (`_clean_ws`) — không đổi ý nghĩa, không chuẩn hóa nội dung.
- ⚠️ **Salary bị gate đăng nhập — KẾT LUẬN 2026-10-05: KHÔNG tự động đăng nhập.**
  Đã probe `https://itviec.com/sign_in`: form email/password có gắn **reCAPTCHA**
  (`recaptcha_controller`) → tự động hóa login để lấy lương = bypass cơ chế bảo vệ,
  vi phạm quy tắc an toàn của nhóm + điều khoản site. **DỪNG tuyến này.**
  Hiện tại: `salary_text` lưu nguyên văn chuỗi hiển thị (thường `"Đăng nhập để xem
  mức lương"`), `salary_jsonld` lưu `baseSalary` gốc (value có thể obfuscate
  `"You'll love it"`). **Không bịa/tính lương.** Parser đã thiết kế để TỰ ĐỘNG lấy
  lương thật nếu source hiển thị công khai (selector `.salary` không hard-code chuỗi gate).
  Nếu muốn có salary thật, cần quyết định của leader + sự cho phép bằng văn bản của
  ITviec (ví dụ API/đối tác) — không dùng cookie tài khoản tự động hóa trái phép.
  **QUYẾT ĐỊNH 2026-10-05 (Phát): chọn hướng D — bỏ qua authenticated salary.**
  Đã đánh giá: có browser automation nhưng login gắn reCAPTCHA → tự động đăng nhập =
  bypass cơ chế bảo vệ (cấm). Chốt `salary_text` = giá trị gate công khai;
  authenticated salary là **BLOCKER** chờ leader/ITviec, crawler không tự giải quyết.
- ⚠️ **Seniority không tồn tại công khai** trên ITviec → `seniority_text` luôn là `null`
  theo yêu cầu khóa của §4.1. **Không suy diễn** từ title hay `experienceRequirements`.

## Phụ thuộc kiến trúc (báo cáo leader — Thuận)

- `crawlers/common/` **chưa tồn tại trong repo** (task T-01). Trong thời gian chờ,
  `crawler.py` dùng helper nội bộ (HTTP delay 2–5s + retry backoff, checkpoint JSON
  mỗi 10 tin, JSONL append+fsync, validate `_meta`) **viết khớp hành vi đã tài liệu
  hóa** để khi `common/` bàn giao chỉ cần đổi import, không đổi logic. Không tự tạo
  file trong `common/` (đúng rule §3.2).
- `run.py` **chưa tồn tại** (task T-02). `crawler.crawl(max_items, batch_id)` đã sẵn
  sàng để entry point chung gọi kiểu `python run.py --source itviec --max-items 30`.

## Cách chạy

```bash
# Unit tests (không gọi mạng)
python -m unittest discover -s crawlers/sources/itviec/tests -v

# Tạm thời (chưa có run.py) — chạy trực tiếp:
python crawlers/sources/itviec/crawler.py --max-items 1     # Level 1
python crawlers/sources/itviec/crawler.py --max-items 10    # Level 2
python crawlers/sources/itviec/crawler.py --max-items 30    # Level 3 (check pagination/resume)

# Khi run.py của Thuận sẵn:
python run.py --source itviec --max-items 30
```

Output: `data/itviec/dt=YYYY-MM-DD/batch_<seq>.jsonl` (partition theo TASKS.md §7,
đã `.gitignore`). Checkpoint: `data/itviec/checkpoint.json` — chạy lại không cào lại tin
đã thấy. HTML parse lỗi: lưu vào `data/itviec/errors/` + log, không bỏ qua im lặng.

## Ghi chú

- Listing có ~307 job link trên trang kết quả **bao gồm nav/menu links** — thực tế chỉ
  20 `div.job-card` là job; phần còn lại là menu location/skill (đã loại bằng selector scope).
- Chạy 2–5s/request → ~200 tin/batch mất 15–20 phút.
- Tham gia thử nghiệm Browser Use + Ollama cùng Thuận (500 tin, TASKS IT-08) — chưa bắt đầu.
