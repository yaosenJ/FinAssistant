# FinAssistant 金融分析 Agent — 华为 openJiuwen 比赛提交

## 一、项目概述

本项目基于 openJiuwen 社区的 **JiuwenSwarm** 框架，构建了一个多因子量化选股 Agent。采用 Single Skill 流水线 + Swarm Skill 团队协作的双层架构，对比赛指定的 49 只 A 股上市公司进行综合分析，输出投资组合配置和个股研究报告。

### 核心特点

- **深度集成 JiuwenSwarm**：修改 JiuwenSwarm 源码，新增 7 个自定义 Skill（6 个 Single Skill + 1 个 Swarm Skill）
- **多因子量化模型**：基本面(30%) + 估值(25%) + 技术面(20%) + 异常检测(10%) + 行业均衡(15%)
- **GLM-5.1 大模型驱动**：通过 JiuwenSwarm Agent 调用智谱 GLM-5.1，Token 消耗约 5.7 万
- **完整工具链**：从数据获取、分析、打分、组合构建到研报生成全流程自动化

## 二、目录结构

```
competition/
├── run_selection.py              # 主入口：选股+配比+研报
├── stock_scorer.py               # 多因子打分模块（49只股票）
├── portfolio_builder.py          # 仓位配置生成器
├── report_generator.py           # 研报生成器（个股研报 + 总结投资报告）
├── requirements.txt              # Python 依赖
├── environment.yaml              # Conda 环境配置
├── .env.example                  # 数据库配置模板
├── README.md                     # 本文件
├── 投资报告.md                    # 量化投资报告（由 run_selection.py 自动生成，与 output 同步）
│
├── output/                       # 输出目录
│   ├── Portfolio.json            # 投资组合结果
│   ├── resource_log.json         # 资源消耗日志
│   └── 个股投资研报/*.md          # 个股研究报告
│
└── jiuwenswarm-skills/           # JiuwenSwarm Skill 定义（已同步至源码）
    ├── stock-fundamental-analysis/
    ├── stock-valuation-analysis/
    ├── stock-technical-analysis/
    ├── financial-anomaly-detection/
    ├── portfolio-construction/
    ├── investment-report-generation/
    └── financial-analysis-team/  # Swarm Skill（5角色协作）
```

## 三、环境配置

### 3.1 系统要求

- Python >= 3.9
- MySQL 5.7+（已配置 market_data 数据库）
- 操作系统：Windows / Linux / macOS

### 3.2 安装依赖

```bash
# 方式一：pip 安装
cd competition
pip install -r requirements.txt

# 方式二：conda 安装
conda env create -f environment.yaml
conda activate finassistant
```

### 3.3 数据库配置

1. 复制配置模板：
```bash
cp .env.example .env
```

2. 编辑 `.env` 填入数据库连接信息：
```
DB_HOST=your_mysql_host
DB_USER=your_mysql_user
DB_PASSWORD=your_mysql_password
DB_NAME=market_data
```

3. 确保数据库中包含以下表：
- `stock_financial` — 财务报表数据（JSON 格式存储）
- `stock_kline` — K 线行情数据（含 PE_TTM、PB 等）
- `company_info` — 公司基本信息
- `sector_industry_daily` / `sector_industry_cons` — 行业板块数据

### 3.4 JiuwenSwarm 框架集成

本项目修改了 JiuwenSwarm 源码，新增了以下 Skills：

```bash
# Skills 已同步至 JiuwenSwarm 源码目录
D:\jiuwenswarm\jiuwenswarm\resources\agent\workspace\skills\
├── stock-fundamental-analysis/    # 基本面分析
├── stock-valuation-analysis/      # 估值分析
├── stock-technical-analysis/      # 技术面分析
├── financial-anomaly-detection/   # 异常检测
├── portfolio-construction/        # 组合构建
├── investment-report-generation/  # 研报生成
└── financial-analysis-team/       # Swarm Skill（团队协作）
```

源码修改详见 `jiuwenswarm-skills/` 目录及 `框架优化说明.md`。

## 四、执行步骤

### 4.1 一键运行（推荐）

```bash
cd D:\肖老师公开课笔记+代码\FinAssistant
python competition/run_selection.py
```

执行流程：
1. **多因子打分**（~60秒）：对 49 只股票进行基本面、估值、技术面、异常检测四维评分
2. **仓位配置**（<1秒）：按评分加权分配，单只最大 20%，输出 Portfolio.json
3. **投资报告**（<1秒）：根据实际评分和组合结果自动生成 `投资报告.md`（与 output 数据同步）
4. **个股研报**（~5秒）：为全部 49 只股票生成 Markdown 格式详细研究报告
5. **资源日志**（<1秒）：记录运行时长、CPU、内存及 LLM Token 消耗

### 4.2 通过 JiuwenSwarm Agent 使用（比赛推荐方式）

本项目的核心是通过 JiuwenSwarm Agent 框架调用 Skills 完成金融分析。以下是完整的 Agent 使用流程：

#### 前置条件

1. **安装 JiuwenSwarm**（如未安装）：
```bash
cd D:\jiuwenswarm
pip install -e .
```

2. **配置 LLM API**：编辑 `C:\Users\jys\.jiuwenswarm\config\.env`：
```env
API_BASE="https://open.bigmodel.cn/api/paas/v4"
API_KEY="your-zhipuai-api-key"
MODEL_NAME="glm-5.1"
MODEL_PROVIDER=OpenAI
```

3. **Skills 已就位**：7 个 Skill 目录已存在于 JiuwenSwarm 源码的 `resources/agent/workspace/skills/` 下。

#### 启动 Agent 服务

```bash
# 方式一：启动完整服务（Gateway + AgentServer + Web）
jiuwenswarm start

# 方式二：仅使用 CLI 聊天模式（无需启动 Web 服务）
jiuwenswarm chat --mode code.normal
```

启动后可通过 CLI 与 Agent 对话，Agent 会自动加载已注册的 Skills。

#### CLI 对话示例

```bash
# 进入 JiuwenSwarm CLI
jiuwenswarm chat --mode code.normal

# 在对话中输入：
> 请使用 financial-analysis-team Skill，对比赛指定的49只A股进行多因子量化分析，
  生成投资组合 Portfolio.json 和每只股票的研究报告。
```

Agent 会调用 `financial-analysis-team` Swarm Skill，按以下 5 角色协作流程执行：

| 角色 | 职责 |
|------|------|
| 协调者（Coordinator） | 分析任务分解、调度各角色 |
| 基本面分析师 | 调用 `stock-fundamental-analysis` Skill |
| 估值分析师 | 调用 `stock-valuation-analysis` Skill |
| 技术面分析师 | 调用 `stock-technical-analysis` Skill |
| 风险管理者 | 调用 `financial-anomaly-detection` Skill，汇总报告 |

最终由协调者调用 `portfolio-construction` 和 `investment-report-generation` Skill 生成最终输出。

#### Agent 输出

Agent 执行完成后，输出文件位于 `competition/` 和 `competition/output/`：
- `投资报告.md` — 总结性投资报告（自动生成，与 Portfolio.json 数据同步）
- `output/Portfolio.json` — 49 只股票的投资组合权重
- `output/个股投资研报/*.md` — 每只股票的详细研究报告
- `output/resource_log.json` — 资源消耗日志（含 LLM Token 消耗）

### 4.3 分步执行（纯 Python 脚本方式）

```python
# 1. 单独打分
from stock_scorer import score_all_stocks
results = score_all_stocks()

# 2. 单独构建组合
from portfolio_builder import build_portfolio
portfolio = build_portfolio(results, top_n=8, max_weight=0.20)

# 3. 单独生成研报
from report_generator import save_reports
save_reports(portfolio, results, "output/个股投资研报")
```

#### 传入 LLM Token 消耗

当通过 JiuwenSwarm Agent 调用 `run_selection.py` 时，可通过环境变量传入 LLM Token 消耗：

```bash
LLM_MODEL=glm-5.1 LLM_INPUT_TOKENS=56443 LLM_OUTPUT_TOKENS=746 \
LLM_TOTAL_TOKENS=57189 LLM_CACHE_TOKENS=53248 \
python competition/run_selection.py
```

| 环境变量 | 说明 |
|----------|------|
| `LLM_MODEL` | 模型名称，如 glm-5.1 |
| `LLM_INPUT_TOKENS` | 输入 Token 数 |
| `LLM_OUTPUT_TOKENS` | 输出 Token 数 |
| `LLM_TOTAL_TOKENS` | 总 Token 数 |
| `LLM_CACHE_TOKENS` | 缓存 Token 数（可选） |

未设置时默认为 0（纯 Python 脚本模式，不调用 LLM）。

### 4.4 输出文件说明

| 文件 | 格式 | 说明 |
|------|------|------|
| `output/Portfolio.json` | JSON | 投资组合，键为6位股票代码，值为仓位权重 |
| `投资报告.md` | Markdown | 总结性投资报告（自动生成，含选股逻辑、仓位依据、组合明细、风险评估） |
| `output/个股投资研报/*.md` | Markdown | 每只入选股票的详细研究报告 |
| `output/resource_log.json` | JSON | 资源消耗日志（运行时长、CPU、内存、LLM Token） |

> 注：4.3 分步执行方式仅调用 Python 脚本，不经过 JiuwenSwarm Agent，Token 消耗为 0。比赛推荐使用 4.2 的 Agent 方式。

## 五、关键参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `top_n` | 8 | 选取前 N 只股票构建组合 |
| `max_weight` | 0.20 | 单只股票最大仓位（20%） |
| `cash_ratio` | 0.0 | 现金比例（0.0 = 满仓） |
| 评分权重 | 见下表 | 各维度在总分中的占比 |

### 评分权重

| 维度 | 权重 | 数据来源 |
|------|------|----------|
| 基本面 | 30% | ROE、毛利率、净利率、现金流、成长性 |
| 估值 | 25% | PE_TTM/PB 历史分位数 |
| 技术面 | 20% | MA、MACD、RSI、KDJ |
| 异常检测 | 10% | 7类财务异常（默认80分，检测到扣分） |
| 行业均衡 | 15% | 限制同行业入选数量 |

## 六、可能遇到的问题

### Q1: 数据库连接失败
- 检查 `.env` 文件中的数据库配置是否正确
- 确认 MySQL 服务是否可访问（网络/防火墙）
- 确认 `market_data` 数据库及所需表是否存在

### Q2: 某只股票数据缺失
- 评分模块会自动处理：数据缺失的维度设为基准分 50，并在结果中标注 `data_insufficient`
- 不影响整体流程运行

### Q3: JiuwenSwarm Skills 未生效
- 确认 Skills 已复制到 `D:\jiuwenswarm\jiuwenswarm\resources\agent\workspace\skills\`
- 确认 JiuwenSwarm 已正确安装（`pip install -e .`）

### Q4: Python 版本不兼容
- 要求 Python >= 3.9（推荐 3.10+）
- 检查：`python --version`

## 七、框架优化说明

本项目对 JiuwenSwarm 框架进行了以下扩展：

1. **新增 6 个 Single Skill**：将金融分析能力封装为独立 Skill，可被 Symphony 编排
2. **新增 1 个 Swarm Skill**：定义 5 角色协作（协调者、基本面分析师、估值分析师、技术面分析师、风险管理者）
3. **Skill 脚本集成**：每个 Skill 的 `scripts/` 目录包含可执行的 Python 分析脚本

详细修改说明见 `jiuwenswarm-skills/` 目录中的各 SKILL.md 文件。
