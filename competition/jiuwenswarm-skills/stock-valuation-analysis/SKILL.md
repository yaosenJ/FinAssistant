---
name: stock-valuation-analysis
version: 1.0.0
author: FinAssistant
description: |
  A股上市公司估值分析技能。计算PE_TTM、PB、PCF在近一年历史中的百分位，
  判断当前估值处于高估/合理/低估水平。输出估值评分。
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
- PCF 近1年百分位

### Step 3: 估值评级

| PE百分位 | 水平 | 建议 |
|---------|------|------|
| <20% | 极度低估 | 强烈关注 |
| 20%-40% | 低估 | 适度关注 |
| 40%-60% | 合理 | 持有观望 |
| 60%-80% | 偏高 | 谨慎 |
| >80% | 高估 | 回避 |

## Output Schema

```markdown
## 估值分析 - {公司名称}({代码})

| 指标 | 当前值 | 历史分位 | 估值水平 | 1年最低 | 1年最高 | 1年均值 |
|------|--------|----------|----------|---------|---------|---------|
| PE_TTM | XX | XX% | XX | XX | XX | XX |
| PB | XX | XX% | XX | XX | XX | XX |

**估值得分: XX/100**

**估值判断:** 当前估值处于历史XX%分位，属于XX水平。
**投资建议:** ...
```
