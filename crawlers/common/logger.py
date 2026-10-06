"""
crawlers.common.logger
~~~~~~~~~~~~~~~~~~~~~~~
Structured logging setup dùng chung cho tất cả crawlers.

Cung cấp log format chuẩn với timestamp, level, module và message.
Hỗ trợ log ra console (stdout) và file đồng thời.

Functions:
    get_logger(name, level, log_file) -> logging.Logger
        Trả về logger đã cấu hình cho module tương ứng.

Usage:
    >>> from crawlers.common.logger import get_logger
    >>> logger = get_logger(__name__)
    >>> logger.info("Crawling started | source=topdev | batch=001")
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────────────────────
# Log format
# ─────────────────────────────────────────────────────────────
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Root logger cho toàn bộ package
_ROOT_LOGGER_NAME = "crawlers"

# Cache để không tạo lại handler nhiều lần
_configured_loggers: set[str] = set()


def get_logger(
    name: str,
    level: int = logging.INFO,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Tạo và cấu hình logger cho một module.

    Logger được cấu hình một lần duy nhất (idempotent).
    Lần gọi sau với cùng tên sẽ trả về logger đã cấu hình sẵn.

    Args:
        name: Tên logger — thường dùng __name__ của module.
            Ví dụ: "crawlers.sources.topdev.crawler".
        level: Log level (logging.DEBUG, INFO, WARNING, ERROR).
            Default: logging.INFO.
        log_file: Đường dẫn file log (optional).
            Nếu None, chỉ log ra console.
            Nếu có, log ra cả console và file đồng thời.

    Returns:
        logging.Logger đã cấu hình.

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("source=topdev | page=1 | jobs_found=25")

        >>> # Log ra cả file
        >>> logger = get_logger(__name__, log_file="logs/topdev.log")
    """
    logger = logging.getLogger(name)

    # Idempotent: chỉ configure 1 lần
    if name in _configured_loggers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Handler: stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    # Handler: file (optional)
    if log_file:
        _add_file_handler(logger, log_file, formatter, level)

    # Tránh propagate lên root logger (tránh log duplicate)
    logger.propagate = False

    _configured_loggers.add(name)
    return logger


def _add_file_handler(
    logger: logging.Logger,
    log_file: str,
    formatter: logging.Formatter,
    level: int,
) -> None:
    """Thêm FileHandler vào logger.

    Args:
        logger: Logger cần thêm handler.
        log_file: Đường dẫn file log.
        formatter: Log formatter.
        level: Log level cho file handler.
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)


def configure_root_logger(level: int = logging.INFO) -> None:
    """Cấu hình root logger cho toàn bộ package crawlers.

    Gọi hàm này một lần ở entry point (run.py hoặc Airflow DAG)
    để đảm bảo tất cả logger con đều có cùng format.

    Args:
        level: Log level. Default: logging.INFO.

    Examples:
        >>> configure_root_logger(logging.DEBUG)
    """
    get_logger(_ROOT_LOGGER_NAME, level=level)
