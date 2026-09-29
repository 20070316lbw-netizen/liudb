"""S&P 500 数据库表结构与初始化入口。"""
from __future__ import annotations

from liudb._schema import initialize
from liudb.connection import DEFAULT_DB_PATH

SP500_DDL = """
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

    -- 历史汇总表保留 schema 兼容；当前基本面写入统一使用 fundamentals 表。
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

    -- SEC 基本面点时长表: 每行是某份申报文件(accn, filed)对某个期间报告的某个
    -- 标准字段的值; 同一期间的原始申报与后续重述/比较期版本全部保留, 读取时
    -- 按 filed <= 时点 取最新版本。period_months: 0=时点, 3/6/9/12=期间。
    CREATE TABLE IF NOT EXISTS fundamentals (
        ticker          VARCHAR NOT NULL,
        cik             VARCHAR,
        field           VARCHAR NOT NULL,
        concept         VARCHAR,
        unit            VARCHAR,
        period_start    DATE,
        period_end      DATE NOT NULL,
        period_months   INTEGER NOT NULL,
        value           DOUBLE,
        fy              INTEGER,
        fp              VARCHAR,
        form            VARCHAR,
        accn            VARCHAR NOT NULL,
        filed           DATE NOT NULL,
        derived         BOOLEAN NOT NULL,
        PRIMARY KEY (ticker, field, period_end, period_months, accn)
    );
"""

def init_schema(path: str = DEFAULT_DB_PATH) -> None:
    """初始化 S&P 500 数据库表，表已存在时保持原数据。"""
    initialize(path, SP500_DDL)


__all__ = ["SP500_DDL", "init_schema"]
