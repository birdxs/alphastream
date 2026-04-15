# -*- coding: utf-8 -*-
"""
efinance适配器单元测试 [NEW-FILE:#20260415-04]
Input: mock efinance.stock.* 返回DataFrame
Output: pytest结果，覆盖 get_minute_kline / get_top_list / get_margin_trading / get_realtime_quotes / _norm_date
Pos: tests/adapters/ — 回归基线
"""
import os
import sys
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.adapters import efinance_adapter as efa  # noqa: E402


# ==================== 工具：构造mock efinance返回 ====================
def _mk_minute_df():
    return pd.DataFrame({
        '股票名称': ['平安银行'] * 3,
        '股票代码': ['000001'] * 3,
        '日期': ['2026-04-15 09:30', '2026-04-15 09:31', '2026-04-15 09:32'],
        '开盘': [12.1, 12.2, 12.15],
        '收盘': [12.2, 12.15, 12.18],
        '最高': [12.25, 12.23, 12.2],
        '最低': [12.08, 12.1, 12.12],
        '成交量': [1000, 1500, 1200],
        '成交额': [12100.0, 18300.0, 14616.0],
        '振幅': [1.4, 1.1, 0.7],
        '涨跌幅': [0.5, -0.4, 0.25],
        '涨跌额': [0.06, -0.05, 0.03],
        '换手率': [0.01, 0.015, 0.012],
    })


def _mk_billboard_df():
    return pd.DataFrame({
        '股票代码': ['600519', '000858'],
        '股票名称': ['贵州茅台', '五粮液'],
        '上榜日期': ['2026-04-14', '2026-04-14'],
        '解读': ['机构买入', '游资接力'],
        '收盘价': [1680.0, 152.5],
        '涨跌幅': [3.2, 4.5],
        '换手率': [0.5, 1.2],
        '龙虎榜净买额': [2.5e8, 1.2e8],
        '龙虎榜买入额': [5e8, 3e8],
        '龙虎榜卖出额': [2.5e8, 1.8e8],
        '龙虎榜成交额': [7.5e8, 4.8e8],
        '市场总成交额': [1e10, 8e9],
        '净买额占总成交比': [2.5, 1.5],
        '成交额占总成交比': [7.5, 6.0],
        '流通市值': [2.1e12, 5.9e11],
        '上榜原因': ['日涨幅偏离', '日换手率'],
    })


def _mk_realtime_df():
    return pd.DataFrame({
        '股票代码': ['000001', '600519', '000858'],
        '股票名称': ['平安银行', '贵州茅台', '五粮液'],
        '涨跌幅': [0.5, 3.2, 4.5],
        '最新价': [12.2, 1680.0, 152.5],
        '最高': [12.3, 1690.0, 155.0],
        '最低': [12.0, 1650.0, 148.0],
        '今开': [12.1, 1660.0, 150.0],
        '涨跌额': [0.06, 52.0, 6.5],
        '换手率': [0.5, 0.5, 1.2],
        '量比': [1.1, 1.5, 2.0],
        '动态市盈率': [5.2, 30.5, 22.3],
        '成交量': [1e7, 1e6, 5e6],
        '成交额': [1.22e8, 1.68e9, 7.6e8],
        '昨日收盘': [12.14, 1628.0, 146.0],
        '总市值': [2.3e11, 2.1e12, 5.9e11],
        '流通市值': [2.3e11, 2.1e12, 5.9e11],
        '行情ID': ['0.000001', '1.600519', '0.000858'],
        '市场类型': [0, 1, 0],
    })


# ==================== _norm_date ====================
class TestNormDate:
    def test_no_dash(self):
        assert efa.EfinanceAdapter._norm_date("2024-01-01") == "20240101"
        assert efa.EfinanceAdapter._norm_date("20240101") == "20240101"
        assert efa.EfinanceAdapter._norm_date("2024/01/01") == "20240101"

    def test_with_dash(self):
        assert efa.EfinanceAdapter._norm_date("20240101", dash=True) == "2024-01-01"
        assert efa.EfinanceAdapter._norm_date("2024-01-01", dash=True) == "2024-01-01"

    def test_empty(self):
        assert efa.EfinanceAdapter._norm_date("") == ""
        assert efa.EfinanceAdapter._norm_date(None) is None


# ==================== _rename ====================
class TestRename:
    def test_rename_partial(self):
        df = pd.DataFrame({'股票代码': ['000001'], '日期': ['2026-04-15'], 'extra': [1]})
        out = efa.EfinanceAdapter._rename(df, efa._KLINE_FIELD_MAP)
        assert 'code' in out.columns
        assert 'date' in out.columns
        assert 'extra' in out.columns

    def test_rename_empty(self):
        assert efa.EfinanceAdapter._rename(None, {}).empty
        assert efa.EfinanceAdapter._rename(pd.DataFrame(), {}).empty


# ==================== get_minute_kline ====================
class TestMinuteKline:
    def test_ok(self):
        fake_ef = MagicMock()
        fake_ef.stock.get_quote_history.return_value = _mk_minute_df()
        with patch.object(efa, 'ef', fake_ef), patch.object(efa, '_EF_AVAILABLE', True):
            a = efa.EfinanceAdapter()
            df = a.get_minute_kline("000001", klt=1, count=240)
        assert not df.empty
        assert 'code' in df.columns and 'close' in df.columns
        assert len(df) == 3

    def test_count_tail(self):
        big = pd.concat([_mk_minute_df()] * 100, ignore_index=True)  # 300 rows
        fake_ef = MagicMock()
        fake_ef.stock.get_quote_history.return_value = big
        with patch.object(efa, 'ef', fake_ef), patch.object(efa, '_EF_AVAILABLE', True):
            a = efa.EfinanceAdapter()
            df = a.get_minute_kline("000001", klt=5, count=50)
        assert len(df) == 50

    def test_invalid_klt_fallback(self):
        fake_ef = MagicMock()
        fake_ef.stock.get_quote_history.return_value = _mk_minute_df()
        with patch.object(efa, 'ef', fake_ef), patch.object(efa, '_EF_AVAILABLE', True):
            a = efa.EfinanceAdapter()
            a.get_minute_kline("000001", klt=7)  # 非法
        # 确认调用时klt被回退为1
        called_kwargs = fake_ef.stock.get_quote_history.call_args.kwargs
        assert called_kwargs.get('klt') == 1

    def test_ef_unavailable(self):
        with patch.object(efa, '_EF_AVAILABLE', False):
            a = efa.EfinanceAdapter()
            df = a.get_minute_kline("000001")
        assert df.empty

    def test_exception_returns_empty(self):
        fake_ef = MagicMock()
        fake_ef.stock.get_quote_history.side_effect = RuntimeError("net down")
        with patch.object(efa, 'ef', fake_ef), patch.object(efa, '_EF_AVAILABLE', True):
            a = efa.EfinanceAdapter()
            df = a.get_minute_kline("000001")
        assert df.empty


# ==================== get_top_list (龙虎榜) ====================
class TestTopList:
    def test_ok(self):
        fake_ef = MagicMock()
        fake_ef.stock.get_daily_billboard.return_value = _mk_billboard_df()
        with patch.object(efa, 'ef', fake_ef), patch.object(efa, '_EF_AVAILABLE', True):
            a = efa.EfinanceAdapter()
            df = a.get_top_list("20260414", "20260414")
        assert not df.empty
        assert 'code' in df.columns
        assert 'net_buy' in df.columns
        assert 'reason' in df.columns
        # 日期按dash格式传入
        kwargs = fake_ef.stock.get_daily_billboard.call_args.kwargs
        assert kwargs.get('start_date') == "2026-04-14"
        assert kwargs.get('end_date') == "2026-04-14"

    def test_ef_unavailable(self):
        with patch.object(efa, '_EF_AVAILABLE', False):
            a = efa.EfinanceAdapter()
            assert a.get_top_list("20260414", "20260414").empty


# ==================== get_margin_trading ====================
class TestMarginTrading:
    def test_always_empty(self):
        """efinance无此API，恒返回空"""
        a = efa.EfinanceAdapter()
        df = a.get_margin_trading("000001")
        assert isinstance(df, pd.DataFrame)
        assert df.empty


# ==================== get_realtime_quotes ====================
class TestRealtimeQuotes:
    def test_all_market(self):
        fake_ef = MagicMock()
        fake_ef.stock.get_realtime_quotes.return_value = _mk_realtime_df()
        with patch.object(efa, 'ef', fake_ef), patch.object(efa, '_EF_AVAILABLE', True):
            a = efa.EfinanceAdapter()
            df = a.get_realtime_quotes()
        assert len(df) == 3
        assert 'price' in df.columns and 'change_percent' in df.columns

    def test_filter_by_codes(self):
        fake_ef = MagicMock()
        fake_ef.stock.get_realtime_quotes.return_value = _mk_realtime_df()
        with patch.object(efa, 'ef', fake_ef), patch.object(efa, '_EF_AVAILABLE', True):
            a = efa.EfinanceAdapter()
            df = a.get_realtime_quotes(["000001", "600519"])
        assert len(df) == 2
        assert set(df['code'].tolist()) == {"000001", "600519"}

    def test_ef_unavailable(self):
        with patch.object(efa, '_EF_AVAILABLE', False):
            a = efa.EfinanceAdapter()
            assert a.get_realtime_quotes(["000001"]).empty


# ==================== name / health_check ====================
class TestMeta:
    def test_name(self):
        assert efa.EfinanceAdapter().name == "efinance"

    def test_health_check_unavailable(self):
        with patch.object(efa, '_EF_AVAILABLE', False):
            assert efa.EfinanceAdapter().health_check() is False

    def test_health_check_ok(self):
        fake_ef = MagicMock()
        fake_ef.stock.get_realtime_quotes.return_value = _mk_realtime_df()
        with patch.object(efa, 'ef', fake_ef), patch.object(efa, '_EF_AVAILABLE', True):
            assert efa.EfinanceAdapter().health_check() is True
