import hashlib

import pandas as pd

from processing.extraction import run as R
from processing.extraction.skills import SkillMatcher, load_taxonomy
from processing.transformation import run as T

DF = pd.DataFrame([
    {"job_id_global": "a_1", "source_platform": "glints", "description_clean": "- Phát triển API bằng Python\n- Review code",
     "requirements_clean": "- Biết Docker và Kubernetes", "skills_list": ["Python"]},
    {"job_id_global": "a_2", "source_platform": "glints", "description_clean": None, "requirements_clean": None},
    {"job_id_global": "b_1", "source_platform": "topcv", "description_clean": "Làm việc nhóm", "requirements_clean": "Node.js"},
])
M = SkillMatcher(load_taxonomy())
KW = dict(sources=["glints", "topcv"], df=DF, matcher=M, headings={}, cues=[])


def test_no_job_dropped_and_counted(tmp_path):
    out = R.run(dry_run=True, out_root=tmp_path, report_root=tmp_path, **KW)
    r7, r8 = out["07_sections"], out["08_skills"]
    assert r7["glints"].data["output"]["rows"] == 2 and r7["_all"].data["checks"]["rows_conserved"] is True
    assert r7["glints"].data["extra"]["n_jobs_no_bullet"] == 1
    assert r8["_all"].data["extra"]["sparsity"]["before"]["n_jobs"] == 3
    assert not list(tmp_path.iterdir())  # dry-run không ghi


def test_apply_is_reproducible(tmp_path):
    def h(d):
        R.run(dry_run=False, out_root=d, report_root=d / "rep", **KW)
        return hashlib.sha256((d / "08_skills" / "job_skills.parquet").read_bytes()).hexdigest()
    assert h(tmp_path / "1") == h(tmp_path / "2")


def test_tokens_have_placeholders(tmp_path):
    reps = T.run(dry_run=False, out_root=tmp_path, report_root=tmp_path / "r", **KW)
    t = pd.read_parquet(tmp_path / "09_tokens" / "all.parquet").set_index("job_id_global")
    assert [x for x in t.loc["b_1", "tokens"] if x.startswith("sk_")] and "js" not in list(t.loc["b_1", "tokens"])
    assert "sk_docker" in list(t.loc["a_1", "tokens_nostop"])
    assert reps["_all"].data["checks"]["rows_conserved"] is True
