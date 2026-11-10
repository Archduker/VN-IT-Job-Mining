"""PH5: logic dịch (che, tách, kiểm, cache, hook 03) bằng hàm dịch giả tiêm vào; không tải model."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from preprocessing.translation import core
from preprocessing.translation.core import TranslationContext, mask, split_text, unmask


def fake(chunks):  # "dịch": thêm tiền tố như model thật, giữ số và token giữ chỗ
    return ["vi: " + c.upper() for c in chunks]


def test_mask_unmask_roundtrip_only_given_terms():
    m, found = mask("Need UI/UX and python skills, not Pythonic", ["UI/UX", "Python"])
    assert "UI/UX" not in m and "Pythonic" in m and found == ["UI/UX", "python"]
    assert unmask(m, found) == "Need UI/UX and python skills, not Pythonic"
    assert mask("abc", []) == ("abc", [])


def test_load_approved_terms_ignores_unapproved(tmp_path):
    p = tmp_path / "n.json"
    p.write_text('{"entries":[{"term":"A","approved":true},{"term":"B","approved":false}]}')
    assert core.load_approved_terms(p) == ["A"]
    assert core.load_approved_terms(tmp_path / "none.json") == []


def test_split_keeps_lines_bullets_and_limit():
    text = "Intro line\n- first. second one here\n\n- " + " ".join(["w"] * 25)
    pieces = split_text(text, 10, lambda s: len(s.split()))
    assert all(len(b.split()) <= 10 for _, b in pieces)
    out = "".join(lead + b for lead, b in pieces)
    assert out.startswith("Intro line\n- first.") and out.count("\n- ") == 2
    assert out.split("\n")[-1].split() == ["-"] + ["w"] * 25


def test_validity_rules():
    assert core.is_valid("Need 5 years", "Cần 5 năm")
    assert not core.is_valid("Need 5 years", "Cần 6 năm")
    assert not core.is_valid("Use XTERM0X daily", "Dùng hàng ngày")
    assert core.is_valid("Salary 1,500-2,500 USD, 5+ years", "Lương 1.500-2.500 USD, hơn 5 năm")
    assert not core.is_valid("Need 5 years", " ")
    assert not core.is_valid("x" * 100, "y")


def test_translate_fields_vi_row_is_passthrough():
    r = TranslationContext(fake).translate_fields("mô tả", "yêu cầu", "vi")
    assert r["description_vi"] == "mô tả" and r["translated_by"] is None and r["translation_status"] == "not_needed"


def test_translate_fields_en_and_cache(tmp_path):
    calls = []

    def tf(chunks):
        calls.append(len(chunks))
        return fake(chunks)

    cache = tmp_path / "c.jsonl"
    ctx = TranslationContext(tf, terms=["UI/UX"], cache_path=cache)
    r = ctx.translate_fields("Build UI/UX 3 apps\n- Work with team", "5 years exp", "en")
    assert r["translation_status"] == "translated" and "UI/UX" in r["description_vi"]
    assert r["description_vi"].startswith("BUILD") and "\n- WORK WITH TEAM" in r["description_vi"]
    assert r["translated_by"].startswith(core.MODEL_ID) and r["translation_chunks"] == 3
    n = sum(calls)
    ctx2 = TranslationContext(tf, terms=["UI/UX"], cache_path=cache)  # resume từ file
    assert ctx2.translate_fields("Build UI/UX 3 apps\n- Work with team", "5 years exp", "en") == r
    assert sum(calls) == n and ctx2.stats["cache_hits"] == 3


def test_failed_chunk_retries_once_then_keeps_original():
    seen = []

    def bad(chunks):
        seen.append(list(chunks))
        return ["sai 99" for _ in chunks]  # đổi số -> không hợp lệ

    ctx = TranslationContext(bad)
    r = ctx.translate_fields("Need 5 years of experience", None, "en")
    assert len(seen) == 2 and r["translation_status"] == "failed"
    assert r["description_vi"] == "Need 5 years of experience" and ctx.stats["failed_chunks"] == 1
    assert ctx.cache == {}  # đoạn hỏng không vào cache


def test_not_run_when_no_translator():
    r = TranslationContext(None).translate_fields("Hello team", "x", "en")
    assert r["translation_status"] == "not_run" and r["description_vi"] is None


def test_transformation_hook_uses_translation_downstream():
    from preprocessing.transformation import run as t3
    row = {"job_id_global": "a", "source_platform": "topcv", "job_title": "Dev", "company_name": "C",
           "raw_description_text": "We are hiring a backend engineer with experience building scalable systems and working with the team",
           "raw_requirements_text": "Strong knowledge of databases and communication with customers and partners every day"}
    ctx = TranslationContext(fake)
    rows, rep = t3.process_source("topcv", [row], dry_run=True, translation=ctx)
    r = rows[0]
    assert r["language"] == "en" and r["translation_status"] == "translated"
    assert r["description_clean"].startswith("We are") and r["description_vi"].startswith("WE ARE")
    assert r["description_vi_fold"] and rep.data["extra"]["translation"]["rows_translated"] == 1
    rows0, _ = t3.process_source("topcv", [row], dry_run=True)  # mặc định tắt
    assert rows0[0]["translation_status"] == "not_run"


def test_review_sample_stratified_seed42():
    spec = importlib.util.spec_from_file_location("brs", Path(__file__).parents[2] / "scripts" / "build_translation_review_sample.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    df = pd.DataFrame({"source_platform": ["a"] * 60 + ["b"] * 30 + ["c"] * 3,
                       "translation_status": ["translated"] * 92 + ["failed"],
                       "job_id_global": range(93)})
    s = m.stratified_sample(df, 50)
    assert len(s) == 50 and set(s["source_platform"]) == {"a", "b", "c"}
    assert "failed" in set(s["translation_status"])
    assert list(m.stratified_sample(df, 50)["job_id_global"]) == list(s["job_id_global"])


@pytest.mark.live
def test_real_model_few_jds():
    """Chạy model thật (tải/nạp từ cache HF): pytest --run-live tests/unit/test_translation_ph5.py -k real"""
    from preprocessing.translation.translator import make_context
    ctx = make_context(4)
    r = ctx.translate_fields("Design and develop new features.\n- Work with 3 engineers on Python services",
                             "At least 2 years of experience with Java", "en")
    print(r, ctx.manifest())
    assert r["translation_status"] in ("translated", "failed") and r["description_vi"]
