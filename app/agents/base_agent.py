"""
Input: AgentState
Output: 更新后的AgentState
Pos: app/agents/base_agent.py - 所有分析Agent的基类 (集成AdapterRegistry多源降级入口)

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

[C2 2026-04-15] 新增 AdapterRegistry 懒加载入口:
  - property self.registry → AdapterRegistry.default() (进程级单例)
  - self.fetch(domain, method, **kw) 封装 call_with_fallback, 自动多源降级
"""
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.core.ai_client import get_ai_client, get_ai_model, chat_completion, get_completion_content
from app.core.data_provider import get_data_provider

logger = logging.getLogger(__name__)


class BaseStockAgent(ABC):
    """股票分析Agent基类"""

    def __init__(self):
        self.client = get_ai_client()
        self.model = get_ai_model()
        self.data_provider = get_data_provider()
        self.name = self.__class__.__name__
        self._registry = None  # 懒加载 AdapterRegistry

    @property
    def registry(self):
        """懒加载 AdapterRegistry 单例 (首次访问时注册全部适配器)。"""
        if self._registry is None:
            try:
                from app.adapters.adapter_registry import AdapterRegistry
                self._registry = AdapterRegistry.default()
            except Exception as e:
                logger.warning(f"[{self.name}] AdapterRegistry 加载失败: {type(e).__name__}: {e}")
                self._registry = None
        return self._registry

    def fetch(self, domain: str, method: str, **kwargs) -> Optional[Any]:
        """便捷方法: 通过 AdapterRegistry 多源降级获取数据。

        Args:
            domain: 业务域 (a_stock_kline / xbrl_financials / news ...)
            method: 适配器方法名 (get_stock_history / get_financials ...)
            **kwargs: 透传给适配器方法

        Returns:
            首个有效数据源返回值, 全部失败抛 Exception
        """
        reg = self.registry
        if reg is None:
            raise RuntimeError(f"[{self.name}] AdapterRegistry 不可用, 无法 fetch({domain}.{method})")
        return reg.call_with_fallback(domain, method, **kwargs)

    @abstractmethod
    def analyze(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行分析，返回状态更新"""
        pass

    def _update_progress(self, state: Dict[str, Any], progress: float, message: str) -> None:
        """更新执行进度"""
        log_entry = {
            'agent': self.name,
            'progress': progress,
            'message': message,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        if 'execution_log' not in state:
            state['execution_log'] = []
        state['execution_log'].append(log_entry)
        state['progress'] = progress

    def _log_error(self, state: Dict[str, Any], error: str) -> None:
        """记录错误"""
        logger.error(f"[{self.name}] {error}")
        if 'errors' not in state:
            state['errors'] = []
        state['errors'].append(f"[{self.name}] {error}")

    def _ai_analyze(self, prompt: str, temperature: float = 0.7) -> str:
        """调用AI进行分析"""
        messages = [{"role": "user", "content": prompt}]
        response, error = chat_completion(self.client, messages, temperature=temperature)
        if error:
            return f"AI分析失败: {error}"
        content = get_completion_content(response)
        return content if content else "AI未返回分析结果"
