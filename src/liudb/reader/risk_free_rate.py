"""无风险利率读取: 从 DuckDB 查询 risk_free_rate 表。"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

import duckdb
import pandas as pd

from liudb.connection import DEFAULT_DB_PATH, get_duckdb

DateLike = str | date | datetime

_RISK_FREE_COLUMNS = ["date", "series", "value"]


def load_risk_free_rate(
    series: str | Sequence[str] | None = "DGS1MO",
    start: DateLike | None = None,
    end: DateLike | None = None,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """读取无风险利率数据, 支持按序列名和日期范围过滤。

    Args:
        series: FRED 序列标识, 单个或多个, 默认 "DGS1MO", 若为 None 则返回所有序列。
        start: 起始日期(含), 默认 None。
        end: 结束日期(含), 默认 None。
        path: 数据库文件路径, 默认 "sp500.db"。

    Returns:
        DataFrame, 列固定为 [date, series, value], 按 [series, date] 升序排列。
        表不存在或无匹配记录时返回保留列结构的空 DataFrame。

    Example:
        >>> rf = load_risk_free_rate(series="DGS1MO", start="2024-01-01")  # doctest: +SKIP
        >>> rf.columns.tolist()  # doctest: +SKIP
        ['date', 'series', 'value']
    """
    conditions: list[str] = []
    params: list[object] = []

    if series:
        series_list = [series] if isinstance(series, str) else list(series)
        placeholders = ", ".join(["?"] * len(series_list))
        conditions.append(f"series IN ({placeholders})")
        params.extend(series_list)

    if start:
        start_str = str(start)[:10]
        conditions.append("date >= ?")
        params.append(start_str)

    if end:
        end_str = str(end)[:10]
        conditions.append("date <= ?")
        params.append(end_str)

    sql = f"SELECT {', '.join(_RISK_FREE_COLUMNS)} FROM risk_free_rate"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY series, date"

    try:
        with get_duckdb(path=path, read_only=True) as con:
            return con.execute(sql, params).df()
    except duckdb.Error:
        return pd.DataFrame(columns=_RISK_FREE_COLUMNS)
