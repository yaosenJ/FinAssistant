# FinAssistant — 金融智能体项目

## 一、项目背景

A 股市场数据维度多、信息量大，散户和中小机构难以高效整合个股行情、板块轮动、财务报表、市场新闻等多源数据进行综合分析。本项目旨在基于已采集的 A 股全量数据资产，构建一套金融 RAG 检索与智能体应用系统，让用户通过自然语言对话即可完成专业的金融分析工作。

### 核心目标

- **降低分析门槛**：用自然语言替代手动查数据、算指标、写报告
- **多维数据关联**：打通个股、板块、财务、新闻之间的关联，提供全景视角
- **智能体协作**：多个专业 Agent 协同工作，覆盖从数据查询到研报生成的全流程

### 技术路线

```
用户提问 → FastAPI 接口 → AgentScope Agent → 调用工具查询数据 → LLM 汇总生成回答
                                              ↓
                              MySQL(结构化) + Milvus(向量检索) + JSON(原始数据)
```

| 层级 | 技术选型 |
|------|----------|
| 智能体框架 | AgentScope 2.0（多 Agent 编排） |
| 数据存储 | MySQL（结构化查询）+ Milvus（向量检索） |
| 数据采集 | Python + akshare + DrissionPage |
| LLM | Qwen / GPT / Claude |
| Embedding | text-embedding-v3 / BGE |
| 前端 | Streamlit / Gradio |

---

## 二、待开发功能模块

基于现有数据资产，规划以下六大智能体功能模块：

---

### 2.1 个股全景分析智能体

**数据支撑**：个股日行情 + 公司信息 + 三大财务报表

**核心功能**：

| 功能 | 说明 | 实现思路 |
|------|------|----------|
| 基本面评分 | 基于 ROE、毛利率、资产负债率、经营现金流等指标，自动打分（0-100） | 从三张报表提取关键字段，加权计算 |
| 估值分位分析 | PE/PB/PCF 在近一年历史中的百分位，判断高估/低估 | 对日线 PE/PB 序列计算分位数 |
| 技术指标计算 | MA(5/10/20/60)、MACD、RSI、布林带、KDJ | 基于 OHLCV 数据实时计算 |
| 买卖信号生成 | 金叉/死叉、突破/跌破均线、RSI 超买超卖 | 技术指标交叉判定 |
| 个股画像报告 | 综合基本面+技术面+估值+板块归属，生成结构化报告 | LLM 汇总分析结果生成文本 |

**示例问题**：
```
"浦发银行最近一个季度的现金流状况如何？"
"平安银行当前估值处于历史什么水平？"
"帮我分析贵州茅台的技术面走势，给出操作建议"
"生成一份宁德时代的个股画像报告"
```

**待开发**：
- [ ] `tools/stock_fundamental.py` — 基本面指标计算工具
- [ ] `tools/stock_valuation.py` — 估值分位分析工具
- [ ] `tools/stock_technical.py` — 技术指标计算工具
- [ ] `agents/stock_agent.py` — 个股分析 Agent 编排

---

### 2.2 板块轮动分析智能体

**数据支撑**：行业/概念板块日行情（90行业 + 374概念） + 成分股

**核心功能**：

| 功能 | 说明 | 实现思路 |
|------|------|----------|
| 板块强度排名 | 按涨跌幅、成交额变化率、资金流入等维度排名 | 对板块 daily_index 聚合计算 |
| 轮动趋势识别 | 连续N日涨幅居前的板块标记为"热点"，反之为"退潮" | 滑动窗口排名变化分析 |
| 板块对比分析 | 多板块同期涨跌曲线叠加对比 | 提取多个板块 close 序列绘图 |
| 成分股涨跌分布 | 板块内个股涨跌家数、涨跌停家数、中位涨幅 | 关联成分股当日行情数据 |
| 板块资金流向 | 成交额变化趋势，判断资金流入/流出 | 成交额环比变化分析 |
| 板块关联度 | 两个板块成分股重叠度，衡量联动性 | 集合交集/并集比 |

**示例问题**：
```
"最近一周涨幅最大的行业板块有哪些？"
"半导体板块最近一个月的走势如何？资金是在流入还是流出？"
"AI概念和机器人概念的成分股重叠度有多高？"
"今天哪些板块出现了跌停潮？"
```

**待开发**：
- [ ] `tools/sector_ranking.py` — 板块排名工具
- [ ] `tools/sector_rotation.py` — 轮动趋势识别工具
- [ ] `tools/sector_compare.py` — 板块对比工具
- [ ] `agents/sector_agent.py` — 板块分析 Agent 编排

---

### 2.3 跨数据关联分析智能体

**数据支撑**：行情 + 成分股 + 财务报表 + 新闻（全量数据交叉关联）

**核心功能**：

| 功能 | 说明 | 实现思路 |
|------|------|----------|
| 个股→板块映射 | 查询某只股票属于哪些行业/概念板块，各板块近期表现 | 遍历成分股数据反向查找 |
| 板块→财务聚合 | 板块内所有个股的平均 ROE、中位 PE、合计营收 | 关联成分股代码→财务报表 |
| 新闻→行情关联 | 新闻标题提及的公司/板块，关联其近期行情走势 | NER 实体识别 + 代码匹配 |
| 产业链上下游 | 通过概念板块成分股重叠，推断产业链关系 | 成分股集合相似度聚类 |
| 龙头效应分析 | 板块内市值最大的N只股票vs板块整体走势的相关性 | 市值加权 vs 等权指数对比 |

**示例问题**：
```
"比亚迪属于哪些概念板块？这些板块最近表现如何？"
"半导体板块的平均市盈率和平均ROE是多少？"
"最近有关于光伏的新闻吗？相关板块走势怎样？"
"找出和宁德时代关联度最高的5只股票"
```

**待开发**：
- [ ] `tools/stock_sector_mapping.py` — 个股-板块映射工具
- [ ] `tools/sector_financial_agg.py` — 板块财务聚合工具
- [ ] `tools/news_stock_linker.py` — 新闻-行情关联工具
- [ ] `agents/correlation_agent.py` — 关联分析 Agent 编排

---

### 2.4 财务问答智能体（RAG）

**数据支撑**：三大财务报表（4593只股票 x 近三年多期） + 向量数据库 (Milvus)

**核心功能**：

| 功能 | 说明 | 实现思路 |
|------|------|----------|
| 自然语言查财务 | "哪些公司毛利率超过50%" → SQL/向量检索 | 财务字段向量化 + 结构化查询 |
| 跨股票对比 | 同行业多家公司财务指标横向对比 | 按行业分组 + 指标对比表 |
| 多期趋势分析 | 同一公司连续多期报表纵向对比，计算变化率 | 时间序列分析 + 趋势判断 |
| 异常指标预警 | 现金流骤降、应收账款激增、商誉减值等异常 | 阈值/环比变化检测 |
| 财务健康度评分 | 综合偿债能力、盈利能力、成长能力、运营能力打分 | 杜邦分析体系 + 加权评分 |

**示例问题**：
```
"近一年经营活动现金流持续为正的银行股有哪些？"
"对比宁德时代和比亚迪的资产负债率变化趋势"
"哪些公司最近一个季度毛利率下降超过10%？"
"给我一份贵州茅台的杜邦分析"
"找出ROE连续三年超过20%的公司"
```

**待开发**：
- [ ] `tools/financial_query.py` — 财务数据查询工具
- [ ] `tools/financial_compare.py` — 财务对比分析工具
- [ ] `tools/financial_anomaly.py` — 异常指标检测工具
- [ ] `tools/financial_score.py` — 财务健康度评分工具
- [ ] `agents/financial_agent.py` — 财务问答 Agent 编排
- [ ] `rag/financial_embedding.py` — 财务报表向量化入库

---

### 2.5 市场日报/晨会简报智能体

**数据支撑**：全量数据（行情 + 板块 + 新闻 + 财务）

**核心功能**：

| 功能 | 说明 | 实现思路 |
|------|------|----------|
| 大盘概览 | 主要指数涨跌、成交额、涨跌家数统计 | 聚合全市场个股数据 |
| 板块轮动摘要 | 今日领涨/领跌板块、资金流入/流出板块 Top5 | 板块排名工具输出 |
| 异动个股捕捉 | 涨停/跌停、放量突破、异常波动个股 | 筛选条件过滤 |
| 重要新闻摘要 | 当日与市场相关的重要新闻，关联受影响板块 | 新闻筛选 + LLM 摘要 |
| 自选股日报 | 用户关注股票的当日表现、公告、新闻 | 个性化过滤 |
| 趋势研判 | 基于近N日数据，给出市场情绪判断（乐观/中性/悲观） | 多维度指标综合 |

**示例问题**：
```
"帮我生成今天的市场晨会简报"
"今天有哪些股票涨停？分别属于什么板块？"
"最近一周市场情绪怎么样？"
"我的自选股今天表现如何？"
```

**待开发**：
- [ ] `tools/market_overview.py` — 大盘概览工具
- [ ] `tools/abnormal_detector.py` — 异动检测工具
- [ ] `tools/daily_digest.py` — 日报生成工具
- [ ] `agents/daily_report_agent.py` — 日报 Agent 编排

---

### 2.6 投资研究报告生成智能体

**数据支撑**：全量数据 + LLM 生成能力

**核心功能**：

| 功能 | 说明 | 实现思路 |
|------|------|----------|
| 个股深度报告 | 综合基本面、技术面、估值、行业地位，生成结构化研报 | 调用前序工具 + LLM 长文本生成 |
| 行业研究报告 | 板块走势、成分股财务聚合、产业链分析、投资建议 | 板块工具 + 财务工具 + LLM |
| 比较分析报告 | 2-3家同行业公司多维度对比 | 对比工具 + LLM |
| 事件影响分析 | 某新闻/政策对相关板块和个股的影响评估 | 新闻关联 + 历史类比 + LLM |
| 投资组合建议 | 基于风险偏好，推荐板块/个股配置比例 | 优化算法 + LLM |

**示例问题**：
```
"帮我写一份关于半导体行业的深度研究报告"
"对比比亚迪、宁德时代、隆基绿能，出一份比较分析"
"美联储加息对A股哪些板块影响最大？"
"我偏好稳健型投资，帮我推荐几个板块配置方案"
```

**待开发**：
- [ ] `tools/report_generator.py` — 研报生成工具（LLM 调用 + 模板）
- [ ] `templates/` — 研报模板（个股/行业/对比/事件）
- [ ] `agents/report_agent.py` — 研报 Agent 编排
- [ ] `agents/portfolio_agent.py` — 投资组合 Agent 编排

---

## 三、数据资产

### 3.1 数据总览

| 数据类型 | 数量 | 数据源 | 时间范围 |
|----------|------|--------|----------|
| 沪市个股日行情 | 1698 只 | 新浪财经 (akshare) | 2026-01-01 ~ 07-10 |
| 深市个股日行情 | 2895 只 | 新浪财经 (akshare) | 2026-01-01 ~ 07-10 |
| 沪市公司信息 | 1698 家 | 上交所 (akshare) | - |
| 深市公司信息 | 2895 家 | 深交所 (akshare) | - |
| 沪市财务报表 | 1698 只 | 新浪财经 (akshare) | 近三年 |
| 深市财务报表 | 2895 只 | 新浪财经 (akshare) | 近三年 |
| 行业板块日行情 | 90 板块 x 124 天 | 同花顺 (akshare) | 2026-01-01 ~ 07-10 |
| 概念板块日行情 | 374 板块 x 124 天 | 同花顺 (akshare) | 2026-01-01 ~ 07-10 |
| 行业板块成分股 | 90 板块 | 同花顺 (DrissionPage) | - |
| 概念板块成分股 | 213 板块 | 新浪财经 (akshare) | - |
| 财经新闻 | 3097 条 | 同花顺 7x24 | 2026-01-01 ~ 至今 |

### 3.2 数据结构

#### 个股日行情

每只股票一个 JSON 文件，每条记录为一个交易日：

```json
{
  "trade_date": "2026-01-05",
  "ts_code": "600000.SH",
  "symbol": "600000",
  "open": 12.47, "close": 11.82, "high": 12.48, "low": 11.8,
  "volume": 122284342.0,
  "amount": 1459886350.0,
  "pe_ttm": 5.18, "pe_static": 5.01, "pb": 0.56, "pcf": 3.52,
  "total_mv": 3936.75,
  "total_share": 33305838300.0
}
```

#### 公司基本信息

```json
// 沪市
{ "ts_code": "600000.SH", "stock_name": "浦发银行", "full_name": "上海浦东发展银行股份有限公司", "list_date": "1999-11-10", "market": "SH" }
// 深市
{ "ts_code": "000001.SZ", "stock_name": "平安银行", "industry": "J 金融业", "list_date": "1991-04-03", "total_share": 19405918198.0, "market": "SZ" }
```

> 沪市不含 `industry` 字段；深市不含 `full_name`。

#### 三大财务报表

每只股票一个文件，包含 `现金流量表`、`利润表`、`资产负债表`，按报告日倒序排列，近三年数据。

#### 板块日行情

```json
{ "industry_name": "半导体", "industry_ts_code": "881121", "daily_index": [
    { "trade_date": "2026-01-05", "open": 12092.8, "close": 12466.8, "high": 12466.8, "low": 12092.8, "vol": 2724632700, "amount": 20579792.0, "pct_chg": 1.84, "pct_change": 2.33 }
] }
```

概念板块结构一致，字段名为 `concept_name` / `concept_ts_code`。

#### 板块成分股

```json
// 行业板块（THS，仅代码+名称）
{ "name": "半导体", "code": "881121", "stock_count": 100, "stocks": [{ "code": "688216", "name": "气派科技" }] }
// 概念板块（Sina，含行情快照）
{ "name": "华为汽车", "stock_count": 97, "stocks": [{ "code": "600006", "name": "东风股份", "trade": "5.270", "changepercent": 3.131, "mktcap": 1054000 }] }
```

#### 财经新闻

```json
{ "id": "123456", "title": "标题", "digest": "摘要", "url": "链接", "tags": [{ "id": "1", "name": "标签" }], "ctime_str": "2024-01-01 08:00:00", "source": "来源" }
```

### 3.3 数据采集脚本

| 脚本 | 用途 | 数据源 |
|------|------|--------|
| `crawl_sh_stock_data.py` | 沪市个股行情+公司信息 | 新浪财经 / 上交所 |
| `crawl_sz_stock_data.py` | 深市个股行情+公司信息 | 新浪财经 / 深交所 |
| `crawl_financial_reports.py` | 三大财务报表 | 新浪财经 |
| `crawl_sector_data.py` | 板块日行情（行业+概念） | 同花顺 (akshare) |
| `crawl_sector_cons.py` | 板块成分股（行业+概念） | 新浪财经 (akshare) |
| `crawl_sector_cons_ths.py` | 板块成分股（备选） | 同花顺网页 (DrissionPage) |
| `crawl_news_ths.py` | 财经新闻 | 同花顺 7x24 API |
| `crawl_news_em.py` | 东财7x24快讯（定时） | 东方财富 (akshare) |

### 3.4 已知问题

| 问题 | 说明 |
|------|------|
| 东方财富 API 封禁 | `push2his.eastmoney.com` 完全不可用 |
| 同花顺 IP 封禁 | 频繁爬取后 IP 被 Nginx 403 封禁 |
| 板块数据源不一致 | 行情来自 THS，成分股部分来自 Sina，板块名称可能不完全对应 |
| 沪市公司信息缺行业 | 上交所 API 不提供 industry 字段 |

---

## 四、AgentScope 2.0 智能体实现思路

参考项目：`D:\realme_agent0713_1\realme_agent\`（AgentScope 2.0 客服智能体，已完成生产级部署）

### 5.1 整体架构

```
用户提问 → FastAPI 接口 → Agent (system_prompt + model + toolkit + middlewares)
                                ↓
                           Toolkit
                             ├── ToolGroup("个股分析")   → tools/stock_query.py + skills/stock-analysis/
                             ├── ToolGroup("板块分析")   → tools/sector_query.py + skills/sector-rotation/
                             ├── ToolGroup("财务问答")   → tools/financial_query.py + skills/financial-qa/
                             ├── ToolGroup("市场日报")   → tools/news_query.py + skills/daily-report/
                             └── ToolGroup("研报生成")   → tools/indicators.py + skills/research-report/
```

### 5.2 目录结构

```
FinAssistant/
├── config.py                    # 全局配置（路径、模型、API Key）
├── main.py                      # FastAPI 服务入口
├── main_agent.py                # 单智能体启动脚本（无服务，直接对话）
├── core/
│   ├── agent_setup.py           # Agent + Toolkit 初始化
│   └── middleware.py            # 金融场景中间件
├── tools/                       # 工具函数
│   ├── __init__.py
│   ├── stock_query.py           # 个股行情/公司信息查询
│   ├── sector_query.py          # 板块行情/成分股查询
│   ├── financial_query.py       # 财务报表查询与分析
│   ├── news_query.py            # 新闻查询
│   └── indicators.py            # 技术指标/基本面评分计算
├── skills/                      # 技能文档（SKILL.md）
│   ├── stock-analysis/SKILL.md
│   ├── sector-rotation/SKILL.md
│   ├── financial-qa/SKILL.md
│   ├── daily-report/SKILL.md
│   └── research-report/SKILL.md
├── data/                        # 已有数据（不动）
└── data_to_mysql_and_milvus/    # 已有爬虫脚本（不动）
```

### 5.3 实现步骤

#### 第一步：config.py

全局配置，定义数据路径、模型配置、API Key。参考 realme_agent/config.py。

#### 第二步：tools/ 工具函数

每个函数都是 `async def`，返回 `ToolChunk`。**docstring 就是工具描述**，LLM 根据 docstring 决定何时调用。

**tools/stock_query.py** — 个股查询：

```python
async def query_stock_kline(ts_code: str, start_date: str = "2026-01-01", end_date: str = "2026-07-10") -> ToolChunk:
    """查询个股日K线行情数据

    Args:
        ts_code: 股票代码，格式如 600000.SH 或 000001.SZ
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD
    """
    # 根据 ts_code 判断市场，读取对应 JSON 文件，过滤日期范围
    ...

async def search_stock(keyword: str) -> ToolChunk:
    """按名称或代码模糊搜索股票，返回匹配的股票列表"""
    ...

async def query_company_info(ts_code: str) -> ToolChunk:
    """查询公司基本信息（名称、行业、上市日期、市值等）"""
    ...
```

**tools/sector_query.py** — 板块查询：

```python
async def query_sector_ranking(board_type: str = "industry", sort_by: str = "pct_chg", date: str = None) -> ToolChunk:
    """查询板块涨跌幅排名

    Args:
        board_type: 板块类型，industry(行业) 或 concept(概念)
        sort_by: 排序字段，pct_chg(涨跌幅) 或 amount(成交额)
        date: 指定日期，格式 YYYY-MM-DD，默认最新交易日
    """
    ...

async def query_sector_stocks(board_name: str) -> ToolChunk:
    """查询板块成分股列表"""
    ...

async def find_stock_sectors(ts_code: str) -> ToolChunk:
    """查询某只股票属于哪些板块"""
    ...
```

**tools/financial_query.py** — 财务查询：

```python
async def query_financial_report(ts_code: str, report_type: str = "利润表") -> ToolChunk:
    """查询个股财务报表

    Args:
        ts_code: 股票代码
        report_type: 报表类型，可选 现金流量表、利润表、资产负债表
    """
    ...

async def compare_financial(ts_codes: list[str], indicators: list[str] = None) -> ToolChunk:
    """对比多只股票的财务指标

    Args:
        ts_codes: 股票代码列表，如 ["600519.SH", "000858.SZ"]
        indicators: 对比指标，如 ["ROE", "毛利率", "资产负债率"]
    """
    ...
```

**tools/news_query.py** — 新闻查询：

```python
async def query_news(keyword: str = "", start_date: str = "", end_date: str = "", limit: int = 10) -> ToolChunk:
    """查询财经新闻

    Args:
        keyword: 关键词过滤（如"半导体"、"美联储"）
        start_date: 开始日期
        end_date: 结束日期
        limit: 返回条数，默认10
    """
    ...
```

**tools/indicators.py** — 计算工具：

```python
async def calc_technical_indicators(ts_code: str, indicators: list[str] = None) -> ToolChunk:
    """计算个股技术指标（MA/MACD/RSI/KDJ/BOLL）"""
    ...

async def calc_fundamental_score(ts_code: str) -> ToolChunk:
    """计算个股基本面评分（0-100），基于ROE、毛利率、资产负债率、现金流等"""
    ...

async def calc_valuation_percentile(ts_code: str) -> ToolChunk:
    """计算当前PE/PB在近一年历史中的百分位，判断估值高低"""
    ...
```

#### 第三步：skills/SKILL.md 技能文档

每个技能目录下一个 SKILL.md，格式参考 realme_agent：

```markdown
---
name: stock-analysis
description: 个股全景分析技能，涵盖基本面评分、估值分位、技术指标、买卖信号。
当用户询问某只股票的分析、估值、走势、操作建议时触发本技能。
---

# 个股全景分析技能

## 触发条件
用户询问某只股票的分析、估值、走势、操作建议时触发。

## 依赖工具
1. search_stock — 模糊搜索股票
2. query_stock_kline — 查询日K线
3. query_company_info — 查询公司信息
4. query_financial_report — 查询财务报表
5. calc_fundamental_score — 基本面评分
6. calc_valuation_percentile — 估值分位
7. calc_technical_indicators — 技术指标

## 执行流程
1. 搜索确认目标股票
2. 查询公司基本面信息
3. 计算基本面评分
4. 查询估值分位
5. 计算技术指标
6. 汇总生成分析报告
```

#### 第四步：core/middleware.py 中间件

参考 realme_agent 的中间件，适配金融场景：

| 中间件 | 作用 |
|--------|------|
| `InputValidationMiddleware` | 过滤非金融问题（空消息、超长输入） |
| `ToolCallAuditMiddleware` | 记录工具调用日志到 traces/ |
| `PerformanceMonitorMiddleware` | 监控推理轮次、耗时、token |
| `ContextEnrichmentMiddleware` | 注入当前日期、交易日判断等上下文 |

#### 第五步：core/agent_setup.py 智能体初始化

核心组装逻辑：

```python
from agentscope.agent import Agent, ContextConfig
from agentscope.model import OpenAIChatModel
from agentscope.credential import OpenAICredential
from agentscope.tool import FunctionTool, ToolGroup, Toolkit

async def init_agent():
    # 1. 创建模型（OpenAI 兼容，可用 Qwen/豆包等）
    model = OpenAIChatModel(
        credential=OpenAICredential(api_key=..., base_url=...),
        model="qwen-max", stream=True,
    )

    # 2. 将工具函数包装为 FunctionTool
    stock_tools = [
        FunctionTool(query_stock_kline, is_read_only=True),
        FunctionTool(query_company_info, is_read_only=True),
        FunctionTool(search_stock, is_read_only=True),
    ]

    # 3. 按功能分组为 ToolGroup，绑定 SKILL.md
    tool_groups = [
        ToolGroup(
            name="stock-analysis",
            description="个股全景分析",
            tools=stock_tools,
            skills_or_loaders=[os.path.join(SKILLS_DIR, "stock-analysis")],
        ),
        # ... 其他 ToolGroup
    ]

    # 4. 组装 Toolkit
    toolkit = Toolkit(tool_groups=tool_groups)

    # 5. 创建 Agent
    agent = Agent(
        name="FinAssistant",
        system_prompt="你是专业的金融分析助手...",
        model=model, toolkit=toolkit,
        context_config=ContextConfig(trigger_ratio=0.8, reserve_ratio=0.2),
        middlewares=[...],
    )
    return agent
```

#### 第六步：main.py 服务入口

FastAPI 服务，提供 OpenAI 兼容的 `/v1/chat/completions` 接口。

### 5.4 工具函数与已有代码的对照

| 现有 langgraph_getdata/ | 新 tools/ | 说明 |
|---|---|---|
| `query_market_data_day_k.py` | `stock_query.py` | 个股K线查询 |
| `query_industry_index_market.py` | `sector_query.py` | 板块行情查询 |
| `query_industry_component_list.py` | `sector_query.py` | 板块成分股 |
| `query_concept_dc_day.py` | `sector_query.py` | 概念板块行情 |
| `query_concept_dc_stock.py` | `sector_query.py` | 概念板块成分股 |
| `query_fin_account.py` | `financial_query.py` | 财务报表查询 |
| （无） | `news_query.py` | 新闻查询（新增） |
| （无） | `indicators.py` | 技术指标计算（新增） |

### 5.5 依赖安装

```bash
pip install agentscope>=2.0.3 fastapi uvicorn
```
