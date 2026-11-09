"""Kiểm tra logic ngành S-01..S-06 (docs/spec/08_evaluation_spec.md §3.2).

Mỗi kiểm tra trả {id, status: pass|fail|skipped, criterion, detail, values}.
S-01..S-03 tính thẳng từ ma trận kỹ năng (không phụ thuộc ngưỡng min_support của FP-Growth).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from mining.association import find_skill, pair_stats
from mining.salary_model import ALL_SCOPE, select_training_subset

SKILL_ALIASES = {
    "spring_boot": ["Spring Boot", "SpringBoot", "Spring"],
    "java": ["Java"],
    "flutter": ["Flutter"],
    "dart": ["Dart"],
    "react": ["React", "ReactJS", "React.js"],
    "javascript": ["JavaScript", "JS"],
    "typescript": ["TypeScript", "TS"],
    "aws": ["AWS", "Amazon Web Services"],
    "kubernetes": ["Kubernetes", "K8s"],
    "system_design": ["System Design", "System Architecture"],
}


def _result(cid: str, status: str, criterion: str, detail: str, **values: Any) -> dict[str, Any]:
    return {"id": cid, "status": status, "criterion": criterion, "detail": detail, "values": values}


def _rule_check(cid: str, skills: pd.DataFrame, ante: str, cons: list[str], min_conf: float,
                min_lift: float | None, criterion: str) -> dict[str, Any]:
    a = find_skill(skills, SKILL_ALIASES[ante])
    cs = [c for c in (find_skill(skills, SKILL_ALIASES[k]) for k in cons) if c]
    if a is None or not cs:
        return _result(cid, "skipped", criterion, f"Thiếu cột kỹ năng ({ante} hoặc {cons}).")
    st = pair_stats(skills, a, cs)
    if st["confidence"] is None:
        return _result(cid, "skipped", criterion, f"Không có tin nào chứa {a}.", **st)
    ok = st["confidence"] >= min_conf and (min_lift is None or st["lift"] >= min_lift)
    rule = f"{{{a}}} => {{{' | '.join(cs)}}}"
    return _result(cid, "pass" if ok else "fail", criterion,
                   f"{rule}: conf={st['confidence']:.3f}, lift={st['lift']:.3f}, n={st['n_antecedent']}",
                   **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in st.items()})


def run_sanity_checks(
    meta: pd.DataFrame,
    skills: pd.DataFrame,
    skill_values: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    out = [
        _rule_check("S-01", skills, "spring_boot", ["java"], 0.85, 1.5,
                    "{Spring Boot} => {Java}: confidence >= 0.85 và lift >= 1.5"),
        _rule_check("S-02", skills, "flutter", ["dart"], 0.90, None,
                    "{Flutter} => {Dart}: confidence >= 0.90"),
        _rule_check("S-03", skills, "react", ["javascript", "typescript"], 0.80, None,
                    "{React} => {JavaScript hoặc TypeScript}: confidence >= 0.80"),
    ]

    # S-04: trung vị lương tăng dần Fresher < Junior < Middle < Senior (trên Subset A)
    mask, _ = select_training_subset(meta)
    sub = meta.loc[mask]
    crit4 = "Median(Senior) > Median(Middle) > Median(Junior) > Median(Fresher)"
    med = sub.groupby("seniority_ord")["salary_avg_mil"].median()
    cnt = sub.groupby("seniority_ord")["salary_avg_mil"].size()
    levels = {1: "Fresher", 2: "Junior", 3: "Middle", 4: "Senior"}
    vals = {levels[k]: round(float(med[k]), 2) for k in levels if k in med.index}
    counts = {levels[k]: int(cnt[k]) for k in levels if k in cnt.index}
    if len(vals) < 4:
        out.append(_result("S-04", "skipped", crit4, "Thiếu tin có lương ở một số cấp bậc.",
                           medians=vals, counts=counts))
    else:
        seq = [vals[x] for x in ("Fresher", "Junior", "Middle", "Senior")]
        ok = all(a < b for a, b in zip(seq, seq[1:], strict=False))
        out.append(_result("S-04", "pass" if ok else "fail", crit4,
                           " < ".join(f"{k}={v}" for k, v in vals.items()), medians=vals, counts=counts))

    # S-05: SHAP biên dương cho AWS, Kubernetes hoặc System Design
    crit5 = "phi > 0 cho AWS, Kubernetes hoặc System Design (phạm vi ALL)"
    if skill_values is None or skill_values.empty:
        out.append(_result("S-05", "skipped", crit5, "Chưa có bảng SHAP."))
    else:
        allv = skill_values[skill_values["job_family"] == ALL_SCOPE].set_index("skill_name")
        found = {}
        for key in ("aws", "kubernetes", "system_design"):
            for alias in SKILL_ALIASES[key]:
                if alias in allv.index:
                    r = allv.loc[alias]
                    found[alias] = {"phi": round(float(r["mean_shap_value"]), 4),
                                    "marginal_trieu": round(float(r["marginal_trieu"]), 2),
                                    "n": int(r["sample_size"])}
                    break
        if not found:
            out.append(_result("S-05", "skipped", crit5, "Không có kỹ năng nào trong 3 kỹ năng trên."))
        else:
            ok = any(v["phi"] > 0 for v in found.values())
            out.append(_result("S-05", "pass" if ok else "fail", crit5,
                               ", ".join(f"{k}: phi={v['phi']}" for k, v in found.items()), skills=found))

    # S-06: trung vị lương HN và HCM cao hơn > 20% so với tỉnh khác (trừ Remote)
    crit6 = "Median(HN) và Median(HCM) > 1.2 x Median(tỉnh khác, trừ Remote)"
    g = sub.groupby("location_group")["salary_avg_mil"].median()
    if not {"ha_noi", "ho_chi_minh", "khac"} <= set(g.index):
        out.append(_result("S-06", "skipped", crit6, "Thiếu tin có lương ở HN, HCM hoặc tỉnh khác.",
                           medians={k: round(float(v), 2) for k, v in g.items()}))
    else:
        other = float(g["khac"])
        ratios = {k: round(float(g[k]) / other, 3) for k in ("ha_noi", "ho_chi_minh")}
        ok = all(r > 1.2 for r in ratios.values())
        out.append(_result("S-06", "pass" if ok else "fail", crit6,
                           f"HN/khác={ratios['ha_noi']}, HCM/khác={ratios['ho_chi_minh']}",
                           ratios=ratios, medians={k: round(float(v), 2) for k, v in g.items()}))
    return out


def summarize(checks: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [c["status"] for c in checks]
    return {"n_pass": statuses.count("pass"), "n_fail": statuses.count("fail"),
            "n_skipped": statuses.count("skipped"),
            "all_passed": bool(statuses) and all(s == "pass" for s in statuses)}


