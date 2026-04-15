# -*- coding: utf-8 -*-
"""
全局HTTP代理工具 [NEW-FILE:#20260415-38]
Input: 环境变量 HTTP_PROXY / HTTPS_PROXY / http_proxy / https_proxy
Output: get_proxies() -> dict | None (requests兼容) / get_proxy_url() -> str | None (yfinance/ccxt单串)
Pos: app/adapters层，统一代理读取入口，消除境内访问境外源(Yahoo/EDGAR/FRED/Binance...)的科学上网痛点

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

联网调研权威源 (2026-04-15 13:52 +08:00)：
  1. https://requests.readthedocs.io/en/latest/user/advanced/#proxies
     - requests.Session 默认 trust_env=True，自动读取 HTTP_PROXY/HTTPS_PROXY/NO_PROXY env
     - 显式 proxies= 参数会覆盖 env
  2. https://ranaroussi.github.io/yfinance/ - yf.Ticker(..., proxy="http://host:port") 底层传给 requests
  3. https://docs.ccxt.com/#/?id=proxy - exchange({"proxies": {"http":..., "https":...}}) 字典注入
  4. Python 12-factor：优先 env 统一配置，代码不硬编码代理地址
"""
from __future__ import annotations

import os
from typing import Dict, Optional


def get_proxies() -> Optional[Dict[str, str]]:
    """从env读取HTTP_PROXY/HTTPS_PROXY(大小写兼容)，返回requests兼容dict或None。

    Returns:
        {"http": "...", "https": "..."} 或 None (未配置)
    """
    http = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if not http and not https:
        return None
    proxies: Dict[str, str] = {}
    if http:
        proxies["http"] = http
    if https:
        proxies["https"] = https
    # 若只给一个，另一个也用它（便于单端口通吃）
    if "http" not in proxies and "https" in proxies:
        proxies["http"] = proxies["https"]
    if "https" not in proxies and "http" in proxies:
        proxies["https"] = proxies["http"]
    return proxies


def get_proxy_url() -> Optional[str]:
    """返回单一proxy URL字符串 (yfinance/ccxt/feedparser等场景)。优先HTTPS_PROXY。"""
    return (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
        or None
    )
