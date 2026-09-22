"""成分股读取: 从 DuckDB 查询 constituents 表。"""
from __future__ import annotations

from collections.abc import Sequence

import duckdb
import pandas as pd

from liudb.connection import DEFAULT_DB_PATH, get_duckdb


def load_constituents(
    tickers: str | Sequence[str] | None = None,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """读取成分股列表, 支持按标的代码过滤。

    Args:
        tickers: 单个 ticker 或 ticker 列表, 默认 None 表示获取全部成分股。
        path: 数据库文件路径, 默认 "sp500.db"。

    Returns:
        DataFrame, 列固定为 [ticker, name], 按 ticker 升序排列。
        表不存在或查询为空时返回保留列结构的空 DataFrame。

    Example:
        >>> universe = load_constituents(tickers=["AAPL", "MSFT"])  # doctest: +SKIP
        >>> universe.columns.tolist()  # doctest: +SKIP
        ['ticker', 'name']
    """
    conditions: list[str] = []
    params: list[object] = []

    if tickers:
        ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
        placeholders = ", ".join(["?"] * len(ticker_list))
        conditions.append(f"ticker IN ({placeholders})")
        params.extend(ticker_list)

    sql = "SELECT ticker, name FROM constituents"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY ticker"

    try:
        with get_duckdb(path=path, read_only=True) as con:
            return con.execute(sql, params).df()
    except duckdb.Error:
        return pd.DataFrame(columns=["ticker", "name"])
