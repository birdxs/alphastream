# -*- coding: utf-8 -*-
"""
JobsAdapter 单元测试（纯 mock, 无真实网络请求）
Input: mock 的 requests.Session.get/post 响应
Output: pytest 用例结果
Pos: tests/adapters, CI 回归保护 [NEW-FILE:#20260415-26]
"""
from unittest.mock import MagicMock, patch

import pandas as pd

from app.adapters.jobs_adapter import JobsAdapter


def _mk_resp(status: int = 200, payload: dict = None) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload or {}
    return m


ARBEITNOW_PAYLOAD = {
    "data": [
        {
            "title": "Senior Python Engineer",
            "company_name": "Apple",
            "location": "Cupertino, CA",
            "remote": False,
            "tags": ["python", "backend"],
            "description": "Build backend systems in Python",
            "url": "https://arbeitnow.com/jobs/1",
            "created_at": 1712000000,
        },
        {
            "title": "Frontend React Dev",
            "company_name": "Spotify",
            "location": "Berlin",
            "remote": True,
            "tags": ["react", "typescript"],
            "description": "Build streaming UI",
            "url": "https://arbeitnow.com/jobs/2",
            "created_at": 1712100000,
        },
        {
            "title": "Python Data Scientist",
            "company_name": "Apple",
            "location": "Austin, TX",
            "remote": False,
            "tags": ["python", "ml"],
            "description": "Data & ML work in python",
            "url": "https://arbeitnow.com/jobs/3",
            "created_at": 1712200000,
        },
    ]
}

LAGOU_PAYLOAD = {
    "content": {
        "positionResult": {
            "result": [
                {
                    "positionId": 111,
                    "positionName": "Python工程师",
                    "companyFullName": "字节跳动有限公司",
                    "companyShortName": "字节跳动",
                    "city": "北京",
                    "positionLables": ["Python", "后端"],
                    "createTime": "2026-04-14 12:00:00",
                },
                {
                    "positionId": 222,
                    "positionName": "高级后端开发",
                    "companyFullName": "腾讯科技",
                    "companyShortName": "腾讯",
                    "city": "深圳",
                    "positionLables": ["Python"],
                    "createTime": "2026-04-13 10:00:00",
                },
            ]
        }
    }
}


class TestInit:
    def test_name_and_sources(self):
        a = JobsAdapter()
        assert a.name == "jobs_adapter"
        assert "arbeitnow" in a.SUPPORTED_SOURCES
        assert "lagou" in a.SUPPORTED_SOURCES


class TestSearchArbeitnow:
    def test_query_filter(self):
        a = JobsAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, ARBEITNOW_PAYLOAD)):
            df = a.search_jobs("python", source="arbeitnow", limit=20)
            assert isinstance(df, pd.DataFrame)
            # 命中 python 的两条
            assert len(df) == 2
            assert all("python" in t.lower() or "python" in tags.lower()
                       for t, tags in zip(df["title"], df["tags"]))
            assert set(df["source"].unique()) == {"arbeitnow"}

    def test_limit_cap(self):
        a = JobsAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, ARBEITNOW_PAYLOAD)):
            df = a.search_jobs("", source="arbeitnow", limit=1)
            assert len(df) == 1

    def test_empty_feed(self):
        a = JobsAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, {"data": []})):
            df = a.search_jobs("python")
            assert df.empty

    def test_http_error(self):
        a = JobsAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(500, {})):
            df = a.search_jobs("python")
            assert df.empty


class TestSearchLagou:
    def test_lagou_happy_path(self):
        a = JobsAdapter()
        with patch.object(a.session, "post",
                          return_value=_mk_resp(200, LAGOU_PAYLOAD)) as mp:
            df = a.search_jobs("python", source="lagou", limit=10)
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert df.iloc[0]["title"] == "Python工程师"
            assert df.iloc[0]["company"] == "字节跳动有限公司"
            assert df.iloc[0]["source"] == "lagou"
            # URL 为拼接详情页
            assert "lagou.com/jobs/111.html" in df.iloc[0]["url"]
            # UA 伪装生效
            called_headers = mp.call_args.kwargs.get("headers") or {}
            assert "Mozilla" in called_headers.get("User-Agent", "")

    def test_lagou_anti_crawl_empty(self):
        a = JobsAdapter()
        with patch.object(a.session, "post",
                          return_value=_mk_resp(200, {"content": {}})):
            df = a.search_jobs("python", source="lagou")
            assert df.empty

    def test_lagou_http_403(self):
        a = JobsAdapter()
        with patch.object(a.session, "post",
                          return_value=_mk_resp(403, {})):
            df = a.search_jobs("python", source="lagou")
            assert df.empty


class TestUnifiedEntry:
    def test_unknown_source_fallback_arbeitnow(self):
        a = JobsAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, ARBEITNOW_PAYLOAD)):
            df = a.search_jobs("python", source="indeed", limit=10)
            # 未支持 source → fallback arbeitnow, 返回过滤后结果
            assert not df.empty
            assert set(df["source"].unique()) == {"arbeitnow"}


class TestCompanyPostings:
    def test_filter_by_company(self):
        a = JobsAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, ARBEITNOW_PAYLOAD)):
            df = a.get_company_postings("Apple")
            assert len(df) == 2
            assert all(c.lower() == "apple" for c in df["company"])

    def test_empty_company(self):
        a = JobsAdapter()
        df = a.get_company_postings("")
        assert df.empty

    def test_no_match(self):
        a = JobsAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, ARBEITNOW_PAYLOAD)):
            df = a.get_company_postings("NotExist Corp")
            assert df.empty


class TestBaseAdapterInterface:
    def test_get_stock_history_empty(self):
        assert JobsAdapter().get_stock_history("x", "1", "2").empty

    def test_get_index_stocks_empty(self):
        assert JobsAdapter().get_index_stocks("SPX") == []

    def test_get_financial_data_empty(self):
        assert JobsAdapter().get_financial_data("Apple") == {}

    def test_get_stock_info_summary(self):
        a = JobsAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, ARBEITNOW_PAYLOAD)):
            info = a.get_stock_info("Apple")
            assert info["company"] == "Apple"
            assert info["posting_count"] == 2
            assert set(info["locations"]) >= {"Cupertino, CA", "Austin, TX"}

    def test_health_check_true(self):
        a = JobsAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, ARBEITNOW_PAYLOAD)):
            assert a.health_check() is True

    def test_health_check_false(self):
        a = JobsAdapter()
        with patch.object(a.session, "get",
                          return_value=_mk_resp(200, {"data": []})):
            assert a.health_check() is False
