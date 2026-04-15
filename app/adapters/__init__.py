# 数据源适配器模块
from .base_adapter import BaseAdapter
from .akshare_adapter import AkshareAdapter
from .baostock_adapter import BaostockAdapter
from .opencli_bridge import OpenCLIBridge
from .edgar_adapter import EDGARAdapter
from .nbs_adapter import NBSAdapter
from .fred_adapter import FREDAdapter
from .ccxt_adapter import CCXTAdapter
from .coingecko_adapter import CoinGeckoAdapter
from .worldbank_adapter import WorldBankAdapter
from .imf_adapter import IMFAdapter

__all__ = ['BaseAdapter', 'AkshareAdapter', 'BaostockAdapter', 'OpenCLIBridge',
           'EDGARAdapter', 'NBSAdapter', 'FREDAdapter', 'CCXTAdapter',
           'CoinGeckoAdapter', 'WorldBankAdapter', 'IMFAdapter']
