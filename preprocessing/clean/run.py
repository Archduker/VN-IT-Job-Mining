# -*- coding: utf-8 -*-
"""Bước 01 Clean (docs/spec/preprocessing/spec/P1_clean.md): khử trùng, bỏ rác, phân loại IT bằng luật 2 tầng ở cả 8 nguồn.

Không bỏ tin ngoài IT khi chưa có preprocessing/clean/it_policy.json do người dùng duyệt (C4c).
Output giữ nguyên raw_payload, chỉ thêm metadata.clean.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from preprocessing.clean.label_review import validation_metrics
from preprocessing.common import REPO_ROOT, SOURCES, province, step_report
from preprocessing.common.it_filter import classify, classify_unknown
from preprocessing.common.raw_reader import read_raw, snapshot_order
from preprocessing.common.step_report import StepReport, merge_reports
from preprocessing.integration.json_flattener import flatten_raw_job_record
from preprocessing.normalization.cross_deduplicator import normalize_company_name

STEP = "01_clean"
DATA_DIR = REPO_ROOT / "data"
OUT_DIR = DATA_DIR / "preprocessing" / STEP
REVIEW_DIR = DATA_DIR / "preprocessing" / "review"
POLICY_PATH = REPO_ROOT / "preprocessing" / "clean" / "it_policy.json"
MIN_JD_WORDS = 30  # chính sách 1.B cũ (transformation/text_metrics.filter_valid_clean_records)
TEST_ID = re.compile(r"^job-[a-z]+-\d+$")
REVIEW_NON_IT, REVIEW_LEVEL2, REVIEW_SEED = 50, 30, 42
# Bổ sung độ phủ tầng 1 dự đoán IT; mẫu cũ chỉ đại diện tầng 2 và non_it tầng 1.
REVIEW_LEVEL1_IT = 100
KEY_FIELDS = ("job_title", "company_name", "raw_location_text", "raw_posted_date", "raw_description_text", "skills_list")

Item = dict[str, Any]  # {"rel", "env", "origin", "flat"}


# ---------------------------------------------------------------- khóa
def _empty(v: Any) -> bool:
    return v is None or (isinstance(v, list | dict | str) and not (v.strip() if isinstance(v, str) else v))


def _day(value: Any) -> datetime | None:
    s = str(value or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    try:
        return datetime(int(m[3]), int(m[2]), int(m[1])) if m else datetime.fromisoformat(s[:19]) if s else None
    except ValueError:
        return None


def _week(flat: dict[str, Any]) -> str:
    d = _day(flat.get("raw_posted_date")) or _day(flat.get("crawled_at"))  # TopCV, TopDev không có ngày đăng
    if not d:
        return ""
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def company_norm(name: Any) -> str:
    return re.sub(r"^(cty|ctcp|cong ty|công ty)\s+", "", normalize_company_name(name if isinstance(name, str) else None))


def dedup_key(flat: dict[str, Any]) -> str | None:
    title = re.sub(r"\s+", " ", str(flat.get("job_title") or "").lower()).strip(" .,-:;!|")
    company = company_norm(flat.get("company_name"))
    if not title or not company:
        return None
    first = (flat.get("working_locations") or [None])[0] or flat.get("raw_location_text")
    return "|".join([company, title, province.key(first) or "", _week(flat)])


def jd_words(flat: dict[str, Any]) -> int:
    text = f"{flat.get('raw_description_text') or ''} {flat.get('raw_requirements_text') or ''}"
    return len(re.findall(r"\b[\w\d_.-]+\b", text))


def filled(flat: dict[str, Any]) -> int:
    return sum(not _empty(v) for k, v in flat.items() if k not in {"job_id_global", "source_platform"})


# ---------------------------------------------------------------- tiện ích báo cáo
def _job_id(item: Item) -> str:
    return str(item["env"]["metadata"].get("job_id") or "")


def _ex(item: Item, field: str, before: Any, after: Any) -> dict[str, Any]:
    return {"job_id": _job_id(item), "field": field, "before": before, "after": after,
            "url": item["env"]["metadata"].get("source_url")}


def _fill(items: Sequence[Item]) -> dict[str, float]:
    n = len(items)
    return {f: round(100 * sum(not _empty(i["flat"].get(f)) for i in items) / n, 1) if n else 0.0 for f in KEY_FIELDS}


def load_policy() -> dict[str, Any]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8")) if POLICY_PATH.exists() else {}


# ---------------------------------------------------------------- C1–C6 trong một nguồn
def clean_source(source: str, policy: dict[str, Any], report: StepReport) -> tuple[list[Item], list[Item]]:
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
    best: dict[str, Item] = {}
    c1: list[tuple[Item, Item]] = []
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
    c2: list[Item] = []
    batch_best: dict[str, Item] = {}
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

    # C4a: luật 2 tầng ở mọi nguồn, chỉ gắn nhãn; bỏ hay không do C4c và it_policy.json
    status, levels = Counter(), Counter()
    for it in items:
        f = it["flat"]
        rule = classify(f.get("job_title"), f.get("skills_list"))
        level = 1
        if rule == "unknown":
            level = 2
            st = classify_unknown(f.get("job_title"), f.get("skills_list"),
                                  f"{f.get('raw_description_text') or ''} {f.get('raw_requirements_text') or ''}", f.get("company_name"))
        else:
            st = rule
        status[st] += 1
        levels[f"tang_{level}_{st}"] += 1
        it["env"]["metadata"]["clean"] = {"snapshot_file": it["rel"], "it_rule": rule, "it_rule_level": level,
                                          "it_status": st, "dedup_key": dedup_key(f), "also_on": []}
    non_it = [i for i in items if i["env"]["metadata"]["clean"]["it_status"] == "non_it"]
    report.rule("C4a", "Phân loại IT bằng luật 2 tầng (từ khóa tiêu đề, rồi nhóm nghề + kỹ năng JD), chỉ gắn nhãn",
                "flag", status["non_it"], [_ex(i, "job_title", i["flat"].get("job_title"), "non_it") for i in non_it])
    report.data["extra"]["it_levels"] = dict(levels)
    report.data["extra"]["it_status"] = dict(status)

    classified = list(items)

    # C4c: chỉ bỏ theo chính sách đã duyệt
    drop_status = set((policy.get(source) or {}).get("drop", []))
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
    groups: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        k = it["env"]["metadata"]["clean"]["dedup_key"]
        if k:
            groups[k].append(it)
    c6: list[tuple[Item, Item]] = []
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
def cross_source_dedup(kept: dict[str, list[Item]], reports: dict[str, StepReport]) -> Counter:
    """Trả số tin trùng theo cặp nguồn (giữ → bỏ) cho Monitoring."""
    order = {s: n for n, s in enumerate(SOURCES)}
    groups: dict[str, list[tuple[str, Item]]] = defaultdict(list)
    for src, items in kept.items():
        for it in items:
            k = it["env"]["metadata"]["clean"]["dedup_key"]
            if k:
                groups[k].append((src, it))
    dropped: dict[str, list[tuple[Item, str, Item]]] = defaultdict(list)
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


def level1_it_count(items: Sequence[Item]) -> int:
    """Số tin tầng 1 mà bộ lọc dự đoán `it` - pool của nhóm mẫu cần thêm (Q1/C4b)."""
    return sum(1 for i in items
               if (c := i["env"]["metadata"]["clean"])["it_rule_level"] == 1 and c["it_status"] == "it")


def plan_level1_it(pool_sizes: dict[str, int], total: int = REVIEW_LEVEL1_IT) -> dict[str, int]:
    """Chia `total` tin tầng 1 IT cho các sàn theo tỷ lệ số tin tầng 1 IT của từng sàn.

    Dùng phương pháp số dư lớn nhất, mỗi sàn có tin đều phải có mặt trong mẫu (tối thiểu 1)
    và không bao giờ lấy quá số tin sẵn có; tổng không vượt quá số tin đang có.
    """
    if not isinstance(total, int) or total < 0:
        raise ValueError("total phải là số nguyên >= 0")
    sizes = {s: max(0, int(n)) for s, n in pool_sizes.items()}
    quota = {s: 0 for s in sizes}
    avail = {s: n for s, n in sizes.items() if n > 0}
    left = min(total, sum(avail.values()))
    for s in sorted(avail, key=lambda k: (-avail[k], k)):  # bảo đảm mọi sàn có đại diện
        if left <= 0:
            break
        quota[s] += 1
        left -= 1
    while left > 0:
        free = {s: avail[s] - quota[s] for s in avail if avail[s] > quota[s]}
        w = sum(free.values())
        if not w:
            break
        raw = {s: left * n / w for s, n in free.items()}
        base = {s: int(raw[s]) for s in free}
        rest = left - sum(base.values())
        for s in sorted(free, key=lambda k: (-(raw[k] - base[k]), k))[:rest]:
            base[s] += 1
        for s, n in base.items():
            take = min(n, free[s])
            quota[s] += take
            left -= take
    return quota


def review_sample(source: str, items: list[Item], report: StepReport,
                  level1_it: int | None = None) -> None:
    """Xuất mẫu; file đã có nhãn tay thì giữ nguyên, chỉ đọc nhãn để đo độ đúng. Chưa có nhãn nào thì xuất lại.

    Ba tầng mẫu: tin `non_it` tầng 1 (người duyệt kiểm nhóm bị bỏ), mọi tin tầng 2,
    và tin tầng 1 dự đoán `it` (anh gán để đo Precision IT >= 95%).
    `level1_it=None` lấy suất chia đều `REVIEW_LEVEL1_IT / 8 sàn` (khi chạy lẻ một sàn).
    """
    path = REVIEW_DIR / f"it_{source}.csv"
    by_id = {_job_id(i): i["env"]["metadata"]["clean"] for i in items}
    if level1_it is None:
        level1_it = max(1, REVIEW_LEVEL1_IT // len(SOURCES))
    strata = [(1, "non_it", REVIEW_NON_IT), (2, None, REVIEW_LEVEL2), (1, "it", level1_it)]
    if not _has_labels(path):
        rng = random.Random(REVIEW_SEED)
        pick, seen = [], set()
        for level, want, n in strata:
            pool = sorted((i for i in items if i["env"]["metadata"]["clean"]["it_rule_level"] == level
                           and (want is None or i["env"]["metadata"]["clean"]["it_status"] == want)),
                          key=_job_id)
            got = rng.sample(pool, min(n, len(pool)))
            pick += [i for i in got if id(i) not in seen and not seen.add(id(i))]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["job_id", "source_url", "job_title", "skills", "it_rule", "it_rule_level", "it_status", "nhan_tay"])
            for i in pick:  # giữ thứ tự từng tầng: nhóm bị bỏ trước, để người duyệt đọc theo mạch
                c = i["env"]["metadata"]["clean"]
                w.writerow([_job_id(i), i["env"]["metadata"].get("source_url"), i["flat"].get("job_title"),
                            ", ".join(map(str, (i["flat"].get("skills_list") or [])[:10])), c["it_rule"],
                            c["it_rule_level"], c["it_status"], ""])
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    labeled = [(r["nhan_tay"].strip(), by_id[r["job_id"]]) for r in rows
               if (r.get("nhan_tay") or "").strip() in {"it", "non_it"} and r["job_id"] in by_id]
    decided = [(lab, c) for lab, c in labeled if c["it_rule"] in {"it", "non_it"}]
    non_it = [(lab, c) for lab, c in labeled if c["it_status"] == "non_it"]  # đúng nhóm mà chính sách sẽ bỏ
    level2 = [(lab, c) for lab, c in labeled if c["it_rule_level"] == 2]
    level1_kept = [(lab, c) for lab, c in labeled if c["it_rule_level"] == 1 and c["it_status"] == "it"]
    report.data["extra"]["review"] = {
        "file": f"data/preprocessing/review/{path.name}", "rows": len(rows), "labeled": len(labeled),
        "sample_strata": dict(Counter(f"tang_{r['it_rule_level']}_{r['it_status']}" for r in rows)),
        "labeled_non_it": sum(lab == "non_it" for lab, _ in labeled),
        "rule_decided": len(decided), "rule_correct": sum(lab == c["it_rule"] for lab, c in decided),
        "status_non_it": len(non_it), "status_non_it_correct": sum(lab == "non_it" for lab, _ in non_it),
        "level2_labeled": len(level2), "level2_correct": sum(lab == c["it_status"] for lab, c in level2),
        "level1_it_labeled": len(level1_kept),
        "level1_it_correct": sum(lab == "it" for lab, _ in level1_kept),
        "validation": validation_metrics([
            {"nhan_tay": lab, "it_status": c["it_status"]} for lab, c in labeled])}


# ---------------------------------------------------------------- chạy
def run(sources: Sequence[str] = SOURCES, dry_run: bool = True) -> dict[str, StepReport]:
    full_run = len(sources) == len(SOURCES) and set(sources) == set(SOURCES)
    if len(set(sources)) != len(sources):
        raise ValueError("sources không được lặp")
    # API run() giữ hợp đồng với orchestrator (có thể cung cấp tập nguồn riêng).
    # CLI chặn applied thiếu sàn; mọi phép thử dry-run lẻ được cách ly báo cáo.
    report_root = step_report.REPORTS_ROOT / "_partial" if dry_run and not full_run else None
    policy = load_policy()
    reports: dict[str, StepReport] = {}
    kept: dict[str, list[Item]] = {}
    classified: dict[str, list[Item]] = {}
    for src in sources:
        reports[src] = StepReport(STEP, src, dry_run)
        kept[src], classified[src] = clean_source(src, policy, reports[src])
    pairs = cross_source_dedup(kept, reports)
    quota = plan_level1_it({s: level1_it_count(classified[s]) for s in sources})
    for src in sources:
        r = reports[src]
        r.data["output"] = {"path": f"data/preprocessing/{STEP}/{src}.jsonl", "rows": len(kept[src])}
        out_fill = _fill(kept[src])
        for f in r.data["fields"]:
            f["fill_pct_out"] = out_fill[f["field"]]
        review_sample(src, classified[src], r, level1_it=quota[src])
        if not full_run:  # ghi ngay vào báo cáo từng sàn để CLI và trang Monitoring cùng thấy cảnh báo
            r.note(f"chạy lẻ {len(sources)}/{len(SOURCES)} sàn - C7 so trùng khác sàn chưa đủ dữ liệu"
                   "; muốn số đúng toàn dự án: --source all")
        r.check_conserved()  # một nguồn sai thì dừng cả bước, chưa nguồn nào được ghi
    for src in sources:
        if not dry_run:
            out_path = OUT_DIR / f"{src}.jsonl"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("w", encoding="utf-8") as fh:
                for it in kept[src]:
                    fh.write(json.dumps(it["env"], ensure_ascii=False) + "\n")
        reports[src].write(root=report_root)
    total = merge_reports(STEP, list(reports.values()), dry_run)
    total.data["extra"]["it_status"] = {s: reports[s].data["extra"]["it_status"] for s in sources}
    total.data["extra"]["review"] = {s: reports[s].data["extra"]["review"] for s in sources}
    total.data["extra"]["cross_source_pairs"] = dict(pairs.most_common())
    total.data["extra"]["it_policy"] = {s: reports[s].data["extra"]["it_policy"] for s in sources}
    total.data["extra"]["it_levels"] = {s: reports[s].data["extra"]["it_levels"] for s in sources}
    # `_all.json` là số Monitoring đọc: chạy lẻ một sàn mà ghi đè thì trang sẽ hiện số thiếu.
    total.data["extra"]["partial_run"] = not full_run
    if total.data["extra"]["partial_run"]:
        total.note(f"_all chỉ tổng hợp {len(sources)}/{len(SOURCES)} sàn "
                   f"({', '.join(sources)}) - muốn số toàn dự án phải chạy --source all")
    total.write(root=report_root)
    return reports


def resample_review(sources: Sequence[str] = SOURCES,
                    level1_it: int | None = None) -> dict[str, dict[str, Any]]:
    """Chỉ dựng lại mẫu gán nhãn tay (C4b), không ghi dữ liệu 01_clean, không ghi báo cáo chung.

    Dùng khi cần đổi thiết kế mẫu (thêm tầng dự đoán IT của tầng 1) nhưng chưa được
    phép xuất bản snapshot mới. Sàn đã có nhãn tay thì giữ nguyên file, không xoá nhãn.
    `level1_it` nới tổng số dòng tầng 1 dự đoán IT khi mẫu 100 dòng không đủ hẹp
    khoảng tin cậy (xem docs/tasks/02 §5.8.2).
    """
    if len(set(sources)) != len(sources):
        raise ValueError("sources không được lặp")
    policy = load_policy()
    classified: dict[str, list[Item]] = {}
    for src in sources:
        _, classified[src] = clean_source(src, policy, StepReport(STEP, src, True))
    quota = plan_level1_it({s: level1_it_count(classified[s]) for s in sources},
                           total=REVIEW_LEVEL1_IT if level1_it is None else level1_it)
    out: dict[str, dict[str, Any]] = {}
    for src in sources:
        frozen = _has_labels(REVIEW_DIR / f"it_{src}.csv")
        rep = StepReport(STEP, src, True)
        review_sample(src, classified[src], rep, level1_it=quota[src])
        rv = rep.data["extra"]["review"]
        out[src] = {"quota_tang1_it": quota[src], "rows": rv["rows"], "labeled": rv["labeled"],
                    "strata": rv["sample_strata"], "giu_nguyen_vi_da_co_nhan": frozen}
    return out


def main(argv: list[str] | None = None) -> int:
    """CLI chạy riêng bước 01 để kiểm tra nhanh (orchestrator chung của dự án vẫn là `scripts/`)."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default="all", choices=[*SOURCES, "all"])
    parser.add_argument("--dry-run", action="store_true", help="chỉ đo và ghi báo cáo, không ghi dữ liệu")
    parser.add_argument("--resample-review", action="store_true",
                        help="chỉ dựng lại mẫu gán nhãn tay C4b (không ghi dữ liệu, không ghi báo cáo)")
    parser.add_argument("--level1-it", type=int, default=None, metavar="N",
                        help=f"tổng số dòng tầng 1 dự đoán IT trong mẫu (mặc định {REVIEW_LEVEL1_IT}),"
                             " dùng với --resample-review")
    args = parser.parse_args(argv)
    sources = list(SOURCES) if args.source == "all" else [args.source]
    if args.level1_it is not None:
        if not args.resample_review:
            parser.error("--level1-it chỉ dùng với --resample-review")
        if args.level1_it < 0:
            parser.error("--level1-it phải >= 0")
    if args.resample_review:
        for src, info in resample_review(sources, level1_it=args.level1_it).items():
            print(f"{STEP} {src}: mẫu {info['rows']} dòng, đã nhãn {info['labeled']}"
                  f" | tầng 1 IT cấp {info['quota_tang1_it']}"
                  f" | {info['strata']}"
                  f"{' | GIỮ NGUYÊN (đã có nhãn tay)' if info['giu_nguyen_vi_da_co_nhan'] else ''}")
        return 0
    if len(sources) != len(SOURCES) and not args.dry_run:
        parser.error("chạy lẻ một sàn chỉ hợp lệ với --dry-run: luật C7 so trùng khác sàn cần đủ 8 sàn,"
                     " chạy applied một sàn sẽ ghi đè output 01_clean của sàn đó bằng kết quả thiếu"
                     " (muốn làm lại toàn bộ: --source all)")
    reports = run(sources, dry_run=args.dry_run)
    for src, r in reports.items():
        d = r.data
        print(f"{STEP} {src}: input {d['input']['rows']} -> output {d['output']['rows']} ({d['mode']})"
              f" -> reports/preprocessing/{'' if args.source == 'all' else '_partial/'}{STEP}/{src}.json")
        for note in d["checks"]["notes"]:
            print(f"    ⚠ {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
