"""ROE 财务数据读取: 从 DuckDB 查询 roe 表。"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

import duckdb
import pandas as pd

from liudb.connection import DEFAULT_DB_PATH, get_duckdb

DateLike = str | date | datetime

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
        ['ticker', 'period_end', 'net_income', 'beginning_equity', 'ending_equity',
         'average_equity', 'roe', 'roe_percent']
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
