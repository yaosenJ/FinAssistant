# 协作流程

## 流程图

```mermaid
graph TD
    A[协调者接收任务] --> B[Step1: 采集49只股票多维度数据]
    B --> C[Step2: 计算绝对排名(1-49)]
    C --> D[Agent 自主分析数据]
    D --> E[Step3: Agent 决策持仓与权重]
    E --> F[Step4: 生成 Portfolio.json]
    F --> G[Step5: 生成个股研报]
    G --> H[Step6: 生成投资报告.md]
    H --> I[输出全部结果]
```

> 比赛指定的 49 只 A 股详见 `SKILL.md`。

## 执行步骤

### Step 1: 采集全部股票数据

运行 `stock_scorer.py` 采集上述 49 只股票的多维度原始指标：

```bash
cd competition
python stock_scorer.py --output output/score_results.json
```

输出 `output/score_results.json`，包含每只股票的：
- 基本面指标（ROE、毛利率/营业利润率、净利率、杜邦三因子、经营现金流/净利润、应收账款占比、资产负债率、营收/净利润同比环比增长率）
- 估值数据（PE_TTM、PB 及其历史分位数）
- 技术面信号（MA趋势、MACD、RSI、KDJ）
- 动量因子（近5/10/20日收益率、量比、20日波动率）
- 异常检测结果

### Step 2: 计算绝对排名

`stock_scorer.py` 自动计算 49 只股票内各指标的绝对排名（1-49，1=最优），并按维度加权计算综合排名：

| 维度 | 权重 |
|------|------|
| 基本面 | 20% |
| 估值 | 15% |
| 技术面 | 30% |
| 动量 | 25% |
| 风险 | 10% |

### Step 3: Agent 自主决策

Agent 读取 `output/score_results.json`，综合分析以下信息，**自主决定**：

**a) 选几只股票？**
- Agent 自主决定入选数量，不固定为 8 只
- **允许空仓**（0只股票），但必须在投资报告中阐明空仓理由
- 给出选择该数量的理由

**b) 选哪些股票？**
- 综合排名靠前的优先，但 Agent 可根据多维度判断灵活选择
- 技术面趋势向上的加分（MA多头排列、MACD金叉）
- 动量强势的加分（近5/10/20日收益率为正、量比>1）
- 异常检测 HIGH/MEDIUM 风险的降权或排除
- 波动率过高的降权

**c) 每只多少仓位？**
- Agent 自主决定每只股票的仓位权重
- 给出每只股票的仓位理由
- 单只最大仓位不超过 20%（约束条件）
- 权重归一化确保总和 = 1.0

**d) 不选哪些股票？**
- 对未入选的股票给出排除理由（如排名靠后、估值偏高、财务异常等）

### Step 4: 构建投资组合

Agent 将决策结果写入 `output/Portfolio.json`，**只保留股票代码和权重**：

```json
{
  "600519": 0.18,
  "300750": 0.15,
  "002594": 0.12
}
```

选股理由、排除理由、仓位理由全部写入 `投资报告.md`（Step 6），不要放在 Portfolio.json 里。

### Step 5: 生成个股研报

为全部 49 只股票生成研报（不只是入选的）：

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

### Step 6: 生成投资报告

生成总结性投资报告，Agent 将选股理由、排除理由、仓位理由直接写入报告：

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

Agent 在生成报告时，应将以下内容直接写入 `投资报告.md`：
- 选股策略概述
- 每只入选股票的入选理由和仓位理由
- 未入选股票的排除理由

## 输出文件

| 文件 | 说明 |
|------|------|
| `output/score_results.json` | 49只股票的原始指标 + 绝对排名（1-49） |
| `output/Portfolio.json` | 投资组合（纯 `{symbol: weight}` 格式） |
| `投资报告.md` | 总结性投资报告（含选股理由、排除理由、仓位理由） |
| `output/个股投资研报/*.md` | 全部 49 只股票的详细研报（每只一份） |
