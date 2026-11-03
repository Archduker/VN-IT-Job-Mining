# -*- coding: utf-8 -*-
"""Dịch JD tiếng Anh sang tiếng Việt bằng Gemini, gọi thẳng API Google (luật T6b).

- Khóa GEMINI_API_KEY (hoặc GOOGLE_API_KEY) trong .env, gửi qua header x-goog-api-key, không đưa vào URL.
- Model mặc định gemini-3.8-flash (có gói miễn phí), đối chứng gemini-4-argon (chỉ trả phí) trên 30 JD.
- JD dài được chia đoạn (<= 3.000 ký tự, theo đoạn văn), dịch từng đoạn rồi nối; cache theo đoạn.
- Trần tiền: per-run max_budget_usd và trần chung của tài khoản (ApiCache.over_budget).
- Giữ nguyên thuật ngữ KEEP; thiếu thuật ngữ sau dịch thì cờ translate_lost_term.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from preprocessing.common import REPO_ROOT
from preprocessing.common.api_cache import ApiCache
from preprocessing.transformation.skill_extractor import load_skills_dict

DEFAULT_MODEL = "gemini-3.8-flash"
CHALLENGER_MODEL = "gemini-4-argon"
# Giá trả phí USD / 1M token (vào, ra) theo aistudio.google.com/docs/pricing ngày 03/11/2026:
# 3.8 Flash giảm giá tới 31/12/2026, Argon giảm 50% tới 30/11/2026. Gói miễn phí thực tế tốn 0 nhưng sổ vẫn ghi theo giá này.
PRICES = {DEFAULT_MODEL: (0.75, 3.75), CHALLENGER_MODEL: (2.00, 10.00)}
OUT_TOKEN_RATIO = 1.5  # tiếng Việt tốn token hơn tiếng Anh: ước tính token ra = 1,5 × token vào
CHUNK_CHARS = 3000
THINKING = {"gemini-3.5-flash": "minimal", "gemini-3.5-flash-lite": "minimal"}  # 3.8 Flash không nhận "minimal"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
PROMPT_VERSION = "v1.0"
MAX_BUDGET_USD = 0.60

COMMON_TECH_ROLES = {
    "Backend", "Frontend", "Fullstack", "DevOps", "QA", "QC", "BA",
    "Intern", "Fresher", "Junior", "Middle", "Senior", "Lead", "Manager",
    "Scrum", "Agile", "Product Owner", "Product Manager", "Architect",
    "Data Scientist", "Data Engineer", "Machine Learning", "AI", "Mobile",
    "iOS", "Android", "Cloud", "Security", "Tester", "Developer", "Engineer"
}


def build_keep_terms() -> Set[str]:
    """Tập hợp danh sách các thuật ngữ không được dịch."""
    keep: Set[str] = set(COMMON_TECH_ROLES)
    skills = load_skills_dict()
    for canon, vars_list in skills.items():
        keep.add(canon)
        for v in vars_list:
            if len(v) >= 2:
                keep.add(v)
    return keep


def _term_re(term: str) -> "re.Pattern[str]":
    # \b không đứng được sau "C++", ".NET": dùng lookaround thay cho ranh giới từ
    return re.compile(rf"(?<![\w+#.]){re.escape(term)}(?![\w+#])", re.IGNORECASE)


def split_chunks(text: str, limit: int = CHUNK_CHARS) -> List[str]:
    """Chia theo dòng, gom tới <= limit ký tự; dòng dài quá limit thì cắt cứng."""
    chunks: List[str] = []
    cur = ""
    for line in text.split("\n"):
        while len(line) > limit:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if cur and len(cur) + 1 + len(line) > limit:
            chunks.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur.strip():
        chunks.append(cur)
    return chunks


def _api_key() -> Optional[str]:
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or None


class GeminiTranslator:
    def __init__(
        self,
        use_api: bool = False,
        dry_run: bool = True,
        model: str = DEFAULT_MODEL,
        max_budget_usd: float = MAX_BUDGET_USD,
        cache: Optional[ApiCache] = None,
        session: Any = None,
    ):
        self.use_api = use_api
        self.dry_run = dry_run
        self.model = model
        self.max_budget_usd = max_budget_usd
        self.cache = cache or ApiCache("translate", provider="google")
        self.session = session or requests.Session()
        self.key = _api_key() if use_api else None
        self.reason = None if self.key else ("không bật --use-api" if not use_api else "thiếu GEMINI_API_KEY trong .env")
        self.would_call = 0
        self.est_tokens = 0
        self.errors = 0
        self._consecutive_errors = 0
        self.keep_terms = build_keep_terms()

    def _est_cost(self, in_tokens: int) -> float:
        p_in, p_out = PRICES.get(self.model, (0.3, 1.2))
        return (in_tokens * p_in + in_tokens * OUT_TOKEN_RATIO * p_out) / 1_000_000

    def translate_text(self, text: Optional[str]) -> Tuple[Optional[str], bool]:
        """Dịch cả JD. Trả về (bản_dịch, có_mất_từ_keep_không); một đoạn lỗi thì cả bản là None."""
        if not text or not str(text).strip():
            return None, False
        clean_text = str(text).strip()
        present_keep = [k for k in self.keep_terms if _term_re(k).search(clean_text)]
        parts = []
        for chunk in split_chunks(clean_text):
            out = self._translate_chunk(chunk, present_keep)
            if out is None:
                return None, False
            parts.append(out)
        translated = "\n".join(parts)
        return translated, self._check_lost_terms(present_keep, translated)

    def _translate_chunk(self, chunk: str, present_keep: List[str]) -> Optional[str]:
        cache_key = self.cache.key(self.model, PROMPT_VERSION, chunk)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached.get("translated_text")

        est_tok = len(chunk) // 4 + 150  # tiếng Anh khoảng 4 ký tự/token; 150 token cho lời dặn
        if self.dry_run:
            if self.use_api:
                self.would_call += 1
                self.est_tokens += est_tok
            return None
        if not self.key or not self.use_api:
            return None
        if self.cache.cost_usd >= self.max_budget_usd or self.cache.over_budget():
            self.reason = f"dừng gọi: đã tới trần {self.max_budget_usd} USD lần này hoặc trần chung của tài khoản"
            return None
        if self._consecutive_errors >= 5:
            return None

        keep_in_chunk = [k for k in present_keep if _term_re(k).search(chunk)]
        system_prompt = (
            "Dịch sang tiếng Việt tự nhiên, chính xác cho ngành IT tuyển dụng. "
            f"BẮT BUỘC giữ nguyên từng thuật ngữ kỹ thuật, tên công nghệ, chức danh trong danh sách sau: [{', '.join(keep_in_chunk[:40])}]. "
            "Giữ nguyên định dạng gạch đầu dòng và số liệu. Chỉ trả về duy nhất bản dịch tiếng Việt."
        )
        headers = {"x-goog-api-key": self.key, "Content-Type": "application/json"}
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": chunk}]}],
            # tắt bớt "suy nghĩ": thử 03/11 một câu 21 token bị cộng 407 token suy nghĩ, tính giá như token ra
            "generationConfig": {"temperature": 0.2, "thinkingConfig": {"thinkingLevel": THINKING.get(self.model, "low")}},
        }

        for attempt in range(5):
            try:
                resp = self.session.post(ENDPOINT.format(model=self.model), headers=headers, json=payload, timeout=90)
                if resp.status_code in (429, 503):  # hết lượt/phút hoặc model quá tải: chờ rồi thử lại
                    time.sleep(10 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                parts = data["candidates"][0]["content"]["parts"]
                translated = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
                if not translated:
                    raise ValueError("bản dịch rỗng")
                usage = data.get("usageMetadata") or {}
                p_in, p_out = PRICES.get(self.model, (3.0, 15.0))
                out_tok = usage.get("candidatesTokenCount", est_tok * OUT_TOKEN_RATIO) + usage.get("thoughtsTokenCount", 0)
                cost = (usage.get("promptTokenCount", est_tok) * p_in + out_tok * p_out) / 1e6
                self._consecutive_errors = 0
                self.cache.put(cache_key, {"translated_text": translated, "model": self.model}, cost_usd=cost)
                return translated
            except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as e:
                self.errors += 1
                if attempt == 4:
                    self._consecutive_errors += 1
                    if self._consecutive_errors >= 5:
                        self.reason = f"dừng gọi sau 5 lỗi liên tiếp: {type(e).__name__}"
                    return None
                time.sleep(1.5)
        # hết 5 lần vì 429/503: tính là một lỗi, để luật "5 lỗi liên tiếp" dừng hẳn thay vì chờ mãi từng đoạn
        self.errors += 1
        self._consecutive_errors += 1
        if self._consecutive_errors >= 5:
            self.reason = "dừng gọi sau 5 đoạn liên tiếp bị 429/503 (model quá tải hoặc hết lượt)"
        return None

    def _check_lost_terms(self, present_keep: List[str], translated_text: Optional[str]) -> bool:
        """Trả về True nếu có thuật ngữ KEEP trong gốc bị mất tích trong bản dịch."""
        if not translated_text:
            return False
        for k in present_keep:
            if not _term_re(k).search(translated_text):
                return True
        return False

    def stats(self) -> Dict[str, Any]:
        out = self.cache.stats(self.model)
        out["used"] = bool(self.key) and not self.dry_run and self.use_api
        out.update({
            "errors": self.errors,
            "reason": self.reason,
            "max_budget_usd": self.max_budget_usd,
        })
        if self.dry_run:
            out.update({
                "would_call": self.would_call,
                "estimated_cost_usd": round(self._est_cost(self.est_tokens), 4),
            })
        return out
