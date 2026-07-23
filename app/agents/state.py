"""
Input: 用户请求参数(stock_code, market_type, research_depth, router_decision)
Output: 完整的分析状态对象，各Agent共享读写，支持动态路由决策记录
Pos: app/agents/state.py - 所有Agent的共享状态定义，含路由决策字段

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import operator
from typing import TypedDict, Annotated, Optional, List, Dict, Any
from langgraph.graph.message import add_messages


def _progress_reducer(old: float, new: float) -> float:
    """并发进度更新时取最大值，确保进度只向前推进"""
    return max(old, new)


class StockAnalysisState(TypedDict):
    """股票分析Agent系统的共享状态

    注意: progress / execution_log / errors 使用 Annotated reducer，
    以支持 LangGraph 并行 fan-out 节点并发写入同一 key。
    """
    # 输入参数
    stock_code: str
    market_type: str  # A, HK, US
    research_depth: int  # 1-5, 控制调用哪些Agent

    # 消息历史(LangGraph标准)
    messages: Annotated[list, add_messages]

    # 各Agent分析结果
    technical_report: Optional[Dict[str, Any]]
    fundamental_report: Optional[Dict[str, Any]]
    capital_flow_report: Optional[Dict[str, Any]]
    sentiment_report: Optional[Dict[str, Any]]

    # 辩论结果
    bull_case: Optional[str]
    bear_case: Optional[str]
    debate_summary: Optional[str]

    # 投资者人格分析结果
    investor_opinions: Optional[Dict[str, Any]]  # 各投资者的建议汇总
    investor_consensus: Optional[Dict[str, Any]]  # 投资者共识（实际存储dict结构）

    # 风险与决策
    risk_assessment: Optional[Dict[str, Any]]
    final_decision: Optional[Dict[str, Any]]  # {action, reasoning, confidence, price_targets}

    # 路由决策（动态编排用）
    router_decision: Optional[str]  # 路由决策记录，如 "fast_fail" / "normal"

    # 元数据 — 使用 Annotated reducer 支持并行节点并发写入
    execution_log: Annotated[List[Dict[str, Any]], operator.add]
    progress: Annotated[float, _progress_reducer]  # 0.0 - 100.0
    errors: Annotated[List[str], operator.add]
    # P0 降级可视化（零假值）：结构化 degradation + confidence 上界帽
    degradations: Annotated[List[Dict[str, Any]], operator.add]
    confidence_cap: Optional[float]  # 全 run 最紧上界；None=不封顶
