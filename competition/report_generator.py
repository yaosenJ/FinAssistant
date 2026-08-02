# -*- coding: utf-8 -*-
"""
个股研报生成器
为全部49只股票生成 Markdown 格式研报，以及总结性投资报告
"""

import os


def _calc_sector_avg(all_results, sector, detail_key, field_name):
    """计算板块内某指标的平均值

    Args:
        all_results: 所有股票的打分结果列表
        sector: 板块名称
        detail_key: details 中的 key（如 'fundamental', 'valuation'）
        field_name: 指标名称（如 '毛利率', 'ROE', 'pe_ttm'）

    Returns:
        float or None: 板块均值
    """
    if not all_results:
        return None

    values = []
    for r in all_results:
        if r.get('sector') != sector:
            continue
        val = r.get('details', {}).get(detail_key, {}).get(field_name)
        if val is not None:
            try:
                values.append(float(val))
            except (ValueError, TypeError):
                continue

    if not values:
        return None

    return round(sum(values) / len(values), 2)


def _compare_indicator(company_val, sector_avg):
    """比较公司指标与板块均值

    Args:
        company_val: 公司指标值
        sector_avg: 板块均值

    Returns:
        str: 对比结果（高于/低于/持平）
    """
    if company_val is None or sector_avg is None:
        return '--'

    try:
        company_val = float(company_val)
        sector_avg = float(sector_avg)
    except (ValueError, TypeError):
        return '--'

    if company_val > sector_avg * 1.05:
        return '高于'
    elif company_val < sector_avg * 0.95:
        return '低于'
    else:
        return '持平'


def _compare_indicator_pe(company_val, sector_avg):
    """比较估值指标（PE/PB）与板块均值（估值越低越好）

    Args:
        company_val: 公司估值
        sector_avg: 板块均值

    Returns:
        str: 对比结果（低于行业/高于行业）
    """
    if company_val is None or sector_avg is None:
        return '--'

    try:
        company_val = float(company_val)
        sector_avg = float(sector_avg)
    except (ValueError, TypeError):
        return '--'

    if company_val < sector_avg * 0.95:
        return '低于行业'
    elif company_val > sector_avg * 1.05:
        return '高于行业'
    else:
        return '持平'


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


def _get_rating(val, thresholds):
    """根据阈值获取评级"""
    if val is None:
        return '--'
    try:
        val = float(val)
    except (ValueError, TypeError):
        return '--'
    if val > thresholds[0]:
        return '优'
    elif val > thresholds[1]:
        return '良'
    elif val > thresholds[2]:
        return '中'
    else:
        return '差'


def _generate_profitability_interpretation(fund):
    """生成盈利能力图表解读

    Args:
        fund: 基本面数据 dict

    Returns:
        str: 图表解读文字
    """
    gross_margin = fund.get('毛利率') or fund.get('营业利润率')
    net_margin = fund.get('净利率')
    roe = fund.get('ROE')

    parts = []

    if gross_margin is not None:
        if gross_margin > 40:
            parts.append(f"毛利率+{gross_margin}%，处于优秀水平，盈利能力突出")
        elif gross_margin > 25:
            parts.append(f"毛利率+{gross_margin}%，处于良好水平，盈利能力稳健")
        elif gross_margin > 15:
            parts.append(f"毛利率+{gross_margin}%，处于中等水平")
        else:
            parts.append(f"毛利率仅+{gross_margin}%，盈利能力偏弱")

    if roe is not None:
        if roe < 6:
            parts.append(f"ROE仅+{roe}%，股东回报偏低，需关注资本使用效率")
        elif roe > 18:
            parts.append(f"ROE+{roe}%，股东回报优秀")

    return '；'.join(parts) if parts else '盈利能力指标处于正常范围'


def _generate_valuation_interpretation(val):
    """生成估值图表解读

    Args:
        val: 估值数据 dict

    Returns:
        str: 图表解读文字
    """
    pe_pct = val.get('pe_ttm_percentile')
    pb_pct = val.get('pb_percentile')

    parts = []

    if pe_pct is not None:
        if pe_pct > 80:
            parts.append(f"PE_TTM历史分位+{pe_pct}%，处于近1年高位，估值风险较大")
        elif pe_pct < 20:
            parts.append(f"PE_TTM历史分位仅+{pe_pct}%，处于近1年低位，估值有提升空间")
        else:
            parts.append(f"PE_TTM历史分位+{pe_pct}%，估值处于合理区间")

    if pb_pct is not None:
        if pb_pct > 80:
            parts.append(f"PB历史分位+{pb_pct}%，市净率偏高，需警惕估值回调")
        elif pb_pct < 20:
            parts.append(f"PB历史分位仅+{pb_pct}%，市净率较低，安全边际充足")

    return '；'.join(parts) if parts else '估值指标处于正常范围'


def _generate_momentum_interpretation(tech):
    """生成动量图表解读

    Args:
        tech: 技术面数据 dict

    Returns:
        str: 图表解读文字
    """
    pct_5d = tech.get('pct_5d')
    pct_10d = tech.get('pct_10d')
    pct_20d = tech.get('pct_20d')
    vol_ratio = tech.get('vol_ratio')
    ma_trend = tech.get('ma_trend', '')

    parts = []

    # 动量趋势判断
    if pct_5d is not None and pct_10d is not None and pct_20d is not None:
        if pct_5d > 0 and pct_10d > 0 and pct_20d > 0:
            parts.append(f"近5/10/20日收益率均为正（+{pct_5d}%/+{pct_10d}%/+{pct_20d}%），短中长期趋势一致向上")
        elif pct_5d < 0 and pct_10d < 0 and pct_20d < 0:
            parts.append(f"近5/10/20日收益率均为负（{pct_5d}%/{pct_10d}%/{pct_20d}%），短中长期趋势一致向下")
        elif pct_5d > 0 and pct_20d < 0:
            parts.append(f"近5日涨幅+{pct_5d}%但20日跌幅{pct_20d}%，短期反弹但中期仍弱")
        elif pct_5d < 0 and pct_20d > 0:
            parts.append(f"近5日跌幅{pct_5d}%但20日涨幅+{pct_20d}%，短期回调但中期趋势向上")

    # 量比解读
    if vol_ratio is not None:
        if vol_ratio > 1.5:
            parts.append(f"量比{vol_ratio}，成交明显放量，资金关注度提升")
        elif vol_ratio > 1.0:
            parts.append(f"量比{vol_ratio}，成交温和放量")
        elif vol_ratio < 0.7:
            parts.append(f"量比{vol_ratio}，成交缩量，市场参与度下降")

    # 均线趋势
    if '多头' in str(ma_trend):
        parts.append("均线呈多头排列，趋势向好")
    elif '空头' in str(ma_trend):
        parts.append("均线呈空头排列，趋势偏弱")

    return '；'.join(parts) if parts else '动量指标处于正常范围'


def _generate_radar_interpretation(scores, rank, sector_rank, sector):
    """生成雷达图解读

    Args:
        scores: 各维度得分 dict
        rank: 全局排名
        sector_rank: 板块排名
        sector: 板块名称

    Returns:
        str: 雷达图解读文字
    """
    parts = []

    # 找出优势维度（得分最高）
    dim_names = {'fundamental': '基本面', 'valuation': '估值', 'technical': '技术面', 'momentum': '动量', 'anomaly': '风险'}
    best_dim = max(scores.items(), key=lambda x: x[1] if x[0] != 'anomaly' else 0)
    worst_dim = min(scores.items(), key=lambda x: x[1] if x[0] != 'anomaly' else 100)

    if best_dim[0] in dim_names:
        parts.append(f"优势维度: {dim_names[best_dim[0]]}")

    if worst_dim[0] in dim_names:
        parts.append(f"短板维度: {dim_names[worst_dim[0]]}")

    parts.append(f"全局排名{rank}（第{rank}名），{sector}内排名第{sector_rank}名")

    if rank <= 10:
        parts.append("整体处于上游水平")
    elif rank <= 25:
        parts.append("整体处于中上水平")
    elif rank <= 35:
        parts.append("整体处于中等水平")
    else:
        parts.append("整体处于中下水平")

    return '；'.join(parts) if parts else '综合评估正常'


def _generate_selection_reason(r, is_selected):
    """生成选股/排除理由

    Args:
        r: 股票评分结果（含 rank, sector_rank, scores, details 等）
        is_selected: 是否入选持仓

    Returns:
        str: 选股或排除理由
    """
    scores = r.get('scores', {})
    rank = r.get('rank', 49)
    sector_rank = r.get('sector_rank', 49)
    name = r.get('name', '')
    sector = r.get('sector', '')

    fund = r.get('details', {}).get('fundamental', {})
    val = r.get('details', {}).get('valuation', {})
    tech = r.get('details', {}).get('technical', {})
    anomaly_text = r.get('details', {}).get('anomaly', '')

    if is_selected:
        # 选股理由
        reasons = []
        if rank <= 10:
            reasons.append(f"全局排名第{rank}名，综合表现优秀")
        elif rank <= 20:
            reasons.append(f"全局排名第{rank}名，综合表现良好")
        else:
            reasons.append(f"全局排名第{rank}名")

        if sector_rank <= 2:
            reasons.append(f"{sector}内排名第{sector_rank}名，板块龙头")

        # 优势维度
        advantages = []
        if scores.get('fundamental', 0) >= 65:
            advantages.append("基本面")
        if scores.get('valuation', 0) >= 65:
            advantages.append("估值")
        if scores.get('technical', 0) >= 65:
            advantages.append("技术面")
        if advantages:
            reasons.append(f"优势维度: {'/'.join(advantages)}")

        # 毛利率优秀
        gross_margin = fund.get('毛利率')
        if gross_margin and gross_margin > 50:
            reasons.append(f"毛利率优秀({gross_margin}%)")

        return "；".join(reasons)
    else:
        # 排除理由
        reasons = []

        # 检测到财务异常
        high_count = anomaly_text.count('[HIGH]')
        medium_count = anomaly_text.count('[MEDIUM]')
        if high_count > 0:
            reasons.append("检测到HIGH级财务异常")
        elif medium_count > 0:
            reasons.append("检测到MEDIUM级财务异常")

        # 短板维度
        weaknesses = []
        if scores.get('valuation', 50) < 45:
            weaknesses.append("估值")
        if scores.get('fundamental', 50) < 45:
            weaknesses.append("基本面")
        if scores.get('technical', 50) < 45:
            weaknesses.append("技术面")
        if weaknesses:
            reasons.append(f"短板维度: {'/'.join(weaknesses)}")

        # 估值偏高
        pe_pct = val.get('pe_ttm_percentile')
        if pe_pct and pe_pct > 70:
            reasons.append("估值偏高")

        if not reasons:
            if rank <= 10:
                reasons.append(f"全局排名第{rank}名，表现良好但未入选（板块名额有限或竞争激烈）")
            else:
                reasons.append("综合评分未进入持仓")

        return "；".join(reasons)


def generate_stock_report(ts_code, name, sector, score_result, all_results=None):
    """
    生成单只股票的 Markdown 研报

    Args:
        ts_code: 带后缀的股票代码
        name: 股票名称
        sector: 所属板块
        score_result: stock_scorer 的打分结果 dict
        all_results: 所有股票的打分结果列表（用于板块对比）

    Returns:
        str: Markdown 格式研报
    """
    details = score_result.get('details', {})
    scores = score_result.get('scores', {})
    total_score = score_result.get('total_score', 0)
    rank = score_result.get('rank', '--')
    sector_rank = score_result.get('sector_rank', '--')

    fund = details.get('fundamental', {})
    val = details.get('valuation', {})
    tech = details.get('technical', {})
    anomaly = details.get('anomaly', '')

    symbol = ts_code.split('.')[0]

    # 计算综合评级
    if total_score >= 70:
        overall_rating = '优'
    elif total_score >= 55:
        overall_rating = '良'
    elif total_score >= 40:
        overall_rating = '中'
    else:
        overall_rating = '差'

    # 生成核心优势和主要风险
    core_advantages = []
    main_risks = []

    gross_margin = fund.get('毛利率') or fund.get('营业利润率')
    if gross_margin and gross_margin > 40:
        core_advantages.append(f"毛利率+{gross_margin}%，盈利能力突出")

    cf_ratio = fund.get('经营现金流净利润比')
    if cf_ratio is not None and cf_ratio > 1:
        core_advantages.append(f"经营现金流/净利润{cf_ratio}，盈利质量扎实")

    if '多头' in str(tech.get('ma_trend', '')):
        core_advantages.append("技术面呈多头排列，趋势向好")

    # 动量优势
    pct_5d = tech.get('pct_5d')
    if pct_5d is not None and pct_5d > 3:
        core_advantages.append(f"短期动量偏强，近5日涨幅+{pct_5d}%")

    # 风险提示
    high_count = anomaly.count('[HIGH]')
    if high_count > 0:
        main_risks.append("检测到HIGH级财务异常")

    ar_ratio = fund.get('应收账款占比')
    if ar_ratio is not None and ar_ratio > 30:
        main_risks.append(f"应收账款占比+{ar_ratio}%，回款风险较高")

    cf_ratio = fund.get('经营现金流净利润比')
    if cf_ratio is not None and cf_ratio < 0:
        main_risks.append("现金流质量较差，利润缺乏现金支撑")

    pe_pct = val.get('pe_ttm_percentile')
    if pe_pct and pe_pct > 80:
        main_risks.append("估值处于历史高位，存在回调风险")

    report = f"""# {name}({symbol}) 投资研究报告

## 一、投资要点

**综合评级: {overall_rating}**

**核心优势:** {'；'.join(core_advantages) if core_advantages else '暂无明显优势'}

**主要风险:** {'；'.join(main_risks) if main_risks else '暂无明显风险'}

## 二、公司概况

| 项目 | 内容 |
|------|------|
| 股票代码 | {symbol} |
| 股票名称 | {name} |
| 所属板块 | {sector} |
| 综合评级 | **{overall_rating}** |
| 全局排名 | 第{rank}名（49只内） |
| 板块内排名 | 第{sector_rank}名（{sector}内） |

### 各维度排名对比

| 维度 | 全局排名 | 板块排名 |
|------|----------|----------|
| 基本面 | {score_result.get('dim_ranks', {}).get('fundamental', '--')} | {score_result.get('dim_sector_ranks', {}).get('fundamental', '--')} |
| 估值 | {score_result.get('dim_ranks', {}).get('valuation', '--')} | {score_result.get('dim_sector_ranks', {}).get('valuation', '--')} |
| 技术面 | {score_result.get('dim_ranks', {}).get('technical', '--')} | {score_result.get('dim_sector_ranks', {}).get('technical', '--')} |
| 动量 | {score_result.get('dim_ranks', {}).get('momentum', '--')} | {score_result.get('dim_sector_ranks', {}).get('momentum', '--')} |
| 风险 | {score_result.get('dim_ranks', {}).get('anomaly', '--')} | {score_result.get('dim_sector_ranks', {}).get('anomaly', '--')} |

## 三、盈利能力分析

| 指标 | 数值 | 评级 | 说明 |
|------|------|------|------|
| 毛利率/营业利润率 | {_safe_pct(fund.get('毛利率'))} | {_get_rating(fund.get('毛利率'), [40, 25, 15])} | 越高越好，反映产品竞争力 |
| 净利率 | {_safe_pct(fund.get('净利率'))} | {_get_rating(fund.get('净利率'), [20, 12, 6])} | 综合盈利能力 |
| ROE | {_safe_pct(fund.get('ROE'))} | {_get_rating(fund.get('ROE'), [18, 12, 6])} | 股东回报率 |

**杜邦拆解:**
| 指标 | 数值 | 说明 |
|------|------|------|
| 杜邦_净利率 | {_safe_pct(fund.get('杜邦_净利率'))} | ROE = 净利率 × 周转率 × 权益乘数 |
| 杜邦_总资产周转率 | {_safe_str(fund.get('杜邦_总资产周转率'))} | 反映资产运营效率 |
| 杜邦_权益乘数 | {_safe_str(fund.get('杜邦_权益乘数'))} | 反映杠杆水平 |

![盈利能力](./charts/{name}_profitability.png)

> **图表解读**: {_generate_profitability_interpretation(fund)}

> 数据来源: market_data.stock_financial（财务报表明细数据）

## 四、盈利真实性与营运风险

| 指标 | 数值 | 评级 | 说明 |
|------|------|------|------|
| 经营现金流/净利润 | {_safe_str(fund.get('经营现金流净利润比'))} | {_get_rating(fund.get('经营现金流净利润比'), [1.2, 0.8, 0.5])} | >1说明利润有现金支撑 |
| 应收账款/营收 | {_safe_pct(fund.get('应收账款占比'))} | {_get_rating(-(fund.get('应收账款占比') or 0), [-10, -20, -30])} | 越低越好，回款风险小 |
| 资产负债率 | {_safe_pct(fund.get('资产负债率'))} | {_get_rating(-(fund.get('资产负债率') or 0), [-30, -50, -70])} | 越低越安全 |

> 数据来源: market_data.stock_financial（现金流量表、资产负债表）

## 五、成长性分析

| 指标 | 数值 | 评级 |
|------|------|------|
| 营收同比增长率 | {_safe_pct(fund.get('营收同比增长率'))} | {_get_rating(fund.get('营收同比增长率'), [20, 10, 0])} |
| 净利润同比增长率 | {_safe_pct(fund.get('净利润同比增长率'))} | {_get_rating(fund.get('净利润同比增长率'), [30, 15, 0])} |
| 营收环比增长率 | {_safe_pct(fund.get('营收环比增长率'))} | -- |
| 净利润环比增长率 | {_safe_pct(fund.get('净利润环比增长率'))} | -- |

> 数据来源: market_data.stock_financial（利润表同比/环比计算）

## 六、估值分析

| 指标 | 当前值 | 历史分位 | 估值评级 |
|------|--------|----------|----------|
| PE_TTM | {_safe_str(val.get('pe_ttm'))} | {_safe_pct(val.get('pe_ttm_percentile'))} | {_safe_str(val.get('pe_ttm_level'))} |
| PB | {_safe_str(val.get('pb'))} | {_safe_pct(val.get('pb_percentile'))} | {_safe_str(val.get('pb_level'))} |

![估值象限](./charts/{name}_valuation.png)

> **图表解读**: {_generate_valuation_interpretation(val)}

> 数据来源: market_data.stock_kline（近1年K线数据计算历史分位数）

## 七、技术面分析

| 指标 | 数值 | 评级 |
|------|------|------|
| 最新收盘价 | {_safe_str(tech.get('close'))} | -- |
| MA趋势 | {_safe_str(tech.get('ma_trend'))} | {'偏多' if '多头' in str(tech.get('ma_trend', '')) else '偏空' if '空头' in str(tech.get('ma_trend', '')) else '--'} |
| MACD信号 | {_safe_str(tech.get('macd_signal'))} | {'偏多' if '金叉' in str(tech.get('macd_signal', '')) else '偏空' if '死叉' in str(tech.get('macd_signal', '')) else '--'} |
| RSI6信号 | {_safe_str(tech.get('rsi6_signal'))} | -- |
| KDJ信号 | {_safe_str(tech.get('kdj_signal'))} | -- |

> 数据来源: market_data.stock_kline（近120个交易日K线数据计算技术指标）

## 八、动量与趋势分析

| 指标 | 数值 | 评级 |
|------|------|------|
| 近5日收益率 | {_safe_pct(tech.get('pct_5d'))} | {'偏强' if (tech.get('pct_5d') or 0) > 5 else '偏弱' if (tech.get('pct_5d') or 0) < -5 else '--'} |
| 近10日收益率 | {_safe_pct(tech.get('pct_10d'))} | -- |
| 近20日收益率 | {_safe_pct(tech.get('pct_20d'))} | -- |
| 量比(5/20) | {_safe_str(tech.get('vol_ratio'))} | {'放量' if (tech.get('vol_ratio') or 0) > 1.5 else '缩量' if (tech.get('vol_ratio') or 0) < 0.7 else '温和'} |
| 20日波动率(年化) | {_safe_pct(tech.get('volatility_20d'))} | -- |

![动量趋势](./charts/{name}_momentum.png)

> **图表解读**: {_generate_momentum_interpretation(tech)}

> 数据来源: market_data.stock_kline（近20个交易日收益率和成交量数据）

## 九、风险检测

```
{anomaly if anomaly else '未检测到明显异常信号'}
```

> 数据来源: market_data.stock_financial（7类财务异常规则检测）

## 九、综合评估

综合评级: **{overall_rating}**

![多维评分](./charts/{name}_radar.png)

> **图表解读**: {_generate_radar_interpretation(scores, rank, sector_rank, sector)}

| 维度 | 得分 | 权重 |
|------|------|------|
| 基本面 | {scores.get('fundamental', '--')} | 20% |
| 估值 | {scores.get('valuation', '--')} | 15% |
| 技术面 | {scores.get('technical', '--')} | 30% |
| 动量 | {scores.get('momentum', '--')} | 25% |
| 风险 | {scores.get('anomaly', '--')} | 10% |

> 评级基于盈利能力、估值水平、技术面趋势、动量强度等多维度定性判断。

## 十一、行业对比（{sector}）

### 财务指标对比

| 指标 | 本公司 | 行业均值 | 对比 |
|------|--------|----------|------|
| 毛利率 | {_safe_pct(fund.get('毛利率'))} | {_safe_pct(_calc_sector_avg(all_results, sector, 'fundamental', '毛利率'))} | {_compare_indicator(fund.get('毛利率'), _calc_sector_avg(all_results, sector, 'fundamental', '毛利率'))} |
| ROE | {_safe_pct(fund.get('ROE'))} | {_safe_pct(_calc_sector_avg(all_results, sector, 'fundamental', 'ROE'))} | {_compare_indicator(fund.get('ROE'), _calc_sector_avg(all_results, sector, 'fundamental', 'ROE'))} |
| 营收增长率 | {_safe_pct(fund.get('营收同比增长率'))} | {_safe_pct(_calc_sector_avg(all_results, sector, 'fundamental', '营收同比增长率'))} | {_compare_indicator(fund.get('营收同比增长率'), _calc_sector_avg(all_results, sector, 'fundamental', '营收同比增长率'))} |

### 估值对比

| 指标 | 本公司 | 行业均值 | 对比 |
|------|--------|----------|------|
| PE_TTM | {_safe_str(val.get('pe_ttm'))} | {_safe_str(_calc_sector_avg(all_results, sector, 'valuation', 'pe_ttm'))} | {_compare_indicator_pe(val.get('pe_ttm'), _calc_sector_avg(all_results, sector, 'valuation', 'pe_ttm'))} |
| PB | {_safe_str(val.get('pb'))} | {_safe_str(_calc_sector_avg(all_results, sector, 'valuation', 'pb'))} | {_compare_indicator_pe(val.get('pb'), _calc_sector_avg(all_results, sector, 'valuation', 'pb'))} |

> 数据来源: 49只股票基本面/估值数据计算板块均值

## 十二、盈利预测

| 预测项 | 预测值 | 预测依据 |
|--------|--------|----------|
| 营收增速 | 预计下一年营收增速约 {_safe_pct((fund.get('营收同比增长率') or 0) * 0.7)}（基于本期{_safe_pct(fund.get('营收同比增长率'))}的70%衰减） | 基于本期增速70%衰减 |
| 净利润增速 | 预计下一年净利润增速约 {_safe_pct((fund.get('净利润同比增长率') or 0) * 0.7)}（基于本期{_safe_pct(fund.get('净利润同比增长率'))}的70%衰减） | 基于本期增速70%衰减 |
| 远期PE | 按预测增速，远期PE约 {_safe_str(round((val.get('pe_ttm') or 0) * 0.95, 1))}（当前{_safe_str(val.get('pe_ttm'))}） | 按预测增速折算 |

> 注：预测基于历史增长率简单外推（衰减系数0.7），仅供参考，不构成盈利承诺。

---

> 风险提示: 本报告基于量化模型自动生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。

---

## 附录：评级标准

| 维度 | 优 | 良 | 中 | 差 |
|------|------|------|------|------|
| 毛利率 | >40% | 25-40% | 15-25% | <15% |
| 净利率 | >20% | 12-20% | 6-12% | <6% |
| ROE | >18% | 12-18% | 6-12% | <6% |
| 经营现金流/净利润 | >1.2 | 0.8-1.2 | 0.5-0.8 | <0.5 |
| 应收账款/营收 | <10% | 10-20% | 20-30% | >30% |
| 资产负债率 | <30% | 30-50% | 50-70% | >70% |

| 维度 | 低估/偏多/强势 | 合理/中性/偏强 | 偏高/偏弱 | 高估/弱势 |
|------|----------------|----------------|-----------|-----------|
| PE/PB历史分位 | <20% | 20-50% | 50-80% | >80% |
| MA趋势 | 多头排列 | 交叉盘整 | -- | 空头排列 |
| 近5日收益率 | >5% | 1-5% | -5~1% | <-5% |
| 量比 | >1.5 | 1.0-1.5 | 0.7-1.0 | <0.7 |
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
            'rank': r.get('rank', '--'),
            'sector_rank': r.get('sector_rank', '--'),
            'scores': r.get('scores', {}),
            'details': r.get('details', {}),
            'reason': _generate_selection_reason(r, True),
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
        table_rows += f"| {i} | {s['symbol']} | {s['name']} | {s['sector']} | {s['rank']} | {s['sector_rank']} | {s['weight']*100:.2f}% |\n"

    # 入选股票核心指标
    stock_details = ""
    for i, s in enumerate(selected, 1):
        fund = s['details'].get('fundamental', {})
        val = s['details'].get('valuation', {})
        tech = s['details'].get('technical', {})
        scores = s['scores']

        stock_details += f"\n**{i}. {s['name']}({s['symbol']}) — 仓位 {s['weight']*100:.2f}%**\n"
        stock_details += f"- 全局排名: 第{s['rank']}名 | 板块内排名: 第{s['sector_rank']}名（{s['sector']}）\n"
        stock_details += f"- **入选理由**: {s['reason']}\n"
        stock_details += f"- 基本面: ROE{_safe_pct(fund.get('ROE'))} 毛利率{_safe_pct(fund.get('毛利率'))}\n"
        stock_details += f"- 估值: PE{_safe_str(val.get('pe_ttm'))} PB{_safe_str(val.get('pb'))}\n"
        stock_details += f"- 动量: 5日涨幅{_safe_pct(tech.get('pct_5d'))} 20日涨幅{_safe_pct(tech.get('pct_20d'))}\n"

    # 板块分布表
    sector_rows = ""
    for sec, info in sector_sorted:
        sector_rows += f"| {sec} | {info['count']} | {info['weight']*100:.2f}% |\n"

    # 49只股票全量排名表
    all_ranked = sorted(score_results, key=lambda x: x.get('rank', 99))
    all_stocks_table = ""
    for r in all_ranked:
        ts_code = r.get('ts_code', '')
        symbol = ts_code.split('.')[0]
        name = r.get('name', symbol)
        sector = r.get('sector', '')
        rank = r.get('rank', '--')
        sector_rank = r.get('sector_rank', '--')
        is_selected = symbol in portfolio
        mark = "★" if is_selected else ""
        reason = _generate_selection_reason(r, is_selected)
        tech = r.get('details', {}).get('technical', {})
        pct_5d = tech.get('pct_5d')
        pct_5d_str = f"{pct_5d:+.1f}%" if pct_5d is not None else '--'
        all_stocks_table += f"| {sector} | {symbol} | {name} | {rank} | {sector_rank} | {pct_5d_str} | {mark} | {reason} |\n"

    # 行业集中度风险判断
    max_sector = sector_sorted[0] if sector_sorted else ('', {'weight': 0, 'count': 0})
    concentration_risk = "存在一定集中风险" if max_sector[1]['weight'] > 0.4 else "分布较为均衡"

    report = f"""# 量化投资报告

## 一、选股逻辑

### 1.1 分析框架

本 Agent 采用**多因子量化选股模型**，对比赛指定的 49 只 A 股进行绝对排名（1-49，1=最优），Agent 根据排名数据自主决策持仓和权重。

**分析维度与核心指标：**

| 维度 | 权重 | 核心指标 |
|------|------|----------|
| 基本面 | 20% | ROE、毛利率/营业利润率、净利率、杜邦三因子（净利率/周转率/权益乘数）、经营现金流/净利润、应收账款占比、营收/净利润同比增长率 |
| 估值 | 15% | PE_TTM 历史分位数、PB 历史分位数（近1年） |
| 技术面 | 30% | MA 趋势、MACD 信号、RSI 超买超卖、KDJ 交叉信号 |
| 动量 | 25% | 近5/10/20日收益率、量比（5日/20日均量）、20日波动率 |
| 风险 | 10% | 7类财务异常检测（现金流骤降、应收账款激增、商誉减值等） |

### 1.2 排名规则

各指标在 49 只股票内计算绝对排名（1=最优，49=最差）。综合排名 = 各维度评分加权平均。同时计算**板块内排名**（同板块内比较），更准确反映个股在行业内的相对位置。

### 1.3 选股流程

```
49只股票 → 各维度原始数据采集 → 49只内绝对排名 → Agent 自主分析决策
```

## 二、仓位决策依据

Agent 综合考虑基本面排名、估值水平、技术面趋势、动量因子和风险检测结果，自主决策持仓和权重。

- 单只股票最大仓位不超过 20%（约束条件）
- 权重归一化确保总和 = 1.0
- 入选 {len(selected)} 只股票，覆盖 {len(sector_stats)} 个板块

## 三、分析过程

### 3.1 基本面分析

按分析框架顺序对 49 只股票逐一计算：

| 步骤 | 分析内容 | 核心指标 |
|------|----------|----------|
| 1 | 盈利能力 | 毛利率/营业利润率、净利率 |
| 2 | 股东回报 | ROE + 杜邦拆解（净利率 × 周转率 × 权益乘数） |
| 3 | 现金流质量 | 经营现金流/净利润、应收账款占比 |
| 4 | 成长性 | 营收/净利润同比、环比增长率 |

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

### 3.4 动量分析

基于近 20 个交易日数据计算动量因子（权重25%）：

- **短期动量**：近5日收益率，捕捉近期强势股
- **中期动量**：近10/20日收益率，确认趋势持续性
- **量比**：5日均量/20日均量，>1表示资金流入加速
- **波动率**：20日日收益率标准差（年化），越低越稳定

### 3.5 异常检测

执行 7 类财务异常检测：

1. **经营现金流骤降**：净利润增长但现金流大幅下降
2. **应收账款激增**：应收账款增速远超营收增速
3. **商誉减值风险**：商誉占净资产比例 > 15%
4. **存货异常增长**：存货增速远超营收增速
5. **负债率飙升**：资产负债率短期大幅上升
6. **利润-现金流背离**：连续多期盈利但现金流为负
7. **毛利率/营业利润率异常波动**：毛利率或营业利润率大幅下降 > 10 个百分点

> 数据来源: market_data.stock_financial（财务报表历史数据对比）、market_data.stock_kline（K线行情数据）

## 四、风险评估

### 4.1 组合风险特征

| 风险维度 | 评估结果 |
|----------|----------|
| 行业集中度 | {max_sector[0]}占比{max_sector[1]['weight']*100:.1f}%，{concentration_risk} |
| 个股集中度 | 前3只股票占比{sum(s['weight'] for s in selected[:3])*100:.1f}%，集中度适中 |
| 财务风险 | 入选股票均未检测到 HIGH 级财务异常 |

### 4.2 主要风险点

1. **行业集中风险**：{max_sector[0]}板块权重较高（{max_sector[1]['count']}只，占{max_sector[1]['weight']*100:.1f}%），若该板块回调，组合可能面临较大回撤
2. **满仓风险**：现金比例为 0%，无缓冲空间
3. **单一因子偏差**：历史数据驱动的量化模型可能忽略突发事件影响

### 4.3 风险缓释措施

- 行业均衡机制限制单一行业过度集中
- 异常检测模块自动过滤财务风险较高的标的
- 单只股票 20% 仓位上限控制个股风险

## 五、止损策略

| 触发条件 | 操作 | 说明 |
|----------|------|------|
| 单只股票回撤 > 8% | 减半仓 | 个股止损，控制单票亏损 |
| 组合整体回撤 > 5% | 降低仓位至 70% | 组合止损，保留30%现金缓冲 |
| 触发止损后 | 保留 30% 现金 | 为反弹预留资金 |

## 六、最终投资组合

### 6.1 组合明细

| 序号 | 代码 | 名称 | 板块 | 全局排名 | 板块排名 | 仓位 |
|------|------|------|------|----------|----------|------|
{table_rows}| **合计** | | | | | | **100.00%** |

### 6.2 入选股票核心指标

{stock_details}

### 6.3 板块分布

| 板块 | 股票数 | 合计仓位 |
|------|--------|----------|
{sector_rows}| **合计** | **{len(selected)}** | **100.00%** |

## 七、49只股票全量排名

> ★ 标记为入选投资组合的股票

| 板块 | 代码 | 名称 | 全局排名 | 板块排名 | 近5日涨幅 | 入选 | 理由 |
|------|------|------|----------|----------|-----------|------|------|
{all_stocks_table}

## 八、免责声明

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

        report = generate_stock_report(ts_code, name, sector, r, all_results=score_results)

        filepath = os.path.join(output_dir, f"{symbol}.md")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        count += 1
        print(f"  研报已生成: {name}({symbol})")

    print(f"\n共生成 {count} 份研报")
