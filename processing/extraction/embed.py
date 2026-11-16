# -*- coding: utf-8 -*-
"""Bước 12_e5 (PH8): embedding bullet bằng multilingual-e5-base và vector JD.

Cache theo sha1(text) chia thành shard để chạy lại/ngắt giữa chừng không tính lại. Vector JD = trung bình mọi bullet
(người dùng chọn a, 11/11) và thêm trung bình riêng theo 3 section; JD không có bullet thì vector 0, không điền.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Dict, List, Sequence

import numpy as np
import pandas as pd

from preprocessing.common.step_report import StepReport, merge_reports

STEP = "12_e5"
MODEL = "intfloat/multilingual-e5-base"
SECTIONS = ("mo_ta", "yeu_cau", "phuc_loi")


def text_key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def load_cache(cache_dir: Path) -> Dict[str, np.ndarray]:
    cache: Dict[str, np.ndarray] = {}
    for f in sorted(Path(cache_dir).glob("shard_*.npz")):
        z = np.load(f, allow_pickle=False)
        cache.update(zip(z["keys"].tolist(), z["vecs"]))
    return cache


def embed_texts(texts: Sequence[str], encode_fn: Callable[[List[str]], np.ndarray], cache_dir: Path,
                chunk: int = 4096) -> np.ndarray:
    """Trả ma trận float16 (len(texts), d) theo đúng thứ tự texts; chỉ gọi model cho văn bản chưa có trong cache."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = load_cache(cache_dir)
    keys = [text_key(t) for t in texts]
    todo: Dict[str, str] = {}
    for k, t in zip(keys, texts):
        if k not in cache and k not in todo:
            todo[k] = t
    items = list(todo.items())
    shard = len(list(cache_dir.glob("shard_*.npz")))
    for i in range(0, len(items), chunk):
        part = items[i:i + chunk]
        vecs = np.asarray(encode_fn([t for _, t in part]), dtype=np.float16)
        np.savez(cache_dir / f"shard_{shard:05d}.npz", keys=np.array([k for k, _ in part]), vecs=vecs)
        shard += 1
        cache.update(zip((k for k, _ in part), vecs))
    return np.vstack([cache[k] for k in keys]) if keys else np.zeros((0, 0), dtype=np.float16)


def job_vectors(index: pd.DataFrame, emb: np.ndarray, job_ids: Sequence[str]) -> dict:
    """index: cột job_id_global, section (cùng thứ tự với emb). Trả {all, mo_ta, yeu_cau, phuc_loi: (n,d), has: (n,3) bool}."""
    pos = {j: i for i, j in enumerate(job_ids)}
    n, d = len(job_ids), emb.shape[1]
    rows = index["job_id_global"].map(pos).to_numpy()
    ok = ~pd.isna(rows)
    rows = rows[ok].astype(int)
    e = emb[ok].astype(np.float32)
    secs = index["section"].to_numpy()[ok]

    def mean_of(mask) -> tuple:
        s = np.zeros((n, d), dtype=np.float32)
        c = np.zeros(n, dtype=int)
        np.add.at(s, rows[mask], e[mask])
        np.add.at(c, rows[mask], 1)
        nz = np.linalg.norm(s, axis=1)
        s[nz > 0] /= nz[nz > 0, None]
        return s, c > 0

    out = {"all": mean_of(np.ones(len(rows), dtype=bool))[0]}
    has = []
    for sec in SECTIONS:
        out[sec], h = mean_of(secs == sec)
        has.append(h)
    out["has"] = np.stack(has, axis=1)
    return out


def _model_encoder(batch_size: int = 64, max_len: int = 256):
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(MODEL, device="cuda")
    m.half()
    m.max_seq_length = max_len

    def enc(texts: List[str]) -> np.ndarray:
        return m.encode([f"passage: {t}" for t in texts], batch_size=batch_size, normalize_embeddings=True,
                        show_progress_bar=False)
    return enc


def run(sources, dry_run: bool = True, out_root=None, report_root=None, encoder=None, limit=None):
    from processing.extraction.run import OUT_ROOT, REPORT_ROOT
    out_root, report_root = out_root or OUT_ROOT, report_root or REPORT_ROOT
    b = pd.read_parquet(out_root / "07_sections" / "all.parquet")
    b = b[b["source_platform"].isin(list(sources))].sort_values(["job_id_global", "bullet_idx"], kind="mergesort").reset_index(drop=True)
    ids = sorted(b["job_id_global"].unique())
    if limit:
        b = b.head(limit)
    out = out_root / STEP
    if dry_run:
        n_new = len(set(text_key(t) for t in b["text"]) - set(load_cache(out / "cache")))
        extra = {"bullets": len(b), "texts_to_embed_now": n_new, "model": MODEL, "note": "dry-run: không gọi model"}
        emb = None
    else:
        emb = embed_texts(b["text"].tolist(), encoder or _model_encoder(), out / "cache")
        extra = {"bullets": len(b), "dim": int(emb.shape[1]), "model": MODEL}
    reports: Dict[str, StepReport] = {}
    for src in sources:
        n = int((b["source_platform"] == src).sum())
        r = StepReport(STEP, src, dry_run)
        r.set_io(None, n, out / "bullet_emb.npy", n)
        r.data["extra"] = dict(extra)
        reports[src] = r
    total = merge_reports(STEP, list(reports.values()), dry_run)
    total.data["extra"].update(extra)
    reports["_all"] = total
    for r in reports.values():
        r.check_conserved()
    if not dry_run:
        v = job_vectors(b, emb, ids)
        for r in reports.values():
            r.data["extra"]["jobs"] = len(ids)
            r.write(report_root)
        np.save(out / "bullet_emb.npy", emb)
        b[["job_id_global", "bullet_idx", "section"]].to_parquet(out / "bullet_index.parquet", index=False)
        np.savez(out / "job_emb.npz", ids=np.array(ids), **{k: (x.astype(np.float16) if k != "has" else x) for k, x in v.items()})
        (out / "meta.json").write_text(json.dumps({"model": MODEL, "prefix": "passage: ", "sections": SECTIONS}), encoding="utf-8")
    return reports
