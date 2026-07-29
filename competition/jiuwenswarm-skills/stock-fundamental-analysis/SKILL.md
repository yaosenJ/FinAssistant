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

### Step 2: 计算评分
根据以下维度计算基本面评分（0-100）：

| 维度 | 权重 | 优秀标准 | 较差标准 |
|------|------|----------|----------|
| ROE | 35% | >15% | <5% |
| 毛利率 | 20% | >40% | <15% |
| 现金流质量 | 25% | 经营CF/净利润>1 | <0.5 |
| 成长性 | 20% | 营收增长>15% | <-5% |

### Step 3: 输出分析报告
输出包含：
- 核心指标表格
- 同比/环比增长率
- 基本面评分及等级（A/B/C/D）
- 关键优势与风险点

## Output Schema

```markdown
## 基本面分析 - {公司名称}({代码})

| 指标 | 数值 | 行业水平 | 评价 |
|------|------|----------|------|
| ROE | XX% | XX% | 优秀/一般/较差 |
| 毛利率 | XX% | XX% | ... |
| 净利率 | XX% | XX% | ... |
| 资产负债率 | XX% | XX% | ... |
| 经营现金流/净利润 | XX | XX | ... |

**基本面评分: XX/100 (等级: X)**

**成长性:**
- 营收同比增长: +XX%
- 净利润同比增长: +XX%

**关键优势:** ...
**主要风险:** ...
```
