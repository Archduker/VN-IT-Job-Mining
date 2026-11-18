# -*- coding: utf-8 -*-
"""K8.12: script gom ứng viên kỹ năng (scripts/mine_skill_candidates.py)."""

import importlib.util
from pathlib import Path

import pandas as pd

_P = Path(__file__).resolve().parents[2] / "scripts" / "mine_skill_candidates.py"
_spec = importlib.util.spec_from_file_location("mine_skill_candidates", _P)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


def test_key_of_fold_va_bo_dau_cau():
    assert M.key_of("  Tiếng Anh, ") == "tieng anh"
    assert M.key_of("Node.js") == "node.js"
    assert M.key_of("C#") == "c#"


def test_shaped_ngrams_viet_hoa_giua_cau_va_ky_hieu():
    got = dict(M.shaped_ngrams("Có kinh nghiệm với Spring Boot và C# tốt"))
    assert got["Spring Boot"] is True
    assert got["Spring"] is True
    assert got["C#"] is True
    # đầu câu: chữ hoa của từ đầu không tính
    got2 = dict(M.shaped_ngrams("Python is required"))
    assert got2["Python"] is False
    assert got2["is"] is False
    assert dict(M.shaped_ngrams("Node.js and more"))["Node.js"] is True


def test_cue_phrases_tach_theo_dau_phay_va_hoac():
    assert M.cue_phrases("Có kinh nghiệm với MySQL hoặc PostgreSQL.") == ["MySQL", "PostgreSQL"]
    assert M.cue_phrases("Proficient in Java, Kotlin and Swift") == ["Java", "Kotlin", "Swift"]
    assert M.cue_phrases("Thành thạo ReactJS, React Native và Node.js") == ["ReactJS", "React Native", "Node.js"]


def test_mine_df_theo_tin_va_loc_min_df():
    rows = pd.DataFrame([
        {"job_id_global": "a_1", "source_platform": "itviec", "skills_list": ["Docker"],
         "raw_requirements_text": "Kinh nghiệm với Kubernetes, Docker", "raw_description_text": "We use Kubernetes daily"},
        {"job_id_global": "b_2", "source_platform": "topdev", "skills_list": ["docker"],
         "raw_requirements_text": "Biết Kubernetes là lợi thế", "raw_description_text": ""},
        {"job_id_global": "c_3", "source_platform": "topcv", "skills_list": None,
         "raw_requirements_text": "Golang là điểm cộng", "raw_description_text": ""},
    ])
    out = {r["key"]: r for r in M.mine(rows, M.alias_regex({"docker"}), min_df=2)}
    assert out["docker"]["df"] == 2 and out["docker"]["df_a"] == 2 and out["docker"]["df_d"] == 1
    assert out["kubernetes"]["df"] == 2 and out["kubernetes"]["df_c"] == 1
    assert "golang" not in out  # chỉ 1 tin
    assert out["kubernetes"]["by_platform"] == "itviec:1,topdev:1"
    assert len(out["kubernetes"]["examples"].split(" ‖ ")) == 2
