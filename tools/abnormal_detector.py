#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异动检测工具
检测当日市场异动信号：涨停/跌停、放量突破、大幅波动、板块异动。

用法:
    from tools.abnormal_detector import detect_abnormal, format_abnormal
    print(format_abnormal())

CLI:
    python tools/abnormal_detector.py
    python tools/abnormal_detector.py --trade_date 20260801
"""

import logging

try:
    from tools.db import get_connection
    from tools.financial_query import _get_stock_name
except ImportError:
    from db import get_connection
    from financial_query import _get_stock_name

logger = logging.getLogger(__name__)


def _get_latest_trade_date():
    """获取最新交易日"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT MAX(trade_date) FROM stock_kline")
            row = cursor.fetchone()
            return str(row[0]) if row and row[0] else None
    finally:
        conn.close()


def _is_gem_or_star(ts_code):
    """判断是否为创业板或科创板"""
    prefix = ts_code[:3]
    return prefix in ('300', '301', '688', '689')


def _classify_limit(ts_code, pct_chg):
    """判断涨跌停状态"""
    if pct_chg is None:
        return None
    threshold = 19.9 if _is_gem_or_star(ts_code) else 9.9
    if pct_chg >= threshold:
        return 'limit_up'
    elif pct_chg <= -threshold:
        return 'limit_down'
    return None


def detect_abnormal(trade_date=None):
    """检测当日市场异动

    Args:
        trade_date: 交易日期，默认最新

    Returns:
        dict: {
            trade_date,
            limit_up: [{ts_code, name, pct_chg}],
            limit_down: [{ts_code, name, pct_chg}],
            volume_breakout: [{ts_code, name, pct_chg, vol_ratio}],
            price_surge: [{ts_code, name, pct_chg, direction}],
            sector_anomaly: [{sector, avg_pct_chg, direction}],
        }
    """
    if trade_date is None:
        trade_date = _get_latest_trade_date()
        if not trade_date:
            return {'error': '无法获取交易日期'}

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 涨停/跌停检测
            cursor.execute("""
                SELECT ts_code, pct_chg, close
                FROM stock_kline
                WHERE trade_date = %s AND pct_chg IS NOT NULL
            """, (trade_date,))
            all_rows = cursor.fetchall()

            limit_up = []
            limit_down = []
            price_surge = []

            for row in all_rows:
                ts_code = row[0]
                pct_chg = row[1]

                status = _classify_limit(ts_code, pct_chg)
                if status == 'limit_up':
                    name = _get_stock_name(ts_code)
                    limit_up.append({'ts_code': ts_code, 'name': name, 'pct_chg': round(pct_chg, 2)})
                elif status == 'limit_down':
                    name = _get_stock_name(ts_code)
                    limit_down.append({'ts_code': ts_code, 'name': name, 'pct_chg': round(pct_chg, 2)})
                elif abs(pct_chg) >= 7:
                    # 大幅异动（非涨跌停）
                    name = _get_stock_name(ts_code)
                    direction = '上涨' if pct_chg > 0 else '下跌'
                    price_surge.append({
                        'ts_code': ts_code, 'name': name,
                        'pct_chg': round(pct_chg, 2), 'direction': direction,
                    })

            # 按涨跌幅排序
            limit_up.sort(key=lambda x: x['pct_chg'], reverse=True)
            limit_down.sort(key=lambda x: x['pct_chg'])
            price_surge.sort(key=lambda x: abs(x['pct_chg']), reverse=True)

            # 2. 放量突破检测（量比 > 3 且涨幅 > 3%）
            volume_breakout = []
            try:
                cursor.execute("""
                    SELECT t.ts_code, t.pct_chg, t.volume,
                           t.volume / a.avg_vol AS vol_ratio
                    FROM stock_kline t
                    JOIN (
                        SELECT ts_code, AVG(volume) AS avg_vol
                        FROM stock_kline
                        WHERE trade_date < %s
                        GROUP BY ts_code
                        HAVING COUNT(*) >= 10
                    ) a ON t.ts_code = a.ts_code
                    WHERE t.trade_date = %s
                      AND t.volume IS NOT NULL AND a.avg_vol > 0
                      AND t.volume / a.avg_vol > 3
                      AND t.pct_chg > 3
                    ORDER BY vol_ratio DESC
                    LIMIT 50
                """, (trade_date, trade_date))
                vol_rows = cursor.fetchall()

                for row in vol_rows:
                    ts_code = row[0]
                    name = _get_stock_name(ts_code)
                    volume_breakout.append({
                        'ts_code': ts_code,
                        'name': name,
                        'pct_chg': round(row[1], 2),
                        'vol_ratio': round(row[3], 2),
                    })
            except Exception as e:
                logger.warning(f"放量突破检测失败: {e}")
                # 回退到简单检测
                cursor.execute("""
                    SELECT ts_code, pct_chg, volume
                    FROM stock_kline
                    WHERE trade_date = %s AND pct_chg > 3 AND volume IS NOT NULL
                    ORDER BY volume DESC
                    LIMIT 20
                """, (trade_date,))
                for row in cursor.fetchall():
                    name = _get_stock_name(row[0])
                    volume_breakout.append({
                        'ts_code': row[0],
                        'name': name,
                        'pct_chg': round(row[1], 2),
                        'vol_ratio': None,
                    })

            # 3. 板块异动检测（平均涨跌幅绝对值 > 3%）
            sector_anomaly = []
            try:
                cursor.execute("""
                    SELECT sector_name, pct_chg
                    FROM sector_industry_daily
                    WHERE trade_date = %s AND pct_chg IS NOT NULL
                      AND ABS(pct_chg) > 3
                    ORDER BY ABS(pct_chg) DESC
                    LIMIT 20
                """, (trade_date,))
                for row in cursor.fetchall():
                    direction = '领涨' if row[1] > 0 else '领跌'
                    sector_anomaly.append({
                        'sector': row[0],
                        'avg_pct_chg': round(row[1], 2),
                        'direction': direction,
                    })
            except Exception as e:
                logger.warning(f"板块异动检测失败: {e}")

            return {
                'trade_date': str(trade_date),
                'limit_up': limit_up,
                'limit_down': limit_down,
                'volume_breakout': volume_breakout,
                'price_surge': price_surge[:30],  # 最多30只
                'sector_anomaly': sector_anomaly,
            }
    finally:
        conn.close()


def format_abnormal(trade_date=None):
    """格式化输出异动检测结果（Markdown）

    Args:
        trade_date: 交易日期，默认最新

    Returns:
        str: Markdown 格式的异动报告
    """
    data = detect_abnormal(trade_date)
    if 'error' in data:
        return f"异动检测失败: {data['error']}"

    td = data['trade_date']
    lines = [f"## 市场异动检测 ({td})", ""]

    # 涨停股
    lu = data['limit_up']
    if lu:
        lines.append(f"### 涨停股 ({len(lu)}只)")
        lines.append("")
        lines.append("| 股票 | 代码 | 涨幅 |")
        lines.append("|------|------|------|")
        for s in lu[:30]:
            lines.append(f"| {s['name']} | {s['ts_code']} | {s['pct_chg']}% |")
        lines.append("")
    else:
        lines.append("### 涨停股: 无")
        lines.append("")

    # 跌停股
    ld = data['limit_down']
    if ld:
        lines.append(f"### 跌停股 ({len(ld)}只)")
        lines.append("")
        lines.append("| 股票 | 代码 | 跌幅 |")
        lines.append("|------|------|------|")
        for s in ld[:30]:
            lines.append(f"| {s['name']} | {s['ts_code']} | {s['pct_chg']}% |")
        lines.append("")
    else:
        lines.append("### 跌停股: 无")
        lines.append("")

    # 放量突破
    vb = data['volume_breakout']
    if vb:
        lines.append(f"### 放量突破 ({len(vb)}只，量比>3且涨幅>3%)")
        lines.append("")
        lines.append("| 股票 | 代码 | 涨幅 | 量比 |")
        lines.append("|------|------|------|------|")
        for s in vb[:20]:
            vr = f"{s['vol_ratio']}" if s['vol_ratio'] else '--'
            lines.append(f"| {s['name']} | {s['ts_code']} | {s['pct_chg']}% | {vr} |")
        lines.append("")
    else:
        lines.append("### 放量突破: 无")
        lines.append("")

    # 大幅异动
    ps = data['price_surge']
    if ps:
        lines.append(f"### 大幅异动 ({len(ps)}只，|涨跌幅|>7%，非涨跌停)")
        lines.append("")
        lines.append("| 股票 | 代码 | 涨跌幅 | 方向 |")
        lines.append("|------|------|--------|------|")
        for s in ps[:20]:
            lines.append(f"| {s['name']} | {s['ts_code']} | {s['pct_chg']}% | {s['direction']} |")
        lines.append("")
    else:
        lines.append("### 大幅异动: 无")
        lines.append("")

    # 板块异动
    sa = data['sector_anomaly']
    if sa:
        lines.append(f"### 板块异动 ({len(sa)}个，|平均涨跌幅|>3%)")
        lines.append("")
        lines.append("| 板块 | 平均涨跌幅 | 方向 |")
        lines.append("|------|------------|------|")
        for s in sa[:15]:
            lines.append(f"| {s['sector']} | {s['avg_pct_chg']}% | {s['direction']} |")
        lines.append("")
    else:
        lines.append("### 板块异动: 无")
        lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='市场异动检测')
    parser.add_argument('--trade_date', help='交易日期，如 20260801，默认最新')
    args = parser.parse_args()

    print(format_abnormal(args.trade_date))
