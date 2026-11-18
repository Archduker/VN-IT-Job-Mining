"""K8.15: bước 08 dùng processing/dictionaries/skills_v2.json (ví dụ ở prompt 08_skills_v2 mục 5)."""
import json

import pytest

from processing.extraction.sections import Bullet
from processing.extraction.skills import extract_skills, load_skills_v2, matcher_from_v2

D = load_skills_v2()
M = matcher_from_v2(D)


def rows_of(text, meta=()):
    rows, _ = extract_skills([Bullet(0, "yeu_cau", text, "S7.2")] if text else [], M, meta)
    return {r["slug"]: r for r in rows}


def test_react_family_with_parent():
    r = rows_of("Thành thạo ReactJS, React Native và Node.js")
    assert {"react", "react_native", "nodejs"} <= set(r)
    assert r["react_native"]["parent"] == "react"
    assert r["react"]["level"] == "required"


def test_databases_point_to_sql():
    r = rows_of("Có kinh nghiệm với MySQL hoặc PostgreSQL")
    assert r["mysql"]["parent"] == r["postgresql"]["parent"] == "sql"


def test_platform_industry_tag_is_not_skill():
    assert rows_of("", ["IT - Phần mềm"]) == {}


def test_platform_soft_tag():
    r = rows_of("", ["Team Leadership"])
    assert r["leadership"]["kind"] == "soft" and r["leadership"]["via"] == "meta"


def test_language_kind():
    assert rows_of("Tiếng Anh giao tiếp tốt")["english"]["kind"] == "language"


def test_go_short_alias_and_go_live():
    assert {"golang", "rust"} <= set(rows_of("Kinh nghiệm Go hoặc Rust"))
    assert "golang" not in rows_of("Sẵn sàng hỗ trợ Go-live và go-live hệ thống")


def test_diacritics_must_match_alias_form():
    assert "active_listening" not in rows_of("Am hiểu công nghệ mới")
    assert "technical_drawing" not in rows_of("Kiến thức cơ bản về mạng")
    assert "technical_drawing" in rows_of("Đọc hiểu bản vẽ kỹ thuật")


def test_unaccented_text_still_matches():
    assert "communication" in rows_of("Ky nang giao tiep tot")


def test_degree_phrase_blocks_nested_skill():
    r = rows_of("Tốt nghiệp ngành Khoa học máy tính")
    assert "machine_learning" not in r and "__block__" not in r
    assert "machine_learning" in rows_of("Có kinh nghiệm học máy")


def test_r_and_d_is_not_r_language():
    assert "r_lang" not in rows_of("Phòng R&D cần người")


def test_rows_carry_kind_parent_and_name():
    r = rows_of("Thành thạo Python")["python"]
    assert r["kind"] == "technical" and r["skill"] == "Python" and "parent" in r


def test_unapproved_dictionary_stops(tmp_path):
    p = tmp_path / "skills_v2.json"
    p.write_text(json.dumps({"_meta": {"approved": False}, "skills": [], "not_skill": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="skills_v2.json chưa được duyệt"):
        load_skills_v2(p)
