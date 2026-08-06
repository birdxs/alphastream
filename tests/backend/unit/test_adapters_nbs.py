"""
P1: NBS Adapter AkShare 宏观数据降级测试 (2026-08-05)
"""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from app.adapters.nbs_adapter import NBSAdapter


class TestNBSAdapterAkShareFallback:
    """测试 NBS Adapter AkShare 降级能力"""

    @pytest.fixture
    def adapter(self):
        return NBSAdapter()

    def test_gdp_fallback_success(self, adapter, monkeypatch):
        """GDP 官网失败 → AkShare 降级成功"""
        # Mock 官网路径失败
        def mock_get_gdp_fail():
            raise ConnectionError("NBS官网不可达")

        monkeypatch.setattr(adapter, "get_gdp", mock_get_gdp_fail)

        # Mock AkShare 成功
        mock_df = pd.DataFrame({
            "日期": ["2024-Q1", "2024-Q2"],
            "GDP": [280000, 285000],
        })
        with patch("akshare.macro_china_gdp", return_value=mock_df):
            result = adapter.get_macro_indicators(["GDP"])

        assert "GDP" in result
        assert isinstance(result["GDP"], pd.DataFrame)
        assert not result["GDP"].empty
        assert "value" in result["GDP"].columns
        assert "indicator" in result["GDP"].columns

    def test_cpi_fallback_success(self, adapter, monkeypatch):
        """CPI 官网失败 → AkShare 降级成功"""
        def mock_get_cpi_fail():
            raise TimeoutError("NBS官网超时")

        monkeypatch.setattr(adapter, "get_cpi", mock_get_cpi_fail)

        mock_df = pd.DataFrame({
            "日期": ["2024-01", "2024-02"],
            "CPI": [102.5, 102.8],
        })
        with patch("akshare.macro_china_cpi", return_value=mock_df):
            result = adapter.get_macro_indicators(["CPI"])

        assert "CPI" in result
        assert isinstance(result["CPI"], pd.DataFrame)
        assert not result["CPI"].empty

    def test_pmi_fallback_success(self, adapter, monkeypatch):
        """PMI 官网失败 → AkShare 降级成功"""
        def mock_get_pmi_fail():
            raise Exception("官网数据解析失败")

        monkeypatch.setattr(adapter, "get_pmi", mock_get_pmi_fail)

        mock_df = pd.DataFrame({
            "日期": ["2024-01", "2024-02"],
            "PMI": [50.2, 50.5],
        })
        with patch("akshare.macro_china_pmi", return_value=mock_df):
            result = adapter.get_macro_indicators(["PMI"])

        assert "PMI" in result
        assert isinstance(result["PMI"], pd.DataFrame)

    def test_industrial_output_fallback_success(self, adapter, monkeypatch):
        """工业增加值官网失败 → AkShare 降级成功"""
        def mock_get_industrial_fail():
            raise Exception("官网数据缺失")

        monkeypatch.setattr(adapter, "get_industrial_output", mock_get_industrial_fail)

        mock_df = pd.DataFrame({
            "日期": ["2024-01", "2024-02"],
            "工业增加值": [6.2, 6.5],
        })
        with patch("akshare.macro_china_industrial_production_yoy", return_value=mock_df):
            result = adapter.get_macro_indicators(["IndustrialOutput"])

        assert "IndustrialOutput" in result
        assert isinstance(result["IndustrialOutput"], pd.DataFrame)

    def test_fallback_akshare_not_installed(self, adapter, monkeypatch):
        """AkShare 未安装时降级失败"""
        def mock_get_gdp_fail():
            raise Exception("官网失败")

        monkeypatch.setattr(adapter, "get_gdp", mock_get_gdp_fail)

        # Mock akshare import 失败
        with patch.dict("sys.modules", {"akshare": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module akshare")):
                result = adapter.get_macro_indicators(["GDP"])

        # GDP 应该不在结果中（官网失败 + AkShare 不可用）
        assert "GDP" not in result

    def test_fallback_all_fail(self, adapter, monkeypatch):
        """官网失败 + AkShare 降级失败 → 空结果"""
        def mock_get_cpi_fail():
            raise Exception("官网失败")

        monkeypatch.setattr(adapter, "get_cpi", mock_get_cpi_fail)

        # Mock AkShare 也失败
        with patch("akshare.macro_china_cpi", side_effect=Exception("AkShare API error")):
            result = adapter.get_macro_indicators(["CPI"])

        assert "CPI" not in result
