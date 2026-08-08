#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大盘概览工具
查询指定交易日的全市场概览：涨跌家数、涨停跌停、成交额、板块排名等。

由于数据库中无指数数据，市场统计从个股数据聚合计算。

用法:
    from tools.market_overview import get_market_overview, format_market_overview
    print(format_market_overview())

CLI:
    python tools/market_overview.py
    python tools/market_overview.py --trade_date 20260801
"""

import logging

try:
    from tools.db import get_connection
except ImportError:
    from db import get_connection

logger = logging.getLogger(__name__)


def _get_latest_trade_date():
    """获取 stock_kline 中最新交易日"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT MAX(trade_date) FROM stock_kline")
            row = cursor.fetchone()
            return str(row[0]) if row and row[0] else None
    finally:
        conn.close()


def _is_gem_or_star(ts_code):
    """判断是否为创业板(300xxx)或科创板(688xxx)"""
    prefix = ts_code[:3]
    return prefix in ('300', '301', '688', '689')


def _classify_limit(ts_code, pct_chg):
    """判断涨跌停状态

    Returns:
        'limit_up', 'limit_down', or None
    """
    if pct_chg is None:
        return None
    threshold = 19.9 if _is_gem_or_star(ts_code) else 9.9
    if pct_chg >= threshold:
        return 'limit_up'
    elif pct_chg <= -threshold:
        return 'limit_down'
    return None


def get_market_overview(trade_date=None):
    """获取全市场概览

    Args:
        trade_date: 交易日期，默认最新日期

    Returns:
        dict: {
            trade_date, total_stocks,
            advance_count, decline_count, flat_count,
            limit_up_count, limit_down_count,
            limit_up_list: [ts_code, ...],
            limit_down_list: [ts_code, ...],
            total_amount_亿, total_volume,
            avg_pct_chg, median_pct_chg,
        }
    """
    if trade_date is None:
        trade_date = _get_latest_trade_date()
        if not trade_date:
            return {'error': '无法获取交易日期，stock_kline 表可能为空'}

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 查询全市场数据
            cursor.execute("""
                SELECT ts_code, close, pct_chg, volume, amount, total_mv
                FROM stock_kline
                WHERE trade_date = %s
            """, (trade_date,))
            rows = cursor.fetchall()

            if not rows:
                return {'error': f'{trade_date} 无交易数据', 'trade_date': trade_date}

            # 统计
            total = len(rows)
            advance = 0
            decline = 0
            flat = 0
            limit_up_list = []
            limit_down_list = []
            pct_chgs = []
            total_amount = 0
            total_volume = 0

            for row in rows:
                ts_code = row[0]
                pct_chg = row[2]
                vol = row[3] or 0
                amount = row[4] or 0

                if pct_chg is not None:
                    pct_chgs.append(pct_chg)
                    if pct_chg > 0:
                        advance += 1
                    elif pct_chg < 0:
                        decline += 1
                    else:
                        flat += 1

                    limit_status = _classify_limit(ts_code, pct_chg)
                    if limit_status == 'limit_up':
                        limit_up_list.append(ts_code)
                    elif limit_status == 'limit_down':
                        limit_down_list.append(ts_code)

                total_amount += amount
                total_volume += vol

            # 计算平均和中位数涨跌幅
            avg_pct = round(sum(pct_chgs) / len(pct_chgs), 2) if pct_chgs else 0
            sorted_chgs = sorted(pct_chgs)
            n = len(sorted_chgs)
            if n > 0:
                median_pct = round(sorted_chgs[n // 2], 2) if n % 2 == 1 else round((sorted_chgs[n // 2 - 1] + sorted_chgs[n // 2]) / 2, 2)
            else:
                median_pct = 0

            return {
                'trade_date': str(trade_date),
                'total_stocks': total,
                'advance_count': advance,
                'decline_count': decline,
                'flat_count': flat,
                'limit_up_count': len(limit_up_list),
                'limit_down_count': len(limit_down_list),
                'limit_up_list': limit_up_list,
                'limit_down_list': limit_down_list,
                'total_amount_亿': round(total_amount / 1e8, 2),
                'total_volume': total_volume,
                'avg_pct_chg': avg_pct,
                'median_pct_chg': median_pct,
            }
    finally:
        conn.close()


def format_market_overview(trade_date=None):
    """格式化输出大盘概览（Markdown）

    Args:
        trade_date: 交易日期，默认最新

    Returns:
        str: Markdown 格式的大盘概览
    """
    data = get_market_overview(trade_date)
    if 'error' in data:
        return f"获取大盘概览失败: {data['error']}"

    td = data['trade_date']
    total = data['total_stocks']
    adv = data['advance_count']
    dec = data['decline_count']
    flt = data['flat_count']
    lu = data['limit_up_count']
    ld = data['limit_down_count']
    amt = data['total_amount_亿']
    avg_chg = data['avg_pct_chg']
    med_chg = data['median_pct_chg']

    # 涨跌比
    adv_pct = round(adv / total * 100, 1) if total > 0 else 0
    dec_pct = round(dec / total * 100, 1) if total > 0 else 0

    # 市场情绪判断
    if adv_pct >= 70:
        sentiment = '强势普涨'
    elif adv_pct >= 55:
        sentiment = '偏多'
    elif adv_pct >= 45:
        sentiment = '震荡'
    elif adv_pct >= 30:
        sentiment = '偏空'
    else:
        sentiment = '弱势普跌'

    lines = [
        f"## 大盘概览 ({td})",
        "",
        f"**市场情绪: {sentiment}**",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 上涨家数 | {adv} ({adv_pct}%) |",
        f"| 下跌家数 | {dec} ({dec_pct}%) |",
        f"| 平盘家数 | {flt} |",
        f"| 涨停家数 | {lu} |",
        f"| 跌停家数 | {ld} |",
        f"| 总成交额 | {amt} 亿元 |",
        f"| 平均涨跌幅 | {avg_chg}% |",
        f"| 中位数涨跌幅 | {med_chg}% |",
        "",
    ]

    # 涨停股列表（前20只）
    if data['limit_up_list']:
        display = data['limit_up_list'][:20]
        lines.append(f"### 涨停股 ({lu}只，展示前{len(display)}只)")
        lines.append("")
        lines.append(", ".join(display))
        lines.append("")

    # 跌停股列表（前20只）
    if data['limit_down_list']:
        display = data['limit_down_list'][:20]
        lines.append(f"### 跌停股 ({ld}只，展示前{len(display)}只)")
        lines.append("")
        lines.append(", ".join(display))
        lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='大盘概览')
    parser.add_argument('--trade_date', help='交易日期，如 20260801，默认最新')
    args = parser.parse_args()

    print(format_market_overview(args.trade_date))
