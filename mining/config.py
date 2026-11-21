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
DEFAULT_JOB_SKILLS = REPO_ROOT / "data" / "processing" / "08_skills" / "job_skills.parquet"
ARTIFACTS_DIR = REPO_ROOT / "mining" / "artifacts"
SYNTHETIC_ARTIFACTS_DIR = ARTIFACTS_DIR / "_synthetic"

ARTIFACT_FILES = {
    "rules": "skill_association_rules.parquet",
    "clusters": "job_clusters.parquet",
    "anomalies": "job_anomalies.parquet",
    "shap": "skill_salary_shap_values.parquet",
    "model": "trained_salary_rf_model.joblib",
    "estimates": "salary_estimates.parquet",
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
PASSTHROUGH_COLUMNS = ("province", "company_id", "seniority_inferred", "exp_inferred", "work_mode", "employment_type",
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
    min_support_count: int = 10  # M2.2a: mỗi luật dựa trên ít nhất 10 tin
    min_level_group_size: int = 40  # 2.3, người dùng chốt 20/11 (2.B): nghề × nhóm cấp cần >= 40 giỏ
    top_n: int = 15  # 2.1
    min_family_jobs: int = 30  # 2.1: nghề < 30 tin -> "ít dữ liệu"
    rare_max_df: float = 0.02  # 2.4 (PRE-36)
    rare_min_lift: float = 2.0
    rare_senior_share: float = 0.6
    stability_factors: tuple[float, ...] = (0.5, 2.0)  # M2.5: support một bậc dưới / trên
    stability_top: int = 20
    stability_target: float = 0.70  # đề xuất đã duyệt 20/11
    hand_check_n: int = 20  # M2.6
    hand_check_per_scope: int = 5


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
    e5_weight: float = 0.5  # chỉ cho build_vector_space hai khối cũ; M3 dùng block_weights
    silhouette_sample_size: int = 3000
    hdbscan_min_cluster_size: int = 25
    glosh_outlier_quantile: float = 0.97
    top_skills_per_cluster: int = 8
    # M3.1a: trọng số khối; khối vắng thì chia lại cho tổng các khối có mặt. Người dùng chốt 20/11 (1.D):
    # 0,15 / 0,15 / 0,7 thay 0,35 / 0,15 / 0,5 (bộ cũ gom 928 tin không công cụ vào một cụm)
    block_weights: dict[str, float] = field(default_factory=lambda: {"tool": 0.15, "concept": 0.15, "e5": 0.7})
    kmeans_n_init: int = 50  # 2.B (20/11): n_init 10 cho ARI 5 seed 0,73; 50 cho 0,83 (k = 10)
    stability_seeds: tuple[int, ...] = (42, 43, 44, 45, 46)  # M3.7
    stability_ari_target: float = 0.80  # PRE-36
    min_cluster_share: float = 0.01  # cụm nhỏ nhất >= 1% số tin (PRE-36)
    skill_count_ratio_max: float | None = None  # M3.8, 3.B (20/11): chỉ kiểm trung vị n_tools < 1
    hybrid_max_share: float = 0.60  # M3.10 nghề lai
    hybrid_min_second: float = 0.20
    niche_family_share: float = 0.50  # M3.10 nghề ngách
    niche_small_share: float = 0.05
    niche_min_lift: float = 5.0
    niche_min_skills: int = 3
    mismatch_majority: float = 0.60  # M3.10 có vẻ gán sai
    mismatch_dist_q: float = 0.25
    mismatch_family_share: float = 0.10


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
    r2_target: float = 0.60  # chỉ báo cáo (ngưỡng cũ, PRE-36)
    mae_target_mil: float = 4.5  # chỉ báo cáo (ngưỡng cũ, PRE-36)
    cv_std_target: float = 0.05
    # M5 (docs/spec/mining/M5_luong_shap.md, duyệt 20/11)
    baseline_margin: float = 0.10  # M5.7: phương án A phải có MAE thấp hơn baseline cấp × nghề >= 10%
    min_group_eval: int = 30  # ô baseline và nhóm MAE dưới 30 tin: lùi về cấp / ghi "ít dữ liệu"
    bootstrap_n: int = 200  # M5.10: khoảng tin cậy giá trị kỹ năng
    dist_warn_ratio: float = 2.0  # M5.12: nhóm chiếm tỷ lệ >= 2 lần ở tập thỏa thuận → cảnh báo
    n_bands: int = 4  # phương án B: 4 khung theo tứ phân vị train
    feature_config: str = "tool_concept"  # M5.3b: người dùng chọn 20/11 (1.B); "tool_only" vẫn được đo để so


@dataclass
class AnomalyParams:
    contamination: float = 0.03
    n_estimators: int = 300
    # M4.4a (duyệt 20/11): ngưỡng số công cụ theo phân vị dữ liệu, thay số cố định 15
    too_many_q: float = 0.99  # TOO_MANY_SKILLS: n_tools > P99 mọi tin
    fresher_q: float = 0.95  # FRESHER_TOO_MANY_SKILLS: tin người mới có n_tools > P95 của tin người mới
    normal_band: tuple[float, float] = (0.05, 0.95)  # M4.5: "mới" khi các trường trong P5–P95 của cấp
    hand_check_n: int = 20  # M4.6
    exp_mismatch_years: float = 5.0
    salary_ratio_limit: float = 3.0  # lương > 3x (hoặc < 1/3) trung vị cùng cấp bậc


NEWCOMER_LABELS = ("Intern/Fresher", "Junior")
MIDDLE_PLUS_LABELS = ("Middle", "Senior", "Lead/Manager")


@dataclass
class BIParams:
    """M1 (docs/spec/mining/M1_bi.md)."""
    min_cell: int = 30  # M1.0b: nhóm n < 30 -> "ít dữ liệu" (PRE-36)
    mnar_share: float = 0.55  # M1.0d: cấp có >= 55% tin thỏa thuận -> ghi chú MNAR
    top_provinces: int = 10
    top_benefits: int = 15
    top_benefit_cross: int = 5
    top_tools: int = 15
    top_soft: int = 10
    min_newcomer_jobs: int = 30  # M1.D: nghề có >= 30 tin người mới mới có demand
    newcomer: tuple[str, ...] = NEWCOMER_LABELS
    middle_plus: tuple[str, ...] = MIDDLE_PLUS_LABELS
    first_month: str = "2026-09"
    # 1.7: nguồn ghi ngày đăng cho gần hết tin (bỏ topcv, topdev; target SD1 mục 4)
    month_compare_sources: tuple[str, ...] = ("vietnamworks", "careerviet", "vieclam24h", "itviec", "glints", "jobsgo")


@dataclass
class SanityParams:
    s01_min_conf: float = 0.85
    s01_min_lift: float = 1.5
    s02_report_only: bool = True  # M0.7a: Flutter => Dart chỉ báo cáo (quyết định 6: không tự suy kỹ năng)
    s03_min_conf: float = 0.60  # M0.7b: T2 (19/11)
    s06_ratio: float = 1.2


@dataclass
class RecommendParams:
    """M6 (docs/spec/mining/M6_lo_trinh.md, duyệt 20/11; ngưỡng PRE-36)."""
    min_newcomer_jobs: int = 30  # M6.0
    min_demand: float = 0.05  # M6.1: chỉ xếp kỹ năng >= 5% tin người mới của nghề
    strong_conf: float = 0.60  # M6.2: luật mạnh
    strong_lift: float = 1.20
    defer_ratio: float = 3.0  # M6.3
    defer_min_jobs: int = 10  # 4.B (20/11): kỹ năng phải có >= 10 tin Senior/Lead
    coverage_need: float = 0.70  # M6.4: top N đáp ứng >= 70% công cụ của tin
    coverage_ns: tuple[int, ...] = (5, 10, 15)
    split: float = 0.20  # M6.5
    split_max_diff: float = 0.10
    split_seeds: tuple[int, ...] = (42, 43, 44, 45, 46)  # 3.B (20/11): lấy trung bình độ lệch qua 5 lần chia


@dataclass
class MiningParams:
    association: AssociationParams = field(default_factory=AssociationParams)
    clustering: ClusteringParams = field(default_factory=ClusteringParams)
    salary: SalaryParams = field(default_factory=SalaryParams)
    anomaly: AnomalyParams = field(default_factory=AnomalyParams)
    sanity: SanityParams = field(default_factory=SanityParams)
    bi: BIParams = field(default_factory=BIParams)
    recommend: RecommendParams = field(default_factory=RecommendParams)
    random_state: int = RANDOM_STATE
