#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基本面指标计算工具
从 MySQL market_data.stock_financial 表获取财务数据，计算基本面指标

支持:
- 通用制造业、消费等行业
- 银行股（字段名不同，自动识别）

指标:
- ROE（净资产收益率） = 归属于母公司股东净利润 / 归属于母公司股东权益合计 × 100%
- 毛利率 = (营业收入 - 营业成本) / 营业收入 × 100%
- 净利率 = 净利润 / 营业收入 × 100%
- 资产负债率 = 负债合计 / 资产总计 × 100%
- 经营现金流净利润比 = 经营活动产生的现金流量净额 / 净利润
- 营收增长率 = (本期营业收入 - 上期营业收入) / |上期营业收入| × 100%
- 净利润增长率 = (本期净利润 - 上期净利润) / |上期净利润| × 100%

银行股特殊处理:
- 营业收入 = 净利息收入 + 手续费及佣金净收入
- 营业成本 = 利息支出 + 手续费及佣金支出
- 通过资产负债表特征字段（发放贷款及垫款净额/客户存款）自动识别银行股

用法:
    from tools.stock_fundamental import calc_fundamental_indicators
    result = calc_fundamental_indicators('600519.SH')
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


def _is_bank(ts_code):
    """判断是否为银行股（通过资产负债表特征字段）"""
    balance, _ = _get_report(ts_code, 'balance')
    if not balance:
        return False
    # 银行股的资产负债表有'发放贷款及垫款净额'或'客户存款'等字段
    bank_fields = ['发放贷款及垫款净额', '客户存款', '吸收存款']
    return any(balance.get(f) is not None for f in bank_fields)


def _get_report(ts_code, statement_type, report_date=None):
    """从MySQL获取单张报表数据，返回 report_data dict 和 report_date"""
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
    """获取上一期报表数据（用于计算同比增长率）"""
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


def _calc_common_indicators(income, balance, cashflow):
    """计算通用指标（制造业、消费等行业）"""
    result = {}

    # 营业收入、营业成本（用营业成本，非营业总成本）、净利润
    revenue = _extract_field(income, '营业总收入', '营业收入')
    cost = _extract_field(income, '营业成本')  # 营业成本，不含费用
    net_profit = _extract_field(income, '净利润', '归属于母公司所有者的净利润', '归属于母公司股东的净利润')

    # 资产总计、负债合计、归属于母公司股东权益
    total_assets = _extract_field(balance, '资产总计')
    total_liabilities = _extract_field(balance, '负债合计')
    equity = _extract_field(balance, '归属于母公司股东权益合计', '归属于母公司所有者权益', '所有者权益（或股东权益）合计')

    # 经营活动现金流净额
    operating_cashflow = _extract_field(cashflow, '经营活动产生的现金流量净额')

    # 毛利率
    if revenue and cost and revenue > 0:
        result['毛利率'] = round((revenue - cost) / revenue * 100, 2)

    # 净利率
    if net_profit and revenue and revenue > 0:
        result['净利率'] = round(net_profit / revenue * 100, 2)

    # ROE
    if net_profit and equity and equity > 0:
        result['ROE'] = round(net_profit / equity * 100, 2)

    # 资产负债率
    if total_liabilities and total_assets and total_assets > 0:
        result['资产负债率'] = round(total_liabilities / total_assets * 100, 2)

    # 经营现金流/净利润
    if operating_cashflow is not None and net_profit and net_profit != 0:
        result['经营现金流净利润比'] = round(operating_cashflow / net_profit, 2)

    # 原始值也保留，方便后续使用
    result['_revenue'] = revenue
    result['_net_profit'] = net_profit
    result['_total_assets'] = total_assets
    result['_equity'] = equity
    result['_operating_cashflow'] = operating_cashflow

    return result


def _calc_bank_indicators(income, balance, cashflow):
    """计算银行股指标"""
    result = {}

    # 银行营业收入 = 净利息收入 + 手续费及佣金净收入
    net_interest_income = _extract_field(income, '净利息收入')
    fee_income = _extract_field(income, '手续费及佣金净收入')
    revenue = None
    if net_interest_income is not None:
        revenue = net_interest_income
        if fee_income is not None:
            revenue += fee_income
    else:
        revenue = _extract_field(income, '营业总收入', '营业收入')

    # 银行营业成本 = 利息支出 + 手续费及佣金支出
    interest_expense = _extract_field(income, '利息支出')
    fee_expense = _extract_field(income, '手续费及佣金支出')
    cost = None
    if interest_expense is not None:
        cost = interest_expense
        if fee_expense is not None:
            cost += fee_expense

    net_profit = _extract_field(income, '净利润', '归属于母公司所有者的净利润', '归属于母公司股东的净利润')

    # 资产负债
    total_assets = _extract_field(balance, '资产总计')
    total_liabilities = _extract_field(balance, '负债合计')
    equity = _extract_field(balance, '归属于母公司股东权益合计', '归属于母公司所有者权益', '所有者权益（或股东权益）合计')

    # 经营现金流
    operating_cashflow = _extract_field(cashflow, '经营活动产生的现金流量净额')

    # 毛利率（银行用净利息收入概念）
    if revenue and cost and revenue > 0:
        result['毛利率'] = round((revenue - cost) / revenue * 100, 2)

    # 净利率
    if net_profit and revenue and revenue > 0:
        result['净利率'] = round(net_profit / revenue * 100, 2)

    # ROE
    if net_profit and equity and equity > 0:
        result['ROE'] = round(net_profit / equity * 100, 2)

    # 资产负债率
    if total_liabilities and total_assets and total_assets > 0:
        result['资产负债率'] = round(total_liabilities / total_assets * 100, 2)

    # 经营现金流/净利润
    if operating_cashflow is not None and net_profit and net_profit != 0:
        result['经营现金流净利润比'] = round(operating_cashflow / net_profit, 2)

    result['_revenue'] = revenue
    result['_net_profit'] = net_profit
    result['_total_assets'] = total_assets
    result['_equity'] = equity
    result['_operating_cashflow'] = operating_cashflow

    return result


def _calc_growth_rates(ts_code, report_date, is_bank):
    """计算同比和环比增长率（营收、净利润）

    一、同比增长率（Year-over-Year, YoY）
    ─────────────────────────────────────
    定义：本期累计值 vs 上年同期累计值
    公式：(本期 - 上年同期) / |上年同期| × 100%
    特点：直接用累计值对比，无需拆分单季

    对比规则：
    - Q1(0331) vs 上年Q1(0331)    例：20260331 vs 20250331
    - Q2(0630) vs 上年Q2(0630)    例：20260630 vs 20250630
    - Q3(0930) vs 上年Q3(0930)    例：20260930 vs 20250930
    - Q4(1231) vs 上年Q4(1231)    例：20251231 vs 20241231

    二、环比增长率（Quarter-over-Quarter, QoQ）
    ────────────────────────────────────────────
    定义：本季单季值 vs 上季单季值
    公式：(本季单季 - 上季单季) / |上季单季| × 100%

    为什么需要拆分单季？
    - A股财报是累计制：Q2报表 = Q1+Q2，Q3报表 = Q1+Q2+Q3，Q4报表 = 全年
    - 直接用累计值做环比会导致数据失真
    - 必须先拆成单季数据再对比

    单季拆分公式：
    - Q1单季 = Q1累计（本身就是单季）
    - Q2单季 = 半年报(0630)累计 - Q1(0331)累计
    - Q3单季 = 三季报(0930)累计 - 半年报(0630)累计
    - Q4单季 = 年报(1231)累计 - 三季报(0930)累计

    环比对比规则：
    - Q1 vs 上年Q4    例：2026Q1 vs 2025Q4
    - Q2 vs 本年Q1    例：2026Q2 vs 2026Q1
    - Q3 vs 本年Q2    例：2026Q3 vs 2026Q2
    - Q4 vs 本年Q3    例：2025Q4 vs 2025Q3

    示例（贵州茅台）：
    ┌─────────┬──────────┬──────────┬────────┬──────────┬──────────┐
    │  报告期  │ 营收累计  │ 营收单季  │ 同比   │   环比   │ 环比对比  │
    ├─────────┼──────────┼──────────┼────────┼──────────┼──────────┤
    │ 2025Q1  │  514亿   │  514亿   │  --    │   --     │   --     │
    │ 2025Q2  │  898亿   │  384亿   │  --    │ -25.29%  │ vs Q1    │
    │ 2025Q3  │ 1309亿   │  411亿   │  --    │  +7.03%  │ vs Q2    │
    │ 2025Q4  │ 1720亿   │  411亿   │  --    │  +0.0%   │ vs Q3    │
    │ 2026Q1  │  547亿   │  547亿   │ +6.34% │ +32.93%  │ vs 2025Q4│
    └─────────┴──────────┴──────────┴────────┴──────────┴──────────┘
    """
    result = {}

    curr_income, _ = _get_report(ts_code, 'income', report_date)
    if not curr_income:
        return result

    def _rev(income_data):
        """获取营收（银行股用净利息收入）"""
        if is_bank:
            return _extract_field(income_data, '净利息收入')
        return _extract_field(income_data, '营业总收入', '营业收入')

    def _np(income_data):
        """获取净利润"""
        return _extract_field(income_data, '净利润', '归属于母公司所有者的净利润')

    curr_revenue = _rev(curr_income)
    curr_np_val = _np(curr_income)

    # ════════════════════════════════════════════════════════════
    # 同比计算：本期累计值 vs 上年同期累计值
    # ════════════════════════════════════════════════════════════
    # 计算上年同期报告日：YYYYMMDD - 10000（年份减1，月日不变）
    # 例：20260331 → 20250331，20251231 → 20241231
    prev_year_date = str(int(report_date) - 10000)
    yoy_income, _ = _get_report(ts_code, 'income', prev_year_date)
    if yoy_income:
        yoy_revenue = _rev(yoy_income)
        yoy_np_val = _np(yoy_income)

        if curr_revenue and yoy_revenue and yoy_revenue != 0:
            result['营收同比增长率'] = round((curr_revenue - yoy_revenue) / abs(yoy_revenue) * 100, 2)
        if curr_np_val and yoy_np_val and yoy_np_val != 0:
            result['净利润同比增长率'] = round((curr_np_val - yoy_np_val) / abs(yoy_np_val) * 100, 2)

    # ════════════════════════════════════════════════════════════
    # 环比计算：本季单季值 vs 上季单季值
    # ════════════════════════════════════════════════════════════
    # report_date格式：YYYYMMDD，末两位决定季度
    # 03 → Q1，06 → Q2，09 → Q3，12 → Q4
    month = int(report_date[4:6])

    def _get_single_quarter(ts_code, report_date, is_bank):
        """获取某期的单季营收和净利润

        原理：A股财报是累计制
        - Q1(0331)：累计 = 单季（本身就是第一季度数据）
        - Q2(0630)：累计 = Q1+Q2，所以 Q2单季 = 半年报 - Q1累计
        - Q3(0930)：累计 = Q1+Q2+Q3，所以 Q3单季 = 三季报 - 半年报累计
        - Q4(1231)：累计 = Q1+Q2+Q3+Q4，所以 Q4单季 = 年报 - 三季报累计

        Args:
            ts_code: 股票代码
            report_date: 报告日（YYYYMMDD）
            is_bank: 是否为银行股

        Returns:
            (单季营收, 单季净利润)
        """
        income_data, _ = _get_report(ts_code, 'income', report_date)
        if not income_data:
            return None, None

        rev = _rev(income_data)
        np_val = _np(income_data)

        month = int(report_date[4:6])

        if month == 3:
            # Q1：累计 = 单季，无需拆分
            return rev, np_val
        elif month == 6:
            # Q2单季 = 半年报(0630) - Q1(0331)
            prev_date = report_date[:4] + '0331'
        elif month == 9:
            # Q3单季 = 三季报(0930) - 半年报(0630)
            prev_date = report_date[:4] + '0630'
        else:  # month == 12
            # Q4单季 = 年报(1231) - 三季报(0930)
            prev_date = report_date[:4] + '0930'

        # 获取上一期累计数据
        prev_data, _ = _get_report(ts_code, 'income', prev_date)
        if not prev_data:
            return rev, np_val  # 无法拆分，返回累计值

        prev_rev = _rev(prev_data)
        prev_np_val = _np(prev_data)

        # 单季 = 本期累计 - 上期累计
        sq_rev = (rev - prev_rev) if (rev is not None and prev_rev is not None) else rev
        sq_np = (np_val - prev_np_val) if (np_val is not None and prev_np_val is not None) else np_val
        return sq_rev, sq_np

    # 获取当前期单季数据
    curr_sq_rev, curr_sq_np = _get_single_quarter(ts_code, report_date, is_bank)

    # 确定上期报告日（环比对比对象）
    if month == 3:
        # Q1环比：对比上年Q4单季（2026Q1 vs 2025Q4）
        # 计算方法：年份减1，月日设为1231
        prev_year = str(int(report_date[:4]) - 1)
        qoq_date = prev_year + '1231'
    elif month == 6:
        # Q2环比：对比本年Q1单季（2026Q2 vs 2026Q1）
        qoq_date = report_date[:4] + '0331'
    elif month == 9:
        # Q3环比：对比本年Q2单季（2026Q3 vs 2026Q2）
        qoq_date = report_date[:4] + '0630'
    else:  # month == 12
        # Q4环比：对比本年Q3单季（2025Q4 vs 2025Q3）
        qoq_date = report_date[:4] + '0930'

    # 获取上期单季数据
    qoq_sq_rev, qoq_sq_np = _get_single_quarter(ts_code, qoq_date, is_bank)

    # 计算环比增长率
    if curr_sq_rev is not None and qoq_sq_rev is not None and qoq_sq_rev != 0:
        result['营收环比增长率'] = round((curr_sq_rev - qoq_sq_rev) / abs(qoq_sq_rev) * 100, 2)
    if curr_sq_np is not None and qoq_sq_np is not None and qoq_sq_np != 0:
        result['净利润环比增长率'] = round((curr_sq_np - qoq_sq_np) / abs(qoq_sq_np) * 100, 2)

    return result


def get_financial_data(ts_code, report_date=None):
    """从MySQL获取某只股票的三张报表数据

    Args:
        ts_code: 股票代码，如 600519.SH
        report_date: 报告日，格式YYYYMMDD，如 20260331(2026一季报)、20251231(2025年报)，None则取最新

    Returns:
        dict: {income: {...}, balance: {...}, cashflow: {...}, report_date: str}
    """
    income, rd1 = _get_report(ts_code, 'income', report_date)
    balance, rd2 = _get_report(ts_code, 'balance', report_date)
    cashflow, rd3 = _get_report(ts_code, 'cashflow', report_date)

    return {
        'income': income,
        'balance': balance,
        'cashflow': cashflow,
        'report_date': rd1 or rd2 or rd3,
    }


def calc_fundamental_indicators(ts_code, report_date=None):
    """计算基本面指标

    Args:
        ts_code: 股票代码，如 600519.SH 或 600000.SH
        report_date: 报告日，格式YYYYMMDD，如 20260331(2026一季报)、20251231(2025年报)，None则取最新一期

    Returns:
        dict: {
            ts_code, report_date, is_bank,
            ROE, 毛利率, 净利率, 资产负债率, 经营现金流净利润比,
            营收同比增长率, 净利润同比增长率, 营收环比增长率, 净利润环比增长率,
            _revenue, _net_profit, _total_assets, _equity, _operating_cashflow
        }
    """
    data = get_financial_data(ts_code, report_date)
    income = data['income']
    balance = data['balance']
    cashflow = data['cashflow']
    rd = data['report_date']

    if not income and not balance and not cashflow:
        return {'ts_code': ts_code, 'error': '无财务数据'}

    is_bank = _is_bank(ts_code)

    if is_bank:
        indicators = _calc_bank_indicators(income, balance, cashflow)
    else:
        indicators = _calc_common_indicators(income, balance, cashflow)

    # 增长率
    growth = _calc_growth_rates(ts_code, rd, is_bank)
    indicators.update(growth)

    indicators['ts_code'] = ts_code
    indicators['report_date'] = rd
    indicators['is_bank'] = is_bank

    return indicators


def get_report_dates(ts_code, limit=8):
    """获取某只股票最近N期的报告日列表"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """SELECT DISTINCT report_date FROM stock_financial
                     WHERE ts_code=%s AND statement_type='income'
                     ORDER BY report_date DESC LIMIT %s"""
            cursor.execute(sql, (ts_code, limit))
            return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def calc_fundamental_trend(ts_code, periods=4):
    """计算最近N期的基本面指标趋势

    Args:
        ts_code: 股票代码，如 600519.SH
        periods: 返回期数，默认4期

    report_date格式示例: 20260331(2026一季报)、20251231(2025年报)、20250930(三季报)、20250630(半年报)

    Returns:
        dict: {
            ts_code, is_bank,
            trend: [
                {report_date, ROE, 毛利率, 净利率, 资产负债率, 经营现金流净利润比,
                 营收同比增长率, 净利润同比增长率, 营收环比增长率, 净利润环比增长率},
                ...
            ]
        }
    """
    report_dates = get_report_dates(ts_code, limit=periods + 1)
    if not report_dates:
        return {'ts_code': ts_code, 'error': '无财务数据'}

    is_bank = _is_bank(ts_code)
    trend = []

    for rd in report_dates[:periods]:
        data = get_financial_data(ts_code, rd)
        income = data['income']
        balance = data['balance']
        cashflow = data['cashflow']

        if not income and not balance:
            continue

        if is_bank:
            indicators = _calc_bank_indicators(income, balance, cashflow)
        else:
            indicators = _calc_common_indicators(income, balance, cashflow)

        growth = _calc_growth_rates(ts_code, rd, is_bank)
        indicators.update(growth)

        # 只保留核心指标
        display = {
            'report_date': rd,
            'ROE': indicators.get('ROE'),
            '毛利率': indicators.get('毛利率'),
            '净利率': indicators.get('净利率'),
            '资产负债率': indicators.get('资产负债率'),
            '经营现金流净利润比': indicators.get('经营现金流净利润比'),
            '营收同比增长率': indicators.get('营收同比增长率'),
            '净利润同比增长率': indicators.get('净利润同比增长率'),
            '营收环比增长率': indicators.get('营收环比增长率'),
            '净利润环比增长率': indicators.get('净利润环比增长率'),
        }
        trend.append(display)

    return {
        'ts_code': ts_code,
        'is_bank': is_bank,
        'trend': trend,
    }


if __name__ == '__main__':

    test_stocks = [
        ('600519.SH', '贵州茅台'),
        ('600000.SH', '浦发银行'),
    ]

    # 测试单期指标
    print("=" * 60)
    print("单期指标测试")
    print("=" * 60)
    for code, name in test_stocks:
        print(f"\n--- {name} ({code}) ---")
        result = calc_fundamental_indicators(code)
        display = {k: v for k, v in result.items() if not k.startswith('_')}
        print(json.dumps(display, ensure_ascii=False, indent=2))

    # 测试趋势指标
    print("\n" + "=" * 60)
    print("趋势指标测试（最近4期）")
    print("=" * 60)
    for code, name in test_stocks:
        print(f"\n--- {name} ({code}) ---")
        trend = calc_fundamental_trend(code, periods=4)
        print(json.dumps(trend, ensure_ascii=False, indent=2))
