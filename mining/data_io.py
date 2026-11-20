"""Đọc dữ liệu đầu vào cho Mining và kiểm tra hợp đồng cột.

Đầu vào (M0, docs/spec/mining/M0_chuan_bi.md): Silver (`data/preprocessing/04_normalization/silver.parquet`),
`features.parquet` của bước 10 và `job_emb.npz` khóa `job` của 12_e5. Nối theo id, không theo thứ tự dòng.

Đầu ra là `MiningData`:
- `meta`: mỗi dòng một tin, các cột logic (job_id, job_title, job_family, seniority_ord, exp_min_years,
  location_group, salary_avg_mil, is_negotiable, salary_outlier, company_id, n_tools, salary_target_m, ...).
- `skills` (K-tool, `skill__`), `concepts` (`concept__`), `soft` (`soft__`): ma trận 0/1 (uint8), tên cột là
  tên hiển thị, cùng thứ tự dòng với `meta`; không có cột `<khối>__other_skill`.
- `e5`: vector khóa `job` (mô tả + yêu cầu), cùng thứ tự `meta`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mining.config import (
    JOB_FAMILY_OTHER,
    COLUMN_ALIASES,
    FEATURE_META_COLUMNS,
    PASSTHROUGH_COLUMNS,
    SALARY_VND_DETECT_THRESHOLD,
    SKILL_BLOCKS,
    SENIORITY_LEVEL_TO_ORD,
    SENIORITY_ORDER_LABELS,
    SENIORITY_ORDINAL,
    SKILL_EXCLUDE_COLUMNS,
    SKILL_PREFIXES,
)

logger = logging.getLogger(__name__)


class MiningContractError(ValueError):
    """Dữ liệu đầu vào không đúng hợp đồng (thiếu khóa, cột kỹ năng không phải 0/1, ...)."""


@dataclass
class MiningData:
    meta: pd.DataFrame
    skills: pd.DataFrame  # K-tool (skill__)
    concepts: pd.DataFrame = field(default_factory=pd.DataFrame)  # K-concept (concept__)
    soft: pd.DataFrame = field(default_factory=pd.DataFrame)  # K-soft (soft__)
    e5: np.ndarray | None = None  # vector e5 khóa "job", cùng thứ tự meta
    table_path: Path | None = None
    input_sha256: dict[str, str | None] = field(default_factory=dict)
    resolved_columns: dict[str, str | None] = field(default_factory=dict)
    row_log: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def n_jobs(self) -> int:
        return len(self.meta)

    def log_rows(self, step: str, n: int, note: str = "") -> None:
        self.row_log.append({"step": step, "rows": int(n), "note": note})


# ---------------------------------------------------------------------------
# Tiện ích
# ---------------------------------------------------------------------------
def fold_text(text: Any) -> str:
    """Chữ thường, bỏ dấu tiếng Việt (đ -> d), gộp khoảng trắng."""
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return ""
    s = str(text).strip().lower().replace("đ", "d")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.split())


def resolve_column(df: pd.DataFrame, logical: str) -> str | None:
    """Trả về tên cột thật ứng với tên logic, theo thứ tự ưu tiên trong COLUMN_ALIASES."""
    for cand in COLUMN_ALIASES.get(logical, [logical]):
        if cand in df.columns:
            return cand
    return None


def find_skill_columns(columns: Iterable[str], prefix: str | None = None) -> list[str]:
    """Các cột 0/1 của một khối theo tiền tố (mặc định K-tool `skill__`), bỏ `<khối>__other_skill`."""
    prefixes = (prefix,) if prefix else SKILL_PREFIXES
    return [c for c in columns if c not in SKILL_EXCLUDE_COLUMNS and any(c.startswith(p) for p in prefixes)]


def strip_skill_prefix(col: str) -> str:
    for p in (*SKILL_PREFIXES, *SKILL_BLOCKS.values()):
        if col.startswith(p):
            return col[len(p):]
    return col


def file_sha256(path: Path | None) -> str | None:
    """16 ký tự đầu của sha256 (ghi vào metrics để biết số chạy trên file nào)."""
    if not path or not Path(path).exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _as_list(val: Any) -> list[Any]:
    if val is None:
        return []
    if isinstance(val, float) and np.isnan(val):
        return []
    if isinstance(val, str):
        return [v.strip() for v in val.split(",") if v.strip()]
    if isinstance(val, list | tuple | set | np.ndarray | pd.Series):
        return list(val)
    return [val]


def seniority_to_ordinal(label: Any) -> int:
    """Nhãn cấp bậc -> 0..4, không rõ -> -1."""
    if label is None or (isinstance(label, float) and np.isnan(label)):
        return -1
    if isinstance(label, int | np.integer):
        return int(label) if 0 <= int(label) <= 4 else -1
    raw = str(label).strip().lower()
    if raw in SENIORITY_ORDINAL:
        return SENIORITY_ORDINAL[raw]
    folded = fold_text(label)
    return SENIORITY_ORDINAL.get(folded, -1)


def seniority_level_to_ordinal(level: Any, mapping: dict[int, int] | None = None) -> int:
    """seniority_level (0-4, cùng thang với Mining); null/ngoài khoảng -> -1."""
    m = SENIORITY_LEVEL_TO_ORD if mapping is None else mapping
    v = pd.to_numeric(pd.Series([level]), errors="coerce").iloc[0]
    if pd.isna(v) or float(v) != int(v):
        return -1
    return m.get(int(v), -1)


def _seniority_from_column(s: pd.Series, numeric_scale: str) -> tuple[np.ndarray, str]:
    """Đổi một cột cấp bậc sang 0-4. Cột số dùng thang `numeric_scale`.

    Cột chữ (kể cả seniority_level của bản cũ, chứa nhãn) đọc theo nhãn.
    """
    num = pd.to_numeric(s, errors="coerce")
    if s.notna().any() and num[s.notna()].notna().all():
        if numeric_scale == "level":
            return np.array([seniority_level_to_ordinal(v) for v in num], dtype=int), "level_0_4"
        out = num.fillna(-1).astype(int)
        return out.where(out.between(0, 4), -1).to_numpy(), "ord_0_4"
    return s.map(seniority_to_ordinal).astype(int).to_numpy(), "label"


def location_group(province: Any, locations: Any = None) -> str:
    """Nhóm địa bàn: ha_noi | ho_chi_minh | remote | nhieu_dia_diem | toan_quoc | khac | khong_ro."""
    f = fold_text(province).replace("_", " ")
    if f:
        if "ha noi" in f or f in {"hn", "hanoi"}:
            return "ha_noi"
        if "ho chi minh" in f or f in {"hcm", "tp hcm", "tphcm", "sai gon", "saigon"}:
            return "ho_chi_minh"
        if "remote" in f or "tu xa" in f:
            return "remote"
        if "nhieu dia diem" in f or "multi location" in f:
            return "nhieu_dia_diem"
        if "toan quoc" in f or "nationwide" in f:
            return "toan_quoc"
        return "khac"
    # Không có tỉnh chính: thử locations[] (dict có tinh_key, remote)
    for loc in _as_list(locations):
        if isinstance(loc, dict):
            if loc.get("tinh_key"):
                return location_group(loc.get("tinh_key"))
            if loc.get("remote"):
                return "remote"
    return "khong_ro"


def _to_bool(series: pd.Series | None, n: int) -> np.ndarray:
    if series is None:
        return np.zeros(n, dtype=bool)
    return series.astype("boolean").fillna(False).to_numpy(dtype=bool)


def _salary_to_mil(values: pd.Series) -> tuple[pd.Series, str]:
    """Đưa lương về triệu VNĐ/tháng. Tự nhận đơn vị theo trung vị."""
    s = pd.to_numeric(values, errors="coerce").astype(float)
    s = s.where(s > 0)
    med = s.median()
    if pd.notna(med) and med > SALARY_VND_DETECT_THRESHOLD:
        return s / 1e6, "vnd"
    return s, "trieu"


# ---------------------------------------------------------------------------
# Chuẩn hóa
# ---------------------------------------------------------------------------
def build_meta(golden: pd.DataFrame, notes: list[str]) -> tuple[pd.DataFrame, dict[str, str | None]]:
    n = len(golden)
    resolved = {k: resolve_column(golden, k) for k in COLUMN_ALIASES}
    if resolved["job_id"] is None:
        raise MiningContractError("Bộ golden thiếu khóa job_id_global/job_id.")

    def col(name: str) -> pd.Series | None:
        c = resolved.get(name)
        return golden[c] if c else None

    meta = pd.DataFrame(index=golden.index)
    meta["job_id"] = golden[resolved["job_id"]].astype(str).to_numpy()
    if meta["job_id"].duplicated().any():
        dup = int(meta["job_id"].duplicated().sum())
        raise MiningContractError(f"job_id bị trùng {dup} dòng; bộ golden phải mỗi tin một dòng.")

    for logical in ("job_title", "company_name", "source_platform", "job_family"):
        s = col(logical)
        meta[logical] = s.astype("string").to_numpy() if s is not None else pd.array([pd.NA] * n, dtype="string")
    meta["job_family"] = meta["job_family"].fillna(JOB_FAMILY_OTHER)

    # Cấp bậc: seniority_ord (0-4) > nhãn chữ > seniority_level (0-4)
    for logical, scale in (("seniority_ord", "ord"), ("seniority", "ord"), ("seniority_level", "level")):
        if resolved.get(logical) is not None:
            meta["seniority_ord"], how = _seniority_from_column(col(logical), scale)
            notes.append(f"Cấp bậc lấy từ cột {resolved[logical]} (dạng {how}).")
            break
    else:
        meta["seniority_ord"] = -1
        notes.append("Không có cột cấp bậc: seniority_ord = -1 cho mọi tin.")
    labels = np.array(SENIORITY_ORDER_LABELS + ["Chưa rõ"], dtype=object)
    meta["seniority"] = pd.array(labels[meta["seniority_ord"].to_numpy()], dtype="string")  # -1 -> "Chưa rõ"

    exp = col("exp_min_years")
    meta["exp_min_years"] = pd.to_numeric(exp, errors="coerce").to_numpy() if exp is not None else np.nan

    # Địa bàn
    prov = col("province")
    locs = col("locations")
    meta["location_group"] = [
        location_group(prov.iloc[i] if prov is not None else None, locs.iloc[i] if locs is not None else None)
        for i in range(n)
    ]

    # Lương (triệu VNĐ/tháng)
    unit = "missing"
    if resolved["salary_avg"] is not None:
        sal, unit = _salary_to_mil(col("salary_avg"))
    elif resolved["salary_min"] is not None or resolved["salary_max"] is not None:
        smin, u1 = _salary_to_mil(col("salary_min")) if resolved["salary_min"] else (pd.Series(np.nan, index=golden.index), "missing")
        smax, u2 = _salary_to_mil(col("salary_max")) if resolved["salary_max"] else (pd.Series(np.nan, index=golden.index), "missing")
        sal = pd.concat([smin, smax], axis=1).mean(axis=1, skipna=True)
        unit = u1 if u1 != "missing" else u2
        notes.append(f"Không có salary_avg: lấy trung bình ({resolved['salary_min']}, {resolved['salary_max']}).")
    else:
        sal = pd.Series(np.nan, index=golden.index)
        notes.append("Không có cột lương: bỏ qua mô hình lương.")
    meta["salary_avg_mil"] = sal.to_numpy(dtype=float)
    meta["is_negotiable"] = _to_bool(col("is_negotiable"), n)
    meta["salary_outlier"] = _to_bool(col("salary_outlier"), n)
    notes.append(f"Đơn vị lương đầu vào nhận diện: {unit}.")

    # Cột Silver chép nguyên (M0.2); thiếu cột thì để null, M1–M6 tự ghi "Không rõ"
    for logical in PASSTHROUGH_COLUMNS:
        s = col(logical)
        meta[logical] = s.to_numpy() if s is not None else None

    meta = meta.reset_index(drop=True)
    return meta, resolved


def skills_from_lists(lists: Sequence[Any], min_count: int = 1, max_k: int | None = None) -> pd.DataFrame:
    """Dựng ma trận multi-hot từ cột danh sách kỹ năng (dùng khi chưa có features.parquet)."""
    rows = [{str(s).strip() for s in _as_list(v) if str(s).strip()} for v in lists]
    counts: dict[str, int] = {}
    for r in rows:
        for s in r:
            counts[s] = counts.get(s, 0) + 1
    vocab = [s for s, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])) if c >= min_count]
    if max_k:
        vocab = vocab[:max_k]
    idx = {s: i for i, s in enumerate(vocab)}
    mat = np.zeros((len(rows), len(vocab)), dtype=np.uint8)
    for i, r in enumerate(rows):
        for s in r:
            j = idx.get(s)
            if j is not None:
                mat[i, j] = 1
    return pd.DataFrame(mat, columns=vocab)


def _aligned_features(features: pd.DataFrame, job_ids: pd.Series) -> pd.DataFrame:
    """features.parquet xếp lại theo job_id của meta (nối theo id). Thiếu hoặc trùng id thì báo lỗi."""
    key = "job_id_global" if "job_id_global" in features.columns else resolve_column(features, "job_id")
    if key is None:
        raise MiningContractError("features.parquet thiếu khóa job_id_global/job_id.")
    ids = features[key].astype(str)
    if ids.duplicated().any():
        raise MiningContractError("features.parquet có job_id trùng.")
    aligned = features.set_index(ids.to_numpy()).reindex(job_ids.astype(str).to_numpy())
    missing = int(pd.isna(aligned[key]).sum())
    if missing:
        raise MiningContractError(f"{missing} tin của bảng đầu vào không có dòng trong features.parquet.")
    return aligned.reset_index(drop=True)


def block_from_features(
    aligned: pd.DataFrame,
    prefix: str,
    skills_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Một khối kỹ năng (đã căn theo meta) thành ma trận 0/1, tên cột là tên hiển thị."""
    cols = find_skill_columns(aligned.columns, prefix)
    if not cols:
        return pd.DataFrame(index=aligned.index)
    vals = aligned[cols].to_numpy()
    if pd.isna(vals).any() or not np.isin(vals, [0, 1]).all():
        raise MiningContractError(f"Cột {prefix}* phải chỉ chứa 0/1, không có NaN.")
    names = []
    for c in cols:
        slug = strip_skill_prefix(c)
        names.append((skills_map or {}).get(slug) or (skills_map or {}).get(c) or slug)
    out = pd.DataFrame(vals.astype(np.uint8), columns=names)
    if out.columns.duplicated().any():  # hai slug ra cùng tên hiển thị -> gộp bằng OR
        out = out.T.groupby(level=0, sort=False).max().T.astype(np.uint8)
    return out


def skills_from_features(
    features: pd.DataFrame,
    job_ids: pd.Series,
    skills_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Khối K-tool (`skill__`) căn theo thứ tự job_id của meta."""
    aligned = _aligned_features(features, job_ids)
    if not find_skill_columns(aligned.columns):
        raise MiningContractError("features.parquet không có cột kỹ năng skill__*.")
    return block_from_features(aligned, SKILL_PREFIXES[0], skills_map)


def load_skills_map(path: Path | None) -> dict[str, str]:
    if not path or not Path(path).exists():
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    skills = data.get("skills", {}) if isinstance(data, dict) else {}
    m = skills.get("skills_map") or {}
    return {str(k): str(v) for k, v in m.items()}


def prepare_mining_data(
    golden: pd.DataFrame,
    features: pd.DataFrame | None = None,
    skills_map: dict[str, str] | None = None,
) -> MiningData:
    """Chuẩn hóa bảng đầu vào (Silver) + features.parquet thành MiningData (M0)."""
    notes: list[str] = []
    meta, resolved = build_meta(golden, notes)
    data_log = [{"step": "table", "rows": len(meta), "note": ""}]
    concepts = soft = pd.DataFrame(index=meta.index)

    if features is not None:
        aligned = _aligned_features(features, meta["job_id"])
        if not find_skill_columns(aligned.columns):
            raise MiningContractError("features.parquet không có cột kỹ năng skill__*.")
        skills = block_from_features(aligned, SKILL_BLOCKS["skills"], skills_map)
        concepts = block_from_features(aligned, SKILL_BLOCKS["concepts"], skills_map)
        soft = block_from_features(aligned, SKILL_BLOCKS["soft"], skills_map)
        notes.append(f"Ba khối kỹ năng từ features.parquet: skill {skills.shape[1]}, concept {concepts.shape[1]}, "
                     f"soft {soft.shape[1]} cột (bỏ <khối>__other_skill).")
        # M0.3, M0.9: đếm và mục tiêu lương lấy thẳng từ bước 10
        for c in FEATURE_META_COLUMNS:
            if c in aligned.columns:
                meta[c] = pd.to_numeric(aligned[c], errors="coerce").to_numpy()
        if "salary_target_m" in meta:
            meta["salary_avg_mil"] = meta["salary_target_m"].to_numpy(dtype=float)
            notes.append("Lương = salary_target_m của bước 10 (triệu VNĐ/tháng).")
    elif resolved.get("skills_list"):
        skills = skills_from_lists(golden[resolved["skills_list"]].tolist())
        notes.append(
            f"Chưa có features.parquet: dựng ma trận kỹ năng từ cột {resolved['skills_list']} "
            f"({skills.shape[1]} kỹ năng), chỉ để thử; không có khối concept/soft."
        )
    else:
        raise MiningContractError("Không có features.parquet và bảng đầu vào không có cột danh sách kỹ năng.")

    skills = skills.reset_index(drop=True)
    meta["n_skills"] = skills.sum(axis=1).to_numpy(dtype=int)  # số cột K-tool của ma trận (M4 cũ dùng)
    if "n_tools" not in meta:
        meta["n_tools"] = meta["n_skills"]
    return MiningData(meta=meta, skills=skills, concepts=concepts.reset_index(drop=True),
                      soft=soft.reset_index(drop=True), resolved_columns=resolved, row_log=data_log, notes=notes)


def load_e5(path: Path, job_ids: pd.Series) -> np.ndarray:
    """Vector e5 khóa "job" (mô tả + yêu cầu, không phúc lợi; M0.4), xếp theo job_ids.

    Thiếu khóa hoặc thiếu tin thì báo lỗi, không bịa vector và không lùi về khóa "all"."""
    z = np.load(path, allow_pickle=True)
    if "job" not in z.files:
        raise MiningContractError(f"{path} không có khóa 'job' (có: {z.files}); chạy lại 12_e5.")
    pos = {str(j): i for i, j in enumerate(z["ids"])}
    miss = [j for j in job_ids.astype(str) if j not in pos]
    if miss:
        raise MiningContractError(f"{len(miss)} tin không có vector e5 (ví dụ {miss[0]}).")
    return z["job"][[pos[j] for j in job_ids.astype(str)]].astype(np.float32)


def load_mining_data(
    table_path: Path,
    features_path: Path | None = None,
    encoding_dict_path: Path | None = None,
    e5_path: Path | None = None,
) -> MiningData:
    """Đọc Silver + features + e5 từ file. Thiếu bảng thì FileNotFoundError (không đọc file khác thay)."""
    table_path = Path(table_path)
    if not table_path.exists():
        raise FileNotFoundError(f"Không tìm thấy bảng đầu vào: {table_path}")
    table = pd.read_parquet(table_path)
    features = None
    if features_path and Path(features_path).exists():
        features = pd.read_parquet(features_path)
    elif features_path:
        logger.warning("Không thấy %s, dựng ma trận kỹ năng từ cột danh sách (chỉ để thử).", features_path)
    data = prepare_mining_data(table, features, load_skills_map(encoding_dict_path))
    if e5_path and Path(e5_path).exists():
        data.e5 = load_e5(Path(e5_path), data.meta["job_id"])
        data.notes.append(f"Vector e5 (khóa job): {data.e5.shape}")
    data.table_path = table_path
    data.input_sha256 = {"table": file_sha256(table_path), "features": file_sha256(features_path),
                         "encoding_dict": file_sha256(encoding_dict_path), "e5": file_sha256(e5_path)}
    data.notes.insert(0, f"table={table_path.as_posix()}, "
                         f"features={Path(features_path).as_posix() if features is not None else None}")
    return data
