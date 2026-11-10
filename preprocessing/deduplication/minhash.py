"""PH4 tầng 2-3: sha1(text_fold) và MinHash/LSH sinh ứng viên + Jaccard CHÍNH XÁC trên shingle 5 từ.

Tham số đọc từ preprocessing/dictionaries/dedup_policy.json (không hardcode).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from datasketch import MinHash, MinHashLSH

from preprocessing.common import REPO_ROOT
from preprocessing.deduplication.text_norm import clean_text, fold

POLICY_PATH = REPO_ROOT / "preprocessing" / "dictionaries" / "dedup_policy.json"


@lru_cache(maxsize=1)
def policy() -> dict[str, Any]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def fold_text(flat: dict) -> str:
    """fold(clean(title + requirements + description)), cùng hàm đã dùng để đo ở spec PH4 mục 2.2."""
    parts = (clean_text(flat.get(k)) for k in ("job_title", "raw_requirements_text", "raw_description_text"))
    return fold(" ".join(p for p in parts if p))


def sha1_fold(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def shingles(text: str, k: int | None = None) -> frozenset[str]:
    """Shingle k từ. Văn bản ngắn hơn k từ thành đúng một shingle; rỗng thành tập rỗng."""
    k = k or policy()["shingle_words"]
    w = text.split()
    if not w:
        return frozenset()
    return frozenset(" ".join(w[i:i + k]) for i in range(max(1, len(w) - k + 1)))


def exact_jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _minhash(sh: frozenset[str]) -> MinHash:
    p = policy()
    m = MinHash(num_perm=p["num_perm"], seed=p["seed"])
    for s in sorted(sh):
        m.update(s.encode("utf-8"))
    return m


def candidate_pairs(shs: Sequence[frozenset[str]]) -> list[tuple[int, int, float]]:
    """(i, j, Jaccard chính xác) cho mọi ứng viên LSH có J >= cận dưới review_band. LSH chỉ lọc, không quyết."""
    p = policy()
    low = p["review_band"][0]
    lsh = MinHashLSH(threshold=low, num_perm=p["num_perm"])
    mhs = {}
    for i, sh in enumerate(shs):
        if sh:
            mhs[i] = _minhash(sh)
            lsh.insert(str(i), mhs[i])
    out = []
    for i, m in mhs.items():
        for key in lsh.query(m):
            j = int(key)
            if j > i:
                jac = exact_jaccard(shs[i], shs[j])
                if jac >= low:
                    out.append((i, j, jac))
    return sorted(out)
