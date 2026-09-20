"""数据写入模块，负责将各类量化数据写入 DuckDB 并执行主键覆盖更新。"""
from __future__ import annotations

import pandas as pd
from loguru import logger

from liudb.connection import DEFAULT_DB_PATH, get_duckdb
from liudb.schema import init_schema

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


def save_constituents(df: pd.DataFrame, path: str = DEFAULT_DB_PATH) -> None:
    """写入或更新成分股数据, 按 ticker 主键自动去重覆盖。

    Args:
        df: 包含 [ticker, name] 的成分股 DataFrame。
        path: 数据库文件路径, 默认 "sp500.db"。

    Returns:
        None。

    Raises:
        ValueError: DataFrame 缺少必需列 'ticker' 或 'name'。

    Example:
        >>> df = pd.DataFrame([{"ticker": "AAPL", "name": "Apple Inc."}])  # doctest: +SKIP
        >>> save_constituents(df, "sp500.db")  # doctest: +SKIP
    """
    if df.empty:
        logger.warning("传入的 constituents DataFrame 为空，跳过写入")
        return

    required = {"ticker", "name"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"constituents 缺少必需列: {missing}")

    data = df[["ticker", "name"]].copy()
    init_schema(path=path)

    with get_duckdb(path=path) as con:
        con.execute("INSERT OR REPLACE INTO constituents SELECT * FROM data")
        logger.info(f"成功存入 {len(data)} 条成分股记录")


def save_prices(df: pd.DataFrame, path: str = DEFAULT_DB_PATH) -> None:
    """写入或更新历史行情长表数据, 按 (ticker, date) 主键自动去重覆盖。

    Args:
        df: 包含 [date, ticker, open, high, low, close, adj_close, volume] 的行情 DataFrame,
            必须包含 'date'、'ticker' 与 'close' 列。
        path: 数据库文件路径, 默认 "sp500.db"。

    Returns:
        None。

    Raises:
        ValueError: DataFrame 缺少必需列 'date'、'ticker' 或 'close'。

    Example:
        >>> prices = pd.DataFrame([{"date": "2024-01-02", "ticker": "AAPL", "close": 182.0}])  # doctest: +SKIP
        >>> save_prices(prices, "sp500.db")  # doctest: +SKIP
    """
    if df.empty:
        logger.warning("传入的 prices DataFrame 为空，跳过写入")
        return

    required = {"date", "ticker", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"prices 缺少必需列: {missing}")

    data = df.copy()
    for col in _PRICES_COLUMNS:
        if col not in data.columns:
            data[col] = None

    data = data[_PRICES_COLUMNS].copy()
    data["date"] = pd.to_datetime(data["date"]).dt.date

    init_schema(path=path)

    with get_duckdb(path=path) as con:
        con.execute("INSERT OR REPLACE INTO prices SELECT * FROM data")
        logger.info(f"成功存入 {len(data)} 条行情记录")


def save_risk_free_rate(df: pd.DataFrame, path: str = DEFAULT_DB_PATH) -> None:
    """写入或更新无风险利率数据, 按 (series, date) 主键自动去重覆盖。

    Args:
        df: 包含 [date, series, value] 的无风险利率 DataFrame。
        path: 数据库文件路径, 默认 "sp500.db"。

    Returns:
        None。

    Raises:
        ValueError: DataFrame 缺少必需列 'date'、'series' 或 'value'。

    Example:
        >>> rf = pd.DataFrame([{"date": "2024-01-02", "series": "DGS1MO", "value": 5.45}])  # doctest: +SKIP
        >>> save_risk_free_rate(rf, "sp500.db")  # doctest: +SKIP
    """
    if df.empty:
        logger.warning("传入的 risk_free_rate DataFrame 为空，跳过写入")
        return

    required = {"date", "series", "value"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"risk_free_rate 缺少必需列: {missing}")

    data = df[_RISK_FREE_COLUMNS].copy()
    data["date"] = pd.to_datetime(data["date"]).dt.date

    init_schema(path=path)

    with get_duckdb(path=path) as con:
        con.execute("INSERT OR REPLACE INTO risk_free_rate SELECT * FROM data")
        logger.info(f"成功存入 {len(data)} 条无风险利率记录")


def save_roe(df: pd.DataFrame, path: str = DEFAULT_DB_PATH) -> None:
    """写入或更新 ROE 财务数据, 按 (ticker, period_end) 主键自动去重覆盖。

    Args:
        df: 包含 [ticker, period_end, net_income, beginning_equity, ending_equity, average_equity, roe, roe_percent]
            的 ROE DataFrame, 必须包含 'ticker' 与 'period_end'。
        path: 数据库文件路径, 默认 "sp500.db"。

    Returns:
        None。

    Raises:
        ValueError: DataFrame 缺少必需列 'ticker' 或 'period_end'。

    Example:
        >>> roe = pd.DataFrame([{"ticker": "AAPL", "period_end": "2023-09-30", "roe": 1.719}])  # doctest: +SKIP
        >>> save_roe(roe, "sp500.db")  # doctest: +SKIP
    """
    if df.empty:
        logger.warning("传入的 roe DataFrame 为空，跳过写入")
        return

    required = {"ticker", "period_end"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"roe 缺少必需列: {missing}")

    data = df.copy()
    for col in _ROE_COLUMNS:
        if col not in data.columns:
            data[col] = None

    data = data[_ROE_COLUMNS].copy()
    data["period_end"] = pd.to_datetime(data["period_end"]).dt.date

    init_schema(path=path)

    with get_duckdb(path=path) as con:
        con.execute("INSERT OR REPLACE INTO roe SELECT * FROM data")
        logger.info(f"成功存入 {len(data)} 条 ROE 记录")
