"""Sparse full-corpus exploratory TF-IDF with reconstructable transform state."""

import json
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer

from preprocessing.encoding.execution_io import COMMON_JD_STOPWORDS, is_null

PARAMETERS = dict(analyzer="word", ngram_range=(1, 2), min_df=5, max_df=0.8, max_features=3000,
                  norm="l2", use_idf=True, smooth_idf=True, sublinear_tf=False, binary=False,
                  lowercase=True, strip_accents=None, token_pattern=r"(?u)\b\w\w+\b")


def corpus(df):
    return [f"{'' if is_null(a) else a}\n{'' if is_null(b) else b}" for a, b in
            zip(df.description_clean, df.requirements_clean, strict=True)]


def fit_text(df, stopword_asset):
    words = json.loads(stopword_asset.read_text())["words"]
    params = dict(PARAMETERS, stop_words=words, dtype=np.float32)
    vectorizer, matrix = _fit_vectorizer(corpus(df), **params)
    matrix = matrix.tocsr()
    terms = vectorizer.get_feature_names_out().tolist()
    vocabulary = [dict(index=i, feature_name=f"tfidf_{i:04d}", term=term, idf=float(vectorizer.idf_[i])) for i, term in enumerate(terms)]
    config = dict(parameters={**PARAMETERS, "ngram_range": [1, 2], "dtype": "float32"},
                  stopwords=words, stopword_version="jd-stopwords-v1", text_fields=["description_clean", "requirements_clean"],
                  join_separator="\n", sklearn_version=sklearn.__version__, view="full-corpus exploratory",
                  downstream_warning="Supervised evaluation must refit preprocessing on training data only")
    return matrix, vocabulary, config


def reconstruct_transform(texts, vocabulary, config):
    params = dict(config["parameters"])
    params["ngram_range"] = tuple(params["ngram_range"])
    params["dtype"] = np.float32
    model = TfidfVectorizer(**params, stop_words=config["stopwords"],
                            vocabulary={entry["term"]: entry["index"] for entry in vocabulary})
    model.idf_ = np.asarray([entry["idf"] for entry in vocabulary], dtype=np.float32)
    return model.transform(texts).tocsr()


def _fit_vectorizer(texts, **parameters):
    """Shared sklearn fit; callers retain their explicit text/config contracts."""
    vectorizer = TfidfVectorizer(**parameters)
    return vectorizer, vectorizer.fit_transform(texts)


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
        vectorizer, tfidf_mat = _fit_vectorizer(
            texts,
            max_features=max_features,
            min_df=effective_min_df,
            max_df=max_df,
            ngram_range=(1, 2),
            stop_words=COMMON_JD_STOPWORDS,
            dtype=np.float32,
        )
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
