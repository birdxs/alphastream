# -*- coding: utf-8 -*-
"""
IMF 适配器单元测试（纯 mock，无真实网络请求）
Input: mock 的 requests.Session.get 响应（SDMX-JSON CompactData）
Output: pytest 用例结果
Pos: tests/adapters 层，CI 回归保护
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.adapters.imf_adapter import IMFAdapter


def _mk_resp(status: int = 200, payload=None) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload if payload is not None else {}
    return m


# 典型 SDMX-JSON：单 Series + 多 Obs
IFS_CN_CPI_PAYLOAD = {
    "CompactData": {
        "DataSet": {
            "Series": {
                "@FREQ": "A",
                "@REF_AREA": "CN",
                "@INDICATOR": "PCPI_IX",
                "@UNIT_MULT": "0",
                "Obs": [
                    {"@TIME_PERIOD": "2020", "@OBS_VALUE": "102.5"},
                    {"@TIME_PERIOD": "2021", "@OBS_VALUE": "103.4"},
                    {"@TIME_PERIOD": "2022", "@OBS_VALUE": "105.6"},
                ],
            }
        }
    }
}

# 多 Series（多国）+ 混合 Obs 形式
IFS_MULTI_PAYLOAD = {
    "CompactData": {
        "DataSet": {
            "Series": [
                {
                    "@FREQ": "A",
                    "@REF_AREA": "CN",
                    "@INDICATOR": "PCPI_IX",
                    "Obs": {"@TIME_PERIOD": "2022", "@OBS_VALUE": "105.6"},
                },
                {
                    "@FREQ": "A",
                    "@REF_AREA": "US",
                    "@INDICATOR": "PCPI_IX",
                    "Obs": [
                        {"@TIME_PERIOD": "2021", "@OBS_VALUE": "270.97"},
                        {"@TIME_PERIOD": "2022", "@OBS_VALUE": "292.66"},
                    ],
                },
            ]
        }
    }
}

EMPTY_PAYLOAD = {"CompactData": {"DataSet": {}}}


class TestBasics:
    def test_name(self):
        assert IMFAdapter().name == "imf"

    def test_session_ua(self):
        a = IMFAdapter()
        assert "StockAnalSys" in a.session.headers.get("User-Agent", "")

    def test_extract_series_empty(self):
        assert IMFAdapter._extract_series(None) == []
        assert IMFAdapter._extract_series({}) == []
        assert IMFAdapter._extract_series(EMPTY_PAYLOAD) == []

    def test_extract_series_dict_to_list(self):
        out = IMFAdapter._extract_series(IFS_CN_CPI_PAYLOAD)
        assert isinstance(out, list) and len(out) == 1
        assert out[0]["@REF_AREA"] == "CN"

    def test_extract_series_list(self):
        out = IMFAdapter._extract_series(IFS_MULTI_PAYLOAD)
        assert len(out) == 2


class TestFlatten:
    def test_flatten_single_series_multi_obs(self):
        series = IMFAdapter._extract_series(IFS_CN_CPI_PAYLOAD)
        df = IMFAdapter._flatten_series(series)
        assert len(df) == 3
        assert set(["freq", "ref_area", "indicator",
                    "period", "value"]).issubset(df.columns)
        assert list(df["period"]) == ["2020", "2021", "2022"]
        assert df["value"].iloc[0] == pytest.approx(102.5)
        assert df["ref_area"].iloc[0] == "CN"

    def test_flatten_mixed_obs_shapes(self):
        series = IMFAdapter._extract_series(IFS_MULTI_PAYLOAD)
        df = IMFAdapter._flatten_series(series)
        # CN 1 条 + US 2 条 = 3
        assert len(df) == 3
        # 排序 by ref_area,indicator,period -> CN(2022), US(2021), US(2022)
        assert list(df["ref_area"]) == ["CN", "US", "US"]

    def test_flatten_missing_value_becomes_none(self):
        payload = {
            "CompactData": {
                "DataSet": {
                    "Series": {
                        "@FREQ": "A", "@REF_AREA": "XX",
                        "@INDICATOR": "TEST",
                        "Obs": [
                            {"@TIME_PERIOD": "2020", "@OBS_VALUE": None},
                            {"@TIME_PERIOD": "2021", "@OBS_VALUE": "notanumber"},
                            {"@TIME_PERIOD": "2022", "@OBS_VALUE": "3.14"},
                        ],
                    }
                }
            }
        }
        df = IMFAdapter._flatten_series(IMFAdapter._extract_series(payload))
        # pandas 将 None/异常值统一转为 NaN（混入数值列后）
        assert pd.isna(df["value"].iloc[0])
        assert pd.isna(df["value"].iloc[1])
        assert df["value"].iloc[2] == pytest.approx(3.14)


class TestEndpoints:
    def test_get_dataset_url_and_params(self):
        a = IMFAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, IFS_CN_CPI_PAYLOAD)) as mg:
            df = a.get_dataset(
                "IFS", "A.CN.PCPI_IX",
                start_period=2020, end_period=2022
            )
            assert len(df) == 3
            url = mg.call_args.args[0]
            assert url == (
                "https://dataservices.imf.org/REST/SDMX_JSON.svc/"
                "CompactData/IFS/A.CN.PCPI_IX"
            )
            params = mg.call_args.kwargs.get("params") or {}
            assert params.get("startPeriod") == "2020"
            assert params.get("endPeriod") == "2022"

    def test_get_ifs_builds_key(self):
        a = IMFAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, IFS_CN_CPI_PAYLOAD)) as mg:
            df = a.get_ifs("PCPI_IX", "CN", freq="A",
                           start_period=2020, end_period=2022)
            assert not df.empty
            url = mg.call_args.args[0]
            assert url.endswith("/CompactData/IFS/A.CN.PCPI_IX")

    def test_get_ifs_empty_input(self):
        a = IMFAdapter()
        assert a.get_ifs("", "CN").empty
        assert a.get_ifs("PCPI_IX", "").empty

    def test_get_dataset_http_error(self):
        a = IMFAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(500, {})):
            df = a.get_dataset("IFS", "A.CN.PCPI_IX")
            assert df.empty

    def test_get_data_structure_url(self):
        a = IMFAdapter()
        payload = {"Structure": {"KeyFamilies": {}}}
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, payload)) as mg:
            out = a.get_data_structure("IFS")
            assert out == payload
            url = mg.call_args.args[0]
            assert url == (
                "https://dataservices.imf.org/REST/SDMX_JSON.svc/"
                "DataStructure/IFS"
            )


class TestBaseAdapterInterface:
    def test_stock_history_empty(self):
        a = IMFAdapter()
        assert a.get_stock_history("CN", "20200101", "20201231").empty

    def test_index_stocks_empty(self):
        assert IMFAdapter().get_index_stocks("IFS") == []

    def test_stock_info_empty(self):
        assert IMFAdapter().get_stock_info("CN") == {}

    def test_financial_data_empty(self):
        assert IMFAdapter().get_financial_data("CN") == {}

    def test_health_check_ok(self):
        a = IMFAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, IFS_CN_CPI_PAYLOAD)):
            assert a.health_check() is True

    def test_health_check_fail(self):
        a = IMFAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(500, {})):
            assert a.health_check() is False
