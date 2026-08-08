#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场趋势研判工具
基于近 N 日数据，综合多维度指标给出市场情绪判断（乐观/中性/悲观）。

评分维度（各 20 分，满分 100）：
- 涨跌比：近5日平均上涨家数占比
- 涨停跌停比：涨停数/(涨停+跌停+1)
- 成交额趋势：近5日 vs 前5日
- 板块轮动强度：上涨板块数占比
- 连续趋势：连涨/连跌天数

用法:
    from tools.market_trend import analyze_market_trend, format_market_trend
    print(format_market_trend())

CLI:
    python tools/market_trend.py
    python tools/market_trend.py --days 10
"""

import logging

try:
    from tools.db import get_connection
except ImportError:
    from db import get_connection

logger = logging.getLogger(__name__)


def _get_trade_dates(days=10):
    """获取最近 N 个交易日"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT trade_date FROM stock_kline
                ORDER BY trade_date DESC LIMIT %s
            """, (days,))
            rows = cursor.fetchall()
            return sorted([str(r[0]) for r in rows])
    finally:
        conn.close()


def _is_gem_or_star(ts_code):
    prefix = ts_code[:3]
    return prefix in ('300', '301', '688', '689')


def analyze_market_trend(days=5):
    """分析市场趋势

    Args:
        days: 分析天数，默认5

    Returns:
        dict: {
            sentiment: str,
            score: int (0-100),
            factors: [{name, value, signal, score}],
            summary: str,
        }
    """
    trade_dates = _get_trade_dates(max(days * 2, 10))
    if len(trade_dates) < days:
        return {'error': f'数据不足，需要至少{days}个交易日，当前仅有{len(trade_dates)}个'}

    recent_dates = trade_dates[-days:]
    prev_dates = trade_dates[-days * 2:-days] if len(trade_dates) >= days * 2 else trade_dates[:days]
    latest_date = trade_dates[-1]

    conn = get_connection()
    try:
        factors = []

        # ─── 维度1: 涨跌比 (20分) ───
        with conn.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(recent_dates))
            cursor.execute(f"""
                SELECT trade_date,
                       SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) as up_count,
                       SUM(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END) as down_count,
                       COUNT(*) as total
                FROM stock_kline
                WHERE trade_date IN ({placeholders})
                GROUP BY trade_date
            """, recent_dates)
            rows = cursor.fetchall()

            up_ratios = []
            for row in rows:
                total = row[3] or 1
                up_ratios.append(row[1] / total)

            avg_up_ratio = sum(up_ratios) / len(up_ratios) if up_ratios else 0.5

        # 涨跌比评分
        if avg_up_ratio >= 0.65:
            ad_score = 20
            ad_signal = 'positive'
        elif avg_up_ratio >= 0.55:
            ad_score = 16
            ad_signal = 'positive'
        elif avg_up_ratio >= 0.45:
            ad_score = 12
            ad_signal = 'neutral'
        elif avg_up_ratio >= 0.35:
            ad_score = 8
            ad_signal = 'negative'
        else:
            ad_score = 4
            ad_signal = 'negative'

        factors.append({
            'name': '涨跌比',
            'value': f'{days}日平均上涨占比 {avg_up_ratio:.1%}',
            'signal': ad_signal,
            'score': ad_score,
        })

        # ─── 维度2: 涨停跌停比 (20分) ───
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT ts_code, pct_chg FROM stock_kline
                WHERE trade_date = %s AND pct_chg IS NOT NULL
            """, (latest_date,))
            all_rows = cursor.fetchall()

            limit_up = 0
            limit_down = 0
            for row in all_rows:
                ts_code = row[0]
                pct = row[1]
                threshold = 19.9 if _is_gem_or_star(ts_code) else 9.9
                if pct >= threshold:
                    limit_up += 1
                elif pct <= -threshold:
                    limit_down += 1

            total_limit = limit_up + limit_down
            lu_ratio = limit_up / (total_limit + 1)  # +1 避免除零

        if lu_ratio >= 0.75 and total_limit >= 10:
            ll_score = 20
            ll_signal = 'positive'
        elif lu_ratio >= 0.6:
            ll_score = 16
            ll_signal = 'positive'
        elif lu_ratio >= 0.4:
            ll_score = 12
            ll_signal = 'neutral'
        elif lu_ratio >= 0.25:
            ll_score = 8
            ll_signal = 'negative'
        else:
            ll_score = 4
            ll_signal = 'negative'

        factors.append({
            'name': '涨停跌停比',
            'value': f'涨停{limit_up}家 / 跌停{limit_down}家',
            'signal': ll_signal,
            'score': ll_score,
        })

        # ─── 维度3: 成交额趋势 (20分) ───
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT trade_date, SUM(amount) as total_amount
                FROM stock_kline
                WHERE trade_date IN ({placeholders})
                GROUP BY trade_date
                ORDER BY trade_date
            """, recent_dates)
            recent_amounts = [float(r[1] or 0) for r in cursor.fetchall()]

            prev_placeholders = ','.join(['%s'] * len(prev_dates))
            cursor.execute(f"""
                SELECT trade_date, SUM(amount) as total_amount
                FROM stock_kline
                WHERE trade_date IN ({prev_placeholders})
                GROUP BY trade_date
                ORDER BY trade_date
            """, prev_dates)
            prev_amounts = [float(r[1] or 0) for r in cursor.fetchall()]

        recent_avg = sum(recent_amounts) / len(recent_amounts) if recent_amounts else 0
        prev_avg = sum(prev_amounts) / len(prev_amounts) if prev_amounts else 1
        amount_ratio = recent_avg / prev_avg if prev_avg > 0 else 1.0

        if amount_ratio >= 1.2:
            amt_score = 20
            amt_signal = 'positive'
            amt_desc = '放量'
        elif amount_ratio >= 1.05:
            amt_score = 16
            amt_signal = 'positive'
            amt_desc = '温和放量'
        elif amount_ratio >= 0.95:
            amt_score = 12
            amt_signal = 'neutral'
            amt_desc = '持平'
        elif amount_ratio >= 0.8:
            amt_score = 8
            amt_signal = 'negative'
            amt_desc = '温和缩量'
        else:
            amt_score = 4
            amt_signal = 'negative'
            amt_desc = '明显缩量'

        factors.append({
            'name': '成交额趋势',
            'value': f'{amt_desc}（近{days}日/前{days}日 = {amount_ratio:.2f}）',
            'signal': amt_signal,
            'score': amt_score,
        })

        # ─── 维度4: 板块轮动强度 (20分) ───
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT trade_date,
                       SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) as up_count,
                       COUNT(*) as total
                FROM sector_industry_daily
                WHERE trade_date IN ({placeholders})
                GROUP BY trade_date
            """, recent_dates)
            sector_rows = cursor.fetchall()

            sector_up_ratios = []
            for row in sector_rows:
                total = row[2] or 1
                sector_up_ratios.append(row[1] / total)

            avg_sector_up = sum(sector_up_ratios) / len(sector_up_ratios) if sector_up_ratios else 0.5

        if avg_sector_up >= 0.65:
            sec_score = 20
            sec_signal = 'positive'
        elif avg_sector_up >= 0.55:
            sec_score = 16
            sec_signal = 'positive'
        elif avg_sector_up >= 0.45:
            sec_score = 12
            sec_signal = 'neutral'
        elif avg_sector_up >= 0.35:
            sec_score = 8
            sec_signal = 'negative'
        else:
            sec_score = 4
            sec_signal = 'negative'

        factors.append({
            'name': '板块轮动强度',
            'value': f'{days}日平均上涨板块占比 {avg_sector_up:.1%}',
            'signal': sec_signal,
            'score': sec_score,
        })

        # ─── 维度5: 连续趋势 (20分) ───
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT trade_date,
                       SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) as up_count,
                       COUNT(*) as total
                FROM stock_kline
                WHERE trade_date IN ({placeholders})
                GROUP BY trade_date
                ORDER BY trade_date
            """, recent_dates)
            daily_rows = cursor.fetchall()

            # 计算连涨/连跌天数
            consecutive_up = 0
            consecutive_down = 0
            for row in daily_rows:
                total = row[2] or 1
                ratio = row[1] / total
                if ratio > 0.5:
                    consecutive_up += 1
                    consecutive_down = 0
                elif ratio < 0.5:
                    consecutive_down += 1
                    consecutive_up = 0
                else:
                    consecutive_up = 0
                    consecutive_down = 0

        if consecutive_up >= 4:
            cont_score = 20
            cont_signal = 'positive'
            cont_desc = f'连涨{consecutive_up}日'
        elif consecutive_up >= 2:
            cont_score = 15
            cont_signal = 'positive'
            cont_desc = f'连涨{consecutive_up}日'
        elif consecutive_down >= 4:
            cont_score = 4
            cont_signal = 'negative'
            cont_desc = f'连跌{consecutive_down}日'
        elif consecutive_down >= 2:
            cont_score = 8
            cont_signal = 'negative'
            cont_desc = f'连跌{consecutive_down}日'
        else:
            cont_score = 12
            cont_signal = 'neutral'
            cont_desc = '无明显连续趋势'

        factors.append({
            'name': '连续趋势',
            'value': cont_desc,
            'signal': cont_signal,
            'score': cont_score,
        })

        # ─── 综合评分 ───
        total_score = sum(f['score'] for f in factors)

        if total_score >= 75:
            sentiment = '乐观'
        elif total_score >= 60:
            sentiment = '中性偏多'
        elif total_score >= 40:
            sentiment = '中性'
        elif total_score >= 25:
            sentiment = '中性偏空'
        else:
            sentiment = '悲观'

        # 生成总结
        positive_count = sum(1 for f in factors if f['signal'] == 'positive')
        negative_count = sum(1 for f in factors if f['signal'] == 'negative')

        if positive_count >= 4:
            summary = '多项指标积极，市场整体偏强'
        elif positive_count >= 3:
            summary = '多数指标偏暖，市场情绪尚可'
        elif negative_count >= 4:
            summary = '多项指标走弱，市场承压明显'
        elif negative_count >= 3:
            summary = '多数指标偏冷，市场情绪谨慎'
        else:
            summary = '多空交织，市场处于震荡格局'

        return {
            'sentiment': sentiment,
            'score': total_score,
            'factors': factors,
            'summary': summary,
            'trade_date': latest_date,
        }

    finally:
        conn.close()


def format_market_trend(days=5):
    """格式化输出趋势研判（Markdown）"""
    data = analyze_market_trend(days)
    if 'error' in data:
        return f"趋势研判失败: {data['error']}"

    td = data.get('trade_date', '')
    lines = [
        f"## 趋势研判 ({td})",
        "",
        f"**市场情绪: {data['sentiment']}（{data['score']}分/100分）**",
        "",
        f"> {data['summary']}",
        "",
        "| 维度 | 信号 | 得分 | 说明 |",
        "|------|------|------|------|",
    ]

    signal_map = {'positive': '🟢 积极', 'neutral': '🟡 中性', 'negative': '🔴 消极'}
    for f in data['factors']:
        sig = signal_map.get(f['signal'], f['signal'])
        lines.append(f"| {f['name']} | {sig} | {f['score']}/20 | {f['value']} |")

    lines.append("")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='市场趋势研判')
    parser.add_argument('--days', type=int, default=5, help='分析天数，默认5')
    args = parser.parse_args()

    print(format_market_trend(args.days))
