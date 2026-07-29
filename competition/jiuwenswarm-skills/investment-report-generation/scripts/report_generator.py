#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股研报生成脚本 - 供 investment-report-generation Skill 调用
"""
import sys
import os
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINASSISTANT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR))))
sys.path.insert(0, FINASSISTANT_DIR)
from competition.report_generator import generate_stock_report


def run_generate(ts_code, name, sector, score_result):
    report = generate_stock_report(ts_code, name, sector, score_result)
    return report


def format_output(report):
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='个股研报生成')
    parser.add_argument('--ts_code', required=True, help='股票代码')
    parser.add_argument('--name', required=True, help='股票名称')
    parser.add_argument('--sector', required=True, help='所属板块')
    parser.add_argument('--score_json', required=True, help='评分结果JSON文件路径')
    parser.add_argument('--symbol', default=None, help='6位代码（用于匹配JSON中的key）')
    parser.add_argument('--output_dir', default=None, help='研报输出目录')
    args = parser.parse_args()

    with open(args.score_json, 'r', encoding='utf-8') as f:
        score_data = json.load(f)

    # 支持两种输入格式：单只股票的评分dict，或评分列表
    if isinstance(score_data, list):
        symbol = args.symbol or args.ts_code.split('.')[0]
        score_result = next((r for r in score_data if r['ts_code'].split('.')[0] == symbol), None)
        if not score_result:
            score_result = next((r for r in score_data if r['ts_code'] == args.ts_code), None)
        if not score_result:
            print(f"错误: 未找到 {args.ts_code} 的评分数据")
            sys.exit(1)
    else:
        score_result = score_data

    report = run_generate(args.ts_code, args.name, args.sector, score_result)
    print(format_output(report))
    print("\n---JSON---")
    print(json.dumps({'ts_code': args.ts_code, 'name': args.name, 'report_length': len(report)}, ensure_ascii=False))

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        symbol = args.ts_code.split('.')[0]
        filepath = os.path.join(args.output_dir, f"{symbol}.md")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n研报已保存: {filepath}")
