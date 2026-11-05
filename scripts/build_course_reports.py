#!/usr/bin/env python3
"""Build the unified course report from Markdown. Requires python-docx and Pillow.

Run: python3 scripts/build_course_reports.py
Outputs live beside the Markdown sources in docs/reports/.
"""
from __future__ import annotations

import re
from pathlib import Path
from tempfile import TemporaryDirectory

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "docs" / "reports"
FONT = "Times New Roman"
BLUE = "17365D"


def xml(tag, **attrs):
    element = OxmlElement(tag)
    for key, value in attrs.items():
        element.set(qn(key), str(value))
    return element


def field(paragraph, instruction, placeholder="1"):
    run = paragraph.add_run()
    run._r.append(xml("w:fldChar", **{"w:fldCharType": "begin"}))
    code = xml("w:instrText", **{"xml:space": "preserve"})
    code.text = f" {instruction} "
    run._r.append(code)
    run._r.append(xml("w:fldChar", **{"w:fldCharType": "separate"}))
    paragraph.add_run(placeholder)
    paragraph.add_run()._r.append(xml("w:fldChar", **{"w:fldCharType": "end"}))


def inline(paragraph, text, source):
    """Preserve bold, code and external links; print repo-relative citations."""
    pattern = r"(\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)"
    for token in re.split(pattern, text):
        if not token:
            continue
        if token.startswith("[") and "](" in token:
            match = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", token)
            label, target = match.groups()
            if target.startswith("https://"):
                relation = paragraph.part.relate_to(
                    target,
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                    is_external=True,
                )
                link = xml("w:hyperlink", **{"r:id": relation})
                run = xml("w:r")
                props = xml("w:rPr")
                props.append(xml("w:color", **{"w:val": BLUE}))
                props.append(xml("w:u", **{"w:val": "single"}))
                run.append(props)
                value = xml("w:t")
                value.text = label.replace("*", "")
                run.append(value)
                link.append(run)
                paragraph._p.append(link)
            else:
                path = (source.parent / target).resolve().relative_to(ROOT)
                paragraph.add_run(f"{label} ({path.as_posix()})")
        elif token.startswith("**"):
            paragraph.add_run(token[2:-2]).bold = True
        elif token.startswith("*"):
            paragraph.add_run(token[1:-1]).italic = True
        elif token.startswith("`"):
            paragraph.add_run(token[1:-1])
        else:
            paragraph.add_run(token)


def make_table(doc, lines, source, cover=False):
    rows = [[s.strip() for s in line.strip().strip("|").split("|")] for line in lines]
    rows = [row for row in rows if not all(re.fullmatch(r":?-+:?", x) for x in row)]
    table = doc.add_table(rows=0, cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table.autofit = False
    n = len(rows[0])
    widths = ([4, 12] if cover else [16 / n] * n)
    for col, width in zip(table.columns, widths):
        col.width = Cm(width)
    for i, values in enumerate(rows):
        cells = table.add_row().cells
        for j, (cell, value) in enumerate(zip(cells, values)):
            cell.width = Cm(widths[j])
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(4)
            paragraph.paragraph_format.space_before = Pt(3)
            paragraph.paragraph_format.line_spacing = 1.05
            inline(paragraph, value, source)
            for run in paragraph.runs:
                run.font.size = Pt(11 if cover or n <= 3 else 10)
                if i == 0:
                    run.bold = True
            if i == 0:
                cell._tc.get_or_add_tcPr().append(xml("w:shd", **{"w:fill": "E8EEF5"}))
        if i == 0:
            table.rows[-1]._tr.get_or_add_trPr().append(xml("w:tblHeader"))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def diagram(path, cleaning):
    """Draw a source-controlled workflow, without rasterizing document text."""
    image = Image.new("RGB", (1800, 1370), "white")
    draw = ImageDraw.Draw(image)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font = ImageFont.truetype(font_path, 35)
    small = ImageFont.truetype(font_path, 31)
    if cleaning:
        main = ["Đóng băng raw và lập manifest", "Kiểm envelope và định danh",
                "Chọn snapshot, bỏ bản sao kỹ thuật", "Đánh giá phạm vi IT và địa lý",
                "Gắn cờ thiếu và bất thường", "Tập Clean: raw + metadata", "Chuyển sang preprocessing"]
        branches = [(1, "Lỗi kỹ thuật → Cách ly"), (3, "Ngoài phạm vi → Sổ loại"),
                    (5, "Báo cáo chất lượng / Review")]
    else:
        main = ["Input Clean và cờ chất lượng", "Ánh xạ schema theo nguồn",
                "Chuyển kiểu, giữ ngữ cảnh văn bản", "Chuẩn hóa nghề và kỹ năng",
                "Bảng tin và bằng chứng từng trường", "Quan hệ tin–kỹ năng / tin–địa điểm", "Tập phân tích → Nghề và kỹ năng"]
        branches = [(1, "Báo lỗi mapping và độ phủ"), (4, "Xác minh tin cùng thực thể"),
                    (6, "Ma trận khi có bài toán cụ thể")]
    def arrow(a, b):
        draw.line([a, b], fill="#52677b", width=5)
        x, y = b
        if a[0] == x:
            draw.polygon([(x, y), (x-12, y-18), (x+12, y-18)], fill="#52677b")
        else:
            draw.polygon([(x, y), (x-18, y-12), (x-18, y+12)], fill="#52677b")
    for i, label in enumerate(main):
        y = 35 + i*180
        if i:
            arrow((530, y-55), (530, y))
        draw.rounded_rectangle((40, y, 1020, y+125), radius=16, fill="#eef3f8", outline="#17365d", width=3)
        draw.text((530, y+62), label, font=font, fill="#17365d", anchor="mm")
    for i, label in branches:
        y = 35 + i*180
        arrow((1020, y+62), (1110, y+62))
        draw.rounded_rectangle((1110, y+8, 1780, y+117), radius=14, fill="#f7f4eb", outline="#a29064", width=3)
        draw.text((1445, y+62), label, font=small, fill="#51472f", anchor="mm")
    image.save(path)


def configure(doc, title):
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin, section.bottom_margin = Cm(2), Cm(2)
    section.left_margin, section.right_margin = Cm(3), Cm(2)
    section.header_distance = section.footer_distance = Cm(1)
    section.different_first_page_header_footer = True
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.3
    normal.paragraph_format.space_after = Pt(6)
    normal.element.get_or_add_rPr().append(xml("w:lang", **{"w:val": "vi-VN"}))
    for name, size in [("Title", 20), ("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 12)]:
        style = doc.styles[name]
        style.font.name, style.font.size = FONT, Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(BLUE)
        style.paragraph_format.keep_with_next = True
    header = section.header.paragraphs[0]
    header.text = "VN-IT-JOB-MINING  |  " + title
    header.runs[0].font.size = Pt(9)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("Trang ")
    field(footer, "PAGE")
    doc.settings.element.append(xml("w:updateFields", **{"w:val": "true"}))
    doc.core_properties.title = title
    doc.core_properties.subject = "Đồ án phân tích nghề nghiệp và kỹ năng IT"
    doc.core_properties.language = "vi-VN"


def build(source):
    lines = source.read_text(encoding="utf-8").splitlines()
    cleaning = source.name.startswith("01")
    combined = source.name.startswith("bao_cao_tong_hop")
    title = "Cleaning và Preprocessing" if combined else "Data Cleaning" if cleaning else "Tích hợp và Data Preprocessing"
    doc = Document()
    configure(doc, title)
    # A separate cover, with editable institutional information.
    p = doc.add_paragraph("BÁO CÁO ĐỒ ÁN MÔN HỌC", "Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(40)
    p = doc.add_paragraph(lines[1].removeprefix("# "), "Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(20)
    p = doc.add_paragraph()
    inline(p, lines[3], source)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(20)
    cover_start = next(i for i, x in enumerate(lines) if x.startswith("|"))
    end = cover_start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    make_table(doc, lines[cover_start:end], source, cover=True)
    p = doc.add_paragraph("Bản khảo sát và thiết kế — chưa phải kết quả thực nghiệm pipeline mới")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].italic = True
    with TemporaryDirectory(prefix="vn_it_reports_") as temporary:
        i = end
        figure_count = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            if line == "## Mục lục":
                doc.add_page_break()
                doc.add_paragraph("Mục lục", "Title")
                toc = doc.add_paragraph()
                run = toc.add_run()
                run._r.append(xml("w:fldChar", **{"w:fldCharType": "begin"}))
                code = xml("w:instrText", **{"xml:space": "preserve"})
                code.text = ' TOC \\o "1-2" \\h \\z \\u '
                run._r.append(code)
                run._r.append(xml("w:fldChar", **{"w:fldCharType": "separate"}))
                i += 1
                while i < len(lines) and not lines[i].startswith("## "):
                    if re.match(r"\d+\. ", lines[i]):
                        toc = doc.add_paragraph(lines[i])
                    i += 1
                toc.add_run()._r.append(xml("w:fldChar", **{"w:fldCharType": "end"}))
                continue
            if line.startswith("## "):
                doc.add_page_break()
                doc.add_heading(line[3:], 1)
            elif line.startswith("### "):
                doc.add_heading(line[4:], 2)
            elif line.startswith("|"):
                j = i
                while j < len(lines) and lines[j].startswith("|"):
                    j += 1
                make_table(doc, lines[i:j], source)
                i = j
                continue
            elif line == "```mermaid":
                j = i + 1
                while j < len(lines) and lines[j].strip() != "```":
                    j += 1
                figure_count += 1
                image_path = Path(temporary) / f"workflow_{figure_count}.png"
                is_cleaning = "Đóng băng" in "\n".join(lines[i:j])
                diagram(image_path, is_cleaning)
                doc.add_picture(str(image_path), width=Cm(16))
                process = "Data Cleaning" if is_cleaning else "Data Preprocessing"
                p = doc.add_paragraph(f"Hình {figure_count}. Quy trình {process} đề xuất và các nhánh kiểm soát chất lượng.")
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.runs[0].italic = True
                i = j + 1
                continue
            else:
                p = doc.add_paragraph(style="List Bullet" if line.startswith("- ") else "Normal")
                inline(p, line[2:] if line.startswith("- ") else line, source)
                if line.startswith("**Bảng "):
                    p.paragraph_format.keep_with_next = True
                elif not line.startswith("-"):
                    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            i += 1
        target = source.with_suffix(".docx")
        doc.save(target)
    print(target.relative_to(ROOT))


def combine_sources():
    """Keep the substantive chapters, with one introduction and reference section."""
    clean = (REPORTS / "01_bao_cao_data_cleaning.md").read_text(encoding="utf-8")
    prep = (REPORTS / "02_bao_cao_data_preprocessing.md").read_text(encoding="utf-8")

    def sections(text):
        return {int(m[1]): m[0] for m in re.finditer(
            r"^## (\d+)\. .*?(?=^## |\Z)", text, re.M | re.S
        )}

    def citations(text, prefix):
        return re.sub(r"\[([NP]\d+[^\]]*)\]", lambda m: "[" + re.sub(
            r"([NP]\d+)", lambda n: prefix + "-" + n[0], m[1]
        ) + "]", text)

    c, p = sections(citations(clean, "C")), sections(citations(prep, "P"))
    cover = clean.split("## Tóm tắt")[0].replace(
        "KHẢO SÁT DỮ LIỆU VÀ THIẾT KẾ QUY TRÌNH DATA CLEANING",
        "KHẢO SÁT DỮ LIỆU, DATA CLEANING VÀ DATA PREPROCESSING"
    ).replace("1.0 — Khảo sát hiện trạng và đề xuất thiết kế lại",
              "2.0 — Báo cáo tổng hợp Cleaning và Preprocessing")
    abstract = """## Tóm tắt

Báo cáo khảo sát dữ liệu tuyển dụng từ tám nguồn và thiết kế lại hai quy trình Data Cleaning, tích hợp và Data Preprocessing cho đề tài phân tích nghề nghiệp và kỹ năng IT. Nội dung đi từ mục tiêu, input/output, phạm vi và chất lượng dữ liệu đến quy tắc xử lý, tiêu chí đánh giá và thứ tự điều chỉnh project.

Phần Data Cleaning tập trung vào phạm vi IT, snapshot, trùng kỹ thuật, dữ liệu thiếu và việc giữ hoặc loại tin có căn cứ. Phần Data Preprocessing tiếp nối bằng ánh xạ đa nguồn, chuẩn hóa nghề, kỹ năng, địa điểm và các thuộc tính bổ trợ; đầu ra là bộ dữ liệu phân tích có thể truy vết. Các số liệu trong báo cáo được đối chiếu với tài liệu lịch sử và mã nguồn, chưa phải thực nghiệm của pipeline đề xuất. Không bổ sung LLM hay công bố kết quả khai phá chưa thực hiện.

**Từ khóa:** tuyển dụng IT, chất lượng dữ liệu, cleaning, preprocessing, nghề nghiệp, kỹ năng.

"""
    c[1] = c[1].replace("Ranh giới hai báo cáo", "Ranh giới hai quy trình")
    c[1] = c[1].replace("bộ báo cáo dùng quy ước", "báo cáo dùng quy ước")
    c[1] = c[1].replace("Chi tiết tại [Báo cáo 2](02_bao_cao_data_preprocessing.md).", "Chi tiết tại Chương 6–10.")
    c[4] = c[4].replace("Thiết kế quy trình Data Cleaning", "PHẦN I — Thiết kế quy trình Data Cleaning", 1)

    chapters = [c[n] for n in range(1, 6)]
    for old in range(2, 7):
        new = old + 4
        part = p[old]
        part = re.sub(rf"^(## |### ){old}\.", lambda m: m[1] + f"{new}.", part, flags=re.M)
        part = re.sub(r"Bảng (\d+)", lambda m: f"Bảng {int(m[1])+9}", part)
        if old == 2:
            part = part.replace("Hiện trạng và hợp đồng dữ liệu", "PHẦN II — Tích hợp và Data Preprocessing: hiện trạng và hợp đồng dữ liệu", 1)
        part = part.replace("xem Báo cáo 1", "xem Chương 4–5").replace("theo Báo cáo cáo 1", "theo Chương 4–5")
        part = part.replace("theo Báo cáo 1", "theo Chương 4–5")
        part = part.replace("hai báo cáo này", "báo cáo này")
        chapters.append(part)

    conclusion = """## 11. Kết luận và định hướng thực hiện

Project cần lấy câu hỏi về nghề nghiệp và kỹ năng IT làm căn cứ cho mọi quyết định xử lý. Cleaning tạo tập tin có phạm vi rõ ràng, giữ được thông tin gốc và giải thích được quyết định giữ, cách ly hoặc loại. Preprocessing tiếp nhận tập này để tích hợp schema, chuẩn hóa nghiệp vụ và tạo các bảng phân tích với bằng chứng và mẫu số rõ ràng.

Thứ tự ưu tiên là đóng băng tập dữ liệu, kiểm lại lọc IT và JD ngắn, tách trùng kỹ thuật khỏi trùng nghiệp vụ, sau đó bổ sung bằng chứng kỹ năng và đánh giá nhãn nghề. Tái sử dụng các thành phần hiện có nhưng không mặc định áp dụng top K, capping, log hoặc encoding trước khi có nhu cầu phân tích cụ thể. Các bảng kế hoạch ở Chương 5 và Chương 10 là cơ sở triển khai; các bảng quyết định trong phụ lục chỉ rõ phần giữ lại, sửa, bổ sung và hoãn.

Giới hạn khảo sát là chưa có raw cục bộ và chưa kiểm chứng trạng thái R2 hiện tại. Số liệu lịch sử không thay thế kết quả thực nghiệm mới. Chất lượng của quy trình đề xuất cần được đo trên cùng manifest và tập nhãn tay độc lập trước khi công bố kết quả khai phá.

"""
    references = "## 12. Tài liệu tham khảo\n\nCác mã C-* chỉ căn cứ của phần Cleaning; P-* chỉ căn cứ của phần Preprocessing. Một tài liệu có thể được sử dụng cho cả hai phần.\n\n"
    references += re.sub(r"^## 7\..*\n", "### 12.1. Căn cứ khảo sát và Cleaning\n", c[7])
    references += re.sub(r"^## 8\..*\n", "### 12.2. Căn cứ tích hợp và Preprocessing\n", p[8])
    appendix = c[8].replace("## 8. Phụ lục: hồ sơ quyết định và việc cần thực hiện", "## 13. Phụ lục: hồ sơ quyết định, ví dụ và công việc cần thực hiện")
    appendix = re.sub(r"^### 8\.", "### 13.", appendix, flags=re.M)
    extra = re.sub(r"^## 9\..*\n", "", p[9])
    extra = re.sub(r"^### 9\.(\d+)", lambda m: f"### 13.{int(m[1])+2}", extra, flags=re.M)
    content = "\n".join(chapters) + conclusion + references + appendix + extra
    toc = "## Mục lục\n\n" + "\n".join(re.findall(r"^## (\d+\. .*)", content, re.M)) + "\n\n"
    target = REPORTS / "bao_cao_tong_hop_cleaning_preprocessing.md"
    target.write_text(cover + abstract + toc + content, encoding="utf-8")
    return target


if __name__ == "__main__":
    build(combine_sources())
