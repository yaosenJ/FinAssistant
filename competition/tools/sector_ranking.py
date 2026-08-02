#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块排名工具
从 MySQL market_data.sector_industry_daily / sector_concept_daily 表获取数据，计算板块排名

功能:
- 板块涨跌幅排名
- 板块成交额排名
- 板块换手率排名
- 多日连续上涨/下跌板块
- 板块资金流向分析

用法:
    from tools.sector_ranking import get_sector_ranking, get_sector_top_gainers
    print(get_sector_ranking(sector_type='industry', top_n=10))
    print(get_sector_top_gainers(sector_type='concept', days=3))
"""

import logging
from datetime import datetime, timedelta

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


def _get_trade_dates(sector_type='industry', days=5):
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
            return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_sector_ranking(sector_type='industry', trade_date=None, top_n=20, sort_by='pct_chg'):
    """
    获取板块排名

    Args:
        sector_type: 'industry'（行业）或 'concept'（概念）
        trade_date: 交易日期，默认最新日期
        top_n: 返回前N名
        sort_by: 排序字段 'pct_chg'（涨跌幅）/ 'amount'（成交额）/ 'vol'（成交量）

    Returns:
        str: 格式化的排名结果
    """
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    type_name = '行业' if sector_type == 'industry' else '概念'

    if trade_date is None:
        trade_date = _get_latest_trade_date(sector_type)
        if not trade_date:
            return f"错误: 无法获取{type_name}板块数据"

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 验证排序字段
            valid_sort_fields = {'pct_chg', 'amount', 'vol'}
            if sort_by not in valid_sort_fields:
                sort_by = 'pct_chg'

            order = 'DESC'

            cursor.execute(f"""
                SELECT sector_name, sector_code, trade_date,
                       open, high, low, close, vol, amount, pct_chg
                FROM {table}
                WHERE trade_date = %s
                ORDER BY {sort_by} {order}
                LIMIT %s
            """, (trade_date, top_n))

            rows = cursor.fetchall()

            if not rows:
                return f"{trade_date} 无{type_name}板块数据"

            # 格式化输出
            sort_name = {'pct_chg': '涨跌幅', 'amount': '成交额', 'vol': '成交量'}
            result = f"=== {type_name}板块排名 ({trade_date}) ===\n"
            result += f"排序依据: {sort_name.get(sort_by, sort_by)}\n\n"
            result += f"{'排名':<4} {'板块名称':<12} {'涨跌幅(%)':<10} {'成交额(亿)':<12}\n"
            result += "-" * 40 + "\n"

            for i, row in enumerate(rows, 1):
                sector_name = row[0]
                pct_chg = row[9] or 0
                amount = (row[8] or 0) / 1e8  # 转换为亿
                result += f"{i:<4} {sector_name:<12} {pct_chg:<10.2f} {amount:<12.2f}\n"

            return result

    finally:
        conn.close()


def get_sector_top_gainers(sector_type='industry', days=3, top_n=10):
    """
    获取连续上涨的板块

    Args:
        sector_type: 'industry' 或 'concept'
        days: 连续上涨天数
        top_n: 返回前N名

    Returns:
        str: 格式化的结果
    """
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    type_name = '行业' if sector_type == 'industry' else '概念'

    trade_dates = _get_trade_dates(sector_type, days)
    if len(trade_dates) < days:
        return f"数据不足，无法计算连续{days}天上涨板块"

    trade_dates_sorted = sorted(trade_dates)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 查询连续N天都上涨的板块
            placeholders = ','.join(['%s'] * days)
            cursor.execute(f"""
                SELECT sector_name, sector_code,
                       COUNT(*) as up_days,
                       SUM(pct_chg) as total_chg,
                       AVG(pct_chg) as avg_chg
                FROM {table}
                WHERE trade_date IN ({placeholders})
                  AND pct_chg > 0
                GROUP BY sector_name, sector_code
                HAVING up_days = %s
                ORDER BY total_chg DESC
                LIMIT %s
            """, (*trade_dates_sorted, days, top_n))

            rows = cursor.fetchall()

            if not rows:
                return f"近{days}个交易日无连续上涨的{type_name}板块"

            result = f"=== 连续{days}天上涨的{type_name}板块 ===\n"
            result += f"日期范围: {trade_dates_sorted[0]} ~ {trade_dates_sorted[-1]}\n\n"
            result += f"{'排名':<4} {'板块名称':<12} {'累计涨幅(%)':<12} {'日均涨幅(%)':<12}\n"
            result += "-" * 42 + "\n"

            for i, row in enumerate(rows, 1):
                sector_name = row[0]
                total_chg = row[3] or 0
                avg_chg = row[4] or 0
                result += f"{i:<4} {sector_name:<12} {total_chg:<12.2f} {avg_chg:<12.2f}\n"

            return result

    finally:
        conn.close()


def get_sector_top_losers(sector_type='industry', days=3, top_n=10):
    """
    获取连续下跌的板块

    Args:
        sector_type: 'industry' 或 'concept'
        days: 连续下跌天数
        top_n: 返回前N名

    Returns:
        str: 格式化的结果
    """
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    type_name = '行业' if sector_type == 'industry' else '概念'

    trade_dates = _get_trade_dates(sector_type, days)
    if len(trade_dates) < days:
        return f"数据不足，无法计算连续{days}天下跌板块"

    trade_dates_sorted = sorted(trade_dates)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 查询连续N天都下跌的板块
            placeholders = ','.join(['%s'] * days)
            cursor.execute(f"""
                SELECT sector_name, sector_code,
                       COUNT(*) as down_days,
                       SUM(pct_chg) as total_chg,
                       AVG(pct_chg) as avg_chg
                FROM {table}
                WHERE trade_date IN ({placeholders})
                  AND pct_chg < 0
                GROUP BY sector_name, sector_code
                HAVING down_days = %s
                ORDER BY total_chg ASC
                LIMIT %s
            """, (*trade_dates_sorted, days, top_n))

            rows = cursor.fetchall()

            if not rows:
                return f"近{days}个交易日无连续下跌的{type_name}板块"

            result = f"=== 连续{days}天下跌的{type_name}板块 ===\n"
            result += f"日期范围: {trade_dates_sorted[0]} ~ {trade_dates_sorted[-1]}\n\n"
            result += f"{'排名':<4} {'板块名称':<12} {'累计跌幅(%)':<12} {'日均跌幅(%)':<12}\n"
            result += "-" * 42 + "\n"

            for i, row in enumerate(rows, 1):
                sector_name = row[0]
                total_chg = row[3] or 0
                avg_chg = row[4] or 0
                result += f"{i:<4} {sector_name:<12} {total_chg:<12.2f} {avg_chg:<12.2f}\n"

            return result

    finally:
        conn.close()


def get_sector_summary(sector_type='industry', trade_date=None):
    """
    获取板块市场概览

    Args:
        sector_type: 'industry' 或 'concept'
        trade_date: 交易日期，默认最新日期

    Returns:
        str: 格式化的概览信息
    """
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    type_name = '行业' if sector_type == 'industry' else '概念'

    if trade_date is None:
        trade_date = _get_latest_trade_date(sector_type)
        if not trade_date:
            return f"错误: 无法获取{type_name}板块数据"

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 统计涨跌情况
            cursor.execute(f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) as up_count,
                    SUM(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END) as down_count,
                    SUM(CASE WHEN pct_chg = 0 THEN 1 ELSE 0 END) as flat_count,
                    AVG(pct_chg) as avg_chg,
                    MAX(pct_chg) as max_chg,
                    MIN(pct_chg) as min_chg,
                    SUM(amount) as total_amount
                FROM {table}
                WHERE trade_date = %s
            """, (trade_date,))

            row = cursor.fetchone()
            if not row:
                return f"{trade_date} 无{type_name}板块数据"

            total = row[0] or 0
            up_count = row[1] or 0
            down_count = row[2] or 0
            flat_count = row[3] or 0
            avg_chg = row[4] or 0
            max_chg = row[5] or 0
            min_chg = row[6] or 0
            total_amount = (row[7] or 0) / 1e8

            # 涨停/跌停板块
            cursor.execute(f"""
                SELECT sector_name, pct_chg
                FROM {table}
                WHERE trade_date = %s AND pct_chg >= 9.9
                ORDER BY pct_chg DESC
                LIMIT 5
            """, (trade_date,))
            limit_up = cursor.fetchall()

            cursor.execute(f"""
                SELECT sector_name, pct_chg
                FROM {table}
                WHERE trade_date = %s AND pct_chg <= -9.9
                ORDER BY pct_chg ASC
                LIMIT 5
            """, (trade_date,))
            limit_down = cursor.fetchall()

            # 格式化输出
            result = f"=== {type_name}板块市场概览 ({trade_date}) ===\n\n"
            result += f"总板块数: {total}\n"
            result += f"上涨: {up_count}  下跌: {down_count}  平盘: {flat_count}\n"
            result += f"涨跌比: {up_count}:{down_count}\n\n"
            result += f"平均涨跌幅: {avg_chg:.2f}%\n"
            result += f"最大涨幅: {max_chg:.2f}%\n"
            result += f"最大跌幅: {min_chg:.2f}%\n"
            result += f"总成交额: {total_amount:.2f}亿\n"

            if limit_up:
                result += f"\n【涨幅居前板块】\n"
                for name, chg in limit_up:
                    result += f"  {name}: +{chg:.2f}%\n"

            if limit_down:
                result += f"\n【跌幅居前板块】\n"
                for name, chg in limit_down:
                    result += f"  {name}: {chg:.2f}%\n"

            return result

    finally:
        conn.close()


if __name__ == '__main__':
    # 测试
    print("\n1. 行业板块涨跌幅排名 Top 10:")
    print(get_sector_ranking(sector_type='industry', top_n=10))

    print("\n2. 概念板块成交量排名 Top 10:")
    print(get_sector_ranking(sector_type='concept', top_n=10, sort_by='vol'))

    print("\n3. 连续3天上涨的行业板块:")
    print(get_sector_top_gainers(sector_type='industry', days=3))

    print("\n4. 行业板块市场概览:")
    print(get_sector_summary(sector_type='industry'))
