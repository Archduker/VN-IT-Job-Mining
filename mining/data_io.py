"""Đọc dữ liệu đầu vào cho Mining và kiểm tra hợp đồng cột.

Đầu ra là `MiningData`, một cấu trúc đã chuẩn hóa tên cột, để 4 thuật toán không phải biết
schema của bộ golden hay features.parquet thay đổi thế nào:
- `meta`: mỗi dòng một tin, các cột logic (job_id, job_title, job_family, seniority_ord,
  exp_min_years, location_group, salary_avg_mil, is_negotiable, salary_suspect, jd_text, ...).
- `skills`: ma trận 0/1 (uint8), tên cột là tên kỹ năng hiển thị, cùng thứ tự dòng với `meta`.
"""

from __future__ import annotations

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
    COLUMN_ALIASES,
    SALARY_VND_DETECT_THRESHOLD,
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
    skills: pd.DataFrame
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


def find_skill_columns(columns: Iterable[str]) -> list[str]:
    """Các cột kỹ năng nhị phân theo tiền tố, bỏ cột đếm như skills__other_count."""
    out = []
    for c in columns:
        if c in SKILL_EXCLUDE_COLUMNS:
            continue
        if any(c.startswith(p) for p in SKILL_PREFIXES):
            out.append(c)
    return out


def strip_skill_prefix(col: str) -> str:
    for p in SKILL_PREFIXES:  # "skill__" đứng trước "skill_" nên bỏ đúng 2 gạch
        if col.startswith(p):
            return col[len(p):]
    return col


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
    """Nhãn cấp bậc -> 0..5, không rõ -> -1."""
    if label is None or (isinstance(label, float) and np.isnan(label)):
        return -1
    if isinstance(label, int | np.integer):
        return int(label) if 0 <= int(label) <= 5 else -1
    raw = str(label).strip().lower()
    if raw in SENIORITY_ORDINAL:
        return SENIORITY_ORDINAL[raw]
    folded = fold_text(label)
    return SENIORITY_ORDINAL.get(folded, -1)


def seniority_level_to_ordinal(level: Any, mapping: dict[int, int] | None = None) -> int:
    """Thang 0-4 của Duy (seniority_level) -> thang 0-5 của Mining; -1/không rõ -> -1."""
    m = SENIORITY_LEVEL_TO_ORD if mapping is None else mapping
    v = pd.to_numeric(pd.Series([level]), errors="coerce").iloc[0]
    if pd.isna(v) or float(v) != int(v):
        return -1
    return m.get(int(v), -1)


def _seniority_from_column(s: pd.Series, numeric_scale: str) -> tuple[np.ndarray, str]:
    """Đổi một cột cấp bậc sang 0-5. Cột số dùng thang `numeric_scale` ("ord" 0-5 hoặc "level" 0-4).

    Cột chữ (kể cả seniority_level của bản cũ, chứa nhãn) đọc theo nhãn.
    """
    num = pd.to_numeric(s, errors="coerce")
    if s.notna().any() and num[s.notna()].notna().all():
        if numeric_scale == "level":
            return np.array([seniority_level_to_ordinal(v) for v in num], dtype=int), "level_0_4"
        out = num.fillna(-1).astype(int)
        return out.where(out.between(0, 5), -1).to_numpy(), "ord_0_5"
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
    meta["job_family"] = meta["job_family"].fillna("Khác")

    # Cấp bậc: seniority_ord (0-5) > nhãn chữ > seniority_level (0-4 của Duy)
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
    meta["salary_suspect"] = _to_bool(col("salary_suspect"), n)
    notes.append(f"Đơn vị lương đầu vào nhận diện: {unit}.")

    # Văn bản JD cho TF-IDF
    parts = [s.astype("string").fillna("") for s in (col("jd_text"), col("jd_requirements")) if s is not None]
    if parts:
        jd = parts[0]
        for p in parts[1:]:
            jd = jd + " " + p
        meta["jd_text"] = jd.str.strip().to_numpy()
    else:
        meta["jd_text"] = ""

    grp = col("dup_group_id")
    meta["dup_group_id"] = grp.astype("string").to_numpy() if grp is not None else pd.NA

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


def skills_from_features(
    features: pd.DataFrame,
    job_ids: pd.Series,
    skills_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Lấy ma trận kỹ năng từ features.parquet, căn theo thứ tự job_id của meta."""
    key = resolve_column(features, "job_id")
    if key is None:
        raise MiningContractError("features.parquet thiếu khóa job_id_global/job_id.")
    skill_cols = find_skill_columns(features.columns)
    if not skill_cols:
        raise MiningContractError("features.parquet không có cột kỹ năng (tiền tố skill_ hoặc skill__).")

    mat = features[skill_cols]
    vals = mat.to_numpy()
    bad = ~np.isin(vals[~pd.isna(vals)], [0, 1])
    if pd.isna(vals).any() or bad.any():
        raise MiningContractError("Cột kỹ năng phải chỉ chứa 0/1, không có NaN.")

    feat = features[[key] + skill_cols].copy()
    feat[key] = feat[key].astype(str)
    if feat[key].duplicated().any():
        raise MiningContractError("features.parquet có job_id trùng.")
    aligned = feat.set_index(key).reindex(job_ids.astype(str).to_numpy())
    missing = int(aligned[skill_cols[0]].isna().sum())
    if missing:
        raise MiningContractError(f"{missing} tin trong golden không có dòng trong features.parquet.")

    names = []
    for c in skill_cols:
        slug = strip_skill_prefix(c)
        names.append((skills_map or {}).get(slug) or (skills_map or {}).get(c) or slug)
    out = pd.DataFrame(aligned.to_numpy(dtype=np.uint8), columns=names)
    # Hai slug có thể ra cùng tên hiển thị -> gộp bằng OR
    if out.columns.duplicated().any():
        out = out.T.groupby(level=0, sort=False).max().T.astype(np.uint8)
    return out


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
    """Chuẩn hóa golden (+ features nếu có) thành MiningData."""
    notes: list[str] = []
    meta, resolved = build_meta(golden, notes)
    data_log = [{"step": "golden", "rows": len(meta), "note": ""}]

    if features is not None:
        skills = skills_from_features(features, meta["job_id"], skills_map)
        notes.append(f"Ma trận kỹ năng lấy từ features.parquet: {skills.shape[1]} cột.")
    elif resolved.get("skills_list"):
        skills = skills_from_lists(golden[resolved["skills_list"]].tolist())
        notes.append(
            f"Chưa có features.parquet: dựng ma trận kỹ năng từ cột {resolved['skills_list']} "
            f"({skills.shape[1]} kỹ năng)."
        )
    else:
        raise MiningContractError("Không có features.parquet và golden không có cột danh sách kỹ năng.")

    skills = skills.reset_index(drop=True)
    meta["n_skills"] = skills.sum(axis=1).to_numpy(dtype=int)
    data = MiningData(meta=meta, skills=skills, resolved_columns=resolved, row_log=data_log, notes=notes)
    return data


def load_mining_data(
    golden_path: Path,
    features_path: Path | None = None,
    encoding_dict_path: Path | None = None,
) -> MiningData:
    golden_path = Path(golden_path)
    if not golden_path.exists():
        raise FileNotFoundError(f"Không tìm thấy bộ golden: {golden_path}")
    golden = pd.read_parquet(golden_path)
    features = None
    if features_path and Path(features_path).exists():
        features = pd.read_parquet(features_path)
    elif features_path:
        logger.warning("Không thấy %s, dựng ma trận kỹ năng từ golden.", features_path)
    data = prepare_mining_data(golden, features, load_skills_map(encoding_dict_path))
    data.notes.insert(0, f"golden={golden_path.as_posix()}, features={Path(features_path).as_posix() if features is not None else None}")
    return data
