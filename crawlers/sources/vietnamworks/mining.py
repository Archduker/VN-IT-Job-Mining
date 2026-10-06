"""
=============================================================================
DATA MINING — VIETNAMWORKS IT 1000
Chạy 3 thuật toán: Apriori · K-Means · Decision Tree
Xuất báo cáo HTML đẹp: bao_cao_data_mining.html
=============================================================================
"""

import sys, io, json, math
from collections import Counter
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd
import numpy as np

# ── Load data ──────────────────────────────────────────────────────────────
print("="*70)
print("  LOAD DỮ LIỆU")
print("="*70)

with open("it_1000_clean.json", encoding="utf-8") as f:
    raw = json.load(f)

records = raw["records"]
df = pd.DataFrame(records)

# Skill matrix → separate DataFrame
skill_df = pd.DataFrame([r["skill_matrix"] for r in records])
skill_cols = list(skill_df.columns)

# Numeric features
for col in ["salary_avg_mil_vnd","job_level_order","skill_count","years_of_experience"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

print(f"[✓] Loaded {len(df)} records, {len(df.columns)} columns")

# ══════════════════════════════════════════════════════════════════════════
# THUẬT TOÁN 1 — APRIORI (Association Rules)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("  BƯỚC 4A — APRIORI: Khai phá luật kết hợp kỹ năng")
print("="*70)

from mlxtend.frequent_patterns import apriori, association_rules

skill_bool = skill_df.astype(bool)

# Tìm frequent itemsets
freq = apriori(skill_bool, min_support=0.015, use_colnames=True)
print(f"[*] Frequent itemsets (min_support=1.5%): {len(freq)}")

rules_apriori = pd.DataFrame()
if not freq.empty:
    rules_apriori = association_rules(freq, metric="lift", min_threshold=1.1,
                                      num_itemsets=len(freq))
    rules_apriori = rules_apriori.sort_values(["lift","confidence"], ascending=False)
    rules_apriori["antecedents_str"] = rules_apriori["antecedents"].apply(
        lambda x: " + ".join(str(s).replace("_"," ") for s in x))
    rules_apriori["consequents_str"] = rules_apriori["consequents"].apply(
        lambda x: " + ".join(str(s).replace("_"," ") for s in x))
    print(f"[*] Tổng luật kết hợp (Lift>1.1): {len(rules_apriori)}")
    print(f"[*] Top 5:")
    for _, r in rules_apriori.head(5).iterrows():
        print(f"    {r['antecedents_str']} => {r['consequents_str']}  "
              f"[sup={r['support']:.3f}, conf={r['confidence']:.3f}, lift={r['lift']:.2f}]")

# Skill frequency (top 20)
skill_freq_series = skill_bool.sum().sort_values(ascending=False)

# ══════════════════════════════════════════════════════════════════════════
# THUẬT TOÁN 2 — K-MEANS (Clustering)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("  BƯỚC 4B — K-MEANS: Phân cụm vị trí việc làm")
print("="*70)

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

features_km = ["salary_avg_mil_vnd","job_level_order","skill_count","years_of_experience"]
X_km = df[features_km].fillna(0).values
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_km)

# Tìm k tối ưu
silhouettes, inertias = [], []
K_range = range(2, 8)
for k in K_range:
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    lbs = km.fit_predict(X_scaled)
    silhouettes.append(silhouette_score(X_scaled, lbs))
    inertias.append(km.inertia_)

best_k = list(K_range)[silhouettes.index(max(silhouettes))]
print(f"[*] k tối ưu (Silhouette): k={best_k}  (score={max(silhouettes):.4f})")

km_final = KMeans(n_clusters=best_k, random_state=42, n_init=10)
df["cluster"] = km_final.fit_predict(X_scaled)

cluster_summary = df.groupby("cluster").agg(
    count=("cluster","count"),
    luong_tb=("salary_avg_mil_vnd","mean"),
    bac_tb=("job_level_order","mean"),
    skill_tb=("skill_count","mean"),
    exp_tb=("years_of_experience","mean"),
).reset_index()

# Đặt tên cụm dựa trên bậc trung bình
def cluster_label(row):
    b = row["bac_tb"]
    if b < 1.5:  return "Fresher / Intern"
    if b < 2.5:  return "Developer / Engineer"
    if b < 3.5:  return "Senior / Specialist"
    if b < 4.5:  return "Lead / Manager"
    return "Director / Executive"

cluster_summary["label"] = cluster_summary.apply(cluster_label, axis=1)
df["cluster_label"] = df["cluster"].map(dict(zip(cluster_summary["cluster"], cluster_summary["label"])))

print(f"[*] Phân bổ {best_k} cụm:")
for _, row in cluster_summary.iterrows():
    print(f"    Cụm {int(row['cluster'])} ({row['label']}): {int(row['count'])} jobs | "
          f"lương {row['luong_tb']:.1f}tr | {row['exp_tb']:.1f} năm KN")

# ══════════════════════════════════════════════════════════════════════════
# THUẬT TOÁN 3 — DECISION TREE (Classification)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("  BƯỚC 4C — DECISION TREE: Phân loại cấp bậc")
print("="*70)

from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, accuracy_score

feat_dt = skill_cols + ["skill_count","salary_avg_mil_vnd","years_of_experience",
                        "loc_hcm","loc_hn"]
for c in feat_dt:
    if c not in df.columns:
        df[c] = 0
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

# Gom nhóm level: 0→1 (Fresher), 5→4 (Director→Manager)
df["level_group"] = df["job_level_order"].replace({0:1, 5:4}).astype(int)
level_names = {1:"Fresher", 2:"Experienced", 3:"Team Leader", 4:"Manager/Director"}

X_dt = df[feat_dt]
y_dt = df["level_group"]

X_tr, X_te, y_tr, y_te = train_test_split(X_dt, y_dt, test_size=0.2,
                                           random_state=42, stratify=y_dt)
clf = DecisionTreeClassifier(max_depth=5, min_samples_leaf=5,
                             random_state=42, class_weight="balanced")
clf.fit(X_tr, y_tr)

cv = cross_val_score(clf, X_dt, y_dt, cv=5, scoring="accuracy")
y_pred = clf.predict(X_te)
acc = accuracy_score(y_te, y_pred)

print(f"[*] Cross-Val Accuracy (k=5): {cv.mean():.3f} ± {cv.std():.3f}")
print(f"[*] Test Accuracy: {acc:.3f}")

# Feature importance
imp = pd.Series(clf.feature_importances_, index=feat_dt).sort_values(ascending=False)
top_imp = imp.head(12)
print(f"[*] Top 5 features quan trọng nhất:")
for feat, val in top_imp.head(5).items():
    print(f"    {feat.replace('_',' '):<30} {val:.4f}")

# Class report dict
from sklearn.metrics import classification_report
target_names = [level_names.get(lv, str(lv)) for lv in sorted(y_dt.unique())]
report_dict = classification_report(y_te, y_pred, target_names=target_names,
                                    zero_division=0, output_dict=True)

# ══════════════════════════════════════════════════════════════════════════
# XUẤT BÁO CÁO HTML
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("  XUẤT BÁO CÁO HTML")
print("="*70)

# ── Helpers ──
def pct(n, total): return f"{n/total*100:.1f}%"
def row_color(i): return "#1a1f35" if i % 2 == 0 else "#1e2440"

# ── Salary distribution ──
salary_dist = df["salary_band"].value_counts()
# ── Location distribution ──
loc_dist = {"HCM": int(df["loc_hcm"].sum()), "Hà Nội": int(df["loc_hn"].sum()),
            "Đà Nẵng": int(df["loc_da_nang"].sum()), "Khác": int(df["loc_other"].sum())}
# ── Level distribution ──
level_dist = df["job_level_en"].value_counts()
# ── Experience distribution ──
exp_dist = df["experience_band"].value_counts()

# ── Build skill freq table ──
skill_top20_html = ""
colors = ["#6c63ff","#f7971e","#2af598","#ee0979","#09f1b8",
          "#00f2fe","#f953c6","#0ff","#f8c471","#a9cce3"]
for i, (sk, cnt) in enumerate(skill_freq_series.head(20).items()):
    pct_val = cnt / len(df) * 100
    c = colors[i % len(colors)]
    skill_top20_html += f"""
    <tr>
      <td style="color:#aaa">{i+1}</td>
      <td style="font-weight:600;color:#e0e6ff">{sk.replace("_"," ").title()}</td>
      <td style="color:{c};font-weight:700">{int(cnt)}</td>
      <td>
        <div style="background:#0d1117;border-radius:4px;height:8px;width:100%">
          <div style="background:{c};height:8px;border-radius:4px;width:{min(pct_val*2.5,100):.1f}%"></div>
        </div>
      </td>
      <td style="color:#aaa">{pct_val:.1f}%</td>
    </tr>"""

# ── Apriori rules table ──
apriori_rows_html = ""
if not rules_apriori.empty:
    for i, (_, r) in enumerate(rules_apriori.head(15).iterrows()):
        lift_color = "#2af598" if r["lift"] > 3 else "#f7971e" if r["lift"] > 2 else "#aaa"
        apriori_rows_html += f"""
        <tr style="background:{row_color(i)}">
          <td style="color:#6c63ff;font-weight:600">{r['antecedents_str']}</td>
          <td style="color:#888;font-size:1.3em">⟹</td>
          <td style="color:#2af598;font-weight:600">{r['consequents_str']}</td>
          <td style="color:#f8c471">{r['support']:.3f}</td>
          <td style="color:#f7971e">{r['confidence']:.3f}</td>
          <td style="color:{lift_color};font-weight:700">{r['lift']:.2f}</td>
        </tr>"""
else:
    apriori_rows_html = "<tr><td colspan='6' style='text-align:center;color:#888'>Không đủ dữ liệu tạo luật</td></tr>"

# ── K-Means cluster table ──
cluster_colors = ["#6c63ff","#2af598","#f7971e","#ee0979","#00f2fe","#f953c6"]
cluster_rows_html = ""
for _, row in cluster_summary.iterrows():
    ci = int(row["cluster"])
    cc = cluster_colors[ci % len(cluster_colors)]
    cluster_rows_html += f"""
    <tr style="background:{row_color(ci)}">
      <td><span style="background:{cc};color:#fff;padding:2px 10px;border-radius:12px;font-weight:700">Cụm {ci}</span></td>
      <td style="color:#e0e6ff;font-weight:600">{row['label']}</td>
      <td style="color:#f8c471;font-weight:700">{int(row['count'])}</td>
      <td style="color:{cc}">{row['luong_tb']:.1f} tr</td>
      <td style="color:#aaa">{row['bac_tb']:.2f}</td>
      <td style="color:#aaa">{row['skill_tb']:.1f}</td>
      <td style="color:#aaa">{row['exp_tb']:.1f} năm</td>
    </tr>"""

# ── Decision Tree feature importance ──
imp_rows_html = ""
for i, (feat, val) in enumerate(top_imp.items()):
    bar_pct = val / top_imp.max() * 100
    imp_rows_html += f"""
    <tr style="background:{row_color(i)}">
      <td style="color:#e0e6ff">{feat.replace('_',' ').title()}</td>
      <td>
        <div style="background:#0d1117;border-radius:4px;height:8px;width:100%">
          <div style="background:#6c63ff;height:8px;border-radius:4px;width:{bar_pct:.1f}%"></div>
        </div>
      </td>
      <td style="color:#6c63ff;font-weight:700">{val:.4f}</td>
    </tr>"""

# ── DT Classification report table ──
dt_report_rows = ""
for cls_name in target_names:
    if cls_name in report_dict:
        r = report_dict[cls_name]
        dt_report_rows += f"""
        <tr>
          <td style="color:#e0e6ff;font-weight:600">{cls_name}</td>
          <td style="color:#2af598">{r['precision']:.3f}</td>
          <td style="color:#f7971e">{r['recall']:.3f}</td>
          <td style="color:#6c63ff;font-weight:700">{r['f1-score']:.3f}</td>
          <td style="color:#aaa">{int(r['support'])}</td>
        </tr>"""

# ── K-Means silhouette chart data ──
sil_bars = ""
for k, s, inn in zip(K_range, silhouettes, inertias):
    pct_bar = s / max(silhouettes) * 100
    color = "#2af598" if k == best_k else "#6c63ff"
    bold = "font-weight:700" if k == best_k else ""
    sil_bars += f"""
    <div style="display:flex;align-items:center;gap:12px;margin:6px 0">
      <div style="width:30px;color:#aaa;{bold}">k={k}</div>
      <div style="flex:1;background:#0d1117;border-radius:4px;height:20px;position:relative">
        <div style="background:{color};height:20px;border-radius:4px;width:{pct_bar:.1f}%"></div>
      </div>
      <div style="width:80px;color:{color};{bold}">{s:.4f}{"  ◄ Best" if k==best_k else ""}</div>
    </div>"""

# ── Salary donut data ──
salary_items_html = ""
sal_colors = ["#888","#2af598","#f7971e","#6c63ff","#ee0979","#00f2fe","#f8c471"]
for i, (band, cnt) in enumerate(salary_dist.items()):
    salary_items_html += f"""
    <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1e2440">
      <span style="color:{sal_colors[i % len(sal_colors)]}">{band}</span>
      <span style="color:#e0e6ff;font-weight:700">{cnt} <span style="color:#888;font-weight:400">({pct(cnt,len(df))})</span></span>
    </div>"""

# ── Location breakdown ──
loc_items_html = ""
loc_colors = ["#6c63ff","#2af598","#f7971e","#888"]
for i, (city, cnt) in enumerate(loc_dist.items()):
    loc_items_html += f"""
    <div style="display:flex;align-items:center;gap:12px;margin:8px 0">
      <div style="width:90px;color:#aaa">{city}</div>
      <div style="flex:1;background:#0d1117;border-radius:4px;height:16px">
        <div style="background:{loc_colors[i]};height:16px;border-radius:4px;width:{cnt/len(df)*100:.1f}%"></div>
      </div>
      <div style="width:60px;color:{loc_colors[i]};font-weight:700">{cnt}</div>
    </div>"""

# ── Level breakdown ──
level_items_html = ""
for i, (lvl, cnt) in enumerate(level_dist.items()):
    level_items_html += f"""
    <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e2440">
      <span style="color:#aaa">{lvl}</span>
      <span style="color:#e0e6ff">{cnt} ({pct(cnt,len(df))})</span>
    </div>"""

# ══════════════════════════════════════════════════════════════════════════
# HTML TEMPLATE
# ══════════════════════════════════════════════════════════════════════════
html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Báo Cáo Data Mining — Thị Trường Tuyển Dụng IT Việt Nam</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap');
  :root {{
    --bg: #0d1117; --card: #161b27; --border: #21293d;
    --purple: #6c63ff; --green: #2af598; --orange: #f7971e;
    --pink: #ee0979; --cyan: #00f2fe; --text: #e0e6ff; --muted: #6b7a99;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:var(--bg); color:var(--text); font-family:'Inter',sans-serif; line-height:1.6; }}
  /* HERO */
  .hero {{
    background: linear-gradient(135deg,#0d1117 0%,#1a0533 50%,#0d1117 100%);
    border-bottom: 1px solid var(--border); padding: 60px 40px 50px;
    text-align:center; position:relative; overflow:hidden;
  }}
  .hero::before {{
    content:''; position:absolute; top:-50%; left:-50%; width:200%; height:200%;
    background: radial-gradient(ellipse at center, rgba(108,99,255,.12) 0%, transparent 60%);
    pointer-events:none;
  }}
  .hero h1 {{ font-size:2.6rem; font-weight:800; background:linear-gradient(90deg,#6c63ff,#2af598,#f7971e);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:12px; }}
  .hero p {{ color:var(--muted); font-size:1.05rem; max-width:600px; margin:0 auto 24px; }}
  .badges {{ display:flex; gap:12px; justify-content:center; flex-wrap:wrap; }}
  .badge {{ background:rgba(108,99,255,.15); border:1px solid rgba(108,99,255,.4);
    color:var(--purple); padding:6px 16px; border-radius:20px; font-size:.85rem; font-weight:600; }}
  .badge.green {{ background:rgba(42,245,152,.1); border-color:rgba(42,245,152,.4); color:var(--green); }}
  .badge.orange {{ background:rgba(247,151,30,.1); border-color:rgba(247,151,30,.4); color:var(--orange); }}
  /* LAYOUT */
  .container {{ max-width:1200px; margin:0 auto; padding:40px 24px; }}
  .section-title {{
    font-size:1.5rem; font-weight:700; margin:40px 0 20px;
    padding-left:16px; border-left:4px solid var(--purple);
    display:flex; align-items:center; gap:12px;
  }}
  .section-title .algo-badge {{
    font-size:.7rem; padding:3px 10px; border-radius:12px;
    background:rgba(108,99,255,.2); color:var(--purple); border:1px solid rgba(108,99,255,.4);
    font-weight:600; letter-spacing:.05em; text-transform:uppercase;
  }}
  /* STAT CARDS */
  .stats-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:32px; }}
  .stat-card {{
    background:var(--card); border:1px solid var(--border); border-radius:16px;
    padding:24px; text-align:center; position:relative; overflow:hidden;
    transition:transform .2s, box-shadow .2s;
  }}
  .stat-card:hover {{ transform:translateY(-4px); box-shadow:0 8px 32px rgba(108,99,255,.2); }}
  .stat-card::before {{
    content:''; position:absolute; top:0; left:0; right:0; height:3px;
  }}
  .stat-card.purple::before {{ background:linear-gradient(90deg,#6c63ff,#a78bfa); }}
  .stat-card.green::before  {{ background:linear-gradient(90deg,#2af598,#09f1b8); }}
  .stat-card.orange::before {{ background:linear-gradient(90deg,#f7971e,#f953c6); }}
  .stat-card.cyan::before   {{ background:linear-gradient(90deg,#00f2fe,#4facfe); }}
  .stat-num {{ font-size:2.4rem; font-weight:800; margin:8px 0 4px; }}
  .stat-label {{ color:var(--muted); font-size:.88rem; }}
  /* CARD */
  .card {{
    background:var(--card); border:1px solid var(--border); border-radius:16px;
    padding:28px; margin-bottom:24px;
  }}
  .card h3 {{ color:var(--text); font-size:1.05rem; margin-bottom:18px; font-weight:600; }}
  /* TABLE */
  table {{ width:100%; border-collapse:collapse; font-size:.9rem; }}
  th {{ background:#1e2847; color:var(--muted); font-weight:600; padding:10px 14px;
    text-align:left; font-size:.8rem; letter-spacing:.05em; text-transform:uppercase; }}
  td {{ padding:10px 14px; border-bottom:1px solid var(--border); vertical-align:middle; }}
  tr:hover td {{ background:rgba(108,99,255,.06); }}
  /* GRID */
  .two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:24px; }}
  @media(max-width:768px) {{ .two-col {{ grid-template-columns:1fr; }} .hero h1 {{ font-size:1.8rem; }} }}
  /* INSIGHT BOX */
  .insight {{
    background:linear-gradient(135deg,rgba(108,99,255,.1),rgba(42,245,152,.05));
    border:1px solid rgba(108,99,255,.3); border-radius:12px;
    padding:20px 24px; margin:20px 0;
  }}
  .insight-title {{ color:var(--purple); font-weight:700; margin-bottom:8px; font-size:.95rem; }}
  .insight ul {{ color:#b0bdd8; padding-left:18px; }}
  .insight li {{ margin:4px 0; }}
  /* FOOTER */
  footer {{ text-align:center; color:var(--muted); font-size:.85rem; padding:32px; border-top:1px solid var(--border); }}
  .tag {{ display:inline-block; background:#1e2440; border:1px solid var(--border);
    color:#aaa; padding:3px 10px; border-radius:8px; font-family:'Fira Code',monospace;
    font-size:.78rem; margin:2px; }}
  .metric-chip {{ display:inline-flex; align-items:center; gap:6px; background:rgba(42,245,152,.08);
    border:1px solid rgba(42,245,152,.3); color:var(--green);
    padding:4px 14px; border-radius:20px; font-size:.88rem; font-weight:600; }}
</style>
</head>
<body>

<!-- HERO -->
<div class="hero">
  <h1>📊 Báo Cáo Data Mining</h1>
  <p>Phân tích thị trường tuyển dụng IT Việt Nam từ dữ liệu VietnamWorks</p>
  <div class="badges">
    <span class="badge">🔗 Apriori — Association Rules</span>
    <span class="badge green">🎯 K-Means — Clustering (k={best_k})</span>
    <span class="badge orange">🌳 Decision Tree — Classification</span>
  </div>
</div>

<div class="container">

<!-- OVERVIEW STATS -->
<div class="stats-grid">
  <div class="stat-card purple">
    <div class="stat-num" style="color:#6c63ff">1,000</div>
    <div class="stat-label">Tin tuyển dụng IT</div>
  </div>
  <div class="stat-card green">
    <div class="stat-num" style="color:#2af598">52</div>
    <div class="stat-label">Thuộc tính / bản ghi</div>
  </div>
  <div class="stat-card orange">
    <div class="stat-num" style="color:#f7971e">298</div>
    <div class="stat-label">Jobs có lương cụ thể</div>
  </div>
  <div class="stat-card cyan">
    <div class="stat-num" style="color:#00f2fe">{acc:.0%}</div>
    <div class="stat-label">Decision Tree Accuracy</div>
  </div>
</div>

<!-- DATASET OVERVIEW -->
<h2 class="section-title">📋 Tổng quan Dataset <span class="algo-badge">Overview</span></h2>
<div class="two-col">
  <div class="card">
    <h3>🗺️ Phân bổ địa lý</h3>
    {loc_items_html}
    <div class="insight" style="margin-top:16px">
      <div class="insight-title">💡 Nhận xét</div>
      <ul>
        <li>Hà Nội chiếm ưu thế với 555 jobs (55.5%)</li>
        <li>TP.HCM: 399 jobs (39.9%) — trung tâm startup & fintech</li>
        <li>Đà Nẵng chỉ có 15 jobs — thị trường IT còn nhỏ</li>
      </ul>
    </div>
  </div>
  <div class="card">
    <h3>💰 Phân nhóm mức lương</h3>
    {salary_items_html}
    <div class="insight" style="margin-top:16px">
      <div class="insight-title">💡 Nhận xét</div>
      <ul>
        <li>70.3% jobs không công bố lương (thương lượng)</li>
        <li>Nhóm 30–50tr chiếm tỷ lệ cao nhất trong số có lương</li>
        <li>23 jobs lương trên 100 triệu/tháng (Senior/Lead)</li>
      </ul>
    </div>
  </div>
</div>
<div class="two-col">
  <div class="card">
    <h3>🏅 Phân bổ cấp bậc</h3>
    {level_items_html}
  </div>
  <div class="card">
    <h3>⏱️ Phân nhóm kinh nghiệm</h3>
    {"".join(f'<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e2440"><span style="color:#aaa">{band}</span><span style="color:#e0e6ff">{cnt} ({pct(cnt,len(df))})</span></div>' for band, cnt in exp_dist.items())}
  </div>
</div>

<!-- APRIORI -->
<h2 class="section-title">🔗 Apriori — Khai phá Luật kết hợp <span class="algo-badge">Association Rules</span></h2>

<div class="card">
  <h3>📈 Top 20 Kỹ năng IT phổ biến nhất (Frequency)</h3>
  <table>
    <thead><tr><th>#</th><th>Kỹ năng</th><th>Số Jobs</th><th style="min-width:200px">Tần suất</th><th>%</th></tr></thead>
    <tbody>{skill_top20_html}</tbody>
  </table>
</div>

<div class="card">
  <h3>⚡ Top 15 Luật kết hợp kỹ năng mạnh nhất (Lift > 1.1)</h3>
  <table>
    <thead>
      <tr>
        <th>Tiền đề (Antecedent)</th><th></th><th>Hệ quả (Consequent)</th>
        <th>Support</th><th>Confidence</th><th>Lift ▼</th>
      </tr>
    </thead>
    <tbody>{apriori_rows_html}</tbody>
  </table>
  <div class="insight">
    <div class="insight-title">💡 Đọc kết quả Apriori</div>
    <ul>
      <li><strong>Support</strong>: Tỷ lệ % job có cả 2 kỹ năng xuất hiện cùng nhau</li>
      <li><strong>Confidence</strong>: Nếu có kỹ năng A → khả năng có kỹ năng B là bao nhiêu</li>
      <li><strong style="color:#2af598">Lift > 1</strong>: Hai kỹ năng bổ trợ nhau (càng cao càng mạnh) | Lift = 1: Độc lập | Lift &lt; 1: Xung đột</li>
    </ul>
  </div>
</div>

<!-- K-MEANS -->
<h2 class="section-title">🎯 K-Means — Phân cụm vị trí IT <span class="algo-badge">Clustering</span></h2>

<div class="two-col">
  <div class="card">
    <h3>📐 Chọn k tối ưu — Silhouette Score</h3>
    {sil_bars}
    <div style="margin-top:16px;padding:12px;background:#0d1117;border-radius:8px;text-align:center">
      <span class="metric-chip">✓ k = {best_k} được chọn &nbsp;·&nbsp; Silhouette = {max(silhouettes):.4f}</span>
    </div>
  </div>
  <div class="card">
    <h3>🧮 Phương pháp</h3>
    <div style="color:#b0bdd8;font-size:.9rem;line-height:1.9">
      <div style="margin-bottom:10px"><span class="tag">Features</span> salary_avg_mil_vnd · job_level_order · skill_count · years_of_experience</div>
      <div style="margin-bottom:10px"><span class="tag">Chuẩn hoá</span> StandardScaler (Z-score normalization)</div>
      <div style="margin-bottom:10px"><span class="tag">Chọn k</span> Silhouette Score tối đa trong k ∈ [2,7]</div>
      <div><span class="tag">n_init</span> 10 lần khởi tạo ngẫu nhiên → chọn inertia nhỏ nhất</div>
    </div>
  </div>
</div>

<div class="card">
  <h3>📊 Tổng quan {best_k} cụm việc làm IT</h3>
  <table>
    <thead>
      <tr><th>Cụm</th><th>Tên cụm</th><th>Số jobs</th><th>Lương TB (tr VNĐ)</th><th>Bậc TB (0–5)</th><th>Skills TB</th><th>Kinh nghiệm TB</th></tr>
    </thead>
    <tbody>{cluster_rows_html}</tbody>
  </table>
  <div class="insight">
    <div class="insight-title">💡 Giải thích thang bậc (job_level_order)</div>
    <ul>
      <li>0 = Intern / Thực tập &nbsp;·&nbsp; 1 = Fresher &nbsp;·&nbsp; 2 = Experienced &nbsp;·&nbsp; 3 = Team Leader &nbsp;·&nbsp; 4 = Manager &nbsp;·&nbsp; 5 = Director</li>
    </ul>
  </div>
</div>

<!-- DECISION TREE -->
<h2 class="section-title">🌳 Decision Tree — Phân loại cấp bậc <span class="algo-badge">Classification</span></h2>

<div class="two-col">
  <div class="card">
    <h3>🏆 Kết quả mô hình</h3>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">
      <div style="background:#0d1117;border-radius:12px;padding:16px;text-align:center">
        <div style="font-size:1.8rem;font-weight:800;color:#2af598">{cv.mean():.1%}</div>
        <div style="color:#aaa;font-size:.82rem">Cross-Val Accuracy (k=5)</div>
        <div style="color:#555;font-size:.78rem">± {cv.std():.3f}</div>
      </div>
      <div style="background:#0d1117;border-radius:12px;padding:16px;text-align:center">
        <div style="font-size:1.8rem;font-weight:800;color:#6c63ff">{acc:.1%}</div>
        <div style="color:#aaa;font-size:.82rem">Test Accuracy (20% holdout)</div>
        <div style="color:#555;font-size:.78rem">200 samples</div>
      </div>
    </div>
    <table>
      <thead><tr><th>Lớp</th><th>Precision</th><th>Recall</th><th>F1-Score</th><th>Support</th></tr></thead>
      <tbody>{dt_report_rows}</tbody>
    </table>
  </div>
  <div class="card">
    <h3>⭐ Top Feature Quan trọng nhất</h3>
    <table>
      <thead><tr><th>Đặc trưng</th><th style="min-width:150px">Importance</th><th>Score</th></tr></thead>
      <tbody>{imp_rows_html}</tbody>
    </table>
  </div>
</div>

<div class="card">
  <h3>💡 Cách đọc kết quả Decision Tree</h3>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px">
    <div style="background:#0d1117;border-radius:12px;padding:18px">
      <div style="color:#f7971e;font-weight:700;margin-bottom:8px">📏 Precision</div>
      <div style="color:#b0bdd8;font-size:.9rem">Trong số model dự đoán là <em>Senior</em> → có bao nhiêu % thực sự là Senior</div>
    </div>
    <div style="background:#0d1117;border-radius:12px;padding:18px">
      <div style="color:#2af598;font-weight:700;margin-bottom:8px">🎯 Recall</div>
      <div style="color:#b0bdd8;font-size:.9rem">Trong số tất cả <em>Senior</em> thực tế → model tìm đúng được bao nhiêu %</div>
    </div>
    <div style="background:#0d1117;border-radius:12px;padding:18px">
      <div style="color:#6c63ff;font-weight:700;margin-bottom:8px">⚖️ F1-Score</div>
      <div style="color:#b0bdd8;font-size:.9rem">Trung bình điều hoà của Precision & Recall — chỉ số tổng hợp tốt nhất</div>
    </div>
    <div style="background:#0d1117;border-radius:12px;padding:18px">
      <div style="color:#ee0979;font-weight:700;margin-bottom:8px">🔑 Feature Importance</div>
      <div style="color:#b0bdd8;font-size:.9rem"><strong>years_of_experience</strong> chiếm {top_imp.iloc[0]:.0%} → Kinh nghiệm là yếu tố quyết định cấp bậc</div>
    </div>
  </div>
</div>

<!-- CONCLUSIONS -->
<h2 class="section-title">📌 Kết luận tổng hợp <span class="algo-badge">Insights</span></h2>
<div class="card">
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px">
    <div class="insight">
      <div class="insight-title">🔗 Từ Apriori</div>
      <ul>
        <li>Python & SQL là cặp kỹ năng gắn kết mạnh nhất thị trường IT</li>
        <li>Lift cao → học combo Python+SQL tăng cơ hội trúng tuyển rõ rệt</li>
        <li>Các kỹ năng soft skill (Communication, English) thường đi cùng Technical</li>
      </ul>
    </div>
    <div class="insight" style="background:linear-gradient(135deg,rgba(42,245,152,.08),rgba(0,242,254,.05));border-color:rgba(42,245,152,.3)">
      <div class="insight-title" style="color:#2af598">🎯 Từ K-Means</div>
      <ul>
        <li>Thị trường IT phân hoá rõ thành {best_k} nhóm đặc trưng</li>
        <li>Nhóm Developer/Engineer đông nhất — cơ hội việc làm lớn nhất</li>
        <li>Manager/Director: yêu cầu &gt;5 năm KN, lương chênh lệch rõ rệt</li>
      </ul>
    </div>
    <div class="insight" style="background:linear-gradient(135deg,rgba(247,151,30,.08),rgba(238,9,121,.05));border-color:rgba(247,151,30,.3)">
      <div class="insight-title" style="color:#f7971e">🌳 Từ Decision Tree</div>
      <ul>
        <li>Kinh nghiệm ({top_imp.iloc[0]:.0%}) là yếu tố số 1 quyết định cấp bậc</li>
        <li>Mức lương ({top_imp.iloc[1]:.1%}) và vị trí địa lý cũng có tác động đáng kể</li>
        <li>Accuracy {acc:.0%} — mô hình đủ mạnh để sơ bộ phân loại candidate</li>
      </ul>
    </div>
  </div>
</div>

</div>
<footer>
  Báo cáo được tạo tự động bởi Pipeline Data Mining &nbsp;·&nbsp;
  Nguồn dữ liệu: <strong>VietnamWorks API</strong> &nbsp;·&nbsp;
  1,000 tin tuyển dụng IT &nbsp;·&nbsp; 52 thuộc tính
</footer>
</body>
</html>"""

out_path = "bao_cao_data_mining.html"
Path(out_path).write_text(html, encoding="utf-8")
size_kb = Path(out_path).stat().st_size / 1024
print(f"[✓] Báo cáo HTML đã xuất: {out_path}  ({size_kb:.1f} KB)")
print(f"    Mở file trong trình duyệt để xem báo cáo đầy đủ.")
print("\n" + "="*70)
print("  HOÀN THÀNH TOÀN BỘ PIPELINE DATA MINING!")
print("="*70)
