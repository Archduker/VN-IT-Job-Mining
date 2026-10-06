"""
crawlers.common.http_client
~~~~~~~~~~~~~~~~~~~~~~~~~~~
HTTP client dùng chung cho tất cả crawlers.

Features:
    - Random delay 2–5 giây giữa các request (tôn trọng server)
    - Exponential backoff retry (tối đa 3 lần)
    - User-Agent rotation tự động
    - Session reuse (TCP connection pooling)
    - Timeout cấu hình được
    - Structured logging

Classes:
    HttpClient  — Main HTTP client class
    RetryConfig — Cấu hình retry policy

Usage:
    >>> client = HttpClient(source="topdev")
    >>> response = client.get("https://topdev.vn/it-jobs")
    >>> html = response.text
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# User-Agent pool (Chrome/Firefox trên Windows/Mac/Linux)
# ─────────────────────────────────────────────────────────────
_USER_AGENTS: list[str] = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
    # Firefox on Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

# ─────────────────────────────────────────────────────────────
# Default headers (giả lập browser thật)
# ─────────────────────────────────────────────────────────────
_DEFAULT_HEADERS: dict[str, str] = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}


# ─────────────────────────────────────────────────────────────
# Config dataclasses
# ─────────────────────────────────────────────────────────────

@dataclass
class RetryConfig:
    """Cấu hình retry policy cho HTTP requests.

    Attributes:
        max_retries: Số lần retry tối đa (default: 3).
        backoff_factor: Hệ số delay giữa các lần retry.
            Delay = backoff_factor * (2 ** (retry_number - 1)) giây.
            Ví dụ với factor=1: retry 1=1s, retry 2=2s, retry 3=4s.
        status_forcelist: Danh sách HTTP status codes cần retry.
            Mặc định: 429 (Too Many Requests), 500, 502, 503, 504.
        raise_on_status: Raise exception nếu response có status lỗi.
    """

    max_retries: int = 3
    backoff_factor: float = 1.0
    status_forcelist: tuple[int, ...] = field(
        default_factory=lambda: (429, 500, 502, 503, 504)
    )
    raise_on_status: bool = True


@dataclass
class DelayConfig:
    """Cấu hình random delay giữa các request.

    Attributes:
        min_seconds: Delay tối thiểu (default: 2.0 giây).
        max_seconds: Delay tối đa (default: 5.0 giây).

    Notes:
        Delay ngẫu nhiên giúp tránh bị nhận diện là bot.
        Không nên đặt dưới 1 giây để tôn trọng server.
    """

    min_seconds: float = 2.0
    max_seconds: float = 5.0

    def __post_init__(self) -> None:
        """Validate delay range."""
        if self.min_seconds < 0:
            raise ValueError("min_seconds phải >= 0")
        if self.max_seconds < self.min_seconds:
            raise ValueError("max_seconds phải >= min_seconds")

    def random_delay(self) -> float:
        """Lấy một giá trị delay ngẫu nhiên trong khoảng cấu hình.

        Returns:
            Số giây delay (float).
        """
        return random.uniform(self.min_seconds, self.max_seconds)


# ─────────────────────────────────────────────────────────────
# Main HttpClient
# ─────────────────────────────────────────────────────────────

class HttpClient:
    """HTTP client dùng chung cho tất cả crawlers.

    Tự động xử lý:
        - Random delay giữa các request
        - User-Agent rotation
        - Exponential backoff retry
        - Session/connection pooling

    Attributes:
        source: Tên nguồn crawler (dùng cho logging).
        timeout: Request timeout (giây).
        delay_config: Cấu hình delay giữa các request.
        retry_config: Cấu hình retry policy.

    Examples:
        >>> client = HttpClient(source="topdev")
        >>> response = client.get("https://topdev.vn/it-jobs")
        >>> print(response.status_code)
        200

        >>> # Tắt delay cho testing
        >>> client = HttpClient(
        ...     source="topdev",
        ...     delay_config=DelayConfig(min_seconds=0, max_seconds=0),
        ... )
    """

    def __init__(
        self,
        source: str,
        timeout: int = 30,
        delay_config: Optional[DelayConfig] = None,
        retry_config: Optional[RetryConfig] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> None:
        """Khởi tạo HttpClient.

        Args:
            source: Tên nguồn crawler (dùng cho logging, ví dụ "topdev").
            timeout: Timeout cho mỗi request (giây). Default: 30.
            delay_config: Cấu hình delay giữa requests. Default: 2-5 giây.
            retry_config: Cấu hình retry policy. Default: 3 retries với backoff.
            extra_headers: Headers bổ sung (merge vào _DEFAULT_HEADERS).
        """
        self.source = source
        self.timeout = timeout
        self.delay_config = delay_config or DelayConfig()
        self.retry_config = retry_config or RetryConfig()

        self._session = self._build_session(extra_headers or {})
        self._request_count = 0

        logger.debug(
            "[%s] HttpClient initialized | timeout=%ss | delay=%s-%ss | max_retries=%s",
            self.source,
            self.timeout,
            self.delay_config.min_seconds,
            self.delay_config.max_seconds,
            self.retry_config.max_retries,
        )

    def _build_session(self, extra_headers: dict[str, str]) -> Session:
        """Khởi tạo requests.Session với retry adapter và default headers.

        Args:
            extra_headers: Headers bổ sung merge vào default headers.

        Returns:
            Configured requests.Session.
        """
        session = requests.Session()

        # Mount retry adapter cho cả http:// và https://
        retry_strategy = Retry(
            total=self.retry_config.max_retries,
            backoff_factor=self.retry_config.backoff_factor,
            status_forcelist=list(self.retry_config.status_forcelist),
            allowed_methods=["GET", "HEAD"],
            raise_on_status=False,  # Xử lý thủ công sau để log được
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Set default headers (User-Agent sẽ được rotate trước mỗi request)
        headers = {**_DEFAULT_HEADERS, **extra_headers}
        session.headers.update(headers)

        return session

    def _rotate_user_agent(self) -> str:
        """Chọn ngẫu nhiên một User-Agent từ pool.

        Returns:
            User-Agent string được chọn.
        """
        ua = random.choice(_USER_AGENTS)
        self._session.headers["User-Agent"] = ua
        return ua

    def get(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict[str, str]] = None,
        apply_delay: bool = True,
        **kwargs,
    ) -> Response:
        """Gửi GET request với delay và User-Agent rotation tự động.

        Args:
            url: URL cần fetch.
            params: Query parameters (dict).
            headers: Request-level headers (override session headers).
            apply_delay: Có áp dụng delay trước request không.
                Đặt False cho request đầu tiên hoặc khi test.
            **kwargs: Các tham số khác truyền vào requests.get().

        Returns:
            requests.Response object.

        Raises:
            requests.HTTPError: Nếu response status là lỗi (4xx/5xx)
                và retry_config.raise_on_status = True.
            requests.ConnectionError: Nếu không kết nối được.
            requests.Timeout: Nếu request timeout.

        Examples:
            >>> client = HttpClient(source="topdev")
            >>> resp = client.get("https://topdev.vn/it-jobs", params={"page": 2})
            >>> resp.status_code
            200
        """
        # Apply random delay (trừ request đầu tiên)
        if apply_delay and self._request_count > 0:
            delay = self.delay_config.random_delay()
            logger.debug(
                "[%s] Sleeping %.2fs before request #%s",
                self.source, delay, self._request_count + 1,
            )
            time.sleep(delay)

        # Rotate User-Agent
        ua = self._rotate_user_agent()
        logger.debug("[%s] User-Agent: %s...", self.source, ua[:50])

        # Merge request-level headers
        request_headers = {**self._session.headers, **(headers or {})}

        try:
            response = self._session.get(
                url,
                params=params,
                headers=request_headers,
                timeout=self.timeout,
                **kwargs,
            )
            self._request_count += 1

            logger.info(
                "[%s] GET %s | status=%s | size=%s bytes | #%s",
                self.source,
                url,
                response.status_code,
                len(response.content),
                self._request_count,
            )

            # Raise nếu status lỗi và config yêu cầu
            if self.retry_config.raise_on_status:
                response.raise_for_status()

            return response

        except requests.HTTPError as e:
            logger.error(
                "[%s] HTTP error | url=%s | status=%s",
                self.source, url, e.response.status_code if e.response else "N/A",
            )
            raise
        except requests.ConnectionError as e:
            logger.error("[%s] Connection error | url=%s | error=%s", self.source, url, e)
            raise
        except requests.Timeout:
            logger.error(
                "[%s] Timeout after %ss | url=%s", self.source, self.timeout, url
            )
            raise

    def get_html(self, url: str, **kwargs) -> str:
        """Convenience method: GET request và trả về HTML text.

        Args:
            url: URL cần fetch.
            **kwargs: Truyền vào self.get().

        Returns:
            HTML content dạng string (UTF-8 decoded).

        Examples:
            >>> client = HttpClient(source="topdev")
            >>> html = client.get_html("https://topdev.vn/it-jobs")
            >>> "<html" in html
            True
        """
        response = self.get(url, **kwargs)
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    def post(
        self,
        url: str,
        data: Any = None,
        json: Any = None,
        headers: Optional[dict[str, str]] = None,
        apply_delay: bool = True,
        **kwargs,
    ) -> Response:
        """Gửi POST request với delay và User-Agent rotation tự động."""
        if apply_delay and self._request_count > 0:
            delay = self.delay_config.random_delay()
            logger.debug(
                "[%s] Sleeping %.2fs before POST #%s",
                self.source, delay, self._request_count + 1,
            )
            time.sleep(delay)

        ua = self._rotate_user_agent()
        request_headers = {**self._session.headers, **(headers or {})}

        try:
            response = self._session.post(
                url,
                data=data,
                json=json,
                headers=request_headers,
                timeout=self.timeout,
                **kwargs,
            )
            self._request_count += 1

            logger.info(
                "[%s] POST %s | status=%s | size=%s bytes | #%s",
                self.source,
                url,
                response.status_code,
                len(response.content),
                self._request_count,
            )

            if self.retry_config.raise_on_status:
                response.raise_for_status()

            return response
        except Exception as exc:
            logger.error("[%s] POST error | url=%s | err=%s", self.source, url, exc)
            raise

    def close(self) -> None:
        """Đóng session và giải phóng connection pool.

        Nên gọi khi kết thúc crawl để tránh resource leak.

        Examples:
            >>> client = HttpClient(source="topdev")
            >>> # ... crawl ...
            >>> client.close()
        """
        self._session.close()
        logger.debug("[%s] Session closed. Total requests: %s", self.source, self._request_count)

    def __enter__(self) -> "HttpClient":
        """Support context manager protocol."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Tự động đóng session khi ra khỏi context."""
        self.close()

    def __repr__(self) -> str:
        return (
            f"HttpClient(source={self.source!r}, timeout={self.timeout}, "
            f"requests_made={self._request_count})"
        )
