"""旧版 A 股 reader 路径的兼容转发层。"""
from __future__ import annotations

from liudb.ashare.reader import (
    LatestDateTable,
    load_daily_status,
    load_index_members,
    load_index_members_history,
    load_intraday_bars,
    load_latest_dates,
    load_latest_ts,
    load_prices,
    load_stock_basic,
    load_trade_calendar,
)

__all__ = [
    "LatestDateTable", "load_daily_status", "load_index_members",
    "load_index_members_history", "load_intraday_bars", "load_latest_dates",
    "load_latest_ts", "load_prices", "load_stock_basic", "load_trade_calendar",
]
