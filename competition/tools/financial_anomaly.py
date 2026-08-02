#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财务异常指标检测工具
检测上市公司财务报表中的异常信号

检测维度:
- 经营现金流骤降：净利润增长但经营现金流大幅下降
- 应收账款激增：应收账款增速远超营收增速
- 商誉减值风险：商誉占净资产比例过高
- 存货异常增长：存货增速远超营收增速
- 负债率飙升：资产负债率短期大幅上升
- 净利润与现金流背离：连续多期净利润有但现金流为负
- 毛利率异常波动：毛利率大幅下降

用法:
    from tools.financial_anomaly import detect_anomalies, detect_sector_anomalies
    print(detect_anomalies('600519.SH'))
    print(detect_sector_anomalies('白酒'))
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


def _get_prev_report(ts_code, statement_type, current_report_date):
    """获取上一期报表"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """SELECT report_data, report_date FROM stock_financial
                     WHERE ts_code=%s AND statement_type=%s AND report_date < %s
                     ORDER BY report_date DESC LIMIT 1"""
            cursor.execute(sql, (ts_code, statement_type, current_report_date))
            row = cursor.fetchone()
            if not row:
                return None, None
            data = row[0]
            if isinstance(data, str):
                data = json.loads(data)
            return data, row[1]
    finally:
        conn.close()


def _get_recent_reports(ts_code, statement_type, limit=4):
    """获取最近N期报表"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """SELECT report_data, report_date FROM stock_financial
                     WHERE ts_code=%s AND statement_type=%s
                     ORDER BY report_date DESC LIMIT %s"""
            cursor.execute(sql, (ts_code, statement_type, limit))
            results = []
            for row in cursor.fetchall():
                data = row[0]
                if isinstance(data, str):
                    data = json.loads(data)
                results.append((data, row[1]))
            return results
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


def _calc_change_rate(curr, prev):
    """计算变化率"""
    if curr is None or prev is None or prev == 0:
        return None
    return round((curr - prev) / abs(prev) * 100, 2)


def _detect_cashflow_drop(ts_code, report_date, income, cashflow):
    """检测经营现金流骤降"""
    alerts = []

    net_profit = _extract_field(income, '净利润', '归属于母公司所有者的净利润')
    operating_cf = _extract_field(cashflow, '经营活动产生的现金流量净额')

    if net_profit is None or operating_cf is None:
        return alerts

    # 净利润为正但经营现金流为负
    if net_profit > 0 and operating_cf < 0:
        severity = 'HIGH' if abs(operating_cf) > net_profit * 0.5 else 'MEDIUM'
        alerts.append({
            'type': '经营现金流为负',
            'severity': severity,
            'detail': f"净利润: {net_profit / 1e8:.2f}亿, 经营现金流: {operating_cf / 1e8:.2f}亿",
            'explanation': '盈利但经营现金流为负，可能应收账款激增或存货积压',
        })

    # 与上期对比现金流骤降
    prev_cashflow, prev_date = _get_prev_report(ts_code, 'cashflow', report_date)
    if prev_cashflow:
        prev_ocf = _extract_field(prev_cashflow, '经营活动产生的现金流量净额')
        if prev_ocf and operating_cf:
            chg = _calc_change_rate(operating_cf, prev_ocf)
            if chg is not None and chg < -50 and operating_cf < 0:
                alerts.append({
                    'type': '经营现金流骤降',
                    'severity': 'HIGH',
                    'detail': f"上期: {prev_ocf / 1e8:.2f}亿 → 本期: {operating_cf / 1e8:.2f}亿 (变化: {chg:+.2f}%)",
                    'explanation': '经营现金流同比大幅下降，需关注经营质量',
                })

    return alerts


def _detect_receivables_surge(ts_code, report_date, income, balance):
    """检测应收账款激增"""
    alerts = []

    revenue = _extract_field(income, '营业总收入', '营业收入')
    receivables = _extract_field(balance, '应收账款', '应收票据及应收账款')

    if receivables is None:
        return alerts

    # 与上期对比
    prev_balance, prev_date = _get_prev_report(ts_code, 'balance', report_date)
    if prev_balance:
        prev_recv = _extract_field(prev_balance, '应收账款', '应收票据及应收账款')
        if prev_recv and prev_recv > 0:
            recv_chg = _calc_change_rate(receivables, prev_recv)

            # 应收账款增速远超营收增速
            if recv_chg is not None and recv_chg > 30:
                prev_income, _ = _get_prev_report(ts_code, 'income', report_date)
                prev_rev = _extract_field(prev_income, '营业总收入', '营业收入') if prev_income else None
                rev_chg = _calc_change_rate(revenue, prev_rev) if prev_rev else None

                if rev_chg is None or recv_chg > rev_chg * 2:
                    severity = 'HIGH' if recv_chg > 80 else 'MEDIUM'
                    detail = f"应收账款变化: {recv_chg:+.2f}%"
                    if rev_chg is not None:
                        detail += f", 营收变化: {rev_chg:+.2f}%"
                    alerts.append({
                        'type': '应收账款激增',
                        'severity': severity,
                        'detail': detail,
                        'explanation': '应收账款增速远超营收增速，可能存在回款困难或虚增收入风险',
                    })

    # 应收账款占营收比例过高
    if revenue and receivables and revenue > 0:
        ratio = receivables / revenue * 100
        if ratio > 50:
            alerts.append({
                'type': '应收账款占比过高',
                'severity': 'HIGH' if ratio > 80 else 'MEDIUM',
                'detail': f"应收账款/营业收入: {ratio:.1f}%",
                'explanation': '应收账款占营收比例过高，收入质量存疑',
            })

    return alerts


def _detect_goodwill_risk(ts_code, balance):
    """检测商誉减值风险"""
    alerts = []

    goodwill = _extract_field(balance, '商誉')
    total_assets = _extract_field(balance, '资产总计')
    equity = _extract_field(balance, '归属于母公司股东权益合计', '所有者权益(或股东权益)合计')

    if goodwill is None or goodwill <= 0:
        return alerts

    # 商誉占净资产比例
    if equity and equity > 0:
        ratio = goodwill / equity * 100
        if ratio > 30:
            alerts.append({
                'type': '商誉减值风险',
                'severity': 'HIGH',
                'detail': f"商誉: {goodwill / 1e8:.2f}亿, 占净资产: {ratio:.1f}%",
                'explanation': '商誉占净资产比例过高，一旦减值将对净资产造成重大冲击',
            })
        elif ratio > 15:
            alerts.append({
                'type': '商誉占比较高',
                'severity': 'MEDIUM',
                'detail': f"商誉: {goodwill / 1e8:.2f}亿, 占净资产: {ratio:.1f}%",
                'explanation': '商誉占净资产比例偏高，需关注并购资产盈利情况',
            })

    # 商誉占总资产比例
    if total_assets and total_assets > 0:
        ratio = goodwill / total_assets * 100
        if ratio > 20:
            alerts.append({
                'type': '商誉占总资产过高',
                'severity': 'HIGH',
                'detail': f"商誉/总资产: {ratio:.1f}%",
                'explanation': '商誉占总资产比例过高，资产质量存疑',
            })

    return alerts


def _detect_inventory_surge(ts_code, report_date, income, balance):
    """检测存货异常增长"""
    alerts = []

    revenue = _extract_field(income, '营业总收入', '营业收入')
    inventory = _extract_field(balance, '存货')

    if inventory is None:
        return alerts

    prev_balance, _ = _get_prev_report(ts_code, 'balance', report_date)
    if prev_balance:
        prev_inv = _extract_field(prev_balance, '存货')
        if prev_inv and prev_inv > 0:
            inv_chg = _calc_change_rate(inventory, prev_inv)

            if inv_chg is not None and inv_chg > 30:
                prev_income, _ = _get_prev_report(ts_code, 'income', report_date)
                prev_rev = _extract_field(prev_income, '营业总收入', '营业收入') if prev_income else None
                rev_chg = _calc_change_rate(revenue, prev_rev) if prev_rev else None

                if rev_chg is None or inv_chg > rev_chg * 2:
                    severity = 'HIGH' if inv_chg > 80 else 'MEDIUM'
                    alerts.append({
                        'type': '存货异常增长',
                        'severity': severity,
                        'detail': f"存货变化: {inv_chg:+.2f}%",
                        'explanation': '存货增速远超营收增速，可能存在滞销或产品积压风险',
                    })

    return alerts


def _detect_debt_surge(ts_code, report_date, balance):
    """检测负债率飙升"""
    alerts = []

    total_assets = _extract_field(balance, '资产总计')
    total_liabilities = _extract_field(balance, '负债合计')

    if not total_assets or not total_liabilities or total_assets <= 0:
        return alerts

    curr_ratio = total_liabilities / total_assets * 100

    prev_balance, _ = _get_prev_report(ts_code, 'balance', report_date)
    if prev_balance:
        prev_assets = _extract_field(prev_balance, '资产总计')
        prev_liabilities = _extract_field(prev_balance, '负债合计')
        if prev_assets and prev_liabilities and prev_assets > 0:
            prev_ratio = prev_liabilities / prev_assets * 100
            ratio_chg = curr_ratio - prev_ratio

            if ratio_chg > 10:
                alerts.append({
                    'type': '资产负债率飙升',
                    'severity': 'HIGH' if ratio_chg > 20 else 'MEDIUM',
                    'detail': f"资产负债率: {prev_ratio:.1f}% → {curr_ratio:.1f}% (上升{ratio_chg:.1f}个百分点)",
                    'explanation': '资产负债率短期大幅上升，财务风险增加',
                })

    if curr_ratio > 80:
        alerts.append({
            'type': '资产负债率过高',
            'severity': 'HIGH',
            'detail': f"资产负债率: {curr_ratio:.1f}%",
            'explanation': '资产负债率超过80%，财务杠杆过高',
        })

    return alerts


def _detect_profit_cashflow_divergence(ts_code):
    """检测净利润与现金流连续背离"""
    alerts = []

    # 获取最近4期数据
    income_reports = _get_recent_reports(ts_code, 'income', 4)
    cashflow_reports = _get_recent_reports(ts_code, 'cashflow', 4)

    if len(income_reports) < 2 or len(cashflow_reports) < 2:
        return alerts

    # 按 report_date 匹配
    cf_map = {r[1]: r[0] for r in cashflow_reports}

    neg_count = 0
    total_count = 0
    for income_data, rd in income_reports:
        np_val = _extract_field(income_data, '净利润', '归属于母公司所有者的净利润')
        cf_data = cf_map.get(rd)
        if cf_data:
            ocf = _extract_field(cf_data, '经营活动产生的现金流量净额')
            if np_val is not None and ocf is not None:
                total_count += 1
                if np_val > 0 and ocf < 0:
                    neg_count += 1

    if total_count >= 2 and neg_count >= 2:
        alerts.append({
            'type': '净利润与现金流持续背离',
            'severity': 'HIGH',
            'detail': f"最近{total_count}期中有{neg_count}期净利润为正但经营现金流为负",
            'explanation': '连续多期盈利但经营现金流为负，盈利质量存疑',
        })

    return alerts


def _detect_margin_volatility(ts_code, report_date, income):
    """检测毛利率/营业利润率异常波动（银行股用营业支出，非银行股用营业成本）"""
    alerts = []

    revenue = _extract_field(income, '营业总收入', '营业收入')
    cost = _extract_field(income, '营业成本') or _extract_field(income, '营业支出')
    margin_name = '营业利润率' if _extract_field(income, '营业成本') is None else '毛利率'

    if not revenue or not cost or revenue <= 0:
        return alerts

    curr_margin = (revenue - cost) / revenue * 100

    prev_income, _ = _get_prev_report(ts_code, 'income', report_date)
    if prev_income:
        prev_rev = _extract_field(prev_income, '营业总收入', '营业收入')
        prev_cost = _extract_field(prev_income, '营业成本') or _extract_field(prev_income, '营业支出')
        if prev_rev and prev_cost and prev_rev > 0:
            prev_margin = (prev_rev - prev_cost) / prev_rev * 100
            margin_chg = curr_margin - prev_margin

            if margin_chg < -10:
                alerts.append({
                    'type': f'{margin_name}大幅下降',
                    'severity': 'HIGH' if margin_chg < -20 else 'MEDIUM',
                    'detail': f"{margin_name}: {prev_margin:.1f}% → {curr_margin:.1f}% (下降{abs(margin_chg):.1f}个百分点)",
                    'explanation': f'{margin_name}大幅下降，可能面临成本上升或产品降价压力',
                })

    return alerts


def detect_anomalies(ts_code, report_date=None):
    """
    检测单个公司的财务异常指标

    Args:
        ts_code: 股票代码（带后缀），如 '600519.SH'
        report_date: 指定报告日期，默认取最新一期

    Returns:
        str: 格式化的异常检测结果
    """
    name = _get_stock_name(ts_code)

    # 获取最新报表
    income, report_date = _get_report(ts_code, 'income', report_date)
    if not income:
        return f"未找到 {ts_code} 的利润表数据"

    balance, _ = _get_report(ts_code, 'balance', report_date)
    cashflow, _ = _get_report(ts_code, 'cashflow', report_date)

    # 执行所有检测
    all_alerts = []
    all_alerts.extend(_detect_cashflow_drop(ts_code, report_date, income, cashflow))
    all_alerts.extend(_detect_receivables_surge(ts_code, report_date, income, balance))
    all_alerts.extend(_detect_goodwill_risk(ts_code, balance))
    all_alerts.extend(_detect_inventory_surge(ts_code, report_date, income, balance))
    all_alerts.extend(_detect_debt_surge(ts_code, report_date, balance))
    all_alerts.extend(_detect_profit_cashflow_divergence(ts_code))
    all_alerts.extend(_detect_margin_volatility(ts_code, report_date, income))

    # 按严重程度排序
    severity_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    all_alerts.sort(key=lambda x: severity_order.get(x['severity'], 3))

    # 格式化输出
    result = f"=== {name}({ts_code}) 财务异常检测 ===\n"
    result += f"报告期: {report_date}\n"

    if not all_alerts:
        result += f"\n未检测到明显异常信号\n"
        return result

    high_count = sum(1 for a in all_alerts if a['severity'] == 'HIGH')
    medium_count = sum(1 for a in all_alerts if a['severity'] == 'MEDIUM')

    result += f"\n检测结果: {len(all_alerts)}个异常信号"
    if high_count:
        result += f" (高风险: {high_count}个"
    if medium_count:
        result += f", 中风险: {medium_count}个"
    if high_count:
        result += ")"
    result += "\n"

    for i, alert in enumerate(all_alerts, 1):
        icon = "!!" if alert['severity'] == 'HIGH' else "! "
        result += f"\n{icon} [{alert['severity']}] {alert['type']}\n"
        result += f"   数据: {alert['detail']}\n"
        result += f"   说明: {alert['explanation']}\n"

    return result


def detect_sector_anomalies(sector_name, sector_type='industry', top_n=10):
    """
    批量检测板块内成分股的财务异常

    Args:
        sector_name: 板块名称（支持模糊匹配）
        sector_type: 'industry' 或 'concept'
        top_n: 检测前N只成分股，默认10

    Returns:
        str: 格式化的板块异常检测结果
    """
    type_name = '行业' if sector_type == 'industry' else '概念'
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    cons_table = 'sector_industry_cons' if sector_type == 'industry' else 'sector_concept_cons'

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 搜索板块
            cursor.execute(f"SELECT DISTINCT sector_code, sector_name FROM {table} WHERE sector_name LIKE %s", (f'%{sector_name}%',))
            matches = cursor.fetchall()
            if not matches:
                return f"未找到{type_name}板块: {sector_name}"
            exact = [m for m in matches if m[1] == sector_name]
            sector_code = exact[0][0] if exact else matches[0][0]
            sector_name_real = exact[0][1] if exact else matches[0][1]

            # 获取成分股
            cursor.execute(f"SELECT stock_code, stock_name FROM {cons_table} WHERE sector_code = %s", (sector_code,))
            constituents = cursor.fetchall()
    finally:
        conn.close()

    if not constituents:
        return f"板块 [{sector_name_real}] 无成分股数据"

    # 转换为 ts_code
    stock_codes = [c[0] for c in constituents]
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(stock_codes))
            cursor.execute(f"SELECT symbol, ts_code FROM company_info WHERE symbol IN ({placeholders})", (*stock_codes,))
            code_map = {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        conn.close()

    ts_codes = [code_map[c] for c in stock_codes if c in code_map][:top_n]

    # 批量检测
    result = f"=== {sector_name_real}板块 财务异常检测 ===\n"
    result += f"检测范围: 前{len(ts_codes)}只成分股\n"

    has_anomaly = 0
    for ts_code in ts_codes:
        name = _get_stock_name(ts_code)
        income, rd = _get_report(ts_code, 'income')
        if not income:
            continue
        balance, _ = _get_report(ts_code, 'balance')
        cashflow, _ = _get_report(ts_code, 'cashflow')

        alerts = []
        alerts.extend(_detect_cashflow_drop(ts_code, rd, income, cashflow))
        alerts.extend(_detect_receivables_surge(ts_code, rd, income, balance))
        alerts.extend(_detect_goodwill_risk(ts_code, balance))
        alerts.extend(_detect_inventory_surge(ts_code, rd, income, balance))
        alerts.extend(_detect_debt_surge(ts_code, rd, balance))
        alerts.extend(_detect_profit_cashflow_divergence(ts_code))
        alerts.extend(_detect_margin_volatility(ts_code, rd, income))

        if alerts:
            has_anomaly += 1
            high_alerts = [a for a in alerts if a['severity'] == 'HIGH']
            result += f"\n  {name}({ts_code}) - {len(alerts)}个异常"
            if high_alerts:
                result += f" [含{len(high_alerts)}个高风险]"
            result += "\n"
            for a in alerts[:3]:  # 每只最多显示3个
                result += f"    [{a['severity']}] {a['type']}: {a['detail']}\n"
            if len(alerts) > 3:
                result += f"    ...还有{len(alerts) - 3}个异常\n"

    if has_anomaly == 0:
        result += f"\n前{len(ts_codes)}只成分股均未检测到明显异常\n"
    else:
        result += f"\n汇总: {has_anomaly}/{len(ts_codes)}只成分股存在异常信号\n"

    return result


if __name__ == '__main__':
    print("\n1. 贵州茅台财务异常检测:")
    print(detect_anomalies('600519.SH'))

    print("\n2. 白酒板块异常检测:")
    print(detect_sector_anomalies('白酒', top_n=5))
