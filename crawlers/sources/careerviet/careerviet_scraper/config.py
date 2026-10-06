"""
config.py - Thiết lập toàn bộ cấu hình cho CareerViet Scraper
Bao gồm: URLs, User-Agents, danh mục ngành nghề, timeouts, paths
"""

import os

# ============================================================
# 1. ĐƯỜNG DẪN FILE
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OUTPUT_FILE       = os.path.join(BASE_DIR, "careerviet_raw_jobs.json")
CHECKPOINT_FILE   = os.path.join(BASE_DIR, "checkpoint.json")
ERROR_LOG_FILE    = os.path.join(BASE_DIR, "error_log.txt")

# ============================================================
# 2. CẤU HÌNH MẠNG & BROWSER
# ============================================================
BASE_URL = "https://careerviet.vn"

# Timeout (giây)
PAGE_LOAD_TIMEOUT   = 30_000   # ms (Playwright)
ELEMENT_TIMEOUT     = 10_000   # ms
REQUEST_TIMEOUT     = 30       # giây (requests fallback)

# Delay ngẫu nhiên giữa các request (giây) – tránh bị chặn IP
DELAY_MIN = 1.5
DELAY_MAX = 3.5

# Số tab/trang đồng thời tối đa (Semaphore)
MAX_CONCURRENT_PAGES = 3

# Số lần retry khi gặp lỗi mạng / timeout
MAX_RETRIES = 3
RETRY_DELAY = 5  # giây

# ============================================================
# 3. USER-AGENTS ROTATION
# ============================================================
USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # Safari Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

# ============================================================
# 4. DANH MỤC NGÀNH NGHỀ MỤC TIÊU
# ============================================================
# Cấu trúc: { "name": tên hiển thị, "url_path": đường dẫn trên CareerViet }
# URL mẫu: https://careerviet.vn/viec-lam/cntt-phan-mem-c47-vi.html
TARGET_CATEGORIES = [
    {
        "name": "CNTT - Phần mềm",
        "url_path": "/viec-lam/cntt-phan-mem-c1-vi.html",
        "category_id": "1",
    },
    {
        "name": "CNTT - Phần cứng / Mạng",
        "url_path": "/viec-lam/cntt-phan-cung-mang-c48-vi.html",
        "category_id": "48",
    },
    {
        "name": "Viễn thông",
        "url_path": "/viec-lam/vien-thong-c49-vi.html",
        "category_id": "49",
    },
    {
        "name": "Internet / Thương mại điện tử",
        "url_path": "/viec-lam/internet-thuong-mai-dien-tu-c137-vi.html",
        "category_id": "137",
    },
    {
        "name": "Mỹ thuật / Thiết kế",
        "url_path": "/viec-lam/my-thuat-thiet-ke-in-an-bao-bi-c24-vi.html",
        "category_id": "24",
    },
    {
        "name": "Tự động hóa / Điện - Điện tử",
        "url_path": "/viec-lam/dien-dien-tu-tu-dong-hoa-c20-vi.html",
        "category_id": "20",
    },
    {
        "name": "Tư vấn / Dịch vụ tài chính - Ngân hàng",
        "url_path": "/viec-lam/ngan-hang-tai-chinh-c13-vi.html",
        "category_id": "13",
    },
]

# ============================================================
# 5. CSS SELECTORS & XPath – DOM MAPPING
# ============================================================
SELECTORS = {
    # --- Danh sách job (trang listing) ---
    "job_list_items":  "div.job-item",
    "job_link":        "a.job-title",
    "pagination_next": "li.next-page a",

    # --- Chi tiết job ---
    "title":           "div.job-desc h1.title, h1.title",
    "company_name":    "a.employer.job-company-name, div.company-info a.company-name",
    "company_url":     "a.employer.job-company-name",

    # Salary / Thông tin tóm tắt (li bên trong ul.job-info)
    "info_block":      "ul.job-info li",

    # Mô tả công việc & yêu cầu
    "detail_sections": "div.detail-row.reset-bullet",

    # Tags / Kỹ năng
    "tags_container":  ".job-tags ul li a, .tag-list li a",

    # Địa điểm
    "location_block":  "div.detail-row.info-place-detail, div.info-place-detail",

    # Ngày đăng
    "posted_date":     "div.job-desc .posted-date, span.posted-date",
}

# ============================================================
# 6. BROWSER ARGUMENTS (Playwright / Chromium)
# ============================================================
BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--lang=vi-VN,vi",
]

# Viewport giả lập desktop thực
VIEWPORT = {"width": 1366, "height": 768}

# Locale & timezone
LOCALE   = "vi-VN"
TIMEZONE = "Asia/Ho_Chi_Minh"

# ============================================================
# 7. EXTRA HEADERS
# ============================================================
EXTRA_HEADERS = {
    "Accept-Language":  "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept":           "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding":  "gzip, deflate, br",
    "Connection":       "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":   "document",
    "Sec-Fetch-Mode":   "navigate",
    "Sec-Fetch-Site":   "none",
}
