"""兼容旧导入路径的市场 DDL 转发模块。"""
from __future__ import annotations

from liudb.ashare.schema import ASHARE_DDL
from liudb.sp500.schema import SP500_DDL

__all__ = ["ASHARE_DDL", "SP500_DDL"]
