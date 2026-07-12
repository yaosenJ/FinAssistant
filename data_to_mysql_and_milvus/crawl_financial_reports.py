#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬取三大财务报表: 现金流量表、利润表、资产负债表
数据源: 新浪财经 (Sina)
日期范围: 近三年 (2023-2026)

用法:
    python crawl_financial_reports.py sh     # 沪市
    python crawl_financial_reports.py sz     # 深市
    python crawl_financial_reports.py all    # 全部
"""

import json
import os
import sys
import time
import random
import logging
import threading
from datetime import datetime

import akshare as ak
import pandas as pd


def call_with_timeout(func, *args, timeout=30, **kwargs):
    """在子线程中执行函数，超时则返回 None"""
    result = [None]
    error = [None]
    def target():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            error[0] = e
    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        return None
    if error[0]:
        raise error[0]
    return result[0]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, '..', 'log')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'crawl_financial.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

REPORT_TYPES = ['现金流量表', '利润表', '资产负债表']
START_DATE = '20230101'  # 近三年
REQUEST_DELAY = (0.5, 1.5)
BATCH_PAUSE_SIZE = 50
BATCH_PAUSE_DELAY = (3, 6)


def get_stock_list(market):
    """获取股票列表"""
    if market == 'sh':
        kline_dir = os.path.join(SCRIPT_DIR, '..', 'data', 'sh_stock', 'sh_kline')
    else:
        kline_dir = os.path.join(SCRIPT_DIR, '..', 'data', 'sz_stock', 'sz_kline')

    if not os.path.exists(kline_dir):
        return []

    return [f.replace('.json', '') for f in os.listdir(kline_dir) if f.endswith('.json')]


def crawl_single_stock(symbol, market):
    """爬取单只股票的三大报表"""
    result = {}
    for report_type in REPORT_TYPES:
        try:
            df = call_with_timeout(
                ak.stock_financial_report_sina,
                stock=symbol, symbol=report_type,
                timeout=30
            )
            if df is None or df.empty:
                result[report_type] = []
                continue

            # 过滤近三年数据
            df['报告日'] = df['报告日'].astype(str)
            df = df[df['报告日'] >= START_DATE]

            # 转为字典列表
            records = df.to_dict('records')
            result[report_type] = records
        except Exception as e:
            logger.warning(f"{symbol} {report_type} 失败: {e}")
            result[report_type] = []

    return result


def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def process_market(market):
    """处理单个市场"""
    stocks = get_stock_list(market)
    if not stocks:
        logger.error(f"未找到{market}股票列表")
        return

    # 输出目录
    out_dir = os.path.join(SCRIPT_DIR, '..', 'data', f'{market}_stock', f'{market}_financial')
    os.makedirs(out_dir, exist_ok=True)

    total = len(stocks)
    logger.info(f"[{market.upper()}] 共 {total} 只股票需要处理")

    success = 0
    skip = 0
    fail = 0

    for idx, symbol in enumerate(stocks):
        filepath = os.path.join(out_dir, f'{symbol}.json')

        # 检查是否已处理
        if os.path.exists(filepath):
            skip += 1
            continue

        try:
            time.sleep(random.uniform(*REQUEST_DELAY))

            data = crawl_single_stock(symbol, market)
            save_json(filepath, data)
            success += 1

            # 统计
            counts = {k: len(v) for k, v in data.items()}
            logger.info(f"[{idx+1}/{total}] {symbol}: 现金{counts['现金流量表']} 利润{counts['利润表']} 资产{counts['资产负债表']}")

            # 批次暂停
            if (idx + 1) % BATCH_PAUSE_SIZE == 0:
                delay = random.uniform(*BATCH_PAUSE_DELAY)
                logger.info(f"--- 已处理{idx+1}只，暂停{delay:.1f}秒 ---")
                time.sleep(delay)

        except Exception as e:
            fail += 1
            logger.error(f"[{idx+1}/{total}] {symbol} 失败: {e}")

    logger.info(f"[{market.upper()}] 完成: 成功 {success}, 跳过 {skip}, 失败 {fail}, 共 {total}")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if target not in ('sh', 'sz', 'all'):
        print("用法: python crawl_financial_reports.py [sh|sz|all]")
        sys.exit(1)

    if target in ('sh', 'all'):
        process_market('sh')
    if target in ('sz', 'all'):
        process_market('sz')


if __name__ == '__main__':
    main()
