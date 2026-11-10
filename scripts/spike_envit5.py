#!/usr/bin/env python3
"""Spike PH0: đo VietAI/envit5-translation trên 20 JD tiếng Anh thật. Chạy tay, không đưa vào pytest/git.

    python scripts/spike_envit5.py [--n 20] [--seed 42] [--max-tokens 200]
Ghi reports/preprocessing/_spike/envit5_<ngày>.md. Cần mạng để tải model từ Hugging Face.
"""
from __future__ import annotations

import argparse
import random
import re
import statistics
import sys
import time
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
MODEL = "VietAI/envit5-translation"
EN_STOP = re.compile(r"\b(the|and|with|you|our|will|experience|team|of|to|for)\b", re.I)
TAG = re.compile(r"<[^>]+>")


def is_english(t: str) -> bool:
    # heuristic tạm: tỉ lệ ASCII cao và nhiều stopword tiếng Anh; PH3 sẽ thay bằng fasttext lid
    t = t[:3000]
    return len(t) > 400 and sum(c.isascii() for c in t) / len(t) > 0.985 and len(EN_STOP.findall(t)) / (len(t.split()) or 1) > 0.15


def jd_text(flat: dict) -> str:
    parts = [flat.get("raw_description_text"), flat.get("raw_requirements_text")]
    t = "\n".join(str(p) for p in parts if p and str(p) != "None")
    return re.sub(r"\n{2,}", "\n", TAG.sub("\n", t)).strip()


def chunks(text: str, tok, limit: int):
    cur, n = [], 0
    for line in (l.strip() for l in text.split("\n") if l.strip()):
        for sent in re.split(r"(?<=[.!?;])\s+", line):
            k = len(tok(sent, add_special_tokens=False).input_ids)
            if cur and n + k > limit:
                yield "\n".join(cur); cur, n = [], 0
            cur.append(sent); n += k
    if cur:
        yield "\n".join(cur)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-tokens", type=int, default=200)
    a = ap.parse_args()
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    from preprocessing.common import SOURCES
    from preprocessing.common.raw_reader import latest_envelopes
    from preprocessing.integration.json_flattener import flatten_raw_job_record

    pool, total = [], 0
    for s in SOURCES:
        envs, _ = latest_envelopes(REPO_ROOT / "data" / s / "raw")
        for e in envs:
            f = flatten_raw_job_record(e); total += 1
            t = jd_text(f)
            if is_english(t):
                pool.append((s, f.get("job_id_global"), t))
    print(f"JD raw mới nhất: {total}, JD tiếng Anh theo heuristic: {len(pool)}")
    jds = random.Random(a.seed).sample(pool, a.n)

    L = ["# Spike envit5-translation", "", f"Ngày: {date.today()}; model `{MODEL}`; torch {torch.__version__}; seed {a.seed}", ""]
    t0 = time.time()
    try:
        tok = AutoTokenizer.from_pretrained(MODEL)
        tok_note = "AutoTokenizer"
    except Exception:  # transformers 5.22 lỗi chuyển đổi vocab của repo này: nạp thẳng tokenizer.json
        from huggingface_hub import hf_hub_download
        from transformers import PreTrainedTokenizerFast
        tok = PreTrainedTokenizerFast(tokenizer_file=hf_hub_download(MODEL, "tokenizer.json"), eos_token="</s>", pad_token="<pad>", unk_token="<unk>")
        tok_note = "AutoTokenizer LỖI (TypeError vocab dict/Sequence, transformers 5.22.2); dùng PreTrainedTokenizerFast(tokenizer.json)"
    model0 = AutoModelForSeq2SeqLM.from_pretrained(MODEL)
    load_s = time.time() - t0
    from huggingface_hub import scan_cache_dir
    size = sum(r.size_on_disk for r in scan_cache_dir().repos if r.repo_id == MODEL) / 1e6
    cfg = model0.config
    L += ["## 1. Giới hạn đầu vào", f"- cách nạp tokenizer: {tok_note}", f"- tokenizer.model_max_length = {tok.model_max_length}", f"- config n_positions = {getattr(cfg, 'n_positions', None)}; relative_attention_max_distance = {getattr(cfg, 'relative_attention_max_distance', None)}",
          f"- dung lượng tải: {size:.0f} MB; thời gian nạp (gồm tải): {load_s:.0f}s; tham số: {sum(p.numel() for p in model0.parameters())/1e6:.0f}M"]
    long_text = max(jds, key=lambda x: len(x[2]))[2]
    ids = tok("en: " + long_text, return_tensors="pt")
    L.append(f"- đoạn thử dài nhất ({ids.input_ids.shape[1]} token, không cắt): ")
    L.append("")

    results = {}
    for dev in (["cuda"] if torch.cuda.is_available() else []) + ["cpu"]:
        model = model0.to(dev).eval()
        # đoạn dài hơn giới hạn: ghi hành vi
        try:
            with torch.no_grad():
                n_in = ids.input_ids.shape[1]
                out = model.generate(**{k: v.to(dev) for k, v in ids.items()}, max_length=512)
            L.append(f"  - {dev}: dịch cả đoạn {n_in} token một lần: không lỗi; đầu ra {out.shape[1]} token (max_length=512 cắt đầu ra)")
        except Exception as e:
            L.append(f"  - {dev}: dịch cả đoạn {n_in} token một lần: LỖI {type(e).__name__}: {str(e)[:150]}")
        for bs in (1, 4):
            if dev == "cpu" and bs == 4 and len(jds) > 5:
                sub = jds[:5]   # CPU chậm: batch 4 chỉ đo trên 5 JD
            else:
                sub = jds
            per_jd, oom, outs = [], False, {}
            if dev == "cuda":
                torch.cuda.reset_peak_memory_stats()
            for s, jid, text in sub:
                cs = ["en: " + c for c in chunks(text, tok, a.max_tokens)]
                t1 = time.time(); res = []
                try:
                    for i in range(0, len(cs), bs):
                        enc = tok(cs[i:i + bs], return_tensors="pt", padding=True, truncation=False).to(dev)
                        with torch.no_grad():
                            o = model.generate(**enc, max_length=512)
                        res += tok.batch_decode(o, skip_special_tokens=True)
                except torch.cuda.OutOfMemoryError:
                    oom = True; torch.cuda.empty_cache(); break
                per_jd.append(time.time() - t1); outs[jid] = (text, "\n".join(res), len(cs))
            peak = f"{torch.cuda.max_memory_allocated()/2**20:.0f} MiB" if dev == "cuda" else "n/a (CPU)"
            med = statistics.median(per_jd) if per_jd else None
            results[(dev, bs)] = (len(per_jd), med, peak, oom)
            if (dev, bs) == (("cuda" if torch.cuda.is_available() else "cpu"), 1):
                samples = outs
        if dev == "cuda":
            model0 = model.to("cpu"); torch.cuda.empty_cache()

    L += ["", "## 2-3. VRAM và tốc độ", "| thiết bị | batch | số JD đo | trung vị s/JD | VRAM đỉnh | OOM |", "|---|---|---|---|---|---|"]
    for (dev, bs), (n, med, peak, oom) in results.items():
        L.append(f"| {dev} | {bs} | {n} | {med:.1f} | {peak} | {'có' if oom else 'không'} |" if med else f"| {dev} | {bs} | {n} | chưa đo | {peak} | {'có' if oom else 'không'} |")
    L += ["", "## 4. Ước lượng tổng thời gian",
          f"- số JD tiếng Anh theo heuristic tạm trên {total} JD raw mới nhất (chưa khử trùng, chưa lọc IT): {len(pool)} ({100*len(pool)/total:.1f}%)"]
    for (dev, bs), (n, med, peak, oom) in results.items():
        if med:
            L.append(f"- {dev} batch {bs}: {len(pool)} x {med:.1f}s = {len(pool)*med/3600:.1f} giờ")
    L += ["", "## 5. 5 JD gốc và bản dịch (đầu 700 ký tự mỗi bản)"]
    for jid, (src, dst, k) in list(samples.items())[:5]:
        L += [f"### {jid} ({k} đoạn)", "**Gốc**", "```", src[:700], "```", "**Dịch**", "```", dst[:700], "```"]
    out = REPO_ROOT / "reports" / "preprocessing" / "_spike"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"envit5_{date.today()}.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L[:30]))


if __name__ == "__main__":
    main()
