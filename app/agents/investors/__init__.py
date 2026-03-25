"""
Input: 无
Output: 投资者人格Agent模块导出
Pos: app/agents/investors/__init__.py - 投资者人格子系统入口

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
from .buffett import BuffettAgent
from .munger import MungerAgent
from .lynch import LynchAgent
from .damodaran import DamodaranAgent
from .investor_coordinator import InvestorCoordinator

__all__ = [
    'BuffettAgent',
    'MungerAgent',
    'LynchAgent',
    'DamodaranAgent',
    'InvestorCoordinator',
]
