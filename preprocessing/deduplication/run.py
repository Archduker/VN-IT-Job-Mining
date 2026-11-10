"""Bước 01b Deduplication 2 lớp (docs/spec/05_preprocessing_spec.md mục 3, docs/tasks/02).

Đầu vào: `data/preprocessing/01_clean/<nguồn>.jsonl` (đầu ra duy nhất của 01 Clean, theo P0 mục 2).
Đầu ra:
  - `data/preprocessing/01b_deduplication/<nguồn>.jsonl`  : bản ghi giữ lại, thêm `metadata.dedup`
  - `data/preprocessing/01b_deduplication/golden_master_jobs.parquet` (+ .jsonl): bảng Golden Master
  - `data/preprocessing/01b_deduplication/duplicates_audit.csv`  : mọi cặp trùng và cặp sát ngưỡng,
    kèm một dòng truy vết riêng cho từng bản bị loại nối gián tiếp (người duyệt kiểm được 100%)
  - `reports/preprocessing/01b_deduplication/<nguồn>.json` + `_all.json`

Luật (tiền tố D, theo quy ước mã luật của P0 mục 4; PH4 10/11/2026, 3 tầng):
  D0 Tầng 1: trùng (nguồn, job_id) (drop)        - lưới an toàn, 01 Clean đã khử
  D1 Kiểm toán chuỗi version CDC (flag)          - bao nhiêu lần cào lại không đổi nội dung thật
  D2 Tầng 2 cùng sàn: sha1(text_fold) + cùng công ty (drop)
  D3 Gán Blocking Key (flag)
  D4 Tầng 2 liên sàn: sha1(text_fold) + cùng công ty (drop)
  D5 Tầng 3: MinHash -> Jaccard chính xác shingle 5 từ >= 0.85 và cùng company_slug (drop),
     cả cùng sàn lẫn khác sàn
  D6 Hợp nhất Golden Record (flag)
  D7 Cặp J >= 0.70 không bị loại (khác công ty hoặc dưới 0.85) chỉ vào audit (flag)
Tham số: preprocessing/dictionaries/dedup_policy.json.

Chạy:  python -m preprocessing.deduplication.run --dry-run
       python -m preprocessing.deduplication.run --source itviec
"""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from typing import Any

from preprocessing.clean.run import filled
from preprocessing.common import REPO_ROOT, SOURCES, step_report
from preprocessing.common.step_report import StepReport, merge_reports
from preprocessing.deduplication import inter_source as inter
from preprocessing.deduplication import minhash as mh
from preprocessing.deduplication.blocking import blocking_key, company_slug
from preprocessing.deduplication.intra_source import apply_d2, cdc_chain_audit, pick_winner
from preprocessing.deduplication.text_norm import canonical_hash, fold
from preprocessing.integration.json_flattener import flatten_raw_job_record

STEP = "01b_deduplication"
DATA_DIR = REPO_ROOT / "data" / "preprocessing"
IN_DIR = DATA_DIR / "01_clean"
OUT_DIR = DATA_DIR / STEP
REJECTED_DIR = DATA_DIR / "rejected" / STEP
RAW_ROOT = REPO_ROOT / "data"  # test thay bằng tmp_path
Item = dict[str, Any]

RULE_TEXT = {
    "D1": "Kiểm toán chuỗi version CDC (cào lại có đổi nội dung thật không)",
    "D0": "Tầng 1: trùng (nguồn, job_id)",
    "D2": "Tầng 2 cùng sàn: sha1(text_fold) trùng và cùng company_slug",
    "D3": "Gán Blocking Key = Slug(Company)_LocationCode_TitleGroup",
    "D4": "Tầng 2 liên sàn: sha1(text_fold) trùng và cùng company_slug",
    "D5": "Tầng 3: Jaccard shingle 5 từ >= ngưỡng và cùng company_slug (cùng sàn và khác sàn)",
    "D6": "Hợp nhất Golden Record (bản giữ có merged_from)",
    "D7": "Cặp gần trùng không bị loại (khác công ty hoặc dưới ngưỡng), chỉ vào audit",
}


# ---------------------------------------------------------------- đọc
def load_items(source: str) -> list[Item]:
    path = IN_DIR / f"{source}.jsonl"
    if not path.is_file():
        raise FileNotFoundError(
            f"thieu {path}: chay buoc 01 Clean truoc "
            "(python -m preprocessing.clean.run --source all)")
    items: list[Item] = []
    for line in path.open(encoding="utf-8"):
        if not line.strip():
            continue
        env = json.loads(line)
        flat = flatten_raw_job_record(env, source)
        meta = env["metadata"]
        items.append(enrich({
            "src": source, "jid": str(meta.get("job_id") or ""), "url": str(meta.get("source_url") or ""),
            "env": env, "flat": flat, "chash": canonical_hash(flat),
            "bkey": blocking_key(flat), "seen_at": str(meta.get("scraped_at") or ""),
            "ver": int(meta.get("version") or 1), "drop": None, "master": None,
            "reposts": [], "merged": [],
        }))
    return items


def enrich(it: Item) -> Item:
    """Thêm khóa PH4 từ it["flat"]: fhash = sha1(text_fold), slug công ty, fkey (tầng 2), shingles, title_key."""
    text = mh.fold_text(it["flat"])
    it["fhash"] = mh.sha1_fold(text) if text else ""
    it["slug"] = company_slug(it["flat"].get("company_name"))
    it["fkey"] = f"{it['fhash']}|{it['slug']}" if it["fhash"] and it["slug"] else ""
    it["sh"] = mh.shingles(text)
    it["tkey"] = re.sub(r"[^a-z0-9]", "", fold(str(it["flat"].get("job_title") or "")))
    return it


def pick_cross_winner(group: Sequence[Item]) -> Item:
    """Bản giữ của cụm liên sàn: sàn uy tín nhất, đến bản đầy đủ trường, rồi bản cào MỚI NHẤT.

    Ưu tiên bản mới nhất cùng chiều với tầng nội sàn (D2) và đúng ý SPEC-05 mục 3.1
    ("giữ version mới nhất"): bản cũ có thể đã hết hạn nộp hoặc đổi mô tả. Muốn vậy phải xếp
    thời gian giảm dần TRƯỚC rồi mới `min` theo (uy tín, độ đầy đủ) - `min`/`sorted` của Python
    ổn định nên các bản ngang cấp giữ nguyên thứ tự mới-cũ, job_id nhỏ nhất thắng khi bằng hết.
    """
    by_time = sorted(sorted(group, key=lambda it: it["jid"]),
                     key=lambda it: str(it["seen_at"]), reverse=True)
    return min(by_time, key=lambda it: (inter.authority(it["src"]), -filled(it["flat"])))


def artifact_suffix(full_run: bool) -> str:
    """Chạy lẻ một sàn thì file toàn dự án phải mang hậu tố `.partial`.

    Nếu không, người duyệt chỉ cần chạy thử một sàn là `golden_master_jobs.*` và
    `duplicates_audit.csv` bị thu lại bằng đúng sàn đó mà vẫn mang tên toàn dự án.
    """
    return "" if full_run else ".partial"


def pair_key(a: Item, b: Item) -> tuple[int, int]:
    """Khóa vô hướng của một cặp bản ghi, dùng chung cho `scores` và truy vết gián tiếp."""
    return (id(a), id(b)) if id(a) < id(b) else (id(b), id(a))


def band_counts(scores: dict[tuple[int, int], float]) -> dict[str, int]:
    pol = mh.policy()
    thr, low = pol["threshold"], pol["review_band"][0]
    return {f"[{thr},1]": sum(v >= thr for v in scores.values()),
            f"[0.80,0.90)": sum(0.80 <= v < 0.90 for v in scores.values()),
            f"[{low},{thr})": sum(low <= v < thr for v in scores.values())}


def dup_ref(d: Item) -> str:
    kept = d["drop"].get("kept_ref")
    return f"{kept['src'] if kept else d['src']}:{d['drop']['kept_job_id']}"


# ---------------------------------------------------------------- chay
def run(sources: Sequence[str] = SOURCES, dry_run: bool = True) -> dict[str, StepReport]:
    full_run = len(sources) == len(SOURCES) and set(sources) == set(SOURCES)
    if len(set(sources)) != len(sources):
        raise ValueError("sources không được lặp")
    if not full_run and not dry_run:
        raise ValueError("chạy thiếu sàn chỉ hợp lệ với dry_run=True")
    report_root = None if full_run else step_report.REPORTS_ROOT / "_partial"
    suffix = artifact_suffix(full_run)
    pol = mh.policy()
    thr = pol["threshold"]
    prev_path = step_report.REPORTS_ROOT / STEP / "_all.json"
    prev = json.loads(prev_path.read_text(encoding="utf-8")) if prev_path.is_file() else None
    reports = {src: StepReport(STEP, src, dry_run) for src in sources}
    items: list[Item] = []
    for src in sources:
        part = load_items(src)
        items.extend(part)
        r = reports[src]
        r.set_io(IN_DIR / f"{src}.jsonl", len(part), OUT_DIR / f"{src}.jsonl", len(part))
        r.data["extra"]["cdc"] = cdc_chain_audit(src, RAW_ROOT / src / "raw")
        r.data["extra"]["blocking_blocks"] = len({i["bkey"] for i in part})
        r.rule("D1", RULE_TEXT["D1"], "flag", r.data["extra"]["cdc"]["hops"], reason="chỉ đo, không bỏ dòng")

    # D0: tầng 1, trùng (nguồn, job_id)
    dropped: list[Item] = []
    by_id: dict[tuple[str, str], list[Item]] = {}
    for it in items:
        by_id.setdefault((it["src"], it["jid"]), []).append(it)
    for g in by_id.values():
        if len(g) > 1:
            win = pick_winner(g)
            for it in g:
                if it is not win:
                    it["drop"] = {"rule": "D0", "kept_job_id": win["jid"], "kept_url": win["url"],
                                  "jaccard": 1.0, "kept_ref": win}
                    dropped.append(it)
    gone = {id(d) for d in dropped}
    live = [i for i in items if id(i) not in gone]

    # D2: tầng 2 cùng sàn (sha1 text_fold + cùng công ty)
    for src in sources:
        dropped += apply_d2([i for i in live if i["src"] == src], reports[src].data["extra"])

    # D3: blocking key cho mọi bản ghi còn sống
    gone = {id(d) for d in dropped}
    survivors = [i for i in items if id(i) not in gone]
    inter.build_blocks(survivors)

    # D4 (sha1 liên sàn) + D5 (MinHash -> Jaccard chính xác); giữ cả cặp dưới ngưỡng cho audit/D7
    scores: dict[tuple[int, int], float] = {}
    meta: dict[tuple[int, int], dict[str, Any]] = {}
    hit_keys: set[tuple[int, int]] = set()
    by_obj = {id(it): it for it in survivors}
    pairs = [(a, b, 1.0) for a, b, _ in inter.exact_cross_pairs(survivors)]
    pairs += [(survivors[i], survivors[j], jac) for i, j, jac in mh.candidate_pairs([s["sh"] for s in survivors])]
    gate_blocked = 0
    for a, b, jac in pairs:
        key = pair_key(a, b)
        scores[key] = max(scores.get(key, 0.0), jac)
        same_co = bool(a["slug"]) and a["slug"] == b["slug"]
        meta[key] = {"same_company": same_co, "title_differs": a["tkey"] != b["tkey"],
                     "same_source": a["src"] == b["src"]}
        if scores[key] >= thr and same_co:
            hit_keys.add(key)
    gate_blocked = sum(1 for k, v in scores.items() if v >= thr and k not in hit_keys)
    hits = [(by_obj[k[0]], by_obj[k[1]], scores[k]) for k in hit_keys]
    clusters = inter.clusters(survivors, hits)
    # Cặp mạnh nhất mà từng bản ghi tham gia: cụm union-find có thể nối gián tiếp (A~B, B~C).
    link: dict[int, tuple[int, float]] = {}
    for a, b, v in hits:
        for x, y in ((a, b), (b, a)):
            if id(x) not in link or v > link[id(x)][1]:
                link[id(x)] = (id(y), v)

    member_of: dict[int, list[Item]] = {}
    root_of: dict[int, int] = {}
    cross_dropped: list[Item] = []
    for g in clusters:
        win = pick_cross_winner(g)
        for it in g:
            member_of[id(it)] = g
            root_of[id(it)] = id(g[0])
            if it is win:
                continue
            k = pair_key(it, win)
            direct = scores.get(k, 0.0) if k in hit_keys else 0.0
            via_id, via_score = (id(win), direct) if k in hit_keys else link[id(it)]
            it["drop"] = {"rule": "D4" if it["fkey"] and it["fkey"] == win["fkey"] else "D5",
                          "kept_job_id": win["jid"], "kept_url": win["url"], "kept_title": win["flat"].get("job_title"),
                          "jaccard": round(max(direct, via_score), 4), "linked_via": by_obj[via_id]["jid"],
                          "kept_ref": win}
            cross_dropped.append(it)
        win["merged"] = sorted(f"{i['src']}:{i['jid']}" for i in g if i is not win)

    # Bản nối gián tiếp (A~B, B~C nên C bị loại) hoặc cặp (bản bị loại, bản giữ) không phải cạnh trực tiếp
    # thì dòng `dropped` không nói lên được lý do của chính nó. Ghi thêm một dòng riêng cho từng bản đó.
    indirect = [it for it in cross_dropped if pair_key(it, it["drop"]["kept_ref"]) not in hit_keys]

    # D6: Golden Master cho từng bản ghi giữ lại (cụm => hợp nhất cả cụm; đơn => chính nó)
    kept = [i for i in survivors if id(i) not in {id(d) for d in cross_dropped}]
    masters: list[dict[str, Any]] = []
    for it in kept:
        rec = inter.fuse(member_of.get(id(it)) or [it])
        it["master"] = rec
        masters.append(rec)
        it["env"]["metadata"]["dedup"] = {
            "content_hash_norm": it["chash"], "text_fold_sha1": it["fhash"], "blocking_key": it["bkey"],
            "master_id": rec["master_id"], "cluster_size": rec["duplicate_count"], "merged_from": it["merged"],
            "sources": rec["source_job_ids"] + [f"{r['source']}:{r['job_id']}" for r in rec["repost_records"]],
            "duplicate_count": rec["duplicate_count"],
            "repost_records": rec["repost_records"] or None}
    for d in dropped + cross_dropped:
        d["env"]["metadata"]["dedup"] = {
            "content_hash_norm": d["chash"], "text_fold_sha1": d["fhash"], "blocking_key": d["bkey"],
            "dropped_by": d["drop"]["rule"], "kept_job_id": d["drop"]["kept_job_id"],
            "duplicate_of": dup_ref(d), "kept_url": d["drop"]["kept_url"], "jaccard": d["drop"].get("jaccard")}

    # Bao cao theo nguon, kiem luat bao toan
    all_drops = dropped + cross_dropped
    drop_count: dict[str, Counter] = {src: Counter() for src in sources}
    for d in all_drops:
        drop_count[d["src"]][d["drop"]["rule"]] += 1
    all_items = all_drops + kept
    review = [(k, v) for k, v in scores.items() if k not in hit_keys]  # D7
    for src in sources:
        r = reports[src]
        keep = [i for i in kept if i["src"] == src]
        r.data["output"]["rows"] = len(keep)
        for rule in ("D0", "D2", "D4", "D5", "D6", "D7"):
            if rule == "D6":
                rows, ex = len([i for i in keep if i["merged"]]), [
                    {"job_id": i["jid"], "field": "master_id", "before": i["url"],
                     "after": i["master"]["master_id"], "url": i["url"]} for i in keep if i["merged"]]
            elif rule == "D7":
                mine = [(k, v) for k, v in review if by_obj[k[0]]["src"] == src]
                rows, ex = len(mine), [{"job_id": by_obj[k[0]]["jid"], "field": "jaccard", "before": None,
                                        "after": round(v, 4), "url": by_obj[k[0]]["url"]} for k, v in mine]
            else:
                picked = [d for d in all_drops if d["src"] == src and d["drop"]["rule"] == rule]
                rows, ex = len(picked), [
                    {"job_id": d["jid"], "field": "dedup", "before": d["url"],
                     "after": d["drop"]["kept_url"], "url": d["url"]} for d in picked]
            name = RULE_TEXT[rule] + (f" (J >= {thr})" if rule == "D5" else "")
            r.rule(rule, name, "flag" if rule in ("D6", "D7") else "drop", rows, ex)
        if not full_run:  # để CLI và trang Monitoring thấy rõ đây không phải số toàn dự án
            r.note(f"chạy lẻ {len(sources)}/{len(SOURCES)} sàn - khử trùng liên sàn cần đủ 8 sàn"
                   "; file golden master/audit lần này mang hậu tố '.partial'")
        r.data["extra"]["rule_totals"] = dict(drop_count[src])
        r.check_conserved()

    if not dry_run:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        REJECTED_DIR.mkdir(parents=True, exist_ok=True)
        for src in sources:
            with (OUT_DIR / f"{src}.jsonl").open("w", encoding="utf-8") as fh:
                for it in [i for i in kept if i["src"] == src]:
                    fh.write(json.dumps(it["env"], ensure_ascii=False) + "\n")
            with (REJECTED_DIR / f"{src}.jsonl").open("w", encoding="utf-8") as fh:  # không chứa nội dung JD
                for d in sorted((x for x in all_drops if x["src"] == src), key=lambda x: x["jid"]):
                    fh.write(json.dumps({"source": src, "job_id": d["jid"], "duplicate_of": dup_ref(d),
                                         "drop_rule": d["drop"]["rule"], "jaccard": d["drop"].get("jaccard"),
                                         "linked_via": d["drop"].get("linked_via")}, ensure_ascii=False) + "\n")
        write_masters(masters, suffix)
    write_audit(all_items, scores, meta, hit_keys, by_obj, root_of, suffix, indirect)

    for src in sources:
        reports[src].write(root=report_root)
    total = merge_reports(STEP, [reports[s] for s in sources], dry_run)
    hit_pairs = [meta[k] for k in hit_keys]
    total.data["extra"].update({
        "dedup": {"num_perm": pol["num_perm"], "shingle_words": pol["shingle_words"], "threshold": thr,
                  "review_band": pol["review_band"], "seed": pol["seed"], "policy_version": pol["version"],
                  "lib_version": f"datasketch {importlib.metadata.version('datasketch')}"},
        "jaccard_threshold": thr,
        "tier_counts": dict(Counter(d["drop"]["rule"] for d in all_drops)),
        "pairs_by_band": band_counts(scores),
        "same_source_pairs": sum(m["same_source"] for m in hit_pairs),
        "cross_source_pairs": sum(not m["same_source"] for m in hit_pairs),
        "company_gate_blocked_pairs": gate_blocked,
        "hit_pairs_title_differs": sum(m["title_differs"] for m in hit_pairs),
        "pairs_audited": len(scores), "pairs_over_threshold": len(hit_keys),
        "clusters": len(clusters), "golden_rows": len(masters),
        "cross_platform_clusters": sum(1 for m in masters if m["duplicate_count"] > 1 and m["is_cross_platform"]),
        "rule_totals": dict(Counter(d["drop"]["rule"] for d in all_drops)),
        "cross_dropped": len(cross_dropped), "audit_rows_indirect": len(indirect),
        "audit_review_band": len(review),
        "cdc": {s: reports[s].data["extra"]["cdc"] for s in sources},
        "blocking_blocks": sum(reports[s].data["extra"]["blocking_blocks"] for s in sources),
        "blocking_unique_blocks": len({i["bkey"] for i in survivors}),
        "repost_records": sum(len(m["repost_records"]) for m in masters),
        "lineage_rows": sum(m["duplicate_count"] + len(m["repost_records"]) for m in masters),
        "unparsed_dates": sum(len(m["unparsed_dates"]) for m in masters),
        "cross_language_dupes": "không đo được: PH4 chạy trước dịch (PH5), shingle khác ngôn ngữ không chung nhau",
    })
    if prev and "cosine_threshold" in (prev.get("extra") or {}):  # báo cáo của thuật toán TF-IDF cũ
        total.data["extra"]["previous_tfidf_run"] = {
            "generated_at": prev.get("generated_at"), "input_rows": prev["input"]["rows"],
            "output_rows": prev["output"]["rows"], "rule_totals": prev["extra"].get("rule_totals")}
    # `_all.json` là số Monitoring đọc: chạy lẻ một sàn mà ghi đè thì trang sẽ hiện số thiếu.
    total.data["extra"]["partial_run"] = not full_run
    if not full_run:
        total.note(f"_all chỉ tổng hợp {len(sources)}/{len(SOURCES)} sàn ({', '.join(sources)})"
                   " - muốn số toàn dự án phải chạy --source all")
        total.note("golden master và audit viết ra file hậu tố '.partial' để không đè bản đủ 8 sàn")
    total.write(root=report_root)
    return reports


def write_masters(masters: list[dict[str, Any]], suffix: str = "") -> None:
    import pandas as pd

    pd.DataFrame(masters).to_parquet(OUT_DIR / f"golden_master_jobs{suffix}.parquet", index=False)
    with (OUT_DIR / f"golden_master_jobs{suffix}.jsonl").open("w", encoding="utf-8") as fh:
        for m in masters:
            fh.write(json.dumps(m, ensure_ascii=False, default=str) + "\n")


def write_audit(all_items: Sequence[Item], scores: dict[tuple[int, int], float],
                meta: dict[tuple[int, int], dict[str, Any]], hit_keys: set[tuple[int, int]],
                by_obj: dict[int, Item], root_of: dict[int, int], suffix: str = "",
                indirect: Sequence[Item] = ()) -> None:
    """CSV audit, mỗi cặp ứng viên (J >= cận dưới review_band) một dòng, chia 4 loại.

    - `dropped`             : cặp vượt ngưỡng và qua cổng công ty, khiến một trong hai bản bị loại.
    - `transitive-link`     : cặp không phải cạnh quyết định nhưng hai bên cùng một cụm.
    - `review-band` (D7)    : cặp không bị loại (J dưới ngưỡng, hoặc J đủ nhưng khác công ty).
    - `transitive-dropped`  : bản BỊ LOẠI không nối trực tiếp với bản giữ; `linked_via` chỉ bản cầu nối.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dropped_by = {id(d): d for d in all_items if d["drop"]}
    with (OUT_DIR / f"duplicates_audit{suffix}.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["kind", "rule", "job_id_a", "title_a", "url_a", "job_id_b", "title_b", "url_b",
                    "jaccard", "same_company", "title_differs", "same_source", "blocking_key", "kept_job_id",
                    "linked_via"])
        for key, score in sorted(scores.items(), key=lambda kv: -kv[1]):
            ia, ib = key
            a, b = by_obj[ia], by_obj[ib]
            loser = dropped_by.get(ia) or dropped_by.get(ib)
            m = meta[key]
            if key in hit_keys:
                kind = "dropped"
            elif root_of.get(ia) is not None and root_of.get(ia) == root_of.get(ib):
                kind = "transitive-link"
            else:
                kind = "review-band"
            rule = loser["drop"]["rule"] if kind == "dropped" and loser else "D7"
            w.writerow([kind, rule, a["jid"], a["flat"].get("job_title"), a["url"],
                        b["jid"], b["flat"].get("job_title"), b["url"], round(score, 4),
                        m["same_company"], m["title_differs"], m["same_source"], a["bkey"],
                        loser["drop"]["kept_job_id"] if loser and kind == "dropped" else "", ""])
        for it in sorted(indirect, key=lambda i: (i["src"], i["jid"])):
            win = it["drop"]["kept_ref"]
            w.writerow(["transitive-dropped", it["drop"]["rule"],
                        it["jid"], it["flat"].get("job_title"), it["url"],
                        win["jid"], win["flat"].get("job_title"), win["url"],
                        it["drop"]["jaccard"], it["slug"] == win["slug"], it["tkey"] != win["tkey"],
                        it["src"] == win["src"], it["bkey"], win["jid"], it["drop"]["linked_via"]])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default="all", choices=[*SOURCES, "all"])
    parser.add_argument("--dry-run", action="store_true", help="chỉ đo và ghi báo cáo, không ghi dữ liệu")
    args = parser.parse_args(argv)
    sources = list(SOURCES) if args.source == "all" else [args.source]
    if len(sources) != len(SOURCES) and not args.dry_run:
        parser.error("chạy lẻ một sàn chỉ hợp lệ với --dry-run: khử trùng liên sàn cần đủ 8 sàn,"
                     " chạy applied một sàn sẽ ghi đè output và golden master của cả dự án"
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
