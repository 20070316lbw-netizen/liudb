"""基于 DuckDB 的 prices 查询: Query 做校验, build_sql 拼参数化 SQL, loader 执行并返回 DataFrame。

结构照抄 quant_lab/src/quant_lab/data/loader.py 的思路(Query 校验 -> build_sql
-> loader), 只是把 PostgreSQL(psycopg.sql.Composed)换成 DuckDB 的 `?` 占位符。
"""
from __future__ import annotations

from typing import Self

import pandas as pd
from loguru import logger
from pydantic import BaseModel, field_validator, model_validator

from liudb.connection import DEFAULT_DB_PATH, get_duckdb
from liudb.reader.registry import PHYSICAL_COLUMNS, VALID, ValidTableName


class Query(BaseModel):
    """prices 查询参数。

    table   : 目标表名, 目前只注册了 "prices"。
    columns : 要查询的逻辑列, 必须都在 VALID[table].columns 白名单里。
    tickers : 限定的标的列表, 不传则不限。
    start   : 起始日期(含), 不传则不限。
    end     : 结束日期(含), 不传则不限。

    包含对内容的检查:
        1. table  : 用 Literal 做校验, 再用 @model_validator(mode="after")
                     兜底确认注册表里确实登记了这张表。
        2. columns: 用 @field_validator("columns") 逐个核对是否在白名单里,
                     不在白名单里直接 raise。
    """

    table: ValidTableName = "prices"
    columns: list[str]
    tickers: list[str] | None = None
    start: str | None = None
    end: str | None = None

    @model_validator(mode="after")
    def _check_table(self) -> Self:
        """对 table 进行检查"""
        if self.table not in VALID:
            raise ValueError(f"`table` should be one of {list(VALID)}")
        return self

    @field_validator("columns")
    @classmethod
    def _check_columns(cls, value: list[str], info) -> list[str]:
        """对 columns 做检查"""
        table = info.data.get("table", "prices")
        valid_columns = VALID[table].columns
        invalid = [column for column in value if column not in valid_columns]

        if invalid:
            raise ValueError(f"{table} not support {invalid}, valid={list(valid_columns)}")

        return value


def build_sql(request: Query) -> tuple[str, list[object]]:
    """拼接需要的 SQL 语句, 返回 (sql, params), 配合 DuckDB 的 `?` 占位符使用。"""

    table_info = VALID[request.table]
    date_col, ticker_col = table_info.index

    selected = [ticker_col, date_col] + [
        f"{PHYSICAL_COLUMNS[column]} AS {column}"
        if PHYSICAL_COLUMNS[column] != column
        else column
        for column in request.columns
    ]

    conditions: list[str] = []
    params: list[object] = []

    if request.tickers:
        placeholders = ", ".join(["?"] * len(request.tickers))
        conditions.append(f"{ticker_col} IN ({placeholders})")
        params.extend(request.tickers)

    if request.start:
        conditions.append(f"{date_col} >= ?")
        params.append(request.start)

    if request.end:
        conditions.append(f"{date_col} <= ?")
        params.append(request.end)

    sql = f"SELECT {', '.join(selected)} FROM {table_info.table}"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += f" ORDER BY {date_col}, {ticker_col}"

    return sql, params


def loader(*, request: Query, path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """以只读的形式查询并且返回 [date, ticker] MultiIndex DataFrame。"""

    sql, params = build_sql(request)
    logger.debug(f"executing prices query: {sql} params={params}")

    with get_duckdb(path=path, read_only=True) as con:
        dataframe = con.execute(sql, params).df()

    date_col, ticker_col = VALID[request.table].index
    return dataframe.set_index([date_col, ticker_col])


if __name__ == "__main__":
    query = Query(columns=["close", "volume"], start="2024-01-01", end="2024-01-31")
    logger.info(query)

    sql, params = build_sql(query)
    logger.info(f"{sql} params={params}")

    df = loader(request=query)
    print(df)
