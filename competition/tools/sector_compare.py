#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块对比工具
多板块同期涨跌曲线叠加对比

功能:
- 多板块累计涨跌幅对比
- 归一化处理（以起始日为基准=0%）
- 输出文本表格 + ASCII 趋势图

用法:
    from tools.sector_compare import compare_sectors, compare_sector_trend
    print(compare_sectors(['白酒', '电力', '银行'], sector_type='industry', days=20))
"""

import logging

try:
    from tools.db import get_connection
except ImportError:
    from db import get_connection

logger = logging.getLogger(__name__)


def _get_latest_trade_date(sector_type='industry'):
    """获取最新交易日期"""
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT MAX(trade_date) FROM {table}")
            result = cursor.fetchone()
            return result[0] if result else None
    finally:
        conn.close()


def _get_trade_dates(sector_type='industry', days=20):
    """获取最近N个交易日"""
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT DISTINCT trade_date FROM {table}
                ORDER BY trade_date DESC
                LIMIT %s
            """, (days,))
            return sorted([row[0] for row in cursor.fetchall()])
    finally:
        conn.close()


def _search_sector_code(sector_type, keyword):
    """根据关键词模糊搜索板块代码"""
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT DISTINCT sector_code, sector_name
                FROM {table}
                WHERE sector_name LIKE %s
                LIMIT 5
            """, (f'%{keyword}%',))
            return cursor.fetchall()
    finally:
        conn.close()


def _get_sector_daily_data(sector_type, sector_codes, trade_dates):
    """获取多个板块在指定日期的日K线数据"""
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            code_placeholders = ','.join(['%s'] * len(sector_codes))
            date_placeholders = ','.join(['%s'] * len(trade_dates))
            cursor.execute(f"""
                SELECT sector_code, sector_name, trade_date, close, pct_chg
                FROM {table}
                WHERE sector_code IN ({code_placeholders})
                  AND trade_date IN ({date_placeholders})
                ORDER BY trade_date
            """, (*sector_codes, *trade_dates))

            # {code: {date: (name, close, pct_chg)}}
            data = {}
            for row in cursor.fetchall():
                code, name, date, close, pct_chg = row
                if code not in data:
                    data[code] = {'name': name, 'daily': {}}
                data[code]['daily'][date] = (float(close or 0), float(pct_chg or 0))
            return data
    finally:
        conn.close()


def compare_sectors(sector_names, sector_type='industry', days=20):
    """
    多板块同期涨跌对比

    Args:
        sector_names: 板块名称列表，如 ['白酒', '电力', '银行']
        sector_type: 'industry'（行业）或 'concept'（概念）
        days: 对比天数

    Returns:
        str: 格式化的对比结果（含数据表格）
    """
    type_name = '行业' if sector_type == 'industry' else '概念'

    # 获取交易日期
    trade_dates = _get_trade_dates(sector_type, days)
    if len(trade_dates) < 2:
        return f"数据不足，需要至少2个交易日"

    # 解析板块名称 -> 代码
    resolved = []
    not_found = []
    for name in sector_names:
        matches = _search_sector_code(sector_type, name)
        if not matches:
            not_found.append(name)
        else:
            # 优先精确匹配，否则取第一个
            exact = [m for m in matches if m[1] == name]
            if exact:
                resolved.append(exact[0])
            else:
                resolved.append(matches[0])

    if not_found:
        return f"未找到{type_name}板块: {', '.join(not_found)}"

    sector_codes = [r[0] for r in resolved]
    code_name_map = {r[0]: r[1] for r in resolved}

    # 获取数据
    raw_data = _get_sector_daily_data(sector_type, sector_codes, trade_dates)

    if not raw_data:
        return f"无数据"

    # 计算累计涨跌幅（归一化到起始日=0%）
    # {code: [(date, cum_pct)]}
    series = {}
    for code in sector_codes:
        if code not in raw_data:
            continue
        daily = raw_data[code]['daily']
        cum = 0.0
        points = []
        for date in trade_dates:
            if date in daily:
                _, pct = daily[date]
                cum += pct
            points.append((date, cum))
        series[code] = points

    # 格式化输出
    date_range = f"{trade_dates[0]}~{trade_dates[-1]}"
    result = f"=== {type_name}板块涨跌对比 ===\n"
    result += f"对比周期: {date_range} ({len(trade_dates)}个交易日)\n"
    result += f"基准: 以首日为0%，展示累计涨跌幅\n\n"

    # 表格输出
    names = [code_name_map.get(c, c) for c in sector_codes if c in series]
    codes = [c for c in sector_codes if c in series]

    # 表头
    header = f"{'日期':<12}"
    for name in names:
        header += f" {name:<10}"
    result += header + "\n"
    result += "-" * (12 + 10 * len(names)) + "\n"

    # 数据行（每行一个日期）
    for i, date in enumerate(trade_dates):
        row = f"{date:<12}"
        for code in codes:
            if code in series:
                _, cum_pct = series[code][i]
                row += f" {cum_pct:>+8.2f}% "
            else:
                row += f" {'N/A':>8} "
        result += row + "\n"

    # 最终涨跌幅
    result += "\n" + "=" * (12 + 10 * len(names)) + "\n"
    final_row = f"{'累计涨跌幅':<10}"
    for code in codes:
        if code in series:
            _, final_pct = series[code][-1]
            final_row += f" {final_pct:>+8.2f}% "
        else:
            final_row += f" {'N/A':>8} "
    result += final_row + "\n"

    # ASCII 趋势图
    result += "\n" + _render_ascii_chart(series, codes, code_name_map, trade_dates)

    return result


def _render_ascii_chart(series, codes, code_name_map, trade_dates, width=60, height=15):
    """渲染ASCII趋势图"""
    # 收集所有数据点
    all_values = []
    for code in codes:
        if code in series:
            all_values.extend(v for _, v in series[code])

    if not all_values:
        return ""

    min_val = min(all_values)
    max_val = max(all_values)
    val_range = max_val - min_val if max_val != min_val else 1

    # 符号列表（不同板块用不同符号）
    symbols = ['*', '#', '@', '+', 'o', 'x', '%', '&']
    names = [code_name_map.get(c, c) for c in codes]

    result = "【趋势图】\n"
    result += f"  Y轴: 累计涨跌幅(%)  X轴: 交易日\n\n"

    # 按行渲染（从上到下）
    for row in range(height, -1, -1):
        threshold = min_val + (row / height) * val_range
        # Y轴标签
        if row == height:
            label = f"{max_val:>+6.1f}"
        elif row == 0:
            label = f"{min_val:>+6.1f}"
        elif row == height // 2:
            label = f"{(max_val + min_val) / 2:>+6.1f}"
        else:
            label = "      "

        line = f"{label} |"
        for i, date in enumerate(trade_dates):
            col_char = ' '
            for si, code in enumerate(codes):
                if code not in series:
                    continue
                _, val = series[code][i]
                # 判断该值是否在当前行的阈值附近
                if abs(val - threshold) < val_range / height / 2:
                    col_char = symbols[si % len(symbols)]
                    break
            line += col_char
        result += line + "\n"

    # X轴
    result += "       +" + "-" * len(trade_dates) + "\n"
    # 只显示首尾日期
    first_date = trade_dates[0][5:]  # 去掉年份
    last_date = trade_dates[-1][5:]
    x_label = "        " + first_date + " " * (len(trade_dates) - len(first_date) - len(last_date)) + last_date
    result += x_label + "\n"

    # 图例
    result += "\n  图例:\n"
    for si, name in enumerate(names):
        result += f"    {symbols[si % len(symbols)]} = {name}\n"

    return result


def compare_sector_trend(sector_names, sector_type='industry', days=20):
    """
    多板块趋势强度对比（简化版，仅输出对比结论）

    Args:
        sector_names: 板块名称列表
        sector_type: 'industry' 或 'concept'
        days: 对比天数

    Returns:
        str: 趋势对比结论
    """
    type_name = '行业' if sector_type == 'industry' else '概念'
    trade_dates = _get_trade_dates(sector_type, days)
    if len(trade_dates) < 2:
        return f"数据不足"

    resolved = []
    for name in sector_names:
        matches = _search_sector_code(sector_type, name)
        if matches:
            exact = [m for m in matches if m[1] == name]
            resolved.append(exact[0] if exact else matches[0])

    sector_codes = [r[0] for r in resolved]
    code_name_map = {r[0]: r[1] for r in resolved}
    raw_data = _get_sector_daily_data(sector_type, sector_codes, trade_dates)

    # 计算各板块指标
    stats = []
    for code in sector_codes:
        if code not in raw_data:
            continue
        daily = raw_data[code]['daily']
        cum = 0.0
        values = []
        up_days = 0
        for date in trade_dates:
            if date in daily:
                _, pct = daily[date]
                cum += pct
                values.append(pct)
                if pct > 0:
                    up_days += 1

        name = code_name_map.get(code, code)
        total_days = len(values)
        stats.append({
            'name': name,
            'cum_pct': cum,
            'avg_pct': cum / total_days if total_days else 0,
            'up_days': up_days,
            'total_days': total_days,
            'max_gain': max(values) if values else 0,
            'max_loss': min(values) if values else 0,
            'volatility': (max(values) - min(values)) if values else 0,
        })

    if not stats:
        return f"无数据"

    # 排序
    stats.sort(key=lambda x: x['cum_pct'], reverse=True)

    date_range = f"{trade_dates[0]}~{trade_dates[-1]}"
    result = f"=== {type_name}板块趋势对比 ({date_range}) ===\n\n"

    result += f"{'板块':<12} {'累计涨幅':<10} {'日均涨幅':<10} {'上涨天数':<10} {'波动幅度':<10}\n"
    result += "-" * 54 + "\n"

    for s in stats:
        days_str = f"{s['up_days']}/{s['total_days']}"
        result += f"{s['name']:<12} {s['cum_pct']:>+8.2f}%  {s['avg_pct']:>+8.2f}%  {days_str:<10} {s['volatility']:<10.2f}\n"

    # 结论
    best = stats[0]
    worst = stats[-1]
    result += f"\n【结论】\n"
    result += f"  最强: {best['name']}，累计涨幅 {best['cum_pct']:+.2f}%，上涨{best['up_days']}/{best['total_days']}天\n"
    result += f"  最弱: {worst['name']}，累计涨幅 {worst['cum_pct']:+.2f}%，上涨{worst['up_days']}/{worst['total_days']}天\n"

    if len(stats) >= 2:
        diff = best['cum_pct'] - worst['cum_pct']
        result += f"  强弱差: {diff:.2f}%，资金明显偏好{best['name']}方向\n"

    return result


if __name__ == '__main__':
    print("\n1. 白酒 vs 电力 vs 银行 涨跌对比(20日):")
    print(compare_sectors(['白酒', '电力', '银行'], sector_type='industry', days=20))

    print("\n2. 趋势强度对比:")
    print(compare_sector_trend(['白酒', '电力', '银行', '证券'], sector_type='industry', days=20))
