"""prices 表注册表查询(Query/build_sql/loader)单元测试。"""
from __future__ import annotations

import pandas as pd
import pytest

from liudb import Query, build_sql, init_schema, loader, save_prices


@pytest.fixture
def db_path(tmp_path):
    """提供干净的临时数据库文件路径, 并写入两只标的的行情数据。"""
    path = str(tmp_path / "test_sp500.db")
    init_schema(path=path)

    df = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "ticker": "AAPL",
                "open": 180.0,
                "high": 185.0,
                "low": 179.0,
                "close": 182.0,
                "adj_close": 181.5,
                "volume": 5_000_000.0,
            },
            {
                "date": "2024-01-03",
                "ticker": "AAPL",
                "open": 182.0,
                "high": 186.0,
                "low": 181.0,
                "close": 184.0,
                "adj_close": 183.5,
                "volume": 6_000_000.0,
            },
            {
                "date": "2024-01-02",
                "ticker": "MSFT",
                "open": 370.0,
                "high": 375.0,
                "low": 368.0,
                "close": 372.0,
                "adj_close": 372.0,
                "volume": 3_000_000.0,
            },
        ]
    )
    save_prices(df, path=path)
    return path


def test_query_rejects_unregistered_column():
    with pytest.raises(ValueError):
        Query(columns=["close", "adj_close"])


def test_query_rejects_unregistered_table():
    with pytest.raises(ValueError):
        Query(table="daily_prices", columns=["close"])  # type: ignore[arg-type]


def test_build_sql_selects_adj_close_as_close():
    query = Query(columns=["close"], tickers=["AAPL"], start="2024-01-01", end="2024-01-31")
    sql, params = build_sql(query)

    assert "adj_close AS close" in sql
    assert "close" not in sql.replace("adj_close AS close", "")
    assert params == ["AAPL", "2024-01-01", "2024-01-31"]


def test_loader_returns_adjusted_close_indexed_by_date_ticker(db_path):
    query = Query(columns=["close", "volume"])
    result = loader(request=query, path=db_path)

    assert result.index.names == ["date", "ticker"]
    aapl_first_day = result.loc[("2024-01-02", "AAPL")]
    assert aapl_first_day["close"] == 181.5  # 复权收盘价, 不是未复权的 182.0
    assert aapl_first_day["volume"] == 5_000_000.0


def test_loader_filters_by_ticker_and_date(db_path):
    query = Query(columns=["close"], tickers=["MSFT"], start="2024-01-02", end="2024-01-02")
    result = loader(request=query, path=db_path)

    assert len(result) == 1
    assert result.index.get_level_values("ticker").tolist() == ["MSFT"]
