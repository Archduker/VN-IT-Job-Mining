"""Read-only PostgreSQL analytics queries; never substitute synthetic data."""

import os
from contextlib import closing

import psycopg2
from psycopg2.extras import RealDictCursor


def query(sql, params=()):
    with closing(
        psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            dbname=os.getenv("POSTGRES_DB", "vn_it_jobs"),
            user=os.getenv("POSTGRES_USER", "airflow"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            connect_timeout=3,
            options="-c statement_timeout=5000",
        )
    ) as conn:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]


def result(rows):
    return {
        "status": "OK" if rows else "EMPTY",
        "reason": None if rows else "NO_DATA",
        "data": rows or None,
    }


def predicate(city=None, level=None, job_family=None):
    clauses, values = [], []
    for column, value in (
        ("province_norm", city),
        ("seniority_level", level),
        ("job_family", job_family),
    ):
        if value:
            clauses.append(f"j.{column} = %s")
            values.append(value)
    return (" AND ".join(clauses) or "TRUE"), values


def salary(city=None, level=None, job_family=None):
    where, values = predicate(city, level, job_family)
    valid = (
        "NOT COALESCE(is_salary_negotiable, FALSE) AND salary_avg_vnd BETWEEN 1000000 AND 500000000"
    )
    return result(
        query(
            f"""
        SELECT job_family, seniority_level,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY salary_avg_vnd)
            FILTER (WHERE {valid}) / 1000000 AS median,
        percentile_cont(0.25) WITHIN GROUP (ORDER BY salary_avg_vnd)
            FILTER (WHERE {valid}) / 1000000 AS q25,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY salary_avg_vnd)
            FILTER (WHERE {valid}) / 1000000 AS q75,
        count(*) FILTER (WHERE {valid}) AS sample_count,
        count(*) FILTER (WHERE is_salary_negotiable) AS negotiable_count
        FROM curated_jobs j WHERE {where}
        GROUP BY job_family, seniority_level ORDER BY job_family, seniority_level
    """,
            values,
        )
    )


def combos(min_support, min_confidence, min_lift, scope, antecedent, limit):
    return result(
        query(
            """
        SELECT antecedents, consequents, support, confidence, lift, job_family_scope
        FROM skill_rules WHERE support >= %s AND confidence >= %s AND lift >= %s
        AND job_family_scope = %s AND (%s IS NULL OR %s = ANY(antecedents))
        ORDER BY lift DESC, confidence DESC, id LIMIT %s
    """,
            (min_support, min_confidence, min_lift, scope, antecedent, antecedent, limit),
        )
    )


def clusters(city=None, level=None, job_family=None):
    where, values = predicate(city, level, None)
    if job_family:
        where += " AND COALESCE(c.job_family, j.job_family) = %s"
        values.append(job_family)
    return result(
        query(
            f"""
        SELECT c.*, j.company_name, j.province_norm, j.seniority_level,
        j.salary_avg_vnd, j.source_platform
        FROM job_clusters c LEFT JOIN curated_jobs j ON j.job_id = c.job_id
        WHERE {where} ORDER BY c.job_id
    """,
            values,
        )
    )


def options():
    return result(
        query("""
        SELECT DISTINCT job_family, seniority_level, province_norm FROM curated_jobs
        ORDER BY job_family, seniority_level, province_norm
    """)
    )
