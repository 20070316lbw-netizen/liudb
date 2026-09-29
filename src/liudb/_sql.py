"""数据库写入共用的私有 SQL 辅助函数。"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import suppress

import pandas as pd
from loguru import logger

from liudb.connection import get_duckdb


def upsert_dataframe(
    df: pd.DataFrame,
    table: str,
    columns: Sequence[str],
    required: set[str],
    primary_key: Sequence[str],
    *,
    date_columns: Sequence[str],
    path: str,
    init_schema: Callable[[str], None],
    timestamp_columns: Sequence[str] = (),
) -> None:
    """校验并规范化输入，在单个事务内按主键覆盖写入。"""
    if df.empty:
        logger.warning(f"传入的 {table} DataFrame 为空，跳过写入")
        return

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{table} 缺少必需列: {missing}")

    data = df.copy()
    for column in columns:
        if column not in data.columns:
            data[column] = None
    data = data[list(columns)].copy()
    for column in date_columns:
        data[column] = pd.to_datetime(data[column]).dt.date
    for column in timestamp_columns:
        data[column] = pd.to_datetime(data[column])

    duplicates = data.duplicated(subset=list(primary_key), keep=False)
    if duplicates.any():
        keys = data.loc[duplicates, list(primary_key)].drop_duplicates().to_dict("records")
        raise ValueError(f"{table} 输入批次含重复主键: {keys[:5]}")

    # 初始化放在写入事务外，避免 DDL 失败后留下半批数据。
    init_schema(path)
    column_list = ", ".join(columns)
    with get_duckdb(path=path) as con:
        con.execute("BEGIN TRANSACTION")
        try:
            con.register("_upsert_data", data)
            con.execute(
                f"INSERT OR REPLACE INTO {table} ({column_list}) "  # noqa: S608 - 内部常量
                f"SELECT {column_list} FROM _upsert_data"
            )
            con.unregister("_upsert_data")
            con.execute("COMMIT")
        except Exception:
            with suppress(Exception):
                con.unregister("_upsert_data")
            con.execute("ROLLBACK")
            raise
    logger.info(f"成功存入 {len(data)} 条 {table} 记录")
