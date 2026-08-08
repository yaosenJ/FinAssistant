#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自选股日报工具
针对用户关注的股票，生成个性化日报：当日行情、近5日涨跌幅、相关新闻。

用法:
    from tools.watchlist_report import format_watchlist_report
    print(format_watchlist_report(['600519.SH', '300750.SZ']))

CLI:
    python tools/watchlist_report.py --ts_codes 600519.SH,300750.SZ
"""

import os
import json
import logging

try:
    from tools.db import get_connection
    from tools.financial_query import _get_stock_name
except ImportError:
    from db import get_connection
    from financial_query import _get_stock_name

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'watchlist_config.json')


def _load_default_watchlist():
    """从配置文件加载默认自选股列表"""
    if not os.path.exists(CONFIG_PATH):
        return []
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get('default', [])
    except Exception:
        return []


def _get_stock_news(ts_code, name, limit=3):
    """获取股票相关新闻"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 按股票名称搜索新闻
            cursor.execute("""
                SELECT title, publish_time, '东财' as source
                FROM stock_news.news_em
                WHERE title LIKE %s
                ORDER BY publish_time DESC
                LIMIT %s
            """, (f'%{name}%', limit))
            news_em = cursor.fetchall()

            cursor.execute("""
                SELECT title, ctime_str, source
                FROM stock_news.news_ths
                WHERE title LIKE %s
                ORDER BY ctime_str DESC
                LIMIT %s
            """, (f'%{name}%', limit))
            news_ths = cursor.fetchall()

            all_news = []
            for title, time_str, source in news_em:
                all_news.append({'title': title, 'time': time_str, 'source': source})
            for title, time_str, source in news_ths:
                all_news.append({'title': title, 'time': time_str, 'source': source or '同花顺'})

            all_news.sort(key=lambda x: x.get('time', '') or '', reverse=True)
            return all_news[:limit]
    except Exception as e:
        logger.warning(f"获取{name}新闻失败: {e}")
        return []
    finally:
        conn.close()


def get_watchlist_report(ts_codes, trade_date=None):
    """获取自选股日报数据

    Args:
        ts_codes: 股票代码列表，如 ['600519.SH', '300750.SZ']
        trade_date: 交易日期，默认最新

    Returns:
        dict: {
            trade_date,
            stocks: [{ts_code, name, close, pct_chg, amount, change_5d, news}],
        }
    """
    if not ts_codes:
        ts_codes = _load_default_watchlist()
    if not ts_codes:
        return {'error': '未配置自选股，请传入 ts_codes 或编辑 watchlist_config.json'}

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 获取最新交易日
            if trade_date is None:
                cursor.execute("SELECT MAX(trade_date) FROM stock_kline")
                row = cursor.fetchone()
                trade_date = str(row[0]) if row and row[0] else None
                if not trade_date:
                    return {'error': '无法获取交易日期'}

            # 获取最近5个交易日
            cursor.execute("""
                SELECT DISTINCT trade_date FROM stock_kline
                WHERE trade_date <= %s
                ORDER BY trade_date DESC LIMIT 5
            """, (trade_date,))
            dates = sorted([str(r[0]) for r in cursor.fetchall()])

            stocks = []
            for ts_code in ts_codes:
                name = _get_stock_name(ts_code)

                # 当日行情
                cursor.execute("""
                    SELECT close, pct_chg, amount, volume
                    FROM stock_kline
                    WHERE ts_code = %s AND trade_date = %s
                """, (ts_code, trade_date))
                row = cursor.fetchone()

                if not row:
                    stocks.append({
                        'ts_code': ts_code, 'name': name,
                        'close': None, 'pct_chg': None, 'amount': None,
                        'change_5d': None, 'news': [],
                    })
                    continue

                close = float(row[0]) if row[0] else None
                pct_chg = round(float(row[1]), 2) if row[1] else None
                amount = round(float(row[2]) / 1e8, 2) if row[2] else None  # 转亿元

                # 近5日涨跌幅
                change_5d = None
                if len(dates) >= 2:
                    cursor.execute("""
                        SELECT close FROM stock_kline
                        WHERE ts_code = %s AND trade_date = %s
                    """, (ts_code, dates[0]))
                    first_row = cursor.fetchone()
                    if first_row and first_row[0] and close:
                        change_5d = round((close - float(first_row[0])) / float(first_row[0]) * 100, 2)

                # 相关新闻
                news = _get_stock_news(ts_code, name, limit=3)

                stocks.append({
                    'ts_code': ts_code,
                    'name': name,
                    'close': close,
                    'pct_chg': pct_chg,
                    'amount': amount,
                    'change_5d': change_5d,
                    'news': news,
                })

            return {'trade_date': trade_date, 'stocks': stocks}
    finally:
        conn.close()


def format_watchlist_report(ts_codes, trade_date=None):
    """格式化输出自选股日报（Markdown）

    Args:
        ts_codes: 股票代码列表
        trade_date: 交易日期，默认最新

    Returns:
        str: Markdown 格式的自选股日报
    """
    data = get_watchlist_report(ts_codes, trade_date)
    if 'error' in data:
        return f"自选股日报失败: {data['error']}"

    td = data['trade_date']
    lines = [
        f"## 自选股日报 ({td})",
        "",
        "| 股票 | 代码 | 收盘价 | 当日涨跌 | 成交额(亿) | 近5日涨跌 |",
        "|------|------|--------|----------|------------|-----------|",
    ]

    for s in data['stocks']:
        close = f"{s['close']:.2f}" if s['close'] else '--'
        pct = f"{s['pct_chg']}%" if s['pct_chg'] is not None else '--'
        amt = f"{s['amount']}" if s['amount'] else '--'
        chg5 = f"{s['change_5d']}%" if s['change_5d'] is not None else '--'
        lines.append(f"| {s['name']} | {s['ts_code']} | {close} | {pct} | {amt} | {chg5} |")

    lines.append("")

    # 相关新闻
    has_news = False
    for s in data['stocks']:
        if s['news']:
            if not has_news:
                lines.append("### 相关新闻")
                lines.append("")
                has_news = True
            lines.append(f"**{s['name']}({s['ts_code']})**")
            lines.append("")
            for n in s['news']:
                lines.append(f"- [{n['source']}] {n['title']} ({n['time']})")
            lines.append("")

    if not has_news:
        lines.append("暂无相关新闻")
        lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='自选股日报')
    parser.add_argument('--ts_codes', help='股票代码，逗号分隔，如 600519.SH,300750.SZ')
    parser.add_argument('--trade_date', help='交易日期，默认最新')
    args = parser.parse_args()

    if args.ts_codes:
        codes = [c.strip() for c in args.ts_codes.split(',')]
    else:
        codes = []

    print(format_watchlist_report(codes, args.trade_date))
