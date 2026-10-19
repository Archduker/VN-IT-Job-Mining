# -*- coding: utf-8 -*-
"""Raw Envelope (Raw As-Is / Zero Information Loss) cho nguồn CareerViet.

Module NÀY KHÔNG thay thế ``parse_item()`` của ``crawler.py`` (vẫn trả ``JobRecord``
Schema v1 cho Airflow + DataQualityChecker). Nó cung cấp tầng thu thô riêng theo mẫu
``{metadata, raw_payload}`` của skill ``crawling-architect``:

- ``raw_payload`` giữ các khối DOM theo ĐÚNG tên class CSS gốc của CareerViet
  (``title``, ``job-company-name``, ``detail-box``, ``detail-row``, ``job-tags``,
  ``map``), không ép schema, không đổi tên trừu tượng, không lưu ``__html``.
- ``job-posting-schema`` là khóa riêng chứa nguyên bản JSON-LD JobPosting
  (tái dùng logic bóc JSON-LD từ bản ``backup/careerviet-raw``), trả ``None``
  khi thiếu hoặc JSON hỏng — tuyệt đối không làm crash.

Hàm băm ``container_text_for_hash`` cho phép TẮM tạm 2 cặp nhãn ngày tháng động
("Ngày cập nhật", "Hết hạn nộp") nằm trong khối ``.job-detail-page`` (đã kiểm
30/30 trang đều có). Đây là LỰA CHỌN TẠM chờ nhóm trưởng quyết (xem docstring).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from bs4 import BeautifulSoup

SOURCE = "careerviet"
# Phiên bản envelope thô (tách biệt CRAWLER_VERSION của parse_item Schema v1).
SCRAPER_VERSION = "1.0.0-raw-envelope"
CONTAINER_SELECTOR = ".job-detail-page"
# 2 cặp nhãn đổi giá trị theo thời điểm -> dễ gây "nhảy hash oan" khi re-crawl 21 ngày.
VOLATILE_LABELS: tuple[str, ...] = ("Ngày cập nhật", "Hết hạn nộp")


def _normalize_ws(text: str) -> str:
    """Chuẩn hóa khoảng trắng: mọi chuỗi whitespace -> 1 dấu cách, rồi strip."""
    return re.sub(r"\s+", " ", text or "").strip()


def _el_text(el) -> str:
    """Văn bản thô của 1 node, dùng get_text(' ') + chuẩn hóa khoảng trắng."""
    if el is None:
        return ""
    return _normalize_ws(el.get_text(" ", strip=True))


def extract_job_posting_jsonld(soup: BeautifulSoup) -> Optional[Any]:
    """Bóc JSON-LD JobPosting nguyên bản. Không bao giờ raise; thiếu/hỏng -> None.

    Ưu tiên ``<script id="job-posting-schema">``; fallback quét mọi
    ``<script type="application/ld+json">`` có chuỗi "JobPosting".
    """
    try:
        jp_script = soup.find("script", id="job-posting-schema")
        if not jp_script:
            for s in soup.find_all("script", type="application/ld+json"):
                if s.string and '"JobPosting"' in s.string:
                    jp_script = s
                    break
        if not jp_script or not jp_script.string:
            return None

        loaded = json.loads(jp_script.string.strip())
        if isinstance(loaded, dict) and loaded.get("@type") == "JobPosting":
            return loaded
        if isinstance(loaded, list):
            for el in loaded:
                if isinstance(el, dict) and el.get("@type") == "JobPosting":
                    return el
            return loaded or None
        return loaded
    except Exception:
        return None


def _select_container(soup: BeautifulSoup, container_selector: str):
    """Chọn khối container băm hash, fallback body -> toàn bộ soup (như hàm chung)."""
    return soup.select_one(container_selector) or soup.body or soup


def _clean_container(target) -> None:
    """Gỡ các thẻ động khỏi CHÍNH target (script/style/iframe/noscript/svg)."""
    for tag in target(["script", "style", "iframe", "noscript", "svg"]):
        tag.decompose()


def _strip_volatile_labels(target) -> None:
    """Gỡ các khối <li> chứa nhãn 'Ngày cập nhật'/'Hết hạn nộp' khỏi target (bản sao)."""
    blocks = []
    seen = set()
    for label in VOLATILE_LABELS:
        needle = label.lower()
        for node in target.find_all(string=lambda s, n=needle: n in (str(s) or "").lower()):
            blk = node.find_parent("li")
            if blk is None:
                blk = node.parent
            if blk is None or id(blk) in seen:
                continue
            seen.add(id(blk))
            blocks.append(blk)
    for blk in blocks:
        try:
            blk.decompose()
        except Exception:
            pass


def container_text_for_hash(
    html: str,
    container_selector: str = CONTAINER_SELECTOR,
    exclude_volatile_dates: bool = True,
) -> str:
    """Trả ĐÚNG phần text mà ``calculate_container_html_hash`` sẽ băm, sau khi:

    1. parse html, chọn khối ``container_selector`` (fallback body -> soup);
    2. gỡ ``script/style/iframe/noscript/svg``;
    3. ``get_text(separator=" ", strip=True)`` rồi chuẩn hóa khoảng trắng.

    Khi ``exclude_volatile_dates=True``: trên BẢN SAO container, loại thêm các khối
    <li> chứa nhãn "Ngày cập nhật" và "Hết hạn nộp" (2 chuỗi ngày tháng đổi theo
    thời điểm, nằm trong ``.job-detail-page`` ở 30/30 trang đã kiểm).

    TƯƠNG THÍCH: với ``exclude_volatile_dates=False``, kết quả ``sha256`` của chuỗi
    trả về trùng khớp ``crawlers.common.url_ledger.calculate_container_html_hash``
    (hàm chung KHÔNG bị sửa; thao tác chỉ trên bản sao parse lại từ html).

    [TẠM THỜI] Việc bỏ 2 nhãn ngày là quyết định của tầng cào Careerviet, chờ nhóm
    trưởng chốt chính sách hash toàn hệ thống (xem docs/crawl/careerviet.md).
    """
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    target = _select_container(soup, container_selector)
    _clean_container(target)
    if exclude_volatile_dates:
        _strip_volatile_labels(target)
    return _normalize_ws(target.get_text(" ", strip=True))


def hash_container_text(text: str) -> str:
    """SHA-256 hex của chuỗi text đã làm sạch (dùng làm content_hash envelope)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_raw_payload(html: str) -> dict[str, Any]:
    """Bóc các khối DOM thô theo tên class CSS gốc + JSON-LD nguyên bản.

    Raw As-Is: giữ nguyên văn text (get_text(' ') + chuẩn hóa ws), không parse
    lương/thành số, không gom bullet, không đổi tên class thành tên trừu tượng.
    """
    soup = BeautifulSoup(html, "html.parser")
    page = soup.select_one(CONTAINER_SELECTOR) or soup

    # 1. Tiêu đề (h1.title) và công ty (a.job-company-name / a.employer)
    title_el = page.select_one("h1.title") or page.find("h1") or page.select_one(".job-title")
    company_el = page.select_one(
        "a.job-company-name, a.employer, .company-name, a.company"
    )

    # 2. detail-box: các dòng key-value metadata, giữ nguyên văn từng dòng <li>
    detail_box = [
        _el_text(li)
        for li in page.select(".detail-box li, .box-item li, ul.list-info li")
    ]
    detail_box = [t for t in detail_box if t]

    # 3. detail-row: các section (Mô tả / Yêu cầu / Phúc lợi / ...) -> {header: text}
    detail_row: dict[str, Any] = {}
    for s in page.select(".detail-row, .job-description"):
        header = s.find(["h2", "h3", "h4"])
        key = _el_text(header) if header else ""
        value = _el_text(s)
        if not key and not value:
            continue
        key = key or f"section_{len(detail_row) + 1}"
        if key in detail_row:
            if isinstance(detail_row[key], list):
                detail_row[key].append(value)
            else:
                detail_row[key] = [detail_row[key], value]
        else:
            detail_row[key] = value

    # 4. job-tags: pill tag chuyên môn (rỗng nếu tin không có tag — 14/30 tin)
    tag_items: list[str] = []
    for a in page.select(".job-tags a, .tag-item a, .tag-item, .job-tags li"):
        txt = _el_text(a)
        if txt and not txt.startswith("+") and txt not in tag_items:
            tag_items.append(txt)

    # 5. map: địa điểm, nhiều thẻ <a> nối bằng ", " (đúng nguyên văn web)
    location = None
    map_el = page.select_one("div.map")
    if map_el:
        a_tags = [_el_text(a) for a in map_el.find_all("a")]
        a_tags = [t for t in a_tags if t]
        location = ", ".join(a_tags) if a_tags else (_el_text(map_el) or None)

    # 6. "Ngành nghề" NGUYÊN VĂN (nhãn IT): lấy phần giá trị của mọi dòng detail-box
    #    bắt đầu bằng nhãn "Ngành nghề", khử trùng lặp giữ thứ tự. KHÔNG lọc bỏ tin
    #    nào ở tầng raw — đây chỉ là bản sao thô để truy vết, chưa phân loại.
    industry_vals: list[str] = []
    for line in detail_box:
        if line.startswith("Ngành nghề"):
            val = _normalize_ws(line[len("Ngành nghề"):]).lstrip(":").strip()
            if val and val not in industry_vals:
                industry_vals.append(val)

    return {
        "title": _el_text(title_el),
        "job-company-name": _el_text(company_el),
        "detail-box": detail_box,
        "detail-row": detail_row,
        "job-tags": tag_items,
        "map": location,
        "Ngành nghề": industry_vals or None,
        "job-posting-schema": extract_job_posting_jsonld(soup),
    }


def build_raw_envelope(
    html: str,
    job_id: str,
    source_url: str,
    source_category: Optional[str] = None,
    version: int = 1,
    scraped_at: Optional[str] = None,
    container_selector: str = CONTAINER_SELECTOR,
    exclude_volatile_dates: bool = True,
) -> dict[str, Any]:
    """Sinh raw envelope ``{metadata, raw_payload}`` cho 1 tin CareerViet.

    Args:
        html: nội dung HTML chi tiết (đọc từ file, không gọi mạng ở đây).
        job_id: id tin (định danh sàn).
        source_url: canonical url bài đăng.
        source_category: nhãn nhóm IT (c1/c61/keyword:developer) — do NGƯỜI GỌI
            tra từ ``category_by_job_id.json`` rồi truyền vào (KHÔNG hardcode
            đường dẫn trong module này).
        version: số phiên bản snapshot (CDC).
        scraped_at: ISO8601 UTC; mặc định thời điểm hiện tại.
        exclude_volatile_dates: bật/tắt tạm bỏ 2 nhãn ngày khi băm hash.

    Returns:
        dict với 2 khóa ``metadata`` và ``raw_payload``.
    """
    cleaned = container_text_for_hash(
        html, container_selector=container_selector, exclude_volatile_dates=exclude_volatile_dates
    )
    metadata = {
        "job_id": job_id,
        "source": SOURCE,
        "source_url": source_url,
        "scraped_at": scraped_at or datetime.now(timezone.utc).isoformat(),
        "scraper_version": SCRAPER_VERSION,
        "version": version,
        "content_hash": hash_container_text(cleaned),
        "source_category": source_category,
    }
    return {"metadata": metadata, "raw_payload": build_raw_payload(html)}
