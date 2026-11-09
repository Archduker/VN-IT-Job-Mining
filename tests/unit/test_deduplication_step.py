"""Unit test cho `preprocessing/deduplication` (docs/tasks/02_tai_clean_and_deduplication.md).

Phủ: 3.1 chuẩn hóa văn bản/băm khóa, 3.2.A Blocking Key, 3.3 tầng 1 nội sàn (D1/D2),
3.4 tầng 2 liên sàn (D4/D5 + audit duyệt mẫu) và bảng hợp nhất Golden Master SPEC-05 3.2.C.
Thêm: quy tắc chọn bản ghi thắng của cả hai tầng (hướng của tie-break thời gian),
dòng truy vết cho bản bị loại nối gián tiếp, và an toàn khi ai đó chạy lẻ một sàn.

Mọi giá trị kỳ vọng đều được đo lại từ chính module rồi mới viết vào test, không đoán.

Chạy:  pytest tests/unit/test_deduplication_step.py -q
"""

import csv
import json
import unicodedata

import pytest

from preprocessing.clean import label_review
from preprocessing.clean import run as clean
from preprocessing.common import step_report
from preprocessing.deduplication import inter_source as inter
from preprocessing.deduplication import run as dedup
from preprocessing.deduplication.blocking import (
    blocking_key,
    company_slug,
    location_code,
    title_group,
)
from preprocessing.deduplication.intra_source import (
    apply_d2,
    cdc_chain_audit,
    pick_winner,
    repost_groups,
)
from preprocessing.deduplication.text_norm import (
    canonical_hash,
    clean_text,
    fold,
    identity_hash,
    jd_text,
    strip_html,
)

JD = " ".join(["Mô tả công việc: phát triển hệ thống backend bằng Python, Django cho khách hàng."] * 2)
REQ = "Yêu cầu: kinh nghiệm Python, MySQL, Docker, làm việc nhóm tốt."
COMPANY = "Công ty Cổ phần AZNova"
SEEN = "2026-10-20T06:00:00+00:00"


# ------------------------------------------------------------------ fixture dùng chung
def flat(title="Backend Developer", company=COMPANY, city="Hà Nội", salary="15 - 25 triệu",
         exp="1 năm", jd=JD, req=REQ, skills=(), posted="05/10/2026"):
    """Bản phẳng tối giản, đúng các trường mà module dedup đọc."""
    return {"job_title": title, "company_name": company, "raw_location_text": city,
            "working_locations": [city] if city else [], "raw_salary_text": salary,
            "raw_experience_text": exp, "raw_description_text": jd, "raw_requirements_text": req,
            "skills_list": list(skills), "raw_posted_date": posted}


def item(src, jid, f=None, seen=SEEN, version=1):
    """Item đúng cấu trúc mà dedup.run.load_items trả về."""
    f = flat() if f is None else f
    return {"src": src, "jid": jid, "url": f"https://x/{src}/{jid}",
            "env": {"metadata": {"job_id": jid, "source": src, "source_url": f"https://x/{src}/{jid}",
                                 "scraped_at": seen, "version": version}},
            "flat": f, "chash": canonical_hash(f), "xhash": identity_hash(f), "jd": jd_text(f),
            "bkey": blocking_key(f), "seen_at": seen, "ver": version, "drop": None, "master": None,
            "reposts": [], "merged": []}


def itviec_env(jid, title="Backend Developer", company=COMPANY, city="Hà Nội", salary="15 - 25 triệu",
               desc=JD, req=REQ, posted="05/10/2026", seen=SEEN, version=1):
    """Envelope theo đúng cấu trúc raw_payload của ITviec (sections + work_location)."""
    return {"metadata": {"job_id": jid, "source": "itviec", "source_url": f"https://x/itviec/{jid}",
                         "scraped_at": seen, "version": version},
            "raw_payload": {"title": title, "company_name": company, "work_location": city,
                            "salary_display_text": salary, "posted_at_raw": posted,
                            "sections": {"Mô tả": [desc], "Yêu cầu": [req]}}}


def jobsgo_env(jid, title="Backend Developer", company=COMPANY, city="Hà Nội", salary="Thỏa thuận",
               desc=JD, req=REQ, exp="1 năm", skills=(), posted="05/10/2026", seen=SEEN, version=1):
    """Envelope theo đúng cấu trúc raw_payload của JobsGO (bullets + salary_raw + general_info)."""
    return {"metadata": {"job_id": jid, "source": "jobsgo", "source_url": f"https://x/jobsgo/{jid}",
                         "scraped_at": seen, "version": version},
            "raw_payload": {"title": title, "company": company, "location": city,
                            "salary_raw": salary, "experience": exp,
                            "description_bullets": [desc], "requirements_bullets": [req],
                            "skills": list(skills), "general_info": {"posted_date": posted}}}


def generic_env(jid, seen, version, desc="Mô tả gốc.", title="Backend Developer"):
    """Envelope cho nguồn lạ (nhánh _flatten_generic) dùng kiểm chuỗi CDC nội sàn."""
    return {"metadata": {"job_id": jid, "source": "src_a", "source_url": f"https://x/src_a/{jid}",
                         "scraped_at": seen, "version": version},
            "raw_payload": {"title": title, "company": COMPANY, "location": "Hà Nội",
                            "salary": "15 - 25 triệu", "description": desc}}


def rows_of(report, rule_id):
    return next((r["rows_affected"] for r in report.data["rules"] if r["id"] == rule_id), 0)


# ------------------------------------------------------------------ 3.1 bóc HTML + làm sạch
def test_strip_html_giu_bullet_và_loại_script():
    out = strip_html("<div><h3>Mô tả</h3><ul><li>backend</li><li>python</li></ul>"
                     "<script>track()</script><br>het</div>")
    assert out == "Mô tả\n• \nbackend\n\n\n• \npython\n\n\n\n\nhet\n\n"
    assert "track" not in out


def test_strip_html_khong_đổi_văn_bản_thuần():
    assert strip_html("Backend Developer Python") == "Backend Developer Python"
    assert strip_html("") == ""


def test_strip_html_giải_mã_entity_theo_SPEC_2_1_4():
    """Nhiều sàn trả JD đã là văn thuần nhưng còn nguyên entity, không được bỏ qua.

    Giá trị kỳ vọng đo trực tiếp từ module: `&nbsp;` giải ra U+00A0 chứ không phải dấu cách,
    và `clean_text` mới là chỗ quy nó về khoảng trắng thường.
    """
    assert strip_html("K&#39;math &amp; QA") == "K'math & QA"
    assert strip_html("Backend&nbsp;Developer") == "Backend\xa0Developer"
    assert clean_text("Backend&nbsp;Developer") == "Backend Developer"
    # entity bị mã hóa hai lớp: sau khi giải mã thành thẻ thật thì bị bóc luôn, không lọt vào TF-IDF
    assert strip_html("&lt;script&gt;alert()&lt;/script&gt;") == ""
    assert clean_text("<div>Java&nbsp;&amp;&nbsp;Spring</div>") == "Java & Spring"


def test_clean_text_xóa_ký_tự_điều_khiển_và_gom_khoảng_trắng():
    assert clean_text("a​b c﻿d e\x07") == "a b c d e"


def test_clean_text_đọc_boilerplate_nhưng_giữ_nguyên_nội_dung_jd_bên_cạnh():
    s = clean_text("Mô tả công việc. Tải ứng dụng TopCV ngay hôm nay. "
                   "Mã tin tuyển dụng: 12345. Hạn nộp hồ sơ: 15/11/2026. "
                   "Phát triển backend bằng Python.")
    assert "Tải ứng dụng" not in s and "Mã tin" not in s and "Hạn nộp" not in s
    assert "Phát triển backend bằng Python." in s


def test_fold_bỏ_dấu_nhưng_giữ_ký_tự_công_nghệ():
    """Điều kiện nghiệm thu 3.1: C#, C++, .NET, F# phải còn sau khi bỏ dấu."""
    assert fold("Kỹ Sư .NET / C++ / C# - F#") == "ky su .net / c++ / c# - f#"


def test_canonical_hash_bất_biến_với_metadata_không_phải_nội_dung():
    f = flat()
    assert canonical_hash(f) == canonical_hash(flat(posted="01/01/2026"))
    assert canonical_hash(f) != canonical_hash(flat(jd=JD + " Thêm trách nhiệm quản lý đội."))


def test_identity_hash_bỏ_qua_lương_và_địa_chỉ_vì_mỗi_sàn_ghi_khác_nhau():
    a, b = flat(salary="15 - 25 triệu", city="Hà Nội"), flat(salary="Lương upto $2000", city="Ha Noi, Vietnam")
    assert identity_hash(a) == identity_hash(b)      # D4 vẫn coi là một tin
    assert canonical_hash(a) != canonical_hash(b)    # D2 nội sàn thì phân biệt
    assert identity_hash(a) != identity_hash(flat(title="Data Engineer"))


# ------------------------------------------------------------------ 3.2.A Blocking Key
def test_blocking_key_đúng_công_thục_ba_thành_phần():
    f = flat()
    assert blocking_key(f) == "aznova_HN_backend"
    assert blocking_key(f) == f"{company_slug(f['company_name'])}_{location_code(f)}_{title_group(f['job_title'])}"


def test_company_slug_bỏ_hậu_tố_pháp_lý_và_ngành_nghề():
    assert company_slug(COMPANY) == "aznova"
    assert company_slug("FPT Software") == "fpt"
    assert company_slug("Viettel Solutions") == "viettel"
    assert company_slug("A") == "a"


def test_location_code_gộp_biến_thể_tên_thành_phố():
    assert location_code(flat(city="Hà Nội")) == "HN"
    assert location_code(flat(city="Hanoi")) == "HN"
    assert location_code(flat(city="Hồ Chí Minh")) == location_code(flat(city="TP. Hồ Chí Minh")) == "HCM"
    assert location_code(flat(city="Đà Nẵng")) == "DN"


@pytest.mark.parametrize("city", ["", "Không rõ"])
def test_location_code_không_xác_định_thành_na(city):
    assert location_code(flat(city=city)) == "na"


@pytest.mark.parametrize(("title", "group"), [
    ("Lập trình viên Fullstack", "fullstack"),
    ("Backend Developer", "backend"),
    ("Thực tập sinh Kiểm thử", "qa"),
    ("Data Engineer", "data"),
    ("Java Developer", "java"),
    ("Kỹ sư cầu nối", "brse"),
    ("Trưởng nhóm Kỹ thuật", "manage"),
    ("Chuyên viên Kinh doanh", "other"),
    ("", "unknown"),
])
def test_title_group_phân_nhóm_theo_từ_khóa_đã_bỏ_dấu(title, group):
    assert title_group(title) == group


# ------------------------------------------------------------------ 3.3 tầng 1: nội sàn (D1, D2)
def test_repost_groups_nhóm_theo_hash_nội_dung_khác_job_id():
    a, b = item("src_x", "1"), item("src_x", "2")
    c = item("src_x", "3", flat(title="Data Engineer"))
    groups = repost_groups([a, b, c])
    assert [sorted(i["jid"] for i in g) for g in groups] == [["1", "2"]]


def test_apply_d2_giữ_bản_đầy_đủ_nhất_rồi_mới_nhất_và_truy_vết_repost():
    old = item("src_x", "1", seen="2026-10-10T06:00:00+00:00")
    new = item("src_x", "2")                       # cùng nội dung, cào muộn hơn
    dropped = apply_d2([old, new], extra := {})
    assert [d["jid"] for d in dropped] == ["1"]
    assert dropped[0]["drop"] == {"rule": "D2", "kept_job_id": "2", "kept_url": new["url"],
                                  "hash": old["chash"]}
    assert new["reposts"] == [{"source": "src_x", "job_id": "1", "url": old["url"], "content_hash": old["chash"]}]
    assert extra["d2_groups"] == 1


def test_cdc_chain_audit_phân_loại_bước_nhảy_version(tmp_path):
    files = [(tmp_path / "2026-10-20" / "7_v1.json", generic_env("7", "2026-10-20T06:00:00+00:00", 1)),
             (tmp_path / "2026-11-01" / "7_v2.json", generic_env("7", "2026-11-01T06:00:00+00:00", 2)),
             # đổi nội dung thật nhưng collection không bump version -> bất thường cần báo về Collection
             (tmp_path / "2026-11-01" / "7_v3.json",
              generic_env("7", "2026-11-01T07:00:00+00:00", 2, desc="Mô tả đã đổi.")),
             (tmp_path / "2026-11-01" / "8_v1.json", generic_env("8", "2026-11-01T06:00:00+00:00", 1))]
    for path, data in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert cdc_chain_audit("src_a", tmp_path) == {"job_ids": 2, "chains_gt1": 1, "hops": 2,
                                                  "hop_same_crawler_hash": 0, "hop_same_canonical_hash": 1,
                                                  "hop_version_not_bumped": 1, "hop_same_version": 1}


def test_cdc_chain_audit_thiếu_thư_mục_raw_thì_trả_toàn_0(tmp_path):
    assert set(cdc_chain_audit("src_a", tmp_path / "khong_ton_tai").values()) == {0}


# ------------------------------------------------------------------ 3.4 tầng 2: liên sàn (D4, D5)
def _thin(**drops):
    """Bản phẳng cố tình thiếu vài trường để thử tie-break 'độ đầy đủ'."""
    f = flat()
    for k in drops.get("fields", ()):
        f[k] = None
    return f


def test_pick_cross_winner_giữ_bản_cào_mới_nhất_khi_ngang_uy_tín_và_độ_đầy_đủ():
    """Hướng của tie-break thời gian: bản cũ không được thắng (SPEC-05 mục 3.1 "giữ version mới nhất").

    Trên snapshot f693b30 có 3 cụm chạm tới đúng tie-break này, nên hướng phải được test chặt.
    """
    # 1) uy tín sàn là tiêu chí số 1, thắng cả thời gian
    old_top = item("itviec", "1", seen="2026-09-01T00:00:00+00:00")
    new_low = item("jobsgo", "2", seen="2026-11-01T00:00:00+00:00")
    assert dedup.pick_cross_winner([new_low, old_top]) is old_top
    # 2) độ đầy đủ trường là tiêu chí số 2, thắng cả thời gian
    old_full = item("jobsgo", "3", seen="2026-08-01T00:00:00+00:00")
    new_thin = item("jobsgo", "4", _thin(fields=("raw_salary_text", "raw_experience_text")),
                    seen="2026-11-05T00:00:00+00:00")
    assert dedup.pick_cross_winner([new_thin, old_full]) is old_full
    # 3) bằng cả hai tiêu chí trên thì bản mới nhất thắng, bất kể thứ tự truyền vào
    old = item("jobsgo", "5", seen="2026-08-01T00:00:00+00:00")
    new = item("jobsgo", "6", seen="2026-11-05T00:00:00+00:00")
    assert dedup.pick_cross_winner([old, new]) is new
    assert dedup.pick_cross_winner([new, old]) is new
    # 4) bằng hết thì job_id nhỏ nhất giữ kết quả tất định
    elder_id = item("jobsgo", "5", seen="2026-11-05T00:00:00+00:00")
    assert dedup.pick_cross_winner([new, elder_id]) is elder_id


def test_pick_winner_nội_sàn_ưu_tiên_độ_đầy_đủ_rồi_bản_mới_nhất():
    """Cùng chiều với D2 nhưng độ đầy đủ xét trước; repost trùng hash thì bản cào muộn hơn giữ."""
    old, new = (item("src_x", "1", seen="2026-08-01T00:00:00+00:00"),
                item("src_x", "2", seen="2026-11-05T00:00:00+00:00"))
    assert pick_winner([old, new])["jid"] == "2"
    thin = item("src_x", "3", _thin(fields=("raw_salary_text", "raw_experience_text")),
                seen="2026-12-20T00:00:00+00:00")
    assert pick_winner([thin, old])["jid"] == "1", "bản đầy đủ trường hơn thắng dù cào sớm hơn"


def test_exact_cross_pairs_dùng_khóa_identity_nên_độc_lập_blocking_key():
    a = item("itviec", "1")
    b = item("jobsgo", "2", flat(salary="Thỏa thuận", city="Ha Noi, Vietnam"))
    assert inter.exact_cross_pairs([a, b]) == [(a, b, 1.0)]
    c = item("topcv", "3", flat(title="Data Engineer"))
    assert inter.exact_cross_pairs([a, c]) == []


def test_cross_source_pairs_bắt_cặp_dịch_lai_vượt_ngưỡng():
    a = item("itviec", "1")
    b = item("jobsgo", "2", flat(jd=JD.replace("phát triển", "xây dựng")))
    hits = inter.cross_source_pairs([a, b])
    assert len(hits) == 1 and hits[0][2] >= inter.COSINE_THRESHOLD
    assert inter.exact_cross_pairs([a, b]) == []      # đây là D5, không phải D4


def test_cross_source_pairs_bỏ_qua_hai_vị_trí_khác_nhau_hoàn_toàn():
    a = item("itviec", "1")
    c = item("jobsgo", "2", flat(title="Data Engineer",
                                 jd="Xây dựng pipeline dữ liệu, ETL và kho dữ liệu cho doanh nghiệp.",
                                 req="SQL, Python, Airflow, kinh nghiệm xử lý dữ liệu lớn."))
    assert a["bkey"] != c["bkey"]
    assert inter.cross_source_pairs([a, c]) == []
    assert inter.clusters([a, c], []) == []


def test_candidate_blocks_loại_block_một_sàn_và_tên_công_ty_quá_ngắn():
    solo = inter.build_blocks([item("itviec", "1"), item("itviec", "2")])
    assert list(solo) and inter.candidate_blocks(solo) == {}
    thin = inter.build_blocks([item("itviec", "3", flat(company="A")), item("jobsgo", "4", flat(company="A"))])
    key = next(iter(thin))
    assert len(key.rsplit("_", 2)[0]) < inter.MIN_COMPANY_SLUG
    assert inter.candidate_blocks(thin) == {}


def test_same_company_phân_biệt_các_công_ty_con_cùng_slug_ngắn():
    """Slug 3 ký tự như `fpt` dùng chung cho FPT Software và FPT Telecom nên phải đòi bằng chứng."""
    a = item("itviec", "1", flat(company="FPT Software"))
    b = item("jobsgo", "2", flat(company="FPT Telecom"))
    c = item("topdev", "3", flat(company="Công ty TNHH FPT Software"))
    assert len(inter.block_slug(a["bkey"])) < inter.AMBIGUOUS_SLUG, "fixture phải rơi vào nhóm slug ngắn"
    assert not inter.same_company(a, b), "hai công ty con khác nhau không được coi là một"
    assert inter.same_company(a, c), "tên bao hàm nhau (fpt software ⊂ công ty tnhh fpt software) là một"
    assert not inter.same_company(item("topcv", "4", flat(company=None)), a), "thiếu tên thì không đủ căn cứ"
    # và block slug ngắn vẫn được so, chỉ so các cặp đạt same_company
    assert inter.candidate_blocks(inter.build_blocks([a, b, c])) != {}


def test_clusters_nối_bắc_cầu_union_find():
    a, b, c = item("itviec", "1"), item("topdev", "2"), item("jobsgo", "3")
    clusters = inter.clusters([a, b, c], [(a, b, 0.9), (b, c, 0.9)])
    assert len(clusters) == 1 and len(clusters[0]) == 3


def test_authority_theo_thứ_tự_uy_tín_đặc_tả():
    order = ["itviec", "topdev", "vietnamworks", "topcv", "careerviet", "glints", "jobsgo", "vieclam24h"]
    assert [inter.authority(s) for s in order] == list(range(8))
    assert inter.authority("src_x") == 8


def test_fuse_đúng_bảng_hợp_nhất_golden_master():
    it = item("itviec", "1", flat(salary="Thỏa thuận", skills=["Python", "Django"]))
    jg = item("jobsgo", "2", flat(title="Senior Backend Developer", company="CTCP AZNova VN",
                                   salary="18 - 25 triệu", skills=["Git", "Python"],
                                   jd=JD + " Môi trường trẻ, đào tạo bài bản.", posted="01/09/2026"),
              seen="2026-11-05T06:00:00+00:00")
    gold = inter.fuse([jg, it])                       # thứ tự vào cụm không ảnh hưởng kết quả
    assert gold["job_title"] == "Backend Developer", "tiêu đề lấy theo sàn uy tín nhất"
    assert gold["company_name"] == COMPANY, "công ty lấy bản dài hơn"
    assert gold["job_description"] == JD + " Môi trường trẻ, đào tạo bài bản.", "JD lấy bản dài hơn"
    assert gold["skills_extracted"] == ["Python", "Django", "Git"], "kỹ năng là hợp tập hợp theo thứ tự sàn uy tín"
    assert gold["salary_text"] == "18 - 25 triệu" and gold["salary_source_platform"] == "jobsgo"
    assert gold["location"] == "Hà Nội"
    assert gold["source_platforms"] == ["itviec", "jobsgo"]
    assert gold["source_job_ids"] == ["itviec:1", "jobsgo:2"]
    assert gold["first_posted_at"] == "01/09/2026" and gold["last_seen_at"] == "2026-11-05T06:00:00+00:00"
    assert gold["blocking_key"] == it["bkey"] and gold["duplicate_count"] == 2
    assert gold["is_cross_platform"] is True
    assert gold["master_id"] == inter.fuse([it, jg])["master_id"], "UUIDv5 tất định"


def test_fuse_bản_độc_nhất_vẫn_có_golden_record_riêng():
    solo = item("topcv", "9")
    gold = inter.fuse([solo])
    assert gold["duplicate_count"] == 1 and gold["is_cross_platform"] is False
    assert gold["source_job_ids"] == ["topcv:9"] and gold["salary_source_platform"] == "topcv"
    assert gold["master_id"] != inter.fuse([item("topcv", "10")])["master_id"]


# ------------------------------------------------------------------ end-to-end bước 01b
@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Đầu vào 01 Clean giả + mọi đường dẫn ghi trỏ vào tmp, không đụng dữ liệu/report thật."""
    in_dir = tmp_path / "data" / "preprocessing" / "01_clean"
    in_dir.mkdir(parents=True)
    docs = {"itviec": [itviec_env("i1"), itviec_env("i2", seen="2026-10-10T06:00:00+00:00"),
                       itviec_env("i3", title="Chuyên viên Marketing",
                                  desc="Tư vấn giải pháp phần mềm cho khách hàng doanh nghiệp khu vực phía Bắc.",
                                  req="Giao tiếp tốt, hiểu về phần mềm quản lý doanh nghiệp.")],
            "jobsgo": [jobsgo_env("j1"),
                       jobsgo_env("j2", desc=JD.replace("phát triển", "xây dựng")),
                       jobsgo_env("j3", title="Data Engineer",
                                  desc="Xây dựng pipeline dữ liệu, ETL và kho dữ liệu cho doanh nghiệp.",
                                  req="SQL, Python, Airflow, kinh nghiệm xử lý dữ liệu lớn.")]}
    for name, rows in docs.items():
        (in_dir / f"{name}.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(dedup, "IN_DIR", in_dir)
    monkeypatch.setattr(dedup, "OUT_DIR", tmp_path / "data" / "preprocessing" / dedup.STEP)
    monkeypatch.setattr(dedup, "RAW_ROOT", tmp_path / "data")
    monkeypatch.setattr(dedup, "SOURCES", ["itviec", "jobsgo"])  # để sandbox được tính là chạy đủ sàn
    monkeypatch.setattr(step_report, "REPORTS_ROOT", tmp_path / "reports")
    return tmp_path


def load_out(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_run_end_to_end_áp_dụng_cả_hai_tầng_và_bảo_toàn_dòng(sandbox):
    res = dedup.run(["itviec", "jobsgo"], dry_run=False)
    a, b = res["itviec"], res["jobsgo"]

    assert a.data["step"] == dedup.STEP and a.data["mode"] == "applied"
    assert a.data["input"]["rows"] == 3 and a.data["output"]["rows"] == 2
    assert (rows_of(a, "D1"), rows_of(a, "D2"), rows_of(a, "D4"), rows_of(a, "D5")) == (0, 1, 0, 0)
    assert b.data["input"]["rows"] == 3 and b.data["output"]["rows"] == 1
    assert (rows_of(b, "D2"), rows_of(b, "D4"), rows_of(b, "D5")) == (0, 1, 1)
    for rep in (a, b):  # luật bảo toàn P0 mục 4
        assert rep.data["input"]["rows"] == rep.data["output"]["rows"] + sum(d["rows"] for d in rep.data["dropped"])
        rep.check_conserved()
        assert (sandbox / "reports" / dedup.STEP / f"{rep.data['source']}.json").is_file()

    out = sandbox / "data" / "preprocessing" / dedup.STEP
    kept = load_out(out / "itviec.jsonl") + load_out(out / "jobsgo.jsonl")
    assert sorted(e["metadata"]["job_id"] for e in kept) == ["i1", "i3", "j3"]
    for e in kept:
        d = e["metadata"]["dedup"]
        assert d["content_hash_norm"] and d["identity_hash"] and d["blocking_key"] and d["master_id"]
        assert "repost_records" in d  # khóa luôn có, giá trị None khi không phải bản giữ của nhóm repost
    winner = next(e for e in kept if e["metadata"]["job_id"] == "i1")
    assert winner["metadata"]["dedup"]["merged_from"] == ["jobsgo:j1", "jobsgo:j2"]
    repost = winner["metadata"]["dedup"]["repost_records"]
    assert [r["job_id"] for r in repost] == ["i2"]
    assert repost[0]["url"] == "https://x/itviec/i2" and len(repost[0]["content_hash"]) == 64

    gold = load_out(out / "golden_master_jobs.jsonl")
    assert len(gold) == 3 and len({g["master_id"] for g in gold}) == 3
    cross = [g for g in gold if g["duplicate_count"] > 1]
    assert len(cross) == 1 and cross[0]["source_platforms"] == ["itviec", "jobsgo"]
    assert (out / "golden_master_jobs.parquet").stat().st_size > 0

    audit = (out / "duplicates_audit.csv").read_text(encoding="utf-8-sig").splitlines()
    assert audit[0].startswith("kind,rule,job_id_a")
    assert [line.split(",")[0] for line in audit[1:]] == ["dropped", "dropped"]


def test_báo_cáo_hợp_gộp_cộng_số_theo_luật_và_đo_đạc_chỉ_kiểm(sandbox):
    res = dedup.run(["itviec", "jobsgo"], dry_run=False)
    total = step_report.merge_reports(dedup.STEP, [res["itviec"], res["jobsgo"]], False)
    assert total.data["source"] == "_all"
    assert total.data["input"]["rows"] == 6 and total.data["output"]["rows"] == 3
    dropped = {r["id"]: r["rows_affected"] for r in total.data["rules"] if r["action"] == "drop"}
    assert dropped == {"D2": 1, "D4": 1, "D5": 1}
    assert total.data["extra"]["sources"] == {"itviec": {"input": 3, "output": 2},
                                              "jobsgo": {"input": 3, "output": 1}}
    total.check_conserved()
    # số đo riêng của từng sàn: 2 block itviec, 1 nhóm repost, raw không tồn tại -> CDC bằng 0
    assert res["itviec"].data["extra"]["blocking_blocks"] == 2
    assert res["itviec"].data["extra"]["d2_groups"] == 1
    assert res["itviec"].data["extra"]["cdc"] == dict.fromkeys(
        ["job_ids", "chains_gt1", "hops", "hop_same_crawler_hash", "hop_same_canonical_hash",
         "hop_version_not_bumped", "hop_same_version"], 0)


def test_run_dry_run_chỉ_đo_không_ghi_dữ_liệu(sandbox):
    res = dedup.run(["itviec", "jobsgo"], dry_run=True)
    assert res["itviec"].data["mode"] == "dry_run"
    assert res["itviec"].data["output"]["rows"] == 2 and res["jobsgo"].data["output"]["rows"] == 1
    out = sandbox / "data" / "preprocessing" / dedup.STEP
    assert not (out / "itviec.jsonl").exists()
    assert not (out / "golden_master_jobs.parquet").exists()


def test_chạy_lẻ_một_sàn_đánh_dấu_partial_run_để_monitoring_không_đọc_nhầm(sandbox):
    dedup.run(["itviec"], dry_run=True)
    total = json.loads((sandbox / "reports" / "_partial" / dedup.STEP / "_all.json").read_text(encoding="utf-8"))
    assert total["extra"]["partial_run"] is True and list(total["extra"]["sources"]) == ["itviec"]
    assert any("--source all" in n for n in total["checks"]["notes"])
    anysrc = json.loads((sandbox / "reports" / "_partial" / dedup.STEP / "itviec.json").read_text(encoding="utf-8"))
    assert any(".partial" in n for n in anysrc["checks"]["notes"]), "phải cảnh báo ngay trong báo cáo từng sàn"


def test_chạy_lẻ_một_sàn_không_ghi_đè_file_toàn_dự_án(sandbox):
    """Dry-run một sàn mà đè `duplicates_audit.csv` thì người duyệt tưởng cả nước chỉ có vài cặp."""
    out = sandbox / "data" / "preprocessing" / dedup.STEP
    dedup.run(["itviec", "jobsgo"], dry_run=True)          # bản đủ: ghi file không hậu tố
    dedup.run(["itviec"], dry_run=True)                    # bản lẻ: không được chạm vào file của bản đủ
    assert (out / "duplicates_audit.csv").is_file()
    assert (out / "duplicates_audit.partial.csv").is_file()
    assert not (out / "golden_master_jobs.partial.jsonl").exists(), "dry-run lẻ không ghi golden master"


def test_pipeline_transitive_audit(sandbox, monkeypatch):
    """Kiểm quyết định merge và CSV; mock điểm biên, không gán sẵn trạng thái drop."""
    a = item("itviec", "a")
    b = item("jobsgo", "b", flat(jd=JD + " B"))
    c = item("topcv", "c", flat(jd=JD + " C"))
    # Dùng 3 nguồn để cả hai cạnh mạnh là liên sàn.
    monkeypatch.setattr(dedup, "SOURCES", ["itviec", "jobsgo", "topcv"])
    monkeypatch.setattr(dedup, "load_items", lambda src: [i for i in (a, b, c) if i["src"] == src])
    monkeypatch.setattr(inter, "exact_cross_pairs", lambda _: [])
    monkeypatch.setattr(inter, "cross_source_pairs",
                        lambda *args, **kwargs: [(a, b, .85), (b, c, .9), (a, c, .8)])
    dedup.run(dedup.SOURCES, dry_run=False)
    gold = load_out(dedup.OUT_DIR / "golden_master_jobs.jsonl")
    assert len(gold) == 1 and gold[0]["duplicate_count"] == 3
    rows = list(csv.DictReader((dedup.OUT_DIR / "duplicates_audit.csv").open(encoding="utf-8-sig")))
    tail = next(r for r in rows if r["kind"] == "transitive-dropped")
    assert (tail["job_id_a"], tail["job_id_b"], tail["linked_via"], tail["cosine"]) == ("c", "a", "b", "0.9")
    assert sum(r["kind"] == "dropped" for r in rows) == 2
    assert sum(r["kind"] == "transitive-link" for r in rows) == 1



def test_CLI_chặn_applied_khi_chạy_lẻ_một_sàn(sandbox):
    """Applied một sàn sẽ ghi đè output và golden master của cả dự án -> phải bị từ chối."""
    with pytest.raises(SystemExit):
        dedup.main(["--source", "itviec"])
    assert dedup.main(["--source", "itviec", "--dry-run"]) == 0


def test_run_thiếu_đầu_vào_01_clean_thì_dừng_chắn(sandbox):
    with pytest.raises(FileNotFoundError, match="01 Clean"):
        dedup.run(["careerviet"], dry_run=True)


def test_main_cli_in_báo_từng_nguồn_và_trả_exit_0(sandbox, capsys):
    assert dedup.main(["--source", "itviec", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert f"{dedup.STEP} itviec: input 3 -> output 2 (dry_run)" in out


def test_nfc_before_boilerplate():
    text = "Tải ứng dụng TopCV ngay hôm nay. Backend Python."
    assert clean_text(unicodedata.normalize("NFD", text)) == clean_text(text)
    assert "Tải ứng dụng" not in clean_text(text)


def test_fusion_dates_chronological_and_invalid():
    a = item("itviec", "a", flat(posted="10/10/2026"), seen="2026-11-07T08:00:00+07:00")
    b = item("jobsgo", "b", flat(posted="28/09/2026"), seen="2026-11-07T02:00:00Z")
    c = item("topcv", "c", flat(posted="vừa đăng"), seen="không rõ")
    gold = inter.fuse([a, b, c])
    assert gold["first_posted_at"] == "28/09/2026"
    assert gold["last_seen_at"] == "2026-11-07T02:00:00Z"
    assert len(gold["unparsed_dates"]) == 2
    assert inter.fuse([c])["first_posted_at"] == ""
    b["flat"]["raw_posted_date"] = "2026-09-09T08:59:43+07:00"
    assert inter.fuse([a, b])["first_posted_at"] == "2026-09-09T08:59:43+07:00"


def test_cdc_same_version_unchanged_is_not_violation(tmp_path):
    for n, desc in enumerate(("same", "same", "changed")):
        env = generic_env("7", f"2026-11-0{n + 1}T00:00:00Z", 1, desc=desc)
        (tmp_path / f"{n}.json").write_text(json.dumps(env), encoding="utf-8")
    report = cdc_chain_audit("src_a", tmp_path)
    assert report["hop_same_version"] == 2
    assert report["hop_version_not_bumped"] == 1
    assert report["hop_same_canonical_hash"] == 1


def test_reposts_follow_cross_source_loser(sandbox):
    rows = [jobsgo_env("old", seen="2026-10-10T00:00:00Z"), jobsgo_env("new")]
    (dedup.IN_DIR / "jobsgo.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    dedup.run(["itviec", "jobsgo"], dry_run=False)
    gold = load_out(dedup.OUT_DIR / "golden_master_jobs.jsonl")
    master = next(g for g in gold if "jobsgo:new" in g["source_job_ids"])
    assert any(r["source"] == "jobsgo" and r["job_id"] == "old" for r in master["repost_records"])
    output = load_out(dedup.OUT_DIR / "itviec.jsonl")
    winner = next(e for e in output if e["metadata"]["dedup"]["master_id"] == master["master_id"])
    assert winner["metadata"]["dedup"]["repost_records"] == master["repost_records"]
    assert sum(g["duplicate_count"] + len(g["repost_records"]) for g in gold) == 5


def test_partial_preserves_all_dedup_reports(sandbox):
    dedup.run(["itviec", "jobsgo"], dry_run=False)
    main = sandbox / "reports" / dedup.STEP
    before = {p.name: p.read_bytes() for p in main.glob("*.json")}
    dedup.main(["--source", "itviec", "--dry-run"])
    assert before == {p.name: p.read_bytes() for p in main.glob("*.json")}
    assert (sandbox / "reports" / "_partial" / dedup.STEP / "_all.json").exists()


def test_partial_preserves_all_clean_reports(sandbox, monkeypatch):
    monkeypatch.setattr(clean, "DATA_DIR", sandbox / "raw_data")
    monkeypatch.setattr(clean, "OUT_DIR", sandbox / "clean_out")
    monkeypatch.setattr(clean, "REVIEW_DIR", sandbox / "review")
    monkeypatch.setattr(clean, "POLICY_PATH", sandbox / "policy.json")
    monkeypatch.setattr(clean, "SOURCES", ["itviec", "jobsgo"])
    for src, env in (("itviec", itviec_env("a")), ("jobsgo", jobsgo_env("b"))):
        raw = clean.DATA_DIR / src / "raw"
        raw.mkdir(parents=True)
        (raw / "job.json").write_text(json.dumps(env), encoding="utf-8")
    clean.run(clean.SOURCES, dry_run=False)
    main = sandbox / "reports" / clean.STEP
    before = {p.name: p.read_bytes() for p in main.glob("*.json")}
    clean.main(["--source", "itviec", "--dry-run"])
    assert before == {p.name: p.read_bytes() for p in main.glob("*.json")}
    partial = json.loads((sandbox / "reports" / "_partial" / clean.STEP / "_all.json").read_text(encoding="utf-8"))
    assert partial["extra"]["partial_run"] is True
    with pytest.raises(SystemExit) as exc:
        clean.main(["--source", "itviec"])
    assert exc.value.code == 2


def test_precision_metrics_distinguish_classes_and_no_labels():
    rows = [{"it_status": predicted, "nhan_tay": actual} for predicted, actual in
            [("it", "it"), ("it", "non_it"), ("non_it", "it"),
             ("non_it", "non_it"), ("non_it", "non_it"), ("it", "")]]
    metrics = label_review.validation_metrics(rows)
    assert metrics == {"tp": 1, "fp": 1, "tn": 2, "fn": 1, "labeled": 5,
                       "precision_it": .5, "precision_non_it": 2 / 3, "recall_it": .5,
                       "precision_it_ci": label_review.wilson_ci(1, 2),
                       "precision_non_it_ci": label_review.wilson_ci(2, 3),
                       "recall_it_ci": label_review.wilson_ci(1, 2),
                       "reason": None}
    empty = label_review.validation_metrics([{"it_status": "it", "nhan_tay": ""}])
    assert empty["reason"] == "NO_LABELS" and empty["precision_it"] is None
    assert empty["precision_it_ci"] is None  # mẫu trống: "chưa đo", không phải 0%


def test_wilson_ci_reports_small_sample_honestly():
    ci = label_review.wilson_ci
    assert ci(0, 0) is None
    with pytest.raises(ValueError):
        ci(5, 0)  # số đúng không thể lớn hơn tổng số đã đo
    lo, hi = ci(1, 2)
    assert 0.0 <= lo < 0.5 < hi <= 1.0                      # mẫu nhỏ thì khoảng rộng
    assert ci(10, 10)[0] > ci(10, 20)[0]                    # thêm dòng siết cận dưới lại
    assert ci(1, 100)[0] < 0.5 < ci(99, 100)[0] < 1.0       # hiếm khi gặp vẫn không âm
    # Ý nghĩa nghiệp vụ (lead yêu cầu báo kèm KTC): mẫu 100 dòng tầng 1 IT chỉ KẾT LUẬN được
    # "precision IT >= 95%" khi cả 100 dòng đều đúng; sai 1 dòng là cận dưới tụt dưới 95%.
    assert ci(100, 100)[0] >= 0.95 and ci(99, 100)[0] < 0.95
    assert ci(197, 200)[0] >= 0.95 and ci(196, 200)[0] < 0.95  # 200 dòng chịu được tối đa 3 lỗi


def test_cosine_stats_count_before_threshold():
    a, b = item("itviec", "a"), item("jobsgo", "b", flat(jd="Completely unrelated document " * 4, req=""))
    stats = {}
    assert inter.cross_source_pairs([a, b], threshold=1.01, stats=stats) == []
    assert stats == {"cosine_blocks": 1, "cosine_pairs_computed": 1, "cross_pairs_evaluated": 1}
