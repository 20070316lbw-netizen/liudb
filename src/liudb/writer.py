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

    init_schema(path=path)

    with get_duckdb(path=path) as con:
        con.execute("INSERT OR REPLACE INTO risk_free_rate SELECT * FROM data")
        logger.info(f"成功存入 {len(data)} 条无风险利率记录")


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

    init_schema(path=path)

    with get_duckdb(path=path) as con:
        con.execute("INSERT OR REPLACE INTO roe SELECT * FROM data")
        logger.info(f"成功存入 {len(data)} 条 ROE 记录")


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

    可以直接传 sources.sec.get_fundamentals / get_fundamentals_batch 的输出。同一期间
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


# ---------------------------------------------------------------- A 股

_TRADE_CALENDAR_COLUMNS = ["date", "is_open"]
_STOCK_BASIC_COLUMNS = ["ticker", "name", "list_date", "delist_date", "sec_type", "is_listed"]
_DAILY_STATUS_COLUMNS = [
    "date",
    "ticker",
    "amount",
    "pre_close",
    "turnover",
    "pct_chg",
    "is_suspended",
    "is_st",
]
_INDEX_MEMBER_COLUMNS = ["index_code", "date", "ticker", "name", "update_date"]


def save_trade_calendar(df: pd.DataFrame, path: str = DEFAULT_DB_PATH) -> None:
    """写入或更新交易日历, 按 date 主键覆盖。

    Args:
        df: 包含 [date, is_open] 的 DataFrame(即 sources.cn.get_cn_trade_calendar 的输出)。
        path: 数据库文件路径。

    Raises:
        ValueError: 缺少必需列。
    """
    _upsert(df, "trade_calendar", _TRADE_CALENDAR_COLUMNS, {"date", "is_open"},
            date_columns=["date"], path=path)


def save_stock_basic(df: pd.DataFrame, path: str = DEFAULT_DB_PATH) -> None:
    """写入或更新证券基本资料, 按 ticker 主键覆盖。

    Args:
        df: 包含 [ticker, name, list_date, delist_date, sec_type, is_listed] 的
            DataFrame(即 sources.cn.get_cn_stock_basic 的输出), 必须包含 ticker。
        path: 数据库文件路径。

    Raises:
        ValueError: 缺少必需列。
    """
    _upsert(df, "stock_basic", _STOCK_BASIC_COLUMNS, {"ticker"},
            date_columns=["list_date", "delist_date"], path=path)


def save_daily_status(df: pd.DataFrame, path: str = DEFAULT_DB_PATH) -> None:
    """写入或更新 A 股每日交易状态, 按 (ticker, date) 主键覆盖。

    可以直接传 sources.cn.get_cn_daily_bars 的输出: 多余的行情列会被忽略,
    行情部分另用 save_prices 写入 prices 表。

    Args:
        df: 包含 [date, ticker, amount, pre_close, turnover, pct_chg, is_suspended,
            is_st] 的 DataFrame, 必须包含 date 与 ticker。
        path: 数据库文件路径。

    Raises:
        ValueError: 缺少必需列。

    Example:
        >>> bars = get_cn_daily_bars(tickers, start="2024-01-01")  # doctest: +SKIP
        >>> save_prices(bars, "ashare.db")  # doctest: +SKIP
        >>> save_daily_status(bars, "ashare.db")  # doctest: +SKIP
    """
    _upsert(df, "daily_status", _DAILY_STATUS_COLUMNS, {"date", "ticker"},
            date_columns=["date"], path=path)


def save_index_members(df: pd.DataFrame, path: str = DEFAULT_DB_PATH) -> None:
    """写入或更新指数成分快照, 按 (index_code, date, ticker) 主键覆盖。

    Args:
        df: 包含 [index_code, date, ticker, name, update_date] 的 DataFrame
            (即 sources.cn.get_cn_index_members(_history) 的输出),
            必须包含 index_code、date 与 ticker。
        path: 数据库文件路径。

    Raises:
        ValueError: 缺少必需列。
    """
    _upsert(df, "index_members", _INDEX_MEMBER_COLUMNS, {"index_code", "date", "ticker"},
            date_columns=["date", "update_date"], path=path)


def _upsert(
    df: pd.DataFrame,
    table: str,
    columns: list[str],
    required: set[str],
    *,
    date_columns: list[str],
    path: str,
) -> None:
    """通用的 "校验 -> 补齐缺失列 -> 转日期 -> INSERT OR REPLACE" 写入流程。

    table / columns 都是本模块里写死的常量, 不接受外部输入。
    """
    if df.empty:
        logger.warning(f"传入的 {table} DataFrame 为空，跳过写入")
        return

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{table} 缺少必需列: {missing}")

    data = df.copy()
    for col in columns:
        if col not in data.columns:
            data[col] = None
    data = data[columns].copy()
    for col in date_columns:
        data[col] = pd.to_datetime(data[col]).dt.date

    init_schema(path=path)

    column_list = ", ".join(columns)
    with get_duckdb(path=path) as con:
        con.register("_upsert_data", data)
        con.execute(
            f"INSERT OR REPLACE INTO {table} ({column_list}) "  # noqa: S608 - 表名/列名为内部常量
            f"SELECT {column_list} FROM _upsert_data"
        )
        con.unregister("_upsert_data")
        logger.info(f"成功存入 {len(data)} 条 {table} 记录")
