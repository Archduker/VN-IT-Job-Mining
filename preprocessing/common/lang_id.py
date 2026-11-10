# -*- coding: utf-8 -*-
"""Nhận diện ngôn ngữ JD bằng fastText lid.176 (PH3 S4). Không tự tải model, thiếu file thì báo lỗi rõ ràng.

Model: models/fasttext/lid.176.bin (git-ignored; tải bằng scripts/download_lid_model.py), hoặc đường dẫn
trong biến môi trường LID_MODEL_PATH. Nhãn ra: vi / en / other.
"""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path

from preprocessing.common import REPO_ROOT

DEFAULT_MODEL = REPO_ROOT / "models" / "fasttext" / "lid.176.bin"
CONF_MIN = 0.6      # dưới ngưỡng này thành "other" (PH3 C5)
MAX_CHARS = 1000    # chỉ cần đầu văn bản (PH3 C5)


def model_path() -> Path:
    return Path(os.environ.get("LID_MODEL_PATH") or DEFAULT_MODEL)


def model_sha256(path: Path | None = None) -> str:
    h = hashlib.sha256()
    with (path or model_path()).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@lru_cache(maxsize=1)
def _model():
    import fasttext

    fasttext.FastText.eprint = lambda *_: None  # bỏ cảnh báo load_model

    p = model_path()
    if not p.is_file():
        raise FileNotFoundError(f"thiếu model fastText {p}: chạy python scripts/download_lid_model.py")
    return fasttext.load_model(str(p))


def detect_lang(text: str | None) -> tuple[str, float]:
    """(lang, conf). Văn bản rỗng -> ("other", 0.0). Không lùi về luật cũ nếu thiếu model."""
    s = " ".join((text or "")[:MAX_CHARS].split())
    if not s:
        return "other", 0.0
    # gọi f.predict trực tiếp: Model.predict của gói fasttext hỏng với numpy 2
    prob, label_ = _model().f.predict(s, 1, 0.0, "strict")[0]
    conf = min(1.0, round(float(prob), 4))
    label = label_.replace("__label__", "")
    return (label if label in ("vi", "en") and conf >= CONF_MIN else "other"), conf
