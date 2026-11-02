# -*- coding: utf-8 -*-
"""Tests for Cloudflare R2 endpoint resolution, which must come only from configuration."""

import pytest

from collection.common.r2_raw_pipeline import R2RawStore
from collection.common.r2_storage import resolve_r2_endpoint


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("R2_ENDPOINT_URL", "S3_ENDPOINT_URL", "R2_ACCOUNT_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)


def test_explicit_endpoint_wins(monkeypatch):
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://env.example")
    assert resolve_r2_endpoint("https://arg.example") == "https://arg.example"


def test_endpoint_is_built_from_account_id(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID", "abc123")
    assert resolve_r2_endpoint() == "https://abc123.r2.cloudflarestorage.com"


def test_missing_endpoint_raises():
    with pytest.raises(ValueError, match="R2_ENDPOINT_URL"):
        resolve_r2_endpoint()


def test_missing_endpoint_is_empty_when_optional():
    assert resolve_r2_endpoint(required=False) == ""


def test_store_without_endpoint_raises():
    with pytest.raises(ValueError, match="R2_ENDPOINT_URL"):
        R2RawStore(access_key="key", secret_key="secret", ensure_bucket=False)
