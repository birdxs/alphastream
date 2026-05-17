# Input  : IndexIndustryAnalyzer 单元测试，mock data_provider + 内置 analyzer
# Output : pytest 用例（实例化/指数/行业/比较/边界）
# Pos    : tests/backend/unit/test_analysis_index_industry.py - BE-06c 第 2/5
"""BE-06c #2: IndexIndustryAnalyzer 单元测试。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.analysis.index_industry_analyzer import IndexIndustryAnalyzer


@pytest.fixture
def fake_base_analyzer():
    """伪造 StockAnalyzer.quick_analyze_stock 行为。"""
    base = MagicMock()
    base.quick_analyze_stock.side_effect = lambda code: {
        "stock_code": code,
        "score": 70 if code.endswith("1") else 55,
        "price_change": 1.5 if code.endswith("1") else -0.5,
    }
    return base


@pytest.fixture
def analyzer(fake_base_analyzer):
    inst = IndexIndustryAnalyzer(fake_base_analyzer)
    # 用 MagicMock 替换 data_provider 摆脱真实数据层
    inst.data_provider = MagicMock()
    return inst


def test_instantiate(analyzer, fake_base_analyzer):
    """用例 1：实例化（包含 data_provider 和 analyzer 引用）。"""
    assert analyzer.analyzer is fake_base_analyzer
    assert isinstance(analyzer.data_cache, dict)
    assert analyzer.data_provider is not None


def test_analyze_index_success(analyzer):
    """用例 2：分析指数 - mock 成分股列表。"""
    analyzer.data_provider.get_index_stocks.return_value = ["000001", "000002", "000003"]
    result = analyzer.analyze_index("000300", limit=3)
    assert "error" not in result
    assert result["index_code"] == "000300"
    assert result["index_name"] == "沪深300"
    assert result["stock_count"] == 3
    # 分布统计
    assert result["up_count"] + result["down_count"] + result["flat_count"] == 3


def test_analyze_index_unsupported_code(analyzer):
    """用例 3：不支持的指数代码 - 返回 error。"""
    result = analyzer.analyze_index("999999")
    assert "error" in result


def test_analyze_index_empty_stocks(analyzer):
    """用例 4：边界 - 成分股为空。"""
    analyzer.data_provider.get_index_stocks.return_value = []
    result = analyzer.analyze_index("000300")
    assert "error" in result


def test_analyze_industry_success(analyzer):
    """用例 5：分析行业 - mock 行业成分股。"""
    analyzer.data_provider.get_industry_stocks.return_value = ["000011", "000022"]
    result = analyzer.analyze_industry("半导体", limit=5)
    assert "error" not in result
    assert result["industry"] == "半导体"
    assert result["stock_count"] == 2


def test_analyze_industry_empty(analyzer):
    """用例 6：边界 - 行业成分股为空。"""
    analyzer.data_provider.get_industry_stocks.return_value = []
    result = analyzer.analyze_industry("不存在的行业")
    assert "error" in result


def test_analyze_index_cache_hit(analyzer):
    """用例 7：缓存命中。"""
    analyzer.data_provider.get_index_stocks.return_value = ["000001"]
    analyzer.analyze_index("000300", limit=1)
    # 第二次走缓存：清空 data_provider mock 后仍应正常返回
    analyzer.data_provider.get_index_stocks.reset_mock()
    res2 = analyzer.analyze_index("000300", limit=1)
    assert "error" not in res2
    analyzer.data_provider.get_index_stocks.assert_not_called()


def test_compare_industries_basic(analyzer):
    """用例 8：比较行业 - mock industry list + analyze_industry。"""
    analyzer.data_provider.get_industry_list.return_value = pd.DataFrame(
        {"板块名称": ["半导体", "白酒"], "板块代码": ["BK0001", "BK0002"]}
    )
    # 直接 patch analyze_industry 以避免深层调用
    with patch.object(
        analyzer,
        "analyze_industry",
        side_effect=[
            {"industry": "半导体", "score": 80, "up_ratio": 0.7, "avg_change": 1.5,
             "stock_count": 5},
            {"industry": "白酒", "score": 50, "up_ratio": 0.4, "avg_change": -0.5,
             "stock_count": 4},
        ],
    ):
        result = analyzer.compare_industries(limit=2)
    assert isinstance(result, (list, dict))
