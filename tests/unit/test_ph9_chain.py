"""PH9: chuỗi driver (INPUT_MISSING, thứ tự), khối samples, profiling after_clean đọc cột đã làm sạch."""
import json
import unicodedata

import pandas as pd

from preprocessing.common.samples import inject_samples, pair_samples
from scripts import run_preprocessing as D
from scripts.profile_sources import AFTER_TEXT_COLS, text_quality


def test_chain_order_covers_processing():
    assert D.CHAIN == ("01_clean", "01b_deduplication", "02_integration", "03_transformation",
                       "04_normalization", "05_encoding", "07_sections", "08_skills", "09_tokens",
                       "10_features", "12_tfidf", "12_e5")


def test_missing_inputs_listed_not_zero(tmp_path):
    assert D.missing_inputs("03_transformation", ["glints"], tmp_path)
    p = tmp_path / "data" / "preprocessing" / "03_transformation"
    p.mkdir(parents=True)
    (p / "all.parquet").write_bytes(b"x")
    assert D.missing_inputs("04_normalization", ["glints"], tmp_path) == []
    assert D.missing_inputs("09_tokens", ["glints"], tmp_path)  # đọc 04, chưa có
    assert len(D.missing_inputs("10_features", ["glints"], tmp_path)) == 3  # thiếu 04, 09, 08


def test_dry_run_chain_marks_input_missing(tmp_path):
    res = D.run_chain(["03_transformation"], ["glints"], dry_run=True, root=tmp_path, write_summary=False)
    assert res[0]["status"] == "INPUT_MISSING" and res[0]["output"] is None and res[0]["input"] is None


def test_pair_samples_prefers_changed_and_is_seeded():
    n = 20
    before = pd.DataFrame({"job_id_global": [f"j{i}" for i in range(n)], "source_platform": ["a"] * n,
                           "raw": [f"x{i}" for i in range(n)]})
    after = pd.DataFrame({"job_id_global": before.job_id_global,
                          "clean": [f"x{i}" if i % 5 else f"Y{i}" for i in range(n)]})
    s1 = pair_samples(before, after, [("clean", "raw", "clean")])
    s2 = pair_samples(before, after, [("clean", "raw", "clean")])
    assert s1 == s2 and len(s1["a"]) == 3
    assert all(r["before"] != r["after"] for r in s1["a"])
    assert set(s1["a"][0]) >= {"job_id", "source", "field", "before", "after"}


def test_inject_samples_into_report_file(tmp_path):
    d = tmp_path / "03_transformation"
    d.mkdir()
    (d / "glints.json").write_text(json.dumps({"mode": "applied"}))
    (d / "_all.json").write_text(json.dumps({"mode": "applied"}))
    inject_samples(tmp_path, "03_transformation", {"glints": [{"job_id": "1", "source": "glints", "field": "f",
                                                             "before": "a", "after": "b"}]})
    assert json.loads((d / "glints.json").read_text())["samples"][0]["after"] == "b"
    assert len(json.loads((d / "_all.json").read_text())["samples"]) == 1


def test_after_clean_profiles_clean_columns():
    nfc = "Tuyển dụng Việt"
    df = pd.DataFrame({"raw_description_text": [unicodedata.normalize("NFD", nfc)], "description_clean": [nfc]})
    assert text_quality(df, AFTER_TEXT_COLS)["nfd"] == 0.0
    assert text_quality(df)["nfd"] == 100.0


def test_plan_objects_lists_pipeline_keys():
    from preprocessing.common import r2_export as X
    keys = [o["key"] for o in X.plan_objects(build=False)]
    assert all(k.startswith(("staging/", "curated/", "pipeline/")) for k in keys)
    assert X.pipeline_key("09_tokens", "all.parquet").endswith("pipeline/09_tokens/all.parquet")


def test_extraction_step_finishes_both_07_and_08_reports(tmp_path, monkeypatch):
    """07 và 08 do cùng một lần gọi ghi lại cả hai báo cáo: chạy một bước phải gắn mẫu cho cả hai (19/11)."""
    import sys
    import types

    class Rep:
        data = {"input": {"rows": 1}, "output": {"rows": 1}, "dropped": [], "mode": "applied", "source": "topcv"}

    fake = types.ModuleType("processing.extraction.run")
    fake.run = lambda sources, dry_run: {"07_sections": {"topcv": Rep()}, "08_skills": {"topcv": Rep()}}
    monkeypatch.setitem(sys.modules, "processing.extraction.run", fake)
    monkeypatch.setattr(D, "missing_inputs", lambda *a: [])
    calls = []
    monkeypatch.setattr(D, "_finish_reports", lambda step, *a: calls.append(step))
    D.run_chain(["08_skills"], ["topcv"], dry_run=True, root=tmp_path, write_summary=False)
    assert calls == ["07_sections", "08_skills"]
