"""tests/unit/test_careerviet_eda_charts.py — Kiểm thử `scripts/careerviet_eda_charts.py`.

Ba nhóm rủi ro được khóa ở đây:

1. Cấu trúc dữ liệu: độ dài JD phải đo từ `detail-row` (dict {heading: text} = JD
   thật), KHÔNG đo từ `detail-box` (List[str] = hộp metadata Lương/Kinh nghiệm).
   Tin rỗng `Ngành nghề` phải tách thành nhóm "không phân loại được", không gộp
   vào ngoài IT.
2. Số liệu thật không được rò rỉ vào test (chỉ dùng dữ liệu giả trong tmp_path).
3. Hiển thị: tiêu đề/phụ đề dài phải tự thu nhỏ hoặc xuống dòng, không bị cắt nét.

An toàn: tmp_path + dữ liệu giả, CHỈ đọc, không gọi mạng, không MinIO.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import pytest  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import careerviet_eda_charts as ec  # noqa: E402

MO_TA = "Mô tả Công việc"
YEU_CAU = "Yêu Cầu Công Việc"
PHUC_LOI = "Phúc lợi"

ALL_FILES = [
    "01_bucket_supply.png", "02_it_share_donut.png", "03_it_ratio_bucket.png",
    "04_null_rate.png", "05_salary_hist.png", "06_salary_box_it_vs_non.png",
    "07_locations.png", "08_location_group_heatmap.png", "09_tags_all_top.png",
    "10_tags_it_only_top.png", "11_companies_top.png", "12_benefits_top.png",
    "13_date_posted.png", "14_employment_type.png", "15_jd_length_groups.png",
    "16_ledger_cdc.png",
]


# ============================================================ định dạng số VN
def test_fmt_int_uses_dot_thousands_separator():
    assert ec.fmt_int(1018) == "1.018"
    assert ec.fmt_int(24) == "24"


def test_fmt_num_and_pct_use_comma_decimal():
    assert ec.fmt_num(17.5) == "17,5"
    assert ec.pct(591, 1018) == "58,1%"


def test_pct_of_zero_base_is_na_not_zero():
    """Mẫu bằng 0 không được suy ra 0,0% - phải trả 'n/a' để không bịa số."""
    assert ec.pct(3, 0) == "n/a"


# ============================================================ group_of
def test_group_of_it_requires_it_industry():
    assert ec.group_of({"Ngành nghề": ["CNTT - Phần mềm"]}) == "it"
    assert ec.group_of({"Ngành nghề": ["Viễn thông / CNTT"]}) == "it"


def test_group_of_empty_industry_is_unclassified_not_nonit():
    """24 tin tối giản PHẢI là nhóm riêng - gộp vào non-IT sẽ làm sai tỷ lệ IT."""
    assert ec.group_of({"Ngành nghề": []}) == "unclassified"
    assert ec.group_of({}) == "unclassified"
    assert ec.group_of({"Ngành nghề": None}) == "unclassified"


def test_group_of_other_industry_is_nonit():
    assert ec.group_of({"Ngành nghề": ["Marketing - PR"]}) == "nonit"


# ============================================================ bucket_of
def test_bucket_of_strips_suffix_and_keeps_keyword_prefix():
    assert ec.bucket_of("c1") == "c1"
    assert ec.bucket_of("c37_digital_mkt") == "c37"
    assert ec.bucket_of("keyword:developer") == "keyword:developer"
    assert ec.bucket_of("c61_it_vn") == "c61"


def test_bucket_of_missing_value_falls_back():
    assert ec.bucket_of(None) == "khác"
    assert ec.bucket_of("   ") == "khác"
    assert ec.bucket_of("Khoa học - Công trình") == "Khoa học - Công trình"


# ============================================================ box_fields
def test_box_fields_splits_by_leading_label():
    box = ["Lương Lương: 20 - 30 Triệu VND", "Kinh nghiệm 2 Năm",
           "Hình thức Nhân viên chính thức", "Ngày cập nhật 16/10/2026"]
    out = ec.box_fields(box)
    # nhãn lặp cả trong giá trị ("Lương Lương: ...") phải còn đúng một lần "Lương:"
    assert out["Lương"] == ["20 - 30 Triệu VND"]
    assert out["Kinh nghiệm"] == ["2 Năm"]
    assert out["Hình thức"] == ["Nhân viên chính thức"]
    assert out["Cấp bậc"] == []


def test_box_fields_deduplicates_nothing_keeps_both_occurrences():
    """Desktop + mobile lặp cùng nhãn -> giữ 2 giá trị để caller tự dedupe."""
    out = ec.box_fields(["Kinh nghiệm Không yêu cầu", "Kinh nghiệm Không yêu cầu"])
    assert out["Kinh nghiệm"] == ["Không yêu cầu", "Không yêu cầu"]


def test_box_fields_non_list_and_empty():
    assert set(ec.box_fields(None)) == set(ec.BOX_LABELS)
    assert ec.box_fields(None)["Lương"] == []


# ============================================================ split_multi / benefits
def test_split_multi_splits_on_comma_and_ignores_blanks():
    assert ec.split_multi("Nhân viên chính thức , Thực tập") == ["Nhân viên chính thức", "Thực tập"]
    assert ec.split_multi("") == []
    assert ec.split_multi(None) == []


def test_split_benefits_from_comma_string():
    assert ec.split_benefits("Đào tạo, Chế độ bảo hiểm,Laptop") == ["Đào tạo", "Chế độ bảo hiểm", "Laptop"]


def test_split_benefits_from_list_and_empty():
    assert ec.split_benefits(["Đào tạo", " Laptop "]) == ["Đào tạo", "Laptop"]
    assert ec.split_benefits("") == []
    assert ec.split_benefits(None) == []


# ============================================================ lương
def test_salary_month_m_average_of_range():
    schema = {"baseSalary": {"currency": "VND",
                             "value": {"minValue": 20000000, "maxValue": 30000000,
                                       "unitText": "MONTH"}}}
    assert ec.salary_month_m(schema) == 25.0


def test_salary_month_m_single_value_and_missing_unit():
    schema = {"baseSalary": {"currency": "VND", "value": {"value": 18000000}}}
    assert ec.salary_month_m(schema) == 18.0


@pytest.mark.parametrize("schema", [
    {},                                                  # không có baseSalary
    {"baseSalary": "Cạnh tranh"},                        # không phải dict
    {"baseSalary": {"currency": "USD",
                    "value": {"minValue": 1000, "maxValue": 2000}}},   # ngoài VND
    {"baseSalary": {"currency": "VND",
                    "value": {"minValue": 500000, "maxValue": 900000,
                              "unitText": "YEAR"}}},                   # không phải tháng
    {"baseSalary": {"currency": "VND", "value": {"minValue": 0, "maxValue": 0}}},
])
def test_salary_month_m_returns_none_when_unsafe(schema):
    """Không suy đoán: ngoài VND / không phải MONTH / bằng 0 -> loại khỏi phép đo."""
    assert ec.salary_month_m(schema) is None


# ============================================================ qstats
def test_qstats_quartiles_need_four_points():
    d = ec.qstats([1, 2, 3, 4, 5])
    assert (d["n"], d["min"], d["med"], d["max"]) == (5, 1, 3, 5)
    assert d["q1"] is not None and d["q3"] is not None
    short = ec.qstats([7, 9])
    assert short["q1"] is None and short["q3"] is None


# ============================================================ pick_section
def test_pick_section_finds_by_substring_case_insensitive():
    """pick_section trả text ĐÃ FLATTEN (đã cắt whitespace đầu/cuối) vì độ dài JD đo trên text đó."""
    row = {MO_TA: "  JD noi dung  ", YEU_CAU: "req text"}
    assert ec.pick_section(row, "mô tả") == "JD noi dung"
    assert ec.pick_section(row, "yêu cầu") == "req text"


def test_pick_section_missing_key_returns_empty():
    assert ec.pick_section({PHUC_LOI: "x"}, "mô tả") == ""
    assert ec.pick_section({}, "mô tả") == ""


@pytest.mark.parametrize("bad", [None, [], "chuoi", 0])
def test_pick_section_non_dict_returns_empty(bad):
    assert ec.pick_section(bad, "mô tả") == ""


def test_pick_section_flattens_list_value():
    row = {MO_TA: ["dong 1", "dong 2"]}
    assert ec.pick_section(row, "mô tả") == "dong 1 dong 2"


# ============================================================ source_caption
def test_source_caption_merges_utc_and_vietnam_day():
    """Run 17:17 UTC -> 16/10 (UTC) và 17/10 (VN) phải gộp thành '16-17/10/2026'."""
    ts = ["2026-10-16T17:17:43.627971+00:00", "2026-10-16T18:02:00+00:00"]
    assert ec.source_caption(1018, ts) == "Nguồn: 1.018 envelope CareerViet, thu thập 16-17/10/2026"


def test_source_caption_single_day_and_no_timestamp():
    assert ec.source_caption(5, ["2026-10-10T02:00:00+00:00"]).endswith("10/10/2026")
    assert ec.source_caption(5, []) == "Nguồn: 5 envelope CareerViet"


# ============================================================ iter_envelopes
def _write_env(root: Path, jid: str, payload: dict, ver: int = 1, *,
               bucket: str = "c1", scraped: str = "2026-10-16T17:17:43.627971+00:00",
               day: str = "2026-10-16") -> Path:
    d = root / day
    d.mkdir(parents=True, exist_ok=True)
    env = {
        "metadata": {
            "job_id": jid,
            "source": "careerviet",
            "source_url": f"https://careerviet.vn/vi/tim-viec-lam/x.{jid}.html",
            "scraped_at": scraped,
            "scraper_version": "1.0.0-raw-envelope",
            "version": ver,
            "content_hash": f"{jid}-hash",
            "source_category": bucket,
        },
        "raw_payload": payload,
    }
    p = d / f"{jid}_v{ver}.json"
    p.write_text(json.dumps(env, ensure_ascii=False), encoding="utf-8")
    return p


def test_iter_envelopes_keeps_only_highest_version_per_job(tmp_path):
    _write_env(tmp_path, "A1", {"title": "ban cu"}, ver=1)
    _write_env(tmp_path, "A1", {"title": "ban moi"}, ver=3)
    _write_env(tmp_path, "A1", {"title": "ban giua"}, ver=2)
    envs = ec.iter_envelopes(tmp_path)
    assert len(envs) == 1
    assert envs[0]["raw_payload"]["title"] == "ban moi"


def test_iter_envelopes_accepts_bare_and_dt_prefixed_dirs(tmp_path):
    _write_env(tmp_path, "A1", {}, day="2026-10-16")
    _write_env(tmp_path, "A2", {}, day="dt=2026-10-17")
    assert len(ec.iter_envelopes(tmp_path)) == 2
    assert len(ec.iter_envelopes(tmp_path, "2026-10-16")) == 1


def test_iter_envelopes_ignores_other_folders_and_bad_json(tmp_path):
    junk = tmp_path / "not-a-date"
    junk.mkdir()
    (junk / "x.json").write_text("{}", encoding="utf-8")
    broken = tmp_path / "2026-10-16"
    broken.mkdir()
    (broken / "bad_v1.json").write_text("{khong phai json", encoding="utf-8")
    assert ec.iter_envelopes(tmp_path) == []


# ============================================================ read_ledger
def _write_ledger(led: Path, records: dict, manifest: list[dict] | None = None) -> None:
    led.mkdir(parents=True, exist_ok=True)
    (led / "catalog_master.json").write_text(json.dumps(records, ensure_ascii=False),
                                             encoding="utf-8")
    if manifest is not None:
        mp = led / "manifests"
        mp.mkdir(exist_ok=True)
        (mp / "manifest_2026-10-16.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in manifest), encoding="utf-8")


def test_read_ledger_counts_status_repost_version_errors(tmp_path):
    led = tmp_path / "ledger"
    _write_ledger(led, {
        "h1": {"source": "careerviet", "status": "DONE", "latest_version": 1, "job_id": "A1"},
        "h2": {"source": "careerviet", "status": "DONE", "latest_version": 1, "job_id": "A2"},
        "h3": {"source": "careerviet", "status": "DONE", "latest_version": 0, "job_id": None,
               "repost_of_url_hash": "h1"},
        "h4": {"source": "careerviet", "status": "PENDING", "latest_version": 0,
               "error_log": "404"},
        "h5": {"source": "glints", "status": "DONE", "latest_version": 9, "job_id": "G1"},
    })
    out = ec.read_ledger(led, "careerviet")
    assert sum(out["statuses"].values()) == 4          # không lẫn nguồn khác
    assert out["repost"] == 1
    assert out["with_version"] == 2
    assert out["errors"] == 1


def test_read_ledger_manifest_is_discovery_snapshot_only(tmp_path):
    """Manifest vẫn ghi PENDING/latest_version=0 -> chỉ dùng để đếm URL được phát hiện."""
    led = tmp_path / "ledger"
    _write_ledger(led, {}, [
        {"source": "careerviet", "canonical_url": "https://careerviet.vn/a.html",
         "status": "PENDING", "latest_version": 0},
        {"source": "careerviet", "canonical_url": "https://www.careerviet.vn/a.html",
         "status": "PENDING", "latest_version": 0},     # trùng sau strip_prefix
        {"source": "careerviet", "canonical_url": "https://careerviet.vn/b.html",
         "status": "PENDING", "latest_version": 0},
        {"source": "glints", "canonical_url": "https://glints.com/c", "status": "PENDING"},
    ])
    out = ec.read_ledger(led, "careerviet")
    assert out["manifest_urls"] == 2
    assert sum(out["statuses"].values()) == 0


def test_read_ledger_missing_dir_is_empty(tmp_path):
    out = ec.read_ledger(tmp_path / "khong-ton-tai", "careerviet")
    assert out["records"] == [] and out["manifest_urls"] == 0


# ============================================================ flat_text
def test_flat_text_strips_tags_and_collapses_whitespace():
    """Tag bị loại mà KHÔNG chèn space (hành vi đã ghi trong docstring `flat_text`):
    chỉ whitespace trong cùng một text node mới được gộp. Khóa lại để không đổi
    âm thầm khi sửa parser.
    """
    assert ec.flat_text("<p>a\n  b</p>") == "a b"
    assert ec.flat_text("<p>a</p><p>b</p>") == "ab"
    assert ec.flat_text(None) == ""
    assert ec.flat_text(["<b>x</b>", "y"]) == "x y"


def test_flat_text_keeps_bare_ampersand():
    """Regression: 'Nhân viên C&B' từng trả về '' vì HTMLParser chờ entity đóng.

    Lỗi này biến 3 tin có `title` và 5 tin có `job-company-name` thành 'rỗng'
    trong biểu đồ 04, và làm thất lạc tên công ty có dấu '&' trong biểu đồ 11.
    """
    assert ec.flat_text("Nhân viên C&B") == "Nhân viên C&B"
    assert ec.flat_text("Công ty D&C") == "Công ty D&C"
    assert ec.flat_text("A &amp; B") == "A & B"
    assert ec.flat_text("<b>N&D</b> &amp; more") == "N&D & more"


# ============================================================ chuan hoa chu trong hinh
def plt_close(fig):
    import matplotlib.pyplot as plt

    plt.close(fig)


def test_fit_text_keeps_short_text_at_max_size():
    ec.use_default_style()
    fig, ax = ec.new_fig(figsize=(9.2, 4.6))
    fig.canvas.draw()
    text, size = ec._fit_text(fig, fig.canvas.get_renderer(), "Tiêu đề ngắn", 4000,
                              (13.5, 12.0, 11.0, 10.0), "bold")
    assert text == "Tiêu đề ngắn" and size == 13.5
    plt_close(fig)


def test_fit_text_shrinks_then_wraps_long_text():
    """Text dài hơn chỗ còn lại phải nhỏ dần, hết cỡ vẫn dài thì xuống dòng."""
    ec.use_default_style()
    fig, ax = ec.new_fig(figsize=(9.2, 4.6))
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    long_text = "Trống nhiều nhất: Lương quy đổi được (VND/tháng) - 57,0% tin (580/1.018)"

    shrunk, size = ec._fit_text(fig, renderer, long_text, 650, (13.5, 12.0, 11.0, 10.0), "bold")
    assert size < 13.5 and "\n" not in shrunk
    assert ec._text_width_px(fig, renderer, shrunk, size, "bold") <= 650

    wrapped, size = ec._fit_text(fig, renderer, long_text, 300, (13.5, 12.0, 11.0, 10.0), "bold")
    assert "\n" in wrapped
    for line in wrapped.split("\n"):
        assert ec._text_width_px(fig, renderer, line, size, "bold") <= 300 * 1.35
    plt_close(fig)


def test_decorate_wraps_oversize_title():
    """Loi luot truoc: title dai van bi cat vi do nham artist. decorate() phai xuong dong."""
    ec.use_default_style()
    fig, ax = ec.new_fig()                       # 9.2 x 4.8 = kich thuoc that cua bieu do
    long_title = "Trống nhiều nhất: " + "Lương quy đổi được (VND/tháng) - 57,0% tin " * 3
    ec.decorate(fig, ax, long_title, "n = 44 envelope", "Nguồn: test", grid="y")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    left = ax._left_title                        # loc="left" -> ax.title la tieu de GIUA (rong)
    room = ec._room_px(fig, ax)
    assert "\n" in left.get_text()
    for line in left.get_text().split("\n"):
        assert ec._text_width_px(fig, renderer, line, left.get_fontsize(), "bold") <= room + 2
    plt_close(fig)


def test_room_px_subtracts_colorbar():
    """Heatmap co colorbar: cho trong ben phai phai tru be ngang colorbar."""
    import numpy as np

    ec.use_default_style()
    fig, ax = ec.new_fig(figsize=(9.6, 4.6))
    im = ax.imshow(np.arange(9).reshape(3, 3), cmap="Blues")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    room_plain = ec._room_px(fig, ax)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    assert ec._room_px(fig, ax) < room_plain - 20
    plt_close(fig)


def _audit_save(problems: list):
    """Boc `ec.save`: kiem tra chu bi cat o bien figure va nhan de len colorbar.

    Khong do doi chieu tick label bang `get_xticklabels()`: matplotlib tra ve ca
    tick nam NGOAI view interval (nhau '120' voi xlim(0, 116)) - artist van co
    bbox but khong bao giờ được vẽ nên phép đo sinh báo động giả. Chữ bị cắt thật
    được phát hiện bằng `fig.get_tightbbox()` (đã lọc theo view interval), còn
    từng artist do script tự đặt (tieu de, phụ đề, nhãn trục, ghi chu) thi do
    truc tiep.
    """
    real_save = ec.save

    def patched(fig, path):
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        fw, fh = fig.bbox.width, fig.bbox.height
        aux = [a for a in fig.axes[1:]]
        name = Path(path).name
        tb = fig.get_tightbbox(renderer)
        if tb is not None and (tb.x0 < -1 or tb.x1 > fw + 1 or tb.y0 < -1 or tb.y1 > fh + 1):
            problems.append(f"{name}: nội dung bị cắt ở biên figure "
                            f"(x {tb.x0:.0f}-{tb.x1:.0f}/{fw:.0f}, "
                            f"y {tb.y0:.0f}-{tb.y1:.0f}/{fh:.0f})")
        for ax in fig.axes:
            top = ax.get_window_extent().y1
            # `ax.title` vô nghĩa khi loc="left" (là tiêu đề GIỮA rỗng) -> đọc cả
            # `ax._left_title` để bắt đúng chữ hiển thị.
            cands = [ax.title, ax._left_title, ax.xaxis.label, ax.yaxis.label] + list(ax.texts)
            for t in cands:
                s = t.get_text() if hasattr(t, "get_text") else ""
                if not s:
                    continue
                bb = t.get_window_extent(renderer)
                if bb.x0 < -1 or bb.x1 > fw + 1 or bb.y0 < -1 or bb.y1 > fh + 1:
                    problems.append(f"{name}: '{s[:32]}' tràn khỏi figure "
                                    f"(x {bb.x0:.0f}-{bb.x1:.0f}/{fw:.0f})")
                if bb.y0 >= top - 1 and aux:
                    limit = min(a.get_window_extent().x0 for a in aux
                                if a.get_window_extent().x0 > ax.get_window_extent().x0 + 1)
                    if bb.x1 > limit + 1:
                        problems.append(f"{name}: '{s[:32]}' đè lên axes phụ (colorbar)")
        return real_save(fig, path)

    return patched


def test_no_text_overflows_or_collides_in_any_figure(tmp_path, monkeypatch):
    """Ca 16 bieu do tren mau gia dinh: khong duoc con chu bi cat / de colorbar."""
    raw, led = tmp_path / "raw", tmp_path / "ledger"
    _write_ledger(led, {
        f"h{i}": {"source": "careerviet", "status": "DONE", "latest_version": 1,
                  "job_id": f"C1_{i:02d}"} for i in range(22)
    })
    spec = [(f"C1_{i:02d}", "c1", True, _payload(i, it=True)) for i in range(22)]
    spec += [(f"C37_{i:02d}", "c37_digital_mkt", False, _payload(i, it=False)) for i in range(22)]
    _corpus(raw, spec)
    problems: list[str] = []
    monkeypatch.setattr(ec, "save", _audit_save(problems))
    code = ec.main(["--raw", str(raw), "--ledger", str(led),
                    "--fig-dir", str(tmp_path / "figs"), "--md-out", str(tmp_path / "out.md")])
    assert code == 0
    assert problems == []


# ============================================================ du lieu gia dinh (e2e)
def _payload(i: int, *, it: bool, desc: str | None = "M" * 1200, box: bool = True,
             benefits: str = "Đào tạo, Chế độ bảo hiểm, Laptop") -> dict:
    row: dict[str, str] = {YEU_CAU: "Yeu cau chung " * 10, PHUC_LOI: "Phuc loi chung " * 5}
    if desc is not None:
        row[MO_TA] = desc
    schema = {
        "datePosted": f"2026-10-{(i % 20) + 1:02d}",
        "employmentType": "FULL_TIME",
        "description": "<p>" + "x" * 1500 + "</p>",
        "jobBenefits": benefits,
    }
    if i % 2 == 0:
        schema["baseSalary"] = {
            "currency": "VND",
            "value": {"minValue": 15000000 + i * 100000,
                      "maxValue": 30000000 + i * 100000, "unitText": "MONTH"},
        }
    return {
        "title": f"Engineer {i}" if it else f"Marketing {i}",
        "job-company-name": f"Công ty {i % 7}",
        "detail-box": ([
            f"Lương Lương: {15 + i} - {25 + i} Triệu VND", "Kinh nghiệm 2 Năm",
            "Cấp bậc Nhân viên", "Hình thức Nhân viên chính thức",
            "Ngày cập nhật 16/10/2026", "Hết hạn nộp 30/10/2026",
        ] if box else []),
        "detail-row": row,
        "job-tags": (["IT Engineer", "python"] if it else ["Marketer"]),
        "map": ["Hà Nội", "Hồ Chí Minh", "Đà Nẵng"][i % 3],
        "Ngành nghề": ["CNTT - Phần mềm"] if it else ["Marketing - PR"],
        "job-posting-schema": schema,
    }


def _corpus(raw: Path, spec) -> None:
    for jid, bucket, it, payload in spec:
        _write_env(raw, jid, payload, bucket=bucket)


@pytest.fixture(scope="module")
def rich_run(tmp_path_factory):
    """44 tin / 2 bucket (>= 20 mỗi bucket) -> đủ điều kiện vẽ cả 16 biểu đồ."""
    tmp = tmp_path_factory.mktemp("cveda")
    raw, led = tmp / "raw", tmp / "ledger"
    _write_ledger(led, {
        f"h{i}": {"source": "careerviet", "status": "DONE", "latest_version": 1,
                  "job_id": f"C1_{i:02d}"} for i in range(22)
    } | {
        f"r{i}": {"source": "careerviet", "status": "DONE", "latest_version": 0,
                  "job_id": None, "repost_of_url_hash": "h1"} for i in range(3)
    })
    spec = [(f"C1_{i:02d}", "c1", True, _payload(i, it=True)) for i in range(22)]
    spec += [(f"C37_{i:02d}", "c37_digital_mkt", False, _payload(i, it=False)) for i in range(22)]
    _corpus(raw, spec)
    fig, md = tmp / "figs", tmp / "out.md"
    code = ec.main(["--raw", str(raw), "--ledger", str(led),
                    "--fig-dir", str(fig), "--md-out", str(md)])
    assert code == 0
    return raw, led, fig, md, md.read_text(encoding="utf-8")


def _run_on(tmp_path, spec, ledger_records=None):
    raw, led = tmp_path / "raw", tmp_path / "ledger"
    _write_ledger(led, ledger_records or {})
    _corpus(raw, spec)
    fig, md = tmp_path / "figs", tmp_path / "out.md"
    code = ec.main(["--raw", str(raw), "--ledger", str(led),
                    "--fig-dir", str(fig), "--md-out", str(md)])
    assert code == 0
    return fig, md.read_text(encoding="utf-8")


# ============================================================ e2e: bo bieu do
def test_main_draws_all_16_figures(rich_run):
    raw, led, fig, md, text = rich_run
    for name in ALL_FILES:
        assert (fig / name).exists(), name
    assert len(list(fig.glob("*.png"))) == 16


def test_md_has_three_part_insight_for_every_chart(rich_run):
    _raw, _led, _fig, _md, text = rich_run
    assert text.count("## ") == 16
    assert text.count("- **Quan sát:**") == 16
    assert text.count("- **Ý nghĩa:**") == 16
    assert text.count("- **Hạn chế:**") == 16
    assert "Mỗi biểu đồ gồm 3 phần" in text


def test_md_embeds_images_with_relative_paths(rich_run):
    _raw, _led, _fig, _md, text = rich_run
    for name in ALL_FILES:
        assert f"](figures/careerviet/{name})" in text


def test_source_line_is_measured_not_hardcoded(rich_run):
    _raw, _led, _fig, _md, text = rich_run
    assert "Nguồn: 44 envelope CareerViet, thu thập 16-17/10/2026" in text
    assert "1.018" not in text        # so lieu that cua 1018 envelope khong ro ri


# ============================================================ e2e: 24 tin khong phan loai
def test_unclassified_jobs_get_their_own_group(rich_run):
    """Tin rỗng `Ngành nghề` phải là nhóm riêng, không bị cộng vào ngoài IT."""
    tmp = rich_run[0].parents[0]
    raw = tmp / "unk" / "raw"
    spec = [(f"U{i:02d}", "c1", True, _payload(i, it=True)) for i in range(20)]
    spec += [(f"X{i:02d}", "c1", True,
              {**_payload(i, it=True), "Ngành nghề": [], "map": None}) for i in range(4)]
    fig, text = _run_on(raw.parent, spec)
    assert "4 tin (16,7%) rỗng 'Ngành nghề' được tách thành nhóm riêng" in text
    assert (fig / "02_it_share_donut.png").exists()


# ============================================================ e2e: JD tu detail-row
def test_chart15_measures_description_section_from_detail_row(tmp_path):
    long_desc = "M" * 1200
    spec = [(f"A{i}", "c1", True, _payload(i, it=True, desc=long_desc)) for i in range(21)]
    _fig, text = _run_on(tmp_path, spec)
    assert "Section 'Mô tả Công việc'" in text
    assert "1.200" in text                       # trung vi = min = max = 1200 ky tu
    assert "21/21 tin (100,0%)" in text
    assert "90 ky tu" not in text                # detail-box khong duoc lam so do


def test_chart15_reports_requirement_and_benefit_coverage(tmp_path):
    spec = [(f"A{i}", "c1", True, _payload(i, it=True, desc="desc " * 50)) for i in range(21)]
    _fig, text = _run_on(tmp_path, spec)
    assert "'Yêu Cầu Công Việc': 21 tin" in text
    assert "'Phúc lợi': 21 tin" in text


def test_chart15_says_so_when_no_description_section(tmp_path):
    """Không envelope nào có heading 'Mô tả' -> ghi chú rõ, không bịa số."""
    spec = []
    for i in range(21):
        p = _payload(i, it=True, desc=None)
        p["detail-row"].pop(MO_TA, None)
        spec.append((f"A{i}", "c1", True, p))
    _fig, text = _run_on(tmp_path, spec)
    assert "Không tìm thấy section 'Mô tả Công việc'" in text


# ============================================================ e2e: phuc loi
def test_benefits_chart_counts_chip_vocabulary(tmp_path):
    """i le co 'Đào tạo, Laptop' -> 10/21 tin co Laptop (i chan chi co 'Đào tạo')."""
    spec = []
    for i in range(21):
        p = _payload(i, it=True, benefits="Đào tạo, Laptop" if i % 2 else "Đào tạo")
        spec.append((f"B{i}", "c1", True, p))
    fig, text = _run_on(tmp_path, spec)
    assert (fig / "12_benefits_top.png").exists()
    assert "Đào tạo 21 tin (100,0%)" in text
    assert "Laptop 10 tin (47,6%)" in text


def test_benefits_chart_skipped_when_source_has_none(tmp_path):
    spec = [(f"B{i}", "c1", True, _payload(i, it=True, benefits="")) for i in range(21)]
    fig, text = _run_on(tmp_path, spec)
    assert not (fig / "12_benefits_top.png").exists()
    assert "không tách được loại phúc lợi nào" in text


# ============================================================ e2e: luong
def test_salary_chart_reports_disclosure_rate(tmp_path):
    """i % 2 == 0 co baseSalary -> 11/21 tin quy doi duoc (52,4%)."""
    spec = [(f"S{i}", "c1", True, _payload(i, it=True)) for i in range(21)]
    fig, text = _run_on(tmp_path, spec)
    assert (fig / "05_salary_hist.png").exists()
    assert (fig / "06_salary_box_it_vs_non.png").exists()
    assert "11/21 tin (52,4%) đọc được lương" in text


def test_salary_charts_skipped_without_readable_salary(tmp_path):
    spec = []
    for i in range(21):
        p = _payload(i, it=True)
        p["job-posting-schema"].pop("baseSalary", None)
        p["detail-box"] = [x for x in p["detail-box"] if not x.startswith("Lương")]
        spec.append((f"S{i}", "c1", True, p))
    fig, text = _run_on(tmp_path, spec)
    assert not (fig / "05_salary_hist.png").exists()
    assert not (fig / "06_salary_box_it_vs_non.png").exists()
    assert "0/21" in text


# ============================================================ e2e: ledger
def test_ledger_chart_reconciles_urls_and_repost(tmp_path):
    spec = [(f"L{i}", "c1", True, _payload(i, it=True)) for i in range(21)]
    led_records = {
        f"h{i}": {"source": "careerviet", "status": "DONE", "latest_version": 1,
                  "job_id": f"L{i}"} for i in range(21)
    } | {
        f"rp{i}": {"source": "careerviet", "status": "DONE", "latest_version": 0,
                   "job_id": None, "repost_of_url_hash": "h0"} for i in range(2)
    }
    tmp_path2 = tmp_path / "case"
    tmp_path2.mkdir()
    _fig, text = _run_on(tmp_path2, spec, led_records)
    assert "23 URL của careerviet, 23 DONE, 2 DONE + có `repost_of_url_hash`" in text
    assert "Đẳng thức 23 URL - 2 repost = 21 envelope" in text


# ============================================================ e2e: don PNG cu
def test_main_prunes_stale_png_and_keep_stale_flag(tmp_path):
    spec = [(f"P{i}", "c1", True, _payload(i, it=True)) for i in range(21)]
    raw, led = tmp_path / "raw", tmp_path / "ledger"
    _write_ledger(led, {})
    _corpus(raw, spec)
    fig, md = tmp_path / "figs", tmp_path / "out.md"
    fig.mkdir(parents=True)
    (fig / "99_stale_chart.png").write_bytes(b"png")

    args = ["--raw", str(raw), "--ledger", str(led), "--fig-dir", str(fig), "--md-out", str(md)]
    ec.main(args + ["--keep-stale"])
    assert (fig / "99_stale_chart.png").exists()

    ec.main(args)
    assert not (fig / "99_stale_chart.png").exists()
    assert (fig / "01_bucket_supply.png").exists()


# ============================================================ e2e: du lieu mong
def test_main_survives_minimal_corpus(tmp_path):
    """2 tin, 1 bucket, khong tag/khong luong/khong map: khong duoc crash, khong bia so."""
    thin = {
        "title": "Việc A", "job-company-name": "", "detail-box": [], "detail-row": {},
        "job-tags": [], "map": None, "Ngành nghề": [], "job-posting-schema": {},
    }
    _fig, text = _run_on(tmp_path, [("T1", "c1", False, thin), ("T2", "c1", False, thin)])
    assert "## 1." in text and "## 16." in text
    assert "2 tin (100,0%) rỗng 'Ngành nghề'" in text
    assert "1.018" not in text
