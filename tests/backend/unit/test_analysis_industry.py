# Input  : IndustryAnalyzer 单元测试，全程 mock akshare/外部 IO
# Output : pytest 用例（实例化/资金流向/评分/建议/边界）
# Pos    : tests/backend/unit/test_analysis_industry.py - BE-06c 第 1/5
"""BE-06c #1: IndustryAnalyzer 单元测试。"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from app.analysis.industry_analyzer import IndustryAnalyzer


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def analyzer() -> IndustryAnalyzer:
    return IndustryAnalyzer()


@pytest.fixture
def fund_flow_df() -> pd.DataFrame:
    """模拟 ak.stock_fund_flow_industry(symbol='即时') 返回。"""
    return pd.DataFrame(
        {
            "序号": [1, 2, 3],
            "行业": ["半导体", "白酒", "新能源"],
            "行业指数": [1500.5, 2300.1, 980.3],
            "行业-涨跌幅": ["1.2%", "-0.5%", "2.8%"],
            "流入资金": [3.5e8, 1.2e8, 5.6e8],
            "流出资金": [2.0e8, 1.4e8, 2.4e8],
            "净额": [1.5e8, -2.0e7, 3.2e8],
            "公司家数": [50, 20, 60],
        }
    )


# --------------------------------------------------------------------------- #
# Cases
# --------------------------------------------------------------------------- #
def test_instantiate(analyzer):
    """用例 1：实例化。"""
    assert analyzer is not None
    assert isinstance(analyzer.data_cache, dict)
    assert isinstance(analyzer.industry_code_map, dict)
    assert hasattr(analyzer, "data_provider")


def test_safe_helpers(analyzer):
    """用例 2：安全转换辅助方法。"""
    assert analyzer._safe_float("3.14") == 3.14
    assert analyzer._safe_float("--") == 0.0
    assert analyzer._safe_int("42") == 42
    assert analyzer._safe_int("xx") == 0
    # _safe_percent 返回字符串（实现）
    assert analyzer._safe_percent("5.5%") == "5.5"
    assert analyzer._safe_percent("--") == "0.00"


def test_get_industry_fund_flow_ok(analyzer, fund_flow_df):
    """用例 3：行业资金流向 - mock akshare 返回 DataFrame。"""
    with patch("app.analysis.industry_analyzer.ak.stock_fund_flow_industry",
               return_value=fund_flow_df):
        result = analyzer.get_industry_fund_flow(symbol="即时")
    assert isinstance(result, list)
    assert len(result) == 3
    assert {item["industry"] for item in result} == {"半导体", "白酒", "新能源"}
    semi = next(x for x in result if x["industry"] == "半导体")
    assert semi["change"] == "1.2"
    assert semi["netFlow"] == pytest.approx(1.5e8)


def test_get_industry_fund_flow_empty(analyzer):
    """用例 4：边界 - 空 DataFrame。"""
    with patch("app.analysis.industry_analyzer.ak.stock_fund_flow_industry",
               return_value=pd.DataFrame()):
        result = analyzer.get_industry_fund_flow()
    assert result == []


def test_get_industry_fund_flow_exception(analyzer):
    """用例 5：边界 - akshare 抛异常返回 []。"""
    with patch("app.analysis.industry_analyzer.ak.stock_fund_flow_industry",
               side_effect=RuntimeError("net error")):
        result = analyzer.get_industry_fund_flow()
    assert result == []


def test_get_industry_fund_flow_cache_hit(analyzer, fund_flow_df):
    """用例 6：缓存命中分支 - 第二次调用直接走缓存。"""
    with patch("app.analysis.industry_analyzer.ak.stock_fund_flow_industry",
               return_value=fund_flow_df) as p:
        analyzer.get_industry_fund_flow(symbol="即时")
        analyzer.get_industry_fund_flow(symbol="即时")
    # 第二次应该走缓存，akshare 只被调用一次
    assert p.call_count == 1


def test_calculate_industry_score_positive(analyzer):
    """用例 7：行业评分（涨幅 + 主力净流入）。"""
    score = analyzer.calculate_industry_score(
        {"change": 2.0, "netFlow": 3.0}, []
    )
    assert isinstance(score, (int, float))
    assert score >= 50


def test_calculate_industry_score_negative(analyzer):
    """用例 8：评分（下跌 + 资金流出）。"""
    score = analyzer.calculate_industry_score(
        {"change": -4.0, "netFlow": -6.0}, []
    )
    assert score < 50


def test_calculate_industry_score_exception(analyzer):
    """用例 9：异常分支默认 50。"""
    score = analyzer.calculate_industry_score({"change": "bad"}, [])
    assert score == 50


def test_generate_industry_recommendation_levels(analyzer):
    """用例 10：根据分数生成不同建议。"""
    rec_high = analyzer.generate_industry_recommendation(85, {}, [])
    rec_mid = analyzer.generate_industry_recommendation(50, {}, [])
    rec_low = analyzer.generate_industry_recommendation(15, {}, [])
    assert isinstance(rec_high, str)
    assert rec_high != rec_low
    assert rec_mid != rec_high


def test_get_industry_code_mapping(analyzer):
    """用例 11：行业代码映射 - 已知与未知。"""
    # 已知映射（如有）
    known = analyzer._get_industry_code("半导体")
    assert known is None or isinstance(known, str)
    # 未知
    assert analyzer._get_industry_code("不存在的行业9X") is None


def test_get_industry_stocks_fallback_mock(analyzer):
    """用例 12：data_provider 返回空 → 金融铁律：返回空列表，禁止 mock 伪造数据。"""
    analyzer.data_provider = MagicMock()
    analyzer.data_provider.get_industry_stocks.return_value = []
    # 同时让 get_industry_fund_flow 走缓存（直接预置 data_cache）
    from datetime import datetime as _dt
    analyzer.data_cache["fund_flow_即时"] = (
        _dt.now(),
        [{"industry": "半导体", "companyCount": 5}],
    )
    result = analyzer.get_industry_stocks("半导体")
    # 金融铁律：数据未到位返回空列表，不允许 mock 伪造股票代码/价格
    assert isinstance(result, list)
    assert len(result) == 0


def test_get_industry_stocks_cache(analyzer):
    """用例 13：成分股缓存命中。"""
    from datetime import datetime as _dt
    cached = [{"code": "000001", "name": "X", "price": 10.0, "change": 0.5}]
    analyzer.data_cache["industry_stocks_半导体"] = (_dt.now(), cached)
    result = analyzer.get_industry_stocks("半导体")
    assert result == cached


def test_get_industry_detail_not_found(analyzer):
    """用例 14：行业详情 - 未找到对应行业返回 None。"""
    from unittest.mock import patch as _patch
    with _patch.object(analyzer, "get_industry_fund_flow", return_value=[]):
        out = analyzer.get_industry_detail("不存在")
    assert out is None


def test_get_industry_detail_basic(analyzer):
    """用例 15：行业详情成功路径（mock get_industry_fund_flow）。"""
    from unittest.mock import patch as _patch
    base_item = {
        "industry": "半导体", "index": 1500.0, "change": "1.5",
        "companyCount": 50, "inflow": 3.5e8, "outflow": 2.0e8,
        "netFlow": 1.5e8, "leadingStock": "X", "leadingStockChange": "2",
        "leadingStockPrice": 10.0,
    }
    with _patch.object(analyzer, "get_industry_fund_flow",
                       return_value=[base_item]):
        out = analyzer.get_industry_detail("半导体")
    assert out is not None
    assert out["industry"] == "半导体"
    assert "score" in out
    assert "recommendation" in out
    assert "flowHistory" in out


def test_compare_industries_empty(analyzer):
    """用例 16：比较行业 - data_provider 返回空 DataFrame。"""
    analyzer.data_provider = MagicMock()
    analyzer.data_provider.get_industry_list.return_value = pd.DataFrame()
    out = analyzer.compare_industries(limit=5)
    assert "error" in out


def test_compare_industries_with_data(analyzer):
    """用例 17：比较行业 - mock 历史数据返回。"""
    analyzer.data_provider = MagicMock()
    analyzer.data_provider.get_industry_list.return_value = pd.DataFrame(
        {"板块名称": ["半导体", "白酒"], "板块代码": ["BK0001", "BK0002"]}
    )
    hist_df = pd.DataFrame(
        [{"涨跌幅": 2.0, "成交量": 1e7, "成交额": 1e9}]
    )
    with patch(
        "app.analysis.industry_analyzer.ak.stock_board_industry_hist_em",
        return_value=hist_df,
    ):
        out = analyzer.compare_industries(limit=2)
    assert "results" in out
    assert out["count"] == 2
