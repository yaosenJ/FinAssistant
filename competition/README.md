# FinAssistant 金融分析 Agent — 华为 openJiuwen 比赛提交

## 一、项目概述

本项目基于 openJiuwen 社区的 **JiuwenSwarm** 框架，构建了一个多因子量化选股 Agent。采用 Single Skill 流水线 + Swarm Skill 团队协作的双层架构，对比赛指定的 49 只 A 股上市公司进行综合分析，输出投资组合配置和个股研究报告。

### 核心特点

- **深度集成 JiuwenSwarm**：修改 JiuwenSwarm 源码，新增 7 个自定义 Skill（6 个 Single Skill + 1 个 Swarm Skill）
- **多因子量化模型**：基本面(20%) + 估值(15%) + 技术面(30%) + 动量(25%) + 风险(10%)
- **完整工具链**：从数据获取、分析、打分、组合构建到研报生成全流程自动化
- **板块对比分析**：按6个板块（金融/消费/新能源/科技/周期/高端制造）进行行业对比

## 二、目录结构

```
competition/
├── stock_scorer.py               # 多因子打分模块（49只股票）
├── portfolio_builder.py          # 仓位配置生成器
├── report_generator.py           # 研报生成器（个股研报 + 总结投资报告）
├── chart_generator.py            # 图表生成模块
├── requirements.txt              # Python 依赖
├── environment.yaml              # Conda 环境配置
├── .env.example                  # 数据库配置模板
├── README.md                     # 本文件
├── 投资报告.md                    # 量化投资报告（Agent 自动生成）
│
├── output/                       # 输出目录
│   ├── Portfolio.json            # 投资组合结果
│   ├── score_results.json        # 49只股票评分数据
│   └── 个股投资研报/
│       ├── *.md                  # 个股研究报告（49只）
│       └── charts/*.png          # 图表文件
│
├── tools/                        # 工具模块
│   ├── stock_fundamental.py      # 基本面分析
│   ├── stock_valuation.py        # 估值分析
│   ├── stock_technical.py        # 技术面分析
│   └── financial_anomaly.py      # 异常检测
│
└── jiuwenswarm-skills/           # JiuwenSwarm Skill 定义
    ├── stock-fundamental-analysis/
    ├── stock-valuation-analysis/
    ├── stock-technical-analysis/
    ├── financial-anomaly-detection/
    ├── portfolio-construction/
    ├── investment-report-generation/
    └── financial-analysis-team/  # Swarm Skill（协调者统筹）
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

### 4.1 通过 JiuwenSwarm Agent 使用（比赛推荐方式）

本项目的核心是通过 JiuwenSwarm Agent 框架调用 Skills 完成金融分析。

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

#### CLI 对话示例

```bash
# 进入 JiuwenSwarm CLI
jiuwenswarm chat --mode code.normal

# 在对话中输入：
> 请使用 financial-analysis-team Skill，对比赛指定的49只A股进行多因子量化分析，
  生成投资组合 Portfolio.json 和每只股票的研究报告。
```

#### Agent 自主执行流程

Agent 会调用 `financial-analysis-team` Swarm Skill，按 workflow.md 中定义的步骤自主执行：

| 步骤 | 内容 | 说明 |
|------|------|------|
| Step 1 | 采集数据 | 运行 stock_scorer.py 采集49只股票多维度数据 |
| Step 2 | 计算排名 | 自动计算绝对排名（1-49，无并列） |
| Step 3 | Agent 决策 | Agent 自主分析数据，决策持仓股票和仓位权重 |
| Step 4 | 生成组合 | 写入 Portfolio.json（只保留股票代码和权重） |
| Step 5 | 生成研报 | 为全部49只股票生成详细研报 |
| Step 6 | 生成报告 | 生成总结性投资报告.md |

#### Agent 输出

Agent 执行完成后，输出文件位于 `competition/` 和 `competition/output/`：
- `投资报告.md` — 总结性投资报告（含选股逻辑、仓位依据、组合明细、风险评估、49只全量排名）
- `output/Portfolio.json` — 投资组合权重（纯 `{symbol: weight}` 格式）
- `output/个股投资研报/*.md` — 49只股票的详细研究报告（含图表解读、板块对比）
- `output/个股投资研报/charts/*.png` — 盈利能力、估值、动量、雷达图

### 4.2 手动分步执行（调试用）

```bash
cd D:\肖老师公开课笔记+代码\FinAssistant\competition

# Step 1: 采集数据 + 计算排名
python stock_scorer.py --output output/score_results.json

# Step 5: 生成个股研报
python -c "
from report_generator import save_all_reports
import json
with open('output/score_results.json') as f:
    results = json.load(f)
save_all_reports(results, 'output/个股投资研报')
"

# Step 6: 生成投资报告
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

> 注：Step 3（Agent决策持仓）和 Step 4（写入Portfolio.json）需要 Agent 自主完成。

### 4.3 输出文件说明

| 文件 | 格式 | 说明 |
|------|------|------|
| `output/Portfolio.json` | JSON | 投资组合，键为6位股票代码，值为仓位权重 |
| `投资报告.md` | Markdown | 总结性投资报告（含选股逻辑、仓位依据、组合明细、风险评估、49只全量排名） |
| `output/个股投资研报/*.md` | Markdown | 49只股票的详细研究报告（含图表解读、板块对比、盈利预测） |
| `output/个股投资研报/charts/*.png` | PNG | 盈利能力图、估值象限图、动量趋势图、雷达图 |

## 五、关键参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_weight` | 0.20 | 单只股票最大仓位（20%） |
| `cash_ratio` | 0.0 | 现金比例（0.0 = 满仓） |
| 评分权重 | 见下表 | 各维度在总分中的占比 |

### 评分权重

| 维度 | 权重 | 核心指标 |
|------|------|----------|
| 基本面 | 20% | ROE、毛利率/营业利润率、净利率、杜邦三因子、经营现金流/净利润、应收账款占比、资产负债率、营收/净利润同比环比增长率 |
| 估值 | 15% | PE_TTM/PB 历史分位数（近1年） |
| 技术面 | 30% | MA趋势、MACD信号、RSI超买超卖、KDJ交叉信号 |
| 动量 | 25% | 近5/10/20日收益率、量比（5日/20日均量）、20日波动率 |
| 风险 | 10% | 7类财务异常检测（现金流骤降、应收账款激增、商誉减值等） |

### 比赛指定的49只A股

| 板块 | 股票 |
|------|------|
| 金融板块 | 601318.SH 中国平安、600036.SH 招商银行、601688.SH 华泰证券、601398.SH 工商银行、601288.SH 农业银行、601988.SH 中国银行、600000.SH 浦发银行、601998.SH 中信银行 |
| 消费板块 | 600519.SH 贵州茅台、000858.SZ 五粮液、600887.SH 伊利股份、603288.SH 海天味业、600660.SH 福耀玻璃、000333.SZ 美的集团、000651.SZ 格力电器、601888.SH 中国中免、600809.SH 山西汾酒 |
| 新能源/电力板块 | 300750.SZ 宁德时代、002594.SZ 比亚迪、601012.SH 隆基绿能、300274.SZ 阳光电源、600900.SH 长江电力、600438.SH 通威股份、600089.SH 特变电工、600212.SH 绿能慧充 |
| 科技/AI/半导体板块 | 688981.SH 中芯国际、600584.SH 长电科技、600183.SH 生益科技、300308.SZ 中际旭创、300394.SZ 天孚通信、603501.SH 韦尔股份、600703.SH 三安光电、600570.SH 恒生电子、600845.SH 宝信软件、688041.SH 海光信息、603986.SH 兆易创新、002475.SZ 立讯精密 |
| 周期/资源板块 | 601899.SH 紫金矿业、600309.SH 万华化学、601600.SH 中国铝业、600028.SH 中国石化、601088.SH 中国神华、600547.SH 山东黄金、600426.SH 华鲁恒升、601168.SH 西部矿业 |
| 高端制造/基建板块 | 600031.SH 三一重工、601766.SH 中国中车、601668.SH 中国建筑、601186.SH 中国铁建 |

## 六、个股研报内容

每只股票的研报包含以下章节：

| 章节 | 内容 |
|------|------|
| 一、投资要点 | 综合评级、核心优势、主要风险 |
| 二、公司概况 | 基本信息 + 各维度排名对比（全局/板块） |
| 三、盈利能力分析 | 毛利率/净利率/ROE + 杜邦拆解 + 图表解读 |
| 四、盈利真实性与营运风险 | 经营现金流/应收账款/资产负债率 |
| 五、成长性分析 | 营收/净利润同比环比增长率 |
| 六、估值分析 | PE/PB 历史分位 + 图表解读 |
| 七、技术面分析 | MA/MACD/RSI/KDJ |
| 八、动量与趋势分析 | 近5/10/20日收益率/量比/波动率 + 图表解读 |
| 九、风险检测 | 7类财务异常检测 |
| 十、综合评估 | 雷达图 + 图表解读 |
| 十一、行业对比 | 财务指标/估值 vs 板块均值 |
| 十二、盈利预测 | 营收/净利润增速预测 |
| 附录 | 评级标准 |

## 七、可能遇到的问题

### Q1: 数据库连接失败
- 检查 `.env` 文件中的数据库配置是否正确
- 确认 MySQL 服务是否可访问（网络/防火墙）
- 确认 `market_data` 数据库及所需表是否存在

### Q2: 某只股票数据缺失
- 评分模块会自动处理：数据缺失的维度设为基准分 50
- 不影响整体流程运行

### Q3: JiuwenSwarm Skills 未生效
- 确认 Skills 已复制到 `D:\jiuwenswarm\jiuwenswarm\resources\agent\workspace\skills\`
- 确认 JiuwenSwarm 已正确安装（`pip install -e .`）

### Q4: Python 版本不兼容
- 要求 Python >= 3.9（推荐 3.10+）
- 检查：`python --version`

## 八、框架优化说明

本项目对 JiuwenSwarm 框架进行了以下扩展：

1. **新增 6 个 Single Skill**：将金融分析能力封装为独立 Skill，可被 Symphony 编排
2. **新增 1 个 Swarm Skill**：定义协调者统筹全流程（数据采集→排名计算→Agent决策→组合构建→研报生成）
3. **Skill 脚本集成**：每个 Skill 的 `scripts/` 目录包含可执行的 Python 分析脚本
4. **动量因子**：新增近5/10/20日收益率、量比、波动率等动量指标
5. **板块对比**：个股研报支持按6个板块进行行业对比分析
6. **图表解读**：自动生成盈利能力、估值、动量、雷达图的文字解读

详细修改说明见 `jiuwenswarm-skills/` 目录中的各 SKILL.md 文件。
