# -*- coding: utf-8 -*-
"""Bước 7 PH8: tách section/bullet (luật S7.1-S7.5, docs/spec/preprocessing/spec/PH8_*.md).

Từ điển tiêu đề và cụm "ưu tiên" chỉ gồm mục `approved: true` trong file JSON (file ứng viên do script sinh, người dùng duyệt).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from preprocessing.common.gold import SECTIONS
from preprocessing.deduplication.text_norm import fold

DICT_DIR = Path(__file__).resolve().parents[1] / "dictionaries"
HEADINGS_PATH = DICT_DIR / "section_headings.json"
CUES_PATH = DICT_DIR / "priority_cues.json"
MAX_HEADING_WORDS = 6


@dataclass(frozen=True)
class Bullet:
    idx: int
    section: str
    text: str
    rule: str  # S7.2 mặc định theo trường | S7.3 theo tiêu đề | S7.4 theo cụm ưu tiên


def load_approved(path: Path) -> List[dict]:
    """Chỉ các mục approved=true; file thiếu = chưa duyệt gì."""
    if not Path(path).exists():
        return []
    return [i for i in json.loads(Path(path).read_text(encoding="utf-8")).get("items", []) if i.get("approved") is True]


def load_headings(path: Path = HEADINGS_PATH) -> Dict[str, str]:
    out = {}
    for i in load_approved(path):
        if i["section"] not in SECTIONS:
            raise ValueError(f"section lạ trong {path}: {i['section']!r}")
        out[fold(i["phrase"]).rstrip(":").strip()] = i["section"]
    return out


def load_cues(path: Path = CUES_PATH) -> List[str]:
    return [fold(i["phrase"]) for i in load_approved(path)]


def _starts_with_cue(key: str, cues: Iterable[str]) -> bool:
    return any(key == c or key.startswith(c + " ") or key.startswith(c + ":") for c in cues)


def split_sections(description, requirements, benefits=None, headings: Dict[str, str] | None = None,
                   cues: Sequence[str] = ()) -> List[Bullet]:
    headings = headings or {}
    out: List[Bullet] = []
    for field, default in ((description, "mo_ta"), (requirements, "yeu_cau"), (benefits, "phuc_loi")):
        sec = default
        for line in str(field if field is not None else "").split("\n"):
            text = line.strip()
            if text.startswith("- "):
                text = text[2:].strip()
            if not text:
                continue
            key = fold(text).rstrip(":").strip()
            if len(key.split()) <= MAX_HEADING_WORDS:
                if key in headings:  # S7.3: tiêu đề đổi section, không thành bullet
                    sec = headings[key]
                    continue
                if text.endswith(":") and _starts_with_cue(key, cues):
                    sec = "uu_tien"
                    continue
            if _starts_with_cue(key, cues):
                out.append(Bullet(len(out), "uu_tien", text, "S7.4"))
            else:
                out.append(Bullet(len(out), sec, text, "S7.2" if sec == default else "S7.3"))
    return out
