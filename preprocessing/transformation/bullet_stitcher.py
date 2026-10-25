# -*- coding: utf-8 -*-
"""preprocessing.transformation.bullet_stitcher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Thuật toán ghép câu bullet bị đứt đoạn (Bullet Stitcher) đặc biệt cho Vieclam24h.

Hiện tượng:
  DOM selector bắt từng thẻ con rời rạc khiến câu:
    "Có kinh nghiệm làm việc tối thiểu 1 năm với Python"
  Bị chẻ thành các dòng:
    ["Có", "kinh nghiệm", "làm việc", "tối thiểu 1 năm với Python"]

Giải pháp:
  Thuật toán nhận diện các mảnh vụn dòng ngắn (dưới 4 từ) và nối lại thành câu hoàn chỉnh.
"""

from __future__ import annotations

import re
from typing import List, Union

BULLET_PREFIX_REGEX = re.compile(r"^\s*(?:[-–•*+▪▫➢]|(?:\d+[.)]))\s*")


def stitch_fragmented_bullets(items: Union[List[str], str]) -> List[str]:
    """Nối các dòng bullet bị chẻ vụn thành danh sách các câu hoàn chỉnh."""
    if isinstance(items, str):
        lines = [line.strip() for line in items.splitlines() if line.strip()]
    elif isinstance(items, list):
        lines = [str(x).strip() for x in items if str(x).strip()]
    else:
        return []

    if not lines:
        return []

    stitched: List[str] = []
    current_sentence = ""

    for line in lines:
        is_new_bullet = bool(BULLET_PREFIX_REGEX.match(line))
        word_count = len(line.split())

        # Nếu dòng hiện tại là một bullet mới hoặc câu trước đã kết thúc trọn vẹn (có dấu chấm kết thúc)
        if is_new_bullet or not current_sentence:
            if current_sentence:
                stitched.append(current_sentence.strip())
            current_sentence = line
        else:
            # Nếu dòng trước chưa có dấu kết thúc và dòng hiện tại là đoạn ngắn tiếp nối
            prev_ended = current_sentence.endswith((".", ":", ";", "!"))
            if not prev_ended and word_count <= 4:
                # Nối tiếp vào câu trước
                current_sentence = f"{current_sentence} {line}"
            elif not prev_ended and not is_new_bullet:
                # Nối tiếp câu dài
                current_sentence = f"{current_sentence} {line}"
            else:
                stitched.append(current_sentence.strip())
                current_sentence = line

    if current_sentence:
        stitched.append(current_sentence.strip())

    return stitched
