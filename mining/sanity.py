"""Kiểm tra logic ngành S-01..S-06 (docs/spec/08_evaluation_spec.md §3.2).

Mỗi kiểm tra trả {id, status: pass|fail|skipped|info, criterion, detail, values}.
S-01..S-03 tính thẳng từ ma trận K-tool (không phụ thuộc ngưỡng min_support của FP-Growth).
Từ 20/11 (docs/spec/mining/M0_chuan_bi.md): S-02 chỉ báo cáo (`info`, M0.7a); S-03 ngưỡng 0,60 (M0.7b);
S-04 dùng đúng thang 0 = Intern/Fresher … 3 = Senior, Lead/Manager ghi riêng (MNAR, M0.8);
lương = salary_avg_mil (= salary_target_m của bước 10) trên tin không thỏa thuận, không salary_outlier (M0.9).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from mining.association import find_skill, pair_stats
from mining.config import SENIORITY_ORDER_LABELS, SanityParams
from mining.salary_model import ALL_SCOPE

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


def _salary_subset(meta: pd.DataFrame) -> pd.DataFrame:
    """Tin có lương dùng được cho S-04, S-06: có số, không thỏa thuận, không bị Silver gắn cờ ngoại lai."""
    sal = pd.to_numeric(meta["salary_avg_mil"], errors="coerce")
    neg = meta["is_negotiable"].astype(bool) if "is_negotiable" in meta else False
    out = meta["salary_outlier"].astype(bool) if "salary_outlier" in meta else False
    return meta.loc[sal.notna() & (sal > 0) & ~neg & ~out]


def run_sanity_checks(
    meta: pd.DataFrame,
    skills: pd.DataFrame,
    skill_values: pd.DataFrame | None = None,
    params: SanityParams | None = None,
) -> list[dict[str, Any]]:
    p = params or SanityParams()
    s02 = _rule_check("S-02", skills, "flutter", ["dart"], 0.90, None,
                      "{Flutter} => {Dart}: chỉ báo cáo (độ đầy đủ của JD, quyết định 6)")
    if p.s02_report_only and s02["status"] in ("pass", "fail"):
        s02["status"] = "info"
    out = [
        _rule_check("S-01", skills, "spring_boot", ["java"], p.s01_min_conf, p.s01_min_lift,
                    f"{{Spring Boot}} => {{Java}}: confidence >= {p.s01_min_conf} và lift >= {p.s01_min_lift}"),
        s02,
        _rule_check("S-03", skills, "react", ["javascript", "typescript"], p.s03_min_conf, None,
                    f"{{React}} => {{JavaScript hoặc TypeScript}}: confidence >= {p.s03_min_conf}"),
    ]

    # S-04: trung vị lương tăng dần Intern/Fresher < Junior < Middle < Senior; Lead/Manager ghi riêng (MNAR)
    sub = _salary_subset(meta)
    crit4 = "Median: Intern/Fresher < Junior < Middle < Senior (Lead/Manager ghi riêng, không xét)"
    grp = sub.groupby("seniority_ord")["salary_avg_mil"]
    med, cnt = grp.median(), grp.size()
    chain = {i: SENIORITY_ORDER_LABELS[i] for i in range(4)}
    vals = {lab: round(float(med[i]), 2) for i, lab in chain.items() if i in med.index}
    counts = {lab: int(cnt[i]) for i, lab in chain.items() if i in cnt.index}
    lead = None
    if 4 in med.index:
        lv = meta["seniority_ord"] == 4
        neg_share = float(meta.loc[lv, "is_negotiable"].astype(bool).mean()) if "is_negotiable" in meta else None
        lead = {"median": round(float(med[4]), 2), "n": int(cnt[4]),
                "negotiable_share": None if neg_share is None else round(neg_share, 3)}
    if len(vals) < 4:
        out.append(_result("S-04", "skipped", crit4, "Thiếu tin có lương ở một số cấp bậc.",
                           medians=vals, counts=counts, lead=lead))
    else:
        seq = list(vals.values())
        ok = all(a < b for a, b in zip(seq, seq[1:], strict=False))
        detail = " < ".join(f"{k}={v}" for k, v in vals.items())
        if lead:
            detail += f"; Lead/Manager={lead['median']} (thỏa thuận {lead['negotiable_share']})"
        out.append(_result("S-04", "pass" if ok else "fail", crit4, detail, medians=vals, counts=counts, lead=lead))

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
    crit6 = f"Median(HN) và Median(HCM) > {p.s06_ratio} x Median(tỉnh khác, trừ Remote)"
    g = sub.groupby("location_group")["salary_avg_mil"].median()
    if not {"ha_noi", "ho_chi_minh", "khac"} <= set(g.index):
        out.append(_result("S-06", "skipped", crit6, "Thiếu tin có lương ở HN, HCM hoặc tỉnh khác.",
                           medians={k: round(float(v), 2) for k, v in g.items()}))
    else:
        other = float(g["khac"])
        ratios = {k: round(float(g[k]) / other, 3) for k in ("ha_noi", "ho_chi_minh")}
        ok = all(r > p.s06_ratio for r in ratios.values())
        out.append(_result("S-06", "pass" if ok else "fail", crit6,
                           f"HN/khác={ratios['ha_noi']}, HCM/khác={ratios['ho_chi_minh']}",
                           ratios=ratios, medians={k: round(float(v), 2) for k, v in g.items()}))
    return out


def summarize(checks: list[dict[str, Any]]) -> dict[str, Any]:
    """`info` chỉ để báo cáo: không tính vào pass/fail/all_passed."""
    statuses = [c["status"] for c in checks if c["status"] != "info"]
    return {"n_pass": statuses.count("pass"), "n_fail": statuses.count("fail"),
            "n_skipped": statuses.count("skipped"), "n_info": sum(c["status"] == "info" for c in checks),
            "all_passed": bool(statuses) and all(s == "pass" for s in statuses)}


