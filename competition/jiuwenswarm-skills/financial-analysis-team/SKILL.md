---
name: financial-analysis-team
version: 2.0.0
author: FinAssistant
description: |
  A股上市公司多维度金融分析团队技能。由协调者统筹全流程：
  采集49只股票数据 → 计算绝对排名（1-49） → Agent自主决策持仓与权重 →
  生成Portfolio.json → 生成个股研报 → 生成投资报告。
  Agent 可根据数据和自身策略灵活决策，不受固定权重约束。
kind: team-skill
tags: [finance, team, multi-agent, a-share, portfolio]
roles:
  - id: coordinator
    purpose: 统筹全流程：数据采集、排名计算、Agent决策、组合构建、研报生成
    skills: [portfolio-construction, investment-report-generation]
    tools: [executeCommand, readFile, writeFile]
---

# 金融分析团队

## 团队概述

本技能由协调者统筹，完成从数据采集到研报生成的全流程。
Agent 拥有自主决策权，可根据多维度数据和自身策略灵活决定持仓和权重。

## 比赛指定的 49 只 A 股

| 板块 | 股票 |
|------|------|
| 金融板块 | 601318.SH 中国平安、600036.SH 招商银行、601688.SH 华泰证券、601398.SH 工商银行、601288.SH 农业银行、601988.SH 中国银行、600000.SH 浦发银行、601998.SH 中信银行 |
| 消费板块 | 600519.SH 贵州茅台、000858.SZ 五粮液、600887.SH 伊利股份、603288.SH 海天味业、600660.SH 福耀玻璃、000333.SZ 美的集团、000651.SZ 格力电器、601888.SH 中国中免、600809.SH 山西汾酒 |
| 新能源/电力板块 | 300750.SZ 宁德时代、002594.SZ 比亚迪、601012.SH 隆基绿能、300274.SZ 阳光电源、600900.SH 长江电力、600438.SH 通威股份、600089.SH 特变电工、600212.SH 绿能慧充 |
| 科技/AI/半导体板块 | 688981.SH 中芯国际、600584.SH 长电科技、600183.SH 生益科技、300308.SZ 中际旭创、300394.SZ 天孚通信、603501.SH 韦尔股份、600703.SH 三安光电、600570.SH 恒生电子、600845.SH 宝信软件、688041.SH 海光信息、603986.SH 兆易创新、002475.SZ 立讯精密 |
| 周期/资源板块 | 601899.SH 紫金矿业、600309.SH 万华化学、601600.SH 中国铝业、600028.SH 中国石化、601088.SH 中国神华、600547.SH 山东黄金、600426.SH 华鲁恒升、601168.SH 西部矿业 |
| 高端制造/基建板块 | 600031.SH 三一重工、601766.SH 中国中车、601668.SH 中国建筑、601186.SH 中国铁建 |

## 工作流程

详见 `workflow.md`。

核心步骤：
1. 进入 `competition` 目录，运行 `stock_scorer.py` 采集 49 只股票的多维度数据
2. 计算 49 只内的绝对排名（1-49，1=最优），按维度加权：基本面20%、估值15%、技术面30%、动量25%、风险10%
3. Agent 自主分析数据，决策持仓股票和仓位权重
4. 输出 Portfolio.json、个股研报、投资报告

## Agent 决策要点

- 不使用固定权重公式，Agent 可灵活调整
- **允许空仓**：若市场整体风险过高或无合适标的，Agent 可选择空仓，但必须在投资报告中阐明理由
- 综合考虑基本面（ROE、毛利率、净利率、杜邦三因子）、估值、技术面、**动量**、风险检测等多维度信息
- **动量优先**：20日收益期限内，动量因子权重最高（技术面30%+动量25%=55%）
- 关注盈利真实性：经营现金流/净利润比、应收账款占比
- 注意行业分布均衡，避免过度集中
- 关注异常检测中的 HIGH/MEDIUM 风险提示
- 关注波动率：波动率过高的股票应降权
- **新闻面辅助**：Agent 可按需查询近期新闻，作为事件驱动维度辅助决策（见下方「新闻查询」）

## 新闻查询

Agent 在分析过程中可按需调用新闻工具，获取事件驱动信息：

```python
# 查询单只股票近期新闻（返回摘要）
cd competition && python -c "
import sys; sys.path.insert(0, '..')
from tools.news_stock_linker import find_news_by_keyword
print(find_news_by_keyword('贵州茅台', limit=5))
"

# 查询新闻并关联行情走势（新闻前后3天涨跌）
cd competition && python -c "
import sys; sys.path.insert(0, '..')
from tools.news_stock_linker import search_news_with_market
print(search_news_with_market('半导体', limit=3))
"
```

**使用场景：**
- 入选候选名单确定后，查询候选股票近期新闻，辅助最终决策
- 发现利空新闻（监管处罚、业绩暴雷等）的标的可降权或排除
- 发现利好新闻（政策支持、重大订单等）的标的可适当加权
- 不需要对全部49只都查，按需查询感兴趣的标的即可
