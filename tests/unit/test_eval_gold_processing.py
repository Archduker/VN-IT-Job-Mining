import json

from processing.evaluate import section_accuracy, skills_f1
from processing.extraction.sections import Bullet
from processing.extraction.skills import SkillMatcher

# Fixture tay tối thiểu chỉ để chạy đường code, KHÔNG phải nhãn gold thật.
TEXT = "Làm API\nBiết Docker\n"
LAB = {"j1": {"sections": [{"section": "mo_ta", "start": 0, "end": 8}, {"section": "yeu_cau", "start": 8, "end": 19}],
              "skills": [{"name": "Docker", "level": "required"}, {"name": "Cobol", "level": "required"}]}}
TAX = [{"canonical": "Docker", "slug": "docker", "group": "g", "aliases": ["docker"]}]


def test_section_accuracy():
    pred = lambda j: [Bullet(0, "mo_ta", "Làm API", "S7.2"), Bullet(1, "mo_ta", "Biết Docker", "S7.2"), Bullet(2, "mo_ta", "ngoài vùng", "S7.2")]
    r = section_accuracy(LAB, {"j1": TEXT}, {"j1": "topcv"}, pred)
    assert r["_all"]["bullets"] == 2 and r["_all"]["accuracy"] == 0.5


def test_skills_f1_counts_outside_taxonomy_as_fn():
    pred = lambda j: [{"slug": "docker", "level": "required", "via": "text"}, {"slug": "docker", "level": "required", "via": "meta"}]
    r = skills_f1(LAB, {"j1": "topcv"}, pred, SkillMatcher(TAX))
    m = r["micro"]["_all"]
    assert (m["tp"], m["fp"], m["fn"]) == (1, 0, 1) and r["labels_outside_taxonomy"] == {"cobol": 1}


def test_script_without_labels(tmp_path, capsys):
    import scripts.eval_gold_processing as s
    assert s.main(["--gold", str(tmp_path / "x.json")]) == 0
    assert "chưa có nhãn" in capsys.readouterr().out
