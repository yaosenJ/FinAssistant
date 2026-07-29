#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投资组合构建脚本 - 供 portfolio-construction Skill 调用
接收评分JSON，输出 Portfolio.json
"""
import sys
import os
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINASSISTANT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR))))
sys.path.insert(0, FINASSISTANT_DIR)
from competition.portfolio_builder import build_portfolio


def run_build(score_results, top_n=8, max_weight=0.20, cash_ratio=0.0):
    portfolio = build_portfolio(score_results, top_n, max_weight, cash_ratio)
    return portfolio


def format_output(portfolio, score_results):
    score_map = {r['ts_code'].split('.')[0]: r for r in score_results}

    output = "## 投资组合配置\n\n"
    output += "| 代码 | 名称 | 综合评分 | 仓位 |\n"
    output += "|------|------|----------|------|\n"

    for symbol, weight in sorted(portfolio.items(), key=lambda x: x[1], reverse=True):
        r = score_map.get(symbol, {})
        name = r.get('name', symbol)
        score = r.get('total_score', 0)
        output += f"| {symbol} | {name} | {score:.1f} | {weight:.2%} |\n"

    output += f"\n**合计仓位:** {sum(portfolio.values()):.2%}\n"
    output += f"**股票数量:** {len(portfolio)}\n"

    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='投资组合构建')
    parser.add_argument('--input', required=True, help='评分结果JSON文件路径')
    parser.add_argument('--top_n', type=int, default=8, help='选取股票数')
    parser.add_argument('--max_weight', type=float, default=0.20, help='单只最大仓位')
    parser.add_argument('--cash_ratio', type=float, default=0.0, help='现金比例')
    parser.add_argument('--output', default=None, help='Portfolio.json输出路径')
    args = parser.parse_args()

    with open(args.input, 'r', encoding='utf-8') as f:
        score_results = json.load(f)

    portfolio = run_build(score_results, args.top_n, args.max_weight, args.cash_ratio)

    print(format_output(portfolio, score_results))
    print("\n---JSON---")
    print(json.dumps(portfolio, ensure_ascii=False, indent=2))

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(portfolio, f, indent=2, ensure_ascii=False)
        print(f"\nPortfolio 已保存: {args.output}")
