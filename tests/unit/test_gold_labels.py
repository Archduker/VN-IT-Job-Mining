"""Schema nhãn gold và mẫu 100 JD (docs/spec/preprocessing/spec/PH1_gold_va_profiling.md)."""
import json

import pytest

from preprocessing.common.gold import coverage, load_gold, validate_label
from scripts.build_gold_sample import quota


def _write(tmp_path, labels):
    p = tmp_path / "gold_labels.json"
    p.write_text(json.dumps({"version": 1, "labels": labels}), encoding="utf-8")
    return p


def test_quota_is_100_with_12_or_13_per_source():
    q = quota(100)
    assert sum(q.values()) == 100 and set(q.values()) == {12, 13}


def test_empty_fields_are_valid_unassigned(tmp_path):
    labels = load_gold(_write(tmp_path, {"a": {}, "b": {"it": "non_it"}}))
    assert coverage(labels)["it"] == 1


def test_full_label_is_valid(tmp_path):
    lab = {
        "it": "it", "salary": {"kind": "value", "min": 15e6, "max": None, "currency": "VND", "period": "month"},
        "experience_years": 2, "seniority": "Junior",
        "location": {"provinces": ["ha_noi"], "work_mode": "hybrid"},
        "sections": [{"section": "yeu_cau", "start": 0, "end": 10}], "skills": [{"name": "Python", "level": "required"}],
    }
    assert load_gold(_write(tmp_path, {"a": lab}))["a"]["seniority"] == "Junior"


@pytest.mark.parametrize("lab", [
    {"seniority": "Guru"},
    {"location": {"provinces": ["atlantis"], "work_mode": "remote"}},
    {"salary": {"kind": "value", "min": 5, "max": 1, "currency": "USD", "period": "month"}},
    {"salary": {"kind": "value", "min": 1, "currency": "USD"}},
    {"experience_years": -1},
    {"sections": [{"section": "x", "start": 0, "end": 3}]},
    {"skills": [{"name": "Go", "level": "meh"}]},
    {"unknown_field": 1},
])
def test_bad_labels_raise(lab):
    with pytest.raises(ValueError):
        validate_label("a", lab)
