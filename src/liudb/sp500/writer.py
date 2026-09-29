"""S&P 500 数据表的写入接口。"""
from __future__ import annotations

import pandas as pd
from loguru import logger

from liudb._sql import upsert_dataframe
from liudb.connection import DEFAULT_DB_PATH
from liudb.sp500.schema import init_schema

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
    _upsert(data, "constituents", ["ticker", "name"], required, date_columns=[], path=path)


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
        >>> prices = pd.DataFrame(  # doctest: +SKIP
        ...     [{"date": "2024-01-02", "ticker": "AAPL", "close": 182.0}]
        ... )
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

    _upsert(data, "prices", _PRICES_COLUMNS, required, date_columns=["date"], path=path)


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
        >>> rf = pd.DataFrame(  # doctest: +SKIP
        ...     [{"date": "2024-01-02", "series": "DGS1MO", "value": 5.45}]
        ... )
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

    _upsert(data, "risk_free_rate", _RISK_FREE_COLUMNS, required,
            date_columns=["date"], path=path)


def save_roe(df: pd.DataFrame, path: str = DEFAULT_DB_PATH) -> None:
    """写入或更新 ROE 财务数据, 按 (ticker, period_end) 主键自动去重覆盖。

    Args:
        df: 包含 [ticker, period_end, net_income, beginning_equity, ending_equity,
            average_equity, roe, roe_percent] 的 ROE DataFrame, 必须包含 'ticker' 与 'period_end'。
        path: 数据库文件路径, 默认 "sp500.db"。

    Returns:
        None。

    Raises:
        ValueError: DataFrame 缺少必需列 'ticker' 或 'period_end'。

    Example:
        >>> roe = pd.DataFrame(  # doctest: +SKIP
        ...     [{"ticker": "AAPL", "period_end": "2023-09-30", "roe": 1.719}]
        ... )
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

    _upsert(data, "roe", _ROE_COLUMNS, required,
            date_columns=["period_end"], path=path)


# ---------------------------------------------------------------- SEC 基本面

_FUNDAMENTAL_COLUMNS = [
    "ticker",
    "cik",
    "field",
    "concept",
    "unit",
    "period_start",
    "period_end",
    "period_months",
    "value",
    "fy",
    "fp",
    "form",
    "accn",
    "filed",
    "derived",
]


def save_fundamentals(df: pd.DataFrame, path: str = DEFAULT_DB_PATH) -> None:
    """写入或更新 SEC 基本面点时长表, 按 (ticker, field, period_end, period_months, accn)
    主键覆盖。

    可以直接传 sources.sp500.sec.get_fundamentals(_batch) 的输出。同一期间
    的不同申报版本 accn 不同, 会各自保留, 这正是点时查询需要的。

    Args:
        df: 列为 [ticker, cik, field, concept, unit, period_start, period_end,
            period_months, value, fy, fp, form, accn, filed, derived] 的 DataFrame,
            必须包含 ticker、field、period_end、period_months、accn、filed。
        path: 数据库文件路径。

    Raises:
        ValueError: 缺少必需列。
    """
    data = df
    if not df.empty and "derived" not in df.columns:
        data = df.assign(derived=False)
    _upsert(
        data,
        "fundamentals",
        _FUNDAMENTAL_COLUMNS,
        {"ticker", "field", "period_end", "period_months", "accn", "filed"},
        date_columns=["period_start", "period_end", "filed"],
        path=path,
    )




def _upsert(
    df: pd.DataFrame, table: str, columns: list[str], required: set[str], *,
    date_columns: list[str], path: str, timestamp_columns: tuple[str, ...] = (),
) -> None:
    """把美股表的通用写入参数交给事务型 SQL 辅助函数。"""
    keys = {
        "constituents": ("ticker",),
        "prices": ("ticker", "date"),
        "risk_free_rate": ("series", "date"),
        "roe": ("ticker", "period_end"),
        "fundamentals": ("ticker", "field", "period_end", "period_months", "accn"),
    }[table]
    upsert_dataframe(
        df, table, columns, required, keys, date_columns=date_columns, path=path,
        timestamp_columns=timestamp_columns, init_schema=init_schema,
    )
