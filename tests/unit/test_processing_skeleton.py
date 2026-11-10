"""Khung processing/ phải import được; chưa có logic nên chỉ kiểm cấu trúc gói."""
import importlib

import pytest

SUBPACKAGES = ("selection", "extraction", "transformation", "construction", "encoding")


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_importable(name):
    assert importlib.import_module(f"processing.{name}") is not None
