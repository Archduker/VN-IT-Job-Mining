"""Unit test cho scripts/label_tool.py (TUI, Web UI, Thống kê, Gợi ý, Sinh chính sách)."""

import csv
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from scripts import label_tool


@pytest.fixture
def temp_review(tmp_path, monkeypatch):
    rev_dir = tmp_path / "review"
    rev_dir.mkdir(parents=True, exist_ok=True)
    policy_path = tmp_path / "it_policy.json"

    monkeypatch.setattr(label_tool, "REVIEW_DIR", rev_dir)
    monkeypatch.setattr(label_tool, "POLICY_PATH", policy_path)

    # Tạo file test cho 2 nguồn
    src_a = rev_dir / "it_careerviet.csv"
    with src_a.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=label_tool.FIELDS)
        w.writeheader()
        w.writerow({
            "job_id": "1",
            "source_url": "https://x/1",
            "job_title": "Kế toán trưởng",
            "skills": "Kế toán",
            "it_rule": "non_it",
            "it_rule_level": "1",
            "it_status": "non_it",
            "nhan_tay": "",
        })
        w.writerow({
            "job_id": "2",
            "source_url": "https://x/2",
            "job_title": "Senior Backend Developer",
            "skills": "Python, Django",
            "it_rule": "it",
            "it_rule_level": "1",
            "it_status": "it",
            "nhan_tay": "it",
        })

    return tmp_path


def test_load_and_save_rows(temp_review):
    rows = label_tool.load_rows("careerviet")
    assert len(rows) == 2
    assert rows[0]["job_title"] == "Kế toán trưởng"

    rows[0]["nhan_tay"] = "non_it"
    label_tool.save_rows("careerviet", rows)

    reloaded = label_tool.load_rows("careerviet")
    assert reloaded[0]["nhan_tay"] == "non_it"
    # Kiểm tra bảo toàn encoding UTF-8 BOM
    raw_bytes = (temp_review / "review" / "it_careerviet.csv").read_bytes()
    assert raw_bytes.startswith(b"\xef\xbb\xbf")


def test_get_source_stats(temp_review):
    st = label_tool.get_source_stats("careerviet")
    assert st["total"] == 2
    assert st["labeled"] == 1
    assert st["unlabeled"] == 1
    assert st["it"] == 1
    assert st["non_it"] == 0
    assert st["rule_accuracy"] == 100.0


def test_auto_suggest_obvious(temp_review):
    # Chạy dry-run
    label_tool.auto_suggest_obvious(apply=False)
    rows_before = label_tool.load_rows("careerviet")
    assert rows_before[0]["nhan_tay"] == ""

    # Chạy apply
    label_tool.auto_suggest_obvious(apply=True)
    rows_after = label_tool.load_rows("careerviet")
    assert rows_after[0]["nhan_tay"] == "non_it"


def test_generate_policy(temp_review):
    # Điền nhãn
    rows = label_tool.load_rows("careerviet")
    rows[0]["nhan_tay"] = "non_it"
    label_tool.save_rows("careerviet", rows)

    policy = label_tool.generate_policy(apply=True)
    assert "careerviet" in policy
    assert "drop" in policy["careerviet"]
    assert (temp_review / "it_policy.json").exists()


def test_tui_key_input(temp_review):
    # Mock đầu vào phím '2' (non_it) rồi 'q' (thoát)
    with patch("scripts.label_tool.get_key_raw", side_effect=["2", "q"]):
        label_tool.run_tui(target_source="careerviet", unlabeled_only=True)

    rows = label_tool.load_rows("careerviet")
    assert rows[0]["nhan_tay"] == "non_it"
