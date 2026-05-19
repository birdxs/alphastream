# -*- coding: utf-8 -*-
"""
通用重试+UA池工具 [NEW-FILE:#20260415-44]
Input: HTTP GET 调用函数 / 可重试状态码集合 / UA 字符串需求
Output: random_ua() -> str / retry_with_backoff(func,...) -> Any / build_session_with_ua(...) -> requests.Session
       get_thread_local_session(...) -> requests.Session  (thread-safe, S3-A3 2026-05-20)
Pos: app/adapters 层通用底座，被 shipping/nbs/corporate/esg/rss_news/efinance 复用

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

联网调研权威源 (检索时间 2026-04-15 14:35 +08:00, ≥3 源)：
  1. requests 官方文档 Retry/Adapter https://requests.readthedocs.io/en/latest/user/advanced/
     - 指数退避 backoff_factor=0.3 / 429/5xx 推荐 retry
  2. urllib3 Retry https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html
     - status_forcelist=[429,500,502,503,504], backoff_factor 指数
  3. Chrome UA 公开数据 https://www.whatismybrowser.com/guides/the-latest-user-agent/
     - 采样 2025-Q1 ~ 2026-Q1 主流稳定UA (Chrome122~124, Firefox123, Safari17)
  4. cloudflare/akamai 反爬对抗常识：UA轮询 + Referer伪造 + Accept-Language 本地化
  5. eastmoney反爬研究 GitHub Micro-sheep/efinance issue #xx
     - 单UA固化易被封 → 池化随机 可显著缓解

约束：
  - 零新增 pip 依赖（仅标准库 + requests 已存在）
  - 所有重试最终失败：调用方保持软降级 (空DF/空dict)，不抛异常
"""
from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any, Callable, Iterable, Optional, Tuple

import requests

# S3-A3: thread-local session 存储，保证多线程下每线程独立 Session
# requests.Session 非线程安全（issue #1871），通过 threading.local() 隔离
_thread_local = threading.local()

logger = logging.getLogger(__name__)


# 采样 2025-Q4 ~ 2026-Q1 主流浏览器稳定 UA (桌面优先)
UA_POOL: Tuple[str, ...] = (
    # Chrome 122~124 Win/Mac/Linux
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Firefox 123/124
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.3; rv:123.0) Gecko/20100101 Firefox/123.0",
    # Safari 17
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    # Edge 124
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
)


def random_ua() -> str:
    """随机返回一条 UA，池化轮询对抗反爬"""
    return random.choice(UA_POOL)


DEFAULT_RETRY_STATUS = (429, 500, 502, 503, 504)


def retry_with_backoff(
    func: Callable[[], Any],
    *,
    max_retries: int = 3,
    backoff_base: float = 0.5,
    backoff_cap: float = 8.0,
    status_codes_to_retry: Iterable[int] = DEFAULT_RETRY_STATUS,
    jitter: float = 0.3,
    name: str = "http",
) -> Any:
    """通用重试包装器，支持对 requests.Response 状态码 / 异常两类场景重试。

    语义：
      - func 无参 callable，返回任意对象；若返回 requests.Response，按 status_codes_to_retry 判定；
      - 捕获 requests.RequestException / OSError / TimeoutError 视为可重试；
      - 退避：sleep = min(backoff_cap, backoff_base * 2**(attempt-1)) + random(0, jitter)
      - 所有重试耗尽：返回最后一次结果 (即使是坏状态码) 或 raise 最后异常 — 由调用方软降级。

    Args:
        func: 无参可调用，通常 lambda: session.get(url, ...)
        max_retries: 总尝试次数（含首次），≥1
        backoff_base: 退避基数秒
        backoff_cap:  退避上限秒
        status_codes_to_retry: 触发重试的 HTTP 状态码
        jitter: 随机抖动上限秒
        name: 日志标识

    Returns:
        func 最终结果；即便是坏 Response 也会返回（由调用方决定是否作为软降级返回空）。
    """
    max_retries = max(1, int(max_retries))
    last_exc: Optional[BaseException] = None
    last_result: Any = None
    retry_codes = set(status_codes_to_retry or ())

    for attempt in range(1, max_retries + 1):
        try:
            result = func()
            last_result = result
            # 若返回对象含 status_code (Response 或 Mock)，按状态码判定
            status = getattr(result, "status_code", None)
            if isinstance(status, int):
                if status in retry_codes:
                    logger.debug(
                        "[retry:%s] HTTP %s attempt=%d/%d",
                        name, result.status_code, attempt, max_retries,
                    )
                    if attempt < max_retries:
                        _sleep_backoff(attempt, backoff_base, backoff_cap, jitter)
                        continue
                return result
            # 非 Response 直接返回
            return result
        except (requests.RequestException, OSError, TimeoutError) as e:
            last_exc = e
            logger.debug(
                "[retry:%s] %s attempt=%d/%d: %s",
                name, type(e).__name__, attempt, max_retries, e,
            )
            if attempt < max_retries:
                _sleep_backoff(attempt, backoff_base, backoff_cap, jitter)
                continue
            # 最终失败：raise 最后异常，调用方 try/except 软降级
            raise

    # 退出循环（状态码耗尽路径）
    if last_exc is not None:
        raise last_exc
    return last_result


def _sleep_backoff(attempt: int, base: float, cap: float, jitter: float) -> None:
    delay = min(cap, base * (2 ** (attempt - 1)))
    if jitter > 0:
        delay += random.random() * jitter
    time.sleep(delay)


def build_session_with_ua(
    *,
    extra_headers: Optional[dict] = None,
    referer: Optional[str] = None,
) -> requests.Session:
    """构建带随机UA + 通用伪装头的 requests.Session。

    用法：
        s = build_session_with_ua(referer="https://www.investing.com/")
    Session 级 header 固化为首次随机UA；若需每请求轮询，调用方在 get 前 s.headers["User-Agent"] = random_ua()。
    """
    s = requests.Session()
    headers = {
        "User-Agent": random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer
    if extra_headers:
        headers.update(extra_headers)
    s.headers.update(headers)
    return s


def rotate_ua(session: requests.Session) -> str:
    """对已有 Session 轮询替换 UA，返回新UA"""
    ua = random_ua()
    session.headers["User-Agent"] = ua
    return ua


def get_thread_local_session(
    *,
    extra_headers: Optional[dict] = None,
    referer: Optional[str] = None,
    namespace: str = "default",
) -> requests.Session:
    """获取当前线程独立的 requests.Session（thread-safe, S3-A3 2026-05-20）。

    requests.Session 非线程安全（https://github.com/psf/requests/issues/1871）。
    本函数通过 threading.local() 为每个线程维护独立 Session，避免并发 race condition。

    Args:
        extra_headers: 附加请求头（仅在首次创建 Session 时应用）
        referer: Referer 头（仅在首次创建时应用）
        namespace: Session 命名空间，同一线程内不同 adapter 可用不同 ns 隔离

    Returns:
        当前线程专属的 requests.Session 实例
    """
    attr = f"_session_{namespace}"
    sess: Optional[requests.Session] = getattr(_thread_local, attr, None)
    if sess is None:
        sess = build_session_with_ua(extra_headers=extra_headers, referer=referer)
        setattr(_thread_local, attr, sess)
    return sess
