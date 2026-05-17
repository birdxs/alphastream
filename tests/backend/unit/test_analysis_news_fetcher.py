# Input  : NewsFetcher 单元测试，mock akshare + 临时 save_dir + 调度器线程拦截
# Output : pytest 用例（实例化/抓取/落盘/调度器/边界）
# Pos    : tests/backend/unit/test_analysis_news_fetcher.py - BE-06c 第 3/5
"""BE-06c #3: NewsFetcher 单元测试。

调度器测试关键：不真启动后台线程（monkeypatch threading.Thread）。
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.analysis import news_fetcher as nf_mod
from app.analysis.news_fetcher import NewsFetcher


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def tmp_news_dir(tmp_path):
    d = tmp_path / "news"
    d.mkdir()
    return str(d)


@pytest.fixture
def fetcher(tmp_news_dir):
    return NewsFetcher(save_dir=tmp_news_dir)


@pytest.fixture
def cls_df() -> pd.DataFrame:
    """模拟 ak.stock_info_global_cls 返回。"""
    return pd.DataFrame(
        [
            {"标题": "央行降准", "内容": "中国人民银行宣布降准0.5个百分点。",
             "发布日期": "2026-05-17", "发布时间": "10:30:00"},
            {"标题": "", "内容": "A股三大指数集体收涨，沪指涨1.2%。某科技股领涨。",
             "发布日期": "2026-05-17", "发布时间": "15:00:00"},
            {"标题": "新能源板块异动", "内容": "新能源板块午后拉升。",
             "发布日期": "2026-05-17", "发布时间": "14:00:00"},
        ]
    )


# --------------------------------------------------------------------------- #
# Cases
# --------------------------------------------------------------------------- #
def test_instantiate(fetcher, tmp_news_dir):
    """用例 1：实例化 + 目录创建 + 哈希集初始化。"""
    assert os.path.isdir(tmp_news_dir)
    assert fetcher.save_dir == tmp_news_dir
    assert isinstance(fetcher.news_hashes, set)
    assert fetcher.last_fetch_time is None


def test_calculate_hash(fetcher):
    """用例 2：内容哈希计算（规范化）。"""
    h1 = fetcher._calculate_hash("hello world")
    h2 = fetcher._calculate_hash("hello   world  ")  # 多空白
    assert h1 == h2
    assert fetcher._calculate_hash("") is None


def test_derive_title():
    """用例 3：标题派生 - 含句末标点和长截断。"""
    assert NewsFetcher._derive_title("中央财办：稳楼市。后续动作。") == "中央财办：稳楼市"
    long = "x" * 50
    assert NewsFetcher._derive_title(long).endswith("…")
    assert NewsFetcher._derive_title("") == ""


def test_compose_published_at():
    """用例 4：时间字段组装为 ISO8601 +08:00。"""
    r = NewsFetcher._compose_published_at("2026-05-17", "10:30:00")
    assert r == "2026-05-17T10:30:00+08:00"
    # 全空
    assert NewsFetcher._compose_published_at("", "") == ""
    # 不合规
    assert NewsFetcher._compose_published_at("bad", "bad") == ""


def test_get_news_filename(fetcher, tmp_news_dir):
    """用例 5：文件名拼接。"""
    fname = fetcher.get_news_filename(date=datetime(2026, 5, 17))
    assert fname.endswith("news_20260517.json")
    assert fname.startswith(tmp_news_dir)


def test_fetch_and_save_ok(fetcher, cls_df, tmp_news_dir):
    """用例 6：fetch_and_save - mock akshare，落盘到 tmp_news_dir。"""
    with patch("app.analysis.news_fetcher.ak.stock_info_global_cls",
               return_value=cls_df):
        ok = fetcher.fetch_and_save()
    assert ok is True
    files = os.listdir(tmp_news_dir)
    assert len(files) == 1
    with open(os.path.join(tmp_news_dir, files[0]), "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 3
    # title 派生
    derived = [x for x in data if x["content"].startswith("A股三大指数")][0]
    assert derived["title"]  # 派生出来非空
    # source / published_at
    for it in data:
        assert it["source"] == "财联社"
        assert it["published_at"].startswith("2026-05-17T")
        assert "hash" in it


def test_fetch_and_save_empty(fetcher):
    """用例 7：边界 - akshare 返回空 DataFrame。"""
    with patch("app.analysis.news_fetcher.ak.stock_info_global_cls",
               return_value=pd.DataFrame()):
        ok = fetcher.fetch_and_save()
    assert ok is False


def test_fetch_and_save_exception(fetcher):
    """用例 8：边界 - akshare 抛异常。"""
    with patch("app.analysis.news_fetcher.ak.stock_info_global_cls",
               side_effect=RuntimeError("net")):
        ok = fetcher.fetch_and_save()
    assert ok is False


def test_fetch_news_task(monkeypatch):
    """用例 9：fetch_news_task 调用 news_fetcher.fetch_and_save。"""
    called = {"n": 0}

    def fake_fetch():
        called["n"] += 1
        return True

    monkeypatch.setattr(nf_mod.news_fetcher, "fetch_and_save", fake_fetch)
    nf_mod.fetch_news_task()
    assert called["n"] == 1


def test_start_news_scheduler_no_real_thread(monkeypatch):
    """用例 10：start_news_scheduler 不真启动后台线程。

    关键：用 MagicMock 替换 threading.Thread，避免真起死循环。
    """
    import threading as _t
    fake_thread_instance = MagicMock()
    fake_thread_cls = MagicMock(return_value=fake_thread_instance)
    monkeypatch.setattr(_t, "Thread", fake_thread_cls)

    nf_mod.start_news_scheduler()

    # Thread 应被创建并 start 一次
    assert fake_thread_cls.call_count == 1
    fake_thread_instance.start.assert_called_once()
    # daemon 标志应被设置
    assert fake_thread_instance.daemon is True


def test_get_latest_news_empty(fetcher):
    """用例 11：get_latest_news - tmp_news_dir 下无文件。"""
    result = fetcher.get_latest_news(days=1, limit=10)
    assert result == []


def test_get_latest_news_with_file(fetcher, tmp_news_dir):
    """用例 12：get_latest_news - 写入文件后读取。"""
    today_name = fetcher.get_news_filename()
    sample = [
        {"title": "T1", "content": "C1", "date": "2026-05-17", "time": "10:00:00",
         "datetime": "2026-05-17 10:00:00", "hash": "h1", "source": "财联社",
         "published_at": "2026-05-17T10:00:00+08:00", "fetch_time": "x"},
        {"title": "T2", "content": "C2", "date": "2026-05-17", "time": "11:00:00",
         "datetime": "2026-05-17 11:00:00", "hash": "h2", "source": "财联社",
         "published_at": "2026-05-17T11:00:00+08:00", "fetch_time": "x"},
    ]
    with open(today_name, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False)
    result = fetcher.get_latest_news(days=1, limit=10)
    assert isinstance(result, list)
    assert len(result) == 2
