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
from .rss_news_adapter import RSSNewsAdapter
from .efinance_adapter import EfinanceAdapter
from .yfinance_adapter import YFinanceAdapter
from .ashare_adapter import AshareAdapter
from .easyquotation_adapter import EasyquotationAdapter
from .openbb_adapter import OpenBBAdapter
from .adapter_registry import AdapterRegistry

__all__ = ['BaseAdapter', 'AkshareAdapter', 'BaostockAdapter', 'OpenCLIBridge',
           'EDGARAdapter', 'NBSAdapter', 'FREDAdapter', 'CCXTAdapter',
           'CoinGeckoAdapter', 'WorldBankAdapter', 'IMFAdapter',
           'RSSNewsAdapter', 'EfinanceAdapter', 'YFinanceAdapter',
           'AshareAdapter', 'EasyquotationAdapter', 'OpenBBAdapter',
           'AdapterRegistry']
