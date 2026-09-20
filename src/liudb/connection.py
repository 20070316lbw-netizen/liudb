"""数据库连接模块，提供 DuckDB 连接的获取与基础路径处理。"""
from __future__ import annotations

from pathlib import Path

import duckdb

DEFAULT_DB_PATH = "sp500.db"


def get_duckdb(
    path: str = DEFAULT_DB_PATH,
    *,
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    """获取 DuckDB 数据库连接。

    Args:
        path: 数据库文件路径, 默认 "sp500.db"；若为 ":memory:" 则使用纯内存模式。
        read_only: 是否以只读模式连接, 默认 False(支持写入与建表)。

    Returns:
        DuckDBPyConnection 连接对象, 支持上下文管理器 with 语法。

    Example:
        >>> with get_duckdb("sp500.db") as con:  # doctest: +SKIP
        ...     con.execute("SELECT 1").fetchall()
        [(1,)]
    """
    if path != ":memory:":
        db_file = Path(path)
        if db_file.parent and not db_file.parent.exists():
            db_file.parent.mkdir(parents=True, exist_ok=True)

    return duckdb.connect(database=path, read_only=read_only)
