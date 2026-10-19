# -*- coding: utf-8 -*-
"""Cấu hình riêng cho crawler ITViec (nguồn: https://itviec.com).

Giá trị được tách riêng để crawler.py / parser.py dùng chung và để đối chiếu
dễ dàng khi kiểm thử selector. Credential MinIO KHÔNG đặt ở đây (lấy từ .env).
"""

import os

# ── Định danh nguồn ───────────────────────────────────────────
SOURCE = "itviec"
CRAWLER_VERSION = "2.0.0"

# ── URL (đã verify bằng probe thật 2026-10-17) ────────────────
BASE_URL = "https://itviec.com"
LISTING_URL = "https://itviec.com/viec-lam-it"
# Phân trang: /viec-lam-it?page=N&query=&source=search_job (probe thấy tới trang ~33)
LISTING_PAGE_TEMPLATE = LISTING_URL + "?page={page}&query=&source=search_job"
DETAIL_PATH_PREFIX = "/viec-lam-it/"
SITEMAP_URL = "https://itviec.com/dunggiatminh.xml"

# ── Selector listing (đã verify live: 20 div.job-card/trang) ──
LISTING_CARD_SELECTOR = "div.job-card"
LISTING_SLUG_ATTR = "data-search--job-selection-job-slug-value"
LISTING_TITLE_LINK = "h3 a[href]"
LISTING_COMPANY_LINK = "a[href*='/nha-tuyen-dung/']"

# ── Selector detail (kiến trúc cũ 2026-10-05: JSON-LD JobPosting + SSR) ──
# Chi tiết ITViec render sẵn trong HTML (SSR). Nguồn chính: JSON-LD @type=JobPosting.
JSONLD_TYPE = "JobPosting"
DETAIL_H1_SELECTOR = "h1"
DETAIL_SECTION_HEADING = "h2"
DETAIL_SECTION_CONTAINER = "div.paragraph"
DETAIL_COMPANY_LINK = "a[href*='/nha-tuyen-dung/']"  # CŨ (anchor đầu tiên) — KHÔNG dùng trực tiếp nữa; xem _resolve_company
DETAIL_EMPLOYER_NAME = "div.employer-name"            # tên cty trong khối JD chính (không phải sidebar "Nhà tuyển dụng nổi bật")
JD_MAIN_SELECTOR = "div.jd-main"                       # khối JD chính để scope anchor công ty
# Các container ứng viên cho Clean Container HTML Hash — thử theo thứ tự,
# crawler sẽ tự phát hiện & log container thật sự khớp (không hard-code mù).
DETAIL_HASH_CONTAINERS = [
    "section.job-content",
    "div.job-description",
    "div.jobdetail",
    "div.job-detail",
    "section.job-description",
    "main",
    "article",
]

# ── Cơ chế re-crawl & CDC ─────────────────────────────────────
RECHECK_DAYS = int(os.getenv("CRAWL_RECHECK_DAYS", "21"))

# ── Delay lịch sự (theo chuẩn anti_blocking mới của repo) ─────
MIN_DELAY = float(os.getenv("CRAWL_DELAY_MIN", "3.0"))
MAX_DELAY = float(os.getenv("CRAWL_DELAY_MAX", "5.5"))

# ── Trình duyệt cho Playwright (verify launch được trên máy dev) ──
BROWSER_PATH = os.getenv("ITVIEC_BROWSER_PATH", "/snap/bin/chromium")

# ── Browser context ───────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ── Đường dẫn lưu trữ cục bộ (khớp layout MinIO) ──────────────
# data/itviec/url_ledger/... và data/itviec/raw/YYYY-MM-DD/{job_id}_v{version}.json

# ── MinIO key prefix (bucket lấy từ env MINIO_BUCKET / vn-it-jobs) ──
MINIO_RAW_PREFIX = f"raw/{SOURCE}/"          # raw/itviec/YYYY-MM-DD/<job_id>_v<n>.json
MINIO_HTML_PREFIX = f"raw_html/{SOURCE}/"    # raw_html/itviec/YYYY-MM-DD/<job_id>_v<n>.html

# ── Nội dung tin để băm Clean Container (đã verify offline 3 layout 2026-10-17) ──
JD_HASH_CONTAINER = "section.job-content"     # khối bao trọn JD + Yêu cầu + Quyền lợi + Lý do

# ── content_hash LAI: SHA256( text(section.job-content) + canonical_jsonld ) ──
# Chỉ những field dưới đây vào hash (không vì có mặt trong JSON-LD mà nhét hết).
HASH_JSONLD_FIELDS = [
    "title", "description", "skills", "employmentType", "experienceRequirements",
    "jobLocation", "jobBenefits", "baseSalary", "hiringOrganization", "validThrough",
]
CONTENT_HASH_ALGO = "section.job-content+canonical-jsonld/v1"

# ── D4/D5: đồng bộ HTML theo version + flush ledger định kỳ ──
SYNC_HTML = os.getenv("ITVIEC_SYNC_HTML", "0") == "1"   # Mặc định KHÔNG push HTML lên MinIO (Lựa chọn 1)
LEDGER_FLUSH_EVERY = int(os.getenv("ITVIEC_LEDGER_FLUSH_EVERY", "10"))
LEDGER_MINIO_SYNC_EVERY = int(os.getenv("ITVIEC_LEDGER_SYNC_EVERY", "50"))
