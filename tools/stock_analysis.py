#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股全景分析工具
综合基本面、估值、技术面三个维度，生成专业的个股分析报告

依赖工具:
- tools.stock_fundamental: 基本面指标计算
- tools.stock_valuation: 估值分位分析
- tools.stock_technical: 技术指标计算

用法:
    from tools.stock_analysis import generate_stock_report
    print(generate_stock_report('600519.SH'))
    print(generate_stock_report('600519.SH', report_type='detail'))
"""

from tools.stock_fundamental import calc_fundamental_indicators, calc_fundamental_trend
from tools.stock_valuation import calc_valuation_percentile
from tools.stock_technical import calc_technical_indicators


def _rate_fundamental(data):
    """基本面评级

    评级标准:
    - 优秀: ROE>15%, 毛利率>40%, 经营现金流净利润比>0.8, 营收同比增长>10%
    - 良好: ROE>10%, 毛利率>30%, 经营现金流净利润比>0.5, 营收同比增长>0%
    - 一般: ROE>5%, 毛利率>20%, 经营现金流净利润比>0
    - 较差: 其他

    Returns:
        str: '优秀' / '良好' / '一般' / '较差'
    """
    roe = data.get('ROE', 0) or 0
    margin = data.get('毛利率', 0) or 0
    cf_ratio = data.get('经营现金流净利润比', 0) or 0
    revenue_growth = data.get('营收同比增长率', 0) or 0

    if roe > 15 and margin > 40 and cf_ratio > 0.8 and revenue_growth > 10:
        return '优秀'
    elif roe > 10 and margin > 30 and cf_ratio > 0.5 and revenue_growth > 0:
        return '良好'
    elif roe > 5 and margin > 20 and cf_ratio > 0:
        return '一般'
    else:
        return '较差'


def _rate_valuation(data):
    """估值评级

    评级标准:
    - 低估: PE/PB/PCF百分位均值<30%
    - 合理偏低: 30%-50%
    - 合理: 50%-70%
    - 合理偏高: 70%-80%
    - 高估: >80%

    Returns:
        str: '低估' / '合理偏低' / '合理' / '合理偏高' / '高估'
    """
    pe_pct = data.get('pe_ttm_percentile', 50) or 50
    pb_pct = data.get('pb_percentile', 50) or 50
    pcf_pct = data.get('pcf_percentile', 50) or 50
    avg_pct = (pe_pct + pb_pct + pcf_pct) / 3

    if avg_pct < 30:
        return '低估'
    elif avg_pct < 50:
        return '合理偏低'
    elif avg_pct < 70:
        return '合理'
    elif avg_pct < 80:
        return '合理偏高'
    else:
        return '高估'


def _rate_technical(data):
    """技术面评级

    评级标准:
    - 强势: MA多头排列 + MACD金叉 + RSI在40-70区间
    - 偏强: MA多头排列 或 MACD金叉
    - 中性: 无明显多空信号
    - 偏弱: MA空头排列 或 MACD死叉
    - 弱势: MA空头排列 + MACD死叉

    Returns:
        str: '强势' / '偏强' / '中性' / '偏弱' / '弱势'
    """
    ma_trend = data.get('ma_trend', '')
    macd_signal = data.get('macd_signal', '')
    rsi = data.get('rsi6', 50) or 50

    if ma_trend == '多头排列' and macd_signal == '金叉' and 40 < rsi < 70:
        return '强势'
    elif ma_trend == '多头排列' and macd_signal == '金叉':
        return '偏强'
    elif ma_trend == '多头排列' or macd_signal == '金叉':
        return '偏强'
    elif ma_trend == '空头排列' and macd_signal == '死叉':
        return '弱势'
    elif ma_trend == '空头排列' or macd_signal == '死叉':
        return '偏弱'
    else:
        return '中性'


def _get_suggestion(fundamental_level, valuation_level, technical_level):
    """综合建议

    Returns:
        str: '买入' / '持有' / '观望' / '减持'
    """
    scores = {
        '优秀': 4, '良好': 3, '一般': 2, '较差': 1,
        '低估': 5, '合理偏低': 4, '合理': 3, '合理偏高': 2, '高估': 1,
        '强势': 5, '偏强': 4, '中性': 3, '偏弱': 2, '弱势': 1,
    }

    f_score = scores.get(fundamental_level, 2)
    v_score = scores.get(valuation_level, 3)
    t_score = scores.get(technical_level, 3)

    # 加权: 基本面40% + 估值30% + 技术面30%
    total = f_score * 0.4 + v_score * 0.3 + t_score * 0.3

    if total >= 4.0:
        return '买入'
    elif total >= 3.0:
        return '持有'
    elif total >= 2.0:
        return '观望'
    else:
        return '减持'


def _format_value(val, suffix='', default='-'):
    """格式化数值"""
    if val is None:
        return default
    return f"{val}{suffix}"


def generate_stock_report(ts_code, report_type='brief'):
    """生成个股全景分析报告

    Args:
        ts_code: 股票代码，如 600519.SH
        report_type: 报告类型，brief(简要) / detail(详细)

    Returns:
        str: 格式化的分析报告
    """
    # Step 1: 获取基本面数据
    fundamental = calc_fundamental_indicators(ts_code)
    if 'error' in fundamental:
        return f"无法生成报告: {fundamental['error']}"

    # Step 2: 获取估值数据
    valuation = calc_valuation_percentile(ts_code)

    # Step 3: 获取技术指标
    technical = calc_technical_indicators(ts_code)

    # Step 4: 综合评级
    fundamental_level = _rate_fundamental(fundamental)
    valuation_level = _rate_valuation(valuation) if 'error' not in valuation else '-'
    technical_level = _rate_technical(technical) if 'error' not in technical else '-'
    suggestion = _get_suggestion(fundamental_level, valuation_level, technical_level)

    # Step 5: 生成报告
    report_date = technical.get('trade_date', '-')
    close_price = _format_value(technical.get('close'), '')

    lines = [
        "═" * 65,
        f"          {ts_code} 个股全景分析报告",
        "═" * 65,
        f"报告日期: {report_date}",
        f"最新收盘: {close_price}",
        "",
        "┌─────────────────────────────────────────────────────────────┐",
        "│                        综合评级                             │",
        "├─────────────────────────────────────────────────────────────┤",
        f"│  基本面: {fundamental_level:<8}  估值: {valuation_level:<8}  技术面: {technical_level:<8}  │",
        f"│  综合建议: {suggestion:<10}                                  │",
        "└─────────────────────────────────────────────────────────────┘",
        "",
        "一、基本面分析",
        "─" * 50,
        f"  ROE: {_format_value(fundamental.get('ROE'), '%'):<16}  毛利率: {_format_value(fundamental.get('毛利率'), '%')}",
        f"  净利率: {_format_value(fundamental.get('净利率'), '%'):<14}  资产负债率: {_format_value(fundamental.get('资产负债率'), '%')}",
        f"  经营现金流/净利润: {_format_value(fundamental.get('经营现金流净利润比'))}",
        "",
        "  增长情况:",
        f"  - 营收同比增长: {_format_value(fundamental.get('营收同比增长率'), '%')}",
        f"  - 净利润同比增长: {_format_value(fundamental.get('净利润同比增长率'), '%')}",
        f"  - 营收环比增长: {_format_value(fundamental.get('营收环比增长率'), '%')}",
        f"  - 净利润环比增长: {_format_value(fundamental.get('净利润环比增长率'), '%')}",
    ]

    # 基本面点评
    if fundamental_level == '优秀':
        lines.append(f"\n  基本面点评: 盈利能力突出，现金流充沛，成长性良好。")
    elif fundamental_level == '良好':
        lines.append(f"\n  基本面点评: 盈利能力稳健，财务状况健康。")
    elif fundamental_level == '一般':
        lines.append(f"\n  基本面点评: 盈利能力一般，需关注财务健康度。")
    else:
        lines.append(f"\n  基本面点评: 盈利能力较弱，存在财务风险。")

    # 估值分析
    if 'error' not in valuation:
        lines.extend([
            "",
            "二、估值分析",
            "─" * 50,
            f"  PE_TTM: {_format_value(valuation.get('pe_ttm')):<12} (百分位: {_format_value(valuation.get('pe_ttm_percentile'), '%')}, {valuation.get('pe_ttm_level', '-')})",
            f"  PB: {_format_value(valuation.get('pb')):<15} (百分位: {_format_value(valuation.get('pb_percentile'), '%')}, {valuation.get('pb_level', '-')})",
            f"  PCF: {_format_value(valuation.get('pcf')):<14} (百分位: {_format_value(valuation.get('pcf_percentile'), '%')}, {valuation.get('pcf_level', '-')})",
        ])

        if valuation_level in ['低估', '合理偏低']:
            lines.append(f"\n  估值点评: 当前估值处于历史低位，具有安全边际。")
        elif valuation_level == '合理':
            lines.append(f"\n  估值点评: 当前估值处于合理区间。")
        else:
            lines.append(f"\n  估值点评: 当前估值偏高，需注意估值回调风险。")

    # 技术面分析
    if 'error' not in technical:
        lines.extend([
            "",
            "三、技术面分析",
            "─" * 50,
            f"  均线趋势: {technical.get('ma_trend', '-')}",
            f"  MACD: {technical.get('macd_signal', '-')} (DIF={_format_value(technical.get('macd_dif'))}, DEA={_format_value(technical.get('macd_dea'))})",
            f"  RSI(6): {_format_value(technical.get('rsi6'))} ({technical.get('rsi6_signal', '-')})",
            f"  KDJ: K={_format_value(technical.get('kdj_k'))} D={_format_value(technical.get('kdj_d'))} J={_format_value(technical.get('kdj_j'))} ({technical.get('kdj_signal', '-')})",
        ])

        if technical_level in ['强势', '偏强']:
            lines.append(f"\n  技术面点评: 短期趋势向上，技术形态良好。")
        elif technical_level == '中性':
            lines.append(f"\n  技术面点评: 技术面中性，无明显方向信号。")
        else:
            lines.append(f"\n  技术面点评: 短期趋势偏弱，注意技术性回调风险。")

    # 详细报告增加趋势分析
    if report_type == 'detail':
        trend = calc_fundamental_trend(ts_code, periods=4)
        if 'trend' in trend and trend['trend']:
            lines.extend([
                "",
                "四、基本面趋势（最近4期）",
                "─" * 50,
                f"  {'报告期':<12} {'ROE':<8} {'毛利率':<8} {'营收同比':<10} {'净利同比':<10}",
            ])
            for t in trend['trend']:
                lines.append(
                    f"  {t.get('report_date', '-'):<12} "
                    f"{_format_value(t.get('ROE'), '%'):<8} "
                    f"{_format_value(t.get('毛利率'), '%'):<8} "
                    f"{_format_value(t.get('营收同比增长率'), '%'):<10} "
                    f"{_format_value(t.get('净利润同比增长率'), '%'):<10}"
                )

    # 风险提示
    risks = []
    if 'error' not in technical:
        rsi = technical.get('rsi6', 50) or 50
        if rsi > 80:
            risks.append("RSI超买，短期存在技术性回调压力")
        elif rsi < 20:
            risks.append("RSI超卖，可能存在反弹但趋势仍弱")

    if 'error' not in valuation:
        avg_pct = ((valuation.get('pe_ttm_percentile', 50) or 50) +
                   (valuation.get('pb_percentile', 50) or 50) +
                   (valuation.get('pcf_percentile', 50) or 50)) / 3
        if avg_pct > 70:
            risks.append("估值处于历史高位，注意估值回调风险")

    revenue_growth = fundamental.get('营收同比增长率', 0) or 0
    if revenue_growth < 0:
        risks.append("营收同比下滑，需关注业绩持续性")

    if risks:
        lines.extend([
            "",
            "四、风险提示" if report_type != 'detail' else "五、风险提示",
            "─" * 50,
        ])
        for risk in risks:
            lines.append(f"  - {risk}")

    lines.extend([
        "",
        "═" * 65,
        "免责声明: 本报告基于公开数据自动生成，仅供参考，不构成投资建议。",
        "═" * 65,
    ])

    return "\n".join(lines)


if __name__ == '__main__':
    # 测试
    print("=" * 60)
    print("个股全景分析报告测试")
    print("=" * 60)

    # 简要报告
    print("\n--- 简要报告 ---")
    print(generate_stock_report('600519.SH', report_type='brief'))

    # 详细报告
    print("\n--- 详细报告 ---")
    print(generate_stock_report('600519.SH', report_type='detail'))
