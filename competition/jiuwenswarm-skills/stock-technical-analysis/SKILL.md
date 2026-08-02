---
name: stock-technical-analysis
version: 1.0.0
author: FinAssistant
description: |
  A股上市公司技术面分析技能。计算MA均线、MACD、RSI、KDJ等技术指标，
  以及动量因子（收益率、量比、波动率）。技术面占综合排名30%权重，动量占25%。
  当用户询问股票走势、技术指标、买卖信号时触发。
tags: [finance, technical, macd, rsi, a-share]
allowed_tools: [executeCommand, readFile, writeFile]
---

# 技术面分析技能

## When to Use
- "XX的技术面走势如何"
- "XX有没有买入信号"
- "MACD和RSI指标怎么样"
- 需要判断短期走势时

## Execution Steps

### Step 1: 获取K线数据并计算指标
```bash
python scripts/technical_analysis.py --ts_code {ts_code} --days 120
```

### Step 2: 分析技术指标
- **MA均线**: 5/10/20/60日均线，判断多头/空头排列
- **MACD**: DIF/DEA交叉，金叉/死叉信号
- **RSI**: 超买(>80)/超卖(<20)判断
- **KDJ**: 金叉/死叉/超买/超卖信号

### Step 3: 动量因子
- **近5/10/20日收益率**: 短中长期动量
- **量比**: 5日均量/20日均量，>1表示放量
- **20日波动率**: 日收益率标准差年化，越低越稳定

### Step 4: 综合信号判断

| 信号 | 评级 |
|------|------|
| MA趋势 | 偏多/中性/偏空 |
| MACD信号 | 偏多/中性/偏空 |
| 近5日收益率 | 强势/偏强/偏弱/弱势 |
| 量比 | 放量/温和放量/温和缩量/缩量 |

## Output Schema

```markdown
## 技术面分析

| 指标 | 数值 | 评级 |
|------|------|------|
| MA趋势 | 多头排列 | 偏多 |
| MACD信号 | 金叉 | 偏多 |

## 动量与趋势分析

| 指标 | 数值 | 评级 |
|------|------|------|
| 近5日收益率 | +XX% | 偏强 |
| 量比(5/20) | XX | 温和放量 |

> 数据来源: market_data.stock_kline（近120个交易日K线数据）
```
