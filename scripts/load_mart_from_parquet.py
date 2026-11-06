#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/load_mart_from_parquet.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Loader script to ingest Golden Master IT jobs and Data Mining artifacts
from Apache Parquet files directly into PostgreSQL Analytics Mart (vn_it_jobs).

Tables Supported:
  - curated_jobs   : data/curated/curated_flat_golden_jobs.parquet
  - skill_rules    : mining/artifacts/skill_association_rules.parquet
  - job_clusters   : mining/artifacts/job_clusters.parquet
  - job_anomalies  : mining/artifacts/job_anomalies.parquet

Usage:
  python scripts/load_mart_from_parquet.py --dry-run
  python scripts/load_mart_from_parquet.py --tables all
  python scripts/load_mart_from_parquet.py --tables curated_jobs,job_clusters
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("load_mart")


def get_db_connection_params(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "host": args.host or os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(args.port or os.getenv("POSTGRES_PORT", 5432)),
        "dbname": args.db or os.getenv("POSTGRES_DB", "vn_it_jobs"),
        "user": args.user or os.getenv("POSTGRES_USER", "airflow"),
        "password": args.password or os.getenv("POSTGRES_PASSWORD", "airflow"),
    }


def load_curated_jobs(
    conn: Any,
    parquet_path: Path,
    dry_run: bool = False
) -> int:
    """Load curated golden jobs into curated_jobs table."""
    if not parquet_path.exists():
        logger.warning(f"File curated jobs not found: {parquet_path}")
        return 0

    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas is required to read parquet files. Please install pandas & pyarrow.")
        return 0

    logger.info(f"Reading {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    logger.info(f"Loaded {len(df)} records from {parquet_path.name}.")

    if dry_run:
        logger.info(f"[DRY-RUN] Would insert/update {len(df)} records into curated_jobs.")
        return len(df)

    import psycopg2
    from psycopg2.extras import execute_batch

    cursor = conn.cursor()
    query = """
    INSERT INTO curated_jobs (
        job_id, job_title, company_name, source_platform, job_url,
        job_family, seniority_level, province_norm,
        salary_min_vnd, salary_max_vnd, salary_avg_vnd,
        is_salary_negotiable, skills_array, crawled_date, updated_at
    ) VALUES (
        %(job_id)s, %(job_title)s, %(company_name)s, %(source_platform)s, %(job_url)s,
        %(job_family)s, %(seniority_level)s, %(province_norm)s,
        %(salary_min_vnd)s, %(salary_max_vnd)s, %(salary_avg_vnd)s,
        %(is_salary_negotiable)s, %(skills_array)s, %(crawled_date)s, CURRENT_TIMESTAMP
    )
    ON CONFLICT (job_id) DO UPDATE SET
        job_title = EXCLUDED.job_title,
        company_name = EXCLUDED.company_name,
        job_family = EXCLUDED.job_family,
        seniority_level = EXCLUDED.seniority_level,
        province_norm = EXCLUDED.province_norm,
        salary_min_vnd = EXCLUDED.salary_min_vnd,
        salary_max_vnd = EXCLUDED.salary_max_vnd,
        salary_avg_vnd = EXCLUDED.salary_avg_vnd,
        is_salary_negotiable = EXCLUDED.is_salary_negotiable,
        skills_array = EXCLUDED.skills_array,
        updated_at = CURRENT_TIMESTAMP;
    """

    records = []
    for _, row in df.iterrows():
        skills = row.get("skills_array")
        if isinstance(skills, (list, tuple)):
            skills_list = list(skills)
        elif isinstance(skills, str):
            skills_list = [s.strip() for s in skills.split(",") if s.strip()]
        else:
            skills_list = []

        records.append({
            "job_id": str(row.get("job_id", "")),
            "job_title": str(row.get("job_title", "")),
            "company_name": row.get("company_name"),
            "source_platform": str(row.get("source_platform", "unknown")),
            "job_url": row.get("job_url"),
            "job_family": str(row.get("job_family", "Khác")),
            "seniority_level": row.get("seniority_level"),
            "province_norm": row.get("province_norm"),
            "salary_min_vnd": int(row["salary_min_vnd"]) if pd.notnull(row.get("salary_min_vnd")) else None,
            "salary_max_vnd": int(row["salary_max_vnd"]) if pd.notnull(row.get("salary_max_vnd")) else None,
            "salary_avg_vnd": int(row["salary_avg_vnd"]) if pd.notnull(row.get("salary_avg_vnd")) else None,
            "is_salary_negotiable": bool(row.get("is_salary_negotiable", False)),
            "skills_array": skills_list,
            "crawled_date": row.get("crawled_date"),
        })

    execute_batch(cursor, query, records, page_size=1000)
    conn.commit()
    cursor.close()
    logger.info(f"Successfully inserted/updated {len(records)} rows in curated_jobs.")
    return len(records)


def load_skill_rules(
    conn: Any,
    parquet_path: Path,
    dry_run: bool = False
) -> int:
    """Load association rules into skill_rules table."""
    if not parquet_path.exists():
        logger.warning(f"File skill rules not found: {parquet_path}")
        return 0

    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas is required to read parquet files.")
        return 0

    logger.info(f"Reading {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    logger.info(f"Loaded {len(df)} rules from {parquet_path.name}.")

    if dry_run:
        logger.info(f"[DRY-RUN] Would insert {len(df)} records into skill_rules.")
        return len(df)

    import psycopg2
    from psycopg2.extras import execute_batch

    cursor = conn.cursor()
    # Truncate to refresh latest rules
    cursor.execute("TRUNCATE TABLE skill_rules RESTART IDENTITY;")

    query = """
    INSERT INTO skill_rules (
        antecedents, consequents, support, confidence, lift, conviction, job_family_scope
    ) VALUES (
        %(antecedents)s, %(consequents)s, %(support)s, %(confidence)s, %(lift)s, %(conviction)s, %(job_family_scope)s
    );
    """

    records = []
    for _, row in df.iterrows():
        antecedents = row.get("antecedents")
        consequents = row.get("consequents")
        ant_list = list(antecedents) if isinstance(antecedents, (list, tuple, set)) else [str(antecedents)]
        con_list = list(consequents) if isinstance(consequents, (list, tuple, set)) else [str(consequents)]

        records.append({
            "antecedents": ant_list,
            "consequents": con_list,
            "support": float(row.get("support", 0.0)),
            "confidence": float(row.get("confidence", 0.0)),
            "lift": float(row.get("lift", 0.0)),
            "conviction": float(row["conviction"]) if pd.notnull(row.get("conviction")) else None,
            "job_family_scope": str(row.get("job_family_scope", "ALL")),
        })

    execute_batch(cursor, query, records, page_size=1000)
    conn.commit()
    cursor.close()
    logger.info(f"Successfully inserted {len(records)} rows in skill_rules.")
    return len(records)


def load_job_clusters(
    conn: Any,
    parquet_path: Path,
    dry_run: bool = False
) -> int:
    """Load job clusters and PCA 2D/3D coordinates into job_clusters table."""
    if not parquet_path.exists():
        logger.warning(f"File job clusters not found: {parquet_path}")
        return 0

    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas is required to read parquet files.")
        return 0

    logger.info(f"Reading {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    logger.info(f"Loaded {len(df)} cluster points from {parquet_path.name}.")

    if dry_run:
        logger.info(f"[DRY-RUN] Would insert/update {len(df)} records into job_clusters.")
        return len(df)

    import psycopg2
    from psycopg2.extras import execute_batch

    cursor = conn.cursor()
    query = """
    INSERT INTO job_clusters (
        job_id, job_title, job_family, cluster_id, cluster_name,
        pca_x, pca_y, pca_z, is_outlier, glosh_outlier_score, updated_at
    ) VALUES (
        %(job_id)s, %(job_title)s, %(job_family)s, %(cluster_id)s, %(cluster_name)s,
        %(pca_x)s, %(pca_y)s, %(pca_z)s, %(is_outlier)s, %(glosh_outlier_score)s, CURRENT_TIMESTAMP
    )
    ON CONFLICT (job_id) DO UPDATE SET
        cluster_id = EXCLUDED.cluster_id,
        cluster_name = EXCLUDED.cluster_name,
        pca_x = EXCLUDED.pca_x,
        pca_y = EXCLUDED.pca_y,
        pca_z = EXCLUDED.pca_z,
        is_outlier = EXCLUDED.is_outlier,
        glosh_outlier_score = EXCLUDED.glosh_outlier_score,
        updated_at = CURRENT_TIMESTAMP;
    """

    records = []
    for _, row in df.iterrows():
        records.append({
            "job_id": str(row.get("job_id", "")),
            "job_title": row.get("job_title"),
            "job_family": row.get("job_family"),
            "cluster_id": int(row.get("cluster_id", 0)),
            "cluster_name": row.get("cluster_name"),
            "pca_x": float(row.get("pca_x", 0.0)),
            "pca_y": float(row.get("pca_y", 0.0)),
            "pca_z": float(row["pca_z"]) if pd.notnull(row.get("pca_z")) else None,
            "is_outlier": bool(row.get("is_outlier", False)),
            "glosh_outlier_score": float(row["glosh_outlier_score"]) if pd.notnull(row.get("glosh_outlier_score")) else None,
        })

    execute_batch(cursor, query, records, page_size=1000)
    conn.commit()
    cursor.close()
    logger.info(f"Successfully inserted/updated {len(records)} rows in job_clusters.")
    return len(records)


def load_job_anomalies(
    conn: Any,
    parquet_path: Path,
    dry_run: bool = False
) -> int:
    """Load job anomalies into job_anomalies table."""
    if not parquet_path.exists():
        logger.warning(f"File job anomalies not found: {parquet_path}")
        return 0

    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas is required to read parquet files.")
        return 0

    logger.info(f"Reading {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    logger.info(f"Loaded {len(df)} anomalies from {parquet_path.name}.")

    if dry_run:
        logger.info(f"[DRY-RUN] Would insert {len(df)} records into job_anomalies.")
        return len(df)

    import psycopg2
    from psycopg2.extras import execute_batch

    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE job_anomalies RESTART IDENTITY;")

    query = """
    INSERT INTO job_anomalies (
        job_id, job_title, company_name, anomaly_score, reason_code, detected_by
    ) VALUES (
        %(job_id)s, %(job_title)s, %(company_name)s, %(anomaly_score)s, %(reason_code)s, %(detected_by)s
    );
    """

    records = []
    for _, row in df.iterrows():
        records.append({
            "job_id": str(row.get("job_id", "")),
            "job_title": row.get("job_title"),
            "company_name": row.get("company_name"),
            "anomaly_score": float(row.get("anomaly_score", 0.0)),
            "reason_code": str(row.get("reason_code", "UNKNOWN")),
            "detected_by": str(row.get("detected_by", "IsolationForest")),
        })

    execute_batch(cursor, query, records, page_size=1000)
    conn.commit()
    cursor.close()
    logger.info(f"Successfully inserted {len(records)} rows in job_anomalies.")
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load Golden Parquet and Mining Artifacts into PostgreSQL Mart.")
    parser.add_argument("--curated-path", type=str, default="data/curated/curated_flat_golden_jobs.parquet", help="Path to golden jobs parquet")
    parser.add_argument("--mining-dir", type=str, default="mining/artifacts", help="Directory containing mining parquet artifacts")
    parser.add_argument("--tables", type=str, default="all", help="Comma-separated tables to load: curated_jobs,skill_rules,job_clusters,job_anomalies,all")
    parser.add_argument("--dry-run", action="store_true", help="Inspect files without writing to DB")
    parser.add_argument("--host", type=str, help="PostgreSQL host")
    parser.add_argument("--port", type=int, help="PostgreSQL port")
    parser.add_argument("--db", type=str, help="PostgreSQL database name")
    parser.add_argument("--user", type=str, help="PostgreSQL user")
    parser.add_argument("--password", type=str, help="PostgreSQL password")

    args = parser.parse_args()

    curated_path = Path(args.curated_path)
    mining_dir = Path(args.mining_dir)
    target_tables = [t.strip() for t in args.tables.split(",")] if args.tables != "all" else ["curated_jobs", "skill_rules", "job_clusters", "job_anomalies"]

    logger.info(f"Target tables to load: {target_tables}")
    logger.info(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE LOAD'}")

    conn = None
    if not args.dry_run:
        try:
            import psycopg2
            params = get_db_connection_params(args)
            logger.info(f"Connecting to PostgreSQL at {params['host']}:{params['port']}, DB: {params['dbname']}...")
            conn = psycopg2.connect(**params)
            logger.info("Connected successfully.")
        except Exception as e:
            logger.error(f"Cannot connect to PostgreSQL: {e}")
            logger.info("Hint: Make sure 'docker compose up -d postgres' is running.")
            return 1

    try:
        if "curated_jobs" in target_tables:
            load_curated_jobs(conn, curated_path, dry_run=args.dry_run)

        if "skill_rules" in target_tables:
            rules_path = mining_dir / "skill_association_rules.parquet"
            load_skill_rules(conn, rules_path, dry_run=args.dry_run)

        if "job_clusters" in target_tables:
            clusters_path = mining_dir / "job_clusters.parquet"
            load_job_clusters(conn, clusters_path, dry_run=args.dry_run)

        if "job_anomalies" in target_tables:
            anomalies_path = mining_dir / "job_anomalies.parquet"
            load_job_anomalies(conn, anomalies_path, dry_run=args.dry_run)

    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed.")

    logger.info("Load process completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
