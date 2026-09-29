"""A 股数据表的写入接口，负责清洗并保存行情与基础数据。"""
from __future__ import annotations

import duckdb
import pandas as pd
from loguru import logger

from liudb._sql import upsert_dataframe
from liudb.ashare.clean import clean_daily_bars, clean_intraday_bars
from liudb.ashare.reader import load_stock_basic
from liudb.ashare.schema import init_schema
from liudb.connection import ASHARE_DB_PATH, get_duckdb
from liudb.reader.prices import load_prices

_PRICES_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]

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
_INTRADAY_COLUMNS = [
    "freq", "ts", "ticker", "open", "high", "low", "close", "adj_close", "volume", "amount",
]


def save_trade_calendar(df: pd.DataFrame, path: str = ASHARE_DB_PATH) -> None:
    """写入或更新交易日历, 按 date 主键覆盖。

    Args:
        df: 包含 [date, is_open] 的 DataFrame(即 sources.ashare.get_trade_calendar 的输出)。
        path: 数据库文件路径。

    Raises:
        ValueError: 缺少必需列。
    """
    _upsert(df, "trade_calendar", _TRADE_CALENDAR_COLUMNS, {"date", "is_open"},
            date_columns=["date"], path=path)


def save_stock_basic(df: pd.DataFrame, path: str = ASHARE_DB_PATH) -> None:
    """写入或更新证券基本资料, 按 ticker 主键覆盖。

    Args:
        df: 包含 [ticker, name, list_date, delist_date, sec_type, is_listed] 的
            DataFrame(即 sources.ashare.get_stock_basic 的输出), 必须包含 ticker。
        path: 数据库文件路径。

    Raises:
        ValueError: 缺少必需列。
    """
    _upsert(df, "stock_basic", _STOCK_BASIC_COLUMNS, {"ticker"},
            date_columns=["list_date", "delist_date"], path=path)


def save_daily_status(df: pd.DataFrame, path: str = ASHARE_DB_PATH) -> None:
    """写入或更新 A 股每日交易状态, 按 (ticker, date) 主键覆盖。

    可以直接传 sources.ashare.get_daily_bars 的输出: 多余的行情列会被忽略,
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


def save_index_members(df: pd.DataFrame, path: str = ASHARE_DB_PATH) -> None:
    """写入或更新指数成分快照, 按 (index_code, date, ticker) 主键覆盖。

    Args:
        df: 包含 [index_code, date, ticker, name, update_date] 的 DataFrame
            (即 sources.ashare.get_index_members(_history) 的输出),
            必须包含 index_code、date 与 ticker。
        path: 数据库文件路径。

    Raises:
        ValueError: 缺少必需列。
    """
    _upsert(df, "index_members", _INDEX_MEMBER_COLUMNS, {"index_code", "date", "ticker"},
            date_columns=["date", "update_date"], path=path)


def save_intraday_bars_legacy(
    df: pd.DataFrame,
    freq: str | int = "30",
    path: str = ASHARE_DB_PATH,
) -> None:
    """写入或更新 A 股分钟线, 按 (freq, ticker, ts) 主键覆盖。

    可以直接传 sources.ashare.get_intraday_bars 的输出(它不带 freq 列, 由参数给出;
    传入的 df 若自带 freq 列会被参数覆盖, 保证一批数据只落在一个周期下)。

    Args:
        df: 包含 [ts, ticker, open, high, low, close, adj_close, volume, amount] 的
            DataFrame, 必须包含 ts、ticker 与 close。ts 为 bar 结束时间。
        freq: 周期分钟数, 如 "30" 或 30。
        path: 数据库文件路径。

    Raises:
        ValueError: 缺少必需列, 或 freq 不是正整数分钟数。

    Example:
        >>> bars = get_intraday_bars(["510300.SH"], start="2026-01-01")  # doctest: +SKIP
        >>> save_intraday_bars(bars, freq="30", path="ashare.db")  # doctest: +SKIP
    """
    freq_str = _check_freq(freq)
    data = df if df.empty else df.assign(freq=freq_str)
    _upsert(data, "intraday_bars", _INTRADAY_COLUMNS, {"freq", "ts", "ticker", "close"},
            date_columns=[], timestamp_columns=("ts",), path=path)


def _check_freq(freq: str | int) -> str:
    freq_str = str(freq).strip()
    if not freq_str.isdigit() or int(freq_str) <= 0:
        raise ValueError(f"freq 必须是正整数分钟数, 收到 {freq!r}")
    return str(int(freq_str))


def _upsert(
    df: pd.DataFrame, table: str, columns: list[str], required: set[str], *,
    date_columns: list[str], path: str,
    timestamp_columns: tuple[str, ...] = (),
) -> None:
    """把 A 股表的主键和日期规则交给事务型 SQL 辅助函数。"""
    keys = {
        "prices": ("ticker", "date"),
        "trade_calendar": ("date",),
        "stock_basic": ("ticker",),
        "daily_status": ("ticker", "date"),
        "index_members": ("index_code", "date", "ticker"),
        "intraday_bars": ("freq", "ticker", "ts"),
    }[table]
    upsert_dataframe(
        df, table, columns, required, keys, date_columns=date_columns, path=path,
        timestamp_columns=timestamp_columns, init_schema=init_schema,
    )


# ---------------------------------------------------------------- A 股: 清洗后入库

def save_ashare_daily_bars(df: pd.DataFrame, path: str = ASHARE_DB_PATH) -> None:
    """写入 A 股日线: 先清洗, 再落 `prices` 与 `daily_status`。

    清洗见 liudb.ashare.clean.clean_daily_bars: 用前一交易日官方收盘 / 当日前收
    推算后复权 adj_close(续接库里已有的最后一根日线), 并把非股票的 is_st 置 False。
    行情列进 `prices`, 状态列进 `daily_status`, 都按主键覆盖写入。

    Args:
        df: sources.ashare.get_daily_bars 的输出, 必须含 [date, ticker, close, pre_close]。
        path: 数据库文件路径, 默认 "ashare.db"。

    Raises:
        ValueError: 缺少必需列。
    """
    if df.empty:
        logger.warning("传入的 A 股日线 DataFrame 为空，跳过写入")
        return
    required = {"date", "ticker", "close", "pre_close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"A 股日线缺少必需列: {missing}")

    basic, prior = _ashare_daily_context(df, path)
    cleaned = clean_daily_bars(df, basic=basic, prior=prior)
    _upsert(cleaned, "prices", _PRICES_COLUMNS, {"date", "ticker", "close"},
            date_columns=["date"], path=path)
    _upsert(cleaned, "daily_status", _DAILY_STATUS_COLUMNS, {"date", "ticker"},
            date_columns=["date"], path=path)


def save_ashare_intraday_bars(
    df: pd.DataFrame,
    freq: str | int = "30",
    path: str = ASHARE_DB_PATH,
) -> None:
    """写入 A 股分钟线: 先清洗, 再落 `intraday_bars`。

    清洗见 liudb.ashare.clean.clean_intraday_bars: 用当天的日线因子重算 adj_close,
    并把成交量为 0(临时停牌)的 bar 的 OHLC 置成 NULL。ts 为 bar 结束时间。

    Args:
        df: sources.ashare.get_intraday_bars 的输出, 至少 [ts, ticker, close]。
        freq: 周期分钟数, 如 "30"; 写入前会覆盖 df 里可能自带的 freq 列。
        path: 数据库文件路径, 默认 "ashare.db"。

    Raises:
        ValueError: 缺少必需列, 或 freq 不是正整数分钟数。
    """
    if df.empty:
        logger.warning("传入的 A 股分钟线 DataFrame 为空，跳过写入")
        return
    freq_str = _check_freq(freq)
    data = df.assign(freq=freq_str)
    daily = _ashare_daily_for_bars(data, path)
    cleaned = clean_intraday_bars(data, daily=daily)
    _upsert(cleaned, "intraday_bars", _INTRADAY_COLUMNS, {"freq", "ts", "ticker", "close"},
            date_columns=[], timestamp_columns=("ts",), path=path)


def _ashare_daily_context(
    df: pd.DataFrame, path: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """取日线清洗需要的证券资料与上一根已入库日线。"""
    tickers = sorted(df["ticker"].astype(str).unique())
    basic = load_stock_basic(tickers, path=path)
    prior = _latest_stored_prices(df, path)
    return basic, prior


def _latest_stored_prices(df: pd.DataFrame, path: str) -> pd.DataFrame:
    """每只证券在 df 最早日期之前、最近一根已入库日线 [ticker, close, adj_close]。

    表不存在(新库)时返回空表。用窗口函数一条 SQL 取每只证券的最后一根, 避免把
    整段历史读进内存。
    """
    empty = pd.DataFrame(columns=["ticker", "close", "adj_close"])
    if df.empty or "date" not in df.columns:
        return empty
    cutoffs = (
        pd.to_datetime(df["date"]).groupby(df["ticker"].astype(str))
        .min().rename("cutoff").reset_index()
    )
    sql = """
        SELECT ticker, close, adj_close FROM (
            SELECT p.ticker AS ticker, p.close AS close, p.adj_close AS adj_close,
                   row_number() OVER (PARTITION BY p.ticker ORDER BY p.date DESC) AS rn
            FROM prices p
            JOIN _cutoff c ON p.ticker = c.ticker AND p.date < CAST(c.cutoff AS DATE)
        ) WHERE rn = 1
    """
    try:
        with get_duckdb(path=path, read_only=True) as con:
            con.register("_cutoff", cutoffs)
            return con.execute(sql).df()
    except duckdb.Error:
        return empty


def _ashare_daily_for_bars(bars: pd.DataFrame, path: str) -> pd.DataFrame:
    """分钟线清洗用的日线因子来源: bars 覆盖日期区间内的 prices 日线。"""
    empty = pd.DataFrame(columns=["date", "ticker", "close", "adj_close"])
    if bars.empty or "ts" not in bars.columns:
        return empty
    ts = pd.to_datetime(bars["ts"])
    tickers = sorted(bars["ticker"].astype(str).unique())
    return load_prices(tickers, start=ts.min().date(), end=ts.max().date(), path=path)


# 市场入口使用清洗写入；未清洗的旧行为只由顶层兼容模块转发。
save_daily_bars = save_ashare_daily_bars
save_prices = save_daily_bars
save_intraday_bars = save_ashare_intraday_bars
