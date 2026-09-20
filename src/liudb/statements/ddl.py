"""数据库建表 DDL, 定义 constituents、prices、risk_free_rate、roe 等表结构。"""
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
"""
