# -*- coding: utf-8 -*-
"""preprocessing.normalization.skill_normalizer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Chuẩn hóa danh mục kỹ năng về Từ điển ESCO IT Skills (SD3) và phân 3 nhóm:
``hard_skills`` / ``domain_knowledge`` / ``soft_skills``.

Chiến lược 3 tầng (offline, deterministic, không phụ thuộc embedding/API):
  Tầng 1 - Alias exact  : normalize key (NFC, lowercase, nén `. - / space`) rồi
                          khớp từ điển với quy tắc ALIAS DÀI NHẤT THẮNG
                          (tránh "java" cướp "JavaScript", "c" cướp "C++").
  Tầng 2 - Fuzzy         : difflib SequenceMatcher >= FUZZY_THRESHOLD map biến thể
                          đánh máy ("Reactj", "Kubernates"); cờ `fuzzy_matched`.
  Tầng 3 - Giữ nguyên    : kỹ năng thật ngoài từ điển giữ nguyên nhãn gốc đã clean
                          (tôn trọng ranh giới CẤM mất nhãn gốc), gắn `matched=False`.

Đầu vào : `skills_list` list[str] thô từ Staging (Phúc) + text JD sạch (Phát).
Đầu ra  : `skills_standardized`, `hard_skills`, `domain_knowledge`, `soft_skills`,
          `skills_unmatched`, `esco_coverage_rate`.
"""

from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Vị trí từ điển: đi từ file này lên 2 cấp (preprocessing/normalization -> project root)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
ESCO_DICT_PATH = _PROJECT_ROOT / "data" / "dictionaries" / "esco_it_skills.json"
BLACKLIST_PATH = _PROJECT_ROOT / "data" / "dictionaries" / "skills_blacklist.json"

FUZZY_THRESHOLD = 0.86
# Câu tiếng Việt dài (có dấu) dễ ăn ratio giả với phrase từ điển gần nghĩa ->
# chỉ fuzzy khi chuỗi là thuật ngữ/giới từ ngắn, không phải cả mệnh đề.
FUZZY_MIN_TOKEN_LEN = 6   # bỏ qua term/trust ngắn ("c", "go", "r", "ba", "pm")
FUZZY_MAX_WORDS = 4       # vượt 4 từ được coi là mệnh đề, giữ nguyên Tầng 3


def _is_ascii_term(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False

# Token phân tách đa kỹ năng trong 1 tag (VD: "Java/Spring Boot", "HTML, CSS")
# Lưu ý: KHÔNG cắt mù trước — chỉ split khi cả tag không khớp từ điển (bảo vệ
# "C/C++", "UI/UX", "CI/CD", "QA/QC" khỏi bị xé đôi).
_MULTI_SKILL_SPLIT = re.compile(r"\s*[,;]\s*|\s*/\s*(?=[A-Z])|\s+\+\s+")


def normalize_skill_key(raw: Optional[str]) -> str:
    """Chuẩn hóa key so khớp: NFC → lowercase → nén ký tự phân cách.

    Bỏ toàn bộ `. - _ /` và khoảng trắng: "React.js" == "React JS" == "ReactJS" ==
    "reactjs"; "Node.js" == "nodejs". Giữ nguyên dấu tiếng Việt (skill "Tự học",
    "Điện toán đám mây" là nhãn hợp lệ trong ESCO dict).
    """
    if raw is None:
        return ""
    s = unicodedata.normalize("NFC", str(raw)).strip().lower()
    s = s.replace("&amp;", "&")
    s = re.sub(r"[./\-_]", "", s)
    s = re.sub(r"\s+", "", s)
    return s


class SkillNormalizer:
    """Bộ chuẩn hóa kỹ năng ESCO đơn-instance (load từ điển 1 lần, thread-safe đọc)."""

    def __init__(self, dict_path: Path = ESCO_DICT_PATH, blacklist_path: Path = BLACKLIST_PATH):
        payload = json.loads(dict_path.read_text(encoding="utf-8"))
        self.skills: Dict[str, Dict[str, Any]] = payload["skills"]

        # canonical key -> tên chuẩn
        self._canonical_by_key: Dict[str, str] = {}
        # alias key -> (tên chuẩn, độ dài alias gốc để ưu tiên dài nhất)
        aliases: List[Tuple[str, str, int]] = []

        for canonical, meta in self.skills.items():
            self._canonical_by_key[normalize_skill_key(canonical)] = canonical
            for alias in meta.get("aliases", []):
                nk = normalize_skill_key(alias)
                if nk and nk not in self._canonical_by_key:
                    aliases.append((nk, canonical, len(str(alias))))

        # Ưu tiên alias dài nhất khi 2 alias bao nhau ("react native" > "react")
        self._alias_by_key: Dict[str, str] = {}
        for nk, canonical, _ln in sorted(aliases, key=lambda x: x[2]):
            self._alias_by_key[nk] = canonical

        bl = json.loads(blacklist_path.read_text(encoding="utf-8"))
        self._blacklist = {normalize_skill_key(x) for x in bl["blacklist"]}

        # Index phục vụ fuzzy: key chuẩn hóa -> canonical (only ASCII-ish terms)
        self._fuzzy_index: Dict[str, str] = {}
        for nk, canon in list(self._canonical_by_key.items()) + list(self._alias_by_key.items()):
            self._fuzzy_index.setdefault(nk, canon)

    # ---------------- so khớp Tầng 1/2 ----------------
    def _fuzzy(self, key: str) -> Optional[str]:
        """Fuzzy chỉ áp cho THUẬT NGỮ ASCII ngắn (đánh máy sai biến thể công nghệ:
        "Reactj", "Kubernates"). Câu tiếng Việt/mệnh đề dài bị loại để tránh
        khớp giả với phrase từ điển ("giao tiếp tốt" ~ "giao tiếp")."""
        if len(key) < FUZZY_MIN_TOKEN_LEN or not _is_ascii_term(key):
            return None
        if len(str(key).split()) > FUZZY_MAX_WORDS:
            return None
        best, best_ratio = None, 0.0
        for nk, canon in self._fuzzy_index.items():
            if len(nk) < FUZZY_MIN_TOKEN_LEN or abs(len(nk) - len(key)) > 4:
                continue
            ratio = SequenceMatcher(None, key, nk).ratio()
            if ratio > best_ratio:
                best, best_ratio = canon, ratio
        return best if best_ratio >= FUZZY_THRESHOLD else None

    def match_one(self, raw_skill: str) -> List[Dict[str, Any]]:
        """Map 1 tag kỹ năng -> danh sách metadata ESCO.

        - Tag khớp thẳng (cả cụm) -> [1 hit].
        - Tag chưa khớp nhưng tách được đa kỹ năng (",", " + ", "/ Hoa) -> [n hits
          đã khớp] (bảo vệ "C/C++", "UI/UX", "CI/CD" khỏi bị xé đôi vì chúng khớp
          thẳng cả cụm trước khi split).
        - Blacklist/rỗng -> [].
        - Không khớp và không tách được -> [hit unmatched giữ nhãn gốc] (Tầng 3).
        """
        hits = self._match_atom(raw_skill)
        if hits and hits[0]["matched"]:
            return hits
        if not hits:
            return []  # blacklist / rỗng

        # Tag chưa khớp — thử tách đa kỹ năng trên CHUỖI GỐC (key normalize đã
        # nén hết dấu "/" nên không thể split từ key)
        pieces = [p.strip() for p in _MULTI_SKILL_SPLIT.split(str(raw_skill).strip()) if p.strip()]
        if len(pieces) > 1:
            sub_hits = [h for p in pieces for h in self._match_atom(p) if h and h["matched"]]
            if sub_hits:
                return sub_hits

        # Tầng 2 - Fuzzy: chỉ khi exact cả tag và exact từng mảnh đều thất bại
        return self._match_fuzzy_atom(raw_skill) or hits

    def _match_atom(self, raw_skill: str) -> List[Dict[str, Any]]:
        """Khớp 1 nguyên tử kỹ năng; trả [] nếu blacklist/rỗng, [hit] nếu có kết quả."""
        key = normalize_skill_key(raw_skill)
        if not key or key in self._blacklist:
            return []

        canonical = (
            self._canonical_by_key.get(key)
            or self._alias_by_key.get(key)
        )
        if canonical is None:
            return [{
                "original": str(raw_skill).strip(),
                "canonical": str(raw_skill).strip(),
                "type": "hard_skills",
                "matched": False,
                "fuzzy_matched": False,
            }]
        meta = self.skills[canonical]
        return [{
            "original": str(raw_skill).strip(),
            "canonical": canonical,
            "type": meta["type"],
            "matched": True,
            "fuzzy_matched": False,
        }]

    def _match_fuzzy_atom(self, raw_skill: str) -> List[Dict[str, Any]]:
        """Tầng 2 (fuzzy) — CHỈ chạy sau khi exact cả tag lẫn split đa skill thất bại,
        tránh 'Java/Spring Boot' bị ăn fuzzy giả thành 'Spring Boot' đơn lẻ."""
        key = normalize_skill_key(raw_skill)
        if not key or key in self._blacklist:
            return []
        canonical = self._fuzzy(key)
        if canonical is None:
            return []
        meta = self.skills[canonical]
        return [{
            "original": str(raw_skill).strip(),
            "canonical": canonical,
            "type": meta["type"],
            "matched": True,
            "fuzzy_matched": True,
        }]

    # ---------------- API cấp bản ghi ----------------
    def normalize_list(self, skills: Optional[List[str]]) -> Dict[str, Any]:
        """Chuẩn hóa `skills_list` thô -> cấu trúc 3 nhóm ESCO (SD3).

        Chống trùng tuyệt đối theo canonical (DoD: không còn trùng do hoa/thường
        hay dấu chấm), giữ lần xuất hiện đầu tiên.
        """
        result: Dict[str, Any] = {
            "skills_standardized": [],
            "hard_skills": [],
            "domain_knowledge": [],
            "soft_skills": [],
            "skills_unmatched": [],
            "skills_original": list(skills or []),
            "esco_coverage_rate": 0.0,
        }
        seen = set()
        matched_count = 0
        total = 0

        for tag in skills or []:
            hits = self.match_one(tag)
            if not hits:
                continue
            for hit in hits:
                total += 1
                canon = hit["canonical"]
                if canon in seen:
                    continue
                seen.add(canon)
                result["skills_standardized"].append(canon)
                result[hit["type"]].append(canon)
                if hit["matched"]:
                    matched_count += 1
                else:
                    result["skills_unmatched"].append(canon)

        # hard_skills hiển thị đầy đủ, domain/soft suy ra từ type đã gán
        result["esco_coverage_rate"] = round(matched_count / total, 3) if total else 0.0
        return result


# ---------------------------------------------------------------------------
# Singleton lazy-load dùng cho hàm cấp module / DataFrame
# ---------------------------------------------------------------------------
_normalizer: Optional[SkillNormalizer] = None


def get_normalizer() -> SkillNormalizer:
    global _normalizer
    if _normalizer is None:
        _normalizer = SkillNormalizer()
    return _normalizer


def normalize_skills(skills_list: Optional[List[str]]) -> Dict[str, Any]:
    """Hàm tiện ích cấp module: chuẩn hóa skills_list theo từ điển ESCO (SD3)."""
    return get_normalizer().normalize_list(skills_list)


def process_record_skills(flat: Dict[str, Any]) -> Dict[str, Any]:
    """Sinh các cột kỹ năng chuẩn trên MỘT bản ghi phẳng (in-place, không xóa cột gốc)."""
    norm = normalize_skills(flat.get("skills_list"))
    flat["skills_standardized"] = norm["skills_standardized"]
    flat["hard_skills"] = norm["hard_skills"]
    flat["domain_knowledge"] = norm["domain_knowledge"]
    flat["soft_skills"] = norm["soft_skills"]
    flat["skills_unmatched"] = norm["skills_unmatched"]
    flat["esco_coverage_rate"] = norm["esco_coverage_rate"]
    return flat


def normalize_dataframe(df, skills_column: str = "skills_list"):
    """Vectorize chuẩn hóa trên pandas DataFrame đầu ra Staging của Phúc.

    Thêm 6 cột chuẩn SD3; giữ nguyên cột `skills_list` gốc (ranh giới CẤM mất nhãn gốc).
    """
    norms = df[skills_column].apply(lambda s: get_normalizer().normalize_list(list(s) if s is not None else []))
    df = df.copy()
    for col in ("skills_standardized", "hard_skills", "domain_knowledge", "soft_skills", "skills_unmatched", "esco_coverage_rate"):
        df[col] = norms.apply(lambda d, c=col: d[c])
    return df
