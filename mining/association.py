"""M2: gói kỹ năng cho SD2, FP-Growth phân tầng (docs/spec/mining/M2_fp_growth.md).

- Giỏ = K-tool (`MiningData.skills`, cột `skill__`, không có `other_skill`).
- Vĩ mô: toàn bộ tin, min_support = 0,05. Vi mô: từng job_family đủ lớn, rồi nghề × nhóm cấp
  (người mới / Middle+), min_support = max(0,02; 10 / số giỏ) (M2.2a: mỗi luật dựa trên ít nhất 10 tin).
- Lọc luật: confidence >= 0,60 và lift > 1,20; thêm conviction, cosine, n_support (số tin).
- Ngoài luật: top 15 theo nghề ba bảng tool / concept / soft (2.1), kỹ năng hiếm (2.4),
  độ ổn định khi đổi support một bậc (M2.5), 20 luật để kiểm tay (M2.6).

Giao dịch là một tin có ít nhất 1 kỹ năng đã mã hóa: tin không có kỹ năng nào không phải "giỏ hàng"
và sẽ làm loãng support. Số tin bị bỏ ghi trong metrics.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mlxtend.frequent_patterns import association_rules, fpgrowth

from mining.config import JOB_FAMILY_OTHER, AssociationParams

logger = logging.getLogger(__name__)

RULE_COLUMNS = [
    "antecedents", "consequents", "support", "confidence", "lift", "conviction", "cosine",
    "antecedent_support", "consequent_support", "job_family_scope", "level_group", "n_transactions", "n_support",
]
MACRO_SCOPE = "ALL"
ALL_LEVELS = "all"
LEVEL_GROUPS = ("newcomer", "middle_plus")
SENIOR_LABELS = ("Senior", "Lead/Manager")


def min_support_for(n_transactions: int, base: float, min_count: int) -> float:
    """M2.2a: support tối thiểu của một phạm vi = max(base, min_count / số giỏ)."""
    return max(base, min_count / n_transactions) if n_transactions else base


def _empty_rules() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in RULE_COLUMNS})


def mine_rules(
    skills: pd.DataFrame,
    min_support: float,
    min_confidence: float,
    min_lift: float,
    max_len: int = 3,
    scope: str = MACRO_SCOPE,
    level_group: str = ALL_LEVELS,
) -> pd.DataFrame:
    """Chạy FP-Growth + association_rules trên ma trận 0/1, trả bảng luật theo RULE_COLUMNS."""
    basket = skills.loc[skills.sum(axis=1) > 0]
    basket = basket.loc[:, basket.sum(axis=0) > 0].astype(bool)
    n = len(basket)
    if n == 0 or basket.shape[1] < 2:
        return _empty_rules()

    itemsets = fpgrowth(basket, min_support=min_support, use_colnames=True, max_len=max_len)
    if itemsets.empty or (itemsets["itemsets"].apply(len) > 1).sum() == 0:
        return _empty_rules()

    with np.errstate(divide="ignore", invalid="ignore"):  # mlxtend chia 0 ở chỉ số "certainty" (không dùng)
        rules = association_rules(itemsets, num_itemsets=n, metric="confidence", min_threshold=min_confidence)
    rules = rules[rules["lift"] > min_lift]
    if rules.empty:
        return _empty_rules()

    out = pd.DataFrame({
        "antecedents": [sorted(map(str, a)) for a in rules["antecedents"]],
        "consequents": [sorted(map(str, c)) for c in rules["consequents"]],
        "support": rules["support"].astype(float).to_numpy(),
        "confidence": rules["confidence"].astype(float).to_numpy(),
        "lift": rules["lift"].astype(float).to_numpy(),
        # confidence = 1 -> conviction vô hạn; ghi null để JSON/Dashboard đọc được.
        "conviction": rules["conviction"].astype(float).replace([np.inf, -np.inf], np.nan).to_numpy(),
        "cosine": (rules["support"] / np.sqrt(rules["antecedent support"] * rules["consequent support"])).astype(float).to_numpy(),
        "antecedent_support": rules["antecedent support"].astype(float).to_numpy(),
        "consequent_support": rules["consequent support"].astype(float).to_numpy(),
    })
    out["job_family_scope"] = scope
    out["level_group"] = level_group
    out["n_transactions"] = n
    out["n_support"] = (out["support"] * n).round().astype(int)
    out["_key"] = [f"{','.join(a)}=>{','.join(c)}" for a, c in zip(out["antecedents"], out["consequents"], strict=True)]
    out = out.sort_values(["lift", "confidence", "_key"], ascending=[False, False, True]).drop(columns="_key")
    return out.reset_index(drop=True)


def mine_stratified_rules(
    skills: pd.DataFrame,
    job_family: pd.Series,
    params: AssociationParams | None = None,
    level_group: pd.Series | None = None,
    support_factor: float = 1.0,
    with_levels: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Vĩ mô (ALL) + vi mô theo nghề (+ nghề × nhóm cấp nếu có `level_group`). Trả (bảng luật, metrics).

    `support_factor` nhân vào support gốc (dùng cho kiểm ổn định M2.5)."""
    p = params or AssociationParams()
    skills = skills.reset_index(drop=True)
    job_family = pd.Series(job_family).reset_index(drop=True).fillna(JOB_FAMILY_OTHER).astype(str)
    has_skill = skills.sum(axis=1).to_numpy() > 0
    n_all = int(has_skill.sum())

    macro_sup = min_support_for(n_all, p.macro_min_support * support_factor, p.min_support_count)
    frames = [mine_rules(skills, macro_sup, p.min_confidence, p.min_lift, p.max_len, MACRO_SCOPE)]
    scopes: list[dict[str, Any]] = [{"scope": MACRO_SCOPE, "level_group": ALL_LEVELS, "n_transactions": n_all,
                                     "min_support": round(macro_sup, 4), "n_rules": len(frames[0])}]

    groups: list[tuple[str, str, Any]] = [(fam, ALL_LEVELS, idx) for fam, idx in job_family.groupby(job_family).groups.items()]
    if level_group is not None and with_levels:
        lg = pd.Series(level_group).reset_index(drop=True).astype(str)
        for (fam, lv), idx in pd.DataFrame({"f": job_family, "l": lg}).groupby(["f", "l"]).groups.items():
            if lv in LEVEL_GROUPS:
                groups.append((fam, lv, idx))
    for fam, lv, idx in sorted(groups, key=lambda g: (g[0], g[1] != ALL_LEVELS, g[1])):
        sub = skills.loc[idx]
        n_tx = int((sub.sum(axis=1) > 0).sum())
        if n_tx < p.min_group_size:
            scopes.append({"scope": fam, "level_group": lv, "n_transactions": n_tx,
                           "skipped": f"< {p.min_group_size} tin"})
            continue
        sup = min_support_for(n_tx, p.micro_min_support * support_factor, p.min_support_count)
        r = mine_rules(sub, sup, p.min_confidence, p.min_lift, p.max_len, fam, lv)
        frames.append(r)
        scopes.append({"scope": fam, "level_group": lv, "n_transactions": n_tx, "min_support": round(sup, 4),
                       "n_rules": len(r)})

    frames = [f for f in frames if not f.empty]
    rules = pd.concat(frames, ignore_index=True) if frames else _empty_rules()

    macro = rules[rules["job_family_scope"] == MACRO_SCOPE] if not rules.empty else rules
    no_tool = pd.Series(~has_skill).groupby(job_family).sum()
    metrics = {
        "params": {k: getattr(p, k) for k in ("macro_min_support", "micro_min_support", "min_support_count",
                                             "min_confidence", "min_lift", "max_len", "min_group_size")},
        "n_jobs": int(len(skills)),
        "n_jobs_without_skill": int((~has_skill).sum()),
        "n_jobs_without_tool_by_family": {k: int(v) for k, v in no_tool.items() if v},
        "n_skill_columns": int(skills.shape[1]),
        "n_rules_total": int(len(rules)),
        "n_rules_macro": int(len(macro)),
        "n_rules_unique": int(len({(tuple(a), tuple(c)) for a, c in zip(rules["antecedents"], rules["consequents"], strict=False)})) if len(rules) else 0,
        "meets_min_rules_target": bool(len(rules) >= p.min_rules_target),
        "min_rules_target": p.min_rules_target,
        "scopes": scopes,
        "top_rules_by_lift": format_rules(rules.head(0) if rules.empty else
                                          rules.sort_values(["lift", "confidence"], ascending=False).head(10)),
    }
    if level_group is not None and with_levels and len(rules):
        metrics["level_compare"] = compare_levels(rules)
    return rules, metrics


def _keys(rules: pd.DataFrame) -> set[str]:
    return {f"{','.join(a)}=>{','.join(c)}" for a, c in zip(rules["antecedents"], rules["consequents"], strict=True)}


def compare_levels(rules: pd.DataFrame) -> dict[str, dict[str, int]]:
    """2.3: với nghề có luật ở cả hai nhóm cấp, đếm luật chỉ ở người mới, chỉ ở Middle+, ở cả hai."""
    out = {}
    for fam, g in rules[rules["level_group"].isin(LEVEL_GROUPS)].groupby("job_family_scope"):
        a, b = _keys(g[g["level_group"] == "newcomer"]), _keys(g[g["level_group"] == "middle_plus"])
        if a and b:
            out[fam] = {"only_newcomer": len(a - b), "only_middle_plus": len(b - a), "both": len(a & b)}
    return out


def top_skills_by_family(meta: pd.DataFrame, job_skills: pd.DataFrame | None, blocks: dict | None,
                         p: AssociationParams | None = None) -> dict[str, Any]:
    """2.1: tỷ lệ tin của nghề có kỹ năng k, top N, ba bảng riêng (tool, concept, soft). Thêm phạm vi ALL."""
    from mining.bi import _view_sets, labels

    p = p or AssociationParams()
    meta = meta.reset_index(drop=True)
    sets = _view_sets(meta, job_skills, blocks)
    fam = labels(meta["job_family"])
    ids_all = meta["job_id"].astype(str)
    out: dict[str, Any] = {}
    for f in [MACRO_SCOPE] + sorted(fam.unique()):
        ids = ids_all.tolist() if f == MACRO_SCOPE else ids_all[fam == f].tolist()
        n = len(ids)
        entry: dict[str, Any] = {"n_jobs": n}
        if n < p.min_family_jobs:
            entry["note"] = "ít dữ liệu"
        for view in ("tool", "concept", "soft"):
            cnt: dict[str, int] = {}
            for j in ids:
                for s in sets.get(view, {}).get(j, ()):
                    cnt[s] = cnt.get(s, 0) + 1
            top = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[: p.top_n]
            entry[view] = [{"skill": s, "n": c, "share": round(c / n, 4) if n >= p.min_family_jobs else None}
                           for s, c in top]
        out[f] = entry
    return {"top_n": p.top_n, "min_family_jobs": p.min_family_jobs, "families": out,
            "source": "job_skills + skill_view" if job_skills is not None else "ma trận (đã qua min_df)"}


def rare_skills(skills: pd.DataFrame, rules: pd.DataFrame, seniority: pd.Series,
                p: AssociationParams | None = None) -> dict[str, Any]:
    """2.4: K-tool có DF < rare_max_df số giỏ và (nằm trong luật lift >= rare_min_lift
    hoặc >= rare_senior_share số lần xuất hiện ở tin Senior/Lead)."""
    p = p or AssociationParams()
    skills = skills.reset_index(drop=True)
    sen = pd.Series(seniority).reset_index(drop=True).astype(str)
    basket = skills.sum(axis=1) > 0
    n = int(basket.sum())
    best: dict[str, dict[str, Any]] = {}
    for _, r in rules.iterrows():
        for s in list(r["antecedents"]) + list(r["consequents"]):
            if s not in best or r["lift"] > best[s]["lift"]:
                best[s] = {"rule": f"{{{', '.join(r['antecedents'])}}} => {{{', '.join(r['consequents'])}}}",
                           "scope": r["job_family_scope"], "level_group": r.get("level_group", ALL_LEVELS),
                           "lift": round(float(r["lift"]), 4), "confidence": round(float(r["confidence"]), 4)}
    senior = sen.isin(SENIOR_LABELS).to_numpy()
    out = []
    for col in skills.columns:
        has = skills[col].to_numpy(dtype=bool) & basket.to_numpy()
        c = int(has.sum())
        if c == 0 or c / n >= p.rare_max_df:
            continue
        s_share = round(float(senior[has].mean()), 4)
        b = best.get(col)
        by_lift = b is not None and b["lift"] >= p.rare_min_lift
        by_senior = s_share >= p.rare_senior_share
        if by_lift or by_senior:
            out.append({"skill": col, "n": c, "df_share": round(c / n, 4), "senior_share": s_share,
                        "best_rule": b, "why": [w for w, ok in (("lift", by_lift), ("senior", by_senior)) if ok]})
    out.sort(key=lambda r: (r["df_share"], r["skill"]))
    return {"n_baskets": n, "params": {"rare_max_df": p.rare_max_df, "rare_min_lift": p.rare_min_lift,
                                       "rare_senior_share": p.rare_senior_share},
            "n_candidates_df": int(sum(1 for c in skills.columns
                                       if 0 < (skills[c].to_numpy(dtype=bool) & basket.to_numpy()).sum() < p.rare_max_df * n)),
            "skills": out}


def _top_keys(rules: pd.DataFrame, k: int) -> list[str]:
    """Top k luật theo lift, confidence (hòa thì theo chuỗi luật) để so độ ổn định."""
    if rules.empty:
        return []
    r = rules.assign(_k=[f"{','.join(a)}=>{','.join(c)}" for a, c in zip(rules["antecedents"], rules["consequents"], strict=True)])
    r = r.sort_values(["lift", "confidence", "_k"], ascending=[False, False, True])
    return r["_k"].head(k).tolist()


def support_stability(skills: pd.DataFrame, job_family: pd.Series,
                      p: AssociationParams | None = None) -> dict[str, Any]:
    """M2.5: chạy lại ALL và từng nghề với support × f (f trong stability_factors); overlap = |top_gốc ∩ top_mới| / |top_gốc|."""
    p = p or AssociationParams()
    base, _ = mine_stratified_rules(skills, job_family, p, with_levels=False)
    scopes = sorted(set(base["job_family_scope"])) if len(base) else []
    out: dict[str, Any] = {"top": p.stability_top, "factors": {}}
    for f in p.stability_factors:
        new, _ = mine_stratified_rules(skills, job_family, p, support_factor=f, with_levels=False)
        per = {}
        for s in scopes:
            a = _top_keys(base[base["job_family_scope"] == s], p.stability_top)
            b = set(_top_keys(new[new["job_family_scope"] == s], p.stability_top)) if len(new) else set()
            per[s] = round(len(set(a) & b) / len(a), 4) if a else None
        vals = [v for v in per.values() if v is not None]
        out["factors"][f"x{f:g}"] = {"n_rules": int(len(new)), "per_scope": per,
                                    "mean_overlap": round(float(np.mean(vals)), 4) if vals else None,
                                    "min_overlap": round(float(np.min(vals)), 4) if vals else None}
    return out


def hand_check_rules(rules: pd.DataFrame, p: AssociationParams | None = None) -> pd.DataFrame:
    """M2.6: 20 luật mạnh nhất (lift giảm dần, n_support >= min_support_count, mỗi phạm vi <= 5) để người dùng kiểm tay."""
    p = p or AssociationParams()
    cols = ["rule", "job_family_scope", "level_group", "n_support", "support", "confidence", "lift", "dung", "ghi_chu"]
    if rules.empty:
        return pd.DataFrame(columns=cols)
    r = rules[rules["n_support"] >= p.min_support_count].copy()
    r["rule"] = [f"{{{', '.join(a)}}} => {{{', '.join(c)}}}" for a, c in zip(r["antecedents"], r["consequents"], strict=True)]
    r = r.sort_values(["lift", "confidence", "rule"], ascending=[False, False, True])
    r = r.groupby(["job_family_scope", "level_group"], sort=False).head(p.hand_check_per_scope).head(p.hand_check_n)
    r = r.assign(dung=pd.NA, ghi_chu=pd.NA)
    for c in ("support", "confidence", "lift"):
        r[c] = r[c].round(4)
    return r[cols].reset_index(drop=True)


def write_hand_check(df: pd.DataFrame, path: Path) -> bool:
    """Ghi file kiểm tay; nếu file đã có cột `dung` được điền thì không ghi đè. Trả True nếu đã ghi."""
    path = Path(path)
    if path.exists():
        old = pd.read_csv(path)
        if "dung" in old.columns and old["dung"].notna().any():
            logger.warning("%s đã được điền, không ghi đè.", path)
            return False
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return True


def run_association(data, params: AssociationParams | None = None, level_labels=None) -> tuple[pd.DataFrame, dict, pd.DataFrame, dict]:
    """M2 đầy đủ: luật (gồm nghề × nhóm cấp), top 15 ba bảng, kỹ năng hiếm, độ ổn định, mẫu kiểm tay.
    Trả (luật, {tên file JSON: nội dung}, bảng kiểm tay, metrics)."""
    from mining.bi import _group
    from mining.config import BIParams

    p = params or AssociationParams()
    meta = data.meta.reset_index(drop=True)
    level = _group(meta, level_labels or BIParams())
    rules, m = mine_stratified_rules(data.skills, meta["job_family"], p, level_group=level)
    blocks = {"tool": data.skills, "concept": data.concepts, "soft": data.soft}
    top = top_skills_by_family(meta, data.job_skills, blocks, p)
    rare = rare_skills(data.skills, rules, meta["seniority"], p)
    stab = support_stability(data.skills, meta["job_family"], p)
    hc = hand_check_rules(rules, p)
    m["n_rare_skills"] = len(rare["skills"])
    m["stability"] = {k: {kk: v[kk] for kk in ("n_rules", "mean_overlap", "min_overlap")} for k, v in stab["factors"].items()}
    m["meets_stability_target"] = all((v["mean_overlap"] or 0) >= p.stability_target for v in stab["factors"].values())
    m["n_hand_check"] = int(len(hc))
    jsons = {"sd2_top_skills.json": top, "sd2_rare_skills.json": rare, "sd2_stability.json": stab}
    return rules, jsons, hc, m


def format_rules(rules: pd.DataFrame) -> list[dict[str, Any]]:
    out = []
    for _, r in rules.iterrows():
        out.append({
            "rule": f"{{{', '.join(r['antecedents'])}}} => {{{', '.join(r['consequents'])}}}",
            "scope": r["job_family_scope"],
            "level_group": r.get("level_group", ALL_LEVELS),
            "support": round(float(r["support"]), 4),
            "confidence": round(float(r["confidence"]), 4),
            "lift": round(float(r["lift"]), 4),
        })
    return out


def find_skill(skills: pd.DataFrame, candidates: Sequence[str]) -> str | None:
    """Tìm cột kỹ năng theo tên (không phân biệt hoa thường, bỏ dấu cách/chấm/gạch)."""
    def norm(s: str) -> str:
        return "".join(ch for ch in s.lower() if ch.isalnum())
    lookup = {norm(c): c for c in skills.columns}
    for cand in candidates:
        hit = lookup.get(norm(cand))
        if hit is not None:
            return hit
    return None


def pair_stats(skills: pd.DataFrame, antecedent: str, consequents: Sequence[str]) -> dict[str, Any]:
    """Support/confidence/lift của {antecedent} => {một trong consequents}, tính thẳng từ ma trận.

    Dùng cho sanity check để không phụ thuộc ngưỡng min_support của FP-Growth.
    """
    basket = skills.loc[skills.sum(axis=1) > 0]
    n = len(basket)
    a = basket[antecedent].to_numpy(dtype=bool)
    c = np.zeros(n, dtype=bool)
    for col in consequents:
        c |= basket[col].to_numpy(dtype=bool)
    n_a, n_c, n_ac = int(a.sum()), int(c.sum()), int((a & c).sum())
    if n == 0 or n_a == 0 or n_c == 0:
        return {"n_antecedent": n_a, "support": 0.0, "confidence": None, "lift": None}
    conf = n_ac / n_a
    return {"n_antecedent": n_a, "support": n_ac / n, "confidence": conf, "lift": conf / (n_c / n)}
