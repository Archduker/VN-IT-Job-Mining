# Phân công công việc — Giai đoạn Thu thập Dữ liệu

> **Cập nhật:** 2026-10-04
> **Người điều phối:** Thuận (Leader)
> **Repo:** [Archduker/VN-IT-Job-Mining](https://github.com/Archduker/VN-IT-Job-Mining)

---

## 1. Mô hình triển khai

```text
┌─────────────────────────────────────────────────────────────┐
│  Mỗi thành viên (laptop cá nhân)                           │
│  ┌───────────────────────────────────┐                      │
│  │ 1. Viết crawler cho nguồn mình    │                      │
│  │ 2. Test local (chạy thử 20-50 tin)│                      │
│  │ 3. Push code lên GitHub (branch)  │                      │
│  └────────────────┬──────────────────┘                      │
│                   │ git push                                │
│                   ▼                                         │
│  ┌───────────────────────────────────┐                      │
│  │ GitHub repo (main branch)         │                      │
│  │  - Thuận review & merge PR        │                      │
│  └────────────────┬──────────────────┘                      │
│                   │ git pull                                │
│                   ▼                                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ EC2 / VPS (Thuận quản lý)                             │  │
│  │  - Cron chạy 6 crawler theo lịch (batching)           │  │
│  │  - Ghi JSONL local → upload S3 Raw Zone               │  │
│  │  - Gửi báo cáo Telegram sau mỗi batch                │  │
│  │  - Script ELT: Raw → Staging → Curated                │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Tóm tắt:** Mỗi bạn chỉ cần **viết code crawler + push GitHub**. Thuận sẽ pull code về EC2 và chạy tự động tất cả 6 nguồn trên một máy chủ duy nhất.

---

## 2. Phân công nguồn

| Nguồn | Thư mục | Người phụ trách | Công cụ crawl | Mức độ khó | Quota dự kiến |
|---|---|---|---|---|---|
| TopDev | `crawlers/sources/topdev/` | **Sơn** | `requests` + BS4 | ⭐ Dễ | 2.500 tin |
| CareerViet | `crawlers/sources/careerviet/` | **Tài** | `requests` + BS4 | ⭐ Dễ | 2.500 tin |
| ITviec | `crawlers/sources/itviec/` | **Phát** | `requests` + BS4 | ⭐ Dễ | 2.500 tin |
| VietnamWorks | `crawlers/sources/vietnamworks/` | **Khoa** | `requests` + BS4 | ⭐ Dễ | 2.500 tin |
| TopCV | `crawlers/sources/topcv/` | **Thuận** | Playwright / Browser Use | ⭐⭐⭐ Khó (Cloudflare) | 1.000 tin |
| _Chưa chốt_ | `crawlers/sources/<tên>/` | **Phúc** | _Tùy nguồn_ | _Tùy nguồn_ | 2.000 tin |

> **⚠️ Phúc cần chọn nguồn mới** (LinkedIn bị ToS cấm cào + dễ khóa tài khoản).
> Gợi ý: `vieclam24h.vn`, `mywork.com.vn`, `timviecnhanh.com`, hoặc nguồn khác mà Phúc thấy phù hợp.
> Phúc hãy check `robots.txt` + thử `curl` trước rồi báo lại nhóm.

**Nhánh thử nghiệm Browser Use + Ollama:** Thuận + Phát phối hợp, mục tiêu 1.000 tin từ ITviec + TopCV để so sánh với parser truyền thống.

---

## 3. Quy trình làm việc trên GitHub

### 3.1 Cấu trúc branch

```text
main                          ← code đã review, ổn định
├── feature/common            ← Thuận viết module dùng chung
├── feature/topdev            ← Sơn
├── feature/careerviet        ← Tài
├── feature/itviec            ← Phát
├── feature/vietnamworks      ← Khoa
├── feature/topcv             ← Thuận
└── feature/<nguon-phuc>      ← Phúc
```

### 3.2 Quy trình nộp code

1. **Clone repo** (lần đầu):
   ```bash
   git clone https://github.com/Archduker/VN-IT-Job-Mining.git
   cd VN-IT-Job-Mining
   ```

2. **Tạo branch riêng** (chỉ 1 lần):
   ```bash
   git checkout -b feature/<tên-nguồn>
   ```

3. **Code trong đúng thư mục của mình:**
   ```
   crawlers/sources/<tên-nguồn>/
   ├── crawler.py          # Logic cào (listing + detail)
   ├── parser.py           # Parse HTML → dict
   ├── config.py           # URL gốc, headers, delay, max_items
   ├── README.md           # Ghi chú nguồn: robots.txt, cách chạy, lưu ý
   └── tests/              # (Tùy chọn) test thử parse
   ```

4. **Test local** (chạy thử 20–50 tin, kiểm tra output JSONL):
   ```bash
   python run.py --source <tên-nguồn> --max-items 30
   ```

5. **Commit & push:**
   ```bash
   git add crawlers/sources/<tên-nguồn>/
   git commit -m "feat(<tên-nguồn>): hoàn thành crawler v0.1"
   git push origin feature/<tên-nguồn>
   ```

6. **Tạo Pull Request trên GitHub** → tag Thuận review.

7. **Thuận merge** vào `main` → pull về EC2 → chạy tự động.

> **Quy tắc:** Chỉ sửa file trong thư mục nguồn của mình. **KHÔNG** sửa `crawlers/common/`, `README.md`, hay file của người khác. Nếu cần sửa `common/` thì báo Thuận.

---

## 4. Hợp đồng dữ liệu (Data Contract)

### 4.1 Schema RAW — Bắt buộc mỗi crawler xuất đúng format này

Mỗi dòng trong file JSONL phải có cấu trúc:

```json
{
  "_meta": {
    "source": "topdev",
    "source_job_id": "abc123",
    "url": "https://topdev.vn/detail-jobs/abc123",
    "dedup_key": "topdev:abc123",
    "crawled_at": "2026-10-07T21:00:00+07:00",
    "batch_id": "2026-10-07_topdev_001",
    "crawler_version": "0.1.0"
  },
  "raw": {
    "title": "Senior Backend Developer",
    "company": "FPT Software",
    "salary_text": "15-25 triệu",
    "location_text": "Hồ Chí Minh",
    "skills_text": "Java, Spring Boot, MySQL",
    "posted_date_text": "03/10/2026",
    "employment_type_text": "Full-time",
    "seniority_text": "Senior",
    "description_html": "<div>...</div>",
    "description_text": "Mô tả công việc bằng text thuần...",
    "requirements_text": "Yêu cầu ứng viên..."
  }
}
```

### 4.2 Quy tắc bắt buộc

| Quy tắc | Chi tiết |
|---|---|
| Phần `_meta` | **Bắt buộc giống nhau** cả 6 nguồn. Dùng module `common/schema.py` để validate |
| Phần `raw` | Mỗi nguồn **tự quyết** theo cấu trúc HTML riêng. **Giữ nguyên văn gốc**, không chuẩn hóa |
| `source_job_id` | Mã duy nhất trên trang gốc (ID trong URL hoặc trên trang). Nếu không có thì hash URL |
| `dedup_key` | `"<source>:<source_job_id>"` — dùng để khử trùng tầng 1 |
| `description_html` | **Bắt buộc lưu** HTML gốc. Sau này cần trích lại kỹ năng thì không phải cào lại |
| `description_text` | Text thuần (strip tags). Dùng cho ML |
| URL | Chuẩn hóa: bỏ `utm_*`, bỏ dấu `/` cuối, bỏ fragment `#` |
| Delay | **2–5 giây ngẫu nhiên** giữa các request. Dùng `common/http_client.py` |
| Checkpoint | Ghi checkpoint sau mỗi 10 tin. Dùng `common/checkpoint.py` |

### 4.3 Hai tầng schema

```text
Tầng RAW (crawler viết)          Tầng CURATED (Thuận chạy script ELT)
─────────────────────────         ──────────────────────────────────────
{ "_meta": {...},                 { "job_id": "...",
  "raw": {                          "source": "topdev",
    "title": "...",                  "job_url": "https://...",
    "salary_text": "15-25M",         "job_title": "...",
    "location_text": "HCM",          "salary_min": 15000000,
    ...                               "salary_max": 25000000,
  }                                   "location": "Ho Chi Minh City",
}                                     "skills_normalized": ["Java", ...],
                                      "role_group": "Backend",
Mỗi crawler chỉ lo tầng này.         ...
                                  }
                                  Script ELT chung sẽ chuẩn hóa.
```

---

## 5. Cấu trúc thư mục dự án

```text
VN-IT-Job-Mining/
├── README.md
├── TASKS.md                          ← File này
├── requirements.txt
├── run.py                            ← Entry point chung: python run.py --source topdev
├── crawlers/
│   ├── README.md
│   ├── common/                       ← Module dùng chung (Thuận viết)
│   │   ├── __init__.py
│   │   ├── http_client.py            # requests session + delay + retry + User-Agent
│   │   ├── checkpoint.py             # Đọc/ghi checkpoint (seen_ids, last_page)
│   │   ├── jsonl_writer.py           # Ghi file JSONL an toàn (append, flush)
│   │   ├── s3_uploader.py            # Upload batch lên S3 (boto3)
│   │   ├── telegram_notifier.py      # Gửi báo cáo sau mỗi batch
│   │   ├── schema.py                 # Validate schema _meta + raw
│   │   └── utils.py                  # URL normalize, hash, logging
│   └── sources/
│       ├── topdev/                   # Sơn
│       │   ├── crawler.py
│       │   ├── parser.py
│       │   ├── config.py
│       │   └── README.md
│       ├── careerviet/               # Tài
│       ├── itviec/                   # Phát
│       ├── vietnamworks/             # Khoa
│       ├── topcv/                    # Thuận
│       └── <nguon-phuc>/             # Phúc (chờ chốt)
├── etl/                              ← Script ELT (Thuận viết, chạy sau khi cào)
│   ├── raw_to_staging.py
│   ├── staging_to_curated.py
│   └── dedup.py
├── data/                             ← Dữ liệu local (gitignore, không push)
│   └── <source>/dt=YYYY-MM-DD/
├── docs/
│   ├── vietnam_it_recruitment_data_mining_project.md
│   └── kien_truc_co_the.md
└── .env.example                      ← Mẫu file biến môi trường (không chứa key thật)
```

---

## 6. Task chi tiết theo từng người

---

### 🔧 Thuận — Leader / Infra / TopCV

**Vai trò:** Setup hạ tầng, viết module `common/`, quản lý EC2, review code, crawl TopCV.

| # | Task | Deadline | Trạng thái |
|---|---|---|---|
| T-01 | Viết module `crawlers/common/` (http_client, checkpoint, jsonl_writer, schema, s3_uploader, telegram_notifier) | Tuần 1 — T4 | ⬜ |
| T-02 | Viết `run.py` entry point chung (`python run.py --source <tên> --max-items N`) | Tuần 1 — T4 | ⬜ |
| T-03 | Viết `.env.example` + hướng dẫn cấu hình AWS credentials | Tuần 1 — T4 | ⬜ |
| T-04 | Setup EC2/VPS: cài Python, clone repo, cấu hình cron, test chạy thử | Tuần 1 — CN | ⬜ |
| T-05 | Setup S3 bucket + IAM policy + Budget Alert | Tuần 1 — T4 | ⬜ |
| T-06 | Setup Telegram Bot + channel thông báo nhóm | Tuần 1 — T4 | ⬜ |
| T-07 | Viết crawler TopCV (Playwright / Browser Use + Ollama) | Tuần 2 | ⬜ |
| T-08 | Review & merge PR của 5 thành viên | Tuần 1–2 (ongoing) | ⬜ |
| T-09 | Cấu hình cron trên EC2 chạy 6 crawler tự động (batching) | Tuần 2 | ⬜ |
| T-10 | Viết script ELT: `raw_to_staging.py`, `staging_to_curated.py`, `dedup.py` | Tuần 4–5 | ⬜ |
| T-11 | Thử nghiệm Browser Use + Ollama (cùng Phát, 1.000 tin) | Tuần 3–4 | ⬜ |
| T-12 | Chuẩn bị demo T4 Tuần 1 cho giảng viên | Tuần 1 — T4 | ⬜ |

---

### 🟢 Sơn — TopDev

**Nguồn:** https://topdev.vn | **Công cụ:** `requests` + BeautifulSoup | **Quota:** 2.500 tin

| # | Task | Deadline | Trạng thái |
|---|---|---|---|
| S-01 | Đọc `robots.txt` của TopDev, ghi lại các URL được phép vào `README.md` | Tuần 1 — T3 | ⬜ |
| S-02 | Phân tích cấu trúc HTML trang listing (`/it-jobs`) và trang detail (`/detail-jobs/...`) | Tuần 1 — T4 | ⬜ |
| S-03 | Viết `parser.py`: parse listing page → danh sách URL detail | Tuần 1 — T5 | ⬜ |
| S-04 | Viết `parser.py`: parse detail page → dict theo schema `_meta` + `raw` | Tuần 1 — T6 | ⬜ |
| S-05 | Viết `crawler.py`: tích hợp `common/` (http_client, checkpoint, jsonl_writer) | Tuần 1 — T7 | ⬜ |
| S-06 | Viết `config.py`: URL gốc, headers, delay (2–5s), max_items | Tuần 1 — T7 | ⬜ |
| S-07 | Test local: chạy `python run.py --source topdev --max-items 30`, kiểm tra JSONL output | Tuần 1 — CN | ⬜ |
| S-08 | Tạo Pull Request, tag Thuận review | Tuần 1 — CN | ⬜ |
| S-09 | Sửa bug nếu Thuận báo lỗi khi chạy trên EC2 | Tuần 2 (ongoing) | ⬜ |

**Ghi chú kỹ thuật TopDev:**
- Trang listing: `https://topdev.vn/it-jobs` (SSR, có dữ liệu trong HTML)
- Trang detail: `https://topdev.vn/detail-jobs/<slug>` (SSR, trả 200 OK)
- Nằm sau Cloudflare nhưng **không chặn** request bình thường
- Pagination: kiểm tra URL param `?page=2`, `?page=3`...

---

### 🟢 Tài — CareerViet

**Nguồn:** https://careerviet.vn | **Công cụ:** `requests` + BeautifulSoup | **Quota:** 2.500 tin

| # | Task | Deadline | Trạng thái |
|---|---|---|---|
| CV-01 | Đọc `robots.txt` của CareerViet, ghi lại các URL được phép vào `README.md` | Tuần 1 — T3 | ⬜ |
| CV-02 | Phân tích HTML listing (`/viec-lam/cntt-phan-mem-c1-vi.html`) và detail (`/vi/tim-viec-lam/<slug>.html`) | Tuần 1 — T4 | ⬜ |
| CV-03 | Viết `parser.py`: listing → danh sách URL detail | Tuần 1 — T5 | ⬜ |
| CV-04 | Viết `parser.py`: detail → dict schema `_meta` + `raw` | Tuần 1 — T6 | ⬜ |
| CV-05 | Viết `crawler.py` + `config.py` | Tuần 1 — T7 | ⬜ |
| CV-06 | Test local 30 tin, kiểm tra JSONL | Tuần 1 — CN | ⬜ |
| CV-07 | Tạo PR tag Thuận | Tuần 1 — CN | ⬜ |
| CV-08 | Fix bug khi chạy trên EC2 | Tuần 2 (ongoing) | ⬜ |

**Ghi chú kỹ thuật CareerViet:**
- Không có Cloudflare, server OpenResty, **rất dễ cào**
- Listing trả đủ 50 thẻ tin/trang trong HTML (SSR)
- Detail link dạng: `/vi/tim-viec-lam/<slug>.<id>.html`
- Có 100 job link trên mỗi trang listing (50 thường + 50 premium)

---

### 🟢 Phát — ITviec

**Nguồn:** https://itviec.com | **Công cụ:** `requests` + BeautifulSoup | **Quota:** 2.500 tin

| # | Task | Deadline | Trạng thái |
|---|---|---|---|
| IT-01 | Đọc `robots.txt` của ITviec, ghi vào `README.md` | Tuần 1 — T3 | ⬜ |
| IT-02 | Phân tích HTML listing (`/viec-lam-it/...`) và detail | Tuần 1 — T4 | ⬜ |
| IT-03 | Viết `parser.py`: listing + detail | Tuần 1 — T5–T6 | ⬜ |
| IT-04 | Viết `crawler.py` + `config.py` | Tuần 1 — T7 | ⬜ |
| IT-05 | Test local 30 tin, kiểm tra JSONL | Tuần 1 — CN | ⬜ |
| IT-06 | Tạo PR tag Thuận | Tuần 1 — CN | ⬜ |
| IT-07 | Fix bug khi chạy trên EC2 | Tuần 2 (ongoing) | ⬜ |
| IT-08 | Phối hợp Thuận thử nghiệm Browser Use + Ollama trên ITviec (500 tin) | Tuần 3–4 | ⬜ |

**Ghi chú kỹ thuật ITviec:**
- Cloudflare cấu hình mở, **không chặn** request HTTP
- `robots.txt` rất thoáng: chỉ cấm `/subscriptions/new`
- SSR, dữ liệu job nằm sẵn trong HTML
- Có sitemap: `https://itviec.com/dunggiatminh.xml`

---

### 🟢 Khoa — VietnamWorks

**Nguồn:** https://www.vietnamworks.com | **Công cụ:** `requests` + BeautifulSoup | **Quota:** 2.500 tin

| # | Task | Deadline | Trạng thái |
|---|---|---|---|
| VW-01 | Đọc `robots.txt` của VietnamWorks, ghi vào `README.md` | Tuần 1 — T3 | ⬜ |
| VW-02 | Phân tích HTML listing (`/viec-lam-it-phan-mem-i35-vn`) và detail (`/<slug>-<id>-jd`) | Tuần 1 — T4 | ⬜ |
| VW-03 | Viết `parser.py`: listing + detail | Tuần 1 — T5–T6 | ⬜ |
| VW-04 | Viết `crawler.py` + `config.py` | Tuần 1 — T7 | ⬜ |
| VW-05 | Test local 30 tin, kiểm tra JSONL | Tuần 1 — CN | ⬜ |
| VW-06 | Tạo PR tag Thuận | Tuần 1 — CN | ⬜ |
| VW-07 | Fix bug khi chạy trên EC2 | Tuần 2 (ongoing) | ⬜ |

**Ghi chú kỹ thuật VietnamWorks:**
- Nginx server, **không có Cloudflare**, rất dễ cào
- Listing trả SSR nhưng chỉ ~15 anchor trong HTML (cần kiểm tra pagination/API)
- Detail URL dạng: `https://www.vietnamworks.com/<slug>-<id>-jd` → trả 200 OK, ~65KB HTML
- `robots.txt` cho phép trang tìm kiếm và detail, chỉ cấm trang profile/ứng tuyển

---

### 🟡 Phúc — Nguồn mới (Chờ chốt)

**Nguồn:** ⚠️ **Cần chọn** (LinkedIn đã loại vì ToS cấm cào)

| # | Task | Deadline | Trạng thái |
|---|---|---|---|
| P-01 | Chọn nguồn mới: check `robots.txt`, thử `curl` xem có bị chặn không, báo nhóm | Tuần 1 — T3 | ⬜ |
| P-02 | Phân tích HTML listing + detail | Tuần 1 — T4–T5 | ⬜ |
| P-03 | Viết `parser.py` + `crawler.py` + `config.py` | Tuần 1 — T6–T7 | ⬜ |
| P-04 | Test local 30 tin | Tuần 1 — CN | ⬜ |
| P-05 | Tạo PR tag Thuận | Tuần 1 — CN | ⬜ |
| P-06 | Fix bug khi chạy trên EC2 | Tuần 2 (ongoing) | ⬜ |

**Gợi ý nguồn cho Phúc (cần check thêm):**

| Nguồn | URL | Ghi chú |
|---|---|---|
| Vieclam24h | `vieclam24h.vn` | Nhiều tin IT, phổ biến ở VN |
| MyWork | `mywork.com.vn` | Trang việc làm mới, có danh mục IT |
| Timviecnhanh | `timviecnhanh.com` | Đa ngành, có mục CNTT |

> Phúc hãy thử `curl -sI "https://<trang>/robots.txt"` trước. Nếu trả `200 OK` và không có Cloudflare challenge thì dùng được.

---

## 7. Lịch chạy tự động trên EC2 (Thuận cấu hình)

### 7.1 Batching

```text
Mỗi lần chạy = 1 batch
  → python run.py --source topdev --max-items 200
  → Ghi ra: data/topdev/dt=2026-10-07/batch_001.jsonl
  → Upload S3: s3://<bucket>/raw/source=topdev/dt=2026-10-07/batch_001.jsonl
  → Gửi Telegram: "✅ topdev | batch_001 | 187 tin mới | 13 trùng | 0 lỗi"
```

### 7.2 Cron schedule (EC2)

```cron
# Chạy 6 crawler mỗi ngày, lệch giờ để không đè nhau
# Mỗi nguồn chạy 1 lần/ngày, quota 150-200 tin/lần
0  20 * * * cd /opt/crawler && python run.py --source topdev       --max-items 200
10 20 * * * cd /opt/crawler && python run.py --source careerviet   --max-items 200
20 20 * * * cd /opt/crawler && python run.py --source itviec       --max-items 200
30 20 * * * cd /opt/crawler && python run.py --source vietnamworks --max-items 200
40 20 * * * cd /opt/crawler && python run.py --source topcv        --max-items 100
50 20 * * * cd /opt/crawler && python run.py --source <phuc>       --max-items 200
```

### 7.3 Dữ liệu trên S3

```text
s3://<bucket>/
├── raw/source=topdev/dt=2026-10-07/batch_001.jsonl
├── raw/source=topdev/dt=2026-10-08/batch_001.jsonl
├── raw/source=careerviet/dt=2026-10-07/batch_001.jsonl
├── ...
├── staging/source=topdev/dt=2026-10-07/parsed.jsonl
├── ...
└── curated/jobs_clean.parquet
```

---

## 8. Timeline tổng thể

| Tuần | Mục tiêu tích lũy | Việc chính | Ai làm gì |
|---:|---:|---|---|
| **1** | 300–500 | Setup infra + mỗi người xong crawler v0.1 | Thuận: common/ + EC2 + S3. Cả nhóm: viết crawler, push PR |
| **1 T4** | — | **🎯 Demo cho thầy:** mẫu dữ liệu từ 6 nguồn trên S3 | Cả nhóm |
| **2** | 2.000 | Chạy tự động trên EC2, fix bug, ổn định | Thuận: cron + monitor. Cả nhóm: fix parser khi HTML đổi |
| **3** | 4.000 | Cào ổn định, chốt bài toán ML | Thuận + Phát: bắt đầu thử Browser Use + Ollama |
| **4** | 6.500 | Cào + thử nghiệm AI | Thuận + Phát: so sánh kết quả AI vs parser truyền thống |
| **5** | **10.000+** | **🎯 Dừng cào, kiểm tra chất lượng** | Thuận: chạy dedup liên nguồn, báo cáo số liệu |
| **6** | — | ELT: Raw → Staging → Curated | Thuận: script chuẩn hóa + làm sạch |
| **7** | — | EDA + huấn luyện ML | Cả nhóm: chia nhau vẽ biểu đồ, train model |
| **8** | — | Dashboard, báo cáo, slide thuyết trình | Cả nhóm |
| **9** | — | **🎯 Thuyết trình cuối kỳ** | Cả nhóm |

---

## 9. Checklist nộp crawler (Dành cho mỗi thành viên)

Trước khi tạo PR, hãy đảm bảo:

- [ ] Crawler chạy được local: `python run.py --source <tên> --max-items 30`
- [ ] Output JSONL đúng schema (`_meta` + `raw` đầy đủ)
- [ ] Có `dedup_key` đúng format `"<source>:<source_job_id>"`
- [ ] Có `description_html` (HTML gốc) và `description_text` (text thuần)
- [ ] URL đã chuẩn hóa (bỏ `utm_*`, bỏ `/` cuối)
- [ ] Delay 2–5 giây giữa các request (dùng `common/http_client.py`)
- [ ] Checkpoint hoạt động (chạy lần 2 không cào lại tin cũ)
- [ ] `README.md` trong thư mục nguồn đã ghi: owner, URL cào, robots.txt, cách chạy
- [ ] **Không có** AWS access key, token, hay dữ liệu cá nhân trong code
- [ ] Code chỉ nằm trong `crawlers/sources/<tên-nguồn>/`
- [ ] Đã test ít nhất 20 tin, mở file JSONL kiểm tra bằng mắt

---

## 10. Liên lạc nhóm

| Kênh | Mục đích |
|---|---|
| **GitHub Issues** | Báo bug, yêu cầu feature, thảo luận kỹ thuật |
| **GitHub PR** | Nộp code, code review |
| **Telegram Bot** | Thông báo tự động: kết quả batch, lỗi, tiến độ |
| **Telegram Group** | Trao đổi nhanh, hỏi đáp |

---

> **Lưu ý cuối:** File `.env` chứa AWS credentials **TUYỆT ĐỐI KHÔNG** được push lên GitHub.
> Đã có `.gitignore` chặn sẵn. Nếu cần credentials để test local, hỏi Thuận cấp IAM key riêng.
