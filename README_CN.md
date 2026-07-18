<p align="center">
  <img
    src="./logo.svg"
    alt="FinAssistant Logo"
    width="180"
  />
</p>

<h1 align="center">FinAssistant — 金融智能体项目</h1>

<p align="center">
  <strong>基于 A 股全量数据的 RAG 检索与智能体应用系统</strong>
</p>

<p align="center">
  <a href="#一项目背景">项目背景</a> •
  <a href="#二待开发功能模块">功能模块</a> •
  <a href="#三数据资产">数据资产</a> •
  <a href="#四agentscope-20-智能体实现思路">智能体实现</a> •
  <a href="#54-已实现工具">已实现工具</a>
</p>

<p align="center">
  <b>中文</b> | <a href="./README.md">English</a>
</p>

---



## 一、项目背景

A 股市场数据维度多、信息量大，散户和中小机构难以高效整合个股行情、板块轮动、财务报表、市场新闻等多源数据进行综合分析。本项目旨在基于已采集的 A 股全量数据资产，构建一套金融 RAG 检索与智能体应用系统，让用户通过自然语言对话即可完成专业的金融分析工作。

### 核心目标

- **降低分析门槛**：用自然语言替代手动查数据、算指标、写报告
- **多维数据关联**：打通个股、板块、财务、新闻之间的关联，提供全景视角
- **智能体协作**：多个专业 Agent 协同工作，覆盖从数据查询到研报生成的全流程

### 技术路线

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
- [x] `tools/stock_fundamental.py` — 基本面指标计算工具（已完成）
- [x] `tools/stock_valuation.py` — 估值分位分析工具（已完成）
- [x] `tools/stock_technical.py` — 技术指标计算工具（已完成）
- [x] `tools/stock_analysis.py` — 个股全景分析报告工具（已完成）
- [x] `agents/stock_agent.py` — 个股分析智能体（已完成）

**运行示例**：

```
$ python agents/stock_agent.py

============================================================
FinAssistant — 金融智能体
============================================================
输入股票代码或问题开始分析，输入 'quit' 退出
============================================================

你: 帮我分析贵州茅台的技术面走势，给出操作建议

FinAssistant:
[调用工具: reset_tools]
[完成] 结果: The currently activated tool group(s): stock-technical.

[调用工具: calc_technical_summary]
[完成] 结果: === 600519.SH 技术指标分析 (2026-07-17) ===
收盘价: 1253.0
【移动平均线 MA】
  MA5:  1237.78
  MA10: 1217.11
  MA20: 1204.07
  MA60: 1263.65
  均线趋势: 多头排列
【MACD】
  DIF: -0.2443
  DEA: -11.3353
  MACD柱: 22.182
  信号: 金叉
...

### 贵州茅台(600519.SH)技术面分析与操作建议

#### 一、核心技术指标摘要（近120天）
| 指标类型 | 关键数据 | 信号解读 |
|---------|---------|---------|
| **均线系统** | MA5:1237.78, MA10:1217.11, MA20:1204.07, MA60:1263.65 | 短期均线多头排列，股价略低于MA60 |
| **MACD** | DIF:-0.24, DEA:-11.34, MACD柱:22.18 | 低位金叉形成，短期反弹信号明确 |
| **RSI** | RSI(6):92.76, RSI(12):68.80, RSI(24):48.73 | 短期RSI严重超买（>90），警惕回调风险 |
| **布林带** | 上轨:1252.21, 中轨:1204.07, 下轨:1155.92 | 股价突破上轨，处于强势区间 |
| **KDJ** | K:84.30, D:79.20, J:94.49 | 高位金叉，短期上涨动能充足 |

#### 二、综合研判
技术面呈现**强趋势与短期超买并存**的格局

#### 三、操作建议
1. **持仓投资者**：继续持有为主，可将MA20（1204.07）作为止损线
2. **观望投资者**：等待回调至关键支撑位（MA20:1204或布林中轨:1204）再考虑进场

⚠️ **风险提示**：技术分析仅供参考，不构成投资建议。
```

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

| 数据类型 | 数量     | 数据源 | 时间范围            |
|----------|--------|--------|-----------------|
| 沪市个股日行情 | 2308 只 | 新浪财经 (akshare) | 2026-01-01 ~ 至今 |
| 深市个股日行情 | 2895 只 | 新浪财经 (akshare) | 2026-01-01 ~ 至今 |
| 沪市公司信息 | 2308 家 (主板1699 + 科创板609) | 上交所 (akshare) | -               |
| 深市公司信息 | 2895 家 | 深交所 (akshare) | -               |
| 沪市财务报表 | 2308 只 | 新浪财经 (akshare) | 近三年             |
| 深市财务报表 | 2895 只 | 新浪财经 (akshare) | 近三年             |
| 行业板块日行情 | 90 板块  | 同花顺 (akshare) | 2026-01-01 ~ 至今 |
| 概念板块日行情 | 374 板块  | 同花顺 (akshare) | 2026-01-01 ~ 至今 |
| 行业板块成分股 | 90 板块  | 同花顺 (DrissionPage) | -               |
| 概念板块成分股 | 374 板块 | 同花顺 (DrissionPage) | -               |
| 财经新闻 | -      | 同花顺 7x24 | 2026-01-01 ~ 至今 |

### 3.2 MySQL 数据表结构

数据已导入阿里云 RDS MySQL，包含两个数据库：`market_data`（行情/财务）和 `stock_news`（新闻）。

#### market_data.company_info — 公司基本信息

```sql
CREATE TABLE company_info (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码(带后缀), 如600000.SH',
    symbol VARCHAR(10) NOT NULL COMMENT '股票代码(纯数字)',
    stock_name VARCHAR(50) COMMENT '股票简称',
    full_name VARCHAR(100) COMMENT '公司全称',
    industry VARCHAR(50) COMMENT '所属行业, 如J金融业',
    list_date VARCHAR(20) COMMENT '上市日期, 格式YYYY-MM-DD',
    market VARCHAR(5) COMMENT '市场, SH=沪市 SZ=深市',
    updated_at VARCHAR(30) COMMENT '数据更新时间',
    UNIQUE KEY uk_ts_code (ts_code)
)
```

#### market_data.stock_kline — 个股日K线行情

```sql
CREATE TABLE stock_kline (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码(带后缀), 如600000.SH',
    symbol VARCHAR(10) NOT NULL COMMENT '股票代码(纯数字)',
    trade_date VARCHAR(20) NOT NULL COMMENT '交易日期, 格式YYYY-MM-DD',
    open DOUBLE COMMENT '开盘价(元)',
    close DOUBLE COMMENT '收盘价(元)',
    high DOUBLE COMMENT '最高价(元)',
    low DOUBLE COMMENT '最低价(元)',
    pre_close DOUBLE COMMENT '前收盘价(元)',
    change_data DOUBLE COMMENT '涨跌额(元)',
    pct_chg DOUBLE COMMENT '涨跌幅(%)',
    volume DOUBLE COMMENT '成交量(股)',
    amount DOUBLE COMMENT '成交额(元)',
    pe DOUBLE COMMENT '市盈率',
    pb DOUBLE COMMENT '市净率',
    total_mv DOUBLE COMMENT '总市值(亿元)',
    total_share DOUBLE COMMENT '总股本(股)',
    float_share DOUBLE COMMENT '流通股本(股)',
    circ_mv DOUBLE COMMENT '流通市值(亿元)',
    ln_pctchg DOUBLE COMMENT '对数涨跌幅',
    pe_ttm DOUBLE COMMENT '滚动市盈率(TTM)',
    pe_static DOUBLE COMMENT '静态市盈率',
    pcf DOUBLE COMMENT '市现率',
    UNIQUE KEY uk_code_date (ts_code, trade_date),
    KEY idx_trade_date (trade_date),
    KEY idx_symbol (symbol)
)
```

#### market_data.stock_financial — 三大财务报表

```sql
CREATE TABLE stock_financial (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码(带后缀), 如600000.SH',
    symbol VARCHAR(10) NOT NULL COMMENT '股票代码(纯数字)',
    statement_type VARCHAR(20) NOT NULL COMMENT '报表类型: income=利润表, balance=资产负债表, cashflow=现金流量表',
    report_date VARCHAR(20) NOT NULL COMMENT '报告日, 如20260331',
    report_data JSON COMMENT '完整报表数据(JSON格式)',
    UNIQUE KEY uk_code_type_date (ts_code, statement_type, report_date),
    KEY idx_symbol (symbol),
    KEY idx_report_date (report_date),
    KEY idx_statement_type (statement_type)
)
```

> 不同行业财务字段差异大（银行 vs 制造业），因此采用 JSON 存储完整报表数据。

#### market_data.sector_industry_daily — 行业板块日K线

```sql
CREATE TABLE sector_industry_daily (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    sector_name VARCHAR(50) NOT NULL COMMENT '板块名称',
    sector_code VARCHAR(20) NOT NULL COMMENT '板块代码',
    trade_date VARCHAR(20) NOT NULL COMMENT '交易日期',
    open DOUBLE COMMENT '开盘点位',
    high DOUBLE COMMENT '最高点位',
    low DOUBLE COMMENT '最低点位',
    close DOUBLE COMMENT '收盘点位',
    vol DOUBLE COMMENT '成交量',
    amount DOUBLE COMMENT '成交额',
    pct_chg DOUBLE COMMENT '涨跌幅(%)',
    change_data DOUBLE COMMENT '涨跌点数',
    pct_change DOUBLE COMMENT '涨跌幅(备用)',
    turnover_rate DOUBLE COMMENT '换手率',
    UNIQUE KEY uk_code_date (sector_code, trade_date),
    KEY idx_trade_date (trade_date),
    KEY idx_sector_name (sector_name)
)
```

#### market_data.sector_concept_daily — 概念板块日K线

```sql
CREATE TABLE sector_concept_daily (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    sector_name VARCHAR(50) NOT NULL COMMENT '板块名称',
    sector_code VARCHAR(20) NOT NULL COMMENT '板块代码',
    trade_date VARCHAR(20) NOT NULL COMMENT '交易日期',
    open DOUBLE COMMENT '开盘点位',
    high DOUBLE COMMENT '最高点位',
    low DOUBLE COMMENT '最低点位',
    close DOUBLE COMMENT '收盘点位',
    vol DOUBLE COMMENT '成交量',
    amount DOUBLE COMMENT '成交额',
    pct_chg DOUBLE COMMENT '涨跌幅(%)',
    change_data DOUBLE COMMENT '涨跌点数',
    pct_change DOUBLE COMMENT '涨跌幅(备用)',
    turnover_rate DOUBLE COMMENT '换手率',
    UNIQUE KEY uk_code_date (sector_code, trade_date),
    KEY idx_trade_date (trade_date),
    KEY idx_sector_name (sector_name)
)
```

#### market_data.sector_industry_cons — 行业板块成分股

```sql
CREATE TABLE sector_industry_cons (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    sector_name VARCHAR(50) NOT NULL COMMENT '板块名称',
    sector_code VARCHAR(20) NOT NULL COMMENT '板块代码',
    stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(50) COMMENT '股票名称',
    UNIQUE KEY uk_sector_stock (sector_code, stock_code),
    KEY idx_sector_name (sector_name),
    KEY idx_stock_code (stock_code)
)
```

#### market_data.sector_concept_cons — 概念板块成分股

```sql
CREATE TABLE sector_concept_cons (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    sector_name VARCHAR(50) NOT NULL COMMENT '板块名称',
    sector_code VARCHAR(20) NOT NULL COMMENT '板块代码',
    stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(50) COMMENT '股票名称',
    UNIQUE KEY uk_sector_stock (sector_code, stock_code),
    KEY idx_sector_name (sector_name),
    KEY idx_stock_code (stock_code)
)
```

#### stock_news.news_em — 东财7x24快讯

```sql
CREATE TABLE news_em (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    title VARCHAR(500) NOT NULL COMMENT '新闻标题',
    digest TEXT COMMENT '新闻摘要',
    publish_time VARCHAR(30) COMMENT '发布时间',
    url VARCHAR(500) COMMENT '新闻链接',
    crawl_time VARCHAR(30) COMMENT '爬取时间',
    UNIQUE KEY uk_title_time (title, publish_time)
)
```

#### stock_news.news_ths — 同花顺财经新闻

```sql
CREATE TABLE news_ths (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    news_id VARCHAR(20) NOT NULL COMMENT '新闻ID',
    title VARCHAR(500) NOT NULL COMMENT '新闻标题',
    digest TEXT COMMENT '新闻摘要',
    url VARCHAR(500) COMMENT '新闻链接',
    tags VARCHAR(500) COMMENT '标签(逗号分隔)',
    ctime_str VARCHAR(30) COMMENT '发布时间',
    source VARCHAR(100) COMMENT '来源',
    crawl_time VARCHAR(30) COMMENT '爬取时间',
    UNIQUE KEY uk_news_id (news_id),
    KEY idx_ctime (ctime_str)
)
```

### 3.3 数据导入脚本

| 脚本 | 目标表 | 说明 |
|------|--------|------|
| `import_company_info_to_mysql.py` | `market_data.company_info` | 沪深公司基本信息 |
| `import_kline_to_mysql.py` | `market_data.stock_kline` | 个股日K线（56万+条） |
| `import_financial_to_mysql.py` | `market_data.stock_financial` | 三大财务报表（17万+条） |
| `import_sector_to_mysql.py` | `market_data.sector_industry_daily` / `sector_concept_daily` | 板块日K线 |
| `import_sector_cons_to_mysql.py` | `market_data.sector_industry_cons` / `sector_concept_cons` | 板块成分股 |
| `import_news_em_to_mysql.py` | `stock_news.news_em` | 东财快讯 |
| `import_news_ths_to_mysql.py` | `stock_news.news_ths` | 同花顺新闻 |
| `auto_news_em_to_mysql.py` | `stock_news.news_em` | 东财快讯定时爬取入库 |

### 3.4 数据采集脚本

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

### 3.5 已知问题

| 问题 | 说明 |
|------|------|
| 东方财富 API 封禁 | `push2his.eastmoney.com` 完全不可用 |
| 同花顺 IP 封禁 | 频繁爬取后 IP 被 Nginx 403 封禁 |
| 板块数据源不一致 | 行情来自 THS，成分股部分来自 Sina，板块名称可能不完全对应 |
| 沪市公司信息缺行业 | 上交所 API 不提供 industry 字段 |

---

## 四、AgentScope 2.0 智能体实现思路


### 4.1 整体架构

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

### 4.2 目录结构

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

### 4.3 实现步骤

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

### 5.4 已实现工具

#### tools/stock_fundamental.py — 基本面指标计算工具

从 MySQL `market_data.stock_financial` 表获取三大财务报表数据，计算基本面指标。

**核心函数**：

| 函数 | 说明 |
|------|------|
| `calc_fundamental_indicators(ts_code, report_date=None)` | 计算单期基本面指标 |
| `calc_fundamental_trend(ts_code, periods=4)` | 计算最近N期指标趋势 |
| `get_financial_data(ts_code, report_date=None)` | 获取三张报表原始数据 |
| `get_report_dates(ts_code, limit=8)` | 获取报告日列表 |

**计算指标**：

| 指标 | 公式 | 数据来源 |
|------|------|----------|
| ROE（净资产收益率） | 归母净利润 / 归母股东权益 × 100% | 利润表 + 资产负债表 |
| 毛利率 | (营业收入 - 营业成本) / 营业收入 × 100% | 利润表 |
| 净利率 | 净利润 / 营业收入 × 100% | 利润表 |
| 资产负债率 | 负债合计 / 资产总计 × 100% | 资产负债表 |
| 经营现金流净利润比 | 经营活动现金流净额 / 净利润 | 现金流量表 + 利润表 |
| 营收同比增长率 | (本期营收 - 上年同期营收) / \|上年同期\| × 100% | 利润表(两期累计) |
| 净利润同比增长率 | (本期净利 - 上年同期净利) / \|上年同期\| × 100% | 利润表(两期累计) |
| 营收环比增长率 | (本季单季营收 - 上季单季营收) / \|上季\| × 100% | 利润表(拆分单季) |
| 净利润环比增长率 | (本季单季净利 - 上季单季净利) / \|上季\| × 100% | 利润表(拆分单季) |

**特殊处理**：
- **银行股自动识别**：通过资产负债表特征字段（发放贷款及垫款净额、客户存款）判断
- **银行股字段映射**：营业收入 = 净利息收入 + 手续费及佣金净收入；营业成本 = 利息支出 + 手续费及佣金支出
- **同比计算**：直接用累计值对比上年同季报（2026Q1 vs 2025Q1）
- **环比计算**：先拆分单季数据再对比（Q4单季 = 年报累计 - 三季报累计）

**使用示例**：

```python
from tools.stock_fundamental import calc_fundamental_indicators, calc_fundamental_trend

# 计算单期指标
result = calc_fundamental_indicators('600519.SH')
print(result['ROE'], result['毛利率'], result['营收同比增长率'])

# 计算趋势（最近4期）
trend = calc_fundamental_trend('600519.SH', periods=4)
for t in trend['trend']:
    print(t['report_date'], t['ROE'], t['营收同比增长率'])
```

#### tools/stock_valuation.py — 估值分位分析工具

从 MySQL `market_data.stock_kline` 表获取 PE/PB/PCF 历史数据，计算当前估值在近一年历史中的百分位，判断高估/低估。

**核心函数**：

| 函数 | 说明 |
|------|------|
| `calc_valuation_percentile(ts_code, days=365)` | 计算估值百分位，返回结构化数据 |
| `calc_valuation_summary(ts_code, days=365)` | 生成格式化估值摘要文本 |
| `get_valuation_history(ts_code, days=365)` | 获取近N天估值历史数据 |
| `get_latest_valuation(ts_code)` | 获取最新一天估值数据 |

**估值指标**：

| 指标 | 说明 | 数据来源 |
|------|------|----------|
| PE_TTM | 滚动市盈率（Trailing Twelve Months） | stock_kline.pe_ttm |
| PB | 市净率（Price-to-Book） | stock_kline.pb |
| PCF | 市现率（Price-to-Cash-Flow） | stock_kline.pcf |

**百分位判断规则**：

| 百分位 | 估值水平 | 含义 |
|--------|----------|------|
| < 20% | 低估 | 处于历史低位，可能被低估 |
| 20% - 40% | 合理偏低 | 低于历史中位数 |
| 40% - 60% | 合理 | 处于历史中位区间 |
| 60% - 80% | 合理偏高 | 高于历史中位数 |
| > 80% | 高估 | 处于历史高位，可能被高估 |

**返回字段**：

```python
{
    'ts_code': '600519.SH',
    'trade_date': '2026-07-16',
    'history_days': 128,

    'pe_ttm': 19.03,           # 当前PE_TTM
    'pe_ttm_percentile': 21.88, # 百分位(%)
    'pe_ttm_level': '合理偏低', # 估值水平
    'pe_ttm_min': 17.66,       # 历史最低
    'pe_ttm_max': 22.19,       # 历史最高
    'pe_ttm_avg': 19.73,       # 历史均值

    'pb': 5.81,                # 当前PB
    'pb_percentile': 17.19,
    'pb_level': '低估',
    'pb_min': 5.39,
    'pb_max': 7.57,
    'pb_avg': 6.52,

    'pcf': 25.58,              # 当前PCF
    'pcf_percentile': 69.53,
    'pcf_level': '合理偏高',
    'pcf_min': 17.93,
    'pcf_max': 29.69,
    'pcf_avg': 22.66,
}
```

**使用示例**：

```python
from tools.stock_valuation import calc_valuation_percentile, calc_valuation_summary

# 获取结构化数据
result = calc_valuation_percentile('600519.SH')
print(f"PE_TTM: {result['pe_ttm']}，百分位: {result['pe_ttm_percentile']}%，{result['pe_ttm_level']}")

# 获取格式化摘要
print(calc_valuation_summary('600519.SH'))
```

**输出示例**：

```
=== 600519.SH 估值分析 (2026-07-16) ===
历史数据: 近128个交易日

【PE_TTM（滚动市盈率）】
  当前值: 19.03
  百分位: 21.88%
  估值水平: 合理偏低
  历史区间: 17.66 - 22.19（均值19.73）

【PB（市净率）】
  当前值: 5.81
  百分位: 17.19%
  估值水平: 低估
  历史区间: 5.39 - 7.57（均值6.52）

【PCF（市现率）】
  当前值: 25.58
  百分位: 69.53%
  估值水平: 合理偏高
  历史区间: 17.93 - 29.69（均值22.66）
```

---

#### tools/stock_technical.py — 技术指标计算工具

从 MySQL `market_data.stock_kline` 表获取 OHLCV 数据，计算 MA/MACD/RSI/BOLL/KDJ 技术指标。

**核心函数**：

| 函数 | 说明 |
|------|------|
| `calc_technical_indicators(ts_code, days=120)` | 计算全部技术指标 |
| `calc_technical_summary(ts_code, days=120)` | 生成格式化摘要 |
| `get_kline_data(ts_code, days=120)` | 从MySQL获取K线数据 |

**技术指标**：

| 指标 | 公式 | 选股用途 |
|------|------|----------|
| MA(5/10/20/60) | 最近N日收盘价的算术平均值 | 趋势判断：股价在MA之上为多头；金叉/死叉为买卖信号 |
| MACD | DIF=EMA(12)-EMA(26); DEA=DIF的9日EMA; 柱=(DIF-DEA)×2 | DIF上穿DEA为金叉（买入）；下穿为死叉（卖出） |
| RSI(6/12/24) | RS=N日平均涨幅/N日平均跌幅; RSI=100-100/(1+RS) | >80超买（可能回调）；<20超卖（可能反弹） |
| BOLL(20,2) | 中轨=MA(20); 上轨=MA+2σ; 下轨=MA-2σ | 触及上轨可能回调；触及下轨可能反弹 |
| KDJ(9,3,3) | RSV, K=2/3K+1/3RSV, D=2/3D+1/3K, J=3K-2D | K>80超买；K<20超卖；K/D交叉为买卖信号 |

**信号解读**：

| 信号 | MA | MACD | RSI | BOLL | KDJ |
|------|-----|------|-----|------|-----|
| 看多 | MA5>MA10>MA20（多头排列） | DIF>DEA, MACD柱>0 | RSI<20（超卖） | 股价触及下轨后反弹 | K/D金叉且在超卖区 |
| 看空 | MA5<MA10<MA20（空头排列） | DIF<DEA, MACD柱<0 | RSI>80（超买） | 股价触及上轨后回落 | K/D死叉且在超买区 |

**多指标综合研判**：

买入信号（至少满足2-3个）：
- ✓ 股价站上MA20，MA金叉（MA5>MA10>MA20）
- ✓ MACD金叉（DIF上穿DEA），且MACD柱转正
- ✓ RSI从超卖区回升（<20 → >20）
- ✓ 股价触及布林带下轨后反弹
- ✓ KDJ金叉（K上穿D），且在超卖区

卖出信号（至少满足2-3个）：
- ✗ 股价跌破MA20，MA死叉（MA5<MA10<MA20）
- ✗ MACD死叉（DIF下穿DEA），且MACD柱转负
- ✗ RSI进入超买区（>80）后回落
- ✗ 股价触及布林带上轨后回落
- ✗ KDJ死叉（K下穿D），且在超买区

**使用示例**：

```python
from tools.stock_technical import calc_technical_indicators, calc_technical_summary

# 获取结构化数据
result = calc_technical_indicators('600519.SH')
print(f"收盘价: {result['close']}, MA5: {result['ma5']}, MACD信号: {result['macd_signal']}")

# 获取格式化摘要
print(calc_technical_summary('600519.SH'))
```

### 5.5 工具函数与已有代码的对照

| 现有 langgraph_getdata/ | 新 tools/ | 说明 |
|---|---|---|
| `query_market_data_day_k.py` | `stock_query.py` | 个股K线查询 |
| `query_industry_index_market.py` | `sector_query.py` | 板块行情查询 |
| `query_industry_component_list.py` | `sector_query.py` | 板块成分股 |
| `query_concept_dc_day.py` | `sector_query.py` | 概念板块行情 |
| `query_concept_dc_stock.py` | `sector_query.py` | 概念板块成分股 |
| `query_fin_account.py` | `financial_query.py` | 财务报表查询 |
| （无） | `news_query.py` | 新闻查询（新增） |
| （无） | `stock_fundamental.py` | 基本面指标计算（已完成） |
| （无） | `stock_valuation.py` | 估值分位分析（已完成） |
| （无） | `stock_technical.py` | 技术指标计算（已完成） |

### 5.6 依赖安装

```bash
pip install agentscope>=2.0.3 fastapi uvicorn
```

---

