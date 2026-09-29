"""liudb.ashare.clean 的纯函数清洗测试。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from liudb.ashare.clean import clean_daily_bars, clean_intraday_bars, fix_is_st


def _daily() -> pd.DataFrame:
    """ETF 除息日: 第 2 天前收 9.5 < 前一天收盘 10.0, 应产生复权因子。"""
    return pd.DataFrame({
        "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
        "ticker": "510300.SH",
        "close": [10.0, 10.0, 10.2],
        "pre_close": [10.0, 9.5, 10.0],
        "adj_close": [10.0, 10.0, 10.2],  # BaoStock 对 ETF 恒等于 close
    })


def test_daily_adj_close_uses_pre_close_chain():
    out = clean_daily_bars(_daily())
    # 因子: 1, 10/9.5, 10/10; adj = close * factor
    expected = [10.0, 10.0 * (10.0 / 9.5), 10.2 * (10.0 / 9.5)]
    assert out["adj_close"].tolist() == pytest.approx(expected)


def test_daily_adj_close_seeds_from_stored_prior():
    prior = pd.DataFrame({"ticker": ["510300.SH"], "close": [20.0], "adj_close": [25.0]})
    bars = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-05"]),
        "ticker": "510300.SH",
        "close": [21.0],
        "pre_close": [20.0],
        "adj_close": [21.0],
    })
    out = clean_daily_bars(bars, prior=prior)
    # 种子因子 1.25, 当天无除息 -> 21 * 1.25
    assert out["adj_close"].tolist() == pytest.approx([26.25])


def test_fix_is_st_only_for_stocks():
    bars = pd.DataFrame({
        "ticker": ["510300.SH", "600519.SH", "000001.SZ"],
        "is_st": [True, True, False],
    })
    basic = pd.DataFrame({
        "ticker": ["510300.SH", "600519.SH", "000001.SZ"],
        "sec_type": ["etf", "stock", "stock"],
    })
    out = fix_is_st(bars, basic)
    assert out["is_st"].tolist() == [False, True, False]


def test_clean_daily_bars_fixes_is_st_with_basic():
    bars = _daily().assign(is_st=True)
    basic = pd.DataFrame({"ticker": ["510300.SH"], "sec_type": ["etf"]})
    out = clean_daily_bars(bars, basic=basic)
    assert out["is_st"].tolist() == [False, False, False]


def _intraday() -> pd.DataFrame:
    return pd.DataFrame({
        "ts": pd.to_datetime(["2026-01-05 10:00", "2026-01-05 10:30"]),
        "ticker": "513100.SH",
        "open": [1.0, 1.0],
        "high": [1.0, 1.0],
        "low": [1.0, 1.0],
        "close": [1.0, 1.0],
        "adj_close": [1.0, 1.0],
        "volume": [0.0, 100.0],
        "amount": [0.0, 100.0],
    })


def test_intraday_zero_volume_ohlc_becomes_nan():
    out = clean_intraday_bars(_intraday())
    assert np.isnan(out.loc[0, "close"])
    assert np.isnan(out.loc[0, "adj_close"])
    assert out.loc[0, "volume"] == 0.0
    assert out.loc[1, "close"] == 1.0


def test_intraday_adj_close_uses_daily_factor():
    daily = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-05"]),
        "ticker": "513100.SH",
        "close": [1.0],
        "adj_close": [2.0],
    })
    out = clean_intraday_bars(_intraday(), daily=daily)
    assert out.loc[1, "adj_close"] == 2.0
