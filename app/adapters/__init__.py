# 数据源适配器模块
from .base_adapter import BaseAdapter
from .akshare_adapter import AkshareAdapter
from .baostock_adapter import BaostockAdapter
from .opencli_bridge import OpenCLIBridge
from .edgar_adapter import EDGARAdapter

__all__ = ['BaseAdapter', 'AkshareAdapter', 'BaostockAdapter', 'OpenCLIBridge', 'EDGARAdapter']
