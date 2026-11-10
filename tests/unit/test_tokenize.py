from processing.extraction.skills import SkillMatcher, load_taxonomy
from processing.transformation.tokenize import domain_stopwords, remove_stopwords, tokenize


def test_skills_kept_as_placeholders():
    m = SkillMatcher(load_taxonomy())
    t = "Thành thạo C++, Node.js và C#"
    toks = tokenize(t, m.find(t))
    assert {"sk_cpp", "sk_csharp"} <= set(toks)
    assert not {"node", "js", "+", "#"} & set(toks)
    assert not any(x in toks for x in ["thành thạo "]) and "," not in toks


def test_vietnamese_compounds_kept():
    toks = tokenize("Có kinh nghiệm lập trình viên backend tại công ty phần mềm")
    assert {"kinh nghiệm", "công ty", "phần mềm"} <= set(toks)


def test_domain_stopwords_never_skill():
    docs = [["sk_python", "làm", "x"], ["sk_python", "làm", "y"], ["sk_python", "làm", "z"]]
    dom = domain_stopwords(docs, 0.6)
    assert "làm" in dom and not any(k.startswith("sk_") for k in dom)
    assert remove_stopwords(["sk_python", "làm", "x"], ["x"], dom) == ["sk_python"]
