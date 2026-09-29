"""按指定 DDL 初始化 DuckDB 表结构的私有辅助函数。"""
from __future__ import annotations

from liudb.connection import get_duckdb


def initialize(path: str, ddl: str) -> None:
    """执行一组完整的市场 DDL。"""
    with get_duckdb(path=path) as con:
        con.execute(ddl)
