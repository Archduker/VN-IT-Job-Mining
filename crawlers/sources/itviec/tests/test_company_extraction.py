# -*- coding: utf-8 -*-
"""Unit tests OFFLINE cho trích xuất company_name/company_url (chống lỗi sidebar).

Chạy:  python crawlers/sources/itviec/tests/test_company_extraction.py
   hoặc: pytest crawlers/sources/itviec/tests/test_company_extraction.py -q

Kiểm tra cả company_name và company_url ở các bố cục trang khác nhau.
Không gọi mạng.
"""

import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from crawlers.sources.itviec import parser


def page(sidebar, jd_anchors=None, employer_name=None, jsonld_name=None):
    sb = "".join(f'<a class="category-item" href="/nha-tuyen-dung/{s}">{t}</a>' for s, t in sidebar)
    jd = "".join(f'<a href="/nha-tuyen-dung/{s}">{t}</a>' for s, t in (jd_anchors or []))
    em = f'<div class="employer-name">{employer_name}</div>' if employer_name else ""
    jp = ""
    if jsonld_name:
        obj = {"@context": "http://schema.org", "@type": "JobPosting", "title": "T",
               "hiringOrganization": {"@type": "Organization", "name": jsonld_name}}
        jp = '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False) + "</script>"
    return (f"<html><body><nav>{sb}</nav>"
            f'<div class="jd-main">{em}<section class="job-content"><h2>Mô tả</h2><p>x</p>{jd}</section></div>'
            f"{jp}</body></html>")


def _cp(html, job_id):
    rp = parser.parse_detail(html, job_id)
    return rp["company_name"], rp["company_url"]


def test_jsonld_name_mb_bank_sidebar():
    # Sidebar MB Bank đứng TRƯỚC, nhưng JSON-LD là ABBANK -> phải lấy ABBANK, url khớp theo tên
    name, url = _cp(page([("mb-bank", "MB Bank"), ("abbank", "ABBANK")], jsonld_name="ABBANK"),
                    "cvcc-data-analyst-sql-abbank-3801")
    assert name == "ABBANK", name
    assert url == "/nha-tuyen-dung/abbank", url


def test_slug_fallback_when_name_text_differs():
    # Không có anchor nào text == 'VPBank', nhưng slug vpbank nằm trong job_id -> khớp slug, bỏ mb-bank
    name, url = _cp(page([("mb-bank", "MB Bank"), ("vpbank", "VP BANK")], jsonld_name="VPBank"),
                    "data-business-analyst-id12287-vpbank-1219")
    assert name == "VPBank", name
    assert url == "/nha-tuyen-dung/vpbank", url


def test_no_jsonld_uses_employer_anchor_in_jd_main():
    # Không JSON-LD: lấy tên từ .employer-name, url là anchor trong jd-main (KHÔNG phải sidebar mb-bank)
    name, url = _cp(page([("mb-bank", "MB Bank")], jd_anchors=[("acme", "Acme Corp")],
                          employer_name="Acme Corp"), "backend-engineer-acme-01")
    assert name == "Acme Corp", name
    assert url == "/nha-tuyen-dung/acme", url


def test_unresolvable_returns_none():
    # Không JSON-LD, không employer-name, job_id không chứa slug nào trong sidebar -> unknown, không đoán
    name, url = _cp(page([("mb-bank", "MB Bank"), ("techcombank", "Techcombank")]),
                    "senior-engineer-999")
    assert name is None, name
    assert url is None, url


def test_slug_partial_does_not_false_match():
    # anchor slug 'abc' KHÔNG khớp 'abcxyz' trong job_id (phải là nguyên token liên tiếp) -> url None
    name, url = _cp(page([("abc", "ABC Services")], jsonld_name="ABC"), "engineer-abcxyz-1")
    assert name == "ABC", name
    assert url is None, url


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} company-extraction tests passed.")
    sys.exit(0 if passed == len(fns) else 1)
