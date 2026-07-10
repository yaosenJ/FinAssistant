#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取沪市A股股票列表，保存到本地 JSON 文件

用法:
    python fetch_sh_stock_list.py

输出:
    ../data/sh_stock/sh_stock_list.json
"""

import json
import os
from datetime import datetime

import akshare as ak

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'sh_stock')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'sh_stock_list.json')


def fetch_sh_stock_list():
    """获取沪市主板A股列表"""
    print("正在获取沪市A股列表...")
    df = ak.stock_info_sh_name_code(symbol="主板A股")

    stocks = []
    for _, row in df.iterrows():
        code = str(row['证券代码']).zfill(6)
        stocks.append({
            'symbol': code,
            'ts_code': f"{code}.SH",
            'stock_name': str(row.get('证券简称', '')).strip(),
            'company_name': str(row.get('公司全称', '')).strip() if '公司全称' in row else '',
            'list_date': str(row.get('上市日期', '')) if '上市日期' in row else '',
            'market': 'SH',
        })

    return stocks


def save_to_json(stocks, filepath):
    """保存到JSON文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)
    print(f"已保存到: {filepath}")


def main():
    stocks = fetch_sh_stock_list()
    print(f"获取到 {len(stocks)} 只沪市A股")

    save_to_json(stocks, OUTPUT_FILE)

    # 打印前10只
    print("\n前10只股票:")
    for s in stocks[:10]:
        print(f"  {s['ts_code']}  {s['stock_name']}")

    print(f"\n共 {len(stocks)} 只，已保存至 {OUTPUT_FILE}")



if __name__ == '__main__':
    main()
