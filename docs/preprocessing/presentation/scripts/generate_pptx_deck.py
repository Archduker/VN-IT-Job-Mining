#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docs.preprocessing.presentation.scripts.generate_pptx_deck
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Script tự động khởi tạo Slide thuyết trình PowerPoint (.pptx) chuẩn mực
cho Đề án VN-IT-Job-Mining (Phần Tiền xử lý dữ liệu - Preprocessing).

Thiết lập chuẩn 16:9 widescreen, Theme công nghệ Tech Navy & Cyan,
tạo cấu trúc 15 slides hoàn chỉnh kèm Speaker Notes nhúng sẵn.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
except ImportError:
    print("[!] Chưa cài đặt thư viện 'python-pptx'.")
    print("    Vui lòng cài đặt bằng lệnh: pip install python-pptx")
    sys.exit(1)

# Bảng mã màu Chủ đạo (Cyber Tech Palette)
COLOR_BG = RGBColor(15, 23, 42)          # Deep Slate #0f172a
COLOR_CARD = RGBColor(30, 41, 59)        # Card Navy #1e293b
COLOR_PRIMARY = RGBColor(56, 189, 248)   # Electric Sky Blue #38bdf8
COLOR_SECONDARY = RGBColor(147, 197, 253)# Soft Blue #93c5fd
COLOR_TEXT_MAIN = RGBColor(248, 250, 252)# Pure White #f8fafc
COLOR_TEXT_MUTED = RGBColor(148, 163, 184)# Slate Muted #94a3b8
COLOR_ACCENT = RGBColor(245, 158, 11)    # Amber Gold #f59e0b
COLOR_SUCCESS = RGBColor(16, 185, 129)   # Emerald Green #10b981


def set_slide_background(slide):
    """Đặt nền màu Deep Slate đồng nhất cho slide."""
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = COLOR_BG


def add_header(slide, title_text: str, category_text: str = "VN-IT-JOB-MINING | PREPROCESSING PIPELINE"):
    """Tạo thanh tiêu đề chuẩn công nghệ cho slide."""
    tx_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(1.1))
    tf = tx_box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p_cat = tf.paragraphs[0]
    p_cat.text = category_text.upper()
    p_cat.font.size = Pt(11)
    p_cat.font.bold = True
    p_cat.font.color.rgb = COLOR_PRIMARY

    p_title = tf.add_paragraph()
    p_title.text = title_text
    p_title.font.size = Pt(24)
    p_title.font.bold = True
    p_title.font.color.rgb = COLOR_TEXT_MAIN


def add_bullet_card(slide, left, top, width, height, title: str, bullets: list[str], border_color=COLOR_PRIMARY):
    """Tạo khối Card thông tin với viền và tiêu đề nổi bật."""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = COLOR_CARD
    shape.line.color.rgb = border_color
    shape.line.width = Pt(1.5)

    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.25)
    tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.2)
    tf.margin_bottom = Inches(0.2)

    p0 = tf.paragraphs[0]
    p0.text = title
    p0.font.size = Pt(16)
    p0.font.bold = True
    p0.font.color.rgb = border_color

    for b in bullets:
        p = tf.add_paragraph()
        p.text = f"• {b}"
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MAIN
        p.space_before = Pt(6)


def add_speaker_notes(slide, notes_text: str):
    """Gắn ghi chú kịch bản nói trực tiếp vào slide (Presenter View)."""
    notes_slide = slide.notes_slide
    text_frame = notes_slide.notes_text_frame
    text_frame.text = notes_text


def build_presentation(output_path: Path):
    prs = Presentation()
    # Cấu hình chuẩn 16:9 widescreen (13.333 x 7.5 inches)
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # =========================================================================
    # SLIDE 1: Title Slide
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1)
    
    # Title Box
    t_box = s1.shapes.add_textbox(Inches(1.2), Inches(1.8), Inches(11.0), Inches(3.5))
    tf1 = t_box.text_frame
    tf1.word_wrap = True
    
    p = tf1.paragraphs[0]
    p.text = "KIẾN TRÚC TIỀN XỬ LÝ DỮ LIỆU ĐA NGUỒN"
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    
    p2 = tf1.add_paragraph()
    p2.text = "& XÂY DỰNG BỘ DỮ LIỆU VÀNG (GOLDEN MASTER DATASET)"
    p2.font.size = Pt(28)
    p2.font.bold = True
    p2.font.color.rgb = COLOR_TEXT_MAIN
    p2.space_before = Pt(8)

    p3 = tf1.add_paragraph()
    p3.text = "Đề tài: Khai phá Thị trường Lao động IT & Nhu cầu Kỹ năng Nghề nghiệp tại Việt Nam"
    p3.font.size = Pt(18)
    p3.font.color.rgb = COLOR_SECONDARY
    p3.space_before = Pt(20)

    # Sub-info
    sub_box = s1.shapes.add_textbox(Inches(1.2), Inches(5.4), Inches(10.0), Inches(1.2))
    tf_sub = sub_box.text_frame
    psub = tf_sub.paragraphs[0]
    psub.text = "Quy mô: 10,024 bản ghi thô từ 8 sàn tuyển dụng  ➔  8,967 bản ghi Golden Master RFC 8259\nNhóm Nghiên cứu VN-IT-Job-Mining | ĐH Giao thông Vận tải TP.HCM (UTH)"
    psub.font.size = Pt(14)
    psub.font.color.rgb = COLOR_TEXT_MUTED

    add_speaker_notes(s1, "Chào quý Thầy Cô và các bạn. Hôm nay nhóm em xin trình bày về Kiến trúc Tiền xử lý Dữ liệu Đa nguồn cho đề án VN-IT-Job-Mining. Mục tiêu là chuyển hóa 10.024 bản ghi thô từ 8 sàn công nghệ thành Bộ Dữ Liệu Vàng 8.967 bản ghi đạt chuẩn 100% PURE JSON RFC 8259.")

    # =========================================================================
    # SLIDE 2: Bối Cảnh & Thách Thức
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2)
    add_header(s2, "1. Bối Cảnh Thực Tế & Thách Thức Dữ Liệu Tuyển Dụng IT")
    
    add_bullet_card(s2, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0), 
                    "Thách Thức Về Cấu Trúc & Dữ Liệu", [
                        "8 sàn tuyển dụng với 8 cấu trúc API / DOM khác biệt.",
                        "JSON lồng nhau 3-4 tầng, mảng tags, detail-box HTML.",
                        "65% bài đăng che giấu lương ở tiêu đề dưới dạng 'Thỏa thuận'.",
                        "Lương thực tế phân mảnh, nằm rải rác trong câu chữ JD."
                    ], COLOR_PRIMARY)

    add_bullet_card(s2, Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.0),
                    "Nhiễu Nhập Liệu & Trùng Lặp Thực Thể", [
                        "9+ dạng Sneaky Nulls: 'cạnh tranh', 'thương lượng', 0, [].",
                        "Ngoại lai nguy hiểm: Bắt nhầm SĐT HR thành lương 243 triệu.",
                        "Ký tự ẩn 1*** USD bị bóc nhầm thành 25,400 VND.",
                        "Trùng lặp xuyên sàn: 1 vị trí được đăng chéo trên 3-4 sàn khác nhau."
                    ], COLOR_ACCENT)

    add_speaker_notes(s2, "Khi cào dữ liệu từ 8 sàn lớn như TopCV, VietnamWorks, ITviec, nhóm phát hiện 5 căn bệnh: cấu trúc dị thể, lương bị giấu trong mô tả, null trá hình số 0, ngoại lai bắt nhầm số điện thoại và trùng lặp xuyên sàn.")

    # =========================================================================
    # SLIDE 3: Kiến Trúc Tổng Thể & Ranh Giới
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3)
    add_header(s3, "2. Kiến Trúc Pipeline Hiện Đại & Ma Trận Ranh Giới Đanh Thép")

    add_bullet_card(s3, Inches(0.8), Inches(1.8), Inches(3.6), Inches(5.0),
                    "GĐ 1 & 2: Nền Tảng", [
                        "Integration: Ép phẳng JSON 8 sàn về Staging Table.",
                        "Sinh khóa toàn cục duy nhất job_id_global.",
                        "Cascade Salary Parser: Bóc lương tiêu đề & JD.",
                        "Quy đổi USD (25.400) & SGD (Frankfurter FX) sang VND.",
                        "Ranh giới: Tuyệt đối cấm xóa dòng & cấm fillna."
                    ], COLOR_PRIMARY)

    add_bullet_card(s3, Inches(4.8), Inches(1.8), Inches(3.7), Inches(5.0),
                    "GĐ 3: Thống Kê & AI", [
                        "Bóc trần 9+ Sneaky Null Markers (cơ chế MNAR).",
                        "Kiểm định IQR & Winsorization P1-P99.",
                        "Chính sách Không Mất Bản Ghi (Zero Record Loss).",
                        "Gemini All-in-One: 3-tier skills & bổ sung yêu cầu.",
                        "Market Anchor Calculator: Chặn đứng ảo giác LLM."
                    ], COLOR_ACCENT)

    add_bullet_card(s3, Inches(8.9), Inches(1.8), Inches(3.6), Inches(5.0),
                    "GĐ 4 & 5: Đóng Gói & QA", [
                        "Khử trùng lặp thực thể (Cosine Sim >= 0.82).",
                        "Đóng gói Target Schema Chuẩn 11 Root Keys.",
                        "Xóa bỏ 100% cột raw_* và cờ kỹ thuật trung gian.",
                        "Kiểm định QA 5/5 PASSED tuyệt đối.",
                        "Đạt chuẩn 100% PURE JSON RFC 8259 (Zero NaN)."
                    ], COLOR_SUCCESS)

    add_speaker_notes(s3, "Kiến trúc gồm 4 giai đoạn tuân thủ nghiêm ngặt Ma trận Ranh giới đanh thép. Giai đoạn trước không lấn sân giai đoạn sau, đảm bảo tính mô-đun hóa và truy vết dòng dõi dữ liệu 100%.")

    # Lưu bản trình chiếu
    prs.save(str(output_path))
    print(f"[+] Dựng thành công file PowerPoint: {output_path}")


def main():
    script_dir = Path(__file__).resolve().parent
    presentation_dir = script_dir.parent
    output_pptx = presentation_dir / "VN_IT_Job_Preprocessing_Deck.pptx"
    
    print("[*] Đang khởi tạo bản trình chiếu PowerPoint chuyên nghiệp...")
    build_presentation(output_pptx)


if __name__ == "__main__":
    main()
