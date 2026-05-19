"""
Input: 历史反思记录 + 历史决策表现
Output: 优化后的Agent策略配置
Pos: app/agents/strategy_evolver.py - Agent自主策略演进系统
[E3 2026-04-15] 接入 AdapterRegistry 前瞻性信号:
  - hiring_signal (扩张招聘→基本面前瞻) + esg_rating (ESG趋势)
  - 失败降级为空, 不影响原策略演化AI流程

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

_ASIA_SHANGHAI = timezone(timedelta(hours=8))
now_cn = lambda: datetime.now(_ASIA_SHANGHAI)

logger = logging.getLogger(__name__)


def _safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    """[I2-2026-04-15] 容错 JSON 解析:
       - 去 markdown code fence (```json ... ``` / ``` ... ```)
       - 去 trailing comma
       - 提取首个 {...} 块作兜底
       - 失败返回 None, 不抛异常
    """
    if not text or not isinstance(text, str):
        return None
    s = text.strip()
    # 去 fence
    if s.startswith('```'):
        # 剥第一行 fence
        parts = s.split('\n', 1)
        if len(parts) == 2:
            s = parts[1]
        # 去末尾 fence
        if s.rstrip().endswith('```'):
            s = s.rstrip()[:-3]
        s = s.strip()
    # 尝试直接解析
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    # 去 trailing comma: ,} 或 ,]
    try:
        s2 = re.sub(r',\s*([}\]])', r'\1', s)
        obj = json.loads(s2)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    # 提取首个大括号块
    try:
        m = re.search(r'\{.*\}', s, re.DOTALL)
        if m:
            candidate = re.sub(r',\s*([}\]])', r'\1', m.group(0))
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    return None


def _registry_fetch(domain: str, method: str, **kwargs) -> Optional[Any]:
    """模块级 AdapterRegistry 多源降级 fetch。失败返回None。"""
    try:
        from app.adapters.adapter_registry import AdapterRegistry
        return AdapterRegistry.default().call_with_fallback(domain, method, **kwargs)
    except Exception as e:
        logger.info(f"[StrategyEvolver] registry fetch {domain}.{method} 降级失败: {type(e).__name__}: {e}")
        return None


def _collect_evolve_context(stock_code: str) -> str:
    """拉取招聘前瞻 + ESG趋势, 作为策略演化的附加信号。"""
    parts = []
    hiring = _registry_fetch('hiring_signal', 'get_hiring_trend', query=stock_code)
    if hiring:
        parts.append(f"【招聘扩张信号】{str(hiring)[:250]}")
    esg = _registry_fetch('esg_rating', 'get_esg_rating', code=stock_code)
    if esg:
        parts.append(f"【ESG趋势】{str(esg)[:200]}")
    return "\n".join(parts)

STRATEGY_DIR = os.path.join(os.path.dirname(__file__), '../../data/agent_strategies')


class StrategyEvolver:
    """Agent策略演进器 - 从反思中提炼可执行策略"""

    def __init__(self):
        os.makedirs(STRATEGY_DIR, exist_ok=True)

    def get_active_strategy(self, stock_code: str) -> Dict[str, Any]:
        """获取当前激活的策略配置"""
        # 先查股票专用策略
        strategy = self._load_strategy(f"{stock_code}_strategy")
        if strategy:
            return strategy
        # 回退到全局默认策略
        return self._load_strategy("default_strategy") or self._get_default_strategy()

    def evolve_strategy(self, stock_code: str, reflections: List[Dict]) -> Dict[str, Any]:
        """基于反思记录演化策略"""
        from app.core.ai_client import get_ai_client, chat_completion, get_completion_content

        current_strategy = self.get_active_strategy(stock_code)

        # 提取反思中的改进建议
        improvements = []
        biases = []
        for r in reflections:
            ref = r.get('reflection', {})
            if isinstance(ref, dict):
                improvements.extend(ref.get('improvements', []))
                biases.extend(ref.get('biases_detected', []))

        if not improvements and not biases:
            return current_strategy

        client = get_ai_client()
        if not client:
            return current_strategy

        # === Registry 前瞻信号 (双保险) ===
        forward_signals = ""
        try:
            ctx = _collect_evolve_context(stock_code)
            if ctx:
                forward_signals = f"\n\n前瞻性另类数据信号（用于调整focus_areas）：\n{ctx}"
        except Exception as e:
            logger.info(f"[StrategyEvolver] 前瞻信号聚合失败: {type(e).__name__}")

        prompt = f"""你是一位量化策略优化专家。基于以下信息，优化分析策略配置：

当前策略配置：
{json.dumps(current_strategy, ensure_ascii=False, indent=2)}

历史反思中的改进建议：
{chr(10).join(f'- {i}' for i in improvements[:10])}

检测到的分析偏差：
{chr(10).join(f'- {b}' for b in biases[:5])}{forward_signals}

请输出优化后的策略配置（JSON格式，保持与当前配置相同的键结构）：
{{"focus_areas": ["应重点关注的分析维度"], "risk_sensitivity": "low/medium/high", "confidence_threshold": 0.0-1.0, "analysis_notes": ["分析时的注意事项"], "weight_adjustments": {{"technical": 0.0-1.0, "fundamental": 0.0-1.0, "sentiment": 0.0-1.0, "capital_flow": 0.0-1.0}}}}"""

        response, error = chat_completion(
            client,
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800
        )

        if error:
            logger.warning(f"策略演化失败: {error}")
            return current_strategy

        content = get_completion_content(response) or ""
        # [I2-2026-04-15] 使用 _safe_json_parse 容错解析
        new_strategy = _safe_json_parse(content)
        if not new_strategy:
            logger.warning(f"策略JSON解析失败, 保留当前策略. content前200字: {content[:200]!r}")
            return current_strategy
        try:
            new_strategy['last_evolved'] = now_cn().strftime('%Y-%m-%d %H:%M:%S')
            new_strategy['evolution_count'] = current_strategy.get('evolution_count', 0) + 1
            # 保存新策略
            self._save_strategy(f"{stock_code}_strategy", new_strategy)
            logger.info(f"策略已演化: {stock_code}, 第{new_strategy['evolution_count']}次")
            return new_strategy
        except Exception as e:
            logger.warning(f"策略保存失败: {e}")
            return current_strategy

    def get_strategy_prompt(self, stock_code: str) -> str:
        """生成策略提示注入到Agent prompt中"""
        strategy = self.get_active_strategy(stock_code)
        if not strategy or strategy == self._get_default_strategy():
            return ""

        lines = ["=== 自适应策略配置 ==="]
        if strategy.get('focus_areas'):
            lines.append(f"重点关注: {', '.join(strategy['focus_areas'])}")
        if strategy.get('analysis_notes'):
            lines.append(f"注意事项: {', '.join(strategy['analysis_notes'][:3])}")
        if strategy.get('risk_sensitivity'):
            lines.append(f"风险敏感度: {strategy['risk_sensitivity']}")
        if strategy.get('weight_adjustments'):
            w = strategy['weight_adjustments']
            lines.append(
                f"权重偏好: 技术={w.get('technical', 'N/A')}, "
                f"基本面={w.get('fundamental', 'N/A')}, "
                f"情绪={w.get('sentiment', 'N/A')}"
            )
        if strategy.get('evolution_count'):
            lines.append(f"策略已迭代 {strategy['evolution_count']} 次")
        return '\n'.join(lines)

    def _get_default_strategy(self) -> Dict:
        return {
            'focus_areas': ['技术趋势', '基本面估值', '资金流向'],
            'risk_sensitivity': 'medium',
            'confidence_threshold': 0.6,
            'analysis_notes': [],
            'weight_adjustments': {
                'technical': 0.3,
                'fundamental': 0.3,
                'sentiment': 0.2,
                'capital_flow': 0.2,
            },
            'evolution_count': 0,
        }

    def _load_strategy(self, name: str) -> Optional[Dict]:
        filename = os.path.join(STRATEGY_DIR, f"{name}.json")
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _save_strategy(self, name: str, strategy: Dict):
        filename = os.path.join(STRATEGY_DIR, f"{name}.json")
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(strategy, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存策略失败: {e}")


# 全局单例
_evolver = None


def get_strategy_evolver() -> StrategyEvolver:
    global _evolver
    if _evolver is None:
        _evolver = StrategyEvolver()
    return _evolver
