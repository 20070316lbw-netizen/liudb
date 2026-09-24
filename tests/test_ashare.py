"""A 股相关表(trade_calendar/stock_basic/daily_status/index_members)的读写测试。

输入 DataFrame 的形状与 sources.cn 各函数的输出保持一致(含可空布尔列、NaN、NaT),
但不依赖 sources 包本身。
"""
from __future__ import annotations

import pandas as pd
import pytest

from liudb import (
    get_duckdb,
    init_schema,
    load_daily_status,
    load_index_members,
    load_index_members_history,
    load_latest_dates,
    load_prices,
    load_stock_basic,
    load_trade_calendar,
    save_daily_status,
    save_index_members,
    save_prices,
    save_stock_basic,
    save_trade_calendar,
)


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "ashare.db")
    init_schema(path=path)
    return path


def _bars() -> pd.DataFrame:
    """模拟 sources.cn.get_cn_daily_bars 的输出。"""
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-02", "2024-01-03"]),
            "ticker": ["600519.SH", "600519.SH", "000001.SZ", "000001.SZ"],
            "open": [1700.0, 1710.0, 9.0, 9.0],
            "high": [1720.0, 1715.0, 9.2, 9.0],
            "low": [1690.0, 1700.0, 8.9, 9.0],
            "close": [1710.0, 1705.0, 9.1, 9.1],
            "adj_close": [9000.0, 8973.7, 120.0, 120.0],
            "volume": [1e6, 9e5, 5e7, 0.0],
            "amount": [1.7e9, 1.5e9, 4.5e8, 0.0],
            "pre_close": [1695.0, 1710.0, 9.0, 9.1],
            "turnover": [0.08, 0.07, 0.25, float("nan")],
            "pct_chg": [0.88, -0.29, 1.11, 0.0],
            "is_suspended": [False, False, False, True],
            "is_st": [False, False, False, pd.NA],
        }
    )
    df["is_suspended"] = df["is_suspended"].astype("boolean")
    df["is_st"] = df["is_st"].astype("boolean")
    return df


def test_new_tables_created(db_path):
    with get_duckdb(path=db_path, read_only=True) as con:
        tables = set(con.execute("SHOW TABLES").df()["name"])
    assert {"trade_calendar", "stock_basic", "daily_status", "index_members"} <= tables


def test_bars_split_into_prices_and_status(db_path):
    bars = _bars()
    save_prices(bars, path=db_path)
    save_daily_status(bars, path=db_path)

    prices = load_prices(tickers="600519.SH", path=db_path)
    assert prices["adj_close"].tolist() == [9000.0, 8973.7]

    status = load_daily_status(tickers="000001.SZ", path=db_path)
    assert list(status.columns) == [
        "date", "ticker", "amount", "pre_close", "turnover", "pct_chg", "is_suspended", "is_st",
    ]
    assert status["is_suspended"].tolist() == [False, True]
    assert pd.isna(status["is_st"].iloc[1])
    assert pd.isna(status["turnover"].iloc[1])


def test_daily_status_upsert_and_filters(db_path):
    bars = _bars()
    save_daily_status(bars, path=db_path)
    bars.loc[0, "amount"] = 1.0
    save_daily_status(bars.iloc[[0]], path=db_path)

    df = load_daily_status(start="2024-01-02", end="2024-01-02", path=db_path)
    assert len(df) == 2
    assert df.set_index("ticker").loc["600519.SH", "amount"] == 1.0


def test_daily_status_requires_keys(db_path):
    with pytest.raises(ValueError, match="缺少必需列"):
        save_daily_status(pd.DataFrame({"ticker": ["600519.SH"]}), path=db_path)


def test_trade_calendar(db_path):
    cal = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "is_open": [False, True, True],
        }
    )
    save_trade_calendar(cal, path=db_path)
    save_trade_calendar(cal, path=db_path)  # 重复写入不报错

    assert len(load_trade_calendar(path=db_path)) == 3
    open_days = load_trade_calendar(start="2024-01-01", end="2024-01-02", open_only=True,
                                    path=db_path)
    assert open_days["date"].tolist() == [pd.Timestamp("2024-01-02")]


def test_stock_basic_with_missing_delist_date(db_path):
    basic = pd.DataFrame(
        {
            "ticker": ["600519.SH", "000024.SZ"],
            "name": ["贵州茅台", "招商地产"],
            "list_date": pd.to_datetime(["2001-08-27", "1993-06-07"]),
            "delist_date": pd.to_datetime([None, "2015-12-30"]),
            "sec_type": ["stock", "stock"],
            "is_listed": [True, False],
        }
    )
    save_stock_basic(basic, path=db_path)

    df = load_stock_basic(path=db_path)
    assert df["ticker"].tolist() == ["000024.SZ", "600519.SH"]
    assert pd.isna(df.set_index("ticker").loc["600519.SH", "delist_date"])
    assert load_stock_basic(tickers="000024.SZ", path=db_path)["is_listed"].tolist() == [False]


def _members(snapshot: str, tickers: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "index_code": "000300.SH",
            "date": pd.Timestamp(snapshot),
            "ticker": tickers,
            "name": [f"n{t}" for t in tickers],
            "update_date": pd.Timestamp("2023-12-11"),
        }
    )


def test_index_members_point_in_time(db_path):
    save_index_members(_members("2024-01-01", ["000001.SZ", "600519.SH"]), path=db_path)
    save_index_members(_members("2024-02-01", ["000002.SZ", "600519.SH"]), path=db_path)

    # 1 月中旬只能看到 1 月 1 日的快照
    mid_jan = load_index_members("000300.SH", "2024-01-15", path=db_path)
    assert mid_jan["ticker"].tolist() == ["000001.SZ", "600519.SH"]
    assert (mid_jan["date"] == pd.Timestamp("2024-01-01")).all()

    latest = load_index_members("000300.SH", path=db_path)
    assert latest["ticker"].tolist() == ["000002.SZ", "600519.SH"]

    # 早于第一份快照 -> 空
    assert load_index_members("000300.SH", "2023-12-31", path=db_path).empty
    # 其他指数 -> 空
    assert load_index_members("000905.SH", path=db_path).empty

    history = load_index_members_history("000300.SH", start="2024-01-01", path=db_path)
    assert len(history) == 4
    assert history["date"].is_monotonic_increasing


def test_load_latest_dates(db_path):
    bars = _bars()
    save_prices(bars[bars["date"] == "2024-01-02"], path=db_path)
    save_prices(bars[bars["ticker"] == "600519.SH"], path=db_path)

    latest = load_latest_dates("prices", path=db_path)
    assert latest["ticker"].tolist() == ["000001.SZ", "600519.SH"]
    assert latest["last_date"].tolist() == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")]

    only = load_latest_dates("prices", tickers=["600519.SH"], path=db_path)
    assert only["ticker"].tolist() == ["600519.SH"]

    assert load_latest_dates("daily_status", path=db_path).empty


def test_load_latest_dates_rejects_unknown_table(db_path):
    with pytest.raises(ValueError):
        load_latest_dates("roe; DROP TABLE prices", path=db_path)  # type: ignore[arg-type]


def test_readers_on_missing_db_return_empty(tmp_path):
    missing = str(tmp_path / "nope.db")
    init_schema(path=missing)  # 建库但不建数据
    assert list(load_trade_calendar(path=missing).columns) == ["date", "is_open"]
    assert load_index_members("000300.SH", path=missing).empty
