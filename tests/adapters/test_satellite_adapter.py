# -*- coding: utf-8 -*-
"""
SatelliteAdapter 单元测试 — 纯 mock requests，无真实网络
Input: mock _get_json 返回
Output: pytest 用例结果
Pos: tests/adapters 层，CI 回归保护 (P3-D1 [NEW-FILE:#20260415-24])
"""
from unittest.mock import patch

import pandas as pd
import pytest

from app.adapters.satellite_adapter import SatelliteAdapter


@pytest.fixture
def adapter():
    return SatelliteAdapter()


# ---------- name & BaseAdapter 抽象 ----------

def test_name_is_satellite(adapter):
    assert adapter.name == "satellite"


def test_stock_methods_return_empty_defaults(adapter):
    assert adapter.get_stock_history("600000", "20250101", "20260101").empty
    assert adapter.get_index_stocks("000300") == []
    assert adapter.get_stock_info("600000") == {}
    assert adapter.get_financial_data("600000") == {}


# ---------- search_datasets ----------

def test_search_datasets_parses_entries(adapter):
    fake = {
        "feed": {
            "entry": [
                {
                    "id": "C1711961296-LPCLOUD",
                    "short_name": "HLSL30",
                    "version_id": "2.0",
                    "title": "HLS Landsat 30m",
                    "summary": "Harmonized Landsat Sentinel-2",
                    "data_center": "LPCLOUD",
                    "time_start": "2013-04-11T00:00:00Z",
                    "time_end": "2026-04-15T00:00:00Z",
                    "links": [{"href": "https://lpdaac.usgs.gov/"}],
                },
                {
                    "id": "C2021957657-LPCLOUD",
                    "short_name": "HLSS30",
                    "version_id": "2.0",
                    "title": "HLS Sentinel-2 30m",
                    "summary": "Harmonized",
                    "data_center": "LPCLOUD",
                    "time_start": "2015-06-27T00:00:00Z",
                    "time_end": "2026-04-15T00:00:00Z",
                    "links": [],
                },
            ]
        }
    }
    with patch.object(adapter, "_get_json", return_value=fake):
        out = adapter.search_datasets("landsat", bbox=(100, 20, 130, 45),
                                      start="2025-01-01T00:00:00Z",
                                      end="2026-04-15T00:00:00Z")
    assert len(out) == 2
    assert out[0]["id"] == "C1711961296-LPCLOUD"
    assert out[0]["short_name"] == "HLSL30"
    assert out[1]["data_center"] == "LPCLOUD"


def test_search_datasets_empty_response(adapter):
    with patch.object(adapter, "_get_json", return_value=None):
        assert adapter.search_datasets("ndvi") == []


def test_search_datasets_no_entries(adapter):
    with patch.object(adapter, "_get_json", return_value={"feed": {"entry": []}}):
        assert adapter.search_datasets("xxx") == []


# ---------- get_collection_metadata ----------

def test_get_collection_metadata_parses_umm(adapter):
    fake = {
        "items": [
            {
                "umm": {
                    "ShortName": "HLSL30",
                    "Version": "2.0",
                    "EntryTitle": "HLS Landsat 30m",
                    "Abstract": "Harmonized Landsat data product",
                    "DataCenters": [{"ShortName": "LPCLOUD"}],
                    "Platforms": [{"ShortName": "LANDSAT-8"}],
                    "ProcessingLevel": {"Id": "L2"},
                    "TemporalExtents": [{"RangeDateTimes": []}],
                    "SpatialExtent": {"HorizontalSpatialDomain": {}},
                    "RelatedUrls": [{"URL": "https://lpdaac.usgs.gov/"}],
                }
            }
        ]
    }
    with patch.object(adapter, "_get_json", return_value=fake):
        meta = adapter.get_collection_metadata("C1711961296-LPCLOUD")
    assert meta["short_name"] == "HLSL30"
    assert meta["version"] == "2.0"
    assert meta["processing_level"] == "L2"
    assert "LPCLOUD" in meta["data_center"]
    assert "LANDSAT-8" in meta["platforms"]


def test_get_collection_metadata_empty_id(adapter):
    assert adapter.get_collection_metadata("") == {}


def test_get_collection_metadata_fail(adapter):
    with patch.object(adapter, "_get_json", return_value=None):
        assert adapter.get_collection_metadata("C12345") == {}


def test_get_collection_metadata_no_items(adapter):
    with patch.object(adapter, "_get_json", return_value={"items": []}):
        assert adapter.get_collection_metadata("C12345") == {}


# ---------- search_granules ----------

def test_search_granules_parses_entries(adapter):
    fake = {
        "feed": {
            "entry": [
                {
                    "id": "G2021957657-LPCLOUD",
                    "title": "HLS.L30.T50SMG.2026104T025731.v2.0",
                    "time_start": "2026-04-14T02:57:31Z",
                    "time_end": "2026-04-14T02:58:00Z",
                    "links": [
                        {"rel": "http://esipfed.org/ns/fedsearch/1.1/data#",
                         "href": "https://data.lpdaac.earthdatacloud.nasa.gov/x.tif"}
                    ],
                }
            ]
        }
    }
    with patch.object(adapter, "_get_json", return_value=fake):
        df = adapter.search_granules("C1711961296-LPCLOUD")
    assert len(df) == 1
    assert df.iloc[0]["granule_id"] == "G2021957657-LPCLOUD"
    assert df.iloc[0]["download_url"].endswith(".tif")


def test_search_granules_empty_collection_id(adapter):
    assert adapter.search_granules("").empty


# ---------- health_check & token ----------

def test_health_check_pass(adapter):
    with patch.object(adapter, "_get_json",
                      return_value={"feed": {"entry": [{"id": "C1"}]}}):
        assert adapter.health_check() is True


def test_health_check_fail(adapter):
    with patch.object(adapter, "_get_json", return_value=None):
        assert adapter.health_check() is False


def test_edl_token_added_as_bearer():
    a = SatelliteAdapter(edl_token="abc123")
    assert a._session.headers.get("Authorization") == "Bearer abc123"
