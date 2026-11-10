# -*- coding: utf-8 -*-
"""PH2 bước 1: model đồng nhất schema cho bản ghi ra khỏi Integration (spec mục 4.2).

Chỉ khóa và job_title là bắt buộc (C2: job_title rỗng là lỗi schema); các trường còn lại thiếu thì null.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Union

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from preprocessing.common import SOURCES

Scalar = Optional[Union[str, int, float]]


class JobRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job_id_global: str
    source_platform: str
    source_job_id: str
    source_url: str
    crawled_at: str
    job_title: str
    it_rule: Scalar = None
    it_rule_level: Scalar = None
    it_status: Scalar = None
    dedup_key: Scalar = None
    also_on: Optional[List[Any]] = None
    working_locations: Optional[List[str]] = None
    skills_list: Optional[List[str]] = None
    benefits_list: Optional[List[str]] = None

    @field_validator("source_platform")
    @classmethod
    def _source(cls, v: str) -> str:
        if v not in SOURCES:
            raise ValueError("source_platform ngoài SOURCES")
        return v

    @field_validator("source_job_id", "source_url", "job_title")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("rỗng")
        return v

    @field_validator("crawled_at")
    @classmethod
    def _iso(cls, v: str) -> str:
        datetime.fromisoformat(v)  # ném ValueError nếu không phải ISO-8601; giữ nguyên chuỗi
        return v

    @model_validator(mode="after")
    def _prefix(self) -> "JobRecord":
        if not self.job_id_global.startswith(self.source_platform + "_") or self.job_id_global == self.source_platform + "_":
            raise ValueError("job_id_global phải là <nguồn>_<id>")
        return self
