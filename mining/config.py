"""Cấu hình chung của module Data Mining (docs/spec/07_mining_spec.md).

Mọi chỗ phụ thuộc vào schema của bước trước (Duy: lương, cấp bậc, địa bàn; Phát: cột kỹ năng)
đều gom ở đây. Khi đồng đội đổi tên cột, chỉ sửa COLUMN_ALIASES, không sửa thuật toán.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Đường dẫn mặc định (đầu vào theo docs/tasks/06, đầu ra theo spec 07 §5.3)
# ---------------------------------------------------------------------------
DEFAULT_GOLDEN = REPO_ROOT / "data" / "curated" / "curated_flat_golden_jobs.parquet"
# Pipeline 5 bước hiện tại chưa ghi data/curated/; dùng output Normalization khi thiếu file golden.
FALLBACK_GOLDEN = REPO_ROOT / "data" / "preprocessing" / "04_normalization" / "all.parquet"
DEFAULT_FEATURES = REPO_ROOT / "data" / "preprocessing" / "05_encoding" / "features.parquet"
DEFAULT_ENCODING_DICT = REPO_ROOT / "data" / "preprocessing" / "05_encoding" / "encoding_dictionary.json"
ARTIFACTS_DIR = REPO_ROOT / "mining" / "artifacts"
SYNTHETIC_ARTIFACTS_DIR = ARTIFACTS_DIR / "_synthetic"

ARTIFACT_FILES = {
    "rules": "skill_association_rules.parquet",
    "clusters": "job_clusters.parquet",
    "anomalies": "job_anomalies.parquet",
    "shap": "skill_salary_shap_values.parquet",
    "model": "trained_salary_rf_model.joblib",
    "metrics": "mining_metrics.json",
}

RANDOM_STATE = 42

# ---------------------------------------------------------------------------
# Ánh xạ tên cột logic -> các tên có thể gặp (tên mới theo docs/tasks trước, tên cũ theo code hiện tại)
# Thứ tự trong list là thứ tự ưu tiên.
# ---------------------------------------------------------------------------
COLUMN_ALIASES: dict[str, list[str]] = {
    "job_id": ["job_id_global", "job_id"],
    "job_title": ["job_title_clean", "job_title", "title"],
    "company_name": ["company_name", "company_norm"],
    "source_platform": ["source_platform"],
    "job_family": ["job_family"],
    # Cấp bậc có 3 dạng, ưu tiên: seniority_ord (0-5, Phát E1) > nhãn chữ > seniority_level (0-4, Duy).
    "seniority_ord": ["seniority_ord"],
    "seniority": ["seniority", "seniority_label"],
    "seniority_level": ["seniority_level"],
    "exp_min_years": ["exp_min_years"],
    "skills_list": ["skills_extracted", "skills_std", "skills_array"],
    # Lương trung bình: tên mới (triệu VNĐ/tháng) trước, rồi cột VNĐ cũ.
    "salary_avg": ["salary_avg", "salary_avg_mil", "salary_avg_vnd", "salary_midpoint_vnd"],
    "salary_min": ["salary_min", "salary_min_vnd_capped", "salary_min_vnd"],
    "salary_max": ["salary_max", "salary_max_vnd_capped", "salary_max_vnd"],
    "is_negotiable": ["is_negotiable", "is_salary_negotiable"],
    "salary_suspect": ["salary_suspect"],
    "province": ["city_normalized", "province_norm", "tinh_chinh"],
    "locations": ["locations"],
    "jd_text": ["jd_text", "job_description", "description_clean"],
    "jd_requirements": ["job_requirements", "requirements_clean"],
    "dup_group_id": ["dup_group_id", "duplicate_group_id", "golden_group_id", "cluster_dup_id"],
}

# Tiền tố cột kỹ năng nhị phân (Phát: "skill_" theo docs/tasks/05; code hiện tại: "skill__").
SKILL_PREFIXES: tuple[str, ...] = ("skill__", "skill_")
SKILL_EXCLUDE_COLUMNS = {"skills__other_count", "skill_count", "skills_count"}

# Lương lớn hơn ngưỡng này được hiểu là VNĐ, nhỏ hơn là triệu VNĐ (lương tháng IT nằm trong 1–500 triệu).
SALARY_VND_DETECT_THRESHOLD = 10_000.0

# Cấp bậc -> thứ tự (spec 07 §4.1: Intern=0 ... Lead=5), nhận cả nhãn tiếng Việt lẫn tiếng Anh.
SENIORITY_ORDINAL: dict[str, int] = {
    "thực tập": 0, "thuc tap": 0, "intern": 0, "internship": 0,
    "mới tốt nghiệp": 1, "moi tot nghiep": 1, "fresher": 1, "entry": 1,
    "junior": 2,
    "middle": 3, "mid": 3,
    "senior": 4,
    "trưởng nhóm/quản lý": 5, "truong nhom/quan ly": 5, "lead": 5, "manager": 5, "leader": 5,
}
SENIORITY_ORDER_LABELS = ["Thực tập", "Mới tốt nghiệp", "Junior", "Middle", "Senior", "Trưởng nhóm/Quản lý"]

# Thang 5 mức của Duy (preprocessing/transformation, cột seniority_level):
# 0 Intern/Fresher, 1 Junior, 2 Middle, 3 Senior, 4 Lead/Manager, -1 chưa rõ.
# Đổi sang thang 6 mức ở trên; Intern/Fresher gộp nên đưa về "Mới tốt nghiệp" (1), mức phổ biến hơn.
SENIORITY_LEVEL_TO_ORD: dict[int, int] = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}

# Nhóm địa bàn cho mô hình lương (docs/tasks/06: Hà Nội, TP.HCM, Khác).
# "Nhiều địa điểm" và "Toàn quốc" (location_normalizer của Duy) tách riêng, không gộp vào "khac",
# vì "khac" là các tỉnh còn lại và được dùng để so sánh trong sanity S-06.
LOCATION_GROUPS = ("ha_noi", "ho_chi_minh", "khac", "remote", "nhieu_dia_diem", "toan_quoc", "khong_ro")
LOCATION_FEATURE_GROUPS = ("ha_noi", "ho_chi_minh", "remote", "nhieu_dia_diem", "toan_quoc", "khac")


@dataclass
class AssociationParams:
    macro_min_support: float = 0.05
    micro_min_support: float = 0.02
    min_confidence: float = 0.60
    min_lift: float = 1.20
    max_len: int = 3
    min_group_size: int = 100  # nhóm nghề ít tin hơn thì không chạy vi mô
    min_rules_target: int = 30


@dataclass
class ClusteringParams:
    k_min: int = 4
    k_max: int = 14
    preferred_min_k: int = 8  # spec 08: tối thiểu 8 cụm nghề
    silhouette_target: float = 0.28
    davies_bouldin_target: float = 1.80  # docs/tasks/08 (Thuận): DBI < 1.80
    svd_variance_target: float = 0.80
    svd_max_components: int = 60
    tfidf_max_features: int = 100
    silhouette_sample_size: int = 3000
    hdbscan_min_cluster_size: int = 25
    glosh_outlier_quantile: float = 0.97
    top_skills_per_cluster: int = 8


@dataclass
class SalaryParams:
    test_size: float = 0.20
    cv_folds: int = 5
    min_skill_sample: int = 30  # chỉ xếp hạng kỹ năng có >= N tin có lương
    # Loại tin lương > 3x / < 1/3 trung vị cùng cấp bậc khỏi tập huấn luyện (None = tắt)
    level_ratio_limit: float | None = 3.0
    max_shap_rows: int = 3000
    top_k_report: int = 15
    param_grid: list[dict[str, object]] = field(default_factory=lambda: [
        {"n_estimators": 300, "max_depth": None, "min_samples_leaf": 2, "max_features": 0.33},
        {"n_estimators": 300, "max_depth": 20, "min_samples_leaf": 3, "max_features": 0.33},
        {"n_estimators": 300, "max_depth": None, "min_samples_leaf": 5, "max_features": "sqrt"},
        {"n_estimators": 300, "max_depth": 15, "min_samples_leaf": 1, "max_features": 0.5},
    ])
    r2_target: float = 0.60
    mae_target_mil: float = 4.5
    cv_std_target: float = 0.05


@dataclass
class AnomalyParams:
    contamination: float = 0.03
    n_estimators: int = 300
    fresher_skill_limit: int = 15  # spec 07 §5.1: Fresher/Intern đòi > 15 kỹ năng
    exp_mismatch_years: float = 5.0
    salary_ratio_limit: float = 3.0  # lương > 3x (hoặc < 1/3) trung vị cùng cấp bậc


@dataclass
class MiningParams:
    association: AssociationParams = field(default_factory=AssociationParams)
    clustering: ClusteringParams = field(default_factory=ClusteringParams)
    salary: SalaryParams = field(default_factory=SalaryParams)
    anomaly: AnomalyParams = field(default_factory=AnomalyParams)
    random_state: int = RANDOM_STATE
