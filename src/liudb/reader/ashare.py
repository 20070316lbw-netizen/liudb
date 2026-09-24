"""A 股相关表的读取: trade_calendar / stock_basic / daily_status / index_members,
以及增量抓取时用的"每只股票已入库到哪一天"查询。

与其他 load_* 一致: 过滤条件走 `?` 占位符; 表不存在或查询失败时返回保留列
结构的空 DataFrame。日期参数都是闭区间。
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Literal

import duckdb
import pandas as pd

from liudb.connection import DEFAULT_DB_PATH, get_duckdb

DateLike = str | date | datetime

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
_LATEST_DATE_COLUMNS = ["ticker", "last_date"]

LatestDateTable = Literal["prices", "daily_status"]
_LATEST_DATE_TABLES: tuple[str, ...] = ("prices", "daily_status")


def load_trade_calendar(
    start: DateLike | None = None,
    end: DateLike | None = None,
    *,
    open_only: bool = False,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """读取交易日历。

    Args:
        start: 起始日期(含), 默认不限。
        end: 结束日期(含), 默认不限。
        open_only: True 时只返回交易日。
        path: 数据库文件路径。

    Returns:
        DataFrame, 列为 [date, is_open], 按 date 升序。
    """
    conditions, params = _date_range("date", start, end)
    if open_only:
        conditions.append("is_open")
    return _select("trade_calendar", _TRADE_CALENDAR_COLUMNS, conditions, params,
                   order_by="date", path=path)


def load_stock_basic(
    tickers: str | Sequence[str] | None = None,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """读取证券基本资料。

    Args:
        tickers: 单个代码或代码列表, 默认不限。
        path: 数据库文件路径。

    Returns:
        DataFrame, 列为 [ticker, name, list_date, delist_date, sec_type, is_listed],
        按 ticker 升序。
    """
    conditions, params = _ticker_filter(tickers)
    return _select("stock_basic", _STOCK_BASIC_COLUMNS, conditions, params,
                   order_by="ticker", path=path)


def load_daily_status(
    tickers: str | Sequence[str] | None = None,
    start: DateLike | None = None,
    end: DateLike | None = None,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """读取 A 股每日交易状态(停牌/ST/成交额等)。

    Args:
        tickers: 单个代码或代码列表, 默认不限。
        start: 起始日期(含), 默认不限。
        end: 结束日期(含), 默认不限。
        path: 数据库文件路径。

    Returns:
        DataFrame, 列为 [date, ticker, amount, pre_close, turnover, pct_chg,
        is_suspended, is_st], 按 (ticker, date) 升序。
    """
    conditions, params = _ticker_filter(tickers)
    date_conditions, date_params = _date_range("date", start, end)
    return _select("daily_status", _DAILY_STATUS_COLUMNS, conditions + date_conditions,
                   params + date_params, order_by="ticker, date", path=path)


def load_index_members(
    index_code: str,
    date: DateLike | None = None,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """读取"截至某天"的指数成分: 取 date 当天或之前最近的一份快照。

    用于按时点确定股票池, 不会用到 date 之后才公布的成分。

    Args:
        index_code: 指数代码, 如 "000300.SH"(沪深300)。
        date: 时点, 默认 None 表示取最新一份快照。
        path: 数据库文件路径。

    Returns:
        DataFrame, 列为 [index_code, date, ticker, name, update_date], 按 ticker 升序;
        date 列是实际命中的快照日期。没有 date 之前的快照时返回空表。
    """
    snapshot_sql = "SELECT max(date) FROM index_members WHERE index_code = ?"
    params: list[object] = [index_code]
    if date is not None:
        snapshot_sql += " AND date <= ?"
        params.append(_date_str(date))

    conditions = ["index_code = ?", f"date = ({snapshot_sql})"]
    return _select("index_members", _INDEX_MEMBER_COLUMNS, conditions, [index_code, *params],
                   order_by="ticker", path=path)


def load_index_members_history(
    index_code: str,
    start: DateLike | None = None,
    end: DateLike | None = None,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """读取区间内的全部成分快照。

    Args:
        index_code: 指数代码, 如 "000300.SH"。
        start: 快照起始日期(含), 默认不限。
        end: 快照结束日期(含), 默认不限。
        path: 数据库文件路径。

    Returns:
        DataFrame, 列为 [index_code, date, ticker, name, update_date], 按 (date, ticker) 升序。
    """
    date_conditions, date_params = _date_range("date", start, end)
    return _select("index_members", _INDEX_MEMBER_COLUMNS,
                   ["index_code = ?", *date_conditions], [index_code, *date_params],
                   order_by="date, ticker", path=path)


def load_latest_dates(
    table: LatestDateTable = "prices",
    tickers: str | Sequence[str] | None = None,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """查询每只股票在某张日频表里已入库的最后日期, 供增量抓取确定起点。

    直接从数据本身聚合, 不另外维护抓取日志, 因此不会和实际数据不一致。

    Args:
        table: "prices" 或 "daily_status"。
        tickers: 单个代码或代码列表, 默认不限。
        path: 数据库文件路径。

    Returns:
        DataFrame, 列为 [ticker, last_date], 按 ticker 升序; 库里没有的股票不出现。

    Raises:
        ValueError: table 不在允许范围内。
    """
    if table not in _LATEST_DATE_TABLES:
        raise ValueError(f"table 只能是 {list(_LATEST_DATE_TABLES)}, 收到 {table!r}")

    conditions, params = _ticker_filter(tickers)
    sql = f"SELECT ticker, max(date) AS last_date FROM {table}"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " GROUP BY ticker ORDER BY ticker"
    return _run(sql, params, _LATEST_DATE_COLUMNS, path)


# ---------------------------------------------------------------- helpers

def _ticker_filter(tickers: str | Sequence[str] | None) -> tuple[list[str], list[object]]:
    if not tickers:
        return [], []
    ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
    placeholders = ", ".join(["?"] * len(ticker_list))
    return [f"ticker IN ({placeholders})"], list(ticker_list)


def _date_range(
    column: str, start: DateLike | None, end: DateLike | None
) -> tuple[list[str], list[object]]:
    conditions: list[str] = []
    params: list[object] = []
    if start is not None:
        conditions.append(f"{column} >= ?")
        params.append(_date_str(start))
    if end is not None:
        conditions.append(f"{column} <= ?")
        params.append(_date_str(end))
    return conditions, params


def _date_str(value: DateLike) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _select(
    table: str,
    columns: list[str],
    conditions: list[str],
    params: list[object],
    *,
    order_by: str,
    path: str,
) -> pd.DataFrame:
    sql = f"SELECT {', '.join(columns)} FROM {table}"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += f" ORDER BY {order_by}"
    return _run(sql, params, columns, path)


def _run(sql: str, params: list[object], columns: list[str], path: str) -> pd.DataFrame:
    try:
        with get_duckdb(path=path, read_only=True) as con:
            return con.execute(sql, params).df()
    except duckdb.Error:
        return pd.DataFrame(columns=columns)
