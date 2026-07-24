"""
Input: 各分析模块的方法调用、OpenAI Function Calling工具调用请求；可选请求级 portfolio_snapshot（ContextVar）
Output: LangChain @tool 包装的标准工具函数 + OpenAI Function Calling格式schema + 工具执行分发
Pos: app/core/tools.py - 所有Agent共享的工具函数注册表；execute_tool 挂 P0-1 护栏 + P0-2 写工具硬拦；Sprint2 持仓只读；Sprint4 写仓提案闸门；Sprint4+ plan_dag/skill stub

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
from __future__ import annotations

import json
import logging
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterator, List, Optional

from langchain_core.tools import tool
from app.core.data_provider import get_data_provider

logger = logging.getLogger(__name__)

# Sprint2：请求级持仓上下文（前端 body.portfolio_snapshot → chat 路由 set → 工具读）
# 禁止在工具内编造持仓；无上下文时返回明确空结构。
_portfolio_ctx: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "portfolio_snapshot_ctx", default=None
)
_ASIA_SHANGHAI = timezone(timedelta(hours=8))


def _now_cn_iso() -> str:
    return datetime.now(_ASIA_SHANGHAI).isoformat()


def set_portfolio_context(snapshot: Optional[Dict[str, Any]]) -> None:
    """绑定当前请求/turn 的持仓快照（应在 reset 前 set）。"""
    _portfolio_ctx.set(snapshot if isinstance(snapshot, dict) else None)


def get_portfolio_context() -> Optional[Dict[str, Any]]:
    return _portfolio_ctx.get()


def clear_portfolio_context() -> None:
    _portfolio_ctx.set(None)


@contextmanager
def portfolio_context(snapshot: Optional[Dict[str, Any]]) -> Iterator[None]:
    """with portfolio_context(snap): 自动清理。"""
    token = _portfolio_ctx.set(snapshot if isinstance(snapshot, dict) else None)
    try:
        yield
    finally:
        _portfolio_ctx.reset(token)


def normalize_portfolio_snapshot(raw: Any) -> Dict[str, Any]:
    """
    规范化前端/API 传入的持仓快照。
    - 无假持仓：非法项丢弃；name 等于 code 时 name 置空串
    - 返回结构恒含 holdings(list)/source(str)/as_of(str)
    """
    as_of = _now_cn_iso()
    if raw is None:
        return {"holdings": [], "source": "none", "as_of": as_of}
    if not isinstance(raw, dict):
        return {"holdings": [], "source": "invalid", "as_of": as_of}

    src = raw.get("source") or "client"
    if not isinstance(src, str) or not src.strip():
        src = "client"
    if isinstance(raw.get("as_of"), str) and raw.get("as_of").strip():
        as_of = raw["as_of"].strip()

    items = raw.get("holdings")
    if items is None and isinstance(raw.get("positions"), list):
        items = raw.get("positions")
    if not isinstance(items, list):
        return {"holdings": [], "source": src, "as_of": as_of}

    holdings: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        code = (
            it.get("code")
            or it.get("stock_code")
            or it.get("symbol")
            or ""
        )
        if not isinstance(code, str):
            code = str(code) if code is not None else ""
        code = code.strip()
        if not code or len(code) > 20:
            continue
        name = it.get("name")
        if not isinstance(name, str):
            name = ""
        name = name.strip()
        # 铁律 #1：禁止把 code 当 name
        if name == code:
            name = ""
        weight = it.get("weight")
        try:
            weight_f = float(weight) if weight is not None else None
        except (TypeError, ValueError):
            weight_f = None
        shares = it.get("shares")
        try:
            shares_f = float(shares) if shares is not None else None
        except (TypeError, ValueError):
            shares_f = None
        cost = it.get("cost")
        if cost is None:
            cost = it.get("avg_cost")
        try:
            cost_f = float(cost) if cost is not None else None
        except (TypeError, ValueError):
            cost_f = None
        market_type = it.get("market_type") or it.get("market") or "A"
        if not isinstance(market_type, str):
            market_type = "A"
        market_type = market_type.strip().upper()[:10] or "A"
        row: Dict[str, Any] = {
            "code": code,
            "name": name,
            "market_type": market_type,
        }
        if weight_f is not None:
            row["weight"] = weight_f
        if shares_f is not None:
            row["shares"] = shares_f
        if cost_f is not None:
            row["cost"] = cost_f
        holdings.append(row)

    return {"holdings": holdings, "source": src, "as_of": as_of}


# === 数据获取工具 ===

@tool
def get_stock_data(stock_code: str, market_type: str = 'A', days: int = 120) -> str:
    """获取股票历史K线数据，返回最近N天的OHLCV数据摘要"""
    from datetime import datetime, timezone, timedelta
    _tz = timezone(timedelta(hours=8))
    dp = get_data_provider()
    end_date = datetime.now(_tz).strftime('%Y%m%d')
    start_date = (datetime.now(_tz) - timedelta(days=days)).strftime('%Y%m%d')
    try:
        df = dp.get_stock_history(stock_code, start_date, end_date)
        if df is None or df.empty:
            return f"未获取到{stock_code}的数据"
        latest = df.iloc[-1]
        summary = (
            f"股票{stock_code} 最新数据({df['date'].iloc[-1]}):\n"
            f"收盘价: {latest.get('close', 'N/A')}\n"
            f"最高价: {latest.get('high', 'N/A')}\n"
            f"最低价: {latest.get('low', 'N/A')}\n"
            f"成交量: {latest.get('volume', 'N/A')}\n"
            f"数据范围: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}, 共{len(df)}条"
        )
        return summary
    except Exception as e:
        return f"获取数据失败: {str(e)}"


@tool
def get_technical_indicators(stock_code: str, market_type: str = 'A') -> str:
    """计算股票技术指标(MA/RSI/MACD/布林带等)并返回摘要"""
    from app.analysis.stock_analyzer import StockAnalyzer
    try:
        analyzer = StockAnalyzer()
        result = analyzer.quick_analyze_stock(stock_code, market_type)
        if 'error' in result:
            return f"技术分析失败: {result['error']}"
        return str(result)
    except Exception as e:
        return f"技术分析失败: {str(e)}"


@tool
def get_fundamental_data(stock_code: str) -> str:
    """获取股票基本面数据(PE/PB/ROE/净利润等财务指标)"""
    from app.analysis.fundamental_analyzer import FundamentalAnalyzer
    # P2a：Wind 优先源——需请求级 use_wind=true（或 WIND_USE_DEFAULT）+ 已配 key + 非空结果；
    # 否则静默回落 FundamentalAnalyzer。不改工具签名与返回契约。
    try:
        from app.adapters.wind_adapter import WindAdapter, is_use_wind_enabled
        if is_use_wind_enabled():
            _wind = WindAdapter()
            if _wind.health_check():  # 仅查 key，不连网
                _wind_data = _wind.get_financial_data(stock_code)
                if _wind_data:
                    return str(_wind_data)
    except Exception:
        pass  # Wind 任何异常都不影响原路径
    try:
        fa = FundamentalAnalyzer()
        result = fa.get_financial_indicators(stock_code)
        if not result:
            return f"未获取到{stock_code}的基本面数据"
        return str(result)
    except Exception as e:
        return f"基本面数据获取失败: {str(e)}"


@tool
def get_capital_flow(stock_code: str) -> str:
    """获取股票资金流向数据(主力/北向/机构资金)"""
    from app.analysis.capital_flow_analyzer import CapitalFlowAnalyzer
    try:
        cfa = CapitalFlowAnalyzer()
        result = cfa.get_individual_fund_flow(stock_code)
        if not result:
            return f"未获取到{stock_code}的资金流向数据"
        return str(result)
    except Exception as e:
        return f"资金流向获取失败: {str(e)}"


@tool
def get_stock_news(stock_code: str, limit: int = 5) -> str:
    """获取股票相关的最新新闻和舆情信息"""
    from app.analysis.news_fetcher import news_fetcher
    try:
        news = news_fetcher.get_latest_news(days=1, limit=limit)
        if not news:
            return "暂无最新新闻"
        result = []
        for item in news[:limit]:
            result.append(f"[{item.get('time', '')}] {item.get('content', '')[:100]}")
        return '\n'.join(result)
    except Exception as e:
        return f"新闻获取失败: {str(e)}"


@tool
def search_web_tool(query: str, max_results: int = 5, engine: str = "auto") -> str:
    """搜索互联网获取最新信息。

    支持17种引擎(engine参数):
      - 'auto' 默认走 fallback 链: duckduckgo→baidu→bing_cn→sogou→so360→wechat→brave
      - 中文域: 'baidu' / 'sogou' / 'so360' / 'wechat' / 'toutiao' / 'bing_cn' / 'jisilu' / 'zhihu'
      - 全球域: 'duckduckgo' / 'duckduckgo_html' / 'bing' / 'brave' / 'qwant' / 'startpage' / 'ecosia'
      - 知识域: 'wikipedia'(百科事实), 'wolframalpha'(数学/单位/货币换算)
      - 'concurrent' 并发多引擎 + 去重合并
    """
    from app.core.search import search_web
    try:
        results = search_web(query, max_results, engine=engine)
        if not results:
            return "未找到相关搜索结果"
        output = []
        for r in results:
            output.append(f"[{r.get('source', '')}] {r.get('title', '')}: {r.get('content', '')[:150]}")
        return '\n'.join(output)
    except Exception as e:
        return f"搜索失败: {str(e)}"


@tool
def get_risk_assessment(stock_code: str, market_type: str = 'A') -> str:
    """评估股票的多维度风险(波动率/趋势/反转/成交量风险)"""
    from app.analysis.risk_monitor import RiskMonitor
    from app.analysis.stock_analyzer import StockAnalyzer
    try:
        analyzer = StockAnalyzer()
        rm = RiskMonitor(analyzer)
        result = rm.analyze_stock_risk(stock_code, market_type)
        if not result:
            return f"未获取到{stock_code}的风险数据"
        return str(result)
    except Exception as e:
        return f"风险评估失败: {str(e)}"


@tool
def get_portfolio_snapshot() -> str:
    """读取当前用户真实持仓快照（只读）。

    数据来自请求上下文 portfolio_snapshot（前端 portfolio-store 真值注入）。
    无持仓时返回明确空结构 holdings=[]，绝不编造持仓或权重。
    """
    snap = normalize_portfolio_snapshot(get_portfolio_context())
    payload = {
        "holdings": snap.get("holdings") or [],
        "source": snap.get("source") or "none",
        "as_of": snap.get("as_of") or _now_cn_iso(),
        "count": len(snap.get("holdings") or []),
        "empty": not bool(snap.get("holdings")),
    }
    if payload["empty"]:
        payload["message"] = "当前无持仓快照；请用户在组合页维护持仓，或于对话附带 portfolio_snapshot。"
    return json.dumps(payload, ensure_ascii=False)


def _structural_portfolio_risk(holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """仅基于权重的结构摘要（可离线、不造假市价风险分）。"""
    if not holdings:
        return {
            "mode": "structural",
            "empty": True,
            "message": "持仓为空，无风险结构可汇总",
            "count": 0,
        }
    weights = []
    for h in holdings:
        w = h.get("weight")
        if w is None:
            continue
        try:
            wf = float(w)
        except (TypeError, ValueError):
            continue
        if wf < 0:
            continue
        weights.append((h.get("code") or "", h.get("name") or "", wf))
    n = len(holdings)
    if not weights:
        return {
            "mode": "structural",
            "empty": False,
            "count": n,
            "weight_sum": None,
            "message": "持仓存在但无可用 weight 字段；仅返回 count，不发明权重",
        }
    w_sum = sum(w for _, _, w in weights)
    # 归一用于集中度（若 sum≈0 则跳过 HHI）
    max_item = max(weights, key=lambda x: x[2])
    hhi = None
    top_share = None
    if w_sum > 0:
        norms = [w / w_sum for _, _, w in weights]
        hhi = sum(x * x for x in norms)
        top_share = max_item[2] / w_sum
    # Sprint3：在只读结构摘要中附带组合诊断（行业未知=unknown，不造假）
    diagnosis = None
    try:
        from app.analysis.risk_monitor import build_portfolio_diagnosis
        diagnosis_entries = []
        for h in holdings:
            diagnosis_entries.append({
                "stock_code": h.get("code") or h.get("stock_code") or "",
                "stock_name": h.get("name") or h.get("stock_name") or "",
                "weight": h.get("weight"),
                "industry": h.get("industry") or h.get("sector"),
            })
        diagnosis = build_portfolio_diagnosis(diagnosis_entries)
    except Exception:
        diagnosis = None
    out = {
        "mode": "structural",
        "empty": False,
        "count": n,
        "weighted_names_count": len(weights),
        "weight_sum": w_sum,
        "max_weight_code": max_item[0],
        "max_weight_name": max_item[1],
        "max_weight": max_item[2],
        "top_weight_share": top_share,
        "hhi": hhi,
        "message": "结构摘要来自用户 weight 真值；未调用行情接口，不产生假风险分",
    }
    if diagnosis is not None:
        out["sector_concentration"] = diagnosis.get("sector_concentration")
        out["name_overlap"] = diagnosis.get("name_overlap")
        out["defensive_weight"] = diagnosis.get("defensive_weight")
        out["unknown_industry_share"] = diagnosis.get("unknown_industry_share")
        out["diagnosis"] = diagnosis
    return out


@tool
def get_portfolio_risk_summary(include_market_risk: bool = False) -> str:
    """基于真实持仓快照的组合风险结构摘要（只读）。

    默认仅做权重结构摘要（离线安全、零假数）。
    include_market_risk=true 且未 DISABLE_NETWORK 时，才尝试调用 RiskMonitor.analyze_portfolio_risk；
    上游失败则降级为结构摘要并标明 degraded，不编造风险分。
    """
    snap = normalize_portfolio_snapshot(get_portfolio_context())
    holdings = list(snap.get("holdings") or [])
    base = {
        "source": snap.get("source") or "none",
        "as_of": snap.get("as_of") or _now_cn_iso(),
        "structural": _structural_portfolio_risk(holdings),
        "market_risk": None,
        "degraded": False,
    }
    if not holdings:
        base["message"] = "无持仓，跳过市场风险分析"
        return json.dumps(base, ensure_ascii=False)

    if not include_market_risk:
        base["message"] = "仅结构摘要；如需市价风险分析请设 include_market_risk=true"
        return json.dumps(base, ensure_ascii=False)

    if os.environ.get("DISABLE_NETWORK", "").strip() in ("1", "true", "True", "YES", "yes"):
        base["degraded"] = True
        base["message"] = "DISABLE_NETWORK=1，跳过市场风险分析，仅返回结构摘要"
        return json.dumps(base, ensure_ascii=False)

    try:
        from app.analysis.risk_monitor import RiskMonitor
        from app.analysis.stock_analyzer import StockAnalyzer

        portfolio = []
        for h in holdings:
            portfolio.append(
                {
                    "stock_code": h.get("code"),
                    "weight": h.get("weight") if h.get("weight") is not None else 1.0,
                    "market_type": h.get("market_type") or "A",
                }
            )
        rm = RiskMonitor(StockAnalyzer())
        risk = rm.analyze_portfolio_risk(portfolio)
        if isinstance(risk, dict) and risk.get("error"):
            base["degraded"] = True
            base["message"] = f"市场风险分析降级: {risk.get('error')}"
            base["market_risk"] = None
        else:
            base["market_risk"] = risk
            base["message"] = "结构摘要 + 市场风险分析"
    except Exception as e:
        logger.warning("get_portfolio_risk_summary market path failed: %s", e)
        base["degraded"] = True
        base["message"] = f"市场风险分析异常降级: {e}"
        base["market_risk"] = None
    return json.dumps(base, ensure_ascii=False, default=str)


@tool
def propose_portfolio_write(
    action: str,
    code: str = "",
    name: str = "",
    shares: float = None,
    weight: float = None,
    reason: str = "",
    conversation_id: str = "",
) -> str:
    """生成写仓**提案**（Sprint4），不执行真实下单。

    输出 proposal_id + approval_id；必须先审批再 apply_portfolio_proposal。
    禁止解读为「已下单」；broker 恒为 null。
    action: add_holding | remove_holding | update_holding | rebalance | other
    """
    from app.core.write_proposal import get_write_proposal_store

    store = get_write_proposal_store()
    result = store.create_proposal(
        action=action or "",
        code=code or "",
        name=name or "",
        shares=shares,
        weight=weight,
        reason=reason or "",
        conversation_id=conversation_id or "",
        source="agent_tool",
    )
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def apply_portfolio_proposal(
    proposal_id: str,
    approval_id: str = "",
) -> str:
    """在 approval_id 已批准后，本地标记提案 applied（模拟）。

    **无真实券商**；缺 approval / 未 approved → APPROVAL_REQUIRED，executed=false。
    禁止将成功响应理解为交易所成交。
    """
    from app.core.write_proposal import get_write_proposal_store

    store = get_write_proposal_store()
    result = store.apply_proposal(
        proposal_id=(proposal_id or "").strip(),
        approval_id=(approval_id or "").strip(),
    )
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def decide_portfolio_proposal_approval(
    approval_id: str,
    approved: bool = False,
    feedback: str = "",
) -> str:
    """记录写仓提案审批结果（approve/reject），不执行写仓。

    与 POST /api/agent_submit_approval 同键（task_id=approval_id）：
    decide 会清理 HITL pending；submit 会同步 write_proposal.decide_approval。
    """
    from app.core.write_proposal import get_write_proposal_store

    store = get_write_proposal_store()
    result = store.decide_approval(
        (approval_id or "").strip(),
        approved=bool(approved),
        feedback=feedback or "",
    )
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def create_analysis_plan(
    steps: str,
    title: str = "",
    conversation_id: str = "",
    stock_code: str = "",
) -> str:
    """创建轻量分析计划 DAG（串行 steps / depends_on 校验 + 状态机）。

    steps 可为 JSON 数组字符串，如 '["技术面","基本面","风险"]' 或
    '[{"id":"a","name":"技术"},{"id":"b","name":"基本面","depends_on":["a"]}]'。
    仅结构存储，不抓数、不下单。
    """
    from app.core.plan_dag import get_plan_dag_store

    raw = steps
    parsed: Any = steps
    if isinstance(steps, str):
        s = steps.strip()
        if not s:
            return json.dumps(
                {
                    "success": False,
                    "error_code": "EMPTY_STEPS",
                    "message": "steps 不能为空",
                    "plan": None,
                },
                ensure_ascii=False,
            )
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            # 逗号分隔简写
            parsed = [p.strip() for p in s.split(",") if p.strip()]
    if not isinstance(parsed, list):
        return json.dumps(
            {
                "success": False,
                "error_code": "INVALID_STEPS",
                "message": "steps 须为 JSON 数组",
                "plan": None,
            },
            ensure_ascii=False,
        )
    store = get_plan_dag_store()
    result = store.create_plan(
        parsed,
        title=title or "",
        conversation_id=conversation_id or "",
        stock_code=stock_code or "",
        auto_ready=True,
    )
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def get_plan_status(plan_id: str) -> str:
    """查询分析计划状态（steps / topo_order / current_step）。"""
    from app.core.plan_dag import get_plan_dag_store

    store = get_plan_dag_store()
    result = store.get_status((plan_id or "").strip())
    return json.dumps(result, ensure_ascii=False, default=str)

@tool
def list_analysis_plans(limit: int = 20) -> str:
    """列出近期 analysis plan 状态摘要（只读，不抓数）。

    返回 JSON：success / count / plans[{plan_id,title,status,steps_summary,created_at}]。
    进程内 store；不触上游行情。
    """
    import json
    from app.core.plan_dag import get_plan_dag_store

    try:
        lim = int(limit) if limit is not None else 20
    except (TypeError, ValueError):
        lim = 20
    lim = max(1, min(lim, 50))
    store = get_plan_dag_store()
    plans = store.list_plans(limit=lim)
    items = []
    for p in plans:
        steps = p.get("steps") or []
        items.append(
            {
                "plan_id": p.get("plan_id"),
                "title": p.get("title"),
                "status": p.get("status"),
                "current_step_id": p.get("current_step_id"),
                "created_at": p.get("created_at"),
                "updated_at": p.get("updated_at"),
                "steps_summary": {
                    "pending": [s.get("id") for s in steps if s.get("status") == "pending"],
                    "running": [s.get("id") for s in steps if s.get("status") == "running"],
                    "completed": [s.get("id") for s in steps if s.get("status") == "completed"],
                    "failed": [s.get("id") for s in steps if s.get("status") == "failed"],
                },
                "step_count": len(steps),
            }
        )
    return json.dumps(
        {
            "success": True,
            "error_code": None,
            "message": "ok",
            "count": len(items),
            "plans": items,
            "note": "只读 plan 状态；不抓取行情/不改持仓。",
        },
        ensure_ascii=False,
        default=str,
    )



def _offline_or_disabled() -> bool:
    """DISABLE_NETWORK=1 / 离线：facade 不得联网、不得造假数。"""
    return os.environ.get("DISABLE_NETWORK", "").strip() in ("1", "true", "True", "YES", "yes")



@tool
def load_agent_skill(
    skill_id: str,
    stock_code: str = "",
) -> str:
    """加载 Skill stub 的 system_hint（不替代数据 adapters，不拉实时行情）。

    skill_id 示例：risk_checklist / portfolio_readonly / analysis_plan / reflection_hint。
    reflection_hint 可配合 stock_code 读本地 agent_reflections/strategies 片段。
    """
    from app.core.skill_loader import get_skill_loader

    loader = get_skill_loader()
    result = loader.load_skill(
        (skill_id or "").strip(),
        stock_code=(stock_code or "").strip(),
    )
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def list_agent_skills() -> str:
    """列出可用 Skill stub（builtin + data/skills + reflection_hint 入口）。"""
    from app.core.skill_loader import get_skill_loader

    items = get_skill_loader().list_skills()
    return json.dumps(
        {
            "success": True,
            "count": len(items),
            "skills": items,
            "note": "Skills 仅为 system_hint 片段，禁止当作行情数据源",
        },
        ensure_ascii=False,
    )




@tool
def get_market_overview_brief() -> str:
    """大盘/指数只读简报 facade（G9 薄封装）。

    内部复用现有 market indices 路径；失败/离线返回 indices=[] + source，**不编造指数点位**。
    """
    if _offline_or_disabled():
        return json.dumps({
            "indices": [],
            "source": "offline_disabled",
            "note": "DISABLE_NETWORK=1；不拉取行情、不编造指数",
            "count": 0,
            "asof": _now_cn_iso(),
        }, ensure_ascii=False)
    try:
        # 延迟 import，避免 tools ↔ web_server 循环依赖
        from app.web import web_server as ws
        payload = ws._fetch_market_indices_data()
        if not isinstance(payload, dict):
            payload = {}
        indices = payload.get("indices") if isinstance(payload.get("indices"), list) else []
        source = payload.get("source") or ("empty" if not indices else "market_indices")
        if not indices and source not in ("offline_disabled", "empty"):
            source = source or "degraded"
        return json.dumps({
            "indices": indices[:20],
            "source": source,
            "count": len(indices),
            "asof": payload.get("timestamp") or _now_cn_iso(),
            "note": payload.get("note") or (
                "上游无指数数据" if not indices else "只读指数简报"
            ),
        }, ensure_ascii=False)
    except Exception as e:
        logger.warning("get_market_overview_brief failed: %s", e)
        return json.dumps({
            "indices": [],
            "source": "error",
            "note": f"市场简报失败: {type(e).__name__}",
            "count": 0,
            "asof": _now_cn_iso(),
        }, ensure_ascii=False)


@tool
def get_sector_snapshot(industry: str = "", symbol: str = "即时") -> str:
    """板块/行业资金流只读快照 facade（G9 薄封装）。

    industry 非空优先行业详情；否则取行业资金流即时榜。
    失败/离线 → data=[] + source，**不编造流入金额或假涨跌**。
    """
    industry = (industry or "").strip()
    symbol = (symbol or "即时").strip() or "即时"
    if _offline_or_disabled():
        return json.dumps({
            "data": [],
            "industry": industry or None,
            "symbol": symbol,
            "source": "offline_disabled",
            "note": "DISABLE_NETWORK=1；不拉板块数据、不编造资金流",
            "count": 0,
            "asof": _now_cn_iso(),
        }, ensure_ascii=False)
    try:
        from app.analysis.industry_analyzer import IndustryAnalyzer
        analyzer = IndustryAnalyzer()
        if industry:
            detail = analyzer.get_industry_detail(industry)
            if isinstance(detail, dict) and detail:
                return json.dumps({
                    "data": [detail],
                    "industry": industry,
                    "symbol": symbol,
                    "source": detail.get("source") or "industry_analyzer",
                    "count": 1,
                    "asof": _now_cn_iso(),
                    "note": "行业详情只读快照",
                }, ensure_ascii=False, default=str)
        flow = analyzer.get_industry_fund_flow(symbol=symbol)
        if isinstance(flow, list):
            rows = flow
        elif isinstance(flow, dict):
            rows = flow.get("data") if isinstance(flow.get("data"), list) else []
            if not rows and flow:
                rows = [flow]
        else:
            rows = []
        if industry and rows:
            ind_l = industry.lower()
            filtered = [
                r for r in rows
                if isinstance(r, dict) and ind_l in str(
                    r.get("industry") or r.get("name") or r.get("板块") or ""
                ).lower()
            ]
            if filtered:
                rows = filtered
        return json.dumps({
            "data": rows[:30] if isinstance(rows, list) else [],
            "industry": industry or None,
            "symbol": symbol,
            "source": "industry_fund_flow" if rows else "empty",
            "count": len(rows) if isinstance(rows, list) else 0,
            "asof": _now_cn_iso(),
            "note": "无板块数据" if not rows else "行业/板块资金流只读快照",
        }, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning("get_sector_snapshot failed: %s", e)
        return json.dumps({
            "data": [],
            "industry": industry or None,
            "symbol": symbol,
            "source": "error",
            "note": f"板块快照失败: {type(e).__name__}",
            "count": 0,
            "asof": _now_cn_iso(),
        }, ensure_ascii=False)


# === LangChain工具注册表（保持向后兼容） ===
ALL_TOOLS = [
    get_stock_data,
    get_technical_indicators,
    get_fundamental_data,
    get_capital_flow,
    get_stock_news,
    search_web_tool,
    get_risk_assessment,
    get_portfolio_snapshot,
    get_portfolio_risk_summary,
    get_market_overview_brief,
    get_sector_snapshot,
]

# LangChain按职能分组
TECHNICAL_TOOLS = [get_stock_data, get_technical_indicators]
FUNDAMENTAL_TOOLS = [get_fundamental_data]
CAPITAL_FLOW_TOOLS = [get_capital_flow]
SENTIMENT_TOOLS = [get_stock_news, search_web_tool]
RISK_TOOLS = [get_risk_assessment, get_portfolio_snapshot, get_portfolio_risk_summary]
PORTFOLIO_TOOLS = [get_portfolio_snapshot, get_portfolio_risk_summary]


# === OpenAI Function Calling 格式工具定义 ===

OPENAI_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_data",
            "description": "获取股票历史K线数据，返回最近N天的OHLCV数据摘要",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "股票代码，如 '600519'、'000001'"
                    },
                    "market_type": {
                        "type": "string",
                        "description": "市场类型，'A'为A股，'HK'为港股，'US'为美股",
                        "default": "A"
                    },
                    "days": {
                        "type": "integer",
                        "description": "获取最近多少天的数据",
                        "default": 120
                    }
                },
                "required": ["stock_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_technical_indicators",
            "description": "计算股票技术指标(MA/RSI/MACD/布林带等)并返回摘要",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "股票代码"
                    },
                    "market_type": {
                        "type": "string",
                        "description": "市场类型，'A'为A股，'HK'为港股，'US'为美股",
                        "default": "A"
                    }
                },
                "required": ["stock_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_fundamental_data",
            "description": "获取股票基本面数据(PE/PB/ROE/净利润等财务指标)",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "股票代码"
                    }
                },
                "required": ["stock_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_capital_flow",
            "description": "获取股票资金流向数据(主力/北向/机构资金)",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "股票代码"
                    }
                },
                "required": ["stock_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_news",
            "description": "获取股票相关的最新新闻和舆情信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "股票代码"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回新闻条数上限",
                        "default": 5
                    }
                },
                "required": ["stock_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "搜索互联网获取最新信息。17引擎多源聚合：auto自动降级(DDG→百度→Bing→搜狗→360→微信→Brave)；可明确指定 baidu/sogou/so360/wechat/toutiao/bing_cn/bing/duckduckgo/brave/qwant/startpage/ecosia/jisilu/zhihu/wikipedia/wolframalpha/concurrent",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大返回结果数",
                        "default": 5
                    },
                    "engine": {
                        "type": "string",
                        "description": "引擎名。auto默认；数学/换算用wolframalpha；百科事实用wikipedia；中文新闻可用wechat/toutiao；隐私偏好用duckduckgo/brave/qwant；多源聚合用concurrent",
                        "default": "auto"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_risk_assessment",
            "description": "评估股票的多维度风险(波动率/趋势/反转/成交量风险)",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "股票代码"
                    },
                    "market_type": {
                        "type": "string",
                        "description": "市场类型，'A'为A股，'HK'为港股，'US'为美股",
                        "default": "A"
                    }
                },
                "required": ["stock_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_snapshot",
            "description": (
                "读取当前用户真实持仓快照（只读）。"
                "无持仓时返回 holdings=[] 空结构，禁止编造持仓。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_risk_summary",
            "description": (
                "基于真实持仓快照的组合风险结构摘要（只读）。"
                "默认仅权重结构；include_market_risk=true 才尝试市价风险分析。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "include_market_risk": {
                        "type": "boolean",
                        "description": "是否尝试调用行情路径做组合市场风险（可能较重）",
                        "default": False
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "propose_portfolio_write",
            "description": (
                "生成写仓提案（非真实下单）。返回 proposal_id + approval_id；"
                "approval_id 会进入 HITL pending（task_id=approval_id），"
                "可 /api/agent_submit_approval 或 decide_portfolio_proposal_approval；"
                "再 apply_portfolio_proposal。禁止解读为已下单。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": (
                            "提案动作：add_holding | remove_holding | "
                            "update_holding | rebalance | other"
                        ),
                    },
                    "code": {
                        "type": "string",
                        "description": "股票代码（add/remove/update 必填）",
                        "default": "",
                    },
                    "name": {
                        "type": "string",
                        "description": "股票名称（可选，不得以 code 冒充）",
                        "default": "",
                    },
                    "shares": {
                        "type": "number",
                        "description": "拟调整股数（可选）",
                    },
                    "weight": {
                        "type": "number",
                        "description": "拟目标权重 0-1（可选）",
                    },
                    "reason": {
                        "type": "string",
                        "description": "提案理由（可选，最长约500字）",
                        "default": "",
                    },
                    "conversation_id": {
                        "type": "string",
                        "description": "关联会话 id（可选）",
                        "default": "",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "decide_portfolio_proposal_approval",
            "description": (
                "记录写仓提案审批（approve/reject），不执行写仓、不调用券商。"
                "与 /api/agent_submit_approval 同键 task_id=approval_id。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "approval_id": {
                        "type": "string",
                        "description": "提案返回的 approval_id",
                    },
                    "approved": {
                        "type": "boolean",
                        "description": "true=批准，false=拒绝",
                        "default": False,
                    },
                    "feedback": {
                        "type": "string",
                        "description": "审批意见（可选）",
                        "default": "",
                    },
                },
                "required": ["approval_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_portfolio_proposal",
            "description": (
                "在 approval_id 已批准后，将提案本地标记为 applied（模拟）。"
                "无真实券商；缺/未批 approval → APPROVAL_REQUIRED。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "proposal_id": {
                        "type": "string",
                        "description": "提案 id",
                    },
                    "approval_id": {
                        "type": "string",
                        "description": "已批准的 approval_id",
                        "default": "",
                    },
                },
                "required": ["proposal_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_analysis_plan",
            "description": (
                "创建轻量分析计划 DAG（串行 steps / depends_on 校验）。"
                "仅结构与状态机，不抓数、不下单。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "string",
                        "description": (
                            "JSON 数组字符串，如 '[\"技术\",\"基本面\"]' 或 "
                            "带 id/depends_on 的对象数组"
                        ),
                    },
                    "title": {
                        "type": "string",
                        "description": "计划标题（可选）",
                        "default": "",
                    },
                    "conversation_id": {
                        "type": "string",
                        "description": "会话 id（可选）",
                        "default": "",
                    },
                    "stock_code": {
                        "type": "string",
                        "description": "关联标的（可选）",
                        "default": "",
                    },
                },
                "required": ["steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_plan_status",
            "description": "查询分析计划状态（steps / topo_order / current_step）",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "create_analysis_plan 返回的 plan_id",
                    },
                },
                "required": ["plan_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_analysis_plans",
            "description": (
                "列出近期 analysis plan 及其步骤状态摘要（只读，不抓数）。"
                "用于回顾/续跑前查看 plan_id 与 pending/running/completed。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "最多返回条数，默认 20，上限 50",
                        "minimum": 1,
                        "maximum": 50,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_agent_skill",
            "description": (
                "加载 Skill stub 的 system_hint（不替代 adapters，不拉行情）。"
                "如 risk_checklist / portfolio_readonly / reflection_hint。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_id": {
                        "type": "string",
                        "description": "技能 id",
                    },
                    "stock_code": {
                        "type": "string",
                        "description": "reflection_hint 可选标的",
                        "default": "",
                    },
                },
                "required": ["skill_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_agent_skills",
            "description": "列出可用 Skill stub（builtin + data/skills）",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_overview_brief",
            "description": (
                "大盘/指数只读简报 facade。"
                "失败或离线时返回 indices=[] + source，禁止编造指数点位。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_sector_snapshot",
            "description": (
                "板块/行业资金流只读快照 facade。"
                "industry 可指定行业名；失败或离线返回 data=[] + source，禁止编造资金流假数。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "industry": {
                        "type": "string",
                        "description": "行业/板块名称（可选，空则取即时榜）",
                        "default": ""
                    },
                    "symbol": {
                        "type": "string",
                        "description": "资金流时间维度，默认「即时」",
                        "default": "即时"
                    }
                },
                "required": []
            }
        }
    }
]


# === OpenAI工具按职能分组的schema ===

TECHNICAL_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] in ('get_stock_data', 'get_technical_indicators')
]

FUNDAMENTAL_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] == 'get_fundamental_data'
]

CAPITAL_FLOW_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] == 'get_capital_flow'
]

SENTIMENT_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] in ('get_stock_news', 'search_web')
]

RISK_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] in (
        'get_risk_assessment',
        'get_portfolio_snapshot',
        'get_portfolio_risk_summary',
    )
]

PORTFOLIO_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] in (
        'get_portfolio_snapshot',
        'get_portfolio_risk_summary',
    )
]

MARKET_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] in (
        'get_market_overview_brief',
        'get_sector_snapshot',
    )
]

# 全量schema（排除搜索工具，用于股票分析场景）
STOCK_ANALYSIS_TOOLS_SCHEMA = [
    s for s in OPENAI_TOOLS_SCHEMA
    if s['function']['name'] != 'search_web'
]


# === 工具执行分发 ===

# 工具名称到LangChain工具实例的映射（全部为只读分析工具）
TOOL_EXECUTORS = {
    "get_stock_data": get_stock_data,
    "get_technical_indicators": get_technical_indicators,
    "get_fundamental_data": get_fundamental_data,
    "get_capital_flow": get_capital_flow,
    "get_stock_news": get_stock_news,
    "search_web": search_web_tool,
    "get_risk_assessment": get_risk_assessment,
    "get_portfolio_snapshot": get_portfolio_snapshot,
    "get_portfolio_risk_summary": get_portfolio_risk_summary,
    "propose_portfolio_write": propose_portfolio_write,
    "apply_portfolio_proposal": apply_portfolio_proposal,
    "decide_portfolio_proposal_approval": decide_portfolio_proposal_approval,
    "create_analysis_plan": create_analysis_plan,
    "get_plan_status": get_plan_status,
    "list_analysis_plans": list_analysis_plans,
    "load_agent_skill": load_agent_skill,
    "list_agent_skills": list_agent_skills,
    "get_market_overview_brief": get_market_overview_brief,
    "get_sector_snapshot": get_sector_snapshot,
}

# P0-2：只读工具白名单 = 当前注册面；任何写仓/下单类名称硬拦 no-op
READ_ONLY_TOOL_NAMES = frozenset(TOOL_EXECUTORS.keys())

# 显式写类工具名（含未来 LLM 幻觉名）；一律拒绝，不执行、不假成功
_WRITE_TOOL_EXACT = frozenset({
    "add_holding",
    "remove_holding",
    "update_holding",
    "delete_holding",
    "write_portfolio",
    "save_portfolio",
    "update_portfolio",
    "clear_portfolio",
    "mutate_portfolio",
    "buy",
    "sell",
    "place_order",
    "cancel_order",
    "submit_order",
    "execute_trade",
    "create_order",
    "modify_order",
    "portfolio_write",
    "portfolio_update",
    # G4 扩展矩阵：通用 mutate / system 假成功名
    "mutate",
    "mutate_state",
    "system_mutate",
    "admin_write",
    "force_write",
    "set_holding",
    "insert_holding",
    "upsert_holding",
    "batch_update_holdings",
    "liquidates",
    "liquidate",
    "rebalance_portfolio",
    "transfer_position",
})

_WRITE_TOOL_NAME_RE = re.compile(
    r"(?:^|_)(add|remove|delete|update|write|save|create|place|execute|submit|mutate|upsert|insert|set)"
    r"(?:_|$)"
    r"|(?:portfolio|holding|order|trade|position).*(?:write|mutat|update|add|remove|delete|save|upsert|liquidat)"
    r"|^(?:buy|sell|mutate|liquidate)$"
    r"|mutat(?:e|ion|ing)"
    r"|system[_-]?(?:write|mutat)",
    re.I,
)


def is_write_tool_name(tool_name: str) -> bool:
    """判断工具名是否属于写仓/下单类（服务端硬拦对象）。"""
    n = (tool_name or "").strip()
    if not n:
        return False
    if n in READ_ONLY_TOOL_NAMES:
        return False
    low = n.lower()
    if low in _WRITE_TOOL_EXACT or n in _WRITE_TOOL_EXACT:
        return True
    return bool(_WRITE_TOOL_NAME_RE.search(n))


def _refuse_write_tool(tool_name: str) -> str:
    """写工具硬拦：结构化明确错误，executed=false，data=null（铁律 #1）。"""
    payload = {
        "success": False,
        "executed": False,
        "error": "WRITE_TOOL_BLOCKED",
        "error_code": "WRITE_TOOL_BLOCKED",
        "tool": tool_name,
        "message": (
            "写仓/下单类工具已服务端硬拦：当前 Agent 链路不允许直接改仓/下单。"
            "未执行任何写操作。若需写仓流程，请使用 propose_portfolio_write "
            "→ decide_portfolio_proposal_approval → apply_portfolio_proposal "
            "（提案+审批闸门，仍无真实券商）。"
            "禁止将本响应解读为下单或改仓成功。"
        ),
        "data": None,
        "broker": None,
        "hint": "propose_portfolio_write",
    }
    try:
        logger.warning("WRITE_TOOL_BLOCKED tool=%s", tool_name)
    except Exception:
        pass
    return json.dumps(payload, ensure_ascii=False)


def _raw_execute_tool(tool_name: str, arguments: dict) -> str:
    """底层工具执行（无护栏）。写工具硬拦；未知只读外工具抛 ValueError。"""
    if is_write_tool_name(tool_name):
        return _refuse_write_tool(tool_name)

    executor = TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        available = ', '.join(TOOL_EXECUTORS.keys())
        raise ValueError(f"未知工具: {tool_name}，可用工具: {available}")

    logger.info(f"执行工具 {tool_name}，参数: {arguments}")
    try:
        result = executor.invoke(arguments)
        return result if isinstance(result, str) else str(result)
    except Exception as e:
        error_msg = f"工具 {tool_name} 执行失败: {str(e)}"
        logger.error(error_msg)
        return error_msg


def execute_tool(tool_name: str, arguments: dict) -> str:
    """
    执行指定工具并返回结果字符串。

    通过LangChain工具的 .invoke() 方法调用，兼容 @tool 装饰器的调用约定。
    P0-1：若当前 ContextVar 绑定了 turn 护栏，则同 tool+归一化 args 连续失败
    达阈值时返回结构化 JSON（guardrail=block|halt|warn），不造假金融数据。
    P0-2：写仓/下单类工具名服务端硬拦（no-op + WRITE_TOOL_BLOCKED），只读白名单照常。

    Args:
        tool_name: 工具名称（需与TOOL_EXECUTORS中的key匹配）
        arguments: 工具参数字典

    Returns:
        str: 工具执行结果的字符串表示；被护栏拦截时为含 guardrail 字段的 JSON；
             写工具硬拦时为含 error_code=WRITE_TOOL_BLOCKED 的 JSON

    Raises:
        ValueError: 未知的工具名称（仅裸路径；护栏开启时未知工具仍 raise，由调用方捕获）
    """
    # 写工具硬拦优先于护栏/注册表（含 LLM 幻觉工具名）
    if is_write_tool_name(tool_name):
        return _refuse_write_tool(tool_name)

    try:
        from app.core.tool_guardrails import get_turn_guardrails, guarded_execute

        if get_turn_guardrails() is not None:
            # 未知工具仍 raise，与既有契约一致（ai_client 已 try/except 包装）
            return guarded_execute(
                tool_name,
                arguments or {},
                lambda n, a: _raw_execute_tool(n, a),
            )
    except ValueError:
        raise
    except Exception as e:
        logger.warning("tool_guardrails unavailable, fallback raw execute: %s", e)

    return _raw_execute_tool(tool_name, arguments or {})
