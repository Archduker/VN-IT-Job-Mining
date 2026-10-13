# -*- coding: utf-8 -*-
"""crawlers.preprocessing.eda
~~~~~~~~~~~~~~~~~~~~~~~~~~
Gói thư viện Exploratory Data Analysis (EDA) cho VN-IT-Job-Mining.

Giai đoạn 1 cung cấp:
- EDALoader: Nạp và kiểm định an toàn dữ liệu từ tệp JSON.
- EDAProfiler: Phân tích hồ sơ schema, missingness và kiểu dữ liệu.

Giai đoạn 2 cung cấp:
- SalaryAnalyzer: Phân tích lương theo loại hình tuyển dụng, tiền tệ và kỳ trả lương.
- DateAnalyzer: Phân tích mốc thời gian, hạn ứng tuyển và thời hạn tuyển dụng.
- TextAnalyzer: Phân tích độ dài văn bản, nội dung mỏng và thẻ kỹ năng.
- RiskDetector: Cảnh báo ứng viên phi IT, nhóm ứng viên lặp và bất thường lương.

Giai đoạn 3 cung cấp:
- EDAPipeline: Điều phối toàn bộ quy trình EDA từ đọc file đến tổng hợp báo cáo.
"""

from crawlers.preprocessing.eda.loader import (
    EDALoader,
    EDALoaderError,
    InvalidJSONStructureError,
)
from crawlers.preprocessing.eda.profiler import EDAProfiler
from crawlers.preprocessing.eda.salary_analyzer import SalaryAnalyzer
from crawlers.preprocessing.eda.date_analyzer import DateAnalyzer
from crawlers.preprocessing.eda.text_analyzer import TextAnalyzer
from crawlers.preprocessing.eda.risk_detector import RiskDetector
from crawlers.preprocessing.eda.pipeline import EDAPipeline

__all__ = [
    "EDALoader",
    "EDALoaderError",
    "InvalidJSONStructureError",
    "EDAProfiler",
    "SalaryAnalyzer",
    "DateAnalyzer",
    "TextAnalyzer",
    "RiskDetector",
    "EDAPipeline",
]
