"""Offline contracts for R2 EDA reads; no shared bucket writes."""
import io
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.collection.eda import router
from app.services import eda_r2_service as service


def test_missing_config_is_error_not_empty():
    service._cache.clear()
    with patch.object(service.r2_client, "get_client", return_value=None):
        with pytest.raises(Exception) as error:
            service.dataset("topcv")
        assert error.value.status_code == 503
        assert error.value.detail["reason"] == "R2_NOT_CONFIGURED"


def test_read_closes_body_and_bounds_memory():
    body = io.BytesIO(b"too large")
    client = Mock()
    client.get_object.return_value = {"Body": body, "ContentLength": service.MAX_OBJECT_BYTES + 1}
    with pytest.raises(Exception) as error:
        service._read(client, "raw/test.json")
    assert error.value.status_code == 413
    assert body.closed


def test_r2_route_never_reads_local():
    app = FastAPI()
    app.include_router(router)
    with patch.object(service, "inventory", return_value=[]) as remote, patch(
        "app.services.eda_collection_service.eda_collection_service.get_field_inventory",
        side_effect=AssertionError("Local read forbidden"),
    ):
        response = TestClient(app).get("/topcv/inventory?origin=r2")
    assert response.status_code == 200
    remote.assert_called_once_with("topcv")


def test_origin_validation():
    app = FastAPI()
    app.include_router(router)
    assert TestClient(app).get("/topcv/charts?origin=invalid").status_code == 422


def test_empty_remote_has_no_local_fallback():
    with patch.object(service, "dataset", return_value=([], None)):
        assert service.summary("topcv")["reason"] == "NO_DATA"
        assert service.charts("topcv")["available"] is False
