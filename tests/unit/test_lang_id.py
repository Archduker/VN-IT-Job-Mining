"""PH3 S4: fastText lid.176 trên JD thật (data/preprocessing/01_clean). Không mock model."""

import json

import pytest

from preprocessing.common import lang_id
from preprocessing.integration.json_flattener import flatten_raw_job_record

MODEL = "models/fasttext/lid.176.bin"
DATA = "data/preprocessing/01_clean/itviec.jsonl"


def test_thieu_model_bao_loi_ro_rang(monkeypatch, tmp_path):
    monkeypatch.setenv("LID_MODEL_PATH", str(tmp_path / "khong_co.bin"))
    lang_id._model.cache_clear()
    with pytest.raises(FileNotFoundError, match="download_lid_model"):
        lang_id.detect_lang("Backend developer")
    lang_id._model.cache_clear()


@pytest.mark.needs_data(MODEL)
def test_van_ban_rong_la_other():
    assert lang_id.detect_lang("") == ("other", 0.0)
    assert lang_id.detect_lang(None) == ("other", 0.0)


@pytest.mark.needs_data(MODEL, DATA)
def test_jd_itviec_that_ra_nhan_hop_le():
    seen = {}
    for line in open(lang_id.REPO_ROOT / DATA, encoding="utf-8"):
        flat = flatten_raw_job_record(json.loads(line), "itviec")
        lang, conf = lang_id.detect_lang(flat.get("raw_description_text"))
        assert lang in {"vi", "en", "other"} and 0.0 <= conf <= 1.0
        if lang != "other":
            assert conf >= lang_id.CONF_MIN
        seen[lang] = seen.get(lang, 0) + 1
        if len(seen) >= 2 and sum(seen.values()) >= 100:
            break
    assert "vi" in seen and "en" in seen, seen  # ITviec có cả JD tiếng Việt lẫn tiếng Anh
