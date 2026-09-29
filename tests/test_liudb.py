"""liudb 基础功能单元测试。"""
from __future__ import annotations

import pandas as pd
import pytest

from liudb import (
    get_duckdb,
    init_ashare_schema,
    init_schema,
    init_sp500_schema,
    insert_constituents,
    insert_prices,
    load_constituents,
    load_prices,
    load_risk_free_rate,
    load_roe,
    read_constituents,
    read_prices,
    save_constituents,
    save_prices,
    save_risk_free_rate,
    save_roe,
)


@pytest.fixture
def db_path(tmp_path):
    """提供干净的临时数据库文件路径。"""
    path = str(tmp_path / "test_sp500.db")
    init_schema(path=path)
    return path


def test_init_schema(db_path):
    with get_duckdb(path=db_path, read_only=True) as con:
        tables = con.execute("SHOW TABLES").df()["name"].tolist()
    assert "constituents" in tables
    assert "prices" in tables
    assert "risk_free_rate" in tables
    assert "roe" in tables
    assert "financials" in tables


def test_constituents_save_and_load(db_path):
    df = pd.DataFrame(
        [
            {"ticker": "AAPL", "name": "Apple Inc."},
            {"ticker": "MSFT", "name": "Microsoft Corp."},
        ]
    )
    save_constituents(df, path=db_path)

    # 读取全部
    all_df = load_constituents(path=db_path)
    assert len(all_df) == 2
    assert set(all_df["ticker"]) == {"AAPL", "MSFT"}

    # 按 ticker 过滤
    apple_df = load_constituents(tickers="AAPL", path=db_path)
    assert len(apple_df) == 1
    assert apple_df.iloc[0]["name"] == "Apple Inc."

    # 测试 Upsert 覆盖更新
    update_df = pd.DataFrame([{"ticker": "AAPL", "name": "Apple"}])
    save_constituents(update_df, path=db_path)
    updated_apple = load_constituents(tickers="AAPL", path=db_path)
    assert len(updated_apple) == 1
    assert updated_apple.iloc[0]["name"] == "Apple"

    # 测试别名调用
    insert_constituents(update_df, path=db_path)
    assert len(read_constituents(path=db_path)) == 2


def test_prices_save_and_load(db_path):
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
                "volume": 5000000.0,
            },
            {
                "date": "2024-01-03",
                "ticker": "AAPL",
                "open": 182.0,
                "high": 186.0,
                "low": 181.0,
                "close": 184.0,
                "adj_close": 183.5,
                "volume": 6000000.0,
            },
            {
                "date": "2024-01-02",
                "ticker": "MSFT",
                "open": 370.0,
                "high": 375.0,
                "low": 368.0,
                "close": 372.0,
                "adj_close": 372.0,
                "volume": 3000000.0,
            },
        ]
    )
    save_prices(df, path=db_path)

    # 读取全部
    all_prices = load_prices(path=db_path)
    assert len(all_prices) == 3

    # 按 ticker 过滤
    aapl_prices = load_prices(tickers="AAPL", path=db_path)
    assert len(aapl_prices) == 2

    # 按日期范围过滤
    jan2_prices = load_prices(start="2024-01-02", end="2024-01-02", path=db_path)
    assert len(jan2_prices) == 2

    # 测试 Upsert 覆盖更新
    updated_aapl = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "ticker": "AAPL",
                "open": 180.0,
                "high": 185.0,
                "low": 179.0,
                "close": 199.9,
                "adj_close": 199.0,
                "volume": 5000000.0,
            }
        ]
    )
    insert_prices(updated_aapl, path=db_path)
    check_aapl = read_prices(tickers="AAPL", start="2024-01-02", end="2024-01-02", path=db_path)
    assert len(check_aapl) == 1
    assert check_aapl.iloc[0]["close"] == 199.9


def test_risk_free_rate_save_and_load(db_path):
    df = pd.DataFrame(
        [
            {"date": "2024-01-02", "series": "DGS1MO", "value": 5.45},
            {"date": "2024-01-03", "series": "DGS1MO", "value": 5.46},
            {"date": "2024-01-02", "series": "TB3MS", "value": 5.25},
        ]
    )
    save_risk_free_rate(df, path=db_path)

    # 默认读取 DGS1MO
    rf_dgs = load_risk_free_rate(path=db_path)
    assert len(rf_dgs) == 2
    assert (rf_dgs["series"] == "DGS1MO").all()

    # 指定读取 TB3MS
    rf_tb = load_risk_free_rate(series="TB3MS", path=db_path)
    assert len(rf_tb) == 1
    assert rf_tb.iloc[0]["value"] == 5.25


def test_roe_save_and_load(db_path):
    df = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "period_end": "2023-09-30",
                "net_income": 96995000000.0,
                "beginning_equity": 50672000000.0,
                "ending_equity": 62146000000.0,
                "average_equity": 56409000000.0,
                "roe": 1.719,
                "roe_percent": 171.9,
            }
        ]
    )
    save_roe(df, path=db_path)

    roe_df = load_roe(tickers="AAPL", path=db_path)
    assert len(roe_df) == 1
    assert roe_df.iloc[0]["roe"] == 1.719


def test_empty_dataframe_does_not_fail(db_path):
    save_constituents(pd.DataFrame(columns=["ticker", "name"]), path=db_path)
    save_prices(pd.DataFrame(columns=["date", "ticker", "close"]), path=db_path)
    save_risk_free_rate(pd.DataFrame(columns=["date", "series", "value"]), path=db_path)
    save_roe(pd.DataFrame(columns=["ticker", "period_end"]), path=db_path)


def test_sp500_upsert_rejects_duplicate_primary_keys(db_path):
    original = pd.DataFrame([{"date": "2024-01-02", "ticker": "AAPL", "close": 182.0}])
    save_prices(original, path=db_path)

    duplicates = pd.DataFrame([
        {"date": "2024-01-02", "ticker": "AAPL", "close": 183.0},
        {"date": "2024-01-02", "ticker": "AAPL", "close": 184.0},
    ])
    with pytest.raises(ValueError, match="重复主键"):
        save_prices(duplicates, path=db_path)

    stored = load_prices(tickers="AAPL", path=db_path)
    assert stored.loc[0, "close"] == 182.0


def test_missing_required_columns_raises():
    with pytest.raises(ValueError):
        save_constituents(pd.DataFrame([{"wrong_col": 1}]))
    with pytest.raises(ValueError):
        save_prices(pd.DataFrame([{"wrong_col": 1}]))
    with pytest.raises(ValueError):
        save_risk_free_rate(pd.DataFrame([{"wrong_col": 1}]))
    with pytest.raises(ValueError):
        save_roe(pd.DataFrame([{"wrong_col": 1}]))


def test_init_schema_is_market_specific(tmp_path):
    """两组 DDL 各自完整, 互不建对方的表。"""
    sp500 = str(tmp_path / "sp500.db")
    ashare = str(tmp_path / "ashare.db")
    init_sp500_schema(sp500)
    init_ashare_schema(ashare)

    def tables(path: str) -> set[str]:
        with get_duckdb(path=path, read_only=True) as con:
            return set(con.execute("SHOW TABLES").df()["name"])

    sp, ash = tables(sp500), tables(ashare)
    assert {"constituents", "prices", "risk_free_rate", "roe", "financials",
            "fundamentals"} <= sp
    assert not ({"trade_calendar", "stock_basic", "daily_status", "index_members",
                 "intraday_bars"} & sp)
    assert {"prices", "trade_calendar", "stock_basic", "daily_status", "index_members",
            "intraday_bars"} <= ash
    assert not ({"constituents", "risk_free_rate", "roe", "financials",
                 "fundamentals"} & ash)


def test_init_schema_rejects_unknown_market(tmp_path):
    with pytest.raises(ValueError, match="market"):
        init_schema(str(tmp_path / "x.db"), market="nasdaq")  # type: ignore[arg-type]


def test_init_ashare_relaxes_legacy_intraday_close(tmp_path):
    """旧库的 intraday_bars.close 是 NOT NULL, 建库时自动放开。"""
    path = str(tmp_path / "legacy.db")
    with get_duckdb(path=path) as con:
        con.execute(
            "CREATE TABLE intraday_bars ("
            "  freq VARCHAR NOT NULL, ts TIMESTAMP NOT NULL, ticker VARCHAR NOT NULL,"
            "  close DOUBLE NOT NULL, PRIMARY KEY (freq, ticker, ts))"
        )
    init_ashare_schema(path)
    with get_duckdb(path=path, read_only=True) as con:
        nullable = con.execute(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = 'intraday_bars' AND column_name = 'close'"
        ).fetchone()[0]
    assert nullable == "YES"
