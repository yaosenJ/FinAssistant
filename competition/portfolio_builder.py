# -*- coding: utf-8 -*-
"""
仓位配置生成器
基于选股评分结果，生成 Portfolio.json
"""

import json


def build_portfolio(score_results, top_n=8, max_weight=0.20, cash_ratio=0.0):
    """
    基于评分结果生成仓位配置

    Args:
        score_results: stock_scorer.score_all_stocks() 的返回结果
        top_n: 选取前N只股票，默认8
        max_weight: 单只股票最大仓位，默认20%
        cash_ratio: 现金比例（0.0=满仓，0.3=30%现金）

    Returns:
        dict: {symbol: weight, ...} 格式的 Portfolio
    """
    # 过滤掉评分为0的
    valid = [r for r in score_results if r.get('total_score', 0) > 0]

    if not valid:
        return {}

    # 取 Top N
    selected = valid[:top_n]

    # 按评分加权
    total_score = sum(r['total_score'] for r in selected)
    if total_score <= 0:
        return {}

    investable = 1.0 - cash_ratio  # 可投资比例

    portfolio = {}
    for r in selected:
        symbol = r['ts_code'].split('.')[0]  # 去掉后缀，只保留6位数字
        raw_weight = (r['total_score'] / total_score) * investable
        # 限制单只最大仓位
        weight = min(raw_weight, max_weight)
        portfolio[symbol] = round(weight, 4)

    # 归一化（确保总和 = 1 - cash_ratio）
    total_weight = sum(portfolio.values())
    if total_weight > 0:
        scale = investable / total_weight
        portfolio = {k: round(v * scale, 4) for k, v in portfolio.items()}

    # 修正浮点误差
    diff = round(investable - sum(portfolio.values()), 4)
    if diff != 0 and portfolio:
        max_key = max(portfolio, key=portfolio.get)
        portfolio[max_key] = round(portfolio[max_key] + diff, 4)

    return portfolio


def save_portfolio(portfolio, output_path):
    """保存 Portfolio.json"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(portfolio, f, indent=2, ensure_ascii=False)
    print(f"Portfolio 已保存: {output_path}")
    print(f"  股票数: {len(portfolio)}")
    print(f"  总仓位: {sum(portfolio.values()):.2%}")


def build_full_portfolio(score_results, top_n=8, max_weight=0.20, cash_ratio=0.0):
    """
    生成包含全部股票的持仓比例：入选=top_n只（权重>0），其余权重=0

    Returns:
        dict: {6位代码: 权重, ...} 全部股票，未入选的权重为0
    """
    selected = build_portfolio(score_results, top_n, max_weight, cash_ratio)
    full = {}
    for r in score_results:
        symbol = r['ts_code'].split('.')[0]
        full[symbol] = selected.get(symbol, 0.0)
    return full


def print_portfolio(portfolio, score_results):
    """打印投资组合（全量，权重>0的在前）"""
    score_map = {r['ts_code'].split('.')[0]: r for r in score_results}

    # 分为入选和未入选
    selected = {k: v for k, v in portfolio.items() if v > 0}
    excluded = {k: v for k, v in portfolio.items() if v == 0}

    print(f"\n{'='*60}")
    print(f"投资组合配置（入选{len(selected)}只，共{len(portfolio)}只）")
    print(f"{'='*60}")
    print(f"{'代码':<8} {'名称':<10} {'评分':<8} {'仓位':<10}")
    print(f"{'-'*60}")

    for symbol, weight in sorted(selected.items(), key=lambda x: x[1], reverse=True):
        r = score_map.get(symbol, {})
        name = r.get('name', symbol)
        score = r.get('total_score', 0)
        print(f"{symbol:<8} {name:<10} {score:<8.1f} {weight:<10.2%}")

    if excluded:
        print(f"{'-'*60}")
        print(f"未入选（仓位=0）:")
        for symbol in sorted(excluded.keys()):
            r = score_map.get(symbol, {})
            name = r.get('name', symbol)
            score = r.get('total_score', 0)
            print(f"  {symbol} {name:<10} 评分={score:.1f}")

    print(f"{'-'*60}")
    print(f"{'合计':<8} {'':<10} {'':<8} {sum(portfolio.values()):<10.2%}")
    print(f"{'='*60}")
