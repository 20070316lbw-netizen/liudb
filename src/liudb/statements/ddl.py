"""数据库建表 DDL, 定义 constituents、prices、risk_free_rate、roe 等表结构。

A 股相关的 trade_calendar / stock_basic / daily_status / index_members 四张表
与美股共用一份 DDL: A 股数据建议放在单独的库文件(如 ashare.db), 那里的
prices 表存 A 股日线, 结构与美股完全相同, 下游读取代码不用区分市场。
"""
from __future__ import annotations

CREATE_TABLES = """
    CREATE TABLE IF NOT EXISTS constituents (
        ticker  VARCHAR PRIMARY KEY,
        name    VARCHAR NOT NULL
    );

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

    CREATE TABLE IF NOT EXISTS risk_free_rate (
        date    DATE NOT NULL,
        series  VARCHAR NOT NULL,
        value   DOUBLE NOT NULL,
        PRIMARY KEY (series, date)
    );

    CREATE TABLE IF NOT EXISTS roe (
        ticker              VARCHAR NOT NULL,
        period_end          DATE NOT NULL,
        net_income          DOUBLE,
        beginning_equity    DOUBLE,
        ending_equity       DOUBLE,
        average_equity      DOUBLE,
        roe                 DOUBLE,
        roe_percent         DOUBLE,
        PRIMARY KEY (ticker, period_end)
    );

    CREATE TABLE IF NOT EXISTS financials (
        ticker              VARCHAR NOT NULL,
        period_end          DATE NOT NULL,
        period_type         VARCHAR NOT NULL,
        net_income          DOUBLE,
        total_equity        DOUBLE,
        revenue             DOUBLE,
        total_assets        DOUBLE,
        PRIMARY KEY (ticker, period_end)
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
"""
