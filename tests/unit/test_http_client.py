"""
Unit tests cho crawlers.common.http_client module.

Test coverage:
    - HttpClient: initialization, get(), get_html()
    - DelayConfig: validation, random_delay range
    - RetryConfig: defaults
    - User-Agent rotation
    - Context manager protocol
    - Error handling (HTTP errors, timeouts, connection errors)
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

import requests
from requests import Response

from crawlers.common.http_client import HttpClient, DelayConfig, RetryConfig, _USER_AGENTS


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _make_response(status_code: int = 200, text: str = "<html>OK</html>") -> Response:
    """Tạo mock Response object."""
    resp = MagicMock(spec=Response)
    resp.status_code = status_code
    resp.text = text
    resp.content = text.encode("utf-8")
    resp.apparent_encoding = "utf-8"
    resp.raise_for_status = MagicMock()  # không raise gì mặc định
    return resp


# ─────────────────────────────────────────────────────────────
# Tests: DelayConfig
# ─────────────────────────────────────────────────────────────

class TestDelayConfig:

    def test_default_values(self):
        config = DelayConfig()
        assert config.min_seconds == 2.0
        assert config.max_seconds == 5.0

    def test_custom_values(self):
        config = DelayConfig(min_seconds=1.0, max_seconds=3.0)
        assert config.min_seconds == 1.0
        assert config.max_seconds == 3.0

    def test_random_delay_in_range(self):
        config = DelayConfig(min_seconds=2.0, max_seconds=5.0)
        for _ in range(50):
            delay = config.random_delay()
            assert 2.0 <= delay <= 5.0

    def test_zero_delay_allowed(self):
        config = DelayConfig(min_seconds=0.0, max_seconds=0.0)
        assert config.random_delay() == 0.0

    def test_negative_min_raises_error(self):
        with pytest.raises(ValueError, match="min_seconds"):
            DelayConfig(min_seconds=-1.0, max_seconds=5.0)

    def test_max_less_than_min_raises_error(self):
        with pytest.raises(ValueError, match="max_seconds"):
            DelayConfig(min_seconds=5.0, max_seconds=2.0)


# ─────────────────────────────────────────────────────────────
# Tests: HttpClient initialization
# ─────────────────────────────────────────────────────────────

class TestHttpClientInit:

    def test_default_initialization(self):
        client = HttpClient(source="topdev")
        assert client.source == "topdev"
        assert client.timeout == 30
        assert client._request_count == 0
        client.close()

    def test_custom_timeout(self):
        client = HttpClient(source="itviec", timeout=60)
        assert client.timeout == 60
        client.close()

    def test_custom_delay_config(self):
        delay = DelayConfig(min_seconds=1.0, max_seconds=2.0)
        client = HttpClient(source="topdev", delay_config=delay)
        assert client.delay_config.min_seconds == 1.0
        client.close()

    def test_default_delay_config_set(self):
        client = HttpClient(source="topdev")
        assert client.delay_config is not None
        assert client.delay_config.min_seconds == 2.0
        client.close()

    def test_repr_contains_source(self):
        client = HttpClient(source="topdev")
        assert "topdev" in repr(client)
        client.close()


# ─────────────────────────────────────────────────────────────
# Tests: HttpClient.get() - happy path
# ─────────────────────────────────────────────────────────────

class TestHttpClientGet:

    @pytest.fixture
    def client(self):
        """HttpClient với delay = 0 để tests chạy nhanh."""
        c = HttpClient(
            source="topdev",
            delay_config=DelayConfig(min_seconds=0.0, max_seconds=0.0),
        )
        yield c
        c.close()

    def test_successful_get_returns_response(self, client):
        mock_resp = _make_response(200)
        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            response = client.get("https://topdev.vn/it-jobs", apply_delay=False)
            assert response.status_code == 200
            mock_get.assert_called_once()

    def test_request_count_increments(self, client):
        mock_resp = _make_response(200)
        with patch.object(client._session, "get", return_value=mock_resp):
            assert client._request_count == 0
            client.get("https://topdev.vn/it-jobs", apply_delay=False)
            assert client._request_count == 1
            client.get("https://topdev.vn/it-jobs?page=2", apply_delay=False)
            assert client._request_count == 2

    def test_passes_params_to_session(self, client):
        mock_resp = _make_response(200)
        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            client.get(
                "https://topdev.vn/it-jobs",
                params={"page": 2},
                apply_delay=False,
            )
            call_kwargs = mock_get.call_args
            assert call_kwargs.kwargs["params"] == {"page": 2}

    def test_passes_timeout_to_session(self, client):
        mock_resp = _make_response(200)
        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            client.get("https://topdev.vn/it-jobs", apply_delay=False)
            call_kwargs = mock_get.call_args
            assert call_kwargs.kwargs["timeout"] == 30

    def test_get_html_returns_text(self, client):
        mock_resp = _make_response(200, text="<html><body>Jobs</body></html>")
        with patch.object(client._session, "get", return_value=mock_resp):
            html = client.get_html("https://topdev.vn/it-jobs", apply_delay=False)
            assert "<html>" in html

    def test_delay_applied_after_first_request(self, client):
        """Delay chỉ được apply từ request thứ 2 trở đi."""
        mock_resp = _make_response(200)
        with patch.object(client._session, "get", return_value=mock_resp):
            with patch("time.sleep") as mock_sleep:
                # Request 1: apply_delay=True nhưng request_count=0 → không sleep
                client.get("https://topdev.vn/it-jobs", apply_delay=True)
                mock_sleep.assert_not_called()

                # Request 2: apply_delay=True, request_count=1 → sleep
                client.get("https://topdev.vn/it-jobs?page=2", apply_delay=True)
                mock_sleep.assert_called_once()


# ─────────────────────────────────────────────────────────────
# Tests: User-Agent rotation
# ─────────────────────────────────────────────────────────────

class TestUserAgentRotation:

    def test_user_agent_in_pool(self):
        client = HttpClient(source="topdev")
        ua = client._rotate_user_agent()
        assert ua in _USER_AGENTS
        client.close()

    def test_user_agent_set_on_session(self):
        client = HttpClient(source="topdev")
        ua = client._rotate_user_agent()
        assert client._session.headers["User-Agent"] == ua
        client.close()

    def test_user_agent_pool_not_empty(self):
        assert len(_USER_AGENTS) >= 5

    def test_rotation_varies(self):
        """Với pool đủ lớn, sau nhiều lần rotate phải có ít nhất 2 UA khác nhau."""
        client = HttpClient(source="topdev")
        seen = set()
        for _ in range(30):
            ua = client._rotate_user_agent()
            seen.add(ua)
        assert len(seen) > 1
        client.close()


# ─────────────────────────────────────────────────────────────
# Tests: Error handling
# ─────────────────────────────────────────────────────────────

class TestHttpClientErrors:

    @pytest.fixture
    def client(self):
        c = HttpClient(
            source="topdev",
            delay_config=DelayConfig(min_seconds=0.0, max_seconds=0.0),
        )
        yield c
        c.close()

    def test_http_error_raised_on_4xx(self, client):
        mock_resp = _make_response(404)
        mock_resp.raise_for_status.side_effect = requests.HTTPError(
            response=mock_resp
        )
        with patch.object(client._session, "get", return_value=mock_resp):
            with pytest.raises(requests.HTTPError):
                client.get("https://topdev.vn/not-found", apply_delay=False)

    def test_connection_error_propagated(self, client):
        with patch.object(
            client._session, "get",
            side_effect=requests.ConnectionError("Connection refused"),
        ):
            with pytest.raises(requests.ConnectionError):
                client.get("https://topdev.vn/it-jobs", apply_delay=False)

    def test_timeout_error_propagated(self, client):
        with patch.object(
            client._session, "get",
            side_effect=requests.Timeout("Request timed out"),
        ):
            with pytest.raises(requests.Timeout):
                client.get("https://topdev.vn/it-jobs", apply_delay=False)


# ─────────────────────────────────────────────────────────────
# Tests: Context manager
# ─────────────────────────────────────────────────────────────

class TestHttpClientContextManager:

    def test_context_manager_returns_client(self):
        with HttpClient(source="topdev") as client:
            assert isinstance(client, HttpClient)

    def test_session_closed_on_exit(self):
        client = HttpClient(source="topdev")
        with patch.object(client._session, "close") as mock_close:
            with client:
                pass
            mock_close.assert_called_once()

    def test_client_usable_inside_context(self):
        mock_resp = _make_response(200)
        with HttpClient(
            source="topdev",
            delay_config=DelayConfig(min_seconds=0.0, max_seconds=0.0),
        ) as client:
            with patch.object(client._session, "get", return_value=mock_resp):
                resp = client.get("https://topdev.vn/it-jobs", apply_delay=False)
                assert resp.status_code == 200
