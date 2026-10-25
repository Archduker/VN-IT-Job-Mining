#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đăng ký kết nối Cloudflare R2 S3 (`r2_s3_conn`) vào cơ sở dữ liệu Airflow.

VN-IT-Job-Mining (R2-Exclusive Object Storage).
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

os.environ["AIRFLOW_HOME"] = str(PROJECT_ROOT / "airflow")

try:
    from airflow import settings
    from airflow.models import Connection
except ImportError:
    print("[ERROR] Apache Airflow chưa được cài đặt trong virtualenv.")
    sys.exit(1)


def register_r2_connection():
    endpoint = (
        os.getenv("R2_ENDPOINT_URL")
        or os.getenv("S3_ENDPOINT_URL")
        or "https://bb8811262069cd3e4d244a9dc7bf6a84.r2.cloudflarestorage.com"
    )
    ak = os.getenv("R2_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
    sk = os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")

    conn_id = "r2_s3_conn"

    session = settings.Session()
    try:
        existing = session.query(Connection).filter(Connection.conn_id == conn_id).first()
        extra_data = {
            "endpoint_url": endpoint,
            "region_name": "auto",
        }

        if existing:
            existing.conn_type = "aws"
            existing.login = ak
            existing.set_password(sk)
            existing.set_extra(json.dumps(extra_data))
            print(f"[OK] Cập nhật kết nối '{conn_id}' thành công.")
        else:
            new_conn = Connection(
                conn_id=conn_id,
                conn_type="aws",
                login=ak,
                password=sk,
                extra=json.dumps(extra_data),
            )
            session.add(new_conn)
            print(f"[OK] Đã tạo mới kết nối '{conn_id}' cho Cloudflare R2.")

        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Không thể đăng ký kết nối '{conn_id}': {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    register_r2_connection()
