#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财务健康度评分工具
对 A 股上市公司进行四维度综合评分（盈利能力、成长性、安全性、盈利质量），
结合异常检测扣分，输出 0-100 的财务健康度评分。

评分维度:
- 盈利能力 (30%): ROE、毛利率、净利率
- 成长性   (25%): 营收同比增速、净利润同比增速
- 安全性   (25%): 资产负债率、经营现金流/净利润、应收账款占比
- 盈利质量 (20%): 扣非净利率占比、经营现金流持续性

评级: 优(>=75) / 良(>=60) / 中(>=45) / 差(<45)

用法:
    from tools.financial_score import calc_financial_score, format_financial_score
    print(format_financial_score('600519.SH'))
"""

import logging

try:
    from tools.stock_fundamental import calc_fundamental_indicators, calc_fundamental_trend
    from tools.financial_anomaly import (
        _detect_cashflow_drop, _detect_receivables_surge, _detect_goodwill_risk,
        _detect_inventory_surge, _detect_debt_surge, _detect_profit_cashflow_divergence,
        _detect_margin_volatility, _get_report, _get_stock_name,
    )
except ImportError:
    from stock_fundamental import calc_fundamental_indicators, calc_fundamental_trend
    from financial_anomaly import (
        _detect_cashflow_drop, _detect_receivables_surge, _detect_goodwill_risk,
        _detect_inventory_surge, _detect_debt_surge, _detect_profit_cashflow_divergence,
        _detect_margin_volatility, _get_report, _get_stock_name,
    )

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# 阶梯评分工具函数
# ──────────────────────────────────────────────────────────────

def _tier_score(value, tiers):
    """阶梯评分

    Args:
        value: 待评分数值（可为 None）
        tiers: [(阈值, 分数), ...] 从高到低排列，value >= 阈值时取对应分数

    Returns:
        int: 分数，value 为 None 时返回 50（中性默认分）
    """
    if value is None:
        return 50
    for threshold, score in tiers:
        if value >= threshold:
            return score
    return tiers[-1][1]


def _tier_score_lower_better(value, tiers):
    """阶梯评分（越低越好）

    Args:
        value: 待评分数值（可为 None）
        tiers: [(阈值, 分数), ...] 从低到高排列，value <= 阈值时取对应分数

    Returns:
        int: 分数
    """
    if value is None:
        return 50
    for threshold, score in tiers:
        if value <= threshold:
            return score
    return tiers[-1][1]


def _clamp(val, lo=0, hi=100):
    return max(lo, min(hi, val))


# ──────────────────────────────────────────────────────────────
# 各维度评分
# ──────────────────────────────────────────────────────────────

def _score_profitability(indicators):
    """盈利能力评分 (满分 100)

    指标: ROE(40%) + 毛利率/营业利润率(30%) + 净利率(30%)
    """
    is_bank = indicators.get('is_bank', False)

    # ROE
    roe = indicators.get('ROE')
    roe_score = _tier_score(roe, [
        (15, 95), (12, 85), (10, 75), (8, 65), (5, 55), (3, 45), (0, 30),
    ])

    # 毛利率 / 营业利润率
    margin_name = '营业利润率' if is_bank else '毛利率'
    margin = indicators.get(margin_name)
    margin_score = _tier_score(margin, [
        (50, 90), (35, 75), (25, 60), (15, 45), (8, 30),
    ])

    # 净利率
    net_margin = indicators.get('净利率')
    net_score = _tier_score(net_margin, [
        (20, 90), (12, 75), (8, 60), (5, 50), (2, 35), (0, 20),
    ])

    score = roe_score * 0.40 + margin_score * 0.30 + net_score * 0.30

    return round(score, 1), {
        'ROE': {'value': roe, 'score': roe_score},
        margin_name: {'value': margin, 'score': margin_score},
        '净利率': {'value': net_margin, 'score': net_score},
    }


def _score_growth(indicators):
    """成长性评分 (满分 100)

    指标: 营收同比增长率(50%) + 净利润同比增长率(50%)
    """
    rev_growth = indicators.get('营收同比增长率')
    np_growth = indicators.get('净利润同比增长率')

    rev_score = _tier_score(rev_growth, [
        (30, 90), (20, 80), (10, 65), (5, 55), (0, 40),
    ])
    np_score = _tier_score(np_growth, [
        (30, 90), (20, 80), (10, 65), (5, 55), (0, 40),
    ])

    score = rev_score * 0.50 + np_score * 0.50

    return round(score, 1), {
        '营收同比增长率': {'value': rev_growth, 'score': rev_score},
        '净利润同比增长率': {'value': np_growth, 'score': np_score},
    }


def _score_safety(indicators):
    """安全性评分 (满分 100)

    指标: 资产负债率(40%) + 经营现金流/净利润(35%) + 应收账款占比(25%)
    """
    is_bank = indicators.get('is_bank', False)

    # 资产负债率（越低越好，银行股放宽标准）
    debt_ratio = indicators.get('资产负债率')
    if is_bank:
        debt_score = _tier_score_lower_better(debt_ratio, [
            (90, 80), (92, 60), (94, 40), (96, 20),
        ])
    else:
        debt_score = _tier_score_lower_better(debt_ratio, [
            (35, 90), (45, 80), (55, 70), (65, 55), (75, 40), (85, 25),
        ])

    # 经营现金流/净利润（越高越好）
    cf_ratio = indicators.get('经营现金流净利润比')
    cf_score = _tier_score(cf_ratio, [
        (1.5, 90), (1.2, 80), (1.0, 70), (0.7, 55), (0.3, 40), (0, 25),
    ])

    # 应收账款占比（越低越好，银行股跳过）
    ar_ratio = indicators.get('应收账款占比')
    if is_bank or ar_ratio is None:
        ar_score = 70  # 银行无应收账款概念，给中性偏高分
    else:
        ar_score = _tier_score_lower_better(ar_ratio, [
            (15, 90), (25, 80), (35, 70), (50, 55), (65, 40), (80, 25),
        ])

    score = debt_score * 0.40 + cf_score * 0.35 + ar_score * 0.25

    return round(score, 1), {
        '资产负债率': {'value': debt_ratio, 'score': debt_score},
        '经营现金流净利润比': {'value': cf_ratio, 'score': cf_score},
        '应收账款占比': {'value': ar_ratio, 'score': ar_score},
    }


def _score_quality(indicators, trend_data):
    """盈利质量评分 (满分 100)

    指标: 扣非净利率/净利率(50%) + 经营现金流持续性(50%)
    """
    is_bank = indicators.get('is_bank', False)

    # 扣非净利率/净利率（衡量利润中经常性损益占比）
    deducted = indicators.get('扣非净利率')
    net_margin = indicators.get('净利率')
    if is_bank or deducted is None or net_margin is None or net_margin == 0:
        deduct_score = 65  # 银行股或无数据时给中性分
    else:
        ratio = deducted / net_margin * 100 if net_margin != 0 else None
        deduct_score = _tier_score(ratio, [
            (90, 90), (80, 80), (70, 65), (50, 45), (30, 30),
        ])

    # 经营现金流持续性：最近4期中 CF>0 的占比
    cf_consistency = None
    if trend_data and 'trend' in trend_data:
        cf_positive = 0
        total = 0
        for period in trend_data['trend']:
            cf_ratio = period.get('经营现金流净利润比')
            if cf_ratio is not None:
                total += 1
                if cf_ratio > 0:
                    cf_positive += 1
        if total > 0:
            cf_consistency = cf_positive / total * 100

    cf_con_score = _tier_score(cf_consistency, [
        (100, 95), (75, 75), (50, 55), (25, 35), (0, 15),
    ])

    score = deduct_score * 0.50 + cf_con_score * 0.50

    return round(score, 1), {
        '扣非净利率占比': {'value': deducted, 'score': deduct_score},
        '现金流持续性': {'value': cf_consistency, 'score': cf_con_score},
    }


# ──────────────────────────────────────────────────────────────
# 异常检测扣分
# ──────────────────────────────────────────────────────────────

def _calc_anomaly_deduction(ts_code, report_date=None):
    """计算异常检测扣分

    Returns:
        (float, list): (扣分值, 异常列表)
    """
    income, rd = _get_report(ts_code, 'income', report_date)
    if not income:
        return 0, []

    balance, _ = _get_report(ts_code, 'balance', rd)
    cashflow, _ = _get_report(ts_code, 'cashflow', rd)

    alerts = []
    alerts.extend(_detect_cashflow_drop(ts_code, rd, income, cashflow))
    alerts.extend(_detect_receivables_surge(ts_code, rd, income, balance))
    alerts.extend(_detect_goodwill_risk(ts_code, balance))
    alerts.extend(_detect_inventory_surge(ts_code, rd, income, balance))
    alerts.extend(_detect_debt_surge(ts_code, rd, balance))
    alerts.extend(_detect_profit_cashflow_divergence(ts_code))
    alerts.extend(_detect_margin_volatility(ts_code, rd, income))

    deduction = 0
    for a in alerts:
        if a['severity'] == 'HIGH':
            deduction += 5
        elif a['severity'] == 'MEDIUM':
            deduction += 2

    deduction = min(deduction, 15)  # 最多扣 15 分
    return deduction, alerts


# ──────────────────────────────────────────────────────────────
# 主函数
# ──────────────────────────────────────────────────────────────

def calc_financial_score(ts_code, report_date=None):
    """计算单只股票的财务健康度评分

    Args:
        ts_code: 股票代码，如 600519.SH
        report_date: 报告日，None 取最新一期

    Returns:
        dict: {
            ts_code, name, report_date,
            total_score (0-100), rating (优/良/中/差),
            dimensions: {profitability, growth, safety, quality},
            anomaly_deduction, alerts
        }
    """
    name = _get_stock_name(ts_code)

    # 获取基本面指标
    indicators = calc_fundamental_indicators(ts_code, report_date)
    if 'error' in indicators:
        return {'ts_code': ts_code, 'name': name, 'error': indicators['error']}

    rd = indicators.get('report_date')

    # 获取多期趋势（用于盈利质量）
    trend_data = calc_fundamental_trend(ts_code, periods=4)

    # 四维度评分
    prof_score, prof_details = _score_profitability(indicators)
    grow_score, grow_details = _score_growth(indicators)
    safe_score, safe_details = _score_safety(indicators)
    qual_score, qual_details = _score_quality(indicators, trend_data)

    # 加权综合
    weighted = (prof_score * 0.30 + grow_score * 0.25
                + safe_score * 0.25 + qual_score * 0.20)

    # 异常检测扣分
    deduction, alerts = _calc_anomaly_deduction(ts_code, rd)

    total = _clamp(round(weighted - deduction, 1))

    # 评级
    if total >= 75:
        rating = '优'
    elif total >= 60:
        rating = '良'
    elif total >= 45:
        rating = '中'
    else:
        rating = '差'

    return {
        'ts_code': ts_code,
        'name': name,
        'report_date': rd,
        'total_score': total,
        'rating': rating,
        'dimensions': {
            'profitability': {'score': prof_score, 'weight': 0.30, 'details': prof_details},
            'growth': {'score': grow_score, 'weight': 0.25, 'details': grow_details},
            'safety': {'score': safe_score, 'weight': 0.25, 'details': safe_details},
            'quality': {'score': qual_score, 'weight': 0.20, 'details': qual_details},
        },
        'anomaly_deduction': deduction,
        'alerts': alerts,
    }


def format_financial_score(ts_code, report_date=None):
    """格式化输出财务健康度评分

    Args:
        ts_code: 股票代码
        report_date: 报告日

    Returns:
        str: Markdown 格式的评分报告
    """
    r = calc_financial_score(ts_code, report_date)
    if 'error' in r:
        return f"评分失败: {r['error']}"

    lines = [
        f"## 财务健康度评分 - {r['name']}({r['ts_code']})",
        f"报告期: {r['report_date']}",
        "",
        f"**综合评分: {r['total_score']}  评级: {r['rating']}**",
        "",
    ]

    # 维度明细
    dim_names = {
        'profitability': '盈利能力',
        'growth': '成长性',
        'safety': '安全性',
        'quality': '盈利质量',
    }

    lines.append("| 维度 | 权重 | 评分 | 加权贡献 |")
    lines.append("|------|------|------|----------|")
    for key, cn_name in dim_names.items():
        dim = r['dimensions'][key]
        contrib = round(dim['score'] * dim['weight'], 1)
        lines.append(f"| {cn_name} | {dim['weight']:.0%} | {dim['score']} | {contrib} |")
    lines.append("")

    # 各维度细节
    for key, cn_name in dim_names.items():
        dim = r['dimensions'][key]
        lines.append(f"### {cn_name}（{dim['score']}分）")
        lines.append("")
        lines.append("| 指标 | 数值 | 评分 |")
        lines.append("|------|------|------|")
        for ind_name, ind_data in dim['details'].items():
            val = ind_data['value']
            if val is None:
                val_str = '--'
            elif isinstance(val, float):
                val_str = f"{val:.2f}"
            else:
                val_str = str(val)
            lines.append(f"| {ind_name} | {val_str} | {ind_data['score']} |")
        lines.append("")

    # 异常扣分
    if r['anomaly_deduction'] > 0:
        high_count = sum(1 for a in r['alerts'] if a['severity'] == 'HIGH')
        med_count = sum(1 for a in r['alerts'] if a['severity'] == 'MEDIUM')
        lines.append(f"### 异常检测扣分: -{r['anomaly_deduction']}分")
        lines.append(f"高风险 {high_count} 个, 中风险 {med_count} 个")
        lines.append("")
        for a in r['alerts']:
            icon = "!!" if a['severity'] == 'HIGH' else "! "
            lines.append(f"- {icon} [{a['severity']}] {a['type']}: {a['detail']}")
        lines.append("")

    return "\n".join(lines)


def score_sector(sector_name, sector_type='industry', top_n=10):
    """批量评分板块内成分股

    Args:
        sector_name: 板块名称
        sector_type: 'industry' 或 'concept'
        top_n: 前 N 只

    Returns:
        str: 格式化的板块评分结果
    """
    try:
        from tools.financial_compare import _get_sector_constituents, _stock_code_to_ts_code
    except ImportError:
        from financial_compare import _get_sector_constituents, _stock_code_to_ts_code

    constituents, sector_name_real = _get_sector_constituents(sector_name, sector_type)
    if not constituents:
        return f"未找到板块: {sector_name}"

    stock_codes = [c[0] for c in constituents]
    code_map = _stock_code_to_ts_code(stock_codes)
    ts_codes = [code_map[c][0] for c in stock_codes if c in code_map][:top_n]
    if not ts_codes:
        return f"板块 {sector_name_real} 无有效股票代码"

    results = []
    for code in ts_codes:
        r = calc_financial_score(code)
        if 'error' not in r:
            results.append(r)

    if not results:
        return f"板块 {sector_name} 无有效评分数据"

    results.sort(key=lambda x: x['total_score'], reverse=True)

    lines = [
        f"## {sector_name_real}板块 财务健康度评分",
        f"评分范围: 前{len(results)}只成分股",
        "",
        "| 排名 | 股票 | 综合评分 | 评级 | 盈利 | 成长 | 安全 | 质量 |",
        "|------|------|----------|------|------|------|------|------|",
    ]

    for i, r in enumerate(results, 1):
        d = r['dimensions']
        lines.append(
            f"| {i} | {r['name']}({r['ts_code']}) | {r['total_score']} | {r['rating']} "
            f"| {d['profitability']['score']} | {d['growth']['score']} "
            f"| {d['safety']['score']} | {d['quality']['score']} |"
        )

    avg_score = round(sum(r['total_score'] for r in results) / len(results), 1)
    lines.append("")
    lines.append(f"板块均分: {avg_score}")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='财务健康度评分')
    parser.add_argument('--ts_code', help='单只股票代码，如 600519.SH')
    parser.add_argument('--ts_codes', help='多只股票代码，逗号分隔，如 600519.SH,000858.SZ')
    parser.add_argument('--sector', help='板块名称，如 白酒')
    parser.add_argument('--top_n', type=int, default=10, help='板块评分取前N只，默认10')
    args = parser.parse_args()

    if args.ts_code:
        print(format_financial_score(args.ts_code))
    elif args.ts_codes:
        codes = [c.strip() for c in args.ts_codes.split(',')]
        for code in codes:
            print(format_financial_score(code))
            print()
    elif args.sector:
        print(score_sector(args.sector, top_n=args.top_n))
    else:
        parser.print_help()
