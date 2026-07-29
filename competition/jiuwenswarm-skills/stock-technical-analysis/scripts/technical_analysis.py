#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技术面分析脚本 - 供 stock-technical-analysis Skill 调用
"""
import sys
import os
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINASSISTANT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR))))
sys.path.insert(0, FINASSISTANT_DIR)
from tools.stock_technical import calc_technical_indicators


def run_analysis(ts_code, days=120):
    result = calc_technical_indicators(ts_code, days)
    return result


def format_output(result):
    if 'error' in result:
        return f"分析失败: {result['error']}"

    ts_code = result.get('ts_code', '')
    close = result.get('close', '--')

    output = f"## 技术面分析 - {ts_code}\n"
    output += f"**最新收盘价:** {close}元\n\n"

    output += f"| 指标 | 数值 | 信号 |\n"
    output += f"|------|------|------|\n"

    ma5 = result.get('ma5', '--')
    ma10 = result.get('ma10', '--')
    ma20 = result.get('ma20', '--')
    ma60 = result.get('ma60', '--')
    output += f"| MA5/10/20/60 | {ma5}/{ma10}/{ma20}/{ma60} | {result.get('ma_trend', '--')} |\n"

    output += f"| MACD(DIF/DEA) | {result.get('macd_dif', '--')}/{result.get('macd_dea', '--')} | {result.get('macd_signal', '--')} |\n"
    output += f"| RSI6/12/24 | {result.get('rsi6', '--')}/{result.get('rsi12', '--')}/{result.get('rsi24', '--')} | {result.get('rsi6_signal', '--')} |\n"
    output += f"| KDJ(K/D/J) | {result.get('kdj_k', '--')}/{result.get('kdj_d', '--')}/{result.get('kdj_j', '--')} | {result.get('kdj_signal', '--')} |\n"

    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='技术面分析')
    parser.add_argument('--ts_code', required=True, help='股票代码')
    parser.add_argument('--days', type=int, default=120, help='K线天数')
    args = parser.parse_args()

    result = run_analysis(args.ts_code, args.days)
    print(format_output(result))
    print("\n---JSON---")
    print(json.dumps(result, ensure_ascii=False, default=str))
