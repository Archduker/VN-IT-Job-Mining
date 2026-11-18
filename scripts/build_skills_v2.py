#!/usr/bin/env python3
"""Dựng `processing/dictionaries/skills_v2.json` từ quyết định đọc ứng viên (K8.13). Chỉ ghi trên máy.

Đầu vào:
- `data/processing/skill_candidates/candidates.tsv` (sinh bởi `scripts/mine_skill_candidates.py`), số dòng tính từ 1.
- `processing/dictionaries/skills_v2_decisions/*.txt`: mỗi lô một file, mỗi dòng một lệnh (`#` là chú thích):

    S <dòng> <slug> <nhóm> [p=<slug cha>] [n=<tên hiển thị, tới hết dòng>]   kỹ năng mới, khóa của dòng là alias
    A <dòng...> <slug>                                                      các dòng là alias của slug
    N <lý do> <dòng...>                                                     không phải kỹ năng
    Q <dòng> <ghi chú>                                                      cần người dùng chọn (dòng vẫn phải có S/A/N)
    K <slug> <nhóm> [p=<slug cha>] [n=<tên>]                                kỹ năng không đến từ một dòng (thường là kỹ năng cha)
    L <slug> <alias>;<alias>...                                             alias thêm (đã fold khi khớp)
    F <slug> <dạng>;<dạng>...                                               dạng khớp phân biệt hoa thường (K8.3); bỏ alias fold trùng

  `<dòng...>` nhận số đơn hoặc khoảng `12-15`.

Alias ngắn (dưới 4 ký tự, không có `# + .`) tự chuyển sang `short_aliases` với dạng viết gốc hay gặp nhất,
trừ khi dạng đó toàn chữ thường (khi đó bỏ, ghi cảnh báo).

Đầu ra: `processing/dictionaries/skills_v2.json` (`_meta.approved` = false) và
`processing/dictionaries/skills_v2_decisions.tsv` (khóa → quyết định, không phụ thuộc số dòng).

    python scripts/build_skills_v2.py [--check]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import unicodedata
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from preprocessing.deduplication.text_norm import fold  # noqa: E402

CAND = ROOT / "data" / "processing" / "skill_candidates" / "candidates.tsv"
DEC_DIR = ROOT / "processing" / "dictionaries" / "skills_v2_decisions"
OUT = ROOT / "processing" / "dictionaries" / "skills_v2.json"
OUT_TSV = ROOT / "processing" / "dictionaries" / "skills_v2_decisions.tsv"

GROUPS = {
    "programming_languages": "Ngôn ngữ lập trình",
    "frontend": "Frontend",
    "backend": "Backend, framework phía server",
    "mobile": "Mobile",
    "databases": "Cơ sở dữ liệu",
    "messaging": "Hàng đợi, streaming",
    "data_engineering": "Kỹ thuật dữ liệu",
    "data_science_ml": "Khoa học dữ liệu, học máy",
    "ai_genai": "AI tạo sinh, LLM",
    "ai_tools": "Công cụ AI hỗ trợ làm việc",
    "bi_analytics": "BI, phân tích",
    "cloud": "Cloud",
    "devops": "DevOps, hạ tầng như code, giám sát",
    "systems_network": "Hệ điều hành, mạng, quản trị hệ thống",
    "security": "Bảo mật",
    "testing_qa": "Kiểm thử, QA",
    "architecture_api": "Kiến trúc, API, nguyên lý thiết kế",
    "dev_tools": "Công cụ phát triển, cộng tác",
    "embedded_iot": "Nhúng, IoT, phần cứng",
    "enterprise_apps": "ERP, CRM, ứng dụng doanh nghiệp",
    "design_creative": "Thiết kế, UI/UX, đồ họa",
    "cad_engineering": "CAD, kỹ thuật",
    "game_dev": "Phát triển game",
    "blockchain": "Blockchain",
    "methodology_pm": "Phương pháp, quản lý dự án, phân tích nghiệp vụ",
    "certifications": "Chứng chỉ",
    "office_tools": "Tin học văn phòng",
    "digital_marketing": "Marketing số",
    "soft_skills": "Kỹ năng mềm",
    "languages": "Ngoại ngữ",
}
KIND_BY_GROUP = {"soft_skills": "soft", "languages": "language"}
REASONS = {
    "job_title": "chức danh, vai trò",
    "industry": "ngành, lĩnh vực kinh doanh",
    "benefit": "phúc lợi",
    "degree": "bằng cấp, chuyên ngành học",
    "generic": "từ chung, mảnh cụm",
    "combo": "cụm ghép nhiều kỹ năng (mỗi kỹ năng khớp riêng)",
    "entity": "tên công ty, sản phẩm, địa danh",
}
SLUG = re.compile(r"^[a-z0-9_]+$")


def is_safe_key(key: str) -> bool:
    return len(key) >= 4 or any(ch in key for ch in "#+.")


def rows_of(tokens):
    out = []
    for t in tokens:
        if re.fullmatch(r"\d+-\d+", t):
            a, b = map(int, t.split("-"))
            out.extend(range(a, b + 1))
        elif t.isdigit():
            out.append(int(t))
        else:
            raise ValueError(f"không phải số dòng: {t!r}")
    return out


def opts(tokens):
    """Tách p=..., n=... (n= lấy tới hết dòng)."""
    o, rest = {}, []
    for i, t in enumerate(tokens):
        if t.startswith("n="):
            o["n"] = " ".join([t[2:], *tokens[i + 1:]]).strip()
            break
        if t.startswith("p="):
            o["p"] = t[2:]
        else:
            rest.append(t)
    return o, rest


def load_candidates(path=CAND):
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        return [dict(x) for x in r]


def build(cands, lines):
    errors, warns = [], []
    n = len(cands)
    covered = {}
    skills, not_skill, can_hoi = {}, [], []
    alias_rows = []  # (slug, row)
    extra_alias, forced = {}, {}

    def new_skill(slug, group, o, where, row=None):
        if not SLUG.match(slug):
            errors.append(f"{where}: slug sai {slug!r}")
        if group not in GROUPS:
            errors.append(f"{where}: nhóm lạ {group!r}")
        if slug in skills:
            errors.append(f"{where}: slug trùng {slug!r}")
            return
        c = cands[row - 1] if row else None
        skills[slug] = {
            "slug": slug, "name": o.get("n") or (c["display"] if c else slug), "group": group,
            "kind": KIND_BY_GROUP.get(group, "technical"), "parent": o.get("p"),
            "_keys": [], "_forms": {}, "df": int(c["df"]) if c else 0,
            "examples": (c["examples"].split(" ‖ ")[:2] if c else []),
        }

    def cover(row, what, where):
        if not 1 <= row <= n:
            errors.append(f"{where}: dòng {row} ngoài 1..{n}")
        elif row in covered:
            errors.append(f"{where}: dòng {row} đã quyết ở {covered[row][1]}")
        else:
            covered[row] = (what, where)

    for where, line in lines:
        t = line.split()
        if not t:
            continue
        cmd, args = t[0], t[1:]
        try:
            if cmd == "S":
                o, rest = opts(args)
                row, slug, group = int(rest[0]), rest[1], rest[2]
                cover(row, f"skill:{slug}", where)
                new_skill(slug, group, o, where, row)
                alias_rows.append((slug, row))
            elif cmd == "K":
                o, rest = opts(args)
                new_skill(rest[0], rest[1], o, where)
            elif cmd == "A":
                slug = args[-1]
                for row in rows_of(args[:-1]):
                    cover(row, f"alias:{slug}", where)
                    alias_rows.append((slug, row))
            elif cmd == "N":
                reason = args[0]
                if reason not in REASONS:
                    errors.append(f"{where}: lý do lạ {reason!r}")
                for row in rows_of(args[1:]):
                    cover(row, f"not_skill:{reason}", where)
                    c = cands[row - 1] if 1 <= row <= n else None
                    if c:
                        not_skill.append({"key": c["key"], "display": c["display"], "reason": reason, "df": int(c["df"])})
            elif cmd == "Q":
                row = int(args[0])
                c = cands[row - 1]
                can_hoi.append({"key": c["key"], "display": c["display"], "df": int(c["df"]), "note": " ".join(args[1:]),
                                "_row": row})
            elif cmd == "L":
                extra_alias.setdefault(args[0], []).extend(a.strip() for a in " ".join(args[1:]).split(";") if a.strip())
            elif cmd == "F":
                forced.setdefault(args[0], []).extend(a.strip() for a in " ".join(args[1:]).split(";") if a.strip())
            else:
                errors.append(f"{where}: lệnh lạ {cmd!r}")
        except (IndexError, ValueError) as e:
            errors.append(f"{where}: {e}")

    for slug, row in alias_rows:
        if slug not in skills:
            errors.append(f"dòng {row}: slug chưa định nghĩa {slug!r}")
            continue
        c = cands[row - 1]
        skills[slug]["_keys"].append(c["key"])
        skills[slug]["_forms"][c["key"]] = c["display"]
        skills[slug]["df"] = max(skills[slug]["df"], int(c["df"]))
    for slug, al in extra_alias.items():
        if slug not in skills:
            errors.append(f"L: slug chưa định nghĩa {slug!r}")
            continue
        for a in al:
            k = " ".join(fold(a).split())
            skills[slug]["_keys"].append(k)
            # alias ngắn viết thường trong lệnh L (bdd, hld) là viết tắt: khớp dạng chữ hoa
            skills[slug]["_forms"].setdefault(k, a if is_safe_key(k) or a != a.lower() else a.upper())
    for slug in forced:
        if slug not in skills:
            errors.append(f"F: slug chưa định nghĩa {slug!r}")

    owner = {}
    out_skills = []
    for slug, s in skills.items():
        forms_forced = forced.get(slug, [])
        folded_forced = {" ".join(fold(f).split()) for f in forms_forced}
        aliases, shorts = [], list(forms_forced)
        for k in dict.fromkeys(s.pop("_keys")):
            if k in folded_forced:
                continue
            if is_safe_key(k):
                aliases.append(k)
            else:
                form = s["_forms"].get(k, k)
                if form == form.lower():
                    warns.append(f"{slug}: alias ngắn {k!r} chỉ có dạng chữ thường, bỏ")
                    continue
                shorts.append(form)
        forms = s.pop("_forms")
        # dạng gốc có dấu của alias an toàn: matcher loại chỗ khớp có dấu khác ("nghệ" ≠ "nghe")
        alias_forms = {}
        for a in aliases:
            f = unicodedata.normalize("NFC", forms.get(a, a)).lower()
            if not f.isascii() and " ".join(fold(f).split()) == a:
                alias_forms[a] = f
        for a in aliases:
            owner.setdefault(("safe", a), set()).add(slug)
        for f in shorts:
            owner.setdefault(("short", f), set()).add(slug)
        if s["parent"] and s["parent"] not in skills:
            errors.append(f"{slug}: parent chưa định nghĩa {s['parent']!r}")
        out_skills.append({**s, "aliases": sorted(set(aliases)), "short_aliases": sorted(set(shorts)),
                           "alias_forms": dict(sorted(alias_forms.items()))})
    for (kind, a), owners in owner.items():
        if len(owners) > 1:
            errors.append(f"alias {a!r} ({kind}) thuộc nhiều kỹ năng: {sorted(owners)}")
    for s in out_skills:
        seen, cur = set(), s["slug"]
        while cur:
            if cur in seen:
                errors.append(f"vòng parent ở {s['slug']}")
                break
            seen.add(cur)
            cur = skills.get(cur, {}).get("parent")
        if not s["aliases"] and not s["short_aliases"]:
            warns.append(f"{s['slug']}: không có alias nào")

    progress = 0
    while progress + 1 in covered:
        progress += 1
    return {
        "errors": errors, "warns": warns, "covered": covered, "progress": progress,
        "skills": sorted(out_skills, key=lambda s: (list(GROUPS).index(s["group"]) if s["group"] in GROUPS else 99,
                                                   -s["df"], s["slug"])),
        "not_skill": sorted(not_skill, key=lambda x: (-x["df"], x["key"])),
        "can_hoi": can_hoi,
    }


def read_lines(dec_dir=DEC_DIR):
    lines = []
    for p in sorted(Path(dec_dir).glob("*.txt")):
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            ln = ln.split("#", 1)[0].strip() if not ln.lstrip().startswith(("F ", "L ")) else ln.strip()
            if ln:
                lines.append((f"{p.name}:{i}", ln))
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="chỉ kiểm, không ghi")
    a = ap.parse_args()
    cands = load_candidates()
    res = build(cands, read_lines())
    for w in res["warns"]:
        print("CẢNH BÁO", w)
    for e in res["errors"]:
        print("LỖI", e)
    print(f"đã quyết {len(res['covered'])}/{len(cands)} dòng; đọc liên tục tới dòng {res['progress']}; "
          f"kỹ năng {len(res['skills'])}; not_skill {len(res['not_skill'])}; can_hoi {len(res['can_hoi'])}")
    if res["errors"]:
        sys.exit(1)
    if a.check:
        return
    for q in res["can_hoi"]:
        q["decision"] = res["covered"].get(q.pop("_row"), ("?",))[0]
    doc = {
        "_meta": {
            "version": "2.0.0-draft",
            "approved": False,
            "updated": dt.date.today().isoformat(),
            "spec": "docs/spec/processing/08_skills.md mục 2.3 (K8.11–K8.16)",
            "candidates": "data/processing/skill_candidates/candidates.tsv (scripts/mine_skill_candidates.py, DF >= 2)",
            "n_candidates": len(cands),
            "read_progress": res["progress"],
            "n_decided": len(res["covered"]),
            "groups": GROUPS,
            "not_skill_reasons": REASONS,
            "match": "aliases: khớp trên văn bản fold, nguyên từ; short_aliases: khớp phân biệt hoa thường trên văn bản gốc",
        },
        "skills": res["skills"],
        "not_skill": res["not_skill"],
        "can_hoi": res["can_hoi"],
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    with OUT_TSV.open("w", encoding="utf-8", newline="") as f:
        f.write("key\tdisplay\tdf\tdecision\n")
        for row in sorted(res["covered"]):
            c = cands[row - 1]
            f.write(f"{c['key']}\t{c['display']}\t{c['df']}\t{res['covered'][row][0]}\n")
    print("ghi", OUT.relative_to(ROOT), "và", OUT_TSV.relative_to(ROOT))


if __name__ == "__main__":
    main()
