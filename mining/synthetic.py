"""Bộ dữ liệu giả có đáp án cài sẵn, để test và chạy thử pipeline khi chưa có dữ liệu thật.

KHÔNG dùng kết quả chạy trên dữ liệu này để báo cáo. Output của chế độ --synthetic ghi vào
mining/artifacts/_synthetic/ và mining_metrics.json có "synthetic": true.

Đáp án cài sẵn (SyntheticBundle.truth):
- Luật: {Spring Boot} => {Java} (conf = 1), {Flutter} => {Dart} (conf = 1), {React} => {JavaScript} (~0.95).
- 8 nhóm nghề có bộ kỹ năng tách biệt -> phân cụm phải tìm được cấu trúc.
- Lương tăng theo cấp bậc, HN/HCM cao hơn tỉnh khác, Kubernetes +20%, AWS +12%.
- Tin bất thường: Intern/Fresher đòi 18 kỹ năng; Junior lương 300–450 triệu.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from mining.config import RANDOM_STATE, SENIORITY_ORDER_LABELS

# (tên nhóm nghề, tỉ lệ, các stack: [(kỹ năng, xác suất), ...], từ khóa JD, hệ số lương)
FAMILIES: list[tuple[str, float, list[list[tuple[str, float]]], str, float]] = [
    ("Backend", 0.26, [
        [("Java", 1.0), ("Spring Boot", 0.85), ("SQL", 0.8), ("Microservices", 0.45), ("Kafka", 0.25), ("MySQL", 0.4)],
        [("Python", 1.0), ("Django", 0.7), ("PostgreSQL", 0.6), ("SQL", 0.6), ("Redis", 0.3)],
        [("Golang", 1.0), ("gRPC", 0.5), ("PostgreSQL", 0.6), ("Redis", 0.4), ("Microservices", 0.5)],
    ], "api server database xử lý nghiệp vụ hệ thống backend", 1.05),
    ("Frontend", 0.17, [
        [("React", 1.0), ("JavaScript", 0.95), ("TypeScript", 0.6), ("HTML", 0.8), ("CSS", 0.8), ("Next.js", 0.35)],
        [("Vue.js", 1.0), ("JavaScript", 0.95), ("HTML", 0.85), ("CSS", 0.85)],
        [("Angular", 1.0), ("TypeScript", 0.95), ("RxJS", 0.5), ("HTML", 0.7), ("CSS", 0.7)],
    ], "giao diện web responsive người dùng frontend", 0.95),
    ("Mobile", 0.11, [
        [("Flutter", 1.0), ("Dart", 1.0), ("Firebase", 0.4)],
        [("Kotlin", 1.0), ("Android", 1.0), ("Java", 0.35)],
        [("Swift", 1.0), ("iOS", 1.0), ("Xcode", 0.5)],
    ], "ứng dụng di động mobile app store", 1.0),
    ("Data Science/AI", 0.12, [
        [("Python", 1.0), ("Machine Learning", 0.85), ("PyTorch", 0.5), ("TensorFlow", 0.35), ("SQL", 0.5), ("Pandas", 0.6)],
        [("SQL", 1.0), ("Power BI", 0.7), ("Excel", 0.6), ("Python", 0.4), ("Spark", 0.25)],
    ], "dữ liệu mô hình phân tích data pipeline ai", 1.12),
    ("DevOps/Cloud", 0.10, [
        [("Docker", 1.0), ("Kubernetes", 0.8), ("AWS", 0.65), ("Terraform", 0.4), ("CI/CD", 0.75), ("Linux", 0.7)],
        [("Linux", 1.0), ("Jenkins", 0.6), ("Docker", 0.7), ("CI/CD", 0.7), ("Azure", 0.4)],
    ], "hạ tầng vận hành cloud triển khai devops", 1.18),
    ("Kiểm thử (QA/QC)", 0.09, [
        [("Manual Testing", 1.0), ("Test Case", 0.8), ("Jira", 0.6), ("Postman", 0.5)],
        [("Selenium", 1.0), ("Automation Testing", 0.9), ("Java", 0.3), ("Postman", 0.4)],
    ], "kiểm thử chất lượng phần mềm test", 0.85),
    ("Phân tích nghiệp vụ (BA)", 0.06, [
        [("Business Analysis", 1.0), ("UML", 0.6), ("Jira", 0.6), ("SQL", 0.4), ("Agile", 0.5)],
    ], "yêu cầu nghiệp vụ khách hàng tài liệu phân tích", 0.95),
    ("Fullstack", 0.09, [
        [("Node.js", 1.0), ("JavaScript", 0.95), ("React", 0.6), ("MongoDB", 0.6), ("HTML", 0.5)],
        [("PHP", 1.0), ("Laravel", 0.8), ("MySQL", 0.7), ("JavaScript", 0.7), ("Vue.js", 0.4)],
    ], "fullstack web end to end", 1.0),
]
GENERAL_SKILLS = [("Git", 0.45), ("English", 0.25), ("Agile", 0.2), ("Docker", 0.12)]
SKILL_PREMIUM = {"Kubernetes": 0.20, "AWS": 0.12, "Golang": 0.12, "Kafka": 0.08, "Machine Learning": 0.08}

SENIORITY_PROBS = [0.14, 0.28, 0.28, 0.22, 0.08]
SENIORITY_BASE_MIL = [7.0, 15.0, 25.0, 40.0, 55.0]
EXP_BASE = [0, 1, 2, 4, 6]

LOCATIONS = [("Hà Nội", 0.40, 1.25), ("Hồ Chí Minh", 0.38, 1.30), ("Đà Nẵng", 0.09, 0.85),
             ("Remote", 0.03, 1.15), ("Cần Thơ", 0.04, 0.80), ("Hải Phòng", 0.03, 0.82),
             ("Bình Dương", 0.03, 0.84), ("Nhiều địa điểm", 0.03, 1.10), ("Toàn quốc", 0.01, 1.00)]
SOURCES = ["topcv", "topdev", "vietnamworks", "careerviet", "vieclam24h", "itviec", "glints", "jobsgo"]


def skill_slug(name: str) -> str:
    s = name.lower().replace("c#", "csharp").replace(".net", "dotnet").replace("c++", "cpp")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "unknown"


@dataclass
class SyntheticBundle:
    golden: pd.DataFrame
    features: pd.DataFrame
    encoding_dict: dict[str, Any]
    truth: dict[str, Any] = field(default_factory=dict)


def make_synthetic_jobs(
    n_jobs: int = 1500,
    seed: int = RANDOM_STATE,
    salary_disclosed_rate: float = 0.45,
    n_fresher_anomalies: int = 12,
    n_salary_anomalies: int = 6,
) -> SyntheticBundle:
    rng = np.random.default_rng(seed)
    fam_probs = np.array([f[1] for f in FAMILIES])
    fam_probs = fam_probs / fam_probs.sum()
    loc_probs = np.array([loc[1] for loc in LOCATIONS])
    loc_probs = loc_probs / loc_probs.sum()
    all_skills = sorted({s for f in FAMILIES for st in f[2] for s, _ in st} | {s for s, _ in GENERAL_SKILLS})

    rows: list[dict[str, Any]] = []
    for i in range(n_jobs):
        fi = rng.choice(len(FAMILIES), p=fam_probs)
        fam, _, stacks, jd_kw, fam_mult = FAMILIES[fi]
        stack = stacks[rng.integers(len(stacks))]
        skills = [s for s, p in stack if rng.random() < p]
        skills += [s for s, p in GENERAL_SKILLS if rng.random() < p and s not in skills]

        if rng.random() < 0.02:
            sen_ord, sen_label = -1, None
        else:
            sen_ord = int(rng.choice(5, p=SENIORITY_PROBS))
            sen_label = SENIORITY_ORDER_LABELS[sen_ord]
        exp = float(EXP_BASE[max(sen_ord, 0)] + rng.integers(0, 2)) if rng.random() > 0.15 else np.nan

        li = rng.choice(len(LOCATIONS), p=loc_probs)
        city, _, loc_mult = LOCATIONS[li]

        base = SENIORITY_BASE_MIL[sen_ord] if sen_ord >= 0 else 20.0
        premium = np.prod([1 + SKILL_PREMIUM.get(s, 0.0) for s in skills])
        salary = base * fam_mult * loc_mult * premium * float(np.exp(rng.normal(0, 0.12)))
        disclosed = rng.random() < salary_disclosed_rate

        title = f"{fam} Developer {sen_label}" if sen_ord >= 0 else f"{fam} Developer"
        rows.append({
            "job_id_global": f"syn_{i:05d}",
            "source_platform": SOURCES[rng.integers(len(SOURCES))],
            "job_title": title,
            "company_name": f"Công ty {rng.integers(1, 80):02d}",
            "job_family": fam,
            "seniority": sen_label,
            "exp_min_years": exp,
            "city_normalized": city,
            "skills_extracted": skills,
            "salary_avg": round(salary, 2) if disclosed else np.nan,
            "salary_min": round(salary * 0.85, 2) if disclosed else np.nan,
            "salary_max": round(salary * 1.15, 2) if disclosed else np.nan,
            "is_negotiable": not disclosed,
            "job_description": f"Tuyển {title}. Công việc: {jd_kw}.",
            "job_requirements": "Yêu cầu: " + ", ".join(skills) + ".",
            "_anomaly": None,
        })

    # Tin bất thường cài sẵn
    picks = rng.choice(n_jobs, size=n_fresher_anomalies + n_salary_anomalies, replace=False)
    for j, idx in enumerate(picks):
        r = rows[idx]
        if j < n_fresher_anomalies:
            r["seniority"] = SENIORITY_ORDER_LABELS[0]
            r["exp_min_years"] = 0.0
            r["skills_extracted"] = list(rng.choice(all_skills, size=18, replace=False))
            r["job_requirements"] = "Yêu cầu: " + ", ".join(r["skills_extracted"]) + "."
            r["_anomaly"] = "FRESHER_TOO_MANY_SKILLS"
        else:
            r["seniority"] = "Junior"
            r["exp_min_years"] = 1.0
            sal = float(rng.uniform(300, 450))
            r.update({"salary_avg": sal, "salary_min": sal * 0.9, "salary_max": sal * 1.1, "is_negotiable": False})
            r["_anomaly"] = "SALARY_TOO_HIGH_FOR_LEVEL"

    golden = pd.DataFrame(rows)
    # Như output 04_normalization: nhãn chữ 5 mức + seniority_level số 0-4 (null = chưa rõ).
    golden["seniority_level"] = golden["seniority"].map({lab: float(i) for i, lab in enumerate(SENIORITY_ORDER_LABELS)})
    truth = {
        "rules": [("Spring Boot", "Java"), ("Flutter", "Dart"), ("React", "JavaScript")],
        "positive_salary_skills": ["Kubernetes", "AWS"],
        "n_families": len(FAMILIES),
        "anomaly_ids": golden.loc[golden["_anomaly"].notna(), "job_id_global"].tolist(),
    }
    golden = golden.drop(columns=["_anomaly"])

    # features.parquet + encoding_dictionary.json theo quy ước của Phát (tiền tố skill_)
    slug_to_name = {skill_slug(s): s for s in all_skills}
    feat = {"job_id_global": golden["job_id_global"].to_numpy()}
    sets = [set(x) for x in golden["skills_extracted"]]
    for slug, name in slug_to_name.items():
        feat[f"skill_{slug}"] = np.fromiter((name in s for s in sets), dtype=np.uint8, count=len(sets))
    features = pd.DataFrame(feat)
    encoding_dict = {"skills": {"method": "multi-hot", "skills_map": slug_to_name}}
    return SyntheticBundle(golden=golden, features=features, encoding_dict=encoding_dict, truth=truth)
