"""liudb 包入口，导出常用的数据库连接、初始化、写入与读取接口。"""
from __future__ import annotations

from liudb.connection import DEFAULT_DB_PATH, get_duckdb
from liudb.reader import (
    VALID,
    Query,
    ValidTableName,
    build_sql,
    load_constituents,
    load_daily_status,
    load_fundamentals,
    load_fundamentals_panel,
    load_fundamentals_pit,
    load_fundamentals_ttm,
    load_index_members,
    load_index_members_history,
    load_latest_dates,
    load_latest_filed,
    load_prices,
    load_risk_free_rate,
    load_roe,
    load_stock_basic,
    load_trade_calendar,
    loader,
)
from liudb.schema import init_schema
from liudb.writer import (
    save_constituents,
    save_daily_status,
    save_fundamentals,
    save_index_members,
    save_prices,
    save_risk_free_rate,
    save_roe,
    save_stock_basic,
    save_trade_calendar,
)

# 别名支持 (insert_* 与 read_*)
insert_constituents = save_constituents
insert_prices = save_prices
insert_risk_free_rate = save_risk_free_rate
insert_roe = save_roe

read_constituents = load_constituents
read_prices = load_prices
read_risk_free_rate = load_risk_free_rate
read_roe = load_roe

__all__ = [
    "DEFAULT_DB_PATH",
    "VALID",
    "Query",
    "ValidTableName",
    "build_sql",
    "get_duckdb",
    "init_schema",
    "insert_constituents",
    "insert_prices",
    "insert_risk_free_rate",
    "insert_roe",
    "load_constituents",
    "load_daily_status",
    "load_fundamentals",
    "load_fundamentals_panel",
    "load_fundamentals_pit",
    "load_fundamentals_ttm",
    "load_index_members",
    "load_index_members_history",
    "load_latest_dates",
    "load_latest_filed",
    "load_prices",
    "load_risk_free_rate",
    "load_roe",
    "load_stock_basic",
    "load_trade_calendar",
    "loader",
    "read_constituents",
    "read_prices",
    "read_risk_free_rate",
    "read_roe",
    "save_constituents",
    "save_daily_status",
    "save_fundamentals",
    "save_index_members",
    "save_prices",
    "save_risk_free_rate",
    "save_roe",
    "save_stock_basic",
    "save_trade_calendar",
]
