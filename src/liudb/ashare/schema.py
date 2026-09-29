"""A 股数据库表结构与初始化入口。"""
from __future__ import annotations

from liudb._schema import initialize
from liudb.connection import ASHARE_DB_PATH, get_duckdb

ASHARE_DDL = """
    CREATE TABLE IF NOT EXISTS prices (
        date        DATE NOT NULL,
        ticker      VARCHAR NOT NULL,
        open        DOUBLE,
        high        DOUBLE,
        low         DOUBLE,
        close       DOUBLE NOT NULL,
        adj_close   DOUBLE,
        volume      DOUBLE,
        PRIMARY KEY (ticker, date)
    );

    CREATE TABLE IF NOT EXISTS trade_calendar (
        date        DATE PRIMARY KEY,
        is_open     BOOLEAN NOT NULL
    );

    CREATE TABLE IF NOT EXISTS stock_basic (
        ticker      VARCHAR PRIMARY KEY,
        name        VARCHAR,
        list_date   DATE,
        delist_date DATE,
        sec_type    VARCHAR,
        is_listed   BOOLEAN
    );

    CREATE TABLE IF NOT EXISTS daily_status (
        date            DATE NOT NULL,
        ticker          VARCHAR NOT NULL,
        amount          DOUBLE,
        pre_close       DOUBLE,
        turnover        DOUBLE,
        pct_chg         DOUBLE,
        is_suspended    BOOLEAN,
        is_st           BOOLEAN,
        PRIMARY KEY (ticker, date)
    );

    CREATE TABLE IF NOT EXISTS index_members (
        index_code  VARCHAR NOT NULL,
        date        DATE NOT NULL,
        ticker      VARCHAR NOT NULL,
        name        VARCHAR,
        update_date DATE,
        PRIMARY KEY (index_code, date, ticker)
    );

    -- A 股分钟线(sources.ashare.get_intraday_bars 的输出, 入库前由 liudb 清洗)。
    -- ts 是 bar 的结束时间, 30 分钟线每个交易日 8 根(10:00 ... 15:00)。
    -- freq 为周期分钟数(5/15/30/60), 放进主键里, 不同周期共用一张表。
    -- OHLC 不复权, adj_close 后复权, 与日线口径一致。
    -- close 允许为空: 成交量为 0 的临时停牌 bar(如 513100 溢价停牌)在入库前
    -- 会把 OHLC 置成 NULL, 用 volume = 0 表示有这根 bar 但不可成交。
    CREATE TABLE IF NOT EXISTS intraday_bars (
        freq        VARCHAR NOT NULL,
        ts          TIMESTAMP NOT NULL,
        ticker      VARCHAR NOT NULL,
        open        DOUBLE,
        high        DOUBLE,
        low         DOUBLE,
        close       DOUBLE,
        adj_close   DOUBLE,
        volume      DOUBLE,
        amount      DOUBLE,
        PRIMARY KEY (freq, ticker, ts)
    );
"""


def init_schema(path: str = ASHARE_DB_PATH) -> None:
    """初始化 A 股表；并兼容旧库中分钟线 close 的非空约束。"""
    initialize(path, ASHARE_DDL)
    # 零成交量 bar 清洗后 close 为 NULL；旧库可能仍带有 NOT NULL 限制。
    with get_duckdb(path=path) as con:
        con.execute("ALTER TABLE intraday_bars ALTER COLUMN close DROP NOT NULL")


__all__ = ["ASHARE_DDL", "init_schema"]
