# Input  : Flask test_client (flask_client fixture) + monkeypatch
# Output : pytest 用例：覆盖 10 条股票数据相关路由（快乐路径 + 错误路径）
# Pos    : tests/backend/api/test_stock_data_routes.py
# 说明   : BE-01b 小批量验收。LLM/akshare/baostock/外部 IO 全 mock；不发起任何真实数据拉取。
"""BE-01b 股票数据 10 路由测试。

覆盖路由（精确，路径以 app/web/web_server.py grep 结果为准）：

1.  GET  /api/stock_data         (line 1136)  历史行情 + 技术指标
2.  GET  /api/stock_name         (line 1339)  名称缓存查询
3.  GET  /api/stock_profile      (line 1247)  baostock 概要（行业/PE/PB/ROE）
4.  GET  /api/stock_name_search  (line 1354)  名称反查
5.  GET  /api/market_indices     (line 1639)  四大市场指数
6.  GET  /api/latest_news        (line 2212)  最新新闻
7.  GET  /api/news_sentiment     (line 2345)  新闻情绪分析
8.  POST /api/north_flow_history (line 622)   北向资金历史
9.  GET  /search_us_stocks       (line 649)   美股关键词搜索
10. GET  /api/stock_data         参数错误分支（period 容错）

约束：每路由 ≥ 2 用例（快乐 + 错误）。错误路径不得 500 泄露堆栈。
外部 IO（akshare/baostock/news_fetcher/analyzer/us_stock_service/CapitalFlowAnalyzer）全 mock。
"""

from __future__ import annotations

import json
import sys
import time
import types
from typing import Any, Dict

import pandas as pd
import pytest


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #

def _json(resp) -> Dict[str, Any]:
    """安全解析 JSON 响应；保证返回 dict。"""
    assert resp.content_type and "application/json" in resp.content_type, (
        f"响应非 JSON: content_type={resp.content_type}, body={resp.data[:200]!r}"
    )
    data = json.loads(resp.data.decode("utf-8"))
    assert isinstance(data, dict), f"JSON 顶层非 dict: {type(data)}"
    return data


def _has_error(body: Dict[str, Any]) -> bool:
    """兼容旧 {'error': ...} 与新统一外壳 {'error_code': ..., 'success': False}"""
    return "error" in body or "error_code" in body


def _get_error_msg(body: Dict[str, Any]) -> str:
    """从旧/新外壳中提取错误信息字符串"""
    return body.get("error") or body.get("message") or ""


def _no_stacktrace(resp) -> None:
    """断言响应体不泄露 Python 堆栈关键字。"""
    body = resp.data.decode("utf-8", errors="replace").lower()
    forbidden = ["traceback (most recent call last)", 'file "', "raise "]
    for fb in forbidden:
        assert fb not in body, f"响应不应泄露堆栈关键字 {fb!r}: {body[:300]}"


# --------------------------------------------------------------------------- #
# 1. GET /api/stock_data
# --------------------------------------------------------------------------- #

class TestStockDataRoute:
    """覆盖 /api/stock_data：参数缺失 / 历史数据正常 / period 容错。"""

    def test_missing_stock_code_returns_400(self, flask_client):
        resp = flask_client.get("/api/stock_data")
        assert resp.status_code == 400
        data = _json(resp)
        # S2-A1: 空 stock_code → INVALID_INPUT，消息含 "stock_code" 或 "股票代码" 或 "必填"
        assert _has_error(data)
        msg = _get_error_msg(data)
        assert "stock_code" in msg or "股票代码" in msg or "必填" in msg, \
            f"期望含 stock_code 字段提示，实际: {msg}"
        _no_stacktrace(resp)

    def test_invalid_stock_code_returns_400(self, flask_client):
        # validate_stock_code 对非法 A 股代码（非6位数字）返回失败
        resp = flask_client.get("/api/stock_data?stock_code=ABCXYZ&market_type=A")
        assert resp.status_code == 400, resp.data[:200]
        _no_stacktrace(resp)

    def test_happy_path_returns_records(self, flask_client, monkeypatch):
        from app.web import web_server

        # mock analyzer 历史数据：构造 5 行 DataFrame，含 date / open / high / low / close / volume
        fake_df = pd.DataFrame({
            "date": pd.to_datetime(["2025-12-01", "2025-12-02", "2025-12-03",
                                     "2025-12-04", "2025-12-05"]),
            "open": [10.0, 10.5, 10.2, 10.6, 10.8],
            "high": [10.6, 10.7, 10.5, 10.9, 11.0],
            "low":  [9.9, 10.1, 10.0, 10.4, 10.6],
            "close": [10.5, 10.3, 10.4, 10.8, 10.9],
            "volume": [10000, 12000, 11000, 13000, 14000],
        })
        monkeypatch.setattr(web_server.analyzer, "get_stock_data",
                            lambda code, mt, sd, ed: fake_df.copy())
        # calculate_indicators 直接透传，避免触发 ta 库依赖
        monkeypatch.setattr(web_server.analyzer, "calculate_indicators",
                            lambda df: df)
        # 名称获取走缓存接口，禁止真实回退
        monkeypatch.setattr(web_server, "_get_stock_name_safe",
                            lambda code, mt='A': "测试股票")

        resp = flask_client.get("/api/stock_data?stock_code=600000&market_type=A&period=1m")
        assert resp.status_code == 200, resp.data[:300]
        data = _json(resp)
        assert "data" in data and isinstance(data["data"], list)
        assert len(data["data"]) == 5
        assert data.get("stock_name") == "测试股票"

    def test_empty_dataframe_returns_404(self, flask_client, monkeypatch):
        from app.web import web_server
        monkeypatch.setattr(web_server.analyzer, "get_stock_data",
                            lambda code, mt, sd, ed: pd.DataFrame())
        monkeypatch.setattr(web_server, "_get_stock_name_safe",
                            lambda code, mt='A': "未知")
        resp = flask_client.get("/api/stock_data?stock_code=600001&market_type=A&period=3m")
        assert resp.status_code == 404
        data = _json(resp)
        assert _has_error(data)
        _no_stacktrace(resp)


# --------------------------------------------------------------------------- #
# 2. GET /api/stock_name
# --------------------------------------------------------------------------- #

class TestStockNameRoute:
    def test_missing_stock_code_returns_400(self, flask_client):
        from app.web import web_server
        resp = flask_client.get(
            "/api/stock_name",
            headers={"X-API-Key": web_server._get_api_key()},
        )
        assert resp.status_code == 400
        data = _json(resp)
        assert _has_error(data)  # stock_code required (old: error key, new: error_code key)
        _no_stacktrace(resp)

    def test_happy_path_uses_cache(self, flask_client, monkeypatch):
        from app.web import web_server
        # 直接注入缓存，避免触发 akshare
        monkeypatch.setattr(web_server, "_STOCK_NAME_CACHE",
                            {"600000": "浦发银行"})
        monkeypatch.setattr(web_server, "_load_stock_name_cache", lambda: None)

        resp = flask_client.get(
            "/api/stock_name?stock_code=600000",
            headers={"X-API-Key": web_server._get_api_key()},
        )
        assert resp.status_code == 200
        data = _json(resp)
        assert data["stock_code"] == "600000"
        assert data["stock_name"] == "浦发银行"

    def test_unknown_code_returns_code_as_name(self, flask_client, monkeypatch):
        from app.web import web_server
        monkeypatch.setattr(web_server, "_STOCK_NAME_CACHE", {})
        monkeypatch.setattr(web_server, "_load_stock_name_cache", lambda: None)
        resp = flask_client.get(
            "/api/stock_name?stock_code=999999",
            headers={"X-API-Key": web_server._get_api_key()},
        )
        assert resp.status_code == 200
        data = _json(resp)
        # 未命中时回填 code 作为 name
        assert data["stock_name"] == "999999"

    def test_cold_start_timeout_returns_code_without_waiting_worker(self, flask_client, monkeypatch):
        from app.web import web_server

        monkeypatch.setattr(web_server, "_CACHE_LOADED", False)
        monkeypatch.setattr(web_server, "_STOCK_NAME_CACHE", {})
        monkeypatch.setenv("STOCK_NAME_CACHE_TIMEOUT_S", "0.05")

        fake_akshare = types.SimpleNamespace(
            stock_info_a_code_name=lambda: (time.sleep(1.0) or pd.DataFrame(
                [{"code": "600519", "name": "贵州茅台"}]
            ))
        )
        monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

        start = time.perf_counter()
        resp = flask_client.get(
            "/api/stock_name?stock_code=600519",
            headers={"X-API-Key": web_server._get_api_key()},
        )
        elapsed = time.perf_counter() - start

        assert elapsed < 0.5
        assert resp.status_code == 200
        data = _json(resp)
        assert data["stock_code"] == "600519"
        assert data["stock_name"] == "600519"

    def test_load_cache_timeout_not_permanently_marked_and_retries_after_cooldown(
        self, monkeypatch
    ):
        """[2026-05-29 Bug1] 加载超时后不得永久标记已加载；冷却窗内节流、冷却窗后允许重试并成功填充。"""
        import app.web.web_server as ws

        monkeypatch.setattr(ws, "_CACHE_LOADED", False)
        monkeypatch.setattr(ws, "_CACHE_LAST_FAIL_TS", 0.0)
        monkeypatch.setattr(ws, "_STOCK_NAME_CACHE", {})
        monkeypatch.setenv("STOCK_NAME_CACHE_TIMEOUT_S", "0.05")
        monkeypatch.setenv("STOCK_NAME_CACHE_RETRY_COOLDOWN_S", "60")

        calls = {"n": 0}

        def _fake_code_name_first_slow_then_fast():
            calls["n"] += 1
            if calls["n"] == 1:
                time.sleep(1.0)  # 首次超过 0.05s 超时
                return pd.DataFrame([{"code": "600519", "name": "贵州茅台"}])
            return pd.DataFrame([{"code": "600519", "name": "贵州茅台"}])

        fake_akshare = types.SimpleNamespace(
            stock_info_a_code_name=_fake_code_name_first_slow_then_fast
        )
        monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

        # 第一次：超时 → 未永久标记，记录失败时间戳，请求线程不被长阻塞
        start = time.perf_counter()
        ws._load_stock_name_cache()
        elapsed = time.perf_counter() - start
        assert elapsed < 0.6  # 不阻塞等待慢 worker
        assert ws._CACHE_LOADED is False
        assert ws._CACHE_LAST_FAIL_TS != 0.0
        assert ws._STOCK_NAME_CACHE == {}

        # 冷却窗内（60s）再调：被节流，不触发 worker（calls 不增）
        ws._load_stock_name_cache()
        assert calls["n"] == 1
        assert ws._CACHE_LOADED is False

        # 模拟冷却窗已过：把上次失败时间戳推到很久以前 → 允许重试且成功填充
        monkeypatch.setattr(ws, "_CACHE_LAST_FAIL_TS", time.monotonic() - 999.0)
        ws._load_stock_name_cache()
        assert calls["n"] == 2
        assert ws._CACHE_LOADED is True
        assert ws._CACHE_LAST_FAIL_TS == 0.0
        assert ws._STOCK_NAME_CACHE.get("600519") == "贵州茅台"

    def test_load_cache_exception_not_permanently_marked(self, monkeypatch):
        """[2026-05-29 Bug1] 加载抛异常后不得永久标记已加载；记录失败时间戳供冷却后重试。"""
        import app.web.web_server as ws

        monkeypatch.setattr(ws, "_CACHE_LOADED", False)
        monkeypatch.setattr(ws, "_CACHE_LAST_FAIL_TS", 0.0)
        monkeypatch.setattr(ws, "_STOCK_NAME_CACHE", {})

        def _boom():
            raise RuntimeError("upstream RST")

        fake_akshare = types.SimpleNamespace(stock_info_a_code_name=_boom)
        monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

        ws._load_stock_name_cache()
        assert ws._CACHE_LOADED is False
        assert ws._CACHE_LAST_FAIL_TS != 0.0
        assert ws._STOCK_NAME_CACHE == {}

    def test_request_path_never_calls_full_loader(self, flask_client, monkeypatch):
        """[2026-05-29 后台预热] 缓存未加载时，/api/stock_name 请求线程绝不调用全量加载函数，
        且快速返回（<0.5s），退码兜底。全量加载交由后台预热线程。"""
        from app.web import web_server

        monkeypatch.setattr(web_server, "_CACHE_LOADED", False)
        monkeypatch.setattr(web_server, "_STOCK_NAME_CACHE", {})

        loader_calls = {"n": 0}

        def _spy_loader():
            loader_calls["n"] += 1

        monkeypatch.setattr(web_server, "_load_stock_name_cache", _spy_loader)

        start = time.perf_counter()
        resp = flask_client.get(
            "/api/stock_name?stock_code=600519",
            headers={"X-API-Key": web_server._get_api_key()},
        )
        elapsed = time.perf_counter() - start

        assert elapsed < 0.5
        assert resp.status_code == 200
        # 请求线程未触发全量加载
        assert loader_calls["n"] == 0
        data = _json(resp)
        # 未命中时退码兜底（非"未知"）
        assert data["stock_code"] == "600519"
        assert data["stock_name"] == "600519"

    def test_get_stock_name_safe_does_not_call_loader_on_request_path(self, monkeypatch):
        """[2026-05-29 后台预热] _get_stock_name_safe 的降级路径只读缓存，不调用全量加载函数。"""
        from app.web import web_server

        monkeypatch.setattr(web_server, "_STOCK_NAME_CACHE", {})

        loader_calls = {"n": 0}
        monkeypatch.setattr(
            web_server, "_load_stock_name_cache",
            lambda: loader_calls.__setitem__("n", loader_calls["n"] + 1),
        )

        # analyzer.get_stock_info 失败 → 走只读缓存降级 → 最终退码
        class _Boom:
            def get_stock_info(self, *a, **k):
                raise RuntimeError("eastmoney blocked")

        monkeypatch.setattr(web_server, "get_analyzer", lambda: _Boom())

        name = web_server._get_stock_name_safe("600519", "A")
        assert name == "600519"  # 退码兜底
        assert loader_calls["n"] == 0  # 请求线程未触发全量加载

        # 缓存命中时直接返回真名（仍不触发 loader）
        monkeypatch.setattr(web_server, "_STOCK_NAME_CACHE", {"600519": "贵州茅台"})
        name2 = web_server._get_stock_name_safe("600519", "A")
        assert name2 == "贵州茅台"
        assert loader_calls["n"] == 0

    def test_preload_stock_names_calls_loader_until_loaded(self, monkeypatch):
        """[2026-05-29 后台预热] 后台预热线程循环调用 loader，加载成功后停止。"""
        from app.web import web_server

        monkeypatch.setattr(web_server, "_CACHE_LOADED", False)
        monkeypatch.setattr(web_server, "_STOCK_NAME_CACHE", {})
        monkeypatch.setenv("STOCK_NAME_CACHE_RETRY_COOLDOWN_S", "0")

        calls = {"n": 0}

        def _fake_loader():
            calls["n"] += 1
            if calls["n"] >= 2:
                # 第二次调用模拟加载成功
                web_server._CACHE_LOADED = True
                web_server._STOCK_NAME_CACHE["600519"] = "贵州茅台"

        monkeypatch.setattr(web_server, "_load_stock_name_cache", _fake_loader)
        # 缩短首次 sleep 与轮询间隔，避免测试拖慢
        monkeypatch.setattr(web_server.time, "sleep", lambda *_a, **_k: None)

        web_server._preload_stock_names()

        assert web_server._CACHE_LOADED is True
        assert calls["n"] == 2  # 重试到成功即止
        assert web_server._STOCK_NAME_CACHE.get("600519") == "贵州茅台"

    def test_preload_disabled_in_offline_mode(self, monkeypatch):
        """[2026-05-29 后台预热] 离线/测试门控（DISABLE_NETWORK=1）下后台预热线程不启动。"""
        from app.web import web_server

        monkeypatch.setenv("DISABLE_NETWORK", "1")
        assert web_server._startup_background_enabled() is False
        monkeypatch.delenv("DISABLE_NETWORK", raising=False)
        assert web_server._startup_background_enabled() is True


# --------------------------------------------------------------------------- #
# 3. GET /api/stock_profile
# --------------------------------------------------------------------------- #

class TestStockProfileRoute:
    def test_missing_stock_code_returns_400(self, flask_client):
        resp = flask_client.get("/api/stock_profile")
        assert resp.status_code == 400
        data = _json(resp)
        assert _has_error(data)  # stock_code required (old: error key, new: error_code key)
        _no_stacktrace(resp)

    def test_happy_path_with_mocked_baostock(self, flask_client, monkeypatch):
        """注入 sys.modules['baostock']，全部接口 mock，避免外网。"""
        import sys
        import types

        from app.web import web_server

        # 重置缓存，避免之前用例污染
        web_server._PROFILE_CACHE.clear()

        # mock 名称缓存
        monkeypatch.setattr(web_server, "_STOCK_NAME_CACHE", {"600000": "浦发银行"})
        monkeypatch.setattr(web_server, "_load_stock_name_cache", lambda: None)
        # 跳过 baostock 登录
        monkeypatch.setattr(web_server, "_ensure_bs_login", lambda: None)

        # 构造 fake baostock module
        class _FakeRS:
            def __init__(self, rows):
                self._rows = list(rows)
                self.error_code = "0"
                self._idx = 0

            def next(self):
                if self._idx < len(self._rows):
                    self._idx += 1
                    return True
                return False

            def get_row_data(self):
                return self._rows[self._idx - 1]

        fake_bs = types.ModuleType("baostock")
        fake_bs.login = lambda: None
        fake_bs.logout = lambda: None
        # industry: rows[0][3] 是行业
        fake_bs.query_stock_industry = lambda code: _FakeRS([
            ["2025-12-31", code, "浦发银行", "银行"]
        ])
        # k_data: 16 列，索引 5=close 12=peTTM 13=pbMRQ
        fake_bs.query_history_k_data_plus = lambda *a, **kw: _FakeRS([
            [
                "2025-12-30", "sh.600000",
                "10.0", "10.5", "9.9", "10.3", "100000", "1000000",
                "3", "1.2", "1", "0.5",
                "5.5", "0.6", "1.0", "2.0", "0",
            ]
        ])
        fake_bs.query_stock_basic = lambda code: _FakeRS([])
        # profit: rows[0][3] 是 roeAvg
        fake_bs.query_profit_data = lambda code, year, quarter: _FakeRS([
            ["2025", "sh.600000", "20251231", "0.12"]
        ])
        monkeypatch.setitem(sys.modules, "baostock", fake_bs)

        resp = flask_client.get("/api/stock_profile?stock_code=600000")
        assert resp.status_code == 200, resp.data[:300]
        data = _json(resp)
        assert data["stock_code"] == "600000"
        assert data["stock_name"] == "浦发银行"
        assert data["industry"] == "银行"
        assert data["pe_ttm"] == pytest.approx(5.5)
        assert data["pb"] == pytest.approx(0.6)
        # roeAvg=0.12 * 100 = 12.0
        assert data["roe"] == pytest.approx(12.0)


# --------------------------------------------------------------------------- #
# 4. GET /api/stock_name_search
# --------------------------------------------------------------------------- #

class TestStockNameSearchRoute:
    def test_missing_query_returns_400(self, flask_client):
        resp = flask_client.get("/api/stock_name_search")
        assert resp.status_code == 400
        data = _json(resp)
        assert _has_error(data)  # q required (old: error key, new: error_code key)
        assert data.get("results") == []
        _no_stacktrace(resp)

    def test_match_ranks_exact_first(self, flask_client, monkeypatch):
        from app.web import web_server
        monkeypatch.setattr(web_server, "_STOCK_NAME_CACHE", {
            "600000": "浦发银行",
            "601398": "工商银行",
            "600036": "招商银行",
        })
        monkeypatch.setattr(web_server, "_load_stock_name_cache", lambda: None)

        resp = flask_client.get("/api/stock_name_search?q=招商银行")
        assert resp.status_code == 200
        data = _json(resp)
        assert data["query"] == "招商银行"
        assert data["count"] >= 1
        # exact 命中优先
        assert data["results"][0]["stock_code"] == "600036"


# --------------------------------------------------------------------------- #
# 5. GET /api/market_indices
# --------------------------------------------------------------------------- #

class TestMarketIndicesRoute:
    def test_market_indices_happy_path_returns_indices(self, flask_client, monkeypatch):
        from app.web import web_server
        fake = {"indices": [
            {"name": "上证指数", "code": "000001", "price": 3500.0, "change_pct": 1.2},
            {"name": "深证成指", "code": "399001", "price": 11000.0, "change_pct": -0.5},
        ]}
        monkeypatch.setattr(web_server, "_fetch_market_indices_data", lambda: fake)
        resp = flask_client.get("/api/market_indices")
        assert resp.status_code == 200
        data = _json(resp)
        assert "indices" in data and len(data["indices"]) == 2
        assert data["indices"][0]["code"] == "000001"

    def test_market_indices_empty_when_fetch_fails(self, flask_client, monkeypatch):
        from app.web import web_server
        monkeypatch.setattr(web_server, "_fetch_market_indices_data",
                            lambda: {"indices": []})
        resp = flask_client.get("/api/market_indices")
        assert resp.status_code == 200
        data = _json(resp)
        # B2-4: 响应现在含 meta.data_quality 字段，只验证核心字段
        assert data["indices"] == []
        assert "data_quality" in data.get("meta", {})

    def test_market_indices_timeout_returns_degraded_without_waiting_worker(self, flask_client, monkeypatch):
        from app.web import web_server

        monkeypatch.setenv("INDEX_FAST_TIMEOUT_MS", "50")

        def slow_fetch():
            time.sleep(1.0)
            return {"indices": [{"code": "000001"}], "source": "slow"}

        monkeypatch.setattr(web_server, "_fetch_market_indices_data", slow_fetch)

        start = time.perf_counter()
        resp = flask_client.get("/api/market_indices")
        elapsed = time.perf_counter() - start

        assert elapsed < 0.5
        assert resp.status_code == 503
        data = _json(resp)
        assert data["success"] is False
        assert data["error_code"] == "DEGRADED"


# --------------------------------------------------------------------------- #
# 6. GET /api/latest_news
# --------------------------------------------------------------------------- #

class TestLatestNewsRoute:
    def test_happy_path(self, flask_client, monkeypatch):
        from app.web import web_server
        fake_news = [
            {"title": "央行降准", "content": "重磅利好", "ts": "2025-12-30 10:00"},
            {"title": "美联储加息", "content": "市场风险加剧", "ts": "2025-12-30 09:00"},
        ]
        monkeypatch.setattr(web_server.news_fetcher, "get_latest_news",
                            lambda days=1, limit=1000: list(fake_news))
        resp = flask_client.get("/api/latest_news?days=1&limit=10")
        assert resp.status_code == 200
        data = _json(resp)
        assert data["success"] is True
        assert isinstance(data["news"], list)
        assert len(data["news"]) == 2

    def test_important_filter(self, flask_client, monkeypatch):
        from app.web import web_server
        fake_news = [
            {"title": "央行降准", "content": "重磅利好"},
            {"title": "普通公告", "content": "无关紧要的内容"},
        ]
        monkeypatch.setattr(web_server.news_fetcher, "get_latest_news",
                            lambda days=1, limit=1000: list(fake_news))
        resp = flask_client.get("/api/latest_news?days=1&important=1")
        assert resp.status_code == 200
        data = _json(resp)
        assert data["success"] is True
        # 仅保留含 "重要/利好/重磅/突发/关注" 的条目
        assert len(data["news"]) == 1
        assert data["news"][0]["title"] == "央行降准"

    def test_invalid_days_does_not_500(self, flask_client, monkeypatch):
        """S2-A1：非法 days 参数由 validate_int_range 捕获，返回 400 INVALID_INPUT（不再 500）。"""
        from app.web import web_server
        monkeypatch.setattr(web_server.news_fetcher, "get_latest_news",
                            lambda days=1, limit=1000: [])
        resp = flask_client.get("/api/latest_news?days=abc")
        # S2-A1 改进：非整数 days → 400 而非 500
        assert resp.status_code == 400
        data = _json(resp)
        assert data["success"] is False
        _no_stacktrace(resp)


# --------------------------------------------------------------------------- #
# 7. GET /api/news_sentiment
# --------------------------------------------------------------------------- #

class TestNewsSentimentRoute:
    def test_happy_path_classifies_bullish_bearish(self, flask_client, monkeypatch):
        from app.web import web_server
        fake_news = [
            {"title": "公司业绩超预期", "content": "盈利大幅增长"},
            {"title": "黑天鹅利空", "content": "暴跌风险加剧"},
            {"title": "公告", "content": "正常运营"},
        ]
        monkeypatch.setattr(web_server.news_fetcher, "get_latest_news",
                            lambda days=1: list(fake_news))
        resp = flask_client.get("/api/news_sentiment?days=1")
        assert resp.status_code == 200
        data = _json(resp)
        assert data["total"] == 3
        assert data["bullish"] == 1
        assert data["bearish"] == 1
        assert data["neutral"] == 1
        assert 1.0 <= data["score"] <= 10.0

    def test_empty_news_returns_neutral_default(self, flask_client, monkeypatch):
        from app.web import web_server
        monkeypatch.setattr(web_server.news_fetcher, "get_latest_news",
                            lambda days=1: [])
        resp = flask_client.get("/api/news_sentiment")
        assert resp.status_code == 200
        data = _json(resp)
        assert data["total"] == 0
        assert data["score"] == 5.0


# --------------------------------------------------------------------------- #
# 8. POST /api/north_flow_history
# --------------------------------------------------------------------------- #

class TestNorthFlowHistoryRoute:
    def test_missing_stock_code_returns_400(self, flask_client):
        resp = flask_client.post("/api/north_flow_history", json={"days": 10})
        assert resp.status_code == 400
        data = _json(resp)
        assert _has_error(data) and "股票代码" in _get_error_msg(data)
        _no_stacktrace(resp)

    def test_happy_path(self, flask_client, monkeypatch):
        from app.web import web_server
        fake = {"history": [
            {"date": "2025-12-29", "net_amount": 1000.0},
            {"date": "2025-12-30", "net_amount": -500.0},
        ]}

        class _FakeAnalyzer:
            def get_north_flow_history(self, code, sd, ed):
                return fake

        monkeypatch.setattr(web_server, "CapitalFlowAnalyzer", lambda: _FakeAnalyzer())
        resp = flask_client.post("/api/north_flow_history",
                                  json={"stock_code": "600000", "days": 5})
        assert resp.status_code == 200, resp.data[:300]
        data = _json(resp)
        assert "history" in data and len(data["history"]) == 2


# --------------------------------------------------------------------------- #
# 9. GET /search_us_stocks
# --------------------------------------------------------------------------- #

class TestSearchUsStocksRoute:
    def test_missing_keyword_returns_400(self, flask_client):
        resp = flask_client.get("/search_us_stocks")
        assert resp.status_code == 400
        data = _json(resp)
        assert _has_error(data) and "搜索关键词" in _get_error_msg(data)
        _no_stacktrace(resp)

    def test_happy_path(self, flask_client, monkeypatch):
        from app.web import web_server
        fake_results = [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "AMZN", "name": "Amazon.com Inc."},
        ]
        monkeypatch.setattr(web_server.us_stock_service, "search_us_stocks",
                            lambda kw: list(fake_results))
        resp = flask_client.get("/search_us_stocks?keyword=a")
        assert resp.status_code == 200
        data = _json(resp)
        assert data["results"][0]["symbol"] == "AAPL"
        assert len(data["results"]) == 2

    def test_upstream_exception_returns_500_no_stacktrace(self, flask_client, monkeypatch):
        from app.web import web_server

        def _boom(kw):
            raise RuntimeError("upstream timeout")

        monkeypatch.setattr(web_server.us_stock_service, "search_us_stocks", _boom)
        resp = flask_client.get("/search_us_stocks?keyword=a")
        assert resp.status_code == 500
        data = _json(resp)
        assert _has_error(data)
        _no_stacktrace(resp)
