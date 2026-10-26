# -*- coding: utf-8 -*-
"""Pydantic schemas cho Crawling Observatory."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SourceStatus(BaseModel):
    id: str
    name: str
    status: str = "idle"  # idle | running | completed | error
    total_urls: int = 0
    total_raw: int = 0
    last_crawled_at: Optional[str] = None
    engine: str = "curl_cffi"


class TriggerCrawlRequest(BaseModel):
    phase: str = Field(default="all", description="discover | detail | all")
    max_items: int = Field(default=30, ge=1, le=1000)
    max_pages: Optional[int] = Field(default=None, ge=1)
    engine: Optional[str] = Field(default=None, description="curl_cffi | playwright")


class CrawlJobResponse(BaseModel):
    job_id: str
    source: str
    phase: str
    status: str
    message: str


class LedgerItem(BaseModel):
    job_id: Optional[str] = None
    url_hash: str
    job_title: Optional[str] = None
    company: Optional[str] = None
    url: Optional[str] = None
    status: str
    scraped_at: Optional[str] = None
    http_status: Optional[int] = None
    content_hash: Optional[str] = None
    repost_of_url_hash: Optional[str] = None


class LedgerResponse(BaseModel):
    source: str
    total: int
    counts: Dict[str, int]
    page: int
    page_size: int
    items: List[LedgerItem]
