"""prices 表的查询注册表。

只登记一套复权口径的 OHLCV 列, 不单独注册未复权版本: 物理表 `prices` 里
`close` 存的是未复权收盘价, 真正复权后的收盘价存在 `adj_close` 列。这里把
`close` 登记为对外的逻辑列名, `open/high/low/volume` 目前没有单独的复权列,
沿用物理列名直传。调用方通过 Query 拿到的 "close" 永远是复权后的数字。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ValidTableName = Literal["prices"]

INDEX_COLUMNS = ["date", "ticker"]

# 逻辑列名 -> 物理列名。除 close 外都与物理列同名。
PHYSICAL_COLUMNS: dict[str, str] = {
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "adj_close",
    "volume": "volume",
}


@dataclass(frozen=True)
class ValidName:
    table: str            # 查询的物理表名
    columns: tuple[str, ...]  # 允许查询的逻辑列
    index: list[str]      # 查询结果的索引列


VALID: dict[str, ValidName] = {
    "prices": ValidName(
        table="prices",
        columns=tuple(PHYSICAL_COLUMNS),
        index=INDEX_COLUMNS,
    ),
}
