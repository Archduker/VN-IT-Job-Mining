# -*- coding: utf-8 -*-
"""Lịch ca Phase 2 (Detail) dùng chung cho DAG Airflow, AdaptiveWorkloadRouter và monitoring.

Đổi giờ ở đây thì cron của crawler_detail_<source>, quy tắc của router và
bảng lịch trên trang Crawling cùng đổi theo. Module không import gì khác để DAG
đọc nhanh khi Airflow parse file.
"""

# Các giờ (Việt Nam) DAG crawler_detail_<source> được kích hoạt mỗi ngày.
DETAIL_SLOT_HOURS = (9, 14, 18, 21, 22)

# T2–T6: router chỉ cho chạy từ giờ này trở đi, tối đa một ca mỗi tối.
WEEKDAY_EVENING_HOUR = 20

DETAIL_CRON = f"0 {','.join(str(h) for h in DETAIL_SLOT_HOURS)} * * *"
WEEKDAY_SLOT_HOURS = tuple(h for h in DETAIL_SLOT_HOURS if h >= WEEKDAY_EVENING_HOUR)
WEEKEND_SLOT_HOURS = DETAIL_SLOT_HOURS
