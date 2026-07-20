#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块深度分析工具
关联成分股数据，提供板块内部结构分析

功能:
- 成分股涨跌分布（涨跌家数、涨跌停、中位涨幅）
- 板块资金流向（成交额趋势、流入/流出判断）
- 板块关联度（成分股重叠度）

用法:
    from tools.sector_detail import get_constituent_distribution, get_sector_money_flow, get_sector_correlation
    print(get_constituent_distribution('白酒', sector_type='industry'))
    print(get_sector_money_flow('电力', sector_type='industry'))
    print(get_sector_correlation('白酒', '啤酒', sector_type='industry'))
"""

import logging

try:
    from tools.db import get_connection
except ImportError:
    from db import get_connection

logger = logging.getLogger(__name__)


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


def _get_latest_trade_date_for_stock():
    """获取个股最新交易日期"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT MAX(trade_date) FROM stock_kline")
            result = cursor.fetchone()
            return result[0] if result else None
    finally:
        conn.close()


def get_constituent_distribution(sector_name, sector_type='industry', trade_date=None):
    """
    板块成分股涨跌分布

    Args:
        sector_name: 板块名称（支持模糊匹配）
        sector_type: 'industry' 或 'concept'
        trade_date: 交易日期，默认最新

    Returns:
        str: 格式化的涨跌分布结果
    """
    type_name = '行业' if sector_type == 'industry' else '概念'
    cons_table = 'sector_industry_cons' if sector_type == 'industry' else 'sector_concept_cons'

    # 搜索板块
    match = _search_sector(sector_type, sector_name)
    if not match:
        return f"未找到{type_name}板块: {sector_name}"

    sector_code, sector_name_real = match

    if trade_date is None:
        trade_date = _get_latest_trade_date_for_stock()
        if not trade_date:
            return "无法获取交易日期"

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 获取成分股列表
            cursor.execute(f"""
                SELECT stock_code, stock_name FROM {cons_table}
                WHERE sector_code = %s
            """, (sector_code,))
            constituents = cursor.fetchall()

            if not constituents:
                return f"板块 [{sector_name_real}] 无成分股数据"

            stock_codes = [c[0] for c in constituents]
            code_name_map = {c[0]: c[1] for c in constituents}

            # 获取成分股当日行情
            placeholders = ','.join(['%s'] * len(stock_codes))
            cursor.execute(f"""
                SELECT symbol, pct_chg, amount, close, pre_close
                FROM stock_kline
                WHERE symbol IN ({placeholders}) AND trade_date = %s
            """, (*stock_codes, trade_date))

            rows = cursor.fetchall()

            if not rows:
                return f"[{trade_date}] 板块 [{sector_name_real}] 成分股无行情数据"

            # 统计
            pct_list = []
            up_count = 0
            down_count = 0
            flat_count = 0
            limit_up = []    # 涨停 (>=9.9%)
            limit_down = []  # 跌停 (<=-9.9%)
            total_amount = 0
            stock_details = []

            for row in rows:
                code = row[0]
                pct = float(row[1] or 0)
                amount = float(row[2] or 0)
                close = float(row[3] or 0)
                pre_close = float(row[4] or 0)
                name = code_name_map.get(code, code)

                pct_list.append(pct)
                total_amount += amount

                if pct > 0:
                    up_count += 1
                elif pct < 0:
                    down_count += 1
                else:
                    flat_count += 1

                if pct >= 9.9:
                    limit_up.append((name, code, pct))
                elif pct <= -9.9:
                    limit_down.append((name, code, pct))

                stock_details.append((name, code, pct, amount, close))

            # 排序
            stock_details.sort(key=lambda x: x[2], reverse=True)
            limit_up.sort(key=lambda x: x[2], reverse=True)
            limit_down.sort(key=lambda x: x[2])

            # 中位涨幅
            pct_list.sort()
            mid = len(pct_list) // 2
            median_pct = (pct_list[mid] if len(pct_list) % 2 else (pct_list[mid - 1] + pct_list[mid]) / 2)
            avg_pct = sum(pct_list) / len(pct_list) if pct_list else 0

            # 格式化输出
            result = f"=== 板块成分股涨跌分布 ===\n"
            result += f"板块: {sector_name_real} ({sector_code})  日期: {trade_date}\n"
            result += f"成分股总数: {len(stock_codes)}  有行情: {len(rows)}\n\n"

            result += f"【涨跌统计】\n"
            result += f"  上涨: {up_count}家  下跌: {down_count}家  平盘: {flat_count}家\n"
            result += f"  涨跌比: {up_count}:{down_count}\n"
            result += f"  平均涨幅: {avg_pct:+.2f}%\n"
            result += f"  中位涨幅: {median_pct:+.2f}%\n"
            result += f"  板块总成交额: {total_amount / 1e8:.2f}亿\n"

            if limit_up:
                result += f"\n【涨停个股】({len(limit_up)}家)\n"
                for name, code, pct in limit_up[:10]:
                    result += f"  {name}({code}): {pct:+.2f}%\n"

            if limit_down:
                result += f"\n【跌停个股】({len(limit_down)}家)\n"
                for name, code, pct in limit_down[:10]:
                    result += f"  {name}({code}): {pct:+.2f}%\n"

            result += f"\n【涨幅前5】\n"
            for name, code, pct, amount, close in stock_details[:5]:
                result += f"  {name}({code}): {pct:+.2f}%  收盘{close:.2f}\n"

            result += f"\n【跌幅前5】\n"
            for name, code, pct, amount, close in stock_details[-5:]:
                result += f"  {name}({code}): {pct:+.2f}%  收盘{close:.2f}\n"

            return result

    finally:
        conn.close()


def get_sector_money_flow(sector_name, sector_type='industry', days=10):
    """
    板块资金流向分析
    通过成交额变化趋势判断资金流入/流出

    Args:
        sector_name: 板块名称（支持模糊匹配）
        sector_type: 'industry' 或 'concept'
        days: 分析天数

    Returns:
        str: 格式化的资金流向结果
    """
    type_name = '行业' if sector_type == 'industry' else '概念'
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'

    match = _search_sector(sector_type, sector_name)
    if not match:
        return f"未找到{type_name}板块: {sector_name}"

    sector_code, sector_name_real = match

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT trade_date, close, pct_chg, amount, vol
                FROM {table}
                WHERE sector_code = %s
                ORDER BY trade_date DESC
                LIMIT %s
            """, (sector_code, days))

            rows = cursor.fetchall()
            if not rows:
                return f"板块 [{sector_name_real}] 无数据"

            # 按日期正序
            rows = list(reversed(rows))

            # 计算指标
            amounts = [float(r[3] or 0) for r in rows]
            pct_chgs = [float(r[2] or 0) for r in rows]
            closes = [float(r[1] or 0) for r in rows]
            dates = [r[0] for r in rows]

            # 成交额环比变化
            amount_changes = []
            for i in range(1, len(amounts)):
                if amounts[i - 1] > 0:
                    change = (amounts[i] - amounts[i - 1]) / amounts[i - 1] * 100
                else:
                    change = 0
                amount_changes.append(change)

            # 近期 vs 前期成交额
            mid = len(amounts) // 2
            recent_avg = sum(amounts[mid:]) / len(amounts[mid:]) if amounts[mid:] else 0
            earlier_avg = sum(amounts[:mid]) / len(amounts[:mid]) if amounts[:mid] else 0

            # 涨幅与成交额配合
            up_with_amount = 0
            down_with_amount = 0
            for i in range(len(pct_chgs)):
                if pct_chgs[i] > 0 and (i == 0 or amounts[i] > amounts[i - 1]):
                    up_with_amount += 1  # 放量上涨
                elif pct_chgs[i] < 0 and (i == 0 or amounts[i] > amounts[i - 1]):
                    down_with_amount += 1  # 放量下跌

            # 资金流向判断
            if recent_avg > earlier_avg * 1.2:
                flow = "资金持续流入"
                flow_desc = "近期成交额明显放大，资金关注度提升"
            elif recent_avg > earlier_avg * 1.05:
                flow = "资金小幅流入"
                flow_desc = "近期成交额温和放大"
            elif recent_avg < earlier_avg * 0.8:
                flow = "资金持续流出"
                flow_desc = "近期成交额明显萎缩，资金撤离"
            elif recent_avg < earlier_avg * 0.95:
                flow = "资金小幅流出"
                flow_desc = "近期成交额略有萎缩"
            else:
                flow = "资金平稳"
                flow_desc = "近期成交额变化不大"

            # 格式化输出
            result = f"=== 板块资金流向分析 ===\n"
            result += f"板块: {sector_name_real} ({sector_code})\n"
            result += f"分析周期: {dates[0]} ~ {dates[-1]} ({len(rows)}个交易日)\n\n"

            result += f"【资金流向判断】{flow}\n"
            result += f"  {flow_desc}\n"
            result += f"  近期日均成交额: {recent_avg / 1e8:.2f}亿\n"
            result += f"  前期日均成交额: {earlier_avg / 1e8:.2f}亿\n"
            result += f"  成交额变化: {(recent_avg / earlier_avg - 1) * 100 if earlier_avg > 0 else 0:+.1f}%\n\n"

            result += f"【量价配合】\n"
            result += f"  放量上涨天数: {up_with_amount}\n"
            result += f"  放量下跌天数: {down_with_amount}\n\n"

            # 每日明细
            result += f"{'日期':<12} {'收盘':<10} {'涨跌幅':<10} {'成交额(亿)':<12} {'环比':<10}\n"
            result += "-" * 56 + "\n"
            for i, row in enumerate(rows):
                date = row[0]
                close = float(row[1] or 0)
                pct = float(row[2] or 0)
                amount = float(row[3] or 0) / 1e8
                chg_str = f"{amount_changes[i - 1]:+.1f}%" if i > 0 and i - 1 < len(amount_changes) else "-"
                result += f"{date:<12} {close:<10.2f} {pct:<+10.2f} {amount:<12.2f} {chg_str:<10}\n"

            return result

    finally:
        conn.close()


def get_sector_correlation(sector_name1, sector_name2, sector_type='industry'):
    """
    板块关联度分析
    通过成分股重叠度衡量两个板块的联动性

    Args:
        sector_name1: 板块1名称
        sector_name2: 板块2名称
        sector_type: 'industry' 或 'concept'

    Returns:
        str: 格式化的关联度结果
    """
    type_name = '行业' if sector_type == 'industry' else '概念'
    cons_table = 'sector_industry_cons' if sector_type == 'industry' else 'sector_concept_cons'

    match1 = _search_sector(sector_type, sector_name1)
    match2 = _search_sector(sector_type, sector_name2)

    if not match1:
        return f"未找到{type_name}板块: {sector_name1}"
    if not match2:
        return f"未找到{type_name}板块: {sector_name2}"

    code1, name1 = match1
    code2, name2 = match2

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 获取两个板块的成分股
            cursor.execute(f"""
                SELECT stock_code, stock_name FROM {cons_table}
                WHERE sector_code = %s
            """, (code1,))
            stocks1 = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute(f"""
                SELECT stock_code, stock_name FROM {cons_table}
                WHERE sector_code = %s
            """, (code2,))
            stocks2 = {row[0]: row[1] for row in cursor.fetchall()}

            if not stocks1 or not stocks2:
                return f"成分股数据不足"

            set1 = set(stocks1.keys())
            set2 = set(stocks2.keys())
            intersection = set1 & set2
            union = set1 | set2

            # Jaccard 相似度
            jaccard = len(intersection) / len(union) if union else 0

            # 重叠率（相对于较小集合）
            overlap_rate = len(intersection) / min(len(set1), len(set2)) if min(len(set1), len(set2)) > 0 else 0

            # 关联度判断
            if jaccard > 0.3:
                level = "高度关联"
                desc = "两个板块成分股大量重叠，走势高度相关"
            elif jaccard > 0.1:
                level = "中度关联"
                desc = "两个板块有一定成分股重叠，走势有一定相关性"
            elif jaccard > 0:
                level = "轻度关联"
                desc = "两个板块成分股少量重叠，走势相关性较弱"
            else:
                level = "无关联"
                desc = "两个板块成分股完全独立"

            # 格式化输出
            result = f"=== 板块关联度分析 ===\n\n"
            result += f"板块A: {name1} ({code1}) — {len(set1)}只成分股\n"
            result += f"板块B: {name2} ({code2}) — {len(set2)}只成分股\n\n"

            result += f"【关联度指标】\n"
            result += f"  重叠成分股: {len(intersection)}只\n"
            result += f"  并集成分股: {len(union)}只\n"
            result += f"  Jaccard系数: {jaccard:.4f} ({jaccard * 100:.1f}%)\n"
            result += f"  重叠率(相对较小板块): {overlap_rate * 100:.1f}%\n"
            result += f"  关联等级: {level}\n"
            result += f"  说明: {desc}\n"

            if intersection:
                result += f"\n【重叠成分股】({len(intersection)}只)\n"
                overlap_names = [(stocks1.get(code, code), code) for code in intersection]
                overlap_names.sort(key=lambda x: x[0])
                for name, code in overlap_names[:20]:
                    result += f"  {name}({code})\n"
                if len(overlap_names) > 20:
                    result += f"  ...还有{len(overlap_names) - 20}只\n"

            return result

    finally:
        conn.close()


if __name__ == '__main__':
    print("\n1. 白酒板块成分股涨跌分布:")
    print(get_constituent_distribution('白酒', sector_type='industry'))

    print("\n2. 电力板块资金流向:")
    print(get_sector_money_flow('电力', sector_type='industry'))

    print("\n3. 白酒 vs 啤酒 关联度:")
    print(get_sector_correlation('白酒', '啤酒', sector_type='industry'))
