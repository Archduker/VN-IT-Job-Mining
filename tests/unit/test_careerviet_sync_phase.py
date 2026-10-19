"""tests/unit/test_careerviet_sync_phase.py — Kiem thu `--phase sync` (C3).

An toan: mock UrlLedger, khong goi mang, khong ket noi MinIO that.
`CareerVietCrawler.sync_ledger_to_minio()` phai delegate thang sang
`UrlLedger.sync_to_minio()` va tra nguyen gia tri (True/False).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from crawlers.sources.careerviet.crawler import CareerVietCrawler


def test_sync_ledger_delegates_and_returns_true(tmp_path):
    c = CareerVietCrawler(ledger_dir=str(tmp_path / "ledger"))
    fake_ledger = MagicMock()
    fake_ledger.sync_to_minio.return_value = True
    with patch.object(c, "_get_ledger", return_value=fake_ledger):
        ok = c.sync_ledger_to_minio()
    assert ok is True
    fake_ledger.sync_to_minio.assert_called_once_with()


def test_sync_ledger_returns_false_when_underlying_fails(tmp_path):
    c = CareerVietCrawler(ledger_dir=str(tmp_path / "ledger"))
    fake_ledger = MagicMock()
    fake_ledger.sync_to_minio.return_value = False
    with patch.object(c, "_get_ledger", return_value=fake_ledger):
        ok = c.sync_ledger_to_minio()
    assert ok is False


def test_sync_phase_present_in_argparse_choices():
    """Nhanien main() phai chap nhan `--phase sync` (neu argparse tu choi,
    parse_args se SystemExit -> bat va bao loi)."""
    import io
    import contextlib
    from crawlers.sources.careerviet import crawler as mod

    # Cho main() tao parser va parse_args: chung ta test bang cach
    # monkeypatch CareerVietCrawler de tranh khoi dong that.
    class _FakeCrawler:
        def sync_ledger_to_minio(self):
            return True

    original = mod.CareerVietCrawler
    mod.CareerVietCrawler = lambda **kw: _FakeCrawler()
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mod.main(["--phase", "sync"])
        out = buf.getvalue()
        assert "[sync]" in out
    except SystemExit as exc:
        raise AssertionError(
            f"--phase sync bi argparse tu choi (exit={exc.code})"
        ) from exc
    finally:
        mod.CareerVietCrawler = original


def test_main_dispatches_sync_phase(tmp_path, monkeypatch, capsys):
    """Khi chay `main(['--phase','sync'])`, phai goi crawler.sync_ledger_to_minio."""
    from crawlers.sources.careerviet import crawler as mod

    called = {"n": 0}

    class _FakeCrawler:
        def sync_ledger_to_minio(self):
            called["n"] += 1
            return True

    monkeypatch.setattr(mod, "CareerVietCrawler", lambda **kw: _FakeCrawler())
    monkeypatch.setattr(mod, "DEFAULT_LEDGER_DIR", str(tmp_path / "ledger"))
    rc = mod.main(["--phase", "sync"])
    assert rc == 0 or rc is None
    assert called["n"] == 1
    out = capsys.readouterr().out
    assert "[sync]" in out
    assert "OK" in out
