# -*- coding: utf-8 -*-
"""scripts/report_data_issues.py: chọn snapshot mới nhất, bỏ file batch, luật giữ trường, luật trùng lặp, đủ mục HTML."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import report_data_issues as rdi  # noqa: E402


def envelope(src, job_id, title, company, city, scraped, version=1, **payload):
    return {"metadata": {"job_id": job_id, "source": src, "source_url": f"https://x/{job_id}", "scraped_at": scraped,
                         "version": version},
            "raw_payload": {"title": title, "company": company, "location": city, **payload}}


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def make_data(tmp_path):
    data = tmp_path / "data"
    raw = data / "generic_a" / "raw"
    write(raw / "2026-10-20" / "1_v1.json", envelope("generic_a", "1", "Python Developer", "Cty A", "Hà Nội", "2026-10-20T06:00:00+00:00"))
    write(raw / "2026-11-01" / "1_v2.json", envelope("generic_a", "1", "Senior Python Developer", "Cty A", "Hà Nội",
                                                     "2026-11-01T06:00:00+00:00", version=2))
    write(raw / "2026-11-01" / "2_v1.json", envelope("generic_a", "2", "Senior Python Developer", "CÔNG TY A", "Hà Nội",
                                                     "2026-11-01T07:00:00+00:00"))
    write(raw / "2026-11-01" / "3_v1.json", envelope("generic_a", "3", "Senior Python Developer", "Cty A", "Đà Nẵng",
                                                     "2026-11-01T08:00:00+00:00"))
    write(raw / "2026-10-16" / "raw_batch.json", [envelope("generic_a", "9", "Tester", "B", "HCM", "2026-10-16T06:00:00+00:00")])
    write(data / "generic_b" / "raw" / "2026-11-01" / "7_v1.json",
          envelope("generic_b", "7", "Kế toán", "Cty C", "Hà Nội", "2026-11-01T06:00:00+00:00"))
    return data


def test_latest_snapshot_and_batch_skipped(tmp_path):
    envs, files = rdi.latest_envelopes(make_data(tmp_path) / "generic_a" / "raw")
    by_id = {e["metadata"]["job_id"]: e for e in envs}
    assert sorted(by_id) == ["1", "2", "3"]  # tin 9 chỉ có trong file batch
    assert by_id["1"]["metadata"]["version"] == 2
    assert files["file_batch"] == 1 and files["tin_trong_batch"] == 1 and files["snapshot_v_lớn_hơn_1"] == 1


def test_field_matrix_drops_fields_below_min_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(rdi, "MIN_SOURCES_TO_KEEP", 2)
    stats = rdi.compute(make_data(tmp_path), sources=("generic_a", "generic_b"))
    matrix = {m["field"]: m for m in stats["field_matrix"]}
    assert matrix["job_title"]["keep"] and matrix["job_title"]["sources"] == 2
    assert not matrix["raw_gender_text"]["keep"] and matrix["raw_gender_text"]["sources"] == 0


def test_dedup_funnel_adds_city_and_week(tmp_path):
    dedup = rdi.compute(make_data(tmp_path), sources=("generic_a", "generic_b"))["dedup"]
    # Tin 1 (v2), 2, 3 cùng tiêu đề + công ty ("Cty A" = "CÔNG TY A"); tin 3 khác thành phố
    assert [d["extra_jobs"] for d in dedup] == [2, 1, 1]
    assert dedup[0]["groups_same_source"] == 1 and dedup[0]["groups_cross_source"] == 0


def test_html_has_every_section(tmp_path):
    page = rdi.render_html(rdi.compute(make_data(tmp_path), sources=("generic_a", "generic_b")))
    for heading in ("A. Phạm vi", "B. Trùng lặp", "C. Độ phủ", "D. Lương", "E. Địa điểm", "F. Kinh nghiệm",
                    "G. Kỹ năng", "H. Ngày tháng", "I. Văn bản"):
        assert heading in page
    assert page.startswith("<!doctype html>") and "http" not in page.split("<body>")[0]  # không tải gì từ mạng
