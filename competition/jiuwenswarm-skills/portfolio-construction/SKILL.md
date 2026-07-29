---
name: portfolio-construction
version: 1.0.0
author: FinAssistant
description: |
  投资组合构建技能。基于多因子评分结果，筛选Top N股票并按评分加权配置仓位。
  支持设置单只最大仓位、现金比例等约束条件。输出 Portfolio.json。
  当用户需要构建投资组合、配置仓位时触发。
tags: [finance, portfolio, allocation, a-share]
allowed_tools: [executeCommand, readFile, writeFile]
---

# 投资组合构建技能

## When to Use
- "帮我构建投资组合"
- "如何配置仓位"
- "哪些股票值得买入"
- 需要输出 Portfolio.json 时

## Execution Steps

### Step 1: 获取评分数据
读取多因子评分结果：
```bash
python scripts/portfolio_builder.py --input scores.json --top_n 8 --max_weight 0.20
```

### Step 2: 选股规则
- 综合评分 Top N（默认8只）
- 排除异常检测高风险股票
- 排除评分为0的股票

### Step 3: 仓位配置规则
- 按评分加权分配（评分越高权重越大）
- 单只最大仓位不超过20%
- 支持现金比例设置（满仓/半仓/空仓）
- 权重归一化确保总和=1.0

### Step 4: 输出 Portfolio.json
```json
{
  "600519": 0.18,
  "300750": 0.15,
  "002594": 0.12
}
```

## Output Schema

```markdown
## 投资组合配置

| 排名 | 代码 | 名称 | 综合评分 | 仓位 |
|------|------|------|----------|------|
| 1 | 600519 | 贵州茅台 | 85.2 | 18.0% |
| 2 | 300750 | 宁德时代 | 82.1 | 15.0% |
| ... | ... | ... | ... | ... |

**总仓位:** 100.0%
**股票数量:** X只
**现金比例:** 0.0%

已保存: Portfolio.json
```
