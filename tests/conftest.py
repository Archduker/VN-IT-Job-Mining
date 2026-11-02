# -*- coding: utf-8 -*-
"""Cấu hình chung cho mọi test.

Cấu trúc (xem tests/README.md):
    unit/         hàm nhỏ, không đọc data/, không mạng
    integration/  API monitoring và script, dùng tmp_path
    contract/     crawler có đạt tiêu chuẩn collection C1–C14 không, chạy offline với tests/fixtures/
    data/         đọc data/ hoặc reports/ thật; tự skip khi thiếu

Marker theo thư mục được gắn tự động. Marker thêm bằng tay:
    @pytest.mark.needs_data("data/topcv/url_ledger/catalog_master.json")  skip nếu thiếu đường dẫn
    @pytest.mark.live                                                     cào hoặc gọi R2 thật; chỉ chạy với --run-live

Mặc định test không được kết nối mạng ra ngoài (chỉ cho localhost), để không ghi nhầm lên R2 hay gọi trang thật.
"""

from __future__ import annotations

import ipaddress
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "monitoring" / "backend", ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FOLDER_MARKERS = {"unit": "unit", "integration": "integration", "contract": "contract", "data": "needs_data"}


def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", help="Chạy cả test live (cào thật, gọi R2 thật)")


def pytest_collection_modifyitems(config, items):
    run_live = config.getoption("--run-live")
    for item in items:
        folder = Path(str(item.fspath)).relative_to(Path(__file__).parent).parts[0]
        if folder in FOLDER_MARKERS:
            item.add_marker(getattr(pytest.mark, FOLDER_MARKERS[folder]))
        if "live" in item.keywords and not run_live:
            item.add_marker(pytest.mark.skip(reason="test live: chạy với --run-live"))
        for mark in item.iter_markers("needs_data"):
            missing = [p for p in mark.args if not (ROOT / p).exists()]
            if missing:
                item.add_marker(pytest.mark.skip(reason=f"thiếu dữ liệu thật: {', '.join(missing)}"))


def _is_local(address) -> bool:
    if not isinstance(address, tuple):
        return True  # unix socket
    host = address[0]
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def _block_network(request, monkeypatch):
    if "live" in request.keywords:
        return
    real_connect = socket.socket.connect

    def guarded(self, address):
        if not _is_local(address):
            raise RuntimeError(f"Test không được kết nối mạng ra ngoài ({address}); dùng mock hoặc đánh dấu @pytest.mark.live")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    real_create = socket.create_connection

    def guarded_create(address, *args, **kwargs):
        if not _is_local(address):
            raise RuntimeError(f"Test không được kết nối mạng ra ngoài ({address}); dùng mock hoặc đánh dấu @pytest.mark.live")
        return real_create(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", guarded_create)


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
