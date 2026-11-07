"""Tầng 1 - Khử trùng lặp nội sàn (Intra-Source Deduplication & CDC), docs/spec/05 mục 3.1.

Hai luật:
  D1 (kiểm toán, không bỏ dòng): đọc chuỗi version trong `data/<nguồn>/raw/`, đếm mỗi bước nhảy
     version có đổi nội dung thật không, theo hai khóa:
       - `content_hash` do collection sinh (metadata.content_hash) - khóa sau-cào;
       - `canonical_hash` của module này - khóa đã bóc HTML, bỏ boilerplate, bỏ dấu thanh.
     Số liệu này là phản hồi cho bước Collection (SCRAPE), không thay đổi bản ghi đầu ra.
  D2 (bỏ dòng): repost trong cùng sàn - cùng `canonical_hash` nhưng khác `job_id`/URL.
     Giữ lại một bản ghi chính (canonical record), các bản còn lại bị bỏ và ghi tham chiếu
     `repost_of` (url + job_id + hash) đúng như đặc tả.

Định danh khóa chính của tầng 1 là cặp (source_platform, job_id) - mục 3.1 SPEC-05.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from preprocessing.common.raw_reader import read_raw, snapshot_order
from preprocessing.deduplication.text_norm import canonical_hash
from preprocessing.integration.json_flattener import flatten_raw_job_record

Item = dict[str, Any]  # bản ghi đã làm phẳng, xem preprocessing/deduplication/run.py


def pick_winner(items: Iterable[Item]) -> Item:
    """Bản ghi chính: nhiều trường có giá trị nhất, bằng nhau thì bản cào mới nhất, rồi job_id (ổn định)."""
    from preprocessing.clean.run import filled  # dùng lại thước đo độ đầy đủ của Clean (C6)

    return max(items, key=lambda it: (filled(it["flat"]), str(it["seen_at"]), it["jid"]))


def cdc_chain_audit(source: str, raw_dir: Path) -> dict[str, Any]:
    """Đếm các bước nhảy version của từng job_id và phân loại đổi/không đổi nội dung."""
    snapshots, _, _ = read_raw(raw_dir)
    chains: dict[str, list[tuple[Any, dict[str, Any]]]] = defaultdict(list)
    for rel, env in snapshots:
        jid = str(env["metadata"].get("job_id") or "")
        if jid:
            chains[jid].append((rel, env))

    hops = same_crawler = same_canonical = version_flat = 0
    for entries in chains.values():
        if len(entries) < 2:
            continue
        chain = sorted(
            ((snapshot_order(env), str(env["metadata"].get("content_hash") or ""),
              int(env["metadata"].get("version") or 1), canonical_hash(flatten_raw_job_record(env, source)))
             for _, env in entries),
            key=lambda c: c[0])
        for (_, hc, vc, cc), (_, hy, vn, cy) in zip(chain, chain[1:], strict=False):
            hops += 1
            if hc and hc == hy:
                same_crawler += 1
            if cc == cy:
                same_canonical += 1
            if vc == vn:
                version_flat += 1  # bản sau khác nội dung nhưng collection không bump version
    multi = sum(1 for e in chains.values() if len(e) > 1)
    return {
        "job_ids": len(chains),
        "chains_gt1": multi,
        "hops": hops,
        "hop_same_crawler_hash": same_crawler,
        "hop_same_canonical_hash": same_canonical,
        "hop_version_not_bumped": version_flat,
    }


def repost_groups(items: list[Item]) -> list[list[Item]]:
    """Nhóm repost cùng sàn: cùng canonical_hash, khác job_id (D2)."""
    by_hash: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        if it["chash"]:
            by_hash[it["chash"]].append(it)
    return [g for g in by_hash.values() if len({x["jid"] for x in g}) > 1]


def apply_d2(items: list[Item], reports_extra: dict[str, Any]) -> list[Item]:
    """Bỏ repost, giữ bản chính; trả về các bản ghi bị loại."""
    dropped: list[Item] = []
    groups = repost_groups(items)
    for g in groups:
        win = pick_winner(g)
        for it in g:
            if it is win:
                continue
            it["drop"] = {"rule": "D2", "kept_job_id": win["jid"], "kept_url": win["url"], "hash": it["chash"]}
            dropped.append(it)
        win.setdefault("reposts", []).extend(
            {"job_id": i["jid"], "url": i["url"], "content_hash": i["chash"]} for i in g if i is not win)
    reports_extra["d2_groups"] = len(groups)
    return dropped
