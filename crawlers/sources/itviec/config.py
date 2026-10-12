# -*- coding: utf-8 -*-
"""Cấu hình riêng cho nguồn ITviec.

Owner: Phát
Chỉ chứa hằng số. Logic parse nằm ở parser.py, logic crawl nằm ở crawler.py.
"""

import os

# ---------------------------------------------------------------- danh tính
SOURCE = "itviec"
CRAWLER_VERSION = "0.5.0"

# ---------------------------------------------------------------- URL nguồn
BASE_URL = "https://itviec.com"

# Trang listing gốc (SSR, 20 job/trang, phân trang ?page=2..N).
# Có thể lọc theo location: /viec-lam-it/ho-chi-minh, /ha-noi, /da-nang...
# Mặc định chỉ dùng trang "toàn quốc" vì đã bao phủ toàn bộ job đang mở.
LISTING_LOCATIONS = [
    "/viec-lam-it",
]

# Giới hạn an toàn khi lần theo phân trang (trang hiện tại có ~35-45 trang).
MAX_LISTING_PAGES = 60

# ---------------------------------------------------------------- HTTP
# Data contract TASKS.md §4.2: delay ngẫu nhiên 2–5 giây giữa các request.
REQUEST_DELAY_MIN = 2.0
REQUEST_DELAY_MAX = 5.0
REQUEST_TIMEOUT = 30
# Retry với backoff cho lỗi mạng / 429 / 5xx (hành vi như common/http_client dự kiến).
MAX_RETRIES = 3
BACKOFF_BASE = 2.0  # giây, tăng theo cấp số nhân: 2, 4, 8 (khớp backoff 5s/10s/20s trong docs)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ---------------------------------------------------------------- checkpoint / output
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data", SOURCE)          # đã có trong .gitignore
ERROR_DIR = os.path.join(DATA_DIR, "errors")                # HTML thô khi parse lỗi
CHECKPOINT_FILE = os.path.join(DATA_DIR, "checkpoint.json")
# Data contract: ghi checkpoint sau mỗi 10 tin.
CHECKPOINT_INTERVAL = 10

# ---------------------------------------------------------------- hành vi crawl
DEFAULT_MAX_ITEMS = 30
# Múi giờ ghi crawled_at (contract dùng +07:00).
TZ_NAME = "Asia/Ho_Chi_Minh"
