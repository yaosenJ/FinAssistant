#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新闻-行情关联工具
查询新闻标题提及的公司/板块，关联其近期行情走势

功能:
- 按关键词搜索新闻（支持标题/摘要模糊匹配）
- 自动识别新闻标题中提及的个股和板块
- 关联匹配到的个股/板块在新闻日期前后的行情走势

用法:
    from tools.news_stock_linker import search_news_with_market, find_news_by_keyword
    print(search_news_with_market('半导体'))
    print(find_news_by_keyword('贵州茅台', limit=5))
"""

import logging

try:
    from tools.db import get_connection
except ImportError:
    from db import get_connection

logger = logging.getLogger(__name__)


def _get_all_stock_names():
    """获取所有股票名称，用于标题匹配"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT ts_code, stock_name, symbol FROM company_info WHERE stock_name IS NOT NULL")
            return cursor.fetchall()
    finally:
        conn.close()


def _get_all_sector_names(sector_type):
    """获取所有板块名称，用于标题匹配"""
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT DISTINCT sector_code, sector_name FROM {table}")
            return cursor.fetchall()
    finally:
        conn.close()


def _extract_stocks_from_title(title):
    """从新闻标题中提取提及的个股

    Returns:
        list: [(ts_code, stock_name, symbol), ...]
    """
    all_stocks = _get_all_stock_names()
    matched = []
    for ts_code, name, symbol in all_stocks:
        # 名称太短（<=1字）容易误匹配，跳过
        if name and len(name) >= 2 and name in title:
            matched.append((ts_code, name, symbol))
    return matched


def _extract_sectors_from_title(title, sector_type='industry'):
    """从新闻标题中提取提及的板块

    Returns:
        list: [(sector_code, sector_name), ...]
    """
    all_sectors = _get_all_sector_names(sector_type)
    matched = []
    for code, name in all_sectors:
        if name and len(name) >= 2 and name in title:
            matched.append((code, name))
    return matched


def _get_stock_trend(symbol, center_date, days_before=3, days_after=3):
    """获取个股在指定日期前后的行情走势

    Args:
        symbol: 纯数字股票代码
        center_date: 中心日期（新闻日期）
        days_before: 前N个交易日
        days_after: 后N个交易日

    Returns:
        list: [(trade_date, close, pct_chg, amount), ...]
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 获取中心日期之前的数据
            cursor.execute("""
                SELECT trade_date, close, pct_chg, amount
                FROM stock_kline
                WHERE symbol = %s AND trade_date <= %s
                ORDER BY trade_date DESC
                LIMIT %s
            """, (symbol, center_date, days_before + 1))
            before = list(reversed(cursor.fetchall()))

            # 获取中心日期之后的数据
            cursor.execute("""
                SELECT trade_date, close, pct_chg, amount
                FROM stock_kline
                WHERE symbol = %s AND trade_date > %s
                ORDER BY trade_date ASC
                LIMIT %s
            """, (symbol, center_date, days_after))
            after = list(cursor.fetchall())

            return before + after
    finally:
        conn.close()


def _get_sector_trend(sector_code, center_date, sector_type='industry', days_before=3, days_after=3):
    """获取板块在指定日期前后的行情走势"""
    table = 'sector_industry_daily' if sector_type == 'industry' else 'sector_concept_daily'
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT trade_date, close, pct_chg, amount
                FROM {table}
                WHERE sector_code = %s AND trade_date <= %s
                ORDER BY trade_date DESC
                LIMIT %s
            """, (sector_code, center_date, days_before + 1))
            before = list(reversed(cursor.fetchall()))

            cursor.execute(f"""
                SELECT trade_date, close, pct_chg, amount
                FROM {table}
                WHERE sector_code = %s AND trade_date > %s
                ORDER BY trade_date ASC
                LIMIT %s
            """, (sector_code, center_date, days_after))
            after = list(cursor.fetchall())

            return before + after
    finally:
        conn.close()


def _format_trend(trend_data, name, news_date):
    """格式化行情走势为文本"""
    if not trend_data:
        return f"  {name}: 无行情数据\n"

    result = f"  {name}:\n"
    result += f"    {'日期':<12} {'收盘':<10} {'涨跌幅':<10} {'成交额(亿)':<12}\n"
    result += f"    {'-' * 46}\n"

    for row in trend_data:
        date = row[0]
        close = float(row[1] or 0)
        pct = float(row[2] or 0)
        amount = float(row[3] or 0) / 1e8
        marker = " ◀" if date == news_date else ""
        result += f"    {date:<12} {close:<10.2f} {pct:<+10.2f} {amount:<12.2f}{marker}\n"

    # 计算期间涨跌幅
    if len(trend_data) >= 2:
        first_close = float(trend_data[0][1] or 0)
        last_close = float(trend_data[-1][1] or 0)
        if first_close > 0:
            period_chg = (last_close - first_close) / first_close * 100
            result += f"    期间涨跌幅: {period_chg:+.2f}%\n"

    return result


def find_news_by_keyword(keyword, limit=10):
    """
    按关键词搜索新闻（标题或摘要），返回摘要内容

    Args:
        keyword: 搜索关键词
        limit: 返回条数，默认10

    Returns:
        str: 格式化的新闻列表（显示摘要）
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 同时搜 news_em 和 news_ths，取摘要字段
            cursor.execute("""
                SELECT digest, publish_time, '东财' as source
                FROM stock_news.news_em
                WHERE title LIKE %s OR digest LIKE %s
                ORDER BY publish_time DESC
                LIMIT %s
            """, (f'%{keyword}%', f'%{keyword}%', limit))
            news_em = cursor.fetchall()

            cursor.execute("""
                SELECT digest, ctime_str, source
                FROM stock_news.news_ths
                WHERE title LIKE %s OR digest LIKE %s
                ORDER BY ctime_str DESC
                LIMIT %s
            """, (f'%{keyword}%', f'%{keyword}%', limit))
            news_ths = cursor.fetchall()

            # 合并并按时间排序
            all_news = []
            for digest, time_str, source in news_em:
                all_news.append((digest, time_str, source))
            for digest, time_str, source in news_ths:
                all_news.append((digest, time_str, source or '同花顺'))

            # 按时间倒序
            all_news.sort(key=lambda x: x[1] or '', reverse=True)
            all_news = all_news[:limit]

            if not all_news:
                return f"未找到与 \"{keyword}\" 相关的新闻"

            result = f"=== 新闻搜索结果 ===\n"
            result += f"关键词: {keyword}  匹配: {len(all_news)}条\n\n"
            for i, (digest, time_str, source) in enumerate(all_news, 1):
                content = digest if digest else '无摘要'
                result += f"{i}. [{source}] {content}\n"
                result += f"   时间: {time_str}\n"

            return result
    finally:
        conn.close()


def search_news_with_market(keyword, limit=5, days_before=3, days_after=3):
    """
    搜索新闻并关联匹配个股/板块的近期行情走势

    对每条新闻：
    1. 在标题+摘要中匹配公司名称和板块名称
    2. 获取匹配到的个股/板块在新闻日期前后的行情
    3. 输出新闻摘要 + 关联行情走势

    Args:
        keyword: 搜索关键词
        limit: 返回新闻条数，默认5
        days_before: 新闻前N个交易日
        days_after: 新闻后N个交易日

    Returns:
        str: 格式化的新闻+行情关联结果
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 搜索新闻，同时取标题和摘要
            cursor.execute("""
                SELECT title, digest, publish_time, '东财' as source
                FROM stock_news.news_em
                WHERE title LIKE %s OR digest LIKE %s
                ORDER BY publish_time DESC
                LIMIT %s
            """, (f'%{keyword}%', f'%{keyword}%', limit))
            news_em = cursor.fetchall()

            cursor.execute("""
                SELECT title, digest, ctime_str, source
                FROM stock_news.news_ths
                WHERE title LIKE %s OR digest LIKE %s
                ORDER BY ctime_str DESC
                LIMIT %s
            """, (f'%{keyword}%', f'%{keyword}%', limit))
            news_ths = cursor.fetchall()

            all_news = []
            for title, digest, time_str, source in news_em:
                all_news.append((title, digest, time_str, '东财'))
            for title, digest, time_str, source in news_ths:
                all_news.append((title, digest, time_str, source or '同花顺'))

            all_news.sort(key=lambda x: x[2] or '', reverse=True)
            all_news = all_news[:limit]
    finally:
        conn.close()

    if not all_news:
        return f"未找到与 \"{keyword}\" 相关的新闻"

    result = f"=== 新闻-行情关联分析 ===\n"
    result += f"关键词: {keyword}  匹配新闻: {len(all_news)}条\n"

    for i, (title, digest, time_str, source) in enumerate(all_news, 1):
        result += f"\n{'=' * 50}\n"
        result += f"【新闻 {i}】[{source}] {title}\n"
        result += f"摘要: {digest or '无'}\n"
        result += f"时间: {time_str}\n"

        # 提取新闻日期（取前10位作为日期）
        news_date = (time_str or '')[:10]

        # 从标题+摘要中匹配个股和板块
        match_text = f"{title or ''} {digest or ''}"
        matched_stocks = _extract_stocks_from_title(match_text)
        matched_industries = _extract_sectors_from_title(match_text, 'industry')
        matched_concepts = _extract_sectors_from_title(match_text, 'concept')

        if not matched_stocks and not matched_industries and not matched_concepts:
            result += f"  未匹配到具体个股或板块\n"
            continue

        # 关联个股行情
        if matched_stocks:
            result += f"\n【关联个股】\n"
            for ts_code, name, symbol in matched_stocks:
                trend = _get_stock_trend(symbol, news_date, days_before, days_after)
                result += _format_trend(trend, f"{name}({ts_code})", news_date)

        # 关联行业板块行情
        if matched_industries:
            result += f"\n【关联行业板块】\n"
            for code, name in matched_industries:
                trend = _get_sector_trend(code, news_date, 'industry', days_before, days_after)
                result += _format_trend(trend, name, news_date)

        # 关联概念板块行情
        if matched_concepts:
            result += f"\n【关联概念板块】\n"
            for code, name in matched_concepts:
                trend = _get_sector_trend(code, news_date, 'concept', days_before, days_after)
                result += _format_trend(trend, name, news_date)

    return result


if __name__ == '__main__':
    print(find_news_by_keyword('半导体', limit=5))
    print()
    print(search_news_with_market('贵州茅台', limit=3))
