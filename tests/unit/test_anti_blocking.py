"""Unit tests cho crawlers.common.anti_blocking."""

from unittest.mock import MagicMock
from crawlers.common.anti_blocking import (
    polite_sleep,
    is_cloudflare_challenge,
    handle_cloudflare_backoff,
    human_like_interaction,
)


def test_polite_sleep_returns_delay():
    delay = polite_sleep(min_sec=0.1, max_sec=0.3, reason="unit test")
    assert delay >= 0.1
    # Check that negative or zero min_sec returns 0.0 immediately
    assert polite_sleep(min_sec=0.0) == 0.0


def test_is_cloudflare_challenge():
    assert is_cloudflare_challenge("<html><body>Attention Required! | Cloudflare</body></html>") is True
    assert is_cloudflare_challenge("Just a moment... Enable JavaScript") is True
    assert is_cloudflare_challenge("<html><body><h1>Tuyển dụng IT</h1></body></html>") is False
    assert is_cloudflare_challenge("") is False


def test_handle_cloudflare_backoff():
    mock_page = MagicMock()
    # First content has challenge, second content clears it
    mock_page.content.return_value = "<html><body><h1>Tuyển dụng IT</h1></body></html>"
    handled = handle_cloudflare_backoff(mock_page, retry_attempt=1, base_backoff_sec=0.1)
    assert handled is True
    assert mock_page.content.called


def test_human_like_interaction():
    mock_page = MagicMock()
    mock_page.viewport_size = {"height": 1080}
    human_like_interaction(mock_page, scroll_times=2)
    # Ensure mouse.wheel was invoked
    assert mock_page.mouse.wheel.called
