#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块财务聚合工具
关联成分股数据，计算板块整体财务指标和估值统计

功能:
- 板块财务聚合：平均ROE、平均毛利率、合计营收/净利润
- 板块估值统计：PE/PB均值、中位数、极值、估值分布

用法:
    from tools.sector_financial_agg import get_sector_financial_agg, get_sector_valuation_stats
    print(get_sector_financial_agg('白酒', sector_type='industry'))
    print(get_sector_valuation_stats('白酒', sector_type='industry'))
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


def _median(values):
    """计算中位数"""
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2
    return s[mid]


def _search_sector(sector_type, keyword):
    """模糊搜索板块，返回 (code, name)"""
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT DISTINCT sector_code, sector_name FROM {table}
                WHERE sector_name LIKE %s LIMIT 5
            """, (f'%{keyword}%',))
            matches = cursor.fetchall()
            if not matches:
                return None
            exact = [m for m in matches if m[1] == keyword]
            return exact[0] if exact else matches[0]
    finally:
        conn.close()


def _get_constituents(sector_code, sector_type):
    """获取板块成分股列表"""
    cons_table = 'sector_industry_cons' if sector_type == 'industry' else 'sector_concept_cons'
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT stock_code, stock_name FROM {cons_table}
                WHERE sector_code = %s
            """, (sector_code,))
            return cursor.fetchall()
    finally:
        conn.close()


def _get_latest_valuations(stock_codes):
    """批量获取成分股最新估值数据 (PE_TTM, PB, total_mv, close, pct_chg)

    Returns:
        dict: {symbol: {pe_ttm, pb, total_mv, close, pct_chg}}
    """
    if not stock_codes:
        return {}

    # 获取最新交易日
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT MAX(trade_date) FROM stock_kline")
            row = cursor.fetchone()
            if not row or not row[0]:
                return {}
            latest_date = row[0]

            # 批量查询
            placeholders = ','.join(['%s'] * len(stock_codes))
            cursor.execute(f"""
                SELECT symbol, pe_ttm, pb, total_mv, close, pct_chg
                FROM stock_kline
                WHERE symbol IN ({placeholders}) AND trade_date = %s
            """, (*stock_codes, latest_date))

            result = {}
            for row in cursor.fetchall():
                result[row[0]] = {
                    'pe_ttm': _safe_float(row[1]),
                    'pb': _safe_float(row[2]),
                    'total_mv': _safe_float(row[3]),
                    'close': _safe_float(row[4]),
                    'pct_chg': _safe_float(row[5]),
                }
            return result
    finally:
        conn.close()


def _get_latest_financials(stock_codes):
    """批量获取成分股最新财务数据 (ROE, 毛利率, 营收, 净利润)

    通过查询每只股票最新一期的 income 报表，提取关键指标。

    Returns:
        dict: {symbol: {roe, gross_margin, revenue, net_profit}}
    """
    if not stock_codes:
        return {}

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 获取每只股票最新一期的利润表
            placeholders = ','.join(['%s'] * len(stock_codes))
            cursor.execute(f"""
                SELECT ts_code, report_data, report_date
                FROM stock_financial
                WHERE ts_code IN ({placeholders})
                  AND statement_type = 'income'
                  AND report_date = (
                      SELECT MAX(sf.report_date) FROM stock_financial sf
                      WHERE sf.ts_code = stock_financial.ts_code AND sf.statement_type = 'income'
                  )
            """, (*stock_codes,))

            income_data = {}
            for row in cursor.fetchall():
                ts_code = row[0]
                data = row[1]
                if isinstance(data, str):
                    data = json.loads(data)
                income_data[ts_code] = data

            # 获取资产负债表用于计算ROE
            cursor.execute(f"""
                SELECT ts_code, report_data
                FROM stock_financial
                WHERE ts_code IN ({placeholders})
                  AND statement_type = 'balance'
                  AND report_date = (
                      SELECT MAX(sf.report_date) FROM stock_financial sf
                      WHERE sf.ts_code = stock_financial.ts_code AND sf.statement_type = 'balance'
                  )
            """, (*stock_codes,))

            balance_data = {}
            for row in cursor.fetchall():
                ts_code = row[0]
                data = row[1]
                if isinstance(data, str):
                    data = json.loads(data)
                balance_data[ts_code] = data

            result = {}
            for ts_code in stock_codes:
                symbol = ts_code.split('.')[0]
                income = income_data.get(ts_code, {})
                balance = balance_data.get(ts_code, {})

                if not income:
                    continue

                # 提取字段（兼容不同字段名）
                revenue = None
                for name in ['营业总收入', '营业收入']:
                    v = _safe_float(income.get(name))
                    if v is not None:
                        revenue = v
                        break

                cost = _safe_float(income.get('营业成本'))

                net_profit = None
                for name in ['净利润', '归属于母公司所有者的净利润', '归属于母公司股东的净利润']:
                    v = _safe_float(income.get(name))
                    if v is not None:
                        net_profit = v
                        break

                equity = None
                for name in ['归属于母公司股东权益合计', '归属于母公司所有者权益', '所有者权益（或股东权益）合计']:
                    v = _safe_float(balance.get(name))
                    if v is not None:
                        equity = v
                        break

                # 计算指标
                roe = None
                if net_profit and equity and equity > 0:
                    roe = round(net_profit / equity * 100, 2)

                gross_margin = None
                if revenue and cost and revenue > 0:
                    gross_margin = round((revenue - cost) / revenue * 100, 2)

                result[symbol] = {
                    'roe': roe,
                    'gross_margin': gross_margin,
                    'revenue': revenue,
                    'net_profit': net_profit,
                }

            return result
    finally:
        conn.close()


def _get_valuation_level(percentile):
    """估值水平判断"""
    if percentile is None:
        return "N/A"
    if percentile < 20:
        return "低估"
    elif percentile < 40:
        return "合理偏低"
    elif percentile < 60:
        return "合理"
    elif percentile < 80:
        return "合理偏高"
    else:
        return "高估"


def get_sector_financial_agg(sector_name, sector_type='industry'):
    """
    板块财务聚合分析

    计算板块内所有成分股的平均ROE、平均毛利率、合计营收/净利润等。

    Args:
        sector_name: 板块名称（支持模糊匹配）
        sector_type: 'industry' 或 'concept'

    Returns:
        str: 格式化的板块财务聚合结果
    """
    type_name = '行业' if sector_type == 'industry' else '概念'

    match = _search_sector(sector_type, sector_name)
    if not match:
        return f"未找到{type_name}板块: {sector_name}"

    sector_code, sector_name_real = match

    # 获取成分股
    constituents = _get_constituents(sector_code, sector_type)
    if not constituents:
        return f"板块 [{sector_name_real}] 无成分股数据"

    stock_codes = [c[0] for c in constituents]
    code_name_map = {c[0]: c[1] for c in constituents}

    # 批量获取估值数据
    valuations = _get_latest_valuations(stock_codes)

    # 批量获取财务数据
    financials = _get_latest_financials(stock_codes)

    # 聚合计算
    pe_list = []
    pb_list = []
    mv_list = []
    roe_list = []
    gm_list = []
    total_revenue = 0
    total_net_profit = 0
    valid_count = 0
    revenue_count = 0

    stock_details = []

    for code in stock_codes:
        symbol = code  # stock_code 就是纯数字代码
        name = code_name_map.get(code, code)

        val = valuations.get(symbol, {})
        fin = financials.get(symbol, {})

        pe = val.get('pe_ttm')
        pb = val.get('pb')
        mv = val.get('total_mv')
        roe = fin.get('roe')
        gm = fin.get('gross_margin')
        revenue = fin.get('revenue')
        np_val = fin.get('net_profit')

        # 过滤异常PE值
        if pe is not None and (pe < 0 or pe > 1000):
            pe = None
        if pb is not None and (pb < 0 or pb > 100):
            pb = None

        if pe is not None:
            pe_list.append(pe)
        if pb is not None:
            pb_list.append(pb)
        if mv is not None:
            mv_list.append(mv)
        if roe is not None:
            roe_list.append(roe)
        if gm is not None:
            gm_list.append(gm)
        if revenue is not None:
            total_revenue += revenue
            revenue_count += 1
        if np_val is not None:
            total_net_profit += np_val

        if pe is not None or roe is not None:
            valid_count += 1

        stock_details.append({
            'name': name,
            'code': code,
            'pe': pe,
            'pb': pb,
            'roe': roe,
            'gm': gm,
            'revenue': revenue,
            'mv': mv,
        })

    if valid_count == 0:
        return f"板块 [{sector_name_real}] 无有效财务数据"

    # 格式化输出
    result = f"=== {sector_name_real}板块财务聚合分析 ===\n"
    result += f"板块: {sector_name_real} ({sector_code})\n"
    result += f"成分股: {len(stock_codes)}只  有效估值: {len(pe_list)}只  有效财务: {len(roe_list)}只\n"

    # 估值统计
    result += f"\n【估值统计】\n"
    if pe_list:
        result += (f"  PE_TTM:  均值 {sum(pe_list)/len(pe_list):.1f}"
                   f"  中位数 {_median(pe_list):.1f}"
                   f"  最小 {min(pe_list):.1f}"
                   f"  最大 {max(pe_list):.1f}\n")
    if pb_list:
        result += (f"  PB:      均值 {sum(pb_list)/len(pb_list):.1f}"
                   f"  中位数 {_median(pb_list):.1f}"
                   f"  最小 {min(pb_list):.1f}"
                   f"  最大 {max(pb_list):.1f}\n")

    # 基本面指标
    result += f"\n【基本面指标】\n"
    if roe_list:
        result += f"  平均ROE: {sum(roe_list)/len(roe_list):.2f}%\n"
    if gm_list:
        result += f"  平均毛利率: {sum(gm_list)/len(gm_list):.2f}%\n"
    if total_revenue > 0:
        result += f"  板块合计营收: {total_revenue / 1e8:.2f}亿\n"
    if total_net_profit != 0:
        result += f"  板块合计净利润: {total_net_profit / 1e8:.2f}亿\n"
    if mv_list:
        result += f"  板块总市值: {sum(mv_list):.2f}亿\n"

    return result


def get_sector_valuation_stats(sector_name, sector_type='industry'):
    """
    板块估值分布统计

    统计板块内成分股的PE/PB分布，按估值水平分组。

    Args:
        sector_name: 板块名称（支持模糊匹配）
        sector_type: 'industry' 或 'concept'

    Returns:
        str: 格式化的估值分布结果
    """
    type_name = '行业' if sector_type == 'industry' else '概念'

    match = _search_sector(sector_type, sector_name)
    if not match:
        return f"未找到{type_name}板块: {sector_name}"

    sector_code, sector_name_real = match

    # 获取成分股
    constituents = _get_constituents(sector_code, sector_type)
    if not constituents:
        return f"板块 [{sector_name_real}] 无成分股数据"

    stock_codes = [c[0] for c in constituents]
    code_name_map = {c[0]: c[1] for c in constituents}

    # 批量获取估值数据
    valuations = _get_latest_valuations(stock_codes)

    # 构建个股估值列表并按PE排序
    stock_vals = []
    pe_all = []
    pb_all = []

    for code in stock_codes:
        symbol = code
        name = code_name_map.get(code, code)
        val = valuations.get(symbol, {})

        pe = val.get('pe_ttm')
        pb = val.get('pb')

        # 过滤异常值
        if pe is not None and (pe < 0 or pe > 1000):
            pe = None
        if pb is not None and (pb < 0 or pb > 100):
            pb = None

        if pe is not None:
            pe_all.append(pe)
        if pb is not None:
            pb_all.append(pb)

        stock_vals.append({
            'name': name,
            'code': code,
            'pe': pe,
            'pb': pb,
        })

    if not pe_all and not pb_all:
        return f"板块 [{sector_name_real}] 无有效估值数据"

    # 估值分布统计（基于PE）
    levels = {'低估': [], '合理偏低': [], '合理': [], '合理偏高': [], '高估': [], 'N/A': []}

    if pe_all:
        pe_sorted = sorted(pe_all)
        for sv in stock_vals:
            pe = sv['pe']
            if pe is None:
                levels['N/A'].append(sv)
                continue
            # 计算在板块内的百分位
            count_below = sum(1 for v in pe_sorted if v < pe)
            percentile = count_below / len(pe_sorted) * 100
            level = _get_valuation_level(percentile)
            sv['pe_percentile'] = percentile
            sv['pe_level'] = level
            levels[level].append(sv)
    else:
        for sv in stock_vals:
            levels['N/A'].append(sv)

    # 格式化输出
    result = f"=== {sector_name_real}板块估值分布 ===\n"
    result += f"板块: {sector_name_real} ({sector_code})\n"
    result += f"成分股: {len(stock_codes)}只  有效PE: {len(pe_all)}只  有效PB: {len(pb_all)}只\n"

    # 汇总统计
    result += f"\n【PE_TTM统计】\n"
    if pe_all:
        result += (f"  均值: {sum(pe_all)/len(pe_all):.1f}  "
                   f"中位数: {_median(pe_all):.1f}  "
                   f"最小: {min(pe_all):.1f}  "
                   f"最大: {max(pe_all):.1f}\n")

    result += f"\n【PB统计】\n"
    if pb_all:
        result += (f"  均值: {sum(pb_all)/len(pb_all):.1f}  "
                   f"中位数: {_median(pb_all):.1f}  "
                   f"最小: {min(pb_all):.1f}  "
                   f"最大: {max(pb_all):.1f}\n")

    # 估值分布
    result += f"\n【估值分布（基于PE百分位）】\n"
    for level in ['低估', '合理偏低', '合理', '合理偏高', '高估']:
        stocks = levels[level]
        if stocks:
            names = [f"{s['name']}" for s in stocks[:5]]
            result += f"  {level}(<{'20' if level=='低估' else '40' if level=='合理偏低' else '60' if level=='合理' else '80'}%): {len(stocks)}只"
            if names:
                result += f"  ({', '.join(names)}{'...' if len(stocks)>5 else ''})"
            result += "\n"

    if levels['N/A']:
        result += f"  无数据: {len(levels['N/A'])}只\n"

    # 按PE从低到高排序的个股明细（前10 + 后10）
    valid_stocks = [sv for sv in stock_vals if sv['pe'] is not None]
    valid_stocks.sort(key=lambda x: x['pe'])

    if valid_stocks:
        result += f"\n【低PE个股】(PE最低前5)\n"
        for sv in valid_stocks[:5]:
            result += f"  {sv['name']}({sv['code']}): PE {sv['pe']:.1f}\n"

        result += f"\n【高PE个股】(PE最高前5)\n"
        for sv in valid_stocks[-5:]:
            result += f"  {sv['name']}({sv['code']}): PE {sv['pe']:.1f}\n"

    return result


if __name__ == '__main__':
    print("\n1. 白酒板块财务聚合:")
    print(get_sector_financial_agg('白酒', sector_type='industry'))

    print("\n2. 白酒板块估值分布:")
    print(get_sector_valuation_stats('白酒', sector_type='industry'))
