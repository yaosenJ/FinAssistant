#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股-板块映射工具
查询某只股票属于哪些行业/概念板块，以及各板块近期表现

功能:
- 查询个股所属的所有行业板块和概念板块
- 展示各板块近5日/20日涨跌幅和成交额趋势

用法:
    from tools.stock_sector_mapping import find_stock_sectors
    print(find_stock_sectors('600519.SH'))
"""

import logging

try:
    from tools.db import get_connection
except ImportError:
    from db import get_connection

logger = logging.getLogger(__name__)


def _get_stock_name(ts_code):
    """获取股票名称"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT stock_name FROM company_info WHERE ts_code = %s",
                (ts_code,)
            )
            row = cursor.fetchone()
            return row[0] if row else ts_code
    finally:
        conn.close()


def _get_symbol(ts_code):
    """从 ts_code 提取纯数字代码 (如 600519.SH -> 600519)"""
    return ts_code.split('.')[0]


def _calc_sector_performance(sector_code, days=20):
    """计算板块近N日的涨跌幅和成交额趋势

    Args:
        sector_code: 板块代码
        sector_type: 'industry' 或 'concept'
        days: 计算天数

    Returns:
        dict: {pct_5d, pct_20d, avg_amount, latest_date}
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 尝试行业表
            cursor.execute("""
                SELECT trade_date, close, amount, pct_chg
                FROM sector_industry_daily
                WHERE sector_code = %s
                ORDER BY trade_date DESC
                LIMIT %s
            """, (sector_code, days))
            rows = cursor.fetchall()

            if not rows:
                # 尝试概念表
                cursor.execute("""
                    SELECT trade_date, close, amount, pct_chg
                    FROM sector_concept_daily
                    WHERE sector_code = %s
                    ORDER BY trade_date DESC
                    LIMIT %s
                """, (sector_code, days))
                rows = cursor.fetchall()

            if not rows:
                return None

            # 按日期正序
            rows = list(reversed(rows))

            # 近5日涨跌幅
            pct_5d = None
            if len(rows) >= 5:
                close_now = float(rows[-1][1] or 0)
                close_5ago = float(rows[-5][1] or 0)
                if close_5ago > 0:
                    pct_5d = round((close_now - close_5ago) / close_5ago * 100, 2)

            # 近20日涨跌幅
            pct_20d = None
            if len(rows) >= 2:
                close_now = float(rows[-1][1] or 0)
                close_start = float(rows[0][1] or 0)
                if close_start > 0:
                    pct_20d = round((close_now - close_start) / close_start * 100, 2)

            # 平均成交额
            amounts = [float(r[2] or 0) for r in rows]
            avg_amount = sum(amounts) / len(amounts) if amounts else 0

            return {
                'pct_5d': pct_5d,
                'pct_20d': pct_20d,
                'avg_amount': avg_amount,
                'latest_date': rows[-1][0],
                'days': len(rows),
            }
    finally:
        conn.close()


def find_stock_sectors(ts_code, sector_type=None):
    """
    查询个股所属的所有板块及各板块近期表现

    Args:
        ts_code: 股票代码，如 600519.SH 或 000001.SZ
        sector_type: 过滤板块类型，'industry'=仅行业, 'concept'=仅概念, None=全部

    Returns:
        str: 格式化的板块归属结果
    """
    symbol = _get_symbol(ts_code)
    stock_name = _get_stock_name(ts_code)

    # 查询行业板块
    industry_sectors = []
    if sector_type is None or sector_type == 'industry':
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT sector_code, sector_name
                    FROM sector_industry_cons
                    WHERE stock_code = %s
                """, (symbol,))
                industry_sectors = cursor.fetchall()
        finally:
            conn.close()

    # 查询概念板块
    concept_sectors = []
    if sector_type is None or sector_type == 'concept':
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT sector_code, sector_name
                    FROM sector_concept_cons
                    WHERE stock_code = %s
                """, (symbol,))
                concept_sectors = cursor.fetchall()
        finally:
            conn.close()

    if not industry_sectors and not concept_sectors:
        return f"未找到 {ts_code} ({stock_name}) 的板块归属数据"

    # 格式化输出
    result = f"=== {ts_code} ({stock_name}) 所属板块 ===\n"

    # 行业板块
    if industry_sectors:
        result += f"\n【行业板块】({len(industry_sectors)}个)\n"
        for sector_code, sector_name in sorted(industry_sectors, key=lambda x: x[1]):
            perf = _calc_sector_performance(sector_code)
            if perf:
                pct_5d = f"{perf['pct_5d']:+.2f}%" if perf['pct_5d'] is not None else "N/A"
                pct_20d = f"{perf['pct_20d']:+.2f}%" if perf['pct_20d'] is not None else "N/A"
                result += f"  {sector_name} ({sector_code})  近5日: {pct_5d}  近20日: {pct_20d}\n"
            else:
                result += f"  {sector_name} ({sector_code})  无近期行情数据\n"

    # 概念板块
    if concept_sectors:
        result += f"\n【概念板块】({len(concept_sectors)}个)\n"
        for sector_code, sector_name in sorted(concept_sectors, key=lambda x: x[1]):
            perf = _calc_sector_performance(sector_code)
            if perf:
                pct_5d = f"{perf['pct_5d']:+.2f}%" if perf['pct_5d'] is not None else "N/A"
                pct_20d = f"{perf['pct_20d']:+.2f}%" if perf['pct_20d'] is not None else "N/A"
                result += f"  {sector_name} ({sector_code})  近5日: {pct_5d}  近20日: {pct_20d}\n"
            else:
                result += f"  {sector_name} ({sector_code})  无近期行情数据\n"

    return result


if __name__ == '__main__':
    print(find_stock_sectors('600519.SH'))
    print()
    print(find_stock_sectors('000001.SZ'))
