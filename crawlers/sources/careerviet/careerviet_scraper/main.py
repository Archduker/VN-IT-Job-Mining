"""
main.py - File điều phối chính (CLI Runner)
Khởi chạy CareerViet Scraper với các tùy chọn CLI.
"""

import asyncio
import argparse
import logging
import sys
import os

# Fix UTF-8 encoding trên Windows (tránh UnicodeEncodeError với ký tự tiếng Việt)
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

# Thêm thư mục cha vào PYTHONPATH để import module
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# LOGGING SETUP
# ============================================================

def setup_logging(verbose: bool = False):
    """Thiết lập logging với format đẹp và ghi ra file."""
    log_level = logging.DEBUG if verbose else logging.INFO

    # Format cho console
    console_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # Format cho file (đầy đủ hơn)
    file_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler
    log_file = Path(__file__).parent.parent / "scraper_run.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Tắt bớt log của thư viện ngoài
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return root_logger


# ============================================================
# CLI ARGUMENT PARSER
# ============================================================

def parse_args():
    """Định nghĩa các tham số dòng lệnh."""
    parser = argparse.ArgumentParser(
        prog="careerviet-scraper",
        description=(
            "CareerViet Job Scraper – Thu thập dữ liệu việc làm tự động\n"
            "Hỗ trợ 7 danh mục: CNTT, Viễn thông, TMĐT, Thiết kế, Điện tử, Tài chính"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  python main.py                          # Chạy đầy đủ (tất cả danh mục)
  python main.py --resume                 # Tiếp tục từ checkpoint
  python main.py --category "CNTT - Phần mềm"  # Chỉ cào 1 danh mục
  python main.py --reset                  # Xóa checkpoint và chạy lại từ đầu
  python main.py --verbose                # Log chi tiết (debug mode)
  python main.py --output custom.json     # Xuất ra file tùy chỉnh
        """,
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Tiếp tục từ checkpoint (mặc định: True)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        default=False,
        help="Xóa checkpoint và bắt đầu lại từ đầu",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Chỉ cào một danh mục cụ thể (tên đầy đủ)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Đường dẫn file JSON output (mặc định: careerviet_raw_jobs.json)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Giới hạn số trang listing mỗi danh mục (debug/test)",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        help="Giới hạn tổng số job cào (debug/test)",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        default=False,
        help="Chạy browser ở chế độ có giao diện (không headless)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Hiển thị log chi tiết (debug level)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help=f"Số tab đồng thời (mặc định: {__import__('careerviet_scraper.config', fromlist=['MAX_CONCURRENT_PAGES']).MAX_CONCURRENT_PAGES})",
    )
    parser.add_argument(
        "--delay-min",
        type=float,
        default=None,
        help="Delay tối thiểu giữa requests (giây)",
    )
    parser.add_argument(
        "--delay-max",
        type=float,
        default=None,
        help="Delay tối đa giữa requests (giây)",
    )

    return parser.parse_args()


# ============================================================
# MAIN ENTRY POINT
# ============================================================

async def main_async():
    """Hàm chính bất đồng bộ."""
    args = parse_args()

    # Setup logging trước tiên
    logger = setup_logging(args.verbose)
    logger.info("=" * 60)
    logger.info("  CAREERVIET JOB SCRAPER – KHỞI ĐỘNG")
    logger.info("=" * 60)

    # Import config & scraper sau khi biết args
    from careerviet_scraper import config
    from careerviet_scraper.scraper import CareerVietScraper

    # ---- Ghi đè config nếu có tham số CLI ----
    if args.output:
        config.OUTPUT_FILE = args.output
        logger.info(f"[Config] Output file: {config.OUTPUT_FILE}")

    if args.concurrency:
        config.MAX_CONCURRENT_PAGES = args.concurrency
        logger.info(f"[Config] Concurrency: {config.MAX_CONCURRENT_PAGES}")

    if args.delay_min:
        config.DELAY_MIN = args.delay_min
    if args.delay_max:
        config.DELAY_MAX = args.delay_max
    if args.delay_min or args.delay_max:
        logger.info(f"[Config] Delay: {config.DELAY_MIN}s – {config.DELAY_MAX}s")

    if args.headful:
        # Override BROWSER_ARGS để chạy headful
        config.BROWSER_ARGS = [
            arg for arg in config.BROWSER_ARGS
            if arg != "--disable-gpu"
        ]
        logger.info("[Config] Chạy ở chế độ HEADFUL (có giao diện browser).")

    # ---- Filter danh mục nếu có --category ----
    if args.category:
        filtered = [c for c in config.TARGET_CATEGORIES if c["name"] == args.category]
        if not filtered:
            available = [c["name"] for c in config.TARGET_CATEGORIES]
            logger.error(
                f"Danh mục '{args.category}' không tồn tại.\n"
                f"Các danh mục hợp lệ: {available}"
            )
            sys.exit(1)
        config.TARGET_CATEGORIES = filtered
        logger.info(f"[Config] Chỉ cào danh mục: {args.category}")

    # ---- Reset checkpoint nếu yêu cầu ----
    if args.reset:
        if os.path.exists(config.CHECKPOINT_FILE):
            os.remove(config.CHECKPOINT_FILE)
            logger.info(f"[Config] Đã xóa checkpoint: {config.CHECKPOINT_FILE}")
        if os.path.exists(config.OUTPUT_FILE):
            confirm = input(
                f"Bạn có muốn xóa file output cũ '{config.OUTPUT_FILE}' không? (y/N): "
            )
            if confirm.strip().lower() == "y":
                os.remove(config.OUTPUT_FILE)
                logger.info(f"[Config] Đã xóa output cũ: {config.OUTPUT_FILE}")

    # ---- In thông tin khởi chạy ----
    logger.info(f"[Config] OUTPUT  : {config.OUTPUT_FILE}")
    logger.info(f"[Config] CHECKPOINT: {config.CHECKPOINT_FILE}")
    logger.info(
        f"[Config] DANH MỤC: "
        f"{[c['name'] for c in config.TARGET_CATEGORIES]}"
    )

    # ---- Chạy scraper ----
    scraper = CareerVietScraper()
    await scraper.run()


def main():
    """Entry point đồng bộ cho CLI."""
    try:
        # Windows: Playwright yêu cầu ProactorEventLoop để chạy subprocess
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        asyncio.run(main_async())

    except KeyboardInterrupt:
        print("\n[main] Đã dừng bởi người dùng.")
        sys.exit(0)
    except Exception as e:
        logging.critical(f"[main] Lỗi không xử lý được: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
