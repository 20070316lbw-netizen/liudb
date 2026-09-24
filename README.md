# liudb

[![CI](https://github.com/20070316lbw-netizen/liudb/actions/workflows/ci.yml/badge.svg)](https://github.com/20070316lbw-netizen/liudb/actions/workflows/ci.yml)

基于 DuckDB 的个人量化数据存储包，为后续量化框架提供底层数据持久化与读取服务，数据源对齐 `sources`。

---

## 特性

- **轻量进程内数据库**：基于 DuckDB，无需配置外部数据库服务端，零运维成本。
- **与 Pandas / sources 无缝衔接**：直接接收从 `sources` 抓取的 DataFrame 并执行零拷贝存取。
- **自动 Upsert 去重**：使用 `INSERT OR REPLACE` 语法，按业务主键自动覆盖更新，重复写入不报错。
- **模块命名安全**：SQL 语句集中于 `statements/`（避免 `sql` 命名冲突），读写分立为 `writer.py` 与 `reader.py`，保持代码简洁明了。

---

## 数据表结构

| 表名 | 对应 sources 数据 | 字段与主键 |
|---|---|---|
| `constituents` | `get_sp500_constituents()` | `ticker` (PK), `name` |
| `prices` | `get_prices(...)` | `date`, `ticker`, `open`, `high`, `low`, `close`, `adj_close`, `volume` <br> **PK**: `(ticker, date)` |
| `risk_free_rate` | `get_risk_free_rate(...)` | `date`, `series`, `value` <br> **PK**: `(series, date)` |
| `roe` | `get_roe(...)` / `get_roe_batch()` | `ticker`, `period_end`, `net_income`, `beginning_equity`, `ending_equity`, `average_equity`, `roe`, `roe_percent` <br> **PK**: `(ticker, period_end)` |

A 股(数据来自 `sources.cn`, 建议单独放一个库文件, 如 `ashare.db`; 那里的 `prices`
表存 A 股日线, 结构与美股完全相同: `close` 不复权、`adj_close` 后复权):

| 表名 | 对应 sources 数据 | 字段与主键 |
|---|---|---|
| `prices` | `sources.cn.get_cn_prices(...)` / `get_cn_daily_bars(...)` | 同上 |
| `daily_status` | `sources.cn.get_cn_daily_bars(...)` | `date`, `ticker`, `amount`, `pre_close`, `turnover`, `pct_chg`, `is_suspended`, `is_st` <br> **PK**: `(ticker, date)` |
| `trade_calendar` | `sources.cn.get_cn_trade_calendar(...)` | `date` (PK), `is_open` |
| `stock_basic` | `sources.cn.get_cn_stock_basic(...)` | `ticker` (PK), `name`, `list_date`, `delist_date`, `sec_type`, `is_listed` |
| `index_members` | `sources.cn.get_cn_index_members(_history)(...)` | `index_code`, `date`(快照日), `ticker`, `name`, `update_date` <br> **PK**: `(index_code, date, ticker)` |

---

## 目录结构

```text
src/liudb/
├── __init__.py           # 导出常用操作函数与兼容别名
├── connection.py         # DuckDB 连接管理 (get_duckdb, 支持文件与 :memory:)
├── schema.py             # 表结构初始化 (init_schema)
├── statements/           # SQL 语句集中管理 (避免与 sql 模块撞名)
│   ├── __init__.py
│   └── ddl.py            # 全部数据表的 CREATE TABLE DDL(含 A 股 4 张表)
├── writer.py             # 数据写入层 (save_* , A 股表共用 _upsert)
└── reader/               # 数据读取层
    ├── query.py / registry.py   # prices 的注册表查询 (Query / build_sql / loader)
    ├── prices.py 等             # 各表的 load_* 函数
    └── ashare.py                # A 股 4 张表的 load_* 与 load_latest_dates
```

---

## 快速开始

### 1. 初始化数据库

```python
from liudb import init_schema

# 初始化本地数据库表结构 (默认创建 sp500.db)
init_schema("sp500.db")
```

### 2. 存入数据 (从 sources 抓取后入库)

```python
from sources import get_sp500_constituents, get_prices, get_risk_free_rate
from sources.roe import get_roe_batch
from liudb import (
    save_constituents,
    save_prices,
    save_risk_free_rate,
    save_roe,
)

# 1. 抓取并存入成分股
constituents = get_sp500_constituents()
save_constituents(constituents)

# 2. 抓取并存入行情
prices = get_prices(["AAPL", "MSFT"], start="2024-01-01", end="2024-06-01")
save_prices(prices)

# 3. 抓取并存入无风险利率
rf = get_risk_free_rate(start="2024-01-01", end="2024-06-01")
save_risk_free_rate(rf)

# 4. 抓取并存入 ROE
roe = get_roe_batch(["AAPL", "MSFT"])
save_roe(roe)
```

> **提示**：习惯使用 `insert_*` 的用户可直接调用别名：`insert_constituents`、`insert_prices`、`insert_risk_free_rate`、`insert_roe`。

### 3. 读取数据 (供策略与回测框架使用)

```python
from liudb import (
    load_constituents,
    load_prices,
    load_risk_free_rate,
    load_roe,
)

# 读取特定股票在指定时间区间的行情
df_prices = load_prices(tickers=["AAPL", "MSFT"], start="2024-01-01", end="2024-03-01")

# 读取无风险利率 (默认 DGS1MO)
df_rf = load_risk_free_rate(start="2024-01-01")

# 读取 ROE 财务指标
df_roe = load_roe(tickers=["AAPL"])
```

> **提示**：同样支持 `read_*` 别名：`read_constituents`、`read_prices`、`read_risk_free_rate`、`read_roe`。

### 4. A 股(沪深300 日线)

```python
from sources.cn import (
    get_cn_daily_bars, get_cn_index_members_history, get_cn_trade_calendar, session,
)
from liudb import (
    load_index_members, load_latest_dates, load_trade_calendar,
    save_daily_status, save_index_members, save_prices, save_trade_calendar,
)

DB = "ashare.db"

with session():
    members = get_cn_index_members_history("hs300", "2015-01-01")   # 月度成分快照
    save_index_members(members, DB)
    save_trade_calendar(get_cn_trade_calendar("2015-01-01"), DB)

    tickers = sorted(members["ticker"].unique())                     # 含曾经的成分股
    bars = get_cn_daily_bars(tickers, start="2015-01-01")
    save_prices(bars, DB)          # 行情列 -> prices
    save_daily_status(bars, DB)    # 状态列 -> daily_status

# 读取
universe = load_index_members("000300.SH", "2020-06-30", path=DB)   # 截至该日的最近一份快照
days = load_trade_calendar("2024-01-01", "2024-12-31", open_only=True, path=DB)
latest = load_latest_dates("prices", path=DB)   # 每只股票已入库到哪天, 增量抓取从次日开始
```

---

## 开发与测试

```bash
uv run ruff check .
uv run pytest
```

CI(`.github/workflows/ci.yml`)在 push / PR 到 main 时按 `uv.lock` 安装依赖,
跑同样的 ruff 与 pytest。ruff 版本上界锁死, 规则集在 `pyproject.toml` 里显式写出,
与 sources 保持一致。