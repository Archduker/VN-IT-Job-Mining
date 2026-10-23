# -*- coding: utf-8 -*-
"""Unit tests to validate Airflow DAG integrity and configuration."""

import pytest
import sys
from pathlib import Path

plugins_dir = str(Path(__file__).resolve().parents[2] / "airflow" / "plugins")
if plugins_dir not in sys.path:
    sys.path.insert(0, plugins_dir)

from airflow.models import DagBag
from crawler_operators import (
    JobCrawlerOperator,
    DataQualityOperator,
    DataPreprocessOperator,
    AdaptiveRouteCheckOperator,
)

SOURCES = [
    "topdev",
    "vietnamworks",
    "careerviet",
    "vieclam24h",
    "itviec",
    "topcv",
    "jobsgo",
    "glints",
]


@pytest.fixture(scope="module")
def dag_bag():
    """Load DAG bag from airflow/dags directory."""
    from pathlib import Path
    dag_folder = str(Path(__file__).resolve().parents[2] / "airflow" / "dags")
    bag = DagBag(dag_folder=dag_folder, include_examples=False)
    return bag


def test_no_dag_import_errors(dag_bag):
    """Ensure there are no import errors in DAG files."""
    assert len(dag_bag.import_errors) == 0, f"DAG import errors: {dag_bag.import_errors}"


def test_dag_discovery_daily_structure(dag_bag):
    """Verify daily discovery DAG configuration, pool allocation, and max_active_runs."""
    dag = dag_bag.get_dag("dag_discovery_daily")
    assert dag is not None
    assert dag.max_active_runs == 1

    for src in SOURCES:
        task_id = f"discover_{src}"
        task = dag.get_task(task_id)
        assert task is not None
        assert isinstance(task, JobCrawlerOperator)
        assert task.phase == "discover"
        assert task.pool == f"pool_{src}"


def test_detail_dags_pipeline_and_pools(dag_bag):
    """Verify all 8 detail DAGs have the 4-step pipeline, max_items=30, and matching pools."""
    for src in SOURCES:
        dag_id = f"crawler_detail_{src}"
        dag = dag_bag.get_dag(dag_id)
        assert dag is not None, f"DAG {dag_id} not found"
        assert dag.max_active_runs == 1

        # 4 tasks: route_check, crawl, quality, preprocess
        route_task = dag.get_task(f"check_route_{src}")
        crawl_task = dag.get_task(f"crawl_{src}_detail")
        quality_task = dag.get_task(f"check_quality_{src}")
        preprocess_task = dag.get_task(f"preprocess_{src}")

        assert isinstance(route_task, AdaptiveRouteCheckOperator)
        assert isinstance(crawl_task, JobCrawlerOperator)
        assert isinstance(quality_task, DataQualityOperator)
        assert isinstance(preprocess_task, DataPreprocessOperator)

        # Check hard cap: 30 jobs
        assert crawl_task.max_items == 30

        # Check pools
        assert route_task.pool == f"pool_{src}"
        assert crawl_task.pool == f"pool_{src}"
        assert preprocess_task.pool == f"pool_{src}"

        # Check dependency chaining: route >> crawl >> quality >> preprocess
        assert crawl_task in route_task.downstream_list
        assert quality_task in crawl_task.downstream_list
        assert preprocess_task in quality_task.downstream_list
