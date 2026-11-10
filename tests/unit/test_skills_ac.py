from processing.extraction.sections import Bullet, split_sections
from processing.extraction.skills import SkillMatcher, extract_skills, load_taxonomy, short_alias_candidates

TAX = [{"canonical": "BI", "slug": "bi", "group": "g", "aliases": ["bi", "power bi"]},
       {"canonical": "Python", "slug": "python", "group": "g", "aliases": ["python"]},
       {"canonical": "Docker", "slug": "docker", "group": "g", "aliases": ["docker"]},
       {"canonical": "Kubernetes", "slug": "kubernetes", "group": "g", "aliases": ["kubernetes", "k8s"]}]


def slugs(m, text):
    return [h.slug for h in m.find(text)]


def test_short_alias_not_on_fold_path():
    m = SkillMatcher(TAX)
    assert slugs(m, "Bị phạt nặng, bí quyết") == []
    assert slugs(m, "Kinh nghiệm BI") == []  # chưa duyệt = không dùng


def test_short_alias_case_sensitive_when_approved():
    m = SkillMatcher(TAX, [("bi", "BI")])
    assert slugs(m, "Kinh nghiệm BI và Power BI") == ["bi", "bi"]
    assert slugs(m, "Bị phạt nặng, bi kịch") == []


def test_real_taxonomy_symbols():
    m = SkillMatcher(load_taxonomy())
    got = {h.slug for h in m.find("Thành thạo C++, Node.js và C#/.NET")}
    assert {"cpp", "csharp"} <= got
    assert "c" not in got and "java" not in {h.slug for h in m.find("JavaScript developer")}


def test_levels_and_mentions():
    m = SkillMatcher(TAX)
    b = [Bullet(0, "uu_tien", "Biết Docker", "S7.4"), Bullet(1, "yeu_cau", "Docker và Python", "S7.2"),
         Bullet(2, "phuc_loi", "Học Python miễn phí", "S7.2")]
    rows, hits = extract_skills(b, m)
    d = {r["slug"]: r for r in rows}
    assert (d["docker"]["level"], d["docker"]["weight"], d["docker"]["n_mentions"]) == ("required", 1.0, 2)
    assert d["python"]["n_mentions"] == 1  # phúc lợi không quét
    assert set(hits) == {0, 1}


def test_preferred_only():
    rows, _ = extract_skills(split_sections("", "Ưu tiên Docker", cues=["uu tien"]), SkillMatcher(TAX))
    assert (rows[0]["level"], rows[0]["weight"]) == ("preferred", 0.5)


def test_meta_skill_marked_via_meta():
    rows, _ = extract_skills([], SkillMatcher(TAX), ["Docker"])
    assert rows[0]["via"] == "meta"


def test_span_maps_back_to_original_with_diacritics():
    m = SkillMatcher(TAX)
    t = "Có kinh nghiệm Kubernetes tốt"
    h = m.find(t)[0]
    assert t[h.start:h.end] == "Kubernetes"


def test_candidates_are_unapproved():
    c = short_alias_candidates(load_taxonomy())
    assert c and all(x["approved"] is False for x in c)
