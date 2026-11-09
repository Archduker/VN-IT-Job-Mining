"""preprocessing.deduplication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Khử trùng lặp 2 lớp cho dữ liệu tuyển dụng IT (docs/spec/05_preprocessing_spec.md mục 3).

  - `text_norm`    : bóc HTML, chuẩn Unicode, lọc boilerplate, băm nội dung chuẩn hóa.
  - `blocking`     : Blocking Key = Slug(Company_Norm) + "_" + Location_Code + "_" + Title_Group.
  - `intra_source` : tầng 1 - nội sàn, kiểm toán chuỗi version CDC (D1) + repost (D2).
  - `inter_source` : tầng 2 - liên sàn, TF-IDF Cosine >= 0.85 (D4, D5) + Golden Master Fusion (D6).
  - `run`          : điều phối, ghi `data/preprocessing/01b_deduplication/` và
                     `reports/preprocessing/01b_deduplication/` (chạy: python -m preprocessing.deduplication.run).

Toàn bộ là quy tắc tất định, không dùng model/LLM (P0_pipeline_contract.md mục 6).
"""

from preprocessing.deduplication.blocking import (
    blocking_key,
    company_slug,
    location_code,
    title_group,
)
from preprocessing.deduplication.inter_source import COSINE_THRESHOLD, build_blocks, clusters, fuse
from preprocessing.deduplication.text_norm import (
    canonical_hash,
    clean_text,
    fold,
    jd_text,
    strip_html,
)

__all__ = [
    "strip_html",
    "clean_text",
    "fold",
    "canonical_hash",
    "jd_text",
    "company_slug",
    "location_code",
    "title_group",
    "blocking_key",
    "COSINE_THRESHOLD",
    "build_blocks",
    "clusters",
    "fuse",
]
