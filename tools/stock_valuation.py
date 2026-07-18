#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
估值分位分析工具
从 MySQL market_data.stock_kline 表获取 PE/PB/PCF 历史数据，计算估值百分位

═══════════════════════════════════════════════════════════════════
估值指标详解
═══════════════════════════════════════════════════════════════════

1. PE_TTM（滚动市盈率, Price-to-Earnings Trailing Twelve Months）
─────────────────────────────────────────────────────────────────
   公式: 股价 / 每股收益（最近12个月累计）

   选股用途:
   - 判断估值高低: PE越低，说明买同样的利润越便宜
   - 跨行业对比: 同行业公司PE差异大，可能意味着估值洼地或基本面问题
   - 成长性筛选: 高成长股PE通常较高（市场愿意给溢价），低PE可能意味着增长乏力

   局限:
   - 亏损公司PE为负，无法使用
   - 周期股PE低点可能是业绩顶点（买在山顶）

2. PB（市净率, Price-to-Book）
─────────────────────────────────────────────────────────────────
   公式: 股价 / 每股净资产

   选股用途:
   - 资产型公司首选: 银行、地产、钢铁等重资产行业，PB更能反映真实价值
   - 破净（PB<1）筛选: 股价低于每股净资产，可能是被低估的"便宜货"
   - 安全边际判断: PB越低，下跌空间理论上越有限

   局限:
   - 轻资产公司（科技、消费）PB普遍较高，不适用
   - 净资产质量需关注（商誉、应收账款可能虚增净资产）

3. PCF（市现率, Price-to-Cash-Flow）
─────────────────────────────────────────────────────────────────
   公式: 股价 / 每股经营现金流

   选股用途:
   - 现金流验证: 利润可以调节，现金流很难造假，PCF比PE更真实
   - 识别"纸面富贵": PE低但PCF高，说明利润质量差（可能是应收账款堆出来的）
   - 高分红潜力: PCF低的公司现金流充裕，更有能力分红

   局限:
   - 现金流波动大，单期数据可能失真
   - 扩张期公司现金流为负，PCF不适用

═══════════════════════════════════════════════════════════════════
三指标联合选股思路
═══════════════════════════════════════════════════════════════════

   ┌─────────────────────┬──────────────────────────────┬──────────────────┐
   │ 筛选条件            │ 含义                         │ 适合标的         │
   ├─────────────────────┼──────────────────────────────┼──────────────────┤
   │ PE低 + PB低         │ 便宜且有资产兜底             │ 银行、公用事业   │
   │ PE低 + PCF低        │ 便宜且利润质量高             │ 消费、医药龙头   │
   │ PE高 + PCF低        │ 利润好但市场给溢价           │ 高成长科技股     │
   │ PB<1 + PCF低        │ 破净且现金流好               │ 深度价值股       │
   └─────────────────────┴──────────────────────────────┴──────────────────┘

   核心原则: 单一指标容易踩坑，三个指标交叉验证更可靠。

═══════════════════════════════════════════════════════════════════
百分位计算与估值判断
═══════════════════════════════════════════════════════════════════

   百分位 = 当前值在近N年历史序列中的排名位置

   ┌──────────────┬────────────┬──────────────────────────────────┐
   │ 百分位       │ 估值水平   │ 含义                             │
   ├──────────────┼────────────┼──────────────────────────────────┤
   │ < 20%        │ 低估       │ 处于历史低位，可能被低估         │
   │ 20% - 40%    │ 合理偏低   │ 低于历史中位数                   │
   │ 40% - 60%    │ 合理       │ 处于历史中位区间                 │
   │ 60% - 80%    │ 合理偏高   │ 高于历史中位数                   │
   │ > 80%        │ 高估       │ 处于历史高位，可能被高估         │
   └──────────────┴────────────┴──────────────────────────────────┘

数据来源: market_data.stock_kline 表

   -- 估值指标:
   -- PE_TTM（滚动市盈率）= 股价 / 每股收益(TTM)
   -- PB（市净率）= 股价 / 每股净资产
   -- PCF（市现率）= 股价 / 每股现金流

用法:
    from tools.stock_valuation import calc_valuation_percentile, calc_valuation_summary
    result = calc_valuation_percentile('600519.SH')
    print(result)  # {'pe_ttm': 19.03, 'pe_ttm_percentile': 21.88, 'pe_ttm_level': '合理偏低', ...}

示例输出（贵州茅台 2026-07-16）:
    PE_TTM: 19.03, 百分位: 21.88%, 合理偏低 (历史区间: 17.66 - 22.19)
    PB:     5.81,  百分位: 17.19%, 低估     (历史区间: 5.39 - 7.57)
    PCF:    25.58, 百分位: 69.53%, 合理偏高 (历史区间: 17.93 - 29.69)
"""

import logging
from datetime import datetime, timedelta

try:
    from tools.db import get_connection
except ImportError:
    from db import get_connection

logger = logging.getLogger(__name__)


def _safe_float(val):
    """安全转 float"""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _calc_percentile(current, values):
    """计算当前值在序列中的百分位

    百分位 = (小于当前值的个数 / 总个数) × 100

    Args:
        current: 当前值
        values: 历史值列表

    Returns:
        float: 百分位（0-100）
    """
    if not values or current is None:
        return None

    valid_values = [v for v in values if v is not None]
    if not valid_values:
        return None

    # 计算小于当前值的个数
    count_below = sum(1 for v in valid_values if v < current)
    percentile = round(count_below / len(valid_values) * 100, 2)

    return percentile


def _get_valuation_level(percentile):
    """根据百分位判断估值水平

    Args:
        percentile: 百分位（0-100）

    Returns:
        str: '低估' / '合理偏低' / '合理' / '合理偏高' / '高估'
    """
    if percentile is None:
        return None
    if percentile < 20:
        return '低估'
    elif percentile < 40:
        return '合理偏低'
    elif percentile < 60:
        return '合理'
    elif percentile < 80:
        return '合理偏高'
    else:
        return '高估'


def get_valuation_history(ts_code, days=365):
    """从MySQL获取近N天的估值数据

    Args:
        ts_code: 股票代码，如 600519.SH
        days: 历史天数，默认365天（1年）

    Returns:
        list: [{'trade_date': '2026-07-18', 'pe_ttm': 65.2, 'pb': 12.5, 'pcf': 45.3}, ...]
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 计算起始日期
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            sql = """
                SELECT trade_date, pe_ttm, pb, pcf
                FROM stock_kline
                WHERE ts_code = %s
                  AND trade_date >= %s
                  AND (pe_ttm IS NOT NULL OR pb IS NOT NULL OR pcf IS NOT NULL)
                ORDER BY trade_date
            """
            cursor.execute(sql, (ts_code, start_date))
            rows = cursor.fetchall()

            if not rows:
                return []

            result = []
            for row in rows:
                result.append({
                    'trade_date': str(row[0]),
                    'pe_ttm': _safe_float(row[1]),
                    'pb': _safe_float(row[2]),
                    'pcf': _safe_float(row[3]),
                })

            return result
    finally:
        conn.close()


def get_latest_valuation(ts_code):
    """获取最新一天的估值数据

    Args:
        ts_code: 股票代码

    Returns:
        dict: {'trade_date': '2026-07-18', 'pe_ttm': 65.2, '、': 12.5, 'pcf': 45.3}
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT trade_date, pe_ttm, pb, pcf
                FROM stock_kline
                WHERE ts_code = %s
                  AND (pe_ttm IS NOT NULL OR pb IS NOT NULL OR pcf IS NOT NULL)
                ORDER BY trade_date DESC
                LIMIT 1
            """
            cursor.execute(sql, (ts_code,))
            row = cursor.fetchone()

            if not row:
                return None

            return {
                'trade_date': str(row[0]),
                'pe_ttm': _safe_float(row[1]),
                'pb': _safe_float(row[2]),
                'pcf': _safe_float(row[3]),
            }
    finally:
        conn.close()


def calc_valuation_percentile(ts_code, days=365):
    """计算估值百分位

    Args:
        ts_code: 股票代码，如 600519.SH
        days: 历史天数，默认365天（1年）

    Returns:
        dict: {
            ts_code, trade_date,
            pe_ttm, pe_ttm_percentile, pe_ttm_level,
            pb, pb_percentile, pb_level,
            pcf, pcf_percentile, pcf_level,
            history_days: 历史数据天数
        }
    """
    # 获取最新估值
    latest = get_latest_valuation(ts_code)
    if not latest:
        return {'ts_code': ts_code, 'error': '无估值数据'}

    # 获取历史估值
    history = get_valuation_history(ts_code, days)
    if not history:
        return {'ts_code': ts_code, 'error': '无历史估值数据'}

    # 提取各指标的历史序列
    pe_values = [h['pe_ttm'] for h in history if h['pe_ttm'] is not None]
    pb_values = [h['pb'] for h in history if h['pb'] is not None]
    pcf_values = [h['pcf'] for h in history if h['pcf'] is not None]

    # 计算百分位
    pe_percentile = _calc_percentile(latest['pe_ttm'], pe_values)
    pb_percentile = _calc_percentile(latest['pb'], pb_values)
    pcf_percentile = _calc_percentile(latest['pcf'], pcf_values)

    # 计算统计值
    def _calc_stats(values):
        if not values:
            return None, None, None
        return round(min(values), 2), round(max(values), 2), round(sum(values) / len(values), 2)

    pe_min, pe_max, pe_avg = _calc_stats(pe_values)
    pb_min, pb_max, pb_avg = _calc_stats(pb_values)
    pcf_min, pcf_max, pcf_avg = _calc_stats(pcf_values)

    result = {
        'ts_code': ts_code,
        'trade_date': latest['trade_date'],
        'history_days': len(history),

        # PE_TTM
        'pe_ttm': latest['pe_ttm'],
        'pe_ttm_percentile': pe_percentile,
        'pe_ttm_level': _get_valuation_level(pe_percentile),
        'pe_ttm_min': pe_min,
        'pe_ttm_max': pe_max,
        'pe_ttm_avg': pe_avg,

        # PB
        'pb': latest['pb'],
        'pb_percentile': pb_percentile,
        'pb_level': _get_valuation_level(pb_percentile),
        'pb_min': pb_min,
        'pb_max': pb_max,
        'pb_avg': pb_avg,

        # PCF
        'pcf': latest['pcf'],
        'pcf_percentile': pcf_percentile,
        'pcf_level': _get_valuation_level(pcf_percentile),
        'pcf_min': pcf_min,
        'pcf_max': pcf_max,
        'pcf_avg': pcf_avg,
    }

    return result


def calc_valuation_summary(ts_code, days=365):
    """生成估值摘要（适合直接输出）

    Args:
        ts_code: 股票代码
        days: 历史天数

    Returns:
        str: 格式化的估值摘要文本
    """
    result = calc_valuation_percentile(ts_code, days)

    if 'error' in result:
        return f"{ts_code}: {result['error']}"

    lines = [
        f"=== {ts_code} 估值分析 ({result['trade_date']}) ===",
        f"历史数据: 近{result['history_days']}个交易日",
        "",
        f"【PE_TTM（滚动市盈率）】",
        f"  当前值: {result['pe_ttm']}",
        f"  百分位: {result['pe_ttm_percentile']}%",
        f"  估值水平: {result['pe_ttm_level']}",
        f"  历史区间: {result['pe_ttm_min']} - {result['pe_ttm_max']}（均值{result['pe_ttm_avg']}）",
        "",
        f"【PB（市净率）】",
        f"  当前值: {result['pb']}",
        f"  百分位: {result['pb_percentile']}%",
        f"  估值水平: {result['pb_level']}",
        f"  历史区间: {result['pb_min']} - {result['pb_max']}（均值{result['pb_avg']}）",
        "",
        f"【PCF（市现率）】",
        f"  当前值: {result['pcf']}",
        f"  百分位: {result['pcf_percentile']}%",
        f"  估值水平: {result['pcf_level']}",
        f"  历史区间: {result['pcf_min']} - {result['pcf_max']}（均值{result['pcf_avg']}）",
    ]

    return "\n".join(lines)


if __name__ == '__main__':
    import json

    test_stocks = [
        ('600519.SH', '贵州茅台'),
        ('000858.SZ', '五粮液'),
        ('300750.SZ', '宁德时代'),
    ]

    print("=" * 60)
    print("估值分位分析测试")
    print("=" * 60)

    for code, name in test_stocks:
        print(f"\n--- {name} ({code}) ---")
        result = calc_valuation_percentile(code)
        # 隐藏内部字段
        display = {k: v for k, v in result.items() if not k.startswith('_')}
        print(json.dumps(display, ensure_ascii=False, indent=2))

    # 测试摘要输出
    print("\n" + "=" * 60)
    print("估值摘要测试")
    print("=" * 60)
    print(calc_valuation_summary('600519.SH'))
