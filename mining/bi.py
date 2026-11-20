"""M1: BI cho SD1, bức tranh thị trường (docs/spec/mining/M1_bi.md).

Chỉ đếm, tỷ lệ, bảng chéo, trung vị, tứ phân vị trên Silver (`MiningData.meta`). Không bù lương thiếu,
không dùng lương ước tính của M5, không nói về xu hướng (M1.0e).

Quy tắc ô (M1.0b): tỷ lệ hay trung vị tính trên một nhóm có n < `min_cell` thì để `null` kèm
`note = "ít dữ liệu"`, vẫn ghi `n`. Nhóm của tỷ lệ là mẫu số: cả bảng (bảng đếm), một hàng (bảng chéo theo hàng).

Ngoài 7 câu, M1 còn trả `baseline_salary` (M1.B, cho M5) và `newcomer_demand` (M1.D, cho M6).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from mining.config import BIParams
from mining.data_io import MiningData

UNKNOWN = "Không rõ"
OTHER = "Khác"
LOW = "ít dữ liệu"


# ---------------------------------------------------------------------------
# Bảng dùng chung
# ---------------------------------------------------------------------------
def labels(s: pd.Series) -> pd.Series:
    """Nhãn chữ; null, rỗng, "Chưa rõ" -> "Không rõ"."""
    out = pd.Series(s, copy=True).astype(object)
    bad = out.isna() | out.astype(str).str.strip().isin(["", "Chưa rõ", "None", "nan"])
    return out.where(~bad, UNKNOWN).astype(str).reset_index(drop=True)


def _r(x: float, nd: int = 4) -> float | None:
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def _sort_rows(rows: list[dict], key_cols: list[str]) -> list[dict]:
    """n giảm dần, hòa thì theo nhãn; dòng "Không rõ" luôn cuối."""
    return sorted(rows, key=lambda r: (any(r[k] == UNKNOWN for k in key_cols), -r["n"],
                                       tuple(str(r[k]) for k in key_cols)))


def count_table(s: pd.Series, by: str, p: BIParams) -> dict[str, Any]:
    lab = labels(s)
    vc = lab.value_counts()
    total = int(len(lab))
    rows = [{by: k, "n": int(v), "share": _r(v / total) if total >= p.min_cell else None} for k, v in vc.items()]
    known = total - int(vc.get(UNKNOWN, 0))
    return {"by": [by], "rows": _sort_rows(rows, [by]), "n_total": total, "scope_n": total, "n_sum": total,
            "coverage": _r(known / total) if total else None}


def crosstab_table(a: pd.Series, b: pd.Series, row: str, col: str, p: BIParams) -> dict[str, Any]:
    """Bảng chéo, tỷ lệ theo hàng (share = n / tổng hàng)."""
    la, lb = labels(a), labels(b)
    ct = pd.crosstab(la, lb)
    rows = []
    for r_lab, r in ct.iterrows():
        tot = int(r.sum())
        for c_lab, v in r.items():
            if v == 0:
                continue
            row_d = {row: r_lab, col: c_lab, "n": int(v), "row_n": tot,
                     "share": _r(v / tot) if tot >= p.min_cell else None}
            if tot < p.min_cell:
                row_d["note"] = LOW
            rows.append(row_d)
    n = int(len(la))
    rows = sorted(rows, key=lambda d: (d[row] == UNKNOWN, -d["row_n"], str(d[row]), d[col] == UNKNOWN, -d["n"], str(d[col])))
    return {"by": [row, col], "normalize": "row", "rows": rows, "n_total": n, "scope_n": n, "n_sum": int(ct.values.sum()),
            "coverage": _r(((la != UNKNOWN) & (lb != UNKNOWN)).mean()) if n else None}


def stat_table(values: pd.Series, keys: dict[str, pd.Series], p: BIParams) -> dict[str, Any]:
    """Trung vị, P25, P75 theo nhóm; nhóm n < min_cell không có số."""
    v = pd.to_numeric(pd.Series(values), errors="coerce").reset_index(drop=True)
    df = pd.DataFrame({k: labels(s) for k, s in keys.items()})
    df["_v"] = v.to_numpy()
    df = df[df["_v"].notna()]
    rows = []
    for k, g in df.groupby(list(keys), sort=True):
        k = k if isinstance(k, tuple) else (k,)
        n = int(len(g))
        d = dict(zip(keys, k, strict=True)) | {"n": n}
        if n >= p.min_cell:
            q = g["_v"].quantile([0.25, 0.5, 0.75])
            d |= {"median": _r(q[0.5], 2), "p25": _r(q[0.25], 2), "p75": _r(q[0.75], 2)}
        else:
            d |= {"median": None, "p25": None, "p75": None, "note": LOW}
        rows.append(d)
    return {"by": list(keys), "unit": "triệu VNĐ/tháng", "rows": _sort_rows(rows, list(keys)),
            "scope_n": int(len(df)), "n_sum": int(len(df))}


def _target(meta: pd.DataFrame) -> pd.Series:
    col = "salary_target_m" if "salary_target_m" in meta else "salary_avg_mil"
    return pd.to_numeric(meta[col], errors="coerce").reset_index(drop=True)


def _flag(meta: pd.DataFrame, col: str) -> pd.Series:
    if col not in meta:
        return pd.Series(False, index=range(len(meta)))
    return meta[col].astype("boolean").fillna(False).astype(bool).reset_index(drop=True)


def salary_ok(meta: pd.DataFrame) -> pd.Series:
    """M1.0c: có salary_target_m và không bị Silver gắn cờ ngoại lai. Không bù lương thiếu."""
    return _target(meta).notna() & ~_flag(meta, "salary_outlier")


def _group(meta: pd.DataFrame, p: BIParams) -> pd.Series:
    sen = labels(meta["seniority"])
    return pd.Series(np.where(sen.isin(p.newcomer), "newcomer", np.where(sen.isin(p.middle_plus), "middle_plus", UNKNOWN)))


def _question(qid: str, title: str, tables: dict, n_total: int, notes: list[str] | None = None) -> dict[str, Any]:
    return {"question": qid, "title": title, "n_total": int(n_total), "tables": tables, "notes": notes or []}


# ---------------------------------------------------------------------------
# Câu 1.1 – 1.7
# ---------------------------------------------------------------------------
def q1_1(meta: pd.DataFrame, p: BIParams) -> dict[str, Any]:
    return _question("1.1", "Nhóm nghề và trang tuyển dụng", {
        "family": count_table(meta["job_family"], "job_family", p),
        "source_by_family": crosstab_table(meta["source_platform"], meta["job_family"], "source", "job_family", p),
    }, len(meta))


def q1_2(meta: pd.DataFrame, p: BIParams) -> dict[str, Any]:
    inferred = meta["seniority_inferred"] if "seniority_inferred" in meta else pd.Series([None] * len(meta))
    inf_lab = pd.Series(inferred).map({True: "suy_ra", False: "tu_trang"})
    return _question("1.2", "Cơ cấu cấp bậc", {
        "seniority": count_table(meta["seniority"], "seniority", p),
        "family_by_seniority": crosstab_table(meta["job_family"], meta["seniority"], "job_family", "seniority", p),
        "seniority_by_inferred": crosstab_table(meta["seniority"], inf_lab, "seniority", "seniority_from", p),
    }, len(meta), ["seniority_from: tu_trang = cấp lấy từ trang; suy_ra = cấp tự suy (seniority_inferred)."])


def q1_3(meta: pd.DataFrame, p: BIParams) -> dict[str, Any]:
    prov = labels(meta["province"])
    top = [k for k in prov[prov != UNKNOWN].value_counts().index[: p.top_provinces]]
    prov_top = prov.where(prov.isin(top) | (prov == UNKNOWN), OTHER)
    return _question("1.3", "Tỉnh và hình thức làm việc", {
        "province": count_table(prov_top, "province", p),
        "family_by_work_mode": crosstab_table(meta["job_family"], meta["work_mode"], "job_family", "work_mode", p),
    }, len(meta), [f"Top {p.top_provinces} tỉnh; các tỉnh còn lại gộp vào \"{OTHER}\"."])


def salary_status(meta: pd.DataFrame) -> pd.Series:
    has = _target(meta).notna()
    neg = _flag(meta, "is_negotiable")
    return pd.Series(np.where(has, "co_luong", np.where(neg, "thoa_thuan", UNKNOWN)))


def q1_4(meta: pd.DataFrame, p: BIParams) -> dict[str, Any]:
    meta = meta.reset_index(drop=True)
    status = salary_status(meta)
    ok = salary_ok(meta)
    sal = _target(meta)
    prov = labels(meta["province"])
    top = list(prov[(prov != UNKNOWN) & ok].value_counts().index[: p.top_provinces])
    notes = [
        "co_luong = có salary_target_m (kể cả "
        f"{int((_flag(meta, 'is_negotiable') & _target(meta).notna()).sum())} tin vừa ghi thỏa thuận vừa có số).",
        f"Lương: trung vị, P25, P75 trên {int(ok.sum())} tin có số và không bị gắn cờ ngoại lai; không bù lương thiếu.",
    ]
    neg = _flag(meta, "is_negotiable")
    sen = labels(meta["seniority"])
    for lab in sorted(sen.unique()):
        m = sen == lab
        share = float(neg[m].mean()) if m.any() else 0.0
        if m.sum() >= p.min_cell and share >= p.mnar_share:
            notes.append(f"MNAR: cấp {lab} có {share:.1%} tin thỏa thuận; trung vị lương công bố có thể thấp hơn thực tế.")
    return _question("1.4", "Công khai lương và mức lương công bố", {
        "status_by_source": crosstab_table(meta["source_platform"], status, "source", "salary_status", p),
        "status_by_family": crosstab_table(meta["job_family"], status, "job_family", "salary_status", p),
        "status_by_seniority": crosstab_table(meta["seniority"], status, "seniority", "salary_status", p),
        "salary_by_family_seniority": stat_table(sal[ok], {"job_family": meta["job_family"][ok],
                                                            "seniority": meta["seniority"][ok]}, p),
        "salary_by_seniority": stat_table(sal[ok], {"seniority": meta["seniority"][ok]}, p),
        "salary_by_province": stat_table(sal[ok & prov.isin(top)], {"province": prov[ok & prov.isin(top)]}, p),
    }, len(meta), notes)


def _view_sets(meta: pd.DataFrame, job_skills: pd.DataFrame | None, data_blocks: dict | None) -> dict[str, dict]:
    """job_id -> tập kỹ năng theo view (tool, concept, soft). Ưu tiên job_skills + skill_view của bước 08;
    không có thì lấy từ ma trận (đã qua min_df), có ghi chú."""
    ids = meta["job_id"].astype(str)
    out: dict[str, dict] = {}
    if job_skills is not None:
        from processing.extraction.skills import skill_view

        js = job_skills[job_skills["job_id_global"].astype(str).isin(set(ids))]
        for view in ("tool", "concept", "soft"):
            v = skill_view(js, view)
            out[view] = v.groupby(v["job_id_global"].astype(str))["slug"].agg(lambda s: set(s)).to_dict()
        return out
    for view, mat in (data_blocks or {}).items():
        if mat is None or mat.shape[1] == 0:
            out[view] = {}
            continue
        arr = mat.to_numpy()
        cols = np.array(mat.columns)
        out[view] = {j: set(cols[arr[i] == 1]) for i, j in enumerate(ids) if arr[i].any()}
    return out


def _top_skills(ids: list[str], sets: dict, k: int, p: BIParams) -> list[dict]:
    n = len(ids)
    cnt: dict[str, int] = {}
    for j in ids:
        for s in sets.get(j, ()):
            cnt[s] = cnt.get(s, 0) + 1
    top = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
    return [{"skill": s, "n": c, "share": _r(c / n) if n >= p.min_cell else None} for s, c in top]


def q1_5(meta: pd.DataFrame, job_skills: pd.DataFrame | None, p: BIParams,
         blocks: dict | None = None) -> dict[str, Any]:
    meta = meta.reset_index(drop=True)
    grp = _group(meta, p)
    sets = _view_sets(meta, job_skills, blocks)
    ok = salary_ok(meta)
    exp = pd.to_numeric(meta["exp_min_years"], errors="coerce")
    exp_ok = exp.notna() & ~_flag(meta, "exp_inferred")
    rows, tools, soft = [], [], []
    for g in ("newcomer", "middle_plus"):
        m = grp == g
        n = int(m.sum())
        def med(s: pd.Series) -> float | None:
            return _r(s.median(), 2) if len(s) >= p.min_cell else None
        lang = meta.loc[m, "language"] if "language" in meta else pd.Series(dtype=object)
        rows.append({"group": g, "n": n,
                     "exp_median": med(exp[m & exp_ok]), "n_exp": int((m & exp_ok).sum()),
                     "n_tools_median": med(pd.to_numeric(meta.loc[m, "n_tools"], errors="coerce").dropna()),
                     "en_share": _r((lang == "en").mean()) if n >= p.min_cell else None,
                     "salary_median": med(_target(meta)[m & ok]), "n_salary": int((m & ok).sum())})
        ids = meta.loc[m, "job_id"].astype(str).tolist()
        tools += [{"group": g} | r for r in _top_skills(ids, sets.get("tool", {}), p.top_tools, p)]
        soft += [{"group": g} | r for r in _top_skills(ids, sets.get("soft", {}), p.top_soft, p)]
    notes = [f"newcomer = {', '.join(p.newcomer)}; middle_plus = {', '.join(p.middle_plus)}; "
             f"{int((grp == UNKNOWN).sum())} tin không rõ cấp không thuộc nhóm nào.",
             "exp_median chỉ trên tin exp_inferred = false; số kỹ năng = n_tools (K-tool, bước 10)."]
    if job_skills is None:
        notes.append("Top kỹ năng lấy từ ma trận (đã qua min_df), không từ job_skills.")
    return _question("1.5", "Người mới so với Middle trở lên", {
        "compare": {"by": ["group"], "rows": rows},
        "top_tools": {"by": ["group"], "view": "tool", "rows": tools},
        "top_soft": {"by": ["group"], "view": "soft", "rows": soft},
    }, len(meta), notes)


def q1_6(meta: pd.DataFrame, p: BIParams) -> dict[str, Any]:
    meta = meta.reset_index(drop=True)
    ben = meta["benefits"] if "benefits" in meta else pd.Series([None] * len(meta))
    sets = [set(b) if isinstance(b, list | tuple | np.ndarray) else set() for b in ben]
    has = pd.Series([len(s) > 0 for s in sets])
    base = int(has.sum())
    cnt: dict[str, int] = {}
    for s in sets:
        for b in s:
            cnt[b] = cnt.get(b, 0) + 1
    top = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[: p.top_benefits]
    rows = [{"benefit": b, "n": c, "share": _r(c / base) if base >= p.min_cell else None} for b, c in top]
    cross = {}
    for dim in ("seniority", "job_family"):
        lab = labels(meta[dim])
        crows = []
        for g in sorted(lab[has].unique()):
            m = has & (lab == g)
            n = int(m.sum())
            for b, _ in top[: p.top_benefit_cross]:
                c = sum(1 for i in np.flatnonzero(m.to_numpy()) if b in sets[i])
                crows.append({dim: g, "benefit": b, "n": c, "row_n": n,
                              "share": _r(c / n) if n >= p.min_cell else None} | ({} if n >= p.min_cell else {"note": LOW}))
        cross[f"top_by_{dim}"] = {"by": [dim, "benefit"], "rows": crows, "scope_n": base}
    return _question("1.6", "Phúc lợi", {"top": {"by": ["benefit"], "rows": rows, "scope_n": base}, **cross},
                     len(meta), [f"Tỷ lệ trên {base} tin có ít nhất một phúc lợi."])


def q1_7(meta: pd.DataFrame, p: BIParams) -> dict[str, Any]:
    meta = meta.reset_index(drop=True)
    month = meta["posted_month"]
    dated = meta["source_platform"].isin(p.month_compare_sources).reset_index(drop=True) & month.notna()
    period = pd.Series(np.where(month == p.first_month, "T9", "T10-T11"))[dated]
    sub = meta[dated]
    return _question("1.7", "Cơ cấu theo tháng đăng", {
        "month_by_family": crosstab_table(month, meta["job_family"], "posted_month", "job_family", p),
        "month_by_seniority": crosstab_table(month, meta["seniority"], "posted_month", "seniority", p),
        "compare_family": crosstab_table(period, sub["job_family"], "period", "job_family", p),
        "compare_seniority": crosstab_table(period, sub["seniority"], "period", "seniority", p),
    }, len(meta), [
        "Chỉ so tỷ lệ trong từng tháng, không so tổng số tin (số tin mỗi tháng phụ thuộc lịch cào).",
        f"Bảng compare_*: chỉ {len(p.month_compare_sources)} nguồn ghi ngày đăng ({', '.join(p.month_compare_sources)}).",
    ])


# ---------------------------------------------------------------------------
# M1.B, M1.D
# ---------------------------------------------------------------------------
def baseline_salary(meta: pd.DataFrame, p: BIParams) -> dict[str, Any]:
    """Trung vị salary_target_m theo nghề × cấp; ô n < min_cell lùi về cấp, rồi toàn bộ (M1.B)."""
    meta = meta.reset_index(drop=True)
    ok = salary_ok(meta)
    df = pd.DataFrame({"f": labels(meta["job_family"]), "s": labels(meta["seniority"]), "v": _target(meta)})[ok]
    overall = {"median": _r(df["v"].median(), 2), "n": int(len(df))}
    by_sen = {s: {"median": _r(g["v"].median(), 2), "n": int(len(g))} for s, g in df.groupby("s")}
    cells: dict[str, dict] = {}
    for f in sorted(labels(meta["job_family"]).unique()):
        cells[f] = {}
        for s in sorted(labels(meta["seniority"]).unique()):
            g = df[(df["f"] == f) & (df["s"] == s)]
            if len(g) >= p.min_cell:
                cells[f][s] = {"median": _r(g["v"].median(), 2), "n": int(len(g)), "fallback": None}
            elif s in by_sen and by_sen[s]["n"] >= p.min_cell:
                cells[f][s] = {"median": by_sen[s]["median"], "n": int(len(g)), "fallback": "seniority"}
            else:
                cells[f][s] = {"median": overall["median"], "n": int(len(g)), "fallback": "overall"}
    return {"unit": "triệu VNĐ/tháng", "min_cell": p.min_cell, "overall": overall, "by_seniority": by_sen,
            "cells": cells}


def newcomer_demand(meta: pd.DataFrame, job_skills: pd.DataFrame | None, p: BIParams,
                    blocks: dict | None = None) -> dict[str, Any]:
    """demand[nghề][view][kỹ năng] = tỷ lệ tin người mới của nghề có kỹ năng (M1.D)."""
    meta = meta.reset_index(drop=True)
    grp = _group(meta, p)
    fam = labels(meta["job_family"])
    sets = _view_sets(meta, job_skills, blocks)
    fams, low = {}, {}
    for f in sorted(fam.unique()):
        ids = meta.loc[(grp == "newcomer") & (fam == f), "job_id"].astype(str).tolist()
        if len(ids) < p.min_newcomer_jobs:
            low[f] = len(ids)
            continue
        fams[f] = {"n_newcomer": len(ids)}
        for view in ("tool", "concept", "soft"):
            cnt: dict[str, int] = {}
            for j in ids:
                for s in sets.get(view, {}).get(j, ()):
                    cnt[s] = cnt.get(s, 0) + 1
            fams[f][view] = {s: _r(c / len(ids)) for s, c in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))}
    return {"min_newcomer_jobs": p.min_newcomer_jobs, "families": fams, "low_data": low,
            "source": "job_skills + skill_view" if job_skills is not None else "ma trận (đã qua min_df)"}


# ---------------------------------------------------------------------------
def run_bi(data: MiningData, p: BIParams | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Trả ({tên file: nội dung JSON}, metrics). Không có thời điểm chạy trong file, để chạy lại ra cùng file."""
    p = p or BIParams()
    meta = data.meta.reset_index(drop=True)
    blocks = {"tool": data.skills, "concept": data.concepts, "soft": data.soft}
    qs = [q1_1(meta, p), q1_2(meta, p), q1_3(meta, p), q1_4(meta, p),
          q1_5(meta, data.job_skills, p, blocks), q1_6(meta, p), q1_7(meta, p)]
    out = {f"sd1_{q['question'].replace('.', '_')}.json": q for q in qs}
    out["sd1_baseline_salary.json"] = baseline_salary(meta, p)
    out["sd1_demand.json"] = newcomer_demand(meta, data.job_skills, p, blocks)

    checks, n_low = [], 0
    for q in qs:
        for name, t in q["tables"].items():
            if "n_sum" in t:
                checks.append({"table": f"{q['question']}/{name}", "ok": t["n_sum"] == t["scope_n"]})
            n_low += sum(1 for r in t.get("rows", []) if r.get("note") == LOW)
        for name in ("family", "seniority", "province"):
            t = q["tables"].get(name)
            if t is not None and t["scope_n"] != len(meta):
                checks.append({"table": f"{q['question']}/{name}", "ok": False})
    metrics = {"params": {k: getattr(p, k) for k in ("min_cell", "mnar_share", "top_provinces", "min_newcomer_jobs")},
               "n_jobs": int(len(meta)), "n_tables": sum(len(q["tables"]) for q in qs),
               "n_cells_low_data": n_low, "totals_ok": all(c["ok"] for c in checks),
               "totals_failed": [c["table"] for c in checks if not c["ok"]],
               "n_salary_ok": int(salary_ok(meta).sum()),
               "demand_families": sorted(out["sd1_demand.json"]["families"]),
               "skills_source": out["sd1_demand.json"]["source"]}
    return out, metrics
