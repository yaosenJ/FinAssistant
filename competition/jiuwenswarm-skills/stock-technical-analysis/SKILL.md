---
name: stock-technical-analysis
version: 1.0.0
author: FinAssistant
description: |
  A股上市公司技术面分析技能。计算MA均线、MACD、RSI、布林带、KDJ等技术指标，
  识别趋势方向和买卖信号。输出技术面评分。
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
- **MACD**: DIF/DEA交叉，红绿柱变化
- **RSI**: 超买(>70)/超卖(<30)判断
- **布林带**: 股价相对位置
- **KDJ**: 金叉/死叉信号

### Step 3: 综合信号判断

| 信号 | 权重 | 看多条件 | 看空条件 |
|------|------|----------|----------|
| MA趋势 | 30% | 多头排列 | 空头排列 |
| MACD | 25% | 金叉/红柱放大 | 死叉/绿柱放大 |
| RSI | 20% | 超卖区回升 | 超买区回落 |
| KDJ | 15% | 金叉 | 死叉 |
| 布林带 | 10% | 触及下轨 | 触及上轨 |

## Output Schema

```markdown
## 技术面分析 - {公司名称}({代码})

**最新收盘价:** XX元

| 指标 | 数值 | 信号 |
|------|------|------|
| MA5/10/20/60 | XX/XX/XX/XX | 多头/空头/震荡 |
| MACD(DIF/DEA) | XX/XX | 金叉/死叉/观望 |
| RSI6/12/24 | XX/XX/XX | 超买/超卖/中性 |
| KDJ(K/D/J) | XX/XX/XX | 金叉/死叉/观望 |

**技术面评分: XX/100**

**趋势判断:** ...
**操作建议:** ...
```
