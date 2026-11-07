"""Bước 01b Deduplication 2 lớp (docs/spec/05_preprocessing_spec.md mục 3, docs/tasks/02).

Đầu vào: `data/preprocessing/01_clean/<nguồn>.jsonl` (đầu ra duy nhất của 01 Clean, theo P0 mục 2).
Đầu ra:
  - `data/preprocessing/01b_deduplication/<nguồn>.jsonl`  : bản ghi giữ lại, thêm `metadata.dedup`
  - `data/preprocessing/01b_deduplication/golden_master_jobs.parquet` (+ .jsonl): bảng Golden Master
  - `data/preprocessing/01b_deduplication/duplicates_audit.csv`  : mọi cặp trùng và cặp sát ngưỡng,
    kèm một dòng truy vết riêng cho từng bản bị loại nối gián tiếp (người duyệt kiểm được 100%)
  - `reports/preprocessing/01b_deduplication/<nguồn>.json` + `_all.json`

Luật (tiền tố D, theo quy ước mã luật của P0 mục 4):
  D1 Kiểm toán chuỗi version CDC (flag)          - bao nhiêu lần cào lại không đổi nội dung thật
  D2 Repost cùng sàn, trùng hash nội dung (drop) - SPEC-05 mục 3.1
  D3 Gán Blocking Key (flag)                     - SPEC-05 mục 3.2.A
  D4 Trùng liên sàn trùng hash 100% (drop)
  D5 Trùng liên sàn TF-IDF Cosine >= 0.85 (drop) - SPEC-05 mục 3.2.B
  D6 Hợp nhất Golden Record (flag)               - SPEC-05 mục 3.2.C

Chạy:  python -m preprocessing.deduplication.run --dry-run
       python -m preprocessing.deduplication.run --source itviec
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from collections.abc import Sequence
from typing import Any

from preprocessing.clean.run import filled
from preprocessing.common import REPO_ROOT, SOURCES, step_report
from preprocessing.common.step_report import StepReport, merge_reports
from preprocessing.deduplication import inter_source as inter
from preprocessing.deduplication.blocking import blocking_key
from preprocessing.deduplication.intra_source import apply_d2, cdc_chain_audit
from preprocessing.deduplication.text_norm import canonical_hash, identity_hash, jd_text
from preprocessing.integration.json_flattener import flatten_raw_job_record

STEP = "01b_deduplication"
DATA_DIR = REPO_ROOT / "data" / "preprocessing"
IN_DIR = DATA_DIR / "01_clean"
OUT_DIR = DATA_DIR / STEP
RAW_ROOT = REPO_ROOT / "data"  # test thay bằng tmp_path
REVIEW_BAND = 0.75  # cặp dưới ngưỡng vẫn ghi ra audit để người duyệt kiểm (checklist mục 3.4)
Item = dict[str, Any]

RULE_TEXT = {
    "D1": "Kiểm toán chuỗi version CDC (cào lại có đổi nội dung thật không)",
    "D2": "Repost cùng sàn có nội dung chuẩn hóa trùng nhau (canonical hash)",
    "D3": "Gán Blocking Key = Slug(Company)_LocationCode_TitleGroup",
    "D4": "Trùng liên sàn: hash nội dung khớp 100%",
    "D5": "Trùng liên sàn: TF-IDF Cosine >= ngưỡng",
    "D6": "Hợp nhất Golden Record (bản giữ có merged_from)",
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
        items.append({
            "src": source, "jid": str(meta.get("job_id") or ""), "url": str(meta.get("source_url") or ""),
            "env": env, "flat": flat, "chash": canonical_hash(flat), "xhash": identity_hash(flat),
            "jd": jd_text(flat),
            "bkey": blocking_key(flat), "seen_at": str(meta.get("scraped_at") or ""),
            "ver": int(meta.get("version") or 1), "drop": None, "master": None,
            "reposts": [], "merged": [],
        })
    return items


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


# ---------------------------------------------------------------- chay
def run(sources: Sequence[str] = SOURCES, dry_run: bool = True) -> dict[str, StepReport]:
    full_run = len(sources) == len(SOURCES) and set(sources) == set(SOURCES)
    if len(set(sources)) != len(sources):
        raise ValueError("sources không được lặp")
    if not full_run and not dry_run:
        raise ValueError("chạy thiếu sàn chỉ hợp lệ với dry_run=True")
    report_root = None if full_run else step_report.REPORTS_ROOT / "_partial"
    suffix = artifact_suffix(full_run)
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

    # D2: repost trong cùng một sàn
    dropped: list[Item] = []
    for src in sources:
        dropped += apply_d2([i for i in items if i["src"] == src], reports[src].data["extra"])

    # D3: blocking key cho mọi bản ghi còn sống
    gone = {id(d) for d in dropped}
    survivors = [i for i in items if id(i) not in gone]
    inter.build_blocks(survivors)

    # D4 + D5: so sánh trong block, lấy cả cặp sát ngưỡng để đưa vào audit
    scores: dict[tuple[int, int], float] = {}
    cosine_stats: dict[str, int] = {}
    for a, b, score in inter.exact_cross_pairs(survivors) + inter.cross_source_pairs(
            survivors, REVIEW_BAND, stats=cosine_stats):
        key = pair_key(a, b)
        scores[key] = max(scores.get(key, 0.0), score)
    by_obj = {id(it): it for it in survivors}
    hits = [(by_obj[k[0]], by_obj[k[1]], v) for k, v in scores.items() if v >= inter.COSINE_THRESHOLD]
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
            direct = scores.get(pair_key(it, win), 0.0)
            via_id, via_score = (id(win), direct) if direct >= inter.COSINE_THRESHOLD else link[id(it)]
            it["drop"] = {"rule": "D4" if it["xhash"] and it["xhash"] == win["xhash"] else "D5",
                          "kept_job_id": win["jid"], "kept_url": win["url"], "kept_title": win["flat"].get("job_title"),
                          "cosine": round(max(direct, via_score), 4), "linked_via": by_obj[via_id]["jid"],
                          "kept_ref": win}
            cross_dropped.append(it)
        win["merged"] = sorted(f"{i['src']}:{i['jid']}" for i in g if i is not win)

    # Bản nối gián tiếp (A~B, B~C nên C bị loại) hoặc cặp (bản bị loại, bản giữ) chỉ đạt dưới
    # ngưỡng 0.85 thì dòng `dropped` không nói lên được lý do của chính nó. Ghi thêm một dòng
    # riêng cho từng bản đó để 100% bản bị loại đều có một dòng chỉ thẳng về bản giữ.
    indirect = [it for it in cross_dropped
                if scores.get(pair_key(it, it["drop"]["kept_ref"]), 0.0) < inter.COSINE_THRESHOLD]

    # D6: Golden Master cho từng bản ghi giữ lại (cụm => hợp nhất cả cụm; đơn => chính nó)
    kept = [i for i in survivors if id(i) not in {id(d) for d in cross_dropped}]
    masters: list[dict[str, Any]] = []
    for it in kept:
        rec = inter.fuse(member_of.get(id(it)) or [it])
        it["master"] = rec
        masters.append(rec)
        it["env"]["metadata"]["dedup"] = {
            "content_hash_norm": it["chash"], "identity_hash": it["xhash"], "blocking_key": it["bkey"],
            "master_id": rec["master_id"], "cluster_size": rec["duplicate_count"], "merged_from": it["merged"],
            "repost_records": rec["repost_records"] or None}
    for d in dropped + cross_dropped:
        d["env"]["metadata"]["dedup"] = {
            "content_hash_norm": d["chash"], "identity_hash": d["xhash"], "blocking_key": d["bkey"],
            "dropped_by": d["drop"]["rule"], "kept_job_id": d["drop"]["kept_job_id"],
            "kept_url": d["drop"]["kept_url"], "cosine": d["drop"].get("cosine")}

    # Bao cao theo nguon, kiem luat bao toan
    drop_count: dict[str, Counter] = {src: Counter() for src in sources}
    for d in dropped + cross_dropped:
        drop_count[d["src"]][d["drop"]["rule"]] += 1
    all_items = dropped + cross_dropped + kept
    for src in sources:
        r = reports[src]
        keep = [i for i in kept if i["src"] == src]
        r.data["output"]["rows"] = len(keep)
        for rule in ("D2", "D4", "D5", "D6"):
            if rule == "D6":
                rows, ex = len([i for i in keep if i["merged"]]), [
                    {"job_id": i["jid"], "field": "master_id", "before": i["url"],
                     "after": i["master"]["master_id"], "url": i["url"]} for i in keep if i["merged"]]
            else:
                picked = [d for d in dropped + cross_dropped if d["src"] == src and d["drop"]["rule"] == rule]
                rows, ex = len(picked), [
                    {"job_id": d["jid"], "field": "dedup", "before": d["url"],
                     "after": d["drop"]["kept_url"], "url": d["url"]} for d in picked]
            name = RULE_TEXT[rule] + (f" (cosine >= {inter.COSINE_THRESHOLD})" if rule == "D5" else "")
            r.rule(rule, name, "flag" if rule == "D6" else "drop", rows, ex)
        if not full_run:  # để CLI và trang Monitoring thấy rõ đây không phải số toàn dự án
            r.note(f"chạy lẻ {len(sources)}/{len(SOURCES)} sàn - khử trùng liên sàn cần đủ 8 sàn"
                   "; file golden master/audit lần này mang hậu tố '.partial'")
        r.data["extra"]["rule_totals"] = dict(drop_count[src])
        r.check_conserved()

    if not dry_run:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for src in sources:
            with (OUT_DIR / f"{src}.jsonl").open("w", encoding="utf-8") as fh:
                for it in [i for i in kept if i["src"] == src]:
                    fh.write(json.dumps(it["env"], ensure_ascii=False) + "\n")
        write_masters(masters, suffix)
    write_audit(all_items, scores, by_obj, root_of, suffix, indirect)

    for src in sources:
        reports[src].write(root=report_root)
    total = merge_reports(STEP, [reports[s] for s in sources], dry_run)
    total.data["extra"].update({
        "cosine_threshold": inter.COSINE_THRESHOLD, "feature": "TfidfVectorizer(char_wb, 3..5)",
        "pairs_audited": len(scores), "pairs_over_threshold": len(hits),
        "clusters": len(clusters), "golden_rows": len(masters),
        "cross_platform_clusters": sum(1 for m in masters if m["duplicate_count"] > 1 and m["is_cross_platform"]),
        "rule_totals": dict(Counter(d["drop"]["rule"] for d in dropped + cross_dropped)),
        "cross_dropped": len(cross_dropped), "audit_rows_indirect": len(indirect),
        "audit_review_band": sum(1 for v in scores.values() if v < inter.COSINE_THRESHOLD),
        "cdc": {s: reports[s].data["extra"]["cdc"] for s in sources},
        "blocking_blocks": sum(reports[s].data["extra"]["blocking_blocks"] for s in sources),
        "blocking_unique_blocks": len({i["bkey"] for i in survivors}),
        "repost_records": sum(len(m["repost_records"]) for m in masters),
        "lineage_rows": sum(m["duplicate_count"] + len(m["repost_records"]) for m in masters),
        "unparsed_dates": sum(len(m["unparsed_dates"]) for m in masters),
        **cosine_stats,
    })
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


def write_audit(all_items: Sequence[Item], scores: dict[tuple[int, int], float], by_obj: dict[int, Item],
                root_of: dict[int, int], suffix: str = "", indirect: Sequence[Item] = ()) -> None:
    """CSV phục vụ mục 3.4 checklist: mỗi cặp được đưa vào block đều ghi lại, chia 4 loại.

    - `dropped`             : chính cặp này vượt ngưỡng 0.85 và khiến một trong hai bản bị loại.
    - `transitive-link`     : cặp dưới ngưỡng nhưng hai bên cùng một cụm (nối gián tiếp A~B, B~C).
    - `review-band`         : cặp dưới ngưỡng, chưa bị loại, người duyệt cần kiểm có lọt không.
    - `transitive-dropped`  : bản BỊ LOAI mà cặp của nó với bản giữ không vượt ngưỡng 0.85 (nối bằng
      cầu nối, hoặc chỉ sát ngưỡng); cột `linked_via` chỉ ra bản trung gian nào là cầu nối.
      Mỗi bản bị loại đều có đúng một dòng như vậy nếu cần truy vết -> 100% kiểm được bằng mắt.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dropped_by = {id(d): d for d in all_items if d["drop"]}
    with (OUT_DIR / f"duplicates_audit{suffix}.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["kind", "rule", "job_id_a", "title_a", "url_a", "job_id_b", "title_b", "url_b",
                    "cosine", "blocking_key", "kept_job_id", "linked_via"])
        for (ia, ib), score in sorted(scores.items(), key=lambda kv: -kv[1]):
            a, b = by_obj[ia], by_obj[ib]
            loser = dropped_by.get(ia) or dropped_by.get(ib)
            if score >= inter.COSINE_THRESHOLD:
                kind = "dropped"
            elif root_of.get(ia) is not None and root_of.get(ia) == root_of.get(ib):
                kind = "transitive-link"
            else:
                kind = "review-band"
            w.writerow([kind, loser["drop"]["rule"] if loser else f"cosine<{inter.COSINE_THRESHOLD}",
                        a["jid"], a["flat"].get("job_title"), a["url"],
                        b["jid"], b["flat"].get("job_title"), b["url"], round(score, 4), a["bkey"],
                        loser["drop"]["kept_job_id"] if loser else "", ""])
        for it in sorted(indirect, key=lambda i: (i["src"], i["jid"])):
            win = it["drop"]["kept_ref"]
            w.writerow(["transitive-dropped", it["drop"]["rule"],
                        it["jid"], it["flat"].get("job_title"), it["url"],
                        win["jid"], win["flat"].get("job_title"), win["url"],
                        it["drop"]["cosine"], it["bkey"], win["jid"], it["drop"]["linked_via"]])


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
