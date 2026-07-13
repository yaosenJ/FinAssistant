#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬取行业板块、概念板块成分股
数据源: 新浪财经 (Sina)，东方财富被封，同花顺无成分股API

获取内容:
1. 行业板块列表 (49个) + 每个板块的成分股
2. 概念板块列表 (214个) + 每个板块的成分股

用法:
    python crawl_sector_cons.py industry    # 只爬行业板块
    python crawl_sector_cons.py concept     # 只爬概念板块
    python crawl_sector_cons.py all         # 全部
"""

import json
import os
import sys
import time
import random
import logging
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'sector')
LOG_DIR = os.path.join(SCRIPT_DIR, '..', 'log')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'crawl_sector_cons.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

REQUEST_DELAY = (0.3, 0.8)
BATCH_PAUSE_SIZE = 30
BATCH_PAUSE_DELAY = (2, 5)
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def sina_api(url):
    """调用新浪API"""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.read().decode('utf-8')


def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_sector_nodes():
    """获取新浪所有板块节点"""
    url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodes'
    content = sina_api(url)
    data = json.loads(content)

    def find_nodes(items):
        results = []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, list) and len(item) >= 3:
                    if isinstance(item[2], str) and (item[2].startswith('new_') or item[2].startswith('gn_')):
                        results.append({'name': item[0], 'node': item[2]})
                    results.extend(find_nodes(item))
        return results

    nodes = find_nodes(data)
    industries = [n for n in nodes if n['node'].startswith('new_')]
    concepts = [n for n in nodes if n['node'].startswith('gn_')]
    return industries, concepts


def get_sector_stocks(node_id):
    """获取单个板块的成分股"""
    url = (f'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'
           f'Market_Center.getHQNodeData?num=1000&sort=symbol&asc=1&node={node_id}&symbol=&_s_r_a=page')
    content = sina_api(url)
    data = json.loads(content)
    stocks = []
    for item in data:
        symbol = item.get('symbol', '')
        # 去掉 sh/sz 前缀
        code = symbol[2:] if len(symbol) > 2 else symbol
        market = symbol[:2].upper() if len(symbol) > 2 else ''
        stocks.append({
            'code': code,
            'name': item.get('name', ''),
            'market': market,
            'trade': item.get('trade', ''),
            'changepercent': item.get('changepercent', ''),
            'mktcap': item.get('mktcap', ''),  # 总市值(万)
            'nmc': item.get('nmc', ''),  # 流通市值(万)
            'pe': item.get('pe', ''),  # 市盈率
            'pb': item.get('pb', ''),  # 市净率
        })
    return stocks


def crawl_industry_cons():
    """爬取行业板块成分股"""
    logger.info("获取新浪行业板块列表...")
    industries, _ = get_sector_nodes()
    logger.info(f"行业板块: {len(industries)} 个")

    all_data = []
    total = len(industries)
    for idx, sector in enumerate(industries):
        time.sleep(random.uniform(*REQUEST_DELAY))
        try:
            stocks = get_sector_stocks(sector['node'])
            info = {
                'name': sector['name'],
                'node': sector['node'],
                'stock_count': len(stocks),
                'stocks': stocks,
            }
            all_data.append(info)
            logger.info(f"[{idx+1}/{total}] {sector['name']}: {len(stocks)} 只")
        except Exception as e:
            logger.error(f"[{idx+1}/{total}] {sector['name']} 失败: {e}")

        if (idx + 1) % BATCH_PAUSE_SIZE == 0:
            delay = random.uniform(*BATCH_PAUSE_DELAY)
            logger.info(f"--- 已处理{idx+1}个，暂停{delay:.1f}秒 ---")
            time.sleep(delay)

    save_json(os.path.join(DATA_DIR, 'industry_cons.json'), all_data)
    logger.info(f"行业板块成分股完成: {len(all_data)} 个板块")


def crawl_concept_cons():
    """爬取概念板块成分股"""
    logger.info("获取新浪概念板块列表...")
    _, concepts = get_sector_nodes()
    logger.info(f"概念板块: {len(concepts)} 个")

    all_data = []
    total = len(concepts)
    for idx, sector in enumerate(concepts):
        time.sleep(random.uniform(*REQUEST_DELAY))
        try:
            stocks = get_sector_stocks(sector['node'])
            info = {
                'name': sector['name'],
                'node': sector['node'],
                'stock_count': len(stocks),
                'stocks': stocks,
            }
            all_data.append(info)
            logger.info(f"[{idx+1}/{total}] {sector['name']}: {len(stocks)} 只")
        except Exception as e:
            logger.error(f"[{idx+1}/{total}] {sector['name']} 失败: {e}")

        if (idx + 1) % BATCH_PAUSE_SIZE == 0:
            delay = random.uniform(*BATCH_PAUSE_DELAY)
            logger.info(f"--- 已处理{idx+1}个，暂停{delay:.1f}秒 ---")
            time.sleep(delay)

    save_json(os.path.join(DATA_DIR, 'concept_cons.json'), all_data)
    logger.info(f"概念板块成分股完成: {len(all_data)} 个板块")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if target not in ('industry', 'concept', 'all'):
        print("用法: python crawl_sector_cons.py [industry|concept|all]")
        sys.exit(1)

    if target in ('industry', 'all'):
        crawl_industry_cons()
    if target in ('concept', 'all'):
        crawl_concept_cons()

    logger.info("全部完成!")


if __name__ == '__main__':
    main()
