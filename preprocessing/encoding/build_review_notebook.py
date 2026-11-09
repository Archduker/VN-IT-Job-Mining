"""Build and execute the P5 review notebook with a fresh local kernel."""

import os
import sys
from pathlib import Path


def main():
    import json
    from tempfile import TemporaryDirectory

    import nbformat as nb
    from jupyter_client.kernelspec import KernelSpecManager
    from nbclient import NotebookClient
    from nbconvert import HTMLExporter

    root = Path(__file__).resolve().parents[2]
    cells = []

    def md(s):
        cells.append(nb.v4.new_markdown_cell(s))

    def code(s):
        cells.append(nb.v4.new_code_cell(s))

    md("""# P5 Encoding — EDA trên snapshot ứng viên

Snapshot R2 P4 đã tải, chưa được Phát duyệt sử dụng chính thức. Notebook kiểm tra bytes từ manifest trước mọi thống kê. Không sửa input, không xuất production, không dùng model/LLM hoặc dịch JD. Kết quả chỉ mô tả snapshot này, không đại diện toàn thị trường Việt Nam.

**Job coverage** = jobs có ≥1 giá trị trong vocabulary / tổng jobs. **Pair coverage** = cặp job–skill giữ lại / toàn bộ cặp trên cùng biểu diễn. **Sparsity** = số ô 0 / tổng ô. Raw values không đồng nghĩa kỹ năng chuẩn.""")
    code("""from pathlib import Path
import sys, json, hashlib, platform
from collections import Counter
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import matplotlib.pyplot as plt
import seaborn as sns
ROOT = Path.cwd()
if not (ROOT/'preprocessing').exists(): ROOT=ROOT.parent
sys.path.insert(0,str(ROOT))
from preprocessing.encoding.skills_taxonomy_230 import TAXONOMY_230, SKILL_LOOKUP_MAP, ALIAS_CONFLICTS
from preprocessing.encoding.run import to_col_slug
SNAP=ROOT/'reports/preprocessing/05_encoding/snapshot_audit_2026-11-08'
OUT=ROOT/'reports/preprocessing/05_encoding/review_2026-11-08'
OUT.mkdir(exist_ok=True)
manifest=json.loads((SNAP/'manifest.json').read_text())
frames=[]; schema={}
for item in manifest:
    src=item['key'].split('/')[1]; p=SNAP/f'{src}.parquet'
    assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
    table=pq.read_table(p); d=table.to_pandas()
    assert len(d)==item['rows'] and set(d.source_platform)=={src}
    assert d.job_id_global.notna().all() and d.job_id_global.is_unique
    frames.append(d); schema[src]={f.name:(str(f.type),f.nullable) for f in table.schema}
assert len(frames)==8
df=pd.concat(frames,ignore_index=True)
assert df.job_id_global.notna().all() and df.job_id_global.is_unique
print('Environment:',platform.python_version(),'pandas',pd.__version__,'numpy',np.__version__)
print('Shape:',df.shape,'Snapshot generated-at:',{m['metadata']['generated-at'] for m in manifest})
display(pd.DataFrame([{k:v for k,v in m.items() if k!='schema'} for m in manifest]))
""")
    md(
        "## Schema, input contract và anomalies\nKhông ép kiểu. Null-only Arrow type có thể hợp nhất trên bản phân tích nhưng chưa phải quyết định schema giao nhận."
    )
    code("""diff=[]
for field in sorted(set().union(*(s.keys() for s in schema.values()))):
    types={src:str(s.get(field,('ABSENT',None))) for src,s in schema.items()}
    if len(set(types.values()))>1:
        physical={s.get(field,('ABSENT',None))[0] for s in schema.values()}
        nullonly=(('null' in physical and len(physical-{'null'})==1) or ('list<element: null>' in physical and physical <= {'list<element: null>','list<element: string>'}))
        diff.append(dict(field=field,**types,difference='null-only' if nullonly else 'type/nullable mismatch',impact='no observed encoding failure; review Arrow join' if nullonly else 'check semantics before conversion',proposal='nullable counterpart on analysis copy only' if nullonly else 'inspect per-source type; no coercion',phat_review='yes for official schema'))
schema_diff=pd.DataFrame(diff); schema_diff.to_csv(OUT/'schema_diff.csv',index=False)
display(schema_diff)
display(pd.DataFrame({'null_jobs':df.isna().sum(),'null_rate':df.isna().mean()}))
for field,kind in [('skills_std',str),('locations',dict)]:
    assert df[field].apply(lambda a:isinstance(a,(list,tuple,np.ndarray)) and all(isinstance(v,kind) for v in a)).all()
print('Empty arrays:',{f:int(df[f].apply(len).eq(0).sum()) for f in ['skills_std','locations']})
from preprocessing.encoding.run import encode_dataset
encoded,_,_=encode_dataset(df)
anomalies=[]
for i,r in df.iterrows():
    if r.exp_min_years>r.exp_max_years:
        anomalies.append(dict(job_id_global=r.job_id_global,field='experience_range',value=str((r.exp_min_years,r.exp_max_years)),reason='min > max',derived_effect=str(encoded.loc[i,['exp_min_years','exp_max_years','exp_min_years__missing','exp_max_years__missing']].to_dict())))
    if pd.to_datetime(r.deadline_date,errors='coerce')<pd.to_datetime(r.posted_date,errors='coerce'):
        anomalies.append(dict(job_id_global=r.job_id_global,field='date_range',value=str((r.posted_date,r.deadline_date)),reason='deadline before posting',derived_effect=str(encoded.loc[i,['days_to_deadline','days_to_deadline__missing']].to_dict())))
an=pd.DataFrame(anomalies)
an['evidence']='executed current encoder on checksum-verified P4 snapshot'
an['options']='retain + flag / set derived feature missing; source unchanged'
an['recommendation']='flag for review; Phat decides derived missing policy'
an.to_csv(OUT/'anomalies_review.csv',index=False); display(an)
""")
    md(
        "## Skill/job và tần suất\nMỗi giá trị được đếm tối đa một lần trong một job; bao gồm jobs không có skill."
    )
    code("""rows=[set(map(str,a)) for a in df.skills_std]
counts=Counter(s for row in rows for s in row)
ordered=sorted(counts,key=lambda s:(-counts[s],s)); freq=np.array([counts[s] for s in ordered]); n=len(df)
lengths=np.array([len(s) for s in rows])
print('Jobs with any skill:',int((lengths>0).sum()),'/',n)
fig,ax=plt.subplots(1,2,figsize=(15,5))
ax[0].hist(lengths,bins=np.arange(lengths.max()+2)-.5);ax[0].set(xlabel='Distinct values/job (including 0)',ylabel='Jobs',title=f'Skill count per job; N={n}')
sns.barplot(x=freq[:30],y=ordered[:30],ax=ax[1]);ax[1].set(xlabel=f'Jobs containing value; denominator {n}',title='Top 30 observed values')
plt.tight_layout();plt.show()
fig,ax=plt.subplots(1,2,figsize=(13,4));ax[0].loglog(np.arange(1,len(freq)+1),freq);ax[0].set(xlabel='Rank',ylabel='Jobs',title='Frequency-rank (raw representation)')
ax[1].bar(['>=5','>=10','>=20'],[(freq>=k).sum() for k in [5,10,20]]);ax[1].set(ylabel='Observed values',title='Frequency thresholds before further canonicalization');plt.show()
print('152-style count is representation-dependent; not a proof of impossibility after canonicalization:',int((freq>=20).sum()))
""")
    md(
        "## Coverage theo K\nCác vocabulary raw top-K chưa được duyệt. Không trộn các tỷ lệ này với tỷ lệ sau alias mapping."
    )
    code("""ks=sorted(set([1,10,20,50,100,152,200,230,300,500,len(ordered)]))
coverage=[]
for k in ks:
    v=set(ordered[:k]); coverage.append((k,sum(bool(s&v) for s in rows)/n,sum(counts[s] for s in v)/sum(counts.values())))
curve=pd.DataFrame(coverage,columns=['K','job_coverage','pair_coverage'])
curve.plot(x='K',y=['job_coverage','pair_coverage'],logx=True,figsize=(10,4));plt.axvline(230,color='red',ls='--',label='K=230');plt.ylabel('Ratio; denominators jobs / raw job-skill pairs');plt.legend();plt.show()
""")
    md(
        "## Tỷ lệ theo nguồn\nMẫu số là số jobs của từng nguồn; chênh lệch có thể phản ánh phân khúc nguồn và quy tắc trích xuất."
    )
    code("""top=ordered[:15]; sources=sorted(df.source_platform.unique())
rates=pd.DataFrame({src:{s:sum(s in rows[i] for i in df.index[df.source_platform.eq(src)])/int(df.source_platform.eq(src).sum()) for s in top} for src in sources})
sns.heatmap(rates,annot=True,fmt='.0%',cmap='Blues');plt.title('P(value | source); denominator = jobs/source');plt.tight_layout();plt.show()
""")
    md(
        "## Raw top230 và prototype hiện tại\nPrototype scenario dùng đúng lookup tất định của code P5 (alias mơ hồ bị loại khỏi lookup). Cả hai scenario chưa approved."
    )
    code("""prototype_rows=[]
for row in rows:
    prototype_rows.append({slug for s in row if (slug:=SKILL_LOOKUP_MAP.get(s.lower()) or SKILL_LOOKUP_MAP.get(to_col_slug(s)) or SKILL_LOOKUP_MAP.get(s))})
def metrics(label,data,vocab):
    c=Counter(s for row in data for s in row); kept=sum(c[s] for s in vocab)
    return dict(scenario=label,representation=label,job_coverage=sum(bool(row&vocab) for row in data)/n,pair_coverage=kept/sum(c.values()),sparsity=1-kept/(n*len(vocab)),zero_columns=sum(c[s]==0 for s in vocab),jobs_denominator=n,pairs_denominator=sum(c.values()))
# Prototype pair denominator also includes unmatched original values as distinct other tokens.
proto_data=[]
for raw,mapped in zip(rows,prototype_rows):
    unmatched={'OTHER:'+s for s in raw if not (SKILL_LOOKUP_MAP.get(s.lower()) or SKILL_LOOKUP_MAP.get(to_col_slug(s)) or SKILL_LOOKUP_MAP.get(s))}
    proto_data.append(mapped|unmatched)
comparison=pd.DataFrame([metrics('raw',rows,set(ordered[:230])),metrics('prototype_alias',proto_data,{s.slug for s in TAXONOMY_230})])
display(comparison);comparison.to_csv(OUT/'scenario_metrics.csv',index=False)
comparison.set_index('scenario')[['job_coverage','pair_coverage','sparsity']].plot.bar(rot=0);plt.ylabel('Ratio within declared scenario');plt.show()
print('Alias conflicts:',ALIAS_CONFLICTS)
""")
    md(
        "## Sáu nhóm task — mapping đề xuất\nNhóm prototype mở rộng Security/QA/Data không phải schema nhóm đã duyệt. Crosswalk dưới đây chỉ là proposed; giữ phần chưa phân nhóm."
    )
    code("""group_map={'programming_languages':'Programming Languages','frameworks_libraries':'Frameworks & Libraries','databases_streaming':'Databases & Caching','cloud_devops_security':'Cloud & DevOps','tools_architecture_qa':'Tools, Architecture & Protocols','methodologies_softskills_data':'Methodologies & Soft Skills'}
slug_group={s.slug:group_map[s.group] for s in TAXONOMY_230}
group_counts=Counter()
for row in rows:
    for s in row:
        slug=SKILL_LOOKUP_MAP.get(s.lower()) or SKILL_LOOKUP_MAP.get(to_col_slug(s))
        group_counts[slug_group.get(slug,'UNCLASSIFIED')]+=1
pd.Series(group_counts).sort_values().plot.barh(figsize=(10,4));plt.xlabel('Raw job-value occurrences; proposed group mapping');plt.tight_layout();plt.show()
print('Group crosswalk is proposed. Manual decisions are never overwritten by this notebook.')
""")
    md(
        "## Co-occurrence\nC = XᵀX trên các giá trị raw phổ biến; đây là số jobs có cả hai giá trị, không phải quan hệ nhân quả."
    )
    code("""names=ordered[:12];X=np.array([[int(s in row) for s in names] for row in rows],dtype=np.int64)
C=X.T@X
assert np.array_equal(C,C.T) and np.array_equal(np.diag(C),X.sum(axis=0))
sns.heatmap(pd.DataFrame(C,index=names,columns=names),cmap='mako');plt.title(f'Co-occurrence counts; denominator universe {n} jobs');plt.tight_layout();plt.show()
""")
    md("""## So sánh K — câu hỏi và phương pháp

**Câu hỏi:** tăng K quanh 230 giữ thêm bao nhiêu thông tin? **Cách tính:** frequency theo job, dedup sau mapping, tie-break tên tăng dần. Baseline giữ nguyên skills_std; canonical scenario chỉ chuẩn hóa hoa/thường theo tên canonical trong shared dictionary, không áp alias gộp công nghệ. Nhóm vẫn proposed.

**Kết quả:** bảng và đồ thị dưới đây được tính lại từ snapshot. **Giới hạn:** coverage đo sự giữ lại giá trị quan sát, không chứng minh chất lượng Mining hoặc K tối ưu. Không so pair coverage khác mẫu số như cùng một đại lượng.""")
    code("""from preprocessing.encoding.compare_vocabulary import generate
_,ktable,increments=generate(ROOT)
thresholds=pd.read_csv(OUT/'threshold_comparison.csv')
source_k=pd.read_csv(OUT/'k_source_coverage.csv')
display(ktable);display(thresholds);display(increments)
for scenario,g in ktable.groupby('scenario'):
    ax=g.plot(x='K',y=['job_coverage','pair_coverage'],marker='o',title=scenario)
    ax.axvline(230,color='red',ls='--');ax.set_ylabel('Ratio (see jobs/pairs denominator columns)');plt.show()
increments.assign(change=increments.from_K.astype(str)+' → '+increments.to_K.astype(str)).pivot(index='change',columns='scenario',values='job_coverage_pp').plot.bar(rot=0,title='Incremental job coverage');plt.ylabel('Percentage points');plt.show()
increments.assign(change=increments.from_K.astype(str)+' → '+increments.to_K.astype(str)).pivot(index='change',columns='scenario',values='pair_coverage_pp').plot.bar(rot=0,title='Incremental pair coverage within each representation');plt.ylabel('Percentage points');plt.show()
plt.loglog(np.arange(1,len(freq)+1),freq)
for k in [200,230,300]:plt.axvline(k,ls='--',label=f'K={k}')
plt.xlabel('Frequency rank');plt.ylabel('Jobs containing raw value');plt.legend();plt.show()
g=ktable[ktable.scenario.eq('baseline_skills_std')].set_index('K')
g[[*group_map.values(),'UNCLASSIFIED']].plot.bar(stacked=True,figsize=(12,4));plt.ylabel('Selected values by proposed group');plt.show()
s=source_k[source_k.scenario.eq('baseline_skills_std')].pivot(index='source',columns='K',values='job_coverage')
sns.heatmap(s,annot=True,fmt='.1%',cmap='Blues');plt.title('Job coverage/source; denominator jobs in each source');plt.show()
print('Raw K coverage is preliminary; 230 remains the approved task width, not an inferred optimal K.')
""")
    md("""## Kết luận và quyết định

Các đồ thị chỉ mô tả snapshot ứng viên đã kiểm checksum. Frequency hiện tại phụ thuộc cách P3/P4 gộp alias; chưa chứng minh tính khả thi/bất khả thi sau canonicalization khác. Chưa xác minh mọi tag là skill chuẩn.

Phát cần quyết định snapshot chính thức, chính sách anomalies/missing, alias collision, danh sách 230 và threshold/tie/version, sáu nhóm, feature mapping, schema C, TF-IDF và Golden. Bảng CSV có cột accept/reject/edit; chưa có đề xuất mới được đánh dấu approved. Không có output production được ghi.""")
    notebook = nb.v4.new_notebook(cells=cells)
    dest = root / "notebooks/eda_p5_encoding.ipynb"
    dest.parent.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="p5-kernel-") as td:
        spec = Path(td) / "p5review"
        spec.mkdir()
        (spec / "kernel.json").write_text(
            json.dumps(
                {
                    "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                    "display_name": "P5 isolated review",
                    "language": "python",
                    "env": {
                        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
                        "MPLCONFIGDIR": "/tmp/p5-matplotlib",
                    },
                }
            )
        )
        manager = KernelSpecManager(kernel_dirs=[td])
        from jupyter_client import KernelManager

        km = KernelManager(kernel_name="p5review", kernel_spec_manager=manager)
        NotebookClient(
            notebook,
            km=km,
            timeout=180,
            resources={"metadata": {"path": str(root)}},
            record_timing=True,
        ).execute()
    nb.write(notebook, dest)
    import nbconvert

    candidates = [
        Path(sys.prefix) / "share/jupyter/nbconvert/templates",
        Path(nbconvert.__file__).resolve().parent.parent / "share/jupyter/nbconvert/templates",
    ]
    templates = [str(p) for p in candidates if p.exists()]
    html, _ = HTMLExporter(
        extra_template_basedirs=templates, extra_template_paths=templates
    ).from_notebook_node(notebook)
    dest.with_suffix(".html").write_text(html, encoding="utf-8")
    print(dest)


if __name__ == "__main__":
    main()
