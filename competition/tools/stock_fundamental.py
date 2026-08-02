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
    """计算通用指标（制造业、消费等行业）

    按分析框架顺序：毛利率 → 净利率 → ROE+杜邦 → 现金流+应收

    Returns:
        dict: {
            毛利率, 净利率, ROE,
            杜邦_净利率, 杜邦_总资产周转率, 杜邦_权益乘数,
            资产负债率, 经营现金流, 经营现金流净利润比, 应收账款占比, 应收账款,
            营业收入, 净利润, 归母净利润, 资产总计, 负债合计, 归母权益
        }
    """
    result = {}

    # ═══════════ 原始数据提取 ═══════════
    revenue = _extract_field(income, '营业总收入', '营业收入')
    cost = _extract_field(income, '营业成本')
    # 净利润（含少数股东）用于净利率等
    net_profit = _extract_field(income, '净利润')
    # 归母净利润用于ROE/杜邦（与归母权益匹配）
    parent_net_profit = _extract_field(income, '归属于母公司所有者的净利润')

    total_assets = _extract_field(balance, '资产总计')
    total_liabilities = _extract_field(balance, '负债合计')
    equity = _extract_field(balance, '归属于母公司股东权益合计', '所有者权益(或股东权益)合计')
    accounts_receivable = _extract_field(balance, '应收账款', '应收票据及应收账款')

    operating_cashflow = _extract_field(cashflow, '经营活动产生的现金流量净额')

    # ═══════════ 模块1：盈利能力 ═══════════

    # 毛利率 = (营收-营业成本)/营收
    if revenue and cost and revenue > 0:
        result['毛利率'] = round((revenue - cost) / revenue * 100, 2)

    # 净利率 = 净利润/营收
    if net_profit and revenue and revenue > 0:
        result['净利率'] = round(net_profit / revenue * 100, 2)

    # ROE = 归属于母公司所有者的净利润 / 归母权益
    roe_np = parent_net_profit or net_profit  # 优先用归母净利润，无则用净利润
    if roe_np and equity and equity > 0:
        result['ROE'] = round(roe_np / equity * 100, 2)

    # 杜邦拆解：ROE = 净利率 × 总资产周转率 × 权益乘数
    if roe_np and revenue and revenue > 0 and total_assets and total_assets > 0 and equity and equity > 0:
        result['杜邦_净利率'] = round(roe_np / revenue * 100, 2)
        result['杜邦_总资产周转率'] = round(revenue / total_assets, 4)
        result['杜邦_权益乘数'] = round(total_assets / equity, 4)

    # ═══════════ 模块2：盈利真实性与营运风险 ═══════════

    # 资产负债率
    if total_liabilities and total_assets and total_assets > 0:
        result['资产负债率'] = round(total_liabilities / total_assets * 100, 2)

    # 经营现金流
    if operating_cashflow is not None:
        result['经营现金流'] = round(operating_cashflow, 2)

    # 净利润现金含量 = 经营现金流/净利润
    if operating_cashflow is not None and net_profit and net_profit != 0:
        result['经营现金流净利润比'] = round(operating_cashflow / net_profit, 2)

    # 应收账款占比 = 应收账款/营收
    if accounts_receivable is not None and revenue and revenue > 0:
        result['应收账款占比'] = round(accounts_receivable / revenue * 100, 2)
    result['应收账款'] = accounts_receivable

    # ═══════════ 保留原始值 ═══════════
    result['营业收入'] = revenue
    result['净利润'] = net_profit
    result['归母净利润'] = parent_net_profit
    result['资产总计'] = total_assets
    result['负债合计'] = total_liabilities
    result['归母权益'] = equity

    return result


def _calc_bank_indicators(income, balance, cashflow):
    """计算银行股指标

    Returns:
        dict: {
            营业利润率, 净利率, ROE,
            杜邦_净利率, 杜邦_总资产周转率, 杜邦_权益乘数,
            资产负债率, 经营现金流, 经营现金流净利润比, 应收账款占比, 应收账款,
            营业收入, 净利润, 资产总计, 负债合计, 归母权益
        }
    """
    result = {}

    # ═══════════ 原始数据提取 ═══════════

    # 银行营业收入（直接用营业收入，包含以下组成部分）：
    # - 净利息收入（利息收入 - 利息支出）
    # - 手续费及佣金净收入（手续费及佣金收入 - 手续费及佣金支出）
    # - 投资收益
    # - 公允价值变动收益/(损失)
    # - 其他业务收入
    # - 净交易收入 = 汇兑收益 + 衍生金融工具交易净收入 + 净敞口套期收益
    # - 资产处置收益
    # - 其他收益
    revenue = _extract_field(income, '营业收入', '营业总收入')

    # 银行营业支出（直接用营业支出，包含以下组成部分）：
    # - 营业税金及附加
    # - 业务及管理费用
    # - 信用减值损失
    # - 其他资产减值损失
    # - 其他业务支出
    cost = _extract_field(income, '营业支出', '营业总支出')

    # 净利润 = 归属于母公司的净利润 + 少数股东损益
    net_profit = _extract_field(income, '净利润')
    parent_net_profit = _extract_field(income, '归属于母公司的净利润')

    # 资产负债
    total_assets = _extract_field(balance, '资产总计')
    total_liabilities = _extract_field(balance, '负债合计')
    equity = _extract_field(balance, '归属于母公司股东的权益')

    # 经营现金流
    operating_cashflow = _extract_field(cashflow, '经营活动产生的现金流量净额')

    # 应收账款
    accounts_receivable = _extract_field(balance, '应收账款', '应收票据及应收账款')

    # ═══════════ 模块1：盈利能力 ═══════════

    # 营业利润率 = (营业收入 - 营业支出) / 营业收入（银行无营业成本概念，不叫毛利率）
    if revenue and cost and revenue > 0:
        result['营业利润率'] = round((revenue - cost) / revenue * 100, 2)

    # 净利率 = 净利润/营业收入
    if net_profit and revenue and revenue > 0:
        result['净利率'] = round(net_profit / revenue * 100, 2)

    # ROE = 归属于母公司的净利润 / 归属于母公司股东的权益
    roe_np = parent_net_profit or net_profit  # 优先用归母净利润，无则用净利润
    if roe_np and equity and equity > 0:
        result['ROE'] = round(roe_np / equity * 100, 2)

    # 杜邦拆解：ROE = 净利率 × 总资产周转率 × 权益乘数
    if roe_np and revenue and revenue > 0 and total_assets and total_assets > 0 and equity and equity > 0:
        result['杜邦_净利率'] = round(roe_np / revenue * 100, 2)
        result['杜邦_总资产周转率'] = round(revenue / total_assets, 4)
        result['杜邦_权益乘数'] = round(total_assets / equity, 4)

    # ═══════════ 模块2：盈利真实性与营运风险 ═══════════

    # 资产负债率
    if total_liabilities and total_assets and total_assets > 0:
        result['资产负债率'] = round(total_liabilities / total_assets * 100, 2)

    # 经营现金流（可为负数）
    if operating_cashflow is not None:
        result['经营现金流'] = round(operating_cashflow, 2)

    # 经营现金流/净利润
    if operating_cashflow is not None and net_profit and net_profit != 0:
        result['经营现金流净利润比'] = round(operating_cashflow / net_profit, 2)

    # 应收账款占比 = 应收账款/营收
    if accounts_receivable is not None and revenue and revenue > 0:
        result['应收账款占比'] = round(accounts_receivable / revenue * 100, 2)
    result['应收账款'] = accounts_receivable

    # ═══════════ 保留原始值 ═══════════
    result['营业收入'] = revenue
    result['净利润'] = net_profit
    result['资产总计'] = total_assets
    result['负债合计'] = total_liabilities
    result['归母权益'] = equity

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
    - Q4 vs 本年Q3    例：2026Q4 vs 2026Q3

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
        """获取营收"""
        return _extract_field(income_data, '营业总收入', '营业收入')

    def _np(income_data):
        """获取净利润（区分银行股和非银行股）"""
        if is_bank:
            # 银行股：归属于母公司的净利润
            return _extract_field(income_data, '净利润', '归属于母公司的净利润')
        else:
            # 非银行股：归属于母公司所有者的净利润
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

    def _get_single_quarter(ts_code, report_date):
        """获取某期的单季营收和净利润

        原理：A股财报是累计制
        - Q1(0331)：累计 = 单季（本身就是第一季度数据）
        - Q2(0630)：累计 = Q1+Q2，所以 Q2单季 = 半年报 - Q1累计
        - Q3(0930)：累计 = Q1+Q2+Q3，所以 Q3单季 = 三季报 - 半年报累计
        - Q4(1231)：累计 = Q1+Q2+Q3+Q4，所以 Q4单季 = 年报 - 三季报累计

        Args:
            ts_code: 股票代码
            report_date: 报告日（YYYYMMDD）

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
    curr_sq_rev, curr_sq_np = _get_single_quarter(ts_code, report_date)

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
    qoq_sq_rev, qoq_sq_np = _get_single_quarter(ts_code, qoq_date)

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
            ROE, 毛利率/营业利润率, 净利率, 杜邦_净利率, 杜邦_总资产周转率, 杜邦_权益乘数,
            资产负债率, 经营现金流, 经营现金流净利润比, 应收账款占比, 应收账款,
            营收同比增长率, 净利润同比增长率, 营收环比增长率, 净利润环比增长率,
            营业收入, 净利润, 归母净利润, 资产总计, 负债合计, 归母权益
        }
        注：银行股返回营业利润率（非毛利率）
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
