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


# K8.17: nhãn type (tool | concept) chỉ lấy từ lô đã duyệt
import build_skills_v2 as B  # noqa: E402
import propose_skill_types as PT  # noqa: E402


def _batch(approved, items):
    return {"_meta": {"approved": approved}, "items": items}


def _item(slug, de_xuat, lop=None, quyet_dinh=None):
    return {"slug": slug, "de_xuat": de_xuat, "lop_hoi": lop, "quyet_dinh": quyet_dinh}


def test_types_only_from_approved_batches():
    types, errs, appr = B.load_types([
        ("types_t01", _batch({"date": "2026-11-19"}, [_item("python", "tool"), _item("agile", "concept")])),
        ("types_t02", _batch(None, [_item("docker", "tool")])),
    ])
    assert types == {"python": "tool", "agile": "concept"} and errs == [] and appr == ["types_t01"]


def test_quyet_dinh_and_class_answer_override_proposal():
    types, errs, _ = B.load_types([("t", _batch({"lop_hoi": {"chuan": "concept"}}, [
        _item("rest_api", "hoi", "chuan"), _item("debugging", "tool", quyet_dinh="concept"),
        _item("ccna", "hoi", "chung_chi")]))])
    assert types == {"rest_api": "concept", "debugging": "concept"}
    assert errs == ["t: ccna chưa có nhãn ('hoi')"]       # lớp chưa chốt thì dừng, không tự quyết


def test_attach_types_null_for_unreviewed_and_non_technical():
    skills = [{"slug": "python", "kind": "technical"}, {"slug": "kafka", "kind": "technical"},
              {"slug": "communication", "kind": "soft"}]
    errs = B.attach_types(skills, {"python": "tool", "ghost": "tool"})
    assert [s["type"] for s in skills] == ["tool", None, None]
    assert errs == ["type: slug không có trong từ điển 'ghost'"]


def test_review_list_parses_and_rejects_duplicates(tmp_path):
    p = tmp_path / "types_claude.txt"
    p.write_text("# chú thích\ntool linux figma\ncon erp\nhoi:chuan rest_api\n", encoding="utf-8")
    assert PT.load_review(p) == {"linux": ("tool", None), "figma": ("tool", None), "erp": ("concept", None),
                                 "rest_api": ("hoi", "chuan")}
    p.write_text("tool linux\ncon linux\n", encoding="utf-8")
    with pytest.raises(ValueError, match="linux"):
        PT.load_review(p)


def test_propose_rule_uses_evidence_then_group():
    assert PT.propose("databases", {"tech_stack": 9, "keywords": 1})[0] == "tool"
    assert PT.propose("databases", {"tech_stack": 0, "keywords": 17})[0] == "hoi"    # nhóm và bằng chứng ngược nhau
    assert PT.propose("methodology_pm", {})[0] == "concept"                          # ít bằng chứng: theo nhóm
    assert PT.propose("certifications", {})[0] == "hoi"                              # nhóm ranh giới


def test_read_lines_keeps_hash_inside_names(tmp_path):
    (tmp_path / "b001.txt").write_text("# lô 1\nS 54 csharp programming_languages n=C#  # ghi chú\n", encoding="utf-8")
    (tmp_path / "types_claude.txt").write_text("tool python\n", encoding="utf-8")   # không phải lệnh từ điển
    assert B.read_lines(tmp_path) == [("b001.txt:2", "S 54 csharp programming_languages n=C#")]


# P2: bước 08 ghi `type`; skill_view là định nghĩa duy nhất của K-tool / K-concept / K-soft
import pandas as pd  # noqa: E402
from processing.extraction.skills import skill_view  # noqa: E402


def test_rows_carry_type():
    r = rows_of("Thành thạo Python, Agile và giao tiếp tốt")
    assert r["python"]["type"] == "tool" and r["agile"]["type"] == "concept"
    assert r["communication"]["type"] is None


def test_skill_view_definitions():
    js = pd.DataFrame([
        {"slug": "python", "kind": "technical", "type": "tool", "via": "meta"},
        {"slug": "agile", "kind": "technical", "type": "concept", "via": "text"},
        {"slug": "rare_tool", "kind": "technical", "type": None, "via": "text"},
        {"slug": "communication", "kind": "soft", "type": None, "via": "text"},
        {"slug": "english", "kind": "language", "type": None, "via": "text_vi"},
    ])
    assert list(skill_view(js, "tool")["slug"]) == ["python"]           # thẻ sàn vẫn giữ; null không vào
    assert list(skill_view(js, "concept")["slug"]) == ["agile"]
    assert list(skill_view(js, "soft")["slug"]) == ["communication", "english"]
    assert len(skill_view(js, "all")) == 5
    with pytest.raises(ValueError, match="type"):
        skill_view(js.drop(columns=["type"]), "tool")
    with pytest.raises(ValueError, match="view lạ"):
        skill_view(js, "core")
