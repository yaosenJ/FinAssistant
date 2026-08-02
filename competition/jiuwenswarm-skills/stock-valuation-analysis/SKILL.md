---
name: stock-valuation-analysis
version: 1.0.0
author: FinAssistant
description: |
  A股上市公司估值分析技能。计算PE_TTM、PB在近一年历史中的百分位，
  判断当前估值处于高估/合理/低估水平。估值维度在综合排名中占15%权重。
  当用户询问股票估值、是否便宜、高估低估时触发。
tags: [finance, valuation, pe, pb, a-share]
allowed_tools: [executeCommand, readFile, writeFile]
---

# 估值分析技能

## When to Use
- "XX当前估值处于什么水平"
- "XX现在贵不贵"
- "哪些股票估值较低"
- 需要判断买入时机时

## Execution Steps

### Step 1: 获取估值数据
运行估值分析脚本，获取当前估值和历史分位：

```bash
python scripts/valuation_analysis.py --ts_code {ts_code} --days 365
```

### Step 2: 计算估值百分位
- PE_TTM 近1年百分位
- PB 近1年百分位

百分位越低表示估值越便宜（低估），越高表示估值越贵（高估）。

### Step 3: 估值评级

| PE/PB百分位 | 评级 |
|------------|------|
| <20% | 低估 |
| 20%-50% | 合理 |
| 50%-80% | 偏高 |
| >80% | 高估 |

## Output Schema

```markdown
## 估值分析

| 指标 | 当前值 | 历史分位 | 估值评级 |
|------|--------|----------|----------|
| PE_TTM | XX | XX% | 合理 |
| PB | XX | XX% | 低估 |

> 数据来源: market_data.stock_kline（近1年K线数据计算历史分位数）
```
