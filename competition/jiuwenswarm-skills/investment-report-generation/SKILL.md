---
name: investment-report-generation
version: 2.0.0
author: FinAssistant
description: |
  个股投资研报生成技能。基于49只股票的原始指标和排名数据，
  为每只股票生成结构化的 Markdown 投资研报（定性评级风格）。
  同时生成总结性投资报告（投资报告.md）。
tags: [finance, report, research, a-share]
allowed_tools: [executeCommand, readFile, writeFile]
---

# 投资研报生成技能

## When to Use
- "生成XX的投资研报"
- "为投资组合生成研究报告"
- 需要输出个股研报 .md 文件时

## Execution Steps

### Step 1: 生成全部 49 只个股研报

```bash
cd competition
python -c "
from report_generator import save_all_reports
import json
with open('output/score_results.json') as f:
    results = json.load(f)
save_all_reports(results, 'output/个股投资研报')
"
```

### Step 2: 生成投资报告

```bash
cd competition
python -c "
from report_generator import save_summary_report
import json
with open('output/Portfolio.json') as f:
    portfolio = json.load(f)
with open('output/score_results.json') as f:
    results = json.load(f)
save_summary_report(portfolio, results, '投资报告.md')
"
```

## Output Schema

### 个股研报（定性评级风格 + 图表）
采用优/良/中/差定性评级，含数据来源标注和图表。

```markdown
# {公司名称}({代码}) 投资研究报告

## 一、公司概况
| 项目 | 内容 |
|------|------|
| 股票代码 | {代码} |
| 股票名称 | {名称} |
| 所属板块 | {板块} |
| 综合评级 | **良** |

## 二、盈利能力分析
| 指标 | 数值 | 评级 | 说明 |
|------|------|------|------|
| 毛利率 | XX% | 优 | 越高越好 |
| ROE | XX% | 良 | 股东回报率 |

![盈利能力](./charts/{name}_profitability.png)

> 数据来源: market_data.stock_financial（财务报表明细数据）

## 七、动量与趋势分析
| 指标 | 数值 | 评级 |
|------|------|------|
| 近5日收益率 | +XX% | 偏强 |
| 量比(5/20) | XX | 温和放量 |

![动量趋势](./charts/{name}_momentum.png)

> 数据来源: market_data.stock_kline（近20个交易日收益率和成交量数据）

## 九、综合评估
综合评级: **良**

![多维评分](./charts/{name}_radar.png)
```

### 投资报告（总结性 + 图表）
自动生成 `投资报告.md`，含选股逻辑、仓位依据、组合明细、风险评估、板块分布饼图、仓位柱状图。

### 个股研报新增章节
- **行业对比**：与同板块均值比较（毛利率、ROE、估值）
- **盈利预测**：基于历史增长率外推（70%衰减系数），预测营收/净利润增速和远期PE
