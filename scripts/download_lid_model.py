# -*- coding: utf-8 -*-
"""Tải fastText lid.176.bin từ URL chính thức vào models/fasttext/ (git-ignored) và ghi sha256. Không ghi R2."""

import hashlib
import sys
import urllib.request
from pathlib import Path

URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"
DEST = Path(__file__).resolve().parent.parent / "models" / "fasttext" / "lid.176.bin"

if __name__ == "__main__":
    if DEST.exists() and "--force" not in sys.argv:
        print(f"đã có {DEST}")
    else:
        DEST.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL, DEST)
    sha = hashlib.sha256(DEST.read_bytes()).hexdigest()
    DEST.with_name(DEST.name + ".sha256").write_text(f"{sha}  {DEST.name}\n")
    print("sha256", sha)
