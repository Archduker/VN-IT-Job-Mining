# -*- coding: utf-8 -*-
"""Unit test cho _detect_block/_looks_blocked/_dump_blocked_page cua crawler CareerViet.

Tieu chi CHAN moi: chi khi (a) HTTP 403/429 (ngan _is_blocking), HOAC (b) thieu
.job-detail-page DONG THOI co dau hien ro ret (tieu de 'Access Denied'/'Just a moment',
hop captcha). Chu 'captcha' trong <script> cua trang TOT khong bi tinh.
Dung mini HTML + tmp_path, KHONG goi mang.
"""

from __future__ import annotations

from pathlib import Path

import requests

from crawlers.sources.careerviet.crawler import CareerVietCrawler


def _crawler(tmp_path: Path) -> CareerVietCrawler:
    return CareerVietCrawler(
        max_items=None, output_dir=str(tmp_path / "out"),
        checkpoint_dir=str(tmp_path / "ckpt"),
        ledger_dir=str(tmp_path / "ledger"), raw_dir=str(tmp_path / "raw"),
    )


# ---- Cac mau HTML mini -------------------------------------------------
GOOD_WITH_CAPTCHA_WORD = """<!DOCTYPE html><html><head><title>Backend Developer</title>
<script>var recaptchaSiteKey="6LcXXXX"; /* captcha widget disabled */
console.log("captcha check skipped for logged-in user");</script></head>
<body><div class="job-detail-page">
  <h1 class="title">Backend Developer</h1>
  <a class="employer job-company-name">ABC</a>
  <ul class="detail-box"><li><strong>Ngành nghề</strong><p>CNTT - Phần mềm</p></li></ul>
  <div class="detail-row"><h2>Mô tả</h2><p>Build APIs</p></div>
</div></body></html>"""

BLOCKED_ACCESS_DENIED = """<!DOCTYPE html><html><head><title>Access Denied</title></head>
<body><h1>Access Denied</h1><p>You do not have permission to access this page.</p>
</body></html>"""

BLOCKED_CF_CHALLENGE = """<!DOCTYPE html><html><head><title>Just a moment...</title></head>
<body><div class="cf-challenge-widget"><div id="captcha-box" class="g-recaptcha"></div></div>
</body></html>"""

BLOCKED_EMPTY = ""


def _http_error(status: int) -> requests.HTTPError:
    resp = requests.Response()
    resp.status_code = status
    return requests.HTTPError(response=resp)


# ---- (b) thieu container + dau hien ro ret -----------------------------
def test_good_page_with_captcha_word_not_blocked():
    blocked, reason = CareerVietCrawler._detect_block(GOOD_WITH_CAPTCHA_WORD)
    assert blocked is False
    assert reason == ""
    assert CareerVietCrawler._looks_blocked(GOOD_WITH_CAPTCHA_WORD) is False


def test_missing_container_access_denied_blocked():
    blocked, reason = CareerVietCrawler._detect_block(BLOCKED_ACCESS_DENIED)
    assert blocked is True
    assert "access denied" in reason.lower()


def test_cloudflare_challenge_blocked():
    blocked, reason = CareerVietCrawler._detect_block(BLOCKED_CF_CHALLENGE)
    assert blocked is True


def test_empty_html_blocked():
    blocked, reason = CareerVietCrawler._detect_block(BLOCKED_EMPTY)
    assert blocked is True
    assert reason == "HTML rong"


# ---- (a) 429/403 -------------------------------------------------------
def test_http_429_and_403_are_blocking():
    assert CareerVietCrawler._is_blocking(_http_error(429)) is True
    assert CareerVietCrawler._is_blocking(_http_error(403)) is True
    assert CareerVietCrawler._is_blocking(_http_error(500)) is False
    assert CareerVietCrawler._is_blocking(_http_error(200)) is False


# ---- _dump_blocked_page ------------------------------------------------
def test_dump_blocked_page_writes_and_no_overwrite(tmp_path):
    cr = _crawler(tmp_path)
    dest = cr._dump_blocked_page("BLK001", "<html>first</html>", "ly do 1")
    assert dest == Path(cr.raw_dir).parent / "_blocked" / "BLK001.html"
    assert dest.exists()
    assert "first" in dest.read_text(encoding="utf-8")
    # lan 2 voi noi dung khac -> KHONG ghi de
    dest2 = cr._dump_blocked_page("BLK001", "<html>second</html>", "ly do 2")
    assert dest2.read_text(encoding="utf-8") == "<html>first</html>"
    # dump KHONG nam trong thu muc raw
    assert list(Path(cr.raw_dir).rglob("BLK001*")) == []


# ---- Noi dung rong cua test end-to-end duoi day ------------------------
class _FakeClient:
    """Client gia: lan 1 tra BLOCKED_HTML, cac lan sau tra GOOD (de kiem dung vong lap)."""

    def __init__(self, pages):
        self._pages = list(pages)
        self.calls = 0

    def get_html(self, url, headers=None, **kw):
        self.calls += 1
        p = self._pages.pop(0)
        if isinstance(p, Exception):
            raise p
        return p

    def close(self):
        pass


def _url(jid):
    return f"https://careerviet.vn/vi/tim-viec-lam/x.{jid}.html"


def _seed(crawler, ids):
    led = crawler._get_ledger()
    for j in ids:
        led.register_url(_url(j), job_id=j)
    led.save_catalog()


def _status(crawler, jid):
    for rec in crawler._get_ledger().records.values():
        if rec["job_id"] == jid:
            return rec["status"]
    return "ABSENT"


def test_online_good_page_not_blocked_and_writes(tmp_path):
    """End-to-end: trang TOT (co 'captcha' trong script) -> khong chan -> co envelope."""
    cr = _crawler(tmp_path)
    _seed(cr, ["GOOD01"])
    cr._online_client = lambda: _FakeClient([GOOD_WITH_CAPTCHA_WORD])
    stats = cr.crawl_details(online=True, limit=1)
    assert stats["success"] == 1 and stats["failed"] == 0
    assert _status(cr, "GOOD01") == "DONE"
    assert list(Path(cr.raw_dir).rglob("GOOD01_v1.json")) != []
    # khong co trang bi luu o _blocked
    blocked_dir = Path(cr.raw_dir).parent / "_blocked"
    assert not blocked_dir.exists() or list(blocked_dir.glob("GOOD01*")) == []


def test_online_blocked_page_keeps_pending_and_dumps(tmp_path):
    """End-to-end: trang thieu container + 'Access Denied' -> dung, GIU PENDING, luu _blocked."""
    cr = _crawler(tmp_path)
    _seed(cr, ["BLK001", "NEXT02"])
    fake = _FakeClient([BLOCKED_ACCESS_DENIED, GOOD_WITH_CAPTCHA_WORD])
    cr._online_client = lambda: fake
    stats = cr.crawl_details(online=True, limit=2)
    assert fake.calls == 1                     # dung ngay o tin dau nghi chan
    assert stats["failed"] == 0
    assert _status(cr, "BLK001") == "PENDING"  # khong bi mark_failed
    assert _status(cr, "NEXT02") == "PENDING"  # tin sau khong bi dong
    bdir = Path(cr.raw_dir).parent / "_blocked"
    assert (bdir / "BLK001.html").exists()
    # KHONG sinh envelope cho tin bi chan
    assert list(Path(cr.raw_dir).rglob("BLK001*")) == []


# ---- Phuong an B: chuong 5xx lien tiep (500/502/503/504) ---------------
def _server(status: int) -> requests.HTTPError:
    """Ngoai le HTTPError co response.status_code = status (danh dau 5xx/429)."""
    return _http_error(status)


def _good(marker: str) -> str:
    """Trang TOT duoc biet noi dung theo marker de content_hash KHAC nhau
    (neu khung, hai tin giong het se bi gan 'repost' chu khong phai 'success')."""
    return GOOD_WITH_CAPTCHA_WORD.replace(">ABC<", f">ABC-{marker}<")


def test_three_consecutive_503_stops_keeps_pending(tmp_path, caplog):
    """(a) 3 lan 503 lien tiep -> break; 3 tin PENDING; 0 FAILED; log ro ly do."""
    import logging
    caplog.set_level(logging.WARNING, logger="careerviet.crawler")
    cr = _crawler(tmp_path)
    _seed(cr, ["S1", "S2", "S3", "S4"])        # 4 record nhung limit=3
    fake = _FakeClient([_server(503), _server(503), _server(503), GOOD_WITH_CAPTCHA_WORD])
    cr._online_client = lambda: fake
    stats = cr.crawl_details(online=True, limit=3)
    assert fake.calls == 3                      # dung ngay khi du N=3, khong xin S4
    assert stats["failed"] == 0                 # khong mark_failed chuoi bao N
    for j in ("S1", "S2", "S3"):
        assert _status(cr, j) == "PENDING"      # chuoi cuoi GIU PENDING
    assert _status(cr, "S4") == "PENDING"       # tin sau khong bi dong
    assert any("chuoi 5xx lien tiep" in r.getMessage().lower() for r in caplog.records)


def test_isolated_503_flushed_failed_when_success(tmp_path):
    """(b) 503,200,503,200 -> cac tin 503 roi rac thanh FAILED, tin 200 DONE."""
    cr = _crawler(tmp_path)
    _seed(cr, ["A1", "B2", "A3", "B4"])
    fake = _FakeClient([_server(503), _good("B2"),
                        _server(503), _good("B4")])
    cr._online_client = lambda: fake
    stats = cr.crawl_details(online=True, limit=4)
    assert _status(cr, "A1") == "FAILED"        # flush khi B2 thanh cong (chuoi gian)
    assert _status(cr, "B2") == "DONE"
    assert _status(cr, "A3") == "FAILED"
    assert _status(cr, "B4") == "DONE"
    assert stats["failed"] == 2 and stats["success"] == 2


def test_two_503_at_end_flushed_failed(tmp_path):
    """(c) 2 lan 503 roi het danh sach (duoi N=3) -> het vong flush thanh FAILED."""
    cr = _crawler(tmp_path)
    _seed(cr, ["C1", "C2"])
    fake = _FakeClient([_server(503), _server(503)])
    cr._online_client = lambda: fake
    stats = cr.crawl_details(online=True, limit=2)
    assert _status(cr, "C1") == "FAILED"
    assert _status(cr, "C2") == "FAILED"
    assert stats["failed"] == 2


def test_storm_after_successes_only_trailing_pending(tmp_path):
    """(d) 200,200,503,503,503 -> chi 3 tin cuoi PENDING, 2 tin 200 dau van DONE."""
    cr = _crawler(tmp_path)
    _seed(cr, ["D1", "D2", "S3", "S4", "S5"])
    fake = _FakeClient([_good("D1"), _good("D2"),
                        _server(503), _server(503), _server(503)])
    cr._online_client = lambda: fake
    stats = cr.crawl_details(online=True, limit=5)
    assert _status(cr, "D1") == "DONE" and _status(cr, "D2") == "DONE"
    for j in ("S3", "S4", "S5"):
        assert _status(cr, j) == "PENDING"
    assert stats["success"] == 2 and stats["failed"] == 0
    assert fake.calls == 5


def test_429_still_stops_immediately(tmp_path):
    """(e) 429 van dung tuc thi nhu cu (khong phai 5xx -> khong dem chuoi)."""
    cr = _crawler(tmp_path)
    _seed(cr, ["E1", "E2"])
    fake = _FakeClient([_server(429), GOOD_WITH_CAPTCHA_WORD])
    cr._online_client = lambda: fake
    stats = cr.crawl_details(online=True, limit=2)
    assert fake.calls == 1
    assert stats["failed"] == 0
    assert _status(cr, "E1") == "PENDING"
    assert _status(cr, "E2") == "PENDING"
