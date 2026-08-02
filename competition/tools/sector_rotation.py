#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块轮动趋势识别工具
从 MySQL market_data.sector_industry_daily / sector_concept_daily 表获取数据，分析板块轮动

功能:
- 板块动量评分（短期vs中期涨幅对比）
- 轮动趋势识别（资金流入/流出板块）
- 冷热板块分类
- 板块强度排名

用法:
    from tools.sector_rotation import get_sector_momentum, get_sector_rotation
    print(get_sector_momentum(sector_type='industry'))
    print(get_sector_rotation(sector_type='concept'))
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


def get_sector_momentum(sector_type='industry', short_days=3, long_days=10, top_n=15):
    """
    板块动量分析
    通过对比短期（N日）和中期（M日）涨幅，计算动量评分
    动量评分 = 短期涨幅 - 中期涨幅，正值表示加速上涨，负值表示动能衰减

    Args:
        sector_type: 'industry'（行业）或 'concept'（概念）
        short_days: 短期天数（默认3日）
        long_days: 中期天数（默认10日）
        top_n: 返回前N名

    Returns:
        str: 格式化的动量分析结果
    """
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    type_name = '行业' if sector_type == 'industry' else '概念'

    trade_dates = _get_trade_dates(sector_type, long_days)
    if len(trade_dates) < long_days:
        return f"数据不足，需要至少{long_days}个交易日数据"

    short_dates = trade_dates[-short_days:]
    long_dates = trade_dates

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 计算中期涨幅
            long_placeholders = ','.join(['%s'] * len(long_dates))
            cursor.execute(f"""
                SELECT sector_name, sector_code,
                       SUM(pct_chg) as long_chg,
                       AVG(amount) as avg_amount
                FROM {table}
                WHERE trade_date IN ({long_placeholders})
                GROUP BY sector_name, sector_code
            """, (*long_dates,))
            long_data = {row[1]: (row[0], row[2] or 0, row[3] or 0) for row in cursor.fetchall()}

            # 计算短期涨幅
            short_placeholders = ','.join(['%s'] * len(short_dates))
            cursor.execute(f"""
                SELECT sector_name, sector_code,
                       SUM(pct_chg) as short_chg
                FROM {table}
                WHERE trade_date IN ({short_placeholders})
                GROUP BY sector_name, sector_code
            """, (*short_dates,))
            short_data = {row[1]: (row[0], row[2] or 0) for row in cursor.fetchall()}

            # 合并计算动量评分
            results = []
            for code in long_data:
                if code not in short_data:
                    continue
                name, long_chg, avg_amount = long_data[code]
                _, short_chg = short_data[code]
                momentum = short_chg - (long_chg - short_chg) * short_days / (long_days - short_days)
                results.append((name, code, short_chg, long_chg, momentum, avg_amount))

            # 按动量评分排序
            results.sort(key=lambda x: x[4], reverse=True)
            results = results[:top_n]

            if not results:
                return f"无{type_name}板块数据"

            short_range = f"{short_dates[0]}~{short_dates[-1]}"
            long_range = f"{long_dates[0]}~{long_dates[-1]}"

            result = f"=== {type_name}板块动量分析 ===\n"
            result += f"短期({short_days}日): {short_range}  中期({long_days}日): {long_range}\n"
            result += f"动量评分 = 短期涨幅 - 偏离值，>0加速上涨，<0动能衰减\n\n"
            result += f"{'排名':<4} {'板块名称':<12} {'短期(%)':<10} {'中期(%)':<10} {'动量分':<10} {'趋势':<6}\n"
            result += "-" * 56 + "\n"

            for i, (name, code, short_chg, long_chg, momentum, _) in enumerate(results, 1):
                trend = '加速' if momentum > 0 else ('减速' if momentum < -1 else '平稳')
                result += f"{i:<4} {name:<12} {short_chg:<10.2f} {long_chg:<10.2f} {momentum:<10.2f} {trend:<6}\n"

            return result

    finally:
        conn.close()


def get_sector_rotation(sector_type='industry', short_days=3, long_days=10, top_n=10):
    """
    板块轮动识别
    识别资金流入（短期表现优于中期）和资金流出（短期表现弱于中期）的板块

    Args:
        sector_type: 'industry' 或 'concept'
        short_days: 短期天数
        long_days: 中期天数
        top_n: 每类返回N个

    Returns:
        str: 格式化的轮动分析结果
    """
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    type_name = '行业' if sector_type == 'industry' else '概念'

    trade_dates = _get_trade_dates(sector_type, long_days)
    if len(trade_dates) < long_days:
        return f"数据不足，需要至少{long_days}个交易日数据"

    short_dates = trade_dates[-short_days:]
    long_dates = trade_dates

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 计算中期涨幅和成交额
            long_placeholders = ','.join(['%s'] * len(long_dates))
            cursor.execute(f"""
                SELECT sector_name, sector_code,
                       SUM(pct_chg) as long_chg,
                       AVG(amount) as avg_amount
                FROM {table}
                WHERE trade_date IN ({long_placeholders})
                GROUP BY sector_name, sector_code
            """, (*long_dates,))
            long_data = {row[1]: (row[0], row[2] or 0, row[3] or 0) for row in cursor.fetchall()}

            # 计算短期涨幅
            short_placeholders = ','.join(['%s'] * len(short_dates))
            cursor.execute(f"""
                SELECT sector_name, sector_code,
                       SUM(pct_chg) as short_chg
                FROM {table}
                WHERE trade_date IN ({short_placeholders})
                GROUP BY sector_name, sector_code
            """, (*short_dates,))
            short_data = {row[1]: (row[0], row[2] or 0) for row in cursor.fetchall()}

            # 合并计算
            all_sectors = []
            for code in long_data:
                if code not in short_data:
                    continue
                name, long_chg, avg_amount = long_data[code]
                _, short_chg = short_data[code]
                # 短期日均涨幅 vs 中期日均涨幅
                short_avg = short_chg / short_days
                long_avg = long_chg / long_days
                diff = short_avg - long_avg
                all_sectors.append((name, code, short_chg, long_chg, diff, avg_amount))

            # 资金流入：短期日均 > 中期日均（差值大的前N个）
            inflow = sorted(all_sectors, key=lambda x: x[4], reverse=True)[:top_n]
            # 资金流出：短期日均 < 中期日均（差值小的前N个）
            outflow = sorted(all_sectors, key=lambda x: x[4])[:top_n]

            short_range = f"{short_dates[0]}~{short_dates[-1]}"
            long_range = f"{long_dates[0]}~{long_dates[-1]}"

            result = f"=== {type_name}板块轮动分析 ===\n"
            result += f"短期({short_days}日): {short_range}  中期({long_days}日): {long_range}\n\n"

            result += f"【资金流入板块】短期表现优于中期，资金关注度提升\n"
            result += f"{'排名':<4} {'板块名称':<12} {'短期(%)':<10} {'中期(%)':<10} {'偏离值':<10}\n"
            result += "-" * 48 + "\n"
            for i, (name, code, short_chg, long_chg, diff, _) in enumerate(inflow, 1):
                result += f"{i:<4} {name:<12} {short_chg:<10.2f} {long_chg:<10.2f} {diff:<+10.2f}\n"

            result += f"\n【资金流出板块】短期表现弱于中期，资金关注度下降\n"
            result += f"{'排名':<4} {'板块名称':<12} {'短期(%)':<10} {'中期(%)':<10} {'偏离值':<10}\n"
            result += "-" * 48 + "\n"
            for i, (name, code, short_chg, long_chg, diff, _) in enumerate(outflow, 1):
                result += f"{i:<4} {name:<12} {short_chg:<10.2f} {long_chg:<10.2f} {diff:<+10.2f}\n"

            return result

    finally:
        conn.close()


def get_sector_strength(sector_type='industry', days=5, top_n=15):
    """
    板块强度排名
    综合涨幅、成交额变化、上涨天数计算强度评分

    Args:
        sector_type: 'industry' 或 'concept'
        days: 统计天数
        top_n: 返回前N名

    Returns:
        str: 格式化的强度排名
    """
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    type_name = '行业' if sector_type == 'industry' else '概念'

    trade_dates = _get_trade_dates(sector_type, days)
    if len(trade_dates) < days:
        return f"数据不足，需要至少{days}个交易日数据"

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(trade_dates))
            cursor.execute(f"""
                SELECT sector_name, sector_code,
                       SUM(pct_chg) as total_chg,
                       AVG(pct_chg) as avg_chg,
                       SUM(amount) as total_amount,
                       SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) as up_days,
                       COUNT(*) as total_days
                FROM {table}
                WHERE trade_date IN ({placeholders})
                GROUP BY sector_name, sector_code
            """, (*trade_dates,))

            rows = cursor.fetchall()
            if not rows:
                return f"无{type_name}板块数据"

            # 计算强度评分：涨幅权重0.4 + 上涨天数占比权重0.3 + 成交额权重0.3
            max_amount = max(float(row[4] or 0) for row in rows)
            results = []
            for row in rows:
                name = row[0]
                code = row[1]
                total_chg = float(row[2] or 0)
                avg_chg = float(row[3] or 0)
                total_amount = float(row[4] or 0)
                up_days = int(row[5] or 0)
                total_days = int(row[6] or 1)

                up_ratio = up_days / total_days
                amount_score = (total_amount / max_amount) if max_amount > 0 else 0
                # 强度评分
                strength = total_chg * 0.4 + up_ratio * 30 * 0.3 + amount_score * 100 * 0.3
                results.append((name, code, total_chg, avg_chg, up_days, total_days, strength, total_amount))

            results.sort(key=lambda x: x[6], reverse=True)
            results = results[:top_n]

            date_range = f"{trade_dates[0]}~{trade_dates[-1]}"
            result = f"=== {type_name}板块强度排名 ({date_range}) ===\n"
            result += f"统计周期: {days}个交易日\n"
            result += f"强度评分 = 涨幅×0.4 + 上涨天数比×0.3 + 成交额×0.3\n\n"
            result += f"{'排名':<4} {'板块名称':<12} {'累计涨幅':<10} {'上涨天数':<10} {'强度分':<10}\n"
            result += "-" * 48 + "\n"

            for i, (name, code, total_chg, avg_chg, up_days, total_days, strength, amount) in enumerate(results, 1):
                days_str = f"{up_days}/{total_days}"
                result += f"{i:<4} {name:<12} {total_chg:<10.2f} {days_str:<10} {strength:<10.2f}\n"

            return result

    finally:
        conn.close()


def get_hot_cold_sectors(sector_type='industry', days=5):
    """
    冷热板块分类
    根据近期表现将板块分为：热门、温热、平淡、冷门四类

    Args:
        sector_type: 'industry' 或 'concept'
        days: 统计天数

    Returns:
        str: 格式化的冷热分类结果
    """
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    type_name = '行业' if sector_type == 'industry' else '概念'

    trade_dates = _get_trade_dates(sector_type, days)
    if len(trade_dates) < days:
        return f"数据不足，需要至少{days}个交易日数据"

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(trade_dates))
            cursor.execute(f"""
                SELECT sector_name, sector_code,
                       SUM(pct_chg) as total_chg,
                       SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) as up_days,
                       COUNT(*) as total_days
                FROM {table}
                WHERE trade_date IN ({placeholders})
                GROUP BY sector_name, sector_code
            """, (*trade_dates,))

            rows = cursor.fetchall()
            if not rows:
                return f"无{type_name}板块数据"

            # 分类
            hot = []      # 累计涨幅>5% 且上涨天数>=4
            warm = []     # 累计涨幅>0 且上涨天数>=3
            flat = []     # 其他
            cold = []     # 累计涨幅<0 且下跌天数>=4

            for row in rows:
                name = row[0]
                code = row[1]
                total_chg = float(row[2] or 0)
                up_days = int(row[3] or 0)
                total_days = int(row[4] or 1)
                down_days = total_days - up_days

                if total_chg > 5 and up_days >= total_days * 0.7:
                    hot.append((name, code, total_chg, up_days, total_days))
                elif total_chg > 0 and up_days >= total_days * 0.5:
                    warm.append((name, code, total_chg, up_days, total_days))
                elif total_chg < 0 and down_days >= total_days * 0.7:
                    cold.append((name, code, total_chg, up_days, total_days))
                else:
                    flat.append((name, code, total_chg, up_days, total_days))

            hot.sort(key=lambda x: x[2], reverse=True)
            warm.sort(key=lambda x: x[2], reverse=True)
            cold.sort(key=lambda x: x[2])
            flat.sort(key=lambda x: abs(x[2]), reverse=True)

            date_range = f"{trade_dates[0]}~{trade_dates[-1]}"
            result = f"=== {type_name}板块冷热分布 ({date_range}) ===\n"
            result += f"统计周期: {days}个交易日\n\n"

            def _fmt_section(title, items, max_show=8):
                s = f"【{title}】({len(items)}个)\n"
                s += f"{'板块名称':<12} {'累计涨幅':<10} {'上涨天数':<10}\n"
                s += "-" * 34 + "\n"
                for name, code, chg, up, total in items[:max_show]:
                    s += f"{name:<12} {chg:<10.2f} {up}/{total}\n"
                if len(items) > max_show:
                    s += f"  ...还有{len(items) - max_show}个\n"
                return s

            result += _fmt_section(f"热门板块（涨幅>5%，多数上涨）", hot)
            result += "\n" + _fmt_section(f"温热板块（涨幅>0，过半上涨）", warm)
            result += "\n" + _fmt_section(f"冷门板块（跌幅<0，多数下跌）", cold)
            result += "\n" + _fmt_section(f"平淡板块（其他）", flat)

            return result

    finally:
        conn.close()


if __name__ == '__main__':
    print("\n1. 行业板块动量分析:")
    print(get_sector_momentum(sector_type='industry'))

    print("\n2. 行业板块轮动分析:")
    print(get_sector_rotation(sector_type='industry'))

    print("\n3. 行业板块强度排名:")
    print(get_sector_strength(sector_type='industry'))

    print("\n4. 行业板块冷热分布:")
    print(get_hot_cold_sectors(sector_type='industry'))
