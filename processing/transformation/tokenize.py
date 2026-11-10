# -*- coding: utf-8 -*-
"""Bước 9 PH8: tách từ underthesea với token giữ chỗ kỹ năng `sk_<slug>` và stopword (W9.1-W9.5).

Không dùng model. underthesea.word_tokenize dùng luật + CRF đóng gói sẵn, không tải tài nguyên khi chạy (đã kiểm với 9.5.0 trên máy dev).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Sequence

from underthesea import word_tokenize

from preprocessing.common import REPO_ROOT

PREFIX = "sk_"
STOPWORDS_PATH = REPO_ROOT / "preprocessing" / "encoding" / "assets" / "jd_stopwords_v1.json"


def load_general_stopwords(path: Path = STOPWORDS_PATH) -> frozenset:
    return frozenset(json.loads(Path(path).read_text(encoding="utf-8"))["words"])


def tokenize(text: str, hits: Sequence = ()) -> List[str]:
    """hits: Hit có start/end/slug trên chính `text`. Thay kỹ năng bằng sk_<slug> trước khi tách."""
    parts, pos = [], 0
    for h in sorted(hits, key=lambda h: h.start):
        parts += [text[pos:h.start], f" {PREFIX}{h.slug} "]
        pos = h.end
    parts.append(text[pos:])
    toks = word_tokenize("".join(parts))
    out = []
    for t in toks:
        t = t.strip()
        if t.startswith(PREFIX) or any(c.isalnum() for c in t):  # W9.3: bỏ dấu câu/ký hiệu, giữ số (W4)
            out.append(t if t.startswith(PREFIX) else t.lower())
    return out


def domain_stopwords(docs_tokens: Iterable[Sequence[str]], df_threshold: float = 0.6) -> dict:
    """Token có DF (theo JD) > ngưỡng; trả {token: DF}. Token sk_* không bao giờ là stopword."""
    df, n = Counter(), 0
    for toks in docs_tokens:
        n += 1
        df.update(set(toks))
    return {t: c / n for t, c in sorted(df.items()) if n and c / n > df_threshold and not t.startswith(PREFIX)}


def remove_stopwords(tokens: Sequence[str], general: Iterable[str] = (), domain: Iterable[str] = ()) -> List[str]:
    stop = set(general) | set(domain)
    return [t for t in tokens if t.startswith(PREFIX) or t not in stop]
