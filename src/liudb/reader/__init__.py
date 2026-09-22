"""数据读取包, 负责从 DuckDB 查询并返回清洗后的量化数据 DataFrame。

- `prices` 表有一套基于注册表的查询路径: `registry.VALID` 登记允许查询的
  (复权)列, `query.Query`/`build_sql`/`loader` 负责校验、拼 SQL、执行查询,
  思路照抄 quant_lab/src/quant_lab/data 下的 PostgreSQL 版本, 只是换成了
  DuckDB 的参数化占位符。
- constituents/risk_free_rate/roe 三张表暂时保留原有的直接查询函数, 不在
  这次重构范围内。
- `load_prices` 是保留给旧调用方(如 minibacktest)过渡用的兼容接口, 返回
  未经复权改写的物理列; 新代码建议改用 `Query`/`loader`。
"""
from __future__ import annotations

from liudb.reader.constituents import load_constituents
from liudb.reader.prices import load_prices
from liudb.reader.query import Query, build_sql, loader
from liudb.reader.registry import VALID, ValidTableName
from liudb.reader.risk_free_rate import load_risk_free_rate
from liudb.reader.roe import load_roe

__all__ = [
    "VALID",
    "Query",
    "ValidTableName",
    "build_sql",
    "load_constituents",
    "load_prices",
    "load_risk_free_rate",
    "load_roe",
    "loader",
]
