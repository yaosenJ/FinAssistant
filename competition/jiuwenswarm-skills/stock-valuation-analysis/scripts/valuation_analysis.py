#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
估值分析脚本 - 供 stock-valuation-analysis Skill 调用
"""
import sys
import os
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINASSISTANT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR))))
sys.path.insert(0, FINASSISTANT_DIR)
from tools.stock_valuation import calc_valuation_percentile


def run_analysis(ts_code, days=365):
    result = calc_valuation_percentile(ts_code, days)
    return result


def format_output(result):
    if 'error' in result:
        return f"分析失败: {result['error']}"

    ts_code = result.get('ts_code', '')
    td = result.get('trade_date', '')

    output = f"## 估值分析 - {ts_code}\n"
    output += f"交易日期: {td}\n\n"

    output += f"| 指标 | 当前值 | 历史分位 | 估值水平 | 1年最低 | 1年最高 | 1年均值 |\n"
    output += f"|------|--------|----------|----------|---------|---------|---------|\n"

    for metric, prefix in [('PE_TTM', 'pe_ttm'), ('PB', 'pb')]:
        val = result.get(prefix)
        pct = result.get(f'{prefix}_percentile')
        level = result.get(f'{prefix}_level')
        vmin = result.get(f'{prefix}_min')
        vmax = result.get(f'{prefix}_max')
        vavg = result.get(f'{prefix}_avg')

        val_s = f"{val:.2f}" if val else '--'
        pct_s = f"{pct:.1f}%" if pct else '--'
        level_s = level or '--'
        min_s = f"{vmin:.2f}" if vmin else '--'
        max_s = f"{vmax:.2f}" if vmax else '--'
        avg_s = f"{vavg:.2f}" if vavg else '--'

        output += f"| {metric} | {val_s} | {pct_s} | {level_s} | {min_s} | {max_s} | {avg_s} |\n"

    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='估值分析')
    parser.add_argument('--ts_code', required=True, help='股票代码')
    parser.add_argument('--days', type=int, default=365, help='历史天数')
    args = parser.parse_args()

    result = run_analysis(args.ts_code, args.days)
    print(format_output(result))
    print("\n---JSON---")
    print(json.dumps(result, ensure_ascii=False, default=str))
