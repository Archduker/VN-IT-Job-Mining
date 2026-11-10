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


def test_build_gold_sample_from_processed_table(tmp_path):
    import pandas as pd
    from preprocessing.common import SOURCES
    from scripts.build_gold_sample import build
    rows = [{"job_id_global": f"{s}_{i}", "source_platform": s, "description_clean": f"Làm việc {i}", "requirements_clean": "Biết Docker"}
            for s in SOURCES for i in range(20)]
    p = tmp_path / "all.parquet"
    pd.DataFrame(rows).to_parquet(p)
    a, b = build(42, 100, p), build(42, 100, p)
    assert len(a["items"]) == 100 and a["sample_id"] == b["sample_id"]
    assert a["items"][0]["text"] == f"{a['items'][0]['description_clean']}\n\n{a['items'][0]['requirements_clean']}"


def test_benefits_label_validated_and_scored():
    import pytest
    from preprocessing.common.gold import validate_label
    validate_label("j", {"benefits": ["Bảo hiểm", "Thưởng"]}, set())
    validate_label("j", {"benefits": "none"}, set())
    with pytest.raises(ValueError):
        validate_label("j", {"benefits": "Bảo hiểm"}, set())
    from scripts.eval_gold_processing import benefits_prf
    items = {"j": {"benefits_list": ["Bảo hiểm sức khỏe", "Du lịch hàng năm"], "description_clean": ""}}
    r = benefits_prf({"j": {"benefits": ["Bảo hiểm", "Thưởng"]}}, items)
    assert (r["tp"], r["fp"], r["fn"]) == (1, 1, 1)


def test_benefits_label_validated_and_scored():
    import pytest
    from preprocessing.common.gold import validate_label
    validate_label("j", {"benefits": ["Bảo hiểm", "Thưởng"]}, set())
    validate_label("j", {"benefits": "none"}, set())
    with pytest.raises(ValueError):
        validate_label("j", {"benefits": "Bảo hiểm"}, set())
    from scripts.eval_gold_processing import benefits_prf
    items = {"j": {"benefits_list": ["Bảo hiểm sức khỏe", "Du lịch hàng năm"], "description_clean": ""}}
    r = benefits_prf({"j": {"benefits": ["Bảo hiểm", "Thưởng"]}}, items)
    assert (r["tp"], r["fp"], r["fn"]) == (1, 1, 1)
