"""数据库结构初始化模块，负责建表语句的执行。"""
from __future__ import annotations

from liudb.connection import DEFAULT_DB_PATH, get_duckdb
from liudb.statements import CREATE_TABLES


def init_schema(path: str = DEFAULT_DB_PATH) -> None:
    """初始化数据库表结构, 若表不存在则自动创建。

    Args:
        path: 数据库文件路径, 默认 "sp500.db"。

    Returns:
        None。在目标数据库中创建 constituents、prices、risk_free_rate、roe 与 financials 表。

    Example:
        >>> init_schema("sp500.db")  # doctest: +SKIP
    """
    with get_duckdb(path=path) as con:
        con.execute(CREATE_TABLES)
