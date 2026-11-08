"""Thuật toán 1: FP-Growth phân tầng (spec 07 §2, docs/tasks/06 bước 1).

- Vĩ mô: toàn bộ tin, min_support = 0.05.
- Vi mô: từng job_family đủ lớn, min_support = 0.02.
- Lọc luật: confidence >= 0.60 và lift > 1.20; thêm conviction và cosine (spec 08 §2).

Giao dịch là một tin có ít nhất 1 kỹ năng đã mã hóa: tin không có kỹ năng nào không phải "giỏ hàng"
và sẽ làm loãng support. Số tin bị bỏ ghi trong metrics.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from mlxtend.frequent_patterns import association_rules, fpgrowth

from mining.config import AssociationParams

logger = logging.getLogger(__name__)

RULE_COLUMNS = [
    "antecedents", "consequents", "support", "confidence", "lift", "conviction", "cosine",
    "antecedent_support", "consequent_support", "job_family_scope", "n_transactions",
]
MACRO_SCOPE = "ALL"


def _empty_rules() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in RULE_COLUMNS})


def mine_rules(
    skills: pd.DataFrame,
    min_support: float,
    min_confidence: float,
    min_lift: float,
    max_len: int = 3,
    scope: str = MACRO_SCOPE,
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
    out["n_transactions"] = n
    return out.sort_values(["lift", "confidence"], ascending=False).reset_index(drop=True)


def mine_stratified_rules(
    skills: pd.DataFrame,
    job_family: pd.Series,
    params: AssociationParams | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Vĩ mô (ALL) + vi mô theo từng job_family. Trả (bảng luật, metrics)."""
    p = params or AssociationParams()
    job_family = pd.Series(job_family).reset_index(drop=True).fillna("Khác").astype(str)
    has_skill = skills.sum(axis=1).to_numpy() > 0

    frames = [mine_rules(skills, p.macro_min_support, p.min_confidence, p.min_lift, p.max_len, MACRO_SCOPE)]
    scopes: list[dict[str, Any]] = [{"scope": MACRO_SCOPE, "n_transactions": int(has_skill.sum()),
                                     "min_support": p.macro_min_support, "n_rules": len(frames[0])}]

    for fam, idx in job_family.groupby(job_family).groups.items():
        sub = skills.loc[idx]
        n_tx = int((sub.sum(axis=1) > 0).sum())
        if n_tx < p.min_group_size:
            scopes.append({"scope": fam, "n_transactions": n_tx, "skipped": f"< {p.min_group_size} tin"})
            continue
        r = mine_rules(sub, p.micro_min_support, p.min_confidence, p.min_lift, p.max_len, fam)
        frames.append(r)
        scopes.append({"scope": fam, "n_transactions": n_tx, "min_support": p.micro_min_support, "n_rules": len(r)})

    frames = [f for f in frames if not f.empty]
    rules = pd.concat(frames, ignore_index=True) if frames else _empty_rules()

    macro = rules[rules["job_family_scope"] == MACRO_SCOPE] if not rules.empty else rules
    metrics = {
        "params": {k: getattr(p, k) for k in ("macro_min_support", "micro_min_support", "min_confidence",
                                             "min_lift", "max_len", "min_group_size")},
        "n_jobs": int(len(skills)),
        "n_jobs_without_skill": int((~has_skill).sum()),
        "n_skill_columns": int(skills.shape[1]),
        "n_rules_total": int(len(rules)),
        "n_rules_macro": int(len(macro)),
        "n_rules_unique": int(len({(tuple(a), tuple(c)) for a, c in zip(rules["antecedents"], rules["consequents"], strict=False)})) if len(rules) else 0,
        "meets_min_rules_target": bool(len(rules) >= p.min_rules_target),
        "min_rules_target": p.min_rules_target,
        "scopes": scopes,
        "top_rules_by_lift": format_rules(rules.sort_values("lift", ascending=False).head(10)) if len(rules) else [],
    }
    return rules, metrics


def format_rules(rules: pd.DataFrame) -> list[dict[str, Any]]:
    out = []
    for _, r in rules.iterrows():
        out.append({
            "rule": f"{{{', '.join(r['antecedents'])}}} => {{{', '.join(r['consequents'])}}}",
            "scope": r["job_family_scope"],
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
