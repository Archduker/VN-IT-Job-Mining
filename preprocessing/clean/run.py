# -*- coding: utf-8 -*-
"""Bước 01 Clean (docs/preprocessing/spec/P1_clean.md): khử trùng, bỏ rác, phân loại IT ở cả 8 nguồn.

Không bỏ tin ngoài IT khi chưa có preprocessing/clean/it_policy.json do người dùng duyệt (C4c).
Output giữ nguyên raw_payload, chỉ thêm metadata.clean.
"""

from __future__ import annotations

import csv
import json
import random
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from preprocessing.common import REPO_ROOT, SOURCES, province
from preprocessing.common.it_filter import classify
from preprocessing.common.jev_client import JevClient
from preprocessing.common.raw_reader import read_raw, snapshot_order
from preprocessing.common.step_report import StepReport, merge_reports
from preprocessing.integration.json_flattener import flatten_raw_job_record
from preprocessing.normalization.cross_deduplicator import normalize_company_name

STEP = "01_clean"
DATA_DIR = REPO_ROOT / "data"
OUT_DIR = DATA_DIR / "preprocessing" / STEP
REVIEW_DIR = DATA_DIR / "preprocessing" / "review"
POLICY_PATH = REPO_ROOT / "preprocessing" / "clean" / "it_policy.json"
JEV_BUDGET_USD = 0.30  # trần cho cả lượt chạy; sổ chung của OpenCode chặn ở 0,95 USD
MIN_JD_WORDS = 30  # chính sách 1.B cũ (transformation/text_metrics.filter_valid_clean_records)
TEST_ID = re.compile(r"^job-[a-z]+-\d+$")
REVIEW_NON_IT, REVIEW_CAN_KIEM, REVIEW_SEED = 50, 30, 42
KEY_FIELDS = ("job_title", "company_name", "raw_location_text", "raw_posted_date", "raw_description_text", "skills_list")

IT_QUESTION = dict(
    name="is_it_job",
    instructions="Tin tuyển dụng này có tuyển một vị trí thuộc ngành Công nghệ thông tin không "
                 "(phát triển phần mềm, dữ liệu, hạ tầng, kiểm thử, bảo mật, quản lý sản phẩm công nghệ)?",
    true_desc="Công việc chính là công việc kỹ thuật hoặc sản phẩm công nghệ thông tin.",
    false_desc="Công việc chính thuộc ngành khác (kinh doanh, kế toán, nhân sự, marketing, lái xe, giáo dục…), "
               "kể cả khi công ty là công ty công nghệ.",
)

Item = Dict[str, Any]  # {"rel", "env", "origin", "flat"}


# ---------------------------------------------------------------- khóa
def _empty(v: Any) -> bool:
    return v is None or (isinstance(v, (list, dict, str)) and not (v.strip() if isinstance(v, str) else v))


def _day(value: Any) -> Optional[datetime]:
    s = str(value or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    try:
        return datetime(int(m[3]), int(m[2]), int(m[1])) if m else datetime.fromisoformat(s[:19]) if s else None
    except ValueError:
        return None


def _week(flat: Dict[str, Any]) -> str:
    d = _day(flat.get("raw_posted_date")) or _day(flat.get("crawled_at"))  # TopCV, TopDev không có ngày đăng
    return "%d-W%02d" % d.isocalendar()[:2] if d else ""


def company_norm(name: Any) -> str:
    return re.sub(r"^(cty|ctcp|cong ty|công ty)\s+", "", normalize_company_name(name if isinstance(name, str) else None))


def dedup_key(flat: Dict[str, Any]) -> Optional[str]:
    title = re.sub(r"\s+", " ", str(flat.get("job_title") or "").lower()).strip(" .,-:;!|")
    company = company_norm(flat.get("company_name"))
    if not title or not company:
        return None
    first = (flat.get("working_locations") or [None])[0] or flat.get("raw_location_text")
    return "|".join([company, title, province.key(first) or "", _week(flat)])


def jd_words(flat: Dict[str, Any]) -> int:
    text = f"{flat.get('raw_description_text') or ''} {flat.get('raw_requirements_text') or ''}"
    return len(re.findall(r"\b[\w\d_.-]+\b", text))


def filled(flat: Dict[str, Any]) -> int:
    return sum(not _empty(v) for k, v in flat.items() if k not in {"job_id_global", "source_platform"})


def combine(rule: str, prob: Optional[float]) -> str:
    if prob is None:
        return rule if rule != "unknown" else "can_kiem"
    jev = "it" if prob >= 0.7 else "non_it" if prob <= 0.3 else None
    if jev is None or (rule != "unknown" and rule != jev):
        return "can_kiem"
    return jev


# ---------------------------------------------------------------- tiện ích báo cáo
def _job_id(item: Item) -> str:
    return str(item["env"]["metadata"].get("job_id") or "")


def _ex(item: Item, field: str, before: Any, after: Any) -> Dict[str, Any]:
    return {"job_id": _job_id(item), "field": field, "before": before, "after": after,
            "url": item["env"]["metadata"].get("source_url")}


def _fill(items: Sequence[Item]) -> Dict[str, float]:
    n = len(items)
    return {f: round(100 * sum(not _empty(i["flat"].get(f)) for i in items) / n, 1) if n else 0.0 for f in KEY_FIELDS}


def load_policy() -> Dict[str, Any]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8")) if POLICY_PATH.exists() else {}


# ---------------------------------------------------------------- C1–C6 trong một nguồn
def clean_source(source: str, jev: JevClient, policy: Dict[str, Any], report: StepReport) -> Tuple[List[Item], List[Item]]:
    """Trả (tin giữ lại sau C6, mọi tin đã phân loại IT trước C4c — dùng để đo độ đúng trên nhãn tay)."""
    raw_dir = DATA_DIR / source / "raw"
    snapshots, batch, _ = read_raw(raw_dir)
    items = [{"rel": r, "env": e, "origin": "snapshot"} for r, e in snapshots] + \
            [{"rel": r, "env": e, "origin": "batch"} for r, e in batch]
    report.data["input"] = {"path": f"data/{source}/raw", "rows": len(items)}

    # C3 trước khi gom theo job_id, vì bản ghi test hoặc thiếu job_id không gom được (báo cáo vẫn ghi đúng thứ tự)
    c3 = [i for i in items if not _job_id(i) or TEST_ID.match(_job_id(i)) or not i["env"]["metadata"].get("source_url")
          or str(i["env"]["metadata"].get("source") or source).lower() != source]
    c3_ids = {id(i) for i in c3}
    items = [i for i in items if id(i) not in c3_ids]

    # C1: snapshot mới nhất theo job_id; tin trùng trong chính file batch cũng tính ở đây
    best: Dict[str, Item] = {}
    c1: List[Tuple[Item, Item]] = []
    for it in (i for i in items if i["origin"] == "snapshot"):
        jid = _job_id(it)
        old = best.get(jid)
        if old is None:
            best[jid] = it
        elif snapshot_order(it["env"]) > snapshot_order(old["env"]):
            c1.append((old, it))
            best[jid] = it
        else:
            c1.append((it, old))
    # C2: tin trong file batch đã có file riêng
    c2: List[Item] = []
    batch_best: Dict[str, Item] = {}
    for it in (i for i in items if i["origin"] == "batch"):
        jid = _job_id(it)
        if jid in best:
            c2.append(it)
        elif jid in batch_best:
            c1.append((it, batch_best[jid]))
        else:
            batch_best[jid] = it
    items = list(best.values()) + list(batch_best.values())
    report.rule("C1", "Giữ snapshot mới nhất của mỗi job_id", "drop", len(c1),
                [_ex(new, "snapshot_file", old["rel"], new["rel"]) for old, new in c1])
    report.rule("C2", "Bỏ tin trong file batch cũ đã có file riêng (PRE-8)", "drop", len(c2),
                [_ex(i, "snapshot_file", i["rel"], "đã có file riêng") for i in c2])
    report.rule("C3", "Bỏ bản ghi test, thiếu job_id/source_url hoặc sai nguồn", "drop", len(c3),
                [_ex(i, "job_id", _job_id(i) or None, None) for i in c3])

    # Làm phẳng chỉ để đọc khóa; không ghi ra
    for it in items:
        it["flat"] = flatten_raw_job_record(it["env"], source)
    fill_in = _fill(items)

    # C4a: phân loại IT ở mọi nguồn, không bỏ
    def jev_state(f):
        return {"title": f.get("job_title"), "skills": (f.get("skills_list") or [])[:15],
                "jd": str(f.get("raw_description_text") or "")[:500]}

    q = (IT_QUESTION["name"], IT_QUESTION["instructions"], IT_QUESTION["true_desc"], IT_QUESTION["false_desc"])
    jev.prefetch(*q, [jev_state(it["flat"]) for it in items])
    status = Counter()
    for it in items:
        f = it["flat"]
        rule = classify(f.get("job_title"), f.get("skills_list"))
        prob = jev.noul(*q, jev_state(f))
        st = combine(rule, prob)
        status[st] += 1
        it["env"]["metadata"]["clean"] = {"snapshot_file": it["rel"], "it_rule": rule, "it_prob": prob,
                                          "it_status": st, "dedup_key": dedup_key(f), "also_on": []}
    non_it = [i for i in items if i["env"]["metadata"]["clean"]["it_status"] == "non_it"]
    report.rule("C4a", "Phân loại IT (luật + JEV), chỉ gắn cờ", "flag", status["non_it"] + status["can_kiem"],
                [_ex(i, "job_title", i["flat"].get("job_title"), "non_it") for i in non_it])
    report.data["extra"]["it_status"] = dict(status)

    classified = list(items)

    # C4c: chỉ bỏ theo chính sách đã duyệt; can_kiem không bao giờ bị bỏ tự động
    drop_status = {s for s in (policy.get(source) or {}).get("drop", []) if s != "can_kiem"}
    c4 = [i for i in items if i["env"]["metadata"]["clean"]["it_status"] in drop_status]
    c4_ids = {id(i) for i in c4}
    items = [i for i in items if id(i) not in c4_ids]
    report.rule("C4c", "Bỏ tin ngoài IT theo it_policy.json", "drop", len(c4),
                [_ex(i, "job_title", i["flat"].get("job_title"), None) for i in c4])
    report.data["extra"]["it_policy"] = policy.get(source) or "chưa duyệt, không bỏ tin nào"

    # C5: JD rỗng / quá ngắn
    c5 = [i for i in items if jd_words(i["flat"]) < MIN_JD_WORDS]
    c5_ids = {id(i) for i in c5}
    items = [i for i in items if id(i) not in c5_ids]
    report.rule("C5", f"Bỏ JD dưới {MIN_JD_WORDS} từ", "drop", len(c5),
                [_ex(i, "raw_description_text", (i["flat"].get("raw_description_text") or "")[:120] or None, None)
                 for i in c5])

    # C6: trùng trong cùng nguồn; giữ bản cào mới nhất, bằng nhau thì bản nhiều trường hơn
    groups: Dict[str, List[Item]] = defaultdict(list)
    for it in items:
        k = it["env"]["metadata"]["clean"]["dedup_key"]
        if k:
            groups[k].append(it)
    c6: List[Tuple[Item, Item]] = []
    for g in groups.values():
        if len(g) > 1:
            g.sort(key=lambda i: (str(i["flat"].get("crawled_at") or ""), filled(i["flat"])), reverse=True)
            c6 += [(d, g[0]) for d in g[1:]]
    c6_ids = {id(d) for d, _ in c6}
    items = [i for i in items if id(i) not in c6_ids]
    report.rule("C6", "Bỏ tin trùng trong cùng nguồn (công ty + tiêu đề + tỉnh + tuần)", "drop", len(c6),
                [_ex(d, "dedup_key", d["env"]["metadata"]["clean"]["dedup_key"], f"giữ {_job_id(k)}") for d, k in c6])
    report.data["fields"] = [{"field": f, "fill_pct_in": fill_in[f]} for f in KEY_FIELDS]
    return items, classified


# ---------------------------------------------------------------- C7 chéo nguồn
def cross_source_dedup(kept: Dict[str, List[Item]], reports: Dict[str, StepReport]) -> Counter:
    """Trả số tin trùng theo cặp nguồn (giữ → bỏ) cho Monitoring."""
    order = {s: n for n, s in enumerate(SOURCES)}
    groups: Dict[str, List[Tuple[str, Item]]] = defaultdict(list)
    for src, items in kept.items():
        for it in items:
            k = it["env"]["metadata"]["clean"]["dedup_key"]
            if k:
                groups[k].append((src, it))
    dropped: Dict[str, List[Tuple[Item, str, Item]]] = defaultdict(list)
    pairs: Counter = Counter()
    for g in groups.values():
        if len({s for s, _ in g}) < 2:
            continue
        g.sort(key=lambda x: (-filled(x[1]["flat"]), order.get(x[0], 99)))
        win_src, win = g[0]
        for src, it in g[1:]:
            win["env"]["metadata"]["clean"]["also_on"].append(f"{src}:{_job_id(it)}")
            dropped[src].append((it, win_src, win))
            pairs[f"{win_src} → {src}"] += 1
    for src, items in kept.items():
        gone = {id(it) for it, _, _ in dropped[src]}
        kept[src] = [i for i in items if id(i) not in gone]
        reports[src].rule("C7", "Bỏ tin trùng khác nguồn, ghi nguồn còn lại vào also_on", "drop", len(dropped[src]),
                          [_ex(it, "dedup_key", it["env"]["metadata"]["clean"]["dedup_key"],
                               f"giữ {ws}:{_job_id(w)}") for it, ws, w in dropped[src]])
    return pairs


# ---------------------------------------------------------------- C4b: mẫu gán nhãn tay
def _has_labels(path) -> bool:
    if not path.exists():
        return False
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return any((r.get("nhan_tay") or "").strip() for r in csv.DictReader(fh))


def review_sample(source: str, items: List[Item], report: StepReport) -> None:
    """Xuất mẫu; file đã có nhãn tay thì giữ nguyên, chỉ đọc nhãn để đo độ đúng. Chưa có nhãn nào thì xuất lại."""
    path = REVIEW_DIR / f"it_{source}.csv"
    by_id = {_job_id(i): i["env"]["metadata"]["clean"] for i in items}
    if not _has_labels(path):
        rng = random.Random(REVIEW_SEED)
        pick = []
        for st, n in (("non_it", REVIEW_NON_IT), ("can_kiem", REVIEW_CAN_KIEM)):
            pool = sorted((i for i in items if i["env"]["metadata"]["clean"]["it_status"] == st), key=_job_id)
            pick += rng.sample(pool, min(n, len(pool)))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["job_id", "source_url", "job_title", "skills", "it_rule", "it_prob", "it_status", "nhan_tay"])
            for i in pick:
                c = i["env"]["metadata"]["clean"]
                w.writerow([_job_id(i), i["env"]["metadata"].get("source_url"), i["flat"].get("job_title"),
                            ", ".join(map(str, (i["flat"].get("skills_list") or [])[:10])), c["it_rule"],
                            c["it_prob"], c["it_status"], ""])
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    labeled = [(r["nhan_tay"].strip(), by_id[r["job_id"]]) for r in rows
               if (r.get("nhan_tay") or "").strip() in {"it", "non_it"} and r["job_id"] in by_id]
    decided = [(lab, c) for lab, c in labeled if c["it_rule"] in {"it", "non_it"}]
    non_it = [(lab, c) for lab, c in labeled if c["it_status"] == "non_it"]  # đúng nhóm mà chính sách sẽ bỏ
    jev = [(lab, c) for lab, c in labeled if c["it_prob"] is not None]
    report.data["extra"]["review"] = {
        "file": f"data/preprocessing/review/{path.name}", "rows": len(rows), "labeled": len(labeled),
        "labeled_non_it": sum(lab == "non_it" for lab, _ in labeled),
        "rule_decided": len(decided), "rule_correct": sum(lab == c["it_rule"] for lab, c in decided),
        "status_non_it": len(non_it), "status_non_it_correct": sum(lab == "non_it" for lab, _ in non_it),
        "jev_labeled": len(jev), "jev_correct": sum((c["it_prob"] >= 0.5) == (lab == "it") for lab, c in jev)}


# ---------------------------------------------------------------- chạy
def run(sources: Sequence[str] = SOURCES, dry_run: bool = True, use_api: bool = False) -> Dict[str, StepReport]:
    policy = load_policy()
    reports: Dict[str, StepReport] = {}
    kept: Dict[str, List[Item]] = {}
    classified: Dict[str, List[Item]] = {}
    spent = 0.0
    for src in sources:
        reports[src] = StepReport(STEP, src, dry_run)
        jev = JevClient(use_api, dry_run, max_cost_usd=max(JEV_BUDGET_USD - spent, 0))
        kept[src], classified[src] = clean_source(src, jev, policy, reports[src])
        spent += jev.cache.cost_usd
        reports[src].data["api"] = jev.report()
    pairs = cross_source_dedup(kept, reports)
    for src in sources:
        r = reports[src]
        r.data["output"] = {"path": f"data/preprocessing/{STEP}/{src}.jsonl", "rows": len(kept[src])}
        out_fill = _fill(kept[src])
        for f in r.data["fields"]:
            f["fill_pct_out"] = out_fill[f["field"]]
        review_sample(src, classified[src], r)
        r.check_conserved()  # một nguồn sai thì dừng cả bước, chưa nguồn nào được ghi
    for src in sources:
        if not dry_run:
            out_path = OUT_DIR / f"{src}.jsonl"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("w", encoding="utf-8") as fh:
                for it in kept[src]:
                    fh.write(json.dumps(it["env"], ensure_ascii=False) + "\n")
        reports[src].write()
    total = merge_reports(STEP, list(reports.values()), dry_run)
    total.data["extra"]["it_status"] = {s: reports[s].data["extra"]["it_status"] for s in sources}
    total.data["extra"]["review"] = {s: reports[s].data["extra"]["review"] for s in sources}
    total.data["extra"]["cross_source_pairs"] = dict(pairs.most_common())
    total.data["extra"]["it_policy"] = {s: reports[s].data["extra"]["it_policy"] for s in sources}
    total.data["api"] = {"used": any(r.data["api"]["used"] for r in reports.values()),
                         "calls": sum(r.data["api"]["calls"] for r in reports.values()),
                         "cache_hits": sum(r.data["api"]["cache_hits"] for r in reports.values()),
                         "cost_usd": round(spent, 6),
                         "would_call": sum(r.data["api"].get("would_call", 0) for r in reports.values()),
                         "estimated_cost_usd": round(sum(r.data["api"].get("estimated_cost_usd", 0)
                                                         for r in reports.values()), 4)}
    total.write()
    return reports
