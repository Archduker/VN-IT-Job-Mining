"""Bước 01 Clean (docs/preprocessing/spec/P1_clean.md): C1–C7, chính sách IT, tra tỉnh, JEV có cache."""

import csv
import json

import pytest

from preprocessing.clean import run as clean
from preprocessing.common import province, step_report
from preprocessing.common.api_cache import ApiCache
from preprocessing.common.it_filter import classify
from preprocessing.common.jev_client import JevClient

JD = " ".join(["Phát triển hệ thống backend bằng Python và Django cho khách hàng."] * 5)


def env(src, job_id, title, company="Cty A", city="Hà Nội", scraped="2026-11-01T06:00:00+00:00", version=1, jd=JD,
        url=True):
    meta = {"job_id": job_id, "source": src, "scraped_at": scraped, "version": version}
    if url:
        meta["source_url"] = f"https://x/{src}/{job_id}"
    return {"metadata": meta,
            "raw_payload": {"title": title, "company": company, "location": city, "description": jd}}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(clean, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(clean, "OUT_DIR", tmp_path / "data" / "preprocessing" / "01_clean")
    monkeypatch.setattr(clean, "REVIEW_DIR", tmp_path / "data" / "preprocessing" / "review")
    monkeypatch.setattr(clean, "POLICY_PATH", tmp_path / "it_policy.json")
    monkeypatch.setattr(step_report, "REPORTS_ROOT", tmp_path / "reports")
    monkeypatch.setattr("preprocessing.common.api_cache.CACHE_ROOT", tmp_path / "cache")
    raw_a = tmp_path / "data" / "src_a" / "raw"
    write(raw_a / "2026-10-20" / "1_v1.json", env("src_a", "1", "Backend Developer", scraped="2026-10-20T06:00:00+00:00"))
    write(raw_a / "2026-11-01" / "1_v2.json", env("src_a", "1", "Senior Backend Developer", version=2))
    write(raw_a / "2026-11-01" / "2_v1.json", env("src_a", "2", "Kế toán trưởng"))
    write(raw_a / "2026-11-01" / "3_v1.json", env("src_a", "3", "Python Dev", jd="Liên hệ để biết thêm"))
    write(raw_a / "2026-11-01" / "4_v1.json", env("src_a", "4", "Senior Backend Developer", company="CÔNG TY A",
                                                  scraped="2026-11-01T05:00:00+00:00"))
    write(raw_a / "2026-11-01" / "job-mot-100_v1.json", env("src_a", "job-mot-100", "Tester"))
    write(raw_a / "2026-10-16" / "batch.json", [env("src_a", "2", "Kế toán trưởng"), env("src_a", "9", "QA Engineer")])
    write(tmp_path / "data" / "src_b" / "raw" / "2026-11-01" / "7_v1.json",
          env("src_b", "7", "Senior Backend Developer", city="Ha Noi"))
    return tmp_path


def rows(report, rule_id):
    return next(r["rows_affected"] for r in report.data["rules"] if r["id"] == rule_id)


def test_rules_c1_to_c7_and_conservation(sandbox):
    reports = clean.run(["src_a", "src_b"], dry_run=False)
    a = reports["src_a"]
    assert a.data["input"]["rows"] == 8  # 6 snapshot + 2 tin batch
    assert rows(a, "C1") == 1 and rows(a, "C2") == 1 and rows(a, "C3") == 1
    assert rows(a, "C4c") == 0  # chưa có it_policy.json: không bỏ tin ngoài IT
    assert rows(a, "C5") == 1  # tin 3 JD ngắn
    assert rows(a, "C6") == 1  # tin 4 "CÔNG TY A" trùng tin 1 "Cty A", tin 1 cào sau nên được giữ
    kept_a = [json.loads(x) for x in (sandbox / "data/preprocessing/01_clean/src_a.jsonl").read_text().splitlines()]
    kept_b = (sandbox / "data/preprocessing/01_clean/src_b.jsonl").read_text().splitlines()
    assert rows(reports["src_a"], "C7") + rows(reports["src_b"], "C7") == 1  # "Hà Nội" = "Ha Noi"
    assert len(kept_a) == 3 and kept_b == []  # giữ 1 (v2), 2, 9 (chỉ có trong batch); tin 7 trùng tin 1
    survivor = next(e for e in kept_a if e["metadata"]["job_id"] == "1")
    assert survivor["raw_payload"]["title"] == "Senior Backend Developer"  # bản v2
    assert survivor["metadata"]["clean"]["also_on"] == ["src_b:7"]
    for r in reports.values():
        assert r.data["checks"]["rows_conserved"] is True
    assert (sandbox / "reports/01_clean/_all.json").exists()


def test_policy_drops_only_approved_status(sandbox):
    (sandbox / "it_policy.json").write_text(json.dumps({"src_a": {"drop": ["non_it", "can_kiem"]}}), encoding="utf-8")
    reports = clean.run(["src_a"], dry_run=True)
    assert rows(reports["src_a"], "C4c") == 1  # chỉ "Kế toán trưởng"; can_kiem không bao giờ bị bỏ tự động


def test_review_file_kept_once_labeled(sandbox):
    clean.run(["src_a"], dry_run=True)
    path = sandbox / "data/preprocessing/review/it_src_a.csv"
    with path.open(encoding="utf-8-sig", newline="") as fh:
        data = list(csv.DictReader(fh))
    data[0]["nhan_tay"] = "non_it"  # dòng non_it: "Kế toán trưởng"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
    text = path.read_text(encoding="utf-8-sig")
    report = clean.run(["src_a"], dry_run=True)["src_a"]
    assert report.data["extra"]["review"]["labeled"] == 1 and report.data["extra"]["review"]["rule_correct"] == 1
    assert path.read_text(encoding="utf-8-sig") == text  # không ghi đè nhãn tay


@pytest.mark.parametrize("title,expected", [
    ("Kế toán trưởng", "non_it"), ("Backend Developer", "it"), ("International Sales Manager", "non_it"),
    ("Kinh doanh phần mềm", "unknown"), ("Ít nhất 2 năm kinh nghiệm", "unknown"), ("ASP.NET Developer", "it"),
])
def test_it_rule_whole_words(title, expected):
    assert classify(title) == expected


@pytest.mark.parametrize("title,skills,expected", [
    ("Chuyên Gia Định Phí", ["SQL", "VBA"], "unknown"),  # một kỹ năng công nghệ chưa đủ
    ("Kỹ sư", ["Java", "Spring"], "it"),
    ("Security (Nhân Viên Bảo An)", [], "non_it"),
    ("Thực Tập Sinh Kỹ Thuật (Mảng Bảo Trì)", [], "unknown"),  # "kỹ thuật" một mình không đủ
    ("Chuyên Viên Phân Tích Nghiệp Vụ (Kênh ngân hàng số)", [], "it"),  # BA; "ngân hàng" không còn là từ ngoài IT
    ("Chuyên Gia phát triển Hệ thống ngân hàng lõi - K.CNTT", [], "it"),  # "K.CNTT": từ đứng sau dấu chấm
    ("Kế toán trưởng (Hệ thống thông tin kế toán)", [], "unknown"),  # có cả từ IT lẫn ngoài IT
])
def test_it_rule_needs_real_evidence(title, skills, expected):
    assert classify(title, skills) == expected


def test_combine():
    assert clean.combine("it", 0.95) == "it"
    assert clean.combine("it", 0.2) == "can_kiem"
    assert clean.combine("unknown", 0.1) == "non_it"
    assert clean.combine("non_it", None) == "non_it" and clean.combine("unknown", None) == "can_kiem"


def test_province_34():
    assert province.key("TP.HCM") == province.key("Bình Dương") == province.key("Ho Chi Minh") == "ho_chi_minh"
    assert province.key("Quảng Nam") == "da_nang" and province.key("Hà Giang") == "tuyen_quang"
    assert province.key("Tòa nhà MB, 18 Lê Văn Lương, Hà Nội") == "ha_noi"
    assert province.key("1 Nguyễn Huệ, Quận 1") is None  # tên đường, không phải TP. Huế
    assert province.is_remote("Remote") and province.is_foreign("Tokyo, Japan")


class FakeSession:
    def __init__(self):
        self.calls = 0

    def post(self, url, **kw):
        self.calls += 1

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"model": "typesafe/jev-1.13-x", "answers": {"is_it_job": {"type": "noul", "noul": 0.9}},
                        "usage": {"cost": 0.00002}}
        return R()


def test_jev_cache_and_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "test")
    session = FakeSession()
    jev = JevClient(True, dry_run=False, cache=ApiCache("jev", root=tmp_path), session=session)
    args = ("is_it_job", "q", "t", "f", {"title": "Dev"})
    assert jev.noul(*args) == 0.9 and jev.noul(*args) == 0.9
    assert session.calls == 1 and jev.report()["cache_hits"] == 1
    broke = JevClient(True, dry_run=False, max_cost_usd=0.0, cache=ApiCache("jev2", root=tmp_path), session=session)
    assert broke.noul(*args) is None and session.calls == 1  # hết trần thì không gọi
    dry = JevClient(True, dry_run=True, cache=ApiCache("jev3", root=tmp_path), session=session)
    assert dry.noul(*args) is None and dry.report()["would_call"] == 1 and session.calls == 1
