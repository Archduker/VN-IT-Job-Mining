"""
Module chống chặn bot & cơ chế Polite Sleep cho hệ thống VN-IT-Job-Mining.

Cung cấp:
- polite_sleep: Tạm dừng ngẫu nhiên có phân phối Uniform / Gaussian jitter.
- human_like_interaction: Mô phỏng hành vi người dùng (cuộn trang tự nhiên, di chuột, dừng đọc).
- detect_and_handle_challenge: Phát hiện thử thách Cloudflare / WAF và xử lý giãn cách lũy thừa (exponential backoff).
"""

import logging
import random
import time
from typing import Any, Optional

log = logging.getLogger("crawlers.anti_blocking")


def polite_sleep(
    min_sec: float = 3.0,
    max_sec: float = 5.5,
    reason: str = "",
) -> float:
    """
    Tạm dừng ngẫu nhiên giữa các request để mô phỏng hành vi người dùng thực tế.
    Áp dụng Uniform distribution kết hợp vi sai jitter nhằm tránh pattern cố định.
    """
    if min_sec <= 0:
        return 0.0

    if max_sec < min_sec:
        max_sec = min_sec + 1.0

    base_delay = random.uniform(min_sec, max_sec)
    jitter = random.uniform(-0.15, 0.25)
    actual_delay = max(0.5, round(base_delay + jitter, 2))

    log_msg = f"[Polite Sleep] Nghỉ ngơi {actual_delay}s"
    if reason:
        log_msg += f" ({reason})"
    log.info(log_msg)

    time.sleep(actual_delay)
    return actual_delay


def human_like_interaction(page: Any, scroll_times: int = 2) -> None:
    """
    Mô phỏng thao tác đọc trang của người dùng thật trên trình duyệt Playwright:
    - Cuộn trang từng đoạn ngẫu nhiên (200 - 550px).
    - Tạm dừng ngắn để render lazy loading hình ảnh và thẻ.
    - Cuộn nhẹ ngược lên một đoạn nhỏ.
    """
    if not page:
        return

    try:
        viewport = page.viewport_size or {"height": 900}
        v_height = viewport.get("height", 900)

        for _ in range(scroll_times):
            scroll_delta = random.randint(int(v_height * 0.3), int(v_height * 0.7))
            page.mouse.wheel(0, scroll_delta)
            # Dừng ngắn mô phỏng mắt người quét qua nội dung (0.4s - 0.9s)
            page.wait_for_timeout(random.randint(400, 900))

        # Cuộn nhẹ lên trên mô phỏng nhìn lại tiêu đề
        page.mouse.wheel(0, -random.randint(50, 150))
        page.wait_for_timeout(random.randint(300, 600))
    except Exception as exc:
        log.debug("[AntiBlocking] Bỏ qua tương tác cuộn trang: %s", exc)


def is_cloudflare_challenge(html_content: str) -> bool:
    """Kiểm tra xem nội dung trang có chứa dấu hiệu Cloudflare WAF / Turnstile hay không."""
    if not html_content:
        return False
    blocked_indicators = [
        "Attention Required! | Cloudflare",
        "Just a moment...",
        "Checking your browser before accessing",
        "Cloudflare Ray ID:",
        "Enable JavaScript and cookies to continue",
        "challenge-platform",
    ]
    return any(ind in html_content for ind in blocked_indicators)


def handle_cloudflare_backoff(
    page: Any,
    retry_attempt: int = 1,
    base_backoff_sec: float = 10.0,
) -> bool:
    """
    Xử lý khi phát hiện Cloudflare challenge:
    - Tạm dừng theo cấp số nhân với jitter: base * 2^(attempt - 1) + jitter.
    - Đợi trang tự refresh hoặc challenge giải xong.
    - Trả về True nếu challenge đã vượt qua, False nếu vẫn bị chặn.
    """
    delay = (base_backoff_sec * (2 ** max(0, retry_attempt - 1))) + random.uniform(2.0, 5.0)
    delay = round(delay, 2)
    log.warning(
        "[AntiBlocking] Phát hiện Cloudflare challenge! Kích hoạt backoff %ss (Lần thử %d)...",
        delay,
        retry_attempt,
    )

    try:
        # Chờ đợi với Playwright timeout
        page.wait_for_timeout(int(delay * 1000))
        new_content = page.content()
        if not is_cloudflare_challenge(new_content):
            log.info("[AntiBlocking] Đã vượt qua Cloudflare challenge thành công!")
            return True
    except Exception as exc:
        log.error("[AntiBlocking] Lỗi khi chờ Cloudflare backoff: %s", exc)

    log.warning("[AntiBlocking] Vẫn chưa vượt qua Cloudflare challenge sau %ss.", delay)
    return False
