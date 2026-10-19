# -*- coding: utf-8 -*-
"""Parser ITViec — RAW-FIRST (Zero Information Loss).

Nguyên tắc (Mục 7A + skill crawling-architect/job-crawler-analyzer):
- KHÔNG ép schema hẹp, KHÔNG format lương/skills ở tầng cào.
- Bảo toàn JSON-LD `@type=JobPosting` NGUYÊN VĂN (đây là nguồn cấu trúc richest
  mà site render sẵn; field `description` trong nó là HTML gốc của site, giữ nguyên).
-与各 section (Mô tả / Yêu cầu / Tại sao bạn sẽ yêu thích…) lưu dạng TEXT sạch
  (không nhồi `_html` vào envelope — HTML thô đầy đủ đã lưu riêng thành file .html).
- Site không cung cấp field nào thì KHÔNG tự bịa (ví dụ seniority).
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

import hashlib

from crawlers.common.url_ledger import calculate_container_html_hash
from crawlers.common.utils import clean_text, text_to_clean_lines
from crawlers.sources.itviec import config as C


def extract_job_id(url: str) -> str:
    """ITViec dùng slug làm định danh ổn định (data-job-key UUID chỉ là tracking).

    Args:
        url: URL chi tiết (đã hoặc chưa canonical).

    Returns:
        Slug (đoạn path cuối sau /viec-lam-it/), hoặc hash 8 ký tự của URL nếu lạ.
    """
    path = urlparse(url).path
    m = re.search(r"/viec-lam-it/([^/?#]+)", path)
    if m:
        return m.group(1)
    from crawlers.common.url_ledger import generate_url_hash
    return generate_url_hash(url)[:12]


def is_job_url(url: str) -> bool:
    """URL là TIN TUYỂN DỤNG (không phải trang chuyên mục/kỹ năng/thành phố).

    Kiểm chứng trên ledger 2026-10-18: 112/112 DONE khớp mẫu này; trang lọc
    (/viec-lam-it/<skill>, /viec-lam-it/<skill>/<city>) có <=1 segment và KHÔNG
    kết thúc bằng -<số>. Ngoại lệ: job_id có thể chứa số ở giữa (vd '...id12287-vpbank-1219')
    -> bắt buộc KẾT THÚC '-<số>', không chỉ 'chứa số'.
    """
    if not url:
        return False
    rest = urlparse(url).path[len(C.DETAIL_PATH_PREFIX):] if urlparse(url).path.startswith(C.DETAIL_PATH_PREFIX) else ""
    seg = [s for s in rest.split("/") if s]
    return len(seg) == 1 and bool(re.search(r"-\d+$", seg[0]))


def filter_job_urls(urls: List[str]) -> "tuple[List[str], List[str]]":
    """Tách (job_urls, non_job_urls) từ danh sách URL sitemap."""
    jobs, non = [], []
    for u in urls:
        (jobs if is_job_url(u) else non).append(u)
    return jobs, non


def sync_mode() -> bool:
    """Chế độ sync MinIO cho ITViec. Set env ITVIEC_SYNC=0 khi chạy SIMULATION/ledger tạm
    để KHÔNG bao giờ đụng MinIO thật (bảo vệ ledger production)."""
    return os.getenv("ITVIEC_SYNC", "1") != "0"


def local_catalog_count(ledger) -> int:
    """Số bản ghi trong catalog LOCAL (đọc từ đĩa)."""
    try:
        return len(json.load(open(ledger.catalog_file, encoding="utf-8")))
    except Exception:
        return 0


def remote_catalog_count(ledger) -> Optional[int]:
    """Số bản ghi catalog ITViec trên MinIO; None nếu chưa đọc được."""
    try:
        import boto3
        from botocore.client import Config
        ep = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
        bkt = os.getenv("MINIO_BUCKET", "vn-it-jobs")
        c = boto3.client(
            "s3", endpoint_url=ep,
            aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minioadmin"),
            aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
            config=Config(signature_version="s3v4", connect_timeout=3, retries={"max_attempts": 1}),
            region_name="us-east-1",
        )
        obj = c.get_object(Bucket=bkt, Key=f"url_ledger/{ledger.source}/catalog_master.json")
        rec = json.loads(obj["Body"].read())
        return len(rec) if isinstance(rec, dict) else None
    except Exception:
        return None


def can_upload_catalog(local_count: int, remote_count: Optional[int]) -> bool:
    """Cho ghi catalog local lên MinIO khi: local>0 VÀ (chưa có remote HOẶC local>=remote).

    Chặn catalog nhỏ/rỗng ghi đè catalog lớn hơn (đảm bảo #2/#3). Khi local<remote thường là
    ledger tạm/ít bản ghi -> không upload.
    """
    if local_count <= 0:
        return False
    if remote_count is None:
        return True
    return local_count >= remote_count


def parse_listing(html: str) -> List[Dict[str, Any]]:
    """Trích danh sách job từ trang listing. Đã verify: 20 `div.job-card`/trang.

    Trả về list {job_id, url (canonical-ready absolute), title, company}.
    """
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(C.LISTING_CARD_SELECTOR)
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for card in cards:
        # Slug ưu tiên lấy từ data-attribute (bền nhất), fallback vào h3 a[href].
        slug = card.get(C.LISTING_SLUG_ATTR)
        a_tag = card.select_one(C.LISTING_TITLE_LINK) or card.select_one(
            "a[href^='/viec-lam-it/']"
        )
        href = a_tag.get("href") if a_tag else None

        url: Optional[str] = None
        if slug:
            url = urljoin(C.BASE_URL, C.DETAIL_PATH_PREFIX + str(slug))
        elif href:
            # href có thể là absolute (probe thấy h3 a trả absolute) -> dùng thẳng
            url = href if href.startswith("http") else urljoin(C.BASE_URL, href)

        if not url or "/viec-lam-it/" not in url:
            continue

        # Lọc link skill-tag / location (không phải bài đăng chi tiết):
        #  bài đăng luôn có 1 slug chứa dấu gạch nối và không rỗng.
        job_id = extract_job_id(url)
        if not job_id or job_id in seen:
            continue
        seen.add(job_id)

        title = clean_text(a_tag.get_text()) if a_tag else None
        comp_el = card.select_one(C.LISTING_COMPANY_LINK) or card.select_one(
            ".company, [class*='company' i]"
        )
        company = clean_text(comp_el.get_text()) if comp_el else None
        out.append({"job_id": job_id, "url": url, "title": title, "company": company})

    return out


def _find_jobposting_jsonld(soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
    """Lấy object JSON-LD @type=JobPosting nguyên văn (site SSR sẵn)."""
    for sc in soup.find_all("script", type="application/ld+json"):
        raw = sc.string or sc.get_text() or ""
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        candidates = obj if isinstance(obj, list) else [obj]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == C.JSONLD_TYPE:
                return item
    return None


def _extract_sections(soup: BeautifulSoup) -> Dict[str, Any]:
    """Phân tách các khối section theo heading (Mô tả / Yêu cầu / Tại sao…).

    Key = text heading gốc (nguyên văn, không chuẩn hóa); value = list dòng sạch.
    """
    sections: Dict[str, Any] = {}
    containers = soup.select(C.DETAIL_SECTION_CONTAINER)
    if containers:
        for box in containers:
            heading_el = box.find(["h2", "h3"])
            heading = clean_text(heading_el.get_text()) if heading_el else ""
            body_lines = text_to_clean_lines(box.get_text("\n"))
            if heading:
                body_lines = [ln for ln in body_lines if ln != heading]
            key = heading or f"section_{len(sections)}"
            sections[key] = body_lines
        return sections

    # Fallback: gom text theo từng h2 tới h2 kế tiếp
    for h2 in soup.select(C.DETAIL_SECTION_HEADING):
        heading = clean_text(h2.get_text())
        lines: List[str] = []
        for sib in h2.find_next_siblings():
            if sib.name in ("h1", "h2"):
                break
            lines.extend(text_to_clean_lines(sib.get_text("\n")))
        if heading:
            sections[heading] = lines
    return sections


def _norm_name(s: str) -> str:
    """Chuẩn hoá tên để so khớp: bỏ dấu, lowercase, gộp khoảng trắng."""
    s = clean_text(s or "")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _company_anchors(soup: BeautifulSoup) -> List[Any]:
    return [a for a in soup.select('a[href*="/nha-tuyen-dung/"]') if a.get("href")]


def _resolve_company(
    soup: BeautifulSoup, jsonld: Optional[Dict[str, Any]], job_id: Optional[str]
) -> "tuple[Optional[str], Optional[str]]":
    """Suy (company_name, company_url) đáng tin cậy; KHÔNG lấy anchor đầu tiên.

    - name: ưu tiên JSON-LD hiringOrganization.name, rồi khối .employer-name trong JD.
    - url : anchor trong .employer-name / khối jd-main, hoặc khớp theo TÊN, hoặc khớp
            slug công ty với chuỗi token liên tiếp trong job_id.
    - Không có cơ sở -> None (không đoán, không lấy sidebar "Nhà tuyển dụng nổi bật").
    """
    org = (jsonld or {}).get("hiringOrganization") if isinstance(jsonld, dict) else None
    name = clean_text(org.get("name")) if isinstance(org, dict) and org.get("name") else None

    em = soup.select_one(C.DETAIL_EMPLOYER_NAME) if getattr(C, "DETAIL_EMPLOYER_NAME", "") else None
    if not name and em is not None:
        name = clean_text(em.get_text()) or None

    anchors = _company_anchors(soup)
    url = None

    # 1) anchor bao quanh / được bọc bởi .employer-name
    if em is not None:
        a = em.find("a", href=re.compile(r"/nha-tuyen-dung/")) or em.find_parent(
            "a", href=re.compile(r"/nha-tuyen-dung/")
        )
        if a is not None:
            url = a.get("href")
    # 2) anchor trong khối JD chính (jd-main)
    if not url and getattr(C, "JD_MAIN_SELECTOR", ""):
        jd = soup.select_one(C.JD_MAIN_SELECTOR)
        a = jd.select_one('a[href*="/nha-tuyen-dung/"]') if jd is not None else None
        if a is not None:
            url = a.get("href")
    # 3) khớp anchor có text == tên công ty
    if not url and name:
        nn = _norm_name(name)
        for a in anchors:
            if nn and _norm_name(a.get_text()) == nn:
                url = a.get("href")
                break
    # 4) khớp slug công ty (href) với chuỗi token LIÊN TIẾP trong job_id
    if not url and job_id:
        jt = [t for t in re.split(r"[^a-z0-9]+", job_id.lower()) if t]
        for a in anchors:
            slug = urlparse(a["href"]).path.rstrip("/").split("/")[-1]
            st = [t for t in re.split(r"[^a-z0-9]+", slug.lower()) if t]
            if st and any(jt[i:i + len(st)] == st for i in range(max(0, len(jt) - len(st) + 1))):
                url = a.get("href")
                if not name:
                    name = clean_text(a.get_text()) or None
                break
    # name vẫn thiếu mà đã có url -> lấy text của anchor tương ứng
    if not name and url:
        for a in anchors:
            if a.get("href") == url:
                name = clean_text(a.get_text()) or None
                break
    return (name or None), (url or None)


def parse_detail(html: str, job_id: Optional[str] = None) -> Dict[str, Any]:
    """Trả về `raw_payload` cho envelope — giữ nguyên tối đa dữ liệu site cung cấp.

    Không chứa full HTML (đã lưu file .html riêng); chứa JSON-LD verbatim + text.
    """
    soup = BeautifulSoup(html, "html.parser")
    jsonld = _find_jobposting_jsonld(soup)

    h1 = soup.select_one(C.DETAIL_H1_SELECTOR)
    title = clean_text(h1.get_text()) if h1 else (jsonld or {}).get("title")

    # Company: ƯU TIÊN JSON-LD hiringOrganization.name; KHÔNG dùng anchor đầu tiên
    # (dễ dính sidebar "Nhà tuyển dụng nổi bật"). company_url khớp theo tên/slug job.
    company_name, company_url = _resolve_company(soup, jsonld, job_id)

    # Skill tags thô (JSON-LD skills là 1 chuỗi; giữ nguyên, KHÔNG tách list ở tầng raw)
    skill_tags: List[str] = []
    if jsonld and isinstance(jsonld.get("skills"), str):
        skill_tags.append(jsonld["skills"])

    # Lương hiển thị nguyên văn (có thể là chuỗi gate "Đăng nhập để xem mức lương").
    # Siết selector: bỏ link nhiễu (báo cáo/khảo sát lương), chỉ nhận chuỗi có tín hiệu lương.
    salary_display_text = None
    _sal_tokens = ("triệu", "usd", "$", "đăng nhập để xem", "thỏa thuận", "thoả thuận",
                   "thương lượng", "mức lương", "sign in to view", "cạnh tranh")
    _sal_noise = ("báo cáo", "khảo sát", "survey", "salary report", "xem ngay")
    for el in soup.select("[class*='salary' i]"):
        t = clean_text(el.get_text(" "))
        if not t or len(t) > 80:
            continue
        low = t.lower()
        if any(n in low for n in _sal_noise):
            continue
        if any(tok in low for tok in _sal_tokens):
            salary_display_text = t
            break

    # `salary_range` từ data-layer analytics của ITviec (attribute trên div.jd-main).
    # Đây là trường CÔNG KHAI thứ hai: có giá trị khi NTD công khai lương, rỗng khi gate.
    # Không suy diễn/bịa: gate -> None.
    salary_range_datalayer = None
    dl_el = soup.select_one("[data-jobs--save-data-layer-value]")
    if dl_el:
        try:
            dl = json.loads(dl_el.get("data-jobs--save-data-layer-value", "{}"))
            if isinstance(dl, dict):
                salary_range_datalayer = dl.get("salary_range") or None
        except Exception:
            salary_range_datalayer = None

    raw_payload: Dict[str, Any] = {
        "title": title,
        "company_name": company_name,
        "company_url": company_url,
        "salary_display_text": salary_display_text,
        "skill_tags": skill_tags,
        "salary_range_datalayer": salary_range_datalayer,
        "sections": _extract_sections(soup),
        # JSON-LD JobPosting NGUYÊN VĂN (bao gồm description HTML gốc, baseSalary,
        # jobLocation[], datePosted, validThrough, employmentType, experience…).
        "job_posting_jsonld": jsonld,
    }
    # Không tự chèn field site không có (vd seniority). Giữ raw, không normalize.
    return raw_payload


def build_canonical_jsonld(jsonld: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Trả về tập con các field THEO DÕI từ JSON-LD, chỉ để phục vụ băm hash.

    - Lấy đúng danh sách C.HASH_JSONLD_FIELDS; KHÔNG nhét field lạ chỉ vì nó có trong JSON-LD.
    - Bỏ field không hiện diện (không chèn key giả).
    - Không thay thế JSON-LD gốc trong envelope (hàm này chỉ đọc để băm).
    """
    if not isinstance(jsonld, dict):
        return {}
    return {k: jsonld[k] for k in C.HASH_JSONLD_FIELDS if k in jsonld}


def compute_content_hash(
    html: str,
    jsonld: Optional[Dict[str, Any]],
    container_selector: Optional[str] = None,
) -> str:
    """content_hash LAI (Phương án A, đã duyệt):

        SHA256( clean_text(container)  +  canonical_jsonld )

    - clean_text(container): SHA-256 của text khối JD (script/style đã gỡ) -> không đổi
      khi chỉ layout/nav/footer/tracking đổi.
    - canonical_jsonld: SHA-256 của JSON-LD subset (baseSalary/skills/...) -> đổi khi
      nhà tuyển dụng sửa lương/kỹ năng/mô tả (dù nằm trong <script> bị text-hash bỏ qua).
    """
    container = container_selector or C.JD_HASH_CONTAINER
    text_part = calculate_container_html_hash(html, container_selector=container)
    canon = json.dumps(
        build_canonical_jsonld(jsonld), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    jsonld_part = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    return hashlib.sha256((text_part + jsonld_part).encode("utf-8")).hexdigest()


def parse_sitemap(xml_text: str) -> List[str]:
    """Trích toàn bộ <loc> từ một sitemap XML (urlset HOẶC sitemapindex).

    Pure function (không mạng) -> dễ unit test offline.
    """
    if not xml_text:
        return []
    return [m.strip() for m in re.findall(r"<loc>\s*(.*?)\s*</loc>", xml_text, flags=re.IGNORECASE)]
