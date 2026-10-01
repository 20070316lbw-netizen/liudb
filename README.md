# liudb

[![CI](https://github.com/20070316lbw-netizen/liudb/actions/workflows/ci.yml/badge.svg)](https://github.com/20070316lbw-netizen/liudb/actions/workflows/ci.yml)

`liudb` 提供 DuckDB 表结构、DataFrame 清洗与存储、以及查询接口。抓取由调用方负责；
`liudb` 的读写函数只接收 DataFrame，不会在内部发起网络请求或调用数据源。

项目按市场分开使用，默认数据库为 A 股 `ashare.db` 和 S&P 500 `sp500.db`：

```python
import liudb.ashare as ashare
import liudb.sp500 as sp500

ashare.init_schema()  # ashare.db
sp500.init_schema()   # sp500.db
```

## 安装

`liudb` 没有发布到 PyPI，直接从 GitHub 安装。依赖 `sources` 同样是 Git 源，版本写在
`pyproject.toml` 的 `[tool.uv.sources]` 里（当前为 `v0.1.1`），因此推荐用 `uv`：

```bash
uv add "liudb @ git+https://github.com/20070316lbw-netizen/liudb.git"
```

需要固定版本时在 URL 后接 commit（本仓库暂无 tag）：

```bash
uv add "liudb @ git+https://github.com/20070316lbw-netizen/liudb.git#<commit>"
```

`pip` 不读 `[tool.uv.sources]`，会把 `sources` 解析成 PyPI 上的另一个同名包，
所以 pip 用户必须同时显式指定 `sources` 的 Git 地址：

```bash
pip install \
  "liudb @ git+https://github.com/20070316lbw-netizen/liudb.git" \
  "sources @ git+https://github.com/20070316lbw-netizen/sources.git@v0.1.1"
```

## 只使用 liudb

调用方可以直接构造或从其他系统取得 DataFrame，再传给对应市场的写入函数。下例不导入
数据源，展示了行情、基本资料、交易日历、成分、利率、ROE 和基本面的最小列契约：

```python
import pandas as pd
import liudb.ashare as ashare
import liudb.sp500 as sp500

ashare.init_schema("ashare.db")
sp500.init_schema("sp500.db")

# 基本资料先入库，日线清洗可以据此修正 ETF 的 ST 标记。
ashare.save_stock_basic(pd.DataFrame([{
    "ticker": "510300.SH", "name": "沪深300ETF", "sec_type": "etf",
}]), path="ashare.db")

# A 股日线写入会同时保存 prices 和 daily_status，并在入库前清洗复权价与状态字段。
daily = pd.DataFrame([{
    "date": "2024-01-02", "ticker": "510300.SH", "close": 3.50,
    "pre_close": 3.49, "volume": 1000,
}])
ashare.save_daily_bars(daily, path="ashare.db")
ashare.save_trade_calendar(pd.DataFrame([{
    "date": "2024-01-02", "is_open": True,
}]), path="ashare.db")
ashare.save_index_members(pd.DataFrame([{
    "index_code": "000300.SH", "date": "2024-01-02", "ticker": "510300.SH",
    "name": "沪深300ETF",
}]), path="ashare.db")
ashare.save_intraday_bars(pd.DataFrame([{
    "ts": "2024-01-02 10:00:00", "ticker": "510300.SH", "close": 3.50,
    "volume": 100,
}]), freq="30", path="ashare.db")

# S&P 500 数据可以独立写入，不要求由 liudb 抓取。
sp500.save_constituents(pd.DataFrame([{"ticker": "AAPL", "name": "Apple Inc."}]))
sp500.save_prices(pd.DataFrame([{
    "date": "2024-01-02", "ticker": "AAPL", "close": 185.0,
}]))
sp500.save_risk_free_rate(pd.DataFrame([{
    "date": "2024-01-02", "series": "DGS1MO", "value": 5.45,
}]))
sp500.save_roe(pd.DataFrame([{
    "ticker": "AAPL", "period_end": "2023-09-30", "roe": 1.72,
}]))
sp500.save_fundamentals(pd.DataFrame([{
    "ticker": "AAPL", "field": "net_income", "period_end": "2023-12-31",
    "period_months": 12, "value": 100.0, "accn": "0000320193-24-000001",
    "filed": "2024-02-01", "derived": False,
}]))

ashare_prices = ashare.load_prices(tickers="510300.SH", path="ashare.db")
us_prices = sp500.load_prices(tickers="AAPL", path="sp500.db")
```

各表的必需列和主键见对应 `save_*` 函数文档。写入按主键插入或覆盖，不会删除本批次未出现的
旧记录；空 DataFrame 跳过写入，批次内重复主键会报错。每次表写入在事务中完成。

## 与 sources 搭配

`sources` 负责抓取并整理字段，`liudb` 负责清洗、存储和读取。两个包通过 DataFrame 配合，
调用方决定抓取标的和日期范围。以下接口对应 `sources@v0.1.1`：

```python
import liudb.ashare as ashare
import liudb.sp500 as sp500
from sources.ashare import (
    get_daily_bars,
    get_index_members,
    get_intraday_bars,
    get_stock_basic,
    get_trade_calendar,
)
from sources.roe import get_roe
from sources.sp500.constituents import get_sp500_constituents
from sources.sp500.prices import get_prices
from sources.sp500.riskfree import get_risk_free_rate
from sources.sp500.sec.fundamentals import get_fundamentals

ashare.init_schema("ashare.db")
sp500.init_schema("sp500.db")

# A 股：按需抓取基础资料、交易日历、指数快照、日线和分钟线。
ashare.save_stock_basic(get_stock_basic(["510300.SH", "600519.SH"]))
ashare.save_trade_calendar(get_trade_calendar("2026-09-28", "2026-09-29"))
ashare.save_index_members(get_index_members("hs300", date="2026-09-28"))
ashare.save_daily_bars(get_daily_bars(["510300.SH", "600519.SH"], "2024-01-02"))
ashare.save_intraday_bars(
    get_intraday_bars("510300.SH", "2026-09-28", freq="30"), freq="30"
)

# S&P 500：每个来源单独抓取，再交给对应写入接口。
sp500.save_constituents(get_sp500_constituents())
sp500.save_prices(get_prices(["AAPL", "MSFT"], start="2025-01-02", end="2025-01-06"))
sp500.save_risk_free_rate(get_risk_free_rate(start="2025-01-02", end="2025-01-06"))
sp500.save_roe(get_roe("AAPL", years=1))
sp500.save_fundamentals(get_fundamentals("AAPL", fields=["net_income", "total_equity"]))
```

`sources` 网络请求的可用性、访问限制和覆盖历史由数据源决定；抓取失败时，`liudb` 不会自行
重试或改变抓取区间。是否增量抓取由调用方决定，可通过 `load_latest_dates`、`load_latest_ts`
或 `load_latest_filed` 查看库内最新记录。

## 查询

市场级 `load_prices` 返回物理列，包括未复权 `close` 与 `adj_close`。逻辑列查询使用
`Query`、`build_sql` 和 `loader`；逻辑列 `close` 对应复权收盘价 `adj_close`。市场入口为
查询选择正确的默认数据库：

```python
from liudb.ashare import Query as AShareQuery, loader as load_ashare
from liudb.sp500 import Query as SP500Query, loader as load_sp500

ashare_close = load_ashare(request=AShareQuery(columns=["close"], tickers=["510300.SH"]))
aapl_close = load_sp500(request=SP500Query(columns=["close"], tickers=["AAPL"]))
```

日期范围两端均包含。S&P 500 基本面接口提供原始行、点时快照、日期面板和 TTM 查询；点时读取
按 `filed` 执行 as-of 过滤，不会使用当时尚未公布的版本。历史 `financials` 表结构仍为兼容旧库
保留在 schema 中，当前没有对应的公开写入接口；新的基本面数据使用 `fundamentals` 表。

## 旧版接口

旧版 `liudb.save_*`、`liudb.load_*`、`liudb.init_schema` 和 `liudb.writer`、`liudb.schema`、
`liudb.reader.ashare` 导入路径保留为兼容转发。新代码从 `liudb.ashare` 或 `liudb.sp500` 导入，
避免市场默认库混淆。

## 开发

```bash
uv sync
uv run ruff check .
uv run pytest
```
