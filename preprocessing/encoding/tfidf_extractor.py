"""Trích xuất không gian đặc trưng TF-IDF cho văn bản JD (SPEC-06 §5.3, SPEC-07 §3.1, Task 05).

Phục vụ phân cụm K-Means/HDBSCAN và giảm chiều PCA.
Loại bỏ stopwords song ngữ Anh - Việt, trích xuất n-gram (1, 2) với Scikit-learn TfidfVectorizer.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

# Danh mục stopwords kỹ thuật và stopword tiếng Việt/Anh thông dụng trong tin tuyển dụng
COMMON_JD_STOPWORDS = [
    # Tiếng Việt
    "và",
    "của",
    "các",
    "có",
    "cho",
    "với",
    "được",
    "trong",
    "để",
    "về",
    "người",
    "khi",
    "làm",
    "việc",
    "công",
    "ty",
    "tại",
    "theo",
    "yêu",
    "cầu",
    "kinh",
    "nghiệm",
    "vị",
    "trí",
    "nhân",
    "viên",
    "mức",
    "lương",
    "chế",
    "độ",
    "quyền",
    "lợi",
    "ứng",
    "viên",
    "tham",
    "gia",
    "phát",
    "triển",
    "thực",
    "hiện",
    "tốt",
    "năng",
    "lực",
    "khả",
    "năng",
    "năm",
    "tháng",
    "ngày",
    "chúng",
    "tôi",
    "mô",
    "tả",
    "chi",
    "tiết",
    "hồ",
    "sơ",
    "liên",
    "hệ",
    "tuyển",
    "dụng",
    # Tiếng Anh
    "and",
    "the",
    "to",
    "of",
    "in",
    "for",
    "with",
    "is",
    "a",
    "an",
    "as",
    "at",
    "be",
    "by",
    "on",
    "are",
    "from",
    "you",
    "will",
    "our",
    "we",
    "team",
    "company",
    "work",
    "experience",
    "job",
    "description",
    "requirements",
    "benefits",
    "skills",
    "candidate",
    "position",
    "years",
]


def extract_tfidf_space(
    df: pd.DataFrame,
    text_columns: Sequence[str] = (
        "description_clean",
        "requirements_clean",
        "job_description",
        "job_requirements",
        "description",
        "requirements",
    ),
    max_features: int = 3000,
    min_df: int = 2,
    max_df: float = 0.8,
) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """Trích xuất ma trận TF-IDF từ các trường văn bản khả dụng trong DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame đầu vào chứa job_id_global và các trường mô tả.
    text_columns : Sequence[str]
        Danh sách các cột văn bản ưu tiên kết hợp.
    max_features : int
        Số lượng đặc trưng tối đa (mặc định 3.000).
    min_df : int
        Tần suất tối thiểu của từ khóa.
    max_df : float
        Tỷ lệ xuất hiện tối đa để loại bỏ từ phổ biến.

    Returns
    -------
    Tuple[Optional[pd.DataFrame], Dict[str, Any]]
        (DataFrame TF-IDF kèm job_id_global, Dictionary từ điển & siêu dữ liệu).
    """
    if "job_id_global" not in df.columns or len(df) == 0:
        return None, {}

    # Xác định các cột văn bản có tồn tại trong df
    available_cols = [c for c in text_columns if c in df.columns]
    if not available_cols:
        return None, {"status": "SKIPPED", "reason": "No text columns found in input"}

    # Kết hợp các chuỗi văn bản
    texts: list[str] = []
    for _, row in df[available_cols].iterrows():
        parts = [str(row[c]) for c in available_cols if pd.notna(row[c]) and str(row[c]).strip()]
        texts.append(" ".join(parts).lower())

    non_empty_count = sum(1 for t in texts if len(t.strip()) > 5)
    if non_empty_count < 2:
        return None, {"status": "SKIPPED", "reason": "Insufficient non-empty text documents"}

    effective_min_df = min_df

    try:
        vectorizer = TfidfVectorizer(
            max_features=max_features,
            min_df=effective_min_df,
            max_df=max_df,
            ngram_range=(1, 2),
            stop_words=COMMON_JD_STOPWORDS,
            dtype=np.float32,
        )
        tfidf_mat = vectorizer.fit_transform(texts)
    except ValueError as e:
        return None, {"status": "ERROR", "error": str(e)}

    feature_names = vectorizer.get_feature_names_out().tolist()
    col_names = [f"tfidf_{i:04d}" for i in range(len(feature_names))]

    tfidf_df = pd.DataFrame.sparse.from_spmatrix(tfidf_mat, columns=col_names)
    tfidf_df.insert(0, "job_id_global", df["job_id_global"].astype(str).values)

    vocab_dict = {
        col_names[i]: {
            "ngram": feature_names[i],
            "idf": float(vectorizer.idf_[i]),
        }
        for i in range(len(feature_names))
    }

    metadata = {
        "status": "SUCCESS",
        "total_documents": len(df),
        "total_features": len(feature_names),
        "max_features_configured": max_features,
        "source_columns": available_cols,
        "configuration": {
            "min_df": min_df,
            "max_df": max_df,
            "max_features": max_features,
            "ngram_range": [1, 2],
        },
        "vocabulary": vocab_dict,
    }

    return tfidf_df, metadata
