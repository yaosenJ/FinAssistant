#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基本面分析脚本 - 供 stock-fundamental-analysis Skill 调用
"""
import sys
import os
import json
import argparse

# 添加 FinAssistant 到 Python 路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINASSISTANT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR))))  # scripts -> skill -> jiuwenswarm-skills -> competition -> FinAssistant
sys.path.insert(0, FINASSISTANT_DIR)
from tools.stock_fundamental import calc_fundamental_indicators


def run_analysis(ts_code):
    """运行基本面分析"""
    result = calc_fundamental_indicators(ts_code)
    return result


def format_output(result):
    """格式化输出"""
    if 'error' in result:
        return f"分析失败: {result['error']}"

    ts_code = result.get('ts_code', '')
    rd = result.get('report_date', '')
    is_bank = result.get('is_bank', False)

    output = f"## 基本面分析 - {ts_code}\n"
    output += f"报告期: {rd}\n"
    if is_bank:
        output += "类型: 银行股\n"

    output += f"\n| 指标 | 数值 |\n|------|------|\n"

    # 银行股用营业利润率，非银行股用毛利率
    margin_name = '营业利润率' if is_bank else '毛利率'
    metrics = [
        ('ROE', 'ROE', '%'),
        (margin_name, margin_name, '%'),
        ('净利率', '净利率', '%'),
        ('资产负债率', '资产负债率', '%'),
        ('经营现金流/净利润', '经营现金流净利润比', ''),
    ]

    for label, key, suffix in metrics:
        val = result.get(key)
        if val is not None:
            output += f"| {label} | {val}{suffix} |\n"
        else:
            output += f"| {label} | -- |\n"

    output += f"\n**成长性:**\n"
    growth_metrics = [
        ('营收同比增长率', '营收同比增长率'),
        ('净利润同比增长率', '净利润同比增长率'),
        ('营收环比增长率', '营收环比增长率'),
        ('净利润环比增长率', '净利润环比增长率'),
    ]

    for label, key in growth_metrics:
        val = result.get(key)
        if val is not None:
            output += f"- {label}: {val:+.2f}%\n"
        else:
            output += f"- {label}: --\n"

    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='基本面分析')
    parser.add_argument('--ts_code', required=True, help='股票代码，如 600519.SH')
    args = parser.parse_args()

    result = run_analysis(args.ts_code)
    print(format_output(result))
    print("\n---JSON---")
    print(json.dumps(result, ensure_ascii=False, default=str))
