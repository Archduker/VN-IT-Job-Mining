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
    assert rmp.main(["--table", str(tmp_path / "khong_co.parquet"), "--out", str(tmp_path)]) == 2


@pytest.mark.parametrize("step", ["recommend"])
def test_steps_not_built_yet_fail_loudly(tmp_path, step, caplog):
    """M0.5: bi, recommend đã có trong STEPS nhưng chưa có code (M1, M6): báo lỗi rõ, không chạy im lặng."""
    assert step in rmp.STEPS
    assert rmp.main(["--synthetic", "--synthetic-n", "300", "--only", step, "--out", str(tmp_path)]) == 2
    assert "chưa làm" in caplog.text
    assert not any(tmp_path.iterdir())


@pytest.mark.parametrize("flag", ["--table", "--golden"])
def test_runs_from_silver_files(tmp_path, flag):
    """Đọc từ file như dữ liệu thật: Silver + features (skill__/concept__/soft__) + e5 khóa job; --golden là bí danh."""
    import numpy as np

    from mining.synthetic import make_synthetic_jobs

    b = make_synthetic_jobs(n_jobs=500, seed=5)
    sp, fp, ep = tmp_path / "silver.parquet", tmp_path / "features.parquet", tmp_path / "job_emb.npz"
    b.golden.to_parquet(sp, index=False)
    b.features.sample(frac=1.0, random_state=1).to_parquet(fp, index=False)
    ids = b.golden["job_id"].to_numpy()
    np.savez(ep, ids=ids, job=np.random.default_rng(0).normal(size=(len(ids), 8)).astype(np.float16))
    out = tmp_path / "out"
    rc = rmp.main([flag, str(sp), "--features", str(fp), "--encoding-dict", str(tmp_path / "none.json"),
                   "--e5", str(ep), "--job-skills", str(tmp_path / "none.parquet"),
                   "--out", str(out), "--only", "bi,fp,salary", "--no-shap"])
    assert rc == 0
    m = json.loads((out / ARTIFACT_FILES["metrics"]).read_text(encoding="utf-8"))
    assert m["inputs"]["table"]["sha256_16"] and m["inputs"]["e5"]["sha256_16"]
    assert m["data"]["table_path"].endswith("silver.parquet")
    n_tool = sum(c.startswith("skill__") and c != "skill__other_skill" for c in b.features.columns)
    assert m["data"]["n_cols"]["skill"] == n_tool and m["data"]["n_cols"]["concept"] > 0
    assert m["salary"]["subset"]["n_train_subset"] > 100
    assert m["bi"]["totals_ok"] is True
    assert (out / "sd1_1_1.json").exists() and (out / "sd1_demand.json").exists()
