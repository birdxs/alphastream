# -*- coding: utf-8 -*-
# Input  : CapitalFlowAnalyzer + mock akshare/data_provider
# Output : pytest 用例 BE-06a 资金流向分析单元测试
# Pos    : tests/backend/unit/test_analysis_capital_flow.py
"""BE-06a CapitalFlowAnalyzer 单元测试

覆盖：
1. 实例化 + 个股资金流向快乐路径（mock akshare）
2. akshare 失败 → 降级 mock
3. 美股/港股短路 → mock 兜底
4. 边界：空 DataFrame
5. calculate_capital_flow_score 关键计算
6. _parse_percent 工具
7. get_sector_stocks 兜底
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pandas as pd
import pytest


# -- fixture ------------------------------------------------------------------
@pytest.fixture
def analyzer():
    with patch("app.core.data_provider.get_data_provider", return_value=MagicMock()):
        from app.analysis.capital_flow_analyzer import CapitalFlowAnalyzer
        return CapitalFlowAnalyzer()


def _mock_flow_df(rows=10):
    """构造 akshare stock_individual_fund_flow 返回的 DataFrame"""
    data = []
    for i in range(rows):
        data.append({
            "日期": f"2026-04-{i+1:02d}",
            "收盘价": 10.0 + i * 0.1,
            "涨跌幅": 1.0 if i % 2 == 0 else -0.5,
            "主力净流入-净额": 1_000_000 if i % 2 == 0 else -500_000,
            "主力净流入-净占比": 5.0 if i % 2 == 0 else -2.0,
            "超大单净流入-净额": 800_000 if i % 2 == 0 else -300_000,
            "超大单净流入-净占比": 4.0,
            "大单净流入-净额": 200_000,
            "大单净流入-净占比": 1.5,
            "中单净流入-净额": -100_000,
            "中单净流入-净占比": -0.5,
            "小单净流入-净额": -50_000,
            "小单净流入-净占比": -0.3,
        })
    return pd.DataFrame(data)


# ---------------------------------------------------------------- 1. 快乐路径
def test_individual_fund_flow_happy_path(analyzer):
    df = _mock_flow_df(10)
    with patch("app.analysis.capital_flow_analyzer.ak.stock_individual_fund_flow",
               return_value=df):
        result = analyzer.get_individual_fund_flow("600519", market_type="A")

    assert result["stock_code"] == "600519"
    assert result["amount_unit"] == "yuan"
    assert len(result["data"]) == 10
    assert result["data"][0]["main_net_inflow"] == 1_000_000
    assert "summary" in result
    assert result["summary"]["recent_days"] == 10
    assert result["summary"]["positive_days"] == 5
    assert result["summary"]["negative_days"] == 5
    assert result["summary"]["total_main_net_inflow"] == 2_500_000
    assert result["summary"]["amount_unit"] == "yuan"


# ---------------------------------------------------------------- 2. akshare 抛异常 → 降级空数据（金融铁律：禁止 mock）
def test_individual_fund_flow_akshare_exception_fallback(analyzer):
    with patch("app.analysis.capital_flow_analyzer.ak.stock_individual_fund_flow",
               side_effect=Exception("akshare 网络异常")):
        result = analyzer.get_individual_fund_flow("600519", market_type="A")

    # 金融铁律：降级必须返回空数据 + degraded 标记，不允许伪造
    assert "data" in result
    assert isinstance(result["data"], list)
    assert len(result["data"]) == 0
    assert result.get("source") == "degraded"
    assert result.get("amount_unit") == "yuan"


# ---------------------------------------------------------------- 3. 美股短路（金融铁律：不支持市场返回 unsupported，禁止 mock）
def test_individual_fund_flow_us_market_short_circuit(analyzer):
    # 即便 akshare 仍可调用，US 应走短路，不应调用 akshare
    with patch("app.analysis.capital_flow_analyzer.ak.stock_individual_fund_flow") as mock_ak:
        result = analyzer.get_individual_fund_flow("AAPL", market_type="US")
    mock_ak.assert_not_called()
    assert result.get("data") == []
    assert result.get("source") == "unsupported"
    assert result.get("amount_unit") == "yuan"


# ---------------------------------------------------------------- 4. 空 DataFrame → 降级空数据（金融铁律：禁止 mock）
def test_individual_fund_flow_empty_df_fallback(analyzer):
    with patch("app.analysis.capital_flow_analyzer.ak.stock_individual_fund_flow",
               return_value=pd.DataFrame()):
        result = analyzer.get_individual_fund_flow("000001", market_type="A")
    assert result.get("data") == []
    assert result.get("source") == "degraded"
    assert result.get("amount_unit") == "yuan"


# ---------------------------------------------------------------- 5. 计算评分
def test_calculate_capital_flow_score_full_inflow(analyzer):
    """全部正向流入 → 评分应较高"""
    df = _mock_flow_df(10)
    # 把所有行都改成强正向流入
    df["主力净流入-净额"] = 2_000_000
    df["主力净流入-净占比"] = 5.0
    df["超大单净流入-净额"] = 1_500_000
    df["大单净流入-净额"] = 500_000
    df["中单净流入-净额"] = 300_000
    df["小单净流入-净额"] = 200_000

    with patch("app.analysis.capital_flow_analyzer.ak.stock_individual_fund_flow",
               return_value=df):
        score = analyzer.calculate_capital_flow_score("600519", market_type="A")

    assert score["total"] > 50  # 评分应明显偏高
    assert score["main_force"] >= 30
    assert "details" in score


def test_calculate_capital_flow_score_no_data_returns_zero(analyzer):
    """无数据时返回 0 分结构"""
    # mock get_individual_fund_flow 直接返回空 dict
    with patch.object(analyzer, "get_individual_fund_flow", return_value={}):
        score = analyzer.calculate_capital_flow_score("999999")
    assert score["total"] == 0
    assert score["main_force"] == 0
    assert score["large_order"] == 0
    assert score["small_order"] == 0


# ---------------------------------------------------------------- 6. _parse_percent
def test_parse_percent_handles_various_formats(analyzer):
    assert analyzer._parse_percent("5.5%") == 5.5
    assert analyzer._parse_percent("-3.2%") == -3.2
    assert analyzer._parse_percent(1.23) == 1.23
    assert analyzer._parse_percent("invalid") == 0  # 失败兜底


# ---------------------------------------------------------------- 7. get_sector_stocks 兜底
def test_get_sector_stocks_dataprovider_exception_returns_empty(analyzer):
    analyzer.data_provider.get_concept_stocks_detail = MagicMock(
        side_effect=Exception("provider 异常"))
    result = analyzer.get_sector_stocks("半导体")
    assert result == []


# ---------------------------------------------------------------- 8. get_concept_fund_flow
def test_get_concept_fund_flow_happy_path(analyzer):
    df = pd.DataFrame([{
        "序号": 1, "行业": "半导体", "公司家数": 50, "行业指数": 1000.5,
        "阶段涨跌幅": "5.5%", "流入资金": 1e9, "流出资金": 8e8, "净额": 2e8,
    }])
    with patch("app.analysis.capital_flow_analyzer.ak.stock_fund_flow_concept",
               return_value=df):
        result = analyzer.get_concept_fund_flow(period="10日排行")
    assert len(result) == 1
    assert result[0]["sector"] == "半导体"
    assert result[0]["change_percent"] == 5.5


def test_get_concept_fund_flow_exception_returns_mock(analyzer):
    with patch("app.analysis.capital_flow_analyzer.ak.stock_fund_flow_concept",
               side_effect=Exception("net err")):
        result = analyzer.get_concept_fund_flow(period="10日排行")
    # 金融铁律：异常降级返回空数据 + degraded 标记，禁止 mock 伪造数据
    assert isinstance(result, dict)
    assert result.get("data") == []
    assert result.get("source") == "degraded"


# ---------------------------------------------------------------- 9. get_individual_fund_flow_rank（H2-4 统一返回契约）
def test_get_individual_fund_flow_rank_exception_returns_mock(analyzer):
    with patch("app.analysis.capital_flow_analyzer.ak.stock_individual_fund_flow_rank",
               side_effect=Exception("net err")):
        result = analyzer.get_individual_fund_flow_rank(period="10日")
    # H2-4 统一契约：异常 → {'data': [], 'error': str, 'count': 0, 'amount_unit': 'yuan'}
    assert isinstance(result, dict)
    assert result.get("data") == []
    assert result.get("count") == 0
    assert result.get("amount_unit") == "yuan"
    assert result.get("error") is not None and isinstance(result["error"], str)


# ---------------------------------------------------------------- 10. 沪市/深市 market_type 推导
def test_individual_fund_flow_sh_code_routing(analyzer):
    df = _mock_flow_df(5)
    with patch("app.analysis.capital_flow_analyzer.ak.stock_individual_fund_flow",
               return_value=df) as mock_ak:
        analyzer.get_individual_fund_flow("600000", market_type="A")
        # 应自动推导为 sh
        args, kwargs = mock_ak.call_args
        assert "sh" in str(args) + str(kwargs) or kwargs.get("market") == "sh"


def test_individual_fund_flow_sz_code_routing(analyzer):
    df = _mock_flow_df(5)
    with patch("app.analysis.capital_flow_analyzer.ak.stock_individual_fund_flow",
               return_value=df) as mock_ak:
        analyzer.get_individual_fund_flow("000001", market_type="A")
        args, kwargs = mock_ak.call_args
        assert "sz" in str(args) + str(kwargs) or kwargs.get("market") == "sz"


# ================================================================ Sprint 3-N 新增测试（H2-4 统一返回契约）
# [NEW-FILE:#20260520-S3N] 追加至现有文件

# ---------------------------------------------------------------- S3-N4 成功路径返回 unified schema
def test_fund_flow_rank_success_returns_unified_schema(analyzer):
    """H2-4：成功路径应返回 {'data': list, 'error': None, 'count': int, 'amount_unit': 'yuan'}"""
    import pandas as pd
    # 构造最小可用 DataFrame
    mock_df = pd.DataFrame([{
        "序号": 1,
        "代码": "600519",
        "名称": "贵州茅台",
        "最新价": 1800.0,
        "10日涨跌幅": 2.5,
        "10日主力净流入-净额": 1000000.0,
        "10日主力净流入-净占比": 0.5,
        "10日超大单净流入-净额": 500000.0,
        "10日超大单净流入-净占比": 0.25,
        "10日大单净流入-净额": 300000.0,
        "10日大单净流入-净占比": 0.15,
        "10日中单净流入-净额": 100000.0,
        "10日中单净流入-净占比": 0.05,
        "10日小单净流入-净额": 100000.0,
        "10日小单净流入-净占比": 0.05,
    }])
    with patch("app.analysis.capital_flow_analyzer.ak.stock_individual_fund_flow_rank",
               return_value=mock_df):
        result = analyzer.get_individual_fund_flow_rank(period="10日")
    # 统一 schema 校验
    assert isinstance(result, dict), "成功路径应返回 dict"
    assert "data" in result, "缺少 data 字段"
    assert "error" in result, "缺少 error 字段"
    assert "count" in result, "缺少 count 字段"
    assert "amount_unit" in result, "缺少 amount_unit 字段"
    assert isinstance(result["data"], list), "data 应为 list"
    assert result["error"] is None, f"成功路径 error 应为 None，实际: {result['error']}"
    assert result["amount_unit"] == "yuan"
    assert result["count"] == len(result["data"]), "count 应等于 data 长度"
    assert result["count"] == 1


# ---------------------------------------------------------------- S3-N5 异常路径返回 unified schema
def test_fund_flow_rank_exception_returns_unified_schema(analyzer):
    """H2-4：异常路径应返回 {'data': [], 'error': str, 'count': 0, 'amount_unit': 'yuan'}"""
    with patch("app.analysis.capital_flow_analyzer.ak.stock_individual_fund_flow_rank",
               side_effect=ValueError("mock api error")):
        result = analyzer.get_individual_fund_flow_rank(period="今日")
    # 统一 schema 校验
    assert isinstance(result, dict), "异常路径应返回 dict"
    assert "data" in result and result["data"] == [], "data 应为空列表"
    assert "error" in result and result["error"] is not None, "error 应为非 None 字符串"
    assert isinstance(result["error"], str), "error 应为 str 类型"
    assert "count" in result and result["count"] == 0, "count 应为 0"
    assert "amount_unit" in result and result["amount_unit"] == "yuan", "amount_unit 应为 yuan"
    assert "mock api error" in result["error"], "error 应包含原始异常信息"
