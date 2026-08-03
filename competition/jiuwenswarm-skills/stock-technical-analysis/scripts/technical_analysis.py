#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技术面分析脚本 - 供 stock-technical-analysis Skill 调用
"""
import sys
import os
import json
import argparse

# 添加 FinAssistant 到 Python 路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINASSISTANT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR))))  # scripts -> skill -> jiuwenswarm-skills -> competition -> FinAssistant
sys.path.insert(0, FINASSISTANT_DIR)
from tools.stock_technical import calc_technical_indicators


def run_analysis(ts_code, days=120):
    """运行技术面分析"""
    result = calc_technical_indicators(ts_code, days)
    return result


def format_output(result):
    """格式化输出"""
    if 'error' in result:
        return f"分析失败: {result['error']}"

    ts_code = result.get('ts_code', '')
    trade_date = result.get('trade_date', '')
    close = result.get('close', '')

    output = f"## 技术面分析 - {ts_code}\n"
    output += f"日期: {trade_date}  收盘价: {close}\n"

    # MA 均线
    output += f"\n### 移动平均线\n"
    output += f"| 指标 | 数值 |\n|------|------|\n"
    output += f"| MA5 | {result.get('ma5', '--')} |\n"
    output += f"| MA10 | {result.get('ma10', '--')} |\n"
    output += f"| MA20 | {result.get('ma20', '--')} |\n"
    output += f"| MA60 | {result.get('ma60', '--')} |\n"
    output += f"| MA趋势 | {result.get('ma_trend', '--')} |\n"

    # MACD
    output += f"\n### MACD\n"
    output += f"| 指标 | 数值 |\n|------|------|\n"
    output += f"| DIF | {result.get('macd_dif', '--')} |\n"
    output += f"| DEA | {result.get('macd_dea', '--')} |\n"
    output += f"| MACD柱 | {result.get('macd_hist', '--')} |\n"
    output += f"| 信号 | {result.get('macd_signal', '--')} |\n"

    # RSI
    output += f"\n### RSI\n"
    output += f"| 指标 | 数值 |\n|------|------|\n"
    output += f"| RSI(6) | {result.get('rsi6', '--')} |\n"
    output += f"| RSI(12) | {result.get('rsi12', '--')} |\n"
    output += f"| RSI(24) | {result.get('rsi24', '--')} |\n"
    output += f"| RSI(6)信号 | {result.get('rsi6_signal', '--')} |\n"

    # KDJ
    output += f"\n### KDJ\n"
    output += f"| 指标 | 数值 |\n|------|------|\n"
    output += f"| K | {result.get('kdj_k', '--')} |\n"
    output += f"| D | {result.get('kdj_d', '--')} |\n"
    output += f"| J | {result.get('kdj_j', '--')} |\n"
    output += f"| 信号 | {result.get('kdj_signal', '--')} |\n"

    # 布林带
    output += f"\n### 布林带\n"
    output += f"| 指标 | 数值 |\n|------|------|\n"
    output += f"| 上轨 | {result.get('boll_upper', '--')} |\n"
    output += f"| 中轨 | {result.get('boll_middle', '--')} |\n"
    output += f"| 下轨 | {result.get('boll_lower', '--')} |\n"

    # 动量因子
    output += f"\n### 动量因子\n"
    output += f"| 指标 | 数值 |\n|------|------|\n"
    output += f"| 近5日收益率 | {result.get('pct_5d', '--')}% |\n"
    output += f"| 近10日收益率 | {result.get('pct_10d', '--')}% |\n"
    output += f"| 近20日收益率 | {result.get('pct_20d', '--')}% |\n"
    output += f"| 量比(5/20) | {result.get('vol_ratio', '--')} |\n"
    output += f"| 20日波动率 | {result.get('volatility_20d', '--')}% |\n"

    # 综合研判
    signals = []
    if result.get('ma_trend') == '多头排列':
        signals.append('MA多头排列（偏多）')
    elif result.get('ma_trend') == '空头排列':
        signals.append('MA空头排列（偏空）')

    if result.get('macd_signal') == '金叉':
        signals.append('MACD金叉（偏多）')
    elif result.get('macd_signal') == '死叉':
        signals.append('MACD死叉（偏空）')

    if result.get('rsi6_signal') == '超买':
        signals.append('RSI超买（注意回调）')
    elif result.get('rsi6_signal') == '超卖':
        signals.append('RSI超卖（关注反弹）')

    if result.get('kdj_signal') in ['金叉', '超买', '超卖', '死叉']:
        signals.append(f"KDJ{result['kdj_signal']}")

    if signals:
        output += f"\n**综合信号:** {', '.join(signals)}\n"

    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='技术面分析')
    parser.add_argument('--ts_code', required=True, help='股票代码，如 600519.SH')
    parser.add_argument('--days', type=int, default=120, help='K线天数，默认120')
    args = parser.parse_args()

    result = run_analysis(args.ts_code, args.days)
    print(format_output(result))
    print("\n---JSON---")
    print(json.dumps(result, ensure_ascii=False, default=str))
