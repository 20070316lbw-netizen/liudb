"""S&P 500 与 SEC 数据的读取接口。"""
from __future__ import annotations

import pandas as pd

from liudb.connection import DEFAULT_DB_PATH
from liudb.reader.constituents import load_constituents
from liudb.reader.fundamentals import (
    load_fundamentals,
    load_fundamentals_panel,
    load_fundamentals_pit,
    load_fundamentals_ttm,
    load_latest_filed,
)
from liudb.reader.prices import load_prices
from liudb.reader.query import Query, build_sql
from liudb.reader.query import loader as _loader
from liudb.reader.risk_free_rate import load_risk_free_rate
from liudb.reader.roe import load_roe


def loader(*, request: Query, path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """执行逻辑价格列查询，默认连接 S&P 500 数据库。"""
    return _loader(request=request, path=path)

__all__ = [
    "Query",
    "build_sql",
    "load_constituents",
    "load_fundamentals",
    "load_fundamentals_panel",
    "load_fundamentals_pit",
    "load_fundamentals_ttm",
    "load_latest_filed",
    "load_prices",
    "load_risk_free_rate",
    "load_roe",
    "loader",
]
