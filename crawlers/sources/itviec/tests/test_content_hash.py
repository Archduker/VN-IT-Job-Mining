# -*- coding: utf-8 -*-
"""Unit tests OFFLINE cho content_hash LAI của ITViec (Phương án A — đã duyệt).

Chạy không cần mạng / không cần dữ liệu crawl:
  python crawlers/sources/itviec/tests/test_content_hash.py
hoặc:
  pytest crawlers/sources/itviec/tests/test_content_hash.py -v

5 kịch bản nghiệm thu (theo yêu cầu người dùng):
  1. HTML không đổi + JSON-LD không đổi  -> hash không đổi.
  2. Chỉ baseSalary đổi                 -> hash ĐỔI.
  3. Chỉ skills đổi                      -> hash ĐỔI.
  4. Chỉ UI (ngoài container) đổi        -> hash không đổi.
  5. Chỉ field KHÔNG theo dõi đổi        -> hash không đổi.
"""

import copy
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from crawlers.sources.itviec import config as C
from crawlers.sources.itviec import parser

FIXTURE_HTML = """<html><body>
<nav>Menu việc làm itviec</nav>
<main>
  <aside class="company-box">Nhà tuyển dụng: FPT — logo xyz</aside>
  <section class="job-content">
    <h2>Mô tả công việc</h2><p>Viết backend bằng Python, Django.</p>
    <h2>Yêu cầu công việc</h2><p>Tối thiểu 3 năm kinh nghiệm.</p>
    <h2>Tại sao bạn sẽ yêu thích làm việc tại đây</h2><p>Môi trường agile, lương tốt.</p>
  </section>
</main>
<footer>Copyright itviec 2026</footer>
</body></html>"""

FIXTURE_JSONLD = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    "title": "Senior Python Engineer",
    "description": "<p>Mô tả công việc…</p>",
    "skills": "Python, Django",
    "employmentType": "FULL_TIME",
    "experienceRequirements": "3 năm",
    "jobLocation": [{"@type": "Place", "address": {"addressLocality": "Hà Nội"}}],
    "jobBenefits": "Bảo hiểm full salary",
    "baseSalary": {"@type": "MonetaryAmount", "currency": "VND",
                   "value": {"@type": "QuantitativeValue", "minValue": 30, "maxValue": 50, "unitText": "MONTH"}},
    "hiringOrganization": {"@type": "Organization", "name": "FPT"},
    "validThrough": "2026-12-31",
    # Các field KHÔNG nằm trong danh sách theo dõi:
    "datePosted": "2026-10-01",
    "industry": "Information Technology",
    "directApply": True,
    "potentialAction": {"@type": "SeekToAction", "target": "https://itviec.com/apply?url={url}"},
}


def _h(html, jsonld):
    return parser.compute_content_hash(html, jsonld)


def test_same_inputs_same_hash():
    assert _h(FIXTURE_HTML, FIXTURE_JSONLD) == _h(FIXTURE_HTML, FIXTURE_JSONLD)


def test_baseSalary_change_changes_hash():
    m = copy.deepcopy(FIXTURE_JSONLD)
    m["baseSalary"]["value"]["minValue"] = 99
    assert _h(FIXTURE_HTML, m) != _h(FIXTURE_HTML, FIXTURE_JSONLD)


def test_skills_change_changes_hash():
    m = copy.deepcopy(FIXTURE_JSONLD)
    m["skills"] = "Go, Kubernetes, Rust"
    assert _h(FIXTURE_HTML, m) != _h(FIXTURE_HTML, FIXTURE_JSONLD)


def test_ui_only_change_keeps_hash():
    html2 = FIXTURE_HTML.replace("Copyright itviec 2026", "Copyright itviec 2027")  # footer, ngoài container
    html2 = html2.replace("logo xyz", "logo abc")  # aside, ngoài section.job-content
    assert _h(html2, FIXTURE_JSONLD) == _h(FIXTURE_HTML, FIXTURE_JSONLD)


def test_untracked_field_change_keeps_hash():
    m = copy.deepcopy(FIXTURE_JSONLD)
    m["datePosted"] = "2099-01-01"
    m["potentialAction"]["target"] = "https://itviec.com/other?url={url}"
    m["directApply"] = False
    m["industry"] = "Banking"
    assert _h(FIXTURE_HTML, m) == _h(FIXTURE_HTML, FIXTURE_JSONLD)


def test_canonical_jsonld_excludes_untracked():
    canon = parser.build_canonical_jsonld(FIXTURE_JSONLD)
    assert set(canon.keys()) == set(C.HASH_JSONLD_FIELDS)
    for bad in ("datePosted", "industry", "directApply", "potentialAction", "@type", "@context"):
        assert bad not in canon


def test_hash_is_64_hex():
    assert len(_h(FIXTURE_HTML, FIXTURE_JSONLD)) == 64


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
    print(f"\n{passed}/{len(fns)} offline tests passed.")
    sys.exit(0 if passed == len(fns) else 1)
