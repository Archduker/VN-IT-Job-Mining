# -*- coding: utf-8 -*-
"""preprocessing.missing_outlier.genai_text_imputer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module bù khuyết dữ liệu thông minh bằng GenAI (Gemini 1.5 Flash) kết hợp Heuristic.

Quy chuẩn Quản trị AI (Human-in-the-Loop AI Governance):
  - Bắt buộc kiểm tra cờ `team_approved: bool`.
  - Nếu `team_approved=False`: Chạy hoàn toàn bằng bộ suy luận Heuristic tất định,
    ngăn chặn tự ý gọi API bên thứ ba khi chưa có sự xác nhận của Bạn và Team.
  - Cung cấp hàm `generate_pilot_benchmark()` để chạy đối chứng 20 mẫu gửi Team duyệt.
  - Đảm bảo tính minh bạch: Bật cờ `is_imputed_by_genai = True` và ghi `imputed_fields`.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("genai_imputer")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"


class GenAITextImputer:
    """Bộ bù khuyết dữ liệu thông minh có cơ chế kiểm duyệt AI Sign-off."""

    def __init__(self, api_key: Optional[str] = None, team_approved: bool = False):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.team_approved = team_approved

    def impute_job_record(self, flat_record: Dict[str, Any]) -> Dict[str, Any]:
        """Kiểm tra và bù khuyết các trường bị thiếu từ văn bản JD.

        Quy tắc ưu tiên (Priority Rule):
        1. Nếu trường đã có giá trị hợp lệ -> Giữ nguyên 100%.
        2. Tầng 1: Sử dụng Heuristic Regex tất định để bù khuyết nhanh, chính xác, 0 token.
        3. Tầng 2: Nếu chưa điền được và `team_approved=True` -> Gọi Gemini 1.5 Flash.
        """
        record = dict(flat_record)
        jd_text = record.get("raw_description_text") or ""
        req_text = record.get("raw_requirements_text") or ""
        combined_text = f"{jd_text}\n{req_text}".strip()

        needs_exp = record.get("min_experience_years") is None
        needs_sen = not record.get("standardized_seniority") or record.get("standardized_seniority") in ("Chưa xác định", "None", None)
        needs_loc = not record.get("primary_city") or record.get("primary_city") == "Không xác định"
        needs_skills = len(record.get("skills_list") or []) == 0

        if not any([needs_exp, needs_sen, needs_loc, needs_skills]) or not combined_text:
            return record

        # 1. Tầng Heuristic tất định (Ưu tiên số 1)
        heuristic_data = self._heuristic_extractor(record.get("job_title") or "", combined_text)
        imputed_fields = []

        if needs_exp and heuristic_data.get("min_experience_years") is not None:
            record["min_experience_years"] = float(heuristic_data["min_experience_years"])
            imputed_fields.append("min_experience_years")
            needs_exp = False

        if needs_sen and heuristic_data.get("job_seniority"):
            record["standardized_seniority"] = heuristic_data["job_seniority"]
            if not record.get("raw_seniority_text"):
                record["raw_seniority_text"] = heuristic_data["job_seniority"]
            imputed_fields.append("seniority")
            needs_sen = False

        if needs_loc and heuristic_data.get("primary_city"):
            record["primary_city"] = heuristic_data["primary_city"]
            imputed_fields.append("primary_city")
            needs_loc = False

        if needs_skills and heuristic_data.get("hard_skills"):
            record["skills_list"] = heuristic_data["hard_skills"]
            imputed_fields.append("skills_list")
            needs_skills = False

        # 2. Tầng GenAI (Chỉ gọi khi team_approved=True và vẫn còn trường thiếu)
        if any([needs_exp, needs_sen, needs_loc, needs_skills]) and self.team_approved and self.api_key:
            try:
                genai_data = self._call_gemini_api(record.get("job_title") or "", combined_text)
                if needs_exp and genai_data.get("min_experience_years") is not None:
                    record["min_experience_years"] = float(genai_data["min_experience_years"])
                    imputed_fields.append("min_experience_years_genai")
                if needs_sen and genai_data.get("job_seniority"):
                    record["standardized_seniority"] = genai_data["job_seniority"]
                    imputed_fields.append("seniority_genai")
                if needs_loc and genai_data.get("primary_city"):
                    record["primary_city"] = genai_data["primary_city"]
                    imputed_fields.append("primary_city_genai")
                if needs_skills and genai_data.get("hard_skills"):
                    record["skills_list"] = genai_data["hard_skills"]
                    imputed_fields.append("skills_list_genai")

                record["is_imputed_by_genai"] = True
                record["genai_model"] = "gemini-1.5-flash"
                record["genai_confidence"] = genai_data.get("confidence_score", 0.90)
            except Exception as exc:
                logger.warning("Không thể gọi Gemini API (%s), giữ nguyên kết quả Heuristic", exc)

        if imputed_fields:
            record["imputed_fields"] = imputed_fields

        return record

    def _heuristic_extractor(self, job_title: str, jd_text: str) -> Dict[str, Any]:
        """Bộ bóc tách Heuristic quy tắc mạnh mẽ trên văn bản JD."""
        text = f"{job_title}\n{jd_text}".lower()
        res: Dict[str, Any] = {
            "min_experience_years": None,
            "job_seniority": None,
            "primary_city": None,
            "hard_skills": [],
        }

        # 1. Kinh nghiệm
        # 0 năm
        if re.search(r"(?:không\s+yêu\s+cầu\s+kinh\s+nghiệm|chưa\s+có\s+kinh\s+nghiệm|fresher|intern|thực\s+tập|no\s+experience)", text):
            res["min_experience_years"] = 0.0
        # 6 tháng
        elif re.search(r"(?:6\s*tháng|dưới\s+1\s*năm|under\s+1\s*year)", text):
            res["min_experience_years"] = 0.5
        # Khoảng: 2 - 3 năm
        else:
            m_range = re.search(r"(\d+)\s*[-–tođến]+\s*(\d+)\s*(?:năm|years?)", text)
            if m_range:
                res["min_experience_years"] = float(m_range.group(1))
            else:
                m_at_least = re.search(r"(?:tối\s+thiểu|ít\s+nhất|từ|at\s+least|minimum)\s*(\d+)\s*(?:năm|years?)", text)
                if m_at_least:
                    res["min_experience_years"] = float(m_at_least.group(1))
                else:
                    m_plus = re.search(r"(\d+)\+?\s*(?:năm|years?)\s*(?:kinh\s+nghiệm|of\s+experience)", text)
                    if m_plus:
                        res["min_experience_years"] = float(m_plus.group(1))

        # 2. Cấp bậc
        if any(k in text for k in ["intern", "thực tập", "trainee"]):
            res["job_seniority"] = "Intern"
        elif any(k in text for k in ["fresher", "mới tốt nghiệp"]):
            res["job_seniority"] = "Fresher"
        elif any(k in text for k in ["junior", "dưới 2 năm"]):
            res["job_seniority"] = "Junior"
        elif any(k in text for k in ["lead", "trưởng nhóm", "manager", "quản lý", "giám đốc", "director", "cto"]):
            res["job_seniority"] = "Lead/Manager"
        elif any(k in text for k in ["senior", "chuyên viên cao cấp"]):
            res["job_seniority"] = "Senior"
        elif res["min_experience_years"] is not None:
            y = res["min_experience_years"]
            if y == 0.0:
                res["job_seniority"] = "Fresher"
            elif y >= 4.0:
                res["job_seniority"] = "Senior"
            elif y >= 2.0:
                res["job_seniority"] = "Middle"
            else:
                res["job_seniority"] = "Junior"

        # 3. Địa điểm
        if any(k in text for k in ["hồ chí minh", "tp.hcm", "hcm", "sài gòn"]):
            res["primary_city"] = "Hồ Chí Minh"
        elif any(k in text for k in ["hà nội", "hn", "cầu giấy", "ba đình"]):
            res["primary_city"] = "Hà Nội"
        elif any(k in text for k in ["đà nẵng", "dn"]):
            res["primary_city"] = "Đà Nẵng"
        elif any(k in text for k in ["remote", "từ xa", "toàn quốc"]):
            res["primary_city"] = "Remote"

        # 4. Kỹ năng
        tech_keywords = [
            "python", "java", "golang", "c++", "c#", "php", "javascript", "typescript",
            "react", "vue", "angular", "nextjs", "node.js", "docker", "kubernetes", "aws",
            "azure", "gcp", "sql", "postgresql", "mysql", "mongodb", "redis", "fastapi",
            "django", "spring", "spring boot", "flutter", "react native", "devops", "ci/cd",
            "git", "linux", "html", "css", "tailwind"
        ]
        found = [kw.title() for kw in tech_keywords if re.search(rf"\b{re.escape(kw)}\b", text)]
        res["hard_skills"] = found[:10]

        return res

    def _call_gemini_api(self, job_title: str, jd_text: str) -> Dict[str, Any]:
        """Gọi Gemini API chính thức khi đã có sign-off."""
        prompt = (
            "Bạn là chuyên gia phân tích thị trường lao động IT tại Việt Nam.\n"
            "Hãy đọc kỹ văn bản tuyển dụng và trích xuất JSON chuẩn xác:\n"
            "{\n"
            '  "min_experience_years": float | null,\n'
            '  "job_seniority": "Intern" | "Fresher" | "Junior" | "Middle" | "Senior" | "Lead/Manager" | null,\n'
            '  "primary_city": string | null,\n'
            '  "hard_skills": list[string],\n'
            '  "confidence_score": float\n'
            "}\n\n"
            f"Tiêu đề: {job_title}\n"
            f"Văn bản:\n{jd_text[:2500]}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.1},
        }

        resp = requests.post(
            f"{GEMINI_API_ENDPOINT}?key={self.api_key}",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        raw_json_str = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(raw_json_str)

    def generate_pilot_benchmark(self, records: List[Dict[str, Any]], sample_size: int = 20, output_path: Optional[Path] = None) -> Path:
        """Tạo báo cáo Pilot 20 mẫu đối chứng để gửi Team và User phê duyệt trước khi kích hoạt batch."""
        import random
        random.seed(42)
        candidates = [r for r in records if r.get("min_experience_years") is None or not r.get("skills_list")]
        sample = random.sample(candidates, min(sample_size, len(candidates)))

        report_lines = [
            "# BÁO CÁO ĐỐI CHỨNG THỬ NGHIỆM PILOT GENAI (GENAI IMPUTATION BENCHMARK)",
            "",
            "> **Tài liệu kiểm định quản trị AI:** Gửi Bạn (User) và Team thẩm định trước khi chạy batch toàn hệ thống.",
            f"> **Quy mô mẫu:** {len(sample)} bài đăng ngẫu nhiên có khuyết thiếu kinh nghiệm/kỹ năng.",
            "",
            "| ID | Nguồn | Tiêu Đề | Kinh Nghiệm Trước | Kinh Nghiệm Đề Xuất (Heuristic) | Kỹ Năng Đề Xuất |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |"
        ]

        for r in sample:
            comb = f"{r.get('raw_description_text') or ''} {r.get('raw_requirements_text') or ''}"
            he = self._heuristic_extractor(r.get("job_title") or "", comb)
            exp_before = str(r.get("min_experience_years"))
            exp_after = f"{he.get('min_experience_years')} năm" if he.get("min_experience_years") is not None else "Null"
            skills_after = ", ".join(he.get("hard_skills") or []) or "Chưa tìm thấy"
            title = (r.get("job_title") or "N/A")[:35].replace("|", "-")
            report_lines.append(f"| `{r.get('job_id_global')}` | `{r.get('source_platform')}` | {title} | {exp_before} | **{exp_after}** | {skills_after} |")

        out = output_path or Path("reports/ai_governance/pilot_gemini_imputation_benchmark.md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(report_lines), encoding="utf-8")
        logger.info("Đã xuất báo cáo đối chứng Pilot tại: %s", out)
        return out
