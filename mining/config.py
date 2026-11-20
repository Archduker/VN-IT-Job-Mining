"""Cấu hình chung của module Data Mining (docs/spec/07_mining_spec.md, chi tiết docs/spec/mining/).

Mọi chỗ phụ thuộc vào schema của bước trước (Duy: lương, cấp bậc, địa bàn; Phát: cột kỹ năng)
đều gom ở đây. Khi đồng đội đổi tên cột, chỉ sửa COLUMN_ALIASES, không sửa thuật toán.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Đường dẫn mặc định (M0.1: Silver là đầu vào duy nhất; thiếu thì báo lỗi, không lùi về file khác)
# ---------------------------------------------------------------------------
DEFAULT_TABLE = REPO_ROOT / "data" / "preprocessing" / "04_normalization" / "silver.parquet"
DEFAULT_FEATURES = REPO_ROOT / "data" / "processing" / "10_features" / "features.parquet"
DEFAULT_ENCODING_DICT = REPO_ROOT / "data" / "processing" / "10_features" / "encoding_dictionary.json"
DEFAULT_E5 = REPO_ROOT / "data" / "processing" / "12_e5" / "job_emb.npz"
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
# Ánh xạ tên cột logic -> các tên có thể gặp (M0.2: tên Silver đứng đầu; tên cũ của bảng 04 giữ sau).
# Thứ tự trong list là thứ tự ưu tiên.
# ---------------------------------------------------------------------------
COLUMN_ALIASES: dict[str, list[str]] = {
    "job_id": ["job_id", "job_id_global"],
    "job_title": ["title", "job_title_clean", "job_title"],
    "company_name": ["company", "company_name", "company_norm"],
    "company_id": ["company_id"],
    "source_platform": ["source", "source_platform"],
    "job_family": ["job_family"],
    # Cấp bậc có 3 dạng, ưu tiên: seniority_ord (0-4, bước Encoding E1) > nhãn chữ > seniority_level (0-4, 04_normalization).
    "seniority_ord": ["seniority_ord"],
    "seniority": ["seniority", "seniority_label"],
    "seniority_level": ["seniority_level"],
    "seniority_inferred": ["seniority_inferred"],
    "exp_min_years": ["exp_min_years"],
    "exp_inferred": ["exp_inferred"],
    "skills_list": ["skills", "skills_extracted", "skills_std", "skills_array"],
    # Lương trung bình: tên mới (triệu VNĐ/tháng) trước, rồi cột VNĐ cũ.
    "salary_avg": ["salary_avg", "salary_avg_mil", "salary_avg_vnd", "salary_midpoint_vnd"],
    "salary_min": ["salary_min", "salary_min_vnd_capped", "salary_min_vnd"],
    "salary_max": ["salary_max", "salary_max_vnd_capped", "salary_max_vnd"],
    "is_negotiable": ["salary_negotiable", "is_negotiable", "is_salary_negotiable"],
    "salary_outlier": ["salary_outlier", "salary_suspect"],
    "province": ["province", "city_normalized", "province_norm", "tinh_chinh"],
    "locations": ["locations"],
    "work_mode": ["work_mode"],
    "employment_type": ["employment_type"],
    "language": ["language"],
    "benefits": ["benefits", "benefits_std"],
    "posted_month": ["posted_month"],
}
# Cột Silver chép nguyên sang meta cho M1–M6 (không đổi giá trị).
PASSTHROUGH_COLUMNS = ("company_id", "seniority_inferred", "exp_inferred", "work_mode", "employment_type",
                       "language", "benefits", "posted_month")

# Ba khối kỹ năng của bước 10 (M0.3, docs/target/06_yeu_cau_du_lieu.md mục 2):
# skill__ = K-tool, concept__ = K-concept, soft__ = K-soft. "skill_" một gạch không còn là tiền tố hợp lệ,
# để không nuốt khối khác. Cột <khối>__other_skill là kỹ năng hiếm đã gom, không phải một kỹ năng.
SKILL_PREFIXES: tuple[str, ...] = ("skill__",)
CONCEPT_PREFIX = "concept__"
SOFT_PREFIX = "soft__"
SKILL_BLOCKS: dict[str, str] = {"skills": "skill__", "concepts": CONCEPT_PREFIX, "soft": SOFT_PREFIX}
OTHER_SKILL_SUFFIX = "other_skill"
SKILL_EXCLUDE_COLUMNS = {f"{p}{OTHER_SKILL_SUFFIX}" for p in SKILL_BLOCKS.values()}
# Cột đếm và mục tiêu lương lấy thẳng từ features.parquet (bước 10), không tính lại.
FEATURE_META_COLUMNS = ("n_tools", "n_concepts", "n_soft", "salary_target_m")

# Lương lớn hơn ngưỡng này được hiểu là VNĐ, nhỏ hơn là triệu VNĐ (lương tháng IT nằm trong 1–500 triệu).
SALARY_VND_DETECT_THRESHOLD = 10_000.0

# Cấp bậc -> thứ tự (spec 07 §4.1: Intern/Fresher=0 ... Lead/Manager=4), nhận cả nhãn tiếng Việt lẫn tiếng Anh.
SENIORITY_ORDINAL: dict[str, int] = {
    "intern/fresher": 0, "intern": 0, "internship": 0, "fresher": 0, "entry": 0,
    "thực tập": 0, "thuc tap": 0, "mới tốt nghiệp": 0, "moi tot nghiep": 0,
    "junior": 1,
    "middle": 2, "mid": 2,
    "senior": 3,
    "lead/manager": 4, "lead": 4, "manager": 4, "leader": 4,
    "trưởng nhóm/quản lý": 4, "truong nhom/quan ly": 4,
}
SENIORITY_ORDER_LABELS = ["Intern/Fresher", "Junior", "Middle", "Senior", "Lead/Manager"]
JOB_FAMILY_OTHER = "Other"  # nhãn dự phòng của job_title.OTHER (SPEC-01: 12 nhóm + Other)

# Cột seniority_level của 04_normalization cùng thang 0-4 (null = chưa rõ), nên ánh xạ là đồng nhất.
SENIORITY_LEVEL_TO_ORD: dict[int, int] = {i: i for i in range(5)}

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
    algorithm: str = "kmeans"  # "kmeans" | "agglomerative" (Ward) | "gmm"; K-Means có Silhouette và độ ổn định tốt nhất (đo 11/11)
    k_fixed: int | None = 10  # người dùng chốt k=10; None thì chọn theo Silhouette trong [k_min, k_max]
    k_min: int = 2  # quét 2–20 để báo Elbow và Silhouette
    k_max: int = 20
    preferred_min_k: int = 5
    silhouette_target: float = 0.28
    davies_bouldin_target: float = 1.80  # docs/tasks/08 (Thuận): DBI < 1.80
    svd_variance_target: float = 0.80
    svd_max_components: int = 60
    # TF-IDF đã gỡ (spec 07 quyết định 1, M0.6)
    e5_weight: float = 0.5  # tỉ lệ năng lượng của khối vector e5 trong không gian phân cụm
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
class SanityParams:
    s01_min_conf: float = 0.85
    s01_min_lift: float = 1.5
    s02_report_only: bool = True  # M0.7a: Flutter => Dart chỉ báo cáo (quyết định 6: không tự suy kỹ năng)
    s03_min_conf: float = 0.60  # M0.7b: T2 (19/11)
    s06_ratio: float = 1.2


@dataclass
class MiningParams:
    association: AssociationParams = field(default_factory=AssociationParams)
    clustering: ClusteringParams = field(default_factory=ClusteringParams)
    salary: SalaryParams = field(default_factory=SalaryParams)
    anomaly: AnomalyParams = field(default_factory=AnomalyParams)
    sanity: SanityParams = field(default_factory=SanityParams)
    random_state: int = RANDOM_STATE
