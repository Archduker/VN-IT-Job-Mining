# -*- coding: utf-8 -*-
"""preprocessing.normalization.text_cleaner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Chuẩn hóa văn bản JD, tiêu đề, địa danh (63 tỉnh thành) cho Tầng Normalization.

Đầu vào : Cột text thô từ Staging (`raw_description_text`, `raw_requirements_text`,
          `job_title`, `raw_location_text`, `raw_work_mode`).
Đầu ra  : `jd_clean_text`, `requirements_clean_text`, `clean_job_title`,
          `primary_city`, `is_remote`.

Ranh giới (Ironclad Boundaries):
  - CẤM ghi đè nhãn gốc — mọi hàm chỉ SINH cột mới từ cột gốc, không mutate.
  - Strip HTML & ghép bullet fragmentation DELEGATE sang module của Anh Khoa
    (`preprocessing/transformation/html_cleaner.py`, `bullet_stitcher.py`)
    để đúng WBS Bước 2 — normalization chỉ tiêu thụ, không nhân bản logic.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Union

from preprocessing.transformation.html_cleaner import strip_html_tags
from preprocessing.transformation.bullet_stitcher import stitch_fragmented_bullets
from preprocessing.normalization.taxonomy_mapper import (  # noqa: F401 (tương thích ngược)
    classify_job_family,
    normalize_seniority,
)

# Emoji & ký tự điều khiển ẩn (bệnh án EDA: rác Unicode trong JD đa sàn)
_EMOJI_REGEX = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # blocks ký tự emoji hiện đại
    "\U00002600-\U000027BF"  # misc symbols + dingbats
    "\U0001F1E6-\U0001F1FF"  # cờ quốc kỳ
    "\U00002B00-\U00002BFF"
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # zero-width joiner
    "]+",
    flags=re.UNICODE,
)
_CONTROL_CHARS_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b\u200c\u2060\ufeff]")


def clean_job_title(title: Optional[str]) -> Optional[str]:
    """Làm sạch tiêu đề công việc.

    - Bỏ tag địa danh MỌI vị trí (đầu/giữa/cuối): `[HN]`, `[HCM]`, `(Hà Nội)`,
      `[Ho Chi Minh]`, `[Bình Dương]`... (bằng chứng data thật: TopCV đặt tag giữa
      title, ITviec dùng tên tiếng Anh không dấu).
    - Bỏ đuôi quảng cáo lương/thu nhập: `- Lương 20M`, `| Thu nhập cao`,
      `- Up to 30 triệu`, `(Lương Khởi Điểm Từ 45M)`...
    """
    if not title:
        return None

    s = str(title).strip()

    # 1. Tag địa danh trong ngoặc Vuông/Tròn — áp dụng MỌI vị trí trong chuỗi.
    #    Callback kiểm tra nội dung ngoặc CHỈ chứa nhãn địa danh + ký tự ngăn,
    #    chặn xóa nhầm ngoặc tech stack: `Developer (ReactJS/ NodeJS)` phải giữ.
    _LOC_ALT = r"\b(?:hn|hcm|hcmc|sg|dn|đn|hp|ct|sài gòn|saigon|ha noi|hà nội|ho chi minh|hồ chí minh|đà nẵng|da nang|bình dương|binh duong|toàn quốc|toan quoc|long an|đồng nai|dong nai|bắc ninh|bac ninh|hải phòng|hai phong|cần thơ|can tho|khánh hòa|khanh hoa|huế|hue)\b"

    def _strip_loc_brackets(m: "re.Match") -> str:
        inner = m.group(1).strip().lower()
        rest = re.sub(rf"(?:{ _LOC_ALT})", " ", inner, flags=re.UNICODE)
        rest = re.sub(r"[^\s]+", lambda w: "" if w.group(0) in {"tp", "thanh", "pho", "tp.", "tinh", "quan"} else w.group(0), rest)
        rest = rest.strip(" .,-/|()\t")
        # Sau khi trừ mọi nhãn địa danh + từ loại địa lý thờng mọn, phần còn lại
        # phải rỗng => đúng là tag location (ngoặc tech stack sẽ còn sót token)
        if rest == "":
            return " "
        return m.group(0)

    s = re.sub(r"[\[(]([^\[\]()]*)[\])]", _strip_loc_brackets, s, flags=re.IGNORECASE)

    # 2. Đuôi quảng cáo lương/thu nhập sau dấu ngăn - | • (tối đa 45 ký tự)
    s = re.sub(
        rf"[-–|•]\s*\(?\s*(?:lương|thu nhập|up\s*-?\s*to\b|upto\b|salary|signing bonus|review now|ngay|hấp dẫn)[^\[(]{{0,45}}?\)?\s*$",
        "",
        s,
        flags=re.IGNORECASE,
    )
    # 2b. Cả cụm ngoặc chứa lương ở cuối: "(Lương Khởi Điểm Từ 45M)"
    s = re.sub(r"\(\s*(?:lương|thu nh[àa]p|up to)[^)]{0,50}\)\s*$", "", s, flags=re.IGNORECASE)

    # 3. Ký tự điều khiển & emoji
    s = _CONTROL_CHARS_REGEX.sub(" ", s)
    s = _EMOJI_REGEX.sub(" ", s)
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\s([-–|•])\s*", r" \1 ", s).strip(" -–|•,")
    s = re.sub(r"\s{2,}", " ", s).strip(" -–|•,")
    return s.strip() or str(title).strip()


def strip_control_and_emoji(text: Optional[str]) -> Optional[str]:
    """Dọn ký tự điều khiển ẩn + emoji, giữ nguyên dấu câu tiếng Việt."""
    if text is None:
        return None
    s = _CONTROL_CHARS_REGEX.sub(" ", str(text))
    s = _EMOJI_REGEX.sub(" ", s)
    return s


def clean_jd_text(raw_text: Union[str, list, None]) -> Optional[str]:
    """Làm sạch một khối văn bản JD hoàn chỉnh (Mô tả / Yêu cầu / Phúc lợi).

    Pipeline 4 bước (theo Bệnh án EDA Trụ cột 1 & 2):
      1. Strip 100% thẻ HTML/CSS inline (TopDev 100% rác HTML) — delegate Khoa.
      2. Bullet Stitching: nối câu bị DOM selector cắt vụn (Vieclam24h/CareerViet)
         — delegate Khoa.
      3. Dọn emoji, ký tự điều khiển ẩn, non-breaking space.
      4. Nén khoảng trắng thừa đầu/cuỗi dòng.

    Returns:
        Chuỗi text sạch nhiều dòng, hoặc ``None`` nếu đầu vào rỗng/null.
    """
    if raw_text is None:
        return None

    if isinstance(raw_text, list):
        raw = "\n".join(str(x) for x in raw_text if x is not None)
    else:
        raw = str(raw_text)

    if not raw.strip():
        return None

    # 1. Strip HTML (chức năng của Bước 2 - Transformation, tái sử dụng trực tiếp)
    text = strip_html_tags(raw) or ""

    # 2.+3. Ghép câu bullet phân mảnh rồi dọn emoji/control ký tự
    stitched = stitch_fragmented_bullets(text.splitlines())
    cleaned_lines = []
    for line in stitched:
        line = strip_control_and_emoji(line) or ""
        line = line.replace("\xa0", " ")
        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        if line:
            cleaned_lines.append(line)

    result = "\n".join(cleaned_lines).strip()
    return result or None


# ---------------------------------------------------------------------------
# ĐỊA DANH — 63 tỉnh thành chuẩn Việt Nam (docs 04 §5) + cờ is_remote
# ---------------------------------------------------------------------------

from pathlib import Path as _Path

_PROVINCE_DICT_PATH = _Path(__file__).resolve().parents[2] / "data" / "dictionaries" / "vn_provinces.json"


def _deaccent(s: str) -> str:
    """Bỏ dấu tiếng Việt (NFD -> lọc combining + đ→d), phục vụ khớp alias không dấu."""
    import unicodedata

    nfkd = unicodedata.normalize("NFD", s)
    base = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return base.replace("đ", "d").replace("Đ", "D")


def _load_province_index() -> tuple:
    """(alias_sorted_desc, special_map, hubs) từ JSON — nạp 1 lần, cache module."""
    import json

    data = json.loads(_PROVINCE_DICT_PATH.read_text(encoding="utf-8"))
    alias: dict = {}
    for canonical, aliases in data["provinces"].items():
        keys = {canonical} | set(aliases)
        for a in keys:
            na = _deaccent(str(a)).lower().strip()
            na = re.sub(r"\s+", " ", na)
            if na and na not in alias:          # alias đầu tiên thắng -> ưu tiên canonical ntn
                alias[na] = canonical
    special: dict = {}
    for group, terms in data["special_values"].items():
        target = {"remote": "Remote", "toan_quoc": "Toàn quốc", "nuoc_ngoai": "Quốc tế"}[group]
        for t in terms:
            special[t] = target
    return alias, special, data.get("priority_hubs", [])


class _ProvinceIndex:
    """Lazy singleton: alias đã bỏ dấu, sắp xếp DÀI NHẤT TRƯỚC để ưu đặc thù."""

    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
            cls._inst.alias, cls._inst.special, cls._inst.hubs = _load_province_index()
            # Sắp theo độ dài giảm dần: 'vsip bac ninh' phải thắng 'vsip'
            cls._inst.sorted_alias_keys = sorted(cls._inst.alias, key=len, reverse=True)
            # Hub tra theo canonical, giu THU TU uu tien cua priority_hubs
            hub_list = []
            for h in cls._inst.hubs:
                for cand in (h, _deaccent(h).lower(), _norm_loc(h)):
                    if cand in cls._inst.alias and cls._inst.alias[cand] not in hub_list:
                        hub_list.append(cls._inst.alias[cand])
                        break
            cls._inst.hub_keys = hub_list
            # Bien regex compiled cho lookup: 'quan 3' khong duoc khop trong
            # 'quan ba dinh' (substring musoi bo qua ranh gioi tu)
            cls._inst.alias_res = {
                a: re.compile(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])")
                for a in cls._inst.sorted_alias_keys
            }
        return cls._inst

    def lookup(self, s_norm: str) -> Optional[str]:
        # 1. Alias dai nhat thang, khop CO RANH GIOI TU ('ba dinh' thay vi 'bd')
        for a, rx in self.alias_res.items():
            if rx.search(s_norm):
                return self.alias[a]
        # 2. Fallback chuoi DA DIA DANH khong khop alias nao: uu tien hub lon
        #    theo THU TU priority_hubs ('Ha Noi, Ho Chi Minh' -> HCM)
        for hub_canon in self.hub_keys:
            if _norm_loc(hub_canon) in s_norm:
                return hub_canon
        return None


_province_index = _ProvinceIndex


_WORD_NUMS = {"mot": "1", "hai": "2", "ba": "3", "bon": "4", "nam": "5",
              "sau": "6", "bay": "7", "tam": "8", "chin": "9", "muoi": "10",
              "muoi mot": "11", "muoi hai": "12", "muoi ba": "13"}


def _norm_loc(s: str) -> str:
    t = _deaccent(str(s)).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Dich quan huyen viet chu thanh so CHU KHI tu chi so dung CUOI chuoi.
    #   'Quan Muoi Hai' -> 'quan 12' (quy danh so thu) NHUNG 'Quan Ba Dinh'
    #   khong bi dich (co 'dinh' di sau) -> tranh xuyen TP (Ba Dinh = Ha Noi).
    #   Can cu: quan danh so o 8 san luon dung o cuoi ('...', 'Quận 7, TP.HCM'
    #   da dang so nen khong can dich).
    t = re.sub(r"\bquan (muoi (?:mot|hai|ba)|(?:mot|hai|ba|bon|nam|sau|bay|tam|chin))\s*$",
               lambda m: "quan " + _WORD_NUMS[m.group(1)], t)
    return t


# Thuật ngữ remote ưu tiên nhận diện trước (data thật: ITviec ghi 'Remote' tiếng Anh)
_REMOTE_TERMS = ("remote", "từ xa", "tu xa", "wfh", "work from home", "online working", "working from home", "hybrid")


def normalize_city(location_text: Optional[str]) -> str:
    """Chuẩn hóa chuỗi địa điểm về MỘT trong 34 đơn vị hành chính hiện hành
    (VN từ 1/7/2025, NQ 60-NQ/TW) — `vn_provinces.json` v2. Từ điển vẫn giu
    alias ten tinh CU (63 don vi tru day) trong truong `successor_map_2025`.

    Quy tac (doi chieu thang voi code):
    - Khong phan biet dau: 'Ha Noi'->'Ha Noi', 'Ho Chi Minh'->'Hồ Chi Minh'.
    - Quan/huyen -> tinh theo alias tu dien co RANH GIOI TU ('ba dinh' chuyen
      'ha dong' khong an khop); ALIAS DAI NHAT THANG ('vsip bac ninh' > 'vsip').
    - Chuoi nhieu dia danh: KHONG phai 'tinh dau tien' — uu tien alias dai nhat
      khop trong toan chuoi, roi moi deny `priority_hubs` (HCM/HN/DN).
    - Khong nhan dien duoc -> tra nguyen van chuoi goc (ranh gioi cam mat nhan goc).
    - 'Quận <so viet chu>' chi dich sang so khi tu chi so dung CUOI chuoi
      ('quan ba'->'quan 3'), de 'quan ba dinh' (Ha Noi) khong bi hieu lam Quan 3.
    """
    if not location_text or not str(location_text).strip():
        return "Không xác định"

    raw = str(location_text).strip()
    s = _norm_loc(raw)
    if not s:
        return "Không xác định"

    idx = _ProvinceIndex()

    # Special values (remote/toàn quốc/quốc tế) — xét trên both bản có dấu lẫn không dấu
    low = raw.lower()
    for term, target in idx.special.items():
        if term in low or _norm_loc(term) in s:
            return target

    # Alias province (không dấu) — dài nhất thắng
    hit = idx.lookup(s)
    if hit:
        return hit
    # B2: khớp token-liền (data thật: 'Hochiminh', 'bienhoa', 'danang')
    s_sq = s.replace(" ", "")
    for a in idx.sorted_alias_keys:
        if " " not in a and a.replace(" ", "") == s_sq:
            return idx.alias[a]

    return raw


def detect_remote(
    location_text: Optional[str] = None,
    work_mode_text: Optional[str] = None,
    jd_text: Optional[str] = None,
) -> int:
    """Gắn cờ `is_remote`: 1 nếu tin cho phép làm việc từ xa, ngược lại 0.

    Quét 3 nguồn: địa điểm, hình thức làm việc (`raw_work_mode`), và nội dung JD
    (cụm "làm việc từ xa/remote working" trong mô tả).

    Quy tắc ngữ nghĩa (thay đổi 26/10 — 🟡 chờ team duyệt S-5): "Toàn quốc" là
    địa bàn tuyển dụng rộng, **KHÔNG đồng nghĩa remote** → không còn kích hoạt
    is_remote; tin vừa ghi Toàn quốc vừa có từ khóa remote trong JD vẫn = 1.
    """
    combined = f"{location_text or ''} {work_mode_text or ''} {jd_text or ''}".lower()
    return 1 if any(term in combined for term in _REMOTE_TERMS) else 0


def normalize_work_locations(working_locations: Union[list, str, None]) -> list:
    """Ép mảng `working_locations` (dict/str lai từ 8 sàn) về list[str] tỉnh chuẩn."""
    if not working_locations:
        return []
    items = working_locations if isinstance(working_locations, list) else [working_locations]
    out, seen = [], set()
    for it in items:
        if isinstance(it, dict):
            name = it.get("name") or it.get("city") or it.get("label") or ""
        else:
            name = str(it)
        if not name or not name.strip():
            continue
        city = normalize_city(name)
        if city and city not in seen:
            seen.add(city)
            out.append(city)
    return out


def process_record_text(flat: Dict[str, Any]) -> Dict[str, Any]:
    """Chạy toàn bộ chuẩn hóa văn bản trên MỘT bản ghi phẳng Staging (in-place an toàn).

    Chỉ SINH cột mới (`*_clean_*`, `primary_city`, `is_remote`), không xóa/sửa cột gốc.
    """
    flat["job_title_clean"] = clean_job_title(flat.get("job_title"))
    flat["jd_clean_text"] = clean_jd_text(flat.get("raw_description_text"))
    flat["requirements_clean_text"] = clean_jd_text(flat.get("raw_requirements_text"))
    flat["primary_city"] = normalize_city(flat.get("raw_location_text"))
    flat["working_locations_clean"] = normalize_work_locations(flat.get("working_locations"))
    flat["is_remote"] = detect_remote(
        flat.get("raw_location_text"), flat.get("raw_work_mode"), flat.get("jd_clean_text")
    )
    flat["standardized_job_family"] = classify_job_family(flat.get("job_title"), flat.get("skills_list"))
    from preprocessing.normalization.taxonomy_mapper import standardized_seniority
    flat["standardized_seniority"] = standardized_seniority(
        flat.get("raw_seniority_text"), flat.get("job_title"), flat.get("raw_experience_text")
    )
    return flat


def apply_legacy_column_names(flat: Dict[str, Any]) -> Dict[str, Any]:
    """Cây chuyển tương thích với pipeline Phúc hiện hành
    (`scripts/run_staging_integration_pipeline.py` dùng cột `job_family` và
    `job_seniority` nhãn hiển thị cũ — xem Delivery Contract §3, pending S-2).

    Chỉ SINH thêm 2 cột bản sao, không xóa cột chuẩn. Thuận sẽ bỏ lớp này khi
    `master_pipeline.py` đọc thẳng tên cột chuẩn.
    """
    from preprocessing.normalization.taxonomy_mapper import _SENIORITY_DISPLAY, map_seniority_code

    flat.setdefault("job_family", flat.get("standardized_job_family"))
    flat.setdefault(
        "job_seniority",
        _SENIORITY_DISPLAY.get(flat.get("standardized_seniority", "UNKNOWN"), "Chưa xác định"),
    )
    return flat
