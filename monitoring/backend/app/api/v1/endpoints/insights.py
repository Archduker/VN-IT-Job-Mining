"""Analytics Mart HTTP contract."""

import psycopg2
from app.services import insights_service as service
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


def run(function, *args):
    try:
        return function(*args)
    except psycopg2.Error as exc:
        # Connection strings and SQL error details may contain sensitive data.
        raise HTTPException(503, detail={"reason": "MART_UNAVAILABLE"}) from exc


@router.get("/salary-heatmap")
def salary(city: str | None = None, level: str | None = None, job_family: str | None = None):
    return run(service.salary, city, level, job_family)


@router.get("/skill-combos")
def combos(
    min_support: float = Query(0.02, ge=0, le=1),
    min_confidence: float = Query(0.5, ge=0, le=1),
    min_lift: float = Query(1.2, ge=0),
    job_family_scope: str = "ALL",
    antecedent: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
):
    return run(
        service.combos, min_support, min_confidence, min_lift, job_family_scope, antecedent, limit
    )


@router.get("/clusters")
def clusters(city: str | None = None, level: str | None = None, job_family: str | None = None):
    return run(service.clusters, city, level, job_family)


@router.get("/filters/options")
def options():
    return run(service.options)
