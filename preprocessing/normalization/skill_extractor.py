# -*- coding: utf-8 -*-
"""preprocessing.normalization.skill_extractor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Trích ngược kỹ năng ESCO từ VĂN BẢN JD sạch khi sàn không gắn tag cấu trúc
(Đề xuất S-3 trong docs/preprocessing/normalization/01_text_skill_processing_contract.md).

Bằng chứng dữ liệu (audit R2 26/10/2026):
  - TopDev `skills_list` trống 55,5%; CareerViet trống 21,9% — bệnh án EDA yêu cầu
    "bổ khuyết kỹ năng bằng từ điển chuẩn bóc tách ngược từ JD".
  - Mean esco_coverage_rate toàn 8 nguồn chỉ 0,197.

Chiến lược boundary-aware (KHÔNG phải substring mù):
  1. Token hóa JD sạch (`jd_clean_text` + `requirements_clean_text`).
  2. Index đảo ngược theo token-first của alias đã BỎ Dấu — chỉ xét alias
     length >= 3 ký tự (chặn 'ai'/'go'/'r'/'ba'/'pm' khớp giả trong tiếng Anh/Việt).
  3. Xác nhận ứng viên bằng regex ranh giới từ trên text bỏ dấu
     ('react js' != 'reactjs' nhưng cùng token-set -> khớp qua prepare text).
  4. Canonical dedup với tag đã có; kỹ năng trích được đánh dấu provenance.

Mặc định CHỈ kích hoạt khi bản ghi sparse (<= SPARSE_THRESHOLD kỹ năng chuẩn hóa)
để không ghi đè/chen lối tag chính thức của sàn (ranh giới O-2 Output Contract).
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

from preprocessing.normalization.skill_normalizer import (
    SkillNormalizer,
    get_normalizer,
    normalize_skill_key,
)

# Alias ngắn hơn ngưỡng này chỉ an toàn ở chế độ exact-tag, cấm dùng khi scan text
MIN_ALIAS_LEN = 3
# Số kỹ năng chuẩn hóa tối đa để bị coi là "thiếu tag" -> kích hoạt scan JD
SPARSE_THRESHOLD = 2

_PUNCT_SPLIT = re.compile(r"[^0-9a-z\u00c0-\u024f+#]+")

_text_scan_blocklist_cache: Optional[set] = None


def get_text_scan_blocklist() -> set:
    """Đọc _meta.text_scan_blocklist tu từ điển ESCO (alias cam dung khi scan text)."""
    global _text_scan_blocklist_cache
    if _text_scan_blocklist_cache is None:
        import json
        from pathlib import Path

        p = Path(__file__).resolve().parents[2] / "data" / "dictionaries" / "esco_it_skills.json"
        meta = json.loads(p.read_text(encoding="utf-8")).get("_meta", {})
        # Pool key da BO DAU ('chi tiet') -> blocklist cung phai bo dau + nen chuoi
        _text_scan_blocklist_cache = {
            _deaccent_lower(normalize_skill_key(t)) for t in meta.get("text_scan_blocklist", [])
        }
    return _text_scan_blocklist_cache


def _deaccent_lower(s: str) -> str:
    import unicodedata

    nfkd = unicodedata.normalize("NFD", str(s).lower())
    base = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return base.replace("đ", "d").replace("Đ", "D")


def _alias_tokens(alias_norm: str) -> List[str]:
    """'react native' -> ['react','native']; 'nodejs' -> ['nodejs'].
    Giữ token ky thuat co dau ('node.js' -> ['node.js']) vi text chuan hoa
    giu dau cham; dong thoi index ca phien ban tach ('node') tu pool key."""
    return [t for t in re.split(r"[^0-9a-z+#.\-]+", alias_norm) if t]


class SkillExtractor:
    """Boundary-aware ESCO scanner tái dùng toàn bộ index của SkillNormalizer."""

    def __init__(self, normalizer: Optional[SkillNormalizer] = None):
        self.nz = normalizer or get_normalizer()

        # Gộp canonical + alias thành pool key đã normalize_skill_key (nén . - _ / space).
        # Bien the tach dau cach ('java script') do chinh từ điển khai bao — khong doan
        # tach tu dong de tranh 'node' + 'js' kieu vuot ngoac.
        pool: Dict[str, str] = {}
        for canon in self.nz.skills:
            pool[normalize_skill_key(canon)] = canon
        for a, canon in self.nz._alias_by_key.items():
            pool.setdefault(a, canon)
        # Alias THO từ điển giu khoang trang ban dau ('java script', 'gitlab ci',
        # 'aws cloud'); cum noi bang '/', '+', '&', ',' tach thanh tung phan ('mysql/mariadb').
        for canon, meta in self.nz.skills.items():
            parts = [canon]
            for raw_a in meta.get("aliases", []):
                parts.extend(p for p in re.split(r"[/+&,]", str(raw_a)) if p.strip())
            for p in parts:
                base = _deaccent_lower(p).strip()
                variants = [re.sub(r"\s+", " ", base).strip()]          # giu 'node.js' nguyên dau
                spaced = re.sub(r"[^0-9a-z+#\-]+", " ", base)            # bien the tach 'node js'
                spaced = re.sub(r"\s+", " ", spaced).strip()
                variants.append(spaced)
                for v in variants:
                    if v:
                        pool.setdefault(v, canon)

        # Loại blacklist, alias quá ngắn, va text_scan_blocklist tu _meta cua
        # từ điển (FP do tren JD that: 'cham soc' > 'soc'/SIEM, 'sap xep' > 'sap'/ERP)
        block = get_text_scan_blocklist()
        # Pool key giu khoang trang ('ky nang giao tiep'), blocklist normalize
        # da nen chuoi -> sinh ca 2 dang (nen + tach dau cach) de so sanh
        block_nospace = set(block)
        for b in block:
            block_nospace.add(b.replace(" ", ""))
            block_nospace.add(_deaccent_lower(b))
        candidates: Dict[str, str] = {}
        for key, canon in pool.items():
            if not key or key in self.nz._blacklist:
                continue
            if len(key) < MIN_ALIAS_LEN:
                continue
            if key in block or re.sub(r"\s+", "", key) in block_nospace:
                continue
            candidates[key] = canon

        # Text ứng viên để khớp: bỏ dấu + tách punctuation giữ token '#', '+', '.'
        self._first_token_index: Dict[str, List[str]] = defaultdict(list)
        self._key_deaccent: Dict[str, str] = {}
        for key, canon in candidates.items():
            da = _deaccent_lower(canon)  # so khớp trên text thật theo canonical có dấu
            self._key_deaccent[key] = da
            toks = _alias_tokens(key)
            if toks:
                self._first_token_index[toks[0]].append(key)
        self._canon_by_key = candidates

    # ------------------------------------------------------------------
    @staticmethod
    def _prepare_text(text: str) -> str:
        """Bỏ dấu + lowercase; tách '/' thành khoảng trắng ('PHP/MySQL' ->
        'php mysql' de ca hai token duoc index hoa), giu '.' '-' noi token
        ky thuat ('node.js', 'full-stack')."""
        t = _deaccent_lower(text)
        t = re.sub(r"\s*[/+&]\s*", " ", t)
        return " " + t + " "

    def extract(self, text: Optional[str]) -> List[str]:
        """Trả về canonical ESCO skills phát hiện trong text (boundary-aware)."""
        if not text or not str(text).strip():
            return []
        prepared = self._prepare_text(str(text))

        # Bước 1: ứng viên qua inverted index token-first (tach punctuation cua text)
        words = re.findall(r"[0-9a-z+#.\-/]+", prepared)
        cand_keys = set()
        for w in words:
            for key in self._first_token_index.get(_alias_tokens(w)[0] if _alias_tokens(w) else "", ()):
                cand_keys.add(key)
        if not cand_keys:
            return []

        # Bước 2: xác nhận ranh giới từ cho cả cụm multi-token
        hits: Dict[str, str] = {}  # canonical -> key khớp dài nhất
        taken_spans: List[tuple] = []
        for key in sorted(cand_keys, key=len, reverse=True):  # ALIAS DAI NHAT THANG
            toks = _alias_tokens(key)
            pattern = r"(?<![0-9a-z+#])" + r"[\s\.\-/]?".join(map(re.escape, toks)) + r"(?![0-9a-z+#])"
            m = re.search(pattern, prepared)
            if m and any(s < m.end() and m.start() < e for s, e in taken_spans):
                m = None  # vung text nay do alias dai hon chiếm rồi (chong 'git' trong 'gitlab ci')
            if m:
                taken_spans.append((m.start(), m.end()))
                canon = self._canon_by_key[key]
                prev = hits.get(canon)
                if prev is None or len(key) > len(prev):
                    hits[canon] = key
        return list(hits)


# ---------------------------------------------------------------------------
# Singleton & API cấp bản ghi
# ---------------------------------------------------------------------------
_extractor: Optional[SkillExtractor] = None


def get_extractor() -> SkillExtractor:
    global _extractor
    if _extractor is None:
        _extractor = SkillExtractor()
    return _extractor


def extract_skills_from_text(text: Optional[str]) -> List[str]:
    """Hàm tiện ích: boundary-aware ESCO scan trên một khối text."""
    return get_extractor().extract(text)


def augment_record(record: Dict[str, Any], sparse_threshold: int = SPARSE_THRESHOLD) -> Dict[str, Any]:
    """Bù khuyết skills sau khi `process_record_skills` đã chạy (đọc cột chuẩn hóa).

    Chỉ kích hoạt khi `skills_standardized` <= sparse_threshold (mặc định 2).
    Thêm 2 cột mới, KHÔNG sửa các cột có sẵn:
      - `skills_extracted_from_jd`: canonical skills chỉ tìm thấy trong JD.
      - `skills_source`: 'tags' | 'tags+jd' | 'jd_scan' | 'none'.
    """
    std = list(record.get("skills_standardized") or [])
    if len(std) > sparse_threshold:
        record.setdefault("skills_extracted_from_jd", [])
        record.setdefault("skills_source", "tags" if std else "none")
        return record

    jd = record.get("jd_clean_text") or ""
    req = record.get("requirements_clean_text") or ""
    benefits = " ".join(str(b) for b in record.get("benefits_list") or [])
    found = get_extractor().extract(f"{jd}\n{req}\n{benefits}")

    extra = [c for c in found if c not in std]
    record["skills_extracted_from_jd"] = extra
    if extra:
        record["skills_standardized"] = std + extra
        # Phân loại lại nhóm cho phần trích thêm
        nz = get_normalizer()
        for c in extra:
            meta = nz.skills.get(c)
            if meta:
                bucket = record.setdefault(meta["type"], [])
                if c not in bucket:
                    bucket.append(c)
        record["skills_source"] = ("tags+jd" if std else "jd_scan")
    else:
        record["skills_source"] = "tags" if std else "none"
    return record
