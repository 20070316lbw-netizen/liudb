"""fundamentals 表(SEC 基本面点时长表)的写入与 as-of 读取测试。

输入 DataFrame 的形状与 sources.sp500.sec.get_fundamentals 的输出一致, 但不依赖
sources 包。虚构公司, 日历年财年:

    2023 单季 净利润: Q1 85 (2023-05-01 申报), Q2 95, Q3 100, Q4 120(推导, 2024-02-10)
    2024 Q1 10-Q(2024-05-01) 把 2023Q1 比较期改成 90(重述)
    2024 单季 净利润: Q1 110, Q2 120, Q3 130, Q4 140(推导, 10-K 2025-02-10)
    10-K/A(2025-04-01) 把 2024 全年从 500 重述为 480, 推导 Q4 变成 120
"""
from __future__ import annotations

import pandas as pd
import pytest

from liudb import (
    init_schema,
    load_fundamentals,
    load_fundamentals_panel,
    load_fundamentals_pit,
    load_fundamentals_ttm,
    load_latest_filed,
    save_fundamentals,
)

T = pd.Timestamp


def _row(field, start, end, months, value, accn, filed, *, form="10-Q", derived=False,
         ticker="TEST"):
    return {
        "ticker": ticker,
        "cik": "0000001234",
        "field": field,
        "concept": "us-gaap:NetIncomeLoss" if field == "net_income" else "us-gaap:X",
        "unit": "USD",
        "period_start": T(start) if start else pd.NaT,
        "period_end": T(end),
        "period_months": months,
        "value": float(value),
        "fy": 2024,
        "fp": "Q1",
        "form": form,
        "accn": accn,
        "filed": T(filed),
        "derived": derived,
    }


def _facts() -> pd.DataFrame:
    ni = "net_income"
    rows = [
        _row(ni, "2023-01-01", "2023-03-31", 3, 85, "Q123", "2023-05-01"),
        _row(ni, "2023-04-01", "2023-06-30", 3, 95, "Q223", "2023-08-01"),
        _row(ni, "2023-07-01", "2023-09-30", 3, 100, "Q323", "2023-11-01"),
        _row(ni, "2023-10-01", "2023-12-31", 3, 120, "K23", "2024-02-10", form="10-K",
             derived=True),
        _row(ni, "2023-01-01", "2023-12-31", 12, 400, "K23", "2024-02-10", form="10-K"),
        _row(ni, "2023-01-01", "2023-03-31", 3, 90, "Q124", "2024-05-01"),
        _row(ni, "2024-01-01", "2024-03-31", 3, 110, "Q124", "2024-05-01"),
        _row(ni, "2024-04-01", "2024-06-30", 3, 120, "Q224", "2024-08-01"),
        _row(ni, "2024-07-01", "2024-09-30", 3, 130, "Q324", "2024-11-01"),
        _row(ni, "2024-10-01", "2024-12-31", 3, 140, "K24", "2025-02-10", form="10-K",
             derived=True),
        _row(ni, "2024-01-01", "2024-12-31", 12, 500, "K24", "2025-02-10", form="10-K"),
        _row(ni, "2024-10-01", "2024-12-31", 3, 120, "K24A", "2025-04-01", form="10-K/A",
             derived=True),
        _row(ni, "2024-01-01", "2024-12-31", 12, 480, "K24A", "2025-04-01", form="10-K/A"),
        _row("total_equity", None, "2023-12-31", 0, 1000, "K23", "2024-02-10", form="10-K"),
        _row("total_equity", None, "2024-12-31", 0, 1200, "K24", "2025-02-10", form="10-K"),
        _row("total_equity", None, "2023-12-31", 0, 1000, "K24", "2025-02-10", form="10-K"),
    ]
    df = pd.DataFrame(rows)
    df["fy"] = df["fy"].astype("Int64")
    for col in ("ticker", "cik", "field", "concept", "unit", "fp", "form", "accn"):
        df[col] = df[col].astype("string")
    return df


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "fundamentals.db")
    save_fundamentals(_facts(), path)
    return path


# ---------------------------------------------------------------- 写入


def test_save_roundtrip_and_idempotent_upsert(db_path):
    save_fundamentals(_facts(), db_path)  # 重复写入按主键覆盖, 不报错不重复

    raw = load_fundamentals(path=db_path)
    assert len(raw) == len(_facts())
    equity = raw[raw["field"].eq("total_equity")]
    assert equity["period_start"].isna().all()
    assert raw["derived"].sum() == 3


def test_save_requires_key_columns(tmp_path):
    with pytest.raises(ValueError, match="缺少必需列"):
        save_fundamentals(_facts().drop(columns=["accn"]), str(tmp_path / "x.db"))


def test_save_empty_is_noop(tmp_path):
    path = str(tmp_path / "x.db")
    save_fundamentals(_facts().iloc[0:0], path)
    assert load_fundamentals(path=path).empty


# ---------------------------------------------------------------- 原始读取


def test_load_fundamentals_filters(db_path):
    raw = load_fundamentals("TEST", "net_income", start="2024-01-01", period_months=3,
                            filed_until="2025-03-01", path=db_path)

    assert raw["accn"].tolist() == ["Q124", "Q224", "Q324", "K24"]


def test_load_fundamentals_missing_table_returns_empty(tmp_path):
    path = str(tmp_path / "empty.db")
    init_schema(path)
    assert load_fundamentals_pit("2024-01-01", path=str(tmp_path / "nope.db")).empty
    out = load_fundamentals_panel(["2024-01-01"], path=path)
    assert out.empty
    assert out.columns.tolist() == [
        "date", "ticker", "field", "period_months", "period_end", "value", "filed"
    ]


# ---------------------------------------------------------------- 快照


def _pit_values(as_of, **kwargs) -> dict:
    snap = load_fundamentals_pit(as_of, **kwargs)
    return {(r.field, r.period_months): (r.period_end, r.value) for r in snap.itertuples()}


def test_pit_snapshot_latest_period(db_path):
    got = _pit_values("2024-06-30", path=db_path)

    assert got == {
        ("net_income", 3): (T("2024-03-31"), 110),
        ("net_income", 12): (T("2023-12-31"), 400),
        ("total_equity", 0): (T("2023-12-31"), 1000),
    }


def test_pit_filed_date_is_inclusive_and_revisions_apply(db_path):
    before = _pit_values("2025-02-09", fields="net_income", period_months=12, path=db_path)
    on = _pit_values("2025-02-10", fields="net_income", period_months=12, path=db_path)
    restated = _pit_values("2025-04-01", fields="net_income", period_months=12, path=db_path)

    assert before[("net_income", 12)] == (T("2023-12-31"), 400)
    assert on[("net_income", 12)] == (T("2024-12-31"), 500)
    assert restated[("net_income", 12)] == (T("2024-12-31"), 480)


def test_pit_full_history_uses_version_known_at_the_time(db_path):
    def q1_2023(as_of):
        snap = load_fundamentals_pit(as_of, fields="net_income", period_months=3,
                                     latest_only=False, path=db_path)
        return snap.set_index("period_end").loc[T("2023-03-31"), "value"]

    assert q1_2023("2024-04-30") == 85
    assert q1_2023("2024-05-01") == 90


# ---------------------------------------------------------------- 面板


def test_panel_equity_across_dates(db_path):
    dates = ["2024-01-31", "2024-06-30", "2025-03-01"]
    panel = load_fundamentals_panel(dates, fields="total_equity", path=db_path)

    assert panel["date"].tolist() == [T("2024-06-30"), T("2025-03-01")]
    assert panel["value"].tolist() == [1000, 1200]


def test_panel_staleness_cutoff(db_path):
    dates = pd.DatetimeIndex(["2025-06-30", "2027-01-01"])

    capped = load_fundamentals_panel(dates, fields="total_equity", path=db_path)
    uncapped = load_fundamentals_panel(dates, fields="total_equity",
                                       max_staleness_days=None, path=db_path)

    assert capped["date"].tolist() == [T("2025-06-30")]
    assert uncapped["date"].tolist() == [T("2025-06-30"), T("2027-01-01")]


def test_panel_empty_dates(db_path):
    assert load_fundamentals_panel([], path=db_path).empty


# ---------------------------------------------------------------- TTM


def _ttm(dates, db_path, **kwargs) -> dict:
    out = load_fundamentals_ttm(dates, fields="net_income", path=db_path, **kwargs)
    return {r.date: (r.period_end, r.value) for r in out.itertuples()}


def test_ttm_rolls_with_filings_and_revisions(db_path):
    got = _ttm(["2023-12-01", "2024-02-10", "2024-06-30", "2025-03-01", "2025-04-02"],
               db_path)

    assert T("2023-12-01") not in got  # 只有 3 个单季
    assert got[T("2024-02-10")] == (T("2023-12-31"), 85 + 95 + 100 + 120)
    assert got[T("2024-06-30")] == (T("2024-03-31"), 95 + 100 + 120 + 110)
    assert got[T("2025-03-01")] == (T("2024-12-31"), 110 + 120 + 130 + 140)
    assert got[T("2025-04-02")] == (T("2024-12-31"), 110 + 120 + 130 + 120)


def test_ttm_requires_consecutive_quarters(tmp_path):
    path = str(tmp_path / "gap.db")
    facts = _facts()
    save_fundamentals(facts[~facts["accn"].eq("Q224")], path)

    got = _ttm(["2024-12-01", "2025-03-01"], path)

    # 2024-12-01: 最近 4 个单季是 2023Q3, 2023Q4, 2024Q1, 2024Q3 -> 跨度超过 9 个月, 不返回
    assert T("2024-12-01") not in got
    assert T("2025-03-01") not in got


def test_ttm_staleness(db_path):
    assert _ttm(["2026-01-01"], db_path) == {}
    assert _ttm(["2026-01-01"], db_path, max_staleness_days=None)[T("2026-01-01")][1] == 480


# ---------------------------------------------------------------- 增量辅助


def test_load_latest_filed(db_path):
    out = load_latest_filed(path=db_path)

    assert out.to_dict("records") == [{"ticker": "TEST", "last_filed": T("2025-04-01")}]
