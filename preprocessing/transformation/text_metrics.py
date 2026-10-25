# -*- coding: utf-8 -*-
"""preprocessing.transformation.text_metrics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module trích xuất chỉ số định lượng văn bản (Đơn biến/Đa biến) và thực thi
2 Chính sách đã được phê duyệt:
  1. Chính sách 1.B: Loại bỏ hoàn toàn bài đăng rác siêu ngắn (Stub JD < 30 từ).
  2. Chính sách 2.B: Chuẩn hóa và dịch thuật đồng nhất về tiếng Việt.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# Từ điển chuẩn hóa các thuật ngữ tuyển dụng tiếng Anh sang tiếng Việt (Chính sách 2.B)
EN_VI_RECRUITMENT_DICTIONARY = {
    "job description": "mô tả công việc",
    "responsibilities": "trách nhiệm công việc",
    "key responsibilities": "trách nhiệm chính",
    "requirements": "yêu cầu ứng viên",
    "job requirements": "yêu cầu công việc",
    "qualifications": "năng lực và bằng cấp",
    "benefits": "quyền lợi và đãi ngộ",
    "why you'll love working here": "tại sao bạn sẽ yêu thích làm việc tại đây",
    "what we offer": "chế độ đãi ngộ chúng tôi cung cấp",
    "full-time": "toàn thời gian",
    "part-time": "bán thời gian",
    "remote": "làm việc từ xa",
    "hybrid": "làm việc kết hợp văn phòng và từ xa",
    "onsite": "làm việc tại văn phòng",
    "years of experience": "năm kinh nghiệm",
    "health insurance": "bảo hiểm sức khỏe",
    "social insurance": "bảo hiểm xã hội",
    "performance bonus": "thưởng hiệu suất",
    "13th month salary": "lương tháng 13",
    "annual leave": "nghỉ phép hàng năm",
    "competitive salary": "mức lương cạnh tranh",
    "negotiable": "thỏa thuận",
}


def calculate_text_metrics(text: Optional[str]) -> Dict[str, Any]:
    """Tính toán các chỉ số định lượng đơn biến của văn bản."""
    if not text or not str(text).strip():
        return {
            "word_count": 0,
            "char_count": 0,
            "sentence_count": 0,
            "lexical_diversity_ttr": 0.0,
            "is_stub_jd": True,
            "primary_language": "unknown",
        }

    s = str(text).strip()
    words = re.findall(r"\b[\w\d_.-]+\b", s)
    total_words = len(words)
    total_chars = len(s)

    # Đếm số câu dựa trên dấu chấm, hỏi, than, hoặc xuống dòng
    sentences = [sent.strip() for sent in re.split(r"[.!?\n]+", s) if sent.strip()]
    sentence_count = len(sentences)

    # Tính độ đa dạng từ vựng TTR (Type-Token Ratio)
    if total_words > 0:
        unique_words = set(w.lower() for w in words)
        ttr = round(len(unique_words) / total_words, 3)
    else:
        ttr = 0.0

    # Nhận diện ngôn ngữ (Chính sách 2.B)
    lang = detect_language(s)

    # Kiểm tra tin rác siêu ngắn (Chính sách 1.B: ngưỡng 30 từ)
    is_stub = total_words < 30

    return {
        "word_count": total_words,
        "char_count": total_chars,
        "sentence_count": sentence_count,
        "lexical_diversity_ttr": ttr,
        "is_stub_jd": is_stub,
        "primary_language": lang,
    }


def detect_language(text: str) -> str:
    """Nhận diện ngôn ngữ văn bản: tiếng Việt ('vi'), tiếng Anh ('en'), hoặc song ngữ ('bilingual')."""
    s = text.lower()
    vi_markers = ("công việc", "yêu cầu", "quyền lợi", "kinh nghiệm", "lương", "chúng tôi", "ứng viên", "bảo hiểm")
    en_markers = ("responsibilities", "requirements", "qualifications", "benefits", "experience", "salary", "team", "working")

    vi_score = sum(1 for m in vi_markers if m in s)
    en_score = sum(1 for m in en_markers if m in s)

    if vi_score >= 3 and en_score == 0:
        return "vi"
    if en_score >= 3 and vi_score == 0:
        return "en"
    if vi_score > 0 and en_score > 0:
        return "bilingual"

    # Fallback theo bảng chữ cái có dấu tiếng Việt
    has_vi_accents = bool(re.search(r"[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]", s))
    return "vi" if has_vi_accents else "en"


def standardize_to_vietnamese(text: Optional[str]) -> Optional[str]:
    """Chuẩn hóa và dịch các tiêu đề/thuật ngữ tiếng Anh thông dụng sang tiếng Việt (Chính sách 2.B)."""
    if not text:
        return text

    res = str(text)
    for en_term, vi_term in EN_VI_RECRUITMENT_DICTIONARY.items():
        pattern = re.compile(rf"\b{re.escape(en_term)}\b", re.IGNORECASE)
        res = pattern.sub(vi_term, res)

    return res


def filter_valid_clean_records(records: List[Dict[str, Any]], min_words: int = 30) -> Tuple[List[Dict[str, Any]], int]:
    """Thực thi Chính sách 1.B: Loại bỏ hoàn toàn các bài đăng rác siêu ngắn (Stub JD < 30 từ).

    Args:
        records: Danh sách các bản ghi phẳng.
        min_words: Ngưỡng số từ tối thiểu (mặc định: 30 từ).

    Returns:
        (valid_records, dropped_count)
    """
    valid = []
    dropped_count = 0

    for r in records:
        desc = r.get("raw_description_text") or ""
        req = r.get("raw_requirements_text") or ""
        total_text = f"{desc} {req}".strip()
        word_count = len(re.findall(r"\b[\w\d_.-]+\b", total_text))

        if word_count < min_words:
            dropped_count += 1
        else:
            r["jd_word_count"] = word_count
            valid.append(r)

    return valid, dropped_count
