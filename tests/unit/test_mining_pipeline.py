"""mining/run_mining_pipeline.py: chạy đủ 4 bước trên dữ liệu giả, ghi artifacts trong tmp_path."""

import json

import joblib
import pandas as pd
import pytest

from mining import run_mining_pipeline as rmp
from mining.config import ARTIFACT_FILES

PARQUETS = ["rules", "clusters", "anomalies", "shap"]


def test_cli_synthetic_writes_all_artifacts(tmp_path, capsys):
    rc = rmp.main(["--synthetic", "--synthetic-n", "800", "--out", str(tmp_path)])
    assert rc == 0
    for key in PARQUETS:
        assert (tmp_path / ARTIFACT_FILES[key]).exists(), key
    bundle = joblib.load(tmp_path / ARTIFACT_FILES["model"])
    assert set(bundle) >= {"model", "feature_names", "target"}

    m = json.loads((tmp_path / ARTIFACT_FILES["metrics"]).read_text(encoding="utf-8"))
    assert m["synthetic"] is True
    assert {"association", "clustering", "anomaly", "salary", "sanity_checks", "targets_summary"} <= set(m)
    assert len(m["sanity_checks"]) == 6
    assert "cluster_davies_bouldin" in m["targets_summary"]
    assert m["clustering"]["davies_bouldin_target"] == 1.80
    assert m["artifacts"]["clusters"]["rows"] == 800

    rules = pd.read_parquet(tmp_path / ARTIFACT_FILES["rules"])
    assert {"antecedents", "consequents", "support", "confidence", "lift", "conviction",
            "job_family_scope"} <= set(rules.columns)
    assert all(len(a) >= 1 for a in rules["antecedents"])  # list, không phải chuỗi
    printed = json.loads(capsys.readouterr().out)
    assert "targets" in printed


def test_only_and_dry_run_write_nothing(tmp_path):
    rc = rmp.main(["--synthetic", "--synthetic-n", "400", "--only", "fp", "--dry-run", "--out", str(tmp_path)])
    assert rc == 0 and not any(tmp_path.iterdir())


def test_bad_step_and_missing_inputs_return_error(tmp_path):
    assert rmp.main(["--synthetic", "--only", "foo", "--out", str(tmp_path)]) == 2
    assert rmp.main(["--golden", str(tmp_path / "khong_co.parquet"), "--out", str(tmp_path)]) == 2


@pytest.mark.parametrize("schema", ["old", "new"])
def test_runs_from_parquet_files(tmp_path, schema):
    """Đọc từ file như dữ liệu thật: golden schema mới (Duy/Phát) và features.parquet với tiền tố skill__."""
    from mining.synthetic import make_synthetic_jobs

    b = make_synthetic_jobs(n_jobs=500, seed=5)
    golden, feats = b.golden.copy(), b.features.copy()
    if schema == "old":
        golden = golden.drop(columns=["seniority_level"]).rename(columns={
            "city_normalized": "tinh_chinh", "skills_extracted": "skills_std", "job_title": "job_title_clean"})
        golden["salary_min_vnd_capped"] = golden.pop("salary_min") * 1e6
        golden["salary_max_vnd_capped"] = golden.pop("salary_max") * 1e6
        golden = golden.drop(columns=["salary_avg"])
        feats.columns = [c.replace("skill_", "skill__", 1) if c.startswith("skill_") else c for c in feats.columns]
    gp, fp = tmp_path / "golden.parquet", tmp_path / "features.parquet"
    golden.to_parquet(gp, index=False)
    feats.to_parquet(fp, index=False)
    out = tmp_path / "out"
    rc = rmp.main(["--golden", str(gp), "--features", str(fp), "--encoding-dict", str(tmp_path / "none.json"),
                   "--out", str(out), "--only", "fp,salary", "--no-shap"])
    assert rc == 0
    m = json.loads((out / ARTIFACT_FILES["metrics"]).read_text(encoding="utf-8"))
    assert m["inputs"]["golden"]["sha256_16"]
    assert m["salary"]["subset"]["n_train_subset"] > 100
    assert m["data"]["n_skill_columns"] == feats.shape[1] - 1
