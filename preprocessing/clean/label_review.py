"""Trợ giúp gán nhãn TAY mẫu kiểm định bộ lọc IT 2 tầng (luật C4b, docs/tasks/02 mục 3.4).

File mẫu do bước 01 Clean xuất ở `data/preprocessing/review/it_<nguồn>.csv`, cột `nhan_tay`
để trống. Chỉ tiêu nghiệm thu là Precision >= 95% trên nhãn tay, nên công cụ này **không tự
gán nhãn** - nó chỉ hiển thị từng mẫu (tiêu đề + kỹ năng + quyết định của bộ lọc) và ghi câu
trả lời của người vào đúng định dạng mà `preprocessing/clean/run.py` đọc lại.

Chạy:
    python -m preprocessing.clean.label_review --status              # đếm số dòng đã nhãn + Precision
    python -m preprocessing.clean.label_review --source itviec       # dán nhãn từng dòng
    python -m preprocessing.clean.label_review --source itviec --limit 40

Phím: i = it, n = non_it, r = bỏ qua (quay lại sau), q = lưu và thoát, h = xem rubric.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from preprocessing.common import REPO_ROOT, SOURCES

REVIEW_DIR = REPO_ROOT / "data" / "preprocessing" / "review"
FIELD = "nhan_tay"
ANSWER = {"i": "it", "n": "non_it"}

RUBRIC = """Rubric (chỉ dựa vào tiêu đề + kỹ năng của chính tin đó, không mở web):
  it      - làm về phần mềm/dữ liệu/hạ tầng CNTT: developer, QA/tester, data, DevOps, security,
            AI/ML, PM/BA/BrSE cho sản phẩm phần mềm, quản lý kỹ thuật, IT helpdesk/quản trị mạng.
  non_it  - marketing, bán hàng, hành chính, kế toán, nhân sự, giáo viên, cơ khí/xây dựng/y tế
            không gắn với phần mềm, tin chung chung không có kỹ thuật.
  r       - chưa chắc: bỏ qua, để lại lượt duyệt sau (không tính vào Precision).
"""


def path_for(source: str) -> Path:
    return REVIEW_DIR / f"it_{source}.csv"


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    """Ghi lại giữ nguyên thứ tự cột; ghi tạm rồi thay để không hỏng file giữa chừng."""
    if not rows:
        return
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def status(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {"rows": 0, "labeled": 0, "it": 0, "non_it": 0, "agree": 0, "disagree": 0}
    rows = read_rows(path)
    labeled = [r for r in rows if (r.get(FIELD) or "").strip() in ANSWER.values()]
    agree = sum((r.get(FIELD) or "").strip() == r["it_status"] for r in labeled)
    return {"rows": len(rows), "labeled": len(labeled),
            "it": sum(r[FIELD] == "it" for r in labeled),
            "non_it": sum(r[FIELD] == "non_it" for r in labeled),
            "agree": agree, "disagree": len(labeled) - agree}


def precision(path: Path) -> float | None:
    """Precision IT = đúng IT / tổng dự đoán IT trong phần có nhãn tay."""
    return validation_metrics(read_rows(path))["precision_it"]


def validation_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Chỉ đo từ nhãn từng tin; không dùng ghi chú tổng hợp trong it_policy.json."""
    matrix = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for row in rows:
        actual, predicted = row.get(FIELD, "").strip(), row.get("it_status", "").strip()
        if actual not in ANSWER.values() or predicted not in ANSWER.values():
            continue
        key = ("tp" if actual == "it" else "fp") if predicted == "it" else (
            "fn" if actual == "it" else "tn")
        matrix[key] += 1
    tp, fp, tn, fn = (matrix[k] for k in ("tp", "fp", "tn", "fn"))
    return {
        **matrix, "labeled": sum(matrix.values()),
        "precision_it": tp / (tp + fp) if tp + fp else None,
        "precision_non_it": tn / (tn + fn) if tn + fn else None,
        "recall_it": tp / (tp + fn) if tp + fn else None,
        "reason": "NO_LABELS" if not sum(matrix.values()) else None,
    }


def show(row: dict[str, Any]) -> str:
    skills = (row.get("skills") or "").strip() or "(không có kỹ năng)"
    return (f"  tiêu đề : {row['job_title']}\n"
            f"  kỹ năng : {skills[:180]}\n"
            f"  bộ lọc  : it_rule={row['it_rule']} level={row['it_rule_level']} -> {row['it_status']}\n"
            f"  link    : {row['source_url']}")


def label_interactive(path: Path, limit: int, redo: bool = False) -> int:
    rows = read_rows(path)
    todo = [i for i, r in enumerate(rows)
            if redo or (r.get(FIELD) or "").strip() not in ANSWER.values()]
    if limit:
        todo = todo[:limit]
    print(f"{path.name}: {len(todo)} dòng cần xem (đã nhãn {status(path)['labeled']}/{len(rows)})\n")
    done = 0
    for n, idx in enumerate(todo, 1):
        row = rows[idx]
        print(f"[{n}/{len(todo)}] job_id={row['job_id']}")
        print(show(row))
        while True:
            try:
                key = input("  [i]t / [n]on_it / [r]ồi tính lại / [q]thoát / [h]rubric: ").strip().lower()
            except EOFError:  # chạy trong pipe/CI: dừng lịch sự, nhãn đã lưu giữ nguyên
                print("\n  hết input phiên tương tác -> dừng (mọi nhãn đã ghi trước đó vẫn còn)")
                return done
            if key == "h":
                print(RUBRIC)
            elif key == "q":
                write_rows(path, rows)
                print(f"  đã lưu {done} nhãn vào {_rel(path)}")
                return done
            elif key == "r":
                break
            elif key in ANSWER:
                rows[idx][FIELD] = ANSWER[key]
                write_rows(path, rows)  # lưu ngay, gián phiên cũng không mất nhãn
                done += 1
                break
        print()
    st = status(path)
    print(f"đã nhãn {st['labeled']}/{st['rows']} | đồng ý với bộ lọc {st['agree']}, bất đồng {st['disagree']}")
    p = precision(path)
    print(f"Precision trên mẫu đã nhãn: {'chưa đo được' if p is None else f'{p:.1%}'}"
          f"  (ngưỡng nghiệm thu 95%)")
    return done


def precision_counts(path: Path) -> tuple[int, int]:
    """(số tin người gọi là it, số tin bộ lọc giữ it) trên phần đã nhãn - để cộng dồn đa nguồn."""
    rows = [r for r in read_rows(path) if (r.get(FIELD) or "").strip() in ANSWER.values()]
    kept = [r for r in rows if r["it_status"] == "it"]
    return sum(r[FIELD].strip() == "it" for r in kept), len(kept)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default="all", choices=[*SOURCES, "all"])
    parser.add_argument("--status", action="store_true", help="chỉ đếm nhãn + Precision, không hỏi")
    parser.add_argument("--limit", type=int, default=0, help="giới hạn số dòng hỏi trong một lần chạy")
    parser.add_argument("--redo", action="store_true", help="hỏi lại cả dòng đã có nhãn")
    args = parser.parse_args(argv)
    sources = list(SOURCES) if args.source == "all" else [args.source]

    missing = [s for s in sources if not path_for(s).is_file()]
    if missing:
        print(f"chưa có mẫu cho {', '.join(missing)} - chay: python -m preprocessing.clean.run --source {missing[0]}")
        return 1
    if args.status:
        tot = {"rows": 0, "labeled": 0}
        all_rows = []
        num = den = 0
        for s in sources:
            st = status(path_for(s))
            all_rows.extend(read_rows(path_for(s)))
            hit, kept = precision_counts(path_for(s))
            num += hit
            den += kept
            tot["rows"] += st["rows"]
            tot["labeled"] += st["labeled"]
            p = hit / kept if kept else None
            print(f"{s:14s} dòng {st['rows']:3d} | đã nhãn {st['labeled']:3d} "
                  f"| it {st['it']:3d} non_it {st['non_it']:3d} | bộ lọc trùng người {st['agree']}/{st['labeled']}"
                  f" | Precision {('n/a' if p is None else f'{p:.1%}')} ({hit}/{kept})")
        rate = num / den if den else None
        print(f"TỔNG: {tot['labeled']}/{tot['rows']} dòng có nhãn tay | "
              f"Precision cộng dồn {'chưa đo được' if rate is None else f'{rate:.1%}'} ({num}/{den})"
              f" - ngưỡng nghiệm thu 95%")
        metrics = validation_metrics(all_rows)
        print(f"Confusion matrix (IT là lớp dương): TP={metrics['tp']} FP={metrics['fp']} "
              f"TN={metrics['tn']} FN={metrics['fn']}")
        for key in ("precision_it", "precision_non_it", "recall_it"):
            value = metrics[key]
            print(f"{key}: {'chưa đo được (mẫu số bằng 0)' if value is None else f'{value:.1%}'}")
        print("Chỉ tiêu tính từ nhãn từng tin; ghi chú policy không thay thế bằng chứng nghiệm thu.")
        if tot["labeled"] < 100:
            print("-> cần >= 100 dòng theo docs/tasks/02 mục 3.4; chạy: "
                  "python -m preprocessing.clean.label_review --source <san>")
        return 0
    for s in sources:
        label_interactive(path_for(s), args.limit, args.redo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
