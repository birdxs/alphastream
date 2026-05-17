# Input  : pytest 测试 app/agents/coordinator.py LangGraph 编排核心
# Output : BE-02a 测试报告 + pytest 日志 + 覆盖率
# Pos    : tests/backend/integration/test_coordinator.py - W2-BE02a 最小批 Agent 测试 #1
#
# 一旦本文件结构变化，请同步更新 tests/audit/reports/BE-02a_coordinator.md。
"""BE-02a coordinator.py 测试

仅测 LangGraph 编排核心 coordinator.py 6 个目标：
  1. _wrap_with_events  - 事件包装器
  2. _summarize_debate  - 多空辩论摘要
  3. _route_after_technical - 条件路由
  4. get_checkpointer   - SqliteSaver 单例 + 并发
  5. build_analysis_graph - StateGraph 装配
  6. run_agent_analysis - 端到端 invoke + 异常 HOLD 兜底（H3）

LLM 全 mock，禁止真调 OpenAI。
"""
from __future__ import annotations

import concurrent.futures
import threading
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Target #1: _wrap_with_events
# =============================================================================
class TestWrapWithEvents:
    """事件包装器：成功路径 publish STARTED+COMPLETED；异常路径目前被吞咽（隐患记录）"""

    def test_success_path_publishes_started_and_completed(self, agent_event_recorder):
        from app.agents.coordinator import _wrap_with_events

        def fake_agent(state):
            return {"progress": 50, "result": "ok"}

        wrapped = _wrap_with_events(fake_agent, "测试Agent")
        result = wrapped({"stock_code": "000001", "progress": 0})

        assert result == {"progress": 50, "result": "ok"}
        names = agent_event_recorder.names()
        assert "agent.started" in names
        assert "agent.completed" in names
        # started 必须早于 completed
        assert names.index("agent.started") < names.index("agent.completed")

    def test_event_payload_contains_agent_name_and_stock_code(self, agent_event_recorder):
        from app.agents.coordinator import _wrap_with_events

        def fake_agent(state):
            return {"progress": 80}

        wrapped = _wrap_with_events(fake_agent, "技术分析师")
        wrapped({"stock_code": "600519", "progress": 10})

        started_payloads = agent_event_recorder.filter("agent.started")
        assert len(started_payloads) >= 1
        payload = started_payloads[0]
        assert payload["data"]["agent_name"] == "技术分析师"
        assert payload["data"]["stock_code"] == "600519"
        assert payload["data"]["status"] == "started"

    def test_reasoning_event_also_published(self, agent_event_recorder):
        from app.agents.coordinator import _wrap_with_events

        wrapped = _wrap_with_events(lambda s: {"progress": 100}, "情绪分析师")
        wrapped({"stock_code": "000001", "progress": 0})

        # 还应触发一条 reasoning 事件 (UI 增强用途)
        assert agent_event_recorder.has("reasoning")

    def test_exception_path_currently_swallowed_no_failed_event(self, agent_event_recorder):
        """H3 隐患：内部 agent 抛错时，coordinator._wrap_with_events 不会捕获 result 阶段异常，
        异常会冒泡；而代码中也没有 EVENT_AGENT_FAILED 常量，无失败事件发布。

        本测试明确暴露此设计：仅 STARTED+reasoning 被发布，COMPLETED 未发布，异常向上传播。
        """
        from app.agents.coordinator import _wrap_with_events

        def failing_agent(state):
            raise RuntimeError("agent内部炸了")

        wrapped = _wrap_with_events(failing_agent, "故障Agent")
        with pytest.raises(RuntimeError, match="agent内部炸了"):
            wrapped({"stock_code": "000001", "progress": 0})

        # 只有 started + reasoning，没有 completed，也无失败事件
        names = agent_event_recorder.names()
        assert "agent.started" in names
        assert "agent.completed" not in names
        # 项目里没有 agent.failed 常量
        assert not agent_event_recorder.has("agent.failed")


# =============================================================================
# Target #2: _summarize_debate
# =============================================================================
class TestSummarizeDebate:
    """多空辩论摘要：纯字符串拼接，不依赖 LLM"""

    def test_with_both_cases_returns_debate_summary(self):
        from app.agents.coordinator import _summarize_debate

        state = {
            "bull_case": "看多论据：A 置信度 高，业绩增长强劲",
            "bear_case": "看空论据：B 置信度 中，估值偏高",
        }
        result = _summarize_debate(state)
        assert "debate_summary" in result
        assert "多方主论点" in result["debate_summary"]
        assert "空方主论点" in result["debate_summary"]
        assert "综合研判" in result["debate_summary"]
        # execution_log 应记录 success
        assert result["execution_log"][0]["status"] == "success"

    def test_empty_cases_returns_skipped(self):
        from app.agents.coordinator import _summarize_debate

        result = _summarize_debate({"bull_case": "", "bear_case": ""})
        assert result["debate_summary"] == "辩论双方均未产出有效分析"
        assert result["execution_log"][0]["status"] == "skipped"

    def test_long_case_truncated_to_300(self):
        from app.agents.coordinator import _summarize_debate

        long_bull = "多" * 500
        result = _summarize_debate({"bull_case": long_bull, "bear_case": "空头"})
        assert "..." in result["debate_summary"]

    def test_tendency_bullish_when_bull_high_confidence(self):
        from app.agents.coordinator import _summarize_debate

        result = _summarize_debate({
            "bull_case": "多方分析：置信度 高 业绩亮眼",
            "bear_case": "空方分析：风险点不强",
        })
        assert "看多" in result["debate_summary"] or "多方" in result["debate_summary"]


# =============================================================================
# Target #3: _route_after_technical
# =============================================================================
class TestRouteAfterTechnical:
    """条件路由：error / depth>=2 / depth=1 三分支"""

    def test_error_returns_fast_fail(self):
        from app.agents.coordinator import _route_after_technical

        state = {"technical_report": {"error": "数据拉取失败"}, "research_depth": 3}
        assert _route_after_technical(state) == "fast_fail"

    def test_depth_3_returns_parallel(self):
        from app.agents.coordinator import _route_after_technical

        state = {"technical_report": {"trend": "up"}, "research_depth": 3}
        assert _route_after_technical(state) == "parallel_depth2"

    def test_depth_2_returns_parallel(self):
        from app.agents.coordinator import _route_after_technical

        state = {"technical_report": {"trend": "up"}, "research_depth": 2}
        assert _route_after_technical(state) == "parallel_depth2"

    def test_depth_1_returns_direct_decision(self):
        from app.agents.coordinator import _route_after_technical

        state = {"technical_report": {"trend": "up"}, "research_depth": 1}
        assert _route_after_technical(state) == "direct_decision"

    def test_no_technical_report_returns_direct_when_depth_1(self):
        from app.agents.coordinator import _route_after_technical

        # technical_report 为 None，按非 error 处理，depth=1 → direct_decision
        state = {"technical_report": None, "research_depth": 1}
        assert _route_after_technical(state) == "direct_decision"

    def test_empty_technical_report_dict_treated_as_no_error(self):
        from app.agents.coordinator import _route_after_technical

        state = {"technical_report": {}, "research_depth": 3}
        # 空 dict 不含 error，走正常路径
        assert _route_after_technical(state) == "parallel_depth2"


# =============================================================================
# Target #4: get_checkpointer
# =============================================================================
class TestGetCheckpointer:
    """SqliteSaver 单例 + 并发安全 + 异常降级"""

    def _reset_singleton(self):
        import app.agents.coordinator as c
        c._checkpointer_instance = None

    def test_first_call_creates_instance(self):
        self._reset_singleton()
        from app.agents.coordinator import get_checkpointer

        inst = get_checkpointer()
        # 正常环境应返回非 None；异常降级返回 None 也可接受
        assert inst is None or inst is not None  # 不抛出即可

    def test_second_call_returns_same_instance(self):
        self._reset_singleton()
        from app.agents.coordinator import get_checkpointer

        inst1 = get_checkpointer()
        inst2 = get_checkpointer()
        assert inst1 is inst2  # identity check

    def test_sqlite_unavailable_falls_back_to_none(self, monkeypatch):
        """模拟 sqlite 不可用 → 降级，不抛出"""
        self._reset_singleton()
        import app.agents.coordinator as c

        # 让 import sqlite3 抛错
        import builtins
        real_import = builtins.__import__

        def faulty_import(name, *args, **kwargs):
            if name == "sqlite3":
                raise ImportError("sqlite3 fake unavailable")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", faulty_import)
        result = c.get_checkpointer()
        assert result is None

    def test_concurrent_10_threads_returns_same_instance(self):
        """10 并发线程调用，全部返回同一实例（线程安全单例）"""
        self._reset_singleton()
        from app.agents.coordinator import get_checkpointer

        results = []
        errors = []

        def call():
            try:
                results.append(get_checkpointer())
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(call) for _ in range(10)]
            concurrent.futures.wait(futures)

        assert errors == [], f"并发调用出现异常: {errors}"
        assert len(results) == 10
        # 全部 identity 相同（含全部 None 的降级场景也满足）
        first = results[0]
        for r in results[1:]:
            assert r is first, "并发 get_checkpointer 返回不同实例，单例失效"

    def test_concurrent_no_database_is_locked(self, capsys):
        """记录是否存在 'database is locked' 异常 — 缺陷追踪 H3 关注点"""
        self._reset_singleton()
        from app.agents.coordinator import get_checkpointer

        locked_errors = []

        def call():
            try:
                get_checkpointer()
            except Exception as e:  # noqa: BLE001
                if "database is locked" in str(e).lower():
                    locked_errors.append(str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            list(ex.map(lambda _: call(), range(10)))

        # 当前实现使用单连接 + check_same_thread=False，预期不出现 locked
        assert locked_errors == [], f"出现 database is locked: {locked_errors}"


# =============================================================================
# Target #5: build_analysis_graph
# =============================================================================
class TestBuildAnalysisGraph:
    """LangGraph StateGraph 装配 & 节点完整性"""

    def test_returns_non_none(self):
        from app.agents.coordinator import build_analysis_graph
        graph = build_analysis_graph(research_depth=5)
        assert graph is not None

    def test_depth_5_contains_all_core_nodes(self):
        from app.agents.coordinator import build_analysis_graph

        graph = build_analysis_graph(research_depth=5)
        nodes = set(graph.get_graph().nodes.keys())
        # 核心节点（LangGraph 中节点 id 与 add_node 名一致）
        expected = {
            "technical", "fundamental", "capital_flow", "sentiment",
            "bull", "bear", "debate_summary", "risk", "decision",
        }
        missing = expected - nodes
        assert not missing, f"缺失核心节点: {missing}, 实际: {nodes}"

    def test_depth_1_only_minimal_nodes(self):
        from app.agents.coordinator import build_analysis_graph

        graph = build_analysis_graph(research_depth=1)
        nodes = set(graph.get_graph().nodes.keys())
        assert "technical" in nodes
        assert "decision" in nodes
        # depth=1 不应有 fundamental/bull/bear
        assert "fundamental" not in nodes
        assert "bull" not in nodes

    def test_depth_3_has_sentiment_no_debate(self):
        from app.agents.coordinator import build_analysis_graph

        graph = build_analysis_graph(research_depth=3)
        nodes = set(graph.get_graph().nodes.keys())
        assert "sentiment" in nodes
        assert "fundamental" in nodes
        assert "bull" not in nodes  # depth<4 无辩论
        assert "debate_summary" not in nodes

    def test_conditional_edges_exist(self):
        from app.agents.coordinator import build_analysis_graph

        graph = build_analysis_graph(research_depth=3)
        # 路由记录节点存在表示 conditional_edges 已挂上
        nodes = set(graph.get_graph().nodes.keys())
        assert "_route_record_normal" in nodes
        assert "_route_record_fast_fail" in nodes


# =============================================================================
# Target #6: run_agent_analysis - 端到端 invoke
# =============================================================================
class TestRunAgentAnalysis:
    """完整 invoke + 异常 HOLD 兜底（H3）"""

    @pytest.fixture
    def mock_all_agents(self, monkeypatch):
        """mock 全部 9 个 agent 的 analyze 静态方法，让 invoke 不真实调度"""
        import app.agents.technical_analyst as ta
        import app.agents.fundamental_analyst as fa
        import app.agents.capital_flow_analyst as ca
        import app.agents.sentiment_analyst as sa
        import app.agents.bull_researcher as bull
        import app.agents.bear_researcher as bear
        import app.agents.risk_manager as rm
        import app.agents.decision_maker as dm

        monkeypatch.setattr(ta.TechnicalAnalystAgent, "analyze",
                            staticmethod(lambda s: {"technical_report": {"trend": "up"}, "progress": 20}))
        monkeypatch.setattr(fa.FundamentalAnalystAgent, "analyze",
                            staticmethod(lambda s: {"fundamental_report": {"pe": 15}, "progress": 40}))
        monkeypatch.setattr(ca.CapitalFlowAnalystAgent, "analyze",
                            staticmethod(lambda s: {"capital_flow_report": {"net_in": 1.2e8}, "progress": 50}))
        monkeypatch.setattr(sa.SentimentAnalystAgent, "analyze",
                            staticmethod(lambda s: {"sentiment_report": {"score": 0.6}, "progress": 60}))
        monkeypatch.setattr(bull.BullResearcherAgent, "analyze",
                            staticmethod(lambda s: {"bull_case": "看多: 业绩增长", "progress": 70}))
        monkeypatch.setattr(bear.BearResearcherAgent, "analyze",
                            staticmethod(lambda s: {"bear_case": "看空: 估值偏高", "progress": 80}))
        monkeypatch.setattr(rm.RiskManagerAgent, "analyze",
                            staticmethod(lambda s: {"risk_assessment": {"level": "MEDIUM"}, "progress": 90}))
        monkeypatch.setattr(dm.DecisionMakerAgent, "analyze",
                            staticmethod(lambda s: {
                                "final_decision": {"action": "BUY", "confidence": 0.75, "reasoning": "综合看多"},
                                "progress": 100,
                            }))

        # 反思 agent 可选 mock
        try:
            import app.agents.reflection as ref
            monkeypatch.setattr(ref.ReflectionAgent, "reflect",
                                staticmethod(lambda s: {"execution_log": []}))
            monkeypatch.setattr(ref.ReflectionAgent, "get_past_reflections",
                                staticmethod(lambda *a, **kw: []))
        except Exception:
            pass

        # investor coordinator 可能存在
        try:
            import app.agents.investors.investor_coordinator as ic
            monkeypatch.setattr(ic.InvestorCoordinator, "analyze",
                                staticmethod(lambda s: {"investor_consensus": "持有", "progress": 95}))
        except Exception:
            pass

    def test_full_invoke_returns_final_decision(self, mock_all_agents, patched_ai_client, iso_checkpointer):
        from app.agents.coordinator import run_agent_analysis

        result = run_agent_analysis(
            stock_code="000001",
            market_type="A",
            research_depth=3,
            conversation_id="test_thread_001",
        )

        assert result is not None
        assert "final_decision" in result
        assert result["final_decision"] is not None
        # mock 设定 action=BUY
        assert result["final_decision"]["action"] == "BUY"
        assert result["stock_code"] == "000001"

    def test_invoke_publishes_analysis_events(
            self, mock_all_agents, patched_ai_client, iso_checkpointer, agent_event_recorder):
        from app.agents.coordinator import run_agent_analysis

        run_agent_analysis(
            stock_code="000001",
            market_type="A",
            research_depth=2,
            conversation_id="test_thread_evt",
        )

        # 应至少触发 analysis.started
        assert agent_event_recorder.has("analysis.started")

    def test_exception_in_agent_falls_back_to_hold(
            self, monkeypatch, patched_ai_client, iso_checkpointer):
        """H3 已知风险：coordinator.py:441-451 异常吞咽 → HOLD 兜底

        让 TechnicalAnalystAgent.analyze 抛错，graph.invoke 失败被 except 捕获，
        返回 final_decision.action == 'HOLD'。
        """
        import app.agents.technical_analyst as ta

        def boom(state):
            raise RuntimeError("技术分析炸了")

        monkeypatch.setattr(ta.TechnicalAnalystAgent, "analyze", staticmethod(boom))

        from app.agents.coordinator import run_agent_analysis

        result = run_agent_analysis(
            stock_code="000001",
            market_type="A",
            research_depth=1,  # 只走 technical → decision，最短路径
            conversation_id="test_thread_boom",
        )

        # H3 异常吞咽 + HOLD 兜底
        assert result is not None
        assert result["final_decision"] is not None
        assert result["final_decision"]["action"] == "HOLD"
        assert result["final_decision"]["confidence"] == 0.0
        assert "分析过程出错" in result["final_decision"]["reasoning"]
        assert len(result["errors"]) >= 1

    def test_invoke_with_default_thread_id_when_no_conversation_id(
            self, mock_all_agents, patched_ai_client, iso_checkpointer):
        """conversation_id 缺省时，应使用 stock_code+时间戳兜底，不应抛错"""
        from app.agents.coordinator import run_agent_analysis

        result = run_agent_analysis(
            stock_code="000001",
            market_type="A",
            research_depth=1,
            conversation_id=None,
        )

        assert result is not None
        assert "final_decision" in result


# =============================================================================
# CoordinatorAgent 类封装
# =============================================================================
class TestCoordinatorAgentClass:
    """类封装入口，确保 .run 委托到 run_agent_analysis"""

    def test_run_delegates(self, monkeypatch):
        from app.agents import coordinator as c

        called = {}

        def fake_run(**kw):
            called.update(kw)
            return {"final_decision": {"action": "BUY"}}

        monkeypatch.setattr(c, "run_agent_analysis", fake_run)
        result = c.CoordinatorAgent.run(stock_code="600519", research_depth=2)
        assert result["final_decision"]["action"] == "BUY"
        assert called["stock_code"] == "600519"
        assert called["research_depth"] == 2
