# -*- coding: utf-8 -*-
"""preprocessing.integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module tích hợp schema & ép phẳng dữ liệu JSON bán cấu trúc đa nguồn.
"""

from preprocessing.integration.json_flattener import flatten_raw_job_record
from preprocessing.integration.run_integration import integrate_single_source, run_all_integration

__all__ = [
    "flatten_raw_job_record",
    "integrate_single_source",
    "run_all_integration",
]
