"""M6: lộ trình học cho người mới, SD5 (docs/spec/mining/M6_lo_trinh.md).

- 5.1 (M6.1): điểm(k) = demand(k) × (1 + premium_chuẩn_hóa(k)); demand từ M1.D (tin người mới của nghề),
  premium = delta_m của M5 (phạm vi ALL) chia max |delta_m| trong các kỹ năng của nghề; chưa định giá → 0.
  Chỉ xếp kỹ năng demand >= 5%. Danh sách công cụ và danh sách kỹ năng mềm tách riêng; kỹ năng mềm chỉ theo demand.
- 5.2 (M6.2): gói = thành phần liên thông của đồ thị luật mạnh M2 (nghề × người mới, thiếu thì cả nghề);
  bậc theo thứ tự topo, chu trình cắt cạnh confidence thấp nhất. Luật là "hay đi kèm", không phải "học trước".
  Quyết định 1.B (20/11): chỉ dùng luật 1 ⇒ 1, và vế phải là nền: react ⇒ javascript (tin có React gần như luôn
  có JavaScript) cho cạnh javascript → react, tức javascript ở bậc trước.
- 5.3 (M6.3): chưa nên đầu tư sớm = tỷ lệ ở tin Senior/Lead / tỷ lệ ở tin người mới >= 3 và demand < 5%.
- 5.4 (M6.4): coverage@N = tỷ lệ tin người mới mà top N đáp ứng >= 70% số công cụ tin đòi (tin 0 công cụ không tính);
  baseline = top N công cụ phổ biến nhất toàn thị trường. M6.5: kiểm 80/20.
Chỉ nói thị trường đòi gì; không đo người học cụ thể, không nói về chương trình đào tạo.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from mining.config import JOB_FAMILY_OTHER, MIDDLE_PLUS_LABELS, NEWCOMER_LABELS, RANDOM_STATE, RecommendParams

SENIOR_LABELS = ("Senior", "Lead/Manager")
NOTES = [
    "Thứ tự trong gói dựa trên luật kết hợp 1 ⇒ 1 (kỹ năng hay đi kèm trong cùng tin), không phải quan hệ học trước - học sau: "
    "luật X ⇒ Y mạnh nghĩa là tin đòi X gần như luôn đòi Y, nên Y được coi là nền và xếp trước X.",
    "premium lấy từ giá trị SHAP của M5: mô tả cách model dùng kỹ năng, không phải nhân quả (MINE-6).",
    "Chỉ nói thị trường đòi gì ở tin cho người mới (Intern/Fresher, Junior); không đo khoảng cách của một người học cụ thể.",
]


def family_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


def _pct(x: float) -> str:
    return f"{100 * x:.0f}%".replace(".", ",")


# ---------------------------------------------------------------------------
def priority_scores(demand: dict[str, float], delta: dict[str, float] | None, p: RecommendParams) -> list[dict[str, Any]]:
    """M6.1. `delta` None = danh sách kỹ năng mềm (chỉ theo demand)."""
    cand = {k: float(v) for k, v in demand.items() if v is not None and float(v) >= p.min_demand}
    rows = []
    if delta is None:
        rows = [{"skill": k, "demand": round(v, 4), "score": round(v, 4)} for k, v in cand.items()]
    else:
        valued = [abs(delta[k]) for k in cand if k in delta and delta[k] is not None and not np.isnan(delta[k])]
        mx = max(valued) if valued else 0.0
        for k, v in cand.items():
            d = delta.get(k)
            ok = d is not None and not np.isnan(d) and mx > 0
            prem = d / mx if ok else 0.0
            rows.append({"skill": k, "demand": round(v, 4), "premium": round(prem, 4),
                         "premium_status": "định giá" if ok else "không định giá",
                         "delta_m": round(float(d), 3) if ok else None,
                         "score": round(v * (1 + prem), 4)})
    return sorted(rows, key=lambda r: (-r["score"], r["skill"]))


# ---------------------------------------------------------------------------
def _strong_edges(skills: list[str], rules: pd.DataFrame, p: RecommendParams) -> dict[tuple[str, str], dict[str, Any]]:
    keep = set(skills)
    edges: dict[tuple[str, str], dict[str, Any]] = {}
    if rules is None or rules.empty:
        return edges
    for r in rules.itertuples():
        a, c = list(r.antecedents), list(r.consequents)
        if len(a) != 1 or len(c) != 1:  # 1.B: chỉ luật 1 ⇒ 1
            continue
        if r.confidence < p.strong_conf or r.lift < p.strong_lift or not set(a + c) <= keep:
            continue
        base, top = c[0], a[0]  # 1.B: vế phải là nền → cạnh nền → vế trái
        e = edges.get((base, top))
        if e is None or r.confidence > e["confidence"]:
            edges[(base, top)] = {"rule": f"{top} ⇒ {base}", "confidence": round(float(r.confidence), 4),
                                  "lift": round(float(r.lift), 3)}
    return edges


def _reaches(edges: set[tuple[str, str]], src: str, dst: str) -> bool:
    seen, stack = set(), [src]
    while stack:
        u = stack.pop()
        if u == dst:
            return True
        if u in seen:
            continue
        seen.add(u)
        stack.extend(v for (x, v) in edges if x == u)
    return False


def _break_cycles(nodes: set[str], edges: dict[tuple[str, str], dict]) -> list[str]:
    """Cắt cạnh confidence thấp nhất nằm trên chu trình tới khi đồ thị không còn chu trình."""
    cut = []
    while True:
        es = set(edges)
        on_cycle = [e for e in es if _reaches(es, e[1], e[0])]
        if not on_cycle:
            return cut
        worst = min(on_cycle, key=lambda e: (edges[e]["confidence"], e))
        cut.append(edges[worst]["rule"])  # ghi theo luật gốc
        del edges[worst]


def learning_path(skills: list[str], rules: pd.DataFrame, p: RecommendParams) -> dict[str, Any]:
    """M6.2: gói (thành phần liên thông >= 2 kỹ năng), bậc topo trong gói, kỹ năng đơn lẻ giữ thứ tự điểm."""
    order = {s: i for i, s in enumerate(skills)}
    edges = _strong_edges(skills, rules, p)
    parent = {s: s for s in skills}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        parent[find(a)] = find(b)
    comps: dict[str, list[str]] = {}
    for s in skills:
        comps.setdefault(find(s), []).append(s)
    bundles, standalone = [], []
    for members in sorted(comps.values(), key=lambda m: min(order[s] for s in m)):
        if len(members) < 2:
            standalone.extend(members)
            continue
        mset = set(members)
        sub = {e: v for e, v in edges.items() if e[0] in mset and e[1] in mset}
        cut = _break_cycles(mset, sub)
        level: dict[str, int] = {}
        remaining = set(members)
        lv = 1
        while remaining:  # Kahn theo tầng: bậc 1 = không có cạnh vào
            layer = {s for s in remaining if not any(b == s and a in remaining for a, b in sub)}
            for s in layer:
                level[s] = lv
            remaining -= layer
            lv += 1
        steps = []
        for s in sorted(members, key=lambda s: (level[s], order[s])):
            ins = [(a, v) for (a, b), v in sub.items() if b == s]
            ev = max(ins, key=lambda kv: (kv[1]["confidence"], kv[0]))[1] if ins and level[s] > 1 else None
            steps.append({"skill": s, "level": level[s], "evidence": ev})
        bundles.append({"name": f"Gói {min(members, key=lambda s: order[s])}",  # tên = kỹ năng điểm cao nhất
                        "skills": sorted(members, key=lambda s: order[s]), "steps": steps, "cut_edges": cut,
                        "n_rules": len(sub)})
    return {"bundles": bundles, "standalone": [s for s in skills if s in set(standalone)]}


# ---------------------------------------------------------------------------
def defer_list(sets_new: list[set], sets_senior: list[set], demand: dict[str, float], p: RecommendParams) -> list[dict]:
    """M6.3. Tỷ lệ ở tin người mới bằng 0 thì tính như 1 tin, để tỷ số không thành vô cùng."""
    n_new, n_sen = len(sets_new), len(sets_senior)
    if not n_new or not n_sen:
        return []
    c_new = Counter(s for x in sets_new for s in x)
    c_sen = Counter(s for x in sets_senior for s in x)
    out = []
    for k, c in c_sen.items():
        s_sen, s_new = c / n_sen, c_new.get(k, 0) / n_new
        ratio = s_sen / max(s_new, 1 / n_new)
        dem = float(demand.get(k, s_new) or 0.0)
        if ratio >= p.defer_ratio and dem < p.min_demand and c >= p.defer_min_jobs:  # 4.B: >= 10 tin Senior/Lead
            out.append({"skill": k, "share_senior_lead": round(s_sen, 4), "share_newcomer": round(s_new, 4),
                        "ratio": round(ratio, 3), "n_senior_lead_jobs": int(c)})
    return sorted(out, key=lambda r: (-r["n_senior_lead_jobs"], -r["ratio"], r["skill"]))


def coverage_share(job_sets: list[set], top: set, need: float) -> tuple[float | None, int, int]:
    """Tỷ lệ tin mà `top` đáp ứng >= need số công cụ của tin; tin không công cụ không vào mẫu số."""
    ok = [len(s & top) / len(s) >= need for s in job_sets if s]
    n_excl = sum(1 for s in job_sets if not s)
    return (round(sum(ok) / len(ok), 4) if ok else None), len(ok), n_excl


def _demand_from_sets(job_sets: list[set]) -> dict[str, float]:
    n = len(job_sets)
    return {k: c / n for k, c in Counter(s for x in job_sets for s in x).items()} if n else {}


def split_check(ids: list[str], tool_sets: dict, delta: dict, sources: pd.Series | None, p: RecommendParams,
                random_state: int = RANDOM_STATE) -> dict[str, Any]:
    """M6.5 với quyết định 3.B (20/11): chia 80/20 theo từng seed trong `p.split_seeds`, lấy trung bình độ lệch."""
    runs = [_split_once(ids, tool_sets, delta, sources, p, s) for s in p.split_seeds]
    diffs = [r["abs_diff"] for r in runs if r["abs_diff"] is not None]
    mean = round(float(np.mean(diffs)), 4) if diffs else None
    return {"seeds": list(p.split_seeds), "runs": runs, "abs_diff": mean,
            "abs_diff_max": round(float(np.max(diffs)), 4) if diffs else None,
            "n_train": runs[0]["n_train"], "n_test": runs[0]["n_test"],
            "ok": bool(mean is not None and mean <= p.split_max_diff)}


def _split_once(ids: list[str], tool_sets: dict, delta: dict, sources: pd.Series | None, p: RecommendParams,
                random_state: int) -> dict[str, Any]:
    """Điểm tính trên 80% tin người mới (demand tính lại, không dùng M1), coverage@10 trên 20% và 80%."""
    strat = None
    if sources is not None:
        vc = sources.value_counts()
        if len(vc) > 1 and vc.min() >= 2:
            strat = sources.to_numpy()
    tr, te = train_test_split(np.array(ids), test_size=p.split, random_state=random_state, stratify=strat)
    s_tr = [tool_sets.get(j, set()) for j in tr]
    s_te = [tool_sets.get(j, set()) for j in te]
    top = {r["skill"] for r in priority_scores(_demand_from_sets(s_tr), delta, p)[:10]}
    c_tr, _, _ = coverage_share(s_tr, top, p.coverage_need)
    c_te, n_te, _ = coverage_share(s_te, top, p.coverage_need)
    diff = None if c_tr is None or c_te is None else round(abs(c_te - c_tr), 4)
    return {"seed": int(random_state), "n_train": int(len(tr)), "n_test": int(len(te)),
            "stratified_by_source": strat is not None, "coverage10_train": c_tr, "coverage10_test": c_te,
            "n_test_eval": n_te, "abs_diff": diff}


# ---------------------------------------------------------------------------
def _rules_for(rules: pd.DataFrame | None, fam: str) -> tuple[pd.DataFrame, str]:
    if rules is None or rules.empty or "job_family_scope" not in rules:
        return pd.DataFrame(), "không có luật"
    lv = rules["level_group"] if "level_group" in rules else pd.Series("all", index=rules.index)
    r = rules[(rules["job_family_scope"] == fam) & (lv == "newcomer")]
    if len(r):
        return r, f"{fam}|newcomer"
    return rules[(rules["job_family_scope"] == fam) & (lv == "all")], f"{fam}|all (fallback: không có luật người mới)"


def _skill_text(fam: str, r: dict, n_new: int, kind: str) -> str:
    t = f"{_pct(r['demand'])} tin {fam} cho người mới ({n_new} tin) đòi {r['skill']}"
    if kind == "tool":
        t += (f"; SHAP lương {r['delta_m']:+.2f} triệu/tháng".replace(".", ",") if r.get("delta_m") is not None
              else "; chưa định giá lương (dưới 30 tin có lương)")
    return t


def run_recommend(meta: pd.DataFrame, view_sets: dict[str, dict], demand: dict, rules: pd.DataFrame | None,
                  shap_values: pd.DataFrame | None, p: RecommendParams | None = None,
                  random_state: int = RANDOM_STATE) -> tuple[dict[str, Any], dict[str, Any]]:
    """Trả ({tên file: JSON}, metrics)."""
    p = p or RecommendParams()
    meta = meta.reset_index(drop=True)
    tool_sets = view_sets.get("tool", {})
    fam = meta["job_family"].fillna(JOB_FAMILY_OTHER).astype(str)
    sen = meta["seniority"].fillna("").astype(str)
    ids = meta["job_id"].astype(str)
    delta = {}
    if shap_values is not None and len(shap_values) and "delta_m" in shap_values:
        allv = shap_values[shap_values["job_family"] == "ALL"]
        delta = dict(zip(allv["skill_name"].astype(str), allv["delta_m"].astype(float), strict=True))
    market = Counter(s for j in ids for s in tool_sets.get(j, ()))
    files: dict[str, Any] = {}
    index, fam_metrics = [], {}
    for f, d in sorted(demand.get("families", {}).items()):
        if f == JOB_FAMILY_OTHER:
            index.append({"job_family": f, "status": "không làm lộ trình", "n_newcomer": d["n_newcomer"],
                          "reason": "Other không phải một nghề"})
            continue
        if d["n_newcomer"] < p.min_newcomer_jobs:
            index.append({"job_family": f, "status": "ít dữ liệu", "n_newcomer": d["n_newcomer"]})
            continue
        new_ids = ids[(fam == f) & sen.isin(NEWCOMER_LABELS)].tolist()
        sen_ids = ids[(fam == f) & sen.isin(SENIOR_LABELS)].tolist()
        n_new = d["n_newcomer"]
        ptool = priority_scores(d.get("tool", {}), delta, p)
        psoft = priority_scores(d.get("soft", {}), None, p)
        r_fam, scope = _rules_for(rules, f)
        path = learning_path([r["skill"] for r in ptool], r_fam, p)
        path["rules_scope"] = scope
        ev = {s["skill"]: s["evidence"] for b in path["bundles"] for s in b["steps"] if s["evidence"]}
        bundle_of = {s: b["name"] for b in path["bundles"] for s in b["skills"]}
        for r in ptool:
            r["n_newcomer_jobs"] = int(round(r["demand"] * n_new))
            r["bundle"] = bundle_of.get(r["skill"])
            r["evidence"] = ev.get(r["skill"])
            r["text"] = _skill_text(f, r, n_new, "tool")
        for r in psoft:
            r["n_newcomer_jobs"] = int(round(r["demand"] * n_new))
            r["text"] = _skill_text(f, r, n_new, "soft")
        sets_new = [tool_sets.get(j, set()) for j in new_ids]
        defer = defer_list(sets_new, [tool_sets.get(j, set()) for j in sen_ids], d.get("tool", {}), p)
        cov = {}
        for n in p.coverage_ns:
            top = {r["skill"] for r in ptool[:n]}
            base = {s for s, _ in sorted(market.items(), key=lambda kv: (-kv[1], kv[0]))[:n]}
            c, n_eval, n_excl = coverage_share(sets_new, top, p.coverage_need)
            cb, _, _ = coverage_share(sets_new, base, p.coverage_need)
            cov[str(n)] = {"coverage": c, "baseline": cb, "n_eval": n_eval, "n_excluded_no_tool": n_excl,
                           "beats_baseline": bool(c is not None and cb is not None and c > cb),
                           "top": [r["skill"] for r in ptool[:n]], "baseline_top": sorted(base, key=lambda s: -market[s])}
        bundle_cov = []
        if len(path["bundles"]) >= 2:  # M6.4b
            for b in path["bundles"]:
                bs = set(b["skills"])
                js = [s for s in sets_new if s & bs]
                bundle_cov.append({"bundle": b["name"], "n_jobs": len(js), **{
                    f"coverage@{n}": coverage_share(js, set(b["skills"][:n]), p.coverage_need)[0] for n in p.coverage_ns}})
        src = meta.loc[(fam == f) & sen.isin(NEWCOMER_LABELS), "source_platform"].reset_index(drop=True) \
            if "source_platform" in meta else None
        split = split_check(new_ids, tool_sets, delta, src, p, random_state)
        files[f"sd5_{family_slug(f)}.json"] = {
            "job_family": f, "n_newcomer": n_new, "newcomer_labels": list(NEWCOMER_LABELS),
            "priority_tool": ptool, "priority_soft": psoft, "path": path, "defer": defer,
            "coverage": cov, "coverage_by_bundle": bundle_cov, "split_check": split,
            "params": {k: getattr(p, k) for k in ("min_demand", "strong_conf", "strong_lift", "defer_ratio",
                                                  "defer_min_jobs", "coverage_need", "split", "split_max_diff")},
            "notes": NOTES,
        }
        index.append({"job_family": f, "status": "có lộ trình", "n_newcomer": n_new, "file": f"sd5_{family_slug(f)}.json"})
        c10 = cov.get("10", {})
        fam_metrics[f] = {"n_newcomer": n_new, "n_priority_tool": len(ptool), "n_priority_soft": len(psoft),
                          "n_bundles": len(path["bundles"]), "n_standalone": len(path["standalone"]),
                          "n_defer": len(defer), "coverage10": c10.get("coverage"), "baseline10": c10.get("baseline"),
                          "beats_baseline10": c10.get("beats_baseline"), "split_diff": split["abs_diff"],
                          "split_ok": split["ok"], "rules_scope": scope}
    for f, n in sorted(demand.get("low_data", {}).items()):
        index.append({"job_family": f, "n_newcomer": n, **({"status": "không làm lộ trình", "reason": "Other không phải một nghề"}
                                                           if f == JOB_FAMILY_OTHER else {"status": "ít dữ liệu"})})
    files["sd5_index.json"] = {"min_newcomer_jobs": p.min_newcomer_jobs, "families": index,
                               "middle_plus_labels": list(MIDDLE_PLUS_LABELS)}
    metrics = {"families": fam_metrics, "n_families_with_path": len(fam_metrics),
               "all_beat_baseline10": bool(fam_metrics) and all(m["beats_baseline10"] for m in fam_metrics.values()),
               "all_split_ok": bool(fam_metrics) and all(m["split_ok"] for m in fam_metrics.values()),
               "n_skills_valued": len(delta)}
    return files, metrics
