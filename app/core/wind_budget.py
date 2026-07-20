# -*- coding: utf-8 -*-
"""
Input: 工具名/windcode/参数/payload、各档日预算 env（WIND_QUOTA_S/A/B）、WIND_DATABASE_URL
Output: 持久化缓存命中结果（WindCache）与日配额闸门判定（WindQuota.try_consume/remaining）
Pos: app/core/wind_budget.py - Wind 数据源「省积分」底座；独立 sqlite 引擎（不碰业务库），供 wind_adapter 在取数前查缓存/控额度；schema 版本控制（PRAGMA user_version）

一旦我被修改，请更新我的头部注释，以及所属文件夹的 md。

[NEW-FILE:#20260529-WIND-01]

设计要点：
1. 独立引擎：WIND_DATABASE_URL（默认 sqlite:///data/wind_cache.db），与项目 USE_DATABASE 开关无关，
   不触碰 app/core/database.py 的休眠业务库；sqlite 连接 check_same_thread=False 允许多线程共享。
2. SQLAlchemy 写法对齐 app/core/database.py（declarative_base/create_engine/sessionmaker）。
3. 时间统一 +08:00 感知（_now_cn），与项目 now_cn 范式一致。
4. RLock 保护读改写，session 用完即关，避免连接泄漏。
5. schema 版本控制：使用 PRAGMA user_version（复用 database._init_schema_version）。
"""
import os
import json
import hashlib
import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 导入 database._init_schema_version 以复用 schema 版本控制逻辑
try:
    from app.core.database import _init_schema_version
except ImportError:
    # 降级：如果导入失败（如测试环境缺少 database.py），提供 stub 实现
    def _init_schema_version(engine, target_version=1):
        """Stub 实现（仅在导入失败时使用）。"""
        logger.warning("未能导入 database._init_schema_version，跳过 schema 版本检查")
        return target_version

logger = logging.getLogger(__name__)

# +08:00 时区感知（对齐项目 now_cn 范式）
_ASIA_SHANGHAI = timezone(timedelta(hours=8))


def _now_cn() -> datetime:
    """返回带 +08:00 的当前时间。"""
    return datetime.now(_ASIA_SHANGHAI)


# ── 独立引擎：与业务库（DATABASE_URL/USE_DATABASE）完全隔离 ──
WIND_DATABASE_URL = os.getenv('WIND_DATABASE_URL', 'sqlite:///data/wind_cache.db')

_WindBase = declarative_base()


class WindCacheRow(_WindBase):
    """Wind 取数结果持久化缓存表。"""
    __tablename__ = 'wind_cache'

    id = Column(Integer, primary_key=True)
    cache_key = Column(String(64), unique=True, index=True, nullable=False)
    tool = Column(String(128))
    windcode = Column(String(32))
    params_json = Column(Text)
    payload_json = Column(Text)
    tier = Column(String(8))
    fetched_at = Column(DateTime)
    expires_at = Column(DateTime)


class WindQuotaRow(_WindBase):
    """Wind 日配额计数表，按 +08:00 自然日 day 主键。"""
    __tablename__ = 'wind_quota'

    day = Column(String(10), primary_key=True)  # 'YYYY-MM-DD' +08:00 自然日
    used_s = Column(Integer, default=0)
    used_a = Column(Integer, default=0)
    used_b = Column(Integer, default=0)


def _build_engine(database_url: str):
    """构造独立引擎；sqlite 需 check_same_thread=False 以便多线程共享连接。

    P1.5：sqlite 方言开 WAL（对照业务库 S1-C6）——WAL 提升并发读写、
    synchronous=NORMAL 平衡安全与性能、busy_timeout=5000 缓解多线程锁竞争。
    非 sqlite（如 pgsql）跳过这些 PRAGMA。WindCache 与 WindQuota 两个引擎都生效。
    """
    if database_url.startswith('sqlite'):
        engine = create_engine(database_url, connect_args={'check_same_thread': False})
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql('PRAGMA journal_mode=WAL')
                conn.exec_driver_sql('PRAGMA synchronous=NORMAL')
                conn.exec_driver_sql('PRAGMA busy_timeout=5000')
        except Exception as e:  # noqa: BLE001 — PRAGMA 失败不应阻断引擎可用
            logger.warning(f"Wind sqlite PRAGMA 设置失败（降级继续）: {type(e).__name__}: {e}")
        return engine
    return create_engine(database_url)


def _make_cache_key(tool: str, windcode: str, params: dict) -> str:
    """cache_key = sha256(tool|windcode|sorted(params))。

    sorted(params) 确保参数顺序无关；payload 不参与 key（key 仅标识请求）。
    """
    params = params or {}
    items = sorted((str(k), str(v)) for k, v in params.items())
    raw = f"{tool}|{windcode}|{items}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


class WindCache:
    """Wind 取数结果持久化缓存（DB 无关，默认 sqlite）。

    命中且未过期返回解析后的 payload（0 积分），否则 None。
    """

    def __init__(self, database_url: str = None):
        self._url = database_url or WIND_DATABASE_URL
        self._engine = _build_engine(self._url)
        _WindBase.metadata.create_all(self._engine)
        # 初始化 schema 版本控制（v1）
        _init_schema_version(self._engine, target_version=1)
        self._Session = sessionmaker(bind=self._engine)
        self._lock = threading.RLock()

    def get(self, tool: str, windcode: str, params: dict):
        """命中且 expires_at > now 返回 payload(dict)，否则 None。"""
        key = _make_cache_key(tool, windcode, params)
        with self._lock:
            session = self._Session()
            try:
                row = session.query(WindCacheRow).filter(
                    WindCacheRow.cache_key == key
                ).first()
                if row is None:
                    return None
                # expires_at 落库为 naive（sqlite 不存 tz），以本地 naive 比较
                now_naive = _now_cn().replace(tzinfo=None)
                if row.expires_at is None or row.expires_at <= now_naive:
                    return None
                try:
                    return json.loads(row.payload_json)
                except (TypeError, ValueError) as e:
                    logger.warning(f"WindCache payload 解析失败 key={key[:12]}: {e}")
                    return None
            finally:
                session.close()

    def set(self, tool: str, windcode: str, params: dict, payload: dict,
            ttl_seconds: int, tier: str):
        """upsert 缓存：写 fetched_at/expires_at。"""
        key = _make_cache_key(tool, windcode, params)
        fetched = _now_cn().replace(tzinfo=None)
        expires = fetched + timedelta(seconds=int(ttl_seconds))
        payload_json = json.dumps(payload, ensure_ascii=False)
        params_json = json.dumps(params or {}, ensure_ascii=False, sort_keys=True)
        with self._lock:
            session = self._Session()
            try:
                row = session.query(WindCacheRow).filter(
                    WindCacheRow.cache_key == key
                ).first()
                if row is None:
                    row = WindCacheRow(cache_key=key)
                    session.add(row)
                row.tool = tool
                row.windcode = windcode
                row.params_json = params_json
                row.payload_json = payload_json
                row.tier = tier
                row.fetched_at = fetched
                row.expires_at = expires
                session.commit()
            except Exception as e:
                session.rollback()
                logger.warning(f"WindCache set 失败 key={key[:12]}: {type(e).__name__}: {e}")
            finally:
                session.close()


class WindQuota:
    """Wind 日配额闸门：S/A/B 三档硬隔离，按 +08:00 自然日重置，持久化跨重启不丢。"""

    def __init__(self, database_url: str = None):
        self._url = database_url or WIND_DATABASE_URL
        self._engine = _build_engine(self._url)
        _WindBase.metadata.create_all(self._engine)
        # 初始化 schema 版本控制（v1）
        _init_schema_version(self._engine, target_version=1)
        self._Session = sessionmaker(bind=self._engine)
        self._lock = threading.RLock()
        # 各档日预算（env 驱动）
        self._budget = {
            'S': int(os.getenv('WIND_QUOTA_S', '50')),
            'A': int(os.getenv('WIND_QUOTA_A', '30')),
            'B': int(os.getenv('WIND_QUOTA_B', '20')),
        }

    @staticmethod
    def _today() -> str:
        return _now_cn().strftime('%Y-%m-%d')

    def _used_attr(self, tier: str) -> str:
        return {'S': 'used_s', 'A': 'used_a', 'B': 'used_b'}[tier]

    def _get_or_create_row(self, session, day: str) -> WindQuotaRow:
        row = session.query(WindQuotaRow).filter(WindQuotaRow.day == day).first()
        if row is None:
            row = WindQuotaRow(day=day, used_s=0, used_a=0, used_b=0)
            session.add(row)
            session.flush()
        return row

    def try_consume(self, tier: str) -> bool:
        """该 tier 当日已用 < 预算则 +1 持久化返回 True，否则 False（额度耗尽）。

        硬隔离：低档不可借高档；day 变更则按新 day 计数（旧 day 行保留作审计）。
        配额告警（2026-07-09）：>90% ERROR，>70% WARNING。
        """
        if tier not in self._budget:
            logger.warning(f"WindQuota 未知档位 tier={tier}，拒绝消费")
            return False
        attr = self._used_attr(tier)
        budget = self._budget[tier]
        day = self._today()
        with self._lock:
            session = self._Session()
            try:
                row = self._get_or_create_row(session, day)
                used = getattr(row, attr) or 0
                if used >= budget:
                    session.commit()  # 落地可能新建的 day 行
                    return False

                # 配额告警（消费前检查）
                new_used = used + 1
                usage_pct = (new_used / budget) * 100
                if usage_pct > 90:
                    logger.error(
                        f"[ALERT] Wind {tier}档配额告急: {new_used}/{budget} (已用 {usage_pct:.1f}%)"
                    )
                elif usage_pct > 70:
                    logger.warning(
                        f"[WARN] Wind {tier}档配额偏低: {new_used}/{budget} (已用 {usage_pct:.1f}%)"
                    )

                setattr(row, attr, new_used)
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                logger.warning(f"WindQuota try_consume 失败 tier={tier}: {type(e).__name__}: {e}")
                return False
            finally:
                session.close()

    def remaining(self) -> dict:
        """返回各档当日剩余额度，供监控。"""
        day = self._today()
        with self._lock:
            session = self._Session()
            try:
                row = session.query(WindQuotaRow).filter(WindQuotaRow.day == day).first()
                used_s = (row.used_s if row else 0) or 0
                used_a = (row.used_a if row else 0) or 0
                used_b = (row.used_b if row else 0) or 0
                return {
                    'S': max(0, self._budget['S'] - used_s),
                    'A': max(0, self._budget['A'] - used_a),
                    'B': max(0, self._budget['B'] - used_b),
                }
            finally:
                session.close()
