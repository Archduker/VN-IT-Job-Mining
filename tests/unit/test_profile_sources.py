import unicodedata

import pandas as pd

from scripts.profile_sources import missing_rates, text_quality


def test_missing_rate_conventions():
    df = pd.DataFrame({"a": [None, "Đang cập nhật"], "b": ["x", "y"], "c": ["0", []]})
    r = missing_rates(df, ["a", "b", "c"])
    assert r == {"a": 1.0, "b": 0.0, "c": 1.0}


def test_text_quality_nfd_vs_nfc():
    nfc = "Tuyển dụng Việt"
    nfd = unicodedata.normalize("NFD", nfc)
    q = text_quality(pd.DataFrame({"raw_description_text": [nfd, nfc]}))
    assert q["nfd"] == 50.0


def test_text_quality_html_and_no_diacritic():
    df = pd.DataFrame({"raw_description_text": ["<p>a</p>", "a &amp; b", "yeu cau kinh nghiem Python", "Yêu cầu kinh nghiệm"]})
    q = text_quality(df)
    assert q["html"] == 50.0 and q["no_diacritic"] == 25.0
