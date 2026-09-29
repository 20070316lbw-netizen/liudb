"""共享查询引擎和旧版读取 API 的兼容汇总入口。

市场专属读取接口分别位于 ``liudb.ashare`` 与 ``liudb.sp500``。这里汇总旧版名称，
保持原有 ``from liudb import load_*`` 和 ``from liudb.reader import load_*`` 调用可用。
"""
from __future__ import annotations

from liudb.reader.ashare import (
    load_daily_status,
    load_index_members,
    load_index_members_history,
    load_intraday_bars,
    load_latest_dates,
    load_latest_ts,
    load_stock_basic,
    load_trade_calendar,
)
from liudb.reader.constituents import load_constituents
from liudb.reader.fundamentals import (
    load_fundamentals,
    load_fundamentals_panel,
    load_fundamentals_pit,
    load_fundamentals_ttm,
    load_latest_filed,
)
from liudb.reader.prices import load_prices
from liudb.reader.query import Query, build_sql, loader
from liudb.reader.registry import VALID, ValidTableName
from liudb.reader.risk_free_rate import load_risk_free_rate
from liudb.reader.roe import load_roe

__all__ = [
    "VALID",
    "Query",
    "ValidTableName",
    "build_sql",
    "load_constituents",
    "load_daily_status",
    "load_fundamentals",
    "load_fundamentals_panel",
    "load_fundamentals_pit",
    "load_fundamentals_ttm",
    "load_index_members",
    "load_index_members_history",
    "load_intraday_bars",
    "load_latest_dates",
    "load_latest_filed",
    "load_latest_ts",
    "load_prices",
    "load_risk_free_rate",
    "load_roe",
    "load_stock_basic",
    "load_trade_calendar",
    "loader",
]
