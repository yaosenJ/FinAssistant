<p align="center">
  <img
    src="./logo.svg"
    alt="FinAssistant Logo"
    width="180"
  />
</p>

<h1 align="center">FinAssistant — AI-Powered Financial Analysis</h1>

<p align="center">
  <strong>RAG Retrieval & Agent System for China A-Share Market</strong>
</p>

<p align="center">
  <a href="#1-background">Background</a> •
  <a href="#2-feature-modules">Features</a> •
  <a href="#3-data-assets">Data Assets</a> •
  <a href="#4-agentscope-20-implementation">Implementation</a> •
  <a href="#54-implemented-tools">Tools</a>
</p>

<p align="center">
  <a href="./README_CN.md">中文</a> | <b>English</b>
</p>

---

## 1. Background

The China A-share market has diverse data dimensions and massive information volumes. Retail investors and small-to-medium institutions struggle to efficiently integrate stock quotes, sector rotation, financial statements, and market news for comprehensive analysis. This project aims to build a financial RAG retrieval and agent system based on collected A-share data assets, enabling users to perform professional financial analysis through natural language conversations.

### Core Objectives

- **Lower Analysis Barriers**: Replace manual data queries, indicator calculations, and report writing with natural language
- **Multi-dimensional Data Correlation**: Connect stocks, sectors, financials, and news for a panoramic view
- **Agent Collaboration**: Multiple specialized agents working together, covering the full workflow from data queries to research reports

### Tech Stack

| Layer | Technology |
|-------|------------|
| Agent Framework | AgentScope 2.0 (Multi-Agent Orchestration) |
| Data Storage | MySQL (Structured Query) + Milvus (Vector Retrieval) |
| Data Collection | Python + akshare + DrissionPage |
| LLM | Qwen / GPT / Claude |
| Embedding | text-embedding-v3 / BGE |
| Frontend | Streamlit / Gradio |

---

## 2. Feature Modules

Six intelligent agent modules planned based on existing data assets:

---

### 2.1 Stock Analysis Agent

**Data Support**: Daily stock quotes + Company info + Financial statements

**Core Features**:

| Feature | Description | Implementation |
|---------|-------------|----------------|
| Fundamental Score | Auto-score (0-100) based on ROE, gross margin, debt ratio, cash flow | Extract key fields from 3 statements, weighted calculation |
| Valuation Percentile | PE/PB/PCF percentile in 1-year history, determine over/undervalued | Calculate percentile on daily PE/PB series |
| Technical Indicators | MA(5/10/20/60), MACD, RSI, Bollinger Bands, KDJ | Real-time calculation based on OHLCV data |
| Trading Signals | Golden/Dead cross, MA breakout, RSI overbought/oversold | Technical indicator crossover detection |
| Stock Profile Report | Comprehensive fundamental + technical + valuation + sector report | LLM aggregates analysis results into text |

**Example Queries**:
```
"How is Pudong Bank's cash flow situation this quarter?"
"What is Ping An Bank's current valuation percentile?"
"Analyze Kweichow Moutai's technical trend and give trading advice"
"Generate a stock profile report for CATL"
```

**To-Do**:
- [x] `tools/stock_fundamental.py` — Fundamental indicator calculator (Done)
- [x] `tools/stock_valuation.py` — Valuation percentile analyzer (Done)
- [x] `tools/stock_technical.py` — Technical indicator calculator (Done)
- [x] `tools/stock_analysis.py` — Comprehensive stock analysis report (Done)
- [x] `agents/stock_agent.py` — Stock analysis agent (Done)

**Agent Demo**:

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

### 2.2 Sector Rotation Analysis Agent

**Data Support**: Industry/Concept sector daily quotes (90 industry + 374 concept) + Constituent stocks

**Core Features**:

| Feature | Description | Implementation |
|---------|-------------|----------------|
| Sector Ranking | Rank by pct_chg, volume change, capital flow | Aggregate sector daily_index |
| Rotation Trend | Sectors with consecutive top N-day gains marked as "hot" | Sliding window rank change analysis |
| Sector Comparison | Multi-sector price curves overlay | Extract multiple sector close series |
| Constituent Distribution | Advance/decline count, limit up/down, median change | Link constituent daily data |
| Capital Flow | Volume change trend, determine inflow/outflow | Volume QoQ change analysis |
| Sector Correlation | Constituent stock overlap between two sectors | Set intersection/union ratio |

**Example Queries**:
```
"Which industry sectors had the highest gains this week?"
"How has the semiconductor sector performed this month? Is capital flowing in or out?"
"How high is the overlap between AI and robotics concept constituents?"
"Which sectors had limit-down waves today?"
```

**To-Do**:
- [ ] `tools/sector_ranking.py` — Sector ranking tool
- [ ] `tools/sector_rotation.py` — Rotation trend identifier
- [ ] `tools/sector_compare.py` — Sector comparison tool
- [ ] `agents/sector_agent.py` — Sector analysis agent

---

### 2.3 Cross-Data Correlation Analysis Agent

**Data Support**: Quotes + Constituents + Financial statements + News (Full data cross-correlation)

**Core Features**:

| Feature | Description | Implementation |
|---------|-------------|----------------|
| Stock→Sector Mapping | Query which sectors a stock belongs to, recent performance | Reverse lookup in constituent data |
| Sector→Financial Aggregation | Average ROE, median PE, total revenue for sector constituents | Link constituent codes to financial statements |
| News→Quote Correlation | Companies/sectors mentioned in news, link to recent price trends | NER entity recognition + code matching |
| Industry Chain | Infer upstream/downstream relationships via concept overlap | Constituent set similarity clustering |
| Leader Effect | Top N stocks by market cap vs sector overall performance | Market-cap weighted vs equal-weight index |

**Example Queries**:
```
"Which concept sectors does BYD belong to? How are they performing?"
"What's the average PE and ROE for the semiconductor sector?"
"Any recent news about solar power? How are related sectors trending?"
"Find the top 5 stocks most correlated with CATL"
```

**To-Do**:
- [ ] `tools/stock_sector_mapping.py` — Stock-sector mapping tool
- [ ] `tools/sector_financial_agg.py` — Sector financial aggregation
- [ ] `tools/news_stock_linker.py` — News-quote correlation tool
- [ ] `agents/correlation_agent.py` — Correlation analysis agent

---

### 2.4 Financial Q&A Agent (RAG)

**Data Support**: Financial statements (4,593 stocks × multi-period) + Vector database (Milvus)

**Core Features**:

| Feature | Description | Implementation |
|---------|-------------|----------------|
| NL Financial Query | "Which companies have gross margin > 50%" → SQL/Vector search | Vectorize financial fields + structured query |
| Cross-stock Comparison | Horizontal comparison of financial indicators for same-industry companies | Group by industry + indicator comparison |
| Multi-period Trend | Vertical comparison of same company across periods | Time series analysis + trend detection |
| Anomaly Alert | Cash flow plunge, receivables surge, goodwill impairment | Threshold/QoQ change detection |
| Financial Health Score | Comprehensive solvency, profitability, growth, operational ability | DuPont analysis system + weighted scoring |

**Example Queries**:
```
"Which banks have positive operating cash flow for the past year?"
"Compare CATL and BYD's debt ratio trends"
"Which companies had gross margin drop > 10% last quarter?"
"Give me a DuPont analysis for Kweichow Moutai"
"Find companies with ROE > 20% for 3 consecutive years"
```

**To-Do**:
- [ ] `tools/financial_query.py` — Financial data query tool
- [ ] `tools/financial_compare.py` — Financial comparison tool
- [ ] `tools/financial_anomaly.py` — Anomaly detection tool
- [ ] `tools/financial_score.py` — Financial health scoring
- [ ] `agents/financial_agent.py` — Financial Q&A agent
- [ ] `rag/financial_embedding.py` — Financial statement vectorization

---

### 2.5 Daily Market Report Agent

**Data Support**: Full data (Quotes + Sectors + News + Financials)

**Core Features**:

| Feature | Description | Implementation |
|---------|-------------|----------------|
| Market Overview | Major index changes, volume, advance/decline stats | Aggregate all market stock data |
| Sector Rotation Summary | Top gainers/losers, capital inflow/outflow Top5 | Sector ranking tool output |
| Anomaly Detection | Limit up/down, volume breakout, abnormal volatility | Filter conditions |
| News Summary | Market-related important news, linked sectors | News filtering + LLM summary |
| Watchlist Report | User's watched stocks daily performance, announcements | Personalized filtering |
| Trend Assessment | Based on recent N-day data, market sentiment judgment | Multi-indicator synthesis |

**Example Queries**:
```
"Generate today's market morning briefing"
"Which stocks hit limit up today? Which sectors do they belong to?"
"How has market sentiment been this week?"
"How are my watchlist stocks performing today?"
```

**To-Do**:
- [ ] `tools/market_overview.py` — Market overview tool
- [ ] `tools/abnormal_detector.py` — Anomaly detection tool
- [ ] `tools/daily_digest.py` — Daily report generator
- [ ] `agents/daily_report_agent.py` — Daily report agent

---

### 2.6 Research Report Generation Agent

**Data Support**: Full data + LLM generation capabilities

**Core Features**:

| Feature | Description | Implementation |
|---------|-------------|----------------|
| Stock Deep Report | Comprehensive fundamental + technical + valuation + industry position | Call previous tools + LLM long-text generation |
| Industry Research | Sector trends, constituent financials, industry chain analysis | Sector tools + Financial tools + LLM |
| Comparative Report | 2-3 same-industry companies multi-dimensional comparison | Comparison tools + LLM |
| Event Impact Analysis | News/policy impact on related sectors and stocks | News correlation + Historical analogy + LLM |
| Portfolio Suggestion | Recommend sector/stock allocation based on risk preference | Optimization algorithm + LLM |

**Example Queries**:
```
"Write a deep research report on the semiconductor industry"
"Compare BYD, CATL, and LONGi Green Energy with a comparative analysis"
"Which A-share sectors are most affected by Fed rate hikes?"
"I prefer conservative investing, recommend some sector allocation plans"
```

**To-Do**:
- [ ] `tools/report_generator.py` — Report generation tool (LLM + templates)
- [ ] `templates/` — Report templates (stock/industry/comparison/event)
- [ ] `agents/report_agent.py` — Report generation agent
- [ ] `agents/portfolio_agent.py` — Portfolio optimization agent

---

## 3. Data Assets

### 3.1 Data Overview

| Data Type | Volume | Source | Time Range |
|-----------|--------|--------|------------|
| SH Stock Daily Quotes | 2,308 stocks | Sina Finance (akshare) | 2026-01-01 ~ Present |
| SZ Stock Daily Quotes | 2,895 stocks | Sina Finance (akshare) | 2026-01-01 ~ Present |
| SH Company Info | 2,308 (Main 1,699 + STAR 609) | SSE (akshare) | - |
| SZ Company Info | 2,895 | SZSE (akshare) | - |
| SH Financial Statements | 2,308 stocks | Sina Finance (akshare) | Recent 3 years |
| SZ Financial Statements | 2,895 stocks | Sina Finance (akshare) | Recent 3 years |
| Industry Sector Quotes | 90 sectors | Tonghuashun (akshare) | 2026-01-01 ~ Present |
| Concept Sector Quotes | 374 sectors | Tonghuashun (akshare) | 2026-01-01 ~ Present |
| Industry Constituents | 90 sectors | Tonghuashun (DrissionPage) | - |
| Concept Constituents | 374 sectors | Tonghuashun (DrissionPage) | - |
| Financial News | - | Tonghuashun 7x24 | 2026-01-01 ~ Present |

### 3.2 MySQL Table Schema

Data is stored in Alibaba Cloud RDS MySQL with two databases: `market_data` (quotes/financials) and `stock_news` (news).

#### market_data.company_info — Company Basic Info

```sql
CREATE TABLE company_info (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-increment ID',
    ts_code VARCHAR(20) NOT NULL COMMENT 'Stock code with suffix, e.g., 600000.SH',
    symbol VARCHAR(10) NOT NULL COMMENT 'Stock code (numeric only)',
    stock_name VARCHAR(50) COMMENT 'Stock short name',
    full_name VARCHAR(100) COMMENT 'Company full name',
    industry VARCHAR(50) COMMENT 'Industry, e.g., J Finance',
    list_date VARCHAR(20) COMMENT 'Listing date, format YYYY-MM-DD',
    market VARCHAR(5) COMMENT 'Market, SH=Shanghai SZ=Shenzhen',
    updated_at VARCHAR(30) COMMENT 'Data update time',
    UNIQUE KEY uk_ts_code (ts_code)
)
```

#### market_data.stock_kline — Stock Daily K-line

```sql
CREATE TABLE stock_kline (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-increment ID',
    ts_code VARCHAR(20) NOT NULL COMMENT 'Stock code with suffix',
    symbol VARCHAR(10) NOT NULL COMMENT 'Stock code (numeric only)',
    trade_date VARCHAR(20) NOT NULL COMMENT 'Trade date, format YYYY-MM-DD',
    open DOUBLE COMMENT 'Open price (CNY)',
    close DOUBLE COMMENT 'Close price (CNY)',
    high DOUBLE COMMENT 'High price (CNY)',
    low DOUBLE COMMENT 'Low price (CNY)',
    pre_close DOUBLE COMMENT 'Previous close (CNY)',
    change_data DOUBLE COMMENT 'Price change (CNY)',
    pct_chg DOUBLE COMMENT 'Change percentage (%)',
    volume DOUBLE COMMENT 'Volume (shares)',
    amount DOUBLE COMMENT 'Turnover (CNY)',
    pe DOUBLE COMMENT 'P/E ratio',
    pb DOUBLE COMMENT 'P/B ratio',
    total_mv DOUBLE COMMENT 'Total market cap (100M CNY)',
    total_share DOUBLE COMMENT 'Total shares',
    float_share DOUBLE COMMENT 'Float shares',
    circ_mv DOUBLE COMMENT 'Circulating market cap (100M CNY)',
    ln_pctchg DOUBLE COMMENT 'Log return',
    pe_ttm DOUBLE COMMENT 'P/E ratio (TTM)',
    pe_static DOUBLE COMMENT 'Static P/E ratio',
    pcf DOUBLE COMMENT 'Price-to-Cash-Flow ratio',
    UNIQUE KEY uk_code_date (ts_code, trade_date),
    KEY idx_trade_date (trade_date),
    KEY idx_symbol (symbol)
)
```

#### market_data.stock_financial — Financial Statements

```sql
CREATE TABLE stock_financial (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-increment ID',
    ts_code VARCHAR(20) NOT NULL COMMENT 'Stock code with suffix',
    symbol VARCHAR(10) NOT NULL COMMENT 'Stock code (numeric only)',
    statement_type VARCHAR(20) NOT NULL COMMENT 'Statement type: income/balance/cashflow',
    report_date VARCHAR(20) NOT NULL COMMENT 'Report date, e.g., 20260331',
    report_data JSON COMMENT 'Complete statement data (JSON)',
    UNIQUE KEY uk_code_type_date (ts_code, statement_type, report_date),
    KEY idx_symbol (symbol),
    KEY idx_report_date (report_date),
    KEY idx_statement_type (statement_type)
)
```

> Financial fields vary significantly across industries (banking vs manufacturing), hence JSON storage for complete statement data.

#### market_data.sector_industry_daily / sector_concept_daily — Sector Daily K-line

```sql
CREATE TABLE sector_industry_daily (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-increment ID',
    sector_name VARCHAR(50) NOT NULL COMMENT 'Sector name',
    sector_code VARCHAR(20) NOT NULL COMMENT 'Sector code',
    trade_date VARCHAR(20) NOT NULL COMMENT 'Trade date',
    open DOUBLE COMMENT 'Open',
    high DOUBLE COMMENT 'High',
    low DOUBLE COMMENT 'Low',
    close DOUBLE COMMENT 'Close',
    vol DOUBLE COMMENT 'Volume',
    amount DOUBLE COMMENT 'Turnover',
    pct_chg DOUBLE COMMENT 'Change (%)',
    change_data DOUBLE COMMENT 'Point change',
    pct_change DOUBLE COMMENT 'Change (backup)',
    turnover_rate DOUBLE COMMENT 'Turnover rate',
    UNIQUE KEY uk_code_date (sector_code, trade_date),
    KEY idx_trade_date (trade_date),
    KEY idx_sector_name (sector_name)
)
```

#### market_data.sector_industry_cons / sector_concept_cons — Sector Constituents

```sql
CREATE TABLE sector_industry_cons (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-increment ID',
    sector_name VARCHAR(50) NOT NULL COMMENT 'Sector name',
    sector_code VARCHAR(20) NOT NULL COMMENT 'Sector code',
    stock_code VARCHAR(10) NOT NULL COMMENT 'Stock code',
    stock_name VARCHAR(50) COMMENT 'Stock name',
    UNIQUE KEY uk_sector_stock (sector_code, stock_code),
    KEY idx_sector_name (sector_name),
    KEY idx_stock_code (stock_code)
)
```

#### stock_news.news_em — Eastmoney 7x24 News

```sql
CREATE TABLE news_em (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-increment ID',
    title VARCHAR(500) NOT NULL COMMENT 'News title',
    digest TEXT COMMENT 'News digest',
    publish_time VARCHAR(30) COMMENT 'Publish time',
    url VARCHAR(500) COMMENT 'News URL',
    crawl_time VARCHAR(30) COMMENT 'Crawl time',
    UNIQUE KEY uk_title_time (title, publish_time)
)
```

#### stock_news.news_ths — Tonghuashun Financial News

```sql
CREATE TABLE news_ths (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-increment ID',
    news_id VARCHAR(20) NOT NULL COMMENT 'News ID',
    title VARCHAR(500) NOT NULL COMMENT 'News title',
    digest TEXT COMMENT 'News digest',
    url VARCHAR(500) COMMENT 'News URL',
    tags VARCHAR(500) COMMENT 'Tags (comma separated)',
    ctime_str VARCHAR(30) COMMENT 'Publish time',
    source VARCHAR(100) COMMENT 'Source',
    crawl_time VARCHAR(30) COMMENT 'Crawl time',
    UNIQUE KEY uk_news_id (news_id),
    KEY idx_ctime (ctime_str)
)
```

### 3.3 Data Import Scripts

| Script | Target Table | Description |
|--------|--------------|-------------|
| `import_company_info_to_mysql.py` | `market_data.company_info` | SH/SZ company info |
| `import_kline_to_mysql.py` | `market_data.stock_kline` | Stock daily K-line (560K+ rows) |
| `import_financial_to_mysql.py` | `market_data.stock_financial` | Financial statements (170K+ rows) |
| `import_sector_to_mysql.py` | `market_data.sector_*_daily` | Sector daily K-line |
| `import_sector_cons_to_mysql.py` | `market_data.sector_*_cons` | Sector constituents |
| `import_news_em_to_mysql.py` | `stock_news.news_em` | Eastmoney news |
| `import_news_ths_to_mysql.py` | `stock_news.news_ths` | Tonghuashun news |

### 3.4 Data Collection Scripts

| Script | Purpose | Source |
|--------|---------|--------|
| `crawl_sh_stock_data.py` | SH stock quotes + company info | Sina Finance / SSE |
| `crawl_sz_stock_data.py` | SZ stock quotes + company info | Sina Finance / SZSE |
| `crawl_financial_reports.py` | Financial statements | Sina Finance |
| `crawl_sector_data.py` | Sector daily quotes (Industry + Concept) | Tonghuashun (akshare) |
| `crawl_sector_cons.py` | Sector constituents | Sina Finance (akshare) |
| `crawl_sector_cons_ths.py` | Sector constituents (backup) | Tonghuashun (DrissionPage) |
| `crawl_news_ths.py` | Financial news | Tonghuashun 7x24 API |
| `crawl_news_em.py` | Eastmoney 7x24 news (scheduled) | Eastmoney (akshare) |

### 3.5 Known Issues

| Issue | Description |
|-------|-------------|
| Eastmoney API Blocked | `push2his.eastmoney.com` completely unavailable |
| Tonghuashun IP Blocked | Frequent crawling triggers Nginx 403 block |
| Inconsistent Sector Sources | Quotes from THS, constituents partially from Sina, names may not match |
| SH Company Missing Industry | SSE API doesn't provide industry field |

---

## 4. AgentScope 2.0 Implementation

### 4.1 Architecture

```
User Query → FastAPI → Agent (system_prompt + model + toolkit + middlewares)
                              ↓
                         Toolkit
                           ├── ToolGroup("Stock Analysis")   → tools/stock_query.py + skills/stock-analysis/
                           ├── ToolGroup("Sector Analysis")   → tools/sector_query.py + skills/sector-rotation/
                           ├── ToolGroup("Financial Q&A")     → tools/financial_query.py + skills/financial-qa/
                           ├── ToolGroup("Daily Report")      → tools/news_query.py + skills/daily-report/
                           └── ToolGroup("Research Report")   → tools/indicators.py + skills/research-report/
```

### 4.2 Directory Structure

```
FinAssistant/
├── config.py                    # Global config (paths, model, API Key)
├── main.py                      # FastAPI service entry
├── main_agent.py                # Single agent script (no server, direct chat)
├── core/
│   ├── agent_setup.py           # Agent + Toolkit initialization
│   └── middleware.py            # Financial scenario middleware
├── tools/                       # Tool functions
│   ├── __init__.py
│   ├── stock_query.py           # Stock quote/company info query
│   ├── sector_query.py          # Sector quote/constituent query
│   ├── financial_query.py       # Financial statement query & analysis
│   ├── news_query.py            # News query
│   └── indicators.py            # Technical/fundamental indicator calculation
├── skills/                      # Skill documents (SKILL.md)
│   ├── stock-analysis/SKILL.md
│   ├── sector-rotation/SKILL.md
│   ├── financial-qa/SKILL.md
│   ├── daily-report/SKILL.md
│   └── research-report/SKILL.md
├── data/                        # Existing data (don't modify)
└── data_to_mysql_and_milvus/    # Existing crawler scripts (don't modify)
```

### 4.3 Implementation Steps

#### Step 1: config.py

Global configuration for data paths, model config, API keys.

#### Step 2: tools/ Tool Functions

Each function is `async def`, returns `ToolChunk`. **Docstring is the tool description** — LLM decides when to call based on docstring.

#### Step 3: skills/SKILL.md Skill Documents

Each skill directory has a SKILL.md with trigger conditions, dependent tools, and execution flow.

#### Step 4: core/middleware.py Middleware

| Middleware | Purpose |
|------------|---------|
| `InputValidationMiddleware` | Filter non-financial queries |
| `ToolCallAuditMiddleware` | Log tool calls to traces/ |
| `PerformanceMonitorMiddleware` | Monitor inference rounds, latency, tokens |
| `ContextEnrichmentMiddleware` | Inject current date, trading day context |

#### Step 5: core/agent_setup.py Agent Initialization

Assemble model, tools, toolkit, and agent with middleware.

#### Step 6: main.py Service Entry

FastAPI service with OpenAI-compatible `/v1/chat/completions` endpoint.

---

## 5. Implemented Tools

### tools/stock_fundamental.py — Fundamental Indicator Calculator

Calculates fundamental indicators from MySQL `market_data.stock_financial` table.

**Core Functions**:

| Function | Description |
|----------|-------------|
| `calc_fundamental_indicators(ts_code, report_date=None)` | Calculate single-period indicators |
| `calc_fundamental_trend(ts_code, periods=4)` | Calculate recent N-period trend |
| `get_financial_data(ts_code, report_date=None)` | Get raw statement data |
| `get_report_dates(ts_code, limit=8)` | Get report date list |

**Calculated Indicators**:

| Indicator | Formula | Data Source |
|-----------|---------|-------------|
| ROE | Net Profit / Equity × 100% | Income + Balance Sheet |
| Gross Margin | (Revenue - COGS) / Revenue × 100% | Income Statement |
| Net Margin | Net Profit / Revenue × 100% | Income Statement |
| Debt Ratio | Total Liabilities / Total Assets × 100% | Balance Sheet |
| Cash Flow / Net Profit | Operating Cash Flow / Net Profit | Cash Flow + Income |
| Revenue YoY Growth | (Current - Prior Year) / |Prior Year| × 100% | Income (2 periods) |
| Net Profit YoY Growth | (Current - Prior Year) / |Prior Year| × 100% | Income (2 periods) |
| Revenue QoQ Growth | (Current Q - Prior Q) / |Prior Q| × 100% | Income (single quarter) |
| Net Profit QoQ Growth | (Current Q - Prior Q) / |Prior Q| × 100% | Income (single quarter) |

**Special Handling**:
- **Auto bank detection**: Via balance sheet fields (loans, deposits)
- **Bank field mapping**: Revenue = Net Interest Income + Fee Income; COGS = Interest Expense + Fee Expense
- **YoY calculation**: Cumulative values vs same quarter last year (2026Q1 vs 2025Q1)
- **QoQ calculation**: Single-quarter values (Q4 = Annual - 9-month cumulative)

**Usage**:

```python
from tools.stock_fundamental import calc_fundamental_indicators, calc_fundamental_trend

# Single period
result = calc_fundamental_indicators('600519.SH')
print(result['ROE'], result['毛利率'], result['营收同比增长率'])

# Trend (recent 4 periods)
trend = calc_fundamental_trend('600519.SH', periods=4)
for t in trend['trend']:
    print(t['report_date'], t['ROE'], t['营收同比增长率'])
```

---

### tools/stock_valuation.py — Valuation Percentile Analyzer

Calculates PE/PB/PCF percentile in 1-year history from `market_data.stock_kline` table.

**Core Functions**:

| Function | Description |
|----------|-------------|
| `calc_valuation_percentile(ts_code, days=365)` | Calculate valuation percentile, return structured data |
| `calc_valuation_summary(ts_code, days=365)` | Generate formatted valuation summary |
| `get_valuation_history(ts_code, days=365)` | Get N-day valuation history |
| `get_latest_valuation(ts_code)` | Get latest day valuation data |

**Valuation Indicators**:

| Indicator | Description | Source |
|-----------|-------------|--------|
| PE_TTM | Price-to-Earnings (Trailing Twelve Months) | stock_kline.pe_ttm |
| PB | Price-to-Book | stock_kline.pb |
| PCF | Price-to-Cash-Flow | stock_kline.pcf |

**Percentile Rules**:

| Percentile | Level | Meaning |
|------------|-------|---------|
| < 20% | Undervalued | At historical low, potentially undervalued |
| 20% - 40% | Below Average | Below historical median |
| 40% - 60% | Fair | At historical median range |
| 60% - 80% | Above Average | Above historical median |
| > 80% | Overvalued | At historical high, potentially overvalued |

**Usage**:

```python
from tools.stock_valuation import calc_valuation_percentile, calc_valuation_summary

# Get structured data
result = calc_valuation_percentile('600519.SH')
print(f"PE_TTM: {result['pe_ttm']}, Percentile: {result['pe_ttm_percentile']}%, {result['pe_ttm_level']}")

# Get formatted summary
print(calc_valuation_summary('600519.SH'))
```

---

### tools/stock_technical.py — Technical Indicator Calculator

Calculates MA/MACD/RSI/BOLL/KDJ indicators from MySQL `market_data.stock_kline` table.

**Core Functions**:

| Function | Description |
|----------|-------------|
| `calc_technical_indicators(ts_code, days=120)` | Calculate all technical indicators |
| `calc_technical_summary(ts_code, days=120)` | Generate formatted summary |
| `get_kline_data(ts_code, days=120)` | Get K-line data from MySQL |

**Technical Indicators**:

| Indicator | Formula | Usage |
|-----------|---------|-------|
| MA(5/10/20/60) | Average of last N closing prices | Trend: Price above MA = bullish; MA crossover = buy/sell signal |
| MACD | DIF = EMA(12) - EMA(26); DEA = EMA(DIF,9); Histogram = (DIF-DEA)×2 | Golden cross (DIF>DEA) = buy; Dead cross = sell |
| RSI(6/12/24) | RS = Avg Gain / Avg Loss; RSI = 100 - 100/(1+RS) | >80 = overbought; <20 = oversold |
| BOLL(20,2) | Upper = MA+2σ; Middle = MA; Lower = MA-2σ | Touch upper = overbought; Touch lower = oversold |
| KDJ(9,3,3) | RSV, K = 2/3K+1/3RSV, D = 2/3D+1/3K, J = 3K-2D | K>80 = overbought; K<20 = oversold; K/D crossover |

**Signal Interpretation**:

| Signal | MA | MACD | RSI | BOLL | KDJ |
|--------|-----|------|-----|------|-----|
| Bullish | MA5>MA10>MA20 (Bull alignment) | DIF>DEA, Histogram>0 | RSI<20 (Oversold) | Price bounces off lower band | K/D golden cross in oversold zone |
| Bearish | MA5<MA10<MA20 (Bear alignment) | DIF<DEA, Histogram<0 | RSI>80 (Overbought) | Price falls from upper band | K/D dead cross in overbought zone |

**Multi-indicator Confirmation**:

Buy signals (need 2-3):
- Price above MA20, MA bullish alignment (MA5>MA10>MA20)
- MACD golden cross (DIF crosses above DEA)
- RSI rebounds from oversold (<20 → >20)
- Price bounces off Bollinger lower band
- KDJ golden cross in oversold zone

Sell signals (need 2-3):
- Price below MA20, MA bearish alignment (MA5<MA10<MA20)
- MACD dead cross (DIF crosses below DEA)
- RSI enters overbought (>80) then falls
- Price falls from Bollinger upper band
- KDJ dead cross in overbought zone

**Usage**:

```python
from tools.stock_technical import calc_technical_indicators, calc_technical_summary

# Get structured data
result = calc_technical_indicators('600519.SH')
print(f"Close: {result['close']}, MA5: {result['ma5']}, MACD: {result['macd_signal']}")

# Get formatted summary
print(calc_technical_summary('600519.SH'))
```

### 5.5 Tool Function Mapping

| Existing langgraph_getdata/ | New tools/ | Description |
|---|---|---|
| `query_market_data_day_k.py` | `stock_query.py` | Stock K-line query |
| `query_industry_index_market.py` | `sector_query.py` | Sector quote query |
| `query_industry_component_list.py` | `sector_query.py` | Sector constituents |
| `query_concept_dc_day.py` | `sector_query.py` | Concept sector quotes |
| `query_concept_dc_stock.py` | `sector_query.py` | Concept sector constituents |
| `query_fin_account.py` | `financial_query.py` | Financial statement query |
| (None) | `news_query.py` | News query (New) |
| (None) | `stock_fundamental.py` | Fundamental indicators (Done) |
| (None) | `stock_valuation.py` | Valuation percentile (Done) |
| (None) | `stock_technical.py` | Technical indicators (Done) |

### 5.6 Dependencies

```bash
pip install agentscope1.0.19.dev0>=2.0.3 fastapi uvicorn
```
