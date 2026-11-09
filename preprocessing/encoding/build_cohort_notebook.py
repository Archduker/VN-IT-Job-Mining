"""Execute bounded cohort EDA with a fresh kernel; preserve the historical notebook."""

import argparse
import json
import os
import sys
import sysconfig
from pathlib import Path
from tempfile import TemporaryDirectory

import nbformat as nb
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager
from nbclient import NotebookClient
from nbconvert import HTMLExporter

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "notebooks",
                        help="Write notebook/HTML to a new directory; existing files are protected")
    parser.add_argument("--kernel-cwd", type=Path, default=ROOT / "notebooks",
                        help="Fresh kernel working directory (default: notebooks/, not repo root)")
    args = parser.parse_args(argv)
    destination = args.output_dir.resolve() / "eda_p5_final_cohort.ipynb"
    if destination.exists() or destination.with_suffix(".html").exists():
        raise FileExistsError("Existing EDA is protected; choose a new --output-dir")
    kernel_cwd = args.kernel_cwd.resolve(strict=True)
    if not kernel_cwd.is_dir():
        raise NotADirectoryError(kernel_cwd)
    md, code = nb.v4.new_markdown_cell, nb.v4.new_code_cell
    cells = [md("""# P5 cohort EDA — 09/11/2026

Snapshot P4 5.177 → cohort theo ledger được Phát cho phép, không sửa upstream.
85 ID được đánh giá trong review có giới hạn; 410 P2 và jobs ngoài queue vẫn **retained_unreviewed**.
Không gọi toàn cohort là verified IT, không suy rộng thành thị trường Việt Nam, không phân tích K/ML.
EDA 5.177 cũ ở `eda_p5_encoding.ipynb/.html` giữ làm historical evidence.
"""), code("""import hashlib, json, platform, sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import sparse
from IPython.display import display
import matplotlib.pyplot as plt

# Work from repo root or notebooks/ without relying on an earlier cell/kernel.
start = Path.cwd().resolve()
root = next((p for p in (start, *start.parents)
             if (p/'pyproject.toml').is_file()
             and (p/'preprocessing/encoding/execute.py').is_file()), None)
if root is None:
    raise FileNotFoundError('Open this notebook inside VN-IT-Job-Mining')
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
out = root / 'data/preprocessing/05_encoding'
m = json.loads((out/'artifact_manifest.json').read_text())
run = root / 'reports/preprocessing/05_encoding' / m['run_id']
metrics = json.loads((run/'metrics.json').read_text())
parent = json.loads((root/'reports/preprocessing/05_encoding/p5_2026-11-09_frozen_v2/metrics.json').read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(root/'reports/preprocessing/05_encoding/snapshot_audit_2026-11-08/manifest.json') == m['input_manifest_sha256']
assert sha(root/m['vocabulary_path']) == m['vocabulary_sha256']
assert sha(root/m['cohort']['ledger_path']) == m['cohort']['ledger_sha256']
for artifact in m['current_artifacts']:
    assert sha(root/artifact['path']) == artifact['sha256']
assert pd.__version__ == m['environment']['pandas']
assert np.__version__ == m['environment']['numpy']
print('run_id:', m['run_id'], 'Python:', platform.python_version(), 'Pandas:', pd.__version__)
print('snapshot SHA:', m['input_manifest_sha256'])
print('ledger SHA:', m['cohort']['ledger_sha256'])
print('vocabulary SHA:', m['vocabulary_sha256'])
"""), md("## Cohort ledger và coverage review — từng ID được giải trình"), code("""from preprocessing.encoding.execution_io import load_snapshot
_, p4, _ = load_snapshot(root/'reports/preprocessing/05_encoding/snapshot_audit_2026-11-08/manifest.json')
ledger = pd.read_csv(root/m['cohort']['ledger_path'], keep_default_na=False)
assert ledger.job_id_global.tolist() == p4.job_id_global.tolist()
assert ledger.job_id_global.is_unique
audit = ledger.assign(source=p4.source_platform.to_numpy())
display(pd.crosstab(audit.source, audit.disposition))
display(audit.groupby(['disposition','review_status']).size().rename('jobs').to_frame())
assert len(ledger)==5177 and ledger.disposition.eq('include').sum()==metrics['rows']
print('Reviewed IDs:', ledger.review_status.ne('retained_unreviewed').sum())
print('P2 retained_unreviewed: 410; outside queue not_flagged_by_targeted_rules: 4682. Neither is verified IT.')
fig, ax=plt.subplots(figsize=(7,3))
ledger.disposition.value_counts().reindex(['include','exclude','quarantine']).plot.bar(ax=ax,color=['#2563eb','#d97706','#64748b'])
ax.set(title='Approved-policy ledger dispositions',ylabel='Jobs',xlabel=''); ax.tick_params(axis='x',rotation=0)
plt.tight_layout(); plt.show()
"""), md("## Frozen 230 features: frequency, skill/job, missing và all-zero"), code("""d = json.loads((out/'encoding_dictionary.json').read_text())
f = pd.read_parquet(out/'features.parquet')
columns=d['skill_columns']
X=f[columns]
included_ids=ledger.loc[ledger.disposition.eq('include'),'job_id_global'].tolist()
denied=set(ledger.loc[ledger.disposition.ne('include'),'job_id_global'])
assert f.job_id_global.tolist()==included_ids and not denied.intersection(f.job_id_global)
assert X.shape==(len(included_ids),230) and X.isin([0,1]).all().all()
skill_counts=X.sum(axis=1)
display(skill_counts.describe().to_frame('canonical skills/job'))
display(pd.DataFrame({'jobs':[int(f.skills__missing.sum()),int(f.skills__empty.sum()),int(skill_counts.eq(0).sum()),int(((skill_counts==0)&(f.other_skills_count>0)).sum())]},index=['null skills','empty skills','all-zero selected skills','unmatched-only']))
items=d['skills']['taxonomy']
freq=pd.DataFrame({'canonical':[i['canonical'] for i in items],'column':columns,'jobs':X.sum().to_numpy(),'skill_type':[i['skill_type'] for i in items],'group':[i['group'] for i in items]})
display(freq.sort_values(['jobs','canonical'],ascending=[False,True]).head(25))
print('Zero-column skills:',freq.loc[freq.jobs.eq(0),'canonical'].tolist())
fig, ax=plt.subplots(figsize=(8,3))
skill_counts.value_counts().sort_index().plot.bar(ax=ax,color='#2563eb')
ax.set(title='Selected canonical skills per included job',xlabel='Skills/job',ylabel='Jobs')
plt.tight_layout(); plt.show()
"""), md("## Coverage và metadata — mẫu số và representation rõ"), code("""covered=int(X.any(axis=1).sum())
source_pairs=metrics['source_value_pairs']
unmatched=metrics['unmatched_source_pairs']
display(pd.DataFrame([{'metric':'job coverage','numerator':covered,'denominator':len(f),'ratio':covered/len(f)}, {'metric':'source-value-pair coverage','numerator':source_pairs-unmatched,'denominator':source_pairs,'ratio':(source_pairs-unmatched)/source_pairs}]))
print('Canonical pairs:',int(X.to_numpy().sum()),'; unmatched source pairs:',unmatched)
print('Representation: frozen whole-value casefold canonical+explicit aliases; each canonical counted once/job.')
display(freq.groupby('skill_type').size().to_frame('vocabulary columns'))
display(freq.groupby('group',dropna=False).size().to_frame('vocabulary columns'))
print('Null group is metadata gap, NOT a seventh task group or soft-skill label; group is not job_family.')
print('Below20:',int(freq.jobs.lt(20).sum()),'— allowed for this run, no padding or replacement.')
"""), md("## Co-occurrence, TF-IDF và sparse summary"), code("""C=pd.read_parquet(out/'skill_cooccurrence.parquet')
assert C.index.tolist()==columns and C.columns.tolist()==columns
assert C.to_numpy().dtype==np.int64 and np.array_equal(C.to_numpy(),C.to_numpy().T)
np.testing.assert_array_equal(np.diag(C),X.sum().to_numpy())
pairs=[(int(C.iloc[i,j]),columns[i],columns[j]) for i in range(230) for j in range(i+1,230)]
display(pd.DataFrame(sorted(pairs,key=lambda x:(-x[0],x[1],x[2]))[:10],columns=['jobs','skill_a','skill_b']))
T=sparse.load_npz(out/'tfidf_matrix.npz')
rows=pd.read_parquet(out/'tfidf_rows.parquet')
assert rows.job_id_global.tolist()==f.job_id_global.tolist() and T.shape[0]==len(f)
assert T.format=='csr' and T.dtype==np.float32 and np.isfinite(T.data).all() and (T.data>=0).all()
norms=np.sqrt(np.asarray(T.multiply(T).sum(axis=1)).ravel())
assert np.all(np.isclose(norms,0,atol=2e-6)|np.isclose(norms,1,atol=2e-6))
display(pd.DataFrame([{'rows':T.shape[0],'terms':T.shape[1],'nnz':T.nnz,'density':T.nnz/(T.shape[0]*T.shape[1]),'zero_rows':int((norms==0).sum()),'CSR_bytes':T.data.nbytes+T.indices.nbytes+T.indptr.nbytes}]))
print('TF-IDF refit on include cohort before fit; full-corpus exploratory view. Supervised downstream must refit train-only.')
"""), md("## Trước/sau và remaining anomalies"), code("""comparison=pd.DataFrame({
 'historical5177':{'jobs':parent['rows'],'covered_jobs':parent['job_coverage']['numerator'],'job_coverage':parent['job_coverage']['numerator']/parent['rows'],'canonical_pairs':parent['canonical_pairs'],'sparsity':parent['sparsity'],'zero_columns':parent['zero_columns'],'below20':parent['below20']},
 'current_include':{'jobs':metrics['rows'],'covered_jobs':covered,'job_coverage':covered/len(f),'canonical_pairs':metrics['canonical_pairs'],'sparsity':metrics['sparsity'],'zero_columns':metrics['zero_columns'],'below20':metrics['below20']}
})
display(comparison)
q=pd.read_parquet(out/'data_quality.parquet')
display(q.reason.value_counts().to_frame('quality events, not unique jobs'))
print('Family values remain P4 source values; flagged questions live in sidecars, not automatic relabeling.')
print('Audit columns excluded from recommended salary predictors:',d['audit_columns'])
assert not set(d['recommended_predictors']['salary_regression']).intersection(d['audit_columns'])
print('P5 acceptance:',m['acceptance_status'],'; Python3.12 remains UNVERIFIED unless separately tested.')
"""), md("""## Giới hạn và handoff

85 reviewed IDs are policy-based Agent assessments or owner-approved decisions, not a human gold-label dataset.
410 P2 and 4.682 outside-queue jobs are intentionally retained_unreviewed; residual scope contamination is possible.
11 quarantine rows stay in immutable P4/ledger and are not confirmed non-IT.
No upstream filter/job_family/dictionary was repaired. Frozen skill counts from 5.177 remain reference counts;
current observed counts are separate. Scope is this collected snapshot, not all Vietnam IT labor demand.
Use manifest+ledger hashes and dictionary.skill_columns, align TF-IDF by row IDs; do not include audit/target-derived
salary columns in supervised predictors. Python3.12/whole-repo test limitations are reported separately.
""")]
    notebook = nb.v4.new_notebook(cells=cells)
    with TemporaryDirectory(prefix="p5-cohort-kernel-") as tmp:
        spec = Path(tmp) / "p5cohort"
        spec.mkdir()
        # Existing runtime packages precede optional notebook tools (which carry
        # another pandas build); the fresh kernel must match the artifact runtime.
        # Do not inject ROOT: the notebook itself must discover/import the repo.
        optional_paths = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
        pythonpath = os.pathsep.join([sysconfig.get_path("purelib"), *optional_paths])
        (spec / "kernel.json").write_text(json.dumps(dict(argv=[sys.executable,"-m","ipykernel_launcher","-f","{connection_file}"], display_name="P5 cohort fresh kernel", language="python",
            env=dict(PYTHONPATH=pythonpath, PYTHONDONTWRITEBYTECODE="1", MPLCONFIGDIR="/tmp/p5-cohort-matplotlib", IPYTHONDIR="/tmp/p5-cohort-ipython", JUPYTER_RUNTIME_DIR=tmp))))
        manager = KernelSpecManager(kernel_dirs=[tmp])
        km = KernelManager(kernel_name="p5cohort", kernel_spec_manager=manager)
        print("Starting fresh cohort kernel", flush=True)
        NotebookClient(notebook, km=km, timeout=120, startup_timeout=30, resources={"metadata":{"path":str(kernel_cwd)}}, record_timing=True).execute()
    import nbconvert
    paths = [Path(sys.prefix)/"share/jupyter/nbconvert/templates",Path(nbconvert.__file__).resolve().parent.parent/"share/jupyter/nbconvert/templates"]
    templates = [str(path) for path in paths if path.exists()]
    html, _ = HTMLExporter(extra_template_basedirs=templates, extra_template_paths=templates).from_notebook_node(notebook)
    destination.parent.mkdir(parents=True, exist_ok=True)
    nb.write(notebook, destination)
    destination.with_suffix(".html").write_text(html, encoding="utf-8")
    errors=[output for cell in notebook.cells if cell.cell_type=="code" for output in cell.outputs if output.output_type=="error"]
    assert not errors and all(cell.execution_count for cell in notebook.cells if cell.cell_type=="code")
    print(json.dumps(dict(notebook=str(destination), html=str(destination.with_suffix('.html')), executed_code_cells=sum(c.cell_type=='code' for c in notebook.cells), fresh_kernel=True, kernel_cwd=str(kernel_cwd), errors=0)))


if __name__ == "__main__":
    main()
