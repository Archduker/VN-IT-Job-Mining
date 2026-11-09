"""Sparse full-corpus exploratory TF-IDF with reconstructable transform state."""

import json

import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer

from preprocessing.encoding.execution_io import is_null

PARAMETERS = dict(analyzer="word", ngram_range=(1, 2), min_df=5, max_df=0.8, max_features=3000,
                  norm="l2", use_idf=True, smooth_idf=True, sublinear_tf=False, binary=False,
                  lowercase=True, strip_accents=None, token_pattern=r"(?u)\b\w\w+\b")


def corpus(df):
    return [f"{'' if is_null(a) else a}\n{'' if is_null(b) else b}" for a, b in
            zip(df.description_clean, df.requirements_clean, strict=True)]


def fit_text(df, stopword_asset):
    words = json.loads(stopword_asset.read_text())["words"]
    params = dict(PARAMETERS, stop_words=words, dtype=np.float32)
    vectorizer = TfidfVectorizer(**params)
    matrix = vectorizer.fit_transform(corpus(df)).tocsr()
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
