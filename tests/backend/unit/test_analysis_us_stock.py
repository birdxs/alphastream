# Input  : USStockService 单元测试，mock akshare.stock_us_spot_em
# Output : pytest 用例（实例化/搜索/大小写/无效/异常）
# Pos    : tests/backend/unit/test_analysis_us_stock.py - BE-06c 第 5/5
"""BE-06c #5: USStockService 单元测试。"""
from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from app.analysis.us_stock_service import USStockService


@pytest.fixture
def service() -> USStockService:
    return USStockService()


@pytest.fixture
def us_spot_df() -> pd.DataFrame:
    """模拟 ak.stock_us_spot_em 返回（含中文列名）。"""
    return pd.DataFrame(
        {
            "序号": [1, 2, 3, 4],
            "名称": ["Apple Inc.", "Microsoft Corp.", "Alphabet Inc.", "apple test"],
            "最新价": [195.0, 410.0, 175.0, np.nan],
            "涨跌额": [1.0, -2.0, 0.5, 0.0],
            "涨跌幅": [0.5, -0.4, 0.3, 0.0],
            "开盘价": [194.0, 412.0, 174.5, 0.0],
            "最高价": [196.0, 413.0, 175.5, 0.0],
            "最低价": [193.0, 409.0, 174.0, 0.0],
            "昨收价": [194.0, 412.0, 174.5, 0.0],
            "总市值": [3.0e12, 3.1e12, 2.2e12, np.nan],
            "市盈率": [30.0, 35.0, 25.0, 0.0],
            "成交量": [1e7, 2e7, 1.5e7, 0],
            "成交额": [1e9, 2e9, 1.5e9, 0],
            "振幅": [1.5, 1.0, 0.8, 0.0],
            "换手率": [0.5, 0.3, 0.2, 0.0],
            "代码": ["AAPL", "MSFT", "GOOG", "AAPL.X"],
        }
    )


# --------------------------------------------------------------------------- #
def test_instantiate(service):
    """用例 1：实例化。"""
    assert service is not None
    assert hasattr(service, "logger")


def test_search_match_uppercase(service, us_spot_df):
    """用例 2：关键词大写匹配（case-insensitive）。"""
    with patch("app.analysis.us_stock_service.ak.stock_us_spot_em",
               return_value=us_spot_df):
        result = service.search_us_stocks("APPLE")
    assert isinstance(result, list)
    # 应同时匹配 'Apple Inc.' 和 'apple test'
    names = {r["name"] for r in result}
    assert "Apple Inc." in names
    assert "apple test" in names
    # 字段结构
    apple = next(r for r in result if r["name"] == "Apple Inc.")
    assert apple["symbol"] == "AAPL"
    assert apple["price"] == 195.0
    assert apple["market_value"] == 3.0e12


def test_search_match_lowercase(service, us_spot_df):
    """用例 3：关键词小写匹配。"""
    with patch("app.analysis.us_stock_service.ak.stock_us_spot_em",
               return_value=us_spot_df):
        result = service.search_us_stocks("microsoft")
    assert len(result) == 1
    assert result[0]["symbol"] == "MSFT"


def test_search_nan_handling(service, us_spot_df):
    """用例 4：NaN 字段安全处理（price/market_value 应为 0.0）。"""
    with patch("app.analysis.us_stock_service.ak.stock_us_spot_em",
               return_value=us_spot_df):
        result = service.search_us_stocks("apple test")
    assert len(result) == 1
    assert result[0]["price"] == 0.0
    assert result[0]["market_value"] == 0.0


def test_search_no_match(service, us_spot_df):
    """用例 5：边界 - 无任何匹配。"""
    with patch("app.analysis.us_stock_service.ak.stock_us_spot_em",
               return_value=us_spot_df):
        result = service.search_us_stocks("不存在Z9Z9")
    assert result == []


def test_search_akshare_exception(service):
    """用例 6：边界 - akshare 抛异常被包装为 Exception。"""
    with patch("app.analysis.us_stock_service.ak.stock_us_spot_em",
               side_effect=RuntimeError("network down")):
        with pytest.raises(Exception) as exc:
            service.search_us_stocks("AAPL")
        assert "搜索美股代码失败" in str(exc.value)


def test_search_empty_keyword(service, us_spot_df):
    """用例 7：空关键词 - str.contains('') 返回全部。"""
    with patch("app.analysis.us_stock_service.ak.stock_us_spot_em",
               return_value=us_spot_df):
        result = service.search_us_stocks("")
    assert len(result) == 4
