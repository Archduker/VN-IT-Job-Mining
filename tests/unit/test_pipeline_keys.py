import pytest

from collection.common.r2_storage import canonicalize_lakehouse_key
from preprocessing.common.r2_export import pipeline_key, silver_key


def test_pipeline_key_ok():
    assert pipeline_key("03_transformation", "all.parquet") == "pipeline/03_transformation/all.parquet"
    assert pipeline_key("rejected", "02.jsonl") == "pipeline/rejected/02.jsonl"
    assert pipeline_key("translation", "x.parquet") == "pipeline/translation/x.parquet"


def test_pipeline_key_bad_step():
    with pytest.raises(ValueError):
        pipeline_key("99_x", "a")


def test_canonicalize_accepts_pipeline_rejects_keep():
    k = pipeline_key("03_transformation", "all.parquet")
    assert canonicalize_lakehouse_key(k) == k
    with pytest.raises(ValueError):
        canonicalize_lakehouse_key("pipeline/.keep")


def test_silver_key_unchanged():
    assert silver_key("01_clean", "topcv") == "staging/topcv/preprocessing/01_clean.jsonl"
    assert silver_key("02_integration", "topcv") == "staging/topcv/preprocessing/02_integration.parquet"
