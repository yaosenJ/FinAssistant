#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财务对比分析工具
同行业多家公司横向对比、同一公司连续多期纵向对比

功能:
- 横向对比：多家公司同一报告期的关键财务指标并排比较
- 纵向对比：同一公司连续多期报表，计算环比/同比变化率
- 支持自动计算：毛利率、净利率、ROE、资产负债率等衍生指标

用法:
    from tools.financial_compare import compare_companies, compare_periods
    print(compare_companies(['600519.SH', '000858.SZ', '000568.SZ'], report_date='20251231'))
    print(compare_periods('600519.SH', periods=4))
"""

import json
import logging

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
        s = str(val).replace(',', '').replace('%', '').strip()
        if not s or s == '--' or s == '-':
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _extract_field(data, *field_names):
    """从报表数据中按优先级提取字段值"""
    if not data:
        return None
    for name in field_names:
        val = data.get(name)
        if val is not None:
            f = _safe_float(val)
            if f is not None:
                return f
    return None


def _format_val(val, suffix='%'):
    """格式化数值"""
    if val is None:
        return '--'
    if suffix == '%':
        return f"{val:+.2f}%" if val != 0 else "0.00%"
    if suffix == '亿':
        return f"{val / 1e8:,.2f}亿"
    return f"{val:,.2f}"


def _calc_indicators(income, balance, cashflow):
    """计算关键财务指标"""
    result = {}

    revenue = _extract_field(income, '营业总收入', '营业收入')
    cost = _extract_field(income, '营业成本')
    net_profit = _extract_field(income, '净利润', '归属于母公司所有者的净利润', '归属于母公司股东的净利润')
    total_assets = _extract_field(balance, '资产总计')
    total_liabilities = _extract_field(balance, '负债合计')
    equity = _extract_field(balance, '归属于母公司股东权益合计', '归属于母公司所有者权益', '所有者权益（或股东权益）合计')
    operating_cf = _extract_field(cashflow, '经营活动产生的现金流量净额')

    result['营业收入'] = revenue
    result['净利润'] = net_profit
    result['资产总计'] = total_assets

    if revenue and cost and revenue > 0:
        result['毛利率'] = round((revenue - cost) / revenue * 100, 2)
    if net_profit and revenue and revenue > 0:
        result['净利率'] = round(net_profit / revenue * 100, 2)
    if net_profit and equity and equity > 0:
        result['ROE'] = round(net_profit / equity * 100, 2)
    if total_liabilities and total_assets and total_assets > 0:
        result['资产负债率'] = round(total_liabilities / total_assets * 100, 2)
    if operating_cf is not None and net_profit and net_profit != 0:
        result['经营现金流/净利润'] = round(operating_cf / net_profit, 2)

    return result


def _get_report(ts_code, statement_type, report_date=None):
    """获取单张报表"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if report_date:
                sql = "SELECT report_data, report_date FROM stock_financial WHERE ts_code=%s AND statement_type=%s AND report_date=%s"
                cursor.execute(sql, (ts_code, statement_type, report_date))
            else:
                sql = "SELECT report_data, report_date FROM stock_financial WHERE ts_code=%s AND statement_type=%s ORDER BY report_date DESC LIMIT 1"
                cursor.execute(sql, (ts_code, statement_type))
            row = cursor.fetchone()
            if not row:
                return None, None
            data = row[0]
            if isinstance(data, str):
                data = json.loads(data)
            return data, row[1]
    finally:
        conn.close()


def _get_report_dates(ts_code, limit=5):
    """获取某公司可用的报告日期列表"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT report_date FROM stock_financial
                WHERE ts_code = %s AND statement_type = 'income'
                ORDER BY report_date DESC LIMIT %s
            """, (ts_code, limit))
            return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def _get_stock_name(ts_code):
    """获取股票名称"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT stock_name FROM company_info WHERE ts_code = %s LIMIT 1", (ts_code,))
            row = cursor.fetchone()
            return row[0] if row else ts_code
    finally:
        conn.close()


def _get_sector_constituents(sector_name, sector_type='industry'):
    """获取板块成分股 ts_code 列表"""
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    cons_table = 'sector_industry_cons' if sector_type == 'industry' else 'sector_concept_cons'

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 模糊搜索板块
            cursor.execute(f"SELECT DISTINCT sector_code, sector_name FROM {table} WHERE sector_name LIKE %s", (f'%{sector_name}%',))
            matches = cursor.fetchall()
            if not matches:
                return None, f"未找到板块: {sector_name}"
            exact = [m for m in matches if m[1] == sector_name]
            sector_code = exact[0][0] if exact else matches[0][0]
            sector_name_real = exact[0][1] if exact else matches[0][1]

            # 获取成分股
            cursor.execute(f"SELECT stock_code, stock_name FROM {cons_table} WHERE sector_code = %s", (sector_code,))
            return cursor.fetchall(), sector_name_real
    finally:
        conn.close()


def _stock_code_to_ts_code(stock_codes):
    """批量将纯数字代码转为 ts_code"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(stock_codes))
            cursor.execute(f"SELECT symbol, ts_code, stock_name FROM company_info WHERE symbol IN ({placeholders})", (*stock_codes,))
            return {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
    finally:
        conn.close()


def compare_companies(ts_codes=None, sector_name=None, sector_type='industry', report_date=None, report_type='income'):
    """
    多家公司财务指标横向对比

    指定 ts_codes 列表或板块名称，对比同一报告期的关键财务指标。

    Args:
        ts_codes: 股票代码列表，如 ['600519.SH', '000858.SZ']
        sector_name: 板块名称（与 ts_codes 二选一），自动取成分股
        sector_type: 'industry' 或 'concept'，默认 'industry'
        report_date: 报告日期（如 '20251231'），默认取最新一期
        report_type: 报表类型，默认 'income'（利润表相关指标）

    Returns:
        str: 格式化的横向对比结果
    """
    # 获取要对比的股票列表
    if sector_name and not ts_codes:
        constituents, sector_real = _get_sector_constituents(sector_name, sector_type)
        if isinstance(constituents, str):
            return constituents  # 错误信息
        stock_codes = [c[0] for c in constituents]
        code_map = _stock_code_to_ts_code(stock_codes)
        ts_codes = [v[0] for v in code_map.values()]
        if not ts_codes:
            return f"板块 [{sector_real}] 无成分股数据"
        label = f"板块: {sector_real}"
        # 成分股可能太多，取前20
        if len(ts_codes) > 20:
            ts_codes = ts_codes[:20]
            label += f"（前20只）"
    elif ts_codes:
        label = f"对比公司: {len(ts_codes)}家"
    else:
        return "请提供 ts_codes 列表或 sector_name"

    # 如果未指定报告日期，取第一只股票的最新日期
    if not report_date:
        dates = _get_report_dates(ts_codes[0], limit=1)
        if not dates:
            return f"未找到 {ts_codes[0]} 的财务数据"
        report_date = dates[0]

    # 收集每家公司的指标
    companies = []
    for ts_code in ts_codes:
        name = _get_stock_name(ts_code)
        income, rd = _get_report(ts_code, 'income', report_date)
        balance, _ = _get_report(ts_code, 'balance', report_date)
        cashflow, _ = _get_report(ts_code, 'cashflow', report_date)

        if not income and not balance:
            continue

        indicators = _calc_indicators(income, balance, cashflow)
        companies.append({
            'ts_code': ts_code,
            'name': name,
            'report_date': rd or report_date,
            **indicators,
        })

    if not companies:
        return f"报告期 {report_date} 无有效财务数据"

    # 格式化输出
    result = f"=== 财务横向对比 ===\n"
    result += f"{label}\n"
    result += f"报告期: {report_date}\n"
    result += f"对比公司: {len(companies)}家\n"

    # 对比指标表
    metrics = [
        ('营业收入', '亿'),
        ('净利润', '亿'),
        ('毛利率', '%'),
        ('净利率', '%'),
        ('ROE', '%'),
        ('资产负债率', '%'),
        ('经营现金流/净利润', ''),
    ]

    for metric_name, suffix in metrics:
        result += f"\n【{metric_name}】\n"
        # 收集有效值用于排序
        valid = [(c['name'], c.get(metric_name)) for c in companies if c.get(metric_name) is not None]
        if not valid:
            result += "  无有效数据\n"
            continue

        # 按值排序（降序）
        if metric_name in ('资产负债率',):
            valid.sort(key=lambda x: x[1])  # 升序（越低越好）
        else:
            valid.sort(key=lambda x: x[1], reverse=True)  # 降序（越高越好）

        for name, val in valid:
            if suffix == '亿':
                result += f"  {name:<12} {_format_val(val, '亿')}\n"
            elif suffix == '%':
                result += f"  {name:<12} {val:.2f}%\n"
            else:
                result += f"  {name:<12} {val:.2f}\n"

    # 排名汇总
    result += f"\n【排名汇总】\n"
    # 按 ROE 排名
    roe_sorted = sorted(companies, key=lambda c: c.get('ROE') or -9999, reverse=True)
    result += "  ROE排名: " + " > ".join([f"{c['name']}({c.get('ROE', '--')}%)" for c in roe_sorted[:5] if c.get('ROE') is not None]) + "\n"

    # 按毛利率排名
    gm_sorted = sorted(companies, key=lambda c: c.get('毛利率') or -9999, reverse=True)
    result += "  毛利率排名: " + " > ".join([f"{c['name']}({c.get('毛利率', '--')}%)" for c in gm_sorted[:5] if c.get('毛利率') is not None]) + "\n"

    return result


def compare_periods(ts_code, report_type='income', periods=4):
    """
    同一公司连续多期报表纵向对比

    获取最近N期报表数据，计算各指标的环比变化率。

    Args:
        ts_code: 股票代码（带后缀），如 '600519.SH'
        report_type: 报表类型，默认 'income'
                     可选：income(利润表)、balance(资产负债表)、cashflow(现金流量表)
        periods: 对比期数，默认4（最近4期）

    Returns:
        str: 格式化的纵向对比结果
    """
    name = _get_stock_name(ts_code)

    # 获取可用报告日期
    dates = _get_report_dates(ts_code, limit=periods)
    if not dates:
        return f"未找到 {ts_code} 的财务数据"

    dates = list(reversed(dates))  # 按时间正序

    # 收集每期数据
    reports = []
    for rd in dates:
        income, _ = _get_report(ts_code, 'income', rd)
        balance, _ = _get_report(ts_code, 'balance', rd)
        cashflow, _ = _get_report(ts_code, 'cashflow', rd)
        indicators = _calc_indicators(income, balance, cashflow)
        indicators['报告期'] = rd
        reports.append(indicators)

    if not reports:
        return f"未找到 {ts_code} 的有效报表数据"

    # 格式化输出
    type_cn = {'income': '利润表', 'balance': '资产负债表', 'cashflow': '现金流量表'}.get(report_type, report_type)
    result = f"=== {name}({ts_code}) 纵向对比 ===\n"
    result += f"报表类型: {type_cn}\n"
    result += f"对比期数: {len(reports)}期 ({dates[0]} ~ {dates[-1]})\n"

    # 对比指标
    if report_type == 'income':
        metrics = ['营业收入', '净利润', '毛利率', '净利率', 'ROE']
    elif report_type == 'balance':
        metrics = ['资产总计', '资产负债率']
    else:
        metrics = ['经营现金流/净利润']

    for metric in metrics:
        result += f"\n【{metric}】\n"
        result += f"  {'报告期':<12} {'当期值':<16} {'环比变化':<12}\n"
        result += f"  {'─' * 42}\n"

        prev_val = None
        for r in reports:
            rd = r['报告期']
            val = r.get(metric)

            # 格式化当期值
            if val is None:
                val_str = '--'
            elif metric in ('营业收入', '净利润'):
                val_str = _format_val(val, '亿')
            else:
                val_str = f"{val:.2f}%"

            # 计算环比变化
            chg_str = '--'
            if val is not None and prev_val is not None and prev_val != 0:
                chg = (val - prev_val) / abs(prev_val) * 100
                chg_str = f"{chg:+.2f}%"
            elif val is not None and prev_val is not None and prev_val == 0 and val != 0:
                chg_str = "N/A→有值"

            result += f"  {rd:<12} {val_str:<16} {chg_str:<12}\n"
            prev_val = val

    # 趋势判断
    result += f"\n【趋势判断】\n"
    for metric in metrics:
        values = [r.get(metric) for r in reports if r.get(metric) is not None]
        if len(values) < 2:
            continue
        # 判断趋势方向
        if values[-1] > values[0] * 1.05:
            trend = "↑ 上升趋势"
        elif values[-1] < values[0] * 0.95:
            trend = "↓ 下降趋势"
        else:
            trend = "→ 基本持平"
        result += f"  {metric}: {trend}\n"

    return result


if __name__ == '__main__':
    print("\n1. 白酒板块横向对比（最新一期）:")
    print(compare_companies(sector_name='白酒', report_date='20251231'))

    print("\n2. 贵州茅台纵向对比（最近4期）:")
    print(compare_periods('600519.SH', periods=4))
