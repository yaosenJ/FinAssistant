---
name: portfolio-construction
version: 2.0.0
author: FinAssistant
description: |
  投资组合构建技能。基于49只股票的多维度绝对排名数据（1-49），
  由Agent自主决策持仓股票和仓位权重，输出 Portfolio.json。
  综合排名权重：基本面20%、估值15%、技术面30%、动量25%、风险10%。
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

### Step 1: 读取评分数据
```bash
cd competition
python portfolio_builder.py --input output/score_results.json --output output/Portfolio.json --top_n 8 --max_weight 0.20
```

### Step 2: Agent 决策要点

Agent 在构建组合时应综合考虑：

- **综合排名**：排名越小（越靠前）越优先入选
- **基本面（权重20%）**：ROE、毛利率、净利率、杜邦三因子的排名
- **估值（权重15%）**：PE/PB 历史分位数排名（低估优先）
- **技术面（权重30%）**：MA趋势、MACD信号、RSI、KDJ排名
- **动量（权重25%）**：近5/10/20日收益率排名、量比、波动率排名
- **风险（权重10%）**：异常检测中的 HIGH/MEDIUM 风险提示
- **行业均衡**：避免单一行业过度集中
- **新闻面**：按需查询近期新闻，利空标的降权/排除，利好标的适当加权

### Step 2.1: 新闻辅助查询（可选）

Agent 可在确定候选名单后，对感兴趣的标的查询近期新闻：

```python
cd competition && python -c "
import sys; sys.path.insert(0, '..')
from tools.news_stock_linker import find_news_by_keyword
print(find_news_by_keyword('招商银行', limit=5))
"
```

### Step 3: 仓位配置规则
- Agent 自主决定选几只股票（不固定数量）
- **允许空仓**（Portfolio.json 为空 `{}`），但必须在投资报告中阐明空仓理由
- Agent 自主决定每只股票的仓位权重
- 单只最大仓位不超过 20%（约束条件）
- 权重归一化确保总和 = 1.0
- **必须给出每只股票的入选理由和仓位理由**
- **必须给出未入选股票的排除理由**

### Step 4: 输出 Portfolio.json

**只保留股票代码和权重，不要 reasoning：**

```json
{
  "600519": 0.18,
  "300750": 0.15,
  "002594": 0.12
}
```

选股理由、排除理由、仓位理由写入 `投资报告.md`，不要放在 Portfolio.json 里。

## Output Schema

```markdown
## 投资组合配置

| 排名 | 代码 | 名称 | 综合排名 | 仓位 |
|------|------|------|----------|------|
| 1 | 600519 | 贵州茅台 | 3 | 18.0% |
| 2 | 300750 | 宁德时代 | 5 | 15.0% |
| ... | ... | ... | ... | ... |

**总仓位:** 100.0%
**股票数量:** X只

已保存: Portfolio.json
```
