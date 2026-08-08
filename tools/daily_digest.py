#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日市场简报生成工具（增强版）
汇总六大模块：大盘概览、趋势研判、板块轮动、市场异动、重要新闻、自选股日报。

用法:
    from tools.daily_digest import generate_daily_digest, get_daily_digest_data
    print(generate_daily_digest())
    print(generate_daily_digest(watchlist=['600519.SH', '300750.SZ']))

CLI:
    python tools/daily_digest.py
    python tools/daily_digest.py --trade_date 20260801
    python tools/daily_digest.py --watchlist 600519.SH,300750.SZ
"""

import logging

try:
    from tools.market_overview import format_market_overview
    from tools.market_trend import format_market_trend
    from tools.abnormal_detector import format_abnormal
    from tools.sector_ranking import get_sector_ranking
    from tools.sector_rotation import get_sector_rotation, get_hot_cold_sectors
    from tools.news_stock_linker import find_news_by_keyword
    from tools.watchlist_report import format_watchlist_report
except ImportError:
    from market_overview import format_market_overview
    from market_trend import format_market_trend
    from abnormal_detector import format_abnormal
    from sector_ranking import get_sector_ranking
    from sector_rotation import get_sector_rotation, get_hot_cold_sectors
    from news_stock_linker import find_news_by_keyword
    from watchlist_report import format_watchlist_report

logger = logging.getLogger(__name__)


def generate_daily_digest(trade_date=None, watchlist=None):
    """生成完整的每日市场简报（Markdown 格式）

    Args:
        trade_date: 交易日期，默认最新
        watchlist: 可选的自选股列表，如 ['600519.SH', '300750.SZ']

    Returns:
        str: Markdown 格式的每日市场简报
    """
    lines = []

    # ─── 一、大盘概览 ───
    try:
        overview = format_market_overview(trade_date)
        lines.append(overview)
    except Exception as e:
        logger.error(f"大盘概览生成失败: {e}")
        lines.append("## 大盘概览\n\n数据暂不可用\n")

    lines.append("")

    # ─── 二、趋势研判 ───
    try:
        trend = format_market_trend(days=5)
        lines.append(trend)
    except Exception as e:
        logger.error(f"趋势研判生成失败: {e}")
        lines.append("## 趋势研判\n\n数据暂不可用\n")

    lines.append("")

    # ─── 三、板块轮动摘要 ───
    lines.append("## 板块轮动摘要")
    lines.append("")

    # 板块排名
    try:
        ranking = get_sector_ranking(
            sector_type='industry', trade_date=trade_date, top_n=10
        )
        lines.append(ranking)
    except Exception as e:
        logger.warning(f"获取板块排名失败: {e}")
        lines.append("板块排名数据暂不可用")

    lines.append("")

    # 资金流入/流出板块
    try:
        rotation = get_sector_rotation(
            sector_type='industry', short_days=3, long_days=10, top_n=5
        )
        lines.append(rotation)
    except Exception as e:
        logger.warning(f"获取板块轮动失败: {e}")
        lines.append("板块轮动数据暂不可用")

    lines.append("")

    # 冷热板块
    try:
        hot_cold = get_hot_cold_sectors(sector_type='industry', days=5)
        lines.append(hot_cold)
    except Exception as e:
        logger.warning(f"获取冷热板块失败: {e}")
        lines.append("冷热板块数据暂不可用")

    lines.append("")

    # ─── 四、市场异动 ───
    try:
        abnormal = format_abnormal(trade_date)
        lines.append(abnormal)
    except Exception as e:
        logger.error(f"异动检测生成失败: {e}")
        lines.append("## 市场异动\n\n数据暂不可用\n")

    lines.append("")

    # ─── 五、重要新闻 ───
    lines.append("## 重要新闻")
    lines.append("")
    try:
        news = find_news_by_keyword("A股", limit=10)
        lines.append(news)
    except Exception as e:
        logger.warning(f"获取新闻失败: {e}")
        lines.append("新闻数据暂不可用")

    lines.append("")

    # ─── 六、自选股日报（可选） ───
    if watchlist:
        try:
            wl_report = format_watchlist_report(watchlist, trade_date)
            lines.append(wl_report)
        except Exception as e:
            logger.warning(f"自选股日报生成失败: {e}")
            lines.append("## 自选股日报\n\n数据暂不可用\n")
        lines.append("")

    # ─── 免责声明 ───
    lines.append("---")
    lines.append("")
    lines.append("> **免责声明**: 以上信息仅供参考，不构成投资建议。投资有风险，入市需谨慎。")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='每日市场简报')
    parser.add_argument('--trade_date', help='交易日期，如 20260801，默认最新')
    parser.add_argument('--watchlist', help='自选股代码，逗号分隔，如 600519.SH,300750.SZ')
    args = parser.parse_args()

    wl = [c.strip() for c in args.watchlist.split(',')] if args.watchlist else None
    print(generate_daily_digest(args.trade_date, wl))
