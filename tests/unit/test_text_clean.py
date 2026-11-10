# -*- coding: utf-8 -*-
"""PH2 bước 2 (T6): làm sạch ký tự. Chuỗi lấy từ dữ liệu thật, job_id ghi ở chú thích."""
import json
import unicodedata
from pathlib import Path

from preprocessing.common import text_clean as tc
from preprocessing.transformation.html_cleaner import strip_html_tags

ROOT = Path(__file__).resolve().parents[2]


def test_dash_normalized():  # careerviet_35C32FB4
    assert tc.clean_text("Tư vấn – Thiết kế — Sản xuất") == "Tư vấn - Thiết kế - Sản xuất"


def test_hidden_char_inside_word():  # topcv_2324178
    assert tc.clean_text("phản biện cá\ufeffc thiết kế") == "phản biện các thiết kế"


def test_zero_width_joiner_line_end():  # glints_369649a4-b509-48ad-a767-e464745bdbb0
    assert tc.clean_text("Môi trường làm việc:\u200d\n- Môi trường product") == "Môi trường làm việc:\n- Môi trường product"


def test_nfd_to_nfc_and_fold():
    s = unicodedata.normalize("NFD", "Khám sức khỏe định kỳ")
    out = tc.clean_text(s)
    assert out == "Khám sức khỏe định kỳ" and tc.is_nfc(out)
    assert tc.make_text_columns(s)[2] == "kham suc khoe dinh ky"


def test_arrow_and_pl_kept():  # topcv_2238387, topdev_2138377
    for s in ("giữ traceability AC <-> test case", "phân tích dữ liệu & P&L; giao tiếp"):
        assert tc.clean_text(s) == s and not tc.html_residual(s)


def test_strip_html_bugs():
    assert strip_html_tags("Kinh nghiệm < 3 năm, lương > 10tr") == "Kinh nghiệm < 3 năm, lương > 10tr"
    assert tc.clean_text("&amp;nbsp;Java") == "Java"
    assert strip_html_tags("<b>Java</b>Script") == "JavaScript"
    assert strip_html_tags("<p>a</p><p>b</p>") == "a\nb"


def test_bullets_unified():
    got = tc.clean_text("• Tham gia\n✔ Có 2–4 năm kinh nghiệm\n+ Biết Java\n* Biết SQL\n- Biết Git")
    assert got == "- Tham gia\n- Có 2-4 năm kinh nghiệm\n- Biết Java\n- Biết SQL\n- Biết Git"
    assert tc.clean_text("+84 912 345 678") == "+84 912 345 678"


def test_loop_until_clean_triple_encoded():
    out, info = tc.clean_text_checked("&amp;amp;lt;b&amp;amp;gt;Java&amp;amp;lt;/b&amp;amp;gt;")
    assert not tc.html_residual(out) and info["residual_html"] is False and out == "Java"


def test_loop_bounded_warns(monkeypatch):
    monkeypatch.setattr(tc, "MAX_RETRIES", 1)
    out, info = tc.clean_text_checked("&amp;amp;lt;b&amp;amp;gt;Java")
    assert out is not None and info["residual_html"] is True  # cảnh báo, không ném lỗi


def test_topdev_fixture():
    d = json.loads((ROOT / "tests/fixtures/topdev/standard.json").read_text(encoding="utf-8"))
    raw = d.get("raw_payload", d)["requirements_original"]
    out = tc.clean_text(raw)
    assert out.startswith("Yêu cầu:\n- ") and "<" not in out and "&ecirc;" not in out


def test_abbreviation_only_in_norm_and_approved_only(tmp_path):
    ab = tc.compile_abbreviations([
        {"canonical": "kinh nghiệm", "variants": ["kn"], "case_sensitive": False, "approved": True},
        {"canonical": "đại học", "variants": ["đh"], "case_sensitive": False, "approved": True},
        {"canonical": "backend", "variants": ["BE"], "case_sensitive": True, "approved": True},
        {"canonical": "cộng tác viên", "variants": ["ctv"], "approved": False},
    ])
    clean, norm, _ = tc.make_text_columns("Tốt nghiệp ĐH, 2 năm kn, ctv", ab)
    assert clean == "Tốt nghiệp ĐH, 2 năm kn, ctv"
    assert norm == "tốt nghiệp đại học, 2 năm kinh nghiệm, ctv"
    assert tc.make_text_columns("Yêu cầu: be curious", ab)[1] == "yêu cầu: be curious"
    assert tc.make_text_columns("BE Java", ab)[1] == "backend java"


def test_shipped_abbreviations_all_unapproved():
    assert tc.load_abbreviations() == []  # file thật chưa có mục nào approved
    data = json.loads((ROOT / "preprocessing/dictionaries/abbreviations.json").read_text(encoding="utf-8"))
    assert data["entries"] and all(e["approved"] is False for e in data["entries"])


def test_fold_keeps_tech():
    assert tc.make_text_columns("Lập trình viên C#/C++ .NET")[2] == "lap trinh vien c#/c++ .net"
