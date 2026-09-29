"""A 股交易规则: 涨跌停幅度、最小价位、T+0 判定。全部可覆盖。

涨跌停幅度(按优先级):
    1. limit_overrides 里显式给了的代码;
    2. 股票: 北交所 30%; 创业板(300/301)、科创板(688/689) 20%(ST 也跟随板块);
       主板 10%, 主板 ST 按日期查 st_limits: 沪深主板 ST 自 2026-07-06 起由 5%
       调整为 10%(两市同日实施);
    3. ETF: 名称含 "创业板" / "科创" 的 20%, 其余 10%。
       ETF 的 is_st 一律忽略(BaoStock 对 ETF 恒给 True)。
    没有覆盖: 新股上市前 5 日不设涨跌停、退市整理期等特殊情形。

T+0(当天买入当天可卖):
    1. t0_overrides 里显式给了的代码;
    2. 只有 ETF 才可能 T+0: 名称含跨境 / 黄金 / 债券 / 货币类关键字的判为 T+0;
    3. 其余一律 T+1。关键字判断是启发式的, 判错了用 t0_overrides 纠正。

最小价位: ETF 0.001 元, 其余 0.01 元。
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

import numpy as np

_GROWTH_PREFIXES = ("300", "301", "688", "689")
_BSE_SUFFIX = ".BJ"


@dataclass(frozen=True)
class MarketRules:
    """A 股交易规则参数, 判定逻辑见模块说明; 所有字段都可以被调用方覆盖。

    幅度都是小数(0.10 表示 10%)。关键字判断(ETF 是否 20% / 是否 T+0)是启发式的,
    判错了用 limit_overrides / t0_overrides 按代码纠正, 覆盖优先于一切其他规则。
    """

    main_limit: float = 0.10       # 主板
    # 主板 ST 的涨跌幅: (生效日, 幅度), 按日期升序; 早于第一项的日期用第一项
    st_limits: tuple[tuple[date, float], ...] = (
        (date(1998, 4, 22), 0.05),
        (date(2026, 7, 6), 0.10),
    )
    growth_limit: float = 0.20     # 创业板 / 科创板(ST 也跟随板块)
    bse_limit: float = 0.30        # 北交所
    fund_limit: float = 0.10       # ETF(名称不含 growth_fund_keywords 的)
    # ETF 名称含这些词的按 growth_limit(跟踪创业板 / 科创板指数)
    growth_fund_keywords: tuple[str, ...] = ("创业板", "科创")
    # ETF 名称含这些词的判为 T+0(跨境、黄金、债券、货币类)
    t0_fund_keywords: tuple[str, ...] = (
        "QDII", "黄金", "债", "货币", "恒生", "港股", "H股", "中概", "纳斯达克", "标普", "日经",
    )
    limit_overrides: Mapping[str, float] = field(default_factory=dict)   # {代码: 幅度}
    t0_overrides: Mapping[str, bool] = field(default_factory=dict)       # {代码: 是否 T+0}

    def __post_init__(self) -> None:
        """检查 st_limits 的格式, 写错了在构造时就报, 不拖到算涨跌停价的时候。"""
        days = [d for d, _ in self.st_limits]
        if not days or days != sorted(set(days)):
            raise ValueError(f"st_limits 必须非空、按日期升序且不重复: {self.st_limits}")

    def limit_pct(self, ticker: str, sec_type: str | None, name: str | None,
                  is_st: bool | None, day: date | None = None) -> float:
        """一只证券的涨跌停幅度, 优先级见模块说明。

        Args:
            ticker: 标准代码, 如 "600519.SH"。
            sec_type: 证券类型("stock" / "etf" / ...), 来自 stock_basic。
            name: 证券简称, 只用于 ETF 的关键字判断。
            is_st: 当天是否 ST; 对 ETF 忽略(BaoStock 对 ETF 恒给 True)。
            day: 交易日, 只影响主板 ST(见 st_limits); None 时按最新规则。

        Returns:
            幅度(小数), 如 0.10。

        Example:
            >>> from datetime import date
            >>> r = MarketRules()
            >>> r.limit_pct("300750.SZ", "stock", "宁德时代", False)
            0.2
            >>> r.limit_pct("600243.SH", "stock", "*ST 某某", True, date(2026, 7, 3))
            0.05
        """
        if ticker in self.limit_overrides:
            return float(self.limit_overrides[ticker])
        if sec_type == "etf":
            return self.growth_limit if _has_any(name, self.growth_fund_keywords) \
                else self.fund_limit
        if ticker.endswith(_BSE_SUFFIX):
            return self.bse_limit
        if ticker.startswith(_GROWTH_PREFIXES):
            return self.growth_limit
        return self.st_limit_on(day) if is_st is True else self.main_limit

    def st_follows_schedule(self, ticker: str, sec_type: str | None) -> bool:
        """这只证券打上 ST 后, 涨跌幅是否按 st_limits 随日期变化。

        只有主板股票是: ETF 忽略 ST、北交所和创业板 / 科创板的 ST 跟随板块、
        limit_overrides 里的代码用覆盖值。调用方用它决定哪些列要逐日查表。

        Args:
            ticker: 标准代码。
            sec_type: 证券类型。

        Returns:
            是否按 st_limits 逐日变化。
        """
        return (ticker not in self.limit_overrides and sec_type != "etf"
                and not ticker.endswith(_BSE_SUFFIX)
                and not ticker.startswith(_GROWTH_PREFIXES))

    def st_limit_on(self, day: date | None = None) -> float:
        """某一天主板 ST 的涨跌幅。

        Args:
            day: 交易日; None 时取 st_limits 的最后一项(最新规则)。早于第一项的
                日期用第一项。

        Returns:
            幅度(小数)。
        """
        if day is None:
            return self.st_limits[-1][1]
        return float(self.st_limit_series(np.array([day], dtype="datetime64[D]"))[0])

    def st_limit_series(self, days: np.ndarray) -> np.ndarray:
        """向量化的 st_limit_on, 给调用方一次查完所有 bar 用。

        Args:
            days: datetime64 数组(任意精度, 按日比较)。

        Returns:
            与 days 同形状的 float 数组。

        Example:
            >>> days = np.array(["2026-07-03", "2026-07-06"], dtype="datetime64[D]")
            >>> MarketRules().st_limit_series(days).tolist()
            [0.05, 0.1]
        """
        starts = np.array([d for d, _ in self.st_limits], dtype="datetime64[D]")
        pcts = np.array([p for _, p in self.st_limits], dtype=float)
        idx = np.searchsorted(starts, np.asarray(days).astype("datetime64[D]"), side="right") - 1
        return pcts[np.clip(idx, 0, None)]

    def is_t0(self, ticker: str, sec_type: str | None, name: str | None) -> bool:
        """是否 T+0(当天买入当天可卖)。

        Args:
            ticker: 标准代码; 在 t0_overrides 里的直接用覆盖值。
            sec_type: 证券类型; 只有 "etf" 才可能 T+0。
            name: 证券简称, 按 t0_fund_keywords 做关键字判断。

        Returns:
            是否 T+0。

        Example:
            >>> MarketRules().is_t0("518880.SH", "etf", "华安黄金ETF")
            True
        """
        if ticker in self.t0_overrides:
            return bool(self.t0_overrides[ticker])
        return sec_type == "etf" and _has_any(name, self.t0_fund_keywords)

    def tick(self, sec_type: str | None) -> float:
        """最小价位(元): ETF 0.001, 其余 0.01。"""
        return 0.001 if sec_type == "etf" else 0.01


def limit_prices(
    pre_close: np.ndarray, pct: np.ndarray, tick: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """按交易所规则算涨跌停价: 前收 x (1 ± 幅度), 按最小价位四舍五入(不是银行家舍入)。

    Args:
        pre_close: 前收盘价(官方口径)。
        pct: 涨跌停幅度(小数)。
        tick: 最小价位。
        三者可以是任意同形状或可广播的数组。

    Returns:
        (涨停价, 跌停价); pre_close 为 NaN 的位置结果也是 NaN。

    Example:
        >>> up, down = limit_prices(np.array([10.05]), np.array([0.10]), np.array([0.01]))
        >>> float(up[0]), float(down[0])
        (11.06, 9.05)
    """
    pre = np.asarray(pre_close, dtype=float)
    return _round_half_up(pre * (1 + pct), tick), _round_half_up(pre * (1 - pct), tick)


def _round_half_up(x: np.ndarray, tick: np.ndarray) -> np.ndarray:
    """按 tick 四舍五入(0.5 进位); np.round 是银行家舍入, 不符合交易所规则。"""
    # 1e-9 吸收浮点误差: 10.05 * 1.1 = 11.055000000000001 或 11.054999999999999 都应得到 11.06
    return np.round(np.floor(x / tick + 0.5 + 1e-9) * tick, 6)


def _has_any(text: str | None, keywords: tuple[str, ...]) -> bool:
    """text 里是否含任一关键字; text 为空时为 False。"""
    return bool(text) and any(k in text for k in keywords)
