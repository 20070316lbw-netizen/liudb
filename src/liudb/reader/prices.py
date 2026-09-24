"""历史行情读取(兼容旧接口): 从 DuckDB 查询 prices 表, 返回未处理的宽列长表。

按标的/日期过滤后直接返回物理列(含未复权 close 和 adj_close), 供还在用旧
接口的调用方(如 minibacktest)过渡使用。新代码请走 `liudb.reader.query`
里基于注册表的 Query/build_sql/loader, 它只暴露复权口径的 OHLCV。
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

import duckdb
import pandas as pd

from liudb.connection import DEFAULT_DB_PATH, get_duckdb

DateLike = str | date | datetime

_PRICES_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]


def load_prices(
    tickers: str | Sequence[str] | None = None,
    start: DateLike | None = None,
    end: DateLike | None = None,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """读取历史行情长表数据, 支持按标的和日期范围过滤。

    Args:
        tickers: 单个 ticker 或 ticker 列表, 默认 None 表示不限标的。
        start: 起始日期(含), 如 "2024-01-01", 默认 None。
        end: 结束日期(含), 如 "2024-06-01", 默认 None。
        path: 数据库文件路径, 默认 "sp500.db"。

    Returns:
        DataFrame, 列固定为 [date, ticker, open, high, low, close, adj_close, volume],
        按 [ticker, date] 升序排列。表不存在或无匹配记录时返回保留列结构的空 DataFrame。

    Example:
        >>> prices = load_prices(  # doctest: +SKIP
        ...     tickers="AAPL", start="2024-01-01", end="2024-03-01"
        ... )
        >>> prices.columns.tolist()  # doctest: +SKIP
        ['date', 'ticker', 'open', 'high', 'low', 'close', 'adj_close', 'volume']
    """
    conditions: list[str] = []
    params: list[object] = []

    if tickers:
        ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
        placeholders = ", ".join(["?"] * len(ticker_list))
        conditions.append(f"ticker IN ({placeholders})")
        params.extend(ticker_list)

    if start:
        start_str = str(start)[:10]
        conditions.append("date >= ?")
        params.append(start_str)

    if end:
        end_str = str(end)[:10]
        conditions.append("date <= ?")
        params.append(end_str)

    sql = f"SELECT {', '.join(_PRICES_COLUMNS)} FROM prices"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY ticker, date"

    try:
        with get_duckdb(path=path, read_only=True) as con:
            return con.execute(sql, params).df()
    except duckdb.Error:
        return pd.DataFrame(columns=_PRICES_COLUMNS)
