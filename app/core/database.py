import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

logger = logging.getLogger(__name__)

# 读取配置
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/stock_analyzer.db')
USE_DATABASE = os.getenv('USE_DATABASE', 'False').lower() == 'true'

# 创建引擎
engine = create_engine(DATABASE_URL)
Base = declarative_base()


def _init_schema_version(engine, target_version=1):
    """初始化或检查 schema 版本（使用 SQLite PRAGMA user_version）。

    版本策略：
    - current == 0（首次）：初始化为 target_version
    - current < target_version：需要迁移（预留钩子）
    - current > target_version：代码过旧，需升级
    - current == target_version：版本匹配，正常运行

    Args:
        engine: SQLAlchemy engine
        target_version: 当前代码期望的 schema 版本

    Returns:
        int: 数据库当前 schema 版本

    Raises:
        RuntimeError: 数据库版本过新，需要升级代码
    """
    # 仅 sqlite 支持 PRAGMA user_version（其他 DB 跳过）
    if not engine.url.drivername.startswith('sqlite'):
        logger.info(f"非 sqlite 引擎 ({engine.url.drivername})，跳过 schema 版本检查")
        return target_version

    # 使用 raw DBAPI connection 执行 PRAGMA
    with engine.connect() as conn:
        raw_conn = conn.connection.dbapi_connection
        cursor = raw_conn.execute('PRAGMA user_version')
        current = cursor.fetchone()[0]

        if current == 0:
            # 首次初始化
            raw_conn.execute(f'PRAGMA user_version = {target_version}')
            raw_conn.commit()
            logger.info(f"数据库 schema 初始化版本: v{target_version} ({engine.url.database})")
        elif current < target_version:
            # 需要迁移（预留钩子）
            logger.warning(
                f"数据库 schema 版本过旧: v{current} < v{target_version}，"
                f"建议运行迁移脚本 (参考 docs/migrations/README.md)"
            )
            # 未来可在此加 migration 逻辑：
            # if current == 1 and target_version == 2:
            #     _migrate_v1_to_v2(conn)
            #     raw_conn.execute(f'PRAGMA user_version = {target_version}')
        elif current > target_version:
            raise RuntimeError(
                f"数据库版本过新: v{current} > v{target_version}，"
                f"请升级代码或回退数据库版本"
            )
        else:
            logger.debug(f"schema 版本匹配: v{current} ({engine.url.database})")

        return current


# 定义模型
class StockInfo(Base):
    __tablename__ = 'stock_info'

    id = Column(Integer, primary_key=True)
    stock_code = Column(String(10), nullable=False, index=True)
    stock_name = Column(String(50))
    market_type = Column(String(5))
    industry = Column(String(50))
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'market_type': self.market_type,
            'industry': self.industry,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }


class AnalysisResult(Base):
    __tablename__ = 'analysis_results'

    id = Column(Integer, primary_key=True)
    stock_code = Column(String(10), nullable=False, index=True)
    market_type = Column(String(5))
    analysis_date = Column(DateTime, default=datetime.now)
    score = Column(Float)
    recommendation = Column(String(100))
    technical_data = Column(JSON)
    fundamental_data = Column(JSON)
    capital_flow_data = Column(JSON)
    ai_analysis = Column(Text)

    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'market_type': self.market_type,
            'analysis_date': self.analysis_date.strftime('%Y-%m-%d %H:%M:%S') if self.analysis_date else None,
            'score': self.score,
            'recommendation': self.recommendation,
            'technical_data': self.technical_data,
            'fundamental_data': self.fundamental_data,
            'capital_flow_data': self.capital_flow_data,
            'ai_analysis': self.ai_analysis
        }


class Portfolio(Base):
    __tablename__ = 'portfolios'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)
    name = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    stocks = Column(JSON)  # 存储股票列表的JSON

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
            'stocks': self.stocks
        }


# 创建会话工厂
Session = sessionmaker(bind=engine)


# 初始化数据库
def init_db():
    Base.metadata.create_all(engine)


# 获取数据库会话
def get_session():
    return Session()


# 如果启用数据库，则初始化
if USE_DATABASE:
    init_db()
    # 初始化 schema 版本控制
    _init_schema_version(engine, target_version=1)
