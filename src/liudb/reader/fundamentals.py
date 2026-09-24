"""SEC 基本面的点时(point-in-time)读取: 从 fundamentals 表按申报日期做 as-of 查询。

fundamentals 表保存同一期间的所有申报版本(原始申报、后续作为比较期再次出现、
重述), 每个版本带申报日 filed。"在时点 t 能看到的数据"定义为 filed <= t 的版本中
最新申报的那个——这样回测时不会用到当时还没公布、或者后来才改过的数字。

关于 filed: 它是 EDGAR 的官方申报日。美东 17:30 之后提交的文件会被记到下一个
工作日, 所以 filed <= t 意味着文件最晚在 t 当天 17:30 前已公开; 用 t 日收盘价
做信号、t+1 成交的回测可以直接用。若信号在 t 日盘中生成, 应把 as_of 前移一天。

提供四个层次的查询:
    load_fundamentals        -- 原始版本行, 不做 as-of 取舍(核对/调试用)
    load_fundamentals_pit    -- 单个时点的快照
    load_fundamentals_panel  -- 多个时点(如每个调仓日)的快照面板
    load_fundamentals_ttm    -- 多个时点的滚动四季度合计(TTM), 用单季值(period_months=3)求和

以及增量更新辅助 load_latest_filed。
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime

import duckdb
import pandas as pd

from liudb.connection import DEFAULT_DB_PATH, get_duckdb

DateLike = str | date | datetime

FUNDAMENTAL_COLUMNS = [
    "ticker",
    "cik",
    "field",
    "concept",
    "unit",
    "period_start",
    "period_end",
    "period_months",
    "value",
    "fy",
    "fp",
    "form",
    "accn",
    "filed",
    "derived",
]
_PIT_COLUMNS = [
    "ticker",
    "field",
    "period_months",
    "period_start",
    "period_end",
    "value",
    "concept",
    "form",
    "accn",
    "filed",
    "derived",
]
_PANEL_COLUMNS = ["date", "ticker", "field", "period_months", "period_end", "value", "filed"]
_TTM_COLUMNS = ["date", "ticker", "field", "period_end", "value"]
_LATEST_FILED_COLUMNS = ["ticker", "last_filed"]

# 多个版本在同一天申报时的先后: 报告值优先于推导值, 再按文件号
_VERSION_ORDER = "filed DESC, derived ASC, accn DESC"
# TTM 的四个单季截止日应跨约 9 个月(52/53 周财年会有几天出入)
_TTM_SPAN_DAYS = (250, 300)


def load_fundamentals(
    tickers: str | Sequence[str] | None = None,
    fields: str | Sequence[str] | None = None,
    start: DateLike | None = None,
    end: DateLike | None = None,
    *,
    period_months: int | Sequence[int] | None = None,
    filed_until: DateLike | None = None,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """读取原始版本行(同一期间可能有多行), 不做 as-of 取舍。

    Args:
        tickers: 单个或多个 ticker, 默认不限。
        fields: 单个或多个标准字段(如 "revenue"), 默认不限。
        start: period_end 下限(含)。
        end: period_end 上限(含)。
        period_months: 0(时点)/3/6/9/12, 单个或多个, 默认不限。
        filed_until: 只要 filed <= 该日的版本。
        path: 数据库文件路径。

    Returns:
        DataFrame, 列为 FUNDAMENTAL_COLUMNS, 按 [ticker, field, period_end,
        period_months, filed] 升序。
    """
    conditions, params = _filters(tickers, fields, period_months)
    for column, op, value in (("period_end", ">=", start), ("period_end", "<=", end),
                              ("filed", "<=", filed_until)):
        if value is not None:
            conditions.append(f"{column} {op} ?")
            params.append(_date_str(value))

    sql = f"SELECT {', '.join(FUNDAMENTAL_COLUMNS)} FROM fundamentals"
    sql += _where(conditions)
    sql += " ORDER BY ticker, field, period_end, period_months, filed, accn"
    return _run(sql, params, FUNDAMENTAL_COLUMNS, path)


def load_fundamentals_pit(
    as_of: DateLike,
    tickers: str | Sequence[str] | None = None,
    fields: str | Sequence[str] | None = None,
    *,
    period_months: int | Sequence[int] | None = None,
    latest_only: bool = True,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """某一时点能看到的基本面快照。

    Args:
        as_of: 时点, 只用 filed <= as_of 的版本。
        tickers / fields / period_months: 过滤条件, 同 load_fundamentals。
        latest_only: True 时每个 (ticker, field, period_months) 只返回最近一期;
            False 时返回截至 as_of 已公布的每一期(各取当时最新版本), 可用来算同比等。
        path: 数据库文件路径。

    Returns:
        DataFrame, 列为 [ticker, field, period_months, period_start, period_end, value,
        concept, form, accn, filed, derived], 按 [ticker, field, period_months,
        period_end] 升序。

    Example:
        >>> snap = load_fundamentals_pit(  # doctest: +SKIP
        ...     "2020-06-30", fields=["total_equity", "net_income"], period_months=[0, 12]
        ... )
    """
    conditions, params = _filters(tickers, fields, period_months)
    conditions.append("filed <= ?")
    params.append(_date_str(as_of))

    group = "ticker, field, period_months" if latest_only else (
        "ticker, field, period_months, period_end"
    )
    sql = f"""
        SELECT {', '.join(_PIT_COLUMNS)}
        FROM (
            SELECT *, row_number() OVER (
                PARTITION BY {group} ORDER BY period_end DESC, {_VERSION_ORDER}
            ) AS rn
            FROM fundamentals{_where(conditions)}
        )
        WHERE rn = 1
        ORDER BY ticker, field, period_months, period_end
    """
    return _run(sql, params, _PIT_COLUMNS, path)


def load_fundamentals_panel(
    dates: Iterable[DateLike],
    tickers: str | Sequence[str] | None = None,
    fields: str | Sequence[str] | None = None,
    *,
    period_months: int | Sequence[int] | None = None,
    max_staleness_days: int | None = 550,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """在一组时点(如调仓日)上分别取点时快照, 拼成长表面板。

    每个 (date, ticker, field, period_months) 取 date 当天已公布的最近一期, 同一期
    多个版本取 date 之前最新申报的那个。

    Args:
        dates: 时点序列(字符串、date、Timestamp、DatetimeIndex 都行)。
        tickers / fields / period_months: 过滤条件, 同 load_fundamentals。
        max_staleness_days: 最近一期的 period_end 距 date 超过这么多天就不返回
            (已退市、停止申报的公司不会一直沿用旧数据)。默认 550 天, 年度值(12 个月)
            在年报公布前最多也就旧 15 个月左右; None 表示不限。
        path: 数据库文件路径。

    Returns:
        DataFrame, 列为 [date, ticker, field, period_months, period_end, value, filed],
        按 [date, ticker, field, period_months] 升序。
    """
    conditions, params = _filters(tickers, fields, period_months)
    join = "f.filed <= d.date"
    join_params: list[object] = []
    if max_staleness_days is not None:
        join += " AND f.period_end >= d.date - CAST(? AS INTEGER)"
        join_params.append(int(max_staleness_days))

    sql = f"""
        WITH d AS (SELECT DISTINCT CAST(date AS DATE) AS date FROM _pit_dates),
        f AS (SELECT * FROM fundamentals{_where(conditions)}),
        j AS (
            SELECT d.date, f.*, row_number() OVER (
                PARTITION BY d.date, f.ticker, f.field, f.period_months
                ORDER BY f.period_end DESC, {_VERSION_ORDER}
            ) AS rn
            FROM d JOIN f ON {join}
        )
        SELECT {', '.join(_PANEL_COLUMNS)} FROM j WHERE rn = 1
        ORDER BY date, ticker, field, period_months
    """
    return _run_with_dates(sql, [*params, *join_params], _PANEL_COLUMNS, dates, path)


def load_fundamentals_ttm(
    dates: Iterable[DateLike],
    tickers: str | Sequence[str] | None = None,
    fields: str | Sequence[str] | None = None,
    *,
    max_staleness_days: int | None = 200,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """在一组时点上计算滚动四季度合计(TTM), 只适用于利润表/现金流量表的金额字段。

    对每个 date, 取当时已公布的最近 4 个单季(period_months=3, 含 sources 推导出的
    单季), 每个单季用 date 之前最新的版本, 求和。4 个单季必须齐全且首尾截止日相差
    约 9 个月(250~300 天), 否则不返回——宁可缺失也不拿不连续的季度凑数。

    Args:
        dates: 时点序列。
        tickers / fields: 过滤条件。fields 应为可加字段(revenue、net_income、
            operating_cash_flow、capex 等), EPS/股数这类字段求和没有意义。
        max_staleness_days: 最近一个单季的 period_end 距 date 超过这么多天就不返回,
            默认 200 天; None 表示不限。
        path: 数据库文件路径。

    Returns:
        DataFrame, 列为 [date, ticker, field, period_end(最近一个单季的截止日), value],
        按 [date, ticker, field] 升序。
    """
    conditions, params = _filters(tickers, fields, 3)
    join = "f.filed <= d.date"
    join_params: list[object] = []
    stale_filter = ""
    if max_staleness_days is not None:
        # 四个季度往前再多留 300 天, 保证最早那个季度也在窗口里
        join += " AND f.period_end >= d.date - CAST(? AS INTEGER)"
        join_params.append(int(max_staleness_days) + _TTM_SPAN_DAYS[1])
        stale_filter = " AND period_end >= date - CAST(? AS INTEGER)"

    sql = f"""
        WITH d AS (SELECT DISTINCT CAST(date AS DATE) AS date FROM _pit_dates),
        f AS (SELECT * FROM fundamentals{_where(conditions)}),
        v AS (
            SELECT d.date, f.ticker, f.field, f.period_end, f.value, row_number() OVER (
                PARTITION BY d.date, f.ticker, f.field, f.period_end
                ORDER BY {_VERSION_ORDER}
            ) AS rn
            FROM d JOIN f ON {join}
        ),
        q AS (
            SELECT date, ticker, field, period_end, value, row_number() OVER (
                PARTITION BY date, ticker, field ORDER BY period_end DESC
            ) AS k
            FROM v WHERE rn = 1
        ),
        agg AS (
            SELECT date, ticker, field,
                   max(period_end) AS period_end, min(period_end) AS first_end,
                   count(*) AS n, sum(value) AS value
            FROM q WHERE k <= 4
            GROUP BY date, ticker, field
        )
        SELECT {', '.join(_TTM_COLUMNS)} FROM agg
        WHERE n = 4
          AND date_diff('day', first_end, period_end) BETWEEN ? AND ?{stale_filter}
        ORDER BY date, ticker, field
    """
    all_params = [*params, *join_params, *_TTM_SPAN_DAYS]
    if max_staleness_days is not None:
        all_params.append(int(max_staleness_days))
    return _run_with_dates(sql, all_params, _TTM_COLUMNS, dates, path)


def load_latest_filed(
    tickers: str | Sequence[str] | None = None,
    path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """每只股票已入库的最近申报日, 供增量更新判断(比如只重抓超过一个季度没更新的)。

    Returns:
        DataFrame, 列为 [ticker, last_filed], 按 ticker 升序; 库里没有的股票不出现。
    """
    conditions, params = _filters(tickers, None, None)
    sql = "SELECT ticker, max(filed) AS last_filed FROM fundamentals"
    sql += _where(conditions) + " GROUP BY ticker ORDER BY ticker"
    return _run(sql, params, _LATEST_FILED_COLUMNS, path)


# ---------------------------------------------------------------- helpers


def _filters(
    tickers: str | Sequence[str] | None,
    fields: str | Sequence[str] | None,
    period_months: int | Sequence[int] | None,
) -> tuple[list[str], list[object]]:
    conditions: list[str] = []
    params: list[object] = []
    for column, values in (("ticker", tickers), ("field", fields),
                           ("period_months", period_months)):
        if values is None or (not isinstance(values, int) and len(values) == 0):
            continue
        items = [values] if isinstance(values, str | int) else list(values)
        conditions.append(f"{column} IN ({', '.join(['?'] * len(items))})")
        params.extend(items)
    return conditions, params


def _where(conditions: list[str]) -> str:
    return " WHERE " + " AND ".join(conditions) if conditions else ""


def _date_str(value: DateLike) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _run(sql: str, params: list[object], columns: list[str], path: str) -> pd.DataFrame:
    try:
        with get_duckdb(path=path, read_only=True) as con:
            return con.execute(sql, params).df()
    except duckdb.Error:
        return pd.DataFrame(columns=columns)


def _run_with_dates(
    sql: str,
    params: list[object],
    columns: list[str],
    dates: Iterable[DateLike],
    path: str,
) -> pd.DataFrame:
    date_frame = pd.DataFrame({"date": pd.to_datetime(list(dates)).normalize()})
    if date_frame.empty:
        return pd.DataFrame(columns=columns)
    try:
        with get_duckdb(path=path, read_only=True) as con:
            con.register("_pit_dates", date_frame)
            return con.execute(sql, params).df()
    except duckdb.Error:
        return pd.DataFrame(columns=columns)
