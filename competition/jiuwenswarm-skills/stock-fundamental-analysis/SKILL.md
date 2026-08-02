---
name: stock-fundamental-analysis
version: 1.0.0
author: FinAssistant
description: |
  A股上市公司基本面分析技能。计算ROE、毛利率、净利率、资产负债率、现金流质量等核心指标，
  并计算同比/环比增长率。输出结构化基本面评分。
  当用户询问公司盈利能力、财务健康度、成长性时触发。
tags: [finance, fundamental, a-share, china]
allowed_tools: [executeCommand, readFile, writeFile]
---

# 基本面分析技能

## When to Use
- "分析XX公司的基本面"
- "XX的ROE和毛利率怎么样"
- "哪些公司盈利能力最强"
- 需要评估公司财务健康度时

## Execution Steps

### Step 1: 获取财务数据
运行基本面分析脚本，获取三大报表数据并计算核心指标：

```bash
python scripts/fundamental_analysis.py --ts_code {ts_code}
```

### Step 2: 计算绝对排名
计算49只股票内各基本面指标的绝对排名（1=最优，49=最差）：

| 指标 | 排名规则 |
|------|----------|
| ROE、毛利率、净利率 | 值越大排名越靠前 |
| 经营现金流/净利润 | 值越大排名越靠前 |
| 应收账款占比 | 值越小排名越靠前 |
| 营收/净利润同比增长率 | 值越大排名越靠前 |
| 杜邦三因子（净利率/周转率/权益乘数） | 值越大排名越靠前 |

基本面维度在综合排名中占20%权重。

### Step 3: 输出分析报告
输出包含：
- 核心指标表格（数值 + 定性评级：优/良/中/差）
- 盈利能力柱状图
- 数据来源标注

## Output Schema

```markdown
## 盈利能力分析

| 指标 | 数值 | 评级 | 说明 |
|------|------|------|------|
| 毛利率 | XX% | 优 | 越高越好 |
| 净利率 | XX% | 良 | 综合盈利能力 |
| ROE | XX% | 优 | 股东回报率 |

> 数据来源: market_data.stock_financial
```
