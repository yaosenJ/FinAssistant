#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增量添加估值指标到K线数据
从 stock_zh_valuation_baidu 获取 总市值/市盈率(TTM)/市盈率(静)/市净率/市现率
按日期匹配合并到已有K线JSON文件中

增量处理逻辑:
    1. crawl 脚本检查每只股票最新日期，只爬取之后的新数据，追加到JSON文件
    2. 本脚本检查最近的K线记录是否缺少估值指标，有缺失就从百度股市通获取指标并合并
    3. 只对缺失记录填充指标，已有指标的记录不会被覆盖

配合 crawl 脚本使用:
    python crawl_sh_stock_data.py --mode kline           # 增量爬K线
    python add_indicators_to_kline.py sh                 # 补充估值指标
    # 或一步到位:
    python crawl_sh_stock_data.py --mode kline --add-indicators

独立使用:
    python add_indicators_to_kline.py sh     # 沪市
    python add_indicators_to_kline.py sz     # 深市
    python add_indicators_to_kline.py all    # 全部
"""

import json
import os
import sys
import threading
import time
import random
import logging
from datetime import datetime

import akshare as ak
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, '..', 'log')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'add_indicators.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

INDICATORS = ['总市值', '市盈率(TTM)', '市盈率(静)', '市净率', '市现率']
INDICATOR_KEYS = {
    '总市值': 'total_mv',
    '市盈率(TTM)': 'pe_ttm',
    '市盈率(静)': 'pe_static',
    '市净率': 'pb',
    '市现率': 'pcf',
}
REQUEST_DELAY = (0.3, 0.8)
BATCH_PAUSE_SIZE = 50
BATCH_PAUSE_DELAY = (3, 6)
MAX_RETRIES = 3


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


def load_json(filepath):
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        logger.warning(f"文件损坏，跳过: {filepath}")
        return None


def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_indicators(symbol):
    """获取单只股票的5个估值指标，返回 {日期: {key: value}}"""
    ind_map = {}
    for indicator in INDICATORS:
        try:
            df = call_with_timeout(
                ak.stock_zh_valuation_baidu,
                symbol=symbol, indicator=indicator, period="近一年",
                timeout=30
            )
            if df is not None and not df.empty:
                key = INDICATOR_KEYS[indicator]
                for _, row in df.iterrows():
                    d = str(row['date'])[:10]  # YYYY-MM-DD
                    if d not in ind_map:
                        ind_map[d] = {}
                    val = row['value']
                    ind_map[d][key] = float(val) if pd.notna(val) else None
        except Exception as e:
            logger.warning(f"{symbol} {indicator} 失败: {e}")
    return ind_map


def merge_indicators(kline_data, ind_map):
    """将指标数据按日期合并到K线记录中（仅填充缺失字段）

    流程:
        1. K线记录由 crawl 脚本创建，只有基础字段（trade_date/open/close/high/low/volume/amount）
        2. 本函数按 trade_date 匹配百度股市通的指标数据
        3. 对缺少 pe_ttm 的记录，自动新增字段（pe_ttm/pb/pe_static/pcf/total_mv）并填值
        4. 已有指标字段的记录跳过，不会被覆盖
    """
    updated = 0
    for record in kline_data:
        date = record.get('trade_date', '')[:10]
        if date in ind_map and record.get('pe_ttm') is None:
            for key, val in ind_map[date].items():
                record[key] = val
            updated += 1
    return updated


def needs_indicators(kline_data, check_last=60):
    """检查最近的K线记录是否缺少指标字段"""
    recent = kline_data[-check_last:] if len(kline_data) > check_last else kline_data
    return any(r.get('pe_ttm') is None for r in recent)


def process_single_stock(symbol, filepath, idx=None, total=None):
    """处理单只股票的指标补充，返回 'success' / 'skip' / 'fail'"""
    label = f"[{idx+1}/{total}] " if idx is not None else ""

    existing = load_json(filepath)
    if not existing:
        return 'skip'

    if not needs_indicators(existing):
        return 'skip'

    try:
        time.sleep(random.uniform(*REQUEST_DELAY))

        ind_map = fetch_indicators(symbol)
        if not ind_map:
            logger.warning(f"{label}{symbol} 无指标数据")
            return 'fail'

        updated = merge_indicators(existing, ind_map)
        save_json(filepath, existing)
        logger.info(f"{label}{symbol} 合并 {updated} 条指标")
        return 'success'

    except Exception as e:
        logger.error(f"{label}{symbol} 失败: {e}")
        return 'fail'


def process_market(market):
    """处理单个市场"""
    if market == 'sh':
        kline_dir = os.path.join(SCRIPT_DIR, '..', 'data', 'sh_stock', 'sh_kline')
    else:
        kline_dir = os.path.join(SCRIPT_DIR, '..', 'data', 'sz_stock', 'sz_kline')

    if not os.path.exists(kline_dir):
        logger.error(f"目录不存在: {kline_dir}")
        return

    files = sorted([f for f in os.listdir(kline_dir) if f.endswith('.json')])
    total = len(files)
    logger.info(f"[{market.upper()}] 共 {total} 只股票需要处理")

    success = 0
    skip = 0
    fail = 0

    for idx, filename in enumerate(files):
        symbol = filename.replace('.json', '')
        filepath = os.path.join(kline_dir, filename)

        result = process_single_stock(symbol, filepath, idx, total)
        if result == 'success':
            success += 1
        elif result == 'skip':
            skip += 1
        else:
            fail += 1

        # 批次暂停
        if (idx + 1) % BATCH_PAUSE_SIZE == 0:
            delay = random.uniform(*BATCH_PAUSE_DELAY)
            logger.info(f"--- 已处理{idx+1}只，暂停{delay:.1f}秒 ---")
            time.sleep(delay)

    logger.info(f"[{market.upper()}] 完成: 成功 {success}, 跳过 {skip}, 失败 {fail}, 共 {total}")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if target not in ('sh', 'sz', 'all'):
        print("用法: python add_indicators_to_kline.py [sh|sz|all]")
        sys.exit(1)

    if target in ('sh', 'all'):
        process_market('sh')
    if target in ('sz', 'all'):
        process_market('sz')


if __name__ == '__main__':
    main()
