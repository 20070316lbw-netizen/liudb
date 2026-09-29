"""SQL 语句包，集中管理各类 SQL 模板与 DDL。"""
from __future__ import annotations

from liudb.statements.ddl import ASHARE_DDL, SP500_DDL

__all__ = [
    "ASHARE_DDL",
    "SP500_DDL",
]
