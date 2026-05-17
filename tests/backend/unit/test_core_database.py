# -*- coding: utf-8 -*-
"""
Input : pytest 收集
Output: StockInfo / AnalysisResult / Portfolio ORM 单元测试 (SQLite in-memory)
Pos   : tests/backend/unit/test_core_database.py - BE-03c Core #2

一旦此文件被修改，请同步更新 tests/audit/reports/BE-03c_core_misc.md。
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, StockInfo, AnalysisResult, Portfolio


@pytest.fixture
def session():
    """SQLite in-memory，每个用例独立。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    yield s
    s.close()
    engine.dispose()


def test_init_db_creates_tables():
    """Base.metadata.create_all 应建立三张表。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    insp_names = engine.dialect.get_table_names(engine.connect())
    assert "stock_info" in insp_names
    assert "analysis_results" in insp_names
    assert "portfolios" in insp_names


def test_stock_info_crud_and_to_dict(session):
    """StockInfo 写入/查询/序列化。"""
    s = StockInfo(stock_code="600519", stock_name="贵州茅台",
                  market_type="A", industry="白酒")
    session.add(s)
    session.commit()

    fetched = session.query(StockInfo).filter_by(stock_code="600519").one()
    d = fetched.to_dict()
    assert d["stock_code"] == "600519"
    assert d["stock_name"] == "贵州茅台"
    assert d["market_type"] == "A"
    assert d["industry"] == "白酒"
    # updated_at 应被 default 填充
    assert d["updated_at"] is not None


def test_analysis_result_with_json_fields(session):
    """AnalysisResult JSON 字段读写一致。"""
    tech = {"score": 78.5, "trend": "up"}
    fund = {"pe": 32.1, "roe": 0.28}
    a = AnalysisResult(
        stock_code="000001", market_type="A",
        score=85.5, recommendation="买入",
        technical_data=tech, fundamental_data=fund,
        capital_flow_data={"net": 1e8}, ai_analysis="测试 AI 摘要",
    )
    session.add(a)
    session.commit()

    got = session.query(AnalysisResult).filter_by(stock_code="000001").one()
    assert got.technical_data == tech
    assert got.fundamental_data == fund
    d = got.to_dict()
    assert d["score"] == 85.5
    assert d["recommendation"] == "买入"
    assert d["capital_flow_data"]["net"] == 1e8


def test_portfolio_with_json_stocks(session):
    """Portfolio.stocks JSON 列表读写。"""
    stocks = [{"code": "600519", "shares": 100},
              {"code": "000858", "shares": 50}]
    p = Portfolio(user_id="u-1", name="主组合", stocks=stocks)
    session.add(p)
    session.commit()

    got = session.query(Portfolio).filter_by(user_id="u-1").one()
    assert got.name == "主组合"
    assert got.stocks == stocks
    d = got.to_dict()
    assert d["user_id"] == "u-1"
    assert d["stocks"][0]["code"] == "600519"


def test_index_on_stock_code(session):
    """stock_code 列应建立索引（验证存在）。"""
    indexes = {ix.name for ix in StockInfo.__table__.indexes}
    # SQLAlchemy 自动命名为 ix_<table>_<col>
    assert any("stock_code" in (ix.name or "") for ix in StockInfo.__table__.indexes)


def test_multiple_records_isolation(session):
    """多条记录隔离查询。"""
    session.add_all([
        StockInfo(stock_code="600000", stock_name="浦发", market_type="A"),
        StockInfo(stock_code="600036", stock_name="招行", market_type="A"),
        StockInfo(stock_code="00700", stock_name="腾讯", market_type="HK"),
    ])
    session.commit()

    a_market = session.query(StockInfo).filter_by(market_type="A").all()
    hk_market = session.query(StockInfo).filter_by(market_type="HK").all()
    assert len(a_market) == 2
    assert len(hk_market) == 1
    assert hk_market[0].stock_name == "腾讯"
