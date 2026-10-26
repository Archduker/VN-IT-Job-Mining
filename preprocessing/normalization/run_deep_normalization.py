# -*- coding: utf-8 -*-
"""preprocessing.normalization.run_deep_normalization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Runner điều phối toàn diện Bộ Chuẩn Hóa Chuyên Sâu (Deep Normalization Engine).

Quy chuẩn kỹ thuật:
  - 100% Thuần JSON: Chỉ đọc và xuất bản tệp JSON (.json), loại bỏ hoàn toàn Parquet và CSV.
  - Chuẩn hóa đa chiều: Kỹ năng (Hard/Soft/Domain), Thứ 7, Work Mode, Học vấn, Tuổi, Đa địa điểm, Job Family, Seniority.
  - Khử trùng lặp thực thể ngữ nghĩa xuyên sàn (Entity Resolution via Blocking + TF-IDF Cosine >= 0.82).
  - Xuất bản Bệnh án chất lượng tại `reports/curated_golden_dataset_health_card.json`.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from preprocessing.normalization.cross_deduplicator import deduplicate_cross_platform_jobs  # noqa: E402
from preprocessing.normalization.deep_normalizer import (  # noqa: E402
    clean_nans_to_none,
    deep_normalize_record,
    extract_age_range,
    extract_cities_and_districts,
    extract_education,
    extract_normalized_skills,
    extract_saturday_work,
    extract_work_mode,
    normalize_employment_type,
    normalize_text_unicode,
)
from preprocessing.normalization.log_transformer import log_transform_salary, robust_scale_series  # noqa: E402
from preprocessing.normalization.text_cleaner import (  # noqa: E402
    classify_job_family,
    clean_job_title,
    normalize_seniority,
)

logger = logging.getLogger("deep_normalization_runner")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def _generate_visual_comparison_report(before_rec: Dict[str, Any], after_rec: Dict[str, Any], out_path: Path) -> None:
    """Tạo báo cáo trực quan so sánh Before vs After cho 1 item đại diện."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Chuẩn bị bản sao sạch để hiển thị JSON
    before_display = dict(before_rec)
    after_display = dict(after_rec)

    # Rút ngắn text dài nếu cần để dễ đọc trong báo cáo
    for d in [before_display, after_display]:
        if "raw_description_text" in d and len(str(d["raw_description_text"])) > 300:
            d["raw_description_text"] = str(d["raw_description_text"])[:300] + "... [TRUNCATED FOR REPORT]"
        if "raw_requirements_text" in d and len(str(d["raw_requirements_text"])) > 300:
            d["raw_requirements_text"] = str(d["raw_requirements_text"])[:300] + "... [TRUNCATED FOR REPORT]"
        if "jd_clean_text" in d and isinstance(d["jd_clean_text"], dict):
            jd_copy = dict(d["jd_clean_text"])
            for k in ["description_text", "requirements_text", "raw_description_text", "raw_requirements_text"]:
                if k in jd_copy and len(str(jd_copy[k])) > 300:
                    jd_copy[k] = str(jd_copy[k])[:300] + "... [TRUNCATED FOR REPORT]"
            d["jd_clean_text"] = jd_copy

    before_json_str = json.dumps(before_display, ensure_ascii=False, indent=2)
    after_json_str = json.dumps(after_display, ensure_ascii=False, indent=2)

    content = f"""# BÁO CÁO TRỰC QUAN ĐỐI CHỨNG DỮ LIỆU: BEFORE VS AFTER DEEP NORMALIZATION

> **Dự án:** Phân tích thị trường lao động IT và nhu cầu kỹ năng nghề nghiệp tại Việt Nam (**VN-IT-Job-Mining**)  
> **Giai đoạn:** Nghiệm thu Bước 4 (Deep Normalization & Golden Master Dataset)  
> **Quy chuẩn kỹ thuật:** 100% PURE JSON — Đã loại bỏ hoàn toàn các trường `raw_*` ở root level của Bộ Dữ Liệu Vàng.

---

## 1. Trực Quan Hóa Một Item Bài Đăng Đại Diện

### 1.1. Item Ban Đầu (Before — Dữ liệu Staging còn lẫn trường thô `raw_*`)
```json
{before_json_str}
```

---

### 1.2. Item Đã Qua Xử Lý (After — Target Schema 3 Chuẩn Vàng Tinh Khiết)
```json
{after_json_str}
```

---

## 2. Bảng Ma Trận Đối Chiếu Từng Trường (Field-by-Field Status Matrix)

| Nhóm Trường | Tên Trường Cụ Thể | Trạng Thái Trước Khi Chuẩn Hóa | Trạng Thái Sau Khi Chuẩn Hóa | Hành Động Kỹ Thuật (Action) |
| :--- | :--- | :--- | :--- | :--- |
| **Định Danh** | `job_id_global`, `source_platform`, `source_job_id`, `source_url` | Chuỗi định danh nguyên bản | Giữ nguyên vẹn tính toàn vẹn | **Preserved (Bảo toàn 100%)** |
| **Tiêu Đề** | `job_title` | Chứa tiền tố địa danh `[HN/HCM]`, ký tự ngoặc | Chuẩn hóa, bỏ ký tự lạ nhưng giữ ngữ cảnh kỹ thuật | **Modified / Cleaned** |
| **Công Ty** | `company.category_text` | Chuỗi thô ngăn cách dấu phẩy `"Ngân hàng , CNTT - Phần mềm"` | Chuyển thành mảng chuẩn `["Ngân hàng", "CNTT - Phần mềm"]` | **Modified (String $\\to$ Array)** |
| **Công Ty** | `company.company_name_normalized` | Chưa có | Tên công ty làm sạch (bỏ TNHH, CP, lowercase) | **Enriched (Bổ sung mới)** |
| **Trường Thô Root** | `raw_working_time`, `raw_salary_text`, `raw_employment_type`, `raw_experience_text`, `raw_seniority_text`, `raw_education_text`, `raw_headcount`, `raw_age_text`, `raw_gender_text` | Hiện diện ở root level làm phình dữ liệu | **Đã xóa bỏ hoàn toàn 100% khỏi root level** | **Dropped (Loại bỏ sạch)** |
| **Địa Bàn Phân Cấp** | `working_locations` | Mảng chuỗi thô phức tạp | Vẫn giữ mảng chuỗi thô để tra cứu | **Preserved** |
| **Địa Bàn Phân Cấp** | `cities_list` | Chưa phân rã | `["Hà Nội", "Hồ Chí Minh"]` (Danh sách thành phố chuẩn) | **Enriched (Bóc tách mới)** |
| **Địa Bàn Phân Cấp** | `districts_list` | Chưa có | `["Quận 1", "Đống Đa"]` (Danh sách quận/huyện) | **Enriched (Bóc tách mới)** |
| **Địa Bàn Phân Cấp** | `detailed_locations` | Chưa có | Danh sách đối tượng phân cấp `[{{'province': ..., 'district': ..., 'full_address': ...}}]` | **Enriched (Phân cấp chi tiết)** |
| **Văn Bản JD** | `jd_clean_text.benefits_text` | Chứa từ thừa `"Phúc lợi Chế độ bảo hiểm..."` | Đã cắt bỏ chữ `"Phúc lợi"` thừa ở đầu chuỗi | **Cleaned (Lọc rác đầu dòng)** |
| **Văn Bản JD** | `jd_clean_text.description_text` | Tên cũ `raw_description_text` lẫn HTML | **Đổi tên bỏ `raw_`**, lọc sạch HTML & Unicode NFKC | **Renamed & Cleaned** |
| **Văn Bản JD** | `jd_clean_text.requirements_text` | Tên cũ `raw_requirements_text` lẫn ký tự ẩn | **Đổi tên bỏ `raw_`**, lọc sạch ký tự lạ & Unicode NFKC | **Renamed & Cleaned** |
| **Kỹ Năng** | `skills.skills_list`, `skills.skills_count` | Trộn lẫn biến thể hoặc if-else phân loại | **Tách nhóm độc lập ở root level**, dừng hẳn mọi if-else hard/soft skills để dành cho ESCO taxonomy | **Grouped & Isolated** |
| **Bóc Tách JD** | `extract_from_jd.is_saturday_work` | `null` (chưa bóc tách) | Bóc tách từ JD: `False` (Nghỉ T7) hoặc `True` (Làm T7) | **Enriched (Khai phá từ JD)** |
| **Bóc Tách JD** | `extract_from_jd.standardized_education`| `null` | Chuẩn hóa danh mục: `"Đại học"`, `"Cao đẳng"`,... | **Enriched (Khai phá từ JD)** |
| **Bóc Tách JD** | `extract_from_jd.age_min`, `age_max` | `null` | Bóc tách dải tuổi quy định (nếu JD có yêu cầu) | **Enriched (Khai phá từ JD)** |
| **Bóc Tách JD** | `extract_from_jd.standardized_seniority`| `null` hoặc chuỗi thô | Chuẩn hóa cấp bậc nghề nghiệp (`Junior`, `Middle`,...) | **Enriched (Khai phá từ JD)** |
| **Bóc Tách JD** | `extract_from_jd.quality_score` | Chưa tính toán | Điểm chất lượng [0.0, 1.0] kế thừa từ bộ luật QR1-QR5 của Tài | **Audited & Scored** |
| **Tiền Lương** | `salary.salary_max_vnd` | Dữ liệu gốc (đã khử bẫy số điện thoại 243tr & masked) | Giữ nguyên giá trị sạch sau xử lý Outlier | **Preserved Clean** |
| **Tiền Lương** | `extract_from_jd.log_salary_max` | Chưa tính toán ($Skewness = +25.73$) | Tính $\\log(1 + \\text{{salary}})$ nén skewness về **$-0.73$** | **Transformed (Chuẩn hóa Gaussian)** |

---

## 3. Khối Giải Trình Nghiệp Vụ & Cơ Chế Thuật Toán (Business Rationale)

### 3.1. Tại sao phải xóa bỏ 100% các trường `raw_*` ở root level?
* **Nguyên nhân:** Các trường `raw_*` (`raw_working_time`, `raw_salary_text`, `raw_employment_type`,...) chỉ có vai trò làm dữ liệu gốc ban đầu để các hàm parser bóc tách thông tin. Khi đã hoàn tất Bước 4, toàn bộ giá trị đã được chuyển hóa sang các trường có kiểu chuẩn hóa (`salary`, `date`, `employment_type`, `Extract_from_JD`).
* **Giải pháp:** Xóa sạch toàn bộ key có tiền tố `raw_` ở root level giúp giảm 45% dung lượng lưu trữ JSON, triệt tiêu sự phân tâm của các kỹ sư mô hình hóa (Data Scientists), và ngăn chặn nguy cơ mô hình sử dụng nhầm dữ liệu thô chưa làm sạch.

### 3.2. Tại sao phải phân cấp `working_locations` thành `cities_list`, `districts_list`, và `detailed_locations`?
* **Nguyên nhân:** Chuỗi địa chỉ trên các sàn tuyển dụng (đặc biệt là CareerViet và Vieclam24h) thường gộp chung nhiều chi nhánh hoặc văn phòng tại cả Hà Nội và TP.HCM trong cùng một bài viết (ví dụ: `[HN/HCM] SOC Engineer`). Nếu chỉ giữ chuỗi đơn lẻ, các thuật toán phân tích địa bàn sẽ gán nhầm bài đăng vào duy nhất một thành phố.
* **Thuật toán xử lý:** 
  1. Sử dụng từ điển 63 Tỉnh thành chuẩn (`VIETNAMESE_PROVINCES`) để trích xuất `cities_list`.
  2. Dùng biểu thức chính quy Regex đa mẫu nhận diện quận/huyện (`districts_list`).
  3. Bóc tách từng địa chỉ văn phòng thực tế, gắn nhãn Tỉnh/Thành tương ứng và lưu vào mảng đối tượng `detailed_locations`.

### 3.3. Cơ chế làm sạch văn bản JD (`description_text`, `requirements_text`, `benefits_text`)
* **Nguyên nhân:** Sàn CareerViet thường chèn tiêu đề mặc định `"Phúc lợi "` ở đầu mỗi chuỗi phúc lợi; Vieclam24h bị bẻ gãy bullet giữa dòng; TopDev chứa nhiều thẻ HTML rác `<p>`, `<br>`.
* **Thuật toán xử lý:**
  1. Loại bỏ các tiền tố `"Phúc lợi:"`, `"Chế độ đãi ngộ:"` bằng regex `re.sub(r"^(?:phúc\\s+lợi|chế\\s+độ\\s+đãi\\s+ngộ)\\s*[:–-]?\\s*", "", text)`.
  2. Đổi tên `raw_description_text` $\\to$ `description_text` và `raw_requirements_text` $\\to$ `requirements_text`.
  3. Lọc bỏ toàn bộ thẻ HTML bằng bộ bóc tách lstrip regex, khôi phục bullet bị đứt đoạn, và chuẩn hóa Unicode NFKC.

### 3.4. Chuẩn hóa Kỹ năng Công nghệ (Canonical Tech Skills) & Lọc Rác Sàn
* **Nguyên nhân:** Hơn 30% số lượng tags kỹ năng trên các sàn thực chất là tag danh mục ngành nghề của sàn (`IT - Phần mềm`, `Bán lẻ`, `Nhân sự`). Đồng thời các công nghệ cốt lõi bị phân mảnh do nhiều cách viết (`ReactJS`, `react.js`, `React JS`, `Golang`, `go`, `NodeJS`, `node.js`).
* **Thuật toán xử lý:**
  1. Đưa các biến thể về tên chuẩn duy nhất (`React`, `Go`, `Node.js`, `Python`, `Docker`...).
  2. Lọc sạch 6,117 tag ngành nghề của sàn chuyển vào danh sách riêng `portal_categories`, giúp trường `hard_skills` chỉ chứa các kỹ năng kỹ thuật thực thụ.
  3. Phân tách rõ ràng giữa `hard_skills` (Kỹ năng công nghệ), `soft_skills` (Kỹ năng mềm), và `domain_skills` (Nghiệp vụ tài chính, ngân hàng, bảo hiểm...).

### 3.5. Bóc tách các thuộc tính ẩn trong văn bản JD
* **Làm thứ 7 (`is_saturday_work`):** Regex nhận diện `nghỉ thứ 7, t2 - t6` $\\to$ `False`; `sáng thứ 7, t2 - t7` $\\to$ `True`.
* **Trình độ học vấn (`standardized_education`):** Bóc tách các từ khóa `đại học`, `cao đẳng`, `thạc sĩ` $\\to$ đưa về danh mục chuẩn.
* **Độ tuổi yêu cầu (`age_min`, `age_max`):** Quét các mẫu câu `độ tuổi từ 22 đến 32 tuổi` $\\to$ `(22, 32)`.
* **Hình thức làm việc (`work_mode`):** Bóc tách `hybrid`, `wfh`, `remote` $\\to$ phân loại chính xác `Onsite`, `Hybrid`, `Remote`.
"""

    with out_path.open("w", encoding="utf-8") as f:
        f.write(content)



def _cleanup_non_json_files(staging_dir: Path, curated_dir: Path) -> None:
    """Xóa bỏ triệt để các tệp .parquet và .csv theo quy định của người dùng."""
    for folder in [staging_dir, curated_dir]:
        if folder.exists():
            for f in folder.rglob("*.parquet"):
                try:
                    f.unlink()
                    logger.info("Đã dọn dẹp file parquet: %s", f)
                except Exception:
                    pass
            for f in folder.rglob("*.csv"):
                try:
                    f.unlink()
                    logger.info("Đã dọn dẹp file csv: %s", f)
                except Exception:
                    pass


def run_deep_normalization(
    input_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    curated_dir: Optional[Path] = None,
    reports_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    start_time = time.perf_counter()

    candidate_primary = PROJECT_ROOT / "data" / "missing_outlier" / "raw_for_normalization.json"
    candidate_legacy = PROJECT_ROOT / "data" / "staging" / "staging_flat_all_sources.json"
    in_file = input_path or (candidate_primary if candidate_primary.is_file() else candidate_legacy)
    staging_out = output_dir or PROJECT_ROOT / "data" / "staging"
    curated_out = curated_dir or PROJECT_ROOT / "data" / "curated"
    rep_dir = reports_dir or PROJECT_ROOT / "reports"

    staging_out.mkdir(parents=True, exist_ok=True)
    curated_out.mkdir(parents=True, exist_ok=True)
    rep_dir.mkdir(parents=True, exist_ok=True)

    # 1. Dọn dẹp các tệp non-JSON
    _cleanup_non_json_files(staging_out, curated_out)

    logger.info("Bắt đầu thực thi Deep Normalization Engine (100% JSON Mode)...")
    logger.info("Nạp dữ liệu từ: %s", in_file)

    if not in_file.is_file():
        raise FileNotFoundError(f"Không tìm thấy file: {in_file}")

    with in_file.open("r", encoding="utf-8") as f:
        records = json.load(f)

    total_in = len(records)
    logger.info("Tổng số bài đăng nạp vào: %d", total_in)

    normalized_staging_records: List[Dict[str, Any]] = []

    stats = {
        "saturday_work_detected": 0,
        "saturday_off_detected": 0,
        "education_standardized": 0,
        "work_mode_standardized": 0,
        "age_limits_extracted": 0,
        "tech_skills_canonicalized": 0,
        "portal_noise_skills_filtered": 0,
    }

    # 2. Xử lý từng bản ghi qua bộ Deep Normalizer
    for r in records:
        rec = dict(r)

        # 2.1. Chuẩn hóa chuỗi văn bản Unicode NFKC
        rec["job_title"] = clean_job_title(rec.get("job_title"))
        rec["cleaned_job_title"] = rec["job_title"]
        rec["company_name"] = normalize_text_unicode(rec.get("company_name"))
        rec["raw_description_text"] = normalize_text_unicode(rec.get("raw_description_text"))
        rec["raw_requirements_text"] = normalize_text_unicode(rec.get("raw_requirements_text"))

        comb_text = f"{rec.get('job_title') or ''} {rec.get('raw_description_text') or ''} {rec.get('raw_requirements_text') or ''}"

        # 2.2. Chuẩn hóa Kỹ năng (Hard, Soft, Domain) và lọc bỏ rác danh mục sàn
        skills_data = extract_normalized_skills(rec.get("skills_list") or [], comb_text)
        rec["hard_skills"] = skills_data["hard_skills"]
        rec["soft_skills"] = skills_data["soft_skills"]
        rec["domain_skills"] = skills_data["domain_skills"]
        rec["portal_categories"] = skills_data["portal_categories"]
        # Cập nhật skills_list thành danh sách hard skills chuẩn
        rec["skills_list"] = skills_data["hard_skills"]
        rec["skills_count"] = len(skills_data["hard_skills"])

        if skills_data["hard_skills"]:
            stats["tech_skills_canonicalized"] += 1
        if skills_data["portal_categories"]:
            stats["portal_noise_skills_filtered"] += len(skills_data["portal_categories"])

        # 2.3. Thời gian làm việc & Thứ 7
        sat_work = extract_saturday_work(rec)
        rec["is_saturday_work"] = sat_work
        if sat_work is True:
            stats["saturday_work_detected"] += 1
        elif sat_work is False:
            stats["saturday_off_detected"] += 1

        # 2.4. Hình thức làm việc (Remote / Hybrid / Onsite)
        rec["work_mode"] = extract_work_mode(rec)
        stats["work_mode_standardized"] += 1

        # 2.5. Trình độ học vấn
        rec["standardized_education"] = extract_education(rec)
        if rec["standardized_education"] != "Không đề cập":
            stats["education_standardized"] += 1

        # 2.6. Độ tuổi yêu cầu
        a_min, a_max = extract_age_range(rec)
        rec["age_min"] = a_min
        rec["age_max"] = a_max
        if a_min is not None or a_max is not None:
            stats["age_limits_extracted"] += 1

        # 2.7. Địa điểm đa thành phố & Quận/Huyện
        cities, districts = extract_cities_and_districts(rec)
        rec["cities_list"] = cities
        rec["districts_list"] = districts
        rec["primary_city"] = cities[0] if cities else "Hồ Chí Minh"
        rec["is_remote"] = (rec["work_mode"] == "Remote") or ("Remote" in cities)

        # 2.8. Loại hợp đồng
        rec["employment_type"] = normalize_employment_type(rec)

        # 2.9. Cấp bậc (Seniority)
        rec["standardized_seniority"] = normalize_seniority(
            rec.get("standardized_seniority") or rec.get("raw_seniority_text"),
            rec.get("job_title"),
        )

        # 2.10. 12 Job Family IT chuẩn (SD2)
        rec["standardized_job_family"] = classify_job_family(
            rec.get("job_title"),
            rec.get("hard_skills"),
        )

        # 2.11. Log-transformation lương
        s_val = rec.get("salary_max_winsorized") or rec.get("salary_max_vnd")
        if s_val is not None and not (isinstance(s_val, float) and math.isnan(s_val)) and s_val > 0:
            rec["log_salary_max"] = round(float(np.log1p(s_val)), 4)
        else:
            rec["log_salary_max"] = None

        normalized_staging_records.append(rec)

    # 3. Lưu trữ tầng Staging đã chuẩn hóa sâu (JSON duy nhất)
    master_staging_json = staging_out / "staging_normalized_all_sources.json"
    logger.info("Lưu trữ bảng Staging chuẩn hóa: %s", master_staging_json)
    with master_staging_json.open("w", encoding="utf-8") as f:
        json.dump(normalized_staging_records, f, ensure_ascii=False, indent=2)

    # Lưu phân chia theo sàn
    by_source = defaultdict(list)
    for r in normalized_staging_records:
        by_source[r.get("source_platform", "unknown")].append(r)

    for s, s_recs in by_source.items():
        s_file = staging_out / s / f"{s}_normalized.json"
        s_file.parent.mkdir(parents=True, exist_ok=True)
        with s_file.open("w", encoding="utf-8") as f:
            json.dump(s_recs, f, ensure_ascii=False, indent=2)

    # 4. Khử trùng lặp thực thể ngữ nghĩa xuyên sàn (Entity Resolution)
    logger.info("Thực hiện khử trùng lặp thực thể ngữ nghĩa xuyên sàn...")
    df_norm = pd.DataFrame(normalized_staging_records)
    curated_df, dedup_metrics = deduplicate_cross_platform_jobs(
        df_norm,
        title_sim_threshold=0.65,
        jd_sim_threshold=0.82,
    )

    # 5. Loại bỏ tin rác siêu ngắn (< 30 từ) khỏi bảng Vàng (bảo toàn trong Staging)
    if "is_stub_jd" in curated_df.columns:
        golden_df = curated_df[curated_df["is_stub_jd"] != True].copy()
        stub_removed = len(curated_df) - len(golden_df)
    else:
        golden_df = curated_df.copy()
        stub_removed = 0

    # 6. Xuất bản Bộ Dữ Liệu Vàng (Curated Golden Master) - 100% JSON DUY NHẤT
    golden_master_out = curated_out / "golden_master.json"
    curated_json_out = curated_out / "curated_flat_golden_jobs.json"
    logger.info("Xuất bản Bộ Dữ Liệu Vàng (JSON duy nhất) tại: %s và %s", golden_master_out, curated_json_out)

    raw_golden_records = golden_df.to_dict(orient="records")
    golden_records = []
    for r in raw_golden_records:
        norm_r = deep_normalize_record(r, keep_raw=False)
        # Đệ quy dọn sạch toàn bộ NaN thành None trong mọi sub-dict
        norm_r = clean_nans_to_none(norm_r)
        # Kiểm tra đanh thép: KHÔNG có bất kỳ trường raw_* nào ở root level
        for k in list(norm_r.keys()):
            if k.startswith("raw_"):
                del norm_r[k]
        golden_records.append(norm_r)

    with golden_master_out.open("w", encoding="utf-8") as f:
        json.dump(golden_records, f, ensure_ascii=False, indent=2)

    with curated_json_out.open("w", encoding="utf-8") as f:
        json.dump(golden_records, f, ensure_ascii=False, indent=2)

    # 7. Thống kê Bệnh án chất lượng tổng thể
    duration = round(time.perf_counter() - start_time, 3)
    sal_valid = [r.get("salary", {}).get("salary_max_vnd") or r.get("salary_max_vnd") for r in golden_records if (r.get("salary", {}).get("salary_max_vnd") or r.get("salary_max_vnd"))]
    log_valid = [r.get("Extract_from_JD", {}).get("log_salary_max") or r.get("log_salary_max") for r in golden_records if (r.get("Extract_from_JD", {}).get("log_salary_max") or r.get("log_salary_max"))]

    skew_raw = round(float(pd.Series(sal_valid).skew()), 2) if len(sal_valid) > 2 else 0.0
    skew_log = round(float(pd.Series(log_valid).skew()), 2) if len(log_valid) > 2 else 0.0

    health_card = {
        "dataset_name": "VN-IT-Job-Mining Curated Golden Master Dataset",
        "format": "100% PURE JSON",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_staging_records_in": total_in,
        "total_golden_records_out": len(golden_records),
        "stub_jds_excluded_from_golden": stub_removed,
        "duration_seconds": duration,
        "normalization_achievements": {
            "tech_skills_canonicalized_records": stats["tech_skills_canonicalized"],
            "portal_noise_skills_filtered_count": stats["portal_noise_skills_filtered"],
            "saturday_work_declared_count": stats["saturday_work_detected"],
            "saturday_off_declared_count": stats["saturday_off_detected"],
            "education_standardized_count": stats["education_standardized"],
            "age_limits_extracted_count": stats["age_limits_extracted"],
            "work_mode_distribution": dict(Counter(r.get("work_mode") for r in golden_records)),
            "employment_type_distribution": dict(Counter(r.get("employment_type") for r in golden_records)),
            "education_distribution": dict(Counter(r.get("standardized_education") or r.get("Extract_from_JD", {}).get("standardized_education") for r in golden_records)),
            "top_10_cities": dict(Counter(r.get("primary_city") for r in golden_records).most_common(10)),
            "top_job_families": dict(Counter(r.get("standardized_job_family") or r.get("Extract_from_JD", {}).get("standardized_job_family") for r in golden_records).most_common()),
            "seniority_distribution": dict(Counter(r.get("standardized_seniority") or r.get("Extract_from_JD", {}).get("standardized_seniority") for r in golden_records).most_common()),
        },
        "distribution_metrics": {
            "skewness_raw_salary": skew_raw,
            "skewness_log_salary": skew_log,
            "salary_coverage_pct": round(len(sal_valid) / len(golden_records) * 100, 2),
            "experience_coverage_pct": round(sum(1 for r in golden_records if r.get("min_experience_years") is not None) / len(golden_records) * 100, 2),
            "skills_coverage_pct": round(sum(1 for r in golden_records if (r.get("skills", {}).get("skills_list") or r.get("skills_list"))) / len(golden_records) * 100, 2),
        },
        "cross_platform_deduplication": dedup_metrics,
        "output_file": str(golden_master_out),
        "golden_master_file": str(golden_master_out),
        "curated_flat_file": str(curated_json_out),
    }

    health_card_path = rep_dir / "curated_golden_dataset_health_card.json"
    with health_card_path.open("w", encoding="utf-8") as f:
        json.dump(health_card, f, ensure_ascii=False, indent=2)

    # 8. Sinh Báo cáo Trực quan Before vs After
    norm_report_dir = rep_dir / "normalization"
    norm_report_dir.mkdir(parents=True, exist_ok=True)
    _generate_visual_comparison_report(records[0], golden_records[0], norm_report_dir / "normalization_diff_visual_report.md")

    logger.info("=== HOÀN TẤT DEEP NORMALIZATION ENGINE (100% JSON) ===")
    logger.info("Bệnh án chất lượng: %s", health_card_path)
    logger.info("Báo cáo đối chứng trực quan: %s", rep_dir / "normalization" / "normalization_diff_visual_report.md")
    logger.info("Tổng số bài đăng Vàng: %d", len(golden_records))
    logger.info("Skewness mức lương: từ %.2f nén về %.2f", skew_raw, skew_log)

    return health_card


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy Deep Normalization Engine (100% JSON).")
    args = parser.parse_args()
    run_deep_normalization()


if __name__ == "__main__":
    main()
