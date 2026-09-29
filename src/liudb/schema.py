"""旧版 schema 接口的兼容转发层。"""
from __future__ import annotations

from typing import Literal

from liudb.ashare.schema import init_schema as init_ashare_schema
from liudb.connection import ASHARE_DB_PATH, DEFAULT_DB_PATH
from liudb.sp500.schema import init_schema as init_sp500_schema

Market = Literal["sp500", "ashare"]


def init_schema(path: str = DEFAULT_DB_PATH, *, market: Market = "sp500") -> None:
    """兼容旧版按 market 参数初始化的接口。"""
    if market == "sp500":
        init_sp500_schema(path)
    elif market == "ashare":
        init_ashare_schema(path)
    else:
        raise ValueError(f"unknown market {market!r}, expected ['ashare', 'sp500']")


__all__ = [
    "ASHARE_DB_PATH",
    "DEFAULT_DB_PATH",
    "init_ashare_schema",
    "init_schema",
    "init_sp500_schema",
]
