#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬取同花顺7x24新闻资讯
数据源: 同花顺 (THS)
日期范围: 2026-01-01 至今

字段:
- id: 新闻ID
- title: 标题
- digest: 摘要
- url: 链接
- tags: 标签列表 [{id, name}]
- stock: 关联股票
- ctime: 发布时间戳
- ctime_str: 发布时间(字符串)
- source: 来源

用法:
    python crawl_news_ths.py
"""

import json
import os
import sys
import time
import random
import logging
from datetime import datetime

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'news')
LOG_DIR = os.path.join(SCRIPT_DIR, '..', 'log')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'crawl_news_ths.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

START_DATE = datetime(2026, 7, 10)
START_TS = int(START_DATE.timestamp())
PAGE_SIZE = 20
REQUEST_DELAY = (0.3, 0.8)
BATCH_PAUSE_SIZE = 50
BATCH_PAUSE_DELAY = (3, 6)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}


def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_news_page(page_num):
    """获取单页新闻"""
    url = f'https://news.10jqka.com.cn/tapp/news/push/stock/?page={page_num}&tag=&track=website&num={PAGE_SIZE}'
    resp = requests.get(url, headers=HEADERS, timeout=15)
    data = resp.json()
    return data.get('data', {}).get('list', [])


def crawl_all_news():
    """爬取2026-01-01至今的全部新闻"""
    logger.info("开始爬取同花顺新闻...")
    logger.info(f"目标日期: {START_DATE.strftime('%Y-%m-%d')} 至今")

    all_news = []
    page = 1
    reached_target = False

    while not reached_target:
        try:
            time.sleep(random.uniform(*REQUEST_DELAY))
            items = fetch_news_page(page)

            if not items:
                logger.info(f"页{page}: 无数据，停止")
                break

            for item in items:
                ts = int(item.get('ctime', 0))
                if ts < START_TS:
                    reached_target = True
                    break

                news = {
                    'id': item.get('id', ''),
                    'title': item.get('title', ''),
                    'digest': item.get('digest', ''),
                    'url': item.get('url', ''),
                    'tags': item.get('tags', []),
                    'stock': item.get('stock', []),
                    'ctime': ts,
                    'ctime_str': datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'),
                    'source': item.get('source', ''),
                }
                all_news.append(news)

            first_ts = int(items[0].get('ctime', 0))
            last_ts = int(items[-1].get('ctime', 0))
            first_dt = datetime.fromtimestamp(first_ts).strftime('%Y-%m-%d %H:%M')
            last_dt = datetime.fromtimestamp(last_ts).strftime('%Y-%m-%d %H:%M')
            logger.info(f"页{page}: {len(items)}条, {first_dt} ~ {last_dt}, 累计{len(all_news)}条")

            page += 1

            if page % BATCH_PAUSE_SIZE == 0:
                delay = random.uniform(*BATCH_PAUSE_DELAY)
                logger.info(f"--- 已处理{page}页，暂停{delay:.1f}秒 ---")
                time.sleep(delay)

        except Exception as e:
            logger.error(f"页{page} 失败: {e}")
            time.sleep(5)
            page += 1

    # 按时间倒序排列
    all_news.sort(key=lambda x: x['ctime'], reverse=True)

    output_file = os.path.join(DATA_DIR, 'news_ths.json')
    save_json(output_file, all_news)
    logger.info(f"完成: 共 {len(all_news)} 条新闻, 保存到 {output_file}")


def main():
    crawl_all_news()


if __name__ == '__main__':
    main()
