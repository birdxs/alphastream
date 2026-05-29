# -*- coding: utf-8 -*-
"""
Input: A股代码（如 600519）、WIND_API_KEY（env）、各档配额/缓存（wind_budget）、MCP over HTTP 端点
Output: Dict（基本信息/财务）或降级值（[]/{}/None）；统一过 WindCache（省积分）+ WindQuota（控额度）
Pos: app/adapters/wind_adapter.py - Wind(万得) MCP HTTP 数据源适配器 P1 底层；P1 仅建底座，不接入 registry/tools/路由

一旦我被修改，请更新我的头部注释，以及所属文件夹的 md。

[NEW-FILE:#20260529-WIND-02]

P1 范围说明（不接入任何路由/registry/tools）：
- 仅实现 BaseAdapter 6 方法 + 私有 _call_wind 统一取数入口；未在 adapter_registry 注册。
- health_check 不烧积分、不连网：仅检查 WIND_API_KEY 是否配置（真实连通性留 P2 真机验证）。
- 行情 K 线不走 Wind（避免误烧积分）：get_stock_history 返回 None 降级到免费源，P3 再评估。
- 指数成分股 Wind 无对应工具：get_index_stocks 返回 []（缺口）。

MCP over HTTP + JSON-RPC 2.0：
- 端点 https://mcp.wind.com.cn/vserver_{server_type}/mcp/
- 两步握手：initialize（protocolVersion 2025-03-26，30s）→ tools/call（600s，env WIND_CALL_TIMEOUT）。
- 传输格式（P2c 真机确认）：Wind MCP 实际以 Content-Type: text/event-stream（SSE）返回，
  body 形如 `event: message\\r\\ndata: {"jsonrpc":"2.0",...}`。initialize 与 tools/call 两步均为 SSE。
  故响应统一过 _parse_mcp_response：SSE 时收集 data: 行取最后一条有效 JSON-RPC；否则走 resp.json()。
- 业务解析：payload["result"]["content"][0]["text"]，若为 JSON 字符串则二次 json.loads。
"""
import os
import json
import time
import logging
import threading
from typing import Optional, List, Dict

import pandas as pd
import httpx

from .base_adapter import BaseAdapter
from ..core.wind_budget import WindCache, WindQuota

logger = logging.getLogger(__name__)

# Wind MCP 协议版本（initialize 握手）
_WIND_PROTOCOL_VERSION = "2025-03-26"
_WIND_INIT_TIMEOUT = 30.0
_WIND_ENDPOINT_TMPL = "https://mcp.wind.com.cn/vserver_{server_type}/mcp/"

# TTL 常量（秒）
_TTL_7D = 7 * 24 * 3600
_TTL_30D = 30 * 24 * 3600

# 视为「配额/鉴权」类错误码（静默降级，不抛穿透）
_QUOTA_ERROR_CODES = {'QUOTA_ERROR', 'QPS_LIMIT', 'BALANCE_INSUFFICIENT', 'RATE_LIMITED'}
_AUTH_ERROR_CODES = {'AUTH_ERROR', 'UNAUTHORIZED', 'INVALID_API_KEY'}


def _to_windcode(code: str) -> str:
    """A股 6 位代码 → Wind windcode（带 .SH/.SZ 后缀）。

    规则：
      6xxxxx → .SH（沪市主板/科创板）
      0xxxxx / 3xxxxx → .SZ（深市主板/创业板）
      已含 . 的原样返回。
    """
    code = (code or '').strip().upper()
    if '.' in code:
        return code
    if code.startswith('6'):
        return f"{code}.SH"
    if code.startswith('3') or code.startswith('0'):
        return f"{code}.SZ"
    # 兜底：无法判断时默认沪市（不抛异常）
    return f"{code}.SH"


class WindAdapter(BaseAdapter):
    """Wind(万得) MCP HTTP 数据源适配器（P1 底层，未注册）。

    所有取数均过 _call_wind：缓存优先 → 配额闸门 → HTTP 调用 → 写缓存。
    未配置 WIND_API_KEY → self._enabled=False，所有取数方法直接返回降级值。
    """

    def __init__(self, api_key: Optional[str] = None,
                 cache: Optional[WindCache] = None,
                 quota: Optional[WindQuota] = None):
        self.api_key = api_key or os.getenv('WIND_API_KEY', '')
        self._enabled = bool(self.api_key)
        self._call_timeout = float(os.getenv('WIND_CALL_TIMEOUT', '600'))
        # 缓存/配额：默认各自独立 sqlite 引擎，可注入（测试用临时库）
        self._cache = cache if cache is not None else WindCache()
        self._quota = quota if quota is not None else WindQuota()
        # P1.5 失败短时熔断：进程内 {(windcode, tool): last_fail_ts}，RLock 保护。
        # 冷却窗内对同一 (windcode, tool) 直接降级，不消费额度，避免对故障标的反复烧额度。
        # 进程重启 dict 清空可接受（熔断仅为短时保护，重启后自然解除）。
        self._fail_cooldown = float(os.getenv('WIND_FAIL_COOLDOWN', '300'))
        self._fail_ts: Dict[tuple, float] = {}
        self._fail_lock = threading.RLock()
        if not self._enabled:
            logger.warning(
                "WIND_API_KEY 未配置，WindAdapter 已禁用；所有取数返回降级值。"
                "注册进 registry 后 health_check=False 将被自动摘除。"
            )

    @property
    def name(self) -> str:
        return "Wind"

    # ============================ 统一取数入口 ============================

    @staticmethod
    def _parse_mcp_response(resp):
        """解析 MCP over HTTP 响应为 JSON-RPC dict（P2c）。

        Wind MCP 以 Content-Type: text/event-stream（SSE）返回，body 形如
        `event: message\\r\\ndata: {"jsonrpc":"2.0",...}`，对 SSE 直接 resp.json()
        会抛 JSONDecodeError。处理策略：
          - content-type 含 text/event-stream → 按行收集以 `data:` 开头的载荷，
            去前缀 strip 后逐条 json.loads，取最后一条可解析的 JSON-RPC dict；
          - 否则走原 resp.json()。
        解析失败抛 ValueError（由调用方 _http_call_wind 的 except 统一降级 None）。
        """
        content_type = ''
        try:
            content_type = (resp.headers.get('content-type', '') or '').lower()
        except AttributeError:
            # 测试/兼容场景：响应对象无 headers → 退回 resp.json()
            content_type = ''

        if 'text/event-stream' in content_type:
            last = None
            for line in (resp.text or '').splitlines():
                if not line.startswith('data:'):
                    continue
                chunk = line[len('data:'):].strip()
                if not chunk:
                    continue
                try:
                    last = json.loads(chunk)
                except (TypeError, ValueError):
                    continue
            if last is None:
                raise ValueError('SSE 响应无可解析的 data: JSON 载荷')
            return last

        # 非 SSE：原 JSON 解析路径
        return resp.json()

    def _http_call_wind(self, server_type: str, tool: str, arguments: dict):
        """两步握手 MCP over HTTP；返回解析后的 content 文本（dict/原文）或 None。

        失败（网络/超时/配额/鉴权/解析）一律 WARNING + 返回 None，不向上抛。
        """
        endpoint = _WIND_ENDPOINT_TMPL.format(server_type=server_type)
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
        }
        try:
            with httpx.Client() as client:
                # 步骤 1：initialize 握手
                init_body = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": _WIND_PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": "StockAnalSys", "version": "1.0"},
                    },
                }
                init_resp = client.post(endpoint, headers=headers, json=init_body,
                                        timeout=_WIND_INIT_TIMEOUT)
                init_resp.raise_for_status()
                # initialize 同为 SSE：过 _parse_mcp_response 校验握手成功（不取业务数据）
                self._parse_mcp_response(init_resp)

                # 步骤 2：tools/call
                call_body = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": arguments, "_meta": {}},
                }
                resp = client.post(endpoint, headers=headers, json=call_body,
                                   timeout=self._call_timeout)
                resp.raise_for_status()
                payload = self._parse_mcp_response(resp)
        except httpx.TimeoutException as e:
            logger.warning(f"Wind 调用超时 tool={tool}: {type(e).__name__}: {e}")
            return None
        except httpx.HTTPStatusError as e:
            status = e.response.status_code if e.response is not None else '?'
            # 401/403 视为鉴权失败；429 视为限流；均静默降级
            logger.warning(f"Wind HTTP 错误 tool={tool} status={status}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Wind 调用异常 tool={tool}: {type(e).__name__}: {e}")
            return None

        # JSON-RPC error 信封
        if isinstance(payload, dict) and payload.get('error'):
            logger.warning(f"Wind JSON-RPC error tool={tool}: {payload.get('error')}")
            return None

        # 解析 result.content[0].text
        try:
            content = payload['result']['content']
            text = content[0]['text']
        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"Wind 响应结构异常 tool={tool}: {type(e).__name__}: {e}")
            return None

        # text 若为 JSON 字符串则二次解析
        if isinstance(text, str):
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError):
                return {'text': text}
        else:
            parsed = text

        # 业务信封 {ok:false, error:{code}} → 配额/鉴权静默降级
        if isinstance(parsed, dict) and parsed.get('ok') is False:
            err = parsed.get('error') or {}
            err_code = str(err.get('code', '')).upper() if isinstance(err, dict) else str(err).upper()
            if err_code in _QUOTA_ERROR_CODES:
                logger.warning(f"Wind 额度/限流降级 tool={tool} code={err_code}")
            elif err_code in _AUTH_ERROR_CODES:
                logger.warning(f"Wind 鉴权失败降级 tool={tool} code={err_code}")
            else:
                logger.warning(f"Wind 业务错误 tool={tool} error={err}")
            return None

        return parsed

    def _in_cooldown(self, key: tuple) -> bool:
        """P1.5：判断 (windcode, tool) 是否处于失败冷却窗内。"""
        with self._fail_lock:
            ts = self._fail_ts.get(key)
            if ts is None:
                return False
            if time.monotonic() - ts < self._fail_cooldown:
                return True
            # 冷却窗已过，清除过期记录
            self._fail_ts.pop(key, None)
            return False

    def _mark_fail(self, key: tuple) -> None:
        with self._fail_lock:
            self._fail_ts[key] = time.monotonic()

    def _clear_fail(self, key: tuple) -> None:
        with self._fail_lock:
            self._fail_ts.pop(key, None)

    def _call_wind(self, server_type: str, tool: str, windcode: str,
                   params: dict, tier: str, ttl_seconds: int) -> Optional[dict]:
        """统一取数：缓存优先 → 失败熔断 → 配额闸门 → HTTP → 写缓存。

        额度权衡（P1）：HTTP 调用失败不回滚已消费额度——失败已实际消耗 1 次尝试，
        若回滚会导致网络抖动下对同一标的无限重试持续烧额度，故宁可记 WARNING 计入消耗。

        失败短时熔断（P1.5）：缓存命中仍优先返回（0 积分）；缓存未命中时，若该
        (windcode, tool) 在冷却窗（WIND_FAIL_COOLDOWN，默认 300s）内，直接降级 None，
        不消费额度、不发 HTTP；HTTP 失败写入 last_fail_ts，成功则清除该键。
        """
        if not self._enabled:
            return None

        # 1) 缓存优先（0 积分）—— 始终最先，熔断不影响缓存命中
        cached = self._cache.get(tool, windcode, params)
        if cached is not None:
            return cached

        fail_key = (windcode, tool)

        # 2) 失败熔断：缓存未命中且在冷却窗内 → 降级，不消费额度
        if self._in_cooldown(fail_key):
            logger.warning(
                f"Wind 熔断冷却中降级（不消费额度）tier={tier} tool={tool} windcode={windcode}"
            )
            return None

        # 3) 配额闸门
        if not self._quota.try_consume(tier):
            logger.warning(f"Wind 日额度耗尽降级 tier={tier} tool={tool} windcode={windcode}")
            return None

        # 4) HTTP 调用（失败不回滚额度，见 docstring）
        result = self._http_call_wind(server_type, tool, params)
        if result is None:
            self._mark_fail(fail_key)
            logger.warning(
                f"Wind 调用失败但已消耗 1 次 {tier} 档额度，进入熔断冷却 "
                f"tool={tool} windcode={windcode}"
            )
            return None

        # 5) 成功：清除熔断标记 + 写缓存
        self._clear_fail(fail_key)
        self._cache.set(tool, windcode, params, result, ttl_seconds, tier)
        return result

    # ============================ BaseAdapter 6 方法 ============================

    def health_check(self) -> bool:
        """不烧积分、不连网：仅检查 WIND_API_KEY 是否配置。

        真实连通性（initialize 握手）留 P2 真机验证。
        """
        return self._enabled

    def get_stock_info(self, code: str) -> Dict:
        """股票基本信息（B 档，TTL 7 天）。未启用/降级时返回 {}。"""
        windcode = _to_windcode(code)
        result = self._call_wind(
            'stock_data', 'get_stock_basicinfo', windcode,
            {'windcode': windcode}, tier='B', ttl_seconds=_TTL_7D,
        )
        return result if isinstance(result, dict) else {}

    def get_financial_data(self, code: str) -> Dict:
        """财务数据（S 档，TTL 30 天）。未启用/降级时返回 {}。"""
        windcode = _to_windcode(code)
        result = self._call_wind(
            'stock_data', 'get_stock_fundamentals', windcode,
            {'windcode': windcode}, tier='S', ttl_seconds=_TTL_30D,
        )
        return result if isinstance(result, dict) else {}

    def get_index_stocks(self, index_code: str) -> List[str]:
        """Wind 无成分股工具 → 直接返回 []（降级缺口，由其它适配器补齐）。"""
        logger.debug("Wind 无指数成分股工具，返回空列表，交由其它适配器")
        return []

    def get_stock_history(self, code: str, start_date: str, end_date: str,
                          adjust: str = "qfq") -> Optional[pd.DataFrame]:
        """行情 K 线不走 Wind 的策略：返回 None 降级到免费源（akshare/baostock）。

        注意：本方法不应注册到高频行情域（a_stock_kline/realtime），否则会误烧积分。
        Wind 的 get_stock_kline 留待 P3 评估是否在低频/特殊场景启用。
        """
        logger.debug("Wind 不参与高频行情 K 线，返回 None 降级到免费源")
        return None
