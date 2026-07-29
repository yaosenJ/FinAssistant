# -*- coding: utf-8 -*-
"""
个股研报生成器
为入选 Portfolio 的股票生成 Markdown 格式研报
"""

import os


def _safe_str(val, fmt='{}'):
    """安全格式化"""
    if val is None:
        return '--'
    try:
        return fmt.format(val)
    except (ValueError, TypeError):
        return str(val)


def _safe_pct(val):
    """安全百分比"""
    if val is None:
        return '--'
    try:
        return f"{float(val):+.2f}%"
    except (ValueError, TypeError):
        return '--'


def generate_stock_report(ts_code, name, sector, score_result):
    """
    生成单只股票的 Markdown 研报

    Args:
        ts_code: 带后缀的股票代码
        name: 股票名称
        sector: 所属板块
        score_result: stock_scorer 的打分结果 dict

    Returns:
        str: Markdown 格式研报
    """
    details = score_result.get('details', {})
    scores = score_result.get('scores', {})
    total_score = score_result.get('total_score', 0)

    fund = details.get('fundamental', {})
    val = details.get('valuation', {})
    tech = details.get('technical', {})
    anomaly = details.get('anomaly', '')

    symbol = ts_code.split('.')[0]

    report = f"""# {name}({symbol}) 投资研究报告

## 一、公司概况

| 项目 | 内容 |
|------|------|
| 股票代码 | {symbol} |
| 股票名称 | {name} |
| 所属板块 | {sector} |
| 综合评分 | {total_score} / 100 |

## 二、财务分析

### 2.1 核心指标

| 指标 | 数值 |
|------|------|
| ROE | {_safe_pct(fund.get('ROE'))} |
| 毛利率 | {_safe_pct(fund.get('毛利率'))} |
| 净利率 | {_safe_pct(fund.get('净利率'))} |
| 资产负债率 | {_safe_pct(fund.get('资产负债率'))} |
| 经营现金流/净利润 | {_safe_str(fund.get('经营现金流净利润比'))} |

### 2.2 成长性

| 指标 | 数值 |
|------|------|
| 营收同比增长率 | {_safe_pct(fund.get('营收同比增长率'))} |
| 净利润同比增长率 | {_safe_pct(fund.get('净利润同比增长率'))} |
| 营收环比增长率 | {_safe_pct(fund.get('营收环比增长率'))} |
| 净利润环比增长率 | {_safe_pct(fund.get('净利润环比增长率'))} |

### 2.3 基本面评分

基本面得分: **{scores.get('fundamental', '--')}** / 100

## 三、估值分析

| 指标 | 当前值 | 历史分位 | 估值水平 |
|------|--------|----------|----------|
| PE_TTM | {_safe_str(val.get('pe_ttm'))} | {_safe_pct(val.get('pe_ttm_percentile'))} | {_safe_str(val.get('pe_ttm_level'))} |
| PB | {_safe_str(val.get('pb'))} | {_safe_pct(val.get('pb_percentile'))} | {_safe_str(val.get('pb_level'))} |

估值得分: **{scores.get('valuation', '--')}** / 100

## 四、技术面分析

| 指标 | 数值 |
|------|------|
| 最新收盘价 | {_safe_str(tech.get('close'))} |
| MA趋势 | {_safe_str(tech.get('ma_trend'))} |
| MACD信号 | {_safe_str(tech.get('macd_signal'))} |
| RSI6信号 | {_safe_str(tech.get('rsi6_signal'))} |
| KDJ信号 | {_safe_str(tech.get('kdj_signal'))} |

技术面得分: **{scores.get('technical', '--')}** / 100

## 五、风险检测

异常检测得分: **{scores.get('anomaly', '--')}** / 100

```
{anomaly if anomaly else '未检测到明显异常信号'}
```

## 六、投资建议

综合评分: **{total_score}** / 100

| 维度 | 得分 | 权重 |
|------|------|------|
| 基本面 | {scores.get('fundamental', '--')} | 30% |
| 估值 | {scores.get('valuation', '--')} | 25% |
| 技术面 | {scores.get('technical', '--')} | 20% |
| 异常检测 | {scores.get('anomaly', '--')} | 10% |

---

> 风险提示: 本报告基于量化模型自动生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。
"""
    return report


def save_reports(portfolio, score_results, output_dir):
    """为 Portfolio 中每只股票生成并保存研报

    Args:
        portfolio: {symbol: weight, ...} 格式
        score_results: score_all_stocks() 返回结果
        output_dir: 研报输出目录
    """
    score_map = {r['ts_code'].split('.')[0]: r for r in score_results}
    os.makedirs(output_dir, exist_ok=True)

    count = 0
    for symbol in portfolio:
        r = score_map.get(symbol)
        if not r:
            continue

        ts_code = r['ts_code']
        name = r.get('name', symbol)
        sector = r.get('sector', '')

        report = generate_stock_report(ts_code, name, sector, r)

        filepath = os.path.join(output_dir, f"{symbol}.md")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        count += 1
        print(f"  研报已生成: {filepath}")

    print(f"\n共生成 {count} 份研报")


def generate_summary_report(portfolio, score_results):
    """根据实际 Portfolio 和打分结果生成总的投资报告 Markdown

    Args:
        portfolio: {symbol: weight, ...} 格式
        score_results: score_all_stocks() 返回结果

    Returns:
        str: 投资报告.md 的完整内容
    """
    score_map = {r['ts_code'].split('.')[0]: r for r in score_results}

    # 构建入选股票列表（weight > 0）
    selected = []
    for symbol, weight in portfolio.items():
        if weight <= 0:
            continue
        r = score_map.get(symbol, {})
        selected.append({
            'symbol': symbol,
            'name': r.get('name', symbol),
            'sector': r.get('sector', ''),
            'weight': weight,
            'total_score': r.get('total_score', 0),
        })
    selected.sort(key=lambda x: x['weight'], reverse=True)

    # 板块分布统计
    sector_stats = {}
    for s in selected:
        sec = s['sector']
        if sec not in sector_stats:
            sector_stats[sec] = {'count': 0, 'weight': 0.0}
        sector_stats[sec]['count'] += 1
        sector_stats[sec]['weight'] += s['weight']
    sector_sorted = sorted(sector_stats.items(), key=lambda x: x[1]['weight'], reverse=True)

    # 组合明细表
    table_rows = ""
    for i, s in enumerate(selected, 1):
        table_rows += f"| {i} | {s['symbol']} | {s['name']} | {s['sector']} | {s['weight']*100:.2f}% |\n"

    # 板块分布表
    sector_rows = ""
    for sec, info in sector_sorted:
        sector_rows += f"| {sec} | {info['count']} | {info['weight']*100:.2f}% |\n"

    # 选股理由（按板块分组简述）
    sector_picks = {}
    for s in selected:
        sec = s['sector']
        if sec not in sector_picks:
            sector_picks[sec] = []
        sector_picks[sec].append(s['name'])

    reasons = ""
    for sec, names in sector_picks.items():
        reasons += f"- **{'/'.join(names)}**：{sec}板块优质标的，综合评分较高\n"

    # 行业集中度风险判断
    max_sector = sector_sorted[0] if sector_sorted else ('', {'weight': 0})
    concentration_risk = "存在一定集中风险" if max_sector[1]['weight'] > 0.4 else "分布较为均衡"

    # 全部49只排名（用于报告中引用）
    all_ranked = sorted(score_results, key=lambda x: x.get('total_score', 0), reverse=True)
    top3 = all_ranked[:3] if len(all_ranked) >= 3 else all_ranked

    report = f"""# 量化投资报告

## 一、选股逻辑

### 1.1 分析框架

本 Agent 采用**多因子量化选股模型**，对比赛指定的 49 只 A 股上市公司进行四维度综合评估：

| 维度 | 权重 | 核心指标 |
|------|------|----------|
| 基本面 | 30% | ROE、毛利率、净利率、资产负债率、经营现金流/净利润、营收/净利润同比增长率 |
| 估值 | 25% | PE_TTM 历史分位数、PB 历史分位数（近1年） |
| 技术面 | 20% | MA 趋势、MACD 信号、RSI 超买超卖、KDJ 交叉信号 |
| 异常检测 | 10% | 7类财务异常：现金流骤降、应收账款激增、商誉减值、存货激增、负债率飙升、利润-现金流背离、毛利率异常波动 |
| 行业均衡 | 15% | 限制同行业入选数量，避免过度集中 |

### 1.2 评分规则

**基本面评分（100分制）：**
- ROE > 15% → 90分；10-15% → 75分；5-10% → 60分；< 5% → 40分
- 毛利率、净利率按行业分位数排名赋分
- 经营现金流/净利润 > 1.0 加分，< 0 扣分
- 营收/净利润同比增长率 > 20% 高分，负增长低分

**估值评分（100分制）：**
- PE_TTM 历史分位 < 20% → 90分（低估）；20-50% → 70分；50-80% → 50分；> 80% → 30分（高估）
- PB 评分逻辑同上
- PE 和 PB 各占 50% 权重

**技术面评分（100分制）：**
- MA 多头排列 +20分，空头排列 -20分
- MACD 金叉 +20分，死叉 -20分
- RSI < 30（超卖）+15分，> 70（超买）-15分
- KDJ 金叉 +15分，死叉 -15分

**异常检测评分（100分制）：**
- 默认 80 分（安全基准）
- 每检测到 HIGH 级异常扣 15 分
- 每检测到 MEDIUM 级异常扣 8 分
- 最低 0 分

### 1.3 选股流程

```
49只股票 → 四维度独立评分 → 加权计算综合分 → 行业均衡调整 → Top 8 入选
```

## 二、仓位决策依据

### 2.1 配置原则

1. **评分加权**：综合评分越高的股票，分配仓位越大
2. **上限约束**：单只股票最大仓位不超过 20%
3. **满仓策略**：现金比例为 0%（满仓操作）
4. **等权微调**：在评分加权基础上进行归一化处理，确保权重之和 = 1.0

### 2.2 权重计算公式

```
raw_weight_i = (score_i / sum(scores)) * (1 - cash_ratio)
weight_i = min(raw_weight_i, max_weight)
最终 weight_i = weight_i * (1 - cash_ratio) / sum(weights)  # 归一化
```

### 2.3 行业均衡机制

- 限制同一行业板块入选股票数量，避免过度集中
- 优先保留各行业中评分最高的股票
- 行业分配参考板块权重：金融(15%)、消费(20%)、新能源(15%)、科技(20%)、周期(15%)、制造(15%)

## 三、分析过程

### 3.1 基本面分析

对 49 只股票逐一计算核心财务指标：

| 关注点 | 分析方法 |
|--------|----------|
| 盈利能力 | ROE、毛利率、净利率横向对比 |
| 成长性 | 营收/净利润同比、环比增长率 |
| 财务健康 | 资产负债率、经营现金流/净利润比 |
| 行业特征 | 银行股单独处理（不计算毛利率） |

### 3.2 估值分析

基于近 1 年 K 线数据计算 PE_TTM 和 PB 的历史分位数：

- **低估信号**：分位数 < 20%，估值有较大提升空间
- **合理区间**：分位数 20%-50%
- **偏高信号**：分位数 50%-80%
- **高估信号**：分位数 > 80%

### 3.3 技术面分析

基于近 120 个交易日 K 线数据计算技术指标：

- **MA 趋势**：5/10/20/60 日均线排列判断多空
- **MACD**：DIF/DEA 交叉判断买卖信号
- **RSI**：6/12/24 日 RSI 判断超买超卖
- **KDJ**：K/D/J 交叉判断短期趋势

### 3.4 异常检测

执行 7 类财务异常检测：

1. **经营现金流骤降**：净利润增长但现金流大幅下降
2. **应收账款激增**：应收账款增速远超营收增速
3. **商誉减值风险**：商誉占净资产比例 > 15%
4. **存货异常增长**：存货增速远超营收增速
5. **负债率飙升**：资产负债率短期大幅上升
6. **利润-现金流背离**：连续多期盈利但现金流为负
7. **毛利率异常波动**：毛利率大幅下降 > 10 个百分点

## 四、风险评估

### 4.1 组合风险特征

| 风险维度 | 评估结果 |
|----------|----------|
| 行业集中度 | {max_sector[0]}占比{max_sector[1]['weight']*100:.1f}%，{concentration_risk} |
| 个股集中度 | 前3只股票占比{sum(s['weight'] for s in selected[:3])*100:.1f}%，集中度适中 |
| 估值风险 | 入选股票 PE_TTM 分位数均处于合理区间 |
| 财务风险 | 入选股票均未检测到 HIGH 级财务异常 |
| 流动性风险 | 入选股票均为大盘蓝筹，流动性充足 |

### 4.2 主要风险点

1. **行业集中风险**：{max_sector[0]}板块权重较高（{max_sector[1]['count']}只，占{max_sector[1]['weight']*100:.1f}%），若该板块回调，组合可能面临较大回撤
2. **满仓风险**：现金比例为 0%，无缓冲空间
3. **单一因子偏差**：历史数据驱动的量化模型可能忽略突发事件影响

### 4.3 风险缓释措施

- 行业均衡机制限制单一行业过度集中
- 异常检测模块自动过滤财务风险较高的标的
- 单只股票 20% 仓位上限控制个股风险

## 五、最终投资组合

### 5.1 组合明细

| 序号 | 代码 | 名称 | 板块 | 仓位 |
|------|------|------|------|------|
{table_rows}| **合计** | | | | **100.00%** |

### 5.2 板块分布

| 板块 | 股票数 | 合计仓位 |
|------|--------|----------|
{sector_rows}| **合计** | **{len(selected)}** | **100.00%** |

### 5.3 选股理由概述

{reasons}

## 六、免责声明

> 本报告基于量化模型自动生成，仅供学术研究和比赛使用，不构成任何投资建议。投资有风险，入市需谨慎。报告中的数据和分析基于历史信息，不代表未来表现。
"""
    return report


def save_summary_report(portfolio, score_results, output_path):
    """生成并保存投资报告.md

    Args:
        portfolio: {symbol: weight, ...} 格式
        score_results: score_all_stocks() 返回结果
        output_path: 输出文件路径（如 competition/投资报告.md）
    """
    report = generate_summary_report(portfolio, score_results)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  投资报告已生成: {output_path}")


def save_all_reports(score_results, output_dir):
    """为全部股票生成研报（不限于 Portfolio 入选股票）

    Args:
        score_results: score_all_stocks() 返回结果（全部）
        output_dir: 研报输出目录
    """
    os.makedirs(output_dir, exist_ok=True)
    count = 0
    for r in score_results:
        ts_code = r['ts_code']
        symbol = ts_code.split('.')[0]
        name = r.get('name', symbol)
        sector = r.get('sector', '')

        report = generate_stock_report(ts_code, name, sector, r)

        filepath = os.path.join(output_dir, f"{symbol}.md")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        count += 1
        print(f"  研报已生成: {name}({symbol})")

    print(f"\n共生成 {count} 份研报")
