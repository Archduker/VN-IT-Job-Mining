"""Đối chiếu với dữ liệu ngoài `vietnam-it-job-trends` (chỉ trên máy, chỉ đọc; docs/target/06_yeu_cau_du_lieu.md mục 2, 4).

Dữ liệu do LLM sinh (`extracted_info.tech_stack`, `extracted_info.keywords`), không phải gold, repo gốc không có
license: chỉ dùng để đối chiếu, không trộn vào dữ liệu hay từ điển, không đưa vào git (`data/` bị gitignore).

Ghép tin: cùng sàn + cùng mã số cuối URL + tiêu đề giống nhau (SequenceMatcher ≥ `MIN_TITLE_SIM`). Chỉ so mã số thì
sai ở itviec (53/470 cặp khác hẳn tiêu đề, đo 19/11).
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
EXT_FILE = ROOT / "data" / "external" / "vnjt" / "step07.jsonl"
MIN_TITLE_SIM = 0.5
_ID = re.compile(r"(\d+)(?:\.html|-jv)?/?(?:\?.*)?$")


def url_key(source: str, url: Optional[str]) -> Optional[Tuple[str, str]]:
    m = _ID.search(url or "")
    return (source, m.group(1)) if m else None


def title_sim(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def load_ext(path: Path = EXT_FILE) -> List[dict]:
    if not Path(path).exists():
        raise FileNotFoundError(f"thiếu {path}: chép step07.jsonl của vietnam-it-job-trends vào đây (không đưa vào git)")
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def match_jobs(ours: Iterable[Tuple[str, str, str, str]], ext: List[dict],
               min_sim: float = MIN_TITLE_SIM) -> Dict[str, dict]:
    """`ours`: (job_id, source, url, title). Trả job_id → bản ghi ngoài (lấy bản giống tiêu đề nhất)."""
    by_key: Dict[Tuple[str, str], List[dict]] = {}
    for x in ext:
        k = url_key(x.get("site"), x.get("job_url"))
        if k:
            by_key.setdefault(k, []).append(x)
    out: Dict[str, dict] = {}
    for job_id, source, url, title in ours:
        cands = by_key.get(url_key(source, url) or ("", ""), [])
        best = max(cands, key=lambda x: title_sim(title, x.get("title")), default=None)
        if best is not None and title_sim(title, best.get("title")) >= min_sim:
            out[job_id] = best
    return out


def to_slugs(names: Iterable[str], matcher) -> Set[str]:
    """Tên trong `tech_stack`/`keywords` → slug của skills_v2: khớp nguyên alias trước, không được thì quét như văn bản."""
    out: Set[str] = set()
    for n in names or []:
        s = matcher.meta_slug(str(n))
        if s:
            out.add(s)
            continue
        out.update(h.slug for h in matcher.find(str(n)) if not h.slug.startswith("__"))
    return out


def ext_slug_sets(matched: Dict[str, dict], matcher) -> Dict[str, Tuple[Set[str], Set[str]]]:
    """job_id → (slug trong tech_stack, slug trong keywords)."""
    res = {}
    for j, x in matched.items():
        info = x.get("extracted_info") or {}
        res[j] = (to_slugs(info.get("tech_stack"), matcher), to_slugs(info.get("keywords"), matcher))
    return res
