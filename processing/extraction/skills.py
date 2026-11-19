# -*- coding: utf-8 -*-
"""Bước 8 PH8: trích kỹ năng bằng Aho-Corasick (K8.1-K8.6).

- Đường an toàn: khóa = fold(alias) dài >= 4 ký tự hoặc có `# + .`, quét trên văn bản fold (độ dài từng ký tự giữ nguyên nên span ánh xạ về văn bản gốc).
- Đường alias ngắn (K3): chỉ các dạng `approved: true` trong short_aliases.json, khớp phân biệt hoa thường trên văn bản gốc. Chưa duyệt = không dùng.
- K8.15 (từ 18/11): từ điển `skills_v2.json` (`load_skills_v2`, `matcher_from_v2`). Thêm hai luật: chỗ khớp fold có dấu
  phải đúng dạng có dấu của alias (`alias_forms`; "công nghệ" không khớp "nghe"); alias ngắn ≤ 3 ký tự đứng trước
  "-" + chữ cái bị bỏ ("Go-live"). Cụm `not_skill` loại `degree` là cụm chặn: khớp dài nhất thắng rồi bị bỏ, nên
  "học máy" trong "Khoa học máy tính" không ra kỹ năng.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import ahocorasick

from preprocessing.deduplication.text_norm import fold
from processing.extraction.sections import DICT_DIR, Bullet, load_approved

TAXONOMY_PATH = DICT_DIR / "skills_taxonomy_230.json"
SKILLS_V2_PATH = DICT_DIR / "skills_v2.json"
BLOCK = "__block__"
SHORT_ALIASES_PATH = DICT_DIR / "short_aliases.json"
BOUNDARY = re.compile(r"[a-z0-9_#+]")
GO_LIVE = re.compile(r"-[^\W\d_]")
LEVEL_BY_SECTION = {"yeu_cau": ("required", 1.0), "mo_ta": ("required", 1.0), "khac": ("required", 1.0),
                    "uu_tien": ("preferred", 0.5)}  # phuc_loi: không quét (K8.5)
LEVEL_RANK = {"preferred": 0, "required": 1}


@dataclass(frozen=True)
class Hit:
    slug: str
    start: int
    end: int
    path: str  # safe | short


@lru_cache(maxsize=None)
def _fold_char(c: str) -> str:
    if c.isspace():
        return " "
    r = fold(c)
    return r[0] if r else c


def fold_aligned(text: str) -> str:
    """fold từng ký tự: cùng độ dài với text để span khớp."""
    return "".join(map(_fold_char, text))


def is_safe_key(key: str) -> bool:
    return len(key) >= 4 or any(ch in key for ch in "#+.")


def load_taxonomy(path: Path = TAXONOMY_PATH) -> List[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["skills"]


def load_skills_v2(path: Path = SKILLS_V2_PATH) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("_meta", {}).get("approved") is not True:
        raise ValueError(f"skills_v2.json chưa được duyệt ({path}): chạy scripts/review_skills_v2.py và chờ người dùng duyệt")
    return d


def matcher_from_v2(d: dict) -> "SkillMatcher":
    """Matcher của bước 08 từ skills_v2 (K8.15). Cụm bằng cấp không trùng alias kỹ năng thành cụm chặn."""
    tax = [{"slug": s["slug"], "name": s["name"], "group": s["group"], "kind": s["kind"], "parent": s.get("parent"),
            "type": s.get("type"), "aliases": s["aliases"]} for s in d["skills"]]
    skill_keys = {a for s in d["skills"] for a in s["aliases"]}
    forms = {a: f for s in d["skills"] for a, f in s.get("alias_forms", {}).items()}
    blockers = []
    for n in d.get("not_skill", []):
        if n["reason"] != "degree" or n["key"] in skill_keys:
            continue
        blockers.append(n["key"])
        f = " ".join(unicodedata.normalize("NFC", n["display"]).lower().split())
        if not f.isascii() and " ".join(fold(f).split()) == n["key"]:
            forms[n["key"]] = f
    tax.append({"slug": BLOCK, "name": BLOCK, "group": None, "kind": None, "parent": None, "aliases": blockers})
    short = [(s["slug"], f) for s in d["skills"] for f in s["short_aliases"]]
    return SkillMatcher(tax, short, forms)


def load_short_forms(path: Path = SHORT_ALIASES_PATH) -> List[Tuple[str, str]]:
    return [(i["slug"], f) for i in load_approved(path) for f in i["forms"]]


def alias_owners(taxonomy: Sequence[dict]) -> Dict[str, set]:
    owners: Dict[str, set] = defaultdict(set)
    for s in taxonomy:
        for a in {*([s["canonical"]] if s.get("canonical") else []), *s["aliases"]}:
            owners[fold(a)].add(s["slug"])
    return owners


class SkillMatcher:
    def __init__(self, taxonomy: Sequence[dict], short_forms: Iterable[Tuple[str, str]] = (),
                 forms: Optional[Dict[str, str]] = None):
        """forms: alias fold -> dạng gốc có dấu (viết thường, NFC). None = không áp luật dấu (từ điển cũ)."""
        self.forms = forms
        self.taxonomy = {s["slug"]: s for s in taxonomy}
        owners = alias_owners(taxonomy)
        self.conflicts = {k: sorted(v) for k, v in owners.items() if len(v) > 1}
        self.safe = {k: next(iter(v)) for k, v in owners.items() if len(v) == 1 and is_safe_key(k)}
        self.ac = ahocorasick.Automaton()
        for k, slug in self.safe.items():
            self.ac.add_word(k, (k, slug))
        self.has_ac = bool(self.safe)
        if self.has_ac:
            self.ac.make_automaton()
        self.short_map = {}
        for slug, form in short_forms:
            if slug not in self.taxonomy:
                raise ValueError(f"short_aliases: slug lạ {slug!r}")
            self.short_map[form] = slug
        forms = sorted(self.short_map, key=lambda f: (-len(f), f))
        self.short_re = re.compile(r"(?<![\w#+])(?:" + "|".join(map(re.escape, forms)) + r")(?![\w#+])") if forms else None

    def find(self, text: str) -> List[Hit]:
        cands = []
        if self.has_ac:
            f = fold_aligned(text)
            for end, (key, slug) in self.ac.iter(f):
                s, e = end - len(key) + 1, end + 1
                if (s > 0 and BOUNDARY.match(f[s - 1])) or (e < len(f) and BOUNDARY.match(f[e])):
                    continue
                if self.forms is not None and not self._accent_ok(text[s:e], key):
                    continue
                cands.append(Hit(slug, s, e, "safe"))
        if self.short_re:
            for m in self.short_re.finditer(text):
                if len(m.group()) <= 3 and GO_LIVE.match(text, m.end()):
                    continue
                cands.append(Hit(self.short_map[m.group()], m.start(), m.end(), "short"))
        kept: List[Hit] = []  # dài nhất trước, không chồng nhau
        for h in sorted(cands, key=lambda h: (-(h.end - h.start), h.start, h.path)):
            if all(h.end <= k.start or h.start >= k.end for k in kept):
                kept.append(h)
        return sorted((h for h in kept if h.slug != BLOCK), key=lambda h: h.start)

    def _accent_ok(self, span: str, key: str) -> bool:
        span = " ".join(unicodedata.normalize("NFC", span).lower().split())
        return span.isascii() or span == self.forms.get(key)

    def meta_slug(self, name: str):
        name = str(name).strip()
        key = " ".join(fold(name).split())
        slug = self.safe.get(key)
        if slug and self.forms is not None and not self._accent_ok(name, key):
            slug = None
        slug = slug or self.short_map.get(name)
        return None if slug == BLOCK else slug


def short_alias_candidates(taxonomy: Sequence[dict]) -> List[dict]:
    """Alias bị đưa khỏi đường fold (K3). `forms` là gợi ý dạng viết hoa, người dùng sửa trước khi duyệt."""
    owners = alias_owners(taxonomy)
    by_slug = {s["slug"]: s for s in taxonomy}
    out = []
    for key in sorted(owners):
        if is_safe_key(key):
            continue
        for slug in sorted(owners[key]):
            canon = by_slug[slug]["canonical"]
            forms = list(dict.fromkeys([key.upper(), *( [canon] if fold(canon) == key else [])]))
            out.append({"alias": key, "slug": slug, "forms": forms, "ambiguous": len(owners[key]) > 1, "approved": False})
    return out


def extract_skills(bullets: Sequence[Bullet], matcher: SkillMatcher, meta: Iterable[str] = ()):
    """Trả (rows, hits_by_bullet). rows: mỗi kỹ năng một dòng, giữ level cao nhất, cộng n_mentions."""
    agg: Dict[str, dict] = {}
    hits_by_bullet: Dict[int, List[Hit]] = {}
    for b in bullets:
        if b.section not in LEVEL_BY_SECTION:
            continue
        level, weight = LEVEL_BY_SECTION[b.section]
        hits = matcher.find(b.text)
        if hits:
            hits_by_bullet[b.idx] = hits
        for h in hits:
            r = agg.get(h.slug)
            if r is None:
                agg[h.slug] = {"slug": h.slug, "level": level, "weight": weight, "section": b.section, "via": "text", "n_mentions": 1}
            else:
                r["n_mentions"] += 1
                if LEVEL_RANK[level] > LEVEL_RANK[r["level"]]:
                    r.update(level=level, weight=weight, section=b.section)
    for name in meta:  # K4: kỹ năng từ metadata, tách khỏi F1 bằng via=meta
        slug = matcher.meta_slug(str(name))
        if slug and slug not in agg:
            agg[slug] = {"slug": slug, "level": "required", "weight": 1.0, "section": None, "via": "meta", "n_mentions": 1}
    rows = []
    for slug in sorted(agg):
        t = matcher.taxonomy[slug]
        rows.append({**agg[slug], "skill": t.get("canonical") or t.get("name"), "kind": t.get("kind"),
                     "parent": t.get("parent"), "type": t.get("type")})
    return rows, hits_by_bullet


SKILL_VIEWS = ("all", "tool", "concept", "soft")


def skill_view(job_skills, view: str):
    """Ba góc nhìn kỹ năng của docs/target/06_yeu_cau_du_lieu.md mục 2, một định nghĩa cho bước 10, Silver và Mining.

    - `tool` (K-tool): kỹ thuật, `type = tool` (K8.17); kỹ năng chưa có nhãn duyệt (`type` null) không vào.
    - `concept` (K-concept): kỹ thuật, `type = concept`.
    - `soft` (K-soft): `kind` là `soft` hoặc `language`.
    - `all`: mọi dòng.
    Mọi `via` (văn bản gốc, bản dịch, thẻ sàn) và mọi phần JD đều giữ (quyết định 1, 2 ngày 19/11).
    """
    if view not in SKILL_VIEWS:
        raise ValueError(f"view lạ {view!r}; chọn một trong {SKILL_VIEWS}")
    if view == "all":
        return job_skills
    if view == "soft":
        return job_skills[job_skills["kind"].isin(["soft", "language"])]
    if "type" not in job_skills.columns:
        raise ValueError("job_skills thiếu cột `type`: chạy lại bước 08 với skills_v2 ≥ 2.1.0 (K8.17)")
    return job_skills[(job_skills["kind"] == "technical") & (job_skills["type"] == view)]
