#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Công cụ gán nhãn tay IT / Non-IT cho bước review Clean C4b (VN-IT-Job-Mining).

Tệp đích: data/preprocessing/review/it_<nguồn>.csv (cột 'nhan_tay' là 'it' hoặc 'non_it').
Đặc tả: docs/preprocessing/spec/P1_clean.md & docs/prompting/P1_clean.md.

Tính năng:
1. Terminal Interactive (TUI 1 phím bấm): Nhấn '1'/'i' (IT), '2'/'n' (Non-IT), không cần gõ Enter.
2. Web UI (--web): Giao diện web trực quan, phím tắt cực nhanh, xem toàn cảnh 8 nguồn.
3. Thống kê (--stats): Xem tiến độ gán nhãn và độ đúng của luật từ khóa.
4. Gợi ý tự động (--auto-obvious): Nhận diện các chức danh 100% ngoài IT (kế toán, lái xe, giáo viên...).
5. Sinh chính sách (--generate-policy): Đề xuất và ghi it_policy.json sau khi duyệt.

Cách dùng:
    python scripts/label_tool.py                 # TUI gán nhãn nhanh qua terminal (mặc định chỉ tin chưa gán)
    python scripts/label_tool.py --source topdev # Gán nhãn riêng nguồn topdev
    python scripts/label_tool.py --web           # Bật Web UI tại http://localhost:8765
    python scripts/label_tool.py --stats         # Xem bảng tiến độ 8 nguồn
    python scripts/label_tool.py --auto-obvious  # Xem trước gợi ý các tin ngoài IT rõ ràng
    python scripts/label_tool.py --generate-policy --apply # Ghi preprocessing/clean/it_policy.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import select
import sys
import unicodedata
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEW_DIR = REPO_ROOT / "data" / "preprocessing" / "review"
POLICY_PATH = REPO_ROOT / "preprocessing" / "clean" / "it_policy.json"

SOURCES = (
    "careerviet",
    "glints",
    "itviec",
    "jobsgo",
    "topcv",
    "topdev",
    "vieclam24h",
    "vietnamworks",
)

FIELDS = ["job_id", "source_url", "job_title", "skills", "it_rule", "it_prob", "it_status", "nhan_tay"]

# Danh sách từ khóa chức danh 100% ngoài IT (an toàn tuyệt đối để tự động nhận diện)
OBVIOUS_NON_IT_PATTERNS = [
    r"\bkế toán\b", r"\bke toan\b", r"\baccountant\b", r"\baccounting\b", r"\bkiểm toán\b",
    r"\btài xế\b", r"\blái xe\b", r"\bdriver\b",
    r"\bgiáo viên\b", r"\bgiảng viên\b", r"\bteacher\b", r"\bgia sư\b", r"\bmầm non\b",
    r"\bbảo vệ\b", r"\btạp vụ\b", r"\blễ tân\b", r"\breceptionist\b",
    r"\bthủ kho\b", r"\bphụ kho\b", r"\bnhân viên kho\b",
    r"\bđầu bếp\b", r"\bbếp\b", r"\bphục vụ\b", r"\bphe chế\b", r"\bbarista\b",
    r"\bcông nhân\b", r"\bmay mặc\b", r"\bthợ may\b",
    r"\bbác sĩ\b", r"\by tá\b", r"\bđiều dưỡng\b", r"\bdược sĩ\b",
    r"\btelesales\b", r"\bchăm sóc khách hàng\b", r"\bcskh\b",
]
OBVIOUS_NON_IT_RE = re.compile("|".join(OBVIOUS_NON_IT_PATTERNS), re.I)

# Từ khóa chắc chắn là IT (để không bao giờ nhận diện nhầm "kinh doanh phần mềm" hoặc "kỹ sư CNTT")
TECH_PROTECT_RE = re.compile(
    r"\b(software|developer|dev|lập trình|programmer|tester|qa|qc|devops|sre|backend|frontend|fullstack|"
    r"data engineer|data scientist|ai engineer|machine learning|cloud|sysadmin|dba|cntt|it support|mis|"
    r"hệ thống thông tin)\b",
    re.I
)


# ---------------------------------------------------------------- IO & Data
def get_review_file(source: str) -> Path:
    return REVIEW_DIR / f"it_{source}.csv"


def load_rows(source: str) -> List[Dict[str, str]]:
    path = get_review_file(source)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def save_rows(source: str, rows: List[Dict[str, str]]) -> None:
    path = get_review_file(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".csv.tmp")
    with temp_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            # Chỉ ghi các trường chuẩn
            row_dict = {f: r.get(f, "") for f in FIELDS}
            writer.writerow(row_dict)
    os.replace(temp_path, path)


def get_source_stats(source: str) -> Dict[str, Any]:
    rows = load_rows(source)
    total = len(rows)
    labeled = [r for r in rows if (r.get("nhan_tay") or "").strip() in {"it", "non_it"}]
    it_count = sum(1 for r in labeled if r["nhan_tay"].strip() == "it")
    non_it_count = sum(1 for r in labeled if r["nhan_tay"].strip() == "non_it")
    unlabeled = total - len(labeled)

    # Đo độ trùng khớp giữa nhan_tay và it_rule
    rule_matches = sum(1 for r in labeled if r.get("it_rule") == r["nhan_tay"].strip())
    rule_accuracy = (rule_matches / len(labeled) * 100) if labeled else 0.0

    return {
        "source": source,
        "total": total,
        "labeled": len(labeled),
        "unlabeled": unlabeled,
        "it": it_count,
        "non_it": non_it_count,
        "rule_matches": rule_matches,
        "rule_accuracy": rule_accuracy,
        "progress_pct": (len(labeled) / total * 100) if total else 0.0,
    }


def get_all_stats() -> List[Dict[str, Any]]:
    return [get_source_stats(s) for s in SOURCES]


# ---------------------------------------------------------------- Bảng thống kê
def print_stats_table() -> None:
    stats_list = get_all_stats()
    total_rows = sum(s["total"] for s in stats_list)
    total_labeled = sum(s["labeled"] for s in stats_list)
    total_it = sum(s["it"] for s in stats_list)
    total_non_it = sum(s["non_it"] for s in stats_list)
    total_unlabeled = sum(s["unlabeled"] for s in stats_list)
    overall_pct = (total_labeled / total_rows * 100) if total_rows else 0.0

    policy = {}
    if POLICY_PATH.exists():
        try:
            policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    print("\n" + "=" * 90)
    print(f"📊 TIẾN ĐỘ GÁN NHÃN REVIEW C4b ({total_labeled}/{total_rows} tin, {overall_pct:.1f}%)")
    print("=" * 90)
    print(f"{'Nguồn':<15} | {'Tổng':>5} | {'Đã gán':>6} | {'IT':>4} | {'Non-IT':>6} | {'Chưa gán':>8} | {'Đúng luật':>9} | {'Chính sách':<18}")
    print("-" * 90)

    for s in stats_list:
        pol_info = "Chưa duyệt"
        if s["source"] in policy:
            drop_list = policy[s["source"]].get("drop", [])
            pol_info = f"Bỏ: {','.join(drop_list)}" if drop_list else "Giữ (drop=[])"

        acc_str = f"{s['rule_accuracy']:.1f}%" if s["labeled"] > 0 else "—"
        print(
            f"{s['source']:<15} | {s['total']:>5} | {s['labeled']:>6} | {s['it']:>4} | "
            f"{s['non_it']:>6} | {s['unlabeled']:>8} | {acc_str:>9} | {pol_info:<18}"
        )

    print("-" * 90)
    print(
        f"{'TỔNG CỘNG':<15} | {total_rows:>5} | {total_labeled:>6} | {total_it:>4} | "
        f"{total_non_it:>6} | {total_unlabeled:>8} | {'—':>9} |"
    )
    print("=" * 90 + "\n")


# ---------------------------------------------------------------- Gợi ý tự động chức danh rõ ràng
def auto_suggest_obvious(apply: bool = False) -> None:
    print("\n🔍 ĐANG QUÉT CÁC TIN CÓ CHỨC DANH NGOÀI IT RÕ RÀNG (Kế toán, lái xe, bảo vệ, tạp vụ...)...")
    found_count = 0
    per_source: Dict[str, List[Dict[str, str]]] = {s: [] for s in SOURCES}

    for s in SOURCES:
        rows = load_rows(s)
        for r in rows:
            current_label = (r.get("nhan_tay") or "").strip()
            if current_label:
                continue  # Không đè nhãn đã có
            title = r.get("job_title") or ""
            if OBVIOUS_NON_IT_RE.search(title) and not TECH_PROTECT_RE.search(title):
                per_source[s].append(r)
                found_count += 1

    print(f"\n👉 Tìm thấy tổng cộng: {found_count} tin chưa gán có chức danh ngoài IT 100% rõ ràng:")
    for s in SOURCES:
        cnt = len(per_source[s])
        if cnt > 0:
            print(f"  • {s:<14}: {cnt} tin")
            for ex in per_source[s][:3]:
                print(f"      - {ex.get('job_title')}")

    if not apply:
        print("\n💡 Chế độ chạy thử (Dry-run). Dùng cờ '--apply' để tự động điền nhãn 'non_it' cho các tin này:")
        print("    python scripts/label_tool.py --auto-obvious --apply\n")
        return

    # Áp dụng
    for s in SOURCES:
        if not per_source[s]:
            continue
        rows = load_rows(s)
        lookup = {r["job_id"]: r for r in rows}
        for item in per_source[s]:
            jid = item["job_id"]
            if jid in lookup and not (lookup[jid].get("nhan_tay") or "").strip():
                lookup[jid]["nhan_tay"] = "non_it"
        save_rows(s, rows)

    print(f"\n✅ ĐÃ GÁN THÀNH CÔNG 'non_it' CHO {found_count} TIN RÕ RÀNG!\n")
    print_stats_table()


# ---------------------------------------------------------------- Sinh it_policy.json
def generate_policy(apply: bool = False) -> Dict[str, Any]:
    stats_list = get_all_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    policy_doc: Dict[str, Any] = {}

    for s in stats_list:
        src = s["source"]
        labeled = s["labeled"]
        non_it = s["non_it"]
        it = s["it"]
        pct_non_it = (non_it / labeled * 100) if labeled else 0.0

        if labeled == 0:
            continue

        # Nếu tỷ lệ non_it cao (>70%) và đã được kiểm kỹ:
        if src == "topdev":
            policy_doc[src] = {
                "drop": ["non_it"],
                "approved_on": today,
                "evidence": f"C4b: Gán tay {labeled} tin, phát hiện {non_it} non_it ({pct_non_it:.1f}%). Crawler kéo sai phạm vi (API bỏ qua category_ids=1)",
            }
        elif pct_non_it >= 50.0:
            policy_doc[src] = {
                "drop": ["non_it"],
                "approved_on": today,
                "evidence": f"C4b: Gán tay {labeled} tin, xác nhận {non_it} non_it ({pct_non_it:.1f}%). Nguồn đăng lẫn tin ngoài IT",
            }
        else:
            policy_doc[src] = {
                "drop": ["non_it"] if non_it > 0 else [],
                "approved_on": today,
                "evidence": f"C4b: Gán tay {labeled} tin (IT: {it}, Non-IT: {non_it})",
            }

    print("\n📋 ĐỀ XUẤT NỘI DUNG preprocessing/clean/it_policy.json:")
    print(json.dumps(policy_doc, ensure_ascii=False, indent=2))

    if not apply:
        print("\n💡 Chạy với '--apply' để ghi trực tiếp vào preprocessing/clean/it_policy.json:")
        print("    python scripts/label_tool.py --generate-policy --apply\n")
        return policy_doc

    POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
    POLICY_PATH.write_text(json.dumps(policy_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ ĐÃ GHI THÀNH CÔNG VÀO {POLICY_PATH}!\n")
    return policy_doc


# ---------------------------------------------------------------- Terminal TUI (1 phím bấm)
def get_key_raw() -> str:
    """Đọc 1 phím từ bàn phím ngay lập tức không cần gõ Enter."""
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        return line.strip().lower()[:1] if line else "q"

    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            # Phím điều hướng hoặc ESC
            r, _, _ = select.select([sys.stdin], [], [], 0.05)
            if r:
                seq = sys.stdin.read(2)
                if seq == "[A":
                    return "up"
                if seq == "[B":
                    return "down"
                if seq == "[C":
                    return "right"
                if seq == "[D":
                    return "left"
            return "esc"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def clear_screen() -> None:
    sys.stdout.write("\033[H\033[2J")
    sys.stdout.flush()


def run_tui(target_source: Optional[str] = None, unlabeled_only: bool = True) -> None:
    sources_to_run = [target_source] if target_source else list(SOURCES)
    history: List[Tuple[str, str, str]] = []  # (source, job_id, previous_label)

    for src in sources_to_run:
        rows = load_rows(src)
        if not rows:
            continue

        idx = 0
        while 0 <= idx < len(rows):
            r = rows[idx]
            current_label = (r.get("nhan_tay") or "").strip()

            # Nếu chọn unlabeled_only và tin đã có nhãn, nhảy tới tin chưa có
            if unlabeled_only and current_label in {"it", "non_it"}:
                idx += 1
                continue

            stats = get_source_stats(src)
            all_st = get_all_stats()
            total_labeled = sum(s["labeled"] for s in all_st)
            total_all = sum(s["total"] for s in all_st)
            pct_all = (total_labeled / total_all * 100) if total_all else 0.0

            # Màu sắc ANSI
            C_RESET = "\033[0m"
            C_BOLD = "\033[1m"
            C_CYAN = "\033[96m"
            C_GREEN = "\033[92m"
            C_RED = "\033[91m"
            C_YELLOW = "\033[93m"
            C_DIM = "\033[2m"
            C_BLUE = "\033[94m"

            clear_screen()
            print(f"{C_BOLD}{C_BLUE}========================================================================================{C_RESET}")
            print(
                f"🎯 {C_BOLD}ĐÁNH NHÃN REVIEW C4b{C_RESET} | Nguồn: {C_BOLD}{C_CYAN}{src.upper()}{C_RESET} "
                f"({idx+1}/{len(rows)}) | Đã xong nguồn: {C_BOLD}{stats['progress_pct']:.1f}%{C_RESET} ({stats['labeled']}/{stats['total']})"
            )
            print(
                f"🌐 {C_DIM}Toàn hệ thống:{C_RESET} {total_labeled}/{total_all} ({pct_all:.1f}%) "
                f"| {C_GREEN}IT: {sum(s['it'] for s in all_st)}{C_RESET} "
                f"| {C_RED}Non-IT: {sum(s['non_it'] for s in all_st)}{C_RESET} "
                f"| {C_YELLOW}Chưa gán: {sum(s['unlabeled'] for s in all_st)}{C_RESET}"
            )
            print(f"{C_BOLD}{C_BLUE}========================================================================================{C_RESET}")

            # Thẻ thông tin công việc
            title = r.get("job_title") or "(Không có tiêu đề)"
            skills = r.get("skills") or "(Trống)"
            rule = r.get("it_rule") or "unknown"
            status = r.get("it_status") or "can_kiem"
            prob = r.get("it_prob") or "None"
            url = r.get("source_url") or "—"

            rule_color = C_GREEN if rule == "it" else (C_RED if rule == "non_it" else C_YELLOW)
            status_color = C_GREEN if status == "it" else (C_RED if status == "non_it" else C_YELLOW)

            if current_label == "it":
                nhan_str = f"{C_BOLD}{C_GREEN}[ ĐÃ GÁN: IT ]{C_RESET}"
            elif current_label == "non_it":
                nhan_str = f"{C_BOLD}{C_RED}[ ĐÃ GÁN: NON_IT ]{C_RESET}"
            else:
                nhan_str = f"{C_YELLOW}[ CHƯA GÁN NHÃN ]{C_RESET}"

            print(f"\n💼 {C_BOLD}{C_CYAN}TIÊU ĐỀ:{C_RESET}   {C_BOLD}{title}{C_RESET}")
            print(f"🛠️  {C_BOLD}KỸ NĂNG:{C_RESET}   {skills}")
            print(
                f"🤖 {C_BOLD}DỰ ĐOÁN:{C_RESET}   Luật từ khóa: {rule_color}{rule}{C_RESET} | "
                f"Trạng thái: {status_color}{status}{C_RESET} | "
                f"JEV prob: {prob}"
            )
            print(f"🏷️  {C_BOLD}HIỆN TẠI:{C_RESET}  {nhan_str}")
            print(f"🔗 {C_DIM}Link gốc:{C_RESET}  {url}")

            # Gợi ý nhanh
            recommend = "non_it" if (rule == "non_it" or status == "non_it") else ("it" if rule == "it" else None)
            rec_str = f" [Gợi ý: {recommend}]" if recommend else ""

            print(f"\n{C_BLUE}----------------------------------------------------------------------------------------{C_RESET}")
            print(
                f"{C_BOLD}PHÍM TẮT:{C_RESET}  "
                f"{C_GREEN}[1 / i] IT{C_RESET}   "
                f"{C_RED}[2 / n] Non-IT{C_RESET}   "
                f"{C_YELLOW}[a] Chấp nhận luật{rec_str}{C_RESET}   "
                f"[s / Space] Bỏ qua\n"
                f"          [u] Hoàn tác     [o] Mở link trình duyệt    [j / k] Tới / Lùi    [q] Thoát"
            )
            print(f"{C_BLUE}----------------------------------------------------------------------------------------{C_RESET}")
            sys.stdout.write("👉 Bấm phím: ")
            sys.stdout.flush()

            key = get_key_raw().lower()

            if key in {"1", "i"}:
                history.append((src, r["job_id"], current_label))
                r["nhan_tay"] = "it"
                save_rows(src, rows)
                idx += 1
            elif key in {"2", "n"}:
                history.append((src, r["job_id"], current_label))
                r["nhan_tay"] = "non_it"
                save_rows(src, rows)
                idx += 1
            elif key == "a":
                if recommend:
                    history.append((src, r["job_id"], current_label))
                    r["nhan_tay"] = recommend
                    save_rows(src, rows)
                    idx += 1
            elif key in {"s", " ", "down", "right"}:
                idx += 1
            elif key in {"u", "backspace"}:
                if history:
                    last_src, last_jid, last_val = history.pop()
                    if last_src == src:
                        for prev_idx, prev_row in enumerate(rows):
                            if prev_row["job_id"] == last_jid:
                                prev_row["nhan_tay"] = last_val
                                save_rows(src, rows)
                                idx = prev_idx
                                break
                    else:
                        print(f"\n(Hành động trước ở nguồn {last_src}, hãy hoàn tác thủ công).")
                else:
                    if idx > 0:
                        idx -= 1
            elif key in {"k", "up", "left"}:
                if idx > 0:
                    idx -= 1
            elif key == "o":
                if url and url.startswith("http"):
                    webbrowser.open(url)
            elif key in {"q", "esc"}:
                clear_screen()
                print("\n👋 ĐÃ THOÁT TOOL GÁN NHÃN. Dữ liệu đã được lưu an toàn!")
                print_stats_table()
                return

    clear_screen()
    print("\n🎉 ĐÃ DUYỆT HẾT CÁC TIN CỦA CÁC NGUỒN ĐÃ CHỌN!")
    print_stats_table()


# ---------------------------------------------------------------- Web UI Server
WEB_HTML = r"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Review & Gán Nhãn IT/Non-IT (VN-IT-Job-Mining)</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #38bdf8;
      --it-color: #22c55e;
      --non-it-color: #ef4444;
      --warn: #f59e0b;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); min-height: 100vh; padding: 20px; }
    .container { max-width: 1000px; margin: 0 auto; }
    header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 15px; }
    h1 { font-size: 1.4rem; color: var(--primary); display: flex; align-items: center; gap: 8px; }
    .tabs { display: flex; gap: 6px; margin-bottom: 15px; overflow-x: auto; padding-bottom: 6px; }
    .tab-btn { background: var(--card-bg); color: var(--text-muted); border: 1px solid var(--border); padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-weight: 500; display: flex; align-items: center; gap: 6px; white-space: nowrap; }
    .tab-btn.active { background: var(--primary); color: #000; border-color: var(--primary); font-weight: 700; }
    .badge { background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 10px; font-size: 0.75rem; }
    .progress-bar-container { background: var(--card-bg); border-radius: 8px; height: 10px; overflow: hidden; margin-bottom: 20px; border: 1px solid var(--border); }
    .progress-fill { background: linear-gradient(90deg, #38bdf8, #22c55e); height: 100%; width: 0%; transition: width 0.3s; }
    .stats-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-bottom: 20px; }
    .stat-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px; text-align: center; }
    .stat-val { font-size: 1.3rem; font-weight: bold; margin-top: 4px; }
    .stat-val.it { color: var(--it-color); }
    .stat-val.non-it { color: var(--non-it-color); }
    .stat-val.remain { color: var(--warn); }
    .filters { display: flex; gap: 10px; margin-bottom: 15px; align-items: center; }
    .filter-btn { background: transparent; border: 1px solid var(--border); color: var(--text-muted); padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
    .filter-btn.active { background: var(--border); color: var(--text); font-weight: bold; }
    .job-card { background: var(--card-bg); border: 2px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); position: relative; }
    .job-title { font-size: 1.35rem; font-weight: 700; color: #fff; margin-bottom: 12px; line-height: 1.4; }
    .job-skills { background: rgba(0,0,0,0.25); border: 1px solid var(--border); border-radius: 6px; padding: 10px 14px; margin-bottom: 15px; font-size: 0.95rem; color: #cbd5e1; }
    .job-meta { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; font-size: 0.85rem; }
    .meta-tag { background: rgba(255,255,255,0.06); padding: 4px 10px; border-radius: 4px; border: 1px solid var(--border); }
    .meta-tag.tag-it { border-color: var(--it-color); color: var(--it-color); font-weight: bold; }
    .meta-tag.tag-non-it { border-color: var(--non-it-color); color: var(--non-it-color); font-weight: bold; }
    .meta-tag.tag-can-kiem { border-color: var(--warn); color: var(--warn); font-weight: bold; }
    .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px; }
    .btn-act { padding: 18px 20px; border-radius: 8px; border: none; font-size: 1.15rem; font-weight: bold; cursor: pointer; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; transition: transform 0.1s, opacity 0.1s; }
    .btn-act:hover { opacity: 0.9; transform: translateY(-1px); }
    .btn-act:active { transform: translateY(1px); }
    .btn-it { background: var(--it-color); color: #000; }
    .btn-non-it { background: var(--non-it-color); color: #fff; }
    .btn-sub { font-size: 0.75rem; font-weight: normal; opacity: 0.85; }
    .sub-actions { display: flex; justify-content: space-between; align-items: center; }
    .btn-secondary { background: var(--card-bg); border: 1px solid var(--border); color: var(--text-muted); padding: 8px 14px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; }
    .btn-secondary:hover { color: var(--text); border-color: var(--primary); }
    .keyboard-hint { text-align: center; font-size: 0.8rem; color: var(--text-muted); margin-top: 15px; }
    .kbd { background: #334155; color: #fff; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-family: monospace; }
    .link-origin { color: var(--primary); text-decoration: none; font-size: 0.85rem; display: inline-flex; align-items: center; gap: 4px; }
    .link-origin:hover { text-decoration: underline; }
    .empty-state { text-align: center; padding: 60px 20px; background: var(--card-bg); border-radius: 12px; border: 1px dashed var(--border); }
    .policy-box { background: rgba(56, 189, 248, 0.08); border: 1px solid var(--primary); border-radius: 8px; padding: 16px; margin-top: 25px; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>🎯 VN-IT-Job-Mining | Đánh Nhãn IT / Non-IT</h1>
      <div id="overall-badge" style="font-size:0.9rem; color:var(--text-muted);">Đang tải...</div>
    </header>

    <div class="tabs" id="source-tabs"></div>

    <div class="progress-bar-container">
      <div class="progress-fill" id="progress-fill"></div>
    </div>

    <div class="stats-row">
      <div class="stat-card">
        <div style="font-size:0.8rem; color:var(--text-muted);">Tổng số mẫu</div>
        <div class="stat-val" id="stat-total">0</div>
      </div>
      <div class="stat-card">
        <div style="font-size:0.8rem; color:var(--text-muted);">Đã gán nhãn</div>
        <div class="stat-val" id="stat-labeled">0</div>
      </div>
      <div class="stat-card">
        <div style="font-size:0.8rem; color:var(--text-muted);">Gán là IT</div>
        <div class="stat-val it" id="stat-it">0</div>
      </div>
      <div class="stat-card">
        <div style="font-size:0.8rem; color:var(--text-muted);">Gán là Non-IT</div>
        <div class="stat-val non-it" id="stat-non-it">0</div>
      </div>
      <div class="stat-card">
        <div style="font-size:0.8rem; color:var(--text-muted);">Chưa gán</div>
        <div class="stat-val remain" id="stat-unlabeled">0</div>
      </div>
      <div class="stat-card">
        <div style="font-size:0.8rem; color:var(--text-muted);">Khớp luật từ khóa</div>
        <div class="stat-val" id="stat-acc">0%</div>
      </div>
    </div>

    <div class="filters">
      <button class="filter-btn active" onclick="setFilter('unlabeled')">Chỉ tin chưa gán</button>
      <button class="filter-btn" onclick="setFilter('all')">Toàn bộ tin</button>
      <button class="filter-btn" onclick="setFilter('labeled')">Đã có nhãn</button>
      <button class="filter-btn" onclick="autoObvious()" style="margin-left:auto; border-color:var(--warn); color:var(--warn);">⚡ Tự điền Non-IT rõ ràng</button>
    </div>

    <div id="main-content">
      <div class="empty-state">Đang tải dữ liệu...</div>
    </div>

    <div class="keyboard-hint">
      Phím tắt siêu tốc: <span class="kbd">1</span> hoặc <span class="kbd">I</span> = IT &nbsp;|&nbsp;
      <span class="kbd">2</span> hoặc <span class="kbd">N</span> = Non-IT &nbsp;|&nbsp;
      <span class="kbd">Space</span> = Bỏ qua &nbsp;|&nbsp;
      <span class="kbd">U</span> = Hoàn tác &nbsp;|&nbsp;
      <span class="kbd">O</span> = Mở link gốc
    </div>

    <div class="policy-box">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <strong style="color:var(--primary);">📋 Chính sách duyệt tin (preprocessing/clean/it_policy.json)</strong>
        <button class="btn-secondary" onclick="generatePolicy()" style="border-color:var(--primary); color:var(--primary);">Duyệt & Lưu it_policy.json</button>
      </div>
      <div style="font-size:0.85rem; color:var(--text-muted); line-height:1.5;" id="policy-status">
        Sau khi hoàn tất gán nhãn cho các nguồn, bấm nút trên để tự động tạo <code>it_policy.json</code> giúp P1 loại bỏ tin ngoài IT theo đúng bằng chứng đã kiểm duyệt.
      </div>
    </div>
  </div>

  <script>
    let currentSource = 'careerviet';
    let currentFilter = 'unlabeled';
    let items = [];
    let currentIndex = 0;
    let historyStack = [];

    const SOURCES = ["careerviet", "glints", "itviec", "jobsgo", "topcv", "topdev", "vieclam24h", "vietnamworks"];

    async function init() {
      renderTabs();
      await loadStats();
      await loadSource(currentSource);
      setupHotkeys();
    }

    function renderTabs() {
      const tabsEl = document.getElementById('source-tabs');
      tabsEl.innerHTML = SOURCES.map(s => `
        <button class="tab-btn ${s === currentSource ? 'active' : ''}" onclick="switchSource('${s}')" id="tab-${s}">
          ${s} <span class="badge" id="badge-${s}">...</span>
        </button>
      `).join('');
    }

    async function loadStats() {
      const res = await fetch('/api/stats');
      const stats = await res.json();
      let total = 0, labeled = 0, it = 0, non_it = 0;

      stats.forEach(s => {
        total += s.total;
        labeled += s.labeled;
        it += s.it;
        non_it += s.non_it;
        const b = document.getElementById(`badge-${s.source}`);
        if (b) b.innerText = `${s.labeled}/${s.total}`;
      });

      document.getElementById('stat-total').innerText = total;
      document.getElementById('stat-labeled').innerText = labeled;
      document.getElementById('stat-it').innerText = it;
      document.getElementById('stat-non-it').innerText = non_it;
      document.getElementById('stat-unlabeled').innerText = total - labeled;
      const pct = total ? Math.round((labeled / total) * 100) : 0;
      document.getElementById('progress-fill').style.width = pct + '%';
      document.getElementById('overall-badge').innerText = `Toàn bộ hệ thống: ${labeled}/${total} (${pct}%)`;

      const curStat = stats.find(s => s.source === currentSource);
      if (curStat) {
        document.getElementById('stat-acc').innerText = curStat.rule_accuracy.toFixed(1) + '%';
      }
    }

    async function switchSource(source) {
      currentSource = source;
      renderTabs();
      await loadSource(source);
    }

    function setFilter(f) {
      currentFilter = f;
      document.querySelectorAll('.filters .filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('onclick')?.includes(f));
      });
      applyFilter();
    }

    async function loadSource(source) {
      const res = await fetch(`/api/items?source=${source}`);
      items = await res.json();
      applyFilter();
    }

    let filteredItems = [];
    function applyFilter() {
      if (currentFilter === 'unlabeled') {
        filteredItems = items.filter(i => !i.nhan_tay);
      } else if (currentFilter === 'labeled') {
        filteredItems = items.filter(i => i.nhan_tay);
      } else {
        filteredItems = [...items];
      }
      currentIndex = 0;
      renderCurrentItem();
    }

    function renderCurrentItem() {
      const container = document.getElementById('main-content');
      if (!filteredItems.length) {
        container.innerHTML = `
          <div class="empty-state">
            <h2 style="color:var(--it-color); margin-bottom:10px;">🎉 Nguồn này không còn tin nào cần xử lý!</h2>
            <p style="color:var(--text-muted); margin-bottom:15px;">Đã duyệt hết các tin theo bộ lọc hiện tại.</p>
            <button class="btn-secondary" onclick="switchNextSource()">Chuyển sang nguồn kế tiếp 👉</button>
          </div>
        `;
        return;
      }

      if (currentIndex >= filteredItems.length) currentIndex = filteredItems.length - 1;
      if (currentIndex < 0) currentIndex = 0;

      const item = filteredItems[currentIndex];
      const ruleClass = item.it_rule === 'it' ? 'tag-it' : (item.it_rule === 'non_it' ? 'tag-non-it' : 'tag-can-kiem');
      const statusClass = item.it_status === 'it' ? 'tag-it' : (item.it_status === 'non_it' ? 'tag-non-it' : 'tag-can-kiem');

      container.innerHTML = `
        <div class="job-card">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-size:0.85rem; color:var(--text-muted);">
              Tin <strong>${currentIndex + 1}</strong> / ${filteredItems.length} (${currentSource})
            </span>
            <span style="font-size:0.85rem;">
              Nhãn hiện tại: <strong>${item.nhan_tay ? item.nhan_tay.toUpperCase() : '<em style="color:var(--warn)">Chưa gán</em>'}</strong>
            </span>
          </div>

          <div class="job-title">${escapeHtml(item.job_title)}</div>

          <div class="job-skills">
            <strong style="color:var(--primary);">Kỹ năng:</strong> ${escapeHtml(item.skills || '(Không có thông tin kỹ năng)')}
          </div>

          <div class="job-meta">
            <span class="meta-tag ${ruleClass}">Luật từ khóa: ${item.it_rule}</span>
            <span class="meta-tag ${statusClass}">Trạng thái: ${item.it_status}</span>
            <span class="meta-tag">JEV prob: ${item.it_prob || 'None'}</span>
            <a href="${item.source_url}" target="_blank" class="link-origin" style="margin-left:auto;">
              Mở link gốc ↗
            </a>
          </div>

          <div class="actions">
            <button class="btn-act btn-it" onclick="labelCurrent('it')">
              ✅ IT (Công nghệ thông tin)
              <span class="btn-sub">Bấm phím [1] hoặc [I]</span>
            </button>
            <button class="btn-act btn-non-it" onclick="labelCurrent('non_it')">
              ❌ Non-IT (Ngoài IT)
              <span class="btn-sub">Bấm phím [2] hoặc [N]</span>
            </button>
          </div>

          <div class="sub-actions">
            <button class="btn-secondary" onclick="prevItem()">◀ Lùi lại (K)</button>
            <button class="btn-secondary" onclick="skipItem()">Bỏ qua (Space) ▶</button>
            <button class="btn-secondary" onclick="undo()">Hoàn tác (U)</button>
          </div>
        </div>
      `;
    }

    async function labelCurrent(label) {
      if (!filteredItems.length) return;
      const item = filteredItems[currentIndex];
      const oldVal = item.nhan_tay;
      historyStack.push({ source: currentSource, job_id: item.job_id, prev_label: oldVal });

      item.nhan_tay = label;
      await fetch('/api/label', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: currentSource, job_id: item.job_id, label })
      });

      await loadStats();

      if (currentFilter === 'unlabeled') {
        filteredItems.splice(currentIndex, 1);
      } else {
        currentIndex++;
      }
      renderCurrentItem();
    }

    function skipItem() {
      if (currentIndex < filteredItems.length - 1) {
        currentIndex++;
        renderCurrentItem();
      }
    }

    function prevItem() {
      if (currentIndex > 0) {
        currentIndex--;
        renderCurrentItem();
      }
    }

    async function undo() {
      if (!historyStack.length) return;
      const last = historyStack.pop();
      await fetch('/api/label', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: last.source, job_id: last.job_id, label: last.prev_label })
      });
      await loadStats();
      if (last.source === currentSource) {
        await loadSource(currentSource);
      } else {
        await switchSource(last.source);
      }
    }

    function switchNextSource() {
      const curIdx = SOURCES.indexOf(currentSource);
      const nextSrc = SOURCES[(curIdx + 1) % SOURCES.length];
      switchSource(nextSrc);
    }

    async function autoObvious() {
      if (!confirm("Tự động gán nhãn 'non_it' cho các tin có tiêu đề ngoài IT 100% rõ ràng (kế toán, lái xe, giáo viên...)?")) return;
      const res = await fetch('/api/auto_obvious', { method: 'POST' });
      const data = await res.json();
      alert(`Đã gán xong ${data.count} tin!`);
      await loadStats();
      await loadSource(currentSource);
    }

    async function generatePolicy() {
      const res = await fetch('/api/policy', { method: 'POST' });
      const data = await res.json();
      alert(`Đã lưu thành công preprocessing/clean/it_policy.json cho ${Object.keys(data.policy).length} nguồn!`);
      document.getElementById('policy-status').innerHTML = `<strong style="color:var(--it-color)">Đã lưu thành công it_policy.json!</strong><pre style="background:#000; padding:10px; border-radius:6px; margin-top:8px;">${JSON.stringify(data.policy, null, 2)}</pre>`;
    }

    function setupHotkeys() {
      window.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        const k = e.key.toLowerCase();
        if (k === '1' || k === 'i') { e.preventDefault(); labelCurrent('it'); }
        else if (k === '2' || k === 'n') { e.preventDefault(); labelCurrent('non_it'); }
        else if (k === ' ' || k === 's') { e.preventDefault(); skipItem(); }
        else if (k === 'u') { e.preventDefault(); undo(); }
        else if (k === 'k' || k === 'arrowleft') { e.preventDefault(); prevItem(); }
        else if (k === 'j' || k === 'arrowright') { e.preventDefault(); skipItem(); }
        else if (k === 'o') {
          if (filteredItems[currentIndex]) window.open(filteredItems[currentIndex].source_url, '_blank');
        }
      });
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    window.onload = init;
  </script>
</body>
</html>
"""


class WebLabelHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in {"/", "/index.html"}:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(WEB_HTML.encode("utf-8"))
        elif path == "/api/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(get_all_stats(), ensure_ascii=False).encode("utf-8"))
        elif path == "/api/items":
            qs = parse_qs(parsed.query)
            source = qs.get("source", ["careerviet"])[0]
            rows = load_rows(source)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(rows, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        data = json.loads(body) if body else {}

        if path == "/api/label":
            source = data.get("source")
            job_id = data.get("job_id")
            label = (data.get("label") or "").strip()
            if source in SOURCES and job_id:
                rows = load_rows(source)
                for r in rows:
                    if r["job_id"] == job_id:
                        r["nhan_tay"] = label
                        break
                save_rows(source, rows)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
                return
            self.send_response(400)
            self.end_headers()

        elif path == "/api/auto_obvious":
            count = 0
            for s in SOURCES:
                rows = load_rows(s)
                updated = False
                for r in rows:
                    if not (r.get("nhan_tay") or "").strip():
                        t = r.get("job_title") or ""
                        if OBVIOUS_NON_IT_RE.search(t) and not TECH_PROTECT_RE.search(t):
                            r["nhan_tay"] = "non_it"
                            count += 1
                            updated = True
                if updated:
                    save_rows(s, rows)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "count": count}).encode("utf-8"))

        elif path == "/api/policy":
            pol = generate_policy(apply=True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "policy": pol}, ensure_ascii=False).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        # Tắt bớt log HTTP để màn hình sạch sẽ
        pass


def run_web(port: int = 8765) -> None:
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, WebLabelHandler)
    url = f"http://localhost:{port}"
    print(f"\n🚀 ĐANG KHỞI CHẠY WEB UI GÁN NHÃN:")
    print(f"👉 Mở trình duyệt tại: \033[1m\033[96m{url}\033[0m")
    print(f"⌨️  Hỗ trợ phím tắt siêu tốc: [1]=IT, [2]=Non-IT, [Space]=Skip, [U]=Undo")
    print(f"Nhấn Ctrl+C để dừng web server.\n")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Đã tắt Web server an toàn.")
        httpd.server_close()


# ---------------------------------------------------------------- Main Entrypoint
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tool gán nhãn tay review C4b cho bước Clean (P1) - VN-IT-Job-Mining",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source", choices=[*SOURCES, "all"], default=None, help="Chỉ định nguồn để gán nhãn")
    parser.add_argument("--web", action="store_true", help="Chạy giao diện Web UI siêu tốc trên localhost")
    parser.add_argument("--port", type=int, default=8765, help="Cổng Web UI (mặc định 8765)")
    parser.add_argument("--stats", action="store_true", help="Hiển thị bảng thống kê tiến độ 8 nguồn")
    parser.add_argument("--all-rows", action="store_true", help="TUI: Duyệt cả các tin đã có nhãn (mặc định chỉ tin chưa gán)")
    parser.add_argument("--auto-obvious", action="store_true", help="Gợi ý/điền tự động nhãn 'non_it' cho các chức danh 100% rõ ràng")
    parser.add_argument("--generate-policy", action="store_true", help="Sinh cấu hình it_policy.json theo nhãn đã duyệt")
    parser.add_argument("--apply", action="store_true", help="Áp dụng thay đổi thật khi dùng --auto-obvious hoặc --generate-policy")

    args = parser.parse_args()

    if args.stats:
        print_stats_table()
        return

    if args.auto_obvious:
        auto_suggest_obvious(apply=args.apply)
        return

    if args.generate_policy:
        generate_policy(apply=args.apply)
        return

    if args.web:
        run_web(port=args.port)
        return

    # Chạy TUI (mặc định)
    src = None if args.source == "all" else args.source
    run_tui(target_source=src, unlabeled_only=not args.all_rows)


if __name__ == "__main__":
    main()
