"""数据读取模块，负责从 DuckDB 查询并返回清洗后的量化数据 DataFrame。"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

import duckdb
import pandas as pd

from liudb.connection import DEFAULT_DB_PATH, get_duckdb

DateLike = str | date | datetime

_PRICES_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
_RISK_FREE_COLUMNS = ["date", "series", "value"]
_ROE_COLUMNS = [
    "ticker",
    "period_end",
    "net_income",
    "beginning_equity",
    "ending_equity",
    "average_equity",
    "roe",
    "roe_percent",
]


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
        >>> prices = load_prices(tickers="AAPL", start="2024-01-01", end="2024-03-01")  # doctest: +SKIP
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


def load_risk_free_rate(
    series: str | Sequence[str] | None = "DGS1MO",
    start: DateLike | None = None,
    end: DateLike | None = None,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """读取无风险利率数据, 支持按序列名和日期范围过滤。

    Args:
        series: FRED 序列标识, 单个或多个, 默认 "DGS1MO", 若为 None 则返回所有序列。
        start: 起始日期(含), 默认 None。
        end: 结束日期(含), 默认 None。
        path: 数据库文件路径, 默认 "sp500.db"。

    Returns:
        DataFrame, 列固定为 [date, series, value], 按 [series, date] 升序排列。
        表不存在或无匹配记录时返回保留列结构的空 DataFrame。

    Example:
        >>> rf = load_risk_free_rate(series="DGS1MO", start="2024-01-01")  # doctest: +SKIP
        >>> rf.columns.tolist()  # doctest: +SKIP
        ['date', 'series', 'value']
    """
    conditions: list[str] = []
    params: list[object] = []

    if series:
        series_list = [series] if isinstance(series, str) else list(series)
        placeholders = ", ".join(["?"] * len(series_list))
        conditions.append(f"series IN ({placeholders})")
        params.extend(series_list)

    if start:
        start_str = str(start)[:10]
        conditions.append("date >= ?")
        params.append(start_str)

    if end:
        end_str = str(end)[:10]
        conditions.append("date <= ?")
        params.append(end_str)

    sql = f"SELECT {', '.join(_RISK_FREE_COLUMNS)} FROM risk_free_rate"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY series, date"

    try:
        with get_duckdb(path=path, read_only=True) as con:
            return con.execute(sql, params).df()
    except duckdb.Error:
        return pd.DataFrame(columns=_RISK_FREE_COLUMNS)


def load_roe(
    tickers: str | Sequence[str] | None = None,
    start: DateLike | None = None,
    end: DateLike | None = None,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """读取 ROE 财务数据, 支持按标的和报告期截止日范围过滤。

    Args:
        tickers: 单个 ticker 或 ticker 列表, 默认 None 表示不限标的。
        start: 起始报告期截止日(含), 如 "2023-01-01", 默认 None。
        end: 结束报告期截止日(含), 默认 None。
        path: 数据库文件路径, 默认 "sp500.db"。

    Returns:
        DataFrame, 列固定为 [ticker, period_end, net_income, beginning_equity,
        ending_equity, average_equity, roe, roe_percent], 按 [ticker, period_end] 升序排列。
        表不存在或无匹配记录时返回保留列结构的空 DataFrame。

    Example:
        >>> roe = load_roe(tickers="AAPL")  # doctest: +SKIP
        >>> roe.columns.tolist()  # doctest: +SKIP
        ['ticker', 'period_end', 'net_income', 'beginning_equity', 'ending_equity', 'average_equity', 'roe', 'roe_percent']
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
        conditions.append("period_end >= ?")
        params.append(start_str)

    if end:
        end_str = str(end)[:10]
        conditions.append("period_end <= ?")
        params.append(end_str)

    sql = f"SELECT {', '.join(_ROE_COLUMNS)} FROM roe"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY ticker, period_end"

    try:
        with get_duckdb(path=path, read_only=True) as con:
            return con.execute(sql, params).df()
    except duckdb.Error:
        return pd.DataFrame(columns=_ROE_COLUMNS)
