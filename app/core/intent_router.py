"""
Input: 用户自然语言 message + 可选上下文（是否有持仓 snapshot）
Output: intent 标签与 meta（规则优先，离线可测；无金融假数）
Pos: app/core/intent_router.py — Sprint2 chat 意图路由；挂 /api/ai/chat 预处理；P0-2 拟写仓硬拒绝

一旦我被修改，请更新我的头部注释，以及所属文件夹的 md。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

# 意图枚举（契约稳定，前后端/日志共用）
INTENT_SINGLE_STOCK_DEEP = "single_stock_deep"
INTENT_PORTFOLIO = "portfolio"
INTENT_CROSS_MARKET_EVENT = "cross_market_event"
INTENT_MARKET_OVERVIEW = "market_overview"
INTENT_GENERAL = "general"
INTENT_PORTFOLIO_WRITE = "portfolio_write_blocked"  # P0-2 拟写仓（system_hint 硬拒绝）

VALID_INTENTS = (
    INTENT_SINGLE_STOCK_DEEP,
    INTENT_PORTFOLIO,
    INTENT_CROSS_MARKET_EVENT,
    INTENT_MARKET_OVERVIEW,
    INTENT_GENERAL,
    INTENT_PORTFOLIO_WRITE,
)

# 规则：持仓 / 组合
_PORTFOLIO_RE = re.compile(
    r"(持仓|组合|仓位|我的股票|资产配置|portfolio|持有|仓位结构|"
    r"组合风险|仓位风险|账户股票|自选与持仓|整体仓位)",
    re.IGNORECASE,
)

# P0-2 拟写仓（服务端 system_hint 硬拒绝；不开放写工具）
_PORTFOLIO_WRITE_RE = re.compile(
    r"(加仓|减仓|清仓|调仓|建仓|建个仓|改仓|写入持仓|更新持仓|删除持仓|"
    r"帮我买|帮我卖|下单|挂单|市价单|限价单|自动跟单|"
    r"add\s+holding|remove\s+holding|update\s+portfolio|"
    r"place\s+order|buy\s+now|sell\s+now)",
    re.IGNORECASE,
)

# 规则：跨市场 / 事件冲击
_CROSS_MARKET_RE = re.compile(
    r"(美联储|加息|降息|非农|CPI|PPI|地缘|关税|制裁|战争|冲突|原油冲击|"
    r"外围|美股联动|港股联动|A股联动|跨市场|全球市场|隔夜|外盘|黑天鹅|"
    r"事件驱动|突发|制裁名单|贸易战|美债|美元指数|黄金避险)",
    re.IGNORECASE,
)

# 规则：大盘 / 市场全景
_MARKET_OVERVIEW_RE = re.compile(
    r"(大盘|指数|上证|深证|创业板|沪深300|科创50|恒生|纳斯达克|道琼斯|"
    r"市场概览|今日行情|盘面|板块轮动|北向资金|两市|市场情绪|宏观情绪|"
    r"market\s*overview|indices?)",
    re.IGNORECASE,
)

# 规则：单票深度分析
_DEEP_ANALYZE_RE = re.compile(
    r"(分析|深度|研究|全面|估值|基本面|技术面|诊断|复盘|解读|剖析|多\s*agent|agent)",
    re.IGNORECASE,
)

# A 股 6 位 / 常见带后缀代码 / 美股 ticker 粗识别
_A_CODE_RE = re.compile(r"(?<![A-Za-z0-9])(\d{6})(?![A-Za-z0-9])")
_DOT_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9])(\d{5,6}\.(?:SH|SZ|BJ|SS|HK)|[A-Z]{1,5}\.(?:US|HK|L))",
    re.IGNORECASE,
)
_US_TICKER_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z]{1,5})(?![A-Za-z0-9])")
# 避免把常见英文词当 ticker
_US_TICKER_DENY = {
    "A", "I", "AI", "API", "ETF", "IPO", "PE", "PB", "ROE", "CEO", "CFO",
    "USD", "CNY", "HKD", "SSE", "HTTP", "JSON", "SSE", "GDP", "CPI", "PPI",
}


@dataclass(frozen=True)
class IntentResult:
    intent: str
    confidence: float
    reasons: Tuple[str, ...]
    stock_codes: Tuple[str, ...]
    inject_portfolio: bool
    system_hint: str

    def to_meta(self) -> Dict[str, Any]:
        """写入 SSE meta / 日志的紧凑结构（无假行情数）。"""
        return {
            "intent": self.intent,
            "confidence": round(self.confidence, 3),
            "reasons": list(self.reasons),
            "stock_codes": list(self.stock_codes),
            "inject_portfolio": self.inject_portfolio,
            "router": "rules_v1",
        }


def _extract_codes(message: str) -> List[str]:
    codes: List[str] = []
    seen = set()
    for m in _A_CODE_RE.finditer(message or ""):
        c = m.group(1)
        if c not in seen:
            seen.add(c)
            codes.append(c)
    for m in _DOT_CODE_RE.finditer(message or ""):
        c = m.group(1).upper()
        if c not in seen:
            seen.add(c)
            codes.append(c)
    # 仅当消息很像「看某美股」且长度短词时才收录 ticker，避免噪声
    if re.search(r"(美股|NASDAQ|NYSE|标普|道指)", message or "", re.I):
        for m in _US_TICKER_RE.finditer((message or "").upper()):
            t = m.group(1)
            if t in _US_TICKER_DENY:
                continue
            if t not in seen:
                seen.add(t)
                codes.append(t)
    return codes


def _hint_for(intent: str) -> str:
    if intent == INTENT_PORTFOLIO_WRITE:
        return (
            "【写仓硬拦】用户请求改仓/下单/加仓减仓等写操作。"
            "你必须明确拒绝执行任何写仓或下单；说明系统仅支持只读分析与建议；"
            "引导用户在组合页手动维护持仓。禁止声称「已帮你加仓/下单成功」。"
            "可继续提供只读分析（get_portfolio_snapshot / get_portfolio_risk_summary）。"
        )
    if intent == INTENT_PORTFOLIO:
        return (
            "用户意图为持仓/组合分析。优先调用 get_portfolio_snapshot 读取真实持仓；"
            "无持仓时如实告知空仓，禁止编造持仓或假权重。"
            "需要组合风险结构时可调用 get_portfolio_risk_summary（基于 snapshot 的结构摘要，不发明风险分）。"
            "禁止调用或假装成功任何写仓/下单工具。"
        )
    if intent == INTENT_CROSS_MARKET_EVENT:
        return (
            "用户意图为跨市场/宏观事件冲击。建议工具序："
            "1) search_web_tool 检索事件事实；2) get_stock_news 相关标的新闻；"
            "3) 必要时 get_stock_data / 批量行情对照多市场。"
            "禁止编造未检索到的新闻与价格；禁止写仓。"
        )
    if intent == INTENT_MARKET_OVERVIEW:
        return (
            "用户意图为市场全景/大盘。可结合指数与板块类工具说明，"
            "无实时数据时明确降级，禁止用假指数值填充；禁止写仓。"
        )
    if intent == INTENT_SINGLE_STOCK_DEEP:
        return (
            "用户意图为单票深度分析。优先 get_stock_data / get_fundamental_data / "
            "get_technical_indicators / get_capital_flow / get_risk_assessment；"
            "数据缺失时明确说明，禁止假行情与假财报；禁止写仓/下单。"
        )
    return (
        "通用金融助手模式：有具体代码时再拉数据；无数据源时不编造数字；禁止写仓/下单，仅只读分析。"
    )


def classify_intent(
    message: str,
    *,
    has_portfolio_snapshot: bool = False,
    stock_code_hint: str = "",
) -> IntentResult:
    """规则优先意图分类（确定性、离线可测）。

    优先级（高→低）：
    0. 拟写仓关键词 → portfolio_write_blocked（P0-2，system_hint 硬拒绝）
    1. portfolio 关键词（或有 snapshot 且询问组合相关）
    2. cross_market_event 关键词
    3. market_overview 关键词
    4. 有股票代码 + 分析动词 → single_stock_deep
    5. 有股票代码（无分析动词）→ single_stock_deep（偏弱置信）
    6. general
    """
    text = (message or "").strip()
    reasons: List[str] = []
    codes = _extract_codes(text)
    if stock_code_hint and stock_code_hint.strip():
        hint = stock_code_hint.strip()
        if hint not in codes:
            codes.insert(0, hint)
            reasons.append("stock_code_hint")

    has_write = bool(_PORTFOLIO_WRITE_RE.search(text))
    has_portfolio_kw = bool(_PORTFOLIO_RE.search(text))
    has_cross = bool(_CROSS_MARKET_RE.search(text))
    has_market = bool(_MARKET_OVERVIEW_RE.search(text))
    has_deep = bool(_DEEP_ANALYZE_RE.search(text))

    # 0) 拟写仓 — 最高优先级（仍可 inject 只读 snapshot 供说明）
    if has_write:
        reasons.append("portfolio_write_keyword")
        return IntentResult(
            intent=INTENT_PORTFOLIO_WRITE,
            confidence=0.92,
            reasons=tuple(reasons),
            stock_codes=tuple(codes),
            inject_portfolio=True,
            system_hint=_hint_for(INTENT_PORTFOLIO_WRITE),
        )

    # 1) portfolio
    if has_portfolio_kw:
        reasons.append("portfolio_keyword")
        conf = 0.9 if has_portfolio_snapshot else 0.82
        return IntentResult(
            intent=INTENT_PORTFOLIO,
            confidence=conf,
            reasons=tuple(reasons),
            stock_codes=tuple(codes),
            inject_portfolio=True,
            system_hint=_hint_for(INTENT_PORTFOLIO),
        )

    # 无关键词但 body 带了 snapshot 且用户问「风险/配置」弱信号
    if has_portfolio_snapshot and re.search(r"(风险|配置|分散|集中度|回撤|仓)", text):
        reasons.append("snapshot_present_with_risk_or_allocation_kw")
        return IntentResult(
            intent=INTENT_PORTFOLIO,
            confidence=0.7,
            reasons=tuple(reasons),
            stock_codes=tuple(codes),
            inject_portfolio=True,
            system_hint=_hint_for(INTENT_PORTFOLIO),
        )

    # 2) cross market / event
    if has_cross:
        reasons.append("cross_market_or_event_keyword")
        return IntentResult(
            intent=INTENT_CROSS_MARKET_EVENT,
            confidence=0.85,
            reasons=tuple(reasons),
            stock_codes=tuple(codes),
            inject_portfolio=False,
            system_hint=_hint_for(INTENT_CROSS_MARKET_EVENT),
        )

    # 3) market overview
    if has_market and not codes:
        reasons.append("market_overview_keyword")
        return IntentResult(
            intent=INTENT_MARKET_OVERVIEW,
            confidence=0.84,
            reasons=tuple(reasons),
            stock_codes=tuple(),
            inject_portfolio=False,
            system_hint=_hint_for(INTENT_MARKET_OVERVIEW),
        )
    if has_market and codes:
        # 有代码时更偏单票，但仍记录 market 信号
        reasons.append("market_keyword_with_codes")

    # 4/5) single stock
    if codes and has_deep:
        reasons.append("code_plus_analyze_verb")
        return IntentResult(
            intent=INTENT_SINGLE_STOCK_DEEP,
            confidence=0.88,
            reasons=tuple(reasons),
            stock_codes=tuple(codes),
            inject_portfolio=False,
            system_hint=_hint_for(INTENT_SINGLE_STOCK_DEEP),
        )
    if codes:
        reasons.append("code_only")
        return IntentResult(
            intent=INTENT_SINGLE_STOCK_DEEP,
            confidence=0.72,
            reasons=tuple(reasons),
            stock_codes=tuple(codes),
            inject_portfolio=False,
            system_hint=_hint_for(INTENT_SINGLE_STOCK_DEEP),
        )

    # 6) general
    reasons.append("default_general")
    return IntentResult(
        intent=INTENT_GENERAL,
        confidence=0.55,
        reasons=tuple(reasons),
        stock_codes=tuple(),
        inject_portfolio=has_portfolio_snapshot and has_portfolio_kw,
        system_hint=_hint_for(INTENT_GENERAL),
    )


def intent_result_as_dict(result: IntentResult) -> Dict[str, Any]:
    """测试/序列化辅助。"""
    d = asdict(result)
    d["reasons"] = list(result.reasons)
    d["stock_codes"] = list(result.stock_codes)
    return d
