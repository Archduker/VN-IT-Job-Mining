# -*- coding: utf-8 -*-
"""preprocessing.missing_outlier.genai_text_imputer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module bù khuyết dữ liệu thông minh bằng GenAI (Gemini 1.5 Flash).

Nhiệm vụ:
  - Đọc hiểu sâu văn bản mô tả (JD) và yêu cầu công việc.
  - Bù khuyết các trường bị thiếu: min_experience_years, seniority, city, skills, lương ẩn.
  - Hỗ trợ cả Gemini REST API chính thức và cơ chế heuristic fallback khi offline.
  - Đảm bảo tính minh bạch: Bật cờ is_imputed_by_genai = True.
"""

from __future__ import annotations

import json
import logging
import os
import re
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
    """Bộ bù khuyết dữ liệu thông minh dựa trên GenAI."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def impute_job_record(self, flat_record: Dict[str, Any]) -> Dict[str, Any]:
        """Kiểm tra và bù khuyết các trường bị thiếu từ văn bản JD.

        Chỉ gọi GenAI khi thực sự có trường quan trọng bị thiếu:
        - Thiếu min_experience_years
        - Thiếu raw_seniority_text
        - Thiếu raw_location_text
        - skills_list bị rỗng
        - Lương là thỏa thuận (quét tìm lương ngầm)
        """
        record = dict(flat_record)
        jd_text = record.get("raw_description_text") or ""
        req_text = record.get("raw_requirements_text") or ""
        combined_text = f"{jd_text}\n{req_text}".strip()

        # Kiểm tra xem có cần bù khuyết không
        needs_exp = record.get("min_experience_years") is None
        needs_sen = not record.get("raw_seniority_text")
        needs_loc = not record.get("raw_location_text")
        needs_skills = len(record.get("skills_list") or []) == 0
        needs_salary = record.get("salary_max_vnd") is None

        if not any([needs_exp, needs_sen, needs_loc, needs_skills, needs_salary]) or not combined_text:
            return record

        # Gọi GenAI hoặc fallback
        imputed_data = self._call_gemini_or_fallback(record.get("job_title") or "", combined_text)

        imputed_fields = []

        # 1. Bù kinh nghiệm
        if needs_exp and imputed_data.get("min_experience_years") is not None:
            record["min_experience_years"] = float(imputed_data["min_experience_years"])
            imputed_fields.append("min_experience_years")

        # 2. Bù cấp bậc (seniority)
        if needs_sen and imputed_data.get("job_seniority"):
            record["raw_seniority_text"] = imputed_data["job_seniority"]
            imputed_fields.append("seniority")

        # 3. Bù địa điểm
        if needs_loc and imputed_data.get("primary_city"):
            record["raw_location_text"] = imputed_data["primary_city"]
            imputed_fields.append("location")

        # 4. Bù kỹ năng
        if needs_skills and imputed_data.get("hard_skills"):
            record["skills_list"] = imputed_data["hard_skills"]
            imputed_fields.append("skills_list")
        elif imputed_data.get("hard_skills"):
            # Bổ sung kỹ năng ngầm định vào danh sách hiện có
            existing = set(s.lower() for s in record["skills_list"])
            for s in imputed_data["hard_skills"]:
                if s.lower() not in existing:
                    record["skills_list"].append(s)
                    existing.add(s.lower())

        # 5. Bù lương ngầm
        if needs_salary and imputed_data.get("implicit_salary_max_vnd"):
            record["salary_min_vnd"] = imputed_data.get("implicit_salary_min_vnd")
            record["salary_max_vnd"] = imputed_data.get("implicit_salary_max_vnd")
            record["salary_source"] = "genai_implicit"
            imputed_fields.append("salary")

        if imputed_fields:
            record["is_imputed_by_genai"] = True
            record["genai_imputed_fields"] = imputed_fields
            record["genai_confidence"] = imputed_data.get("confidence_score", 0.85)

        return record

    def _call_gemini_or_fallback(self, job_title: str, jd_text: str) -> Dict[str, Any]:
        """Gọi Gemini API hoặc chạy bộ heuristic offline."""
        if self.api_key:
            try:
                return self._call_gemini_api(job_title, jd_text)
            except Exception as exc:
                logger.warning("Lỗi gọi Gemini API (%s), chuyển sang bộ heuristic fallback", exc)

        return self._heuristic_fallback(job_title, jd_text)

    def _call_gemini_api(self, job_title: str, jd_text: str) -> Dict[str, Any]:
        prompt = (
            "Bạn là chuyên gia phân tích thị trường lao động CNTT tại Việt Nam.\n"
            "Hãy đọc văn bản tuyển dụng sau và trích xuất các thông tin dưới dạng JSON chuẩn:\n"
            "{\n"
            '  "min_experience_years": float | null,\n'
            '  "job_seniority": "Intern" | "Fresher" | "Junior" | "Middle" | "Senior" | "Lead" | null,\n'
            '  "primary_city": string | null,\n'
            '  "hard_skills": list[string],\n'
            '  "domain_skills": list[string],\n'
            '  "implicit_salary_min_vnd": float | null,\n'
            '  "implicit_salary_max_vnd": float | null,\n'
            '  "confidence_score": float\n'
            "}\n\n"
            f"Tiêu đề: {job_title}\n"
            f"Văn bản JD:\n{jd_text[:3000]}"
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

    def _heuristic_fallback(self, job_title: str, jd_text: str) -> Dict[str, Any]:
        """Bộ suy luận heuristic thông minh khi offline hoặc không có API key."""
        text = f"{job_title}\n{jd_text}".lower()
        res: Dict[str, Any] = {
            "min_experience_years": None,
            "job_seniority": None,
            "primary_city": None,
            "hard_skills": [],
            "domain_skills": [],
            "implicit_salary_min_vnd": None,
            "implicit_salary_max_vnd": None,
            "confidence_score": 0.8,
        }

        # 1. Suy luận kinh nghiệm
        exp_match = re.search(r"(\d+)\s*(?:[-–tođến]+\s*(\d+))?\s*năm\s*kinh\s*nghiệm", text)
        if exp_match:
            res["min_experience_years"] = float(exp_match.group(1))
        elif "không yêu cầu kinh nghiệm" in text or "fresher" in text or "thực tập" in text:
            res["min_experience_years"] = 0.0

        # 2. Suy luận cấp bậc
        if "intern" in text or "thực tập" in text:
            res["job_seniority"] = "Intern"
        elif "fresher" in text:
            res["job_seniority"] = "Fresher"
        elif "junior" in text:
            res["job_seniority"] = "Junior"
        elif "senior" in text:
            res["job_seniority"] = "Senior"
        elif "lead" in text or "quản lý" in text or "manager" in text:
            res["job_seniority"] = "Lead"
        elif res["min_experience_years"] is not None:
            y = res["min_experience_years"]
            res["job_seniority"] = "Senior" if y >= 4 else ("Middle" if y >= 2 else "Junior")

        # 3. Suy luận địa điểm
        if any(w in text for w in ["hồ chí minh", "hcm", "tp.hcm", "sài gòn"]):
            res["primary_city"] = "Hồ Chí Minh"
        elif any(w in text for w in ["hà nội", "hn", "cầu giấy"]):
            res["primary_city"] = "Hà Nội"
        elif any(w in text for w in ["đà nẵng", "dn"]):
            res["primary_city"] = "Đà Nẵng"
        elif "remote" in text or "làm việc từ xa" in text:
            res["primary_city"] = "Remote"

        # 4. Trích xuất kỹ năng phổ biến
        known_skills = [
            "python", "java", "golang", "c++", "c#", "php", "javascript", "typescript",
            "react", "vue", "angular", "node.js", "docker", "kubernetes", "aws",
            "sql", "postgresql", "mysql", "mongodb", "redis", "fastapi", "django",
            "spring", "flutter", "react native", "devops", "ci/cd", "git"
        ]
        found = [s.title() for s in known_skills if re.search(rf"\b{re.escape(s)}\b", text)]
        res["hard_skills"] = found[:8]

        return res
