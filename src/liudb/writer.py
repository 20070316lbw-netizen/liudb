"""旧版写入接口的兼容转发层。新代码按市场从 ``liudb.ashare`` 或 ``liudb.sp500`` 导入。"""
from __future__ import annotations

from liudb.ashare.writer import (
    save_ashare_daily_bars,
    save_ashare_intraday_bars,
    save_daily_status,
    save_index_members,
    save_stock_basic,
    save_trade_calendar,
)
from liudb.ashare.writer import (
    save_intraday_bars_legacy as save_intraday_bars,
)
from liudb.sp500.writer import (
    save_constituents,
    save_fundamentals,
    save_prices,
    save_risk_free_rate,
    save_roe,
)

__all__ = [
    "save_ashare_daily_bars", "save_ashare_intraday_bars", "save_constituents",
    "save_daily_status", "save_fundamentals", "save_index_members",
    "save_intraday_bars", "save_prices", "save_risk_free_rate", "save_roe",
    "save_stock_basic", "save_trade_calendar",
]
