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

    Args:
        sector_name: 行业板块名称
        symbols: 限定的股票代码列表（可选，用于只计算49只内的板块均值）

    Returns:
        dict: {
            '毛利率': float, 'ROE': float, '扣非净利率': float,
            '营收同比增长率': float, '净利润同比增长率': float,
            'pe_ttm_percentile': float, 'pb_percentile': float,
            'stock_count': int
        }
    """
    # 获取板块成分股
    constituents = get_sector_constituents(sector_name)
    if not constituents:
        return {}

    sector_symbols = [c[0] for c in constituents]

    # 如果指定了symbols，只计算交集
    if symbols:
        sector_symbols = [s for s in sector_symbols if s in symbols]
        if not sector_symbols:
            return {}

    # 收集各股票的指标值
    metrics = {
        '毛利率': [], 'ROE': [], '扣非净利率': [], '净利率': [],
        '经营现金流净利润比': [], '应收账款占比': [],
        '营收同比增长率': [], '净利润同比增长率': [],
        'pe_ttm_percentile': [], 'pb_percentile': [],
    }

    # 构建 ts_code 列表
    ts_codes = []
    for sym in sector_symbols:
        if sym.startswith('6'):
            ts_codes.append(sym + '.SH')
        else:
            ts_codes.append(sym + '.SZ')

    if not ts_codes:
        return {}

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 查询财务数据
            placeholders = ','.join(['%s'] * len(ts_codes))
            cursor.execute(f"""
                SELECT ts_code, indicator_name, indicator_value
                FROM stock_financial
                WHERE ts_code IN ({placeholders})
                  AND indicator_name IN ('毛利率', 'ROE', '扣非净利率', '净利率',
                                         '经营现金流净利润比', '应收账款占比',
                                         '营收同比增长率', '净利润同比增长率')
            """, ts_codes)

            for row in cursor.fetchall():
                ts_code, ind_name, ind_value = row
                v = _safe_float(ind_value)
                if v is not None and ind_name in metrics:
                    metrics[ind_name].append(v)

            # 查询估值数据（取最新交易日）
            cursor.execute(f"""
                SELECT ts_code, pe_ttm_percentile, pb_percentile
                FROM stock_kline
                WHERE ts_code IN ({placeholders})
                  AND trade_date = (SELECT MAX(trade_date) FROM stock_kline WHERE ts_code = %s)
            """, (*ts_codes, ts_codes[0]))

            for row in cursor.fetchall():
                ts_code, pe_pct, pb_pct = row
                pe_v = _safe_float(pe_pct)
                pb_v = _safe_float(pb_pct)
                if pe_v is not None:
                    metrics['pe_ttm_percentile'].append(pe_v)
                if pb_v is not None:
                    metrics['pb_percentile'].append(pb_v)

    finally:
        conn.close()

    # 计算均值
    result = {'sector_name': sector_name, 'stock_count': len(sector_symbols)}
    for k, vals in metrics.items():
        if vals:
            result[k] = round(sum(vals) / len(vals), 2)
        else:
            result[k] = None

    return result


def get_sector_performance(sector_name):
    """获取板块近期行情表现

    Args:
        sector_name: 行业板块名称

    Returns:
        dict: {'pct_5d': float, 'pct_20d': float, 'avg_amount': float}
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 先获取板块代码
            cursor.execute("""
                SELECT DISTINCT sector_code FROM sector_industry_cons
                WHERE sector_name = %s
                LIMIT 1
            """, (sector_name,))
            row = cursor.fetchone()
            if not row:
                return {}
            sector_code = row[0]

            # 查询板块行情
            cursor.execute("""
                SELECT trade_date, close, amount
                FROM sector_industry_daily
                WHERE sector_code = %s
                ORDER BY trade_date DESC
                LIMIT 25
            """, (sector_code,))
            rows = cursor.fetchall()

            if not rows or len(rows) < 2:
                return {}

            # 按日期正序
            rows = list(reversed(rows))

            # 近5日涨跌幅
            pct_5d = None
            if len(rows) >= 5:
                close_now = _safe_float(rows[-1][1])
                close_5ago = _safe_float(rows[-5][1])
                if close_now and close_5ago and close_5ago > 0:
                    pct_5d = round((close_now - close_5ago) / close_5ago * 100, 2)

            # 近20日涨跌幅
            pct_20d = None
            if len(rows) >= 20:
                close_now = _safe_float(rows[-1][1])
                close_start = _safe_float(rows[-20][1])
                if close_now and close_start and close_start > 0:
                    pct_20d = round((close_now - close_start) / close_start * 100, 2)

            # 平均成交额
            amounts = [_safe_float(r[2]) for r in rows if _safe_float(r[2]) is not None]
            avg_amount = round(sum(amounts) / len(amounts), 2) if amounts else None

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
