#!/usr/bin/env python3
"""Script kiểm tra và chấm điểm tự động hồ sơ nghiệm thu thu thập dữ liệu (DoD Verifier & Grader).

Thang điểm 100 điểm chuẩn theo submission_scoring_rubric.md.

Sử dụng:
    python3 .agents/skills/collection-submission/scripts/verify_submission.py --source topcv
    python3 .agents/skills/collection-submission/scripts/verify_submission.py --all
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

ALL_SOURCES = [
    "topcv",
    "topdev",
    "vietnamworks",
    "careerviet",
    "vieclam24h",
    "itviec",
    "glints",
    "jobsgo",
]


class DoDScorer:
    """Bộ chấm điểm tự động 100 điểm theo tiêu chuẩn nghiệm thu DoD."""

    def __init__(self, source: str) -> None:
        self.source = source.lower().strip()
        self.scores: dict[str, int] = {}
        self.max_scores: dict[str, int] = {
            "TC1_TwoPhase": 20,
            "TC2_SafeSkip": 10,
            "TC3_Recrawl21d": 10,
            "TC4_Samples": 20,
            "TC5_Lakehouse": 10,
            "TC6_ArchitectureDoc": 15,
            "TC7_Reports": 15,
        }
        self.bonus: int = 0
        self.penalty: int = 0
        self.details: dict[str, list[str]] = {}
        self.crawler_path = Path("crawlers") / "sources" / self.source / "crawler.py"
        self.crawler_code = ""
        if self.crawler_path.is_file():
            try:
                self.crawler_code = self.crawler_path.read_text(encoding="utf-8")
            except Exception:
                self.crawler_code = ""

    def evaluate(self) -> dict[str, Any]:
        self._check_tc1_two_phase()
        self._check_tc2_safe_skip()
        self._check_tc3_recrawl()
        self._check_tc4_samples()
        self._check_tc5_lakehouse()
        self._check_tc6_docs()
        self._check_tc7_reports()
        self._check_bonus_and_penalties()

        base_score = sum(self.scores.values())
        total_score = max(0, base_score + self.bonus - self.penalty)

        return {
            "source": self.source,
            "scores": self.scores,
            "bonus": self.bonus,
            "penalty": self.penalty,
            "total_score": total_score,
            "passed": total_score >= 70,
            "details": self.details,
        }

    def _check_tc1_two_phase(self) -> None:
        """TC1 (20đ): discover_urls (10đ) & crawl_details (10đ)."""
        log_items = []
        score = 0
        if not self.crawler_code:
            log_items.append(f"{RED}[FAIL]{RESET} Không tìm thấy file mã nguồn crawler: {self.crawler_path}")
            self.scores["TC1_TwoPhase"] = 0
            self.details["TC1_TwoPhase"] = log_items
            return

        has_discover = bool(re.search(r"def\s+discover_urls\b", self.crawler_code))
        has_crawl_details = bool(re.search(r"def\s+crawl_details\b", self.crawler_code))

        if has_discover:
            score += 10
            log_items.append(f"{GREEN}[PASS]{RESET} Có hàm discover_urls() cho Pha 1 (+10đ)")
        else:
            log_items.append(f"{RED}[FAIL]{RESET} Thiếu hàm discover_urls() (0/10đ)")

        if has_crawl_details:
            score += 10
            log_items.append(f"{GREEN}[PASS]{RESET} Có hàm crawl_details() cho Pha 2 (+10đ)")
        else:
            log_items.append(f"{RED}[FAIL]{RESET} Thiếu hàm crawl_details() (0/10đ)")

        self.scores["TC1_TwoPhase"] = score
        self.details["TC1_TwoPhase"] = log_items

    def _check_tc2_safe_skip(self) -> None:
        """TC2 (10đ): try...except item-level & continue graceful."""
        log_items = []
        score = 0
        if not self.crawler_code:
            self.scores["TC2_SafeSkip"] = 0
            self.details["TC2_SafeSkip"] = [f"{RED}[FAIL]{RESET} Không có code để kiểm tra Safe Skip"]
            return

        has_try = "try:" in self.crawler_code and "except" in self.crawler_code
        has_safe_skip_pattern = bool(
            re.search(r"(safe_skip|Safe Skip|safe skip|skip|continue)", self.crawler_code, re.IGNORECASE)
        )

        if has_try:
            score += 5
            log_items.append(f"{GREEN}[PASS]{RESET} Có khối try...except bao bọc xử lý (+5đ)")
        else:
            log_items.append(f"{RED}[FAIL]{RESET} Không có try...except bao bọc ngoại lệ (0/5đ)")

        if has_safe_skip_pattern:
            score += 5
            log_items.append(f"{GREEN}[PASS]{RESET} Có cơ chế ghi log cảnh báo và bỏ qua an toàn (+5đ)")
        else:
            log_items.append(f"{RED}[FAIL]{RESET} Chưa có cơ chế skip lỗi mạng an toàn (0/5đ)")

        self.scores["TC2_SafeSkip"] = score
        self.details["TC2_SafeSkip"] = log_items

    def _check_tc3_recrawl(self) -> None:
        """TC3 (10đ): Quản lý trạng thái và chu kỳ re-crawl 21 ngày."""
        log_items = []
        score = 0
        if not self.crawler_code:
            self.scores["TC3_Recrawl21d"] = 0
            self.details["TC3_Recrawl21d"] = [f"{RED}[FAIL]{RESET} Không có code để kiểm tra Re-crawl"]
            return

        has_status = bool(re.search(r"(PENDING|DONE|FAILED|status)", self.crawler_code))
        has_21_days = bool(re.search(r"(21|days=21|recrawl|re_crawl)", self.crawler_code, re.IGNORECASE))

        if has_status:
            score += 5
            log_items.append(f"{GREEN}[PASS]{RESET} Có quản lý trạng thái bài viết (+5đ)")
        else:
            log_items.append(f"{RED}[FAIL]{RESET} Thiếu quản lý trạng thái URL PENDING/DONE (0/5đ)")

        if has_21_days:
            score += 5
            log_items.append(f"{GREEN}[PASS]{RESET} Có logic kiểm tra chu kỳ Re-crawl 21 ngày (+5đ)")
        else:
            log_items.append(f"{RED}[FAIL]{RESET} Chưa có điều kiện kiểm tra hạn 21 ngày (0/5đ)")

        self.scores["TC3_Recrawl21d"] = score
        self.details["TC3_Recrawl21d"] = log_items

    def _check_tc4_samples(self) -> None:
        """TC4 (20đ): 3 HTML (7đ) + 3 JSON valid (7đ) + đa dạng layout (3đ) + README (3đ)."""
        log_items = []
        score = 0
        samples_dir = Path("crawlers") / "sources" / self.source / "samples"
        if not samples_dir.is_dir():
            log_items.append(f"{RED}[FAIL]{RESET} Thư mục mẫu không tồn tại: {samples_dir} (0/20đ)")
            self.scores["TC4_Samples"] = 0
            self.details["TC4_Samples"] = log_items
            return

        html_files = sorted(list(samples_dir.glob("*.html")))
        json_files = sorted(list(samples_dir.glob("*.json")))
        readme_file = samples_dir / "README.md"

        # 1. HTML files
        if len(html_files) >= 3:
            score += 7
            log_items.append(f"{GREEN}[PASS]{RESET} Đủ file HTML thô ({len(html_files)}/3 file) (+7đ)")
        else:
            log_items.append(f"{RED}[FAIL]{RESET} Thiếu file HTML thô ({len(html_files)}/3 file) (0/7đ)")

        # 2. JSON files & tính hợp lệ
        valid_json = 0
        for jf in json_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    json.load(f)
                    valid_json += 1
            except Exception:
                pass

        if valid_json >= 3:
            score += 7
            log_items.append(f"{GREEN}[PASS]{RESET} Đủ file JSON tương ứng hợp lệ ({valid_json}/3 file) (+7đ)")
        else:
            log_items.append(f"{RED}[FAIL]{RESET} Thiếu file JSON hợp lệ ({valid_json}/3 file) (0/7đ)")

        # 3. Đa dạng layout
        sample_names = " ".join([f.name for f in html_files + json_files])
        if ("hot" in sample_names or "vip" in sample_names) and ("negotiable" in sample_names or "salary" in sample_names):
            score += 3
            log_items.append(f"{GREEN}[PASS]{RESET} Có sự đa dạng layout (chuẩn, VIP/hot, thỏa thuận) (+3đ)")
        elif len(html_files) >= 3 and valid_json >= 3:
            score += 1
            log_items.append(f"{YELLOW}[WARN]{RESET} Chưa thể hiện rõ sự khác biệt layout giữa các file (+1/3đ)")
        else:
            log_items.append(f"{RED}[FAIL]{RESET} Chưa có layout đa dạng (0/3đ)")

        # 4. README
        if readme_file.is_file() and readme_file.stat().st_size > 50:
            score += 3
            log_items.append(f"{GREEN}[PASS]{RESET} Có samples/README.md hướng dẫn mapping (+3đ)")
        else:
            log_items.append(f"{RED}[FAIL]{RESET} Thiếu file samples/README.md (0/3đ)")

        self.scores["TC4_Samples"] = score
        self.details["TC4_Samples"] = log_items

    def _check_tc5_lakehouse(self) -> None:
        """TC5 (10đ): MinIO & Cloudflare R2 integration."""
        log_items = []
        score = 0

        # Kiểm tra code tích hợp MinIO/Ledger
        has_minio_code = bool(re.search(r"(minio|url_ledger|ledger|sync_to_minio)", self.crawler_code, re.IGNORECASE))
        has_data_dir = (Path("data") / self.source).is_dir() or (Path("data") / "raw" / self.source).is_dir()

        if has_minio_code:
            score += 5
            log_items.append(f"{GREEN}[PASS]{RESET} Mã nguồn có tích hợp module Lakehouse/URL Ledger (+5đ)")
        else:
            log_items.append(f"{RED}[FAIL]{RESET} Mã nguồn chưa tích hợp UrlLedger hoặc sync MinIO (0/5đ)")

        if has_data_dir:
            score += 5
            log_items.append(f"{GREEN}[PASS]{RESET} Đã có thư mục lưu trữ dữ liệu phân vùng data/{self.source}/ (+5đ)")
        else:
            log_items.append(f"{YELLOW}[INFO]{RESET} Chưa có thư mục dữ liệu cục bộ data/{self.source}/ (0/5đ)")

        self.scores["TC5_Lakehouse"] = score
        self.details["TC5_Lakehouse"] = log_items

    def _check_tc6_docs(self) -> None:
        """TC6 (15đ): docs/crawl/<source>.md."""
        log_items = []
        score = 0
        doc_path = Path("docs") / "crawl" / f"{self.source}.md"

        if doc_path.is_file():
            score += 5
            log_items.append(f"{GREEN}[PASS]{RESET} Tồn tại file docs/crawl/{self.source}.md (+5đ)")
            size = doc_path.stat().st_size
            if size >= 500:
                score += 5
                log_items.append(f"{GREEN}[PASS]{RESET} Độ dài tài liệu đầy đủ ({size} bytes) (+5đ)")
            else:
                log_items.append(f"{YELLOW}[WARN]{RESET} Tài liệu quá ngắn ({size} < 500 bytes) (0/5đ)")

            content = doc_path.read_text(encoding="utf-8")
            if any(k in content for k in ["API", "DOM", "selector", "CSS", "WAF", "SSR", "HTML"]):
                score += 5
                log_items.append(f"{GREEN}[PASS]{RESET} Có phân tích kỹ thuật chi tiết (SSR/API/Selector) (+5đ)")
            else:
                log_items.append(f"{YELLOW}[WARN]{RESET} Thiếu phân tích sâu về kiến trúc mạng/DOM (0/5đ)")
        else:
            log_items.append(f"{RED}[FAIL]{RESET} Không tìm thấy docs/crawl/{self.source}.md (0/15đ)")

        self.scores["TC6_ArchitectureDoc"] = score
        self.details["TC6_ArchitectureDoc"] = log_items

    def _check_tc7_reports(self) -> None:
        """TC7 (15đ): inventory (8đ) & eda report (7đ)."""
        log_items = []
        score = 0
        inv_path = Path("reports") / f"{self.source}_inventory.md"
        eda_path = Path("reports") / f"{self.source}_eda.md"

        if inv_path.is_file() and inv_path.stat().st_size >= 100:
            score += 8
            log_items.append(f"{GREEN}[PASS]{RESET} Có báo cáo kiểm kê trường dữ liệu: {inv_path} (+8đ)")
        else:
            log_items.append(f"{RED}[FAIL]{RESET} Thiếu báo cáo kiểm kê: {inv_path} (0/8đ)")

        if eda_path.is_file() and eda_path.stat().st_size >= 100:
            score += 7
            log_items.append(f"{GREEN}[PASS]{RESET} Có báo cáo phân tích EDA sơ bộ: {eda_path} (+7đ)")
        else:
            log_items.append(f"{RED}[FAIL]{RESET} Thiếu báo cáo EDA: {eda_path} (0/7đ)")

        self.scores["TC7_Reports"] = score
        self.details["TC7_Reports"] = log_items

    def _check_bonus_and_penalties(self) -> None:
        """Kiểm tra điểm thưởng và điểm trừ."""
        bonus_items = []
        penalty_items = []

        # 1. Bonus: Kế thừa BaseCrawler
        if self.crawler_code and "BaseCrawler" in self.crawler_code:
            self.bonus += 5
            bonus_items.append(f"{GREEN}[BONUS]{RESET} Kế thừa chuẩn BaseCrawler (+5đ)")

        # 2. Bonus: Unit tests
        test_path = Path("tests") / "unit" / f"test_{self.source}_crawler.py"
        if test_path.is_file():
            self.bonus += 5
            bonus_items.append(f"{GREEN}[BONUS]{RESET} Có file unit test: {test_path} (+5đ)")

        # 3. Penalty: Selenium
        if self.crawler_code and ("selenium" in self.crawler_code or "webdriver" in self.crawler_code):
            self.penalty += 5
            penalty_items.append(f"{RED}[PENALTY]{RESET} Sử dụng Selenium không tối ưu (-5đ)")

        # 4. Penalty: Large files in git
        crawler_dir = Path("crawlers") / "sources" / self.source
        for f in crawler_dir.glob("*.json"):
            if f.stat().st_size > 1024 * 1024:
                self.penalty += 10
                penalty_items.append(f"{RED}[PENALTY]{RESET} Commit file data lớn {f.name} ({f.stat().st_size/1024/1024:.1f} MB) (-10đ)")

        self.details["Bonus"] = bonus_items
        self.details["Penalty"] = penalty_items


def print_single_report(res: dict[str, Any]) -> None:
    source = res["source"]
    print(f"\n{CYAN}{BOLD}{'=' * 70}{RESET}")
    print(f"{CYAN}{BOLD} BÁO CÁO ĐÁNH GIÁ CHUẨN ĐẦU RA THU THẬP DỮ LIỆU: [{source.upper()}]{RESET}")
    print(f"{CYAN}{BOLD}{'=' * 70}{RESET}\n")

    for tc_key, logs in res["details"].items():
        if tc_key in ["Bonus", "Penalty"] and not logs:
            continue
        print(f"{BOLD}► {tc_key}:{RESET}")
        for line in logs:
            print(f"   {line}")
        print()

    print(f"{CYAN}{'-' * 70}{RESET}")
    scores = res["scores"]
    print(f"{BOLD}Điểm các tiêu chí chuẩn DoD:{RESET}")
    for k, v in scores.items():
        print(f"  • {k:22s}: {v:2d} điểm")
    print(f"  • {'Bonus':22s}: +{res['bonus']} điểm")
    print(f"  • {'Penalty':22s}: -{res['penalty']} điểm")
    print(f"{CYAN}{'-' * 70}{RESET}")

    total = res["total_score"]
    color = GREEN if total >= 70 else (YELLOW if total >= 40 else RED)
    status_text = "ĐẠT CHUẨN (PASS)" if res["passed"] else "CHƯA ĐẠT CHUẨN (FAIL)"
    print(f"{BOLD}TỔNG ĐIỂM NGHIỆM THU: {color}{BOLD}{total} / 100 ĐIỂM — {status_text}{RESET}\n")


def print_all_summary(results: list[dict[str, Any]]) -> None:
    print(f"\n{CYAN}{BOLD}{'=' * 85}{RESET}")
    print(f"{CYAN}{BOLD} BẢNG TỔNG KẾT ĐÁNH GIÁ NGHIỆM THU TOÀN BỘ 7 SÀN TUYỂN DỤNG (DoD SUMMARY){RESET}")
    print(f"{CYAN}{BOLD}{'=' * 85}{RESET}\n")

    header = f"{'Nguồn':<14} | {'TC1':<4} | {'TC2':<4} | {'TC3':<4} | {'TC4':<4} | {'TC5':<4} | {'TC6':<4} | {'TC7':<4} | {'Bonus':<5} | {'Phạt':<4} | {'Tổng':<6} | {'Kết Quả':<10}"
    print(f"{BOLD}{header}{RESET}")
    print("-" * len(header))

    for r in results:
        sc = r["scores"]
        src = r["source"]
        tot = r["total_score"]
        status = f"{GREEN}PASS{RESET}" if r["passed"] else f"{RED}FAIL{RESET}"
        print(
            f"{src:<14} | {sc['TC1_TwoPhase']:<4} | {sc['TC2_SafeSkip']:<4} | "
            f"{sc['TC3_Recrawl21d']:<4} | {sc['TC4_Samples']:<4} | {sc['TC5_Lakehouse']:<4} | "
            f"{sc['TC6_ArchitectureDoc']:<4} | {sc['TC7_Reports']:<4} | "
            f"+{r['bonus']:<4} | -{r['penalty']:<3} | {BOLD}{tot:>3}/100{RESET} | {status:<10}"
        )

    print(f"\n{CYAN}{BOLD}{'=' * 85}{RESET}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiểm tra và chấm điểm tự động hồ sơ nghiệm thu thu thập dữ liệu (DoD)")
    parser.add_argument("--source", help="Tên nguồn (VD: topcv, vietnamworks, topdev...)")
    parser.add_argument("--all", action="store_true", help="Chấm điểm toàn bộ 7 sàn tuyển dụng")
    args = parser.parse_args()

    if not args.source and not args.all:
        parser.print_help()
        return 1

    if args.all:
        results = []
        for src in ALL_SOURCES:
            scorer = DoDScorer(src)
            results.append(scorer.evaluate())
        print_all_summary(results)
        return 0

    source = args.source.strip().lower()
    scorer = DoDScorer(source)
    res = scorer.evaluate()
    print_single_report(res)
    return 0 if res["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
