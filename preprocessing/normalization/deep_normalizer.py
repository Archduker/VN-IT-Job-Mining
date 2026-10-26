# -*- coding: utf-8 -*-
"""preprocessing.normalization.deep_normalizer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ chuẩn hóa chuyên sâu (Deep Normalization Engine) cho VN-IT-Job-Mining.

Chuẩn hóa triệt để 100% các chiều dữ liệu theo Target Schema 3:
  1. Kỹ năng (Tech Skills, Soft Skills, Domain Skills): Canonical mapping, lọc rác danh mục sàn.
  2. Thời gian làm việc & Thứ 7 (`is_saturday_work`).
  3. Hình thức làm việc (`work_mode`: Remote / Hybrid / Onsite).
  4. Trình độ học vấn (`standardized_education`).
  5. Độ tuổi yêu cầu (`age_min`, `age_max`).
  6. Phân cấp địa bàn `working_locations` thành `cities_list`, `districts_list`, và `detailed_locations`.
  7. Loại hợp đồng (`employment_type`: Full-time / Part-time / Internship / Contract).
  8. Chuẩn hóa chuỗi văn bản (Unicode NFKC, loại bỏ ký tự lạ).
  9. XÓA BỎ 100% CÁC TRƯỜNG `raw_*` Ở ROOT LEVEL TRONG GOLDEN MASTER DATASET.
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from preprocessing.normalization.cross_deduplicator import normalize_company_name
from preprocessing.normalization.text_cleaner import (
    classify_job_family,
    clean_job_title,
    normalize_seniority,
)

# Từ điển chuẩn hóa Kỹ năng Công nghệ (Canonical Tech Skills Taxonomy)
CANONICAL_TECH_SKILLS: Dict[str, str] = {
    # Frontend
    "react": "React", "reactjs": "React", "react.js": "React", "react js": "React",
    "vue": "Vue", "vuejs": "Vue", "vue.js": "Vue",
    "angular": "Angular", "angularjs": "Angular",
    "nextjs": "Next.js", "next.js": "Next.js", "next js": "Next.js",
    "nuxtjs": "Nuxt.js", "nuxt.js": "Nuxt.js",
    "javascript": "JavaScript", "js": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript",
    "html": "HTML", "html5": "HTML", "css": "CSS", "css3": "CSS",
    "tailwind": "Tailwind CSS", "tailwindcss": "Tailwind CSS",
    "bootstrap": "Bootstrap", "sass": "Sass", "scss": "Sass", "jquery": "jQuery",
    "redux": "Redux",

    # Backend
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js",
    "express": "Express.js", "expressjs": "Express.js",
    "nestjs": "NestJS", "nest.js": "NestJS",
    "python": "Python", "python3": "Python",
    "django": "Django", "fastapi": "FastAPI", "flask": "Flask",
    "java": "Java", "spring": "Spring", "spring boot": "Spring", "springboot": "Spring", "hibernate": "Hibernate",
    "golang": "Go", "go": "Go",
    "php": "PHP", "laravel": "Laravel", "symfony": "Symfony", "wordpress": "WordPress",
    "c#": "C#", "csharp": "C#", ".net": ".NET", "dotnet": ".NET", "asp.net": ".NET", ".net core": ".NET Core",
    "c++": "C++", "c/c++": "C++", "rust": "Rust", "scala": "Scala",
    "ruby": "Ruby", "rails": "Ruby on Rails", "ruby on rails": "Ruby on Rails",

    # Mobile
    "flutter": "Flutter", "react native": "React Native", "reactnative": "React Native",
    "ios": "iOS", "android": "Android", "swift": "Swift", "kotlin": "Kotlin",

    # Database
    "sql": "SQL", "mysql": "MySQL", "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "mongodb": "MongoDB", "mongo": "MongoDB", "redis": "Redis",
    "elasticsearch": "Elasticsearch", "elastic": "Elasticsearch",
    "oracle": "Oracle DB", "sql server": "SQL Server", "mssql": "SQL Server", "sqlite": "SQLite",
    "cassandra": "Cassandra", "dynamodb": "DynamoDB", "firebase": "Firebase",

    # Cloud & DevOps
    "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "aws": "AWS", "amazon web services": "AWS",
    "azure": "Azure", "gcp": "GCP", "google cloud": "GCP",
    "ci/cd": "CI/CD", "cicd": "CI/CD", "jenkins": "Jenkins", "gitlab": "GitLab CI", "github actions": "GitHub Actions",
    "terraform": "Terraform", "ansible": "Ansible", "linux": "Linux", "ubuntu": "Linux",
    "nginx": "Nginx", "apache": "Apache", "kafka": "Kafka", "rabbitmq": "RabbitMQ",

    # Data & AI/ML
    "spark": "Spark", "hadoop": "Hadoop", "airflow": "Airflow", "etl": "ETL", "data warehouse": "Data Warehouse", "dwh": "Data Warehouse",
    "pytorch": "PyTorch", "tensorflow": "TensorFlow", "keras": "Keras", "scikit-learn": "Scikit-Learn",
    "nlp": "NLP", "computer vision": "Computer Vision", "opencv": "OpenCV",
    "llm": "LLM", "generative ai": "Generative AI", "genai": "Generative AI", "rag": "RAG",
    "pandas": "Pandas", "numpy": "NumPy",

    # QA / Testing
    "selenium": "Selenium", "playwright": "Playwright", "cypress": "Cypress",
    "postman": "Postman", "jmeter": "JMeter", "automation test": "Automation Testing", "manual test": "Manual Testing",

    # System & Architecture
    "microservices": "Microservices", "rest api": "RESTful API", "restful": "RESTful API", "graphql": "GraphQL", "grpc": "gRPC",
    "oop": "OOP", "git": "Git", "design patterns": "Design Patterns",
}

# Kỹ năng Mềm (Soft Skills)
SOFT_SKILLS_KEYWORDS: Dict[str, str] = {
    "tiếng anh": "Tiếng Anh", "english": "Tiếng Anh", "toeic": "Tiếng Anh", "ielts": "Tiếng Anh",
    "tiếng nhật": "Tiếng Nhật", "japanese": "Tiếng Nhật", "n1": "Tiếng Nhật", "n2": "Tiếng Nhật", "n3": "Tiếng Nhật",
    "tiếng hàn": "Tiếng Hàn", "korean": "Tiếng Hàn",
    "giao tiếp": "Giao tiếp", "communication": "Giao tiếp",
    "làm việc nhóm": "Làm việc nhóm", "teamwork": "Làm việc nhóm",
    "giải quyết vấn đề": "Giải quyết vấn đề", "problem solving": "Giải quyết vấn đề",
    "tư duy logic": "Tư duy logic", "critical thinking": "Tư duy phản biện",
    "quản lý thời gian": "Quản lý thời gian", "time management": "Quản lý thời gian",
    "agile": "Agile/Scrum", "scrum": "Agile/Scrum", "kanban": "Agile/Scrum",
    "thuyết trình": "Thuyết trình", "presentation": "Thuyết trình",
    "chịu áp lực": "Chịu áp lực cao", "work under pressure": "Chịu áp lực cao",
}

# Kỹ năng Nghiệp vụ Miền (Domain Knowledge)
DOMAIN_SKILLS_KEYWORDS: Dict[str, str] = {
    "fintech": "Fintech", "tài chính": "Fintech", "ngân hàng": "Banking", "banking": "Banking",
    "e-commerce": "E-Commerce", "thương mại điện tử": "E-Commerce", "ecommerce": "E-Commerce",
    "edtech": "Edtech", "giáo dục": "Edtech",
    "healthtech": "Healthtech", "y tế": "Healthtech",
    "logistics": "Logistics", "chuỗi cung ứng": "Logistics",
    "bất động sản": "Proptech", "real estate": "Proptech",
    "bảo hiểm": "Insurtech", "insurance": "Insurtech",
    "an toàn thông tin": "An toàn thông tin", "bảo mật": "Cybersecurity", "security": "Cybersecurity",
    "blockchain": "Blockchain", "crypto": "Blockchain", "web3": "Web3",
}

# Danh mục tag rác ngành nghề của sàn tuyển dụng (cần lọc bỏ khỏi Tech Skills)
PORTAL_NOISE_SKILLS: Set[str] = {
    "it - phần mềm", "cntt - phần mềm", "phần mềm máy tính", "it - phần cứng / mạng",
    "công nghệ thông tin", "it phần mềm", "it phần cứng", "it helpdesk",
    "bán hàng / kinh doanh", "kinh doanh / bán hàng", "marketing / truyền thông / quảng cáo",
    "nhân sự", "hành chính / văn phòng", "kế toán / kiểm toán", "tài chính / ngân hàng",
    "chăm sóc khách hàng", "dịch vụ khách hàng", "tư vấn", "quản lý điều hành",
    "bán lẻ / bán sỉ", "sản xuất", "vận chuyển / giao nhận", "kho vận",
    "tiếng anh", "tiếng nhật", "tiếng hàn", "tiếng trung", "khác",
}

VIETNAMESE_PROVINCES: List[str] = [
    "Hà Nội", "Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Cần Thơ",
    "Bình Dương", "Đồng Nai", "Bà Rịa - Vũng Tàu", "Bắc Ninh", "Hưng Yên",
    "Quảng Nam", "Thừa Thiên Huế", "Khánh Hòa", "Lâm Đồng", "Quảng Ninh",
    "Thái Nguyên", "Vĩnh Phúc", "Bắc Giang", "Hải Dương", "Nam Định",
    "Thái Bình", "Ninh Bình", "Thanh Hóa", "Nghệ An", "Hà Tĩnh",
    "Quảng Bình", "Quảng Trị", "Bình Định", "Phú Yên", "Bình Thuận",
    "Đắk Lắk", "Gia Lai", "Tây Ninh", "Bình Phước", "Long An",
    "Tiền Giang", "Bến Tre", "Vĩnh Long", "Kiên Giang", "An Giang",
    "Toàn quốc", "Remote",
]


def normalize_text_unicode(text: Optional[str]) -> str:
    """Chuẩn hóa Unicode NFKC và dọn sạch ký tự ẩn, khoảng trắng kép."""
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", str(text))
    s = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def clean_benefits_list(benefits: Any) -> List[str]:
    """Làm sạch danh sách phúc lợi, khử các tiền tố nhiễu như 'Phúc lợi' của CareerViet."""
    if not benefits:
        return []
    if isinstance(benefits, str):
        raw_items = [benefits]
    elif isinstance(benefits, list):
        raw_items = benefits
    else:
        raw_items = [str(benefits)]

    cleaned = []
    for item in raw_items:
        s = normalize_text_unicode(str(item))
        # Bỏ tiền tố "Phúc lợi", "Phúc lợi:", "Chế độ đãi ngộ"
        s = re.sub(r"^(?:phúc\s+lợi|chế\s+độ\s+(?:đãi\s+ngộ|phúc\s+lợi))\s*[:–-]?\s*", "", s, flags=re.I)
        s = s.strip()
        if s and len(s) >= 3:
            cleaned.append(s)
    return cleaned


def normalize_company_categories(cat: Any) -> List[str]:
    """Chuẩn hóa category_text của công ty thành list[str]."""
    if not cat:
        return []
    if isinstance(cat, list):
        items = cat
    elif isinstance(cat, str):
        items = re.split(r"[,;/\n]+", cat)
    else:
        items = [str(cat)]

    res: List[str] = []
    for it in items:
        clean_it = normalize_text_unicode(str(it)).strip()
        if clean_it and len(clean_it) >= 2:
            res.append(clean_it)
    return res


def extract_hierarchical_locations(
    working_locations_raw: Any,
    raw_location_text: str = "",
    company_address: str = "",
) -> Tuple[List[str], List[str], List[Dict[str, str]]]:
    """Phân cấp working_locations thành:
    - cities_list: Danh sách tỉnh/thành phố chuẩn
    - districts_list: Danh sách quận/huyện chuẩn
    - detailed_locations: Danh sách các địa điểm chi tiết phân cấp [{'province': ..., 'district': ..., 'full_address': ...}]
    """
    raw_locs: List[str] = []
    if isinstance(working_locations_raw, list):
        raw_locs = [str(x).strip() for x in working_locations_raw if x and str(x).strip()]
    elif isinstance(working_locations_raw, str) and working_locations_raw.strip():
        raw_locs = [working_locations_raw.strip()]

    combined_text = " ".join(raw_locs + [str(raw_location_text or ""), str(company_address or "")]).lower()
    combined_text = normalize_text_unicode(combined_text)

    # 1. Nhận diện các tỉnh/thành phố chuẩn
    cities: Set[str] = set()
    for p in VIETNAMESE_PROVINCES:
        if p.lower() in combined_text:
            cities.add(p)

    if not cities:
        if any(k in combined_text for k in ["hcm", "sài gòn", "tp.hcm", "tp hcm", "tp hồ chí minh", "thủ đức"]):
            cities.add("Hồ Chí Minh")
        elif any(k in combined_text for k in ["hn", "hà nội", "cầu giấy", "ba đình", "đống đa"]):
            cities.add("Hà Nội")
        elif any(k in combined_text for k in ["đà nẵng", "dn"]):
            cities.add("Đà Nẵng")
        elif "remote" in combined_text or "từ xa" in combined_text:
            cities.add("Remote")
        else:
            cities.add("Toàn quốc")

    # 2. Nhận diện các quận/huyện
    districts: Set[str] = set()
    district_patterns = [
        r"(quận\s+\d+|quận\s+[a-zA-Zà-ỹÀ-Ỹ\s]+|huyện\s+[a-zA-Zà-ỹÀ-Ỹ\s]+|thị\s+xã\s+[a-zA-Zà-ỹÀ-Ỹ\s]+|thành\s+phố\s+thủ\s+đức)",
        r"(cầu\s+giấy|ba\s+đình|đống\s+đa|thanh\s+xuân|nam\s+từ\s+liêm|bắc\s+từ\s+liêm|hoàn\s+kiếm|hai\s+bà\s+trưng|hà\s+đông|hoàng\s+mai|long\s+biên|tây\s+hồ)",
        r"(bình\s+thạnh|tân\s+bình|phú\s+nhuận|gò\s+vấp|thủ\s+đức|tân\s+phú|bình\s+tân)",
    ]
    for pat in district_patterns:
        matches = re.findall(pat, combined_text, re.I)
        for m in matches:
            if isinstance(m, str) and len(m.strip()) >= 3:
                clean_d = m.strip().title()
                if clean_d.lower() not in ("quận", "huyện", "thị xã"):
                    districts.add(clean_d)

    major_provinces = sorted(list(cities), key=len, reverse=True)
    address_candidates: List[str] = []
    for loc_str in raw_locs:
        cleaned_loc = re.sub(r"^địa\s+điểm\s+làm\s+việc\s*", "", loc_str, flags=re.I).strip()
        city_split_pattern = rf"(?=(?:{'|'.join(re.escape(c) for c in major_provinces if len(c) > 3)}))"
        if city_split_pattern and len(major_provinces) > 1:
            chunks = re.split(city_split_pattern, cleaned_loc)
            for ch in chunks:
                if ch.strip() and len(ch.strip()) >= 4:
                    address_candidates.append(ch.strip())
        else:
            if cleaned_loc:
                address_candidates.append(cleaned_loc)

    if not address_candidates:
        if raw_location_text:
            address_candidates.append(str(raw_location_text))
        elif company_address:
            address_candidates.append(str(company_address))

    detailed_locations: List[Dict[str, str]] = []
    seen_addr: Set[str] = set()
    for addr in address_candidates:
        addr_clean = normalize_text_unicode(addr)
        if not addr_clean or addr_clean.lower() in seen_addr:
            continue
        seen_addr.add(addr_clean.lower())

        matched_prov = None
        for p in major_provinces:
            if p.lower() in addr_clean.lower():
                matched_prov = p
                break
        if not matched_prov:
            matched_prov = major_provinces[0] if major_provinces else "Hồ Chí Minh"

        matched_dist = None
        for d in districts:
            if d.lower() in addr_clean.lower():
                matched_dist = d
                break

        detailed_locations.append({
            "province": matched_prov,
            "district": matched_dist or "Chưa xác định",
            "full_address": addr_clean,
        })

    # Lọc bỏ các entries quá ngắn (chỉ là tên thành phố trần) nếu đã có địa chỉ cụ thể
    has_specific = any(len(x["full_address"]) > 20 and x["district"] != "Chưa xác định" for x in detailed_locations)
    if has_specific:
        detailed_locations = [x for x in detailed_locations if len(x["full_address"]) > 15]

    if not detailed_locations:
        for p in (cities or ["Toàn quốc"]):
            detailed_locations.append({
                "province": p,
                "district": "Chưa xác định",
                "full_address": p,
            })

    return sorted(list(cities)), sorted(list(districts))[:5], detailed_locations


def extract_cities_and_districts(record: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Tương thích ngược: Bóc tách danh sách thành phố chuẩn và danh sách quận/huyện."""
    locs = record.get("working_locations") or [record.get("raw_location_text") or ""]
    c, d, _ = extract_hierarchical_locations(locs, record.get("raw_location_text") or "", record.get("company_address") or "")
    return c, d


def extract_normalized_skills(raw_skills: List[str], text_corpus: str) -> Dict[str, List[str]]:
    """Phân loại và chuẩn hóa 3 nhóm kỹ năng: Hard Skills, Soft Skills, Domain Knowledge."""
    hard_skills: Set[str] = set()
    soft_skills: Set[str] = set()
    domain_skills: Set[str] = set()
    portal_categories: Set[str] = set()

    clean_corpus = normalize_text_unicode(text_corpus).lower()

    # 1. Xử lý các skills_list có sẵn từ trước
    for raw in raw_skills or []:
        s_clean = normalize_text_unicode(raw).lower()
        if not s_clean or len(s_clean) < 2:
            continue

        # Kiểm tra danh mục rác sàn
        if s_clean in PORTAL_NOISE_SKILLS or any(p in s_clean for p in ["công ty cổ phần", "tập đoàn", "chi nhánh"]):
            portal_categories.add(normalize_text_unicode(raw))
            continue

        # Kiểm tra Tech Skills
        matched_tech = False
        if s_clean in CANONICAL_TECH_SKILLS:
            hard_skills.add(CANONICAL_TECH_SKILLS[s_clean])
            matched_tech = True
        else:
            for alias, canonical in CANONICAL_TECH_SKILLS.items():
                if len(alias) >= 3 and alias in s_clean:
                    hard_skills.add(canonical)
                    matched_tech = True
                    break

        # Kiểm tra Soft Skills
        matched_soft = False
        for kw, canonical in SOFT_SKILLS_KEYWORDS.items():
            if kw in s_clean:
                soft_skills.add(canonical)
                matched_soft = True
                break

        # Kiểm tra Domain
        matched_domain = False
        for kw, canonical in DOMAIN_SKILLS_KEYWORDS.items():
            if kw in s_clean:
                domain_skills.add(canonical)
                matched_domain = True
                break

        if not matched_tech and not matched_soft and not matched_domain:
            if re.match(r"^[A-Za-z0-9#+.\s-]+$", raw) and len(raw) <= 25:
                hard_skills.add(normalize_text_unicode(raw).title())

    # 2. Quét văn bản JD bổ sung Tech Skills nếu còn thiếu
    if len(hard_skills) < 5:
        for alias, canonical in CANONICAL_TECH_SKILLS.items():
            if len(alias) >= 2:
                pattern = rf"\b{re.escape(alias)}\b"
                if re.search(pattern, clean_corpus):
                    hard_skills.add(canonical)

    # 3. Quét Soft Skills từ văn bản
    for kw, canonical in SOFT_SKILLS_KEYWORDS.items():
        if re.search(rf"\b{re.escape(kw)}\b", clean_corpus):
            soft_skills.add(canonical)

    # 4. Quét Domain Skills từ văn bản
    for kw, canonical in DOMAIN_SKILLS_KEYWORDS.items():
        if re.search(rf"\b{re.escape(kw)}\b", clean_corpus):
            domain_skills.add(canonical)

    return {
        "hard_skills": sorted(list(hard_skills)),
        "soft_skills": sorted(list(soft_skills)),
        "domain_skills": sorted(list(domain_skills)),
        "portal_categories": sorted(list(portal_categories)),
    }


def extract_saturday_work(record: Dict[str, Any]) -> Optional[bool]:
    """Bóc tách cờ làm việc thứ 7: True (làm T7), False (nghỉ T7), None (chưa rõ)."""
    text = f"{record.get('raw_working_time') or ''} {record.get('raw_description_text') or ''} {record.get('raw_requirements_text') or ''} {' '.join(record.get('benefits_list') or record.get('benefits_text') or [])}".lower()
    text = normalize_text_unicode(text)

    # 1. Nhận diện Nghỉ Thứ 7
    off_pattern = r"(?:nghỉ\s+(?:thứ\s+7|t7)|thứ\s+2\s*[-–tođến]+\s*thứ\s+6|t2\s*[-–]\s*t6|thứ\s+hai\s+đến\s+thứ\s+sáu|monday\s+to\s+friday|mon\s*-\s*fri|5\s*ngày\s*/\s*tuần|5\s*days\s*a\s*week)"
    if re.search(off_pattern, text):
        return False

    # 2. Nhận diện Có Làm Thứ 7 (Sáng thứ 7 hoặc cả ngày thứ 7)
    work_pattern = r"(?:sáng\s+thứ\s+7|thứ\s+2\s*[-–tođến]+\s*(?:hết\s+)?thứ\s+7|t2\s*[-–]\s*t7|thứ\s+hai\s+đến\s+thứ\s+bảy|làm\s+(?:cả\s+)?thứ\s+7|work\s+on\s+saturday|thứ\s+7\s*cách\s*tuần)"
    if re.search(work_pattern, text):
        return True

    return None


def extract_work_mode(record: Dict[str, Any]) -> str:
    """Chuẩn hóa hình thức làm việc: Remote, Hybrid, Onsite."""
    raw = normalize_text_unicode(str(record.get("raw_work_mode") or record.get("work_mode") or "")).lower()
    text = f"{raw} {record.get('job_title') or ''} {record.get('raw_description_text') or ''} {record.get('raw_requirements_text') or ''}".lower()

    if re.search(r"(?:hybrid|linh\s+hoạt|wfh\s+\d+\s*ngày|kết\s+hợp\s+(?:từ\s+xa|online)|linh\s+hoạt\s+địa\s+điểm)", text):
        return "Hybrid"
    if re.search(r"(?:100%\s*remote|toàn\s+thời\s+gian\s+từ\s+xa|làm\s+việc\s+từ\s+xa|làm\s+tại\s+nhà|work\s+from\s+home|\bremote\b)", text):
        return "Remote"
    return "Onsite"


def extract_education(record: Dict[str, Any]) -> str:
    """Chuẩn hóa trình độ học vấn."""
    text = f"{record.get('raw_education_text') or record.get('standardized_education') or ''} {record.get('raw_requirements_text') or ''} {record.get('raw_description_text') or ''}".lower()
    text = normalize_text_unicode(text)

    if re.search(r"(?:không\s+yêu\s+cầu\s+bằng|không\s+cần\s+bằng|không\s+phân\s+biệt\s+bằng)", text):
        return "Không yêu cầu"
    if re.search(r"(?:thạc\s+sĩ|tiến\s+sĩ|master|phd)", text):
        return "Thạc sĩ / Cao học"
    if re.search(r"(?:đại\s+học|cử\s+nhân|kỹ\s+sư|bachelor|university|tốt\s+nghiệp\s+đh|bằng\s+đh)", text):
        return "Đại học"
    if re.search(r"(?:cao\s+đẳng|college)", text):
        return "Cao đẳng"
    if re.search(r"(?:trung\s+cấp|học\s+nghề|trung\s+học)", text):
        return "Trung cấp / Nghề"

    return "Không đề cập"


def extract_age_range(record: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    """Bóc tách dải tuổi yêu cầu (age_min, age_max)."""
    text = f"{record.get('raw_age_text') or ''} {record.get('raw_requirements_text') or ''} {record.get('raw_description_text') or ''}".lower()
    text = normalize_text_unicode(text)

    # 1. Khoảng: từ 22 - 30 tuổi
    m_range = re.search(r"(?:độ\s+tuổi|tuổi|age)\s*(?:từ|khoảng|:)?\s*(\d{2})\s*[-–tođến]+\s*(\d{2})", text)
    if m_range:
        a_min, a_max = int(m_range.group(1)), int(m_range.group(2))
        if 18 <= a_min <= a_max <= 65:
            return a_min, a_max

    # 2. Dưới X tuổi
    m_under = re.search(r"(?:dưới|không\s+quá|<)\s*(\d{2})\s*tuổi", text)
    if m_under:
        a_max = int(m_under.group(1))
        if 20 <= a_max <= 65:
            return None, a_max

    # 3. Từ X tuổi trở lên
    m_over = re.search(r"(?:từ|trên|>=)\s*(\d{2})\s*tuổi", text)
    if m_over:
        a_min = int(m_over.group(1))
        if 18 <= a_min <= 60:
            return a_min, None

    return None, None


def normalize_employment_type(record: Dict[str, Any]) -> str:
    """Chuẩn hóa loại hình hợp đồng: Full-time, Part-time, Internship, Contract."""
    raw = normalize_text_unicode(str(record.get("raw_employment_type") or record.get("employment_type") or "")).lower()
    title = normalize_text_unicode(str(record.get("job_title") or "")).lower()
    comb = f"{raw} {title}"

    if any(k in comb for k in ["thực tập", "intern", "trainee"]):
        return "Internship"
    if any(k in comb for k in ["part-time", "parttime", "bán thời gian"]):
        return "Part-time"
    if any(k in comb for k in ["hợp đồng", "contract", "freelance", "cộng tác viên", "ctv", "temporary"]):
        return "Contract"
    return "Full-time"


def clean_nans_to_none(obj: Any) -> Any:
    """Đệ quy làm sạch toàn bộ giá trị float('nan') thành None để JSON luôn hợp lệ."""
    if isinstance(obj, float) and (math.isnan(obj) or np.isnan(obj)):
        return None
    if isinstance(obj, dict):
        return {k: clean_nans_to_none(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_nans_to_none(x) for x in obj]
    return obj


def deep_normalize_record(record: Dict[str, Any], keep_raw: bool = False) -> Dict[str, Any]:
    """Chuẩn hóa toàn diện một bản ghi tuyển dụng IT theo Target Schema 3.
    
    Quy chuẩn nghiệm thu:
      - Loại bỏ 100% các trường raw_* ở root level (khi keep_raw=False).
      - Đổi tên raw_description_text -> description_text, raw_requirements_text -> requirements_text trong jd_clean_text.
      - Phân cấp working_locations thành cities_list, districts_list, detailed_locations.
      - Chuẩn hóa company.category_text thành list[str].
      - Bóc tách đầy đủ thuộc tính ẩn vào Extract_from_JD.
    """
    rec = dict(record)

    # 1. Định danh và Tiêu đề
    job_id_global = rec.get("job_id_global")
    source_platform = rec.get("source_platform")
    source_job_id = rec.get("source_job_id")
    source_url = rec.get("source_url")
    title_raw = rec.get("job_title") or rec.get("title") or ""
    clean_title = clean_job_title(normalize_text_unicode(title_raw))

    # 2. Công ty
    comp_name = normalize_text_unicode(rec.get("company_name") or (rec.get("company", {}).get("company_name") if isinstance(rec.get("company"), dict) else ""))
    comp_norm = normalize_company_name(comp_name) if comp_name else None
    comp_scale = rec.get("company_scale") or (rec.get("company", {}).get("company_scale") if isinstance(rec.get("company"), dict) else None)
    cat_raw = rec.get("category_text") or rec.get("raw_category_text") or (rec.get("company", {}).get("category_text") if isinstance(rec.get("company"), dict) else None)
    comp_cats = normalize_company_categories(cat_raw)

    # 3. Tiền lương
    sal_dict = rec.get("salary") if isinstance(rec.get("salary"), dict) else {}
    salary_text = sal_dict.get("salary_text") or rec.get("salary_text_raw") or rec.get("raw_salary_text") or "Thỏa thuận"
    salary_min_vnd = sal_dict.get("salary_min_vnd") if "salary_min_vnd" in sal_dict else rec.get("salary_min_vnd")
    salary_max_vnd = sal_dict.get("salary_max_vnd") if "salary_max_vnd" in sal_dict else rec.get("salary_max_vnd")
    salary_min_orig = sal_dict.get("salary_min_original") if "salary_min_original" in sal_dict else rec.get("salary_min_original")
    salary_max_orig = sal_dict.get("salary_max_original") if "salary_max_original" in sal_dict else rec.get("salary_max_original")
    salary_curr_orig = sal_dict.get("salary_currency_original") or rec.get("salary_currency_original") or "VND"
    pay_period = sal_dict.get("pay_period") or rec.get("pay_period") or "month"
    is_neg = sal_dict.get("is_negotiable") if "is_negotiable" in sal_dict else (bool(rec.get("is_negotiable")) if rec.get("is_negotiable") is not None else True)
    has_comm = sal_dict.get("has_commission") if "has_commission" in sal_dict else bool(rec.get("has_commission", False))
    salary_source = sal_dict.get("salary_source") or rec.get("salary_source") or "header_negotiable"
    salary_curr = sal_dict.get("salary_currency") or rec.get("salary_currency") or "VND"
    salary_fx_rate = sal_dict.get("salary_fx_rate_to_vnd") or rec.get("salary_fx_rate_to_vnd") or 1.0
    salary_fx_date = sal_dict.get("salary_fx_rate_date") or rec.get("salary_fx_rate_date")
    salary_fx_src = sal_dict.get("salary_fx_source") or rec.get("salary_fx_source") or "identity_vnd"
    is_salary_neg_decl = sal_dict.get("is_salary_negotiable_declared") if "is_salary_negotiable_declared" in sal_dict else (rec.get("is_salary_negotiable_declared") or (1 if is_neg else 0))

    # 4. Thời gian
    date_dict = rec.get("date") if isinstance(rec.get("date"), dict) else {}
    posted_date = date_dict.get("posted_date") or rec.get("posted_date") or rec.get("raw_posted_date")
    updated_date = date_dict.get("updated_date") or rec.get("updated_date") or rec.get("raw_updated_at")
    deadline_date = date_dict.get("deadline_date") or rec.get("deadline_date") or rec.get("raw_deadline")
    crawled_iso = date_dict.get("crawled_at_iso") or rec.get("crawled_at_iso") or rec.get("crawled_at")

    # 5. Địa điểm & Phân cấp
    raw_locs = rec.get("working_locations") or [rec.get("raw_location_text") or ""]
    if not isinstance(raw_locs, list):
        raw_locs = [str(raw_locs)]
    cities_list, districts_list, detailed_locations = extract_hierarchical_locations(
        raw_locs,
        rec.get("raw_location_text") or "",
        rec.get("company_address") or "",
    )
    primary_city = cities_list[0] if cities_list else "Toàn quốc"

    # 6. Thuộc tính chung
    emp_type = normalize_employment_type(rec)
    work_mode = extract_work_mode(rec)
    min_exp_years = rec.get("min_experience_years")
    headcount = rec.get("headcount")

    # 7. Văn bản JD làm sạch
    jd_dict = rec.get("jd_clean_text") if isinstance(rec.get("jd_clean_text"), dict) else {}
    raw_benefits = jd_dict.get("benefits_text") or rec.get("benefits_list") or []
    benefits_clean = clean_benefits_list(raw_benefits)
    raw_desc = normalize_text_unicode(jd_dict.get("raw_description_text") or jd_dict.get("description_text") or rec.get("raw_description_text") or rec.get("job_description") or "")
    raw_req = normalize_text_unicode(jd_dict.get("raw_requirements_text") or jd_dict.get("requirements_text") or rec.get("raw_requirements_text") or rec.get("job_requirements") or "")

    comb_text = f"{clean_title} {raw_desc} {raw_req}"

    # 8. Kỹ năng & Bóc tách yêu cầu / vị trí (nhóm skills và extract_from_jd)
    # Khế ước: DỪNG TOÀN BỘ if-else phân loại hard/soft/domain skills;
    # chỉ lưu trữ danh sách kỹ năng thuần túy vào nhóm skills.
    raw_skills = rec.get("skills_list") or rec.get("skills") or (rec.get("skills", {}).get("skills_list") if isinstance(rec.get("skills"), dict) else [])
    if isinstance(raw_skills, str):
        raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
    elif not isinstance(raw_skills, list):
        raw_skills = []

    # Thu dọn và lọc trùng kỹ năng
    cleaned_skills_set = set()
    for s in raw_skills:
        s_clean = normalize_text_unicode(str(s)).strip()
        if s_clean and len(s_clean) >= 2:
            cleaned_skills_set.add(s_clean)
    all_skills = sorted(list(cleaned_skills_set))

    sat_work = extract_saturday_work(rec)
    std_edu = extract_education(rec)
    age_min, age_max = extract_age_range(rec)
    std_seniority = normalize_seniority(rec.get("standardized_seniority") or rec.get("raw_seniority_text"), clean_title)

    words = re.findall(r"\w+", f"{raw_desc} {raw_req}")
    word_count = len(words)
    char_count = len(f"{raw_desc} {raw_req}")
    is_stub = (word_count < 30)

    # Lương winsorized & log-transform
    sal_winsorized = rec.get("salary_max_winsorized") or (rec.get("extract_from_jd", {}).get("salary_max_winsorized") if isinstance(rec.get("extract_from_jd"), dict) else None)
    is_sal_winsorized = bool(rec.get("is_salary_winsorized", False) or (rec.get("extract_from_jd", {}).get("is_salary_winsorized") if isinstance(rec.get("extract_from_jd"), dict) else False))
    s_eval = sal_winsorized or salary_max_vnd
    log_salary_max = round(float(np.log1p(s_eval)), 4) if s_eval is not None and not (isinstance(s_eval, float) and math.isnan(s_eval)) and s_eval > 0 else None

    # Nhóm bóc tách yêu cầu và vị trí (extract_from_jd)
    extract_from_jd_dict = {
        "standardized_education": std_edu,
        "standardized_seniority": std_seniority,
        "age_min": age_min,
        "age_max": age_max,
        "is_saturday_work": sat_work,
        "word_count": word_count,
        "char_count": char_count,
        "is_stub_jd": is_stub,
        "primary_language": "vi",
        "company_size_min": rec.get("company_size_min"),
        "company_size_max": rec.get("company_size_max"),
        "company_scale_tier": rec.get("company_scale_tier"),
        "skills_count": len(all_skills),
        "benefits_count": len(benefits_clean),
        "imputed_fields": rec.get("imputed_fields"),
        "salary_max_winsorized": sal_winsorized,
        "is_salary_winsorized": is_sal_winsorized,
        "is_outlier_capped": bool(rec.get("is_outlier_capped", False) or is_sal_winsorized),
        "log_salary_max": log_salary_max,
        "quality_score": rec.get("quality_score"),
    }

    # Lắp ráp đối tượng kết quả
    out: Dict[str, Any] = {
        "job_id_global": job_id_global,
        "source_platform": source_platform,
        "source_job_id": source_job_id,
        "source_url": source_url,
        "job_title": clean_title,
        "company": {
            "company_name": comp_name,
            "company_name_normalized": comp_norm,
            "company_scale": comp_scale,
            "category_text": comp_cats,
        },
        "salary": {
            "salary_text": salary_text,
            "salary_min_vnd": salary_min_vnd,
            "salary_max_vnd": salary_max_vnd,
            "salary_min_original": salary_min_orig,
            "salary_max_original": salary_max_orig,
            "salary_currency_original": salary_curr_orig,
            "pay_period": pay_period,
            "is_negotiable": is_neg,
            "has_commission": has_comm,
            "salary_source": salary_source,
            "salary_currency": salary_curr,
            "salary_fx_rate_to_vnd": salary_fx_rate,
            "salary_fx_rate_date": salary_fx_date,
            "salary_fx_source": salary_fx_src,
            "is_salary_negotiable_declared": is_salary_neg_decl,
        },
        "date": {
            "posted_date": posted_date,
            "updated_date": updated_date,
            "deadline_date": deadline_date,
            "crawled_at_iso": crawled_iso,
        },
        "working_locations": raw_locs,
        "cities_list": cities_list,
        "districts_list": districts_list,
        "detailed_locations": detailed_locations,
        "employment_type": emp_type,
        "work_mode": work_mode,
        "min_experience_years": min_exp_years,
        "headcount": headcount,
        "jd_clean_text": {
            "benefits_text": benefits_clean,
            # Nếu keep_raw=True thì giữ tên raw_*, ngược lại chuyển thành tên sạch không raw_
            ("raw_description_text" if keep_raw else "description_text"): raw_desc,
            ("raw_requirements_text" if keep_raw else "requirements_text"): raw_req,
        },
        # Nhóm skills độc lập ở root level (không dùng if-else hard/soft)
        "skills": {
            "skills_list": all_skills,
            "skills_count": len(all_skills),
        },
        # Nhóm bóc tách yêu cầu và vị trí (extract_from_jd)
        "extract_from_jd": extract_from_jd_dict,
        "Extract_from_JD": extract_from_jd_dict,  # Alias tương thích ngược
        # Giữ các trường phẳng tiện dụng cho truy vấn nhanh
        "primary_city": primary_city,
        "standardized_districts": districts_list,
        "is_saturday_work": sat_work,
        "standardized_education": std_edu,
        "age_min": age_min,
        "age_max": age_max,
        "standardized_seniority": std_seniority,
        "log_salary_max": log_salary_max,
        "is_outlier_capped": bool(rec.get("is_outlier_capped", False) or is_sal_winsorized),
        "quality_score": rec.get("quality_score"),
    }

    # Nếu keep_raw=True, giữ lại các trường raw_* ở root làm input cho bước sau
    if keep_raw:
        for k, v in rec.items():
            if k.startswith("raw_") and k not in out:
                out[k] = v
    else:
        # XÓA BỎ 100% CÁC TRƯỜNG RAW_* Ở ROOT LEVEL
        for k in list(out.keys()):
            if k.startswith("raw_"):
                del out[k]

    return clean_nans_to_none(out)
