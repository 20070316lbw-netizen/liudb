"""A 股数据的入库前清洗: 修正 BaoStock 的已知数据质量问题。

纯函数, 不访问数据库; 需要的历史上下文(上一根已入库日线、证券资料、日线复权因子)
由写入层查好后传进来(见 liudb.ashare.writer 的清洗写入接口)。

处理的问题:
    - ETF 的 adj_close 没有复权(恒等于 close): 用交易所前收推算后复权因子,
      每日因子 = 上一日官方收盘 / 当日前收, 逐日连乘; 日线第一个交易日因子为 1,
      增量入库时用上一根已入库日线的 adj_close / close 作为种子续接。
    - ETF 的 is_st 恒为 True: 只有 sec_type == "stock" 才保留 ST 标记。
    - 成交量为 0 的分钟 bar(临时停牌): OHLC 被 BaoStock 填成 0, 置成 NaN,
      与缺 bar 同样处理; volume / amount 保留原值(volume = 0)。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_OHLC_FIELDS = ("open", "high", "low", "close")


def clean_daily_bars(
    bars: pd.DataFrame,
    *,
    basic: pd.DataFrame | None = None,
    prior: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """日线入库前清洗: 重算后复权收盘价 + 修正 ETF 的 is_st。

    Args:
        bars: 日线长表, 至少 [date, ticker, close, pre_close]; 有 is_st 时一并修正。
        basic: 证券资料 [ticker, sec_type], 用于判断是否股票; 可为空。
        prior: 每只证券上一根**已入库**日线 [ticker, close, adj_close], 用来续接
            复权因子; 新证券不传或为空。

    Returns:
        清洗后的新 DataFrame(不修改入参), 列与原表一致。
    """
    if bars.empty:
        return bars.copy()
    cleaned = recompute_daily_adj_close(bars, prior)
    if basic is not None and not basic.empty and "is_st" in cleaned.columns:
        cleaned = fix_is_st(cleaned, basic)
    return cleaned



def recompute_daily_adj_close(
    bars: pd.DataFrame,
    prior: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """用交易所前收推算后复权价, 覆盖 BaoStock 的 adj_close。

    每日因子 = 上一日官方收盘 / 当日前收, 逐日连乘; 每只证券的第一天因子为 1
    (没有 prior 时), 有 prior 时把它的 adj_close / close 作为种子, 并把 prior 的
    close 当作批内第一天的上一日收盘。前收缺失或为 0 的那些天因子不变。

    Args:
        bars: 日线长表, 含 [date, ticker, close, pre_close]。
        prior: 上一根已入库日线 [ticker, close, adj_close]; 没有则从 1 起算。

    Returns:
        新 DataFrame, adj_close 已被重写; 缺 close / pre_close 时原样返回。
    """
    if bars.empty or "close" not in bars.columns or "pre_close" not in bars.columns:
        return bars.copy()

    d = bars.copy()
    d["_date"] = pd.to_datetime(d["date"])
    d = d.sort_values(["ticker", "_date"]).reset_index(drop=True)
    adj = np.full(len(d), np.nan, dtype=float)
    seeds = _seed_factors(prior)

    for ticker, group in d.groupby("ticker", sort=False):
        idx = group.index.to_numpy()
        close = pd.to_numeric(group["close"], errors="coerce").to_numpy(dtype=float)
        pre = pd.to_numeric(group["pre_close"], errors="coerce").to_numpy(dtype=float)
        prev = np.empty_like(close)
        prev[0] = np.nan
        prev[1:] = close[:-1]

        seed_factor, seed_close = seeds.get(str(ticker), (1.0, np.nan))
        if np.isfinite(seed_close) and seed_close > 0:
            prev[0] = seed_close
        ratio = np.where(np.isfinite(prev) & (pre > 0), prev / pre, 1.0)
        adj[idx] = close * seed_factor * np.cumprod(ratio)

    d["adj_close"] = adj
    return d.drop(columns="_date")


def _seed_factors(prior: pd.DataFrame | None) -> dict[str, tuple[float, float]]:
    """prior -> {ticker: (复权因子, 上一日收盘)}; 数据不全的证券不返回。"""
    if prior is None or prior.empty:
        return {}
    seeds: dict[str, tuple[float, float]] = {}
    for row in prior.itertuples(index=False):
        close = getattr(row, "close", None)
        adj = getattr(row, "adj_close", None)
        if pd.notna(close) and float(close) > 0 and pd.notna(adj):
            seeds[str(row.ticker)] = (float(adj) / float(close), float(close))
    return seeds



def fix_is_st(bars: pd.DataFrame, basic: pd.DataFrame) -> pd.DataFrame:
    """非股票的 is_st 一律置 False(BaoStock 对 ETF 恒给 True)。

    Args:
        bars: 含 [ticker, is_st] 的 DataFrame(daily_status 的来源)。
        basic: 证券资料 [ticker, sec_type]; 空表时原样返回。

    Returns:
        新 DataFrame; 只在 sec_type 明确不是 "stock" 的行上改 is_st。
    """
    if bars.empty or basic is None or basic.empty or "is_st" not in bars.columns:
        return bars.copy()
    sec_type = basic.drop_duplicates("ticker").set_index("ticker")["sec_type"]
    d = bars.copy()
    mapped = d["ticker"].astype(str).map(sec_type).astype("string")
    mask = mapped.notna() & mapped.ne("stock")
    d["is_st"] = d["is_st"].astype("boolean").where(~mask, False).astype("boolean")
    return d


def clean_intraday_bars(
    bars: pd.DataFrame,
    daily: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """分钟线入库前清洗: 重算 adj_close + 把零成交量 bar 的 OHLC 置 NaN。

    Args:
        bars: 分钟线长表, 至少 [ts, ticker, close]; 有 volume 时按成交量为 0 处理。
        daily: 同日线 read(日线 prices, 含 [date, ticker, close, adj_close]),
            用来给分钟线提供当天的复权因子; 没有的那天保留原始 adj_close。

    Returns:
        新 DataFrame(不修改入参), 列与原表一致。
    """
    if bars.empty:
        return bars.copy()
    d = recompute_intraday_adj_close(bars, daily)
    if "volume" in d.columns:
        no_trade = pd.to_numeric(d["volume"], errors="coerce").fillna(0.0) <= 0
        for field in _OHLC_FIELDS:
            if field in d.columns:
                d[field] = d[field].where(~no_trade, np.nan)
        if "adj_close" in d.columns:
            d.loc[no_trade, "adj_close"] = np.nan
    return d



def recompute_intraday_adj_close(
    bars: pd.DataFrame,
    daily: pd.DataFrame,
) -> pd.DataFrame:
    """用当天的日线复权因子重算分钟线 adj_close。

    因子 = 日线 adj_close / close, 按 (ticker, 交易日) 用 as-of 向后对齐(当天没有
    日线时沿用之前最近一天)。找不到日线的 bar 保留原始 adj_close, 不强行覆盖。

    Args:
        bars: 分钟线长表, 含 [ts, ticker, close]。
        daily: 日线 prices, 含 [date, ticker, close, adj_close]。

    Returns:
        新 DataFrame; 复用可计算的 bar 上的 adj_close。
    """
    if bars.empty or daily is None or daily.empty or "ts" not in bars.columns:
        return bars.copy()

    out = bars.copy()
    out["_day"] = pd.to_datetime(out["ts"]).dt.normalize()
    if "adj_close" not in out.columns:
        out["adj_close"] = np.nan

    right = daily[["ticker", "date", "close", "adj_close"]].copy()
    right["date"] = pd.to_datetime(right["date"])
    right = right[right["close"] > 0].rename(
        columns={"close": "_dclose", "adj_close": "_dadj"}
    )
    by_ticker = {str(t): g.sort_values("date") for t, g in right.groupby("ticker", sort=False)}

    # 逐证券 merge_asof: 取 bar 当天(或之前最近一天)的日线因子
    for ticker, group in out.groupby("ticker", sort=False):
        d = by_ticker.get(str(ticker))
        if d is None or d.empty:
            continue
        merged = pd.merge_asof(
            group.sort_values("_day"), d[["date", "_dclose", "_dadj"]],
            left_on="_day", right_on="date", direction="backward",
        )
        factor = merged["_dadj"] / merged["_dclose"]
        computed = merged["close"] * factor
        idx = merged.index
        out.loc[idx, "adj_close"] = computed.where(
            factor.notna(), out.loc[idx, "adj_close"]
        ).to_numpy()

    return out.drop(columns="_day")
