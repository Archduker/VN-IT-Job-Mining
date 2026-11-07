"""Làm sạch văn bản phục vụ băm nội dung (docs/spec/05_preprocessing_spec.md mục 2.1, 2.2, 2.3, 3.1).

Ba việc, tất định, không model:
  1. Bóc HTML bằng BeautifulSoup + lxml, giải mã HTML entity, bảo toàn ngữ nghĩa (`<li>` -> "• ", thẻ ngắt đoạn -> "\\n").
  2. Chuẩn hóa Unicode NFC, xóa ký tự điều khiển và khoảng trắng thừa.
  3. Lọc boilerplate của sàn (quảng cáo ứng dụng, mã tin, hạn nộp, giới thiệu chung).

`fold()` bỏ dấu thanh để so sánh nhưng **giữ nguyên ký tự công nghệ** `C#`, `C++`, `.NET`, `F#`
(điều kiện nghiệm thu mục 3.1 của docs/tasks/02_tai_clean_and_deduplication.md).
Không sửa `raw_payload`: mọi kết quả ở đây chỉ dùng để tính khóa và ghi vào `metadata.dedup`.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from typing import Any

from bs4 import BeautifulSoup

# Ký tự vô hình gây lỗi tokenizer (SPEC-05 mục 2.2.3)
CONTROL_CHARS = re.compile(r"[\x00\x01-\x08\x0b\x0c\x0e-\x1f\x7f\u200b\u200c\u200d\ufeff]")

# Boilerplate quảng cáo / thông báo chung của sàn (SPEC-05 mục 2.3).
# Nhánh "nuốt cả câu" dùng `[^.\n]` chứ không dùng `[^\n]`: nếu không, một câu quảng cáo ở đầu
# dòng sẽ ăn luôn 60 ký tự JD thật nằm sau nó và làm mất nội dung đưa vào TF-IDF.
BOILERPLATE = re.compile(
    r"(tải ứng dụng [^.\n]{0,60}|ứng tuyển ngay [^.\n]{0,60}|cam kết bảo mật[^.\n]{0,60}|"
    r"bảo mật thông tin cá nhân[^.\n]{0,40}|mã tin(?: tuyển dụng)?[:\s]*\d+|"
    r"hạn nộp(?: hồ sơ)?[:\s]*\d{1,2}/\d{1,2}/\d{4}|ngày hết hạn[^.\n]{0,30}|"
    r"công ty chúng tôi được thành lập[^.\n]{0,80}|tự hào là môi trường làm việc[^.\n]{0,80}|"
    r"(?:topcv|vietnamworks|itviec|topdev|glints|jobsgo|careerviet|vieclam24h)\s+(?:vn|app|nền tảng)[^.\n]{0,40})",
    re.IGNORECASE,
)

HTML_TAGS = ("script", "style", "noscript", "iframe", "header", "footer")
TEXT_FIELDS = (
    "job_title", "company_name", "raw_location_text", "raw_salary_text",
    "raw_experience_text", "raw_description_text", "raw_requirements_text", "skills_list",
)
# Khóa "cùng một tin" dùng cho tầng 2: chỉ băm tiêu đề + tên công ty + toàn văn JD, bỏ lương,
# mô tả địa chỉ và kinh nghiệm, vì mỗi sàn trình bày mấy trường này mỗi khác ("15 - 25 triệu"
# vs "Lương: $2000", "Hà Nội" vs "Ha Noi, Vietnam", "1 năm" vs "1-3 years").
# An toàn vì Blocking Key đã neo sẵn Slug(công ty) + mã tỉnh thành trước khi so khóa này.
IDENTITY_FIELDS = ("job_title", "company_name", "raw_description_text", "raw_requirements_text")


def as_text(value: Any) -> str:
    """Mọi giá trị (chuỗi, danh sách, từ điển, số) về một chuỗi để băm."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int | float):
        return format(value, ".6g") if isinstance(value, float) else str(value)
    if isinstance(value, list | tuple):
        return " ".join(as_text(v) for v in value if v not in (None, "", [], {}))
    if isinstance(value, dict):
        return " ".join(f"{k}: {as_text(v)}" for k, v in sorted(value.items(), key=lambda kv: str(kv[0])))
    return str(value)


def strip_html(raw: str) -> str:
    """Bóc tách HTML sang văn thuần, giữ ranh giới danh sách và xuống dòng (SPEC-05 mục 2.1)."""
    if not raw:
        return ""
    # SPEC-05 mục 2.1.4: giải mã entity trước khi parse. Nhiều sàn trả JD đã là văn thuần
    # nhưng còn nguyên `&nbsp;` / `&amp;`, nếu bỏ qua bước này thì `&` thừa lọt vào TF-IDF.
    raw = html.unescape(raw)
    if "<" not in raw:
        return raw
    soup = BeautifulSoup(raw, "lxml")
    for tag in soup(HTML_TAGS):
        tag.extract()
    for li in soup.find_all("li"):
        li.insert_before("• ")
        li.append("\n")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for el in soup.find_all(["p", "div", "tr"]):
        el.append("\n")
    return soup.get_text(separator="\n")


def clean_text(value: Any) -> str:
    """Bóc HTML + xóa ký tự điều khiển + lọc boilerplate + gom khoảng trắng, giữ nguyên dấu tiếng Việt."""
    s = unicodedata.normalize("NFC", strip_html(as_text(value)))
    s = CONTROL_CHARS.sub(" ", s)
    s = BOILERPLATE.sub(" ", s)
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[ \t\u00a0]+", " ", s)
    s = re.sub(r"\n\s*\n(?:\s*\n)+", "\n\n", s)
    s = re.sub(r"\s*\n\s*", " \n ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def fold(text: str) -> str:
    """Bỏ dấu thanh để so sánh nhưng giữ ký tự công nghệ (C#, C++, .NET, F#) và chữ số."""
    s = unicodedata.normalize("NFD", text or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("Đ", "D").replace("đ", "d")
    s = unicodedata.normalize("NFC", s).lower()
    return re.sub(r"\s+", " ", s).strip()


def canonical_hash(flat: dict, fields: tuple[str, ...] = TEXT_FIELDS) -> str:
    """SHA-256 trên canonical JSON của các trường nội dung (SPEC-05 mục 3.1).

    Chỉ băm nội dung bán được: không băm ngày cào, lượt xem, version -> hai lần chạy cho cùng
    một tin vẫn ra cùng hash, kể cả khi sàn đổi template hiển thị.
    """
    doc = {f: fold(clean_text(flat.get(f))) for f in fields}
    doc = {k: v for k, v in doc.items() if v}
    payload = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def identity_hash(flat: dict) -> str:
    """Băm tiêu đề + công ty + toàn văn JD để khớp chính xác 100% giữa hai sàn (luật D4)."""
    return canonical_hash(flat, IDENTITY_FIELDS)


def jd_text(flat: dict) -> str:
    """Văn bản đại diện cho TF-IDF: `Clean_Title + Clean_Requirements + Clean_Description` (SPEC-05 mục 3.2.B.1).

    Giữ dấu tiếng Việt (không fold) vì char n-gram trên văn bản có dấu tách rõ hơn;
    chỉ bỏ HTML, ký tự điều khiển và boilerplate.
    """
    parts = [clean_text(flat.get(k)) for k in ("job_title", "raw_requirements_text", "raw_description_text")]
    return ". ".join(p for p in parts if p)
