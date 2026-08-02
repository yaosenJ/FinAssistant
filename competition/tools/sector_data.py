#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块数据工具
从数据库获取股票所属行业板块及板块聚合数据

功能:
- 查询股票所属行业板块（从 sector_industry_cons 表）
- 获取板块成分股列表
- 计算板块聚合指标（均值、中位数）
- 获取板块行情表现（5/20日涨跌幅）

用法:
    from tools.sector_data import get_stock_sector, get_sector_aggregates, get_sector_performance
    print(get_stock_sector('600519'))  # 返回 '白酒'
    print(get_sector_aggregates('白酒'))  # 返回板块均值
"""

import json
import logging

try:
    from tools.db import get_connection
except ImportError:
    from db import get_connection

logger = logging.getLogger(__name__)

# 比赛指定的49只股票板块划分
STOCK_SECTORS = {
    '金融板块': ['601318.SH', '600036.SH', '601688.SH', '601398.SH', '601288.SH', '601988.SH', '600000.SH', '601998.SH'],
    '消费板块': ['600519.SH', '000858.SZ', '600887.SH', '603288.SH', '600660.SH', '000333.SZ', '000651.SZ', '601888.SH', '600809.SH'],
    '新能源/电力板块': ['300750.SZ', '002594.SZ', '601012.SH', '300274.SZ', '600900.SH', '600438.SH', '600089.SH', '600212.SH'],
    '科技/AI/半导体板块': ['688981.SH', '600584.SH', '600183.SH', '300308.SZ', '300394.SZ', '603501.SH', '600703.SH', '600570.SH', '600845.SH', '688041.SH', '603986.SH', '002475.SZ'],
    '周期/资源板块': ['601899.SH', '600309.SH', '601600.SH', '600028.SH', '601088.SH', '600547.SH', '600426.SH', '601168.SH'],
    '高端制造/基建板块': ['600031.SH', '601766.SH', '601668.SH', '601186.SH'],
}


def _safe_float(val):
    """安全转 float"""
    if val is None:
        return None
    try:
        s = str(val).replace(',', '').replace('%', '').strip()
        if not s or s in ('--', '-', 'None', 'nan'):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def get_stock_sector(symbol):
    """查询股票所属的行业板块

    Args:
        symbol: 纯数字股票代码，如 '600519'

    Returns:
        str: 行业板块名称，未找到返回 '未知板块'
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 从 sector_industry_cons 表查询
            cursor.execute("""
                SELECT sector_name FROM sector_industry_cons
                WHERE stock_code = %s
                LIMIT 1
            """, (symbol,))
            row = cursor.fetchone()
            if row:
                return row[0]

            # 尝试从 company_info 表查询
            ts_code = symbol + '.SH' if symbol.startswith('6') else symbol + '.SZ'
            cursor.execute("""
                SELECT industry FROM company_info
                WHERE ts_code = %s
            """, (ts_code,))
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]

            return '未知板块'
    finally:
        conn.close()


def get_sector_constituents(sector_name):
    """获取板块成分股列表

    Args:
        sector_name: 行业板块名称，如 '白酒'

    Returns:
        list: [(symbol, stock_name), ...]
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT stock_code, stock_name FROM sector_industry_cons
                WHERE sector_name = %s
            """, (sector_name,))
            return cursor.fetchall()
    finally:
        conn.close()


def get_sector_aggregates(sector_name, symbols=None):
    """计算板块财务和估值聚合指标

    使用比赛指定的49只股票板块划分，直接从数据库查询计算板块均值。

    Args:
        sector_name: 行业板块名称（如'金融板块'、'消费板块'等）
        symbols: 限定的股票代码列表（可选，用于只计算49只内的板块均值）

    Returns:
        dict: {
            '毛利率': float, '营业利润率': float, 'ROE': float,
            '营收同比增长率': float, '净利润同比增长率': float,
            'pe_ttm': float, 'pb': float,
            'stock_count': int
        }
    """
    # 获取板块成分股
    ts_codes = STOCK_SECTORS.get(sector_name, [])
    if not ts_codes:
        return {}

    # 如果指定了symbols，只计算交集
    if symbols:
        ts_codes = [ts for ts in ts_codes if ts.split('.')[0] in symbols]
        if not ts_codes:
            return {}

    # 收集各股票的指标值
    metrics = {
        '毛利率': [], '营业利润率': [], 'ROE': [], '净利率': [],
        '经营现金流净利润比': [], '应收账款占比': [],
        '营收同比增长率': [], '净利润同比增长率': [],
        'pe_ttm': [], 'pb': [],
    }

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(ts_codes))

            # 查询利润表
            cursor.execute(f"""
                SELECT ts_code, report_data
                FROM stock_financial
                WHERE ts_code IN ({placeholders})
                  AND statement_type = 'income'
                  AND report_date = (
                      SELECT MAX(sf.report_date) FROM stock_financial sf
                      WHERE sf.ts_code = stock_financial.ts_code AND sf.statement_type = 'income'
                  )
            """, ts_codes)

            income_data = {}
            for row in cursor.fetchall():
                ts_code, data = row
                if isinstance(data, str):
                    data = json.loads(data)
                income_data[ts_code] = data

            # 查询资产负债表
            cursor.execute(f"""
                SELECT ts_code, report_data
                FROM stock_financial
                WHERE ts_code IN ({placeholders})
                  AND statement_type = 'balance'
                  AND report_date = (
                      SELECT MAX(sf.report_date) FROM stock_financial sf
                      WHERE sf.ts_code = stock_financial.ts_code AND sf.statement_type = 'balance'
                  )
            """, ts_codes)

            balance_data = {}
            for row in cursor.fetchall():
                ts_code, data = row
                if isinstance(data, str):
                    data = json.loads(data)
                balance_data[ts_code] = data

            # 查询估值数据
            cursor.execute(f"""
                SELECT ts_code, pe_ttm, pb
                FROM stock_kline
                WHERE ts_code IN ({placeholders})
                  AND trade_date = (SELECT MAX(trade_date) FROM stock_kline WHERE ts_code = %s)
            """, (*ts_codes, ts_codes[0]))

            for row in cursor.fetchall():
                ts_code, pe_ttm, pb = row
                pe_v = _safe_float(pe_ttm)
                pb_v = _safe_float(pb)
                if pe_v is not None and pe_v > 0:
                    metrics['pe_ttm'].append(pe_v)
                if pb_v is not None and pb_v > 0:
                    metrics['pb'].append(pb_v)

    finally:
        conn.close()

    # 从JSON数据中提取指标并计算均值
    for ts_code in ts_codes:
        income = income_data.get(ts_code, {})
        balance = balance_data.get(ts_code, {})
        if not income:
            continue

        # 营收
        revenue = None
        for name in ['营业总收入', '营业收入']:
            v = _safe_float(income.get(name))
            if v is not None:
                revenue = v
                break

        # 营业成本/营业支出
        cost = _safe_float(income.get('营业成本')) or _safe_float(income.get('营业支出'))

        # 净利润
        net_profit = None
        for name in ['净利润', '归属于母公司所有者的净利润']:
            v = _safe_float(income.get(name))
            if v is not None:
                net_profit = v
                break

        # 归母权益
        equity = None
        for name in ['归属于母公司股东权益合计', '所有者权益(或股东权益)合计']:
            v = _safe_float(balance.get(name))
            if v is not None:
                equity = v
                break

        # 毛利率/营业利润率
        is_bank = balance.get('发放贷款及垫款净额') is not None or balance.get('客户存款') is not None
        if revenue and cost and revenue > 0:
            margin = round((revenue - cost) / revenue * 100, 2)
            if is_bank:
                metrics['营业利润率'].append(margin)
            else:
                metrics['毛利率'].append(margin)

        # ROE
        if net_profit and equity and equity > 0:
            metrics['ROE'].append(round(net_profit / equity * 100, 2))

        # 净利率
        if net_profit and revenue and revenue > 0:
            metrics['净利率'].append(round(net_profit / revenue * 100, 2))

    # 计算均值
    result = {'sector_name': sector_name, 'stock_count': len(ts_codes)}
    for k, vals in metrics.items():
        if vals:
            result[k] = round(sum(vals) / len(vals), 2)
        else:
            result[k] = None

    return result


def get_sector_performance(sector_name):
    """获取板块近期行情表现（从成分股kline数据计算）

    Args:
        sector_name: 行业板块名称（如'金融板块'、'消费板块'等）

    Returns:
        dict: {'pct_5d': float, 'pct_20d': float, 'avg_amount': float}
    """
    ts_codes = STOCK_SECTORS.get(sector_name, [])
    if not ts_codes:
        return {}

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(ts_codes))

            # 获取每只股票最近25个交易日的收盘价和成交额
            cursor.execute(f"""
                SELECT ts_code, trade_date, close, amount
                FROM stock_kline
                WHERE ts_code IN ({placeholders})
                  AND trade_date >= (
                      SELECT trade_date FROM (
                          SELECT DISTINCT trade_date FROM stock_kline
                          WHERE ts_code = %s
                          ORDER BY trade_date DESC LIMIT 25
                      ) t ORDER BY trade_date ASC LIMIT 1
                  )
                ORDER BY ts_code, trade_date
            """, (*ts_codes, ts_codes[0]))

            rows = cursor.fetchall()
            if not rows:
                return {}

            # 按股票分组
            stock_data = {}  # {ts_code: [(trade_date, close, amount), ...]}
            for ts_code, trade_date, close, amount in rows:
                if ts_code not in stock_data:
                    stock_data[ts_code] = []
                stock_data[ts_code].append((trade_date, _safe_float(close), _safe_float(amount)))

            # 计算每只股票的5日和20日涨跌幅
            pct_5d_list = []
            pct_20d_list = []
            amount_list = []

            for ts_code, data in stock_data.items():
                if len(data) < 2:
                    continue
                # 按日期正序
                data.sort(key=lambda x: x[0])
                closes = [d[1] for d in data if d[1] is not None]

                if len(closes) >= 5 and closes[-5] > 0:
                    pct_5d_list.append((closes[-1] - closes[-5]) / closes[-5] * 100)
                if len(closes) >= 20 and closes[-20] > 0:
                    pct_20d_list.append((closes[-1] - closes[-20]) / closes[-20] * 100)

                amounts = [d[2] for d in data if d[2] is not None]
                if amounts:
                    amount_list.append(sum(amounts) / len(amounts))

            pct_5d = round(sum(pct_5d_list) / len(pct_5d_list), 2) if pct_5d_list else None
            pct_20d = round(sum(pct_20d_list) / len(pct_20d_list), 2) if pct_20d_list else None
            avg_amount = round(sum(amount_list) / len(amount_list), 2) if amount_list else None

            return {
                'pct_5d': pct_5d,
                'pct_20d': pct_20d,
                'avg_amount': avg_amount,
            }
    finally:
        conn.close()


def get_all_sectors_for_stocks(symbols):
    """批量查询多只股票的行业板块归属

    Args:
        symbols: 股票代码列表，如 ['600519', '000858', ...]

    Returns:
        dict: {symbol: sector_name, ...}
    """
    result = {}
    for sym in symbols:
        result[sym] = get_stock_sector(sym)
    return result


if __name__ == '__main__':
    # 测试
    print("=== 测试板块数据工具 ===")

    # 查询单只股票所属板块
    sector = get_stock_sector('600519')
    print(f"600519 所属板块: {sector}")

    # 获取板块聚合数据
    agg = get_sector_aggregates(sector)
    print(f"\n{sector} 板块聚合指标:")
    for k, v in agg.items():
        print(f"  {k}: {v}")

    # 获取板块行情
    perf = get_sector_performance(sector)
    print(f"\n{sector} 板块行情:")
    for k, v in perf.items():
        print(f"  {k}: {v}")
