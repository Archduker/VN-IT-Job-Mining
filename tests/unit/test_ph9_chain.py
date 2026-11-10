"""PH9: chuỗi driver (INPUT_MISSING, thứ tự), khối samples, profiling after_clean đọc cột đã làm sạch."""
import json
import unicodedata

import pandas as pd

from preprocessing.common.samples import inject_samples, pair_samples
from scripts import run_preprocessing as D
from scripts.profile_sources import AFTER_TEXT_COLS, text_quality


def test_chain_order_covers_processing():
    assert D.CHAIN == ("01_clean", "01b_deduplication", "02_integration", "03_transformation",
                       "04_normalization", "05_encoding", "07_sections", "08_skills", "09_tokens")


def test_missing_inputs_listed_not_zero(tmp_path):
    assert D.missing_inputs("03_transformation", ["glints"], tmp_path)
    p = tmp_path / "data" / "preprocessing" / "03_transformation"
    p.mkdir(parents=True)
    (p / "all.parquet").write_bytes(b"x")
    assert D.missing_inputs("04_normalization", ["glints"], tmp_path) == []
    assert D.missing_inputs("09_tokens", ["glints"], tmp_path)  # đọc 04, chưa có


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
