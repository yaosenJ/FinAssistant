#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
估值分析脚本 - 供 stock-valuation-analysis Skill 调用
"""
import sys
import os
import json
import argparse

# 添加 FinAssistant 到 Python 路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINASSISTANT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR))))  # scripts -> skill -> jiuwenswarm-skills -> competition -> FinAssistant
sys.path.insert(0, FINASSISTANT_DIR)
from tools.stock_valuation import calc_valuation_percentile


def run_analysis(ts_code, days=365):
    """运行估值分析"""
    result = calc_valuation_percentile(ts_code, days)
    return result


def format_output(result):
    """格式化输出"""
    if 'error' in result:
        return f"分析失败: {result['error']}"

    ts_code = result.get('ts_code', '')
    trade_date = result.get('trade_date', '')
    history_days = result.get('history_days', 0)

    output = f"## 估值分析 - {ts_code}\n"
    output += f"日期: {trade_date}  历史数据: 近{history_days}个交易日\n"

    # PE_TTM
    output += f"\n### PE_TTM（滚动市盈率）\n"
    output += f"| 指标 | 数值 |\n|------|------|\n"
    output += f"| 当前值 | {result.get('pe_ttm', '--')} |\n"
    output += f"| 百分位 | {result.get('pe_ttm_percentile', '--')}% |\n"
    output += f"| 估值水平 | {result.get('pe_ttm_level', '--')} |\n"
    output += f"| 历史区间 | {result.get('pe_ttm_min', '--')} ~ {result.get('pe_ttm_max', '--')}（均值{result.get('pe_ttm_avg', '--')}） |\n"

    # PB
    output += f"\n### PB（市净率）\n"
    output += f"| 指标 | 数值 |\n|------|------|\n"
    output += f"| 当前值 | {result.get('pb', '--')} |\n"
    output += f"| 百分位 | {result.get('pb_percentile', '--')}% |\n"
    output += f"| 估值水平 | {result.get('pb_level', '--')} |\n"
    output += f"| 历史区间 | {result.get('pb_min', '--')} ~ {result.get('pb_max', '--')}（均值{result.get('pb_avg', '--')}） |\n"

    # PCF
    output += f"\n### PCF（市现率）\n"
    output += f"| 指标 | 数值 |\n|------|------|\n"
    output += f"| 当前值 | {result.get('pcf', '--')} |\n"
    output += f"| 百分位 | {result.get('pcf_percentile', '--')}% |\n"
    output += f"| 估值水平 | {result.get('pcf_level', '--')} |\n"
    output += f"| 历史区间 | {result.get('pcf_min', '--')} ~ {result.get('pcf_max', '--')}（均值{result.get('pcf_avg', '--')}） |\n"

    # 综合判断
    levels = []
    pe_lv = result.get('pe_ttm_level')
    pb_lv = result.get('pb_level')
    if pe_lv:
        levels.append(f"PE_TTM{pe_lv}")
    if pb_lv:
        levels.append(f"PB{pb_lv}")

    if levels:
        output += f"\n**估值判断:** {', '.join(levels)}\n"

    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='估值分析')
    parser.add_argument('--ts_code', required=True, help='股票代码，如 600519.SH')
    parser.add_argument('--days', type=int, default=365, help='历史天数，默认365')
    args = parser.parse_args()

    result = run_analysis(args.ts_code, args.days)
    print(format_output(result))
    print("\n---JSON---")
    print(json.dumps(result, ensure_ascii=False, default=str))
