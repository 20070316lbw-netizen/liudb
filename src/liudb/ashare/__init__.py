"""A 股表结构、清洗、写入与读取接口。"""
from __future__ import annotations

from liudb.ashare.clean import (
    clean_daily_bars,
    clean_intraday_bars,
    fix_is_st,
    recompute_daily_adj_close,
)
from liudb.ashare.reader import (
    Query,
    load_daily_status,
    load_index_members,
    load_index_members_history,
    load_intraday_bars,
    load_latest_dates,
    load_latest_ts,
    load_prices,
    load_stock_basic,
    load_trade_calendar,
    loader,
)
from liudb.ashare.rules import MarketRules, limit_prices
from liudb.ashare.schema import init_schema
from liudb.ashare.writer import (
    save_ashare_daily_bars as save_daily_bars,
)
from liudb.ashare.writer import (
    save_ashare_intraday_bars as save_intraday_bars,
)
from liudb.ashare.writer import (
    save_daily_status,
    save_index_members,
    save_stock_basic,
    save_trade_calendar,
)
from liudb.reader.query import build_sql

# 这两个别名承接旧市场写入命名，保证新入口仍自动执行 A 股清洗。
save_prices = save_daily_bars

__all__ = [
    "MarketRules", "Query", "build_sql", "clean_daily_bars", "clean_intraday_bars", "fix_is_st",
    "init_schema", "limit_prices", "load_daily_status", "load_index_members",
    "load_index_members_history", "load_intraday_bars", "load_latest_dates",
    "load_latest_ts", "load_prices", "load_stock_basic", "load_trade_calendar", "loader",
    "recompute_daily_adj_close", "save_daily_bars", "save_daily_status",
    "save_index_members", "save_intraday_bars", "save_prices", "save_stock_basic",
    "save_trade_calendar",
]
