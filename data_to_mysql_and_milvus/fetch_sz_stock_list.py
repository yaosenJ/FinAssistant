#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取深交所A股股票列表，保存到本地 JSON 文件

用法:
    python fetch_sz_stock_list.py

输出:
    ../data/sz_stock/sz_stock_list.json
"""

import json
import os
from datetime import datetime

import akshare as ak

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'sz_stock')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'sz_stock_list.json')


def fetch_sz_stock_list():
    """获取深交所A股列表"""
    print("正在获取深交所A股列表...")

    # 获取深交所各类股票
    df_a = ak.stock_info_sz_name_code(symbol="A股列表")
    print(f"  A股列表: {len(df_a)} 条, 列名: {list(df_a.columns)}")

    stocks = []
    for _, row in df_a.iterrows():
        code = str(row.iloc[1]).strip().zfill(6)
        stocks.append({
            'symbol': code,
            'ts_code': f"{code}.SZ",
            'stock_name': str(row.iloc[2]).strip(),
            'list_date': str(row.iloc[3]).strip(),
            'industry': str(row.iloc[6]).strip() if len(row) > 6 else '',
            'market': 'SZ',
        })

    return stocks


def save_to_json(stocks, filepath):
    """保存到JSON文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)
    print(f"已保存到: {filepath}")


def main():
    stocks = fetch_sz_stock_list()
    print(f"获取到 {len(stocks)} 只深交所A股")

    save_to_json(stocks, OUTPUT_FILE)

    # 打印前10只
    print("\n前10只股票:")
    for s in stocks[:10]:
        print(f"  {s['ts_code']}  {s['stock_name']}  行业={s.get('industry', '')}")

    print(f"\n共 {len(stocks)} 只，已保存至 {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
