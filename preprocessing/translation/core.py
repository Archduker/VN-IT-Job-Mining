# -*- coding: utf-8 -*-
"""PH5 logic dịch JD Anh -> Việt, không phụ thuộc model: che thuật ngữ, tách đoạn, kiểm, cache, ghép.

Hàm dịch được tiêm vào (`translate_batch(list[str]) -> list[str]`), nên unit test không cần tải model.
Chỉ `description` và `requirements` được dịch (người dùng chốt); cột gốc luôn giữ.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

MODEL_ID = "VietAI/envit5-translation"
MODEL_REVISION = "840bc88104d5a4277af740eaedb024df8c3093e7"  # commit HF, ghim để tái lập
MAX_CHUNK_TOKENS = 200
GEN_PARAMS = {"do_sample": False, "num_beams": 1, "max_new_tokens": 512, "input_prefix": "en: "}
NO_TRANSLATE_FILE = Path(__file__).resolve().parents[1] / "dictionaries" / "no_translate.json"

_NUM = re.compile(r"\d+")
_SEP = re.compile(r"(?<=\d)[.,](?=\d)")  # model đổi 1,500 thành 1.500: bỏ dấu phân cách trước khi so
_PH = re.compile(r"XTERM\d+X")
_BULLET = re.compile(r"^(\s*(?:[-•*●▪–]|\d{1,2}[.)])\s+)")
_SENT = re.compile(r"(?<=[.!?;:])\s+")
_VI_PREFIX = re.compile(r"^\s*vi:\s*", re.I)
LEN_RATIO = (0.3, 3.0)  # đề xuất, chưa có số đo; chỉ áp cho đoạn >= 20 ký tự


def _ph(i: int) -> str:
    return f"XTERM{i}X"  # đo với model thật 10/11: "[[T0]]" bị phá, "XTERM0X" qua nguyên vẹn


def load_approved_terms(path: Path = NO_TRANSLATE_FILE) -> List[str]:
    """Chỉ mục approved=true mới được che."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    return [e["term"] for e in data.get("entries", []) if e.get("approved") is True]


def mask(text: str, terms: Sequence[str]) -> Tuple[str, List[str]]:
    """Thay thuật ngữ bằng token giữ chỗ (dài trước, không phân biệt hoa thường, theo ranh giới từ)."""
    found: List[str] = []
    if not terms:
        return text, found
    ordered = sorted({t for t in terms if t}, key=len, reverse=True)
    pat = re.compile(r"(?<![\w])(" + "|".join(re.escape(t) for t in ordered) + r")(?![\w])", re.I)

    def sub(m: re.Match) -> str:
        found.append(m.group(1))  # giữ đúng chữ gốc để trả lại
        return _ph(len(found) - 1)

    return pat.sub(sub, text), found


def unmask(text: str, found: Sequence[str]) -> str:
    for i, orig in enumerate(found):
        text = text.replace(_ph(i), orig)
    return text


def split_text(text: str, max_tokens: int, count: Callable[[str], int]) -> List[Tuple[str, str]]:
    """Tách thành [(lead, body)]: theo dòng -> câu -> nhóm từ <= max_tokens. lead giữ xuống dòng/bullet ngoài model."""
    pieces: List[Tuple[str, str]] = []
    for line in (l for l in text.split("\n") if l.strip()):
        m = _BULLET.match(line)
        bullet, body = (m.group(1), line[m.end():]) if m else ("", line.strip())
        lead = ("\n" if pieces else "") + bullet.lstrip(" \t")
        segs = [body] if count(body) <= max_tokens else [s for s in _SENT.split(body) if s]
        first = True
        for seg in segs:
            for part in _by_words(seg, max_tokens, count):
                pieces.append((lead if first else " ", part))
                first = False
    return pieces


def _by_words(seg: str, max_tokens: int, count: Callable[[str], int]) -> List[str]:
    if count(seg) <= max_tokens:
        return [seg]
    out, cur = [], []
    for w in seg.split():
        if cur and count(" ".join(cur + [w])) > max_tokens:
            out.append(" ".join(cur))
            cur = []
        cur.append(w)  # shortcut: một "từ" đơn dài hơn max_tokens vẫn nguyên, hiếm
    return out + [" ".join(cur)] if cur else out


def numbers_equal(src: str, dst: str) -> bool:
    nums = lambda t: sorted(_NUM.findall(_SEP.sub("", _PH.sub("", t))))
    return nums(src) == nums(dst)


def is_valid(src: str, dst: str) -> bool:
    if not dst.strip():
        return False
    ph = _PH.findall(src)
    if sorted(ph) != sorted(_PH.findall(dst)):
        return False
    if not numbers_equal(src, dst):
        return False
    return len(src) < 20 or LEN_RATIO[0] <= len(dst) / len(src) <= LEN_RATIO[1]


def cache_key(chunk: str, model_id: str = MODEL_ID, revision: str = MODEL_REVISION, params: Optional[dict] = None) -> str:
    raw = "\x1f".join([model_id, revision, json.dumps(params or GEN_PARAMS, sort_keys=True), chunk])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TranslationContext:
    """Giữ hàm dịch, cache (RAM + jsonl nối tiếp để resume) và bộ đếm cho báo cáo."""

    def __init__(self, translate_batch: Optional[Callable[[List[str]], List[str]]] = None,
                 count: Callable[[str], int] = lambda s: len(s.split()),
                 terms: Sequence[str] = (), cache_path: Optional[Path] = None,
                 max_tokens: int = MAX_CHUNK_TOKENS, meta: Optional[Callable[[], dict]] = None):
        self.translate_batch, self.count, self.terms = translate_batch, count, list(terms)
        self.max_tokens, self.meta = max_tokens, meta or dict  # meta: hàm trả dict (VRAM đỉnh đọc lúc báo cáo)
        self.cache_path = Path(cache_path) if cache_path else None
        self.cache: Dict[str, str] = {}
        if self.cache_path and self.cache_path.exists():
            for line in self.cache_path.read_text(encoding="utf-8").splitlines():
                d = json.loads(line)
                self.cache[d["k"]] = d["v"]
        self.stats = {"rows_en": 0, "rows_translated": 0, "rows_failed": 0, "chunks": 0,
                      "cache_hits": 0, "model_calls": 0, "retries": 0, "failed_chunks": 0}

    def _put(self, key: str, val: str) -> None:
        self.cache[key] = val
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self.cache_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"k": key, "v": val}, ensure_ascii=False) + "\n")

    def _translate_chunks(self, chunks: List[str]) -> Tuple[List[str], int]:
        """Trả (bản dịch từng đoạn, số đoạn hỏng); đoạn hỏng giữ nguyên gốc, không vào cache."""
        keys = [cache_key(c) for c in chunks]
        res: Dict[int, str] = {i: self.cache[k] for i, k in enumerate(keys) if k in self.cache}
        self.stats["cache_hits"] += len(res)
        todo = [i for i in range(len(chunks)) if i not in res]
        failed = 0
        for attempt in (0, 1):
            if not todo:
                break
            if attempt:
                self.stats["retries"] += len(todo)
            outs = self.translate_batch([chunks[i] for i in todo])
            self.stats["model_calls"] += len(todo)
            bad = []
            for i, o in zip(todo, outs):
                o = _VI_PREFIX.sub("", o).strip()
                if is_valid(chunks[i], o):
                    res[i] = o
                    self._put(keys[i], o)
                else:
                    bad.append(i)
            todo = bad
        for i in todo:  # retry một lần rồi vẫn hỏng: giữ gốc
            res[i] = chunks[i]
            failed += 1
        return [res[i] for i in range(len(chunks))], failed

    def translate_fields(self, desc: Optional[str], req: Optional[str], language: str) -> dict:
        """Cột dịch cho một tin. Chỉ dịch khi language == 'en' và có translate_batch."""
        out = {"description_vi": None, "requirements_vi": None, "translated_by": None,
               "translation_status": "not_needed", "translation_chunks": 0}
        if language != "en":
            out.update(description_vi=desc, requirements_vi=req)  # tin vi: *_vi = gốc
            return out
        self.stats["rows_en"] += 1
        if self.translate_batch is None:
            out["translation_status"] = "not_run"
            return out
        fields = {"description_vi": desc, "requirements_vi": req}
        plan, chunks = {}, []  # plan[field] = (pieces, masks, index đầu trong chunks)
        for name, text in fields.items():
            if not text or not text.strip():
                continue
            masked, found = mask(text, self.terms)
            pieces = split_text(masked, self.max_tokens, self.count)
            plan[name] = (pieces, found, len(chunks))
            chunks += [b for _, b in pieces]
        outs, failed = self._translate_chunks(chunks)
        for name, (pieces, found, start) in plan.items():
            body = "".join(lead + outs[start + i] for i, (lead, _) in enumerate(pieces))
            out[name] = unmask(body, found)
        for name, text in fields.items():
            if name not in plan:
                out[name] = text
        out["translation_chunks"] = len(chunks)
        out["translated_by"] = f"{MODEL_ID}@{MODEL_REVISION[:8]}"
        out["translation_status"] = "failed" if failed else "translated"
        self.stats["chunks"] += len(chunks)
        self.stats["failed_chunks"] += failed
        self.stats["rows_failed" if failed else "rows_translated"] += 1
        return out

    def manifest(self) -> dict:
        return {"model_id": MODEL_ID, "model_revision": MODEL_REVISION, "gen_params": GEN_PARAMS,
                "max_chunk_tokens": MAX_CHUNK_TOKENS, "fields": ["description", "requirements"],
                "approved_terms": len(self.terms), **self.meta(), **self.stats}
