#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
研报数据聚合工具
汇总基本面、估值、技术面、新闻等多维度数据，生成结构化研报数据供 Agent 使用

不调用 LLM，纯数据聚合。Agent 层负责根据返回数据生成研报文本。

功能:
- collect_stock_report_data: 个股研报数据聚合
- collect_industry_report_data: 行业研报数据聚合
- collect_comparison_report_data: 多股对比数据聚合
- collect_event_report_data: 事件影响数据聚合
- save_report: 保存研报为 Markdown 文件

用法:
    from tools.report_generator import collect_stock_report_data
    data = collect_stock_report_data('600519.SH')
"""

import os
import logging

try:
    from tools.stock_fundamental import calc_fundamental_indicators, calc_fundamental_trend
    from tools.stock_valuation import calc_valuation_percentile
    from tools.stock_technical import calc_technical_indicators
    from tools.financial_anomaly import detect_anomalies
    from tools.sector_data import get_stock_sector, get_sector_constituents
    from tools.sector_ranking import get_sector_ranking, get_sector_summary
    from tools.sector_rotation import get_sector_momentum, get_sector_rotation
    from tools.sector_financial_agg import get_sector_financial_agg, get_sector_valuation_stats
    from tools.news_stock_linker import find_news_by_keyword, search_news_with_market
except ImportError:
    from stock_fundamental import calc_fundamental_indicators, calc_fundamental_trend
    from stock_valuation import calc_valuation_percentile
    from stock_technical import calc_technical_indicators
    from financial_anomaly import detect_anomalies
    from sector_data import get_stock_sector, get_sector_constituents
    from sector_ranking import get_sector_ranking, get_sector_summary
    from sector_rotation import get_sector_momentum, get_sector_rotation
    from sector_financial_agg import get_sector_financial_agg, get_sector_valuation_stats
    from news_stock_linker import find_news_by_keyword, search_news_with_market

logger = logging.getLogger(__name__)


def _safe_float(val, default=None):
    """安全转换为 float"""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_str(val, default='--'):
    """安全转换为字符串"""
    if val is None:
        return default
    try:
        return str(val)
    except (ValueError, TypeError):
        return default


def _safe_pct(val, default='--'):
    """安全百分比格式化"""
    if val is None:
        return default
    try:
        return f"{float(val):+.2f}%"
    except (ValueError, TypeError):
        return default


def _safe_pct_abs(val, default='--'):
    """安全百分比格式化（无正负号）"""
    if val is None:
        return default
    try:
        return f"{float(val):.2f}%"
    except (ValueError, TypeError):
        return default


def _get_rating(val, thresholds):
    """根据阈值获取评级"""
    if val is None:
        return '--'
    try:
        val = float(val)
    except (ValueError, TypeError):
        return '--'
    if val > thresholds[0]:
        return '优'
    elif val > thresholds[1]:
        return '良'
    elif val > thresholds[2]:
        return '中'
    else:
        return '差'


def _calc_sector_avg(all_results, sector, detail_key, field_name):
    """计算板块内某指标的平均值"""
    if not all_results:
        return None
    values = []
    for r in all_results:
        if r.get('sector') != sector:
            continue
        val = r.get('details', {}).get(detail_key, {}).get(field_name)
        if val is not None:
            try:
                values.append(float(val))
            except (ValueError, TypeError):
                continue
    return round(sum(values) / len(values), 2) if values else None


def collect_stock_report_data(ts_code):
    """聚合个股全维度研报数据

    Args:
        ts_code: 股票代码，如 600519.SH

    Returns:
        dict: 结构化研报数据，包含 fundamental/valuation/technical/anomaly/sector 等维度
    """
    # 获取股票名称和板块
    sector_info = get_stock_sector(ts_code)
    stock_name = sector_info.get('name', ts_code.split('.')[0]) if isinstance(sector_info, dict) else ts_code.split('.')[0]
    sector = sector_info.get('sector', '未知') if isinstance(sector_info, dict) else '未知'

    # 基本面数据
    fundamental = calc_fundamental_indicators(ts_code)
    fundamental_trend = calc_fundamental_trend(ts_code, periods=4)

    # 估值数据
    valuation = calc_valuation_percentile(ts_code)

    # 技术面数据
    technical = calc_technical_indicators(ts_code)

    # 异常检测
    anomaly = detect_anomalies(ts_code)

    # 板块对比数据
    sector_financial = get_sector_financial_agg(sector, sector_type='industry')
    sector_valuation = get_sector_valuation_stats(sector, sector_type='industry')

    # 评级计算
    fundamental_rating = _rate_fundamental(fundamental)
    valuation_rating = _rate_valuation(valuation)
    technical_rating = _rate_technical(technical)

    return {
        'ts_code': ts_code,
        'name': stock_name,
        'sector': sector,
        'fundamental': fundamental,
        'fundamental_trend': fundamental_trend.get('trend', []) if isinstance(fundamental_trend, dict) else [],
        'valuation': valuation,
        'technical': technical,
        'anomaly': anomaly,
        'sector_financial': sector_financial,
        'sector_valuation': sector_valuation,
        'ratings': {
            'fundamental': fundamental_rating,
            'valuation': valuation_rating,
            'technical': technical_rating,
        },
    }


def collect_industry_report_data(sector_name):
    """聚合板块研报数据

    Args:
        sector_name: 板块名称，如 '白酒'、'半导体'

    Returns:
        dict: 结构化板块研报数据
    """
    # 板块成分股
    constituents = get_sector_constituents(sector_name)

    # 板块排名
    ranking = get_sector_ranking(sector_type='industry', top_n=50)

    # 板块概览
    summary = get_sector_summary(sector_type='industry')

    # 板块轮动
    momentum = get_sector_momentum(sector_type='industry')
    rotation = get_sector_rotation(sector_type='industry')

    # 板块财务聚合
    financial_agg = get_sector_financial_agg(sector_name, sector_type='industry')
    valuation_stats = get_sector_valuation_stats(sector_name, sector_type='industry')

    # 板块内成分股详情
    stock_details = []
    if isinstance(constituents, dict) and 'constituents' in constituents:
        for stock in constituents.get('constituents', [])[:20]:
            code = stock.get('ts_code') or stock.get('symbol', '')
            if code:
                try:
                    fund = calc_fundamental_indicators(code)
                    val = calc_valuation_percentile(code)
                    tech = calc_technical_indicators(code)
                    stock_details.append({
                        'ts_code': code,
                        'name': stock.get('name', ''),
                        'fundamental': fund,
                        'valuation': val,
                        'technical': tech,
                    })
                except Exception as e:
                    logger.warning(f"获取 {code} 数据失败: {e}")

    return {
        'sector_name': sector_name,
        'constituents': constituents,
        'ranking': ranking,
        'summary': summary,
        'momentum': momentum,
        'rotation': rotation,
        'financial_agg': financial_agg,
        'valuation_stats': valuation_stats,
        'stock_details': stock_details,
    }


def collect_comparison_report_data(ts_codes):
    """聚合多股对比研报数据

    Args:
        ts_codes: 股票代码列表，如 ['600519.SH', '000858.SZ', '300750.SZ']

    Returns:
        dict: 结构化对比数据
    """
    stocks = []
    for ts_code in ts_codes:
        sector_info = get_stock_sector(ts_code)
        name = sector_info.get('name', ts_code.split('.')[0]) if isinstance(sector_info, dict) else ts_code.split('.')[0]
        sector = sector_info.get('sector', '未知') if isinstance(sector_info, dict) else '未知'

        fund = calc_fundamental_indicators(ts_code)
        val = calc_valuation_percentile(ts_code)
        tech = calc_technical_indicators(ts_code)
        anomaly = detect_anomalies(ts_code)

        stocks.append({
            'ts_code': ts_code,
            'name': name,
            'sector': sector,
            'fundamental': fund,
            'valuation': val,
            'technical': tech,
            'anomaly': anomaly,
            'ratings': {
                'fundamental': _rate_fundamental(fund),
                'valuation': _rate_valuation(val),
                'technical': _rate_technical(tech),
            },
        })

    return {
        'ts_codes': ts_codes,
        'stock_count': len(stocks),
        'stocks': stocks,
    }


def collect_event_report_data(keyword):
    """聚合事件影响研报数据

    Args:
        keyword: 事件关键词，如 '半导体'、'碳中和'、'贵州茅台'

    Returns:
        dict: 结构化事件影响数据
    """
    # 搜索相关新闻
    news = find_news_by_keyword(keyword, limit=10)
    news_with_market = search_news_with_market(keyword, limit=5)

    return {
        'keyword': keyword,
        'news': news,
        'news_with_market': news_with_market,
    }


def save_report(content, output_path):
    """保存研报为 Markdown 文件

    Args:
        content: 研报文本内容
        output_path: 输出文件路径

    Returns:
        str: 保存的文件路径
    """
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    logger.info(f"研报已保存: {output_path}")
    return output_path


def _rate_fundamental(data):
    """基本面评级"""
    if 'error' in data:
        return '--'
    roe = _safe_float(data.get('ROE'), 0)
    margin = _safe_float(data.get('毛利率'), 0)
    cf_ratio = _safe_float(data.get('经营现金流净利润比'), 0)
    revenue_growth = _safe_float(data.get('营收同比增长率'), 0)

    if roe > 15 and margin > 40 and cf_ratio > 0.8 and revenue_growth > 10:
        return '优秀'
    elif roe > 10 and margin > 30 and cf_ratio > 0.5 and revenue_growth > 0:
        return '良好'
    elif roe > 5 and margin > 20 and cf_ratio > 0:
        return '一般'
    else:
        return '较差'


def _rate_valuation(data):
    """估值评级"""
    if 'error' in data:
        return '--'
    pe_pct = _safe_float(data.get('pe_ttm_percentile'), 50)
    pb_pct = _safe_float(data.get('pb_percentile'), 50)
    pcf_pct = _safe_float(data.get('pcf_percentile'), 50)
    avg_pct = (pe_pct + pb_pct + pcf_pct) / 3

    if avg_pct < 30:
        return '低估'
    elif avg_pct < 50:
        return '合理偏低'
    elif avg_pct < 70:
        return '合理'
    elif avg_pct < 80:
        return '合理偏高'
    else:
        return '高估'


def _rate_technical(data):
    """技术面评级"""
    if 'error' in data:
        return '--'
    ma_trend = data.get('ma_trend', '')
    macd_signal = data.get('macd_signal', '')
    rsi = _safe_float(data.get('rsi6'), 50)

    if ma_trend == '多头排列' and macd_signal == '金叉' and 40 < rsi < 70:
        return '强势'
    elif ma_trend == '多头排列' and macd_signal == '金叉':
        return '偏强'
    elif ma_trend == '多头排列' or macd_signal == '金叉':
        return '偏强'
    elif ma_trend == '空头排列' and macd_signal == '死叉':
        return '弱势'
    elif ma_trend == '空头排列' or macd_signal == '死叉':
        return '偏弱'
    else:
        return '中性'


if __name__ == '__main__':
    print("=" * 60)
    print("研报数据聚合工具测试")
    print("=" * 60)

    # 测试个股数据聚合
    print("\n--- 个股研报数据: 600519.SH ---")
    data = collect_stock_report_data('600519.SH')
    print(f"股票: {data['name']}({data['ts_code']})")
    print(f"板块: {data['sector']}")
    print(f"基本面评级: {data['ratings']['fundamental']}")
    print(f"估值评级: {data['ratings']['valuation']}")
    print(f"技术面评级: {data['ratings']['technical']}")
    print(f"基本面数据: ROE={data['fundamental'].get('ROE')}, 毛利率={data['fundamental'].get('毛利率')}")
    print(f"估值数据: PE_TTM={data['valuation'].get('pe_ttm')}, PB={data['valuation'].get('pb')}")

    # 测试对比数据聚合
    print("\n--- 对比研报数据: 600519.SH vs 000858.SZ ---")
    comp = collect_comparison_report_data(['600519.SH', '000858.SZ'])
    print(f"对比标的数: {comp['stock_count']}")
    for s in comp['stocks']:
        print(f"  {s['name']}: 基本面={s['ratings']['fundamental']}, 估值={s['ratings']['valuation']}")

    print("\n测试完成")
