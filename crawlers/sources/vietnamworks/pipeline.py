"""
=============================================================================
PIPELINE CHUẨN — VIETNAMWORKS IT 1000
Tất cả trong một file duy nhất:
  Bước 1 ─ Crawl 1000 mẫu IT với đầy đủ thuộc tính (API ms.vietnamworks.com)
  Bước 2 ─ Khử trùng lặp (Deduplication) theo job_id
  Bước 3 ─ Làm sạch & xử lý Missing Values
  Bước 4 ─ Feature Engineering (encoding, salary band, skill matrix...)
  Bước 5 ─ Xuất file it_1000_clean.json (1000 records, đẹp, có thể mở trực tiếp)

Chạy: python pipeline.py
=============================================================================
"""

import os, sys, re, html, time, random, json, csv
from typing import Any, Dict, List
from collections import Counter
import requests

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ──────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────
API_URL         = "https://ms.vietnamworks.com/job-search/v1.0/search"
HEADERS         = {
    "Content-Type": "application/json",
    "X-Source":     "Page-Container",
    "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Origin":       "https://www.vietnamworks.com",
    "Referer":      "https://www.vietnamworks.com/viec-lam?q=it",
}
TARGET_COUNT    = 1000
HITS_PER_PAGE   = 50
USD_RATE        = 25_400          # 1 USD = 25,400 VND (tỷ giá tham chiếu)
IT_QUERIES      = ["software developer", "it", "developer", "cntt", "lap trinh", "data engineer"]
OUTPUT_JSON     = "it_1000_clean.json"


# ──────────────────────────────────────────────────────────
# BƯỚC 1  ─  CRAWL
# ──────────────────────────────────────────────────────────

def clean_html(raw: str) -> str:
    """Xoá toàn bộ tag HTML, chuẩn hoá khoảng trắng."""
    if not raw or not isinstance(raw, str):
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_salary(item: Dict) -> Dict:
    """Làm sạch & quy đổi lương về Triệu VNĐ."""
    pretty   = (item.get("prettySalary") or "").strip()
    s_min    = float(item.get("salaryMin") or 0)
    s_max    = float(item.get("salaryMax") or 0)
    curr     = (item.get("salaryCurrency") or "").upper().strip()

    # Sửa nhầm đơn vị: nếu > 50_000 thì là VNĐ
    if s_min > 50_000 or s_max > 50_000:
        curr = "VND"
    if not curr:
        curr = "USD" if ("$" in pretty or "USD" in pretty) else "VND"

    negotiable = 1 if (not pretty or "thương lượng" in pretty.lower() or (s_min == 0 and s_max == 0)) else 0

    if negotiable == 0:
        factor  = USD_RATE / 1_000_000 if curr == "USD" else 1 / 1_000_000
        min_mil = round(s_min * factor, 2)
        max_mil = round(s_max * factor, 2)
        avg_mil = round((min_mil + max_mil) / 2, 2) if (min_mil > 0 and max_mil > 0) else max(min_mil, max_mil)
    else:
        min_mil = max_mil = avg_mil = 0.0

    return {
        "pretty_salary":        pretty or "Thương lượng",
        "salary_min_raw":       int(s_min),
        "salary_max_raw":       int(s_max),
        "salary_currency":      curr,
        "is_salary_negotiable": negotiable,
        "salary_min_mil_vnd":   min_mil,
        "salary_max_mil_vnd":   max_mil,
        "salary_avg_mil_vnd":   avg_mil,
    }


def level_order(level_str: str) -> int:
    """Ordinal encoding cấp bậc: 0=Intern … 5=Director."""
    lvl = (level_str or "").lower()
    for kw, v in [("intern", 0), ("thực tập", 0), ("student", 0),
                  ("fresher", 1), ("mới tốt nghiệp", 1),
                  ("experienced", 2), ("nhân viên", 2),
                  ("team leader", 3), ("trưởng nhóm", 3),
                  ("manager", 4), ("quản lý", 4), ("trưởng phòng", 4),
                  ("director", 5), ("giám đốc", 5)]:
        if kw in lvl:
            return v
    return 2


def extract_record(item: Dict) -> Dict:
    """Trích xuất toàn bộ 40 thuộc tính từ một record thô API."""
    sal  = parse_salary(item)

    # Skills
    skills_list = [s["skillName"].strip() for s in (item.get("skills") or [])
                   if isinstance(s, dict) and s.get("skillName")]
    skills_list = list(dict.fromkeys(skills_list))   # giữ thứ tự, xoá trùng

    # Benefits
    ben_list = [b["benefitName"].strip() for b in (item.get("benefits") or [])
                if isinstance(b, dict) and b.get("benefitName")]

    # Locations + GPS
    loc_names, lat, lon = [], None, None
    for loc in (item.get("workingLocations") or []):
        if isinstance(loc, dict):
            city = loc.get("cityNameVI") or loc.get("cityName")
            if city and city not in loc_names:
                loc_names.append(city.strip())
            geo = loc.get("geoLoc") or {}
            if isinstance(geo, dict) and geo.get("lat") and lat is None:
                lat, lon = geo["lat"], geo["lon"]

    # Industries
    ind_list = []
    for ind in (item.get("industriesV3") or item.get("industries") or []):
        if isinstance(ind, dict):
            name = ind.get("industryV3Name") or ind.get("industryNameVI") or ind.get("industryName")
            if name and name not in ind_list:
                ind_list.append(name.strip())

    # Job Function
    jf = item.get("jobFunction") or {}
    jf_parent   = jf.get("parentName", "") if isinstance(jf, dict) else ""
    jf_children = [ch["name"].strip() for ch in (jf.get("children") or [])
                   if isinstance(ch, dict) and ch.get("name")] if isinstance(jf, dict) else []

    lvl_en    = item.get("jobLevel", "Experienced")
    lvl_vi    = item.get("jobLevelVI", "Nhân viên")
    jd_clean  = clean_html(item.get("jobDescription", ""))
    jr_clean  = clean_html(item.get("jobRequirement", ""))

    return {
        # ── Định danh ──
        "job_id":                   item.get("jobId"),
        "job_title":                clean_html(item.get("jobTitle", "")),
        "job_url":                  item.get("jobUrl", ""),

        # ── Công ty ──
        "company_id":               item.get("companyId"),
        "company_name":             clean_html(item.get("companyName", "")),
        "company_size":             item.get("companySizeVI") or item.get("companySize", ""),
        "company_address":          clean_html(item.get("address", "")),
        "company_profile":          clean_html(item.get("companyProfile", "")),

        # ── Nội dung JD / JR / Phúc lợi ──
        "job_description":          jd_clean,
        "job_requirement":          jr_clean,
        "benefits":                 "; ".join(ben_list),

        # ── Kỹ năng & Chức năng ──
        "skills":                   "; ".join(skills_list),
        "skill_list":               skills_list,          # dạng list để FE dễ
        "skill_count":              len(skills_list),
        "job_function_parent":      jf_parent,
        "job_function_children":    "; ".join(jf_children),
        "industries":               "; ".join(ind_list),

        # ── Cấp bậc & Kinh nghiệm ──
        "job_level_en":             lvl_en,
        "job_level_vi":             lvl_vi,
        "job_level_order":          level_order(lvl_en),
        "years_of_experience":      item.get("yearsOfExperience") or 0,
        "number_of_recruits":       item.get("numberOfRecruits") or 1,
        "language_required":        item.get("languageSelectedVI") or item.get("languageSelected") or "",

        # ── Lương ──
        **sal,

        # ── Địa lý ──
        "locations":                "; ".join(loc_names),
        "location_list":            loc_names,
        "latitude":                 lat,
        "longitude":                lon,

        # ── Thời gian ──
        "created_on":               item.get("createdOn", ""),
        "approved_on":              item.get("approvedOn", ""),
        "expired_on":               item.get("expiredOn", ""),
        "duration_days":            item.get("durationDays") or 30,

        # ── Cờ trạng thái ──
        "is_urgent":                bool(item.get("isUrgentJob") or item.get("isUrgentJobM")),
        "is_reposted":              bool(item.get("isReposted")),
    }


def crawl(target: int = TARGET_COUNT) -> List[Dict]:
    print(f"\n{'='*70}")
    print(f"  BƯỚC 1 ─ CRAWL {target} BẢN GHI IT TỪ VIETNAMWORKS API")
    print(f"{'='*70}")

    all_records: List[Dict] = []
    seen_ids: set = set()

    for q in IT_QUERIES:
        if len(all_records) >= target:
            break
        print(f"\n[+] Từ khoá: '{q}'")
        page = 0
        while len(all_records) < target and page < 30:
            payload = {
                "userId": 0, "query": q,
                "filter": [], "ranges": [], "order": [],
                "hitsPerPage": HITS_PER_PAGE, "page": page,
            }
            try:
                resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=12)
                items = resp.json().get("data", []) if resp.status_code == 200 else []
            except Exception as e:
                print(f"   [!] Lỗi request: {e}")
                items = []

            if not items:
                break

            added = 0
            for item in items:
                jid = item.get("jobId")
                if jid and jid not in seen_ids:
                    seen_ids.add(jid)
                    all_records.append(extract_record(item))
                    added += 1
                    if len(all_records) >= target:
                        break

            print(f"   Trang {page+1:>2}: +{added:>2} | Tổng: {len(all_records):>4}/{target}")
            if added == 0 and page > 2:
                break
            time.sleep(random.uniform(0.8, 1.4))
            page += 1

    print(f"\n[✓] Crawl xong: {len(all_records)} records thô, {len(seen_ids)} job_id duy nhất")
    return all_records


# ──────────────────────────────────────────────────────────
# BƯỚC 2  ─  DEDUPLICATION
# ──────────────────────────────────────────────────────────

def dedup(records: List[Dict]) -> List[Dict]:
    print(f"\n{'='*70}")
    print(f"  BƯỚC 2 ─ DEDUPLICATION (khử trùng lặp)")
    print(f"{'='*70}")
    before = len(records)
    seen   = set()
    clean  = []
    for r in records:
        jid = r.get("job_id")
        if jid not in seen:
            seen.add(jid)
            clean.append(r)
    removed = before - len(clean)
    print(f"[*] Trước: {before} | Sau: {len(clean)} | Loại bỏ: {removed} bản trùng")
    return clean


# ──────────────────────────────────────────────────────────
# BƯỚC 3  ─  LÀM SẠCH & XỬ LÝ MISSING VALUES
# ──────────────────────────────────────────────────────────

DEFAULT_FILL = {
    "company_size": "Không rõ",
    "company_address": "",
    "company_profile": "",
    "job_description": "",
    "job_requirement": "",
    "benefits": "",
    "skills": "",
    "job_function_parent": "Không rõ",
    "job_function_children": "",
    "industries": "Công nghệ thông tin",
    "language_required": "",
    "years_of_experience": 0,
    "number_of_recruits": 1,
    "latitude": None,
    "longitude": None,
}


def clean_and_fill(records: List[Dict]) -> List[Dict]:
    print(f"\n{'='*70}")
    print(f"  BƯỚC 3 ─ LÀM SẠCH & XỬ LÝ MISSING VALUES")
    print(f"{'='*70}")

    missing_report: Dict[str, int] = Counter()
    cleaned = []

    for r in records:
        rec = dict(r)

        # Thống kê missing trước khi fill
        for k, default in DEFAULT_FILL.items():
            v = rec.get(k)
            is_missing = (v is None or v == "" or v == [] or
                          (isinstance(v, str) and v.strip() == ""))
            if is_missing:
                missing_report[k] += 1
                rec[k] = default

        # Làm sạch thêm: chuẩn hoá khoảng trắng thừa
        for k, v in rec.items():
            if isinstance(v, str):
                rec[k] = v.strip()

        # Đảm bảo skill_list là list
        if not isinstance(rec.get("skill_list"), list):
            raw = rec.get("skills", "")
            rec["skill_list"] = [s.strip() for s in raw.split(";") if s.strip()] if raw else []
            rec["skill_count"] = len(rec["skill_list"])

        # Đảm bảo location_list là list
        if not isinstance(rec.get("location_list"), list):
            raw = rec.get("locations", "")
            rec["location_list"] = [s.strip() for s in raw.split(";") if s.strip()] if raw else []

        cleaned.append(rec)

    print(f"[*] Thống kê missing values đã xử lý:")
    for col, cnt in sorted(missing_report.items(), key=lambda x: -x[1]):
        pct = cnt / len(records) * 100
        bar = "█" * min(int(pct), 40)
        print(f"    {col:<30} {cnt:>4} ({pct:>5.1f}%) {bar}")
    if not missing_report:
        print("    → Không có missing value nào!")

    return cleaned


# ──────────────────────────────────────────────────────────
# BƯỚC 4  ─  FEATURE ENGINEERING
# ──────────────────────────────────────────────────────────

def feature_engineering(records: List[Dict]) -> List[Dict]:
    print(f"\n{'='*70}")
    print(f"  BƯỚC 4 ─ FEATURE ENGINEERING")
    print(f"{'='*70}")

    # 4.1 Tìm Top 20 kỹ năng IT phổ biến nhất để tạo One-Hot
    all_skills_flat = [s.lower().strip()
                       for r in records
                       for s in r.get("skill_list", []) if s.strip()]
    skill_freq = Counter(all_skills_flat)
    top20 = [s for s, _ in skill_freq.most_common(20)]
    print(f"\n[4.1] Top 20 kỹ năng IT phổ biến nhất:")
    for i, (sk, cnt) in enumerate(skill_freq.most_common(20), 1):
        print(f"      {i:>2}. {sk:<35} ({cnt} jobs)")

    # 4.2 Cột địa lý
    def loc_flag(r, city):
        return 1 if city.lower() in r.get("locations", "").lower() else 0

    # 4.3 salary_band
    def salary_band(r):
        avg = r.get("salary_avg_mil_vnd") or 0
        neg = r.get("is_salary_negotiable", 1)
        if neg or avg == 0:
            return "Thương lượng"
        if avg < 10:  return "Dưới 10 triệu"
        if avg < 20:  return "10–20 triệu"
        if avg < 30:  return "20–30 triệu"
        if avg < 50:  return "30–50 triệu"
        if avg < 100: return "50–100 triệu"
        return "Trên 100 triệu"

    # 4.4 experience_band
    def exp_band(r):
        yoe = r.get("years_of_experience") or 0
        if yoe == 0:  return "Không yêu cầu / Fresher"
        if yoe <= 1:  return "0–1 năm"
        if yoe <= 3:  return "1–3 năm"
        if yoe <= 5:  return "3–5 năm"
        return "Trên 5 năm"

    enriched = []
    for r in records:
        rec = dict(r)
        skill_lower = " ".join(rec.get("skill_list", [])).lower()

        # One-Hot kỹ năng top 20
        rec["skill_matrix"] = {
            sk.replace(" ", "_"): (1 if sk in skill_lower else 0)
            for sk in top20
        }

        # Cờ địa lý
        rec["loc_hcm"]     = loc_flag(r, "Hồ Chí Minh")
        rec["loc_hn"]      = loc_flag(r, "Hà Nội")
        rec["loc_da_nang"] = loc_flag(r, "Đà Nẵng")
        rec["loc_other"]   = int(rec["loc_hcm"] == 0 and rec["loc_hn"] == 0 and rec["loc_da_nang"] == 0)

        # Nhóm phân loại
        rec["salary_band"]     = salary_band(r)
        rec["experience_band"] = exp_band(r)

        # Cờ nội dung
        rec["has_job_description"] = int(bool(rec.get("job_description", "").strip()))
        rec["has_job_requirement"]  = int(bool(rec.get("job_requirement", "").strip()))
        rec["has_benefits"]         = int(bool(rec.get("benefits", "").strip()))
        rec["has_salary"]           = int(rec.get("is_salary_negotiable", 1) == 0)

        enriched.append(rec)

    # Report
    salary_dist = Counter(r["salary_band"] for r in enriched)
    exp_dist    = Counter(r["experience_band"] for r in enriched)
    loc_dist    = {
        "HCM":     sum(r["loc_hcm"] for r in enriched),
        "Hà Nội":  sum(r["loc_hn"] for r in enriched),
        "Đà Nẵng": sum(r["loc_da_nang"] for r in enriched),
        "Khác":    sum(r["loc_other"] for r in enriched),
    }
    print(f"\n[4.2] Phân bổ địa lý:   {loc_dist}")
    print(f"[4.3] Phân nhóm lương:  {dict(salary_dist.most_common())}")
    print(f"[4.4] Phân nhóm kinh nghiệm: {dict(exp_dist.most_common())}")
    print(f"[4.5] Jobs có JD: {sum(r['has_job_description'] for r in enriched)} | "
          f"có JR: {sum(r['has_job_requirement'] for r in enriched)} | "
          f"có lương cụ thể: {sum(r['has_salary'] for r in enriched)}")

    return enriched


# ──────────────────────────────────────────────────────────
# BƯỚC 5  ─  XUẤT FILE JSON
# ──────────────────────────────────────────────────────────

def export_json(records: List[Dict], path: str):
    print(f"\n{'='*70}")
    print(f"  BƯỚC 5 ─ XUẤT FILE JSON")
    print(f"{'='*70}")

    output = {
        "meta": {
            "total_records":  len(records),
            "source":         "VietnamWorks (ms.vietnamworks.com API)",
            "query_keywords": IT_QUERIES,
            "fields_per_record": len(records[0]) if records else 0,
            "pipeline_steps": [
                "1. Crawl (API ms.vietnamworks.com)",
                "2. Deduplication (theo job_id)",
                "3. Data Cleaning & Missing Value Handling",
                "4. Feature Engineering (One-Hot skills, salary_band, exp_band, location flags)",
            ],
        },
        "records": records,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(path) / 1_048_576
    print(f"[✓] Đã xuất: {path}")
    print(f"    Số records: {len(records)}")
    print(f"    Số trường/record: {len(records[0]) if records else 0}")
    print(f"    Kích thước file: {size_mb:.2f} MB")


# ──────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "█"*70)
    print("  PIPELINE CHUẨN — VIETNAMWORKS IT 1000")
    print("  Crawl → Dedup → Clean → Feature Engineering → Export JSON")
    print("█"*70)

    raw      = crawl(TARGET_COUNT)
    deduped  = dedup(raw)
    cleaned  = clean_and_fill(deduped)
    enriched = feature_engineering(cleaned)
    export_json(enriched, OUTPUT_JSON)

    print("\n" + "█"*70)
    print(f"  HOÀN THÀNH!  →  {OUTPUT_JSON}")
    print("█"*70 + "\n")
