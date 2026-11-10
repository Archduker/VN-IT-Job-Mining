from processing.extraction.sections import load_approved, load_headings, split_sections

HEAD = {"quyen loi": "phuc_loi"}
CUES = ["uu tien", "nice to have"]


def test_default_by_field():
    b = split_sections("- Phát triển API\n- Review code", "- Có 2 năm kinh nghiệm\n- Biết Docker")
    assert [(x.section, x.rule) for x in b] == [("mo_ta", "S7.2")] * 2 + [("yeu_cau", "S7.2")] * 2
    assert [x.idx for x in b] == [0, 1, 2, 3]


def test_heading_switches_and_is_not_bullet():
    b = split_sections("- Làm API\nQuyền lợi:\n- Thưởng tháng 13", "", headings=HEAD)
    assert [x.text for x in b] == ["Làm API", "Thưởng tháng 13"]
    assert (b[1].section, b[1].rule) == ("phuc_loi", "S7.3")


def test_priority_cue():
    b = split_sections("", "Ưu tiên có kinh nghiệm Kubernetes", cues=CUES)
    assert (b[0].section, b[0].rule) == ("uu_tien", "S7.4")


def test_cue_heading_applies_to_following_lines():
    b = split_sections("", "Ưu tiên:\n- Biết Docker", cues=CUES)
    assert [(x.text, x.section) for x in b] == [("Biết Docker", "uu_tien")]


def test_empty_dicts_only_default():
    b = split_sections("Quyền lợi:\n- Thưởng", None)
    assert len(b) == 2 and {x.section for x in b} == {"mo_ta"}


def test_unapproved_not_loaded(tmp_path):
    p = tmp_path / "h.json"
    p.write_text('{"items":[{"phrase":"quyền lợi","section":"phuc_loi","approved":false},'
                 '{"phrase":"Yêu cầu","section":"yeu_cau","approved":true}]}', encoding="utf-8")
    assert load_headings(p) == {"yeu cau": "yeu_cau"}
    assert len(load_approved(p)) == 1
    assert load_headings(tmp_path / "none.json") == {}
