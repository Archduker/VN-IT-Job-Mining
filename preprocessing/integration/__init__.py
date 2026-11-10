# -*- coding: utf-8 -*-
"""preprocessing.integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module tích hợp schema & ép phẳng dữ liệu JSON bán cấu trúc đa nguồn.
"""

from preprocessing.integration.json_flattener import flatten_raw_job_record, JsonFlattener
from preprocessing.integration.run import run as run_integration

__all__ = [
    "flatten_raw_job_record",
    "JsonFlattener",
    "run_integration",
]