#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时爬取东财7x24财经快讯 (stock_info_global_em)
数据源: 东方财富 (Eastmoney)
每次获取最新200条，自动去重追加

字段:
- title: 标题
- digest: 摘要
- publish_time: 发布时间
- url: 链接
- crawl_time: 爬取时间

用法:
    python crawl_news_em.py          # 执行一次爬取
    python crawl_news_em.py loop     # 循环爬取（每30分钟一次）
"""

import json
import os
import sys
import time
import logging
from datetime import datetime

import akshare as ak

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'news')
LOG_DIR = os.path.join(SCRIPT_DIR, '..', 'log')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'crawl_news_em.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

OUTPUT_FILE = os.path.join(DATA_DIR, 'news_em.json')
CRAWL_INTERVAL = 30 * 60  # 30分钟


def load_existing():
    """加载已有数据"""
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_data(data):
    """保存数据"""
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def crawl_once():
    """执行一次爬取，返回新增条数"""
    existing = load_existing()
    # 用 (标题, 发布时间) 去重
    seen = set()
    for item in existing:
        key = (item.get('title', ''), item.get('publish_time', ''))
        seen.add(key)

    try:
        df = ak.stock_info_global_em()
    except Exception as e:
        logger.error(f"调用 stock_info_global_em 失败: {e}")
        return 0

    if df is None or df.empty:
        logger.warning("返回数据为空")
        return 0

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_items = []
    for _, row in df.iterrows():
        title = str(row.get('标题', '')).strip()
        publish_time = str(row.get('发布时间', '')).strip()
        key = (title, publish_time)
        if key in seen:
            continue
        seen.add(key)
        new_items.append({
            'title': title,
            'digest': str(row.get('摘要', '')).strip(),
            'publish_time': publish_time,
            'url': str(row.get('链接', '')).strip(),
            'crawl_time': now,
        })

    if new_items:
        # 新数据放前面，按时间倒序
        all_data = new_items + existing
        save_data(all_data)
        logger.info(f"新增 {len(new_items)} 条，累计 {len(all_data)} 条")
    else:
        logger.info("无新增数据")

    return len(new_items)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'once'

    if mode == 'loop':
        logger.info(f"进入循环模式，间隔 {CRAWL_INTERVAL // 60} 分钟")
        while True:
            try:
                crawl_once()
            except Exception as e:
                logger.error(f"爬取异常: {e}")
            logger.info(f"等待 {CRAWL_INTERVAL // 60} 分钟...")
            time.sleep(CRAWL_INTERVAL)
    else:
        crawl_once()


if __name__ == '__main__':
    main()
