"""Vẽ biểu đồ EDA cho RAW R4 của CareerViet (1018 envelope thật).

Chỉ đọc file local, KHÔNG gọi mạng. Mọi hình dựng bằng một lệnh:

    python -X utf8 scripts/careerviet_eda_charts.py

Tinh chỉnh (R4): đo thật từ envelope, không áp biên luỹ kế.
Chuẩn nhất quán cho mọi hình: một style duy nhất (bảng 5 màu, nền trắng, bỏ viền
trên/phải, lưới nhạt đúng trục giá trị, dpi 200, nhãn tiếng Việt có dấu qua DejaVu Sans);
tiêu đề NÊU KẾT LUẬN, phụ đề ghi n=..., mỗi hình có dòng nguồn dưới cùng, ghi số + %
trên cột, sắp xếp giảm dần, cột quan trọng nhất tô màu nhấn.

Cấu trúc `raw_payload` thật (raw_envelope.py):
  - `detail-box`  : List[str] - HỘP metadata (Lương / Kinh nghiệm / Cấp bậc / Hình
                    thức / Ngày cập nhật / Hết hạn nộp / Ngành nghề), dòng lặp ×2 để
                    giữ nguyên văn. KHÔNG phải mô tả công việc.
  - `detail-row`  : Dict[str, str] - các SECTION JD thật, key là heading
                    ("Mô tả Công việc", "Yêu Cầu Công Việc", "Phúc lợi", ...)
  - `job-posting-schema.description` : toàn bộ HTML mô tả (giữ nguyên văn)
  - `job-posting-schema.jobBenefits` : chuỗi phân tách dấu phẩy, thuộc bộ từ vựng 15
                    loại phúc lợi cố định của nguồn => đếm được từng phúc lợi (hình 12)

Thước đo: `is_it` giữ nguyên quy tắc lọc "Ngành nghề" chứa "CNTT" / "Phần mềm" để đối
chiếu với `scripts/careerviet_report_fill.py`; ngoài ra tách riêng nhóm `unclassified`
(24 tin rỗng "Ngành nghề") để không gộp nhầm vào "ngoài IT".
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import statistics
import sys
import textwrap
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.text import Text  # noqa: E402

# ---------------------------------------------------------------- phong cách
COLORS = {
    "primary": "#2563eb",   # xanh chủ đạo (cột thông thường)
    "accent":  "#0ea5e9",   # xanh nhẹ (chuỗi phụ)
    "it":      "#2563eb",   # nhóm IT
    "nonit":   "#94a3b8",   # ngoài IT
    "unknown": "#f59e0b",   # không phân loại được
    "hot":     "#dc2626",   # đỏ = cột cần nhấn mạnh nhất
    "grid":    "#e2e8f0",
    "spine":   "#cbd5e1",
    "muted":   "#64748b",
    "ink":     "#0f172a",
}
DPI = 200


def use_default_style() -> None:
    """Áp dụng một style duy nhất cho toàn bộ biểu đồ."""
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "font.family": "DejaVu Sans",
        "axes.edgecolor": COLORS["spine"],
        "axes.linewidth": 0.9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlesize": 13.5,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "axes.grid": False,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "xtick.color": "#334155",
        "ytick.color": "#334155",
        "text.color": COLORS["ink"],
        "legend.frameon": False,
        "axes.unicode_minus": False,
    })


def new_fig(figsize=(9.2, 4.8)):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    return fig, ax


def _text_width_px(fig, renderer, text: str, size: float, weight: str) -> float:
    """Do rong (px) cua chu bang artist Text tam thoi.

    Khong dung `ax.title.get_window_extent()`: khi loc="left", `ax.title` la
    doi tuong tieu de GIUA (rong) nen chieu dai tra ve luon = 0, phep do vo nghia.
    """
    artist = Text(0, 0, text, fontsize=size, fontweight=weight,
                  family=matplotlib.rcParams["font.family"][0])
    artist.set_figure(fig)
    return artist.get_window_extent(renderer).width


def _room_px(fig, ax) -> float:
    """Chỗ còn lại bên phải nhãn trục: tính cả colorbar (axes phụ) nếu có."""
    right = 1.0
    for other in fig.axes:
        if other is ax:
            continue
        pos = other.get_position()
        if pos.x0 >= ax.get_position().x1 - 0.01:
            right = min(right, pos.x0 - 0.015)
    return max(60.0, fig.bbox.width * (right - ax.get_position().x0) - 14)


def _fit_text(fig, renderer, text: str, room: float, sizes, weight: str):
    """Thu nho dan co chu; van dai thi xuong dong. Tra ve (text, fontsize).

    Sau khi xuống dòng phải đo lại từng dòng: tỉ lệ độ dài trung bình có thể cho ra
    một dòng ngắn nhưng nặng chữ hơn chỗ trống (vd 'Chi' 'Minh' rộng hơn 'i' 'n'),
    nên thắt dần số ký tự mỗi dòng cho tới khi không dòng nào tràn.
    """
    width = 0.0
    for s in sizes:
        width = _text_width_px(fig, renderer, text, s, weight)
        if width <= room:
            return text, s
    smallest = sizes[-1]
    per_line = max(8, int(len(text) * room / max(width, 1.0)))
    lines = [text]
    for _ in range(8):
        lines = textwrap.wrap(text, width=per_line) or [text]
        worst = max(_text_width_px(fig, renderer, ln, smallest, weight) for ln in lines)
        if worst <= room or per_line <= 6:
            break
        per_line = max(6, int(per_line * room / worst) - 1)
    return "\n".join(lines), smallest


def decorate(fig, ax, title: str, subtitle: str, source: str, grid: str = "y",
             title_size: float = 13.5) -> None:
    """Tiêu đề = kết luận; phụ đề = n=...; dòng nguồn sát mép dưới; lưới nhạt 1 trục.

    Cả hai dòng đều tự thu nhỏ / xuống dòng theo chiều ngang thật của renderer (đo
    bang artist Text tach rieng, KHONG dung `ax.title` vi khi loc="left" no rong),
    va tru be ngang colorbar neu co - mau: bieu do null rate va heatmap dia diem.

    Do hai lan: lan mot lay chieu ngang khi axes chua co chu, lan hai sau
    `tight_layout` cuoi (dat chu co the lam hep axes/colorbar) -> dung room nho hon.
    """
    if grid in ("x", "y", "both"):
        ax.grid(axis=grid, color=COLORS["grid"], linewidth=0.8)
    else:
        ax.grid(False)
    ax.set_axisbelow(True)
    size0 = title_size
    arts: list = []

    def place(room: float) -> None:
        for a in arts:
            a.remove()
        arts.clear()
        renderer = fig.canvas.get_renderer()
        sub_text, sub_size = _fit_text(fig, renderer, subtitle, room, (9.5, 8.6, 7.8), "normal")
        title_text, t_size = _fit_text(fig, renderer, title, room, (size0, 12.0, 11.0, 10.0), "bold")
        # Tieu de neo duoi cach axes `pad` diem -> phai day len tren phan subtitle da don dong.
        pad = 22 + 13 * sub_text.count("\n") + (20 if title_text.count("\n") else 0)
        ax.set_title(title_text, loc="left", pad=pad, color=COLORS["ink"], fontsize=t_size)
        arts.append(ax.text(0, 1.012, sub_text, transform=ax.transAxes, fontsize=sub_size,
                            color=COLORS["muted"], va="bottom", ha="left"))
        arts.append(fig.text(0.012, 0.012, source, fontsize=8.2, color=COLORS["muted"], ha="left"))

    fig.tight_layout(rect=(0, 0.05, 1, 1))   # co dinh vi tri axes truoc khi do chieu dai chu
    room = _room_px(fig, ax)
    place(room)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    room2 = _room_px(fig, ax)
    if room2 < room - 1:
        place(min(room, room2))


def save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def fmt_int(x) -> str:
    """Số nguyên theo quy ước tiếng Việt: 1018 -> '1.018'."""
    return f"{int(x):,}".replace(",", ".")


def fmt_num(x) -> str:
    """Số thập phân: dùng dấu phẩy kiểu Việt Nam."""
    s = f"{x:g}"
    return s.replace(".", ",") if "." in s else s


def pct(a, b) -> str:
    """Tỷ lệ '%' với thập phân phẩy: 591/1018 -> '58,1%'."""
    return f"{100 * a / b:.1f}%".replace(".", ",") if b else "n/a"


def qstats(values: list[float]) -> dict:
    """n/min/Q1/median/Q3/max/mean của một dãy đã lọc rỗng."""
    v = sorted(values)
    d = {"n": len(v), "min": v[0], "med": statistics.median(v), "max": v[-1],
         "mean": statistics.mean(v)}
    if len(v) >= 4:
        q = statistics.quantiles(v, n=4)
        d["q1"], d["q3"] = q[0], q[2]
    else:
        d["q1"] = d["q3"] = None
    return d


def iqr_txt(q: dict) -> str:
    """Dải tứ phân vị để ghi vào văn bản; ghi rõ khi mẫu dưới 4 điểm."""
    return f"{fmt_num(q['q1'])}-{fmt_num(q['q3'])}" if q["q1"] is not None else "chưa đủ 4 điểm"


# --------------------------------------------------------------------- đọc raw
_TAG_ONLY = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_DT_RE = re.compile(r"^(?:dt=)?(\d{4}-\d{2}-\d{2})$")
_BUCKET_RE = re.compile(r"^(c\d+|keyword:[a-z0-9_-]+)")
IT_KEYWORDS = ("cntt", "phan mem", "phần mềm")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data):
        self.parts.append(data)


def flat_text(html) -> str:
    """Flatten HTML -> text nguyên văn, chỉ gộp whitespace, KHÔNG cắt/rửa từ ngữ."""
    if html is None:
        return ""
    if isinstance(html, (list, tuple)):
        return " ".join(flat_text(x) for x in html).strip()
    if isinstance(html, dict):
        return " ".join(flat_text(v) for v in html.values()).strip()
    s = str(html)
    p = _Text()
    try:
        p.feed(s)
        # `close()` bắt buộc: HTMLParser (convert_charrefs=True) giữ toàn bộ đoạn
        # text sau một `&` không đóng entity ("Nhân viên C&B", "D&C") trong buffer
        # cho tới khi đóng luồng - thiếu nó thì chữ bị mất, đếm thành tin rỗng giả.
        p.close()
        body = "".join(p.parts)
    except Exception:
        body = _TAG_ONLY.sub(" ", s)
    return _WS.sub(" ", body).strip()


def is_null(v) -> bool:
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, (list, tuple, dict)):
        return len(v) == 0
    return v is None or v == "" or v == [] or v == {}


def as_list(v) -> list[str]:
    if is_null(v):
        return []
    if isinstance(v, str):
        return [v.strip()] if v.strip() else []
    if isinstance(v, (list, tuple)):
        out = []
        for i in v:
            s = i.strip() if isinstance(i, str) else flat_text(i).strip()
            if s:
                out.append(s)
        return out
    return [flat_text(v).strip()]


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_salary(schema):
    """Đọc baseSalary JSON-LD (chỉ để EDA, không ghi ngược vào raw)."""
    if not isinstance(schema, dict):
        return None
    bs = schema.get("baseSalary")
    if not isinstance(bs, dict):
        return None
    val = bs.get("value")
    cur = bs.get("currency")
    lo = hi = unit = None
    if isinstance(val, dict):
        lo, hi = num(val.get("minValue")), num(val.get("maxValue"))
        single = num(val.get("value"))
        unit = val.get("unitText")
        if lo is None and hi is None and single is not None:
            lo = hi = single
    else:
        lo = hi = num(val)
    return {"currency": cur, "lo": lo, "hi": hi, "unit": unit}


def to_month_million(parsed) -> float | None:
    """Kết quả parse_salary -> TRIỆU VND/THÁNG; None nếu không đọc an toàn được."""
    if not parsed:
        return None
    if (parsed.get("currency") or "").upper() != "VND":
        return None
    if (parsed.get("unit") or "").upper() not in ("MONTH", ""):
        return None
    pts = [x for x in (parsed.get("lo"), parsed.get("hi")) if x and x > 0]
    if not pts:
        return None
    return round(sum(pts) / len(pts) / 1e6, 2)


def salary_month_m(schema) -> float | None:
    """Dải lương giữa trung bình, tính trực tiếp từ JSON-LD schema."""
    return to_month_million(parse_salary(schema))


def split_benefits(value) -> list[str]:
    """Tách `jobBenefits` (chuỗi phân tách dấu phẩy/;/|) -> danh sách phúc lợi."""
    if is_null(value):
        return []
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            s = (v.strip() if isinstance(v, str) else flat_text(v).strip())
            if s:
                out.append(s)
        return out
    return [p.strip() for p in re.split(r"[,;|]", flat_text(value)) if p.strip()]


def bucket_of(source_category) -> str:
    """Nhãn bucket từ `metadata.source_category` (c1 / c61 / c37_digital_mkt / ...).

    Đây là nhãn do Phase 1 gán cho job_id trong `category_by_job_id.json` (mỗi job
    một nhãn), KHÔNG phải nhãn IT để bóc - crawler.py yêu cầu Data Integration dùng
    `raw_payload['Ngành nghề']`.
    """
    s = str(source_category or "").strip()
    if not s:
        return "khác"
    m = _BUCKET_RE.match(s)
    return m.group(1) if m else s


def strip_prefix(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", str(url)).strip("/")


BOX_LABELS = ("Lương", "Kinh nghiệm", "Cấp bậc", "Hình thức", "Ngày cập nhật",
              "Hết hạn nộp", "Ngành nghề")


def box_fields(detail_box) -> dict[str, list[str]]:
    """Tách các dòng `detail-box` theo nhãn đầu dòng -> {label: [giá trị...]}.

    `detail-box` là List[str], mỗi dòng có dạng "<Nhãn> <Giá trị>" và một số nhãn
    lặp 2 lần (bản desktop + mobile - raw_envelope.py:163-168). Chỉ dùng ĐỂ ĐO ở tầng
    EDA, không ghi ngược cấu trúc đã tách vào raw.
    """
    out: dict[str, list[str]] = {lab: [] for lab in BOX_LABELS}
    for line in as_list(detail_box):
        for lab in BOX_LABELS:
            if line.startswith(lab):
                val = line[len(lab):].lstrip(" :").strip()
                # nguồn có dòng lặp cả nhãn lẫn giá trị: "Lương Lương: 15 - 20 Triệu VND"
                if val.startswith(lab + ":"):
                    val = val[len(lab) + 1:].strip()
                if val:
                    out[lab].append(val)
                break
    return out


def split_multi(value: str) -> list[str]:
    """Tách giá trị nhiều lựa chọn ghi kiểu 'A , B' thành [A, B]."""
    text = str(value or "")
    return [p.strip() for p in re.split(r"\s*,\s*", text) if p.strip()]


def pick_section(detail_row, needle: str) -> str:
    """Lấy văn bản của section JD có tên chứa `needle` (không phân biệt hoa/thường).

    `detail-row` là dict {header: text} (raw_envelope.py:170-185) - đây LÀ nội dung
    mô tả / yêu cầu / phúc lợi. `detail-box` chỉ là list[str] hộp metadata nên không
    thể dùng làm độ dài mô tả công việc.
    """
    if not isinstance(detail_row, dict):
        return ""
    low = str(needle).lower()
    for k, v in detail_row.items():
        if low in str(k).lower():
            return flat_text(v)
    return ""


def group_of(payload: dict) -> str:
    """'it' | 'nonit' | 'unclassified' (tin rỗng 'Ngành nghề' KHÔNG gộp vào non-IT)."""
    inds = as_list(payload.get("Ngành nghề"))
    if not inds:
        return "unclassified"
    txt = " ".join(inds).lower()
    return "it" if any(k in txt for k in IT_KEYWORDS) else "nonit"


def source_caption(n: int, scraped_at: list[str]) -> str:
    """Dòng nguồn in dưới mỗi hình, tính từ chính metadata.scraped_at (không hằng số).

    Run bắt đầu 17:09 UTC nên ngày UTC (16/10) và ngày giờ Việt Nam (17/10) lệch nhau
    -> lấy hợp của hai cách biểu diễn, cho ra '16-17/10/2026'.
    """
    ts = []
    for s in scraped_at:
        try:
            ts.append(datetime.fromisoformat(str(s).replace("Z", "+00:00")))
        except ValueError:
            continue
    if not ts:
        return f"Nguồn: {fmt_int(n)} envelope CareerViet"
    days = set()
    for t in ts:
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        days.add(t.astimezone(timezone.utc).date())
        days.add(t.astimezone(timezone(timedelta(hours=7))).date())
    lo, hi = min(days), max(days)
    if lo == hi:
        rng = f"{lo.day}/{lo.month}/{lo.year}"
    elif (lo.year, lo.month) == (hi.year, hi.month):
        rng = f"{lo.day}-{hi.day}/{hi.month}/{hi.year}"
    else:
        rng = f"{lo.day}/{lo.month}/{lo.year} - {hi.day}/{hi.month}/{hi.year}"
    return f"Nguồn: {fmt_int(n)} envelope CareerViet, thu thập {rng}"


def iter_envelopes(raw_dir: Path, dt: str | None = None):
    """Đọc envelope `<job_id>_v<version>.json`, mỗi job_id lấy bản lớn nhất.

    Nhận cả `dt=YYYY-MM-DD` lẫn `YYYY-MM-DD` (cách sau là thư mục đang dùng thực tế
    và cũng là đường dẫn CDC của `push_raw_to_minio.py`).
    """
    best: dict[str, tuple[int, dict]] = {}
    for p in sorted(raw_dir.glob("*/*.json")):
        m = _DT_RE.match(p.parent.name)
        if not m:
            continue
        if dt and m.group(1) != dt:
            continue
        try:
            env = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        meta = env.get("metadata") or {}
        jid = str(meta.get("job_id") or "")
        if not jid:
            continue
        ver = int(meta.get("version") or 0)
        if jid not in best or ver > best[jid][0]:
            best[jid] = (ver, env)
    return [env for _, env in best.values()]


# --------------------------------------------------------------------- hàm vẽ
def barh_chart(labels, values, percents, title, subtitle, source, path,
               highlight: int = 0, xlabel="", figsize=None):
    """Barh sắp giảm dần (lớn nhất trên cùng), số + % bên cột, cột nhấn màu đỏ."""
    k = len(labels)
    fig, ax = new_fig(figsize or (9.2, max(3.2, 0.44 * k + 1.7)))
    order = list(range(k))[::-1]
    xs = [values[i] for i in order]
    cols = [COLORS["hot"] if i == highlight else COLORS["primary"] for i in order]
    ax.barh([labels[i] for i in order], xs, color=cols, height=0.66)
    top = max(xs) or 1
    for pos, i in enumerate(order):
        ax.text(xs[pos] + 0.014 * top, pos, f"{fmt_int(values[i])}  ·  {percents[i]}",
                va="center", ha="left", fontsize=8.6,
                color=COLORS["ink"] if i == highlight else COLORS["muted"],
                fontweight="bold" if i == highlight else "normal")
    ax.set_xlim(0, top * 1.28)
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.margins(y=0.02)
    decorate(fig, ax, title, subtitle, source, grid="x")
    return save(fig, path)


def bar_chart(labels, values, percents, title, subtitle, source, path,
              highlight: int = 0, ylabel=""):
    fig, ax = new_fig(figsize=(9.2, 4.7))
    cols = [COLORS["hot"] if i == highlight else COLORS["primary"] for i in range(len(labels))]
    bars = ax.bar(range(len(labels)), values, color=cols, width=0.62)
    ax.set_xticks(range(len(labels)), labels)
    top = max(values) or 1
    for b, v, p in zip(bars, values, percents):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.015 * top, f"{fmt_int(v)}\n{p}",
                ha="center", va="bottom", fontsize=8.4, color=COLORS["muted"])
    ax.set_ylim(0, top * 1.22)
    if ylabel:
        ax.set_ylabel(ylabel)
    decorate(fig, ax, title, subtitle, source, grid="y")
    return save(fig, path)


def donut_chart(labels, values, colors, title, subtitle, source, path, center_note):
    fig, ax = new_fig(figsize=(7.8, 5.0))
    total = sum(values) or 1
    wedges, _ = ax.pie(values, colors=colors, startangle=90, counterclock=False,
                       radius=1.0, wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2))
    for w, lab, v in zip(wedges, labels, values):
        ang = math.radians((w.theta1 + w.theta2) / 2)
        x, y = math.cos(ang) * 1.16, math.sin(ang) * 1.16
        ax.text(x, y, f"{lab}\n{fmt_int(v)} ({pct(v, total)})",
                ha="left" if x >= 0 else "right", va="center", fontsize=9.6, color=COLORS["ink"])
    ax.text(0, 0.06, center_note, ha="center", va="center", fontsize=12,
            fontweight="bold", color=COLORS["it"])
    ax.text(0, -0.12, f"n = {fmt_int(total)}", ha="center", va="center", fontsize=9,
            color=COLORS["muted"])
    ax.set_xlim(-2.1, 2.1)
    ax.set_ylim(-1.32, 1.32)
    ax.set_aspect("equal")
    decorate(fig, ax, title, subtitle, source, grid="")
    return save(fig, path)


def hist_chart(values, title, subtitle, source, path, bins=28, xlabel="", vline=None,
               vline_label=""):
    fig, ax = new_fig(figsize=(9.2, 4.6))
    ax.hist(values, bins=bins, color=COLORS["primary"], edgecolor="white",
            linewidth=0.6, alpha=0.9)
    if vline is not None:
        ax.axvline(vline, color=COLORS["hot"], linewidth=1.6, linestyle="--",
                   label=f"trung vị {vline_label}")
        ax.legend(fontsize=9, loc="upper right")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Số tin")
    decorate(fig, ax, title, subtitle, source, grid="y")
    return save(fig, path)


def box_chart(groups, title, subtitle, source, path, xlabel="", ylabel="Số tin"):
    """Boxplot so sánh các nhóm, ghi trung vị ngay trên mỗi hộp."""
    fig, ax = new_fig(figsize=(9.2, 4.7))
    data = [g["values"] for g in groups]
    box = ax.boxplot(
        data, patch_artist=True, widths=0.5, showfliers=True,
        medianprops=dict(color=COLORS["hot"], linewidth=2),
        whiskerprops=dict(color="#475569"), capprops=dict(color="#475569"),
        flierprops=dict(marker="o", markersize=3.5, markerfacecolor=COLORS["spine"],
                        markeredgecolor="none"))
    for patch, g in zip(box["boxes"], groups):
        patch.set_facecolor(g["color"])
        patch.set_alpha(0.85)
        patch.set_edgecolor("#475569")
    ax.set_xticks(range(1, len(groups) + 1),
                  [f"{g['label']}\nn = {fmt_int(len(g['values']))}" for g in groups])
    for i, g in enumerate(groups, start=1):
        med = statistics.median(g["values"])
        ax.annotate(fmt_num(med), xy=(i, med), xytext=(i + 0.34, med), fontsize=9.4,
                    color=COLORS["hot"], fontweight="bold",
                    arrowprops=dict(arrowstyle="-", color=COLORS["hot"], linewidth=0.8))
    ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)
    decorate(fig, ax, title, subtitle, source, grid="y")
    return save(fig, path)


def heatmap_chart(row_labels, col_labels, counts, row_totals, title, subtitle, source, path):
    """Ma trận địa điểm × nhóm: ô tô số tin và % theo hàng."""
    import numpy as np

    mat = np.array(counts, dtype=float)
    fig, ax = new_fig(figsize=(9.6, max(3.8, 0.44 * len(row_labels) + 2.0)))
    im = ax.imshow(mat, cmap="Blues", aspect="auto", vmin=0, vmax=mat.max())
    ax.set_xticks(range(len(col_labels)), col_labels, fontsize=9.2)
    ax.set_yticks(range(len(row_labels)), row_labels, fontsize=9.2)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    vmax = mat.max() or 1
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = int(mat[i, j])
            share = pct(v, row_totals[i]) if row_totals[i] else "0%"
            ax.text(j, i, f"{fmt_int(v)}\n{share}", ha="center", va="center", fontsize=8.2,
                    color="white" if v > 0.55 * vmax else COLORS["ink"])
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Số tin", fontsize=9)
    cbar.ax.tick_params(labelsize=8)
    decorate(fig, ax, title, subtitle, source, grid="", title_size=12.2)
    return save(fig, path)


# --------------------------------------------------------------------- main
def read_ledger(ledger_dir: Path, source: str) -> dict:
    """Doc URL Ledger cua nguồn: `catalog_master.json` (trạng thái crawl) + `manifests/`.

    `manifests/manifest_<date>.jsonl` la anh khoanh LUC PHAT HIEN (van ghi PENDING,
    latest_version=0) nen khong duoc dung de do trang thai crawl; trang thái thật
    nằm trong `catalog_master.json` (UrlLedger.mark_done/save_catalog).
    """
    out = {"records": [], "statuses": Counter(), "repost": 0, "with_version": 0,
           "errors": 0, "manifest_urls": 0, "dir": str(ledger_dir)}
    if not ledger_dir.exists():
        return out
    cat = ledger_dir / "catalog_master.json"
    if cat.exists():
        try:
            data = json.loads(cat.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = []
        recs = list(data.values()) if isinstance(data, dict) else list(data)
        recs = [r for r in recs if isinstance(r, dict) and r.get("source") == source]
        out["records"] = recs
        for r in recs:
            st = str(r.get("status") or r.get("crawl_status") or "?")
            rp = bool(r.get("repost_of_url_hash"))
            out["statuses"][(st, rp)] += 1
            if rp:
                out["repost"] += 1
            if int(r.get("latest_version") or 0) >= 1:
                out["with_version"] += 1
            if r.get("error_log"):
                out["errors"] += 1
    mp = ledger_dir / "manifests"
    if mp.exists():
        seen = set()
        for f in sorted(mp.glob("*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("source") == source:
                    seen.add(strip_prefix(rec.get("canonical_url")
                                        or rec.get("job_url_canonical", "")))
        out["manifest_urls"] = len(seen)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", default="data/careerviet/raw")
    ap.add_argument("--ledger", default="data/careerviet/url_ledger")
    ap.add_argument("--source", default="careerviet")
    ap.add_argument("--dt", default=None)
    ap.add_argument("--fig-dir", default="reports/figures/careerviet")
    ap.add_argument("--md-out", default="reports/careerviet_eda_charts.md")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--keep-stale", action="store_true",
                    help="Giữ lại PNG cũ không thuộc bộ sinh lần này (mặc định: xóa trong --fig-dir)")
    args = ap.parse_args(argv)

    use_default_style()
    raw = Path(args.raw)
    fig_dir = Path(args.fig_dir)
    fig_dir.mkdir(parents=True, exist_ok=True)

    envs = iter_envelopes(raw, args.dt)
    n = len(envs)
    if n == 0:
        print(f"[EDA] Không có envelope nào trong {raw} (c1/c37/c61 = 0 URL -> 0 tin).")
        return 0
    src = source_caption(n, [str(e["metadata"].get("scraped_at") or "") for e in envs])
    print(f"[EDA] {src}")

    rows = []
    for e in envs:
        meta, p = e["metadata"], e["raw_payload"]
        schema = p.get("job-posting-schema")
        schema = schema if isinstance(schema, dict) else {}
        grp = group_of(p)
        box = as_list(p.get("detail-box"))
        bx = box_fields(box)
        row = p.get("detail-row")
        desc = schema.get("description")
        rows.append({
            "job_id": meta.get("job_id"),
            "bucket": bucket_of(meta.get("source_category")),
            "group": grp,
            "is_it": grp == "it",
            "locs": {s.strip() for x in as_list(p.get("map"))
                     for s in str(x).split(",") if s.strip()},
            "title": flat_text(p.get("title")),
            "company": flat_text(p.get("job-company-name")),
            "tags": as_list(p.get("job-tags")),
            "ind": as_list(p.get("Ngành nghề")),
            "map": p.get("map"),
            "salary_txt": bx["Lương"],
            "exp": bx["Kinh nghiệm"],
            "level": bx["Cấp bậc"],
            "emp": bx["Hình thức"],
            "updated": bx["Ngày cập nhật"],
            "deadline": bx["Hết hạn nộp"],
            "box_n": len(box),
            "row_n": len(row) if isinstance(row, dict) else 0,
            "row_keys": list(row) if isinstance(row, dict) else [],
            "jd_len": len(pick_section(p.get("detail-row"), "mô tả")),
            "req_len": len(pick_section(p.get("detail-row"), "yêu cầu")),
            "ben_len": len(pick_section(p.get("detail-row"), "phúc lợi")),
            "row_len": len(flat_text(p.get("detail-row"))),
            "desc_jsonld": flat_text(desc),
            "benefits": split_benefits(schema.get("jobBenefits")),
            "has_bs": isinstance(schema.get("baseSalary"), dict) and bool(schema.get("baseSalary")),
            "sal_m": salary_month_m(schema),
            "schema": schema,
            "date_posted": schema.get("datePosted"),
            "content_hash": meta.get("content_hash"),
            "scraped": meta.get("scraped_at"),
        })

    ins: list[dict] = []

    # Doc ledger TRUOC de insight sau do (ngay dang/repost, hinh 16) dung so that.
    led = read_ledger(Path(args.ledger), args.source)
    led_done = sum(v for (st, _), v in led["statuses"].items() if st == "DONE")
    led_repost = led["repost"]
    led_total = sum(led["statuses"].values())
    led_pending = led_total - led_done

    def add(no, title, fname, observe, meaning, limit):
        ins.append({"no": no, "title": title, "file": fname, "observe": observe,
                    "meaning": meaning, "limit": limit})

    def skip(no, title, why):
        """Không đủ dữ liệu -> ghi chú trung thực, KHÔNG vẽ, KHÔNG bịa số."""
        add(no, title, None, why,
            "Mẫu của lần chạy này chưa đủ dày cho chỉ báo nên chưa rút ra nhận xét nào.",
            "Không có số đo thì không có kết luận; chỉ báo sẽ có ý nghĩa khi mẫu đủ lớn.")

    def null_count(field):
        if field == "Ngành nghề":
            return sum(1 for r in rows if not r["ind"])
        if field == "job-tags":
            return sum(1 for r in rows if not r["tags"])
        if field == "detail-box (hộp metadata)":
            return sum(1 for r in rows if r["box_n"] == 0)
        if field == "detail-row (section JD)":
            return sum(1 for r in rows if r["row_n"] == 0)
        if field == "job-posting-schema":
            return sum(1 for r in rows if not r["schema"])
        if field == "description (JSON-LD)":
            return sum(1 for r in rows if not r["desc_jsonld"])
        if field == "jobBenefits (JSON-LD)":
            return sum(1 for r in rows if not r["benefits"])
        if field == "baseSalary (JSON-LD)":
            return sum(1 for r in rows if not r["has_bs"])
        if field == "Lương (dòng detail-box)":
            return sum(1 for r in rows if not r["salary_txt"])
        if field == "Lương quy đổi được (VND/tháng)":
            return sum(1 for r in rows if not r["sal_m"])
        if field == "Kinh nghiệm (dòng detail-box)":
            return sum(1 for r in rows if not r["exp"])
        if field == "Hình thức (dòng detail-box)":
            return sum(1 for r in rows if not r["emp"])
        return sum(1 for r in rows if is_null(r[field]))

    def sec_cover(pat: str, lens_key: str):
        """Tên heading nguyên văn của nguồn khớp `pat` + số tin có nội dung section không rỗng."""
        names = Counter(k for r in rows for k in r["row_keys"] if pat in k.lower())
        if not names:
            return None
        return names.most_common(1)[0][0], sum(1 for r in rows if r[lens_key] > 0)

    zero_box = null_count("detail-box (hộp metadata)")
    zero_row = null_count("detail-row (section JD)")
    null_tag = null_count("tags")
    g = Counter(r["group"] for r in rows)

    # 1 - Nhóm URL cung cấp tin
    cb = Counter(r["bucket"] for r in rows).most_common()
    bl, bv = [k for k, _ in cb], [v for _, v in cb]
    bp = [pct(v, n) for v in bv]
    bar_chart(bl, bv, bp,
              f"Nhóm '{bl[0]}' cung cấp {fmt_int(bv[0])}/{fmt_int(n)} tin ({bp[0]})",
              f"n = {fmt_int(n)} envelope, {len(bl)} bucket sinh ra từ Phase 1", src,
              fig_dir / "01_bucket_supply.png", highlight=0, ylabel="Số tin")
    add(1, "Cơ cấu nguồn theo bucket URL-Discovery", "01_bucket_supply.png",
        (f"{bl[0]} cho {fmt_int(bv[0])} tin ({bp[0]}), {bl[1]} cho {fmt_int(bv[1])} tin ({bp[1]}); "
         f"đứng đầu là {bl[0]} + {bl[1]} đã chiếm {pct(bv[0] + bv[1], n)} số tin.") if len(bl) > 1 else
        (f"{bl[0]} cho {fmt_int(bv[0])} tin ({bp[0]}); mẫu chỉ sinh ra từ 1 bucket nên không so sánh "
         f"được cơ cấu nguồn."),
        "Tỷ trọng này là hệ quả của việc chọn danh mục ở Phase 1 (độ rộng ngành của từng bucket), "
        "không phải độ nóng việc làm của thị trường.",
        "Nhãn bucket lấy từ `metadata.source_category` - mỗi job_id chỉ mang một nhãn nên tổng cột "
        "đúng bằng số tin, nhưng chính crawler yêu cầu Data Integration KHÔNG dùng nó để lọc IT.")

    # 2 - Donut IT / ngoài IT / không phân loại
    donut_chart(
        ["Tin IT", "Ngoài IT", "Không phân loại được"],
        [g["it"], g["nonit"], g["unclassified"]],
        [COLORS["it"], COLORS["nonit"], COLORS["unknown"]],
        f"{pct(g['it'], n)} tin tuyển dụng thuộc nhóm IT ({fmt_int(g['it'])}/{fmt_int(n)})",
        f"n = {fmt_int(n)} envelope; lọc theo 'Ngành nghề' chứa CNTT / Phần mềm", src,
        fig_dir / "02_it_share_donut.png", center_note=f"IT\n{pct(g['it'], n)}")
    add(2, "Tỷ lệ IT / ngoài IT (donut 3 nhóm)", "02_it_share_donut.png",
        f"IT {fmt_int(g['it'])} tin ({pct(g['it'], n)}), ngoài IT {fmt_int(g['nonit'])} tin "
        f"({pct(g['nonit'], n)}), và {fmt_int(g['unclassified'])} tin ({pct(g['unclassified'], n)}) "
        f"rỗng 'Ngành nghề' được tách thành nhóm riêng thay vì gộp vào ngoài IT.",
        f"Sau bước lọc IT còn {fmt_int(g['nonit'] + g['unclassified'])} tin không phải IT - đây là khối "
        f"dữ liệu cần loại ở Phase 2, không phải 'phế liệu' bỏ quên.",
        f"Quy tắc khóa 'cntt/phan mem/phần mềm' có thể bỏ sót tin IT ghi ngành theo kỹ năng (Data, BA, "
        f"QA...), đồng thời {fmt_int(g['unclassified'])} tin tối giản không đủ căn cứ phân loại => "
        f"{pct(g['it'], n)} là cận dưới hợp lý, không phải tỷ lệ thị trường.")

    # 3 - Tỷ lệ IT theo bucket (stacked 100%)
    bs = [(k, v) for k, v in Counter(r["bucket"] for r in rows).most_common() if v >= 20]
    ratios = []
    for k, v in bs:
        it_c = sum(1 for r in rows if r["bucket"] == k and r["is_it"])
        un_c = sum(1 for r in rows if r["bucket"] == k and r["group"] == "unclassified")
        ratios.append((k, v, it_c / v * 100, un_c / v * 100))
    ratios.sort(key=lambda x: x[2])
    if not ratios:
        skip(3, "Tỷ lệ IT theo bucket",
             f"Không bucket nào đạt ngưỡng 20 tin (nhiều nhất "
             f"{fmt_int(max((v for _, v in Counter(r['bucket'] for r in rows).items()), default=0))} tin) "
             f"nên không so sánh được tỷ lệ IT giữa các bucket.")
    else:
        fig, ax = new_fig(figsize=(9.2, max(3.6, 0.56 * len(ratios) + 1.8)))
        ys = list(range(len(ratios)))
        it_v = [x[2] for x in ratios]
        un_v = [x[3] for x in ratios]
        non_v = [100 - a - b for a, b in zip(it_v, un_v)]
        ax.barh(ys, it_v, color=COLORS["it"], height=0.62, label="IT")
        ax.barh(ys, non_v, left=it_v, color=COLORS["nonit"], height=0.62, label="Ngoài IT")
        ax.barh(ys, un_v, left=[a + b for a, b in zip(it_v, non_v)], color=COLORS["unknown"],
                height=0.62, label="Không phân loại")
        for i, (k, v, a, b) in enumerate(ratios):
            ax.text(a / 2 if a > 14 else 1.5, i, f"{fmt_num(round(a, 1))}%", va="center",
                    ha="center" if a > 14 else "left", fontsize=8.8,
                    color="white" if a > 14 else COLORS["it"], fontweight="bold")
            ax.text(101.5, i, f"n = {fmt_int(v)}", va="center", fontsize=8.2, color=COLORS["muted"])
        ax.set_yticks(ys, [f"{k} ({fmt_int(v)})" for k, v, _, _ in ratios])
        ax.set_xlim(0, 116)
        ax.set_xlabel("% số tin trong bucket")
        # Legend dat duoi truc: bar 100% nam ngang kin be ngang nen de trong axes se de len cot.
        ax.legend(ncol=3, fontsize=8.8, loc="upper center", bbox_to_anchor=(0.5, -0.16),
                  frameon=False)
        decorate(fig, ax,
                 f"Tỷ lệ IT cao nhất ở {ratios[-1][0]} ({fmt_num(round(ratios[-1][2], 1))}%), "
                 f"thấp nhất ở {ratios[0][0]} ({fmt_num(round(ratios[0][2], 1))}%)",
                 f"n = {fmt_int(sum(x[1] for x in ratios))} envelope (chỉ bucket có >= 20 tin)", src,
                 grid="")
        save(fig, fig_dir / "03_it_ratio_bucket.png")
        add(3, "Tỷ lệ IT theo bucket", "03_it_ratio_bucket.png",
            f"{ratios[0][0]}: {fmt_num(round(ratios[0][2], 1))}% IT (thấp nhất); {ratios[-1][0]}: "
            f"{fmt_num(round(ratios[-1][2], 1))}% IT (cao nhất); khoảng cách giữa {len(ratios)} bucket lên "
            f"tới {fmt_num(round(ratios[-1][2] - ratios[0][2], 1))} điểm phần trăm.",
            f"Bucket {ratios[-1][0]} là danh mục 'ruột' của mảng IT trên CareerViet, còn {ratios[0][0]} "
            f"chủ yếu đăng ngành ngoài IT.",
            "Mỗi bucket là một quyết định chốt danh mục của Phase 1, không phải phép đo thị trường; so sánh "
            "tuyệt đối giữa các bucket dễ dẫn tới kết luận sai về nhu cầu tuyển dụng.")

    # 4 - Tỷ lệ trống từng trường
    fields = ["title", "company", "Ngành nghề", "map", "job-tags",
              "detail-box (hộp metadata)", "detail-row (section JD)", "job-posting-schema",
              "description (JSON-LD)", "jobBenefits (JSON-LD)", "baseSalary (JSON-LD)",
              "Lương quy đổi được (VND/tháng)",
              "Lương (dòng detail-box)", "Kinh nghiệm (dòng detail-box)",
              "Hình thức (dòng detail-box)"]
    nr = sorted(((f, null_count(f)) for f in fields), key=lambda x: -x[1])
    barh_chart([k for k, _ in nr], [v for _, v in nr], [pct(v, n) for _, v in nr],
               f"Trống nhiều nhất: {nr[0][0]} - {pct(nr[0][1], n)} tin ({fmt_int(nr[0][1])}/{fmt_int(n)})",
               f"n = {fmt_int(n)} envelope; đơn vị: số tin có trường rỗng", src,
               fig_dir / "04_null_rate.png", highlight=0, xlabel="Số tin rỗng")
    add(4, "Độ phủ / tỷ lệ trống từng trường", "04_null_rate.png",
        f"Đứng đầu là {nr[0][0]} với {fmt_int(nr[0][1])} tin rỗng ({pct(nr[0][1], n)}), kế đến "
        f"{nr[1][0]} {fmt_int(nr[1][1])} tin ({pct(nr[1][1], n)}); trong khi đó `detail-box` chỉ rỗng ở "
        f"{fmt_int(zero_box)} tin và `detail-row` rỗng ở {fmt_int(zero_row)} tin.",
        "Các trường cần cho SD3/SD4 (tag, lương, map) có mức trống khác nhau nên không thể áp một ngưỡng "
        "hoàn thiện chung cho mọi mẫu.",
        "Rỗng ở đây nghĩa là nguồn không cho giá trị trong SSR/JSON-LD; chưa đủ căn cứ kết luận lỗi "
        "trích xuất. Mức trống theo nhóm IT / ngoài IT được tách ở hình 10.")

    # 5 - Phân bố lương toàn mẫu
    sal = [r["sal_m"] for r in rows if r["sal_m"]]
    n_vague = sum(1 for r in rows if r["salary_txt"]
                  and any(k in " ".join(r["salary_txt"]).lower() for k in ("cạnh tranh", "thỏa thuận")))
    disc_it = pct(sum(1 for r in rows if r["sal_m"] and r["group"] == "it"), g["it"])
    disc_non = pct(sum(1 for r in rows if r["sal_m"] and r["group"] == "nonit"), g["nonit"])
    if not sal:
        skip(5, "Phân bố lương (toàn mẫu)",
             f"0/{fmt_int(n)} tin quy đổi được lương VND/tháng từ `baseSalary` nên không có phân bố.")
    else:
        q = qstats(sal)
        hist_chart(sal,
                   f"Chỉ {pct(q['n'], n)} tin đọc được lương VND/tháng, trung vị {fmt_num(q['med'])} triệu",
                   f"n = {fmt_int(q['n'])}/{fmt_int(n)} tin có baseSalary đọc được (VND, MONTH)", src,
                   fig_dir / "05_salary_hist.png", bins=28,
                   xlabel="Trung bình dải lương (triệu VND/tháng)", vline=q["med"],
                   vline_label=f"{fmt_num(q['med'])}")
        add(5, "Phân bố lương (toàn mẫu)", "05_salary_hist.png",
            f"{fmt_int(q['n'])}/{fmt_int(n)} tin ({pct(q['n'], n)}) đọc được lương; trung vị "
            f"{fmt_num(q['med'])}, tứ phân vị {iqr_txt(q)}, nhỏ nhất "
            f"{fmt_num(q['min'])}, lớn nhất {fmt_num(q['max'])} (triệu VND/tháng); {pct(n - q['n'], n)} tin "
            f"không đủ dữ liệu lương, trong đó {fmt_int(n_vague)} tin chỉ ghi 'Lương cạnh tranh'/'Thỏa "
            f"thuận' ở dòng `detail-box`.",
            f"Mặt bằng lương công khai trong mẫu dồn ở dải {iqr_txt(q)} triệu/tháng; tỷ lệ công khai "
            f"lương khác nhau giữa hai nhóm (IT {disc_it} tin có lương, ngoài "
            f"IT {disc_non}).",
            f"{pct(n - q['n'], n)} tin không đủ dữ liệu lương là thiên lệch chọn lọc lớn: cùng một công "
            f"việc, nhà tuyển dụng công khai lương có thể khác nhóm 'Thỏa thuận', nên không suy ra được "
            f"mặt bằng lương chung của thị trường.")

    # 6 - Boxplot lương IT vs ngoài IT (so sánh)
    sal_it = [r["sal_m"] for r in rows if r["sal_m"] and r["group"] == "it"]
    sal_non = [r["sal_m"] for r in rows if r["sal_m"] and r["group"] == "nonit"]
    sal_unk = [r["sal_m"] for r in rows if r["sal_m"] and r["group"] == "unclassified"]
    sal_groups = [
        gp for gp in ({"label": "IT", "values": sal_it, "color": COLORS["it"]},
                      {"label": "Ngoài IT", "values": sal_non, "color": COLORS["nonit"]})
        if gp["values"]
    ]
    unk_note = (f" ({fmt_int(len(sal_unk))} tin không phân loại có lương, loại khỏi so sánh)"
                if sal_unk else "")
    if not sal_groups:
        skip(6, "Lương: IT vs ngoài IT (boxplot)",
             f"Không tin nào có lương quy đổi được (0/{fmt_int(n)}) nên không có hộp nào để vẽ.")
    elif len(sal_groups) == 1:
        gp = sal_groups[0]
        one = qstats(gp["values"])
        box_chart([gp],
                  f"Chỉ nhóm {gp['label']} có lương đọc được trong mẫu này: trung vị "
                  f"{fmt_num(one['med'])} triệu (n = {fmt_int(one['n'])})",
                  f"n = {fmt_int(one['n'])} tin {gp['label'].lower()} công khai lương trên tổng "
                  f"{fmt_int(n)} tin" + unk_note,
                  src, fig_dir / "06_salary_box_it_vs_non.png",
                  xlabel="Nhóm (lọc từ 'Ngành nghề')", ylabel="Triệu VND/tháng")
        add(6, "Lương: IT vs ngoài IT (boxplot)", "06_salary_box_it_vs_non.png",
            f"Chỉ {gp['label']} có lương quy đổi được: n = {fmt_int(one['n'])}, trung vị "
            f"{fmt_num(one['med'])}, IQR {iqr_txt(one)}, tối đa {fmt_num(one['max'])}; nhóm còn lại có 0 tin "
            f"đọc được lương.",
            f"Một nhóm trống nên chưa so sánh mức lương IT / ngoài IT được; con số trên chỉ mô tả nhóm "
            f"{gp['label']} trong phần tin công khai lương.",
            f"Chỉ {pct(one['n'], n)} mẫu đọc được lương và chúng nằm hết một nhóm => chưa kiểm định thống "
            f"kê, không suy ra mặt bằng lương của nhóm còn lại.")
    else:
        qi, qn = qstats(sal_it), qstats(sal_non)
        diff = (qi["med"] - qn["med"]) / qn["med"] * 100
        box_chart([{"label": "IT", "values": sal_it, "color": COLORS["it"]},
                   {"label": "Ngoài IT", "values": sal_non, "color": COLORS["nonit"]}],
                  f"Lương trung vị nhóm IT {fmt_num(qi['med'])} triệu cao hơn ngoài IT "
                  f"{fmt_num(qn['med'])} triệu (+{fmt_num(round(diff, 1))}%)",
                  f"n = {fmt_int(len(sal_it))} tin IT và {fmt_int(len(sal_non))} tin ngoài IT công khai "
                  f"lương" + unk_note,
                  src, fig_dir / "06_salary_box_it_vs_non.png",
                  xlabel="Nhóm (lọc từ 'Ngành nghề')", ylabel="Triệu VND/tháng")
        add(6, "Lương: IT vs ngoài IT (boxplot)", "06_salary_box_it_vs_non.png",
            f"IT n = {fmt_int(qi['n'])}: trung vị {fmt_num(qi['med'])}, IQR {iqr_txt(qi)}, tối đa "
            f"{fmt_num(qi['max'])}. Ngoài IT n = {fmt_int(qn['n'])}: trung vị {fmt_num(qn['med'])}, IQR "
            f"{iqr_txt(qn)}, tối đa {fmt_num(qn['max'])}. Chênh lệch trung vị +{fmt_num(round(diff, 1))}%.",
            "Trong phần tin công khai lương của CareerViet, nhóm IT không chỉ có mức trung vị cao hơn mà "
            "còn có biên độ (IQR) rộng hơn - nhất quán với tính chuyên môn hóa và phân tầng bậc của việc IT.",
            f"So sánh chỉ chạy trên {fmt_int(qi['n'] + qn['n'])} tin có lương ({pct(qi['n'] + qn['n'], n)} "
            f"mẫu); tỷ lệ công khai lương của hai nhóm có thể khác nhau và chưa kiểm định thống kê "
            f"(Mann-Whitney/t) => coi là giả thuyết hướng, không phải kết luận toàn thị trường.")

    # 7 - Địa điểm (barh)
    lc = Counter()
    for r in rows:
        for l in r["locs"]:
            lc[l] += 1
    top_loc = lc.most_common(args.top)
    null_map = null_count("map")
    if len(top_loc) < 2:
        skip(7, "Địa điểm làm việc",
             f"`map` chỉ cho {fmt_int(len(top_loc))} địa điểm khác nhau trên {fmt_int(n)} tin "
             f"(trống {fmt_int(null_map)} tin) nên không đo được tập trung địa bàn.")
        skip(8, "Địa điểm × nhóm IT (heatmap)",
             "Cùng lý do với hình 7: không đủ địa điểm để lập ma trận địa điểm × nhóm.")
    else:
        tot_luot = sum(lc.values())
        sum_top2 = top_loc[0][1] + top_loc[1][1]
        tail = (f", các tỉnh còn lại đều dưới {fmt_int(top_loc[2][1])} lượt" if len(top_loc) > 2 else "")
        barh_chart([k for k, _ in top_loc], [v for _, v in top_loc], [pct(v, n) for _, v in top_loc],
                   f"{top_loc[0][0]} và {top_loc[1][0]} chiếm {pct(sum_top2, tot_luot)} lượt nhắc "
                   f"địa điểm ({fmt_int(sum_top2)}/{fmt_int(tot_luot)})",
                   f"n = {fmt_int(n)} envelope; đơn vị: lượt xuất hiện trong `map` ({fmt_int(tot_luot)} lượt, "
                   f"{len(lc)} địa phương)", src, fig_dir / "07_locations.png", highlight=0,
                   xlabel="Số lượt xuất hiện")
        add(7, "Địa điểm làm việc", "07_locations.png",
            f"{top_loc[0][0]} {fmt_int(top_loc[0][1])} lượt ({pct(top_loc[0][1], n)}), {top_loc[1][0]} "
            f"{fmt_int(top_loc[1][1])} lượt ({pct(top_loc[1][1], n)}); tổng {fmt_int(tot_luot)} lượt rải "
            f"trên {len(lc)} địa phương{tail}.",
            "Thị trường trong mẫu dồn ở hai địa bàn đầu bảng "
            f"({pct(sum_top2, tot_luot)} lượt); {len(lc) - 2} địa phương còn lại chỉ chiếm "
            f"{pct(tot_luot - sum_top2, tot_luot)} lượt nên quá mỏng để phân tích vùng.",
            f"Một tin có thể ghi nhiều tỉnh (tách theo dấu phẩy) nên tổng lượt lớn hơn số tin; `map` rỗng ở "
            f"{fmt_int(null_map)} tin ({pct(null_map, n)}).")

        # 8 - Heatmap địa điểm × nhóm
        loc_order = [k for k, _ in lc.most_common(10)]
        xtab = defaultdict(Counter)
        for r in rows:
            for l in r["locs"]:
                xtab[l][r["group"]] += 1
        # Loai cot rong: 24 tin khong phan loai cung chinh la 24 tin rong `map`
        cols = [k for k in ("it", "nonit", "unclassified")
                if any(xtab[l][k] for l in loc_order)]
        col_names = {"it": "IT", "nonit": "Ngoài IT", "unclassified": "Không phân loại"}
        mat = [[xtab[l][k] for k in cols] for l in loc_order]
        rtot = [sum(xtab[l][k] for k in cols) for l in loc_order]

        def it_share(L):
            d = xtab[L]["it"] + xtab[L]["nonit"]
            return xtab[L]["it"] / d * 100 if d else 0.0

        hot = max(loc_order, key=it_share)
        cold = min(loc_order, key=it_share)
        by_n = sorted(loc_order, key=lambda L: -sum(xtab[L][k] for k in cols))
        hi_n, lo_n = by_n[0], by_n[1]
        cold_n = fmt_int(sum(xtab[cold][k] for k in cols))
        gap = abs(it_share(hi_n) - it_share(lo_n))
        heatmap_chart(loc_order, [col_names[c] for c in cols], mat, rtot,
                      f"IT chiếm {fmt_num(round(it_share(hi_n), 1))}% ở {hi_n} so với "
                      f"{fmt_num(round(it_share(lo_n), 1))}% ở {lo_n} - hai địa bàn dày nhất mẫu",
                      f"n = {fmt_int(n)} envelope; % trong mỗi ô tính theo hàng (chỉ "
                      f"{fmt_int(n - null_map)} tin có `map`; {fmt_int(g['unclassified'])} tin không phân "
                      f"loại cũng trống `map` nên không thành cột riêng)", src,
                      fig_dir / "08_location_group_heatmap.png")
        add(8, "Địa điểm × nhóm IT (heatmap)", "08_location_group_heatmap.png",
            f"{hi_n}: {fmt_int(xtab[hi_n]['it'])} IT / {fmt_int(xtab[hi_n]['nonit'])} ngoài IT "
            f"({fmt_num(round(it_share(hi_n), 1))}% IT); {lo_n}: {fmt_int(xtab[lo_n]['it'])} IT / "
            f"{fmt_int(xtab[lo_n]['nonit'])} ngoài IT ({fmt_num(round(it_share(lo_n), 1))}% IT). Hai cực "
            f"của bảng là {hot} ({fmt_num(round(it_share(hot), 1))}% IT) và {cold} "
            f"({fmt_num(round(it_share(cold), 1))}% IT, chỉ {cold_n} tin).",
            f"Cơ cấu IT / ngoài IT chênh {fmt_num(round(gap, 1))} điểm phần trăm giữa hai địa bàn dày nhất "
            f"({hi_n} so với {lo_n}) - căn cứ để chốt địa bàn khi phân tích cụm kỹ năng theo vùng.",
            f"Hàng chỉ bao phủ tin có `map`; {fmt_int(null_map)} tin rỗng `map` trùng chính xác với "
            f"{fmt_int(g['unclassified'])} tin không phân loại được nên không bị trừ hai lần; các hàng mỏng "
            f"(như {cold} chỉ {cold_n} tin) có tỷ lệ rất dễ đổi, và không suy được cung - cầu nhân lực của "
            f"từng tỉnh từ một ảnh chụp.")

    # 9 - Tag toàn mẫu (tag_it/tag_non tinh luon de hinh 9 va 10 dung chung)
    tag_all = Counter()
    tag_it, tag_non = Counter(), Counter()
    for r in rows:
        for t in set(r["tags"]):
            tag_all[t] += 1
            (tag_it if r["group"] == "it" else tag_non)[t] += 1
    t_all = tag_all.most_common(args.top)
    if not t_all:
        skip(9, "Tag kỹ năng toàn mẫu",
             f"Không tin nào trong {fmt_int(n)} tin có `job-tags` (trống {fmt_int(null_tag)} tin) nên "
             f"không đo được tần suất tag.")
    else:
        top_non_share = pct(tag_non[t_all[0][0]], t_all[0][1])
        mix = sum(1 for k, _ in t_all if tag_non[k] > tag_it[k])
        barh_chart([k for k, _ in t_all], [v for _, v in t_all], [pct(v, n) for _, v in t_all],
                   f"Tag đứng đầu toàn mẫu là '{t_all[0][0]}' ({fmt_int(t_all[0][1])} tin), "
                   f"{top_non_share} nằm ngoài nhóm IT",
                   f"n = {fmt_int(n)} envelope; {fmt_int(len(tag_all))} tag khác nhau; "
                   f"% tính trên {fmt_int(n)} tin",
                   src, fig_dir / "09_tags_all_top.png", highlight=0, xlabel="Số tin chứa tag")
        add(9, "Tag kỹ năng toàn mẫu", "09_tags_all_top.png",
            f"{fmt_int(len(tag_all))} tag khác nhau; cao nhất '{t_all[0][0]}' {fmt_int(t_all[0][1])} tin "
            f"({pct(t_all[0][1], n)}), trong đó {fmt_int(tag_non[t_all[0][0]])} tin ngoài nhóm IT; "
            f"top {args.top} trải trên {pct(sum(v for _, v in t_all), n)} số tin; "
            f"{fmt_int(null_tag)} tin ({pct(null_tag, n)}) không có tag nào.",
            f"Bảng tag toàn mẫu KHÔNG phải 'bộ kỹ năng IT': {pct(g['nonit'] + g['unclassified'], n)} tin "
            f"thuộc ngành khác, nên {fmt_int(mix)}/{fmt_int(len(t_all))} tag đứng đầu xuất hiện ở tin "
            f"ngoài IT nhiều hơn ở tin IT.",
            "Tag là chuỗi thô của nguồn, chưa chuẩn hóa (khác biệt hoa/thường, synonym), nên tần suất một kỹ "
            "năng bị phân tán; đây là lý do Phase 2 phải tách `Technical skills` và chuẩn hóa từ điển.")

    # 10 - Tag chỉ trong tin IT
    t_it = tag_it.most_common(args.top)
    no_tag_it = sum(1 for r in rows if r["group"] == "it" and not r["tags"])
    no_tag_non = sum(1 for r in rows if r["group"] == "nonit" and not r["tags"])
    if not t_it:
        skip(10, f"Tag trong {fmt_int(g['it'])} tin IT",
             f"{fmt_int(g['it'])} tin IT trong mẫu không tag nào nên không lập được bảng tag theo "
             f"chuyên môn IT.")
    else:
        cov_word = ("thấp hơn" if g["it"] and g["nonit"]
                    and no_tag_it / g["it"] > no_tag_non / g["nonit"] else "cao hơn")
        cov_concl = ("lọc IT bằng `job-tags` sẽ mất nhiều tin hơn lọc bằng 'Ngành nghề'"
                     if cov_word == "thấp hơn"
                     else "lọc IT bằng `job-tags` mất ít tin hơn lọc bằng 'Ngành nghề'")
        barh_chart([k for k, _ in t_it], [v for _, v in t_it], [pct(v, g["it"]) for _, v in t_it],
                   f"Trong tin IT, tag phổ biến nhất chỉ xuất hiện ở '{t_it[0][0]}' "
                   f"({fmt_int(t_it[0][1])} tin)",
                   f"n = {fmt_int(g['it'])} tin IT; {fmt_int(len(tag_it))} tag khác nhau; "
                   f"% tính trên số tin IT",
                   src, fig_dir / "10_tags_it_only_top.png", highlight=0,
                   xlabel="Số tin IT chứa tag")
        add(10, f"Tag trong {fmt_int(g['it'])} tin IT", "10_tags_it_only_top.png",
            f"{fmt_int(len(tag_it))} tag xuất hiện trong tin IT, cao nhất '{t_it[0][0]}' "
            f"{fmt_int(t_it[0][1])} tin ({pct(t_it[0][1], g['it'])}); ba tag đứng đầu: "
            f"{', '.join(f'{k} {fmt_int(v)}' for k, v in t_it[:3])}. Tin IT không có tag: "
            f"{fmt_int(no_tag_it)} ({pct(no_tag_it, g['it'])}) so với ngoài IT {fmt_int(no_tag_non)} "
            f"({pct(no_tag_non, g['nonit'])}).",
            f"Độ phủ tag của nhóm IT {cov_word} nhóm ngoài IT ({pct(no_tag_it, g['it'])} so với "
            f"{pct(no_tag_non, g['nonit'])} tin trống), nên {cov_concl}.",
            f"Tag đầu bảng chỉ phủ {fmt_int(t_it[0][1])}/{fmt_int(g['it'])} tin IT "
            f"({pct(t_it[0][1], g['it'])}) nên đuôi rất ngắn; không đủ chứng cứ để nói IT 'thiếu kỹ năng' "
            f"hay so sánh kỹ năng giữa ngành.")

    # 11 - Công ty
    cc = Counter(r["company"] for r in rows if r["company"])
    c_top = cc.most_common(args.top)
    null_comp = null_count("company")
    if not c_top:
        skip(11, "Nhà tuyển dụng",
             f"Toàn bộ {fmt_int(n)} tin đều trống `job-company-name` nên không đếm được nhà tuyển dụng.")
    else:
        barh_chart([k for k, _ in c_top], [v for _, v in c_top], [pct(v, n) for _, v in c_top],
                   f"{c_top[0][0]} đăng nhiều nhất: {fmt_int(c_top[0][1])} tin ({pct(c_top[0][1], n)})",
                   f"n = {fmt_int(n)} envelope; {fmt_int(len(cc))} tên công ty khác nhau "
                   f"(thô, chưa chuẩn hóa)",
                   src, fig_dir / "11_companies_top.png", highlight=0, xlabel="Số tin đăng")
        add(11, "Nhà tuyển dụng", "11_companies_top.png",
            f"{fmt_int(len(cc))} tên khác nhau phủ {fmt_int(n - null_comp)} tin có tên; cao nhất "
            f"{c_top[0][0]} với {fmt_int(c_top[0][1])} tin ({pct(c_top[0][1], n)}); "
            f"{pct(sum(v for _, v in c_top), n)} số tin nằm trong top {args.top}.",
            f"Nhà đăng nhiều nhất chỉ chiếm {pct(c_top[0][1], n)} số tin, nên mẫu này mô tả thị trường "
            f"'việc đăng rải' hơn là hệ sinh thái quây quanh vài doanh nghiệp lớn.",
            f"Tên công ty chưa chuẩn hóa (công ty mẹ/con, sai chính tả) => `distinct company` chỉ là cận "
            f"trên; {fmt_int(null_comp)} tin ({pct(null_comp, n)}) không có tên.")

    # 12 - Top 15 heading phúc lợi (jobBenefits, đo được thật)
    ben_c = Counter()
    for r in rows:
        for b in set(r["benefits"]):
            ben_c[b] += 1
    b_top = ben_c.most_common(15)
    n_ben = sum(1 for r in rows if r["benefits"])
    null_ben = null_count("jobBenefits (JSON-LD)")
    if not b_top:
        skip(12, "Top 15 heading phúc lợi",
             f"`jobBenefits` không tách được loại phúc lợi nào trên {fmt_int(n)} tin "
             f"(trống {fmt_int(null_ben)} tin) nên không đo được.")
    else:
        lead = ", ".join(f"{k} {fmt_int(v)} tin ({pct(v, n_ben)})" for k, v in b_top[:2])
        rare = [x for x in b_top[-2:] if x[0] != b_top[0][0]]
        rare_txt = (", hiếm nhất " + ", ".join(f"'{k}' {fmt_int(v)} tin" for k, v in rare)) if rare else ""
        barh_chart([k for k, _ in b_top], [v for _, v in b_top], [pct(v, n_ben) for _, v in b_top],
                   f"Phúc lợi phổ biến nhất '{b_top[0][0]}' xuất hiện ở {pct(b_top[0][1], n_ben)} tin có "
                   f"liệt kê",
                   f"n = {fmt_int(n_ben)}/{fmt_int(n)} tin có `jobBenefits` ({pct(n_ben, n)}); "
                   f"{fmt_int(len(ben_c))} loại phúc lợi trong bộ từ vựng cố định của nguồn", src,
                   fig_dir / "12_benefits_top.png", highlight=0, xlabel="Số tin nêu phúc lợi")
        add(12, "Top 15 heading phúc lợi", "12_benefits_top.png",
            f"`jobBenefits` (JSON-LD, chuỗi phân tách dấu phẩy) tách được {fmt_int(len(ben_c))} loại trên "
            f"{fmt_int(n_ben)} tin ({pct(n_ben, n)}); dẫn đầu {lead}{rare_txt}.",
            f"Các phúc lợi đứng đầu ({', '.join(k for k, _ in b_top[:4])}) là chuẩn chung của mọi ngành, "
            f"nên chúng không phải điểm khác biệt giữa việc IT và việc ngoài IT trong mẫu này.",
            "Số liệu chỉ ghi nhận 'có/không nêu tên phúc lợi', không có giá trị tiền tệ hay mức độ; so sánh "
            "phúc lợi theo nhóm IT cần tách cấu trúc ở Phase 2.")

    # 13 - Ngày đăng
    dp = Counter()
    for r in rows:
        v = r["date_posted"]
        if isinstance(v, str) and v[:10]:
            dp[v[:10]] += 1
    xs = sorted(dp)
    if not dp:
        skip(13, "Ngày đăng tin",
             f"Không tin nào trong {fmt_int(n)} tin có `datePosted` hợp lệ nên không dựng được chuỗi "
             f"thời gian.")
    else:
        yv = [dp[k] for k in xs]
        peak = max(dp, key=lambda k: dp[k])
        span = (datetime.strptime(xs[-1], "%Y-%m-%d")
                - datetime.strptime(xs[0], "%Y-%m-%d")).days + 1
        fig, ax = new_fig(figsize=(9.2, 4.5))
        ax.plot(xs, yv, color=COLORS["primary"], linewidth=2, marker="o", markersize=4.5,
                markerfacecolor=COLORS["hot"])
        ax.fill_between(range(len(xs)), yv, color=COLORS["primary"], alpha=0.12)
        step = max(1, len(xs) // 12)
        ax.set_xticks(range(0, len(xs), step), [xs[i] for i in range(0, len(xs), step)],
                      rotation=30, ha="right", fontsize=8)
        ax.set_ylabel("Số tin")
        ax.annotate(f"{peak}: {fmt_int(dp[peak])} tin", xy=(xs.index(peak), dp[peak]),
                    xytext=(4, -14), textcoords="offset points", fontsize=8.6, color=COLORS["muted"])
        decorate(fig, ax,
                 f"Ngày đăng dồn về {peak} ({fmt_int(dp[peak])} tin) - mẫu là ảnh chụp một thời điểm",
                 f"n = {fmt_int(sum(yv))} tin có `datePosted`, từ {xs[0]} đến {xs[-1]}", src, grid="y")
        save(fig, fig_dir / "13_date_posted.png")
        add(13, "Ngày đăng tin", "13_date_posted.png",
            f"{fmt_int(sum(yv))}/{fmt_int(n)} tin có `datePosted`, trải từ {xs[0]} đến {xs[-1]} "
            f"({fmt_int(span)} ngày); cao nhất {peak} với {fmt_int(dp[peak])} tin ({pct(dp[peak], n)}).",
            f"Phân bố ngày đăng phản ánh nhịp đăng tin của nguồn trong {fmt_int(span)} ngày, đủ để mô tả "
            f"khoảng thời gian thu thập chứ không đo được lưu lượng việc IT.",
            f"Mỗi lần crawl là một ảnh khoanh khác nhau; {fmt_int(led_repost)} tin repost mang ngày đăng "
            f"cũ nên phân bố này bị già hóa nhân tạo.")

    # 14 - Hình thức làm việc (tách từ dòng 'Hình thức' trong detail-box, lặp x2 -> dedupe)
    et = Counter()
    for r in rows:
        for v in set(r["emp"]):
            for part in split_multi(v):
                et[part] += 1
    e_top = et.most_common(args.top)
    n_emp = sum(1 for r in rows if r["emp"])
    null_emp = null_count("Hình thức (dòng detail-box)")
    if not e_top:
        skip(14, "Hình thức làm việc",
             f"Dòng 'Hình thức' trong `detail-box` trống ở {fmt_int(null_emp)}/{fmt_int(n)} tin nên không "
             f"đo được hình thức làm việc.")
    else:
        tail = [x for x in e_top[-2:] if x[0] != e_top[0][0]]
        tail_txt = (", hiếm nhất " + ", ".join(f"'{k}' {fmt_int(v)} tin" for k, v in tail)) if tail else ""
        flex = sum(v for k, v in et.items()
                   if any(w in k.lower() for w in ("remote", "hybrid", "linh hoạt", "tại nhà")))
        barh_chart([k for k, _ in e_top], [v for _, v in e_top], [pct(v, n_emp) for _, v in e_top],
                   f"'{e_top[0][0]}' chiếm {pct(e_top[0][1], n_emp)} tin có ghi hình thức - một loại hình "
                   f"áp đảo",
                   f"n = {fmt_int(n_emp)}/{fmt_int(n)} tin có dòng 'Hình thức'; {fmt_int(len(et))} loại hình "
                   f"(giá trị nguồn, có tin ghi nhiều loại)", src,
                   fig_dir / "14_employment_type.png", highlight=0, xlabel="Số tin")
        add(14, "Hình thức làm việc", "14_employment_type.png",
            f"{e_top[0][0]} {fmt_int(e_top[0][1])} tin ({pct(e_top[0][1], n_emp)}); tổng {fmt_int(len(et))} "
            f"loại hình{tail_txt}; trường này trống ở {fmt_int(null_emp)} tin ({pct(null_emp, n)}).",
            f"Trường phân loại chỉ có {fmt_int(len(et))} mức và {fmt_int(flex)} lượt ghi hình thức linh hoạt "
            f"(remote/hybrid/tại nhà), nên muốn đo tỷ lệ làm từ xa phải bóc từ `detail-row` ở Phase 2.",
            "Giá trị là chuỗi thô của nguồn (một tin ghi nhiều loại, tách dấu phẩy nên tổng có thể vượt số "
            "tin); không kết luận được tỷ lệ remote của thị trường từ trường phân loại này.")

    # 15 - Độ dài JD: IT vs ngoài IT (van ve duoc khi chi con mot nhom co JD)
    jd_all = [r["jd_len"] for r in rows if r["jd_len"] > 0]
    jd_it = [r["jd_len"] for r in rows if r["jd_len"] > 0 and r["group"] == "it"]
    jd_non = [r["jd_len"] for r in rows if r["jd_len"] > 0 and r["group"] == "nonit"]
    jd_groups = [gp for gp in ({"label": "IT", "values": jd_it, "color": COLORS["it"]},
                               {"label": "Ngoài IT", "values": jd_non, "color": COLORS["nonit"]})
                 if gp["values"]]
    cov = [c for c in (sec_cover("yêu cầu", "req_len"), sec_cover("phúc lợi", "ben_len")) if c]
    cov_txt = ("; các section khác: " + ", ".join(f"'{k}': {fmt_int(v)} tin" for k, v in cov)) if cov else ""
    short = sum(1 for x in jd_all if x < 1000)
    n_desc = sum(1 for r in rows if r["desc_jsonld"])
    jsonld_med = statistics.median([len(r["desc_jsonld"]) for r in rows if r["desc_jsonld"]] or [0])
    if not jd_all:
        skip(15, "Độ dài nội dung mô tả công việc",
             f"Không tìm thấy section 'Mô tả Công việc' trong `detail-row` của {fmt_int(n)} tin "
             f"({fmt_int(zero_row)} tin rỗng `detail-row`) nên không đo được độ dài JD.")
    elif not jd_groups:
        skip(15, "Độ dài nội dung mô tả công việc",
             f"{fmt_int(len(jd_all))} tin có JD nhưng toàn bộ thuộc nhóm không phân loại được nên chưa "
             f"đo được độ dài theo nhóm IT / ngoài IT.")
    else:
        if jd_it and jd_non:
            m_it, m_non = statistics.median(jd_it), statistics.median(jd_non)
            diff = (m_it - m_non) / m_non * 100
            chart_title = (f"JD nhóm IT dài {fmt_int(m_it)} ký tự, ngoài IT {fmt_int(m_non)} - chênh chỉ "
                           f"{fmt_num(round(diff, 1))}%")
            cmp_txt = (f"; trung vị IT {fmt_int(m_it)} ký tự so với ngoài IT {fmt_int(m_non)} "
                       f"(+{fmt_num(round(diff, 1))}%)")
            meaning = ("Độ dài JD hầu như không phân biệt việc IT với việc ngoài IT; muốn tách hai nhóm "
                       "phải dùng nội dung (từ điển kỹ năng, Job Family), không dùng dung lượng văn bản.")
        else:
            only = "IT" if jd_it else "ngoài IT"
            med = statistics.median(jd_it or jd_non)
            other = fmt_int(len(jd_non) if jd_it else len(jd_it))
            chart_title = (f"Chỉ nhóm {only} có JD đo được: trung vị {fmt_int(med)} ký tự "
                           f"(nhóm còn lại {other} tin)")
            cmp_txt = f"; trung vị nhóm {only} {fmt_int(med)} ký tự"
            meaning = (f"Một nhóm trống JD nên chưa so sánh độ dài IT / ngoài IT được; con số {fmt_int(med)} "
                       f"ký tự chỉ mô tả nhóm {only} trong mẫu này.")
        box_chart(jd_groups, chart_title,
                  f"n = {fmt_int(len(jd_all))}/{fmt_int(n)} tin có section 'Mô tả Công việc' trong "
                  f"`detail-row`",
                  src, fig_dir / "15_jd_length_groups.png", xlabel="Nhóm",
                  ylabel="Số ký tự (text phẳng)")
        add(15, "Độ dài nội dung mô tả công việc", "15_jd_length_groups.png",
            f"Section 'Mô tả Công việc' (key của `detail-row`) xuất ở {fmt_int(len(jd_all))}/{fmt_int(n)} "
            f"tin ({pct(len(jd_all), n)}){cov_txt}{cmp_txt}; {fmt_int(short)} tin ({pct(short, n)}) dưới "
            f"1.000 ký tự. `description` JSON-LD đầy đủ ở {fmt_int(n_desc)}/{fmt_int(n)} tin, trung vị "
            f"{fmt_int(jsonld_med)} ký tự text thuần (đã bóc thẻ HTML).",
            meaning,
            "`detail-box` CHỈ là hộp metadata (rỗng ở " + fmt_int(zero_box) + " tin), JD thật nằm trong "
            "`detail-row` và `job-posting-schema.description`; độ dài text phẳng chưa tính thẻ HTML nên "
            "không so sánh được với token của mô hình ngôn ngữ.")

    # 16 - Ledger CDC (đối chiếu Phase 1)
    if led["statuses"]:
        labels = [f"{st} / {'repost' if rp else 'có envelope'}" for (st, rp), _ in
                  sorted(led["statuses"].items(), key=lambda x: -x[1])]
        vals = [v for _, v in sorted(led["statuses"].items(), key=lambda x: -x[1])]
        hl = labels.index("DONE / repost") if "DONE / repost" in labels else 0
        barh_chart(labels, vals, [pct(v, led_total) for v in vals],
                   f"Ledger {fmt_int(led_total)} URL DONE - {fmt_int(led_repost)} URL repost không envelope "
                   f"({fmt_int(led_total)} - {fmt_int(led_repost)} = {fmt_int(led_total - led_repost)})",
                   f"n = {fmt_int(led_total)} URL trong catalog_master.json; envelope đọc được = "
                   f"{fmt_int(n)} ({pct(n, led_total)} URL); được phát hiện = {fmt_int(led['manifest_urls'])} URL",
                   src, fig_dir / "16_ledger_cdc.png", highlight=hl, xlabel="Số URL")
        add(16, "Ledger CDC (đối chiếu Phase 1)", "16_ledger_cdc.png",
            f"catalog_master: {fmt_int(led_total)} URL của {args.source}, {fmt_int(led_done)} DONE, "
            f"{fmt_int(led_repost)} DONE + có `repost_of_url_hash`, {fmt_int(led_pending)} chưa DONE, "
            f"{fmt_int(led['errors'])} URL có `error_log`; {fmt_int(led['with_version'])} URL có "
            f"`latest_version >= 1` = {fmt_int(n)} envelope EDA.",
            f"Đẳng thức {fmt_int(led_total)} URL - {fmt_int(led_repost)} repost = "
            f"{fmt_int(led_total - led_repost)} envelope khớp chính xác với số tin đã đo; không có tin mất "
            f"không rõ nguyên nhân và không có lỗi mạng tồn đọng.",
            "Ledger là trạng thái tại thời điểm đọc; `manifests/*.jsonl` chỉ là ảnh chụp lúc phát hiện "
            "(vẫn ghi PENDING) nên không dùng nó để đo trạng thái crawl.")
    else:
        skip(16, "Ledger CDC (đối chiếu Phase 1)",
             f"`catalog_master.json` trong {args.ledger} không có URL nào của nguồn `{args.source}` nên "
             f"không đối chiếu được {fmt_int(n)} envelope với Phase 1.")

    # ------------------------------------------------------------------ md
    md = [
        "# CareerViet EDA - chú thích biểu đồ (máy sinh)",
        "",
        f"> Sinh bởi `scripts/careerviet_eda_charts.py` trên **{fmt_int(n)} envelope thật** "
        f"(`data/careerviet/raw`). Chỉ đọc local, không gọi mạng.",
        "",
        f"**{src}**",
        "",
        "Mỗi biểu đồ gồm 3 phần: **Quan sát** (số đo được), **Ý nghĩa** (với thị trường IT), "
        "**Hạn chế** (thiên lệch dữ liệu).",
        "",
    ]
    for i in ins:
        md.append(f"## {i['no']}. {i['title']}")
        md.append("")
        if i["file"]:
            md.append(f"![{i['title']}](figures/careerviet/{i['file']})")
            md.append("")
        md.append(f"- **Quan sát:** {i['observe']}")
        md.append(f"- **Ý nghĩa:** {i['meaning']}")
        md.append(f"- **Hạn chế:** {i['limit']}")
        md.append("")
    out_md = Path(args.md_out)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")

    # Don PNG cua dot cu (chi trong --fig-dir, khong bao gio cham du lieu raw).
    made = {i["file"] for i in ins if i["file"]}
    stale = []
    if not args.keep_stale:
        for p in sorted(fig_dir.glob("*.png")):
            if p.name not in made:
                p.unlink()
                stale.append(p.name)
    if stale:
        print(f"[EDA] Xoa {len(stale)} PNG cu khong con duoc sinh: " + ", ".join(stale))
    print(f"[EDA] {len(list(fig_dir.glob('*.png')))} PNG -> {fig_dir}/")
    print(f"[EDA] Chú thích -> {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
