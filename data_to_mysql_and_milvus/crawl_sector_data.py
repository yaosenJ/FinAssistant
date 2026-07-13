#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬取行业板块、概念板块每日行情指数
数据源: 同花顺 (THS)

获取内容:
1. 行业板块列表 + 每日行情指数 (2026-01-01 ~ 2026-07-10)
2. 概念板块列表 + 每日行情指数 (2026-01-01 ~ 2026-07-10)

字段说明:
- concept_ts_code/industry_ts_code: 板块代码
- concept_name/industry_name: 板块名称
- trade_date: 交易日期
- open: 开盘点位
- close: 收盘点位
- high: 最高点位
- low: 最低点位
- pct_chg: 涨跌幅(%)
- change_data: 涨跌额
- vol: 成交量
- amount: 成交额(万元)
- pct_change: 振幅(%)
- turnover_rate: 换手率(%) (THS不提供，为null)

用法:
    python crawl_sector_data.py industry    # 只爬行业板块
    python crawl_sector_data.py concept     # 只爬概念板块
    python crawl_sector_data.py all         # 全部
"""

import json
import os
import sys
import time
import random
import logging
from datetime import datetime

import akshare as ak
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'sector')
LOG_DIR = os.path.join(SCRIPT_DIR, '..', 'log')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'crawl_sector.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

START_DATE = '2026-01-01'
END_DATE = '2026-07-10'
REQUEST_DELAY = (0.5, 1.5)
BATCH_PAUSE_SIZE = 20
BATCH_PAUSE_DELAY = (3, 6)


def safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_date(val):
    """将各种日期格式统一为 YYYY-MM-DD 字符串"""
    if val is None:
        return ''
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d')
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d')
    return str(val)[:10]


def calc_extra_fields(records):
    """计算涨跌幅、涨跌额、振幅"""
    for i, r in enumerate(records):
        close = r.get('close')
        high = r.get('high')
        low = r.get('low')
        prev_close = records[i-1].get('close') if i > 0 else None

        if prev_close and prev_close != 0 and close is not None:
            r['pct_chg'] = round((close - prev_close) / prev_close * 100, 2)
            r['change_data'] = round(close - prev_close, 2)
        else:
            r['pct_chg'] = None
            r['change_data'] = None

        if prev_close and prev_close != 0 and high is not None and low is not None:
            r['pct_change'] = round((high - low) / prev_close * 100, 2)
        else:
            r['pct_change'] = None

        r['turnover_rate'] = None  # THS不提供换手率
    return records


# ==================== 行业板块 ====================

def crawl_industry_list():
    """获取行业板块列表"""
    logger.info("获取行业板块列表...")
    try:
        df = ak.stock_board_industry_name_ths()
        sectors = []
        for _, row in df.iterrows():
            sectors.append({
                'name': str(row['name']).strip(),
                'code': str(row['code']).strip(),
            })
        logger.info(f"行业板块: {len(sectors)} 个")
        return sectors
    except Exception as e:
        logger.error(f"获取行业板块列表失败: {e}")
        return []


def crawl_industry_index(sector_name):
    """获取单个行业板块的历史指数行情"""
    try:
        df = ak.stock_board_industry_index_ths(symbol=sector_name, start_date='20260101', end_date='20260710')
        if df is None or df.empty:
            return []
        records = []
        for _, row in df.iterrows():
            d = normalize_date(row['日期'])
            records.append({
                'trade_date': d,
                'open': safe_float(row['开盘价']),
                'high': safe_float(row['最高价']),
                'low': safe_float(row['最低价']),
                'close': safe_float(row['收盘价']),
                'vol': int(row['成交量']) if pd.notna(row['成交量']) else None,
                'amount': round(safe_float(row['成交额']) / 10000, 2) if safe_float(row['成交额']) else None,  # 转为万元
            })
        records = [r for r in records if START_DATE <= r['trade_date'] <= END_DATE]
        records = calc_extra_fields(records)
        return records
    except Exception as e:
        logger.warning(f"行业指数 {sector_name} 失败: {e}")
        return []


def crawl_all_industry():
    """爬取全部行业板块数据"""
    sectors = crawl_industry_list()
    if not sectors:
        return

    all_data = []
    total = len(sectors)
    for idx, sector in enumerate(sectors):
        name = sector['name']
        time.sleep(random.uniform(*REQUEST_DELAY))

        index_data = crawl_industry_index(name)
        info = {
            'industry_name': name,
            'industry_ts_code': sector['code'],
            'daily_index': index_data,
        }

        all_data.append(info)
        logger.info(f"[{idx+1}/{total}] {name}: {len(index_data)} 条日线")

        if (idx + 1) % BATCH_PAUSE_SIZE == 0:
            delay = random.uniform(*BATCH_PAUSE_DELAY)
            logger.info(f"--- 已处理{idx+1}个，暂停{delay:.1f}秒 ---")
            time.sleep(delay)

    save_json(os.path.join(DATA_DIR, 'industry_sectors.json'), all_data)
    logger.info(f"行业板块完成: {len(all_data)} 个，保存到 industry_sectors.json")


# ==================== 概念板块 ====================

def crawl_concept_list():
    """获取概念板块列表"""
    logger.info("获取概念板块列表...")
    try:
        df = ak.stock_board_concept_name_ths()
        sectors = []
        for _, row in df.iterrows():
            sectors.append({
                'name': str(row['name']).strip(),
                'code': str(row['code']).strip(),
            })
        logger.info(f"概念板块: {len(sectors)} 个")
        return sectors
    except Exception as e:
        logger.error(f"获取概念板块列表失败: {e}")
        return []


def crawl_concept_index(concept_name):
    """获取单个概念板块的历史指数行情"""
    try:
        df = ak.stock_board_concept_index_ths(symbol=concept_name, start_date='20260101', end_date='20260710')
        if df is None or df.empty:
            return []
        records = []
        for _, row in df.iterrows():
            d = normalize_date(row['日期'])
            records.append({
                'trade_date': d,
                'open': safe_float(row['开盘价']),
                'high': safe_float(row['最高价']),
                'low': safe_float(row['最低价']),
                'close': safe_float(row['收盘价']),
                'vol': int(row['成交量']) if pd.notna(row['成交量']) else None,
                'amount': round(safe_float(row['成交额']) / 10000, 2) if safe_float(row['成交额']) else None,  # 转为万元
            })
        records = [r for r in records if START_DATE <= r['trade_date'] <= END_DATE]
        records = calc_extra_fields(records)
        return records
    except Exception as e:
        logger.warning(f"概念指数 {concept_name} 失败: {e}")
        return []


def crawl_all_concept():
    """爬取全部概念板块数据"""
    sectors = crawl_concept_list()
    if not sectors:
        return

    all_data = []
    total = len(sectors)
    for idx, sector in enumerate(sectors):
        name = sector['name']
        time.sleep(random.uniform(*REQUEST_DELAY))

        index_data = crawl_concept_index(name)
        info = {
            'concept_name': name,
            'concept_ts_code': sector['code'],
            'daily_index': index_data,
        }

        all_data.append(info)
        logger.info(f"[{idx+1}/{total}] {name}: {len(index_data)} 条日线")

        if (idx + 1) % BATCH_PAUSE_SIZE == 0:
            delay = random.uniform(*BATCH_PAUSE_DELAY)
            logger.info(f"--- 已处理{idx+1}个，暂停{delay:.1f}秒 ---")
            time.sleep(delay)

    save_json(os.path.join(DATA_DIR, 'concept_sectors.json'), all_data)
    logger.info(f"概念板块完成: {len(all_data)} 个，保存到 concept_sectors.json")


# ==================== 主入口 ====================

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if target not in ('industry', 'concept', 'all'):
        print("用法: python crawl_sector_data.py [industry|concept|all]")
        sys.exit(1)

    if target in ('industry', 'all'):
        crawl_all_industry()
    if target in ('concept', 'all'):
        crawl_all_concept()

    logger.info("全部完成!")


if __name__ == '__main__':
    main()
