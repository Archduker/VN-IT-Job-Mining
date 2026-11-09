"""Create conservative, compact review tables without modifying review inputs."""

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from preprocessing.encoding.skills_taxonomy_230 import ALIAS_CONFLICTS, TAXONOMY_230


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / "reports/preprocessing/05_encoding/review_2026-11-08"
    paths = [base / name for name in ["candidate_generated.csv", "candidate_decisions.csv"]]
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    candidates, decisions = [pd.read_csv(p, keep_default_na=False) for p in paths]
    assert candidates.value.is_unique and decisions.value.is_unique
    assert set(decisions.value) <= set(candidates.value)
    decisions = decisions.set_index("value").to_dict("index")
    snap = base.parent / "snapshot_audit_2026-11-08"
    manifest = json.loads((snap / "manifest.json").read_text())
    frames = []
    for entry in manifest:
        p = snap / (entry["key"].split("/")[1] + ".parquet")
        assert hashlib.sha256(p.read_bytes()).hexdigest() == entry["sha256"]
        frames.append(pd.read_parquet(p, columns=["job_id_global", "skills_std"]))
    df = pd.concat(frames, ignore_index=True)
    assert df.job_id_global.is_unique and df.job_id_global.notna().all()
    rows = [set(map(str, s)) for s in df.skills_std]
    counts = Counter(s for row in rows for s in row)
    assert dict(zip(candidates.value, candidates.jobs, strict=True)) == dict(counts)
    shared = json.loads((root / "preprocessing/dictionaries/skills.json").read_text())
    known = {s.casefold(): s for s in shared}
    entries = {e.canonical: e for e in TAXONOMY_230}
    for name in entries:
        known.setdefault(name.casefold(), name)
    # Clear same-technology aliases, all already present in repository prototype.
    safe_aliases = {
        "reactjs": "React",
        "react.js": "React",
        "vuejs": "Vue",
        "vue.js": "Vue",
        "nodejs": "Node.js",
        "k8s": "Kubernetes",
        "postgres": "PostgreSQL",
        "amazon web services": "AWS",
    }
    group_names = dict(
        zip(
            [
                "programming_languages",
                "frameworks_libraries",
                "databases_streaming",
                "cloud_devops_security",
                "tools_architecture_qa",
                "methodologies_softskills_data",
            ],
            [
                "Programming Languages",
                "Frameworks & Libraries",
                "Databases & Caching",
                "Cloud & DevOps",
                "Tools, Architecture & Protocols",
                "Methodologies & Soft Skills",
            ],
            strict=True,
        )
    )
    merged, issues, excluded, reserve = defaultdict(set), defaultdict(set), [], []
    for value in counts:
        d = decisions.get(value, {})
        lower = value.casefold()
        if d.get("decision") == "reject":
            excluded.append(
                dict(value=value, jobs=counts[value], reason="Phát đã reject trong bảng quyết định")
            )
            continue
        if d.get("decision") or d.get("edit_canonical"):
            # Do not silently interpret an unfamiliar manual decision.
            excluded.append(
                dict(
                    value=value,
                    jobs=counts[value],
                    reason="Có quyết định/edit thủ công: cần đối chiếu riêng, không tự diễn giải",
                )
            )
            continue
        if lower in ALIAS_CONFLICTS:
            excluded.append(
                dict(
                    value=value,
                    jobs=counts[value],
                    reason="Collision: problem_solving / logical_thinking; đề xuất tạm loại đến khi duyệt nghĩa",
                )
            )
            continue
        if lower == "machine learning":
            excluded.append(
                dict(
                    value=value,
                    jobs=counts[value],
                    reason="Upstream gộp TensorFlow/PyTorch và ML; đề xuất tạm tách khỏi shortlist cho tới khi duyệt phạm vi",
                )
            )
            continue
        canonical = known.get(lower) or safe_aliases.get(lower)
        if canonical:
            merged[canonical].add(value)
            issues[canonical].add("proposed; chưa approved")
            if canonical not in entries:
                issues[canonical].add("nhóm chưa xác định theo prototype")
            if value != canonical:
                issues[canonical].add("duyệt gộp cách viết/alias cùng công nghệ")
        elif re.search(
            r"accepted|internship|fresher|developer|engineer|tester|analyst|quảng cáo|marketing|ngân hàng|tài chính",
            lower,
        ):
            excluded.append(
                dict(
                    value=value,
                    jobs=counts[value],
                    reason="Đề xuất loại: tag vị trí/cấp bậc/ngành, chưa đủ căn cứ là kỹ năng độc lập",
                )
            )
        elif lower in {"ai", "cloud", "database", "security", "game", "...)"}:
            excluded.append(
                dict(
                    value=value,
                    jobs=counts[value],
                    reason="Đề xuất tạm loại: quá rộng/mơ hồ hoặc tag lỗi; cần xác định nghĩa",
                )
            )
        else:
            reserve.append(
                dict(
                    canonical=value,
                    so_job=counts[value],
                    nhom="",
                    alias_duoc_gop="",
                    van_de_can_duyet="Dự phòng unresolved: giá trị quan sát; chưa xác minh canonical/group, chưa gộp alias",
                )
            )
    compact = []
    for canonical, aliases in merged.items():
        jobs = sum(bool(row & aliases) for row in rows)
        entry = entries.get(canonical)
        compact.append(
            dict(
                canonical=canonical,
                so_job=jobs,
                nhom=group_names[entry.group] if entry else "Chưa phân nhóm",
                alias_duoc_gop=" | ".join(sorted(aliases - {canonical})),
                van_de_can_duyet="; ".join(sorted(issues[canonical])),
            )
        )
    compact.sort(key=lambda x: (-x["so_job"], x["canonical"]))
    # Canonical names in shared/prototype may still be synonyms of each other;
    # make cross-taxonomy overlap explicit, do not silently merge meanings.
    for row in compact:
        targets = {
            e.canonical
            for e in TAXONOMY_230
            if row["canonical"].casefold() in {a.casefold() for a in e.aliases}
            and e.canonical != row["canonical"]
        }
        if targets:
            row["van_de_can_duyet"] += "; có thể trùng canonical khác: " + " | ".join(
                sorted(targets)
            )
    reserve.sort(key=lambda x: (-x["so_job"], x["canonical"]))
    excluded.sort(key=lambda x: (-x["jobs"], x["value"]))
    out = base / "short_review"
    out.mkdir(exist_ok=True)
    pd.DataFrame(compact[:230]).to_csv(out / "canonical_shortlist.csv", index=False)
    pd.DataFrame(excluded).to_csv(out / "ambiguous_and_exclusions.csv", index=False)
    pd.DataFrame(reserve[:30]).to_csv(out / "reserves.csv", index=False)
    for p in paths:
        assert hashlib.sha256(p.read_bytes()).hexdigest() == hashes[p.name]
    summary = f"""# Review ngắn vocabulary P5 — proposed

- Có **{len(compact[:230])} canonical ứng viên có căn cứ tên từ shared dictionary/prototype và có quan sát thực tế**; còn thiếu ít nhất **{max(0, 230 - len(compact[:230]))}** so với 230. Đây chưa phải số skill hợp lệ đã được Phát duyệt; synonym/cross-taxonomy và nhóm còn cần rà soát nên số cuối có thể thấp hơn.
- `canonical_shortlist.csv`: đúng năm cột yêu cầu; số job tính bằng hợp các ID sau mapping, không cộng frequency alias gây đếm trùng. Chỉ gộp cách viết canonical không phân biệt hoa/thường và tám alias cùng công nghệ đã tồn tại trong repo. Không tự tách skill từ JD.
- `ambiguous_and_exclusions.csv`: các giá trị mơ hồ/collision/upstream gộp và đề xuất loại tag ngành/vị trí. Các lý do là đề xuất, không phải quyết định đã duyệt. Không phục hồi Machine Learning thành TensorFlow/PyTorch.
- `reserves.csv`: tối đa 30 giá trị quan sát dự phòng, unresolved; không dùng để lấp đủ 230. Tần suất cao không đủ để xác nhận skill.
- Nhóm trong shortlist lấy crosswalk sáu nhóm prototype, vẫn proposed; thiếu căn cứ thì ghi Chưa phân nhóm. Canonical dùng chung có thể khác phạm vi prototype nên cần Phát duyệt.
- Không có mục nào được tự đánh approved. Hai CSV gốc giữ nguyên bytes. Script tái lập: `.venv/bin/python -m preprocessing.encoding.short_candidate_review`.

## Input và xác thực

Snapshot: 8 partitions P4, {len(df)} jobs; SHA mỗi partition kiểm lại từ manifest; frequency toàn bộ candidate_generated khớp snapshot. SHA-256 CSV nguồn:
{chr(10).join("- " + name + ": `" + digest + "`" for name, digest in hashes.items())}
"""
    (out / "README.md").write_text(summary, encoding="utf-8")
    print(
        "shortlist",
        len(compact[:230]),
        "shortfall",
        max(0, 230 - len(compact[:230])),
        "reserves",
        len(reserve[:30]),
        "path",
        out,
    )


if __name__ == "__main__":
    main()
