#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投资组合构建工具
基于多因子打分结果，构建投资组合并校验约束条件

功能:
- build_portfolio: 基于打分结果构建投资组合
- validate_portfolio: 校验组合约束（权重和、单只上限）
- get_portfolio_summary: 组合摘要数据（板块分布、集中度等）

用法:
    from tools.portfolio_builder import build_portfolio, validate_portfolio
    portfolio = build_portfolio(score_results)
    print(validate_portfolio(portfolio))
"""

import logging

logger = logging.getLogger(__name__)


def _safe_float(val, default=0.0):
    """安全转换为 float"""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def build_portfolio(score_results, max_position=0.2, min_score=50, top_n=None):
    """基于打分结果构建投资组合

    策略:
    1. 按综合得分降序排列
    2. 过滤低于 min_score 的股票
    3. 按得分比例分配权重
    4. 约束单只不超过 max_position
    5. 归一化确保权重和为 1

    Args:
        score_results: 打分结果列表，每项需包含 ts_code, total_score, scores, name, sector 等字段
        max_position: 单只股票最大仓位，默认 0.2（20%）
        min_score: 最低入选分数，默认 50
        top_n: 最多入选股票数，None 为不限制

    Returns:
        dict: {symbol: weight, ...} 格式的投资组合
    """
    if not score_results:
        logger.warning("打分结果为空，返回空组合")
        return {}

    # 按总分降序排列
    ranked = sorted(score_results, key=lambda x: _safe_float(x.get('total_score'), 0), reverse=True)

    # 过滤低分股
    candidates = [r for r in ranked if _safe_float(r.get('total_score'), 0) >= min_score]

    if not candidates:
        logger.warning(f"没有得分 >= {min_score} 的股票，返回空组合")
        return {}

    # 限制数量
    if top_n:
        candidates = candidates[:top_n]

    # 按得分比例分配权重
    total_score = sum(_safe_float(r.get('total_score'), 0) for r in candidates)
    if total_score <= 0:
        logger.warning("总分为0，返回空组合")
        return {}

    portfolio = {}
    for r in candidates:
        ts_code = r.get('ts_code', '')
        symbol = ts_code.split('.')[0] if '.' in ts_code else ts_code
        score = _safe_float(r.get('total_score'), 0)
        weight = score / total_score

        # 约束单只上限
        weight = min(weight, max_position)
        portfolio[symbol] = round(weight, 4)

    # 归一化确保权重和为 1
    total_weight = sum(portfolio.values())
    if total_weight > 0:
        portfolio = {k: round(v / total_weight, 4) for k, v in portfolio.items()}

    # 修正浮点误差
    diff = 1.0 - sum(portfolio.values())
    if portfolio and abs(diff) > 0:
        max_key = max(portfolio, key=portfolio.get)
        portfolio[max_key] = round(portfolio[max_key] + diff, 4)

    logger.info(f"组合构建完成: {len(portfolio)} 只股票，权重和={sum(portfolio.values()):.4f}")
    return portfolio


def validate_portfolio(portfolio, max_position=0.2):
    """校验投资组合约束

    Args:
        portfolio: {symbol: weight, ...} 格式
        max_position: 单只股票最大仓位，默认 0.2

    Returns:
        dict: 校验结果，包含 valid(bool)、errors(list)、warnings(list)
    """
    errors = []
    warnings = []

    if not portfolio:
        errors.append("组合为空")
        return {'valid': False, 'errors': errors, 'warnings': warnings}

    # 校验权重和
    total_weight = sum(portfolio.values())
    if abs(total_weight - 1.0) > 0.01:
        errors.append(f"权重和为 {total_weight:.4f}，不等于 1.0")

    # 校验单只上限
    for symbol, weight in portfolio.items():
        if weight > max_position + 0.001:
            errors.append(f"{symbol} 权重 {weight:.4f} 超过上限 {max_position}")
        if weight <= 0:
            warnings.append(f"{symbol} 权重为 {weight:.4f}，不应包含在组合中")

    # 校验负权重
    negative = [s for s, w in portfolio.items() if w < 0]
    if negative:
        errors.append(f"存在负权重: {negative}")

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'stock_count': len(portfolio),
        'total_weight': round(total_weight, 4),
    }


def get_portfolio_summary(portfolio, score_results):
    """获取组合摘要数据

    Args:
        portfolio: {symbol: weight, ...} 格式
        score_results: 打分结果列表

    Returns:
        dict: 组合摘要，包含板块分布、集中度、风险指标等
    """
    score_map = {}
    for r in score_results:
        ts_code = r.get('ts_code', '')
        symbol = ts_code.split('.')[0] if '.' in ts_code else ts_code
        score_map[symbol] = r

    # 构建持仓明细
    holdings = []
    for symbol, weight in sorted(portfolio.items(), key=lambda x: x[1], reverse=True):
        r = score_map.get(symbol, {})
        holdings.append({
            'symbol': symbol,
            'name': r.get('name', symbol),
            'sector': r.get('sector', '未知'),
            'weight': weight,
            'total_score': r.get('total_score', 0),
            'rank': r.get('rank', '--'),
            'sector_rank': r.get('sector_rank', '--'),
            'scores': r.get('scores', {}),
        })

    # 板块分布统计
    sector_stats = {}
    for h in holdings:
        sec = h['sector']
        if sec not in sector_stats:
            sector_stats[sec] = {'count': 0, 'weight': 0.0, 'stocks': []}
        sector_stats[sec]['count'] += 1
        sector_stats[sec]['weight'] += h['weight']
        sector_stats[sec]['stocks'].append(h['symbol'])
    sector_sorted = sorted(sector_stats.items(), key=lambda x: x[1]['weight'], reverse=True)

    # 集中度分析
    weights_sorted = sorted(portfolio.values(), reverse=True)
    top3_weight = sum(weights_sorted[:3]) if len(weights_sorted) >= 3 else sum(weights_sorted)
    top5_weight = sum(weights_sorted[:5]) if len(weights_sorted) >= 5 else sum(weights_sorted)

    max_sector = sector_sorted[0] if sector_sorted else ('', {'weight': 0, 'count': 0})

    return {
        'stock_count': len(portfolio),
        'total_weight': round(sum(portfolio.values()), 4),
        'holdings': holdings,
        'sector_stats': dict(sector_sorted),
        'sector_count': len(sector_stats),
        'top3_weight': round(top3_weight, 4),
        'top5_weight': round(top5_weight, 4),
        'max_sector': max_sector[0],
        'max_sector_weight': round(max_sector[1]['weight'], 4),
        'max_sector_count': max_sector[1]['count'],
        'concentration_risk': '较高' if max_sector[1]['weight'] > 0.4 else '适中' if max_sector[1]['weight'] > 0.25 else '分散',
    }


if __name__ == '__main__':
    print("=" * 60)
    print("投资组合构建工具测试")
    print("=" * 60)

    # 模拟打分结果
    test_scores = [
        {'ts_code': '600519.SH', 'name': '贵州茅台', 'sector': '消费', 'total_score': 68.5, 'rank': 1, 'scores': {}},
        {'ts_code': '300750.SZ', 'name': '宁德时代', 'sector': '新能源', 'total_score': 65.2, 'rank': 2, 'scores': {}},
        {'ts_code': '601899.SH', 'name': '紫金矿业', 'sector': '周期', 'total_score': 63.8, 'rank': 3, 'scores': {}},
        {'ts_code': '000858.SZ', 'name': '五粮液', 'sector': '消费', 'total_score': 62.1, 'rank': 4, 'scores': {}},
        {'ts_code': '600309.SH', 'name': '万华化学', 'sector': '周期', 'total_score': 58.5, 'rank': 5, 'scores': {}},
        {'ts_code': '601318.SH', 'name': '中国平安', 'sector': '金融', 'total_score': 55.0, 'rank': 6, 'scores': {}},
        {'ts_code': '600887.SH', 'name': '伊利股份', 'sector': '消费', 'total_score': 48.0, 'rank': 7, 'scores': {}},  # 低于 min_score
    ]

    # 构建组合
    portfolio = build_portfolio(test_scores, max_position=0.2, min_score=50)
    print(f"\n组合: {portfolio}")
    print(f"权重和: {sum(portfolio.values()):.4f}")

    # 校验组合
    result = validate_portfolio(portfolio)
    print(f"\n校验结果: {result}")

    # 组合摘要
    summary = get_portfolio_summary(portfolio, test_scores)
    print(f"\n组合摘要:")
    print(f"  股票数: {summary['stock_count']}")
    print(f"  板块数: {summary['sector_count']}")
    print(f"  最大板块: {summary['max_sector']}({summary['max_sector_weight']*100:.1f}%)")
    print(f"  集中度: {summary['concentration_risk']}")
    print(f"  前3权重: {summary['top3_weight']*100:.1f}%")

    print("\n测试完成")
