"""旧版写入接口的兼容转发层。新代码从 ``liudb.sp500`` 导入。"""
from __future__ import annotations

from liudb.sp500.writer import (
    save_constituents,
    save_fundamentals,
    save_prices,
    save_risk_free_rate,
    save_roe,
)

__all__ = [
    "save_constituents", "save_fundamentals", "save_prices", "save_risk_free_rate",
    "save_roe",
]
