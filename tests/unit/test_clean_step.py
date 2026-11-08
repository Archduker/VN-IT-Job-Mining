"""Bước 01 Clean (docs/preprocessing/spec/P1_clean.md): C1–C7, chính sách IT, luật IT 2 tầng, tra tỉnh."""

import csv
import json

import pytest

from preprocessing.clean import label_review
from preprocessing.clean import run as clean
from preprocessing.common import province, step_report
from preprocessing.common.it_filter import classify, classify_unknown

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
    (sandbox / "it_policy.json").write_text(json.dumps({"src_a": {"drop": ["non_it"]}}), encoding="utf-8")
    reports = clean.run(["src_a"], dry_run=True)
    assert rows(reports["src_a"], "C4c") == 1  # chỉ "Kế toán trưởng"


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


def strata(rows):
    """Đếm mẫu theo (tầng, it_status) - thiết kế 3 tầng của C4b."""
    out = {}
    for r in rows:
        k = f"tang_{r['it_rule_level']}_{r['it_status']}"
        out[k] = out.get(k, 0) + 1
    return out


def test_review_sample_includes_level1_it_rows(sandbox):
    """Mẫu phải có tin tầng 1 dự đoán IT, nếu không thì Precision IT >=95% không đo được (Q1)."""
    report = clean.run(["src_a"], dry_run=True)["src_a"]
    path = sandbox / "data/preprocessing/review/it_src_a.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    # "1 Senior Backend Developer", "3 Python Dev", "4 Senior Backend Developer", "9 QA Engineer": 4 tin tầng 1 IT
    # ("4" bị C6 bỏ sau đó nhưng vẫn thuộc tập phân loại mà mẫu C4b cần phủ)
    assert strata(rows) == {"tang_1_non_it": 1, "tang_1_it": 4}
    assert report.data["extra"]["review"]["sample_strata"] == {"tang_1_non_it": 1, "tang_1_it": 4}
    assert report.data["extra"]["review"]["level1_it_labeled"] == 0  # chưa ai gán -> chưa đo được precision
    # mẫu ổn định theo seed: chạy lại không đổi tập tin đã chọn
    ids = [r["job_id"] for r in rows]
    clean.run(["src_a"], dry_run=True)
    again = [r["job_id"] for r in csv.DictReader(path.open(encoding="utf-8-sig"))]
    assert again == ids


def test_level1_it_labeled_feeds_precision(sandbox):
    """Nhãn tay của nhóm tầng 1 IT phải vào ô TP/FP của validation (Precision IT)."""
    clean.run(["src_a"], dry_run=True)
    path = sandbox / "data/preprocessing/review/it_src_a.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    for r in rows:
        if r["it_rule_level"] == "1" and r["it_status"] == "it":
            r["nhan_tay"] = "it" if r["job_id"] == "1" else "non_it"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    rv = clean.run(["src_a"], dry_run=True)["src_a"].data["extra"]["review"]
    assert rv["level1_it_labeled"] == 4 and rv["level1_it_correct"] == 1
    v = rv["validation"]
    assert (v["tp"], v["fp"]) == (1, 3)
    assert v["precision_it"] == pytest.approx(0.25)


@pytest.mark.parametrize("sizes,total,expected", [
    ({"a": 500, "b": 300, "c": 200}, 100, {"a": 50, "b": 30, "c": 20}),
    ({"a": 5, "b": 1000}, 100, {"a": 1, "b": 99}),          # sàn ít tin vẫn có đại diện, không bị lọt
    ({"a": 40, "b": 40}, 100, {"a": 40, "b": 40}),          # tổng nhỏ hơn total -> nhận hết
    ({"a": 0, "b": 10}, 100, {"a": 0, "b": 10}),            # sàn trống không được cấp suất
    ({"a": 7, "b": 3}, 10, {"a": 7, "b": 3}),
])
def test_plan_level1_it_allocation(sizes, total, expected):
    assert clean.plan_level1_it(sizes, total=total) == expected


def test_plan_level1_it_never_over_pool():
    quota = clean.plan_level1_it({"a": 120, "b": 80, "c": 1})
    assert sum(quota.values()) == clean.REVIEW_LEVEL1_IT
    assert quota["a"] <= 120 and quota["b"] <= 80 and quota["c"] <= 1
    assert quota["a"] > quota["b"] > 0  # phân tầng theo sàn: sàn nhiều tin hơn lấy mẫu nhiều hơn


def test_resample_review_writes_nothing_but_samples(sandbox):
    """`--resample-review` chỉ dựng mẫu C4b: không đụng 01_clean, không ghi báo cáo chung (Q6)."""
    info = clean.resample_review(["src_a"])
    assert info["src_a"]["rows"] == 5 and info["src_a"]["strata"] == {"tang_1_non_it": 1, "tang_1_it": 4}
    assert info["src_a"]["quota_tang1_it"] == 4  # chỉ có 4 tin tầng 1 IT -> cấp đúng số có
    assert not (sandbox / "data/preprocessing/01_clean").exists()
    assert not (sandbox / "reports").exists()


def test_resample_cli_respects_source(monkeypatch):
    calls = []
    monkeypatch.setattr(clean, "resample_review", lambda sources, level1_it: (
        calls.append((sources, level1_it)) or {}))
    assert clean.main(["--resample-review", "--source", "glints", "--level1-it", "20"]) == 0
    assert calls == [(["glints"], 20)]


@pytest.mark.parametrize("args", [
    ["--level1-it", "20"], ["--resample-review", "--level1-it", "-1"],
])
def test_invalid_sampling_cli_never_writes(monkeypatch, args):
    def unexpected(*args, **kwargs):
        pytest.fail("invalid arguments must be rejected before any write")
    monkeypatch.setattr(clean, "resample_review", unexpected)
    monkeypatch.setattr(clean, "run", unexpected)
    with pytest.raises(SystemExit) as exc:
        clean.main(args)
    assert exc.value.code == 2


def test_negative_sample_budget_rejected():
    with pytest.raises(ValueError):
        clean.plan_level1_it({"glints": 100}, total=-1)


@pytest.mark.parametrize("n_sai,ket_luan", [
    (0, "cận dưới mẫu >= 95%"),
    (1, "cận dưới mẫu < 95%"),
])
def test_status_ket_luan_precision_bang_can_duoi(tmp_path, monkeypatch, capsys, n_sai, ket_luan):
    """KTC tham khảo không được biến thành kết luận nghiệm thu toàn bộ."""
    review = tmp_path / "review"
    review.mkdir()
    rows = [{"job_id": str(i), "source_url": f"https://x/src_a/{i}", "job_title": "Backend Developer",
             "skills": "Python, Docker", "it_rule": "it", "it_rule_level": "1", "it_status": "it",
             "nhan_tay": "non_it" if i < n_sai else "it"} for i in range(100)]
    with (review / "it_src_a.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    monkeypatch.setattr(label_review, "REVIEW_DIR", review)
    monkeypatch.setattr(label_review, "SOURCES", ("src_a",))
    assert label_review.main(["--source", "src_a", "--status"]) == 0
    out = capsys.readouterr().out
    assert f"precision_it: {(100 - n_sai) / 100:.1%}" in out
    assert "KTC 95%" in out and f"{ket_luan}" in out
    assert "Chưa kết luận nghiệm thu toàn bộ" in out
    assert "ĐẠT ngưỡng" not in out
    # đếm "đã nhãn" theo dòng có trả lời (kể cả đáp án trái bộ lọc), không theo đáp án đúng
    assert "Tầng 1 dự đoán IT (nhóm bắt buộc để đo Precision IT): 100/100 dòng đã nhãn" in out


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


@pytest.mark.parametrize("title,jd,expected", [
    ("Nhân viên kinh doanh", "Tư vấn khách hàng, chăm sóc đại lý, báo cáo doanh số hằng tháng.", "non_it"),
    ("Project Manager", "Làm việc với team Java, React, SQL trên AWS để ra mắt sản phẩm.", "it"),  # nhóm PM + 4 kỹ năng
    ("Project Manager", "Làm việc với khách hàng.", "non_it"),  # có nhóm nghề nhưng JD không đủ 2 kỹ năng
])
def test_level2_needs_family_and_jd_skills(title, jd, expected):
    assert classify_unknown(title, None, jd) == expected


def test_province_34():
    assert province.key("TP.HCM") == province.key("Bình Dương") == province.key("Ho Chi Minh") == "ho_chi_minh"
    assert province.key("Quảng Nam") == "da_nang" and province.key("Hà Giang") == "tuyen_quang"
    assert province.key("Tòa nhà MB, 18 Lê Văn Lương, Hà Nội") == "ha_noi"
    assert province.key("1 Nguyễn Huệ, Quận 1") is None  # tên đường, không phải TP. Huế
    assert province.is_remote("Remote") and province.is_foreign("Tokyo, Japan")
