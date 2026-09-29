"""liudb.ashare.rules: A 股涨跌停幅度、最小价位、T+0 判定。"""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from liudb.ashare.rules import MarketRules, limit_prices

R = MarketRules()


@pytest.mark.parametrize(
    ("ticker", "sec_type", "name", "is_st", "expected"),
    [
        ("600519.SH", "stock", "贵州茅台", False, 0.10),
        ("000001.SZ", "stock", "平安银行", False, 0.10),
        ("300750.SZ", "stock", "宁德时代", False, 0.20),   # 创业板
        ("301001.SZ", "stock", "某创业板", False, 0.20),
        ("688981.SH", "stock", "中芯国际", False, 0.20),   # 科创板
        ("430047.BJ", "stock", "诺思兰德", False, 0.30),   # 北交所
        ("920001.BJ", "stock", "某北交所", False, 0.30),
        ("600243.SH", "stock", "*ST 某某", True, 0.10),    # 主板 ST(不给日期按最新: 10%)
        ("300001.SZ", "stock", "ST 某某", True, 0.20),     # 创业板 ST 跟随板块
        ("510300.SH", "etf", "华泰柏瑞沪深300ETF", False, 0.10),
        ("510300.SH", "etf", "华泰柏瑞沪深300ETF", True, 0.10),  # BaoStock 给 ETF 的 ST 标记被忽略
        ("159915.SZ", "etf", "易方达创业板ETF", False, 0.20),
        ("588000.SH", "etf", "华夏上证科创板50成份ETF", False, 0.20),
        ("513100.SH", "etf", "国泰纳斯达克100(QDII-ETF)", False, 0.10),
    ],
)
def test_limit_pct(ticker, sec_type, name, is_st, expected):
    assert R.limit_pct(ticker, sec_type, name, is_st) == expected


def test_limit_override_wins():
    rules = MarketRules(limit_overrides={"510300.SH": 0.2})
    assert rules.limit_pct("510300.SH", "etf", "沪深300ETF", False) == 0.2


@pytest.mark.parametrize(("day", "expected"), [
    (date(2020, 1, 2), 0.05),
    (date(2026, 7, 3), 0.05),    # 周五, 调整前最后一个交易日
    (date(2026, 7, 6), 0.10),    # 周一起 10%
    (date(1990, 12, 19), 0.05),  # 早于第一项, 用第一项
])
def test_main_board_st_limit_by_date(day, expected):
    assert R.limit_pct("600243.SH", "stock", "*ST", True, day) == expected
    assert R.limit_pct("600243.SH", "stock", "*ST", False, day) == 0.10    # 非 ST 不受影响
    assert R.limit_pct("300001.SZ", "stock", "ST", True, day) == 0.20      # 创业板 ST 跟随板块


def test_st_limit_series_vectorized():
    days = np.array(["2026-07-03", "2026-07-06", "2026-09-01"], dtype="datetime64[D]")
    np.testing.assert_allclose(R.st_limit_series(days), [0.05, 0.10, 0.10])


def test_st_limits_must_be_sorted():
    with pytest.raises(ValueError, match="升序"):
        MarketRules(st_limits=((date(2026, 7, 6), 0.1), (date(2020, 1, 1), 0.05)))
    with pytest.raises(ValueError, match="非空"):
        MarketRules(st_limits=())


def test_st_follows_schedule():
    assert R.st_follows_schedule("600243.SH", "stock")
    assert not R.st_follows_schedule("300001.SZ", "stock")
    assert not R.st_follows_schedule("430047.BJ", "stock")
    assert not R.st_follows_schedule("510300.SH", "etf")
    assert not MarketRules(limit_overrides={"600243.SH": 0.05}).st_follows_schedule(
        "600243.SH", "stock")


@pytest.mark.parametrize(
    ("ticker", "sec_type", "name", "expected"),
    [
        ("513100.SH", "etf", "国泰纳斯达克100(QDII-ETF)", True),
        ("518880.SH", "etf", "华安黄金ETF", True),
        ("511260.SH", "etf", "国泰上证10年期国债ETF", True),
        ("159920.SZ", "etf", "华夏恒生ETF", True),
        ("510300.SH", "etf", "华泰柏瑞沪深300ETF", False),
        ("159915.SZ", "etf", "易方达创业板ETF", False),
        ("600519.SH", "stock", "贵州茅台", False),
        ("110000.SH", "convertible_bond", "某转债", False),  # 只对 ETF 用关键字判断
    ],
)
def test_t0(ticker, sec_type, name, expected):
    assert R.is_t0(ticker, sec_type, name) is expected


def test_t0_override_wins():
    rules = MarketRules(t0_overrides={"518880.SH": False, "510300.SH": True})
    assert rules.is_t0("518880.SH", "etf", "华安黄金ETF") is False
    assert rules.is_t0("510300.SH", "etf", "沪深300ETF") is True


def test_tick():
    assert R.tick("etf") == 0.001
    assert R.tick("stock") == 0.01


def test_limit_prices_round_half_up():
    pre = np.array([4.736, 10.0, 8.415, np.nan])
    pct = np.array([0.10, 0.10, 0.10, 0.10])
    tick = np.array([0.001, 0.01, 0.001, 0.001])
    up, down = limit_prices(pre, pct, tick)
    # 4.736 * 1.1 = 5.2096 -> 5.210; 4.736 * 0.9 = 4.2624 -> 4.262
    np.testing.assert_allclose(up[:3], [5.210, 11.00, 9.257])
    np.testing.assert_allclose(down[:3], [4.262, 9.00, 7.574])
    assert np.isnan(up[3]) and np.isnan(down[3])


def test_limit_prices_half_tick_rounds_up():
    # 10.05 * 1.1 = 11.055 -> 11.06(四舍五入, 不是银行家舍入); 浮点误差不能把它变成 11.05
    up, _ = limit_prices(np.array([10.05]), np.array([0.10]), np.array([0.01]))
    assert up[0] == pytest.approx(11.06)
